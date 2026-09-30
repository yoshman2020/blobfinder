"""
ShmController
- バックグラウンドスレッドで共有メモリのコマンド領域を監視
- 撮影指令をキューに積み、ワーカースレッドが順次処理
- 処理結果を共有メモリの結果領域に書き戻す
- 最新結果を asyncio キューに流し、WebSocket で配信
"""

import asyncio
import base64
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime
from multiprocessing import shared_memory
from pathlib import Path

import cv2
import numpy as np

from .layout import (
    CMD_SIZE,
    RES_SIZE,
    SHM_NAME,
    TOTAL_SIZE,
    read_json_field,
    write_json_field,
)

logger = logging.getLogger(__name__)

# デフォルトのキュー最大数
DEFAULT_QUEUE_MAX = 10
# コマンド監視間隔 (秒)
POLL_INTERVAL = 0.02  # 50Hz


class ShmController:
    """
    外部から共有メモリ経由で制御を受け付けるコントローラ。

    app.py から以下のように使う:
        shm_ctrl = ShmController(camera_manager, cam_lock, pipeline_dir)
        shm_ctrl.start()
        ...
        shm_ctrl.stop()

    ブラウザ側の現在の pipeline を同期するには:
        shm_ctrl.set_browser_pipeline(pipeline_list)
    """

    def __init__(
        self,
        camera_manager,
        cam_lock: threading.Lock,
        pipeline_dir: Path,
        queue_max: int = DEFAULT_QUEUE_MAX,
    ):
        self._cam_mgr = camera_manager
        self._cam_lock = cam_lock
        self._pipeline_dir = pipeline_dir
        self._queue_max = queue_max

        # 共有メモリ
        self._shm: shared_memory.SharedMemory | None = None

        # 撮影キュー: deque で最大数管理
        self._capture_queue: deque = deque()
        self._queue_lock = threading.Lock()
        self._queue_event = threading.Event()

        # 現在ロード済みの pipeline (shm 指令 or ブラウザ)
        self._pipeline: list | None = None
        self._pipeline_name: str | None = None
        self._pipeline_lock = threading.Lock()

        # 最後に見たコマンドの seq
        self._last_seq: int = -1

        # asyncio イベントループ & 結果配信キュー
        self._loop: asyncio.AbstractEventLoop | None = None
        self._result_subscribers: list[asyncio.Queue] = []
        self._subscribers_lock = threading.Lock()

        # スレッド
        self._poll_thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None
        self._running = False

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def start(self, loop: asyncio.AbstractEventLoop):
        """アプリ起動時に呼ぶ"""
        self._loop = loop
        self._running = True
        try:
            self._shm = shared_memory.SharedMemory(
                name=SHM_NAME, create=True, size=TOTAL_SIZE
            )
            logger.info(
                "shared memory created: %s (%d bytes)", SHM_NAME, TOTAL_SIZE
            )
        except FileExistsError:
            self._shm = shared_memory.SharedMemory(name=SHM_NAME, create=False)
            logger.info("shared memory attached: %s", SHM_NAME)

        # 結果領域を初期化
        self._write_result(
            {
                "status": "idle",
                "error": None,
                "seq": -1,
                "captured_at": None,
                "capture_b64": None,
                "result_b64": None,
                "blobs": None,
            }
        )

        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="shm-poll"
        )
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="shm-worker"
        )
        self._poll_thread.start()
        self._worker_thread.start()

    def stop(self):
        """アプリ終了時に呼ぶ"""
        self._running = False
        self._queue_event.set()
        if self._shm:
            try:
                self._shm.close()
                self._shm.unlink()
            except Exception:  # noqa: BLE001, S110
                pass

    def set_browser_pipeline(self, pipeline: list, name: str = ""):
        """ブラウザ側で選択中の pipeline を同期する"""
        with self._pipeline_lock:
            self._pipeline = pipeline
            self._pipeline_name = name

    def get_status(self) -> dict:
        """現在の状態を返す（REST API 用）"""
        with self._pipeline_lock:
            pname = self._pipeline_name
            plen = len(self._pipeline) if self._pipeline else 0
        with self._queue_lock:
            qlen = len(self._capture_queue)
        # camera が open されていれば撮影可能（ブラウザへの配信有無は問わない）
        camera_ready = self._cam_mgr.camera is not None
        return {
            "camera_ready": camera_ready,
            "pipeline_name": pname,
            "pipeline_steps": plen,
            "queue_length": qlen,
            "queue_max": self._queue_max,
        }

    def subscribe(self) -> asyncio.Queue:
        """WebSocket ハンドラが呼ぶ。結果を受け取る asyncio.Queue を返す"""
        q: asyncio.Queue = asyncio.Queue(maxsize=4)
        with self._subscribers_lock:
            self._result_subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._subscribers_lock:
            try:
                self._result_subscribers.remove(q)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # 内部: コマンド監視ループ
    # ------------------------------------------------------------------

    def _poll_loop(self):
        while self._running:
            try:
                self._poll_once()
            except Exception:
                logger.exception("shm poll error")
            time.sleep(POLL_INTERVAL)

    def _poll_once(self):
        raw = read_json_field(self._shm.buf, 0, CMD_SIZE)  # type: ignore
        if not raw:
            return
        try:
            cmd = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return

        seq = cmd.get("seq", 0)
        if seq == self._last_seq:
            return  # 変化なし
        self._last_seq = seq

        # --- カメラストリーム開始 ---
        if cmd.get("stream_start", 0):
            self._handle_stream_start(seq)

        # --- pipeline 選択 ---
        if cmd.get("pipeline_select", 0):
            self._handle_pipeline_select(cmd.get("pipeline_name", ""), seq)

        # --- 撮影指令 ---
        if cmd.get("capture", 0):
            self._enqueue_capture(seq)

    # ------------------------------------------------------------------
    # 内部: 各指令ハンドラ
    # ------------------------------------------------------------------

    def _handle_stream_start(self, seq: int):
        with self._cam_lock:
            if self._cam_mgr.camera is None:
                ok = self._open_first_camera()
                if not ok:
                    self._write_result(
                        {
                            "status": "error",
                            "error": "カメラに接続できませんでした",
                            "seq": seq,
                            "captured_at": None,
                            "capture_b64": None,
                            "result_b64": None,
                            "blobs": None,
                        }
                    )
                    self._publish_result()
                    return
                logger.info("stream_start: camera opened")
            else:
                logger.debug("stream_start: camera already open")
        # カメラ open 済み（新規・既存問わず）→ ブラウザにストリーム開始を通知
        # ブラウザ側で既にストリーム中なら無視される
        self._publish_event({"event": "stream_start", "seq": seq})

    def _handle_pipeline_select(self, name: str, seq: int):
        # ファイル名に .json が無ければ補完
        filename = name if name.endswith(".json") else name + ".json"
        filepath = self._pipeline_dir / filename
        if not filepath.exists():
            # ファイル名の日本語対応: glob で部分一致検索
            matches = list(self._pipeline_dir.glob("*.json"))
            found = next(
                (p for p in matches if p.stem == name or p.name == name), None
            )
            if found:
                filepath = found
            else:
                self._write_result(
                    {
                        "status": "error",
                        "error": f"pipeline '{name}' が見つかりません",
                        "seq": seq,
                        "captured_at": None,
                        "capture_b64": None,
                        "result_b64": None,
                        "blobs": None,
                    }
                )
                self._publish_result()
                return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._pipeline_lock:
                self._pipeline = data.get("pipeline", [])
                self._pipeline_name = data.get("name", filepath.stem)
            logger.info("pipeline loaded via shm: %s", filepath.name)
            # ブラウザに pipeline 内容を通知して画面表示を更新させる
            self._publish_event(
                {
                    "event": "pipeline_select",
                    "pipeline": self._pipeline,
                    "pipeline_name": self._pipeline_name,
                    "seq": seq,
                }
            )
        except Exception as e:  # noqa: BLE001
            self._write_result(
                {
                    "status": "error",
                    "error": f"pipeline 読み込みエラー: {e}",
                    "seq": seq,
                    "captured_at": None,
                    "capture_b64": None,
                    "result_b64": None,
                    "blobs": None,
                }
            )
            self._publish_result()

    def _enqueue_capture(self, seq: int):
        with self._queue_lock:
            # 最大数を超えたら古いものを削除
            while len(self._capture_queue) >= self._queue_max:
                dropped = self._capture_queue.popleft()
                logger.debug("capture queue full, dropped seq=%s", dropped)
            self._capture_queue.append(seq)
        self._queue_event.set()

    # ------------------------------------------------------------------
    # 内部: ワーカーループ（撮影 + 画像処理）
    # ------------------------------------------------------------------

    def _worker_loop(self):
        while self._running:
            self._queue_event.wait()
            self._queue_event.clear()
            while True:
                with self._queue_lock:
                    if not self._capture_queue:
                        break
                    seq = self._capture_queue.popleft()
                try:
                    self._process_capture(seq)
                except Exception:
                    logger.exception("capture worker error seq=%s", seq)

    def _process_capture(self, seq: int):
        # ストリームされていなければ自動接続
        with self._cam_lock:
            if self._cam_mgr.camera is None:
                ok = self._open_first_camera()
                if not ok:
                    self._write_result(
                        {
                            "status": "error",
                            "error": "カメラに接続できませんでした",
                            "seq": seq,
                            "captured_at": None,
                            "capture_b64": None,
                            "result_b64": None,
                            "blobs": None,
                        }
                    )
                    self._publish_result()
                    return

        # 撮影
        captured_at = datetime.now().isoformat()  # noqa: DTZ005
        with self._cam_lock:
            ok, frame = self._cam_mgr.read()
        if not ok or frame is None:
            self._write_result(
                {
                    "status": "error",
                    "error": "撮影に失敗しました",
                    "seq": seq,
                    "captured_at": captured_at,
                    "capture_b64": None,
                    "result_b64": None,
                    "blobs": None,
                }
            )
            self._publish_result()
            return

        # pipeline 取得
        with self._pipeline_lock:
            pipeline = self._pipeline
            pipeline_name = self._pipeline_name

        if not pipeline:
            self._write_result(
                {
                    "status": "error",
                    "error": "画像処理リストが選択されていません",
                    "seq": seq,
                    "captured_at": captured_at,
                    "capture_b64": self._encode_jpeg(frame),
                    "result_b64": None,
                    "blobs": None,
                }
            )
            self._publish_result()
            return

        # 画像処理
        self._write_result(
            {
                "status": "processing",
                "error": None,
                "seq": seq,
                "captured_at": captured_at,
                "capture_b64": None,
                "result_b64": None,
                "blobs": None,
            }
        )
        self._publish_result()

        try:
            from api.models import ProcessStep
            from processors.pipeline import apply_pipeline

            steps = [
                ProcessStep(type=s["type"], params=s.get("params", {}))
                for s in pipeline
            ]
            result_img, blobs, _ = apply_pipeline(frame, steps)
        except Exception as e:  # noqa: BLE001
            self._write_result(
                {
                    "status": "error",
                    "error": f"画像処理エラー: {e}",
                    "seq": seq,
                    "captured_at": captured_at,
                    "capture_b64": self._encode_jpeg(frame),
                    "result_b64": None,
                    "blobs": None,
                }
            )
            self._publish_result()
            return

        image_id = self._save_capture(frame)
        result_data = {
            "status": "ok",
            "error": None,
            "seq": seq,
            "captured_at": captured_at,
            "capture_b64": self._encode_jpeg(frame),
            "result_b64": self._encode_jpeg(result_img),
            "blobs": blobs or [],
            "pipeline_name": pipeline_name,
            "image_id": image_id,
        }
        self._write_result(result_data)
        self._publish_result()
        logger.info("capture processed seq=%s blobs=%d", seq, len(blobs or []))

    # ------------------------------------------------------------------
    # 内部: ユーティリティ
    # ------------------------------------------------------------------

    def _open_first_camera(self) -> bool:
        """カメラ一覧を取得して先頭に接続（cam_lock 保持中に呼ぶこと）"""
        from camera.discovery import discover_all

        cameras = discover_all()
        if not cameras:
            return False
        return self._cam_mgr.open_uid(cameras[0]["uid"])

    def _save_capture(self, frame: np.ndarray) -> str:
        try:
            import uuid as _uuid
            from pathlib import Path

            upload_dir = Path(__file__).parent.parent / "uploads"
            upload_dir.mkdir(exist_ok=True)
            image_id = str(_uuid.uuid4())
            dst = upload_dir / f"{image_id}.png"
            cv2.imwrite(str(dst), frame)
            return image_id
        except Exception:
            logger.exception("_save_capture error")
            return ""

    def _encode_jpeg(self, img: np.ndarray) -> str:
        """ndarray → base64 JPEG 文字列"""
        if img is None:
            return ""
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buf.tobytes()).decode("ascii")

    def _write_result(self, data: dict):
        """結果 JSON を共有メモリに書く"""
        if self._shm is None:
            return
        try:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            write_json_field(self._shm.buf, CMD_SIZE, RES_SIZE, raw)
        except Exception:
            logger.exception("shm write_result error")

    def _publish_result(self):
        """最新結果を asyncio キューに流す"""
        if self._shm is None or self._loop is None:
            return
        try:
            raw = read_json_field(self._shm.buf, CMD_SIZE, RES_SIZE)
            data = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return
        self._publish_to_subscribers(data)

    def _publish_event(self, data: dict):
        """任意のイベントを asyncio キューに流す（共有メモリ書き込みなし）"""
        if self._loop is None:
            return
        self._publish_to_subscribers(data)

    def _publish_to_subscribers(self, data: dict):
        with self._subscribers_lock:
            subs = list(self._result_subscribers)
        for q in subs:
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, data)  # type: ignore
            except asyncio.QueueFull:
                pass
            except Exception:  # noqa: BLE001, S110
                pass

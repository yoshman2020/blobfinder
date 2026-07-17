import asyncio
import json
import logging
import logging.handlers
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from api.models import ProcessRequest
from camera.discovery import discover_all
from camera.manager import CameraManager
from processors.pipeline import apply_pipeline
from system.system_manager import SystemManager


class CameraOpenRequest(BaseModel):
    uid: str


# Pydantic モデル
class PipelineSaveRequest(BaseModel):
    name: str
    pipeline: list
    overwrite: bool = False  # 上書き保存フラグ


class PipelineLoadRequest(BaseModel):
    name: str


BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
# 設定の保存先ディレクトリ
PIPELINE_DIR = BASE_DIR / "pipelines"
PIPELINE_DIR.mkdir(exist_ok=True)

TTL = 3600  # seconds

# ログ設定: 1MB x 3世代
# ログレベルは環境変数 LOG_LEVEL で変更可能 (DEBUG/INFO/WARNING/ERROR)
_log_level = getattr(
    logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO
)
_log_handler = logging.handlers.RotatingFileHandler(
    BASE_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
)
_log_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(message)s")
)
logging.basicConfig(
    level=_log_level, handlers=[_log_handler, logging.StreamHandler()]
)
logger = logging.getLogger("blobfinder")

system = SystemManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時
    system.initialize()
    yield  # ←ここでアプリ実行中状態
    # 終了時
    system.shutdown()


app = FastAPI(title="Image Processing App", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.middleware("http")
async def _log_requests(request, call_next):
    try:
        response = await call_next(request)
        log = logger.warning if response.status_code >= 400 else logger.debug
        log("%s %s %s", request.method, request.url.path, response.status_code)
        return response
    except Exception as e:
        logger.exception(
            "unhandled error %s %s: %s", request.method, request.url.path, e
        )
        raise


def purge_old_files():
    now = time.time()
    for d in (UPLOAD_DIR, OUTPUT_DIR):
        for f in d.iterdir():
            if now - f.stat().st_mtime > TTL:
                f.unlink(missing_ok=True)
                logger.info("purged %s", f.name)


def imread_safe(path):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={}
    )


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    try:
        purge_old_files()
        ext = Path(file.filename).suffix.lower()  # type: ignore
        if ext not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
            raise HTTPException(status_code=400, detail="unsupported format")
        image_id = str(uuid.uuid4())
        dst = UPLOAD_DIR / f"{image_id}.png"
        content = await file.read()
        dst.write_bytes(content)
        logger.info("upload image_id=%s name=%s", image_id, file.filename)
        return {
            "image_id": image_id,
            "image_url": f"/image/{image_id}",
            "image_name": file.filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("upload error name=%s: %s", file.filename, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/image/{image_id}")
async def get_image(image_id: str):
    path = UPLOAD_DIR / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.get("/result/{image_id}")
async def get_result(image_id: str):
    path = OUTPUT_DIR / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.get("/result_step/{image_id}/{step}")
async def get_intermediate(image_id: str, step: int):
    path = OUTPUT_DIR / f"{image_id}_step_{step}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


def save_any_image_as_png_by_id(
    image, image_id: str, i: int | None, out_dir: Path
):
    path = (
        out_dir / f"{image_id}.png"
        if i is None
        else out_dir / f"{image_id}_step_{i}.png"
    )
    tmp = image
    if tmp.dtype != np.uint8:
        tmp = np.nan_to_num(tmp, nan=0.0, posinf=255.0, neginf=0.0)
        tmp = np.clip(tmp, 0, 255).astype(np.uint8)
    if len(tmp.shape) == 2:
        tmp = cv2.cvtColor(tmp, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(str(path), tmp)


@app.post("/process/{image_id}")
async def process_image(image_id: str, request: ProcessRequest):
    try:
        # 古い画像を削除
        for f in OUTPUT_DIR.glob(f"{image_id}_step_*.png"):
            f.unlink(missing_ok=True)
        result_path = OUTPUT_DIR / f"{image_id}.png"
        result_path.unlink(missing_ok=True)

        src = UPLOAD_DIR / f"{image_id}.png"
        if not src.exists():
            raise HTTPException(status_code=404, detail="image not found")
        img = imread_safe(str(src))
        if img is None:
            raise HTTPException(status_code=500, detail="failed to read image")
        result, blobs, intermediates = apply_pipeline(img, request.pipeline)
        if result is None:
            logger.warning("process failed image_id=%s", image_id)
            raise HTTPException(
                status_code=400, detail="invalid processing parameters"
            )
        save_any_image_as_png_by_id(result, image_id, None, OUTPUT_DIR)

        intermediate_urls = []
        for i, im in enumerate(intermediates):
            save_any_image_as_png_by_id(im, image_id, i, OUTPUT_DIR)
            intermediate_urls.append(f"/result_step/{image_id}/{i}")

        logger.info(
            "process done image_id=%s blobs=%d", image_id, len(blobs or [])
        )
        return {
            "success": True,
            "result_url": f"/result/{image_id}",
            "intermediate_urls": intermediate_urls,
            "blobs": blobs or [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("process error image_id=%s: %s", image_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{image_id}")
async def download_result(image_id: str):
    path = OUTPUT_DIR / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(
        path,
        media_type="image/png",
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "log_level": logging.getLevelName(logger.getEffectiveLevel()),
    }


@app.post("/log-level/{level}")
async def set_log_level(level: str):
    lv = getattr(logging, level.upper(), None)
    if lv is None:
        raise HTTPException(status_code=400, detail=f"invalid level: {level}")
    logging.getLogger().setLevel(lv)
    logger.setLevel(lv)
    logger.info("log level changed to %s", level.upper())
    return {"log_level": level.upper()}


@app.delete("/image/{image_id}")
async def delete_image(image_id: str):
    for d in (UPLOAD_DIR, OUTPUT_DIR):
        (d / f"{image_id}.png").unlink(missing_ok=True)
    return {"success": True}


# ===== 設定 保存・読み込み =====


@app.post("/api/pipelines/save")
@app.post("/api/pipelines/save")
async def save_pipeline(request: PipelineSaveRequest):
    """現在の設定を名前付きで保存（上書き対応）"""
    try:
        safe_name = "".join(
            c if c.isalnum() or c == "_" else "_" for c in request.name
        )
        if not safe_name:
            raise ValueError("Invalid pipeline name")

        filepath = PIPELINE_DIR / f"{safe_name}.json"

        # 既存ファイルがあり、上書きでない場合は番号を追加
        if filepath.exists() and not request.overwrite:
            counter = 2
            while True:
                new_safe_name = f"{safe_name}({counter})"
                filepath = PIPELINE_DIR / f"{new_safe_name}.json"
                if not filepath.exists():
                    safe_name = new_safe_name
                    break
                counter += 1

        data = {
            "name": safe_name,  # 表示名もファイル名も統一
            "pipeline": request.pipeline,
            "saved_at": datetime.now().isoformat(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Pipeline saved: {filepath}")
        return {
            "success": True,
            "filename": filepath.name,
            "name": safe_name,  # 実際に保存された名前を返す
            "saved_at": data["saved_at"],
        }
    except Exception as e:
        logger.exception("Failed to save pipeline")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/pipelines/check-exists")
async def check_exists(request: dict):
    """ファイルが既に存在するか確認"""
    try:
        name = request.get("name", "")
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        filepath = PIPELINE_DIR / f"{safe_name}.json"

        return {"exists": filepath.exists(), "safe_name": safe_name}
    except Exception as e:
        logger.exception("Failed to check pipeline existence")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipelines/load")
async def load_pipeline(request: PipelineLoadRequest):
    """保存された設定を読み込み"""
    try:
        filepath = PIPELINE_DIR / request.name
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Pipeline not found")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Pipeline loaded: {filepath}")
        return {
            "success": True,
            "pipeline": data.get("pipeline", []),
            "name": data.get("name", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to load pipeline")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pipelines/list")
async def list_pipelines():
    """保存された設定の一覧を取得"""
    try:
        pipelines = []
        for filepath in sorted(PIPELINE_DIR.glob("*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pipelines.append(
                    {
                        "filename": filepath.name,
                        "name": data.get("name", filepath.stem),
                        "saved_at": data.get("saved_at", ""),
                        "steps": len(data.get("pipeline", [])),
                    }
                )
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON: {filepath}")
                continue
        return {"success": True, "pipelines": pipelines}
    except Exception as e:
        logger.exception("Failed to list pipelines")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 設定 エクスポート・インポート =====


@app.get("/api/pipelines/export/{filename}")
async def export_pipeline(filename: str):
    """設定をJSONファイルとしてダウンロード"""
    try:
        filepath = PIPELINE_DIR / filename

        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Pipeline not found")

        return FileResponse(
            filepath, media_type="application/json", filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to export pipeline")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipelines/import")
async def import_pipeline(file: UploadFile = File(...)):
    """JSONファイルから設定をインポート"""
    try:
        # ファイル名を安全にする
        safe_filename = "".join(
            c if c.isalnum() or c in "._-" else "_" for c in file.filename
        )
        if not safe_filename.endswith(".json"):
            safe_filename += ".json"

        # ファイル内容を読み込み
        content = await file.read()
        data = json.loads(content.decode("utf-8"))

        # 検証：必須フィールドの確認
        if "pipeline" not in data or not isinstance(data["pipeline"], list):
            raise ValueError("Invalid pipeline format")

        # 保存
        filepath = PIPELINE_DIR / safe_filename
        if filepath.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = PIPELINE_DIR / f"{filepath.stem}_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Pipeline imported: {filepath}")
        return {
            "success": True,
            "filename": filepath.name,
            "name": data.get("name", filepath.stem),
            "pipeline": data.get("pipeline", []),
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.exception("Failed to import pipeline")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/pipelines/{filename}")
async def delete_pipeline(filename: str):
    """保存された設定を削除"""
    try:
        filepath = PIPELINE_DIR / filename

        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Pipeline not found")

        filepath.unlink()
        logger.info(f"Pipeline deleted: {filepath}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete pipeline")
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# Camera
# =====================

_cam_lock = threading.Lock()

camera_manager = CameraManager()

_fps_stat = {"fps": 0.0, "count": 0, "t": 0.0}

# カメラパラメータ定義
_CAM_PARAMS = [
    "width",
    "height",
    "fps",
    "gain",
    "exposure",
]


@app.get("/cameras")
async def list_cameras():
    """利用可能なカメラインデックスを返す（最大8台試行）"""
    try:
        return {"cameras": discover_all()}
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/camera/open/{uid}")
async def open_camera(uid: str):
    try:
        with _cam_lock:
            ok = camera_manager.open_uid(uid)
        if not ok:
            raise HTTPException(status_code=400, detail="cannot open camera")
        logger.info("camera opened uid=%s", uid)
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("open camera error uid=%s: %s", uid, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/camera/close")
async def close_camera():
    logger.info("camera closed")
    with _cam_lock:
        camera_manager.close()
    return {"success": True}


def _gen_frames():
    global _fps_stat
    _fps_stat = {"fps": 0.0, "count": 0, "t": time.time()}
    frame_skip = 0

    while True:
        with _cam_lock:
            if camera_manager.camera is None:
                break
            ok, frame = camera_manager.read()
        if not ok or frame is None:
            break

        # Skip every Nth frame if needed
        frame_skip += 1
        if frame_skip % 2 == 0:  # Encode every 2nd frame
            continue

        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        update_fps()

        # Consider reducing quality further or using H.264 encoding
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        yield (
            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            + buf.tobytes()
            + b"\r\n"
        )


@app.get("/camera/fps")
async def get_fps():
    return {"fps": _fps_stat["fps"]}


@app.get("/camera/params")
async def get_camera_params():
    if camera_manager.camera is None:
        raise HTTPException(status_code=400, detail="No camera open")
    try:
        result = {}
        with _cam_lock:
            for name in _CAM_PARAMS:
                try:
                    val = camera_manager.camera.get_param(name)
                    result[name] = (
                        round(val, 4) if isinstance(val, (int, float)) else val
                    )
                except Exception:
                    result[name] = None
        return result

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/camera/params")
async def set_camera_params(params: dict):
    try:
        if camera_manager.camera is None:
            raise HTTPException(status_code=400, detail="No camera open")
        applied = {}
        with _cam_lock:
            for k, v in params.items():
                camera_manager.camera.set_param(k, v)
                applied[k] = camera_manager.camera.get_param(k)
        logger.debug("camera params applied: %s", applied)
        return {"applied": applied}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("set camera params error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/camera/stream")
async def camera_stream():
    if camera_manager.camera is None:
        raise HTTPException(status_code=400, detail="No camera open")
    return StreamingResponse(
        _gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


def update_fps():
    global _fps_stat

    _fps_stat["count"] += 1
    now = time.time()
    elapsed = now - _fps_stat["t"]

    if elapsed >= 1.0:
        _fps_stat["fps"] = round(_fps_stat["count"] / elapsed, 1)
        _fps_stat["count"] = 0
        _fps_stat["t"] = now


@app.websocket("/camera/stream/ws")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")

    try:
        while True:
            with _cam_lock:
                if camera_manager.camera is None:
                    break
                ok, frame = camera_manager.read()

            if not ok or frame is None:
                break

            if len(frame.shape) == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            # FPS計測
            update_fps()

            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            await websocket.send_bytes(buf.tobytes())
            await asyncio.sleep(0.001)  # Small delay to prevent CPU spinning
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


@app.post("/camera/capture")
async def camera_capture():
    """現在のフレームをキャプチャしてアップロード画像として保存"""
    try:
        with _cam_lock:
            if camera_manager.camera is None:
                raise HTTPException(status_code=400, detail="No camera open")
            ok, frame = camera_manager.read()
        if not ok or frame is None:
            raise HTTPException(status_code=500, detail="Capture failed")
        purge_old_files()
        image_id = str(uuid.uuid4())
        dst = UPLOAD_DIR / f"{image_id}.png"
        cv2.imwrite(str(dst), frame)
        logger.info("capture image_id=%s", image_id)
        return {
            "image_id": image_id,
            "image_url": f"/image/{image_id}",
            "image_name": f"capture_{image_id[:8]}.png",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("capture error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

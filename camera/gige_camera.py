# camera/gige_camera.py

import logging
import queue
import threading

try:
    import gi

    gi.require_version("Aravis", "0.8")
    from gi.repository import Aravis

except ImportError:
    gi = None
import numpy as np
from numpy import ndarray

from .base import CameraBase

logger = logging.getLogger(__name__)


class GigEVisionCamera(CameraBase):
    """GigE Visionカメラの制御クラス（連続ストリーミング対応）"""

    # Aravisのプロパティマッピング
    PARAMS = {
        "width": "Width",
        "height": "Height",
        "fps": "AcquisitionFrameRate",
        "brightness": "Brightness",
        "contrast": "Contrast",
        "saturation": "Saturation",
        "gain": "Gain",
        "exposure": "ExposureTime",
        "autofocus": "AutoFocus",
    }

    # バッファ設定
    BUFFER_COUNT = 8
    TIMEOUT_US = 2000000  # 2秒
    FRAME_QUEUE_SIZE = 4  # キュー内に保持するフレーム数

    @classmethod
    def initialize(cls):
        """初期化（デバイスリスト更新）"""
        if gi is None:
            logger.debug("Aravis library not available.")
            return
        Aravis.update_device_list()

    @classmethod
    def shutdown(cls):
        """シャットダウン処理"""
        pass

    @classmethod
    def get_camera_names(cls) -> dict[str, str]:
        """利用可能なカメラを取得"""
        if gi is None:
            return {}
        names: dict[str, str] = {}
        try:
            n_devices = Aravis.get_n_devices()
            for i in range(n_devices):
                device_id = Aravis.get_device_id(i)
                device_address = Aravis.get_device_address(i)
                names[device_id] = f"{device_id} ({device_address})"
        except Exception as e:
            logger.debug(f"Error getting camera names: {e}")
        return names

    @classmethod
    def discover(cls) -> list[dict]:
        """カメラの発見"""
        if gi is None:
            return []
        cls.initialize()
        cameras = []
        cam_names = cls.get_camera_names()

        try:
            n_devices = Aravis.get_n_devices()
            for i in range(n_devices):
                device_id = Aravis.get_device_id(i)
                cameras.append(
                    {
                        "type": "gige",
                        "serial": device_id,
                        "name": cam_names.get(device_id) or f"GigE Camera {i}",
                    }
                )
        except Exception as e:
            logger.debug(f"Error discovering cameras: {e}")

        return cameras

    def __init__(self):
        self.camera = None
        self.stream = None
        self.buffer_count = 0

        # ストリーミング制御用
        self._streaming = False
        self._stream_thread = None
        self._stop_event = threading.Event()
        self._frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE)

        # 統計情報
        self._stats = {
            "completed_buffers": 0,
            "failed_buffers": 0,
            "underrun_buffers": 0,
        }

    def open(self, serial: str) -> bool:
        """カメラを開く"""
        if gi is None:
            return False
        try:
            logger.debug(f"Opening GigE camera: {serial}")
            # Aravis.Camera.new(device_id) を使用
            self.camera = Aravis.Camera.new(serial)

            if not self.camera:
                logger.debug(f"Failed to open camera: {serial}")
                return False

            logger.debug("Camera opened successfully.")

            # ピクセルフォーマット確認
            try:
                pixfmt = self.camera.get_string("PixelFormat")
                logger.debug(f"Current PixelFormat: {pixfmt}")
            except:
                pass

            # 解像度確認
            try:
                width = self.camera.get_integer("Width")
                height = self.camera.get_integer("Height")
                logger.debug(f"Camera resolution: {width}x{height}")
            except:
                pass

            # triggerMode = self.camera.get_string("TriggerMode")
            # logger.debug(f"TriggerMode={triggerMode}")
            # acquisitionMode = self.camera.get_string("AcquisitionMode")
            # logger.debug(f"AcquisitionMode={acquisitionMode}")
            # self.camera.set_string("TriggerMode", "Off")
            # self.camera.set_string("AcquisitionMode", "Continuous")

            self.camera.set_integer("Width", 640)
            self.camera.set_integer("Height", 480)

            # ストリーム作成
            self.stream = self.camera.create_stream(None, None)
            if not self.stream:
                logger.debug("Failed to create stream")
                self.camera = None
                return False

            # ペイロードサイズ取得
            payload = self.camera.get_payload()
            logger.debug(f"Payload size: {payload} bytes")

            # バッファ準備
            logger.debug(f"Pushing {self.BUFFER_COUNT} buffers...")
            for _ in range(self.BUFFER_COUNT):
                buffer = Aravis.Buffer.new_allocate(payload)
                self.stream.push_buffer(buffer)
            self.buffer_count = self.BUFFER_COUNT
            logger.debug("Buffers pushed.")

            # 取得開始
            logger.debug("Starting acquisition...")
            self.camera.start_acquisition()
            logger.debug("Acquisition started.")

            # ストリーミングスレッド開始
            self._stop_event.clear()
            self._streaming = True
            self._stream_thread = threading.Thread(
                target=self._streaming_loop, daemon=True
            )
            self._stream_thread.start()
            logger.debug("Streaming thread started.")

            return True

        except Exception as e:
            logger.debug(f"Error opening camera: {e}")
            import traceback

            traceback.print_exc()
            return False

    def close(self):
        """カメラを閉じる"""
        if gi is None:
            return
        try:
            # ストリーミング停止
            if self._streaming:
                logger.debug("Stopping streaming thread...")
                self._stop_event.set()
                self._streaming = False

                if self._stream_thread:
                    self._stream_thread.join(timeout=5)
                    self._stream_thread = None

                logger.debug("Streaming thread stopped.")

            if self.camera:
                logger.debug("Stopping acquisition...")
                self.camera.stop_acquisition(None)
                logger.debug("Acquisition stopped.")

            if self.stream:
                self.stream = None

            if self.camera:
                self.camera = None

            # キューをクリア
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    break

            logger.debug("Camera closed.")
            self._print_stats()

        except Exception as e:
            logger.debug(f"Error closing camera: {e}")

    def read(self) -> tuple[bool, ndarray | None]:
        """フレーム取得（キューからポップ）"""
        try:
            if not self._streaming:
                return False, None

            # キューからフレームを取得（ブロッキング）
            frame = self._frame_queue.get(timeout=2.0)
            # logger.debug(f"frame.shape={frame.shape}")
            return True, frame

        except queue.Empty:
            return False, None
        except Exception as e:
            logger.debug(f"Error reading frame: {e}")
            return False, None

    def _streaming_loop(self):
        """ストリーミングスレッドのメインループ"""
        if gi is None:
            logger.debug(
                "Aravis library not available. Streaming loop cannot start."
            )
            return
        logger.debug("Streaming loop started.")

        while not self._stop_event.is_set():
            try:
                if not self.stream:
                    break

                # バッファ取得（タイムアウト付き）
                # try_pop_buffer() または timeout_pop_buffer() を使用
                # buffer = self.stream.try_pop_buffer()
                buffer = self.stream.timeout_pop_buffer(2000000)

                if not buffer:
                    self._stats["underrun_buffers"] += 1
                    if self._stats["underrun_buffers"] % 10 == 0:
                        logger.debug(
                            f"Buffer underrun: {self._stats['underrun_buffers']} times"
                        )
                    continue

                # バッファステータス確認
                try:
                    status = buffer.get_status()
                    # logger.debug(f"status={status}")
                    if status != Aravis.BufferStatus.SUCCESS:
                        self._stats["failed_buffers"] += 1
                        self.stream.push_buffer(buffer)
                        continue
                except:
                    pass

                # 画像情報取得
                width = buffer.get_image_width()
                height = buffer.get_image_height()
                pixel_format = buffer.get_image_pixel_format()

                # バッファデータ取得
                data = buffer.get_data()
                # logger.debug(f"type(data)={type(data)}")
                # logger.debug(f"len(data)={len(data)}")
                # logger.debug(f"data={data}")

                # ピクセルフォーマットに応じてNumPy配列に変換
                frame = self._buffer_to_ndarray(
                    data, width, height, pixel_format
                )

                if frame is not None:
                    self._stats["completed_buffers"] += 1

                    # キューにフレームを追加（満杯の場合は古いフレームを削除）
                    try:
                        self._frame_queue.put_nowait(frame)
                    except queue.Full:
                        # キューが満杯の場合、古いフレームを削除して新しいフレームを追加
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self._frame_queue.put_nowait(frame)

                    # 30フレームごとに統計情報を出力
                    if self._stats["completed_buffers"] % 30 == 0:
                        logger.debug(
                            f"[{self._stats['completed_buffers']}] Frame: {width}x{height}"
                        )

                # バッファを再利用キューに戻す
                self.stream.push_buffer(buffer)

            except Exception as e:
                logger.debug(f"Error in streaming loop: {e}")
                break

        logger.debug("Streaming loop stopped.")

    def _buffer_to_ndarray(
        self, data: bytes, width: int, height: int, pixel_format: int
    ) -> ndarray | None:
        """バッファをNumPy配列に変換"""
        try:
            # logger.debug(
            #     f"len(data)={len(data)},width={width},height={height},pixel_format={pixel_format}"
            # )

            # ピクセルフォーマットのビット深度を取得
            bits_per_pixel = (pixel_format >> 16) & 0xFF

            # Mono8
            if bits_per_pixel == 8:
                frame = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width)
                )
                return frame

            # Mono16
            elif bits_per_pixel == 16:
                frame = np.frombuffer(data, dtype=np.uint16).reshape(
                    (height, width)
                )
                return frame

            # RGB8 (24-bit)
            elif bits_per_pixel == 24:
                frame = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width, 3)
                )
                # BGRに変換（OpenCV互換）
                return frame[:, :, ::-1]

            # RGB16 (48-bit)
            elif bits_per_pixel == 48:
                frame = np.frombuffer(data, dtype=np.uint16).reshape(
                    (height, width, 3)
                )
                return frame

            # Bayer パターン（CFA処理必要）
            elif "Bayer" in str(pixel_format) or pixel_format & 0x01000000:
                bayer = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width)
                )
                try:
                    import cv2

                    frame = cv2.cvtColor(bayer, cv2.COLOR_BAYER_RG2BGR)
                    return frame
                except:
                    return bayer

            # その他
            else:
                # グレースケールとして扱う
                frame = np.frombuffer(data, dtype=np.uint8).reshape(
                    (height, width)
                )
                return frame

        except Exception as e:
            logger.debug(f"Error converting buffer to ndarray: {e}")
            return None

    def get_param(self, name: str) -> float | None:
        """パラメータ取得"""
        try:
            if not self.camera or name not in self.PARAMS:
                return None

            param_name = self.PARAMS[name]

            # 整数パラメータ
            if name in ["width", "height"]:
                value = self.camera.get_integer(param_name)
            # 浮動小数点パラメータ
            else:
                value = self.camera.get_float(param_name)

            return float(value) if value is not None else None

        except Exception as e:
            logger.debug(f"Error getting parameter {name}: {e}")
            return None

    def set_param(self, name: str, value) -> bool:
        """パラメータ設定"""
        try:
            if not self.camera or name not in self.PARAMS:
                return False

            param_name = self.PARAMS[name]

            # 整数パラメータ
            if name in ["width", "height"]:
                self.camera.set_integer(param_name, int(value))
            # 浮動小数点パラメータ
            else:
                self.camera.set_float(param_name, float(value))

            return True

        except Exception as e:
            logger.debug(f"Error setting parameter {name}: {e}")
            return False

    def _print_stats(self):
        """統計情報を出力"""
        logger.debug("\nStreaming Statistics:")
        logger.debug(f"  Completed buffers: {self._stats['completed_buffers']}")
        logger.debug(f"  Failed buffers: {self._stats['failed_buffers']}")
        logger.debug(f"  Underrun buffers: {self._stats['underrun_buffers']}")

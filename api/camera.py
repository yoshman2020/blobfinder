import asyncio
import logging
import time
import uuid

import cv2
from fastapi import APIRouter, HTTPException, WebSocket
from fastapi.responses import StreamingResponse

from camera.discovery import discover_all
from config import OUTPUT_DIR, TTL, UPLOAD_DIR
from core.state import _cam_lock, camera_manager
from utils.files import purge_old_files

router = APIRouter()
logger = logging.getLogger(__name__)

# =====================
# Camera
# =====================
_fps_stat = {"fps": 0.0, "count": 0, "t": 0.0}


@router.get("/cameras")
async def list_cameras():
    """利用可能なカメラインデックスを返す（最大8台試行）"""
    try:
        return {"cameras": discover_all()}
    except Exception as e:
        logger.exception(e)  # noqa: TRY401
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/camera/open/{uid}")
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
        logger.exception("open camera error uid=%s: %s", uid, e)  # noqa: TRY401
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/camera/close")
async def close_camera():
    logger.info("camera closed")
    with _cam_lock:
        camera_manager.close()
    return {"success": True}


@router.get("/camera/fps")
async def get_fps():
    return {"fps": _fps_stat["fps"]}


@router.get("/camera/params")
async def get_camera_params():
    if camera_manager.camera is None:
        raise HTTPException(status_code=400, detail="No camera open")
    camera = camera_manager.camera

    try:
        definitions = camera.get_param_defs()
        params = []

        with _cam_lock:
            for key, definition in definitions.items():
                item = dict(definition)

                if "value" not in item:
                    try:
                        item["value"] = camera.get_param(key)
                    except Exception:  # noqa: BLE001
                        item["value"] = None

                # javascript側でkeyを使うので、ここで追加しておく
                item["key"] = key

                params.append(item)

        return {
            "camera_type": camera.__class__.__name__,
            "params": params,
        }

    except Exception as e:
        logger.exception(e)  # noqa: TRY401
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/camera/params")
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
        logger.exception("set camera params error: %s", e)  # noqa: TRY401
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/camera/stream")
async def camera_stream():
    if camera_manager.camera is None:
        raise HTTPException(status_code=400, detail="No camera open")
    return StreamingResponse(
        _gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.websocket("/camera/stream/ws")
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
    except Exception as e:  # noqa: BLE001
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


@router.post("/camera/capture")
async def camera_capture():
    """現在のフレームをキャプチャしてアップロード画像として保存"""
    try:
        with _cam_lock:
            if camera_manager.camera is None:
                raise HTTPException(status_code=400, detail="No camera open")
            ok, frame = camera_manager.read()
        if not ok or frame is None:
            raise HTTPException(status_code=500, detail="Capture failed")
        purge_old_files(
            [UPLOAD_DIR, OUTPUT_DIR],
            TTL,
            logger,
        )
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
        logger.exception("capture error: %s", e)  # noqa: TRY401
        raise HTTPException(status_code=500, detail=str(e))


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


def update_fps():
    global _fps_stat  # noqa: PLW0602

    _fps_stat["count"] += 1
    now = time.time()
    elapsed = now - _fps_stat["t"]

    if elapsed >= 1.0:
        _fps_stat["fps"] = round(_fps_stat["count"] / elapsed, 1)
        _fps_stat["count"] = 0
        _fps_stat["t"] = now

import logging
import logging.handlers
import os
import platform
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models import ProcessRequest
from processors import apply_pipeline

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

TTL = 3600  # seconds

# ログ設定: 1MB x 3世代
# ログレベルは環境変数 LOG_LEVEL で変更可能 (DEBUG/INFO/WARNING/ERROR)
_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
_log_handler = logging.handlers.RotatingFileHandler(
    BASE_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=_log_level, handlers=[_log_handler, logging.StreamHandler()])
logger = logging.getLogger("blobfinder")

app = FastAPI(title="Image Processing App")
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
        logger.exception("unhandled error %s %s: %s", request.method, request.url.path, e)
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
        ext = Path(file.filename).suffix.lower()
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


@app.post("/process/{image_id}")
async def process_image(image_id: str, request: ProcessRequest):
    try:
        src = UPLOAD_DIR / f"{image_id}.png"
        if not src.exists():
            raise HTTPException(status_code=404, detail="image not found")
        img = imread_safe(str(src))
        if img is None:
            raise HTTPException(status_code=500, detail="failed to read image")
        result, blobs = apply_pipeline(img, request.pipeline)
        if result is None:
            logger.warning("process failed image_id=%s", image_id)
            raise HTTPException(status_code=400, detail="invalid processing parameters")
        if result.dtype == np.float64:
            result = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        if len(result.shape) == 2:
            result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        output = OUTPUT_DIR / f"{image_id}.png"
        cv2.imwrite(str(output), result)
        logger.info("process done image_id=%s blobs=%d", image_id, len(blobs or []))
        return {
            "success": True,
            "result_url": f"/result/{image_id}",
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
    return {"status": "ok", "log_level": logging.getLevelName(logger.getEffectiveLevel())}


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


# =====================
# Camera
# =====================

_cam_lock = threading.Lock()
_cam: cv2.VideoCapture | None = None
_cam_index: int = -1
_fps_stat = {"fps": 0.0, "count": 0, "t": 0.0}

# カメラパラメータ定義: (cv2定数, 最小, 最大, デフォルト表示名)
_CAM_PARAMS = {
    "width":      cv2.CAP_PROP_FRAME_WIDTH,
    "height":     cv2.CAP_PROP_FRAME_HEIGHT,
    "fps":        cv2.CAP_PROP_FPS,
    "brightness": cv2.CAP_PROP_BRIGHTNESS,
    "contrast":   cv2.CAP_PROP_CONTRAST,
    "saturation": cv2.CAP_PROP_SATURATION,
    "hue":        cv2.CAP_PROP_HUE,
    "gain":       cv2.CAP_PROP_GAIN,
    "exposure":   cv2.CAP_PROP_EXPOSURE,
    "autofocus":  cv2.CAP_PROP_AUTOFOCUS,
    "focus":      cv2.CAP_PROP_FOCUS,
    "auto_exposure": cv2.CAP_PROP_AUTO_EXPOSURE,
}


def _open_camera(index: int) -> bool:
    global _cam, _cam_index
    with _cam_lock:
        if _cam is not None:
            _cam.release()
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            _cam = None
            _cam_index = -1
            return False
        _cam = cap
        _cam_index = index
        return True


def _release_camera():
    global _cam, _cam_index
    with _cam_lock:
        if _cam is not None:
            _cam.release()
            _cam = None
            _cam_index = -1


def _get_camera_names() -> dict[int, str]:
    """OSごとにカメラ名を取得。失敗時は空辞書を返す"""
    names: dict[int, str] = {}
    try:
        if platform.system() == "Windows":
            # PowerShellでWMIに問合せ
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image'} | Select-Object -ExpandProperty Name"
            ]
            out = subprocess.check_output(cmd, timeout=5, stderr=subprocess.DEVNULL, text=True)
            cam_names = [l.strip() for l in out.splitlines() if l.strip()]
            for i, name in enumerate(cam_names):
                names[i] = name
        else:
            # Linux: /sys/class/video4linux/videoN/name
            import glob
            for dev in sorted(glob.glob("/sys/class/video4linux/video*/name")):
                idx_str = re.search(r"video(\d+)", dev)
                if idx_str:
                    idx = int(idx_str.group(1))
                    try:
                        names[idx] = open(dev).read().strip()
                    except Exception:
                        pass
    except Exception:
        pass
    return names


@app.get("/cameras")
async def list_cameras():
    """利用可能なカメラインデックスを返す（最大8台試行）"""
    cam_names = _get_camera_names()
    available = []
    for i in range(8):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            name = cam_names.get(i) or f"Camera {i}"
            available.append({"index": i, "name": name})
            cap.release()
    return {"cameras": available}


@app.post("/camera/open/{index}")
async def open_camera(index: int):
    try:
        if not _open_camera(index):
            logger.warning("open camera failed index=%d", index)
            raise HTTPException(status_code=400, detail=f"Cannot open camera {index}")
        logger.info("camera opened index=%d", index)
        return {"success": True, "index": index}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("open camera error index=%d: %s", index, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/camera/close")
async def close_camera():
    logger.info("camera closed")
    _release_camera()
    return {"success": True}


def _gen_frames():
    global _fps_stat
    _fps_stat = {"fps": 0.0, "count": 0, "t": time.time()}
    while True:
        with _cam_lock:
            if _cam is None or not _cam.isOpened():
                break
            ok, frame = _cam.read()
        if not ok:
            break
        # FPS計測
        _fps_stat["count"] += 1
        now = time.time()
        elapsed = now - _fps_stat["t"]
        if elapsed >= 1.0:
            _fps_stat["fps"] = round(_fps_stat["count"] / elapsed, 1)
            _fps_stat["count"] = 0
            _fps_stat["t"] = now
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
               + buf.tobytes() + b"\r\n")


@app.get("/camera/fps")
async def get_fps():
    return {"fps": _fps_stat["fps"]}


@app.get("/camera/params")
async def get_camera_params():
    if _cam is None:
        raise HTTPException(status_code=400, detail="No camera open")
    result = {}
    with _cam_lock:
        for name, prop in _CAM_PARAMS.items():
            val = _cam.get(prop)
            result[name] = round(val, 4) if val != -1 else None
    return result


@app.post("/camera/params")
async def set_camera_params(params: dict):
    try:
        if _cam is None:
            raise HTTPException(status_code=400, detail="No camera open")
        applied = {}
        with _cam_lock:
            for name, val in params.items():
                if name in _CAM_PARAMS:
                    _cam.set(_CAM_PARAMS[name], float(val))
                    applied[name] = _cam.get(_CAM_PARAMS[name])
        logger.debug("camera params applied: %s", applied)
        return {"applied": applied}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("set camera params error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/camera/stream")
async def camera_stream():
    if _cam is None:
        raise HTTPException(status_code=400, detail="No camera open")
    return StreamingResponse(
        _gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/camera/capture")
async def camera_capture():
    """現在のフレームをキャプチャしてアップロード画像として保存"""
    try:
        with _cam_lock:
            if _cam is None or not _cam.isOpened():
                raise HTTPException(status_code=400, detail="No camera open")
            ok, frame = _cam.read()
        if not ok:
            raise HTTPException(status_code=500, detail="Capture failed")
        purge_old_files()
        image_id = str(uuid.uuid4())
        dst = UPLOAD_DIR / f"{image_id}.png"
        cv2.imwrite(str(dst), frame)
        logger.info("capture image_id=%s", image_id)
        return {"image_id": image_id, "image_url": f"/image/{image_id}",
                "image_name": f"capture_{image_id[:8]}.png"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("capture error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

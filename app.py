import time
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
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

app = FastAPI(title="Image Processing App")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def purge_old_files():
    now = time.time()
    for d in (UPLOAD_DIR, OUTPUT_DIR):
        for f in d.iterdir():
            if now - f.stat().st_mtime > TTL:
                f.unlink(missing_ok=True)


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
    purge_old_files()
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="unsupported format")
    image_id = str(uuid.uuid4())
    dst = UPLOAD_DIR / f"{image_id}.png"
    content = await file.read()
    dst.write_bytes(content)
    return {
        "image_id": image_id,
        "image_url": f"/image/{image_id}",
        "image_name": file.filename,
    }


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
    src = UPLOAD_DIR / f"{image_id}.png"
    if not src.exists():
        raise HTTPException(status_code=404, detail="image not found")
    img = imread_safe(str(src))
    if img is None:
        raise HTTPException(status_code=500, detail="failed to read image")
    result, blobs = apply_pipeline(img, request.pipeline)
    if result is None:
        raise HTTPException(
            status_code=400, detail="invalid processing parameters"
        )
    if result.dtype == np.float64:
        result = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX).astype(
            np.uint8
        )
    if len(result.shape) == 2:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
    output = OUTPUT_DIR / f"{image_id}.png"
    cv2.imwrite(str(output), result)
    return {
        "success": True,
        "result_url": f"/result/{image_id}",
        "blobs": blobs or [],
    }


@app.get("/download/{image_id}")
async def download_result(image_id: str):
    path = OUTPUT_DIR / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(
        path,
        media_type="image/png",
    )


@app.delete("/image/{image_id}")
async def delete_image(image_id: str):
    for d in (UPLOAD_DIR, OUTPUT_DIR):
        (d / f"{image_id}.png").unlink(missing_ok=True)
    return {"success": True}

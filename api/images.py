import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.models import ProcessRequest
from config import OUTPUT_DIR, TTL, UPLOAD_DIR
from processors.pipeline import apply_pipeline
from utils.files import purge_old_files
from utils.image import (
    imread_safe,
    save_image_as_png,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):  # noqa: B008
    try:
        purge_old_files(
            [UPLOAD_DIR, OUTPUT_DIR],
            TTL,
            logger,
        )
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
        logger.exception(
            "upload error name=%s: %s", file.filename, e  # noqa: TRY401
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/image/{image_id}")
async def get_image(image_id: str):
    path = UPLOAD_DIR / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@router.get("/result/{image_id}")
async def get_result(image_id: str):
    path = OUTPUT_DIR / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@router.get("/result_step/{image_id}/{step}")
async def get_intermediate(image_id: str, step: int):
    path = OUTPUT_DIR / f"{image_id}_step_{step}.png"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@router.post("/process/{image_id}")
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
        save_image_as_png(result, image_id, None, OUTPUT_DIR)

        intermediate_urls = []
        for i, im in enumerate(intermediates):
            save_image_as_png(im, image_id, i, OUTPUT_DIR)
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
        logger.exception(
            "process error image_id=%s: %s", image_id, e  # noqa: TRY401
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{image_id}")
async def download_result(image_id: str):
    if not image_id:
        raise HTTPException(status_code=400)
    path = OUTPUT_DIR / f"{image_id}.png"
    if not path.exists():
        # 出力フォルダにない場合は、アップロードフォルダにあるか確認
        path = UPLOAD_DIR / f"{image_id}.png"
        if not path.exists():
            raise HTTPException(status_code=404)
    return FileResponse(
        path,
        media_type="image/png",
    )


@router.delete("/image/{image_id}")
async def delete_image(image_id: str):
    for d in (UPLOAD_DIR, OUTPUT_DIR):
        (d / f"{image_id}.png").unlink(missing_ok=True)
    return {"success": True}

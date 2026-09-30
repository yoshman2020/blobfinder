import json
import logging
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import PIPELINE_DIR

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic モデル
class PipelineSaveRequest(BaseModel):
    name: str
    pipeline: list
    overwrite: bool = False  # 上書き保存フラグ


class PipelineLoadRequest(BaseModel):
    name: str


# ===== 設定 保存・読み込み =====


@router.post("/api/pipelines/save")
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
            "saved_at": datetime.now().isoformat(),  # noqa: DTZ005
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


@router.post("/api/pipelines/check-exists")
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


@router.post("/api/pipelines/load")
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


@router.get("/api/pipelines/list")
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


@router.get("/api/pipelines/export/{filename}")
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


@router.post("/api/pipelines/import")
async def import_pipeline(file: UploadFile = File(...)):  # noqa: B008
    """JSONファイルから設定をインポート"""
    try:
        # ファイル名を安全にする
        safe_filename = "".join(
            c if c.isalnum() or c in "._-" else "_" for c in file.filename  # type: ignore
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
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


@router.delete("/api/pipelines/{filename}")
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

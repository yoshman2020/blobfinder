import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel

from core.state import shm_ctrl

router = APIRouter()
logger = logging.getLogger(__name__)


class ShmPipelineSyncRequest(BaseModel):
    pipeline: list
    name: str = ""


class ShmQueueMaxRequest(BaseModel):
    queue_max: int


# =====================
# Shared Memory: WebSocket 結果配信 & REST API
# =====================


@router.websocket("/ws/shm_result")
async def ws_shm_result(websocket: WebSocket):
    """共有メモリ経由の処理結果をブラウザにリアルタイム配信"""
    await websocket.accept()
    q = shm_ctrl.subscribe()
    try:
        while True:
            result = await asyncio.wait_for(q.get(), timeout=30.0)
            await websocket.send_text(json.dumps(result, ensure_ascii=False))
    except asyncio.TimeoutError:
        pass
    except Exception as e:  # noqa: BLE001
        logger.debug("ws_shm_result closed: %s", e)
    finally:
        shm_ctrl.unsubscribe(q)
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001, S110
            pass


@router.get("/api/shm/status")
async def shm_status():
    """共有メモリコントローラの現在状態を返す"""
    return shm_ctrl.get_status()


@router.post("/api/shm/pipeline_sync")
async def shm_pipeline_sync(req: ShmPipelineSyncRequest):
    """ブラウザ側の現在 pipeline を ShmController に同期する"""
    shm_ctrl.set_browser_pipeline(req.pipeline, req.name)
    return {"success": True}


@router.post("/api/shm/queue_max")
async def shm_set_queue_max(req: ShmQueueMaxRequest):
    """撮影キューの最大数を変更する"""
    if req.queue_max < 1:
        raise HTTPException(status_code=400, detail="queue_max must be >= 1")
    shm_ctrl._queue_max = req.queue_max
    return {"success": True, "queue_max": req.queue_max}

import asyncio
import logging
import mimetypes

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.camera import router as camera_router
from api.images import router as images_router
from api.pipelines import router as pipelines_router
from api.shm import router as shm_router
from config import (
    BASE_DIR,
)
from core.state import shm_ctrl
from logging_config import setup_logging
from system.system_manager import SystemManager

logger = setup_logging(BASE_DIR)

system = SystemManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時
    system.initialize()
    loop = asyncio.get_event_loop()
    shm_ctrl.start(loop)
    yield  # ←ここでアプリ実行中状態
    # 終了時
    shm_ctrl.stop()
    system.shutdown()


mimetypes.add_type("application/javascript", ".js")
app = FastAPI(title="Image Processing App", lifespan=lifespan)
app.include_router(camera_router)
app.include_router(shm_router)
app.include_router(images_router)
app.include_router(pipelines_router)
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


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={}
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

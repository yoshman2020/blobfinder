import threading

from camera.manager import CameraManager
from config import PIPELINE_DIR
from shm.shm_controller import ShmController

_cam_lock = threading.Lock()

camera_manager = CameraManager()

# =====================
# Shared Memory Controller
# =====================

shm_ctrl = ShmController(
    camera_manager=camera_manager,
    cam_lock=_cam_lock,
    pipeline_dir=PIPELINE_DIR,
)

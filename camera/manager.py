# camera/manager.py

from .camera_types import CAMERA_TYPES
from .discovery import get_camera_info


class CameraManager:

    def __init__(self):
        self.camera = None
        self.uid = None

    def close(self):
        if self.camera:
            try:
                self.camera.close()
            finally:
                self.camera = None
                self.uid = None

    def open_uid(self, uid: str):
        info = get_camera_info(uid)
        if info is None:
            return False
        self.close()
        camera_type = info["type"]
        serial = info["serial"]
        cls = CAMERA_TYPES.get(camera_type)
        if cls is None:
            return False
        cam = cls()
        ok = cam.open(serial)
        if not ok:
            return False
        self.camera = cam
        self.uid = uid
        return True

    def read(self):
        if self.camera is None:
            return False, None
        return self.camera.read()

    def get_param(self, name):
        if self.camera is None:
            return None
        return self.camera.get_param(name)

    def set_param(self, name, value):
        if self.camera is None:
            return False
        self.camera.set_param(name, value)
        return True

    def get_info(self):
        if self.camera is None:
            return None
        return self.camera.info()

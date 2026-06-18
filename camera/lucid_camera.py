import numpy as np

try:
    from arena_api.system import system
except ImportError:
    system = None
except Exception:
    system = None

from .base import CameraBase


class LucidCamera(CameraBase):

    @classmethod
    def initialize(cls):
        pass

    @classmethod
    def shutdown(cls):
        pass

    @classmethod
    def discover(cls):
        if system is None:
            return []
        cameras = []
        for info in system.device_infos:
            cameras.append(
                {
                    "type": "lucid",
                    "serial": info["serial"],
                    "name": f"LUCID {info['model']}",
                }
            )
        return cameras

    def __init__(self):
        self.device = None

    def open(self, serial: str) -> bool:
        infos = system.device_infos
        for info in infos:
            if info["serial"] == serial:
                self.device = system.create_device([info])[0]
                self.device.start_stream()
                return True

        return False

    def close(self):
        if self.device:
            self.device.stop_stream()

    def read(self):
        buffer = self.device.get_buffer()
        frame = np.ctypeslib.as_array(
            buffer.pdata, shape=(buffer.height, buffer.width)
        ).copy()
        self.device.requeue_buffer(buffer)
        return True, frame

    def get_param(self, name):
        return self.device.nodemap[name].value

    def set_param(self, name, value):
        self.device.nodemap[name].value = value

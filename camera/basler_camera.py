# camera/basler_camera.py

from typing import ClassVar

try:
    from pypylon import pylon  # type: ignore
except ImportError:
    pylon = None

from .base import CameraBase, CameraParamDef


class BaslerCamera(CameraBase):

    PARAM_DEFS: ClassVar[dict[str, CameraParamDef]] = {
        "width": {
            "label": "Width",
            "type": "number",
            "step": 1,
            "unit": "px",
            "readonly": False,
        },
        "height": {
            "label": "Height",
            "type": "number",
            "step": 1,
            "unit": "px",
            "readonly": False,
        },
        "fps": {
            "label": "FPS",
            "type": "range",
            "step": 0.1,
            "unit": "fps",
            "readonly": True,
        },
        "gain": {
            "label": "Gain",
            "type": "range",
            "step": 1,
            "readonly": True,
        },
        "exposure": {
            "label": "Exposure",
            "type": "range",
            "step": 1,
            "unit": "us",
            "readonly": True,
        },
    }

    @classmethod
    def initialize(cls):
        pass

    @classmethod
    def shutdown(cls):
        pass

    @classmethod
    def discover(cls):
        if pylon is None:
            return []
        cameras = []
        tl = pylon.TlFactory.GetInstance()
        for dev in tl.EnumerateDevices():
            cameras.append(
                {
                    "type": "basler",
                    "serial": dev.GetSerialNumber(),
                    "name": f"Basler {dev.GetModelName()}",
                }
            )
        return cameras

    def __init__(self):
        self.cam = None

    def open(self, serial: str) -> bool:
        if pylon is None:
            return False
        tl = pylon.TlFactory.GetInstance()
        for dev in tl.EnumerateDevices():
            if dev.GetSerialNumber() == serial:
                self.cam = pylon.InstantCamera(tl.CreateDevice(dev))
                self.cam.Open()
                self.cam.StartGrabbing()
                return True
        return False

    def close(self):
        if self.cam:
            if self.cam.IsGrabbing():
                self.cam.StopGrabbing()
            self.cam.Close()

    def read(self):
        if pylon is None:
            return False, None
        if not self.cam or not self.cam.IsGrabbing():
            return False, None
        result = self.cam.RetrieveResult(
            1000, pylon.TimeoutHandling_ThrowException
        )
        if not result.GrabSucceeded():
            return False, None
        frame = result.Array.copy()
        result.Release()
        return True, frame

    def get_param(self, name):
        if self.cam is None:
            return None
        node = self.cam.GetNodeMap().GetNode(name)
        return node.GetValue()

    def set_param(self, name, value):
        if self.cam is None:
            return False
        if not self.PARAM_DEFS[name].get("readonly", False):
            return False
        node = self.cam.GetNodeMap().GetNode(name)
        node.SetValue(value)
        return True

    def get_param_defs(self):
        result = {}

        for key, definition in self.PARAM_DEFS.items():
            item = dict(definition)

            try:
                item["value"] = self.get_param(key)
            except Exception:  # noqa: BLE001
                item["value"] = None

            result[key] = item

        return result

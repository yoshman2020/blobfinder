try:
    from pypylon import pylon
except ImportError:
    pylon = None

from .base import CameraBase


class BaslerCamera(CameraBase):

    PARAMS = {
        "width": ("Width", False),
        "height": ("Height", False),
        "fps": ("AcquisitionFrameRateAbs", True),
        "gain": ("GainRaw", True),
        "exposure": ("ExposureTimeAbs", True),
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
        node = self.cam.GetNodeMap().GetNode(self.PARAMS[name][0])
        return node.GetValue()

    def set_param(self, name, value):
        if self.cam is None:
            return False
        if not self.PARAMS[name][1]:
            return False
        node = self.cam.GetNodeMap().GetNode(self.PARAMS[name][0])
        node.SetValue(value)
        return True

# camera/opencv_camera.py

import platform
import re
import subprocess

import cv2
from numpy import ndarray

from .base import CameraBase


class OpenCVCamera(CameraBase):

    PARAMS = {
        "width": cv2.CAP_PROP_FRAME_WIDTH,
        "height": cv2.CAP_PROP_FRAME_HEIGHT,
        "fps": cv2.CAP_PROP_FPS,
        "brightness": cv2.CAP_PROP_BRIGHTNESS,
        "contrast": cv2.CAP_PROP_CONTRAST,
        "saturation": cv2.CAP_PROP_SATURATION,
        "hue": cv2.CAP_PROP_HUE,
        "gain": cv2.CAP_PROP_GAIN,
        "exposure": cv2.CAP_PROP_EXPOSURE,
        "focus": cv2.CAP_PROP_FOCUS,
        "autofocus": cv2.CAP_PROP_AUTOFOCUS,
    }

    @classmethod
    def initialize(cls):
        pass

    @classmethod
    def shutdown(cls):
        pass

    @classmethod
    def get_camera_names(cls) -> dict[int, str]:
        """OSごとにカメラ名を取得。失敗時は空辞書を返す"""
        names: dict[int, str] = {}
        try:
            if platform.system() == "Windows":
                # PowerShellでWMIに問合せ
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image'} | Select-Object -ExpandProperty Name",
                ]
                out = subprocess.check_output(
                    cmd, timeout=5, stderr=subprocess.DEVNULL, text=True
                )
                cam_names = [
                    line.strip() for line in out.splitlines() if line.strip()
                ]
                for i, name in enumerate(cam_names):
                    names[i] = name
            else:
                # Linux: /sys/class/video4linux/videoN/name
                import glob

                for dev in sorted(
                    glob.glob("/sys/class/video4linux/video*/name")
                ):
                    idx_str = re.search(r"video(\d+)", dev)
                    if idx_str:
                        idx = int(idx_str.group(1))
                        try:
                            names[idx] = open(dev).read().strip()
                        except Exception:
                            pass
        except Exception:
            pass
        return names

    def __init__(self):
        self.cap = None

    @classmethod
    def discover(cls):
        cameras = []
        cam_names = OpenCVCamera.get_camera_names()

        for i in range(8):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append(
                    {
                        "type": "opencv",
                        "serial": str(i),
                        "name": cam_names.get(i) or f"USB Camera {i}",
                    }
                )
            cap.release()
        return cameras

    def open(self, serial: str) -> bool:
        self.cap = cv2.VideoCapture(int(serial))
        return self.cap.isOpened()

    def close(self):
        if self.cap:
            self.cap.release()

    def read(self) -> tuple[bool, ndarray | None]:
        return self.cap.read()  # type: ignore

    def get_param(self, name) -> float | None:
        if not self.cap:
            return None
        val = self.cap.get(self.PARAMS[name])
        return None if val == -1 else val

    def set_param(self, name, value) -> bool:
        if not self.cap:
            return False
        return self.cap.set(self.PARAMS[name], value)

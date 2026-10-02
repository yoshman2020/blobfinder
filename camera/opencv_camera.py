# camera/opencv_camera.py

import platform
import re
import subprocess
from typing import ClassVar

import cv2
from numpy import ndarray

from .base import CameraBase, CameraParamDef


class OpenCVCamera(CameraBase):

    PARAMS: ClassVar[dict[str, int]] = {
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

    PARAM_DEFS: ClassVar[dict[str, CameraParamDef]] = {
        "width": {
            "label": "Width",
            "type": "number",
            "min": 1,
            "step": 1,
            "unit": "px",
        },
        "height": {
            "label": "Height",
            "type": "number",
            "min": 1,
            "step": 1,
            "unit": "px",
        },
        "fps": {
            "label": "FPS",
            "type": "range",
            "min": 1,
            "max": 240,
            "step": 1,
            "unit": "fps",
        },
        "brightness": {
            "label": "Brightness",
            "type": "range",
            "min": 0,
            "max": 255,
            "step": 1,
        },
        "contrast": {
            "label": "Contrast",
            "type": "range",
            "min": 0,
            "max": 255,
            "step": 1,
        },
        "saturation": {
            "label": "Saturation",
            "type": "range",
            "min": 0,
            "max": 255,
            "step": 1,
        },
        "hue": {
            "label": "Hue",
            "type": "range",
            "min": 0,
            "max": 360,
            "step": 1,
        },
        "gain": {
            "label": "Gain",
            "type": "range",
            "min": 0,
            "max": 255,
            "step": 1,
        },
        "exposure": {
            "label": "Exposure",
            "type": "range",
            "min": -13,
            "max": 0,
            "step": 0.1,
        },
        "focus": {
            "label": "Focus",
            "type": "range",
            "min": 0,
            "max": 255,
            "step": 1,
        },
        "autofocus": {
            "label": "Autofocus",
            "type": "checkbox",
        },
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
                            names[idx] = (
                                open(dev).read().strip()  # noqa: SIM115
                            )
                        except Exception:  # noqa: BLE001, S110
                            pass
        except Exception:  # noqa: BLE001, S110
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
        # bool型（True/False）の場合はOpenCVが受け付けないため数値（1/0）に変換する
        if isinstance(value, bool):
            value = 1.0 if value else 0.0
        return self.cap.set(self.PARAMS[name], value)

    def get_param_defs(self) -> dict[str, CameraParamDef]:
        result = {}

        for key, definition in self.PARAM_DEFS.items():
            item = dict(definition)

            try:
                item["value"] = self.get_param(key)
            except Exception:  # noqa: BLE001
                item["value"] = None

            result[key] = item

        return result

# camera/opencv_camera.py

import logging
import platform
import re
import shutil
import subprocess
from typing import ClassVar

import cv2
from numpy import ndarray

from .base import CameraBase, CameraParamDef

logger = logging.getLogger(__name__)


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
        "autoexposure": cv2.CAP_PROP_AUTO_EXPOSURE,
        "exposure": cv2.CAP_PROP_EXPOSURE,
        "autofocus": cv2.CAP_PROP_AUTOFOCUS,
        "focus": cv2.CAP_PROP_FOCUS,
        "autowhitebalance": cv2.CAP_PROP_AUTO_WB,
        "whitebalance": cv2.CAP_PROP_WB_TEMPERATURE,
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
        "autoexposure": {
            "label": "Auto Exposure",
            "type": "checkbox",
        },
        "exposure": {
            "label": "Exposure",
            "type": "range",
            "min": -13,
            "max": 10000,
            "step": 0.1,
        },
        "autofocus": {
            "label": "Autofocus",
            "type": "checkbox",
        },
        "focus": {
            "label": "Focus",
            "type": "range",
            "min": 0,
            "max": 255,
            "step": 1,
        },
        "autowhitebalance": {
            "label": "Auto WB",
            "type": "checkbox",
        },
        "whitebalance": {
            "label": "White Balance",
            "type": "range",
            "min": 2000,
            "max": 7500,
            "step": 0.1,
        },
    }

    V4L2_CONTROLS: ClassVar[dict[str, str]] = {
        "brightness": "brightness",
        "contrast": "contrast",
        "saturation": "saturation",
        "hue": "hue",
        "gain": "gain",
        "exposure": "exposure_absolute",
        "focus": "focus_absolute",
        "whitebalance": "white_balance_temperature",
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
        self.device = None

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
        self.device = (
            f"/dev/video{serial}" if platform.system() == "Linux" else None
        )
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
        if (param := self.PARAMS.get(name)) is None:
            logger.debug(f"Unknown parameter: {name}")
            return None
        if (val := self.cap.get(param)) != -1:
            logger.debug(f"Get parameter {name},{param} = {val}")
            if param == cv2.CAP_PROP_AUTO_EXPOSURE:
                # 0.25 or 1=MANUAL, 0.75 or 3=APERTURE_PRIORITY
                return bool(val == 0.75 or val == 3)
            return val
        logger.debug(f"Failed to get parameter: {name}")
        return None

    def set_param(self, name, value) -> bool:
        if not self.cap:
            return False
        if (param := self.PARAMS.get(name)) is None:
            logger.debug(f"Unknown parameter: {name}")
            return False
        if param == cv2.CAP_PROP_AUTO_EXPOSURE:
            val = self.cap.get(param)
            if value:
                value = (
                    0.75 if (val == 0.25 or val == 0.75) else 3
                )  # APERTURE_PRIORITY
            else:
                value = 0.25 if (val == 0.25 or val == 0.75) else 1  # MANUAL
        # bool型（True/False）の場合はOpenCVが受け付けないため数値（1/0）に変換する
        if isinstance(value, bool):
            value = 1.0 if value else 0.0
        if ret := self.cap.set(param, value):
            logger.debug(f"Set parameter {name} = {value}")
        else:
            logger.debug(f"Failed to set parameter: {name} = {value}")
        return ret

    def get_param_defs(self) -> dict[str, CameraParamDef]:
        result = {}
        ranges = self._get_v4l2_ranges()

        for key, definition in self.PARAM_DEFS.items():
            item = dict(definition)

            try:
                item["value"] = self.get_param(key)
            except Exception:  # noqa: BLE001
                item["value"] = None

            # カメラから取得できた範囲だけ上書き
            if key in ranges:
                logger.debug(f"Update {key} range: {ranges[key]}")
                item.update(ranges[key])

            result[key] = item

        return result

    def _get_v4l2_ranges(self) -> dict[str, dict[str, int]]:
        """Linux V4L2から各コントロールの範囲を取得する。"""
        if platform.system() != "Linux" or not self.device:
            return {}

        executable = shutil.which("v4l2-ctl")
        if not executable:
            logger.warning("v4l2-ctl not found in PATH")
            return {}

        try:
            result = subprocess.run(
                [executable, "-d", self.device, "-L"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Failed to get V4L2 controls: %s", exc)
            return {}

        ranges = {}

        for line in result.stdout.splitlines():
            match = re.search(
                r"^\s*(\w+).*?\bmin=(-?\d+)\s+max=(-?\d+)\s+step=(\d+)",
                line,
            )
            if not match:
                continue

            control, min_val, max_val, step = match.groups()
            logger.debug(
                f"Control: {control}, Min: {min_val}, Max: {max_val}, Step: {step}"
            )

            for name, control_name in self.V4L2_CONTROLS.items():
                if control == control_name:
                    ranges[name] = {
                        "min": int(min_val),
                        "max": int(max_val),
                        "step": int(step),
                    }
                    logger.debug(f"Found {name}: {ranges[name]}")
                    break
                else:
                    logger.debug(f"Unknown control: {control}")

        return ranges

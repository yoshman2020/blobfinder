# camera/owlift_camera.py
# infinitegra OWLIFT Type-F Camera Implementation

import logging
from typing import ClassVar

from numpy import ndarray

try:
    import owlift
except ImportError:
    owlift = None

from .base import CameraBase, CameraParamDef

logger = logging.getLogger(__name__)


class OwliftCamera(CameraBase):

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
        "color": {
            "label": "カラーテーブル",
            "type": "select",
            "options": [
                {
                    "value": (
                        owlift.OwColor.GRAY if owlift is not None else 0  # type: ignore
                    ),
                    "label": "Grayscale",
                },
                {
                    "value": (
                        owlift.OwColor.BLUE_ORANGE  # type: ignore
                        if owlift is not None
                        else 1
                    ),
                    "label": "Blue Orange",
                },
                {
                    "value": (
                        owlift.OwColor.RAINBOW  # type: ignore
                        if owlift is not None
                        else 2
                    ),
                    "label": "Rainbow",
                },
            ],
        },
        "gain_control": {
            "label": "ゲイン制御",
            "type": "select",
            "options": [
                {
                    "value": (
                        owlift.OwGainControl.MANUAL if owlift is not None else 0  # type: ignore
                    ),
                    "label": "マニュアルゲイン制御",
                },
                {
                    "value": (
                        owlift.OwGainControl.AUTO_LINEAR  # type: ignore
                        if owlift is not None
                        else 1
                    ),
                    "label": "線形自動ゲイン制御",
                },
                {
                    "value": (
                        owlift.OwGainControl.AUTO_NON_LINEAR  # type: ignore
                        if owlift is not None
                        else 2
                    ),
                    "label": "非線形自動ゲイン制御",
                },
            ],
        },
        "manual_gain_min": {
            "label": "温度範囲(最低)(K)",
            "type": "range",
            "min": 0,
            "max": 100,
            "step": 1,
        },
        "manual_gain_max": {
            "label": "温度範囲(最高)(K)",
            "type": "range",
            "min": 0,
            "max": 100,
            "step": 1,
        },
        "noise_filter": {
            "label": "ノイズフィルタ",
            "type": "range",
            "min": 0,
            "max": 100,
            "step": 1,
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
        if owlift is None:
            return []
        cameras = []
        for dev in owlift.devices():  # type: ignore
            cameras.append(
                {
                    "type": "owlift",
                    "serial": dev.serial_number,
                    "name": "OWLIFT Type-F",
                }
            )
        return cameras

    def __init__(self):
        if owlift is None:
            raise RuntimeError("Owlift library is not available.")
        self.ow = None

    def open(self, serial: str) -> bool:
        if owlift is None:
            return False
        self.ows = owlift.devices()  # type: ignore
        for dev in self.ows:
            if dev.serial_number == serial:
                self.ow = dev
                self.ow.image_enabled = True
                self.ow.color = owlift.OwColor.GRAY  # type: ignore
                # self.ow.color = owlift.OwColor.BLUE_ORANGE  # type: ignore
                # self.ow.color = owlift.OwColor.RAINBOW  # type: ignore

                # self.ow.gain_control = owlift.OwGainControl.MANUAL  # type: ignore
                # self.ow.gain_control = owlift.OwGainControl.AUTO_LINEAR  # type: ignore
                self.ow.gain_control = owlift.OwGainControl.AUTO_NON_LINEAR  # type: ignore
                self.ow.capture_start()

                wait_count = 0
                while self.ow.alive and self.ow.frame_counter == 0:
                    # wait for the first frame to be captured
                    if wait_count >= 1000:  # 最大1000回待つ
                        logger.error(
                            "Failed to capture the first frame from Owlift camera."
                        )
                        self.close()
                        return False
                return True
        return False

    def close(self):
        if self.ow:
            self.ow.capture_stop()
            self.ow.release()
            self.ow = None

    def read(self) -> tuple[bool, ndarray | None]:
        if not self.ow or not self.ow.alive:
            return False, None
        try:
            _, frame, _ = self.ow.frame
            if frame is None:
                logger.error(
                    "Failed to read frame from Owlift camera: Frame is None"
                )
                return False, None
            return True, frame
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to read frame from Owlift camera: {e}")
            return False, None

    def get_param(self, name) -> float | None:
        if not self.ow:
            return None
        try:
            if name not in self.PARAM_DEFS:
                logger.error(
                    f"Parameter {name} is not supported by Owlift camera."
                )
                return None

            if name == "width":
                width = self.ow.frame_size[0]
                if self.ow.magnification_enabled:
                    width = width * 3
                return width
            elif name == "height":
                height = self.ow.frame_size[1]
                if self.ow.magnification_enabled:
                    height = height * 3
                return height
            elif name == "color":
                return self.ow.color
            elif name == "gain_control":
                return self.ow.gain_control
            elif name == "manual_gain_min":
                return self.ow.manual_gain_range[0]
            elif name == "manual_gain_max":
                return self.ow.manual_gain_range[1]
            elif name == "noise_filter":
                return self.ow.noise_filter
            return None
        except AttributeError:
            logger.error(f"Parameter {name} not found in Owlift camera.")
            return None

    def set_param(self, name, value) -> bool:
        if not self.ow:
            return False
        try:
            if name not in self.PARAM_DEFS:
                logger.error(
                    f"Parameter {name} is not supported by Owlift camera."
                )
                return False

            if name == "width" or name == "height":
                # 解像度に480×360以上の値が設定された場合、画像を縦横3倍に拡大しアンチエイリアス処理
                self.ow.magnification_enabled = (
                    name == "width" and value >= self.ow.frame_size[0] * 3
                ) or (name == "height" and value >= self.ow.frame_size[1] * 3)
            if name == "color":
                assert owlift is not None
                try:
                    control = owlift.OwColor(int(value))  # type: ignore
                except ValueError:
                    raise ValueError(f"Invalid color: {value}")
                if control == owlift.OwColor.GRAY:  # type: ignore
                    self.ow.color = owlift.OwColor.GRAY  # type: ignore
                elif control == owlift.OwColor.BLUE_ORANGE:  # type: ignore
                    self.ow.color = owlift.OwColor.BLUE_ORANGE  # type: ignore
                elif control == owlift.OwColor.RAINBOW:  # type: ignore
                    self.ow.color = owlift.OwColor.RAINBOW  # type: ignore
            if name == "gain_control":
                assert owlift is not None
                try:
                    control = owlift.OwGainControl(int(value))  # type: ignore
                except ValueError:
                    raise ValueError(f"Invalid gain control: {value}")
                if control == owlift.OwGainControl.MANUAL:  # type: ignore
                    self.ow.gain_control = owlift.OwGainControl.MANUAL  # type: ignore
                elif control == owlift.OwGainControl.AUTO_LINEAR:  # type: ignore
                    self.ow.gain_control = owlift.OwGainControl.AUTO_LINEAR  # type: ignore
                elif control == owlift.OwGainControl.AUTO_NON_LINEAR:  # type: ignore
                    self.ow.gain_control = owlift.OwGainControl.AUTO_NON_LINEAR  # type: ignore
            elif name == "manual_gain_min":
                # マニュアルゲインではない場合は設定不可
                if self.ow.gain_control != owlift.OwGainControl.MANUAL:  # type: ignore
                    logger.warning(
                        "Cannot set manual_gain_min when gain_control is not MANUAL."
                    )
                    return False
                current_max = self.ow.manual_gain_range[1]
                if value > current_max:
                    logger.warning(
                        f"manual_gain_min {value} is greater than manual_gain_max {current_max}. Adjusting manual_gain_max to {value}."
                    )
                    self.ow.manual_gain_range = (value, value)
                self.ow.manual_gain_range = (value, current_max)
            elif name == "manual_gain_max":
                # マニュアルゲインではない場合は設定不可
                if self.ow.gain_control != owlift.OwGainControl.MANUAL:  # type: ignore
                    logger.warning(
                        "Cannot set manual_gain_min when gain_control is not MANUAL."
                    )
                    return False
                current_min = self.ow.manual_gain_range[0]
                if value < current_min:
                    logger.warning(
                        f"manual_gain_max {value} is less than manual_gain_min {current_min}. Adjusting manual_gain_min to {value}."
                    )
                    self.ow.manual_gain_range = (value, value)
                self.ow.manual_gain_range = (current_min, value)
            elif name == "noise_filter":
                self.ow.noise_filter = value
            return True
        except AttributeError:
            logger.error(f"Parameter {name} not found in Owlift camera.")
            return False
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to set parameter {name} to {value}: {e}")
            return False

    def get_param_defs(self) -> dict[str, CameraParamDef]:
        result = {}

        for key, definition in self.PARAM_DEFS.items():
            item = dict(definition)

            if key in ["manual_gain_min", "manual_gain_max"]:
                item["min"] = self.ow.agc_range[0] if self.ow else 0
                item["max"] = self.ow.agc_range[1] if self.ow else 100

            try:
                item["value"] = self.get_param(str(key))
            except Exception:  # noqa: BLE001
                item["value"] = None

            result[key] = item

        return result

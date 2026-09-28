# infinitegra OWLIFT Type-F Camera Implementation
try:
    import owlift
except ImportError:
    owlift = None

import logging
from typing import ClassVar

from numpy import ndarray

from .base import CameraBase

logger = logging.getLogger(__name__)


class OwliftCamera(CameraBase):

    PARAMS: ClassVar[dict[str, str]] = {
        "width": "width",
        "height": "height",
        #TODO カメラ固有設定
        "gain_control": "gain_control",
        "manual_gain_min": "manual_gain_min",
        "manual_gain_max": "manual_gain_max",
        "noise_filter": "noise_filter",
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
        for dev in owlift.devices(): # type: ignore
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
        self.ows = owlift.devices() # type: ignore
        for dev in self.ows:
            if dev.serial_number == serial:
                self.ow = dev
                self.ow.image_enabled = True
                self.ow.color = owlift.OwColor.RAINBOW # type: ignore
                # self.ow.color = owlift.OwColor.BLUE_ORANGE
                # self.ow.color = owlift.OwColor.GRAY

                self.ow.gain_control = owlift.OwGainControl.AUTO_NON_LINEAR # type: ignore
                # self.ow.gain_control = owlift.OwGainControl.AUTO_LINEAR
                self.ow.capture_start()

                wait_count = 0
                while self.ow.alive and self.ow.frame_counter == 0:
                    # wait for the first frame to be captured
                    if wait_count >= 1000:  # 最大1000回待つ
                        logger.error("Failed to capture the first frame from Owlift camera.")
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
                logger.error("Failed to read frame from Owlift camera: Frame is None")
                return False, None
            return True, frame
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to read frame from Owlift camera: {e}")
            return False, None

    def get_param(self, name) -> float | None:
        if not self.ow:
            return None
        try:
            if name not in self.PARAMS:
                logger.error(
                    f"Parameter {name} is not supported by Owlift camera."
                )
                return None

            if name == "width":
                return self.ow.frame_size[0]
            elif name == "height":
                return self.ow.frame_size[1]
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
            if name not in self.PARAMS:
                logger.error(
                    f"Parameter {name} is not supported by Owlift camera."
                )
                return False

            if name == "width" or name == "height":
                logger.error(
                    f"Parameter {name} is read-only for Owlift camera."
                )
                return False
            if name == "gain_control":
                self.ow.gain_control = value
            elif name == "manual_gain_min":
                current_max = self.ow.manual_gain_range[1]
                self.ow.manual_gain_range = (value, current_max)
            elif name == "manual_gain_max":
                current_min = self.ow.manual_gain_range[0]
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

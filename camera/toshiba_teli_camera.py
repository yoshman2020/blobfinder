# camera/toshiba_teli_camera.py

import logging
from typing import ClassVar

try:
    import pytelicam  # type: ignore
except ImportError:
    pytelicam = None

from .base import CameraBase, CameraParamDef

logger = logging.getLogger(__name__)


class ToshibaTeliCamera(CameraBase):

    PARAM_DEFS: ClassVar[dict[str, CameraParamDef]] = {
        "width": {
            "label": "Width",
            "type": "number",
            "readonly": False,
            "unit": "px",
        },
        "height": {
            "label": "Height",
            "type": "number",
            "readonly": False,
            "unit": "px",
        },
        "fps": {
            "label": "FPS",
            "type": "range",
            "min": 1,
            "max": 240,
            "step": 0.1,
            "unit": "fps",
        },
        "gain": {
            "label": "Gain",
            "type": "range",
            "min": 0,
            "max": 100,
            "step": 1,
        },
        "exposure": {
            "label": "Exposure",
            "type": "range",
            "min": 0,
            "max": 1000000,
            "step": 1,
            "unit": "us",
        },
    }

    _initialized = False
    cam_system = None

    @classmethod
    def initialize(cls):
        if pytelicam is None:
            return
        if cls._initialized:
            return
        cls.cam_system = pytelicam.get_camera_system()  # type: ignore
        cls._initialized = True

    @classmethod
    def shutdown(cls):
        if pytelicam is None:
            return
        if cls.cam_system is not None:
            cls.cam_system.terminate()

    @classmethod
    def discover(cls):
        if pytelicam is None:
            return []
        cameras = []
        try:
            cam_num = cls.cam_system.get_num_of_cameras()  # type: ignore
            for cam_no in range(cam_num):
                info = cls.cam_system.get_camera_information(cam_no)  # type: ignore
                cameras.append(
                    {
                        "type": "teli",
                        "serial": info.cam_serial_number,
                        "name": f"Toshiba Teli {info.cam_display_name}",
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to enumerate Toshiba Teli cameras: {e}")
            return []
        return cameras

    def __init__(self):
        self.cam_device = None

    def open(self, serial: str) -> bool:
        cam_num = ToshibaTeliCamera.cam_system.get_num_of_cameras()  # type: ignore
        for cam_no in range(cam_num):
            info = ToshibaTeliCamera.cam_system.get_camera_information(cam_no)  # type: ignore
            if info.cam_serial_number != serial:
                continue
            self.cam_device = ToshibaTeliCamera.cam_system.create_device_object(  # type: ignore
                cam_no
            )
            self.cam_device.open()
            self.cam_device.cam_stream.open()
            self.cam_device.cam_stream.start()
        return True

    def close(self):
        self.cam_device.cam_stream.stop()  # type: ignore
        self.cam_device.cam_stream.close()  # type: ignore
        self.cam_device.close()  # type: ignore

    def read(self):
        image_data = self.cam_device.cam_stream.get_next_image()  # type: ignore
        np_arr = image_data.get_ndarray(pytelicam.OutputImageType.Bgr24)  # type: ignore
        image_data.release()
        return True, np_arr

    def get_param(self, name):
        status = None
        value = None
        match name:
            case "width":
                status, value = self.cam_device.cam_control.get_width()  # type: ignore
            case "height":
                status, value = self.cam_device.cam_control.get_height()  # type: ignore
            case "fps":
                status, value = self.cam_device.cam_control.get_acquisition_frame_rate()  # type: ignore
            case "gain":
                status, value = self.cam_device.cam_control.get_gain()  # type: ignore
            case "exposure":
                status, value = self.cam_device.cam_control.get_exposure_time_control()  # type: ignore
        return value if status == pytelicam.CamApiStatus.Success else None  # type: ignore

    def set_param(self, name, value) -> bool:
        status = pytelicam.CamApiStatus.Success  # type: ignore
        match name:
            case "width":
                status = self.cam_device.cam_control.set_width(value)  # type: ignore
            case "height":
                status = self.cam_device.cam_control.set_height(value)  # type: ignore
            case "fps":
                status = self.cam_device.cam_control.set_acquisition_frame_rate(value)  # type: ignore
            case "gain":
                status = self.cam_device.cam_control.set_gain(value)  # type: ignore
            case "exposure":
                status = self.cam_device.cam_control.set_exposure_time_control()  # type: ignore
        return status == pytelicam.CamApiStatus.Success  # type: ignore

    def get_param_defs(self) -> dict[str, CameraParamDef]:
        result = {}
        if self.cam_device is None:
            return result

        for key, definition in self.PARAM_DEFS.items():
            item = dict(definition)

            try:
                item["value"] = self.get_param(key)
            except Exception:  # noqa: BLE001
                item["value"] = None

            result[key] = item

        return result

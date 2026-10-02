# camera/ids_ueye_camera.py

import logging
from typing import ClassVar

from numpy import ndarray

try:
    from pyueye import ueye  # type: ignore
except ImportError:
    ueye = None

from .base import CameraBase, CameraParamDef

logger = logging.getLogger(__name__)


class UeyeCamera(CameraBase):

    PARAM_DEFS: ClassVar[dict[str, CameraParamDef]] = {
        "width": {
            "label": "Width",
            "type": "number",
            "readonly": True,
            "unit": "px",
        },
        "height": {
            "label": "Height",
            "type": "number",
            "readonly": True,
            "unit": "px",
        },
        "fps": {
            "label": "FPS",
            "type": "range",
            "min": 1,
            "max": 200,
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
            "min": 0.1,
            "max": 1000,
            "step": 0.1,
            "unit": "ms",
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
        if ueye is None:
            return []
        cameras = []
        h_cam = ueye.HIDS(0)
        ret = ueye.is_InitCamera(h_cam, None)
        if ret != ueye.IS_SUCCESS:
            return []
        sensor = ueye.SENSORINFO()
        ueye.is_GetSensorInfo(h_cam, sensor)
        cameras.append(
            {
                "type": "ueye",
                "serial": "0",
                "name": sensor.strSensorName.decode(),
            }
        )
        ueye.is_ExitCamera(h_cam)
        return cameras

    def __init__(self):
        self.setup()

    def setup(self):
        if ueye is None:
            raise RuntimeError("ueye is not installed")
        try:
            self.h_cam = ueye.HIDS(0)

            # Exit program if no device was found
            if self.h_cam is None:
                logger.info("No device found.")

            ret = ueye.is_InitCamera(self.h_cam, None)
            if ret != ueye.IS_SUCCESS:
                raise RuntimeError("camera open failed")

            self.sensor = ueye.SENSORINFO()
            ueye.is_GetSensorInfo(self.h_cam, self.sensor)

            logger.info("model =", self.sensor.strSensorName)  # noqa: PLE1205

        except Exception as e:  # noqa: BLE001
            logger.error(f"Exception: {e}")

    def open(self, serial: str) -> bool:
        try:
            if ueye is None:
                return False
            self.width = int(self.sensor.nMaxWidth)
            self.height = int(self.sensor.nMaxHeight)

            self.bits = 24

            self.mem_ptr = ueye.c_mem_p()
            mem_id = ueye.INT()

            ueye.is_AllocImageMem(  # type: ignore
                self.h_cam,
                self.width,
                self.height,
                self.bits,
                self.mem_ptr,
                mem_id,
            )

            ueye.is_SetImageMem(self.h_cam, self.mem_ptr, mem_id)

            ueye.is_CaptureVideo(self.h_cam, ueye.IS_DONT_WAIT)

            self.pitch = ueye.INT()
            ueye.is_GetImageMemPitch(self.h_cam, self.pitch)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"Exception: {e}")
        return False

    def close(self):
        logger.info("Stopping acquisition...")
        try:
            ueye.is_ExitCamera(self.h_cam)  # type: ignore

        except Exception as e:  # noqa: BLE001
            logger.error(f"Exception: {e}")
        finally:
            self.device = None

    def read(self) -> tuple[bool, ndarray | None]:
        if ueye is None:
            return False, None
        try:
            raw = ueye.get_data(
                self.mem_ptr,
                self.width,
                self.height,
                self.bits,
                self.pitch,
                copy=True,
            )

            frame = raw.reshape(self.height, self.width, 3)  # type: ignore
            return True, frame
        except Exception as e:  # noqa: BLE001
            logger.error(f"Exception: {e}")
            return False, None

    def get_param(self, name) -> float | None:
        if ueye is None:
            return None
        try:
            match name:
                case "width":
                    return float(self.width)
                case "height":
                    return float(self.height)
                case "fps":
                    dblFPS = ueye.double()
                    nRet = ueye.is_SetFrameRate(
                        self.h_cam, ueye.IS_GET_FRAMERATE, dblFPS
                    )
                    if nRet != ueye.IS_SUCCESS:
                        return None
                    return float(dblFPS)
                case "gain":
                    sInfo = ueye.SENSORINFO()
                    nRet = ueye.is_GetSensorInfo(self.h_cam, sInfo)
                    if nRet != ueye.IS_SUCCESS:
                        return None
                    return float(sInfo.bMasterGain)
                case "exposure":
                    dExposure = ueye.double()
                    nRet = ueye.is_Exposure(
                        self.h_cam,
                        ueye.IS_EXPOSURE_CMD_GET_EXPOSURE,
                        dExposure,
                        ueye.sizeof(dExposure),
                    )
                    if nRet != ueye.IS_SUCCESS:
                        return None
                    return float(dExposure)
            return None

        except Exception as e:  # noqa: BLE001
            logger.error(f"get_param error: {e}")
            return None

    def set_param(self, name, value) -> bool:
        if ueye is None:
            return False
        try:
            nRet = ueye.IS_SUCCESS
            match name:
                case "width":
                    pass
                case "height":
                    pass
                case "fps":
                    targetFPS = float(value)
                    actualFPS = ueye.double()
                    nRet = ueye.is_SetFrameRate(
                        self.h_cam, targetFPS, actualFPS
                    )
                    logger.info(
                        f"set fps {targetFPS} -> {actualFPS}: return {nRet}"
                    )
                case "gain":
                    nMaster = int(value)
                    nRet = ueye.is_SetHardwareGain(
                        self.h_cam, nMaster, -1, -1, -1
                    )
                    logger.info(f"set gain to {nMaster}: return {nRet}")
                case "exposure":
                    time_exposure = ueye.double(value)
                    nRet = ueye.is_Exposure(
                        self.h_cam,
                        ueye.IS_EXPOSURE_CMD_SET_EXPOSURE,
                        time_exposure,
                        ueye.sizeof(time_exposure),
                    )
                    logger.info(
                        f"set exposure to {time_exposure}: return {nRet}"
                    )
            return nRet == ueye.IS_SUCCESS

        except Exception as e:  # noqa: BLE001
            logger.error(f"set_param error: {e}")
            return False

    def get_param_defs(self) -> dict[str, CameraParamDef]:
        result = {}
        if self.device is None:
            return result

        for key, definition in self.PARAM_DEFS.items():
            item = dict(definition)

            try:
                item["value"] = self.get_param(key)
            except Exception:  # noqa: BLE001
                item["value"] = None

            result[key] = item

        return result

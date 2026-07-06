from .base import CameraBase
from .basler_camera import BaslerCamera
from .gige_camera import GigEVisionCamera
from .ids_camera import IDSCamera
from .ids_ueye_camera import UeyeCamera
from .jai_camera import JAICamera
from .lucid_camera import LucidCamera
from .opencv_camera import OpenCVCamera
from .sentech_camera import SentechCamera
from .toshiba_teli_camera import ToshibaTeliCamera

CAMERA_TYPES: dict[str, type[CameraBase]] = {
    "opencv": OpenCVCamera,
    "sentech": SentechCamera,
    "lucid": LucidCamera,
    "jai": JAICamera,
    "teli": ToshibaTeliCamera,
    "ueye": UeyeCamera,
    "ids": IDSCamera,
    "basler": BaslerCamera,
    "gige": GigEVisionCamera,
}

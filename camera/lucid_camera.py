# camera/lucid_camera.py

from typing import ClassVar

import numpy as np

try:
    from arena_api.system import system  # type: ignore
except ImportError:
    system = None
except Exception:  # noqa: BLE001
    system = None
except BaseException:  # noqa: BLE001
    system = None

from .base import CameraBase, CameraParamDef


class LucidCamera(CameraBase):

    PARAMS: ClassVar[list[str]] = [
        "Width",
        "Height",
        "AcquisitionFrameRate",
        "Gain",
        "ExposureTime",
        "PixelFormat",
        "TriggerMode",
        "TriggerSource",
        "AcquisitionMode",
    ]

    @classmethod
    def initialize(cls):
        pass

    @classmethod
    def shutdown(cls):
        pass

    @classmethod
    def discover(cls):
        if system is None:
            return []
        cameras = []
        for info in system.device_infos:
            cameras.append(
                {
                    "type": "lucid",
                    "serial": info["serial"],
                    "name": f"LUCID {info['model']}",
                }
            )
        return cameras

    def __init__(self):
        self.device = None

    def open(self, serial: str) -> bool:
        if system is None:
            return False
        infos = system.device_infos
        for info in infos:
            if info["serial"] == serial:
                self.device = system.create_device([info])[0]
                self.device.start_stream()
                return True

        return False

    def close(self):
        if self.device:
            self.device.stop_stream()

    def read(self):
        if not self.device:
            return False, None
        buffer = self.device.get_buffer()
        frame = np.ctypeslib.as_array(
            buffer.pdata, shape=(buffer.height, buffer.width)
        ).copy()
        self.device.requeue_buffer(buffer)
        return True, frame

    def get_param(self, name):
        if not self.device:
            return None
        return self.device.nodemap[name].value

    def set_param(self, name, value):
        if not self.device:
            return False
        self.device.nodemap[name].value = value
        return True

    def get_param_defs(self) -> dict[str, CameraParamDef]:
        if not self.device:
            return {}

        result = {}

        for key in self.PARAMS:
            try:
                node = self.device.nodemap[key]
                value = node.value
                item = {
                    "label": key,
                    "type": "number",
                    "value": value,
                }

                # Enumeration
                try:
                    entries = node.entries
                    if entries:
                        options = []
                        for entry in entries:
                            try:
                                options.append(
                                    {
                                        "value": entry.value,
                                        "label": getattr(
                                            entry,
                                            "symbolic",
                                            str(entry.value),
                                        ),
                                    }
                                )
                            except Exception:  # noqa: BLE001, S112
                                continue

                        if options:
                            item["type"] = "select"
                            item["options"] = options
                except Exception:  # noqa: BLE001, S110
                    pass

                # Numeric
                if item["type"] == "number":
                    try:
                        item["min"] = node.min
                    except Exception:  # noqa: BLE001, S110
                        pass

                    try:
                        item["max"] = node.max
                    except Exception:  # noqa: BLE001, S110
                        pass

                    try:
                        item["step"] = node.inc
                    except Exception:  # noqa: BLE001, S110
                        pass

                    if "min" in item and "max" in item:
                        item["type"] = "range"

                try:
                    item["readonly"] = not node.is_writable
                except Exception:  # noqa: BLE001
                    item["readonly"] = False

                result[key] = item

            except Exception:  # noqa: BLE001, S112
                continue

        return result

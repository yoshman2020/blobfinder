# camera/jai_camera.py

from typing import ClassVar

try:
    from harvesters.core import Harvester  # type: ignore
except ImportError:
    Harvester = None

from .base import CameraBase, CameraParamDef


class JAICamera(CameraBase):

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
        if Harvester is None:
            return []
        cameras = []
        h = Harvester()
        h.update()
        for info in h.device_info_list:
            cameras.append(
                {
                    "type": "jaiTeli",
                    "serial": str(info.serial_number),
                    "name": f"JAI / ToshibaTeli {info.model}",
                }
            )
        return cameras

    def __init__(self):
        self.h = Harvester()  # type: ignore
        self.ia = None

    def open(self, serial: str) -> bool:
        # self.h.add_file(r"C:\Program Files\JAI\GenTLProducer.cti")
        self.h.update()
        self.ia = self.h.create({"serial_number": serial})
        self.ia.start()
        return True

    def close(self):
        if self.ia:
            self.ia.stop()

    def read(self):
        assert self.ia is not None
        with self.ia.fetch() as buffer:
            frame = buffer.payload.components[0].data.copy()
        return True, frame

    def get_param(self, name):
        assert self.ia is not None
        return self.ia.remote_device.node_map[name].value

    def set_param(self, name, value):
        assert self.ia is not None
        self.ia.remote_device.node_map[name].value = value
        return True

    def get_param_defs(self) -> dict[str, CameraParamDef]:
        if self.ia is None:
            return {}

        result = {}

        for key in self.PARAMS:
            try:
                node = self.ia.remote_device.node_map[key]

                item = {
                    "label": key,
                    "type": "number",
                    "options": [],
                }

                try:
                    item["value"] = node.value
                except Exception:  # noqa: BLE001, S112
                    continue

                # Enumeration
                try:
                    if hasattr(node, "symbolics"):
                        options = []

                        for option in node.symbolics:
                            options.append(
                                {
                                    "value": option,
                                    "label": option,
                                }
                            )

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

try:
    from harvesters.core import Harvester
except ImportError:
    Harvester = None

from .base import CameraBase


class JAICamera(CameraBase):

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
        self.h = Harvester()
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
        with self.ia.fetch() as buffer:
            frame = buffer.payload.components[0].data.copy()
        return True, frame

    def get_param(self, name):
        return self.ia.remote_device.node_map[name].value

    def set_param(self, name, value):
        self.ia.remote_device.node_map[name].value = value

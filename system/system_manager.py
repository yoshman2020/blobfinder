import logging

from camera.manager import CAMERA_TYPES

logger = logging.getLogger(__name__)


class SystemManager:
    def initialize(self):
        for camera_cls in CAMERA_TYPES.values():
            try:
                camera_cls.initialize()
            except Exception:
                logger.exception(
                    "Failed to initialize %s",
                    camera_cls.__name__,
                )

    def shutdown(self):
        for camera_cls in CAMERA_TYPES.values():
            try:
                camera_cls.shutdown()
            except Exception:
                logger.exception(
                    "Failed to shutdown %s",
                    camera_cls.__name__,
                )

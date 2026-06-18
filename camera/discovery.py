# camera/discovery.py

import logging
import threading
import uuid

from .camera_types import CAMERA_TYPES

logger = logging.getLogger(__name__)

_registry_lock = threading.Lock()

_CAMERA_REGISTRY = {}


def clear_registry():
    with _registry_lock:
        _CAMERA_REGISTRY.clear()


def register_camera(camera_type: str, serial: str, name: str, index: int):
    uid = str(uuid.uuid4())

    info = {
        "uid": uid,
        "type": camera_type,
        "serial": serial,
        "name": name,
        "index": index,
    }

    _CAMERA_REGISTRY[uid] = info
    return info


def get_camera_info(uid: str):
    with _registry_lock:
        return _CAMERA_REGISTRY.get(uid)


def discover_all():
    clear_registry()
    cameras = []
    idx = 0

    for camera_cls in CAMERA_TYPES.values():
        try:
            for info in camera_cls.discover():
                cameras.append(
                    register_camera(
                        info["type"],
                        info["serial"],
                        info["name"],
                        idx,
                    )
                )
                idx += 1

        except Exception:
            logger.exception(
                "discover failed: %s",
                camera_cls.__name__,
            )
    logger.info(f"Discovered {len(cameras)} cameras")
    return cameras

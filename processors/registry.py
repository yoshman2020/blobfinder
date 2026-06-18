# registry.py

import threading

_registry = {}
_registry_lock = threading.Lock()


def register(name: str):
    def decorator(func):
        with _registry_lock:
            if name in _registry:
                raise ValueError(f"processor '{name}' already registered")

            _registry[name] = func

        return func

    return decorator


def get_processor(name: str):
    try:
        return _registry[name]
    except KeyError:
        raise ValueError(f"unknown process: {name}")


def get_processors():
    return _registry.copy()

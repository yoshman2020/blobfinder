# camera/base.py

from abc import ABC, abstractmethod
from typing import Any, TypedDict

from numpy import ndarray


class CameraInfo(TypedDict):
    uid: str
    type: str
    serial: str
    name: str
    index: int


class CameraParamDef(TypedDict, total=False):
    key: str
    label: str
    type: str

    # number / range
    value: Any
    min: float
    max: float
    step: float

    # select
    options: list[dict]

    # UI
    readonly: bool
    unit: str


class CameraBase(ABC):

    @classmethod
    @abstractmethod
    def discover(cls) -> list[dict]:
        pass

    @classmethod
    @abstractmethod
    def initialize(cls):
        pass

    @classmethod
    @abstractmethod
    def shutdown(cls):
        pass

    @abstractmethod
    def open(self, serial: str) -> bool:
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def read(self) -> tuple[bool, ndarray | None]:
        pass

    @abstractmethod
    def get_param(self, name: str) -> float | None:
        pass

    @abstractmethod
    def set_param(self, name: str, value) -> bool:
        pass

    @abstractmethod
    def get_param_defs(self) -> dict[str, CameraParamDef]:
        return {}

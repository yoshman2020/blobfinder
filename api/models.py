from typing import Any

from pydantic import BaseModel, Field


class ProcessStep(BaseModel):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ProcessRequest(BaseModel):
    pipeline: list[ProcessStep]

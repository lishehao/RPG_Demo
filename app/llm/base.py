from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class RouteIntentResult(BaseModel):
    move_id: str
    args: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    interpreted_intent: str


class LLMProvider(ABC):
    @abstractmethod
    def route_intent(self, scene_context: dict[str, Any], text: str) -> RouteIntentResult:
        raise NotImplementedError

    @abstractmethod
    def render_narration(self, slots: dict[str, Any], style_guard: str) -> str:
        raise NotImplementedError

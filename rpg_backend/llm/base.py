from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMJsonObjectResult:
    payload: dict[str, Any]
    duration_ms: int


class LLMProviderConfigError(RuntimeError):
    """Raised when provider is selected but missing required config."""


class LLMProvider(ABC):
    gateway_mode: str
    route_model: str
    narration_model: str
    timeout_seconds: float
    route_max_retries: int
    narration_max_retries: int
    route_temperature: float
    narration_temperature: float

    @abstractmethod
    async def invoke_json_object(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_retries: int,
        timeout_seconds: float,
    ) -> LLMJsonObjectResult:
        raise NotImplementedError

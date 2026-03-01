from __future__ import annotations

from typing import Any

from app.llm.base import LLMProvider, RouteIntentResult


class OpenAIProvider(LLMProvider):
    """Placeholder provider for future OpenAI Responses API integration."""

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def route_intent(self, scene_context: dict[str, Any], text: str) -> RouteIntentResult:
        raise RuntimeError("OpenAIProvider is not enabled in this offline-first build.")

    def render_narration(self, slots: dict[str, Any], style_guard: str) -> str:
        raise RuntimeError("OpenAIProvider is not enabled in this offline-first build.")

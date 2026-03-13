from __future__ import annotations

from threading import Barrier
from typing import Any

from rpg_backend.llm.agents import AgentDiagnostics, AgentUsage, PlayInterpretResult, PlayRenderResult


def _diagnostics(model: str = "test-responses-model") -> AgentDiagnostics:
    return AgentDiagnostics(
        agent_model=model,
        agent_mode="responses",
        response_id="resp_test_123",
        reasoning_summary=None,
        duration_ms=5,
        usage=AgentUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


class _BaseFakeProvider:
    model = "test-responses-model"
    mode = "responses"

    def __init__(self) -> None:
        self.play_agent = self

    async def interpret_turn(
        self,
        *,
        session_id: str,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> PlayInterpretResult:
        del session_id
        payload = self._route_payload(
            scene_context=scene_context,
            route_candidates=route_candidates,
            text=text,
        )
        return PlayInterpretResult(
            selected_key=str(payload["selected_key"]),
            confidence=float(payload["confidence"]),
            interpreted_intent=str(payload["interpreted_intent"]),
            diagnostics=_diagnostics(self.model),
        )

    async def render_resolved_turn(
        self,
        *,
        session_id: str,
        narration_context: dict[str, Any],
        prompt_slots: dict[str, Any],
        style_guard: str,
    ) -> PlayRenderResult:
        del session_id, narration_context, style_guard
        payload = self._narration_payload(prompt_slots=prompt_slots)
        return PlayRenderResult(
            narration_text=str(payload["narration_text"]),
            diagnostics=_diagnostics(self.model),
        )

    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _narration_payload(self, *, prompt_slots: dict[str, Any]) -> dict[str, Any]:
        return {
            "narration_text": f"{prompt_slots.get('echo', '')} {prompt_slots.get('commit', '')} {prompt_slots.get('hook', '')}".strip()
        }


class DeterministicProvider(_BaseFakeProvider):
    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        fallback_move = scene_context.get("fallback_move")
        selected_key = route_candidates[0]["key"] if route_candidates else "m0"
        for candidate in route_candidates:
            if candidate.get("move_id") == fallback_move:
                selected_key = str(candidate["key"])
                break
        return {
            "selected_key": selected_key,
            "confidence": 0.95,
            "interpreted_intent": (text or "").strip() or "help me progress",
        }


class RouteFailureProvider(_BaseFakeProvider):
    async def interpret_turn(self, **kwargs):  # noqa: ANN003, ANN201
        raise RuntimeError("route failed")

    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        raise AssertionError("unreachable")


class LowConfidenceProvider(_BaseFakeProvider):
    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        selected_key = route_candidates[0]["key"] if route_candidates else "m0"
        return {
            "selected_key": selected_key,
            "confidence": 0.1,
            "interpreted_intent": (text or "").strip() or "unclear intent",
        }


class InvalidMoveProvider(_BaseFakeProvider):
    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        return {
            "selected_key": "m999",
            "confidence": 0.95,
            "interpreted_intent": (text or "").strip() or "invalid move intent",
        }


class NarrationFailureProvider(_BaseFakeProvider):
    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        selected_key = route_candidates[0]["key"] if route_candidates else "m0"
        return {
            "selected_key": selected_key,
            "confidence": 0.9,
            "interpreted_intent": (text or "").strip() or "unclear intent",
        }

    async def render_resolved_turn(self, **kwargs):  # noqa: ANN003, ANN201
        raise RuntimeError("narration failed")


class AlwaysGlobalHelpProvider(_BaseFakeProvider):
    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        selected_key = "m999"
        for candidate in route_candidates:
            intents = [str(item).lower() for item in candidate.get("intents", [])]
            label = str(candidate.get("label") or "").lower()
            if candidate.get("is_global") and ("help" in label or "help" in intents):
                selected_key = str(candidate.get("key") or "m999")
                break
        return {
            "selected_key": selected_key,
            "confidence": 0.95,
            "interpreted_intent": (text or "").strip() or "help me progress",
        }


class BarrierDeterministicProvider(DeterministicProvider):
    def __init__(self, barrier: Barrier):
        super().__init__()
        self._barrier = barrier

    def _route_payload(
        self,
        *,
        scene_context: dict[str, Any],
        route_candidates: list[dict[str, Any]],
        text: str,
    ) -> dict[str, Any]:
        self._barrier.wait(timeout=3)
        return super()._route_payload(
            scene_context=scene_context,
            route_candidates=route_candidates,
            text=text,
        )


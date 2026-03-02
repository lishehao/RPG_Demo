from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.pack_schema import StoryPack
from app.llm.base import LLMProvider, RouteIntentResult
from app.runtime.errors import RuntimeNarrationError, RuntimeRouteError
from app.runtime.service import RuntimeService

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _load_pack() -> StoryPack:
    return StoryPack.model_validate(json.loads(PACK_PATH.read_text(encoding="utf-8")))


class _DeterministicProvider(LLMProvider):
    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        fallback = scene_context.get("fallback_move", "global.help_me_progress")
        return RouteIntentResult(
            move_id=fallback,
            args={},
            confidence=0.95,
            interpreted_intent=(text or "").strip() or "help me progress",
        )

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        return f"{slots['echo']} {slots['commit']} {slots['hook']}"


class _RouteFailProvider(LLMProvider):
    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        raise RuntimeError("route failed")

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        return f"{slots['echo']} {slots['commit']} {slots['hook']}"


class _LowConfidenceProvider(LLMProvider):
    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        fallback = scene_context.get("fallback_move", "global.help_me_progress")
        return RouteIntentResult(
            move_id=fallback,
            args={},
            confidence=0.1,
            interpreted_intent=text or "unclear intent",
        )

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        return f"{slots['echo']} {slots['commit']} {slots['hook']}"


class _InvalidMoveProvider(LLMProvider):
    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        return RouteIntentResult(
            move_id="move.not.available",
            args={},
            confidence=0.95,
            interpreted_intent=text or "invalid move intent",
        )

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        return f"{slots['echo']} {slots['commit']} {slots['hook']}"


class _NarrationFailProvider(LLMProvider):
    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        fallback = scene_context.get("fallback_move", "global.help_me_progress")
        return RouteIntentResult(
            move_id=fallback,
            args={},
            confidence=0.9,
            interpreted_intent=text or "unclear intent",
        )

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        raise RuntimeError("narration failed")


def test_fail_forward_on_unmet_precondition() -> None:
    pack = _load_pack()
    runtime = RuntimeService(_DeterministicProvider())
    _, _, state, beat_progress = runtime.initialize_session_state(pack)

    result = runtime.process_step(
        pack,
        current_scene_id="sc5",
        beat_index=1,
        state=state,
        beat_progress=beat_progress,
        action_input={"type": "button", "move_id": "decode_core"},
        dev_mode=True,
    )

    assert result["resolution"]["result"] == "fail_forward"
    assert result["resolution"]["consequences_summary"] != "none"


def test_empty_text_can_progress_when_route_returns_confident_move() -> None:
    pack = _load_pack()
    runtime = RuntimeService(_DeterministicProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    result = runtime.process_step(
        pack,
        current_scene_id=scene_id,
        beat_index=beat_index,
        state=state,
        beat_progress=beat_progress,
        action_input={"type": "text", "text": ""},
    )

    assert result["recognized"]["move_id"]
    assert result["recognized"]["route_source"] == "llm"
    assert result["scene_id"] != scene_id


def test_route_failure_raises_runtime_route_error() -> None:
    pack = _load_pack()
    runtime = RuntimeService(_RouteFailProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    with pytest.raises(RuntimeRouteError) as exc_info:
        runtime.process_step(
            pack,
            current_scene_id=scene_id,
            beat_index=beat_index,
            state=state,
            beat_progress=beat_progress,
            action_input={"type": "text", "text": "do something risky"},
        )

    assert exc_info.value.error_code == "llm_route_failed"
    assert exc_info.value.stage == "route"


def test_low_confidence_raises_runtime_route_error() -> None:
    pack = _load_pack()
    runtime = RuntimeService(_LowConfidenceProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    with pytest.raises(RuntimeRouteError) as exc_info:
        runtime.process_step(
            pack,
            current_scene_id=scene_id,
            beat_index=beat_index,
            state=state,
            beat_progress=beat_progress,
            action_input={"type": "text", "text": "???"},
        )

    assert exc_info.value.error_code == "llm_route_low_confidence"
    assert exc_info.value.stage == "route"


def test_narration_failure_raises_runtime_narration_error() -> None:
    pack = _load_pack()
    runtime = RuntimeService(_NarrationFailProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    with pytest.raises(RuntimeNarrationError) as exc_info:
        runtime.process_step(
            pack,
            current_scene_id=scene_id,
            beat_index=beat_index,
            state=state,
            beat_progress=beat_progress,
            action_input={"type": "text", "text": "help me progress"},
        )

    assert exc_info.value.error_code == "llm_narration_failed"
    assert exc_info.value.stage == "narration"


def test_invalid_move_raises_runtime_route_error() -> None:
    pack = _load_pack()
    runtime = RuntimeService(_InvalidMoveProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    with pytest.raises(RuntimeRouteError) as exc_info:
        runtime.process_step(
            pack,
            current_scene_id=scene_id,
            beat_index=beat_index,
            state=state,
            beat_progress=beat_progress,
            action_input={"type": "text", "text": "do a hidden action"},
        )

    assert exc_info.value.error_code == "llm_route_invalid_move"
    assert exc_info.value.stage == "route"

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class RouteIntentPayload(BaseModel):
    move_id: str
    args: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    interpreted_intent: str


class NarrationPayload(BaseModel):
    narration_text: str


class ReadinessProbePayload(BaseModel):
    ok: bool
    who: str


@dataclass(frozen=True)
class TaskSpec:
    task_name: str
    system_prompt: str
    user_payload: Any


def build_route_intent_task(*, scene_context: dict[str, Any], text: str) -> TaskSpec:
    return TaskSpec(
        task_name="route_intent",
        system_prompt=(
            "You route player text to a move. "
            "Return JSON only with keys: move_id (string), args (object), confidence (0..1), interpreted_intent (string). "
            "Prefer scene-specific moves over global moves. "
            "Use scene_snapshot and state_snapshot to infer intent from current pressure, beat goals, and recent events. "
            "Use global.help_me_progress only when the user explicitly asks for help or says they are stuck."
        ),
        user_payload={
            "task": "route_intent",
            "input_text": text or "",
            "fallback_move": scene_context.get("fallback_move"),
            "moves": scene_context.get("moves", []),
            "scene_seed": scene_context.get("scene_seed", ""),
            "scene_snapshot": scene_context.get("scene_snapshot", {}),
            "state_snapshot": scene_context.get("state_snapshot", {}),
            "route_policy": {
                "prefer_scene_specific": True,
                "allow_global_help": bool(scene_context.get("allow_global_help", False)),
            },
        },
    )


def build_render_narration_task(*, slots: dict[str, Any], style_guard: str) -> TaskSpec:
    return TaskSpec(
        task_name="render_narration",
        system_prompt=(
            "Write one concise narration paragraph from given slots. "
            "Return JSON only with key narration_text (string)."
        ),
        user_payload={
            "task": "render_narration",
            "style_guard": style_guard,
            "slots": slots,
        },
    )


def build_readiness_probe_task() -> TaskSpec:
    return TaskSpec(
        task_name="readiness_probe",
        system_prompt="Readiness probe. Return JSON only with keys ok, who.",
        user_payload="who are you",
    )


def validate_route_intent_payload(payload: dict[str, Any]) -> RouteIntentPayload:
    try:
        parsed = RouteIntentPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if not parsed.move_id.strip():
        raise ValueError("move_id is blank")
    if not parsed.interpreted_intent.strip():
        raise ValueError("interpreted_intent is blank")
    return parsed


def validate_narration_payload(payload: dict[str, Any]) -> NarrationPayload:
    try:
        parsed = NarrationPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if not parsed.narration_text.strip():
        raise ValueError("narration_text is blank")
    return parsed


def validate_readiness_probe_payload(payload: dict[str, Any]) -> ReadinessProbePayload:
    try:
        parsed = ReadinessProbePayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if parsed.ok is not True:
        raise ValueError("probe response ok is not true")
    if not parsed.who.strip():
        raise ValueError("probe response who is blank")
    return parsed

from __future__ import annotations

import pytest

from rpg_backend.llm.task_specs import (
    build_readiness_probe_task,
    build_render_narration_task,
    build_route_intent_task,
    validate_narration_payload,
    validate_readiness_probe_payload,
    validate_route_intent_payload,
)


def test_build_route_intent_task_contains_policy_and_snapshots() -> None:
    spec = build_route_intent_task(
        scene_context={
            "fallback_move": "global.help_me_progress",
            "moves": [{"id": "scan"}],
            "scene_snapshot": {"scene_id": "s1"},
            "state_snapshot": {"pressure": {"noise": 1}},
            "allow_global_help": False,
        },
        text="scan now",
    )
    assert spec.task_name == "route_intent"
    assert spec.user_payload["task"] == "route_intent"
    assert spec.user_payload["route_policy"]["prefer_scene_specific"] is True
    assert spec.user_payload["route_policy"]["allow_global_help"] is False
    assert spec.user_payload["scene_snapshot"]["scene_id"] == "s1"


def test_validate_route_intent_payload_rejects_blank_fields() -> None:
    with pytest.raises(ValueError):
        validate_route_intent_payload(
            {
                "move_id": "",
                "args": {},
                "confidence": 0.5,
                "interpreted_intent": "ok",
            }
        )


def test_build_and_validate_render_narration_task() -> None:
    spec = build_render_narration_task(
        slots={"echo": "signal", "hook": "deadline"},
        style_guard="tense",
    )
    assert spec.task_name == "render_narration"
    parsed = validate_narration_payload({"narration_text": "Systems stutter as alarms flare."})
    assert parsed.narration_text.startswith("Systems")


def test_readiness_probe_task_and_payload_validation() -> None:
    spec = build_readiness_probe_task()
    assert spec.task_name == "readiness_probe"
    assert spec.user_payload == "who are you"
    parsed = validate_readiness_probe_payload({"ok": True, "who": "worker-ready"})
    assert parsed.ok is True

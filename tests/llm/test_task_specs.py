from __future__ import annotations

from rpg_backend.llm.task_specs import build_readiness_probe_task, validate_readiness_probe_payload


def test_readiness_probe_task_and_payload_validation() -> None:
    spec = build_readiness_probe_task()
    assert spec.task_name == "readiness_probe"
    assert spec.user_payload == "who are you"
    parsed = validate_readiness_probe_payload({"ok": True, "who": "worker-ready"})
    assert parsed.ok is True

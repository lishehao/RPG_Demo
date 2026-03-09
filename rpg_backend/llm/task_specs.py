from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class ReadinessProbePayload(BaseModel):
    ok: bool
    who: str


@dataclass(frozen=True)
class TaskSpec:
    task_name: str
    system_prompt: str
    user_payload: Any


def build_readiness_probe_task() -> TaskSpec:
    return TaskSpec(
        task_name="readiness_probe",
        system_prompt="Readiness probe. Return JSON only with keys ok, who.",
        user_payload="who are you",
    )


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

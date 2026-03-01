from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepairResult:
    pack_json: dict[str, Any]
    applied: bool
    attempts: int
    notes: list[str] = field(default_factory=list)


def repair_story_pack(pack_json: dict[str, Any], max_attempts: int = 2) -> RepairResult:
    _ = max_attempts
    return RepairResult(
        pack_json=pack_json,
        applied=False,
        attempts=0,
        notes=["auto-repair placeholder: not implemented"],
    )

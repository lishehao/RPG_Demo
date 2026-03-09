from __future__ import annotations

import re
from dataclasses import dataclass, field

from rpg_backend.domain.conflict_tags import NPCConflictTag
from rpg_backend.generator.defaults import default_npc_conflict_tags, default_npc_red_line


@dataclass(frozen=True)
class BeatPlanItem:
    beat_id: str
    title: str
    step_budget: int
    required_events: list[str]
    npc_quota: int
    entry_scene_id: str
    objective: str
    conflict: str
    scene_intent: str


@dataclass(frozen=True)
class BeatPlan:
    seed_text: str
    target_minutes: int
    target_steps: int
    npc_names: list[str]
    beats: list[BeatPlanItem]
    story_title: str | None = None
    premise: str | None = None
    stakes: str | None = None
    tone: str | None = None
    move_bias: list[str] = field(default_factory=list)
    spec_summary: dict[str, object] | None = None
    npc_red_lines: dict[str, str] = field(default_factory=dict)
    npc_conflict_tags: dict[str, list[NPCConflictTag]] = field(default_factory=dict)


_NAME_POOL = [
    "Kael",
    "Mira",
    "Rook",
    "Tamsin",
    "Vale",
    "Iris",
    "Sera",
    "Dane",
    "Lio",
    "Nyra",
]


def _stable_seed_value(seed_text: str) -> int:
    return sum((idx + 1) * ord(ch) for idx, ch in enumerate(seed_text))


def _select_npc_names(seed_text: str, npc_count: int) -> list[str]:
    start = _stable_seed_value(seed_text) % len(_NAME_POOL)
    ordered = _NAME_POOL[start:] + _NAME_POOL[:start]
    return ordered[:npc_count]


def _target_steps_from_minutes(target_minutes: int) -> int:
    guessed = int(round(target_minutes * 1.5))
    return max(14, min(16, guessed))


def _distribute_step_budget(target_steps: int, beat_count: int = 4) -> list[int]:
    budgets = [3 for _ in range(beat_count)]
    remaining = target_steps - sum(budgets)
    idx = 0
    while remaining > 0:
        if budgets[idx] < 4:
            budgets[idx] += 1
            remaining -= 1
        idx = (idx + 1) % beat_count
    return budgets


def _slug(text: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return compact[:28] or "milestone"


def plan_beats(seed_text: str, target_minutes: int, npc_count: int) -> BeatPlan:
    target_steps = _target_steps_from_minutes(target_minutes)
    beat_ids = ["b1", "b2", "b3", "b4"]
    beat_titles = [
        "Inciting Signal",
        "Crossfire Corridor",
        "Core Descent",
        "Dawn Resolution",
    ]
    entry_scene_ids = ["sc1", "sc5", "sc8", "sc12"]
    budgets = _distribute_step_budget(target_steps, beat_count=4)

    beats = [
        BeatPlanItem(
            beat_id=beat_id,
            title=beat_titles[i],
            step_budget=budgets[i],
            required_events=[f"{beat_id}.{_slug(beat_titles[i])}"],
            npc_quota=2,
            entry_scene_id=entry_scene_ids[i],
            objective=f"Advance {beat_titles[i].lower()}",
            conflict="Escalating pressure from the city-wide signal breach.",
            scene_intent=f"Push toward {beat_titles[i].lower()} without stalling momentum.",
        )
        for i, beat_id in enumerate(beat_ids)
    ]

    npc_names = _select_npc_names(seed_text, npc_count)
    npc_red_lines = {name: default_npc_red_line(name, idx) for idx, name in enumerate(npc_names)}
    npc_conflict_tags = {name: default_npc_conflict_tags(idx) for idx, name in enumerate(npc_names)}

    return BeatPlan(
        seed_text=seed_text,
        target_minutes=target_minutes,
        target_steps=target_steps,
        npc_names=npc_names,
        beats=beats,
        npc_red_lines=npc_red_lines,
        npc_conflict_tags=npc_conflict_tags,
    )

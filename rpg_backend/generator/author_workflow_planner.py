from __future__ import annotations

from rpg_backend.generator.author_workflow_models import BeatBlueprint, StoryOverview


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


def plan_beat_blueprints_from_overview(overview: StoryOverview) -> list[BeatBlueprint]:
    target_steps = _target_steps_from_minutes(overview.target_minutes)
    budgets = _distribute_step_budget(target_steps, beat_count=4)
    phase_titles = [
        "Opening Pressure",
        "Escalation Corridor",
        "Public Reckoning",
        "Final Tradeoff",
    ]
    return [
        BeatBlueprint(
            beat_id=f"b{index + 1}",
            title=phase_titles[index],
            objective=f"Advance {phase_titles[index].lower()} within the frame of {overview.stakes}",
            conflict=(
                f"Keep the story aligned with '{overview.premise}' while increasing pressure around {overview.stakes}."
            ),
            required_event=f"b{index + 1}.milestone",
            step_budget=budgets[index],
            npc_quota=2,
            entry_scene_id=f"b{index + 1}.sc1",
            scene_intent=(
                f"Express {phase_titles[index].lower()} in a {overview.tone.lower()} way without breaking prior beat details."
            ),
        )
        for index in range(4)
    ]


def check_beat_blueprints(blueprints: list[BeatBlueprint]) -> list[str]:
    errors: list[str] = []
    if len(blueprints) != 4:
        errors.append("beat_blueprints must contain exactly 4 items")
        return errors
    beat_ids = [item.beat_id for item in blueprints]
    if len(set(beat_ids)) != len(beat_ids):
        errors.append("beat_blueprints beat_id values must be unique")
    titles = [item.title.strip().casefold() for item in blueprints]
    if len(set(titles)) != len(titles):
        errors.append("beat_blueprints titles must be unique")
    entry_scene_ids = [item.entry_scene_id for item in blueprints]
    if len(set(entry_scene_ids)) != len(entry_scene_ids):
        errors.append("beat_blueprints entry_scene_id values must be unique")
    required_events = [item.required_event for item in blueprints]
    if len(set(required_events)) != len(required_events):
        errors.append("beat_blueprints required_event values must be unique")
    return errors

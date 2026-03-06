from __future__ import annotations

from typing import Any

from rpg_backend.domain.pack_schema import Move, Outcome, Scene
from rpg_backend.runtime.effects import evaluate_preconditions


def choose_outcome(
    move: Move,
    state: dict[str, Any],
    beat_progress: dict[str, int],
    current_beat_id: str,
) -> Outcome:
    if move.resolution_policy == "always_fail_forward":
        for outcome in move.outcomes:
            if outcome.result == "fail_forward":
                return outcome

    if move.resolution_policy == "prefer_partial":
        ordered_results = ["partial", "success", "fail_forward"]
    else:
        ordered_results = ["success", "partial", "fail_forward"]

    fail_forward = next((o for o in move.outcomes if o.result == "fail_forward"), move.outcomes[0])

    for result in ordered_results:
        for outcome in move.outcomes:
            if outcome.result != result:
                continue
            if evaluate_preconditions(outcome.preconditions, state, beat_progress, current_beat_id):
                return outcome

    return fail_forward


def _exit_condition_matches(
    condition,
    state: dict[str, Any],
    beat_progress: dict[str, int],
    beat_id: str,
) -> bool:
    kind = condition.condition_kind
    if kind == "always":
        return True
    if kind == "event_present":
        key = condition.key
        return bool(key and key in state.get("events", []))
    if kind == "state_equals":
        key = condition.key
        if key is None:
            return False
        return state.get("values", {}).get(key) == condition.value
    if kind == "beat_progress_gte":
        target_beat = condition.key or beat_id
        threshold = int(condition.value or 0)
        return beat_progress.get(target_beat, 0) >= threshold
    return False


def resolve_next_scene(
    scene: Scene,
    outcome: Outcome,
    state: dict[str, Any],
    beat_progress: dict[str, int],
    current_beat_id: str,
) -> tuple[str | None, bool]:
    if outcome.next_scene_id:
        return outcome.next_scene_id, False

    for condition in scene.exit_conditions:
        if _exit_condition_matches(condition, state, beat_progress, current_beat_id):
            if condition.end_story:
                return None, True
            return condition.next_scene_id, False

    return None, bool(scene.is_terminal)

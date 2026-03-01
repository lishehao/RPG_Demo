from __future__ import annotations

from typing import Any

from app.domain.pack_schema import Condition, Effect


def _events(state: dict[str, Any]) -> list[str]:
    state.setdefault("events", [])
    return state["events"]


def _inventory(state: dict[str, Any]) -> list[str]:
    state.setdefault("inventory", [])
    return state["inventory"]


def _flags(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("flags", {})
    return state["flags"]


def _values(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("values", {})
    return state["values"]


def evaluate_preconditions(
    preconditions: list[Condition],
    state: dict[str, Any],
    beat_progress: dict[str, int],
    current_beat_id: str,
) -> bool:
    for cond in preconditions:
        if cond.kind == "always":
            continue

        if cond.kind == "event_present":
            if not cond.key or cond.key not in _events(state):
                return False
            continue

        if cond.kind == "state_equals":
            if cond.key is None:
                return False
            if _values(state).get(cond.key) != cond.value:
                return False
            continue

        if cond.kind == "state_gte":
            if cond.key is None:
                return False
            current = _values(state).get(cond.key, 0)
            try:
                if float(current) < float(cond.value):
                    return False
            except (TypeError, ValueError):
                return False
            continue

        if cond.kind == "inventory_has":
            if not cond.key or cond.key not in _inventory(state):
                return False
            continue

        if cond.kind == "beat_progress_gte":
            beat_id = cond.key or current_beat_id
            threshold = int(cond.value or 0)
            if beat_progress.get(beat_id, 0) < threshold:
                return False
            continue

        return False

    return True


def apply_effects(
    effects: list[Effect],
    state: dict[str, Any],
    beat_progress: dict[str, int],
    current_beat_id: str,
) -> tuple[list[str], list[str], bool]:
    costs: list[str] = []
    consequences: list[str] = []
    changed = False

    for effect in effects:
        if effect.type == "add_event":
            key = effect.key
            if key and key not in _events(state):
                _events(state).append(key)
                consequences.append(f"Event '{key}' recorded")
                changed = True
            continue

        if effect.type == "add_inventory":
            key = effect.key
            if key and key not in _inventory(state):
                _inventory(state).append(key)
                consequences.append(f"You gained '{key}'")
                changed = True
            continue

        if effect.type == "remove_inventory":
            key = effect.key
            if key and key in _inventory(state):
                _inventory(state).remove(key)
                consequences.append(f"You used '{key}'")
                changed = True
            continue

        if effect.type == "set_flag":
            if effect.key:
                _flags(state)[effect.key] = effect.value
                consequences.append(f"Flag '{effect.key}' updated")
                changed = True
            continue

        if effect.type == "set_state":
            if effect.key:
                _values(state)[effect.key] = effect.value
                consequences.append(f"State '{effect.key}' set")
                changed = True
            continue

        if effect.type == "inc_state":
            if effect.key:
                current = _values(state).get(effect.key, 0)
                delta = int(effect.value or 1)
                _values(state)[effect.key] = int(current) + delta
                consequences.append(f"State '{effect.key}' changed by {delta}")
                changed = True
            continue

        if effect.type == "advance_beat_progress":
            delta = int(effect.value or 1)
            beat_progress[current_beat_id] = beat_progress.get(current_beat_id, 0) + delta
            consequences.append(f"Beat '{current_beat_id}' progress +{delta}")
            changed = True
            continue

        if effect.type == "cost":
            delta = int(effect.value or 1)
            _values(state)["cost_total"] = int(_values(state).get("cost_total", 0)) + delta
            costs.append(f"Cost +{delta}")
            changed = True
            continue

    if not changed:
        _values(state)["time_pressure"] = int(_values(state).get("time_pressure", 0)) + 1
        consequences.append("Time pressure increases")
        changed = True

    return costs, consequences, changed

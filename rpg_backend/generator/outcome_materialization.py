from __future__ import annotations

import hashlib
import random
from typing import Any

from rpg_backend.domain.outcome_palette import OUTCOME_PALETTE_BY_ID, OutcomePalette
from rpg_backend.domain.pack_schema import StrategyStyle


_STYLE_COST_HINTS: dict[StrategyStyle, str] = {
    "fast_dirty": "Fast but dirty: coordination noise rises and trust may slip.",
    "steady_slow": "Steady but slow: noise drops, but time pressure increases.",
    "political_safe_resource_heavy": "Politically safe: trust improves, but resource stress climbs.",
}

PALETTE_IDS_BY_RESULT: dict[str, tuple[str, ...]] = {
    "success": tuple(palette_id for palette_id, palette in OUTCOME_PALETTE_BY_ID.items() if palette.result_type == "success"),
    "partial": tuple(palette_id for palette_id, palette in OUTCOME_PALETTE_BY_ID.items() if palette.result_type == "partial"),
    "fail_forward": tuple(palette_id for palette_id, palette in OUTCOME_PALETTE_BY_ID.items() if palette.result_type == "fail_forward"),
}


def _sample(items: tuple[str, ...], rng: random.Random) -> str:
    return items[rng.randrange(0, len(items))]


def _augment_cost_delta_with_style(cost_delta: str, strategy_style: StrategyStyle) -> str:
    return f"{cost_delta} {_STYLE_COST_HINTS[strategy_style]}"


def build_narration_slots_from_palette(
    *,
    palette: OutcomePalette,
    strategy_style: StrategyStyle,
    rng: random.Random,
) -> dict[str, str]:
    return {
        "npc_reaction": _sample(palette.npc_reactions, rng),
        "world_shift": _sample(palette.world_shifts, rng),
        "clue_delta": _sample(palette.clue_deltas, rng),
        "cost_delta": _augment_cost_delta_with_style(_sample(palette.cost_deltas, rng), strategy_style),
        "next_hook": _sample(palette.next_hooks, rng),
    }


def build_style_effect_profile(*, strategy_style: StrategyStyle, result: str) -> list[dict[str, Any]]:
    if strategy_style == "fast_dirty":
        noise_delta = 2 if result != "success" else 1
        return [
            {"type": "inc_state", "key": "coordination_noise", "value": noise_delta},
            {"type": "inc_state", "key": "public_trust", "value": -1},
        ]

    if strategy_style == "steady_slow":
        time_delta = 2 if result == "fail_forward" else 1
        return [
            {"type": "inc_state", "key": "coordination_noise", "value": -1},
            {"type": "inc_state", "key": "time_spent", "value": time_delta},
        ]

    stress_delta = 2 if result != "success" else 1
    return [
        {"type": "inc_state", "key": "public_trust", "value": 1},
        {"type": "inc_state", "key": "resource_stress", "value": stress_delta},
    ]


def validate_palette_id_exists(palette_id: str) -> None:
    if palette_id not in OUTCOME_PALETTE_BY_ID:
        raise ValueError(f"unknown palette_id: {palette_id}")


def build_outcome_from_palette_id(
    *,
    move_id: str,
    outcome_index: int,
    result: str,
    palette_id: str,
    strategy_style: StrategyStyle,
    next_scene_id: str | None,
    rng: random.Random | None = None,
    outcome_id: str | None = None,
) -> dict[str, Any]:
    validate_palette_id_exists(palette_id)
    palette = OUTCOME_PALETTE_BY_ID[palette_id]
    if palette.result_type != result:
        raise ValueError(f"palette_id '{palette_id}' does not match result '{result}'")
    working_rng = rng or random.Random(
        int(hashlib.sha256(f"{move_id}|{outcome_index}|{result}|{palette_id}".encode("utf-8")).hexdigest()[:16], 16)
    )
    effects = [dict(effect) for effect in palette.effect_profile]
    effects.extend(build_style_effect_profile(strategy_style=strategy_style, result=result))
    if result == "fail_forward":
        if not any(effect.get("type") in {"advance_beat_progress", "add_event"} for effect in effects):
            effects.append({"type": "advance_beat_progress", "value": 1})
        if not any(effect.get("type") == "add_event" for effect in effects):
            effects.append({"type": "add_event", "key": f"{move_id}.fail_forward"})
        if not any(effect.get("type") == "cost" for effect in effects):
            effects.append({"type": "cost", "value": 1})
    return {
        "id": outcome_id or f"{move_id}.o{outcome_index + 1}.{result}",
        "result": result,
        "preconditions": [],
        "effects": effects,
        "next_scene_id": next_scene_id,
        "narration_slots": build_narration_slots_from_palette(
            palette=palette,
            strategy_style=strategy_style,
            rng=working_rng,
        ),
    }

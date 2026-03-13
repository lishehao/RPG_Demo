from __future__ import annotations

import re
from typing import Any

from rpg_backend.domain.constants import GLOBAL_CLARIFY_MOVE_ID, GLOBAL_HELP_ME_PROGRESS_MOVE_ID
from rpg_backend.domain.pack_schema import Beat, Scene
from rpg_backend.runtime.compiled_pack import CompiledPlayRuntimePack

_HELP_INTENT_RE = re.compile(
    r"\b(help|stuck|next step|what now|guide me|dont know|don't know|how do i proceed)\b",
    flags=re.IGNORECASE,
)


def is_explicit_help_intent(text: str) -> bool:
    return bool(_HELP_INTENT_RE.search(text or ""))


def build_available_move_ids(scene: Scene) -> list[str]:
    return list(dict.fromkeys([*scene.enabled_moves, *scene.always_available_moves]))


def resolve_fallback_move_id(available_move_ids: list[str]) -> str:
    fallback_move_id = (
        GLOBAL_HELP_ME_PROGRESS_MOVE_ID
        if GLOBAL_HELP_ME_PROGRESS_MOVE_ID in available_move_ids
        else GLOBAL_CLARIFY_MOVE_ID
    )
    if fallback_move_id not in available_move_ids and available_move_ids:
        fallback_move_id = available_move_ids[0]
    return fallback_move_id


def build_llm_available_move_ids(available_move_ids: list[str], *, allow_global_help: bool) -> list[str]:
    llm_available_move_ids = [
        move_id
        for move_id in available_move_ids
        if allow_global_help or move_id != GLOBAL_HELP_ME_PROGRESS_MOVE_ID
    ]
    if not llm_available_move_ids:
        return list(available_move_ids)
    return llm_available_move_ids


def build_route_candidates(
    *,
    compiled_pack: CompiledPlayRuntimePack,
    llm_available_move_ids: list[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, move_id in enumerate(llm_available_move_ids):
        move = compiled_pack.moves_by_id.get(move_id)
        if move is None:
            continue
        candidates.append(
            {
                "key": f"m{index}",
                "move_id": move_id,
                "label": move.label,
                "intents": list(move.intents),
                "synonyms": list(move.synonyms),
                "is_global": move_id.startswith("global."),
            }
        )
    return candidates


def build_route_key_map(route_candidates: list[dict[str, Any]]) -> dict[str, str]:
    return {str(item["key"]): str(item["move_id"]) for item in route_candidates}


def build_scene_snapshot(
    *,
    scene: Scene,
    beat: Beat | None,
    beat_index: int | None,
    beat_progress: dict[str, int] | None,
) -> dict[str, Any]:
    beat_progress_map = beat_progress or {}
    return {
        "scene_id": scene.id,
        "beat_id": scene.beat_id,
        "beat_index": beat_index,
        "present_npcs": list(scene.present_npcs),
        "scene_seed": scene.scene_seed,
        "beat_title": beat.title if beat is not None else "",
        "beat_required_events": list(beat.required_events) if beat is not None else [],
        "beat_step_budget": beat.step_budget if beat is not None else None,
        "beat_progress_value": int(beat_progress_map.get(scene.beat_id, 0)),
    }


def build_state_snapshot(state: dict[str, Any] | None) -> dict[str, Any]:
    state_values = ((state or {}).get("values") or {}) if isinstance(state, dict) else {}
    events = ((state or {}).get("events") or []) if isinstance(state, dict) else []
    if not isinstance(events, list):
        events = []
    return {
        "last_move": state_values.get("last_move"),
        "pressure_tracks": {
            "public_trust": int(state_values.get("public_trust", 0)),
            "resource_stress": int(state_values.get("resource_stress", 0)),
            "coordination_noise": int(state_values.get("coordination_noise", 0)),
        },
        "time_spent": int(state_values.get("time_spent", 0)),
        "runtime_turn": int(state_values.get("runtime_turn", 0)),
        "cost_total": int(state_values.get("cost_total", 0)),
        "recent_events_tail": [str(event) for event in events[-8:]],
    }


def build_scene_context(
    *,
    scene: Scene,
    beat: Beat | None,
    beat_index: int | None,
    state: dict[str, Any] | None,
    beat_progress: dict[str, int] | None,
    allow_global_help: bool,
    fallback_move_id: str,
    route_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "moves": [
            {
                "key": str(item["key"]),
                "id": str(item["move_id"]),
                "label": str(item["label"]),
                "intents": list(item["intents"]),
                "synonyms": list(item["synonyms"]),
                "is_global": bool(item["is_global"]),
            }
            for item in route_candidates
        ],
        "fallback_move": GLOBAL_CLARIFY_MOVE_ID if not allow_global_help else fallback_move_id,
        "scene_seed": scene.scene_seed,
        "allow_global_help": allow_global_help,
        "scene_snapshot": build_scene_snapshot(
            scene=scene,
            beat=beat,
            beat_index=beat_index,
            beat_progress=beat_progress,
        ),
        "state_snapshot": build_state_snapshot(state),
    }

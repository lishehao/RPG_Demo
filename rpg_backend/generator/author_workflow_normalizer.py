from __future__ import annotations

from typing import Any

from rpg_backend.domain.constants import GLOBAL_CLARIFY_MOVE_ID, GLOBAL_HELP_ME_PROGRESS_MOVE_ID, GLOBAL_LOOK_MOVE_ID
from rpg_backend.generator.author_workflow_models import BeatBlueprint, BeatDraft, BeatDraftLLM
from rpg_backend.generator.outcome_materialization import build_outcome_from_palette_id


_FIXED_GLOBAL_MOVES = [
    GLOBAL_CLARIFY_MOVE_ID,
    GLOBAL_LOOK_MOVE_ID,
    GLOBAL_HELP_ME_PROGRESS_MOVE_ID,
]


def _scene_id_for(beat_id: str, entry_scene_id: str, index: int) -> str:
    if index == 0:
        return entry_scene_id
    return f"{beat_id}.sc{index + 1}"


def _move_id_for(beat_id: str, index: int) -> str:
    return f"{beat_id}.m{index + 1}"


def _outcome_id_for(move_id: str, index: int, result: str) -> str:
    return f"{move_id}.o{index + 1}.{result}"


def normalize_beat_draft(
    *,
    overview: object | None = None,
    blueprint: BeatBlueprint,
    llm_draft: BeatDraftLLM,
) -> BeatDraft:
    del overview
    scene_count = len(llm_draft.scenes)
    move_count = len(llm_draft.moves)
    scene_ids = [_scene_id_for(blueprint.beat_id, blueprint.entry_scene_id, index) for index in range(scene_count)]
    move_ids = [_move_id_for(blueprint.beat_id, index) for index in range(move_count)]

    normalized_scenes: list[dict[str, Any]] = []
    for index, scene in enumerate(llm_draft.scenes):
        if any(item < 0 or item >= move_count for item in scene.enabled_move_indexes):
            raise ValueError(f"scene[{index}].enabled_move_indexes contains out-of-range index")
        normalized_scenes.append(
            {
                "id": scene_ids[index],
                "beat_id": blueprint.beat_id,
                "scene_seed": scene.scene_seed.strip(),
                "present_npcs": list(scene.present_npcs),
                "enabled_moves": [move_ids[item] for item in scene.enabled_move_indexes],
                "always_available_moves": list(_FIXED_GLOBAL_MOVES),
                "exit_conditions": [],
                "is_terminal": bool(scene.is_terminal),
            }
        )

    normalized_moves: list[dict[str, Any]] = []
    for move_index, move in enumerate(llm_draft.moves):
        normalized_outcomes: list[dict[str, Any]] = []
        for outcome_index, outcome in enumerate(move.outcomes):
            next_scene_id = None
            if outcome.next_scene_index is not None:
                if outcome.next_scene_index < 0 or outcome.next_scene_index >= scene_count:
                    raise ValueError(
                        f"move[{move_index}].outcomes[{outcome_index}].next_scene_index is out of range"
                    )
                next_scene_id = scene_ids[outcome.next_scene_index]
            normalized_outcomes.append(
                build_outcome_from_palette_id(
                    move_id=move_ids[move_index],
                    outcome_index=outcome_index,
                    result=outcome.result,
                    palette_id=outcome.palette_id,
                    strategy_style=move.strategy_style,
                    next_scene_id=next_scene_id,
                )
            )
        normalized_moves.append(
            {
                "id": move_ids[move_index],
                "label": move.label.strip(),
                "strategy_style": move.strategy_style,
                "intents": list(move.intents),
                "synonyms": list(move.synonyms),
                "args_schema": {},
                "resolution_policy": move.resolution_policy,
                "outcomes": normalized_outcomes,
            }
        )

    normalized_events = list(dict.fromkeys([*(llm_draft.events_produced or []), blueprint.required_event]))
    normalized_present_npcs = list(dict.fromkeys([*(llm_draft.present_npcs or []), *[npc for scene in llm_draft.scenes for npc in scene.present_npcs]]))

    return BeatDraft.model_validate(
        {
            "beat_id": blueprint.beat_id,
            "title": blueprint.title,
            "objective": blueprint.objective,
            "conflict": blueprint.conflict,
            "required_event": blueprint.required_event,
            "entry_scene_id": blueprint.entry_scene_id,
            "scenes": normalized_scenes,
            "moves": normalized_moves,
            "present_npcs": normalized_present_npcs,
            "events_produced": normalized_events,
        }
    )

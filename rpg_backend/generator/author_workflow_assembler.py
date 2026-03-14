from __future__ import annotations

import random
from typing import Any

from rpg_backend.domain.constants import (
    GLOBAL_CLARIFY_MOVE_ID,
    GLOBAL_HELP_ME_PROGRESS_MOVE_ID,
    GLOBAL_LOOK_MOVE_ID,
)
from rpg_backend.domain.move_library import GLOBAL_MOVE_TEMPLATE_IDS, MOVE_TEMPLATE_BY_ID
from rpg_backend.domain.opening_guidance import build_opening_guidance_payload
from rpg_backend.generator.author_workflow_models import (
    BeatBlueprint,
    BeatDraft,
    BeatScenePlan,
    GeneratedBeatScene,
    StoryOverview,
)
from rpg_backend.generator.move_materialization import materialize_move_from_template


_FIXED_GLOBAL_MOVES = [
    GLOBAL_CLARIFY_MOVE_ID,
    GLOBAL_LOOK_MOVE_ID,
    GLOBAL_HELP_ME_PROGRESS_MOVE_ID,
]
_OUTCOME_ORDER = ("success", "partial", "fail_forward")


def _unique_ordered(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return unique


def _build_scene_exit_conditions(
    *,
    scene_id: str,
    required_event: str,
    next_scene_id: str | None,
) -> list[dict[str, Any]]:
    if next_scene_id is None:
        return []
    return [
        {
            "id": f"{scene_id}.advance",
            "condition_kind": "event_present",
            "key": required_event,
            "next_scene_id": next_scene_id,
            "end_story": False,
        }
    ]


def assemble_beat(
    *,
    blueprint: BeatBlueprint,
    scene_plan: BeatScenePlan,
    generated_scenes: list[GeneratedBeatScene],
) -> BeatDraft:
    if not generated_scenes:
        raise ValueError("generated_scenes is empty")
    if scene_plan.beat_id != blueprint.beat_id:
        raise ValueError("scene_plan beat_id does not match blueprint beat_id")
    if len(generated_scenes) != len(scene_plan.scenes):
        raise ValueError("generated_scenes count must match beat scene plan count")
    if not scene_plan.scenes:
        raise ValueError("scene_plan is empty")
    if scene_plan.scenes[0].scene_id != blueprint.entry_scene_id:
        raise ValueError("scene_plan entry scene must match blueprint.entry_scene_id")

    local_scenes: list[Any] = []
    ordered_moves: list[Any] = []
    present_npcs: list[str] = []
    events_produced: list[str] = []

    for scene_index, generated in enumerate(generated_scenes):
        plan_item = scene_plan.scenes[scene_index]
        scene_id = str(plan_item.scene_id or f"{blueprint.beat_id}.sc{scene_index + 1}")
        next_scene_id = None
        if scene_index + 1 < len(scene_plan.scenes):
            next_scene_id = str(scene_plan.scenes[scene_index + 1].scene_id)

        merged_npcs = _unique_ordered([*generated.present_npcs, *plan_item.present_npcs])
        if not merged_npcs:
            raise ValueError(f"generated scene '{scene_id}' must include at least one present_npc")

        move_ids: list[str] = []
        for move_index, move in enumerate(generated.local_moves, start=1):
            move_id = f"{scene_id}.m{move_index}"
            move_ids.append(move_id)
            outcomes_by_result = {item.result: item for item in move.outcomes}
            ordered_outcomes = []
            for result in _OUTCOME_ORDER:
                outcome = outcomes_by_result[result]
                ordered_outcomes.append(
                    {
                        "id": f"{move_id}.{result}",
                        "result": result,
                        "preconditions": [],
                        "effects": [],
                        "next_scene_id": next_scene_id,
                        "narration_slots": outcome.narration_slots.model_dump(mode="json"),
                    }
                )
            ordered_moves.append(
                {
                    "id": move_id,
                    "label": move.label,
                    "strategy_style": move.strategy_style,
                    "intents": list(move.intents),
                    "synonyms": list(move.synonyms),
                    "args_schema": {},
                    "resolution_policy": move.resolution_policy,
                    "outcomes": ordered_outcomes,
                }
            )

        local_scenes.append(
            {
                "id": scene_id,
                "beat_id": blueprint.beat_id,
                "scene_seed": generated.scene_seed,
                "present_npcs": merged_npcs,
                "enabled_moves": move_ids,
                "always_available_moves": list(_FIXED_GLOBAL_MOVES),
                "exit_conditions": _build_scene_exit_conditions(
                    scene_id=scene_id,
                    required_event=blueprint.required_event,
                    next_scene_id=next_scene_id,
                ),
                "is_terminal": next_scene_id is None,
            }
        )

        for npc in merged_npcs:
            if npc not in present_npcs:
                present_npcs.append(npc)
        for event_id in generated.events_produced:
            if event_id not in events_produced:
                events_produced.append(event_id)

    if not present_npcs:
        raise ValueError("assembled beat must include at least one present NPC")
    if blueprint.required_event not in events_produced:
        events_produced.append(blueprint.required_event)

    return BeatDraft(
        beat_id=blueprint.beat_id,
        title=blueprint.title,
        objective=blueprint.objective,
        conflict=blueprint.conflict,
        required_event=blueprint.required_event,
        entry_scene_id=blueprint.entry_scene_id,
        scenes=local_scenes,
        moves=ordered_moves,
        present_npcs=present_npcs,
        events_produced=events_produced,
    )


def assemble_story_pack(
    *,
    story_id: str,
    overview: StoryOverview,
    beat_blueprints: list[BeatBlueprint],
    beat_drafts: list[BeatDraft],
) -> dict[str, Any]:
    overview_npcs = [npc.name for npc in overview.npc_roster]
    scene_map = {scene.id: scene.model_dump(mode="json") for beat in beat_drafts for scene in beat.scenes}

    ordered_scenes: list[dict[str, Any]] = []
    for index, beat in enumerate(beat_drafts):
        local_scenes = [scene_map[scene.id] for scene in beat.scenes]
        if local_scenes:
            last_scene = local_scenes[-1]
            local_scenes[-1] = dict(last_scene)
            exit_conditions = list(last_scene.get("exit_conditions") or [])
            if index < len(beat_blueprints) - 1:
                exit_conditions.append(
                    {
                        "id": f"{beat.beat_id}.to_next",
                        "condition_kind": "event_present",
                        "key": beat.required_event,
                        "next_scene_id": beat_blueprints[index + 1].entry_scene_id,
                        "end_story": False,
                    }
                )
            else:
                exit_conditions.append(
                    {
                        "id": f"{beat.beat_id}.finale",
                        "condition_kind": "event_present",
                        "key": beat.required_event,
                        "next_scene_id": None,
                        "end_story": True,
                    }
                )
                local_scenes[-1]["is_terminal"] = True
            local_scenes[-1]["exit_conditions"] = exit_conditions
        ordered_scenes.extend(local_scenes)

    local_moves = [move.model_dump(mode="json") for beat in beat_drafts for move in beat.moves]
    palette_usage: dict[str, int] = {}
    rng = random.Random(story_id)
    global_moves = [
        materialize_move_from_template(template=MOVE_TEMPLATE_BY_ID[move_id], npcs=overview_npcs, rng=rng, palette_policy="random", palette_usage=palette_usage)
        for move_id in GLOBAL_MOVE_TEMPLATE_IDS
    ]
    move_map = {move["id"]: move for move in global_moves}
    move_map.update({move["id"]: move for move in local_moves})

    first_beat = beat_blueprints[0] if beat_blueprints else None
    first_scene = ordered_scenes[0] if ordered_scenes else None
    first_scene_move_ids = [
        *[move_id for move_id in (first_scene or {}).get("enabled_moves", []) if isinstance(move_id, str)],
        *[move_id for move_id in (first_scene or {}).get("always_available_moves", []) if isinstance(move_id, str)],
    ]
    first_scene_moves = [
        {"move_id": move_id, "label": str(move_map.get(move_id, {}).get("label") or move_id)}
        for move_id in first_scene_move_ids
    ]

    return {
        "story_id": story_id,
        "title": overview.title,
        "description": f"{overview.premise} Stakes: {overview.stakes}".strip(),
        "ending_shape_note": overview.ending_shape_note,
        "move_bias_note": overview.move_bias_note,
        "npcs": overview_npcs,
        "npc_profiles": [
            {
                "name": npc.name,
                "red_line": npc.red_line,
                "conflict_tags": list(npc.conflict_tags),
                "pressure_signature": npc.pressure_signature,
            }
            for npc in overview.npc_roster
        ],
        "beats": [
            {
                "id": beat.beat_id,
                "title": beat.title,
                "step_budget": beat.step_budget,
                "required_events": [beat.required_event],
                "npc_quota": beat.npc_quota,
                "entry_scene_id": beat.entry_scene_id,
            }
            for beat in beat_blueprints
        ],
        "scenes": ordered_scenes,
        "moves": list(move_map.values()),
        "input_hint": "Describe what you do next.",
        "style_guard": f"Tone: {overview.tone}. Keep narration concise, concrete, and forward-moving.",
        "opening_guidance": build_opening_guidance_payload(
            title=overview.title,
            description=f"{overview.premise} Stakes: {overview.stakes}".strip(),
            input_hint="Describe what you do next.",
            first_beat_title=first_beat.title if first_beat else "the opening beat",
            first_scene_seed=str((first_scene or {}).get("scene_seed") or "The opening scene is already unstable."),
            first_scene_npcs=[npc for npc in (first_scene or {}).get("present_npcs", []) if isinstance(npc, str)],
            first_scene_moves=first_scene_moves,
        ),
    }

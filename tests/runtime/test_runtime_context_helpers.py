from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.runtime.compiled_pack import compile_play_runtime_pack
from rpg_backend.runtime.narration_context import build_narration_context, build_prompt_slots

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _load_pack() -> StoryPack:
    return StoryPack.model_validate(json.loads(PACK_PATH.read_text(encoding="utf-8")))


def test_compiled_pack_exposes_scene_move_and_beat_indexes() -> None:
    pack = _load_pack()
    compiled_pack = compile_play_runtime_pack(pack)
    scene = pack.scenes[0]

    assert compiled_pack.scene(scene.id).id == scene.id
    assert compiled_pack.scene_move_ids(scene.id) == list(dict.fromkeys([*scene.enabled_moves, *scene.always_available_moves]))
    assert compiled_pack.beat_index_for_scene(scene.id) == 0


def test_compiled_pack_mappings_are_read_only() -> None:
    pack = _load_pack()
    compiled_pack = compile_play_runtime_pack(pack)
    first_move = pack.moves[0]
    with pytest.raises(TypeError):
        compiled_pack.moves_by_id[first_move.id] = first_move  # type: ignore[index]


def test_narration_context_builders_keep_existing_payload_shape() -> None:
    pack = _load_pack()
    slots = pack.moves[0].outcomes[0].narration_slots
    prompt_slots = build_prompt_slots(
        slots=slots,
        interpreted_intent="probe the anomaly",
        result="partial",
        strategy_style="steady_slow",
        stance_summary=None,
    )
    narration_context = build_narration_context(
        scene_id="sc1",
        next_scene_id="sc2",
        interpreted_intent="probe the anomaly",
        move_label="Trace the source",
        strategy_style="steady_slow",
        result="partial",
        costs_summary="time +1",
        consequences_summary="none",
        stance_summary=None,
    )

    assert set(prompt_slots.keys()) == {"echo", "commit", "hook", "strategy_style", "stance_summary"}
    assert prompt_slots["stance_summary"] == ""
    assert prompt_slots["echo"].startswith("Echo: ")
    assert prompt_slots["hook"].startswith("Hook: ")
    assert set(narration_context.keys()) == {
        "scene_id",
        "next_scene_id",
        "interpreted_intent",
        "move_label",
        "strategy_style",
        "result",
        "costs_summary",
        "consequences_summary",
        "stance_summary",
    }
    assert narration_context["stance_summary"] == ""

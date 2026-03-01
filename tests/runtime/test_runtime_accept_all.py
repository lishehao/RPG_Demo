from __future__ import annotations

import json
from pathlib import Path

from app.domain.pack_schema import StoryPack
from app.llm.fake_provider import FakeProvider
from app.runtime.service import RuntimeService

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _load_pack() -> StoryPack:
    return StoryPack.model_validate(json.loads(PACK_PATH.read_text(encoding="utf-8")))


def test_fail_forward_on_unmet_precondition() -> None:
    pack = _load_pack()
    runtime = RuntimeService(FakeProvider())
    _, _, state, beat_progress = runtime.initialize_session_state(pack)

    result = runtime.process_step(
        pack,
        current_scene_id="sc5",
        beat_index=1,
        state=state,
        beat_progress=beat_progress,
        action_input={"type": "button", "move_id": "decode_core"},
        dev_mode=True,
    )

    assert result["resolution"]["result"] == "fail_forward"
    assert result["resolution"]["consequences_summary"] != "none"


def test_low_confidence_text_routes_to_global_move() -> None:
    pack = _load_pack()
    runtime = RuntimeService(FakeProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    result = runtime.process_step(
        pack,
        current_scene_id=scene_id,
        beat_index=beat_index,
        state=state,
        beat_progress=beat_progress,
        action_input={"type": "text", "text": "@@@ ???"},
    )

    assert result["recognized"]["move_id"] in {"global.help_me_progress", "global.clarify"}


def test_accept_all_empty_text_still_progresses() -> None:
    pack = _load_pack()
    runtime = RuntimeService(FakeProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    result = runtime.process_step(
        pack,
        current_scene_id=scene_id,
        beat_index=beat_index,
        state=state,
        beat_progress=beat_progress,
        action_input={"type": "text", "text": ""},
    )

    assert result["recognized"]["move_id"]
    assert result["scene_id"] != scene_id

from __future__ import annotations

import json
from pathlib import Path

from app.domain.pack_schema import StoryPack
from app.llm.fake_provider import FakeProvider
from app.runtime.service import RuntimeService

PACK_PATH = Path("tests/fixtures/story_pack_v1.json")


def test_runtime_simulation_reaches_terminal_within_expected_steps() -> None:
    pack = StoryPack.model_validate(json.loads(PACK_PATH.read_text(encoding="utf-8")))
    runtime = RuntimeService(FakeProvider())
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    steps = 0
    ended = False
    while steps < 25:
        steps += 1
        result = runtime.process_step(
            pack,
            current_scene_id=scene_id,
            beat_index=beat_index,
            state=state,
            beat_progress=beat_progress,
            action_input={"type": "text", "text": "forward"},
        )
        assert result["resolution"]["consequences_summary"] != "none"

        scene_id = result["scene_id"]
        beat_index = result["beat_index"]
        ended = bool(result["ended"])
        if ended:
            break

    assert ended
    assert 14 <= steps <= 16

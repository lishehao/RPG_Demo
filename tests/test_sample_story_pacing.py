from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.llm.base import LLMProvider, RouteIntentResult
from rpg_backend.runtime.service import RuntimeService

PACK_PATH = Path("tests/fixtures/story_pack_v1.json")


class _DeterministicProvider(LLMProvider):
    def route_intent(self, scene_context, text):  # noqa: ANN001, ANN201
        fallback = scene_context.get("fallback_move", "global.help_me_progress")
        return RouteIntentResult(
            move_id=fallback,
            args={},
            confidence=0.9,
            interpreted_intent=(text or "").strip() or "forward",
        )

    def render_narration(self, slots, style_guard):  # noqa: ANN001, ANN201
        return f"{slots['echo']} {slots['commit']} {slots['hook']}"


def test_runtime_simulation_reaches_terminal_within_expected_steps() -> None:
    pack = StoryPack.model_validate(json.loads(PACK_PATH.read_text(encoding="utf-8")))
    runtime = RuntimeService(_DeterministicProvider())
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

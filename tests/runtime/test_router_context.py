from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.llm.agents import AgentDiagnostics, AgentUsage, PlayInterpretResult
from rpg_backend.runtime.compiled_pack import compile_play_runtime_pack
from rpg_backend.runtime.router import route_player_action

PACK_PATH = Path("sample_data/story_pack_v1.json")


class _CaptureAgent:
    def __init__(self) -> None:
        self.contexts: list[dict] = []

    async def interpret_turn(self, **kwargs) -> PlayInterpretResult:  # noqa: ANN003
        scene_context = kwargs["scene_context"]
        self.contexts.append(scene_context)
        return PlayInterpretResult(
            selected_key=scene_context["moves"][0]["key"],
            confidence=0.95,
            interpreted_intent=(kwargs.get("text") or "").strip() or "fallback",
            diagnostics=AgentDiagnostics(
                agent_model="test-model",
                agent_mode="responses",
                response_id="resp_test_123",
                reasoning_summary=None,
                duration_ms=5,
                usage=AgentUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            ),
        )


def _load_pack() -> StoryPack:
    return StoryPack.model_validate(json.loads(PACK_PATH.read_text(encoding="utf-8")))


def test_route_context_includes_rich_snapshot_fields() -> None:
    pack = _load_pack()
    compiled_pack = compile_play_runtime_pack(pack)
    scene = pack.scenes[0]
    beat = pack.beats[0]
    provider = _CaptureAgent()

    _ = asyncio.run(
        route_player_action(
            provider,
            compiled_pack=compiled_pack,
            scene=scene,
            action_input={"type": "text", "text": "trace the source and keep trust stable"},
            session_id="router-context-test",
            state={
                "events": ["b1.root_cause_locked", "redline_hit::Kael"],
                "values": {
                    "last_move": "trace_anomaly",
                    "public_trust": -2,
                    "resource_stress": 1,
                    "coordination_noise": 3,
                    "time_spent": 2,
                    "runtime_turn": 5,
                    "cost_total": 4,
                },
            },
            beat_progress={scene.beat_id: 1},
            beat=beat,
            beat_index=0,
        )
    )

    assert provider.contexts
    context = provider.contexts[0]
    assert context["scene_snapshot"]["scene_id"] == scene.id
    assert context["scene_snapshot"]["beat_title"] == beat.title
    assert context["state_snapshot"]["runtime_turn"] == 5
    assert context["state_snapshot"]["recent_events_tail"][-1] == "redline_hit::Kael"


def test_route_context_excludes_global_help_for_non_help_text() -> None:
    pack = _load_pack()
    compiled_pack = compile_play_runtime_pack(pack)
    scene = pack.scenes[0]
    provider = _CaptureAgent()

    _ = asyncio.run(
        route_player_action(
            provider,
            compiled_pack=compiled_pack,
            scene=scene,
            action_input={"type": "text", "text": "stabilize corridor and reduce noise"},
            session_id="router-context-test",
        )
    )

    context = provider.contexts[0]
    assert context["allow_global_help"] is False
    assert all(not (move["is_global"] and move["label"] == "Help Me Progress") for move in context["moves"])


def test_route_context_allows_global_help_for_help_text() -> None:
    pack = _load_pack()
    compiled_pack = compile_play_runtime_pack(pack)
    scene = pack.scenes[0]
    provider = _CaptureAgent()

    _ = asyncio.run(
        route_player_action(
            provider,
            compiled_pack=compiled_pack,
            scene=scene,
            action_input={"type": "text", "text": "help I am stuck what now"},
            session_id="router-context-test",
        )
    )

    context = provider.contexts[0]
    assert context["allow_global_help"] is True
    assert any(move["is_global"] for move in context["moves"])

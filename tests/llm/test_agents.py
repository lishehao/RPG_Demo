from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from rpg_backend.llm.agents import AuthorAgent, PlayAgent
from rpg_backend.llm.task_specs import ResponsesTaskSpec


class _FakeSessionStore:
    def __init__(self) -> None:
        self.last_model: str | None = None

    async def call_with_cursor(self, *, scope_type: str, scope_id: str, channel: str, model: str, invoke):  # noqa: ANN001, ANN201, ANN003
        del scope_type, scope_id, channel
        self.last_model = model
        return await invoke(None)


def _task_spec(
    *,
    task_name: str,
    output_mode: str,
    channel: str = "play_agent",
    enable_thinking: bool = False,
    max_output_tokens: int | None = None,
) -> ResponsesTaskSpec:
    return ResponsesTaskSpec(
        task_name=task_name,
        developer_prompt=f"developer prompt for {task_name}",
        output_mode=output_mode,  # type: ignore[arg-type]
        channel=channel,
        enable_thinking=enable_thinking,
        max_output_tokens=max_output_tokens,
    )


def test_play_agent_forces_thinking_off() -> None:
    captured_extra_body: list[dict | None] = []
    captured_max_output_tokens: list[int | None] = []

    class _FakeTransport:
        async def create(self, **kwargs):  # noqa: ANN003, ANN201
            captured_extra_body.append(kwargs.get("extra_body"))
            captured_max_output_tokens.append(kwargs.get("max_output_tokens"))
            return SimpleNamespace(
                response_id="resp_1",
                output_text='{"selected_key":"m0","confidence":0.9,"interpreted_intent":"help me progress"}',
                reasoning_summary="short",
                duration_ms=8,
                usage=SimpleNamespace(input_tokens=10, output_tokens=4, total_tokens=14),
                raw_payload={},
            )

    session_store = _FakeSessionStore()
    agent = PlayAgent(
        transport=_FakeTransport(),  # type: ignore[arg-type]
        session_store=session_store,  # type: ignore[arg-type]
        model="qwen-plus",
        timeout_seconds=20.0,
        interpret_task_spec=_task_spec(
            task_name="interpret_turn",
            output_mode="strict_json",
            channel="play_agent",
            enable_thinking=False,
            max_output_tokens=180,
        ),
        render_task_spec=_task_spec(
            task_name="render_resolved_turn",
            output_mode="text",
            channel="play_agent",
            enable_thinking=False,
            max_output_tokens=360,
        ),
    )

    result = asyncio.run(
        agent.interpret_turn(
            session_id="session-1",
            scene_context={"fallback_move": "global.help_me_progress"},
            route_candidates=[
                {
                    "key": "m0",
                    "move_id": "global.help_me_progress",
                    "label": "Help",
                    "intents": ["help"],
                    "synonyms": ["advance"],
                    "is_global": True,
                }
            ],
            text="help me progress",
        )
    )

    assert result.selected_key == "m0"
    assert captured_extra_body == [{"enable_thinking": False}]
    assert captured_max_output_tokens == [180]


def test_author_agent_overview_forces_thinking_off_and_scene_pipeline_forces_on() -> None:
    captured_extra_body: list[dict | None] = []
    captured_max_output_tokens: list[int | None] = []
    captured_payloads: list[dict[str, object]] = []

    class _FakeTransport:
        async def create(self, **kwargs):  # noqa: ANN003, ANN201
            captured_extra_body.append(kwargs.get("extra_body"))
            captured_max_output_tokens.append(kwargs.get("max_output_tokens"))
            payload = json.loads(kwargs["input"][1]["content"][0]["text"])
            captured_payloads.append(payload)
            output_text = '{"ok": true}'
            return SimpleNamespace(
                response_id="resp_1",
                output_text=output_text,
                reasoning_summary="short",
                duration_ms=8,
                usage=SimpleNamespace(input_tokens=10, output_tokens=4, total_tokens=14),
                raw_payload={},
            )

    session_store = _FakeSessionStore()
    agent = AuthorAgent(
        transport=_FakeTransport(),  # type: ignore[arg-type]
        session_store=session_store,  # type: ignore[arg-type]
        model="qwen-plus",
        timeout_seconds=20.0,
        overview_task_spec=_task_spec(
            task_name="generate_overview",
            output_mode="strict_json",
            channel="author_overview",
            enable_thinking=False,
            max_output_tokens=760,
        ),
        beat_plan_task_spec=_task_spec(
            task_name="plan_beat_scenes",
            output_mode="strict_json",
            channel="author_beat_plan",
            enable_thinking=True,
            max_output_tokens=1500,
        ),
        scene_task_spec=_task_spec(
            task_name="generate_scene",
            output_mode="strict_json",
            channel="author_scene",
            enable_thinking=True,
            max_output_tokens=1600,
        ),
    )

    overview_result = asyncio.run(
        agent.generate_overview(
            run_id="run-1",
            raw_brief="brief",
            output_schema={"type": "object"},
        )
    )
    beat_plan_result = asyncio.run(
        agent.plan_beat_scenes(
            run_id="run-1",
            payload={"story_id": "story-1", "output_schema": {"type": "object"}},
        )
    )
    scene_result = asyncio.run(
        agent.generate_scene(
            run_id="run-1",
            beat_id="b1",
            payload={"story_id": "story-1", "output_schema": {"type": "object"}},
        )
    )

    assert overview_result.payload == {"ok": True}
    assert beat_plan_result.payload == {"ok": True}
    assert scene_result.payload == {"ok": True}
    assert captured_payloads[0]["task"] == "generate_overview"
    assert captured_payloads[1]["task"] == "plan_beat_scenes"
    assert captured_payloads[2]["task"] == "generate_scene"
    assert captured_extra_body == [
        {"enable_thinking": False},
        {"enable_thinking": True},
        {"enable_thinking": True},
    ]
    assert captured_max_output_tokens == [760, 1500, 1600]

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from rpg_backend.llm.agents import PlayAgent


class _FakeSessionStore:
    def __init__(self) -> None:
        self.last_model: str | None = None

    async def call_with_cursor(self, *, scope_type: str, scope_id: str, channel: str, model: str, invoke):  # noqa: ANN001, ANN201, ANN003
        del scope_type, scope_id, channel
        self.last_model = model
        return await invoke(None)


def test_play_agent_enable_thinking_flag_is_forwarded() -> None:
    captured_extra_body: list[dict | None] = []

    class _FakeTransport:
        async def create(self, **kwargs):  # noqa: ANN003, ANN201
            captured_extra_body.append(kwargs.get("extra_body"))
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
        enable_thinking=True,
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
    assert captured_extra_body == [{"enable_thinking": True}]


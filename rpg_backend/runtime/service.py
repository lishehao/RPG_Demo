from __future__ import annotations

from typing import Any

from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.llm.agents import PlayAgent
from rpg_backend.runtime.initializer import initialize_session_state
from rpg_backend.runtime.step_engine import process_runtime_step
from rpg_backend.runtime.ui import list_ui_moves


class RuntimeService:
    def __init__(
        self,
        bundle_or_play_agent: Any | None = None,
        *,
        play_agent: PlayAgent | None = None,
        agent_model: str | None = None,
        agent_mode: str | None = None,
    ) -> None:
        resolved_play_agent = play_agent
        resolved_agent_model = agent_model
        resolved_agent_mode = agent_mode

        if resolved_play_agent is None:
            candidate = bundle_or_play_agent
            if candidate is None:
                raise ValueError("RuntimeService requires a play agent or Responses bundle")
            if hasattr(candidate, "play_agent"):
                resolved_play_agent = getattr(candidate, "play_agent")
                if resolved_agent_model is None:
                    resolved_agent_model = getattr(candidate, "model", None)
                if resolved_agent_mode is None:
                    resolved_agent_mode = getattr(candidate, "mode", None)
            else:
                resolved_play_agent = candidate

        if resolved_play_agent is None:
            raise ValueError("RuntimeService missing play agent")

        self.play_agent = resolved_play_agent
        self.agent_model = str(resolved_agent_model or getattr(resolved_play_agent, "model", "unknown"))
        self.agent_mode = str(resolved_agent_mode or "responses")

    def initialize_session_state(self, pack: StoryPack) -> tuple[str, int, dict[str, Any], dict[str, int]]:
        return initialize_session_state(pack)

    def list_ui_moves(self, pack: StoryPack, scene_id: str) -> list[dict[str, Any]]:
        return list_ui_moves(pack, scene_id)

    async def process_step(
        self,
        pack: StoryPack,
        session_id: str,
        current_scene_id: str,
        beat_index: int,
        state: dict[str, Any],
        beat_progress: dict[str, int],
        action_input: dict[str, Any],
        *,
        dev_mode: bool = False,
    ) -> dict[str, Any]:
        result = await process_runtime_step(
            play_agent=self.play_agent,
            pack=pack,
            session_id=session_id,
            current_scene_id=current_scene_id,
            beat_index=beat_index,
            state=state,
            beat_progress=beat_progress,
            action_input=action_input,
            dev_mode=dev_mode,
        )
        return result.to_payload()

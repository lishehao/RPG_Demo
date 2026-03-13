from __future__ import annotations

from typing import Any

from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.llm.agents import PlayAgent
from rpg_backend.runtime.compiled_pack import compile_play_runtime_pack
from rpg_backend.runtime.initializer import initialize_session_state
from rpg_backend.runtime.step_engine import process_runtime_step
from rpg_backend.runtime.ui import list_ui_moves


class RuntimeService:
    def __init__(
        self,
        *,
        play_agent: PlayAgent,
        agent_model: str | None = None,
        agent_mode: str | None = None,
    ) -> None:
        self.play_agent = play_agent
        self.agent_model = str(agent_model or getattr(play_agent, "model", "unknown"))
        self.agent_mode = str(agent_mode or "responses")

    def initialize_session_state(self, pack: StoryPack) -> tuple[str, int, dict[str, Any], dict[str, int]]:
        compiled_pack = compile_play_runtime_pack(pack)
        return initialize_session_state(compiled_pack)

    def list_ui_moves(self, pack: StoryPack, scene_id: str) -> list[dict[str, Any]]:
        compiled_pack = compile_play_runtime_pack(pack)
        return list_ui_moves(compiled_pack, scene_id)

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
        compiled_pack = compile_play_runtime_pack(pack)
        result = await process_runtime_step(
            play_agent=self.play_agent,
            compiled_pack=compiled_pack,
            session_id=session_id,
            current_scene_id=current_scene_id,
            beat_index=beat_index,
            state=state,
            beat_progress=beat_progress,
            action_input=action_input,
            dev_mode=dev_mode,
        )
        return result.to_payload()

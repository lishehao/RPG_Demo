from __future__ import annotations

from app.domain.pack_schema import NarrationSlots
from app.llm.base import LLMProvider


def render_echo_commit_hook(
    provider: LLMProvider,
    slots: NarrationSlots,
    interpreted_intent: str,
    result: str,
    style_guard: str,
) -> str:
    echo = f"Echo: You commit to '{interpreted_intent or 'an uncertain move'}'."
    commit = (
        "Commit: "
        f"{slots.npc_reaction} {slots.world_shift} {slots.clue_delta} {slots.cost_delta} "
        f"Result: {result}."
    )
    hook = f"Hook: {slots.next_hook}"
    return provider.render_narration({"echo": echo, "commit": commit, "hook": hook}, style_guard)

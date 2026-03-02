from __future__ import annotations

from app.domain.pack_schema import NarrationSlots
from app.llm.base import LLMProvider
from app.runtime.errors import RuntimeNarrationError


def _echo_commit_hook_parts(
    slots: NarrationSlots,
    interpreted_intent: str,
    result: str,
) -> tuple[str, str, str]:
    echo = f"Echo: You commit to '{interpreted_intent or 'an uncertain move'}'."
    commit = (
        "Commit: "
        f"{slots.npc_reaction} {slots.world_shift} {slots.clue_delta} {slots.cost_delta} "
        f"Result: {result}."
    )
    hook = f"Hook: {slots.next_hook}"
    return echo, commit, hook


def render_echo_commit_hook(
    provider: LLMProvider,
    slots: NarrationSlots,
    interpreted_intent: str,
    result: str,
    style_guard: str,
) -> str:
    echo, commit, hook = _echo_commit_hook_parts(slots, interpreted_intent, result)
    # Keep deterministic parts as provider input scaffolding. Runtime output must come from LLM.
    prompt_slots = {"echo": echo, "commit": commit, "hook": hook}
    provider_name = "openai"
    try:
        rendered = provider.render_narration(prompt_slots, style_guard)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeNarrationError(
            error_code="llm_narration_failed",
            message=f"render_narration failed after provider retries: {exc}",
            provider=provider_name,
        ) from exc
    if not isinstance(rendered, str) or not rendered.strip():
        raise RuntimeNarrationError(
            error_code="llm_narration_failed",
            message="render_narration returned blank text",
            provider=provider_name,
        )
    return rendered.strip()

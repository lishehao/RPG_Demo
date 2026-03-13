from __future__ import annotations

import time
from typing import Any

from rpg_backend.domain.pack_schema import NarrationSlots
from rpg_backend.llm.agents import PlayAgent
from rpg_backend.runtime.errors import RuntimeNarrationError


def _echo_commit_hook_parts(
    slots: NarrationSlots,
    interpreted_intent: str,
    result: str,
    strategy_style: str,
    stance_summary: str | None,
) -> tuple[str, str, str]:
    echo = f"Echo: You commit to '{interpreted_intent or 'an uncertain move'}'."
    commit = (
        "Commit: "
        f"{slots.npc_reaction} {slots.world_shift} {slots.clue_delta} {slots.cost_delta} "
        f"Result: {result}. Strategy style: {strategy_style}."
    )
    if stance_summary:
        commit = f"{commit} {stance_summary}"
    hook = f"Hook: {slots.next_hook}"
    return echo, commit, hook


async def render_echo_commit_hook(
    play_agent: PlayAgent,
    slots: NarrationSlots,
    interpreted_intent: str,
    result: str,
    style_guard: str,
    *,
    session_id: str,
    strategy_style: str,
    scene_id: str,
    next_scene_id: str | None,
    move_label: str,
    costs_summary: str,
    consequences_summary: str,
    stance_summary: str | None = None,
) -> dict[str, Any]:
    echo, commit, hook = _echo_commit_hook_parts(
        slots,
        interpreted_intent,
        result,
        strategy_style,
        stance_summary,
    )
    # Keep deterministic parts as provider input scaffolding. Runtime output must come from LLM.
    prompt_slots = {
        "echo": echo,
        "commit": commit,
        "hook": hook,
        "strategy_style": strategy_style,
        "stance_summary": stance_summary or "",
    }
    provider_name = "openai"
    gateway_mode = "responses"
    started_at = time.perf_counter()
    try:
        rendered = await play_agent.render_resolved_turn(
            session_id=session_id,
            narration_context={
                "scene_id": scene_id,
                "next_scene_id": next_scene_id,
                "interpreted_intent": interpreted_intent,
                "move_label": move_label,
                "strategy_style": strategy_style,
                "result": result,
                "costs_summary": costs_summary,
                "consequences_summary": consequences_summary,
                "stance_summary": stance_summary or "",
            },
            prompt_slots=prompt_slots,
            style_guard=style_guard,
        )
        duration_ms = int(rendered.diagnostics.duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        raise RuntimeNarrationError(
            error_code="llm_narration_failed",
            message=f"play agent render_resolved_turn failed: {exc}",
            provider=provider_name,
            provider_error_code=getattr(exc, "provider_error_code", None),
            llm_duration_ms=duration_ms,
            gateway_mode=gateway_mode,
        ) from exc
    duration_ms = int(duration_ms or ((time.perf_counter() - started_at) * 1000))
    if not isinstance(rendered.narration_text, str) or not rendered.narration_text.strip():
        raise RuntimeNarrationError(
            error_code="llm_narration_failed",
            message="play agent returned blank narration text",
            provider=provider_name,
            llm_duration_ms=duration_ms,
            gateway_mode=gateway_mode,
            response_id=rendered.diagnostics.response_id,
            reasoning_summary=rendered.diagnostics.reasoning_summary,
        )
    return {
        "text": rendered.narration_text.strip(),
        "llm_duration_ms": duration_ms,
        "llm_gateway_mode": gateway_mode,
        "response_id": rendered.diagnostics.response_id,
        "reasoning_summary": rendered.diagnostics.reasoning_summary,
    }

from __future__ import annotations

import time
from typing import Any

from rpg_backend.domain.pack_schema import NarrationSlots
from rpg_backend.llm.agents import PlayAgent
from rpg_backend.runtime.narration_context import build_narration_context, build_prompt_slots
from rpg_backend.runtime.errors import RuntimeNarrationError


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
    prompt_slots = build_prompt_slots(
        slots=slots,
        interpreted_intent=interpreted_intent,
        result=result,
        strategy_style=strategy_style,
        stance_summary=stance_summary,
    )
    narration_context = build_narration_context(
        scene_id=scene_id,
        next_scene_id=next_scene_id,
        interpreted_intent=interpreted_intent,
        move_label=move_label,
        strategy_style=strategy_style,
        result=result,
        costs_summary=costs_summary,
        consequences_summary=consequences_summary,
        stance_summary=stance_summary,
    )

    llm_backend = "responses"
    gateway_mode = "responses"
    started_at = time.perf_counter()
    try:
        rendered = await play_agent.render_resolved_turn(
            session_id=session_id,
            narration_context=narration_context,
            prompt_slots=prompt_slots,
            style_guard=style_guard,
        )
        duration_ms = int(rendered.diagnostics.duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        raise RuntimeNarrationError(
            error_code="llm_narration_failed",
            message=f"play agent render_resolved_turn failed: {exc}",
            llm_backend=llm_backend,
            llm_backend_error_code=getattr(exc, "llm_backend_error_code", None) or getattr(exc, "error_code", None),
            llm_duration_ms=duration_ms,
            gateway_mode=gateway_mode,
        ) from exc
    duration_ms = int(duration_ms or ((time.perf_counter() - started_at) * 1000))
    if not isinstance(rendered.narration_text, str) or not rendered.narration_text.strip():
        raise RuntimeNarrationError(
            error_code="llm_narration_failed",
            message="play agent returned blank narration text",
            llm_backend=llm_backend,
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

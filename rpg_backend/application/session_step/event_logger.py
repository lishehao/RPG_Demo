from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.infrastructure.db.transaction import transactional
from rpg_backend.infrastructure.repositories.runtime_events_async import save_runtime_event
from rpg_backend.observability.logging import log_event
from rpg_backend.runtime.errors import RuntimeNarrationError, RuntimeRouteError


async def emit_step_started_event(
    *,
    db: AsyncSession,
    session_id: str,
    story_id: str,
    turn_index_expected: int,
    client_action_id: str,
    normalized_input: dict[str, Any],
    scene_id_before: str,
    beat_index_before: int,
    provider_name: str,
    request_id: str,
    agent_model: str | None,
    agent_mode: str | None,
    input_log_fields: dict[str, Any],
) -> None:
    async with transactional(db):
        await save_runtime_event(
            db,
            session_id=session_id,
            turn_index=turn_index_expected,
            event_type="step_started",
            payload_json={
                "client_action_id": client_action_id,
                "turn_index_expected": turn_index_expected,
                "input": normalized_input,
                "scene_id_before": scene_id_before,
                "beat_index_before": beat_index_before,
                "provider": provider_name,
                "request_id": request_id,
                "agent_model": agent_model,
                "agent_mode": agent_mode,
            },
        )
    log_event(
        "session_step_started",
        level="INFO",
        request_id=request_id,
        session_id=session_id,
        story_id=story_id,
        turn_index=turn_index_expected,
        client_action_id=client_action_id,
        scene_id_before=scene_id_before,
        beat_index_before=beat_index_before,
        provider=provider_name,
        agent_model=agent_model,
        agent_mode=agent_mode,
        **input_log_fields,
    )


async def emit_step_replayed_event(
    *,
    db: AsyncSession,
    session_id: str,
    story_id: str,
    turn_index: int,
    client_action_id: str,
    session_action_id: str,
    request_id: str,
    note: str,
) -> None:
    async with transactional(db):
        await save_runtime_event(
            db,
            session_id=session_id,
            turn_index=turn_index,
            event_type="step_replayed",
            payload_json={
                "client_action_id": client_action_id,
                "session_action_id": session_action_id,
                "note": note,
                "request_id": request_id,
            },
        )
    log_event(
        "session_step_replayed",
        level="INFO",
        request_id=request_id,
        session_id=session_id,
        story_id=story_id,
        turn_index=turn_index,
        client_action_id=client_action_id,
    )


async def emit_step_conflicted_event(
    *,
    db: AsyncSession,
    session_id: str,
    story_id: str,
    turn_index_expected: int,
    actual_turn_index: int,
    client_action_id: str,
    scene_id_before: str,
    beat_index_before: int,
    request_id: str,
    input_log_fields: dict[str, Any],
    error_code: str,
) -> None:
    async with transactional(db):
        await save_runtime_event(
            db,
            session_id=session_id,
            turn_index=turn_index_expected,
            event_type="step_conflicted",
            payload_json={
                "client_action_id": client_action_id,
                "expected_turn_index": turn_index_expected,
                "actual_turn_index": actual_turn_index,
                "scene_id_before": scene_id_before,
                "beat_index_before": beat_index_before,
                "request_id": request_id,
                "note": "optimistic_write_conflict",
            },
        )
    log_event(
        "session_step_conflicted",
        level="WARN",
        request_id=request_id,
        session_id=session_id,
        story_id=story_id,
        turn_index=turn_index_expected,
        client_action_id=client_action_id,
        expected_turn_index=turn_index_expected,
        actual_turn_index=actual_turn_index,
        scene_id_before=scene_id_before,
        beat_index_before=beat_index_before,
        error_code=error_code,
        **input_log_fields,
    )


async def emit_step_failed_event(
    *,
    db: AsyncSession,
    session_id: str,
    story_id: str,
    turn_index_expected: int,
    client_action_id: str,
    scene_id_before: str,
    beat_index_before: int,
    request_id: str,
    agent_model: str | None,
    agent_mode: str | None,
    duration_ms: int,
    llm_duration_ms: int,
    llm_gateway_mode: str,
    response_id: str | None,
    reasoning_summary: str | None,
    exc: RuntimeRouteError | RuntimeNarrationError,
    input_log_fields: dict[str, Any],
) -> None:
    async with transactional(db):
        await save_runtime_event(
            db,
            session_id=session_id,
            turn_index=turn_index_expected,
            event_type="step_failed",
            payload_json={
                "client_action_id": client_action_id,
                "turn_index_expected": turn_index_expected,
                "scene_id_before": scene_id_before,
                "beat_index_before": beat_index_before,
                "error_code": exc.error_code,
                "stage": exc.stage,
                "message": exc.message,
                "provider": exc.provider,
                "request_id": request_id,
                "agent_model": agent_model,
                "agent_mode": agent_mode,
                "duration_ms": duration_ms,
                "provider_error_code": exc.provider_error_code,
                "llm_duration_ms": llm_duration_ms,
                "llm_gateway_mode": llm_gateway_mode,
                "response_id": response_id,
                "reasoning_summary": reasoning_summary,
            },
        )
    log_event(
        "session_step_failed",
        level="ERROR",
        request_id=request_id,
        session_id=session_id,
        story_id=story_id,
        turn_index=turn_index_expected,
        client_action_id=client_action_id,
        scene_id_before=scene_id_before,
        beat_index_before=beat_index_before,
        error_code=exc.error_code,
        stage=exc.stage,
        message=exc.message,
        provider=exc.provider,
        agent_model=agent_model,
        agent_mode=agent_mode,
        duration_ms=duration_ms,
        provider_error_code=exc.provider_error_code,
        llm_duration_ms=llm_duration_ms,
        llm_gateway_mode=llm_gateway_mode,
        response_id=response_id,
        **input_log_fields,
    )


async def emit_step_succeeded_event(
    *,
    db: AsyncSession,
    session_id: str,
    story_id: str,
    turn_index_applied: int,
    client_action_id: str,
    scene_id_before: str,
    beat_index_before: int,
    request_id: str,
    agent_model: str | None,
    agent_mode: str | None,
    duration_ms: int,
    interpret_duration_ms: int | None,
    render_duration_ms: int | None,
    interpret_gateway_mode: str,
    render_gateway_mode: str,
    interpret_response_id: str | None,
    render_response_id: str | None,
    interpret_reasoning_summary: str | None,
    render_reasoning_summary: str | None,
    result: dict[str, Any],
    provider_name: str,
    input_log_fields: dict[str, Any],
) -> None:
    async with transactional(db):
        await save_runtime_event(
            db,
            session_id=session_id,
            turn_index=turn_index_applied,
            event_type="step_succeeded",
            payload_json={
                "client_action_id": client_action_id,
                "turn_index": turn_index_applied,
                "scene_id_before": scene_id_before,
                "scene_id_after": result["scene_id"],
                "beat_index_before": beat_index_before,
                "beat_index_after": result["beat_index"],
                "ended": bool(result["ended"]),
                "recognized": result["recognized"],
                "resolution": result["resolution"],
                "narration_text": result["narration_text"],
                "request_id": request_id,
                "agent_model": agent_model,
                "agent_mode": agent_mode,
                "duration_ms": duration_ms,
                "interpret_duration_ms": interpret_duration_ms,
                "render_duration_ms": render_duration_ms,
                "interpret_gateway_mode": interpret_gateway_mode,
                "render_gateway_mode": render_gateway_mode,
                "interpret_response_id": interpret_response_id,
                "render_response_id": render_response_id,
                "interpret_reasoning_summary": interpret_reasoning_summary,
                "render_reasoning_summary": render_reasoning_summary,
            },
        )
    log_event(
        "session_step_succeeded",
        level="INFO",
        request_id=request_id,
        session_id=session_id,
        story_id=story_id,
        turn_index=turn_index_applied,
        client_action_id=client_action_id,
        scene_id_before=scene_id_before,
        scene_id_after=result["scene_id"],
        beat_index_before=beat_index_before,
        beat_index_after=result["beat_index"],
        ended=bool(result["ended"]),
        provider=provider_name,
        agent_model=agent_model,
        agent_mode=agent_mode,
        route_source=result["recognized"].get("route_source"),
        narration_text_len=len(result["narration_text"] or ""),
        duration_ms=duration_ms,
        interpret_duration_ms=interpret_duration_ms,
        render_duration_ms=render_duration_ms,
        interpret_gateway_mode=interpret_gateway_mode,
        render_gateway_mode=render_gateway_mode,
        interpret_response_id=interpret_response_id,
        render_response_id=render_response_id,
        **input_log_fields,
    )

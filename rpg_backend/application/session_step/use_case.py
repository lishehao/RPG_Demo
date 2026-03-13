from __future__ import annotations

import time
from typing import Any, Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.application.play_sessions.errors import RuntimeStepFailedError
from rpg_backend.application.play_sessions.models import SessionStepCommand, SessionStepResult
from rpg_backend.application.session_step.llm_telemetry import llm_runtime_failure_detail
from rpg_backend.application.session_step.stages.commit import cas_commit_transition, resolve_conflict_or_replay
from rpg_backend.application.session_step.stages.emit import emit_success_or_failure_events, record_llm_call_events
from rpg_backend.application.session_step.stages.execute import build_execution_context, execute_runtime_step
from rpg_backend.application.session_step.stages.idempotency import idempotency_precheck
from rpg_backend.application.session_step.stages.validate import validate_request
from rpg_backend.llm.factory import get_llm_provider
from rpg_backend.runtime.errors import RuntimeNarrationError, RuntimeRouteError


async def process_step_command(
    *,
    db: AsyncSession,
    session_id: str,
    command: SessionStepCommand,
    request_id: str,
    provider_factory: Callable[[], Any] = get_llm_provider,
) -> SessionStepResult:
    ctx = await validate_request(
        db=db,
        session_id=session_id,
        command=command,
        request_id=request_id,
    )

    replay_response = await idempotency_precheck(ctx)
    if replay_response is not None:
        return replay_response

    execution_context = build_execution_context(provider_factory)
    started_at = time.perf_counter()
    try:
        execution_success, working_state, working_beat_progress = await execute_runtime_step(
            ctx,
            execution_context=execution_context,
        )
    except (RuntimeRouteError, RuntimeNarrationError) as exc:
        failure_duration_ms = int((time.perf_counter() - started_at) * 1000)
        _interpret_ms, llm_duration_ms, llm_gateway_mode, _render_gateway_mode, _interpret_response_id, _render_response_id, _interpret_reasoning_summary, _render_reasoning_summary = await record_llm_call_events(
            ctx,
            execution_context=execution_context,
            runtime_exc=exc,
            fallback_duration_ms=failure_duration_ms,
        )
        await emit_success_or_failure_events(
            ctx,
            execution_context=execution_context,
            runtime_exc=exc,
            failure_duration_ms=failure_duration_ms,
            llm_duration_ms=llm_duration_ms,
            llm_gateway_mode=llm_gateway_mode,
        )
        detail = llm_runtime_failure_detail(exc)
        raise RuntimeStepFailedError(
            error_code=str(detail.get("error_code") or "service_unavailable"),
            message=str(detail.get("message") or "runtime step failed"),
            retryable=bool(detail.get("retryable", True)),
            details={
                key: value
                for key, value in detail.items()
                if key not in {"error_code", "message", "retryable"}
            },
        ) from exc

    interpret_duration_ms, render_duration_ms, interpret_gateway_mode, render_gateway_mode, interpret_response_id, render_response_id, interpret_reasoning_summary, render_reasoning_summary = (
        await record_llm_call_events(
            ctx,
            execution_context=execution_context,
            execution_success=execution_success,
        )
    )

    result = SessionStepResult.from_runtime_payload(
        session_id=ctx.session.id,
        version=ctx.session.version,
        payload=execution_success.result,
        include_debug=ctx.command.dev_mode,
    )

    commit_result = await cas_commit_transition(
        ctx,
        execution_success=execution_success,
        result=result,
        working_state=working_state,
        working_beat_progress=working_beat_progress,
    )

    if not commit_result.applied:
        return await resolve_conflict_or_replay(ctx, commit_result=commit_result)

    turn_index_applied = commit_result.actual_turn_count
    await emit_success_or_failure_events(
        ctx,
        execution_context=execution_context,
        execution_success=execution_success,
        interpret_duration_ms=interpret_duration_ms,
        render_duration_ms=render_duration_ms,
        interpret_gateway_mode=interpret_gateway_mode,
        render_gateway_mode=render_gateway_mode,
        interpret_response_id=interpret_response_id,
        render_response_id=render_response_id,
        interpret_reasoning_summary=interpret_reasoning_summary,
        render_reasoning_summary=render_reasoning_summary,
        turn_index_applied=turn_index_applied,
    )

    return result

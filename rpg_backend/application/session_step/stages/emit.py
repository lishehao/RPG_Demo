from __future__ import annotations

from rpg_backend.application.session_step.contracts import RuntimeExecutionContext, RuntimeExecutionSuccess, StepRequestContext
from rpg_backend.application.session_step.event_logger import (
    emit_step_failed_event,
    emit_step_succeeded_event,
)
from rpg_backend.application.session_step.llm_telemetry import (
    record_llm_failure_event,
    record_llm_success_events,
)
from rpg_backend.runtime.errors import RuntimeNarrationError, RuntimeRouteError


async def record_llm_call_events(
    ctx: StepRequestContext,
    *,
    execution_context: RuntimeExecutionContext,
    execution_success: RuntimeExecutionSuccess | None = None,
    runtime_exc: RuntimeRouteError | RuntimeNarrationError | None = None,
    fallback_duration_ms: int | None = None,
) -> tuple[
    int | None,
    int | None,
    str,
    str,
    str | None,
    str | None,
    str | None,
    str | None,
]:
    provider_gateway_mode = str(execution_context.agent_mode or "unknown")

    if runtime_exc is not None:
        llm_duration_ms, llm_gateway_mode, _stage_model, response_id, reasoning_summary = await record_llm_failure_event(
            db=ctx.db,
            session_id=ctx.session.id,
            turn_index_expected=ctx.turn_index_expected,
            request_id=ctx.request_id,
            exc=runtime_exc,
            agent_model=execution_context.agent_model,
            fallback_duration_ms=int(fallback_duration_ms or 0),
            provider_gateway_mode=provider_gateway_mode,
        )
        return None, llm_duration_ms, llm_gateway_mode, llm_gateway_mode, None, response_id, None, reasoning_summary

    if execution_success is None:
        return None, None, provider_gateway_mode, provider_gateway_mode, None, None, None, None

    runtime_metrics = execution_success.result.get("runtime_metrics") or {}
    return await record_llm_success_events(
        db=ctx.db,
        session_id=ctx.session.id,
        turn_index_expected=ctx.turn_index_expected,
        request_id=ctx.request_id,
        agent_model=execution_context.agent_model,
        runtime_metrics=runtime_metrics,
        provider_gateway_mode=provider_gateway_mode,
    )


async def emit_success_or_failure_events(
    ctx: StepRequestContext,
    *,
    execution_context: RuntimeExecutionContext,
    execution_success: RuntimeExecutionSuccess | None = None,
    runtime_exc: RuntimeRouteError | RuntimeNarrationError | None = None,
    failure_duration_ms: int | None = None,
    llm_duration_ms: int | None = None,
    llm_gateway_mode: str | None = None,
    interpret_duration_ms: int | None = None,
    render_duration_ms: int | None = None,
    interpret_gateway_mode: str | None = None,
    render_gateway_mode: str | None = None,
    interpret_response_id: str | None = None,
    render_response_id: str | None = None,
    interpret_reasoning_summary: str | None = None,
    render_reasoning_summary: str | None = None,
    turn_index_applied: int | None = None,
) -> None:
    if runtime_exc is not None:
        await emit_step_failed_event(
            db=ctx.db,
            session_id=ctx.session.id,
            story_id=ctx.session.story_id,
            turn_index_expected=ctx.turn_index_expected,
            client_action_id=ctx.command.client_action_id,
            scene_id_before=ctx.scene_id_before,
            beat_index_before=ctx.beat_index_before,
            request_id=ctx.request_id,
            agent_model=execution_context.agent_model,
            agent_mode=execution_context.agent_mode,
            duration_ms=int(failure_duration_ms or 0),
            llm_duration_ms=int(llm_duration_ms or failure_duration_ms or 0),
            llm_gateway_mode=str(llm_gateway_mode or "unknown"),
            response_id=runtime_exc.response_id,
            reasoning_summary=runtime_exc.reasoning_summary,
            exc=runtime_exc,
            input_log_fields=ctx.input_log_fields,
        )
        return

    if execution_success is None or turn_index_applied is None:
        return

    await emit_step_succeeded_event(
        db=ctx.db,
        session_id=ctx.session.id,
        story_id=ctx.session.story_id,
        turn_index_applied=turn_index_applied,
        client_action_id=ctx.command.client_action_id,
        scene_id_before=ctx.scene_id_before,
        beat_index_before=ctx.beat_index_before,
        request_id=ctx.request_id,
        agent_model=execution_context.agent_model,
        agent_mode=execution_context.agent_mode,
        duration_ms=execution_success.duration_ms,
        interpret_duration_ms=interpret_duration_ms,
        render_duration_ms=render_duration_ms,
        interpret_gateway_mode=str(interpret_gateway_mode or "unknown"),
        render_gateway_mode=str(render_gateway_mode or "unknown"),
        interpret_response_id=interpret_response_id,
        render_response_id=render_response_id,
        interpret_reasoning_summary=interpret_reasoning_summary,
        render_reasoning_summary=render_reasoning_summary,
        result=execution_success.result,
        provider_name=execution_context.provider_name,
        input_log_fields=ctx.input_log_fields,
    )

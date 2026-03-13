from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.infrastructure.db.transaction import transactional
from rpg_backend.infrastructure.repositories.observability_async import save_llm_call_event
from rpg_backend.runtime.errors import RuntimeNarrationError, RuntimeRouteError



def provider_name() -> str:
    return "openai"



def llm_runtime_failure_detail(exc: RuntimeRouteError | RuntimeNarrationError) -> dict[str, Any]:
    detail = {
        "error_code": exc.error_code,
        "stage": exc.stage,
        "message": exc.message,
        "provider": exc.provider,
        "retryable": True,
    }
    if exc.provider_error_code:
        detail["provider_error_code"] = exc.provider_error_code
    if exc.llm_duration_ms is not None:
        detail["llm_duration_ms"] = int(exc.llm_duration_ms)
    if exc.gateway_mode:
        detail["llm_gateway_mode"] = exc.gateway_mode
    if exc.response_id:
        detail["response_id"] = exc.response_id
    if exc.reasoning_summary:
        detail["reasoning_summary"] = exc.reasoning_summary
    return detail


async def record_llm_failure_event(
    *,
    db: AsyncSession,
    session_id: str,
    turn_index_expected: int,
    request_id: str,
    exc: RuntimeRouteError | RuntimeNarrationError,
    agent_model: str | None,
    fallback_duration_ms: int,
    provider_gateway_mode: str,
) -> tuple[int, str, str, str | None, str | None]:
    failed_stage_model = str(agent_model or "unknown")
    gateway_mode = str(exc.gateway_mode or provider_gateway_mode or "unknown")
    llm_duration_ms = int(exc.llm_duration_ms) if exc.llm_duration_ms is not None else fallback_duration_ms

    async with transactional(db):
        await save_llm_call_event(
            db,
            session_id=session_id,
            turn_index=turn_index_expected,
            stage=exc.stage,
            gateway_mode=gateway_mode,
            model=failed_stage_model,
            success=False,
            error_code=exc.provider_error_code or exc.error_code,
            duration_ms=llm_duration_ms,
            request_id=request_id,
        )
    return llm_duration_ms, gateway_mode, failed_stage_model, exc.response_id, exc.reasoning_summary


async def record_llm_success_events(
    *,
    db: AsyncSession,
    session_id: str,
    turn_index_expected: int,
    request_id: str,
    agent_model: str | None,
    runtime_metrics: dict[str, Any],
    provider_gateway_mode: str,
) -> tuple[int | None, int | None, str, str, str | None, str | None, str | None, str | None]:
    interpret_duration_ms = runtime_metrics.get("interpret_duration_ms")
    render_duration_ms = runtime_metrics.get("render_duration_ms")
    interpret_gateway_mode = str(runtime_metrics.get("interpret_gateway_mode") or provider_gateway_mode or "unknown")
    render_gateway_mode = str(runtime_metrics.get("render_gateway_mode") or provider_gateway_mode or "unknown")

    interpret_response_id = (
        str(runtime_metrics.get("interpret_response_id"))
        if runtime_metrics.get("interpret_response_id") is not None
        else None
    )
    render_response_id = (
        str(runtime_metrics.get("render_response_id"))
        if runtime_metrics.get("render_response_id") is not None
        else None
    )
    interpret_reasoning_summary = (
        str(runtime_metrics.get("interpret_reasoning_summary"))
        if runtime_metrics.get("interpret_reasoning_summary") is not None
        else None
    )
    render_reasoning_summary = (
        str(runtime_metrics.get("render_reasoning_summary"))
        if runtime_metrics.get("render_reasoning_summary") is not None
        else None
    )

    model = str(agent_model or "unknown")

    async with transactional(db):
        if isinstance(interpret_duration_ms, int):
            await save_llm_call_event(
                db,
                session_id=session_id,
                turn_index=turn_index_expected,
                stage="interpret_turn",
                gateway_mode=interpret_gateway_mode,
                model=model,
                success=True,
                error_code=None,
                duration_ms=interpret_duration_ms,
                request_id=request_id,
            )
        if isinstance(render_duration_ms, int):
            await save_llm_call_event(
                db,
                session_id=session_id,
                turn_index=turn_index_expected,
                stage="render_resolved_turn",
                gateway_mode=render_gateway_mode,
                model=model,
                success=True,
                error_code=None,
                duration_ms=render_duration_ms,
                request_id=request_id,
            )

    return (
        interpret_duration_ms,
        render_duration_ms,
        interpret_gateway_mode,
        render_gateway_mode,
        interpret_response_id,
        render_response_id,
        interpret_reasoning_summary,
        render_reasoning_summary,
    )

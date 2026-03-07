from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.api.route_paths import HEALTH_PATH, READY_PATH
from rpg_backend.api.contracts.observability import ReadinessResponse
from rpg_backend.infrastructure.db.async_engine import async_engine
from rpg_backend.infrastructure.repositories.observability_async import save_readiness_probe_event
from rpg_backend.observability.context import get_request_id
from rpg_backend.observability.logging import log_event
from rpg_backend.observability.readiness import run_readiness_checks_async

router = APIRouter(tags=["health"])


async def _save_backend_readiness_probe(
    *,
    ok: bool,
    error_code: str | None,
    latency_ms: int | None,
    request_id: str | None,
) -> None:
    try:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            await save_readiness_probe_event(
                db,
                service="backend",
                ok=ok,
                error_code=error_code,
                latency_ms=latency_ms,
                request_id=request_id,
            )
    except Exception:  # noqa: BLE001
        return


@router.get(HEALTH_PATH)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(READY_PATH, response_model=ReadinessResponse)
async def ready(request: Request, refresh: bool = Query(default=False)) -> ReadinessResponse | JSONResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    report = ReadinessResponse.model_validate(await run_readiness_checks_async(refresh=refresh))
    db_ok = bool(report.checks.db.ok)
    llm_config_ok = bool(report.checks.llm_config.ok)
    llm_probe_ok = bool(report.checks.llm_probe.ok)
    llm_probe_cached = bool(report.checks.llm_probe.meta.get("cached"))
    latency_candidates = [
        report.checks.db.latency_ms,
        report.checks.llm_config.latency_ms,
        report.checks.llm_probe.latency_ms,
    ]
    latency_ms = max(int(item) for item in latency_candidates if isinstance(item, int)) if any(
        isinstance(item, int) for item in latency_candidates
    ) else None
    if report.status == "ready":
        await _save_backend_readiness_probe(
            ok=True,
            error_code=None,
            latency_ms=latency_ms,
            request_id=request_id,
        )
        log_event(
            "readiness_check_succeeded",
            level="INFO",
            request_id=request_id,
            status_code=200,
            db_ok=db_ok,
            llm_config_ok=llm_config_ok,
            llm_probe_ok=llm_probe_ok,
            llm_probe_cached=llm_probe_cached,
            refresh=bool(refresh),
        )
        return report

    first_error_code = (
        report.checks.db.error_code
        or report.checks.llm_config.error_code
        or report.checks.llm_probe.error_code
        or "readiness_failed"
    )
    await _save_backend_readiness_probe(
        ok=False,
        error_code=first_error_code,
        latency_ms=latency_ms,
        request_id=request_id,
    )
    log_event(
        "readiness_check_failed",
        level="ERROR",
        request_id=request_id,
        status_code=503,
        db_ok=db_ok,
        llm_config_ok=llm_config_ok,
        llm_probe_ok=llm_probe_ok,
        llm_probe_cached=llm_probe_cached,
        refresh=bool(refresh),
        error_code=first_error_code,
    )
    return JSONResponse(status_code=503, content=report.model_dump(mode="json"))

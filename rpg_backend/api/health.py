from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from rpg_backend.api.schemas import ReadinessResponse
from rpg_backend.observability.context import get_request_id
from rpg_backend.observability.logging import log_event
from rpg_backend.observability.readiness import run_readiness_checks

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadinessResponse)
def ready(request: Request, refresh: bool = Query(default=False)) -> ReadinessResponse | JSONResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    report = ReadinessResponse.model_validate(run_readiness_checks(refresh=refresh))
    db_ok = bool(report.checks.db.ok)
    llm_config_ok = bool(report.checks.llm_config.ok)
    llm_probe_ok = bool(report.checks.llm_probe.ok)
    llm_probe_cached = bool(report.checks.llm_probe.meta.get("cached"))
    if report.status == "ready":
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

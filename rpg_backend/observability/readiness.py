from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.config.settings import get_settings
from rpg_backend.infrastructure.db.async_engine import async_engine
from rpg_backend.llm.base import LLMProviderConfigError
from rpg_backend.llm.factory import get_responses_agent_bundle
from rpg_backend.llm.responses_transport import ResponsesTransportError
from rpg_backend.observability.readiness_core import (
    AsyncTTLProbeCache,
    build_check_payload,
    monotonic as _core_monotonic,
    utc_now as _core_utc_now,
    validate_required_config,
)

_probe_cache: AsyncTTLProbeCache[dict[str, Any]] = AsyncTTLProbeCache()


def _utc_now() -> datetime:
    return _core_utc_now()


def _monotonic() -> float:
    return _core_monotonic()


def _build_check_result(
    *,
    ok: bool,
    latency_ms: int | None,
    checked_at: datetime,
    error_code: str | None,
    message: str | None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_check_payload(
        ok=ok,
        latency_ms=latency_ms,
        checked_at=checked_at,
        error_code=error_code,
        message=message,
        meta=meta,
    )


def _resolved_probe_config() -> tuple[dict[str, Any], list[str]]:
    settings = get_settings()
    responses_base_url = (getattr(settings, "responses_base_url", None) or "").strip()
    responses_api_key = (getattr(settings, "responses_api_key", None) or "").strip()
    probe_model = (getattr(settings, "responses_model", None) or "").strip()
    missing = validate_required_config(
        {
            "APP_RESPONSES_BASE_URL": responses_base_url,
            "APP_RESPONSES_API_KEY": responses_api_key,
            "APP_RESPONSES_MODEL": probe_model,
        }
    )
    return (
        {
            "gateway_mode": "responses",
            "responses_base_url": responses_base_url,
            "probe_model": probe_model,
        },
        missing,
    )


async def check_db() -> dict[str, Any]:
    started_at = _monotonic()
    checked_at = _utc_now()
    try:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            await db.exec(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return _build_check_result(
            ok=False,
            latency_ms=int((_monotonic() - started_at) * 1000),
            checked_at=checked_at,
            error_code="db_unavailable",
            message=str(exc),
        )
    return _build_check_result(
        ok=True,
        latency_ms=int((_monotonic() - started_at) * 1000),
        checked_at=checked_at,
        error_code=None,
        message=None,
    )


def check_llm_config() -> dict[str, Any]:
    checked_at = _utc_now()
    config, missing = _resolved_probe_config()
    responses_base_url = str(config.get("responses_base_url") or "")
    meta = {
        "gateway_mode": "responses",
        "probe_model": config.get("probe_model"),
        "responses_host": urlparse(responses_base_url).hostname,
    }
    if missing:
        return _build_check_result(
            ok=False,
            latency_ms=None,
            checked_at=checked_at,
            error_code="llm_config_invalid",
            message=f"missing config: {', '.join(missing)}",
            meta=meta,
        )
    return _build_check_result(
        ok=True,
        latency_ms=None,
        checked_at=checked_at,
        error_code=None,
        message=None,
        meta=meta,
    )


async def reset_llm_probe_cache() -> None:
    await _probe_cache.reset()


def _mark_cached_probe_result(payload: dict[str, Any]) -> dict[str, Any]:
    meta = dict(payload.get("meta") or {})
    meta["cached"] = True
    payload["meta"] = meta
    return payload


async def check_llm_probe(*, refresh: bool = False) -> dict[str, Any]:
    settings = get_settings()
    checked_at = _utc_now()
    if not settings.ready_llm_probe_enabled:
        return _build_check_result(
            ok=True,
            latency_ms=None,
            checked_at=checked_at,
            error_code=None,
            message=None,
            meta={"cached": False, "skipped": True, "reason": "probe_disabled", "gateway_mode": "responses"},
        )

    config, missing = _resolved_probe_config()
    probe_model = str(config.get("probe_model") or "")
    responses_base_url = str(config.get("responses_base_url") or "")
    responses_host = urlparse(responses_base_url).hostname
    cache_key = f"responses|{responses_base_url}|{probe_model}"
    ttl_seconds = settings.ready_llm_probe_cache_ttl_seconds

    if missing:
        return _build_check_result(
            ok=False,
            latency_ms=None,
            checked_at=checked_at,
            error_code="llm_probe_misconfigured",
            message=f"missing config: {', '.join(missing)}",
            meta={
                "cached": False,
                "gateway_mode": "responses",
                "probe_model": probe_model or None,
                "responses_host": responses_host,
            },
        )

    async def _compute_probe_result() -> dict[str, Any]:
        started_at = _monotonic()
        try:
            bundle = get_responses_agent_bundle()
            transport = bundle.play_agent.transport
            probe_response = await transport.create(
                model=probe_model,
                input=[
                    {
                        "role": "developer",
                        "content": [{"type": "input_text", "text": "Return plain text: ready"}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "responses health probe"}],
                    },
                ],
                timeout=float(settings.ready_llm_probe_timeout_seconds),
            )
            return _build_check_result(
                ok=True,
                latency_ms=int((_monotonic() - started_at) * 1000),
                checked_at=_utc_now(),
                error_code=None,
                message=None,
                meta={
                    "cached": False,
                    "gateway_mode": "responses",
                    "probe_model": probe_model,
                    "responses_host": responses_host,
                    "response_id": probe_response.response_id,
                },
            )
        except LLMProviderConfigError as exc:
            return _build_check_result(
                ok=False,
                latency_ms=int((_monotonic() - started_at) * 1000),
                checked_at=_utc_now(),
                error_code="llm_probe_misconfigured",
                message=str(exc),
                meta={
                    "cached": False,
                    "gateway_mode": "responses",
                    "probe_model": probe_model,
                    "responses_host": responses_host,
                },
            )
        except ResponsesTransportError as exc:
            return _build_check_result(
                ok=False,
                latency_ms=int((_monotonic() - started_at) * 1000),
                checked_at=_utc_now(),
                error_code=str(exc.error_code or "llm_probe_failed"),
                message=exc.message,
                meta={
                    "cached": False,
                    "gateway_mode": "responses",
                    "probe_model": probe_model,
                    "responses_host": responses_host,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return _build_check_result(
                ok=False,
                latency_ms=int((_monotonic() - started_at) * 1000),
                checked_at=_utc_now(),
                error_code="llm_probe_failed",
                message=str(exc),
                meta={
                    "cached": False,
                    "gateway_mode": "responses",
                    "probe_model": probe_model,
                    "responses_host": responses_host,
                },
            )

    return await _probe_cache.get_or_compute(
        refresh=refresh,
        cache_key=cache_key,
        ttl_seconds=float(ttl_seconds),
        compute=_compute_probe_result,
        mark_cached=_mark_cached_probe_result,
        now_provider=_monotonic,
    )


async def run_readiness_checks_async(*, refresh: bool = False) -> dict[str, Any]:
    checked_at = _utc_now()
    db_check = dict(await check_db())
    llm_config_check = check_llm_config()
    if llm_config_check["ok"]:
        llm_probe_check = dict(await check_llm_probe(refresh=refresh))
    else:
        llm_probe_check = _build_check_result(
            ok=False,
            latency_ms=None,
            checked_at=_utc_now(),
            error_code="llm_probe_misconfigured",
            message="llm probe skipped because llm_config is invalid",
            meta={"cached": False, "skipped": True, "gateway_mode": "responses"},
        )

    is_ready = bool(db_check["ok"] and llm_config_check["ok"] and llm_probe_check["ok"])
    return {
        "status": "ready" if is_ready else "not_ready",
        "checked_at": checked_at,
        "checks": {
            "db": db_check,
            "llm_config": llm_config_check,
            "llm_probe": llm_probe_check,
        },
    }

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from rpg_backend.llm.task_specs import build_readiness_probe_task, validate_readiness_probe_payload
from rpg_backend.llm_worker.errors import WorkerTaskError
from rpg_backend.llm_worker.schemas import WorkerReadyCheckPayload, WorkerReadyResponse
from rpg_backend.llm_worker.services.task_service import WorkerTaskService
from rpg_backend.observability.readiness_core import (
    AsyncTTLProbeCache,
    build_check_payload,
    monotonic,
    utc_now,
    validate_required_config,
)


class WorkerReadinessService:
    def __init__(self, *, task_service: WorkerTaskService) -> None:
        self._task_service = task_service
        self._probe_cache: AsyncTTLProbeCache[WorkerReadyCheckPayload] = AsyncTTLProbeCache()

    @staticmethod
    def _utc_now() -> datetime:
        return utc_now()

    @staticmethod
    def _monotonic() -> float:
        return monotonic()

    @staticmethod
    def _check_payload(
        *,
        ok: bool,
        latency_ms: int | None,
        error_code: str | None = None,
        message: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> WorkerReadyCheckPayload:
        return WorkerReadyCheckPayload.model_validate(
            build_check_payload(
                ok=ok,
                latency_ms=latency_ms,
                checked_at=WorkerReadinessService._utc_now(),
                error_code=error_code,
                message=message,
                meta=meta,
            )
        )

    def _config_missing(self) -> list[str]:
        missing = validate_required_config(
            {
                "APP_LLM_OPENAI_BASE_URL": self._task_service.base_url,
                "APP_LLM_OPENAI_API_KEY": self._task_service.api_key,
                (
                    "one of APP_LLM_OPENAI_GENERATOR_MODEL / APP_LLM_OPENAI_ROUTE_MODEL / "
                    "APP_LLM_OPENAI_NARRATION_MODEL / APP_LLM_OPENAI_MODEL"
                ): self._task_service.generator_model,
            }
        )
        if self._task_service.upstream_api_format not in {"chat_completions", "responses"}:
            missing.append("APP_LLM_WORKER_UPSTREAM_API_FORMAT(chat_completions|responses)")
        return missing

    @staticmethod
    def _mark_cached_probe(check: WorkerReadyCheckPayload) -> WorkerReadyCheckPayload:
        check.meta["cached"] = True
        return check

    async def _run_probe(self) -> WorkerReadyCheckPayload:
        started = self._monotonic()
        probe_model = (
            self._task_service.generator_model
            or self._task_service.route_model
            or self._task_service.narration_model
        )
        if not probe_model:
            return self._check_payload(
                ok=False,
                latency_ms=None,
                error_code="worker_probe_misconfigured",
                message="probe model is missing",
                meta={"cached": False},
            )

        try:
            execution = await self._task_service.execute_task(
                spec=build_readiness_probe_task(),
                model=probe_model,
                temperature=0.0,
                max_retries=1,
                timeout_seconds=float(self._task_service.settings.ready_llm_probe_timeout_seconds),
                error_code_prefix="worker_probe",
            )
            parsed = validate_readiness_probe_payload(execution.payload)
            return self._check_payload(
                ok=True,
                latency_ms=int((self._monotonic() - started) * 1000),
                meta={
                    "cached": False,
                    "probe_model": probe_model,
                    "base_url_host": urlparse(self._task_service.base_url).hostname,
                    "who_preview": parsed.who.strip()[:120],
                },
            )
        except WorkerTaskError as exc:
            return self._check_payload(
                ok=False,
                latency_ms=int((self._monotonic() - started) * 1000),
                error_code=exc.error_code,
                message=exc.message,
                meta={
                    "cached": False,
                    "probe_model": probe_model,
                    "base_url_host": urlparse(self._task_service.base_url).hostname,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return self._check_payload(
                ok=False,
                latency_ms=int((self._monotonic() - started) * 1000),
                error_code="worker_probe_invalid_response",
                message=str(exc),
                meta={
                    "cached": False,
                    "probe_model": probe_model,
                    "base_url_host": urlparse(self._task_service.base_url).hostname,
                },
            )

    async def ready(self, *, refresh: bool = False) -> WorkerReadyResponse:
        checked_at = self._utc_now()
        missing = self._config_missing()
        llm_config_ok = len(missing) == 0

        llm_config = self._check_payload(
            ok=llm_config_ok,
            latency_ms=None,
            error_code=None if llm_config_ok else "worker_llm_config_invalid",
            message=None if llm_config_ok else f"missing config: {', '.join(missing)}",
            meta={
                "route_model": self._task_service.route_model,
                "narration_model": self._task_service.narration_model,
                "generator_model": self._task_service.generator_model,
                "base_url_host": urlparse(self._task_service.base_url).hostname,
            },
        )

        if not llm_config_ok:
            llm_probe = self._check_payload(
                ok=False,
                latency_ms=None,
                error_code="worker_probe_misconfigured",
                message="worker probe skipped because llm config is invalid",
                meta={"cached": False, "skipped": True},
            )
            return WorkerReadyResponse(
                status="not_ready",
                checked_at=checked_at,
                checks={"llm_config": llm_config, "llm_probe": llm_probe},
            )

        cache_key = (
            f"{self._task_service.base_url}|"
            f"{self._task_service.generator_model or self._task_service.route_model or self._task_service.narration_model}"
        )
        ttl_seconds = int(self._task_service.settings.ready_llm_probe_cache_ttl_seconds)
        llm_probe = await self._probe_cache.get_or_compute(
            refresh=refresh,
            cache_key=cache_key,
            ttl_seconds=float(ttl_seconds),
            compute=self._run_probe,
            mark_cached=self._mark_cached_probe,
            now_provider=self._monotonic,
        )

        return WorkerReadyResponse(
            status="ready" if llm_probe.ok else "not_ready",
            checked_at=checked_at,
            checks={"llm_config": llm_config, "llm_probe": llm_probe},
        )

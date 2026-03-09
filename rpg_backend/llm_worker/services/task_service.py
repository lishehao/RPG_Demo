from __future__ import annotations

import asyncio
from typing import Any

import httpx

from rpg_backend.config.settings import get_settings
from rpg_backend.llm.factory import resolve_openai_generator_model, resolve_openai_models
from rpg_backend.llm.task_executor import TaskExecutionResult, TaskExecutorError, TaskUsage, execute_json_task
from rpg_backend.llm.task_specs import TaskSpec
from rpg_backend.llm_worker.errors import WorkerTaskError
from rpg_backend.llm_worker.schemas import (
    WorkerTaskJsonObjectRequest,
    WorkerTaskJsonObjectResponse,
)
from rpg_backend.llm_worker.upstream.base import WorkerUpstreamClient
from rpg_backend.llm_worker.upstream.factory import build_worker_upstream_client


class WorkerTaskService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.base_url = (settings.llm_openai_base_url or "").strip()
        self.api_key = (settings.llm_openai_api_key or "").strip()
        route_model, narration_model = resolve_openai_models(
            settings.llm_openai_route_model,
            settings.llm_openai_narration_model,
            settings.llm_openai_model,
        )
        self.route_model = route_model
        self.narration_model = narration_model
        self.generator_model = resolve_openai_generator_model(
            settings.llm_openai_generator_model,
            settings.llm_openai_model,
        )
        self.upstream_api_format = (
            getattr(settings, "llm_worker_upstream_api_format", None) or "chat_completions"
        ).strip()

        self._client: httpx.AsyncClient | None = None
        self._upstream_client: WorkerUpstreamClient | None = None

    async def startup(self) -> None:
        if self._client is not None:
            return

        limits = httpx.Limits(
            max_connections=self.settings.llm_worker_max_connections,
            max_keepalive_connections=self.settings.llm_worker_max_keepalive_connections,
            keepalive_expiry=30.0,
        )
        timeout = httpx.Timeout(
            connect=self.settings.llm_worker_connect_timeout_seconds,
            read=self.settings.llm_worker_timeout_seconds,
            write=self.settings.llm_worker_timeout_seconds,
            pool=self.settings.llm_worker_timeout_seconds,
        )
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=bool(self.settings.llm_worker_http2_enabled),
        )
        self._upstream_client = build_worker_upstream_client(
            http_client=self._client,
            api_format=self.upstream_api_format,
            base_url=self.base_url,
            api_key=self.api_key,
        )

    async def shutdown(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None
        self._upstream_client = None

    @staticmethod
    def _monotonic() -> float:
        return asyncio.get_running_loop().time()

    async def call_json_object(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], TaskUsage]:
        if self._client is None:
            await self.startup()
        assert self._upstream_client is not None
        result = await self._upstream_client.call_json_object(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
        return result.payload, result.usage

    async def execute_task(
        self,
        *,
        spec: TaskSpec,
        model: str,
        temperature: float,
        max_retries: int,
        timeout_seconds: float,
        error_code_prefix: str,
    ) -> TaskExecutionResult:
        try:
            return await execute_json_task(
                caller=self,
                model=model,
                system_prompt=spec.system_prompt,
                user_payload=spec.user_payload,
                temperature=temperature,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
                error_code_prefix=error_code_prefix,
            )
        except TaskExecutorError as exc:
            raise WorkerTaskError(
                error_code=exc.error_code,
                message=exc.message,
                retryable=exc.retryable,
                provider_status=exc.status_code,
                model=exc.model or model,
                attempts=exc.attempts,
            ) from exc

    async def execute_json_object_task(
        self,
        payload: WorkerTaskJsonObjectRequest,
    ) -> tuple[WorkerTaskJsonObjectResponse, TaskUsage]:
        started = self._monotonic()
        timeout_seconds = float(payload.timeout_seconds or self.settings.llm_openai_timeout_seconds)
        spec = TaskSpec(
            task_name="json_object",
            system_prompt=payload.system_prompt,
            user_payload=payload.user_prompt,
        )
        execution = await self.execute_task(
            spec=spec,
            model=payload.model,
            temperature=float(payload.temperature),
            max_retries=int(payload.max_retries),
            timeout_seconds=timeout_seconds,
            error_code_prefix="json_task",
        )
        response = WorkerTaskJsonObjectResponse(
            payload=execution.payload,
            model=payload.model,
            attempts=execution.attempts,
            retry_count=max(0, execution.attempts - 1),
            duration_ms=int((self._monotonic() - started) * 1000),
        )
        return response, execution.usage

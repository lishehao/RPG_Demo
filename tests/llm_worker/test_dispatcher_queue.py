from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from rpg_backend.llm.task_executor import TaskUsage
from rpg_backend.llm_worker.dispatcher import WorkerDispatcher, WorkerQueueConfig
from rpg_backend.llm_worker.errors import WorkerTaskError
from rpg_backend.llm_worker.schemas import (
    WorkerTaskJsonObjectRequest,
    WorkerTaskJsonObjectResponse,
    WorkerTaskNarrationRequest,
    WorkerTaskNarrationResponse,
    WorkerTaskRouteIntentRequest,
    WorkerTaskRouteIntentResponse,
)


class _FakeQuotaService:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.reconcile_calls: list[dict[str, int | str | None]] = []

    @staticmethod
    def estimate_tokens(*, system_prompt: str, user_prompt: str, output_token_estimate: int) -> int:
        del system_prompt, user_prompt
        return max(1, int(output_token_estimate))

    async def reserve_async(self, *, model: str, estimated_tokens: int):  # noqa: ANN003, ANN201
        return SimpleNamespace(
            allowed=self.allow,
            model=model,
            window_epoch_minute=123456,
            estimated_tokens=estimated_tokens,
        )

    async def reconcile_async(
        self,
        *,
        model: str,
        window_epoch_minute: int,
        estimated_tokens: int,
        actual_total_tokens: int | None,
    ) -> None:
        self.reconcile_calls.append(
            {
                "model": model,
                "window_epoch_minute": window_epoch_minute,
                "estimated_tokens": estimated_tokens,
                "actual_total_tokens": actual_total_tokens,
            }
        )


class _FakeService:
    async def execute_route_intent_task(self, payload: WorkerTaskRouteIntentRequest):  # noqa: ANN201
        return (
            WorkerTaskRouteIntentResponse(
                move_id="global.help_me_progress",
                args={},
                confidence=0.8,
                interpreted_intent=payload.text or "help",
                model=payload.model,
                attempts=1,
                retry_count=0,
                duration_ms=5,
            ),
            TaskUsage(total_tokens=21),
        )

    async def execute_render_narration_task(self, payload: WorkerTaskNarrationRequest):  # noqa: ANN201
        return (
            WorkerTaskNarrationResponse(
                narration_text="narration",
                model=payload.model,
                attempts=1,
                retry_count=0,
                duration_ms=6,
            ),
            TaskUsage(total_tokens=33),
        )

    async def execute_json_object_task(self, payload: WorkerTaskJsonObjectRequest):  # noqa: ANN201
        return (
            WorkerTaskJsonObjectResponse(
                payload={"ok": True},
                model=payload.model,
                attempts=1,
                retry_count=0,
                duration_ms=7,
            ),
            TaskUsage(total_tokens=55),
        )


class _ConcurrencyTrackingService(_FakeService):
    def __init__(self, *, sleep_seconds: float = 0.05) -> None:
        self._sleep_seconds = float(sleep_seconds)
        self._active_count = 0
        self.max_active_count = 0
        self._lock = asyncio.Lock()

    async def execute_route_intent_task(self, payload: WorkerTaskRouteIntentRequest):  # noqa: ANN201
        async with self._lock:
            self._active_count += 1
            if self._active_count > self.max_active_count:
                self.max_active_count = self._active_count
        try:
            await asyncio.sleep(self._sleep_seconds)
            return await super().execute_route_intent_task(payload)
        finally:
            async with self._lock:
                self._active_count -= 1


def _config(
    *,
    max_size: int = 4,
    wait_timeout_seconds: float = 0.1,
    executor_concurrency: int = 1,
) -> WorkerQueueConfig:
    return WorkerQueueConfig(
        max_size=max_size,
        wait_timeout_seconds=wait_timeout_seconds,
        weights={"route_intent": 5, "render_narration": 3, "json_object": 2},
        executor_concurrency=executor_concurrency,
        token_est_route_output=96,
        token_est_narration_output=192,
        token_est_json_output=256,
    )


def test_dispatcher_queue_full_when_capacity_exceeded() -> None:
    dispatcher = WorkerDispatcher(
        service=_FakeService(),
        quota_service=_FakeQuotaService(allow=True),
        config=_config(max_size=1, wait_timeout_seconds=0.05),
    )
    payload = WorkerTaskRouteIntentRequest(
        scene_context={"moves": [], "fallback_move": "global.help_me_progress"},
        text="help",
        model="m",
        temperature=0.1,
        max_retries=1,
        timeout_seconds=0.05,
    )

    async def _run() -> None:
        first_task = asyncio.create_task(dispatcher.submit_route_intent(payload=payload, request_id="r1"))
        await asyncio.sleep(0)

        with pytest.raises(WorkerTaskError) as exc_info:
            await dispatcher.submit_route_intent(payload=payload, request_id="r2")
        assert exc_info.value.error_code == "worker_queue_full"

        with pytest.raises(WorkerTaskError):
            await first_task

    asyncio.run(_run())


def test_dispatcher_rate_limited_when_reservation_denied() -> None:
    dispatcher = WorkerDispatcher(
        service=_FakeService(),
        quota_service=_FakeQuotaService(allow=False),
        config=_config(max_size=8, wait_timeout_seconds=0.05),
    )

    async def _run() -> None:
        await dispatcher.start()
        try:
            payload = WorkerTaskRouteIntentRequest(
                scene_context={"moves": [], "fallback_move": "global.help_me_progress"},
                text="help",
                model="m",
                temperature=0.1,
                max_retries=1,
                timeout_seconds=0.05,
            )
            with pytest.raises(WorkerTaskError) as exc_info:
                await dispatcher.submit_route_intent(payload=payload, request_id="r3")
            assert exc_info.value.error_code in {"worker_rate_limited", "worker_queue_timeout"}
        finally:
            await dispatcher.stop()

    asyncio.run(_run())


def test_dispatcher_reconciles_actual_usage_on_success() -> None:
    quota = _FakeQuotaService(allow=True)
    dispatcher = WorkerDispatcher(
        service=_FakeService(),
        quota_service=quota,
        config=_config(max_size=8, wait_timeout_seconds=0.2),
    )

    async def _run() -> None:
        await dispatcher.start()
        try:
            payload = WorkerTaskJsonObjectRequest(
                system_prompt="return json",
                user_prompt='{"ok": true}',
                model="model-a",
                temperature=0.1,
                max_retries=1,
                timeout_seconds=0.2,
            )
            result = await dispatcher.submit_json_object(payload=payload, request_id="rq-json")
            assert result.payload == {"ok": True}
            assert quota.reconcile_calls
            call = quota.reconcile_calls[0]
            assert call["model"] == "model-a"
            assert call["actual_total_tokens"] == 55
        finally:
            await dispatcher.stop()

    asyncio.run(_run())


def test_dispatcher_limits_max_inflight_to_executor_concurrency() -> None:
    quota = _FakeQuotaService(allow=True)
    service = _ConcurrencyTrackingService(sleep_seconds=0.05)
    dispatcher = WorkerDispatcher(
        service=service,
        quota_service=quota,
        config=_config(max_size=32, wait_timeout_seconds=1.0, executor_concurrency=2),
    )

    async def _run() -> None:
        await dispatcher.start()
        try:
            payload = WorkerTaskRouteIntentRequest(
                scene_context={"moves": [], "fallback_move": "global.help_me_progress"},
                text="help",
                model="m",
                temperature=0.1,
                max_retries=1,
                timeout_seconds=1.0,
            )
            tasks = [
                asyncio.create_task(dispatcher.submit_route_intent(payload=payload, request_id=f"r-{index}"))
                for index in range(6)
            ]
            results = await asyncio.gather(*tasks)
            assert all(item.move_id == "global.help_me_progress" for item in results)
            assert service.max_active_count <= 2
        finally:
            await dispatcher.stop()

    asyncio.run(_run())

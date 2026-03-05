from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from rpg_backend.llm_worker.errors import WorkerTaskError
from rpg_backend.llm_worker.queue import QueuedTask, TaskKind, WeightedTaskQueue
from rpg_backend.llm_worker.quota_service import QuotaService
from rpg_backend.llm_worker.schemas import (
    WorkerTaskJsonObjectRequest,
    WorkerTaskNarrationRequest,
    WorkerTaskRouteIntentRequest,
)
from rpg_backend.llm_worker.service import LLMWorkerService


@dataclass(frozen=True)
class WorkerQueueConfig:
    max_size: int
    wait_timeout_seconds: float
    weights: dict[TaskKind, int]
    executor_concurrency: int
    token_est_route_output: int
    token_est_narration_output: int
    token_est_json_output: int


class WorkerDispatcher:
    def __init__(
        self,
        *,
        service: LLMWorkerService,
        quota_service: QuotaService,
        config: WorkerQueueConfig,
    ) -> None:
        self._service = service
        self._quota_service = quota_service
        self._queue = WeightedTaskQueue(max_size=config.max_size, weights=config.weights)
        self._wait_timeout_seconds = float(config.wait_timeout_seconds)
        self._executor_concurrency = max(1, int(config.executor_concurrency))
        self._token_est_route_output = max(1, int(config.token_est_route_output))
        self._token_est_narration_output = max(1, int(config.token_est_narration_output))
        self._token_est_json_output = max(1, int(config.token_est_json_output))
        self._dispatcher_tasks: list[asyncio.Task[Any]] = []
        self._running = False
        self._rate_limit_backoff_seconds = 0.08

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for index in range(self._executor_concurrency):
            task = asyncio.create_task(self._run_loop(index), name=f"worker-dispatcher-{index}")
            self._dispatcher_tasks.append(task)

    async def stop(self) -> None:
        self._running = False
        for task in self._dispatcher_tasks:
            task.cancel()
        if self._dispatcher_tasks:
            await asyncio.gather(*self._dispatcher_tasks, return_exceptions=True)
        self._dispatcher_tasks.clear()

    async def submit_route_intent(
        self,
        *,
        payload: WorkerTaskRouteIntentRequest,
        request_id: str | None,
    ):
        return await self._submit(kind="route_intent", payload=payload, request_id=request_id)

    async def submit_render_narration(
        self,
        *,
        payload: WorkerTaskNarrationRequest,
        request_id: str | None,
    ):
        return await self._submit(kind="render_narration", payload=payload, request_id=request_id)

    async def submit_json_object(
        self,
        *,
        payload: WorkerTaskJsonObjectRequest,
        request_id: str | None,
    ):
        return await self._submit(kind="json_object", payload=payload, request_id=request_id)

    async def _submit(
        self,
        *,
        kind: TaskKind,
        payload: Any,
        request_id: str | None,
    ) -> Any:
        now = time.monotonic()
        timeout = self._wait_timeout_seconds
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        queued = QueuedTask(
            kind=kind,
            payload=payload,
            request_id=request_id,
            created_monotonic=now,
            deadline_monotonic=now + timeout,
            future=future,
        )
        accepted = await self._queue.put_nowait(queued)
        if not accepted:
            raise WorkerTaskError(
                error_code="worker_queue_full",
                message="worker queue is full",
                retryable=True,
                model=str(getattr(payload, "model", "") or ""),
                attempts=1,
            )
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            if not future.done():
                future.cancel()
            raise WorkerTaskError(
                error_code="worker_queue_timeout",
                message="worker queue wait timeout",
                retryable=True,
                model=str(getattr(payload, "model", "") or ""),
                attempts=1,
            ) from exc

    def _estimate_tokens(self, *, kind: TaskKind, payload: Any) -> int:
        if kind == "route_intent":
            output = self._token_est_route_output
        elif kind == "render_narration":
            output = self._token_est_narration_output
        else:
            output = self._token_est_json_output
        try:
            payload_json = payload.model_dump_json()
        except Exception:  # noqa: BLE001
            payload_json = str(payload)
        system_prompt = kind
        user_prompt = payload_json
        return self._quota_service.estimate_tokens(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_token_estimate=output,
        )

    async def _run_loop(self, _worker_index: int) -> None:
        while self._running:
            task = await self._queue.get()
            try:
                if task.future.cancelled() or task.future.done():
                    continue

                if time.monotonic() >= task.deadline_monotonic:
                    if not task.future.done():
                        task.future.set_exception(
                            WorkerTaskError(
                                error_code="worker_queue_timeout",
                                message="worker queue wait timeout",
                                retryable=True,
                                model=str(getattr(task.payload, "model", "") or ""),
                                attempts=1,
                            )
                        )
                    continue

                model = str(getattr(task.payload, "model", "") or "")
                estimated_tokens = self._estimate_tokens(kind=task.kind, payload=task.payload)
                reservation = self._quota_service.reserve(model=model, estimated_tokens=estimated_tokens)
                if not reservation.allowed:
                    if time.monotonic() >= task.deadline_monotonic:
                        if not task.future.done():
                            task.future.set_exception(
                                WorkerTaskError(
                                    error_code="worker_rate_limited",
                                    message="worker rate limited",
                                    retryable=True,
                                    model=model,
                                    attempts=1,
                                )
                            )
                        continue
                    await asyncio.sleep(self._rate_limit_backoff_seconds)
                    requeued = await self._queue.requeue(task)
                    if not requeued and not task.future.done():
                        task.future.set_exception(
                            WorkerTaskError(
                                error_code="worker_queue_full",
                                message="worker queue is full",
                                retryable=True,
                                model=model,
                                attempts=1,
                            )
                        )
                    continue

                try:
                    if task.kind == "route_intent":
                        result, usage = await self._service.execute_route_intent_task(task.payload)
                    elif task.kind == "render_narration":
                        result, usage = await self._service.execute_render_narration_task(task.payload)
                    else:
                        result, usage = await self._service.execute_json_object_task(task.payload)
                except WorkerTaskError as exc:
                    if not task.future.done():
                        task.future.set_exception(exc)
                    continue
                except Exception as exc:  # noqa: BLE001
                    if not task.future.done():
                        task.future.set_exception(
                            WorkerTaskError(
                                error_code="worker_task_failed",
                                message=str(exc),
                                retryable=False,
                                model=model,
                                attempts=1,
                            )
                        )
                    continue

                try:
                    self._quota_service.reconcile_usage(
                        model=model,
                        window_epoch_minute=reservation.window_epoch_minute,
                        estimated_tokens=reservation.estimated_tokens,
                        actual_total_tokens=usage.total_tokens,
                    )
                except Exception:  # noqa: BLE001
                    pass

                if not task.future.done():
                    task.future.set_result(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if not task.future.done():
                    task.future.set_exception(
                        WorkerTaskError(
                            error_code="worker_dispatcher_failed",
                            message=str(exc),
                            retryable=True,
                            model=str(getattr(task.payload, "model", "") or ""),
                            attempts=1,
                        )
                    )
                continue

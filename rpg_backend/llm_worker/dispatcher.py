from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from rpg_backend.llm_worker.errors import WorkerTaskError
from rpg_backend.llm_worker.queue import QueuedTask, TaskKind, WeightedTaskQueue
from rpg_backend.llm_worker.services.quota_service import QuotaService
from rpg_backend.llm_worker.schemas import WorkerTaskJsonObjectRequest
from rpg_backend.llm_worker.services.task_service import WorkerTaskService


@dataclass(frozen=True)
class WorkerQueueConfig:
    max_size: int
    wait_timeout_seconds: float
    weights: dict[TaskKind, int]
    executor_concurrency: int
    token_est_json_output: int


class WorkerDispatcher:
    def __init__(
        self,
        *,
        service: WorkerTaskService,
        quota_service: QuotaService,
        config: WorkerQueueConfig,
    ) -> None:
        self._service = service
        self._quota_service = quota_service
        self._queue = WeightedTaskQueue(max_size=config.max_size, weights=config.weights)
        self._wait_timeout_seconds = float(config.wait_timeout_seconds)
        self._executor_concurrency = max(1, int(config.executor_concurrency))
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

    async def submit_json_object(
        self,
        *,
        payload: WorkerTaskJsonObjectRequest,
        request_id: str | None,
    ):
        return await self._submit(kind="json_object", payload=payload, request_id=request_id)

    async def _submit(self, *, kind: TaskKind, payload: Any, request_id: str | None):
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        task = QueuedTask(
            kind=kind,
            payload=payload,
            request_id=request_id,
            created_monotonic=time.monotonic(),
            deadline_monotonic=time.monotonic() + self._wait_timeout_seconds,
            future=future,
        )
        queued = await self._queue.put_nowait(task)
        if not queued:
            raise WorkerTaskError(
                error_code="worker_queue_full",
                message="worker queue is full",
                retryable=True,
                model=str(getattr(payload, "model", "") or ""),
                attempts=1,
            )
        if not self._running:
            try:
                return await asyncio.wait_for(future, timeout=self._wait_timeout_seconds)
            except asyncio.TimeoutError as exc:
                raise WorkerTaskError(
                    error_code="worker_queue_timeout",
                    message="worker queue wait timeout",
                    retryable=True,
                    model=str(getattr(payload, "model", "") or ""),
                    attempts=1,
                ) from exc
        return await future

    def _estimate_tokens(self, *, payload: Any) -> int:
        try:
            payload_json = payload.model_dump_json()
        except Exception:  # noqa: BLE001
            payload_json = str(payload)
        return self._quota_service.estimate_tokens(
            system_prompt="json_object",
            user_prompt=payload_json,
            output_token_estimate=self._token_est_json_output,
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
                estimated_tokens = self._estimate_tokens(payload=task.payload)
                reservation = await self._quota_service.reserve_async(model=model, estimated_tokens=estimated_tokens)
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
                    await self._quota_service.reconcile_async(
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

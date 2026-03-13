from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from rpg_backend.llm.retry_policy import is_retriable_llm_error, retry_delay_seconds


@dataclass(frozen=True)
class TaskUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class TaskExecutionResult:
    payload: dict[str, Any]
    attempts: int
    duration_ms: int
    usage: TaskUsage = TaskUsage()


@dataclass
class TaskExecutorError(RuntimeError):
    error_code: str
    message: str
    retryable: bool = False
    status_code: int | None = None
    attempts: int = 1
    model: str | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class UpstreamJsonCaller(Protocol):
    async def call_json_object(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], TaskUsage]:
        raise NotImplementedError


def _to_executor_error(
    *,
    exc: Exception,
    attempts: int,
    model: str,
    error_code_prefix: str,
    timeout_seconds: float,
) -> TaskExecutorError:
    if isinstance(exc, TaskExecutorError):
        return TaskExecutorError(
            error_code=exc.error_code,
            message=exc.message,
            retryable=exc.retryable,
            status_code=exc.status_code,
            attempts=max(exc.attempts, attempts),
            model=model,
        )
    if isinstance(exc, httpx.TimeoutException):
        detail = str(exc).strip()
        message = detail or f"request timed out after {float(timeout_seconds):.1f}s"
        return TaskExecutorError(
            error_code=f"{error_code_prefix}_timeout",
            message=message,
            retryable=True,
            status_code=None,
            attempts=attempts,
            model=model,
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return TaskExecutorError(
            error_code=f"{error_code_prefix}_http_error",
            message=f"status={exc.response.status_code}",
            retryable=exc.response.status_code in {408, 409, 425, 429, 500, 502, 503, 504},
            status_code=exc.response.status_code,
            attempts=attempts,
            model=model,
        )
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return TaskExecutorError(
            error_code=f"{error_code_prefix}_invalid_response",
            message=str(exc),
            retryable=True,
            status_code=None,
            attempts=attempts,
            model=model,
        )
    if isinstance(exc, httpx.HTTPError):
        return TaskExecutorError(
            error_code=f"{error_code_prefix}_http_error",
            message=str(exc),
            retryable=True,
            status_code=None,
            attempts=attempts,
            model=model,
        )
    return TaskExecutorError(
        error_code=f"{error_code_prefix}_failed",
        message=str(exc),
        retryable=False,
        status_code=None,
        attempts=attempts,
        model=model,
    )


async def execute_json_task(
    *,
    caller: UpstreamJsonCaller,
    model: str,
    system_prompt: str,
    user_payload: Any,
    temperature: float,
    max_retries: int,
    timeout_seconds: float,
    error_code_prefix: str,
) -> TaskExecutionResult:
    retries = max(1, min(int(max_retries), 3))
    started = time.perf_counter()
    last_exc: Exception | None = None
    last_attempt = 1
    user_prompt = user_payload if isinstance(user_payload, str) else json.dumps(user_payload, ensure_ascii=False)

    for attempt in range(1, retries + 1):
        try:
            payload, usage = await caller.call_json_object(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=float(temperature),
                timeout_seconds=float(timeout_seconds),
            )
            if not isinstance(payload, dict):
                raise ValueError("payload is not a JSON object")
            return TaskExecutionResult(
                payload=payload,
                attempts=attempt,
                duration_ms=int((time.perf_counter() - started) * 1000),
                usage=usage,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            last_attempt = attempt
            if not is_retriable_llm_error(exc) or attempt >= retries:
                break
            delay = retry_delay_seconds(attempt, exc)
            if delay > 0:
                await asyncio.sleep(delay)

    assert last_exc is not None
    raise _to_executor_error(
        exc=last_exc,
        attempts=last_attempt,
        model=model,
        error_code_prefix=error_code_prefix,
        timeout_seconds=float(timeout_seconds),
    ) from last_exc

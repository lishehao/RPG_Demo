from __future__ import annotations

import asyncio

import httpx
import pytest

import rpg_backend.llm.task_executor as executor_module
from rpg_backend.llm.task_executor import TaskExecutorError, TaskUsage, execute_json_task


class _FakeCaller:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def call_json_object(self, **_kwargs):  # noqa: ANN003, ANN201
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_execute_json_task_success() -> None:
    caller = _FakeCaller(
        [
            (
                {"ok": True, "value": 1},
                TaskUsage(input_tokens=11, output_tokens=7, total_tokens=18),
            )
        ]
    )
    result = asyncio.run(
        execute_json_task(
            caller=caller,
            model="model-a",
            system_prompt="system",
            user_payload={"q": "hello"},
            temperature=0.1,
            max_retries=3,
            timeout_seconds=5.0,
            error_code_prefix="json_task",
        )
    )
    assert result.payload["ok"] is True
    assert result.attempts == 1
    assert result.usage.total_tokens == 18
    assert caller.calls == 1


def test_execute_json_task_retries_on_retriable_error(monkeypatch) -> None:
    request = httpx.Request("POST", "https://worker.example/v1/chat/completions")
    retriable = httpx.HTTPStatusError("temporary failure", request=request, response=httpx.Response(503, request=request))
    caller = _FakeCaller(
        [
            retriable,
            (
                {"ok": True},
                TaskUsage(total_tokens=20),
            ),
        ]
    )
    monkeypatch.setattr(executor_module, "retry_delay_seconds", lambda *_args, **_kwargs: 0.0)
    result = asyncio.run(
        execute_json_task(
            caller=caller,
            model="model-a",
            system_prompt="system",
            user_payload={"q": "hello"},
            temperature=0.1,
            max_retries=3,
            timeout_seconds=5.0,
            error_code_prefix="json_task",
        )
    )
    assert result.payload["ok"] is True
    assert result.attempts == 2
    assert caller.calls == 2


def test_execute_json_task_no_retry_on_non_retriable_http_status() -> None:
    request = httpx.Request("POST", "https://worker.example/v1/chat/completions")
    non_retriable = httpx.HTTPStatusError("unauthorized", request=request, response=httpx.Response(401, request=request))
    caller = _FakeCaller([non_retriable])
    with pytest.raises(TaskExecutorError) as exc_info:
        asyncio.run(
            execute_json_task(
                caller=caller,
                model="model-a",
                system_prompt="system",
                user_payload={"q": "hello"},
                temperature=0.1,
                max_retries=3,
                timeout_seconds=5.0,
                error_code_prefix="json_task",
            )
        )
    assert exc_info.value.error_code == "json_task_http_error"
    assert exc_info.value.retryable is False
    assert exc_info.value.attempts == 1
    assert caller.calls == 1

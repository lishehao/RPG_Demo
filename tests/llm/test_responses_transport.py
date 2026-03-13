from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import rpg_backend.llm.responses_transport as transport_module
from rpg_backend.llm.responses_transport import ResponsesTransport, ResponsesTransportError


def test_transport_forwards_previous_response_id_and_extra_body(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class _FakeResponses:
        async def create(self, **kwargs):  # noqa: ANN003, ANN201
            calls.append(dict(kwargs))
            return {
                "id": "resp_new",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "ok"}],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs
            self.responses = _FakeResponses()

    monkeypatch.setattr(transport_module, "AsyncOpenAI", _FakeAsyncOpenAI)

    transport = ResponsesTransport(
        base_url="https://example.com/compatible-mode",
        api_key="test-key",
        model="qwen-plus",
        timeout_seconds=20.0,
    )
    result = asyncio.run(
        transport.create(
            model="qwen-plus",
            input=[{"role": "developer", "content": [{"type": "input_text", "text": "test"}]}],
            previous_response_id="resp_prev",
            timeout=7.0,
            extra_body={"enable_thinking": True},
        )
    )

    assert result.response_id == "resp_new"
    assert result.output_text == "ok"
    assert len(calls) == 1
    assert calls[0]["previous_response_id"] == "resp_prev"
    assert calls[0]["extra_body"] == {"enable_thinking": True}
    assert calls[0]["timeout"] == 7.0


def test_transport_missing_model_raises() -> None:
    transport = ResponsesTransport.__new__(ResponsesTransport)
    transport.default_model = ""
    transport.default_timeout_seconds = 20.0
    transport._client = SimpleNamespace(responses=SimpleNamespace())
    with pytest.raises(ResponsesTransportError):
        asyncio.run(transport.create(model="", input=[]))

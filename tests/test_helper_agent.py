from __future__ import annotations

from types import SimpleNamespace

import pytest

import rpg_backend.helper.agent as helper_agent_module
from rpg_backend.config import Settings
from rpg_backend.helper.agent import HelperAgentClient, HelperAgentError, HelperRequest
from rpg_backend.llm_gateway import helper_gateway_config_available


class _FakeHelperClient:
    def __init__(self, *, response_text: str = '{"ok": true}', chat_text: str = '{"ok": true}') -> None:
        self._response_text = response_text
        self._chat_text = chat_text
        self.responses = SimpleNamespace(create=self._create_response)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create_chat_completion))

    def _create_response(self, **_kwargs):
        return SimpleNamespace(
            output_text=self._response_text,
            id="resp-1",
            usage={"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
        )

    def _create_chat_completion(self, **_kwargs):
        return SimpleNamespace(
            id="chat-1",
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._chat_text))],
            usage={"input_tokens": 9, "output_tokens": 3, "total_tokens": 12},
        )


def test_helper_gateway_config_available_requires_helper_fields() -> None:
    missing = Settings(_env_file=None)
    configured = Settings(
        _env_file=None,
        helper_gateway_base_url="https://helper.example/v1",
        helper_gateway_responses_base_url="https://helper-responses.example/v1",
        helper_gateway_api_key="helper-key",
        helper_gateway_model="helper-model",
    )

    assert helper_gateway_config_available(missing) is False
    assert helper_gateway_config_available(configured) is True
    assert configured.resolved_helper_gateway_base_url(transport_style="responses") == "https://helper-responses.example/v1"
    assert configured.resolved_helper_gateway_base_url(transport_style="chat_completions") == "https://helper.example/v1"


def test_helper_agent_client_requires_explicit_helper_config() -> None:
    with pytest.raises(HelperAgentError) as exc_info:
        HelperAgentClient(settings=Settings(_env_file=None))

    assert exc_info.value.code == "helper_agent_config_missing"


def test_helper_agent_client_invokes_responses_and_records_trace(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_client(**kwargs):
        captured.update(kwargs)
        return _FakeHelperClient(response_text='{"answer":"ok"}')

    monkeypatch.setattr(helper_agent_module, "build_openai_client", _fake_client)
    settings = Settings(
        _env_file=None,
        helper_gateway_base_url="https://helper.example/v1",
        helper_gateway_responses_base_url="https://helper-responses.example/v1",
        helper_gateway_api_key="helper-key",
        helper_gateway_model="helper-model",
    )
    client = HelperAgentClient(settings=settings, transport_style="responses")

    response = client.invoke(
        HelperRequest(
            system_prompt="Return JSON.",
            user_payload={"task": "ping"},
            operation_name="helper_ping",
        )
    )

    assert captured["base_url"] == "https://helper-responses.example/v1"
    assert response.payload == {"answer": "ok"}
    assert response.raw_text == '{"answer":"ok"}'
    assert response.transport_style == "responses"
    assert response.model == "helper-model"
    assert client.call_trace[-1]["operation_name"] == "helper_ping"
    assert client.call_trace[-1]["transport_style"] == "responses"
    assert client.call_trace[-1]["model"] == "helper-model"
    assert client.call_trace[-1]["fallback_source"] is None


def test_helper_agent_client_invokes_chat_completions_and_batch(monkeypatch) -> None:
    monkeypatch.setattr(
        helper_agent_module,
        "build_openai_client",
        lambda **_kwargs: _FakeHelperClient(chat_text='{"answer":"ok"}'),
    )
    settings = Settings(
        _env_file=None,
        helper_gateway_base_url="https://helper.example/v1",
        helper_gateway_api_key="helper-key",
        helper_gateway_model="helper-model",
    )
    client = HelperAgentClient(settings=settings, transport_style="chat_completions")

    responses = client.invoke_batch(
        [
            HelperRequest(system_prompt="Return JSON.", user_payload={"task": "one"}, operation_name="helper_one"),
            HelperRequest(system_prompt="Return JSON.", user_payload={"task": "two"}, operation_name="helper_two"),
        ]
    )

    assert len(responses) == 2
    assert all(item.payload == {"answer": "ok"} for item in responses)
    assert all(item.transport_style == "chat_completions" for item in responses)
    assert len(client.call_trace) == 2
    assert {item["operation_name"] for item in client.call_trace} == {"helper_one", "helper_two"}


def test_shared_helper_provider_limiter_defaults() -> None:
    limiter = helper_agent_module.get_shared_helper_provider_limiter(
        base_url="https://helper.example/v1",
        model="helper-model",
    )

    assert limiter.max_concurrency == 20
    assert limiter.max_requests_per_minute == 120


def test_helper_agent_client_uses_minimum_timeout_floor() -> None:
    client = HelperAgentClient(
        settings=Settings(
            _env_file=None,
            helper_gateway_base_url="https://helper.example/v1",
            helper_gateway_api_key="helper-key",
            helper_gateway_model="helper-model",
            gateway_timeout_seconds_benchmark_driver=45,
        ),
        transport_style="chat_completions",
    )

    assert client.timeout_seconds == 60.0

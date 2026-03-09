from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from rpg_backend.config.settings import Settings
import rpg_backend.llm.factory as factory_module
from rpg_backend.llm.base import LLMProviderConfigError
from rpg_backend.llm.json_gateway import JsonGatewayError
from rpg_backend.llm.worker_client import WorkerClientError
from rpg_backend.llm.worker_provider import WorkerProvider


class _FakeWorkerClient:
    def __init__(self) -> None:
        self.payload = {"payload": {"ok": True}, "attempts": 1}

    async def json_object(self, **_kwargs):  # noqa: ANN003, ANN201
        return dict(self.payload)


def test_worker_provider_json_object_success() -> None:
    provider = WorkerProvider(
        worker_client=_FakeWorkerClient(),
        route_model="route-model",
        narration_model="narration-model",
        timeout_seconds=20.0,
        route_max_retries=3,
        narration_max_retries=1,
        route_temperature=0.1,
        narration_temperature=0.4,
    )

    result = asyncio.run(
        provider.invoke_json_object(
            system_prompt="sys",
            user_prompt='{"task":"test"}',
            model="route-model",
            temperature=0.1,
            max_retries=3,
            timeout_seconds=20.0,
        )
    )
    assert result.payload == {"ok": True}


def test_worker_provider_json_object_failure_maps_gateway_error() -> None:
    class _FailingClient(_FakeWorkerClient):
        async def json_object(self, **_kwargs):  # noqa: ANN003, ANN201
            raise WorkerClientError(
                error_code="llm_worker_unreachable",
                message="connection refused",
                retryable=True,
            )

    provider = WorkerProvider(
        worker_client=_FailingClient(),
        route_model="route-model",
        narration_model="narration-model",
        timeout_seconds=20.0,
        route_max_retries=3,
        narration_max_retries=1,
        route_temperature=0.1,
        narration_temperature=0.4,
    )

    with pytest.raises(JsonGatewayError):
        asyncio.run(
            provider.invoke_json_object(
                system_prompt="sys",
                user_prompt='{"task":"test"}',
                model="route-model",
                temperature=0.1,
                max_retries=3,
                timeout_seconds=20.0,
            )
        )


def test_factory_returns_worker_provider(monkeypatch) -> None:
    settings = SimpleNamespace(
        llm_openai_route_model="route-model",
        llm_openai_narration_model="narration-model",
        llm_openai_model="",
        llm_openai_timeout_seconds=20.0,
        llm_openai_route_max_retries=3,
        llm_openai_narration_max_retries=1,
        llm_openai_temperature_route=0.1,
        llm_openai_temperature_narration=0.4,
    )
    monkeypatch.setattr(factory_module, "get_settings", lambda: settings)
    monkeypatch.setattr(factory_module, "get_worker_client", lambda: _FakeWorkerClient())

    provider = factory_module.get_llm_provider()
    assert isinstance(provider, WorkerProvider)


def test_factory_missing_models_raises(monkeypatch) -> None:
    settings = SimpleNamespace(
        llm_openai_route_model="",
        llm_openai_narration_model="",
        llm_openai_model="",
        llm_openai_timeout_seconds=20.0,
        llm_openai_route_max_retries=3,
        llm_openai_narration_max_retries=1,
        llm_openai_temperature_route=0.1,
        llm_openai_temperature_narration=0.4,
    )
    monkeypatch.setattr(factory_module, "get_settings", lambda: settings)

    with pytest.raises(LLMProviderConfigError):
        factory_module.get_llm_provider()


def test_settings_no_longer_exposes_gateway_mode() -> None:
    assert "llm_gateway_mode" not in Settings.model_fields
    assert "llm_worker_route_max_inflight" not in Settings.model_fields
    assert "llm_worker_narration_max_inflight" not in Settings.model_fields
    assert "llm_worker_json_max_inflight" not in Settings.model_fields


def test_openai_provider_module_removed() -> None:
    assert not Path("rpg_backend/llm/openai_provider.py").exists()

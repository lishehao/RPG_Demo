from __future__ import annotations

import asyncio

import httpx

from rpg_backend.llm.worker_client import WorkerClient


class _FakeResponse:
    status_code = 200

    @staticmethod
    def json() -> dict[str, str]:
        return {"status": "ready"}


class _FakeAsyncClient:
    instances: list['_FakeAsyncClient'] = []

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.args = args
        self.kwargs = kwargs
        self.closed = False
        _FakeAsyncClient.instances.append(self)

    async def get(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return _FakeResponse()

    async def post(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return _FakeResponse()

    async def aclose(self) -> None:
        self.closed = True


def test_worker_client_recreates_async_client_across_event_loops(monkeypatch) -> None:
    monkeypatch.setattr(httpx, 'AsyncClient', _FakeAsyncClient)
    client = WorkerClient(
        base_url='http://127.0.0.1:8100',
        timeout_seconds=30.0,
        connect_timeout_seconds=5.0,
        max_connections=10,
        max_keepalive_connections=5,
        http2_enabled=False,
        internal_token='test-token',
    )

    first_client = None
    second_client = None

    async def _first_call() -> None:
        nonlocal first_client
        await client.probe_ready()
        assert client._client is not None
        first_client = client._client

    async def _second_call() -> None:
        nonlocal second_client
        await client.probe_ready()
        assert client._client is not None
        second_client = client._client

    asyncio.run(_first_call())
    asyncio.run(_second_call())

    assert first_client is not None
    assert second_client is not None
    assert first_client is not second_client
    assert len(_FakeAsyncClient.instances) == 2
    assert _FakeAsyncClient.instances[0].closed is True
    assert _FakeAsyncClient.instances[1].closed is False

from __future__ import annotations

import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.infrastructure.db.async_engine import async_engine
from rpg_backend.infrastructure.repositories.observability_async import aggregate_llm_call_health, save_llm_call_event


def test_aggregate_llm_call_health_excludes_legacy_local_gateway_mode() -> None:
    async def _run() -> dict:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            await save_llm_call_event(
                db,
                session_id=None,
                turn_index=1,
                stage="route",
                gateway_mode="local",
                model="model-local",
                success=True,
                error_code=None,
                duration_ms=10,
                request_id="rq-local",
            )
            await save_llm_call_event(
                db,
                session_id=None,
                turn_index=1,
                stage="route",
                gateway_mode="worker",
                model="model-worker",
                success=True,
                error_code=None,
                duration_ms=20,
                request_id="rq-worker",
            )
            await save_llm_call_event(
                db,
                session_id=None,
                turn_index=1,
                stage="narration",
                gateway_mode="unknown",
                model="model-unknown",
                success=False,
                error_code="narration_failed",
                duration_ms=30,
                request_id="rq-unknown",
            )

            return await aggregate_llm_call_health(db, window_seconds=300)

    aggregated = asyncio.run(_run())

    assert aggregated["total_calls"] == 2
    assert aggregated["failed_calls"] == 1
    assert set(aggregated["by_gateway_mode"].keys()) == {"worker", "unknown"}
    assert "local" not in aggregated["by_gateway_mode"]


def test_aggregate_llm_call_health_local_filter_returns_empty_result() -> None:
    async def _run() -> dict:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            await save_llm_call_event(
                db,
                session_id=None,
                turn_index=1,
                stage="route",
                gateway_mode="local",
                model="model-local",
                success=False,
                error_code="route_failed",
                duration_ms=10,
                request_id="rq-local",
            )
            return await aggregate_llm_call_health(
                db,
                window_seconds=300,
                gateway_mode="local",
            )

    aggregated = asyncio.run(_run())

    assert aggregated["total_calls"] == 0
    assert aggregated["failed_calls"] == 0
    assert aggregated["by_gateway_mode"] == {}

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import rpg_backend.llm_worker.services.quota_service as quota_module
from rpg_backend.infrastructure.db.async_engine import async_engine
from rpg_backend.llm_worker.services.quota_service import QuotaService
from rpg_backend.storage.models import LLMQuotaWindow


def _set_quota_settings(monkeypatch, *, default_rpm: int, default_tpm: int, model_limits_json: str = "{}") -> None:
    monkeypatch.setattr(
        quota_module,
        "get_settings",
        lambda: SimpleNamespace(
            llm_worker_default_rpm=default_rpm,
            llm_worker_default_tpm=default_tpm,
            llm_worker_model_limits_json=model_limits_json,
        ),
    )


def test_quota_service_reserve_hits_rpm_limit(monkeypatch) -> None:
    _set_quota_settings(monkeypatch, default_rpm=1, default_tpm=10_000)
    service = QuotaService()
    first = asyncio.run(service.reserve_async(model="qwen-plus-us", estimated_tokens=50))
    second = asyncio.run(service.reserve_async(model="qwen-plus-us", estimated_tokens=50))
    assert first.allowed is True
    assert second.allowed is False
    assert second.error_code == "worker_rate_limited"


def test_quota_service_reserve_hits_tpm_limit(monkeypatch) -> None:
    _set_quota_settings(monkeypatch, default_rpm=100, default_tpm=100)
    service = QuotaService()
    first = asyncio.run(service.reserve_async(model="qwen-flash-us", estimated_tokens=60))
    second = asyncio.run(service.reserve_async(model="qwen-flash-us", estimated_tokens=60))
    assert first.allowed is True
    assert second.allowed is False


def test_quota_service_reconcile_usage_updates_window(monkeypatch) -> None:
    _set_quota_settings(monkeypatch, default_rpm=100, default_tpm=10_000)
    service = QuotaService()
    reservation = asyncio.run(service.reserve_async(model="qwen-plus-us", estimated_tokens=120))
    assert reservation.allowed is True

    asyncio.run(
        service.reconcile_async(
            model=reservation.model,
            window_epoch_minute=reservation.window_epoch_minute,
            estimated_tokens=reservation.estimated_tokens,
            actual_total_tokens=90,
        )
    )

    async def _load_window() -> LLMQuotaWindow:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            return (
                await db.exec(
                    select(LLMQuotaWindow).where(
                        LLMQuotaWindow.model == reservation.model,
                        LLMQuotaWindow.window_epoch_minute == reservation.window_epoch_minute,
                    )
                )
            ).one()

    record = asyncio.run(_load_window())
    assert record.tpm_used == 90
    assert record.rpm_used == 1

    cleanup_count = asyncio.run(
        service.cleanup_async(
            keep_last_minutes=1,
            now=datetime.fromtimestamp((reservation.window_epoch_minute + 200) * 60, tz=timezone.utc),
        )
    )
    assert cleanup_count >= 1

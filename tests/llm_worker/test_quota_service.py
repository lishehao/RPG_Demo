from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session as DBSession
from sqlmodel import select

import rpg_backend.llm_worker.quota_service as quota_module
from rpg_backend.llm_worker.quota_service import QuotaService
from rpg_backend.storage.engine import engine
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
    first = service.reserve(model="qwen-plus-us", estimated_tokens=50)
    second = service.reserve(model="qwen-plus-us", estimated_tokens=50)
    assert first.allowed is True
    assert second.allowed is False
    assert second.error_code == "worker_rate_limited"


def test_quota_service_reserve_hits_tpm_limit(monkeypatch) -> None:
    _set_quota_settings(monkeypatch, default_rpm=100, default_tpm=100)
    service = QuotaService()
    first = service.reserve(model="qwen-flash-us", estimated_tokens=60)
    second = service.reserve(model="qwen-flash-us", estimated_tokens=60)
    assert first.allowed is True
    assert second.allowed is False


def test_quota_service_reconcile_usage_updates_window(monkeypatch) -> None:
    _set_quota_settings(monkeypatch, default_rpm=100, default_tpm=10_000)
    service = QuotaService()
    reservation = service.reserve(model="qwen-plus-us", estimated_tokens=120)
    assert reservation.allowed is True

    service.reconcile_usage(
        model=reservation.model,
        window_epoch_minute=reservation.window_epoch_minute,
        estimated_tokens=reservation.estimated_tokens,
        actual_total_tokens=90,
    )

    with DBSession(engine) as db:
        record = db.exec(
            select(LLMQuotaWindow).where(
                LLMQuotaWindow.model == reservation.model,
                LLMQuotaWindow.window_epoch_minute == reservation.window_epoch_minute,
            )
        ).one()
    assert record.tpm_used == 90
    assert record.rpm_used == 1

    cleanup_count = service.cleanup(
        keep_last_minutes=1,
        now=datetime.fromtimestamp((reservation.window_epoch_minute + 200) * 60, tz=timezone.utc),
    )
    assert cleanup_count >= 1

from __future__ import annotations

from sqlmodel import Session as DBSession

from rpg_backend.storage.engine import engine
from rpg_backend.storage.repositories.observability import aggregate_llm_call_health, save_llm_call_event


def test_aggregate_llm_call_health_excludes_legacy_local_gateway_mode() -> None:
    with DBSession(engine) as db:
        save_llm_call_event(
            db,
            session_id="s-local",
            turn_index=1,
            stage="route",
            gateway_mode="local",
            model="model-local",
            success=True,
            error_code=None,
            duration_ms=10,
            request_id="rq-local",
        )
        save_llm_call_event(
            db,
            session_id="s-worker",
            turn_index=1,
            stage="route",
            gateway_mode="worker",
            model="model-worker",
            success=True,
            error_code=None,
            duration_ms=20,
            request_id="rq-worker",
        )
        save_llm_call_event(
            db,
            session_id="s-unknown",
            turn_index=1,
            stage="narration",
            gateway_mode="unknown",
            model="model-unknown",
            success=False,
            error_code="narration_failed",
            duration_ms=30,
            request_id="rq-unknown",
        )

        aggregated = aggregate_llm_call_health(db, window_seconds=300)

    assert aggregated["total_calls"] == 2
    assert aggregated["failed_calls"] == 1
    assert set(aggregated["by_gateway_mode"].keys()) == {"worker", "unknown"}
    assert "local" not in aggregated["by_gateway_mode"]


def test_aggregate_llm_call_health_local_filter_returns_empty_result() -> None:
    with DBSession(engine) as db:
        save_llm_call_event(
            db,
            session_id="s-local",
            turn_index=1,
            stage="route",
            gateway_mode="local",
            model="model-local",
            success=False,
            error_code="route_failed",
            duration_ms=10,
            request_id="rq-local",
        )
        aggregated = aggregate_llm_call_health(
            db,
            window_seconds=300,
            gateway_mode="local",
        )

    assert aggregated["total_calls"] == 0
    assert aggregated["failed_calls"] == 0
    assert aggregated["by_gateway_mode"] == {}

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from tools import browser_product_smoke
from tools import fullstack_integration_gate


def test_parse_fullstack_integration_gate_args_defaults() -> None:
    config = fullstack_integration_gate.parse_args([])

    assert config.backend_host == fullstack_integration_gate.DEFAULT_BACKEND_HOST
    assert config.backend_port == fullstack_integration_gate.DEFAULT_BACKEND_PORT
    assert config.frontend_port_start == fullstack_integration_gate.DEFAULT_FRONTEND_PORT_START
    assert config.ui_language == "en"
    assert config.request_timeout_seconds == fullstack_integration_gate.DEFAULT_REQUEST_TIMEOUT_SECONDS
    assert config.author_timeout_seconds == fullstack_integration_gate.DEFAULT_AUTHOR_GATE_TIMEOUT_SECONDS
    assert config.max_play_turns == browser_product_smoke.DEFAULT_MAX_PLAY_TURNS
    assert config.headed is False
    assert config.run_play_issue_inspect is True


def test_run_fullstack_integration_gate_writes_combined_artifacts(monkeypatch, tmp_path) -> None:
    config = fullstack_integration_gate.parse_args(
        [
            "--output-dir",
            str(tmp_path),
        ]
    )

    @contextmanager
    def _fake_backend_server(_config, _run_dir):
        yield "http://127.0.0.1:8010"

    @contextmanager
    def _fake_frontend_server(_config, _run_dir, *, backend_base_url, frontend_port):
        assert backend_base_url == "http://127.0.0.1:8010"
        assert frontend_port == 4174
        yield "http://127.0.0.1:4174"

    monkeypatch.setattr(fullstack_integration_gate, "_now_stamp", lambda: "20260326_220000")
    monkeypatch.setattr(fullstack_integration_gate, "_pick_frontend_port", lambda host, start_port: 4174)
    monkeypatch.setattr(fullstack_integration_gate, "_managed_backend_server", _fake_backend_server)
    monkeypatch.setattr(fullstack_integration_gate, "_managed_frontend_server", _fake_frontend_server)
    monkeypatch.setattr(
        fullstack_integration_gate.http_product_smoke,
        "run_http_product_smoke",
        lambda smoke_config: {"ok": True, "language": smoke_config.language, "poll_timeout_seconds": smoke_config.poll_timeout_seconds},
    )
    monkeypatch.setattr(
        fullstack_integration_gate.browser_product_smoke,
        "run_browser_product_smoke",
        lambda browser_config: {
            "ok": True,
            "ui_language": browser_config.ui_language,
            "create": {"first_seed": "seed-a", "second_seed": "seed-b", "expected_npc_count": 4, "expected_beat_count": 3},
            "author": {"cast_card_count": 4, "template_chip_count": 3},
            "detail": {"story_title": "Archive Blackout"},
            "play": {
                "turns_run": 4,
                "completed": True,
                "transcript_scroll_probe": {"scroll_y": 1200.0, "target_top": 130.0},
                "archive_scroll_probe": {"scroll_y": 2400.0, "target_top": 132.0},
            },
        },
    )
    monkeypatch.setattr(
        fullstack_integration_gate.play_issue_inspect,
        "run_play_issue_inspect",
        lambda inspect_config: {
            "summary": {"passed": True},
            "story_id": inspect_config.story_id,
        },
    )
    monkeypatch.setattr(
        fullstack_integration_gate.play_issue_inspect,
        "write_artifacts",
        lambda inspect_config, payload: (
            (tmp_path / "fullstack_integration_gate_20260326_220000" / "play_issue_inspect.json"),
            (tmp_path / "fullstack_integration_gate_20260326_220000" / "play_issue_inspect.md"),
        ),
    )

    summary = fullstack_integration_gate.run_fullstack_integration_gate(config)

    run_dir = tmp_path / "fullstack_integration_gate_20260326_220000"
    assert summary["ok"] is True
    assert summary["backend"]["en"]["language"] == "en"
    assert summary["backend"]["zh"]["language"] == "zh"
    assert summary["backend"]["en"]["poll_timeout_seconds"] == fullstack_integration_gate.DEFAULT_AUTHOR_GATE_TIMEOUT_SECONDS
    assert summary["backend"]["zh"]["poll_timeout_seconds"] == fullstack_integration_gate.DEFAULT_AUTHOR_GATE_TIMEOUT_SECONDS
    assert summary["browser"]["detail"]["story_title"] == "Archive Blackout"
    assert summary["play_issue_inspect"]["summary"]["passed"] is True
    assert (run_dir / "backend_smoke_en.json").exists()
    assert (run_dir / "backend_smoke_zh.json").exists()
    assert (run_dir / "browser_smoke.json").exists()
    assert (run_dir / "browser_smoke.md").exists()
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "summary.md").exists()
    stored_summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert stored_summary["ok"] is True


def test_run_fullstack_integration_gate_persists_failure_summary(monkeypatch, tmp_path) -> None:
    config = fullstack_integration_gate.parse_args(
        [
            "--output-dir",
            str(tmp_path),
        ]
    )

    @contextmanager
    def _fake_backend_server(_config, _run_dir):
        yield "http://127.0.0.1:8010"

    @contextmanager
    def _fake_frontend_server(_config, _run_dir, *, backend_base_url, frontend_port):
        del backend_base_url, frontend_port
        yield "http://127.0.0.1:4174"

    monkeypatch.setattr(fullstack_integration_gate, "_now_stamp", lambda: "20260326_220500")
    monkeypatch.setattr(fullstack_integration_gate, "_pick_frontend_port", lambda host, start_port: 4174)
    monkeypatch.setattr(fullstack_integration_gate, "_managed_backend_server", _fake_backend_server)
    monkeypatch.setattr(fullstack_integration_gate, "_managed_frontend_server", _fake_frontend_server)
    monkeypatch.setattr(
        fullstack_integration_gate.http_product_smoke,
        "run_http_product_smoke",
        lambda smoke_config: {"ok": True, "language": smoke_config.language, "poll_timeout_seconds": smoke_config.poll_timeout_seconds},
    )
    monkeypatch.setattr(
        fullstack_integration_gate.play_issue_inspect,
        "run_play_issue_inspect",
        lambda inspect_config: {"summary": {"passed": True}, "story_id": inspect_config.story_id},
    )
    monkeypatch.setattr(
        fullstack_integration_gate.play_issue_inspect,
        "write_artifacts",
        lambda inspect_config, payload: (
            (tmp_path / "fullstack_integration_gate_20260326_220500" / "play_issue_inspect.json"),
            (tmp_path / "fullstack_integration_gate_20260326_220500" / "play_issue_inspect.md"),
        ),
    )

    def _raise_browser_failure(_browser_config):
        raise browser_product_smoke.BrowserProductSmokeFailure(
            "browser smoke failed",
            summary={"ok": False, "failed_step": "publish", "error_message": "browser smoke failed"},
        )

    monkeypatch.setattr(fullstack_integration_gate.browser_product_smoke, "run_browser_product_smoke", _raise_browser_failure)

    with pytest.raises(fullstack_integration_gate.FullstackIntegrationGateFailure) as exc_info:
        fullstack_integration_gate.run_fullstack_integration_gate(config)

    run_dir = tmp_path / "fullstack_integration_gate_20260326_220500"
    summary = exc_info.value.summary
    assert summary["ok"] is False
    assert summary["failed_stage"] == "browser_smoke"
    assert "browser smoke failed" in summary["error_message"]
    stored_summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert stored_summary["ok"] is False
    assert stored_summary["failed_stage"] == "browser_smoke"

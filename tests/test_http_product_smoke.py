from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tools import http_product_smoke


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def test_parse_http_product_smoke_args_defaults() -> None:
    config = http_product_smoke.parse_args([])

    assert config.base_url == "http://127.0.0.1:8000"
    assert config.language == "en"
    assert config.prompt_seed == http_product_smoke.DEFAULT_SEED
    assert config.first_turn_input == http_product_smoke.DEFAULT_TURN_INPUT
    assert config.copilot_message == http_product_smoke.DEFAULT_COPILOT_MESSAGE
    assert config.poll_timeout_seconds == http_product_smoke.DEFAULT_POLL_TIMEOUT_SECONDS
    assert config.include_copilot is False
    assert config.include_benchmark_diagnostics is False


def test_parse_http_product_smoke_args_zh_defaults_and_copilot_flag() -> None:
    config = http_product_smoke.parse_args(["--language", "zh", "--include-copilot"])

    assert config.language == "zh"
    assert config.prompt_seed == http_product_smoke.DEFAULT_ZH_SEED
    assert config.first_turn_input == http_product_smoke.DEFAULT_ZH_TURN_INPUT
    assert config.copilot_message == http_product_smoke.DEFAULT_ZH_COPILOT_MESSAGE
    assert config.include_copilot is True


def test_stage_timings_summary_handles_missing_payload() -> None:
    assert http_product_smoke._stage_timings_summary(None) == []
    assert http_product_smoke._stage_timings_summary({"stage_timings": []}) == []


def test_stage_timings_summary_extracts_stage_and_elapsed_ms() -> None:
    summary = http_product_smoke._stage_timings_summary(
        {
            "stage_timings": [
                {"stage": "running", "elapsed_ms": 120},
                {"stage": "beat_plan_ready", "elapsed_ms": 480},
            ]
        }
    )

    assert summary == [
        {"stage": "running", "elapsed_ms": 120},
        {"stage": "beat_plan_ready", "elapsed_ms": 480},
    ]


def test_smoke_preflight_requires_base_key_and_model(monkeypatch) -> None:
    config = http_product_smoke.parse_args([])
    monkeypatch.setattr(
        http_product_smoke,
        "_load_smoke_settings",
        lambda: SimpleNamespace(
            resolved_gateway_base_url=lambda: "",
            resolved_gateway_api_key=lambda: "key",
            resolved_gateway_model=lambda: "model",
            enable_benchmark_api=False,
            roster_enabled=False,
        ),
    )

    with pytest.raises(RuntimeError, match="APP_GATEWAY_BASE_URL"):
        http_product_smoke._smoke_preflight(config)


def test_smoke_preflight_requires_roster_embedding_config_when_roster_enabled(monkeypatch) -> None:
    config = http_product_smoke.parse_args([])
    monkeypatch.setattr(
        http_product_smoke,
        "_load_smoke_settings",
        lambda: SimpleNamespace(
            resolved_gateway_base_url=lambda: "https://example.invalid/v1",
            resolved_gateway_api_key=lambda: "key",
            resolved_gateway_model=lambda: "model",
            enable_benchmark_api=True,
            roster_enabled=True,
            resolved_gateway_embedding_base_url=lambda: "",
            resolved_gateway_embedding_api_key=lambda: "",
            resolved_gateway_embedding_model=lambda: "",
            roster_runtime_catalog_path="artifacts/character_roster_runtime.json",
        ),
    )

    with pytest.raises(RuntimeError, match="APP_GATEWAY_EMBEDDING_BASE_URL"):
        http_product_smoke._smoke_preflight(config)


def test_run_http_product_smoke_preserves_core_route_chain_without_copilot(monkeypatch) -> None:
    config = http_product_smoke.parse_args(["--base-url", "http://smoke.local"])
    seen: list[tuple[str, str, object | None]] = []

    monkeypatch.setattr(http_product_smoke.requests, "Session", lambda: _DummySession())
    monkeypatch.setattr(
        http_product_smoke,
        "_smoke_preflight",
        lambda _config: {"llm_configured": True, "benchmark_api_enabled": False, "roster_enabled": False},
    )
    monkeypatch.setattr(
        http_product_smoke,
        "_authenticate_session",
        lambda session, config: {"authenticated": True, "user": {"user_id": "usr-1"}},
    )
    monkeypatch.setattr(
        http_product_smoke,
        "_poll_author_job",
        lambda session, config, *, job_id: (
            {"status": "completed", "progress": {"stage": "completed"}},
            {"poll_count": 2, "poll_elapsed_seconds": 0.3},
        ),
    )

    def _fake_request_json(session, method, url, *, request_timeout_seconds, **kwargs):
        del session, request_timeout_seconds
        seen.append((method, url, kwargs.get("json")))
        payload_by_path = {
            ("GET", "http://smoke.local/health"): {"status": "ok"},
            ("POST", "http://smoke.local/author/story-previews"): {
                "preview_id": "preview-1",
                "language": "en",
                "story": {},
                "flashcards": [],
            },
            ("POST", "http://smoke.local/author/jobs"): {"job_id": "job-1"},
            ("GET", "http://smoke.local/author/jobs/job-1/result"): {
                "summary": {"language": "en"},
                "bundle": {},
            },
            ("POST", "http://smoke.local/author/jobs/job-1/publish"): {
                "story_id": "story-1",
                "title": "The Archive Blackout",
                "language": "en",
            },
            ("GET", "http://smoke.local/stories/story-1"): {
                "story": {"language": "en"},
                "presentation": {},
                "play_overview": {"runtime_profile": "archive_vote_play"},
            },
            ("POST", "http://smoke.local/play/sessions"): {
                "session_id": "session-1",
                "status": "active",
                "beat_title": "Opening Pressure",
                "language": "en",
            },
            ("POST", "http://smoke.local/play/sessions/session-1/turns"): {
                "status": "active",
                "turn_index": 1,
                "beat_title": "Opening Pressure",
                "language": "en",
                "narration": "You force the sealed ration rolls into the open before the council can deny them again.",
                "feedback": {},
                "suggested_actions": [{"label": "Press harder"}],
            },
            ("GET", "http://smoke.local/play/sessions/session-1/history"): {
                "language": "en",
                "entries": [{"speaker": "gm"}, {"speaker": "player"}, {"speaker": "gm"}],
            },
        }
        return payload_by_path[(method, url)], 0.1

    monkeypatch.setattr(http_product_smoke, "_request_json", _fake_request_json)

    summary = http_product_smoke.run_http_product_smoke(config)

    assert summary["ok"] is True
    assert summary["copilot"]["enabled"] is False
    assert all("/copilot/" not in url for _, url, _ in seen)
    assert [url.removeprefix("http://smoke.local") for _, url, _ in seen] == [
        "/health",
        "/author/story-previews",
        "/author/jobs",
        "/author/jobs/job-1/result",
        "/author/jobs/job-1/publish",
        "/stories/story-1",
        "/play/sessions",
        "/play/sessions/session-1/turns",
        "/play/sessions/session-1/history",
    ]


def test_run_http_product_smoke_includes_copilot_route_chain_and_artifact_fields(monkeypatch) -> None:
    config = http_product_smoke.parse_args(
        [
            "--base-url",
            "http://smoke.local",
            "--language",
            "zh",
            "--include-copilot",
            "--include-benchmark-diagnostics",
        ]
    )
    seen: list[tuple[str, str, object | None]] = []

    monkeypatch.setattr(http_product_smoke.requests, "Session", lambda: _DummySession())
    monkeypatch.setattr(
        http_product_smoke,
        "_smoke_preflight",
        lambda _config: {"llm_configured": True, "benchmark_api_enabled": True, "roster_enabled": False},
    )
    monkeypatch.setattr(
        http_product_smoke,
        "_authenticate_session",
        lambda session, config: {"authenticated": True, "user": {"user_id": "usr-1"}},
    )
    monkeypatch.setattr(
        http_product_smoke,
        "_poll_author_job",
        lambda session, config, *, job_id: (
            {"status": "completed", "progress": {"stage": "completed"}},
            {"poll_count": 2, "poll_elapsed_seconds": 0.3},
        ),
    )

    def _fake_request_json(session, method, url, *, request_timeout_seconds, **kwargs):
        del session, request_timeout_seconds
        payload = kwargs.get("json")
        seen.append((method, url, payload))
        payload_by_path = {
            ("GET", "http://smoke.local/health"): {"status": "ok"},
            ("POST", "http://smoke.local/author/story-previews"): {
                "preview_id": "preview-1",
                "language": "zh",
                "story": {},
                "flashcards": [],
            },
            ("POST", "http://smoke.local/author/jobs"): {"job_id": "job-1"},
            ("GET", "http://smoke.local/author/jobs/job-1/result"): {
                "summary": {"language": "zh"},
                "bundle": {},
            },
            ("GET", "http://smoke.local/author/jobs/job-1/editor-state"): None,
            ("POST", "http://smoke.local/author/jobs/job-1/copilot/sessions"): {"session_id": "copilot-session-1"},
            ("GET", "http://smoke.local/author/jobs/job-1/copilot/sessions/copilot-session-1"): {
                "session_id": "copilot-session-1",
                "rewrite_brief": {
                    "latest_instruction": "强化公开记录曝光与政治拉扯。",
                },
            },
            ("POST", "http://smoke.local/author/jobs/job-1/copilot/sessions/copilot-session-1/messages"): {
                "messages": [
                    {"role": "assistant", "content": "我可以把这次要求整理成一份全局重写方案。"},
                ]
            },
            ("POST", "http://smoke.local/author/jobs/job-1/copilot/sessions/copilot-session-1/proposal"): {
                "proposal_id": "proposal-1",
                "variant_label": "公开记录拉扯",
                "request_summary": "强化公开记录曝光与政治拉扯。",
                "affected_sections": ["story_frame", "rule_pack"],
            },
            ("POST", "http://smoke.local/author/jobs/job-1/copilot/proposals/proposal-1/preview"): {
                "editor_state": {
                    "language": "zh",
                    "revision": "rev-1",
                }
            },
            ("POST", "http://smoke.local/author/jobs/job-1/copilot/proposals/proposal-1/apply"): {
                "proposal": {"status": "applied"},
                "editor_state": {
                    "language": "zh",
                    "revision": "rev-2",
                },
            },
            ("POST", "http://smoke.local/author/jobs/job-1/copilot/proposals/proposal-1/undo"): {
                "proposal": {"status": "undone"},
                "editor_state": {
                    "language": "zh",
                    "revision": "rev-1",
                },
            },
            ("POST", "http://smoke.local/author/jobs/job-1/publish"): {
                "story_id": "story-1",
                "title": "档案停电夜",
                "language": "zh",
            },
            ("GET", "http://smoke.local/stories/story-1"): {
                "story": {"language": "zh"},
                "presentation": {},
                "play_overview": {"runtime_profile": "archive_vote_play"},
            },
            ("POST", "http://smoke.local/play/sessions"): {
                "session_id": "play-session-1",
                "status": "active",
                "beat_title": "第一轮公开对照",
                "language": "zh",
            },
            ("POST", "http://smoke.local/play/sessions/play-session-1/turns"): {
                "status": "active",
                "turn_index": 1,
                "beat_title": "第一轮公开对照",
                "language": "zh",
                "narration": "你当众摊开篡改过的配给名册，逼所有人解释差异。",
                "feedback": {},
                "suggested_actions": [{"label": "继续追问"}],
            },
            ("GET", "http://smoke.local/play/sessions/play-session-1/history"): {
                "language": "zh",
                "entries": [{"speaker": "gm"}, {"speaker": "player"}, {"speaker": "gm"}],
            },
        }
        if (method, url) == ("GET", "http://smoke.local/author/jobs/job-1/editor-state"):
            editor_state_calls = sum(1 for item in seen if item[:2] == (method, url))
            if editor_state_calls == 1:
                return (
                    {
                        "language": "zh",
                        "revision": "rev-1",
                        "copilot_view": {},
                        "play_profile_view": {
                            "runtime_profile": "archive_vote_play",
                            "closeout_profile": "record_exposure_closeout",
                            "max_turns": 4,
                        },
                    },
                    0.1,
                )
            if editor_state_calls == 2:
                return (
                    {
                        "language": "zh",
                        "revision": "rev-2",
                        "copilot_view": {"undo_proposal_id": "proposal-1"},
                        "play_profile_view": {
                            "runtime_profile": "archive_vote_play",
                            "closeout_profile": "record_exposure_closeout",
                            "max_turns": 4,
                        },
                    },
                    0.1,
                )
            return (
                {
                    "language": "zh",
                    "revision": "rev-1",
                    "copilot_view": {},
                    "play_profile_view": {
                        "runtime_profile": "archive_vote_play",
                        "closeout_profile": "record_exposure_closeout",
                        "max_turns": 4,
                    },
                },
                0.1,
            )
        return payload_by_path[(method, url)], 0.1

    monkeypatch.setattr(http_product_smoke, "_request_json", _fake_request_json)
    monkeypatch.setattr(
        http_product_smoke,
        "_optional_request_json",
        lambda session, method, url, *, request_timeout_seconds, **kwargs: (
            ({"stage_timings": [{"stage": "completed", "elapsed_ms": 100}]} if "author/jobs" in url else {"summary": {"turn_count": 1}}),
            0.1,
        ),
    )

    summary = http_product_smoke.run_http_product_smoke(config)

    assert summary["ok"] is True
    assert summary["copilot"]["enabled"] is True
    assert summary["copilot"]["session_id"] == "copilot-session-1"
    assert summary["copilot"]["proposal_id"] == "proposal-1"
    assert summary["copilot"]["variant_label"] == "公开记录拉扯"
    assert summary["copilot"]["affected_sections"] == ["story_frame", "rule_pack"]
    assert summary["copilot"]["preview_revision"] == "rev-1"
    assert summary["copilot"]["applied_revision"] == "rev-2"
    assert summary["copilot"]["revision_changed"] is True
    assert summary["copilot"]["undo_proposal_id"] == "proposal-1"
    assert summary["copilot"]["undo_revision"] == "rev-1"
    assert summary["copilot"]["undo_restored_revision"] is True
    assert summary["copilot"]["runtime_profile_preserved"] is True
    assert summary["copilot"]["closeout_profile_preserved"] is True
    assert summary["copilot"]["max_turns_preserved"] is True
    assert summary["copilot"]["runtime_profile_preserved_after_undo"] is True
    assert summary["copilot"]["closeout_profile_preserved_after_undo"] is True
    assert summary["copilot"]["max_turns_preserved_after_undo"] is True
    assert summary["contracts"]["preview_language_matches_request"] is True
    assert summary["contracts"]["editor_state_before_language_matches_request"] is True
    assert summary["contracts"]["editor_state_after_language_matches_request"] is True
    assert summary["contracts"]["editor_state_after_undo_language_matches_request"] is True
    assert summary["contracts"]["copilot_loaded_session_matches_created_session"] is True
    assert summary["contracts"]["copilot_loaded_session_has_rewrite_brief"] is True
    assert summary["contracts"]["copilot_undo_response_received"] is True
    assert summary["contracts"]["story_detail_language_matches_request"] is True
    assert summary["contracts"]["play_session_language_matches_request"] is True
    assert summary["contracts"]["turn_language_matches_request"] is True
    assert summary["contracts"]["history_language_matches_request"] is True
    assert summary["benchmark"]["author_diagnostics_available"] is True
    assert summary["benchmark"]["play_diagnostics_available"] is True
    assert [url.removeprefix("http://smoke.local") for _, url, _ in seen] == [
        "/health",
        "/author/story-previews",
        "/author/jobs",
        "/author/jobs/job-1/result",
        "/author/jobs/job-1/editor-state",
        "/author/jobs/job-1/copilot/sessions",
        "/author/jobs/job-1/copilot/sessions/copilot-session-1",
        "/author/jobs/job-1/copilot/sessions/copilot-session-1/messages",
        "/author/jobs/job-1/copilot/sessions/copilot-session-1/proposal",
        "/author/jobs/job-1/copilot/proposals/proposal-1/preview",
        "/author/jobs/job-1/copilot/proposals/proposal-1/apply",
        "/author/jobs/job-1/editor-state",
        "/author/jobs/job-1/copilot/proposals/proposal-1/undo",
        "/author/jobs/job-1/editor-state",
        "/author/jobs/job-1/publish",
        "/stories/story-1",
        "/play/sessions",
        "/play/sessions/play-session-1/turns",
        "/play/sessions/play-session-1/history",
    ]
    assert seen[1][2] == {"prompt_seed": http_product_smoke.DEFAULT_ZH_SEED, "language": "zh"}
    assert seen[2][2] == {
        "prompt_seed": http_product_smoke.DEFAULT_ZH_SEED,
        "preview_id": "preview-1",
        "language": "zh",
    }
    assert seen[7][2] == {"content": http_product_smoke.DEFAULT_ZH_COPILOT_MESSAGE}


def test_http_product_smoke_main_writes_partial_artifact_on_failure(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "smoke-failure.json"
    failure_summary = {
        "ok": False,
        "failed_step": "copilot_proposal",
        "error_message": "proposal failed",
        "error_code": "author_copilot_instruction_unsupported",
        "ids": {"job_id": "job-1"},
    }

    monkeypatch.setattr(
        http_product_smoke,
        "run_http_product_smoke",
        lambda config: (_ for _ in ()).throw(
            http_product_smoke.HttpProductSmokeFailure(
                "proposal failed",
                summary=failure_summary,
                error_code="author_copilot_instruction_unsupported",
            )
        ),
    )

    exit_code = http_product_smoke.main(["--output-path", str(output_path)])

    assert exit_code == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["failed_step"] == "copilot_proposal"
    assert payload["error_code"] == "author_copilot_instruction_unsupported"

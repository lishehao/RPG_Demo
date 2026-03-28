from __future__ import annotations

import json
from types import SimpleNamespace

from tools.play_benchmarks import live_api_playtest, play_issue_inspect


def test_run_play_issue_inspect_submits_exact_prompt_count_across_sessions(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(play_issue_inspect.live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        play_issue_inspect.live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: (
            {
                "story": {"story_id": story_id, "title": "公议协约"},
                "play_overview": {"max_turns": 10},
            },
            0.1,
        ),
    )

    session_ids = ["session-a", "session-b"]
    created_index = {"value": 0}
    turn_counts: dict[str, int] = {}
    latest_trace: dict[str, dict[str, object]] = {}

    def _fake_create_play_session(session, base_url, story_id):  # noqa: ANN001
        session_id = session_ids[created_index["value"]]
        created_index["value"] += 1
        turn_counts[session_id] = 0
        latest_trace[session_id] = {}
        return (
            {
                "session_id": session_id,
                "story_id": story_id,
                "status": "active",
                "turn_index": 0,
                "beat_title": "记录裂口",
                "narration": "你眼下先得把会议室里的记录裂口顶到台面上。",
                "suggested_actions": [
                    {"label": "逼她开口", "prompt": "继续逼她把剩下的记录链条说完。"},
                    {"label": "压住会场", "prompt": "先压住会场，不让人把档案带走。"},
                ],
                "npc_visuals": [{"name": "佩拉·多恩"}],
                "state_bars": [{"label": "系统完整性"}],
                "feedback": {"last_turn_consequences": ["记录链条已经开始松动。"]},
            },
            0.2,
        )

    def _fake_submit_play_turn(session, base_url, session_id, input_text):  # noqa: ANN001
        turn_counts[session_id] += 1
        turn_index = turn_counts[session_id]
        is_bad_turn = session_id == "session-a" and turn_index == 3
        narration = (
            "You keep the scene moving with 佩拉·多恩 as the room reacts in real time. 你把责任链硬生生拖回众人面前。"
            if is_bad_turn
            else "你把责任链重新拖回台面上，逼得会场没法继续装作没看见。"
        )
        latest_trace[session_id] = {
            "render_source": "llm_repair" if is_bad_turn else "llm",
            "render_failure_reason": "meta_wrapper_echo" if is_bad_turn else None,
            "interpret_failure_reason": None,
        }
        completed = (session_id == "session-a" and turn_index >= 6) or (session_id == "session-b" and turn_index >= 4)
        return (
            {
                "session_id": session_id,
                "story_id": "story-zh",
                "status": "completed" if completed else "active",
                "turn_index": turn_index,
                "beat_title": "记录裂口",
                "narration": narration,
                "suggested_actions": [
                    {"label": "逼她开口", "prompt": "继续逼她把剩下的记录链条说完。"},
                    {"label": "压住会场", "prompt": "先压住会场，不让人把档案带走。"},
                ],
                "npc_visuals": [{"name": "佩拉·多恩"}],
                "state_bars": [{"label": "系统完整性"}],
                "feedback": {"last_turn_consequences": ["记录链条已经开始松动。"]},
            },
            0.3,
        )

    monkeypatch.setattr(play_issue_inspect.live_api_playtest, "_create_play_session", _fake_create_play_session)
    monkeypatch.setattr(play_issue_inspect.live_api_playtest, "_submit_play_turn", _fake_submit_play_turn)
    monkeypatch.setattr(
        play_issue_inspect.live_api_playtest,
        "_get_play_diagnostics",
        lambda session, base_url, session_id: (
            {
                "turn_traces": [latest_trace[session_id]],
                "summary": {
                    "render_source_distribution": {str(latest_trace[session_id].get("render_source") or "llm"): 1},
                    "render_failure_reason_distribution": (
                        {"meta_wrapper_echo": 1} if latest_trace[session_id].get("render_failure_reason") else {}
                    ),
                    "interpret_failure_reason_distribution": {},
                },
            },
            0.1,
        ),
    )
    monkeypatch.setattr(play_issue_inspect, "_run_helper_issue_analysis", lambda **_kwargs: {"status": "disabled"})

    payload = play_issue_inspect.run_play_issue_inspect(
        play_issue_inspect.PlayIssueInspectConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            launch_server=False,
            story_id="story-zh",
            language="zh",
            prompt_count=10,
            seed=7,
            label="inspect-test",
            session_ttl_seconds=3600,
            target_duration_minutes=25,
            helper_analysis_enabled=False,
        )
    )

    assert payload["summary"]["turns_submitted"] == 10
    assert payload["summary"]["sessions_created"] == 2
    assert payload["summary"]["persistent_language_contamination_turn_count"] == 1
    assert payload["summary"]["render_failure_reason_distribution"] == {"meta_wrapper_echo": 1}
    assert payload["summary"]["passed"] is False
    assert payload["helper_analysis"]["status"] == "disabled"


def test_live_api_playtest_main_delegates_to_play_issue_inspect(monkeypatch, tmp_path, capsys) -> None:
    observed: dict[str, object] = {}

    def _fake_run(config):  # noqa: ANN001
        observed["story_id"] = config.story_id
        observed["prompt_count"] = config.prompt_count
        observed["language"] = config.language
        return {"summary": {"passed": True}}

    def _fake_write(config, payload):  # noqa: ANN001
        json_path = tmp_path / "inspect.json"
        md_path = tmp_path / "inspect.md"
        json_path.write_text(json.dumps(payload), encoding="utf-8")
        md_path.write_text("# note\n", encoding="utf-8")
        return json_path, md_path

    monkeypatch.setattr(play_issue_inspect, "run_play_issue_inspect", _fake_run)
    monkeypatch.setattr(play_issue_inspect, "write_artifacts", _fake_write)

    exit_code = live_api_playtest.main(
        [
            "--play-issue-inspect",
            "--output-dir",
            str(tmp_path),
            "--inspect-story-id",
            "story-live",
            "--inspect-language",
            "zh",
            "--inspect-prompt-count",
            "10",
        ]
    )

    captured = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 0
    assert observed == {"story_id": "story-live", "prompt_count": 10, "language": "zh"}
    assert captured["passed"] is True


def test_run_play_issue_inspect_attaches_helper_triage_to_issue_turns(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(play_issue_inspect.live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        play_issue_inspect.live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: (
            {
                "story": {"story_id": story_id, "title": "Ledger Pressure"},
                "play_overview": {"max_turns": 10},
            },
            0.1,
        ),
    )

    session_ids = ["session-a"]
    turn_counts: dict[str, int] = {}
    latest_trace: dict[str, dict[str, object]] = {}

    def _fake_create_play_session(session, base_url, story_id):  # noqa: ANN001
        session_id = session_ids[0]
        turn_counts[session_id] = 0
        latest_trace[session_id] = {}
        return (
            {
                "session_id": session_id,
                "story_id": story_id,
                "status": "active",
                "turn_index": 0,
                "beat_title": "The Ledger",
                "narration": "You arrive with the sealed record.",
                "suggested_actions": [],
                "npc_visuals": [{"name": "Pera Dorn"}],
                "state_bars": [{"label": "System Integrity"}],
                "feedback": {"last_turn_consequences": ["The record chain is slipping."]},
            },
            0.2,
        )

    def _fake_submit_play_turn(session, base_url, session_id, input_text):  # noqa: ANN001
        turn_counts[session_id] += 1
        turn_index = turn_counts[session_id]
        latest_trace[session_id] = {
            "render_source": "llm_repair",
            "render_failure_reason": "play_llm_invalid_json",
            "interpret_failure_reason": None,
        }
        return (
            {
                "session_id": session_id,
                "story_id": "story-en",
                "status": "completed",
                "turn_index": turn_index,
                "beat_title": "The Ledger",
                "narration": "You force the room to confront the damaged record.",
                "suggested_actions": [],
                "npc_visuals": [{"name": "Pera Dorn"}],
                "state_bars": [{"label": "System Integrity"}],
                "feedback": {"last_turn_consequences": ["The record chain is slipping."]},
            },
            0.3,
        )

    class _FakeHelperAgentClient:
        def __init__(self, *, transport_style="chat_completions", **_kwargs):
            self.transport_style = transport_style
            self.model = "helper-test-model"

        def invoke(self, request):  # noqa: ANN001
            del request
            return SimpleNamespace(
                payload={
                    "cluster_label": "render_json_contract",
                    "priority": "p1",
                    "failure_surface": "render",
                    "rationale": "Renderer JSON broke and needed repair.",
                    "next_probe": "Capture raw repair payload.",
                },
                model=self.model,
                transport_style=self.transport_style,
                elapsed_ms=12,
                fallback_source=None,
                operation_name="helper_triage_test",
            )

    monkeypatch.setattr(play_issue_inspect.live_api_playtest, "_create_play_session", _fake_create_play_session)
    monkeypatch.setattr(play_issue_inspect.live_api_playtest, "_submit_play_turn", _fake_submit_play_turn)
    monkeypatch.setattr(
        play_issue_inspect.live_api_playtest,
        "_get_play_diagnostics",
        lambda session, base_url, session_id: (
            {
                "turn_traces": [latest_trace[session_id]],
                "summary": {
                    "render_source_distribution": {"llm_repair": 1},
                    "render_failure_reason_distribution": {"play_llm_invalid_json": 1},
                    "interpret_failure_reason_distribution": {},
                },
            },
            0.1,
        ),
    )
    monkeypatch.setattr(play_issue_inspect, "helper_gateway_config_available", lambda: True)
    monkeypatch.setattr(play_issue_inspect, "HelperAgentClient", _FakeHelperAgentClient)

    payload = play_issue_inspect.run_play_issue_inspect(
        play_issue_inspect.PlayIssueInspectConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            launch_server=False,
            story_id="story-en",
            language="en",
            prompt_count=1,
            seed=7,
            label="inspect-helper-test",
            session_ttl_seconds=3600,
            target_duration_minutes=25,
            helper_analysis_enabled=True,
            helper_analysis_max_turns=4,
            helper_analysis_concurrency=2,
        )
    )

    helper_analysis = payload["helper_analysis"]
    assert helper_analysis["status"] == "completed"
    assert helper_analysis["analyzed_turn_count"] == 1
    assert helper_analysis["cluster_distribution"] == {"render_json_contract": 1}
    assert helper_analysis["priority_distribution"] == {"p1": 1}
    first_turn = payload["sessions"][0]["turns"][0]
    assert first_turn["helper_triage"]["cluster_label"] == "render_json_contract"
    assert first_turn["helper_triage"]["priority"] == "p1"

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from tools.play_benchmarks import live_stability_matrix
from tools.play_benchmarks.story_seed_factory import all_story_seed_bucket_ids


def test_expected_lane_maps_representative_durations() -> None:
    assert live_stability_matrix._expected_lane(10) == {
        "target_duration_minutes": 10,
        "expected_turn_count": 4,
        "expected_beat_count": 2,
        "expected_cast_count": 3,
        "branch_budget": "low",
    }
    assert live_stability_matrix._expected_lane(17) == {
        "target_duration_minutes": 17,
        "expected_turn_count": 8,
        "expected_beat_count": 4,
        "expected_cast_count": 4,
        "branch_budget": "medium",
    }
    assert live_stability_matrix._expected_lane(25) == {
        "target_duration_minutes": 25,
        "expected_turn_count": 10,
        "expected_beat_count": 5,
        "expected_cast_count": 5,
        "branch_budget": "high",
    }


def test_default_bucket_ids_cover_all_seed_buckets() -> None:
    assert live_stability_matrix._default_bucket_ids() == all_story_seed_bucket_ids()


def test_expected_strategy_family_matches_bucket_mapping() -> None:
    assert live_stability_matrix._expected_strategy_family_for_bucket("harbor_quarantine") == {
        "family": "harbor_quarantine_*",
        "story_frame_strategy": "harbor_quarantine_story",
        "cast_strategy": "harbor_quarantine_cast",
        "beat_plan_strategy": "harbor_quarantine_compile",
    }


def test_call_with_single_retry_retries_once_on_transient_error() -> None:
    attempts = {"count": 0}
    retry_state = {"used": False}

    def _flaky():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("Request timed out.")
        return "ok"

    result = live_stability_matrix._call_with_single_retry(retry_state=retry_state, fn=_flaky)

    assert result == "ok"
    assert attempts["count"] == 2
    assert retry_state["used"] is True


def test_build_matrix_summary_counts_25_minute_full_live_cells_only() -> None:
    cells = [
        {
            "bucket_id": "legitimacy_warning",
            "target_duration_minutes": 10,
            "preview_passed": True,
            "author_publish_passed": True,
            "turn_probe_passed": True,
            "full_live_passed": None,
            "preview_elapsed_seconds": 5.0,
            "author_total_elapsed_seconds": 12.0,
            "probes": [{"propose_turn_elapsed_seconds": 8.0}],
            "failure_stage": None,
            "observations": {"preview": {"strategy_family_consistent": True}},
        },
        {
            "bucket_id": "harbor_quarantine",
            "target_duration_minutes": 17,
            "preview_passed": True,
            "author_publish_passed": False,
            "turn_probe_passed": False,
            "full_live_passed": None,
            "preview_elapsed_seconds": 6.0,
            "author_total_elapsed_seconds": 18.0,
            "probes": [],
            "failure_stage": "author_job",
            "observations": {
                "preview": {
                    "strategy_family_consistent": False,
                    "bucket_strategy_expected": "harbor_quarantine_*",
                    "strategies.story_frame_strategy": "harbor_quarantine_story",
                    "strategies.cast_strategy": "bridge_ration_cast",
                    "strategies.beat_plan_strategy": "bridge_ration_compile",
                }
            },
        },
        {
            "bucket_id": "archive_vote_record",
            "target_duration_minutes": 25,
            "preview_passed": True,
            "author_publish_passed": True,
            "turn_probe_passed": True,
            "full_live_passed": True,
            "preview_elapsed_seconds": 7.0,
            "author_total_elapsed_seconds": 40.0,
            "probes": [{"propose_turn_elapsed_seconds": 32.0}],
            "failure_stage": None,
            "observations": {"preview": {"strategy_family_consistent": True}},
        },
    ]

    summary = live_stability_matrix._build_matrix_summary(cells)

    assert summary["preview_pass_rate"] == 1.0
    assert summary["author_publish_pass_rate"] == 0.667
    assert summary["turn_probe_pass_rate"] == 0.667
    assert summary["strategy_consistency_pass_rate"] == 0.667
    assert summary["full_live_pass_rate"] == 1.0
    assert summary["core_gate_passed"] is False
    assert summary["full_live_gate_passed"] is True
    assert summary["cells_passed"] == 2
    assert summary["cells_total"] == 3
    assert summary["core_cells_passed"] == 2
    assert summary["full_live_cells_passed"] == 1
    assert summary["full_live_cells_total"] == 1
    assert summary["max_observed_preview_elapsed_seconds"] == 7.0
    assert summary["max_observed_author_elapsed_seconds"] == 40.0
    assert summary["max_observed_turn_proposal_elapsed_seconds"] == 32.0
    assert summary["failure_stage_distribution"]["passed"] == 2
    assert summary["failure_stage_distribution"]["author_job"] == 1
    assert summary["bucket_pass_matrix"]["archive_vote_record"] is True
    assert summary["bucket_pass_matrix"]["harbor_quarantine"] is False
    assert summary["duration_pass_matrix"]["25"] is True
    assert summary["duration_pass_matrix"]["17"] is False
    assert summary["strategy_drift_count"] == 1
    assert summary["strategy_drift_cells"][0]["bucket_id"] == "harbor_quarantine"
    assert summary["blocking_cells"][0]["bucket_id"] == "harbor_quarantine"


def test_build_matrix_summary_distinguishes_core_gate_from_full_live_gate() -> None:
    cells = [
        {
            "bucket_id": "legitimacy_warning",
            "seed_slug": "legitimacy-warning",
            "target_duration_minutes": 10,
            "preview_passed": True,
            "author_publish_passed": True,
            "turn_probe_passed": True,
            "full_live_passed": None,
            "failure_stage": None,
            "error": None,
            "first_error": None,
            "route": None,
            "operation": None,
            "persona_id": None,
            "turn_index": None,
            "story_frame_strategy": "warning_record_story",
            "cast_strategy": "warning_record_cast",
            "beat_plan_strategy": "warning_record_compile",
            "selected_roster_templates": [],
            "story_instance_materialized_count": 1,
            "story_instance_fallback_count": 0,
            "gender_lock_violation_count": 0,
            "preview_elapsed_seconds": 8.0,
            "author_total_elapsed_seconds": 20.0,
            "probes": [{"propose_turn_elapsed_seconds": 9.0}],
            "observations": {"preview": {"strategy_family_consistent": True}},
        },
        {
            "bucket_id": "legitimacy_warning",
            "seed_slug": "legitimacy-warning",
            "target_duration_minutes": 25,
            "preview_passed": True,
            "author_publish_passed": True,
            "turn_probe_passed": True,
            "full_live_passed": False,
            "failure_stage": "full_live",
            "error": "POST http://127.0.0.1:8010/play/sessions/abc/turns: boom",
            "first_error": "POST http://127.0.0.1:8010/play/sessions/abc/turns: boom",
            "route": "/play/sessions/{id}/turns",
            "operation": "POST /play/sessions/{id}/turns",
            "persona_id": "assertive_operator",
            "turn_index": 1,
            "story_frame_strategy": "warning_record_story",
            "cast_strategy": "warning_record_cast",
            "beat_plan_strategy": "warning_record_compile",
            "selected_roster_templates": [],
            "story_instance_materialized_count": 1,
            "story_instance_fallback_count": 0,
            "gender_lock_violation_count": 0,
            "preview_elapsed_seconds": 9.0,
            "author_total_elapsed_seconds": 24.0,
            "probes": [{"propose_turn_elapsed_seconds": 10.0}],
            "observations": {"preview": {"strategy_family_consistent": True}},
        },
    ]

    summary = live_stability_matrix._build_matrix_summary(cells)

    assert summary["core_gate_passed"] is True
    assert summary["full_live_gate_passed"] is False
    assert summary["passed"] is False
    assert summary["blocking_cells"][0]["route"] == "/play/sessions/{id}/turns"
    assert summary["blocking_cells"][0]["turn_index"] == 1


def test_run_live_stability_matrix_enumerates_buckets_and_durations(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, int]] = []

    @contextmanager
    def _no_server(*_args, **_kwargs):
        yield

    def _fake_run_cell(*, base_url: str, generated_seed, target_duration_minutes: int):  # noqa: ANN001
        del base_url
        calls.append((generated_seed.bucket_id, target_duration_minutes))
        return {
            "bucket_id": generated_seed.bucket_id,
            "target_duration_minutes": target_duration_minutes,
            "preview_passed": True,
            "author_publish_passed": True,
            "turn_probe_passed": True,
            "full_live_passed": True if target_duration_minutes == 25 else None,
            "failure_stage": None,
            "error": None,
            "preview_elapsed_seconds": 9.0,
            "author_total_elapsed_seconds": 20.0,
            "probes": [{"propose_turn_elapsed_seconds": 12.0}],
            "observations": {"preview": {"strategy_family_consistent": True}},
        }

    monkeypatch.setattr(live_stability_matrix.live_api_playtest, "_managed_server", _no_server)
    monkeypatch.setattr(live_stability_matrix, "_run_preflight", lambda _config: {"passed": True})
    monkeypatch.setattr(
        live_stability_matrix.live_api_playtest,
        "run_stage1_spark_smoke",
        lambda _config: {"summary": {"passed": True}},
    )
    monkeypatch.setattr(live_stability_matrix, "_run_matrix_cell", _fake_run_cell)

    payload = live_stability_matrix.run_live_stability_matrix(
        live_stability_matrix.LiveStabilityMatrixConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            label="matrix-test",
            launch_server=False,
            durations=(10, 17, 25),
            bucket_ids=("archive_vote_record", "harbor_quarantine"),
        )
    )

    assert len(calls) == 6
    assert calls == [
        ("archive_vote_record", 10),
        ("archive_vote_record", 17),
        ("archive_vote_record", 25),
        ("harbor_quarantine", 10),
        ("harbor_quarantine", 17),
        ("harbor_quarantine", 25),
    ]
    assert payload["summary"]["cells_total"] == 6
    assert payload["summary"]["cells_passed"] == 6
    assert payload["summary"]["preflight_passed"] is True
    assert payload["summary"]["stage1_smoke_passed"] is True
    assert payload["summary"]["bucket_pass_matrix"]["archive_vote_record"] is True
    assert payload["summary"]["duration_pass_matrix"]["25"] is True


def test_run_live_stability_matrix_short_circuits_when_stage1_smoke_fails(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, int]] = []

    @contextmanager
    def _no_server(*_args, **_kwargs):
        yield

    def _fake_run_cell(*, base_url: str, generated_seed, target_duration_minutes: int):  # noqa: ANN001
        del base_url, generated_seed, target_duration_minutes
        calls.append(("unexpected", 0))
        return {}

    monkeypatch.setattr(live_stability_matrix.live_api_playtest, "_managed_server", _no_server)
    monkeypatch.setattr(live_stability_matrix, "_run_preflight", lambda _config: {"passed": True})
    monkeypatch.setattr(
        live_stability_matrix.live_api_playtest,
        "run_stage1_spark_smoke",
        lambda _config: {"summary": {"passed": False, "languages_passed": 1, "languages_total": 2}},
    )
    monkeypatch.setattr(live_stability_matrix, "_run_matrix_cell", _fake_run_cell)

    payload = live_stability_matrix.run_live_stability_matrix(
        live_stability_matrix.LiveStabilityMatrixConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            label="matrix-stage1-fail",
            launch_server=False,
            durations=(10, 17, 25),
            bucket_ids=("archive_vote_record",),
        )
    )

    assert calls == []
    assert payload["cells"] == []
    assert payload["summary"]["preflight_passed"] is True
    assert payload["summary"]["stage1_smoke_passed"] is False
    assert payload["summary"]["passed"] is False

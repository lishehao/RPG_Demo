from __future__ import annotations

from pathlib import Path

from tools.play_benchmarks import live_stability_aggregate


def test_aggregate_payloads_recomputes_summary() -> None:
    payloads = [
        {
            "base_url": "http://127.0.0.1:8010",
            "bucket_ids": ["harbor_quarantine"],
            "durations": [10, 17, 25],
            "cells": [
                {
                    "bucket_id": "harbor_quarantine",
                    "target_duration_minutes": 10,
                    "preview_passed": True,
                    "author_publish_passed": True,
                    "turn_probe_passed": True,
                    "full_live_passed": None,
                    "preview_elapsed_seconds": 10.0,
                    "author_total_elapsed_seconds": 20.0,
                    "probes": [{"propose_turn_elapsed_seconds": 11.0}],
                    "failure_stage": None,
                    "observations": {"preview": {"strategy_family_consistent": True}},
                }
            ],
        },
        {
            "base_url": "http://127.0.0.1:8010",
            "bucket_ids": ["archive_vote_record"],
            "durations": [25],
            "cells": [
                {
                    "bucket_id": "archive_vote_record",
                    "target_duration_minutes": 25,
                    "preview_passed": True,
                    "author_publish_passed": True,
                    "turn_probe_passed": True,
                    "full_live_passed": True,
                    "preview_elapsed_seconds": 30.0,
                    "author_total_elapsed_seconds": 60.0,
                    "probes": [{"propose_turn_elapsed_seconds": 22.0}],
                    "failure_stage": None,
                    "observations": {"preview": {"strategy_family_consistent": True}},
                }
            ],
        },
    ]

    aggregate = live_stability_aggregate.aggregate_payloads(payloads, label="agg")

    assert aggregate["bucket_ids"] == ["archive_vote_record", "harbor_quarantine"]
    assert aggregate["durations"] == [10, 17, 25]
    assert aggregate["summary"]["cells_total"] == 2
    assert aggregate["summary"]["cells_passed"] == 2
    assert aggregate["summary"]["preflight_passed"] is True
    assert aggregate["summary"]["stage1_smoke_passed"] is True
    assert aggregate["summary"]["bucket_pass_matrix"]["harbor_quarantine"] is True
    assert aggregate["summary"]["duration_pass_matrix"]["25"] is True


def test_write_artifacts_outputs_markdown(tmp_path: Path) -> None:
    payload = {
        "base_url": "http://127.0.0.1:8010",
        "bucket_ids": ["harbor_quarantine"],
        "durations": [10],
        "cells": [],
        "summary": {
            "passed": True,
            "cells_passed": 1,
            "cells_total": 1,
            "preview_pass_rate": 1.0,
            "author_publish_pass_rate": 1.0,
            "turn_probe_pass_rate": 1.0,
            "strategy_consistency_pass_rate": 1.0,
            "full_live_pass_rate": 0.0,
            "max_observed_preview_elapsed_seconds": 24.0,
            "max_observed_author_elapsed_seconds": 180.0,
            "max_observed_turn_proposal_elapsed_seconds": 40.0,
            "failure_stage_distribution": {"passed": 1},
            "bucket_pass_matrix": {"harbor_quarantine": True},
            "duration_pass_matrix": {"10": True},
            "strategy_drift_count": 0,
            "strategy_drift_cells": [],
        },
    }

    _json_path, md_path = live_stability_aggregate.write_artifacts(tmp_path, "agg-test", payload)
    markdown = md_path.read_text()

    assert "Live Stability Aggregate" in markdown
    assert "Core gate passed" in markdown
    assert "Full-live gate passed" in markdown
    assert "Strategy consistency pass rate" in markdown
    assert "Blocking Cells" in markdown
    assert "Bucket Pass Matrix" in markdown

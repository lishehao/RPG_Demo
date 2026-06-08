from __future__ import annotations

import json
from pathlib import Path

from tools.rpg_eval.tiny_stories_reliability_harness import (
    REQUIRED_CASES,
    REQUIRED_FAILURE_CATEGORIES,
    GOLD_SET_PATH,
    run_protocol_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def test_tiny_stories_reliability_gold_set_covers_required_product_cases() -> None:
    payload = json.loads(GOLD_SET_PATH.read_text())
    case_ids = {case["case_id"] for case in payload["cases"]}
    taxonomy = set(payload["failure_taxonomy"])

    assert REQUIRED_CASES.issubset(case_ids)
    assert REQUIRED_FAILURE_CATEGORIES.issubset(taxonomy)
    assert len(payload["cases"]) >= 7
    assert "high_drama_awards_supported" in case_ids
    high_drama = next(case for case in payload["cases"] if case["case_id"] == "high_drama_awards_supported")
    assert "there_is_no_gore" in high_drama["expected"]["forbidden_entities"]
    assert "opening_reaches_play" in high_drama["expected"]


def test_reliability_harness_emits_protocol_summary(tmp_path) -> None:
    output = tmp_path / "summary.json"
    summary = run_protocol_contract(output)

    assert output.exists()
    assert summary["schema_version"] == "tiny_stories_reliability_protocol_summary.v1"
    assert summary["status"] == "pass"
    assert summary["case_count"] >= 7
    assert summary["trajectory_judge"]["schema_version"] == "trajectory_judge.v1"
    assert summary["trajectory_judge"]["status"] in {"pass", "warn"}


def test_evaluation_docs_name_reviewer_only_boundary() -> None:
    docs = (ROOT / "docs/tiny-stories-evaluation-observability-proof.md").read_text()

    assert "reviewer-only evidence path" in docs
    assert "narrative_llm_call_events" in docs
    assert "normal player UI" in docs
    assert "do not call the score a validated academic metric" in docs

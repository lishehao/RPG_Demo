from __future__ import annotations

import json
from pathlib import Path

from tools.rpg_eval.tiny_stories_reliability_harness import (
    REQUIRED_CASES,
    REQUIRED_FAILURE_CATEGORIES,
    REQUIRED_HEALTH_CONFIG,
    REQUIRED_LIVE_OPERATIONS,
    GOLD_SET_PATH,
    _live_operation_failures,
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


def test_live_acceptance_contract_requires_core_live_operations() -> None:
    assert {
        "create.story_butler_turn",
        "narrative.story_brief",
        "narrative.opening",
        "narrative.advance_turn",
    }.issubset(REQUIRED_LIVE_OPERATIONS)
    assert {
        "text_llm",
        "create_story_butler",
        "story_brief",
        "opening",
        "play_turns",
    }.issubset(REQUIRED_HEALTH_CONFIG)


def test_live_operation_validation_rejects_fallback_rows() -> None:
    rows = [
        {
            "operation": "create.story_butler_turn",
            "status": "success",
            "source_label": "live",
            "fallback_reason": None,
        },
        {
            "operation": "narrative.story_brief",
            "status": "success",
            "source_label": "live",
            "fallback_reason": None,
        },
        {
            "operation": "narrative.opening",
            "status": "fallback_used",
            "source_label": "deterministic_fallback",
            "fallback_reason": "live_invalid_response",
        },
        {
            "operation": "narrative.advance_turn",
            "status": "success",
            "source_label": "live_repaired",
            "fallback_reason": None,
        },
    ]

    failures = _live_operation_failures(rows)

    assert failures
    assert failures[0]["stage"] == "narrative.opening"
    assert failures[0]["category"] == "provider"


def test_opening_generation_uses_compact_live_prompt_for_eval_gate() -> None:
    engine = (ROOT / "rpg_backend/narrative/engine.py").read_text()
    opening_block = engine[engine.index("def _generate_opening_once") : engine.index("_OPENING_PASSAGE_KEY_ALIASES")]

    assert "_OPENING_COMPACT_SYSTEM_PROMPT" in opening_block
    assert "max_output_tokens=1800" in opening_block
    assert "max_output_tokens=2500" not in opening_block
    assert "The runtime can deepen relationships during later turns." in engine
    assert "Optional arrays should stay empty or contain one item" in engine


def test_evaluation_docs_name_reviewer_only_boundary() -> None:
    docs = (ROOT / "docs/tiny-stories-evaluation-observability-proof.md").read_text()

    assert "Live Acceptance Protocol" in docs
    assert "Fixture / Protocol Checks" in docs
    assert "not the main acceptance" in docs
    assert "reviewer-only evidence path" in docs
    assert "narrative_llm_call_events" in docs
    assert "normal player UI" in docs
    assert "do not call the score a validated academic metric" in docs

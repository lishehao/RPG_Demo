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
from tools.rpg_eval.tiny_stories_golden_path_harness import (
    GOLDEN_PATH_REQUIRED_OPERATIONS,
    GOLDEN_PATH_TURN_BUDGET,
    QUALITY_CRITERIA,
    _quality_summary,
    _telemetry_failures,
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


def test_ci_uses_current_node24_action_runtimes() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    assert workflow.count("actions/checkout@v7") == 2
    assert workflow.count("actions/setup-node@v7") == 2
    assert "actions/setup-python@v6" in workflow
    assert workflow.count('node-version: "24"') == 2
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-node@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow


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


def test_golden_path_contract_requires_12_live_turns_and_core_ops() -> None:
    assert GOLDEN_PATH_TURN_BUDGET == 12
    assert GOLDEN_PATH_REQUIRED_OPERATIONS == {
        "create.story_butler_turn",
        "narrative.story_brief",
        "narrative.opening",
        "narrative.advance_turn",
    }
    assert {
        "consequence_clarity",
        "choice_diversity",
        "escalation",
        "character_intent",
        "brief_payoff",
        "playable_options",
    }.issubset(set(QUALITY_CRITERIA))


def test_golden_path_telemetry_rejects_missing_or_fallback_turn_rows() -> None:
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
            "status": "success",
            "source_label": "live",
            "fallback_reason": None,
            "session_id": "sess_gold",
        },
    ]
    rows.extend(
        {
            "operation": "narrative.advance_turn",
            "status": "success",
            "source_label": "live",
            "fallback_reason": None,
            "session_id": "sess_gold",
        }
        for _ in range(11)
    )
    rows.append(
        {
            "operation": "narrative.advance_turn",
            "status": "fallback_used",
            "source_label": "deterministic_fallback",
            "fallback_reason": "turn_value_error",
            "session_id": "sess_gold",
        }
    )

    failures = _telemetry_failures(events=rows, session_id="sess_gold", turn_budget=12)

    assert failures
    assert any(failure["stage"] == "narrative.advance_turn" for failure in failures)
    assert any("fallback" in failure["message"] for failure in failures)


def test_golden_path_quality_summary_is_bounded_not_research_metric() -> None:
    turns = [
        {
            "turn_number": index,
            "chosen_option_label": f"Choice {index % 5}",
            "next_option_count": 3 if index < 12 else 0,
            "is_complete": index == 12,
        }
        for index in range(1, 13)
    ]
    agent_events = []
    phases = ["hook", "pressure", "reversal", "climax", "pre_finale", "finale"]
    for index in range(1, 13):
        phase = phases[min(len(phases) - 1, index // 2)]
        agent_events.extend([
            {
                "event_type": "agent_plan",
                "payload": {
                    "director": {
                        "stage_phase": phase,
                        "active_npc_ids": ["singer"] if index > 1 else [],
                    }
                },
            },
            {
                "event_type": "step_judge",
                "payload": {"status": "pass"},
            },
            {
                "event_type": "contract_judge",
                "payload": {"status": "pass"},
            },
        ])
    summary = _quality_summary(
        turn_summaries=turns,
        agent_events=agent_events,
        story={"messages": [{"role": "narrator", "content": "The gala trophy livestream cornered the publicist and singer."}]},
        ending={"label": "自由", "subtitle": "I held the record.", "passage": "The sponsor faced the awards room."},
        seed="At an awards gala, a publicist, a singer, and a sponsor discover the live trophy reveal is rigged.",
    )

    assert summary["schema_version"] == "tiny_stories_golden_path_quality.v2"
    assert summary["status"] in {"pass", "warn"}
    assert "not a calibrated fun metric" in summary["rationale"]


def test_story_mode_character_quality_uses_live_responses_not_gauntlet_agenda() -> None:
    turns = [
        {
            "turn_number": index,
            "chosen_option_label": f"Choice {index}",
            "next_option_count": 3 if index < 12 else 0,
            "is_complete": index == 12,
        }
        for index in range(1, 13)
    ]
    agent_events: list[dict[str, object]] = []
    for index in range(1, 13):
        agent_events.extend([
            {
                "event_type": "agent_plan",
                "payload": {
                    "director": {
                        "difficulty": "story",
                        "stage_phase": "pressure" if index < 8 else "climax",
                        "active_npc_ids": [],
                        "focus_window_npc_ids": ["singer", "sponsor"],
                    }
                },
            },
            {"event_type": "step_judge", "payload": {"status": "pass"}},
            {"event_type": "contract_judge", "payload": {"status": "pass"}},
        ])
    messages: list[dict[str, object]] = [{"role": "narrator", "content": "Opening", "npc_pulse": []}]
    messages.extend(
        {
            "role": "narrator",
            "content": f"Resolved beat {index}",
            "npc_pulse": [
                {"npc_id": "singer", "shift": "wary" if index % 2 else "steady"},
                {"npc_id": "sponsor", "shift": "colder"},
            ],
        }
        for index in range(1, 13)
    )

    summary = _quality_summary(
        turn_summaries=turns,
        agent_events=agent_events,
        story={"messages": messages},
        ending={"label": "Freedom", "passage": "The singer leaves the gala."},
        seed="At a gala, a singer and sponsor corner the publicist.",
    )

    character = summary["criteria"]["character_intent"]
    assert character["status"] == "pass"
    assert character["evidence"]["mode"] == "story"
    assert character["evidence"]["active_npc_turns"] == 0
    assert character["evidence"]["responsive_npc_turns"] == 12
    assert character["evidence"]["shifted_npc_turns"] == 12
    assert character["evidence"]["distinct_npc_ids"] == ["singer", "sponsor"]


def test_story_mode_character_quality_warns_when_npcs_never_respond() -> None:
    turns = [
        {
            "turn_number": index,
            "chosen_option_label": f"Choice {index}",
            "next_option_count": 3 if index < 4 else 0,
            "is_complete": index == 4,
        }
        for index in range(1, 5)
    ]
    agent_events = [
        {
            "event_type": "agent_plan",
            "payload": {
                "director": {
                    "difficulty": "story",
                    "stage_phase": "pressure",
                    "active_npc_ids": [],
                    "focus_window_npc_ids": ["singer", "sponsor"],
                }
            },
        }
        for _ in turns
    ]

    summary = _quality_summary(
        turn_summaries=turns,
        agent_events=agent_events,
        story={"messages": [{"role": "narrator", "content": "No character response", "npc_pulse": []}]},
        ending=None,
        seed="A singer and sponsor wait at a gala.",
    )

    character = summary["criteria"]["character_intent"]
    assert character["status"] == "warn"
    assert character["evidence"]["responsive_npc_turns"] == 0


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


def test_engineering_evidence_packet_has_bounded_application_claims() -> None:
    packet = (ROOT / "docs/tiny-stories-engineering-evidence-packet.md").read_text()
    summary = json.loads(
        (ROOT / "artifacts/portfolio/tiny-stories-engineering-evidence-summary.json").read_text()
    )

    assert "```mermaid" in packet
    assert "Productized LLM / applied AI systems engineering, not HCI research." in packet
    assert "Historical live evidence anchor:" in packet
    assert "Current live evidence anchor:" in packet
    assert "It is not a claim that the commit below is current HEAD" in packet
    assert "for the current reviewer run, first check public visibility" in packet
    assert "those routes remain local" in packet
    assert "verification targets and demo-video context, not public proof" in packet
    assert "Current reviewer run boundary:" in packet
    assert "Public application wording should cite only source, video, and deployed pages" in packet
    assert "`#/portfolio`, `#/reviewer`, Story Desk, Create, Play, Replay, and local QA" in packet
    assert "do not present them as externally reviewable proof" in packet
    assert "Latest evidence anchor:" not in packet
    assert "latest_evidence_anchor" not in summary
    assert "historical_live_evidence_anchor" in summary
    assert "4382874 fix: keep opening live for eval gate" in packet
    assert (
        summary["historical_live_evidence_anchor"]["snapshot"]
        == "snapshot/story-brief-opening-live-reliability-2026-06-08"
    )
    historical_anchor = summary["historical_live_evidence_anchor"]
    assert historical_anchor["visibility"] == "local_historical"
    assert historical_anchor["public_link"] is False
    assert "local run-output names retained for provenance" in historical_anchor["note"]
    assert "not public reviewer links" in historical_anchor["note"]

    visibility = summary["evidence_visibility"]
    assert "not a public deployment proof by itself" in visibility["artifact_scope"]
    assert "public-link check" in visibility["public_use_gate"]
    assert "portfolio_public_evidence_preflight.py" in visibility["public_use_gate"]
    assert "artifacts/portfolio as local-only" in visibility["current_public_claim_boundary"]
    assert "Do not ask public reviewers to start from #/portfolio or #/reviewer" in visibility["application_claim_rule"]
    assert "unless the public-link check passes" in visibility["application_claim_rule"]
    assert "local verification targets and demo-video context" in visibility["application_claim_rule"]
    assert "not public links" in visibility["historical_anchor_boundary"]

    assert "| Opening | `narrative.opening` | 1 | `live/success` | 10942/10942/10942ms | 2678 | 1408 | 693 | 3371 | 0 | none |" in packet
    assert "the 14.0s median Play-turn latency is a real provider-bound product risk" in packet
    assert "Step Judge" in packet
    assert "Contract Judge" in packet
    assert "deterministic trajectory trend" in packet
    assert "not a full live trajectory judge" in packet
    assert "not neural embeddings or a vector database" in packet
    assert "not the main acceptance" in packet

    live_gate = summary["live_gate"]
    assert live_gate["status"] == "pass"
    assert live_gate["failure_count"] == 0
    assert live_gate["completed_turns"] == 12
    current_anchor = summary["current_live_evidence_anchor"]
    assert current_anchor["completed_turns"] == 12
    assert current_anchor["step_judge_passes"] == 12
    assert current_anchor["contract_judge_passes"] == 12
    assert current_anchor["quality_schema_version"] == "tiny_stories_golden_path_quality.v2"
    assert current_anchor["quality_status"] == "pass"
    assert current_anchor["public_link"] is False
    operations = {row["operation"]: row for row in live_gate["required_operations"]}
    assert operations["narrative.opening"]["source"] == "live"
    assert operations["narrative.opening"]["fallback"] is None
    assert operations["narrative.opening"]["total_tokens"] == 3371
    assert operations["narrative.advance_turn"]["call_count"] == 12
    assert operations["narrative.advance_turn"]["retry_count_max"] == 0
    assert any("full live trajectory judge" in item for item in summary["guardrails"])
    assert any("neural embeddings" in item for item in summary["guardrails"])
    assert any("/tmp historical artifact paths" in item for item in summary["guardrails"])

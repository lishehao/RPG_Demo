from __future__ import annotations

from random import Random

from tools.play_benchmarks import generation_acceptance_eval


def _session(*, persona_id: str = "assertive_operator", reports: list[dict] | None = None) -> dict:
    return {
        "persona_id": persona_id,
        "agent_report": {
            "ratings": {
                "ending_satisfaction": 4,
                "overall_player_feel": 4,
                "content_richness": 4,
                "state_feedback_distinctness": 4,
            },
            "source": "llm",
        },
        "independent_judge_reports": reports or [],
    }


def _story(*, duration: int, preview_cast: int, final_cast: int, final_beats: int, turn_budget: int, sessions: list[dict] | None = None) -> dict:
    return {
        "requested_target_duration_minutes": duration,
        "preview": {
            "story_flow_plan": {
                "target_duration_minutes": duration,
                "recommended_cast_count": preview_cast,
            },
            "structure": {
                "expected_npc_count": preview_cast,
            },
        },
        "result": {"status": "completed"},
        "published_story": {
            "story_id": f"story-{duration}",
            "npc_count": final_cast,
            "beat_count": final_beats,
        },
        "story_detail": {
            "play_overview": {
                "max_turns": turn_budget,
            }
        },
        "turn_budget": turn_budget,
        "sessions": sessions or [],
    }


def test_story_duration_assignments_cover_all_buckets_once_and_match_distribution() -> None:
    assignments = generation_acceptance_eval._story_duration_assignments(rng=Random(7))

    assert len(assignments) == 10
    assert len({seed.bucket_id for seed, _duration in assignments}) == 10
    assert [duration for _seed, duration in assignments].count(10) == 4
    assert [duration for _seed, duration in assignments].count(17) == 3
    assert [duration for _seed, duration in assignments].count(25) == 3


def test_generation_acceptance_summary_computes_duration_and_cast_rates() -> None:
    stories = [
        _story(duration=10, preview_cast=3, final_cast=3, final_beats=2, turn_budget=4),
        _story(duration=10, preview_cast=3, final_cast=4, final_beats=2, turn_budget=4),
        _story(duration=17, preview_cast=4, final_cast=4, final_beats=4, turn_budget=8),
    ]

    summary = generation_acceptance_eval._acceptance_summary_for_stories(stories)

    assert summary["overall"]["requested_story_count"] == 3
    assert summary["overall"]["completed_author_jobs"] == 3
    assert summary["overall"]["published_stories"] == 3
    assert summary["overall"]["preview_target_duration_match_rate"] == 1.0
    assert summary["overall"]["preview_expected_npc_count_in_range_rate"] == 1.0
    assert summary["overall"]["final_cast_count_in_range_rate"] == 1.0
    assert summary["overall"]["final_cast_matches_preview_expected_rate"] == round(2 / 3, 3)
    assert summary["per_duration"]["10"]["requested_story_count"] == 2
    assert summary["per_duration"]["17"]["final_beat_count_distribution"] == {"4": 1}


def test_independent_judge_metrics_and_consensus_aggregate_per_panel() -> None:
    reports_a = [
        {
            "judge_id": "ending_payoff_judge",
            "judge_label": "Ending Payoff Judge",
            "provider": "helper",
            "report_source": "llm",
            "error": None,
            "report": {
                "strongest_issue": "ending payoff too soft",
                "flags": ["ending_feels_unearned"],
                "ratings": {
                    "ending_satisfaction": 2,
                    "overall_player_feel": 3,
                    "content_richness": 4,
                    "state_feedback_distinctness": 4,
                },
            },
        },
        {
            "judge_id": "system_clarity_judge",
            "judge_label": "System Clarity Judge",
            "provider": "helper",
            "report_source": "llm",
            "error": None,
            "report": {
                "strongest_issue": "state feedback too flat",
                "flags": ["flat_state_feedback"],
                "ratings": {
                    "ending_satisfaction": 3,
                    "overall_player_feel": 3,
                    "content_richness": 3,
                    "state_feedback_distinctness": 2,
                },
            },
        },
        {
            "judge_id": "prose_variety_judge",
            "judge_label": "Prose Variety Judge",
            "provider": "helper",
            "report_source": "llm_salvage_partial",
            "error": "provider timeout",
            "report": {
                "strongest_issue": "phrasing repetition",
                "flags": ["late_game_flatness"],
                "ratings": {
                    "ending_satisfaction": 4,
                    "overall_player_feel": 4,
                    "content_richness": 3,
                    "state_feedback_distinctness": 4,
                },
            },
        },
    ]
    reports_b = [
        {
            "judge_id": "ending_payoff_judge",
            "judge_label": "Ending Payoff Judge",
            "provider": "helper",
            "report_source": "llm",
            "error": None,
            "report": {
                "strongest_issue": "none",
                "flags": [],
                "ratings": {
                    "ending_satisfaction": 4,
                    "overall_player_feel": 4,
                    "content_richness": 4,
                    "state_feedback_distinctness": 4,
                },
            },
        },
        {
            "judge_id": "system_clarity_judge",
            "judge_label": "System Clarity Judge",
            "provider": "helper",
            "report_source": "llm",
            "error": None,
            "report": {
                "strongest_issue": "none",
                "flags": [],
                "ratings": {
                    "ending_satisfaction": 4,
                    "overall_player_feel": 4,
                    "content_richness": 4,
                    "state_feedback_distinctness": 4,
                },
            },
        },
        {
            "judge_id": "prose_variety_judge",
            "judge_label": "Prose Variety Judge",
            "provider": "helper",
            "report_source": "llm",
            "error": None,
            "report": {
                "strongest_issue": "none",
                "flags": [],
                "ratings": {
                    "ending_satisfaction": 4,
                    "overall_player_feel": 4,
                    "content_richness": 4,
                    "state_feedback_distinctness": 4,
                },
            },
        },
    ]
    stories = [
        _story(duration=10, preview_cast=3, final_cast=3, final_beats=2, turn_budget=4, sessions=[_session(reports=reports_a)]),
        _story(duration=17, preview_cast=4, final_cast=4, final_beats=4, turn_budget=8, sessions=[_session(persona_id="coalition_builder", reports=reports_b)]),
    ]

    metrics = generation_acceptance_eval._build_independent_judge_metrics(stories)
    consensus = generation_acceptance_eval._build_independent_judge_consensus(stories)

    assert metrics["overall"]["session_count"] == 6
    assert metrics["by_judge"]["ending_payoff_judge"]["ending_satisfaction"] == 3.0
    assert metrics["by_judge"]["prose_variety_judge"]["report_source_distribution"] == {
        "llm_salvage_partial": 1,
        "llm": 1,
    }
    assert consensus["session_count"] == 2
    assert consensus["disagreement_count"] == 1
    assert consensus["all_three_ending_payoff_acceptable_count"] == 1
    assert consensus["dominant_ending_failure_count"] == 0


def test_build_acceptance_checks_reflects_thresholds() -> None:
    stories = [
        _story(duration=10, preview_cast=3, final_cast=3, final_beats=2, turn_budget=4),
        _story(duration=17, preview_cast=4, final_cast=4, final_beats=4, turn_budget=8),
    ]
    scorecard = {
        "actuals": {
            "empty_narration_rate": 0.0,
            "render_fallback_rate": 0.0,
        }
    }
    generation_summary = generation_acceptance_eval._acceptance_summary_for_stories(stories)
    independent_metrics = {
        "overall": {
            "session_count": 30,
            "overall_player_feel": 3.4,
        },
        "by_judge": {
            "ending_payoff_judge": {
                "ending_satisfaction": 3.8,
            }
        },
    }
    consensus = {
        "all_three_ending_payoff_acceptable_rate": 0.8,
        "dominant_ending_failure_rate": 0.1,
    }

    checks = generation_acceptance_eval._build_acceptance_checks(
        stories=stories,
        scorecard=scorecard,
        generation_acceptance_summary=generation_summary,
        independent_judge_metrics=independent_metrics,
        independent_judge_consensus=consensus,
    )

    assert all(item["passed"] for item in checks)

from __future__ import annotations

from contextlib import contextmanager
import json
from random import Random
from types import SimpleNamespace

from tools.play_benchmarks import live_api_playtest
from tools.play_benchmarks.story_seed_factory import STORY_SEED_BUCKET_IDS, build_story_seed_batch


def test_story_seed_factory_returns_ten_unique_bucketed_seeds_when_requested() -> None:
    seeds = build_story_seed_batch(rng=Random(7), story_count=10)

    assert len(seeds) == 10
    assert len({item.seed for item in seeds}) == 10
    assert {item.bucket_id for item in seeds} == set(STORY_SEED_BUCKET_IDS)


def test_story_seed_factory_can_sample_three_unique_buckets() -> None:
    seeds = build_story_seed_batch(rng=Random(3), story_count=3)

    assert len(seeds) == 3
    assert len({item.bucket_id for item in seeds}) == 3
    assert len({item.seed for item in seeds}) == 3


def test_live_api_playtest_aggregates_story_matrix_and_scorecard(monkeypatch, tmp_path) -> None:
    seeds = build_story_seed_batch(rng=Random(11), story_count=3)
    seen_turn_budgets: list[int] = []

    def _fake_author_story(*, session, base_url, generated_seed, target_duration_minutes):  # noqa: ANN001
        del session, base_url
        return {
            "bucket_id": generated_seed.bucket_id,
            "slug": generated_seed.slug,
            "seed": generated_seed.seed,
            "generated_at": generated_seed.generated_at,
            "job_id": f"{generated_seed.slug}-job",
            "preview": {"preview_id": f"{generated_seed.slug}-preview"},
            "stream": {"events": [], "stream_elapsed_seconds": 1.2, "terminal_event": {"event": "job_completed"}},
            "result": {"status": "completed"},
            "diagnostics": {
                "source_summary": {
                    "story_frame_source": "generated",
                    "beat_plan_source": "generated",
                    "route_affordance_source": "generated",
                    "ending_source": "generated",
                    "gameplay_semantics_source": "repaired",
                },
                "token_cost_estimate": {"estimated_total_cost_rmb": 0.0012},
                "content_prompt_profile": "role_conditioned",
            },
            "published_story": {
                "story_id": f"{generated_seed.slug}-story",
                "title": generated_seed.slug.replace("_", " ").title(),
            },
            "story_detail": {
                "story": {
                    "story_id": f"{generated_seed.slug}-story",
                    "title": generated_seed.slug.replace("_", " ").title(),
                    "theme": "Civic crisis",
                },
                "play_overview": {
                    "max_turns": 10,
                    "target_duration_minutes": target_duration_minutes,
                    "branch_budget": "high",
                },
            },
            "error": None,
            "timings": {"author_total_elapsed_seconds": 3.4},
        }

    def _fake_story_playtests(*, base_url, story_detail, max_turns, transport_style, use_helper_agent):  # noqa: ANN001
        del base_url, transport_style, use_helper_agent
        seen_turn_budgets.append(max_turns)
        story_id = story_detail["story"]["story_id"]
        sessions = []
        for index, persona in enumerate(live_api_playtest.PERSONAS):
            rich_score = 5 if index in {1, 3} else 4
            ending_id = "collapse" if persona.persona_id == "legitimacy_guardian" else "mixed"
            sessions.append(
                {
                    "persona_id": persona.persona_id,
                    "persona_label": persona.label,
                    "session_id": f"{story_id}-{persona.persona_id}",
                    "turn_budget": max_turns,
                    "turn_budget_utilization": 0.4,
                    "create_elapsed_seconds": round(1.0 + index * 0.1, 3),
                    "forced_stop": False,
                    "opening": "You arrive with the evidence and the room turns toward you.",
                    "final_snapshot": {"status": "completed", "turn_index": 4, "ending": {"ending_id": ending_id}},
                    "turns": [
                        {
                            "agent_turn_source": "llm",
                            "submit_elapsed_seconds": round(3.0 + index * 0.1, 3),
                            "narration_word_count": 80 + index,
                            "feedback": {
                                "last_turn_axis_deltas": {f"axis_{index}": 1},
                                "last_turn_stance_deltas": {f"stance_{index}": -1 if index % 2 == 0 else 1},
                                "last_turn_consequences": [f"Consequence {index}a"],
                            },
                        },
                        {
                            "agent_turn_source": "llm",
                            "submit_elapsed_seconds": round(4.0 + index * 0.1, 3),
                            "narration_word_count": 84 + index,
                            "feedback": {
                                "last_turn_axis_deltas": {f"axis_{index}": 1, "shared_axis": 1},
                                "last_turn_stance_deltas": {f"stance_{index}": -1 if index % 2 == 0 else 1},
                                "last_turn_consequences": [f"Consequence {index}b"],
                            },
                        },
                    ],
                    "feedback_metrics": {
                        "distinct_axis_count": 2,
                        "distinct_stance_count": 1,
                        "distinct_consequence_count": 2,
                        "nonzero_feedback_turns": 2,
                    },
                    "late_half_feedback_metrics": {
                        "distinct_axis_count": 2,
                        "distinct_stance_count": 1,
                        "distinct_consequence_count": 1,
                        "nonzero_feedback_turns": 1,
                    },
                    "diagnostics": {
                        "content_prompt_profile": "role_conditioned",
                        "turn_traces": [
                            {
                                "interpret_source": "llm",
                                "render_source": "llm",
                                "ending_judge_source": "llm",
                                "pyrrhic_critic_source": "skipped",
                                "interpret_failure_reason": None,
                                "render_failure_reason": None,
                                "ending_judge_failure_reason": None,
                                "pyrrhic_critic_failure_reason": None,
                            },
                            {
                                "interpret_source": "llm",
                                "render_source": "llm_repair" if index % 2 == 0 else "llm",
                                "ending_judge_source": "llm",
                                "pyrrhic_critic_source": "skipped",
                                "interpret_failure_reason": None,
                                "render_failure_reason": "missing_state_payoff" if index % 2 == 0 else None,
                                "ending_judge_failure_reason": None,
                                "pyrrhic_critic_failure_reason": None,
                            },
                        ],
                        "summary": {
                            "render_fallback_turn_count": 0,
                            "heuristic_interpret_turn_count": 0,
                            "usage_totals": {"input_tokens": 120 + index, "output_tokens": 60 + index},
                            "interpret_source_distribution": {"llm": 2},
                            "ending_judge_source_distribution": {"llm": 2},
                            "render_source_distribution": {"llm": 1, "llm_repair": 1} if index % 2 == 0 else {"llm": 2},
                        },
                    },
                    "diagnostics_elapsed_seconds": 0.2,
                    "agent_report": {
                        "flags": ["late_game_flatness"] if persona.persona_id == "coalition_builder" else [],
                        "ratings": {
                            "narration_coherence": rich_score,
                            "suggested_action_relevance": rich_score,
                            "state_feedback_credibility": rich_score,
                            "ending_satisfaction": rich_score,
                            "overall_player_feel": rich_score,
                            "content_richness": rich_score,
                            "state_feedback_distinctness": rich_score,
                        },
                        "strongest_issue": f"Persona {persona.persona_id} narrowed too early.",
                        "best_moment": f"Persona {persona.persona_id} hit the cleanest reveal.",
                        "verdict": "Strong, coherent player-facing session.",
                        "source": "llm",
                    },
                    "agent_cache_metrics": {},
                    "agent_cost_estimate": {"estimated_total_cost_rmb": round(0.002 + index * 0.0001, 4)},
                    "agent_call_trace": [{"operation_name": f"playtest_turn_{persona.persona_id}"}],
                    "agent_error_distribution": {},
                    "agent_turn_rejection_distribution": {},
                    "agent_report_missing_field_distribution": {},
                    "agent_turn_max_output_tokens": 420,
                    "agent_report_max_output_tokens": 800,
                    "agent_transcript_window_entries": 12,
                    "error": None,
                }
            )
        return sessions

    monkeypatch.setattr(live_api_playtest, "build_story_seed_batch", lambda rng=None, story_count=5: seeds[:story_count])
    monkeypatch.setattr(live_api_playtest, "_run_author_story", _fake_author_story)
    monkeypatch.setattr(live_api_playtest, "_run_story_playtests", _fake_story_playtests)

    payload = live_api_playtest.run_live_api_playtest(
        live_api_playtest.LiveApiPlaytestConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            label="matrix-test",
            launch_server=False,
            session_ttl_seconds=3600,
            max_turns=None,
            seed=11,
            story_count=3,
            phase_id="stage1",
            seed_set_id="seed-set-a",
            arm="candidate",
            baseline_artifact=None,
            managed_server_content_prompt_profile=None,
            target_duration_minutes=25,
            agent_transport_style="chat_completions",
            probe_turn_proposal=False,
        )
    )

    assert len(payload["stories"]) == 3
    assert all(len(story["sessions"]) == len(live_api_playtest.PERSONAS) for story in payload["stories"])
    assert seen_turn_budgets == [10, 10, 10]
    assert payload["target_duration_minutes"] == 25
    assert payload["scorecard"]["actuals"]["author_publish_success_rate"] == 1.0
    assert payload["scorecard"]["actuals"]["play_completed_sessions"] == 15
    assert payload["scorecard"]["actuals"]["render_fallback_rate"] == 0.0
    assert payload["scorecard"]["actuals"]["mean_narration_word_count_per_turn"] >= 80
    assert payload["scorecard"]["actuals"]["axis_diversity_per_session"] == 2
    assert payload["scorecard"]["actuals"]["late_half_axis_diversity_per_session"] == 2
    assert payload["scorecard"]["actuals"]["late_half_stance_target_diversity_per_session"] == 1
    assert payload["scorecard"]["actuals"]["turn_budget_utilization"] == 0.4
    assert payload["scorecard"]["actuals"]["early_non_collapse_ending_count"] == 12
    assert payload["scorecard"]["actuals"]["late_game_flatness_flag_rate"] == 0.2
    assert payload["scorecard"]["actuals"]["benchmark_agent_turn_fallback_rate"] == 0.0
    assert payload["scorecard"]["actuals"]["benchmark_agent_report_llm_rate"] == 1.0
    assert payload["scorecard"]["actuals"]["benchmark_agent_report_fallback_rate"] == 0.0
    assert payload["scorecard"]["actuals"]["judge_nonfallback_rate"] == 1.0
    assert payload["scorecard"]["actuals"]["judge_fallback_rate"] == 0.0
    assert payload["scorecard"]["actuals"]["ending_judge_failed_rate"] == 0.0
    assert payload["scorecard"]["actuals"]["benchmark_agent_turn_max_output_tokens"] == 420
    assert payload["scorecard"]["actuals"]["benchmark_agent_report_max_output_tokens"] == 800
    assert payload["scorecard"]["actuals"]["benchmark_agent_transcript_window_entries"] == 12
    assert payload["scorecard"]["actuals"]["agent_trace_coverage_rate"] == 1.0
    assert payload["scorecard"]["actuals"]["play_trace_coverage_rate"] == 1.0
    assert payload["scorecard"]["actuals"]["trace_labeled_failure_rate"] == 1.0
    assert payload["scorecard"]["actuals"]["content_richness"] == 4.4
    assert payload["scorecard"]["actuals"]["state_feedback_distinctness"] == 4.4
    assert payload["scorecard"]["actuals"]["author_total_estimated_cost_rmb"] == 0.0036
    assert payload["scorecard"]["actuals"]["benchmark_agent_total_estimated_cost_rmb"] == 0.033
    assert payload["scorecard"]["actuals"]["median_first_submit_turn_seconds"] == 3.2
    assert payload["scorecard"]["actuals"]["play_runtime_total_estimated_cost_rmb"] > 0.0
    assert payload["scorecard"]["subjective_summary"]["avg_suggested_action_relevance"] == 4.4
    assert payload["scorecard"]["passed"] is True
    assert payload["scorecard"]["polluted_by_driver"] is False
    assert payload["phase_id"] == "stage1"
    assert payload["seed_set_id"] == "seed-set-a"
    assert payload["arm"] == "candidate"
    assert payload["configured_content_prompt_profile"] == "role_conditioned"
    assert payload["observed_author_content_prompt_profiles"] == ["role_conditioned"]
    assert payload["observed_play_content_prompt_profiles"] == ["role_conditioned"]


def test_run_author_story_forwards_target_duration_minutes(monkeypatch) -> None:
    preview_calls: list[int | None] = []
    job_calls: list[int | None] = []

    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_story_preview_with_controls",
        lambda session, base_url, prompt_seed, *, target_duration_minutes: (
            preview_calls.append(target_duration_minutes) or {"preview_id": "preview-1"},
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_create_author_job_with_controls",
        lambda session, base_url, prompt_seed, preview_id, *, target_duration_minutes: (
            job_calls.append(target_duration_minutes) or {"job_id": "job-1"},
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_stream_author_job_to_terminal",
        lambda session, base_url, job_id: {"events": [], "terminal_event": {"event": "job_completed"}},
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_author_job_result",
        lambda session, base_url, job_id: ({"status": "completed"}, 0.1),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_author_diagnostics",
        lambda session, base_url, job_id: ({"source_summary": {}, "token_cost_estimate": {}}, 0.1),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_publish_author_job",
        lambda session, base_url, job_id: ({"story_id": "story-1", "title": "Story"}, 0.1),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: ({"story": {"story_id": story_id}}, 0.1),
    )

    seed = build_story_seed_batch(rng=Random(5), story_count=1)[0]
    payload = live_api_playtest._run_author_story(
        session=object(),
        base_url="http://bench.local",
        generated_seed=seed,
        target_duration_minutes=25,
    )

    assert preview_calls == [25]
    assert job_calls == [25]
    assert payload["published_story"]["story_id"] == "story-1"


def test_extract_turn_input_from_raw_text_strips_meta_wrapper() -> None:
    extracted = live_api_playtest._extract_turn_input_from_raw_text(
        'Here is the JSON requested: input_text: "I expose the forged ledger before the whole chamber."'
    )

    assert extracted == "I expose the forged ledger before the whole chamber."


def test_extract_turn_input_candidates_rejects_meta_tokens() -> None:
    candidates = live_api_playtest._extract_turn_input_candidates(
        "Here is the JSON requested\n{\njson\nInput text: I force the chamber to compare the sealed ledgers in public before anyone can revise them.\n}"
    )

    assert candidates == ["I force the chamber to compare the sealed ledgers in public before anyone can revise them."]


def test_extract_turn_input_candidates_decodes_stringified_json() -> None:
    candidates = live_api_playtest._extract_turn_input_candidates(
        '"{\\"input_text\\": \\"I force the chamber to compare the sealed ledgers in public before anyone can revise them.\\"}"'
    )

    assert candidates == ["I force the chamber to compare the sealed ledgers in public before anyone can revise them."]


def test_playtest_agent_uses_longform_budget_and_second_stage_plaintext_prompt(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class _FakeBenchmarkTransport:
        def invoke_json(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    payload={},
                    response_id="resp-1",
                    usage={},
                    input_characters=10,
                    fallback_source="raw_text_passthrough",
                    raw_text="{",
                )
            if len(calls) == 2:
                return SimpleNamespace(
                    payload={},
                    response_id="resp-2",
                    usage={},
                    input_characters=10,
                    fallback_source="raw_text_passthrough",
                    raw_text="INPUT_TEXT: I force the chamber to compare the sealed ledgers in public before anyone can revise them.",
                )

    monkeypatch.setattr(live_api_playtest, "build_openai_client", lambda **_kwargs: object())
    monkeypatch.setattr(live_api_playtest, "build_json_transport", lambda **_kwargs: _FakeBenchmarkTransport())

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            gateway_base_url="https://example.com/v1",
            gateway_api_key="test-key",
            gateway_model="gateway-text-model",
        ),
        transport_style="responses",
    )
    transcript = [{"speaker": "gm", "text": f"line-{idx}"} for idx in range(20)]
    proposed = agent.propose_turn(
        story_detail={"play_overview": {"target_duration_minutes": 25, "branch_budget": "high"}},
        snapshot={
            "beat_title": "The Public Price",
            "suggested_actions": [
                {"label": "Press the room", "prompt": "You press the room for more answers."},
                {"label": "Secure witnesses", "prompt": "You secure the witnesses before the rumor spreads."},
            ],
        },
        transcript=transcript,
    )

    assert proposed["source"] == "llm_salvage"
    assert proposed["attempt"] == 2
    assert proposed["input_text"].startswith("I force the chamber")
    assert calls[0]["max_output_tokens"] == 420
    assert calls[1]["max_output_tokens"] == 520
    assert len(calls[0]["user_payload"]["working_digest"]["recent_gm_consequences"]) <= 2
    assert "Output only JSON" in str(calls[0]["system_prompt"])
    assert "BEAT_ANCHOR" in str(calls[1]["system_prompt"])
    assert "INPUT_TEXT" in str(calls[1]["system_prompt"])


def test_playtest_agent_strict_schema_cleans_payload_input_prefix(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "build_openai_client", lambda **_kwargs: object())
    monkeypatch.setattr(live_api_playtest, "build_json_transport", lambda **_kwargs: SimpleNamespace(invoke_json=lambda **_kwargs: None))
    monkeypatch.setattr(live_api_playtest.PlaytestAgentClient, "_probe_driver_strategy", lambda self: "strict_schema")

    responses = iter(
        [
            live_api_playtest.ResponsesJSONResponse(
                payload={"move_family": "public_pressure"},
                response_id="move-family-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='{"move_family":"public_pressure"}',
            ),
            live_api_playtest.ResponsesJSONResponse(
                payload={"input_text": 'input_text": "I push through the crowd to confront Kaelen Vross and force him to declare the anomaly status aloud.'},
                response_id="turn-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='{"input_text":"input_text\\": \\"I push through the crowd to confront Kaelen Vross and force him to declare the anomaly status aloud.\\""}',
            ),
        ]
    )

    monkeypatch.setattr(
        live_api_playtest.PlaytestAgentClient,
        "_invoke_structured_output_chat",
        lambda self, **_kwargs: next(responses),
    )

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            gateway_base_url="https://example.com/v1",
            gateway_api_key="test-key",
            gateway_model="gateway-text-model",
        ),
        transport_style="chat_completions",
    )

    proposed = agent.propose_turn(
        story_detail={"story": {"story_id": "story-1"}, "play_overview": {"target_duration_minutes": 25, "branch_budget": "high"}},
        snapshot={"beat_title": "Manifest Anomaly", "suggested_actions": []},
        transcript=[{"speaker": "gm", "text": "The anomaly is in plain view."}],
    )

    assert proposed["source"] == "llm"
    assert proposed["input_text"].startswith("I push through the crowd")
    assert 'input_text":' not in proposed["input_text"]


def test_playtest_agent_strict_schema_falls_back_to_raw_text_when_payload_input_is_garbage(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "build_openai_client", lambda **_kwargs: object())
    monkeypatch.setattr(live_api_playtest, "build_json_transport", lambda **_kwargs: SimpleNamespace(invoke_json=lambda **_kwargs: None))
    monkeypatch.setattr(live_api_playtest.PlaytestAgentClient, "_probe_driver_strategy", lambda self: "strict_schema")

    responses = iter(
        [
            live_api_playtest.ResponsesJSONResponse(
                payload={"move_family": "public_pressure"},
                response_id="move-family-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='{"move_family":"public_pressure"}',
            ),
            live_api_playtest.ResponsesJSONResponse(
                payload={"input_text": "json"},
                response_id="turn-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='INPUT_TEXT: I force the chamber to compare the sealed ledgers in public before anyone can revise them.',
            ),
        ]
    )

    monkeypatch.setattr(
        live_api_playtest.PlaytestAgentClient,
        "_invoke_structured_output_chat",
        lambda self, **_kwargs: next(responses),
    )

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            gateway_base_url="https://example.com/v1",
            gateway_api_key="test-key",
            gateway_model="gateway-text-model",
        ),
        transport_style="chat_completions",
    )

    proposed = agent.propose_turn(
        story_detail={"story": {"story_id": "story-1"}, "play_overview": {"target_duration_minutes": 25, "branch_budget": "high"}},
        snapshot={"beat_title": "Manifest Anomaly", "suggested_actions": []},
        transcript=[{"speaker": "gm", "text": "The anomaly is in plain view."}],
    )

    assert proposed["source"] == "llm"
    assert proposed["input_text"].startswith("I force the chamber")
    assert proposed["input_text"] == "I force the chamber to compare the sealed ledgers in public before anyone can revise them."


def test_playtest_agent_uses_benchmark_driver_timeout_override(monkeypatch) -> None:
    build_transport_kwargs: dict[str, object] = {}

    class _FakeBenchmarkTransport:
        def invoke_json(self, **kwargs):
            return SimpleNamespace(
                payload={"input_text": "I force the chamber to compare the sealed ledgers in public before anyone can revise them."},
                response_id="resp-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='{"input_text":"I force the chamber to compare the sealed ledgers in public before anyone can revise them."}',
            )

    monkeypatch.setattr(live_api_playtest, "build_openai_client", lambda **_kwargs: object())
    monkeypatch.setattr(
        live_api_playtest,
        "build_json_transport",
        lambda **kwargs: build_transport_kwargs.update(kwargs) or _FakeBenchmarkTransport(),
    )

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            gateway_base_url="https://example.com/v1",
            gateway_api_key="test-key",
            gateway_model="gateway-text-model",
            gateway_timeout_seconds=20,
            gateway_timeout_seconds_benchmark_driver=90,
        ),
        transport_style="responses",
    )

    assert agent._timeout_seconds == 90.0
    assert build_transport_kwargs["timeout_seconds"] == 90.0


def test_playtest_agent_helper_provider_uses_helper_gateway_settings(monkeypatch) -> None:
    captured_client_kwargs: dict[str, object] = {}
    captured_transport_kwargs: dict[str, object] = {}

    class _FakeBenchmarkTransport:
        def invoke_json(self, **_kwargs):
            return live_api_playtest.ResponsesJSONResponse(
                payload={"input_text": "I force the chamber to compare the sealed ledgers in public before anyone can revise them."},
                response_id="resp-helper-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='{"input_text":"I force the chamber to compare the sealed ledgers in public before anyone can revise them."}',
            )

    monkeypatch.setattr(
        live_api_playtest,
        "build_openai_client",
        lambda **kwargs: captured_client_kwargs.update(kwargs) or object(),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "build_json_transport",
        lambda **kwargs: captured_transport_kwargs.update(kwargs) or _FakeBenchmarkTransport(),
    )

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            helper_gateway_base_url="https://helper.example/v1",
            helper_gateway_responses_base_url="https://helper-responses.example/v1",
            helper_gateway_api_key="helper-key",
            helper_gateway_model="helper-model",
            gateway_timeout_seconds_benchmark_driver=45,
        ),
        transport_style="responses",
        provider="helper",
    )

    proposed = agent.propose_turn(
        story_detail={"play_overview": {"target_duration_minutes": 25, "branch_budget": "high"}},
        snapshot={"beat_title": "The Public Price", "suggested_actions": []},
        transcript=[{"speaker": "gm", "text": "The room hardens around the proof."}],
    )

    assert proposed["source"] == "llm"
    assert captured_client_kwargs["base_url"] == "https://helper-responses.example/v1"
    assert captured_client_kwargs["api_key"] == "helper-key"
    assert captured_transport_kwargs["model"] == "helper-model"
    assert agent._provider == "helper"
    assert agent._timeout_seconds == 60.0


def test_shared_benchmark_provider_limiter_defaults() -> None:
    limiter = live_api_playtest.get_shared_benchmark_provider_limiter(
        base_url="https://benchmark.example/v1",
        model="benchmark-model",
    )

    assert limiter.max_concurrency == 20
    assert limiter.max_requests_per_minute == 120


def test_playtest_agent_prefers_helper_provider_when_probe_succeeds(monkeypatch) -> None:
    captured_client_kwargs: list[dict[str, object]] = []
    captured_transport_kwargs: list[dict[str, object]] = []

    class _FakeBenchmarkTransport:
        def invoke_json(self, **_kwargs):
            return live_api_playtest.ResponsesJSONResponse(
                payload={"input_text": "I force the chamber to compare the sealed ledgers in public before anyone can revise them."},
                response_id="resp-helper-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='{"input_text":"I force the chamber to compare the sealed ledgers in public before anyone can revise them."}',
            )

    monkeypatch.setattr(
        live_api_playtest,
        "build_openai_client",
        lambda **kwargs: captured_client_kwargs.append(dict(kwargs)) or object(),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "build_json_transport",
        lambda **kwargs: captured_transport_kwargs.append(dict(kwargs)) or _FakeBenchmarkTransport(),
    )
    monkeypatch.setattr(
        live_api_playtest.PlaytestAgentClient,
        "_probe_helper_json_schema_capability",
        lambda self: {"supported": True, "elapsed_ms": 5, "error_message": None},
    )

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            gateway_base_url="https://primary.example/v1",
            gateway_responses_base_url="https://primary-responses.example/v1",
            gateway_api_key="primary-key",
            gateway_model="primary-model",
            helper_gateway_base_url="https://helper.example/v1",
            helper_gateway_responses_base_url="https://helper-responses.example/v1",
            helper_gateway_api_key="helper-key",
            helper_gateway_model="helper-model",
        ),
        transport_style="responses",
        provider="helper",
    )

    proposed = agent.propose_turn(
        story_detail={"play_overview": {"target_duration_minutes": 25, "branch_budget": "high"}},
        snapshot={"beat_title": "The Public Price", "suggested_actions": []},
        transcript=[{"speaker": "gm", "text": "The room hardens around the proof."}],
    )

    assert proposed["source"] == "llm"
    assert captured_client_kwargs[0]["base_url"] == "https://helper-responses.example/v1"
    assert captured_transport_kwargs[0]["model"] == "helper-model"
    assert agent._provider == "helper"


def test_playtest_agent_uses_helper_provider_rate_limiter(monkeypatch) -> None:
    acquire_count = {"value": 0}

    @contextmanager
    def _acquire():
        acquire_count["value"] += 1
        yield live_api_playtest._BenchmarkProviderRateLimitDecision(wait_ms=7, applied=True)

    class _FakeLimiter:
        max_concurrency = 20
        max_requests_per_minute = 120

        def acquire(self):
            return _acquire()

    class _FakeChatCompletions:
        def __init__(self, responses):
            self._responses = iter(responses)

        def create(self, **_kwargs):
            payload = next(self._responses)
            return SimpleNamespace(
                id=payload["id"],
                choices=[SimpleNamespace(message=SimpleNamespace(content=payload["content"]))],
                usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            )

    build_client_call = {"value": 0}

    def _fake_build_openai_client(**_kwargs):
        build_client_call["value"] += 1
        if build_client_call["value"] == 1:
            # Main benchmark client used for structured output calls.
            return SimpleNamespace(
                chat=SimpleNamespace(
                    completions=_FakeChatCompletions(
                        [
                            {"id": "move-family-1", "content": '{"move_family":"public_pressure"}'},
                            {"id": "turn-1", "content": '{"input_text":"I force the chamber to compare the sealed ledgers in public before anyone can revise them."}'},
                        ]
                    )
                )
            )
        # Probe client.
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=_FakeChatCompletions(
                    [
                        {"id": "probe-1", "content": '{"ok":true}'},
                    ]
                )
            )
        )

    monkeypatch.setattr(live_api_playtest, "build_openai_client", _fake_build_openai_client)
    monkeypatch.setattr(live_api_playtest, "get_shared_benchmark_provider_limiter", lambda **_kwargs: _FakeLimiter())
    monkeypatch.setattr(live_api_playtest, "build_json_transport", lambda **_kwargs: SimpleNamespace(invoke_json=lambda **_kwargs: None))

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            helper_gateway_base_url="https://helper.example/v1",
            helper_gateway_api_key="helper-key",
            helper_gateway_model="helper-model",
            gateway_base_url="https://primary.example/v1",
            gateway_api_key="primary-key",
            gateway_model="primary-model",
        ),
        transport_style="chat_completions",
        provider="helper",
    )

    proposed = agent.propose_turn(
        story_detail={"story": {"story_id": "story-1"}, "play_overview": {"target_duration_minutes": 25, "branch_budget": "high"}},
        snapshot={"beat_title": "Manifest Anomaly", "suggested_actions": []},
        transcript=[{"speaker": "gm", "text": "The anomaly is in plain view."}],
    )

    assert proposed["source"] == "llm"
    assert acquire_count["value"] == 3
    assert all(item.get("provider_rate_limit_applied") is True for item in agent.call_trace)


def test_playtest_agent_falls_back_to_primary_when_helper_probe_fails(monkeypatch) -> None:
    captured_client_kwargs: list[dict[str, object]] = []

    class _FakeBenchmarkTransport:
        def invoke_json(self, **_kwargs):
            return live_api_playtest.ResponsesJSONResponse(
                payload={"input_text": "I force the chamber to compare the sealed ledgers in public before anyone can revise them."},
                response_id="resp-primary-1",
                usage={},
                input_characters=10,
                fallback_source=None,
                raw_text='{"input_text":"I force the chamber to compare the sealed ledgers in public before anyone can revise them."}',
            )

    monkeypatch.setattr(
        live_api_playtest,
        "build_openai_client",
        lambda **kwargs: captured_client_kwargs.append(dict(kwargs)) or object(),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "build_json_transport",
        lambda **_kwargs: _FakeBenchmarkTransport(),
    )
    monkeypatch.setattr(
        live_api_playtest.PlaytestAgentClient,
        "_probe_helper_json_schema_capability",
        lambda self: {"supported": False, "elapsed_ms": 12, "error_message": "unsupported response_format json_schema"},
    )
    monkeypatch.setattr(
        live_api_playtest.PlaytestAgentClient,
        "_probe_driver_strategy",
        lambda self: "json_mode_compact_prompt",
    )

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            gateway_base_url="https://primary.example/v1",
            gateway_api_key="primary-key",
            gateway_model="primary-model",
            helper_gateway_base_url="https://helper.example/v1",
            helper_gateway_api_key="helper-key",
            helper_gateway_model="helper-model",
        ),
        transport_style="chat_completions",
        provider="helper",
    )

    assert captured_client_kwargs[0]["base_url"] == "https://helper.example/v1"
    assert captured_client_kwargs[1]["base_url"] == "https://primary.example/v1"
    assert agent._provider == "primary"
    assert any(item["operation_name"] == "playtest_helper_provider_probe" for item in agent.call_trace)
    assert any(item["operation_name"] == "playtest_helper_provider_fallback" for item in agent.call_trace)


def test_playtest_agent_records_failed_turn_trace(monkeypatch) -> None:
    class _FailingBenchmarkTransport:
        def invoke_json(self, **_kwargs):
            raise live_api_playtest._PlaytestAgentError(
                code="playtest_agent_provider_failed",
                message="Request timed out.",
            )

    monkeypatch.setattr(live_api_playtest, "build_openai_client", lambda **_kwargs: object())
    monkeypatch.setattr(live_api_playtest, "build_json_transport", lambda **_kwargs: _FailingBenchmarkTransport())

    agent = live_api_playtest.PlaytestAgentClient(
        live_api_playtest.PERSONAS[0],
        settings=live_api_playtest.Settings(
            gateway_base_url="https://example.com/v1",
            gateway_api_key="test-key",
            gateway_model="gateway-text-model",
            gateway_timeout_seconds_benchmark_driver=90,
        ),
        transport_style="responses",
    )

    proposed = agent.propose_turn(
        story_detail={"play_overview": {"target_duration_minutes": 25, "branch_budget": "high"}},
        snapshot={"beat_title": "The Public Price", "suggested_actions": []},
        transcript=[{"speaker": "gm", "text": "The room hardens around the proof."}],
    )

    assert proposed["source"] == "fallback"
    turn_failure = next(item for item in agent.call_trace if item["operation_name"] == "playtest_turn_assertive_operator")
    salvage_trace = next(item for item in agent.call_trace if item["stage_source"] == "llm_salvage")
    assert turn_failure["capability_context"] == "benchmark_driver.turn_proposal"
    assert turn_failure["stage_source"] == "llm"
    assert turn_failure["persona_id"] == "assertive_operator"
    assert turn_failure["timeout_seconds"] == 90.0
    assert turn_failure["error_code"] == "playtest_agent_provider_failed"
    assert "Request timed out." in str(turn_failure["error_message"])
    assert salvage_trace["stage_source"] == "llm_salvage"


def test_probe_persona_turn_proposal_does_not_submit_turn(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda *args, **kwargs: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_play_session",
        lambda session, base_url, story_id: (
            {
                "session_id": f"{story_id}-session",
                "beat_title": "The Public Price",
                "suggested_actions": [{"label": "Press the room", "prompt": "You press the room for more answers."}],
                "state_bars": [],
                "narration": "You arrive with the evidence and the room turns toward you.",
            },
            0.4,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_submit_play_turn",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("probe should not submit turns")),
    )

    class _FakeAgent:
        def __init__(self, persona, **_kwargs):
            self.persona = persona
            self.call_trace = [{"operation_name": "playtest_turn_assertive_operator"}]
            self.error_distribution = {}
            self.turn_rejection_distribution = {}
            self._driver_strategy = "json_mode_compact_prompt"

        def propose_turn(self, *, story_detail, snapshot, transcript):
            del story_detail, snapshot, transcript
            return {
                "input_text": "I force the chamber to compare the sealed ledgers in public before anyone can revise them.",
                "source": "llm",
                "attempt": 1,
            }

    monkeypatch.setattr(live_api_playtest, "PlaytestAgentClient", _FakeAgent)

    probe = live_api_playtest._probe_persona_turn_proposal(
        base_url="http://bench.local",
        story_detail={
            "story": {"story_id": "story-1"},
            "play_overview": {"target_duration_minutes": 25, "branch_budget": "high"},
        },
        persona=live_api_playtest.PERSONAS[0],
        transport_style="chat_completions",
        use_helper_agent=False,
    )

    assert probe["error"] is None
    assert probe["proposed_turn"]["input_text"].startswith("I force the chamber")
    assert probe["agent_call_trace"]
    assert probe["session_id"] == "story-1-session"


def test_probe_persona_turn_proposal_uses_helper_provider_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda *args, **kwargs: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_play_session",
        lambda session, base_url, story_id: (
            {
                "session_id": f"{story_id}-session",
                "beat_title": "The Public Price",
                "suggested_actions": [],
                "state_bars": [],
                "narration": "You arrive with the evidence and the room turns toward you.",
            },
            0.4,
        ),
    )

    class _FakeAgent:
        def __init__(self, persona, **kwargs):
            self.persona = persona
            self.call_trace = [{"operation_name": "playtest_turn_assertive_operator"}]
            self.error_distribution = {}
            self.turn_rejection_distribution = {}
            self._driver_strategy = "json_mode_compact_prompt"
            self._provider = str(kwargs.get("provider"))

        def propose_turn(self, *, story_detail, snapshot, transcript):
            del story_detail, snapshot, transcript
            return {
                "input_text": "I force the chamber to compare the sealed ledgers in public before anyone can revise them.",
                "source": "llm",
                "attempt": 1,
            }

    monkeypatch.setattr(live_api_playtest, "PlaytestAgentClient", _FakeAgent)

    probe = live_api_playtest._probe_persona_turn_proposal(
        base_url="http://bench.local",
        story_detail={
            "story": {"story_id": "story-1"},
            "play_overview": {"target_duration_minutes": 25, "branch_budget": "high"},
        },
        persona=live_api_playtest.PERSONAS[0],
        transport_style="responses",
        use_helper_agent=True,
    )

    assert probe["error"] is None
    assert probe["agent_provider"] == "helper"


def test_salvage_report_from_raw_text_partially_fills_missing_fields() -> None:
    report = live_api_playtest._salvage_report_from_raw_text(
        raw_text=(
            "Ending: pyrrhic\n"
            "narration_coherence: 4/5\n"
            "state_feedback_distinctness: 5 out of 5\n"
            "Strongest issue: The ending still lands too abruptly.\n"
            "Verdict: Strong session once the pressure finally becomes legible."
        ),
        opening="You arrive with the evidence and the room turns toward you.",
        turns=[
            {
                "turn_index": 1,
                "beat_title": "Opening Pressure",
                "narration_word_count": 88,
                "feedback": {
                    "last_turn_axis_deltas": {"public_panic": 1},
                    "last_turn_stance_deltas": {},
                    "last_turn_consequences": ["Public pressure rose."],
                },
            }
        ],
        final_snapshot={"turn_index": 1, "ending": {"ending_id": "collapse"}},
        forced_stop=False,
    )

    assert report is not None
    assert report["source"] == "llm_salvage_partial"
    assert report["ending_id"] == "pyrrhic"
    assert report["ratings"]["narration_coherence"] == 4
    assert report["ratings"]["state_feedback_distinctness"] == 5
    assert report["ratings"]["content_richness"] >= 2
    assert report["missing_field_distribution"]["content_richness"] == 1
    assert "abruptly" in report["strongest_issue"]


def test_write_artifacts_includes_long_flow_metrics(tmp_path) -> None:
    payload = {
        "base_url": "http://127.0.0.1:8010",
        "phase_id": "longflow",
        "seed_set_id": "seed-set-x",
        "arm": "candidate",
        "target_duration_minutes": 25,
        "configured_content_prompt_profile": "role_conditioned",
        "story_count": 1,
        "personas": ["assertive_operator", "coalition_builder"],
        "stories": [
            {
                "slug": "archive_test",
                "bucket_id": "archive_vote_record",
                "seed": "seed text",
                "turn_budget": 10,
                "job_id": "job-1",
                "result": {"status": "completed"},
                "published_story": {"story_id": "story-1", "title": "Archive Test"},
                "sessions": [
                    {
                        "persona_id": "assertive_operator",
                        "turn_budget": 10,
                        "forced_stop": False,
                        "final_snapshot": {"turn_index": 7, "ending": {"ending_id": "mixed"}},
                        "agent_report": {
                            "ratings": {"content_richness": 4, "state_feedback_distinctness": 4},
                            "strongest_issue": "Late feedback narrowed.",
                        },
                        "late_half_feedback_metrics": {"distinct_axis_count": 2, "distinct_stance_count": 1},
                    }
                ],
            }
        ],
        "scorecard": {
            "passed": True,
            "actuals": {
                "author_publish_success_rate": 1.0,
                "play_completed_sessions": 2,
                "expired_sessions": 0,
                "median_create_session_seconds": 1.2,
                "median_first_submit_turn_seconds": 2.4,
                "p95_submit_turn_seconds": 5.4,
                "render_fallback_rate": 0.0,
                "heuristic_interpret_rate": 0.0,
                "ending_judge_failed_rate": 0.0,
                "judge_nonfallback_rate": 1.0,
                "judge_fallback_rate": 0.0,
                "agent_trace_coverage_rate": 1.0,
                "play_trace_coverage_rate": 1.0,
                "trace_labeled_failure_rate": 1.0,
                "player_identity_confusion_flag_rate": 0.0,
                "flat_state_feedback_flag_rate": 0.0,
                "mean_narration_word_count_per_turn": 88.0,
                "content_richness": 4.2,
                "late_half_axis_diversity_per_session": 1.8,
                "late_half_stance_target_diversity_per_session": 1.2,
                "turn_budget_utilization": 0.7,
                "early_non_collapse_ending_count": 0,
                "late_game_flatness_flag_rate": 0.0,
                "author_total_estimated_cost_rmb": 0.12,
                "play_runtime_total_estimated_cost_rmb": 0.05,
                "benchmark_agent_total_estimated_cost_rmb": 0.03,
                "combined_runtime_total_estimated_cost_rmb": 0.17,
            },
            "subjective_summary": {
                "avg_narration_coherence": 4.5,
                "avg_suggested_action_relevance": 4.0,
                "avg_state_feedback_credibility": 4.0,
                "avg_ending_satisfaction": 4.0,
                "avg_overall_player_feel": 4.0,
            },
        },
    }
    config = live_api_playtest.LiveApiPlaytestConfig(
        base_url="http://127.0.0.1:8010",
        output_dir=tmp_path,
        label="artifact-test",
        launch_server=False,
        session_ttl_seconds=3600,
        max_turns=None,
        seed=7,
        story_count=1,
        phase_id="longflow",
        seed_set_id="seed-set-x",
        arm="candidate",
        baseline_artifact=None,
        managed_server_content_prompt_profile=None,
        target_duration_minutes=25,
        agent_transport_style="chat_completions",
        probe_turn_proposal=False,
    )

    _, md_path = live_api_playtest.write_artifacts(config, payload)
    markdown = md_path.read_text()

    assert "Target duration minutes" in markdown
    assert "Judge non-fallback rate" in markdown
    assert "Trace labeled failure rate" in markdown
    assert "Late-half axis diversity per session" in markdown
    assert "Turn budget utilization" in markdown
    assert "issue=`Late feedback narrowed.`" in markdown


def test_build_scorecard_marks_driver_pollution_when_agent_fallbacks_dominate() -> None:
    stories = [
        {
            "published_story": {"story_id": "story-1"},
            "diagnostics": {"source_summary": {}, "token_cost_estimate": {}},
            "sessions": [
                {
                    "persona_id": "assertive_operator",
                    "create_elapsed_seconds": 1.0,
                    "turn_budget": 4,
                    "turn_budget_utilization": 0.5,
                    "forced_stop": False,
                    "final_snapshot": {"status": "completed", "turn_index": 2, "ending": {"ending_id": "collapse"}},
                    "turns": [
                        {
                            "agent_turn_source": "fallback",
                            "submit_elapsed_seconds": 1.0,
                            "narration_word_count": 50,
                            "feedback": {"last_turn_axis_deltas": {}, "last_turn_stance_deltas": {}, "last_turn_consequences": []},
                        },
                        {
                            "agent_turn_source": "fallback",
                            "submit_elapsed_seconds": 1.0,
                            "narration_word_count": 50,
                            "feedback": {"last_turn_axis_deltas": {}, "last_turn_stance_deltas": {}, "last_turn_consequences": []},
                        },
                    ],
                    "late_half_feedback_metrics": {"distinct_axis_count": 0, "distinct_stance_count": 0},
                    "diagnostics": {"summary": {"render_fallback_turn_count": 0, "heuristic_interpret_turn_count": 0, "ending_judge_source_distribution": {"failed": 0}, "usage_totals": {}}},
                    "agent_report": {"source": "fallback", "flags": [], "ratings": {"content_richness": 3, "state_feedback_distinctness": 3, "narration_coherence": 3, "suggested_action_relevance": 3, "state_feedback_credibility": 3, "ending_satisfaction": 3, "overall_player_feel": 3}},
                    "agent_cost_estimate": None,
                    "agent_error_distribution": {"playtest_agent_invalid_json": 2},
                    "agent_turn_rejection_distribution": {"meta_token": 2},
                    "agent_report_missing_field_distribution": {"content_richness": 1},
                }
            ],
        }
    ]

    scorecard = live_api_playtest._build_scorecard(stories, target_story_count=1, personas_per_story=1)

    assert scorecard["actuals"]["benchmark_agent_turn_llm_rate"] == 0.0
    assert scorecard["actuals"]["benchmark_agent_turn_llm_salvage_rate"] == 0.0
    assert scorecard["actuals"]["benchmark_agent_turn_fallback_rate"] == 1.0
    assert scorecard["actuals"]["benchmark_agent_report_llm_salvage_partial_rate"] == 0.0
    assert scorecard["actuals"]["benchmark_agent_report_fallback_rate"] == 1.0
    assert scorecard["polluted_by_driver"] is True
    assert scorecard["benchmark_agent_turn_rejection_distribution"]["meta_token"] == 2
    assert scorecard["benchmark_agent_report_missing_field_distribution"]["content_richness"] == 1
    assert scorecard["passed"] is False


def test_compare_benchmark_payloads_reports_phase_gates() -> None:
    baseline = {
        "label": "baseline",
        "seed_set_id": "seed-set-b",
        "configured_content_prompt_profile": "plain",
        "scorecard": {
            "target_session_count": 6,
            "actuals": {
                "author_publish_success_rate": 1.0,
                "play_completed_sessions": 6,
                "expired_sessions": 0,
                "p95_submit_turn_seconds": 10.0,
                "heuristic_interpret_rate": 0.0,
                "render_fallback_rate": 0.2,
                "flat_state_feedback_flag_rate": 0.7,
                "axis_diversity_per_session": 1.2,
                "state_feedback_distinctness": 3.0,
                "player_identity_confusion_flag_rate": 0.0,
                "mean_narration_word_count_per_turn": 90.0,
            },
            "ending_distribution": {"collapse": 4, "pyrrhic": 2},
        },
    }
    candidate = {
        "label": "candidate",
        "seed_set_id": "seed-set-b",
        "configured_content_prompt_profile": "role_conditioned",
        "scorecard": {
            "target_session_count": 6,
            "actuals": {
                "author_publish_success_rate": 1.0,
                "play_completed_sessions": 6,
                "expired_sessions": 0,
                "p95_submit_turn_seconds": 11.0,
                "heuristic_interpret_rate": 0.0,
                "render_fallback_rate": 0.1,
                "flat_state_feedback_flag_rate": 0.5,
                "axis_diversity_per_session": 2.2,
                "state_feedback_distinctness": 4.0,
                "player_identity_confusion_flag_rate": 0.0,
                "mean_narration_word_count_per_turn": 95.0,
            },
            "ending_distribution": {"collapse": 3, "pyrrhic": 3},
        },
    }

    compare = live_api_playtest.compare_benchmark_payloads(
        baseline_payload=baseline,
        candidate_payload=candidate,
        phase_id="stage1",
        baseline_artifact="/tmp/baseline.json",
    )

    assert compare["passed"] is True
    assert compare["baseline_content_prompt_profile"] == "plain"
    assert compare["candidate_content_prompt_profile"] == "role_conditioned"
    assert compare["delta_actuals"]["flat_state_feedback_flag_rate"] == -0.2
    assert compare["ending_distribution_shift"]["collapse"] == -1


def test_compare_benchmark_payloads_reports_zh_naturalness_gates() -> None:
    baseline = {
        "label": "baseline",
        "seed_set_id": "zh-seed",
        "configured_content_prompt_profile": "plain",
        "scorecard": {
            "target_session_count": 6,
            "actuals": {
                "author_publish_success_rate": 1.0,
                "play_completed_sessions": 6,
                "expired_sessions": 0,
                "p95_submit_turn_seconds": 10.0,
                "heuristic_interpret_rate": 0.1,
                "render_fallback_rate": 0.0,
                "player_identity_confusion_flag_rate": 0.0,
                "mean_narration_word_count_per_turn": 80.0,
                "state_feedback_distinctness": 4.0,
            },
            "subjective_summary": {
                "avg_narration_coherence": 5.0,
                "avg_suggested_action_relevance": 3.5,
                "avg_state_feedback_credibility": 4.0,
                "avg_overall_player_feel": 3.5,
            },
            "ending_distribution": {"collapse": 2, "pyrrhic": 4},
        },
    }
    candidate = {
        "label": "candidate",
        "seed_set_id": "zh-seed",
        "configured_content_prompt_profile": "role_conditioned",
        "scorecard": {
            "target_session_count": 6,
            "actuals": {
                "author_publish_success_rate": 1.0,
                "play_completed_sessions": 6,
                "expired_sessions": 0,
                "p95_submit_turn_seconds": 9.0,
                "heuristic_interpret_rate": 0.0,
                "render_fallback_rate": 0.0,
                "player_identity_confusion_flag_rate": 0.0,
                "mean_narration_word_count_per_turn": 86.0,
                "state_feedback_distinctness": 4.4,
            },
            "subjective_summary": {
                "avg_narration_coherence": 5.0,
                "avg_suggested_action_relevance": 4.0,
                "avg_state_feedback_credibility": 4.8,
                "avg_overall_player_feel": 4.1,
            },
            "ending_distribution": {"collapse": 1, "pyrrhic": 5},
        },
    }

    compare = live_api_playtest.compare_benchmark_payloads(
        baseline_payload=baseline,
        candidate_payload=candidate,
        phase_id="zh-naturalness",
        baseline_artifact="/tmp/zh-baseline.json",
    )

    assert compare["passed"] is True
    assert compare["delta_subjective_summary"]["avg_suggested_action_relevance"] == 0.5
    gate_status = {item["metric"]: item["passed"] for item in compare["phase_gates"]}
    assert gate_status["reliability_gate"] is True
    assert gate_status["avg_suggested_action_relevance"] is True
    assert gate_status["avg_state_feedback_credibility"] is True
    assert gate_status["avg_overall_player_feel"] is True


def test_normalize_agent_report_removes_inconsistent_flat_state_flag() -> None:
    report = {
        "ending_id": "pyrrhic",
        "turn_count": 4,
        "ratings": {
            "narration_coherence": 5,
            "suggested_action_relevance": 4,
            "state_feedback_credibility": 5,
            "ending_satisfaction": 4,
            "overall_player_feel": 4,
            "protagonist_identity_clarity": 4,
            "content_richness": 4,
            "state_feedback_distinctness": 5,
        },
        "flags": ["flat_state_feedback"],
        "strongest_issue": "Test issue",
        "best_moment": "Test moment",
        "verdict": "Test verdict",
        "source": "llm",
    }
    turns = [
        {
            "feedback": {
                "last_turn_axis_deltas": {"public_panic": 2},
                "last_turn_stance_deltas": {"npc_a": -1},
                "last_turn_consequences": ["Visible public pressure rose.", "At least one relationship took damage."],
            }
        },
        {
            "feedback": {
                "last_turn_axis_deltas": {"political_leverage": 2},
                "last_turn_stance_deltas": {},
                "last_turn_consequences": ["The crisis moved closer to a binding outcome."],
            }
        },
        {
            "feedback": {
                "last_turn_axis_deltas": {"public_panic": -1},
                "last_turn_stance_deltas": {"npc_b": 1},
                "last_turn_consequences": ["Visible public pressure eased.", "A relationship shifted inside the coalition."],
            }
        },
    ]

    normalized = live_api_playtest._normalize_agent_report(report=report, turns=turns)

    assert "flat_state_feedback" not in normalized["flags"]


def test_stage1_smoke_language_runs_spark_preview_author_and_two_turn_play(monkeypatch) -> None:
    observed = {
        "spark_languages": [],
        "preview_languages": [],
        "job_languages": [],
        "play_max_turns": [],
    }

    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_story_spark",
        lambda session, base_url, *, language: (
            observed["spark_languages"].append(language) or {
                "prompt_seed": f"{language}-seed",
                "language": language,
            },
            0.2,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_create_story_preview_with_controls",
        lambda session, base_url, prompt_seed, *, target_duration_minutes, language=None: (
            observed["preview_languages"].append(language) or {
                "preview_id": f"{language}-preview",
                "theme": {"primary_theme": "truth_record_crisis"},
                "strategies": {
                    "story_frame_strategy": "warning_record_story",
                    "cast_strategy": "warning_record_cast",
                    "beat_plan_strategy": "warning_record_compile",
                },
                "story_flow_plan": {
                    "target_duration_minutes": target_duration_minutes,
                    "target_turn_count": 10,
                    "target_beat_count": 5,
                },
                "structure": {"expected_npc_count": 5},
            },
            0.3,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_create_author_job_with_controls",
        lambda session, base_url, prompt_seed, preview_id, *, target_duration_minutes, language=None: (
            observed["job_languages"].append(language) or {"job_id": f"{language}-job"},
            0.4,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_stream_author_job_to_terminal",
        lambda session, base_url, job_id: {"stream_elapsed_seconds": 1.2},
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_author_job_result",
        lambda session, base_url, job_id: ({"status": "completed"}, 0.2),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_author_job",
        lambda session, base_url, job_id: (
            {
                "progress_snapshot": {
                    "stage": "resume_from_preview_checkpoint",
                    "stage_index": 1,
                    "stage_total": 10,
                    "stage_label": "正在勾勒人物关系 · 第 2/4 名角色",
                    "stage_message": "正在生成第 2/4 名角色（制度守门人）。 当前调用：author.cast_member_generate · 已等待 6.4s",
                    "running_node": "generate_cast_members",
                    "running_substage": "slot_generate",
                    "running_slot_index": 2,
                    "running_slot_total": 4,
                    "running_slot_label": "制度守门人",
                    "running_capability": "author.cast_member_generate",
                    "running_elapsed_ms": 6400,
                }
            },
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_author_diagnostics",
        lambda session, base_url, job_id: (
            {
                "llm_call_trace": [{}, {}],
                "quality_trace": [
                    {"stage": "cast_member", "reasons": ["story_instance_materialized"]},
                    {"stage": "cast_member", "reasons": ["story_instance_gender_lock_violation"]},
                ],
                "roster_retrieval_trace": [
                    {"selected_character_id": "roster_archive_vote_certifier", "selected_template_version": "tpl-1"}
                ],
            },
            0.2,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_publish_author_job",
        lambda session, base_url, job_id: ({"story_id": f"{job_id}-story", "title": "Smoke Story"}, 0.2),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: (
            {
                "story": {"story_id": story_id, "title": "Smoke Story"},
                "play_overview": {"max_turns": 10, "target_duration_minutes": 25, "branch_budget": "high"},
            },
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_story_turn_proposal_probes",
        lambda *, base_url, story_detail, transport_style, use_helper_agent: [
            {
                "persona_id": persona.persona_id,
                "propose_turn_elapsed_seconds": 4.2 + index * 0.2,
                "proposed_turn": {"input_text": f"I act as {persona.persona_id}.", "source": "llm", "attempt": 1},
                "agent_call_trace": [{"operation_name": f"playtest_turn_{persona.persona_id}"}],
                "agent_error_distribution": {},
                "error": None,
            }
            for index, persona in enumerate(live_api_playtest.PERSONAS)
        ],
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_story_playtests",
        lambda *, base_url, story_detail, max_turns, transport_style, use_helper_agent: (
            observed["play_max_turns"].append(max_turns) or [
                {
                    "persona_id": persona.persona_id,
                    "turns": [{"narration_word_count": 70 + index}, {"narration_word_count": 72 + index}],
                    "diagnostics": {"summary": {"render_source_distribution": {"llm": 2}, "render_fallback_turn_count": 0}},
                    "error": None,
                }
                for index, persona in enumerate(live_api_playtest.PERSONAS)
            ]
        ),
    )

    result = live_api_playtest._run_stage1_smoke_language(
        session=SimpleNamespace(),
        base_url="http://127.0.0.1:8010",
        language="zh",
        target_duration_minutes=25,
        transport_style="chat_completions",
        use_helper_agent=False,
    )

    assert result["passed"] is True
    assert result["failure_stage"] is None
    assert observed["spark_languages"] == ["zh"]
    assert observed["preview_languages"] == ["zh"]
    assert observed["job_languages"] == ["zh"]
    assert observed["play_max_turns"] == [2]
    assert result["author"]["story_instance_materialized_count"] == 1
    assert result["author"]["gender_lock_violation_count"] == 1
    assert result["author"]["progress_snapshot"]["stage_total"] == 10
    assert result["author"]["progress_snapshot"]["running_slot_index"] == 2
    assert result["author"]["progress_snapshot"]["running_capability"] == "author.cast_member_generate"
    assert result["publish"]["selected_roster_templates"] == [{"character_id": "roster_archive_vote_certifier", "template_version": "tpl-1"}]


def test_stage1_smoke_language_preserves_non_cast_progress_snapshot_details(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_story_spark",
        lambda session, base_url, *, language: ({"prompt_seed": f"{language}-seed", "language": language}, 0.1),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_create_story_preview_with_controls",
        lambda session, base_url, prompt_seed, *, target_duration_minutes, language=None: (
            {
                "preview_id": "preview-1",
                "theme": {"primary_theme": "truth_record_crisis"},
                "strategies": {"story_frame_strategy": "warning_record_story", "cast_strategy": "warning_record_cast", "beat_plan_strategy": "warning_record_compile"},
                "story_flow_plan": {"target_duration_minutes": target_duration_minutes, "target_turn_count": 6, "target_beat_count": 3},
                "structure": {"expected_npc_count": 4},
            },
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_create_author_job_with_controls",
        lambda session, base_url, prompt_seed, preview_id, *, target_duration_minutes, language=None: ({"job_id": "job-1"}, 0.1),
    )
    monkeypatch.setattr(live_api_playtest, "_stream_author_job_to_terminal", lambda session, base_url, job_id: {"stream_elapsed_seconds": 0.5})
    monkeypatch.setattr(
        live_api_playtest,
        "_get_author_job",
        lambda session, base_url, job_id: (
            {
                "progress_snapshot": {
                    "stage": "generate_beat_plan",
                    "stage_index": 4,
                    "stage_total": 10,
                    "stage_label": "正在铺排剧情节拍",
                    "stage_message": "正在把故事推进拆成可游玩的节拍。",
                    "running_node": "generate_beat_plan",
                    "running_substage": "beat_plan_generate",
                    "running_capability": "author.beat_skeleton_generate",
                    "running_elapsed_ms": 3200,
                }
            },
            0.1,
        ),
    )
    monkeypatch.setattr(live_api_playtest, "_get_author_job_result", lambda session, base_url, job_id: ({"status": "completed"}, 0.1))
    monkeypatch.setattr(
        live_api_playtest,
        "_get_author_diagnostics",
        lambda session, base_url, job_id: ({"llm_call_trace": [], "quality_trace": [], "roster_retrieval_trace": []}, 0.1),
    )
    monkeypatch.setattr(live_api_playtest, "_publish_author_job", lambda session, base_url, job_id: ({"story_id": "story-1", "title": "Smoke Story"}, 0.1))
    monkeypatch.setattr(
        live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: ({"story": {"story_id": story_id, "title": "Smoke Story"}, "play_overview": {"max_turns": 6}}, 0.1),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_story_turn_proposal_probes",
        lambda *, base_url, story_detail, transport_style, use_helper_agent: [
            {
                "persona_id": persona.persona_id,
                "proposed_turn": {"input_text": f"I act as {persona.persona_id}."},
                "agent_call_trace": [{}],
                "propose_turn_elapsed_seconds": 1.0 + index * 0.1,
                "error": None,
            }
            for index, persona in enumerate(live_api_playtest.PERSONAS)
        ],
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_story_playtests",
        lambda *, base_url, story_detail, max_turns, transport_style, use_helper_agent: [
            {"persona_id": persona.persona_id, "turns": [{}, {}], "diagnostics": {"summary": {"render_source_distribution": {"llm": 2}}}, "error": None}
            for persona in live_api_playtest.PERSONAS
        ],
    )

    result = live_api_playtest._run_stage1_smoke_language(
        session=SimpleNamespace(),
        base_url="http://127.0.0.1:8010",
        language="zh",
        target_duration_minutes=15,
        transport_style="chat_completions",
        use_helper_agent=False,
    )

    assert result["passed"] is True
    assert result["author"]["progress_snapshot"]["stage_total"] == 10
    assert result["author"]["progress_snapshot"]["running_node"] == "generate_beat_plan"
    assert result["author"]["progress_snapshot"]["running_substage"] == "beat_plan_generate"
    assert result["author"]["progress_snapshot"]["running_capability"] == "author.beat_skeleton_generate"


def test_run_stage1_spark_smoke_aggregates_language_runs(monkeypatch, tmp_path) -> None:
    @contextmanager
    def _noop_server(config, library_db_path):  # noqa: ANN001
        yield

    monkeypatch.setattr(live_api_playtest, "_managed_server", _noop_server)
    monkeypatch.setattr(
        live_api_playtest,
        "_run_stage1_smoke_language",
        lambda *, session, base_url, language, target_duration_minutes, transport_style, use_helper_agent: {
            "language": language,
            "passed": language == "zh",
            "failure_stage": None if language == "zh" else "play_turn",
            "error": None if language == "zh" else "play turn failed",
            "author": {"author_total_elapsed_seconds": 12.4 if language == "zh" else 14.8},
            "play": {"personas": [{"propose_turn_elapsed_seconds": 8.1 if language == "zh" else 9.3}]},
        },
    )

    config = live_api_playtest.LiveApiPlaytestConfig(
        base_url="http://127.0.0.1:8010",
        output_dir=tmp_path,
        label="stage1-smoke-test",
        launch_server=False,
        session_ttl_seconds=3600,
        max_turns=None,
        seed=7,
        story_count=1,
        phase_id="stage1-smoke",
        seed_set_id=None,
        arm="candidate",
        baseline_artifact=None,
        managed_server_content_prompt_profile=None,
        target_duration_minutes=25,
        agent_transport_style="chat_completions",
        probe_turn_proposal=False,
        stage1_spark_smoke=True,
    )
    payload = live_api_playtest.run_stage1_spark_smoke(config)

    assert payload["summary"]["passed"] is False
    assert payload["summary"]["languages_passed"] == 1
    assert payload["summary"]["failure_stage_distribution"]["passed"] == 1
    assert payload["summary"]["failure_stage_distribution"]["play_turn"] == 1
    assert payload["summary"]["max_author_elapsed_seconds"] == 14.8
    assert payload["summary"]["max_propose_turn_elapsed_seconds"] == 9.3

    _, md_path = live_api_playtest.write_stage1_spark_smoke_artifacts(config, payload)
    markdown = md_path.read_text()

    assert "Stage-1 Spark Smoke" in markdown
    assert "Languages passed" in markdown
    assert "play turn failed" in markdown


def test_stage1_smoke_preserves_spark_record_when_preview_fails(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_story_spark",
        lambda session, base_url, *, language: (
            {"prompt_seed": f"{language}-seed", "language": language},
            0.2,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_create_story_preview_with_controls",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("preview exploded")),
    )

    result = live_api_playtest._run_stage1_smoke_language(
        session=SimpleNamespace(),
        base_url="http://127.0.0.1:8010",
        language="en",
        target_duration_minutes=10,
        transport_style="chat_completions",
        use_helper_agent=False,
    )

    assert result["failure_stage"] == "preview"
    assert result["spark"] == {
        "language": "en",
        "prompt_seed": "en-seed",
        "elapsed_seconds": 0.2,
    }
    assert result["preview"] is None


def test_parse_args_supports_play_only_campaign_and_helper_shorthand() -> None:
    config = live_api_playtest.parse_args(
        [
            "--base-url",
            "http://127.0.0.1:8010/",
            "--play-only-campaign",
            "--play-only-story-ids",
            "story-zh,story-en",
            "--target-total-turns",
            "240",
            "--max-sessions-per-cell",
            "6",
            "--play-only-checkpoint-path",
            "/tmp/play_only_checkpoint.json",
            "--resume-from",
            "/tmp/play_only_resume.json",
            "--checkpoint-every-sessions",
            "3",
            "--judge-max-workers",
            "5",
            "--use-helper-agent",
        ]
    )

    assert config.base_url == "http://127.0.0.1:8010"
    assert config.play_only_campaign is True
    assert config.play_only_story_ids == ("story-zh", "story-en")
    assert config.target_total_turns == 240
    assert config.max_sessions_per_cell == 6
    assert config.use_helper_agent is True
    assert config.use_helper_turn_agent is True
    assert config.use_helper_judge is True
    assert str(config.play_only_checkpoint_path).endswith("/tmp/play_only_checkpoint.json")
    assert str(config.resume_from).endswith("/tmp/play_only_resume.json")
    assert config.checkpoint_every_sessions == 3
    assert config.judge_max_workers == 5


def test_run_persona_story_session_splits_proposal_and_judge_agents(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_play_session",
        lambda session, base_url, story_id: (
            {
                "session_id": f"{story_id}-session",
                "status": "active",
                "turn_index": 0,
                "beat_title": "Opening Pressure",
                "narration": "The chamber turns toward you.",
                "suggested_actions": [],
                "state_bars": [],
            },
            0.2,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_submit_play_turn",
        lambda session, base_url, session_id, input_text: (
            {
                "session_id": session_id,
                "status": "completed",
                "turn_index": 1,
                "beat_index": 1,
                "beat_title": "Public Reckoning",
                "narration": f"The room absorbs: {input_text}",
                "feedback": {"last_turn_axis_deltas": {"pressure": 1}, "last_turn_stance_deltas": {}, "last_turn_consequences": ["The room tightens."]},
                "suggested_actions": [],
                "state_bars": [],
                "ending": {"ending_id": "mixed"},
            },
            0.4,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_play_diagnostics",
        lambda session, base_url, session_id: (
            {
                "summary": {
                    "render_source_distribution": {"llm": 1},
                    "render_failure_reason_distribution": {},
                    "interpret_failure_reason_distribution": {},
                    "ending_judge_source_distribution": {"llm": 1},
                },
                "turn_traces": [
                    {
                        "render_source": "llm",
                        "interpret_source": "llm",
                        "ending_judge_source": "llm",
                        "render_failure_reason": None,
                        "interpret_failure_reason": None,
                    }
                ],
            },
            0.1,
        ),
    )

    class _FakeAgent:
        def __init__(self, persona, **kwargs):
            self.persona = persona
            self._provider = str(kwargs.get("provider"))
            self._driver_strategy = f"{self._provider}_strategy"
            self.call_trace = [{"operation_name": f"init_{self._provider}_{persona.persona_id}"}]
            self.error_distribution = {f"{self._provider}_error": 1}
            self.turn_rejection_distribution = {f"{self._provider}_reject": 1}
            self.report_missing_field_distribution = {f"{self._provider}_missing": 1}

        def propose_turn(self, *, story_detail, snapshot, transcript):
            del story_detail, snapshot, transcript
            self.call_trace.append({"operation_name": f"proposal_{self._provider}"})
            return {
                "input_text": "I force the chamber to answer in public.",
                "source": "llm",
                "attempt": 1,
                "turn_stage1_success_count": 1,
                "turn_stage2_rescue_count": 0,
            }

        def build_report(self, *, story_detail, opening, turns, final_snapshot, forced_stop):
            del story_detail, opening, turns, final_snapshot, forced_stop
            self.call_trace.append({"operation_name": f"report_{self._provider}"})
            return {
                "ending_id": "mixed",
                "turn_count": 1,
                "ratings": {
                    "narration_coherence": 4,
                    "suggested_action_relevance": 4,
                    "state_feedback_credibility": 4,
                    "ending_satisfaction": 4,
                    "overall_player_feel": 4,
                    "content_richness": 4,
                    "state_feedback_distinctness": 4,
                },
                "flags": [],
                "strongest_issue": "Pressure could climb faster.",
                "best_moment": "The chamber had to answer.",
                "verdict": "Strong pressure turn.",
                "source": "llm",
                "report_stage1_success": True,
                "report_stage2_rescue": False,
            }

    monkeypatch.setattr(live_api_playtest, "PlaytestAgentClient", _FakeAgent)

    session = live_api_playtest._run_persona_story_session(
        base_url="http://bench.local",
        story_detail={
            "story": {"story_id": "story-1", "title": "Pressure Test", "language": "en"},
            "play_overview": {"target_duration_minutes": 25, "branch_budget": "high", "max_turns": 6},
        },
        persona=live_api_playtest.PERSONAS[0],
        max_turns=2,
        transport_style="chat_completions",
        use_helper_agent=False,
        use_helper_turn_agent=False,
        use_helper_judge=True,
    )

    assert session["proposal_agent_provider"] == "primary"
    assert session["judge_agent_provider"] == "helper"
    assert session["agent_provider_mode"] == "split"
    assert session["agent_provider"] == "primary"
    assert session["proposal_agent_driver_strategy"] == "primary_strategy"
    assert session["judge_agent_driver_strategy"] == "helper_strategy"
    assert session["agent_driver_strategy"] == "primary_strategy"
    assert session["proposal_agent_call_trace"] == [
        {"operation_name": "init_primary_assertive_operator"},
        {"operation_name": "proposal_primary"},
    ]
    assert session["judge_agent_call_trace"] == [
        {"operation_name": "init_helper_assertive_operator"},
        {"operation_name": "report_helper"},
    ]
    assert session["agent_call_trace"] == session["proposal_agent_call_trace"] + session["judge_agent_call_trace"]
    assert session["proposal_agent_error_distribution"] == {"primary_error": 1}
    assert session["judge_agent_error_distribution"] == {"helper_error": 1}
    assert session["agent_error_distribution"] == {"primary_error": 1, "helper_error": 1}
    assert session["proposal_agent_turn_rejection_distribution"] == {"primary_reject": 1}
    assert session["judge_agent_report_missing_field_distribution"] == {"helper_missing": 1}
    assert session["agent_turn_rejection_distribution"] == {"primary_reject": 1}
    assert session["agent_report_missing_field_distribution"] == {"helper_missing": 1}


def test_run_persona_story_capture_session_does_not_call_build_report(monkeypatch) -> None:
    monkeypatch.setattr(live_api_playtest, "_authenticate_session", lambda session, base_url, label: {"authenticated": True})
    monkeypatch.setattr(
        live_api_playtest,
        "_create_play_session",
        lambda session, base_url, story_id: (
            {
                "session_id": f"{story_id}-session",
                "status": "active",
                "turn_index": 0,
                "beat_title": "Opening Pressure",
                "narration": "The chamber turns toward you.",
                "suggested_actions": [],
                "state_bars": [],
            },
            0.2,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_submit_play_turn",
        lambda session, base_url, session_id, input_text: (
            {
                "session_id": session_id,
                "status": "completed",
                "turn_index": 1,
                "beat_index": 1,
                "beat_title": "Public Reckoning",
                "narration": f"The room absorbs: {input_text}",
                "feedback": {"last_turn_axis_deltas": {"pressure": 1}, "last_turn_stance_deltas": {}, "last_turn_consequences": ["The room tightens."]},
                "suggested_actions": [],
                "state_bars": [],
                "ending": {"ending_id": "mixed"},
            },
            0.4,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_play_diagnostics",
        lambda session, base_url, session_id: (
            {
                "summary": {
                    "render_source_distribution": {"llm": 1},
                    "render_failure_reason_distribution": {},
                    "interpret_failure_reason_distribution": {},
                    "ending_judge_source_distribution": {"llm": 1},
                },
                "turn_traces": [
                    {
                        "render_source": "llm",
                        "interpret_source": "llm",
                        "ending_judge_source": "llm",
                    }
                ],
            },
            0.1,
        ),
    )

    class _FakeAgent:
        def __init__(self, persona, **kwargs):
            self.persona = persona
            self._provider = str(kwargs.get("provider"))
            self._driver_strategy = f"{self._provider}_strategy"
            self.call_trace = [{"operation_name": f"init_{self._provider}_{persona.persona_id}"}]
            self.error_distribution = {}
            self.turn_rejection_distribution = {}
            self.report_missing_field_distribution = {}

        def propose_turn(self, *, story_detail, snapshot, transcript):
            del story_detail, snapshot, transcript
            self.call_trace.append({"operation_name": f"proposal_{self._provider}"})
            return {
                "input_text": "I force the chamber to answer in public.",
                "source": "llm",
                "attempt": 1,
                "turn_stage1_success_count": 1,
                "turn_stage2_rescue_count": 0,
            }

        def build_report(self, *, story_detail, opening, turns, final_snapshot, forced_stop):
            raise AssertionError("capture runner must not call build_report")

    monkeypatch.setattr(live_api_playtest, "PlaytestAgentClient", _FakeAgent)

    session = live_api_playtest._run_persona_story_capture_session(
        base_url="http://bench.local",
        story_detail={
            "story": {"story_id": "story-1", "title": "Pressure Test", "language": "en"},
            "play_overview": {"target_duration_minutes": 25, "branch_budget": "high", "max_turns": 6},
        },
        persona=live_api_playtest.PERSONAS[0],
        max_turns=2,
        transport_style="chat_completions",
        use_helper_agent=False,
        use_helper_turn_agent=False,
        use_helper_judge=True,
    )

    assert session["proposal_agent_provider"] == "primary"
    assert session["judge_agent_provider_requested"] == "helper"
    assert session["judge_agent_provider"] == "pending"
    assert session["judge_status"] == "pending"
    assert session["agent_report"]["source"] == "pending"
    assert session["judge_agent_call_trace"] == []
    assert session["agent_call_trace"] == session["proposal_agent_call_trace"]


def test_run_play_only_campaign_skips_author_generation_and_uses_existing_story_details(monkeypatch, tmp_path) -> None:
    @contextmanager
    def _noop_server(config, library_db_path):  # noqa: ANN001
        yield

    observed_story_ids: list[str] = []
    judged_sessions: list[str] = []

    monkeypatch.setattr(live_api_playtest, "_managed_server", _noop_server)
    monkeypatch.setattr(
        live_api_playtest,
        "_run_author_story",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("author flow should not run in play-only mode")),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: (
            observed_story_ids.append(story_id) or {
                "story": {
                    "story_id": story_id,
                    "title": f"Story {story_id}",
                    "language": "zh" if story_id.endswith("zh") else "en",
                },
                "play_overview": {"max_turns": 6, "target_duration_minutes": 25, "branch_budget": "high"},
            },
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_persona_story_capture_session_with_retry",
        lambda **kwargs: {
            "story_id": kwargs["story_detail"]["story"]["story_id"],
            "story_title": kwargs["story_detail"]["story"]["title"],
            "story_language": kwargs["story_detail"]["story"]["language"],
            "persona_id": kwargs["persona"].persona_id,
            "persona_label": kwargs["persona"].label,
            "session_id": f"{kwargs['story_detail']['story']['story_id']}-{kwargs['persona'].persona_id}-session",
            "turn_budget": kwargs["max_turns"],
            "turn_budget_utilization": 0.5,
            "create_elapsed_seconds": 0.2,
            "forced_stop": False,
            "opening": "Opening narration.",
            "final_snapshot": {"status": "completed", "turn_index": 1, "ending": {"ending_id": "mixed"}},
            "turns": [
                {
                    "turn_index": 1,
                    "input_text": "I act.",
                    "agent_turn_source": "llm",
                    "submit_elapsed_seconds": 0.4,
                    "narration": "A clean narrated response.",
                    "narration_word_count": 4,
                    "feedback": {"last_turn_axis_deltas": {"pressure": 1}, "last_turn_stance_deltas": {}, "last_turn_consequences": ["Pressure rises."]},
                }
            ],
            "feedback_metrics": {"distinct_axis_count": 1, "distinct_stance_count": 0, "distinct_consequence_count": 1, "nonzero_feedback_turns": 1},
            "late_half_feedback_metrics": {"distinct_axis_count": 1, "distinct_stance_count": 0, "distinct_consequence_count": 1, "nonzero_feedback_turns": 1},
            "diagnostics": {
                "summary": {
                    "render_source_distribution": {"llm": 1},
                    "render_failure_reason_distribution": {},
                    "interpret_failure_reason_distribution": {},
                    "ending_judge_source_distribution": {"llm": 1},
                },
                "turn_traces": [{"render_source": "llm", "interpret_source": "llm", "ending_judge_source": "llm"}],
            },
            "diagnostics_elapsed_seconds": 0.1,
            "agent_report": {
                "ratings": {
                    "narration_coherence": 0,
                    "suggested_action_relevance": 0,
                    "state_feedback_credibility": 0,
                    "ending_satisfaction": 0,
                    "overall_player_feel": 0,
                    "content_richness": 0,
                    "state_feedback_distinctness": 0,
                },
                "flags": [],
                "strongest_issue": "Pending helper judge.",
                "best_moment": "Pending helper judge.",
                "verdict": "Helper judge has not run yet.",
                "source": "pending",
            },
            "agent_cache_metrics": {},
            "agent_cost_estimate": None,
            "proposal_agent_provider": "primary",
            "judge_agent_provider_requested": "helper",
            "judge_agent_provider": "pending",
            "agent_provider_mode": "split",
            "proposal_agent_call_trace": [{"operation_name": "proposal"}],
            "judge_agent_call_trace": [],
            "agent_call_trace": [{"operation_name": "proposal"}],
            "proposal_agent_error_distribution": {},
            "judge_agent_error_distribution": {},
            "agent_error_distribution": {},
            "proposal_agent_turn_rejection_distribution": {},
            "agent_turn_rejection_distribution": {},
            "judge_agent_report_missing_field_distribution": {},
            "agent_report_missing_field_distribution": {},
            "agent_turn_max_output_tokens": 260,
            "agent_report_max_output_tokens": 420,
            "agent_transcript_window_entries": 8,
            "agent_turn_stage1_success_count": 1,
            "agent_turn_stage2_rescue_count": 0,
            "agent_report_stage1_success": False,
            "agent_report_stage2_rescue": False,
            "proposal_agent_driver_strategy": "primary_strategy",
            "judge_agent_driver_strategy": "pending",
            "agent_driver_strategy": "primary_strategy",
            "agent_provider": "primary",
            "judge_status": "pending",
            "judge_started_at": None,
            "judge_completed_at": None,
            "judge_elapsed_seconds": None,
            "judge_error": None,
            "error": None,
        },
    )
    def _fake_judge_phase(*, config, story_records, cell_session_counts, completed_turn_count, checkpoint_json_path, checkpoint_md_path):  # noqa: ANN001
        del config, cell_session_counts, completed_turn_count, checkpoint_json_path, checkpoint_md_path
        for record in story_records:
            for session in record["sessions"]:
                judged_sessions.append(str(session["session_id"]))
                session["agent_report"] = {
                    "ratings": {
                        "narration_coherence": 4,
                        "suggested_action_relevance": 4,
                        "state_feedback_credibility": 4,
                        "ending_satisfaction": 4,
                        "overall_player_feel": 4,
                        "content_richness": 4,
                        "state_feedback_distinctness": 4,
                    },
                    "flags": [],
                    "strongest_issue": "None",
                    "best_moment": "The first turn landed.",
                    "verdict": "Stable run.",
                    "source": "llm",
                }
                session["judge_agent_provider"] = "helper"
                session["judge_agent_call_trace"] = [{"operation_name": "judge"}]
                session["agent_call_trace"] = list(session["proposal_agent_call_trace"]) + list(session["judge_agent_call_trace"])
                session["judge_status"] = "completed"
                session["judge_completed_at"] = "2026-03-28T00:00:00+00:00"
                session["judge_elapsed_seconds"] = 1.2
                session["judge_error"] = None
                session["judge_agent_driver_strategy"] = "helper_strategy"
                session["agent_report_stage1_success"] = True

    monkeypatch.setattr(live_api_playtest, "_run_play_only_judge_phase", _fake_judge_phase)

    payload = live_api_playtest.run_play_only_campaign(
        live_api_playtest.LiveApiPlaytestConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            label="play-only",
            launch_server=False,
            session_ttl_seconds=3600,
            max_turns=None,
            seed=7,
            story_count=1,
            phase_id=None,
            seed_set_id=None,
            arm="candidate",
            baseline_artifact=None,
            managed_server_content_prompt_profile=None,
            target_duration_minutes=25,
            probe_turn_proposal=False,
            agent_transport_style="chat_completions",
            play_only_campaign=True,
            play_only_story_ids=("story-zh", "story-en"),
            target_total_turns=999,
            max_sessions_per_cell=1,
            use_helper_judge=True,
        )
    )

    assert observed_story_ids == ["story-zh", "story-en"]
    assert payload["story_count"] == 2
    assert payload["session_count"] == len(live_api_playtest.PERSONAS) * 2
    assert len(judged_sessions) == len(live_api_playtest.PERSONAS) * 2
    assert payload["proposal_metrics"]["provider_distribution"] == {"primary": 10}
    assert payload["judge_metrics"]["provider_distribution"] == {"helper": 10}
    assert payload["agent_provider_mode_distribution"] == {"split": 10}
    assert sorted(payload["per_language"].keys()) == ["en", "zh"]
    assert all(count == 1 for count in payload["cell_session_counts"].values())
    assert payload["capture_status"] == "completed"
    assert payload["judge_status"] == "completed"
    assert payload["progress"]["judge_pending_sessions"] == 0


def test_run_play_only_campaign_stops_on_target_total_turns(monkeypatch, tmp_path) -> None:
    @contextmanager
    def _noop_server(config, library_db_path):  # noqa: ANN001
        yield

    monkeypatch.setattr(live_api_playtest, "_managed_server", _noop_server)
    monkeypatch.setattr(
        live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: (
            {
                "story": {"story_id": story_id, "title": "Target Story", "language": "en"},
                "play_overview": {"max_turns": 6, "target_duration_minutes": 25, "branch_budget": "high"},
            },
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_persona_story_capture_session_with_retry",
        lambda **kwargs: {
            "story_id": kwargs["story_detail"]["story"]["story_id"],
            "story_title": kwargs["story_detail"]["story"]["title"],
            "story_language": "en",
            "persona_id": kwargs["persona"].persona_id,
            "persona_label": kwargs["persona"].label,
            "session_id": f"{kwargs['persona'].persona_id}-session",
            "turn_budget": kwargs["max_turns"],
            "turn_budget_utilization": 0.5,
            "create_elapsed_seconds": 0.2,
            "forced_stop": False,
            "opening": "Opening narration.",
            "final_snapshot": {"status": "completed", "turn_index": 2, "ending": {"ending_id": "mixed"}},
            "turns": [
                {
                    "turn_index": 1,
                    "input_text": "First move.",
                    "agent_turn_source": "llm",
                    "submit_elapsed_seconds": 0.4,
                    "narration": "First narrated response.",
                    "narration_word_count": 3,
                    "feedback": {"last_turn_axis_deltas": {"pressure": 1}, "last_turn_stance_deltas": {}, "last_turn_consequences": ["Pressure rises."]},
                },
                {
                    "turn_index": 2,
                    "input_text": "Second move.",
                    "agent_turn_source": "llm",
                    "submit_elapsed_seconds": 0.5,
                    "narration": "Second narrated response.",
                    "narration_word_count": 3,
                    "feedback": {"last_turn_axis_deltas": {"pressure": 1}, "last_turn_stance_deltas": {}, "last_turn_consequences": ["Pressure rises again."]},
                },
            ],
            "feedback_metrics": {"distinct_axis_count": 1, "distinct_stance_count": 0, "distinct_consequence_count": 2, "nonzero_feedback_turns": 2},
            "late_half_feedback_metrics": {"distinct_axis_count": 1, "distinct_stance_count": 0, "distinct_consequence_count": 1, "nonzero_feedback_turns": 1},
            "diagnostics": {
                "summary": {
                    "render_source_distribution": {"llm": 2},
                    "render_failure_reason_distribution": {},
                    "interpret_failure_reason_distribution": {},
                    "ending_judge_source_distribution": {"llm": 2},
                },
                "turn_traces": [
                    {"render_source": "llm", "interpret_source": "llm", "ending_judge_source": "llm"},
                    {"render_source": "llm", "interpret_source": "llm", "ending_judge_source": "llm"},
                ],
            },
            "diagnostics_elapsed_seconds": 0.1,
            "agent_report": {
                "ratings": {
                    "narration_coherence": 0,
                    "suggested_action_relevance": 0,
                    "state_feedback_credibility": 0,
                    "ending_satisfaction": 0,
                    "overall_player_feel": 0,
                    "content_richness": 0,
                    "state_feedback_distinctness": 0,
                },
                "flags": [],
                "strongest_issue": "Pending helper judge.",
                "best_moment": "Pending helper judge.",
                "verdict": "Helper judge has not run yet.",
                "source": "pending",
            },
            "agent_cache_metrics": {},
            "agent_cost_estimate": None,
            "proposal_agent_provider": "primary",
            "judge_agent_provider_requested": "primary",
            "judge_agent_provider": "pending",
            "agent_provider_mode": "shared",
            "proposal_agent_call_trace": [{"operation_name": "proposal"}],
            "judge_agent_call_trace": [],
            "agent_call_trace": [{"operation_name": "proposal"}],
            "proposal_agent_error_distribution": {},
            "judge_agent_error_distribution": {},
            "agent_error_distribution": {},
            "proposal_agent_turn_rejection_distribution": {},
            "agent_turn_rejection_distribution": {},
            "judge_agent_report_missing_field_distribution": {},
            "agent_report_missing_field_distribution": {},
            "agent_turn_max_output_tokens": 260,
            "agent_report_max_output_tokens": 420,
            "agent_transcript_window_entries": 8,
            "agent_turn_stage1_success_count": 2,
            "agent_turn_stage2_rescue_count": 0,
            "agent_report_stage1_success": False,
            "agent_report_stage2_rescue": False,
            "proposal_agent_driver_strategy": "primary_strategy",
            "judge_agent_driver_strategy": "pending",
            "agent_driver_strategy": "primary_strategy",
            "agent_provider": "primary",
            "judge_status": "pending",
            "judge_started_at": None,
            "judge_completed_at": None,
            "judge_elapsed_seconds": None,
            "judge_error": None,
            "error": None,
        },
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_play_only_judge_phase",
        lambda **kwargs: None,
    )

    payload = live_api_playtest.run_play_only_campaign(
        live_api_playtest.LiveApiPlaytestConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            label="play-only-target-stop",
            launch_server=False,
            session_ttl_seconds=3600,
            max_turns=None,
            seed=7,
            story_count=1,
            phase_id=None,
            seed_set_id=None,
            arm="candidate",
            baseline_artifact=None,
            managed_server_content_prompt_profile=None,
            target_duration_minutes=25,
            probe_turn_proposal=False,
            agent_transport_style="chat_completions",
            play_only_campaign=True,
            play_only_story_ids=("story-en",),
            target_total_turns=4,
            max_sessions_per_cell=6,
        )
    )

    assert payload["completed_turn_count"] == 4
    assert payload["session_count"] == 2
    assert sum(payload["cell_session_counts"].values()) == 2
    assert payload["progress"]["judge_pending_sessions"] == 2


def test_run_play_only_campaign_can_resume_from_checkpoint(monkeypatch, tmp_path) -> None:
    @contextmanager
    def _noop_server(config, library_db_path):  # noqa: ANN001
        yield

    checkpoint_path = tmp_path / "play_only_resume.json"
    persona = live_api_playtest.PERSONAS[0]
    checkpoint_payload = {
        "mode": "play_only_campaign",
        "run_status": "capture_completed",
        "capture_status": "completed",
        "judge_status": "pending",
        "base_url": "http://127.0.0.1:8010",
        "fixed_story_pool": [
            {
                "story_id": "story-en",
                "title": "Checkpoint Story",
                "language": "en",
                "turn_budget": 6,
                "target_duration_minutes": 25,
                "branch_budget": "high",
            }
        ],
        "stories": [
            {
                "story_id": "story-en",
                "title": "Checkpoint Story",
                "language": "en",
                "turn_budget": 6,
                "story_fetch_elapsed_seconds": 0.1,
                "play_overview": {"max_turns": 6, "target_duration_minutes": 25, "branch_budget": "high"},
                "sessions": [
                    {
                        "story_id": "story-en",
                        "story_title": "Checkpoint Story",
                        "story_language": "en",
                        "persona_id": persona.persona_id,
                        "persona_label": persona.label,
                        "session_id": "existing-session",
                        "cell_session_index": 1,
                        "turn_budget": 6,
                        "turn_budget_utilization": 0.2,
                        "create_elapsed_seconds": 0.2,
                        "forced_stop": False,
                        "opening": "Opening narration.",
                        "final_snapshot": {"status": "completed", "turn_index": 1, "ending": {"ending_id": "mixed"}},
                        "turns": [
                            {
                                "turn_index": 1,
                                "input_text": "Existing move.",
                                "agent_turn_source": "llm",
                                "submit_elapsed_seconds": 0.4,
                                "narration": "Existing narrated response.",
                                "narration_word_count": 3,
                                "feedback": {"last_turn_axis_deltas": {"pressure": 1}, "last_turn_stance_deltas": {}, "last_turn_consequences": ["Pressure rises."]},
                            }
                        ],
                        "feedback_metrics": {},
                        "late_half_feedback_metrics": {},
                        "diagnostics": {
                            "summary": {
                                "render_source_distribution": {"llm": 1},
                                "render_failure_reason_distribution": {},
                                "interpret_failure_reason_distribution": {},
                                "ending_judge_source_distribution": {"llm": 1},
                            },
                            "turn_traces": [{"render_source": "llm", "interpret_source": "llm", "ending_judge_source": "llm"}],
                        },
                        "diagnostics_elapsed_seconds": 0.1,
                        "agent_report": {
                            "ratings": {
                                "narration_coherence": 0,
                                "suggested_action_relevance": 0,
                                "state_feedback_credibility": 0,
                                "ending_satisfaction": 0,
                                "overall_player_feel": 0,
                                "content_richness": 0,
                                "state_feedback_distinctness": 0,
                            },
                            "flags": [],
                            "strongest_issue": "Pending helper judge.",
                            "best_moment": "Pending helper judge.",
                            "verdict": "Helper judge has not run yet.",
                            "source": "pending",
                        },
                        "agent_cache_metrics": {},
                        "agent_cost_estimate": None,
                        "proposal_agent_provider": "primary",
                        "judge_agent_provider_requested": "helper",
                        "judge_agent_provider": "pending",
                        "agent_provider_mode": "split",
                        "proposal_agent_call_trace": [{"operation_name": "proposal"}],
                        "judge_agent_call_trace": [],
                        "agent_call_trace": [{"operation_name": "proposal"}],
                        "proposal_agent_error_distribution": {},
                        "judge_agent_error_distribution": {},
                        "agent_error_distribution": {},
                        "proposal_agent_turn_rejection_distribution": {},
                        "agent_turn_rejection_distribution": {},
                        "judge_agent_report_missing_field_distribution": {},
                        "agent_report_missing_field_distribution": {},
                        "agent_turn_max_output_tokens": 260,
                        "agent_report_max_output_tokens": 420,
                        "agent_transcript_window_entries": 8,
                        "agent_turn_stage1_success_count": 1,
                        "agent_turn_stage2_rescue_count": 0,
                        "agent_report_stage1_success": False,
                        "agent_report_stage2_rescue": False,
                        "proposal_agent_driver_strategy": "primary_strategy",
                        "judge_agent_driver_strategy": "pending",
                        "agent_driver_strategy": "primary_strategy",
                        "agent_provider": "primary",
                        "judge_status": "pending",
                        "judge_started_at": None,
                        "judge_completed_at": None,
                        "judge_elapsed_seconds": None,
                        "judge_error": None,
                        "error": None,
                    }
                ],
            }
        ],
        "cell_session_counts": {f"story-en::{persona.persona_id}": 1},
        "completed_turn_count": 1,
    }
    checkpoint_path.write_text(json.dumps(checkpoint_payload, ensure_ascii=False, indent=2))

    observed_story_ids: list[str] = []
    capture_calls: list[str] = []
    judged_sessions: list[str] = []

    monkeypatch.setattr(live_api_playtest, "_managed_server", _noop_server)
    monkeypatch.setattr(
        live_api_playtest,
        "_get_story_detail",
        lambda session, base_url, story_id: (
            observed_story_ids.append(story_id) or {
                "story": {"story_id": story_id, "title": "Checkpoint Story", "language": "en"},
                "play_overview": {"max_turns": 6, "target_duration_minutes": 25, "branch_budget": "high"},
            },
            0.1,
        ),
    )
    monkeypatch.setattr(
        live_api_playtest,
        "_run_persona_story_capture_session_with_retry",
        lambda **kwargs: capture_calls.append(kwargs["persona"].persona_id) or (_ for _ in ()).throw(AssertionError("resume should skip capture phase")),
    )
    def _fake_judge_phase(*, config, story_records, cell_session_counts, completed_turn_count, checkpoint_json_path, checkpoint_md_path):  # noqa: ANN001
        del config, cell_session_counts, completed_turn_count, checkpoint_json_path, checkpoint_md_path
        for record in story_records:
            for session in record["sessions"]:
                judged_sessions.append(str(session["session_id"]))
                session["agent_report"] = {
                    "ratings": {
                        "narration_coherence": 4,
                        "suggested_action_relevance": 4,
                        "state_feedback_credibility": 4,
                        "ending_satisfaction": 4,
                        "overall_player_feel": 4,
                        "content_richness": 4,
                        "state_feedback_distinctness": 4,
                    },
                    "flags": [],
                    "strongest_issue": "None",
                    "best_moment": "Existing move landed.",
                    "verdict": "Stable run.",
                    "source": "llm",
                }
                session["judge_agent_provider"] = "helper"
                session["judge_agent_call_trace"] = [{"operation_name": "judge"}]
                session["agent_call_trace"] = list(session["proposal_agent_call_trace"]) + list(session["judge_agent_call_trace"])
                session["judge_status"] = "completed"
                session["judge_completed_at"] = "2026-03-28T00:00:00+00:00"
                session["judge_elapsed_seconds"] = 1.0
                session["judge_error"] = None
                session["judge_agent_driver_strategy"] = "helper_strategy"
                session["agent_report_stage1_success"] = True

    monkeypatch.setattr(live_api_playtest, "_run_play_only_judge_phase", _fake_judge_phase)

    payload = live_api_playtest.run_play_only_campaign(
        live_api_playtest.LiveApiPlaytestConfig(
            base_url="http://127.0.0.1:8010",
            output_dir=tmp_path,
            label="play-only-resume",
            launch_server=False,
            session_ttl_seconds=3600,
            max_turns=None,
            seed=7,
            story_count=1,
            phase_id=None,
            seed_set_id=None,
            arm="candidate",
            baseline_artifact=None,
            managed_server_content_prompt_profile=None,
            target_duration_minutes=25,
            probe_turn_proposal=False,
            agent_transport_style="chat_completions",
            play_only_campaign=True,
            target_total_turns=1,
            max_sessions_per_cell=1,
            use_helper_judge=True,
            resume_from=checkpoint_path,
        )
    )

    assert observed_story_ids == ["story-en"]
    assert capture_calls == []
    assert judged_sessions == ["existing-session"]
    assert payload["completed_turn_count"] == 1
    assert payload["capture_status"] == "completed"
    assert payload["judge_status"] == "completed"
    assert payload["resumed_from"] == str(checkpoint_path)
    updated_checkpoint = json.loads(checkpoint_path.read_text())
    assert updated_checkpoint["completed_turn_count"] == 1
    assert updated_checkpoint["run_status"] == "completed"
    assert updated_checkpoint["capture_status"] == "completed"
    assert updated_checkpoint["judge_status"] == "completed"
    assert checkpoint_path.with_suffix(".md").exists()


def test_build_play_only_trace_eval_classifies_expected_buckets() -> None:
    trace_eval = live_api_playtest._build_play_only_trace_eval(
        [
            {
                "story_id": "story-1",
                "story_language": "en",
                "persona_id": "assertive_operator",
                "session_id": "session-1",
                "turns": [
                    {"turn_index": 1, "narration": "Scene reaction spills into labels.", "agent_turn_source": "llm", "feedback": {}},
                    {"turn_index": 2, "narration": "The scene resolves but misses the anchor.", "agent_turn_source": "llm", "feedback": {}},
                    {"turn_index": 3, "narration": "Repair still collapses.", "agent_turn_source": "llm", "feedback": {}},
                    {"turn_index": 4, "narration": "这是中文污染 mixed language leak persists here.", "agent_turn_source": "llm", "feedback": {}},
                ],
                "diagnostics": {
                    "summary": {
                        "render_source_distribution": {"llm": 2, "llm_repair": 1, "fallback": 1},
                        "render_failure_reason_distribution": {"scene_plan_missing": 1},
                        "interpret_failure_reason_distribution": {},
                        "ending_judge_source_distribution": {"llm": 4},
                    },
                    "turn_traces": [
                        {
                            "render_source": "llm_repair",
                            "interpret_source": "llm",
                            "ending_judge_source": "llm",
                            "render_primary_failure_reason": "scene_plan_missing",
                            "render_primary_fallback_source": "plaintext_salvage",
                            "render_primary_raw_excerpt": "SCENE_REACTION: The chamber hardens. AXIS_PAYOFF: Pressure spikes.",
                        },
                        {
                            "render_source": "llm_repair",
                            "interpret_source": "llm",
                            "ending_judge_source": "llm",
                            "render_quality_reason_before_repair": "missing_state_payoff",
                        },
                        {
                            "render_source": "fallback",
                            "interpret_source": "llm",
                            "ending_judge_source": "llm",
                            "render_repair_failure_reason": "play_llm_invalid_json",
                        },
                        {
                            "render_source": "llm",
                            "interpret_source": "llm",
                            "ending_judge_source": "llm",
                        },
                    ],
                },
            }
        ]
    )

    assert trace_eval["trace_issue_distribution"]["stage1_plan_protocol_mismatch"] == 1
    assert trace_eval["trace_issue_distribution"]["quality_gate_rejection"] == 1
    assert trace_eval["trace_issue_distribution"]["repair_instability"] == 1
    assert trace_eval["trace_issue_distribution"]["language_contamination"] == 1
    assert "stage1_plan_protocol_mismatch" in trace_eval["representative_excerpts"]


def test_write_play_only_campaign_artifacts_includes_trace_eval_sections(tmp_path) -> None:
    config = live_api_playtest.LiveApiPlaytestConfig(
        base_url="http://127.0.0.1:8010",
        output_dir=tmp_path,
        label="play-only-writer",
        launch_server=False,
        session_ttl_seconds=3600,
        max_turns=None,
        seed=7,
        story_count=1,
        phase_id=None,
        seed_set_id=None,
        arm="candidate",
        baseline_artifact=None,
        managed_server_content_prompt_profile=None,
        target_duration_minutes=25,
        probe_turn_proposal=False,
        agent_transport_style="chat_completions",
        play_only_campaign=True,
        play_only_story_ids=("story-en",),
        use_helper_judge=True,
    )
    payload = {
        "base_url": "http://127.0.0.1:8010",
        "agent_transport_style": "chat_completions",
        "run_config": {
            "target_total_turns": 240,
            "proposal_provider_requested": "primary",
            "judge_provider_requested": "helper",
        },
        "completed_turn_count": 220,
        "session_count": 12,
        "completed_session_count": 10,
        "proposal_metrics": {
            "provider_distribution": {"primary": 12},
            "turn_source_distribution": {"llm": 220},
            "stage1_success_rate": 0.92,
            "stage2_rescue_rate": 0.06,
        },
        "judge_metrics": {
            "provider_distribution": {"helper": 12},
            "report_source_distribution": {"llm": 10, "fallback": 2},
            "judge_nonfallback_rate": 0.833,
            "judge_fallback_rate": 0.167,
        },
        "trace_eval": {
            "empty_narration_rate": 0.0,
            "issue_turn_rate": 0.08,
            "trace_issue_distribution": {"stage1_plan_protocol_mismatch": 8, "repair_instability": 4},
            "representative_excerpts": {
                "stage1_plan_protocol_mismatch": [
                    {"story_id": "story-en", "persona_id": "assertive_operator", "turn_index": 3, "excerpt": "SCENE_REACTION leaked."}
                ]
            },
        },
        "per_language": {
            "en": {
                "turn_count": 110,
                "session_count": 6,
                "empty_narration_rate": 0.0,
                "issue_turn_rate": 0.07,
                "trace_issue_distribution": {"stage1_plan_protocol_mismatch": 5},
            },
            "zh": {
                "turn_count": 110,
                "session_count": 6,
                "empty_narration_rate": 0.0,
                "issue_turn_rate": 0.09,
                "trace_issue_distribution": {"repair_instability": 4},
            },
        },
        "follow_up_recommendations": ["Tighten stage-1 JSON-only output."],
        "verdict": {"passed": True},
    }

    _, md_path = live_api_playtest.write_play_only_campaign_artifacts(config, payload)
    markdown = md_path.read_text()

    assert "Play-Only Pressure Campaign" in markdown
    assert "Failure Rate Table" in markdown
    assert "Per-Language Split" in markdown
    assert "Top Issue Clusters" in markdown
    assert "Follow-Up Recommendations" in markdown

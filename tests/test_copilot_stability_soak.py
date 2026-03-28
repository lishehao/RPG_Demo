from __future__ import annotations

from random import Random

from tools.copilot_prompt_factory import build_copilot_prompt_batch
from tools.copilot_stability_soak import (
    CopilotStabilitySoakConfig,
    build_story_specs,
    run_copilot_stability_soak,
    _run_prompt_trial,
)


def _config(**overrides):
    base = CopilotStabilitySoakConfig(
        base_url="http://smoke.local",
        output_dir=__import__("pathlib").Path("artifacts/copilot_soak"),
        story_count=5,
        prompt_count_per_story=40,
        language_mix="both",
        seed=7,
        poll_interval_seconds=0.05,
        poll_timeout_seconds=1.0,
        request_timeout_seconds=1.0,
        include_benchmark_diagnostics=False,
        sample_full_chain_count_per_story=1,
    )
    return base.__class__(**{**base.__dict__, **overrides})


def test_build_story_specs_defaults_to_three_en_two_zh_for_five_story_mix() -> None:
    specs = build_story_specs(rng=Random(7), story_count=5, language_mix="both")

    assert len(specs) == 5
    assert sum(1 for item in specs if item.language == "en") == 3
    assert sum(1 for item in specs if item.language == "zh") == 2


def test_build_copilot_prompt_batch_generates_en_and_zh_prompts_with_reasonable_variety() -> None:
    en_prompts = build_copilot_prompt_batch(rng=Random(3), language="en", prompt_count=40)
    zh_prompts = build_copilot_prompt_batch(rng=Random(5), language="zh", prompt_count=40)

    assert len(en_prompts) == 40
    assert len(zh_prompts) == 40
    assert len({item.prompt_text for item in en_prompts}) >= 20
    assert len({item.prompt_text for item in zh_prompts}) >= 20
    assert len({family for item in en_prompts for family in item.families}) == 8
    assert len({family for item in zh_prompts for family in item.families}) == 8


def test_run_prompt_trial_creates_fresh_session_and_never_applies(monkeypatch) -> None:
    seen_urls: list[str] = []
    story_record = {
        "job_id": "job-1",
        "story_key": "en_story_01",
        "story_language": "en",
        "editor_state": {
            "play_profile_view": {
                "runtime_profile": "archive_vote_play",
                "closeout_profile": "record_exposure_closeout",
                "max_turns": 4,
            }
        },
    }
    prompt = build_copilot_prompt_batch(rng=Random(1), language="en", prompt_count=1)[0]

    def _fake_request_json(session, method, url, *, request_timeout_seconds, **kwargs):
        del session, request_timeout_seconds, kwargs
        seen_urls.append(url)
        payload_by_url = {
            "http://smoke.local/author/jobs/job-1/copilot/sessions": {"session_id": "session-1"},
            "http://smoke.local/author/jobs/job-1/copilot/sessions/session-1/messages": {
                "messages": [{"role": "assistant", "content": "I can reshape the draft more aggressively."}]
            },
            "http://smoke.local/author/jobs/job-1/copilot/sessions/session-1/proposal": {
                "proposal_id": "proposal-1",
                "source": "heuristic",
                "affected_sections": ["story_frame", "rule_pack"],
                "variant_label": "Pressure rewrite",
                "request_summary": "Broaden the story rules and public-record pressure.",
            },
            "http://smoke.local/author/jobs/job-1/copilot/proposals/proposal-1/preview": {
                "editor_state": {
                    "language": "en",
                    "play_profile_view": {
                        "runtime_profile": "archive_vote_play",
                        "closeout_profile": "record_exposure_closeout",
                        "max_turns": 4,
                    },
                }
            },
        }
        return payload_by_url[url], 0.1

    monkeypatch.setattr("tools.copilot_stability_soak._request_json", _fake_request_json)

    result = _run_prompt_trial(None, _config(), story_record=story_record, prompt=prompt, prompt_index=1)

    assert result["session_id"] == "session-1"
    assert result["proposal_id"] == "proposal-1"
    assert result["preview_success"] is True
    assert result["status"] == "preview_succeeded"
    assert all("/apply" not in url for url in seen_urls)
    assert seen_urls[0].endswith("/copilot/sessions")


def test_run_copilot_stability_soak_expands_matrix_and_reauthors_for_sampled_full_chain(monkeypatch) -> None:
    author_story_calls: list[str] = []
    trial_calls: list[tuple[str, str]] = []
    sample_calls: list[tuple[str, str]] = []

    monkeypatch.setattr("tools.copilot_stability_soak._smoke_preflight", lambda config: {"ok": True})
    monkeypatch.setattr("tools.copilot_stability_soak._smoke_config_for_preflight", lambda config: None)
    monkeypatch.setattr("tools.copilot_stability_soak._authenticate_session", lambda session, config: {"authenticated": True})
    monkeypatch.setattr("tools.copilot_stability_soak.requests.Session", lambda: type("_S", (), {"__enter__": lambda self: self, "__exit__": lambda self, exc_type, exc, tb: False})())

    def _fake_run_author_story(session, config, *, story_spec, story_key):
        del session, config
        author_story_calls.append(story_key)
        return {
            "story_key": story_key,
            "story_language": story_spec.language,
            "job_id": f"{story_key}-job",
            "status": "author_completed",
            "editor_state": {"play_profile_view": {"runtime_profile": "archive_vote_play", "closeout_profile": "record_exposure_closeout", "max_turns": 4}},
        }

    def _fake_run_prompt_trial(session, config, *, story_record, prompt, prompt_index):
        del session, config, prompt_index
        trial_calls.append((story_record["story_key"], prompt.prompt_id))
        return {
            "story_key": story_record["story_key"],
            "story_language": story_record["story_language"],
            "prompt_id": prompt.prompt_id,
            "prompt_text": prompt.prompt_text,
            "prompt_families": list(prompt.families),
            "proposal_id": f"{prompt.prompt_id}-proposal",
            "proposal_source": "heuristic",
            "affected_sections": ["story_frame", "rule_pack"],
            "variant_label": "Variant",
            "request_summary": "Summary",
            "preview_success": True,
            "status": "preview_succeeded",
            "error_code": None,
            "error_message": None,
            "proposal_elapsed_seconds": 0.1,
            "message_elapsed_seconds": 0.1,
            "preview_elapsed_seconds": 0.1,
            "language_match_flags": {"message": True, "variant_label": True, "request_summary": True, "preview_editor_state": True},
            "runtime_profile_preserved": True,
            "closeout_profile_preserved": True,
            "max_turns_preserved": True,
            "trial_index": 1,
        }

    def _fake_run_sampled_full_chain(session, config, *, story_record, prompt_trial):
        del session, config
        sample_calls.append((story_record["story_key"], prompt_trial["prompt_id"]))
        return {
            "selected_prompt_id": prompt_trial["prompt_id"],
            "apply_success": True,
            "publish_success": True,
            "play_session_success": True,
            "first_turn_success": True,
            "story_id": "story-1",
            "play_session_id": "play-1",
            "ending_status": "active",
        }

    monkeypatch.setattr("tools.copilot_stability_soak._run_author_story", _fake_run_author_story)
    monkeypatch.setattr("tools.copilot_stability_soak._run_prompt_trial", _fake_run_prompt_trial)
    monkeypatch.setattr("tools.copilot_stability_soak._run_sampled_full_chain", _fake_run_sampled_full_chain)

    payload = run_copilot_stability_soak(
        _config(story_count=5, prompt_count_per_story=4, sample_full_chain_count_per_story=1)
    )

    assert len(payload["stories"]) == 5
    assert len(trial_calls) == 20
    assert len(sample_calls) == 5
    assert len(author_story_calls) == 10
    assert all("_sample_" in story_key for story_key, _prompt_id in sample_calls)

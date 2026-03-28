from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any, Literal

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.copilot_prompt_factory import GeneratedCopilotPrompt, build_copilot_prompt_batch
from tools.http_product_smoke import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_POLL_TIMEOUT_SECONDS,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    HttpProductSmokeConfig,
    HttpProductSmokeRequestError,
    _authenticate_session,
    _default_turn_input,
    _optional_request_json,
    _request_json,
    _smoke_preflight,
    _text_matches_language,
)
from tools.play_benchmarks.story_seed_factory import GeneratedStorySeed, StorySeedLanguage, build_story_seed_batch

LanguageMix = Literal["en", "zh", "both"]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "copilot_soak"


@dataclass(frozen=True)
class CopilotStabilitySoakConfig:
    base_url: str
    output_dir: Path
    story_count: int
    prompt_count_per_story: int
    language_mix: LanguageMix
    seed: int | None
    poll_interval_seconds: float
    poll_timeout_seconds: float
    request_timeout_seconds: float
    include_benchmark_diagnostics: bool
    sample_full_chain_count_per_story: int


@dataclass(frozen=True)
class SoakStorySpec:
    story_key: str
    language: StorySeedLanguage
    generated_seed: GeneratedStorySeed


def parse_args(argv: list[str] | None = None) -> CopilotStabilitySoakConfig:
    parser = argparse.ArgumentParser(description="Run randomized Author Copilot stability soak against the live HTTP API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--story-count", type=int, default=5)
    parser.add_argument("--prompt-count-per-story", type=int, default=40)
    parser.add_argument("--language-mix", choices=("en", "zh", "both"), default="both")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--poll-interval-seconds", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--poll-timeout-seconds", type=float, default=DEFAULT_POLL_TIMEOUT_SECONDS)
    parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    parser.add_argument("--include-benchmark-diagnostics", action="store_true")
    parser.add_argument("--sample-full-chain-count-per-story", type=int, default=1)
    args = parser.parse_args(argv)
    return CopilotStabilitySoakConfig(
        base_url=str(args.base_url).rstrip("/"),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        story_count=max(1, int(args.story_count)),
        prompt_count_per_story=max(1, int(args.prompt_count_per_story)),
        language_mix=str(args.language_mix),  # type: ignore[arg-type]
        seed=args.seed,
        poll_interval_seconds=max(float(args.poll_interval_seconds), 0.05),
        poll_timeout_seconds=max(float(args.poll_timeout_seconds), 1.0),
        request_timeout_seconds=max(float(args.request_timeout_seconds), 1.0),
        include_benchmark_diagnostics=bool(args.include_benchmark_diagnostics),
        sample_full_chain_count_per_story=max(0, int(args.sample_full_chain_count_per_story)),
    )


def _smoke_config_for_preflight(config: CopilotStabilitySoakConfig) -> HttpProductSmokeConfig:
    return HttpProductSmokeConfig(
        base_url=config.base_url,
        language="en",
        prompt_seed="preflight",
        first_turn_input=_default_turn_input("en"),
        copilot_message="preflight",
        poll_interval_seconds=config.poll_interval_seconds,
        poll_timeout_seconds=config.poll_timeout_seconds,
        request_timeout_seconds=config.request_timeout_seconds,
        output_path=None,
        include_copilot=True,
        include_benchmark_diagnostics=config.include_benchmark_diagnostics,
    )


def _language_story_counts(total: int, language_mix: LanguageMix) -> dict[StorySeedLanguage, int]:
    if language_mix == "en":
        return {"en": total, "zh": 0}
    if language_mix == "zh":
        return {"en": 0, "zh": total}
    zh_count = total // 2
    en_count = total - zh_count
    return {"en": en_count, "zh": zh_count}


def build_story_specs(
    *,
    rng: Random,
    story_count: int,
    language_mix: LanguageMix,
) -> list[SoakStorySpec]:
    counts = _language_story_counts(story_count, language_mix)
    specs_by_language: dict[StorySeedLanguage, list[SoakStorySpec]] = {"en": [], "zh": []}
    for language in ("en", "zh"):
        needed = counts[language]
        index = 0
        while len(specs_by_language[language]) < needed:
            remaining = needed - len(specs_by_language[language])
            batch = build_story_seed_batch(
                rng=rng,
                story_count=min(remaining, 5),
                language=language,
            )
            for seed in batch:
                index += 1
                specs_by_language[language].append(
                    SoakStorySpec(
                        story_key=f"{language}_story_{index:02d}_{seed.slug}",
                        language=language,
                        generated_seed=seed,
                    )
                )
                if len(specs_by_language[language]) >= needed:
                    break
    if language_mix != "both":
        return specs_by_language["en"] or specs_by_language["zh"]
    interleaved: list[SoakStorySpec] = []
    en_specs = list(specs_by_language["en"])
    zh_specs = list(specs_by_language["zh"])
    while en_specs or zh_specs:
        if en_specs:
            interleaved.append(en_specs.pop(0))
        if zh_specs:
            interleaved.append(zh_specs.pop(0))
    return interleaved


def _poll_author_job(
    session: requests.Session,
    config: CopilotStabilitySoakConfig,
    *,
    job_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = time.perf_counter()
    poll_count = 0
    last_payload: dict[str, Any] | None = None
    while True:
        status_payload, _elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/author/jobs/{job_id}",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        last_payload = status_payload
        poll_count += 1
        if status_payload.get("status") in {"completed", "failed"}:
            return status_payload, {
                "poll_count": poll_count,
                "poll_elapsed_seconds": round(time.perf_counter() - started_at, 3),
            }
        if time.perf_counter() - started_at >= config.poll_timeout_seconds:
            raise RuntimeError(
                f"author job '{job_id}' did not reach terminal state within {config.poll_timeout_seconds:.1f}s "
                f"(last_status={last_payload.get('status') if last_payload else 'unknown'})"
            )
        time.sleep(config.poll_interval_seconds)


def _error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "error_code": getattr(exc, "error_code", None),
        "error_message": str(exc),
    }


def _run_author_story(
    session: requests.Session,
    config: CopilotStabilitySoakConfig,
    *,
    story_spec: SoakStorySpec,
    story_key: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "story_key": story_key,
        "story_language": story_spec.language,
        "bucket_id": story_spec.generated_seed.bucket_id,
        "seed": story_spec.generated_seed.seed,
        "seed_slug": story_spec.generated_seed.slug,
        "generated_at": story_spec.generated_seed.generated_at,
        "status": "author_started",
        "timings": {},
    }
    try:
        preview_payload, preview_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/story-previews",
            request_timeout_seconds=config.request_timeout_seconds,
            json={"prompt_seed": story_spec.generated_seed.seed, "language": story_spec.language},
        )
        record["timings"]["preview_elapsed_seconds"] = preview_elapsed
        record["preview"] = preview_payload
        job_payload, create_job_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs",
            request_timeout_seconds=config.request_timeout_seconds,
            json={
                "prompt_seed": story_spec.generated_seed.seed,
                "preview_id": preview_payload["preview_id"],
                "language": story_spec.language,
            },
        )
        job_id = str(job_payload["job_id"])
        record["job_id"] = job_id
        record["timings"]["create_job_elapsed_seconds"] = create_job_elapsed
        author_status, poll_summary = _poll_author_job(session, config, job_id=job_id)
        record["author_status"] = author_status
        record["timings"]["poll_author"] = poll_summary
        result_payload, result_elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/author/jobs/{job_id}/result",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        record["result"] = result_payload
        record["timings"]["result_elapsed_seconds"] = result_elapsed
        if author_status.get("status") != "completed":
            raise RuntimeError(f"author job '{job_id}' ended with status={author_status.get('status')}")
        editor_state, editor_state_elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/author/jobs/{job_id}/editor-state",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        record["editor_state"] = editor_state
        record["timings"]["editor_state_elapsed_seconds"] = editor_state_elapsed
        if config.include_benchmark_diagnostics:
            diagnostics, diagnostics_elapsed = _optional_request_json(
                session,
                "GET",
                f"{config.base_url}/benchmark/author/jobs/{job_id}/diagnostics",
                request_timeout_seconds=config.request_timeout_seconds,
            )
            record["diagnostics"] = diagnostics
            record["timings"]["author_diagnostics_elapsed_seconds"] = diagnostics_elapsed
        record["status"] = "author_completed"
    except Exception as exc:  # noqa: BLE001
        record.update(_error_payload(exc))
        record["status"] = "author_failed"
    return record


def _run_prompt_trial(
    session: requests.Session,
    config: CopilotStabilitySoakConfig,
    *,
    story_record: dict[str, Any],
    prompt: GeneratedCopilotPrompt,
    prompt_index: int,
) -> dict[str, Any]:
    editor_state = dict(story_record.get("editor_state") or {})
    base_profile = dict(editor_state.get("play_profile_view") or {})
    trial: dict[str, Any] = {
        "story_id": story_record.get("job_id"),
        "story_key": story_record.get("story_key"),
        "story_language": story_record.get("story_language"),
        "prompt_id": prompt.prompt_id,
        "prompt_text": prompt.prompt_text,
        "prompt_families": list(prompt.families),
        "trial_index": prompt_index,
        "session_id": None,
        "proposal_id": None,
        "proposal_source": None,
        "affected_sections": [],
        "variant_label": None,
        "request_summary": None,
        "status": "started",
        "error_code": None,
        "error_message": None,
        "message_elapsed_seconds": None,
        "proposal_elapsed_seconds": None,
        "preview_elapsed_seconds": None,
        "preview_success": False,
        "language_match_flags": {},
        "runtime_profile_preserved": None,
        "closeout_profile_preserved": None,
        "max_turns_preserved": None,
    }
    job_id = story_record.get("job_id")
    if not job_id:
        trial["status"] = "skipped_author_failed"
        return trial
    try:
        session_payload, session_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/sessions",
            request_timeout_seconds=config.request_timeout_seconds,
            json={"hidden": True},
        )
        trial["session_id"] = str(session_payload["session_id"])
        trial["create_session_elapsed_seconds"] = session_elapsed
        message_payload, message_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/sessions/{trial['session_id']}/messages",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
            json={"content": prompt.prompt_text},
        )
        trial["message_elapsed_seconds"] = message_elapsed
        assistant_messages = [
            item
            for item in list(message_payload.get("messages") or [])
            if isinstance(item, dict) and item.get("role") == "assistant"
        ]
        last_assistant = dict(assistant_messages[-1] or {}) if assistant_messages else {}
        trial["language_match_flags"]["message"] = _text_matches_language(
            str(last_assistant.get("content") or ""),
            prompt.language,
        )
        proposal_payload, proposal_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/sessions/{trial['session_id']}/proposal",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
        )
        trial["proposal_elapsed_seconds"] = proposal_elapsed
        trial["proposal_id"] = str(proposal_payload["proposal_id"])
        trial["proposal_source"] = proposal_payload.get("source")
        trial["affected_sections"] = list(proposal_payload.get("affected_sections") or [])
        trial["variant_label"] = proposal_payload.get("variant_label")
        trial["request_summary"] = proposal_payload.get("request_summary")
        trial["language_match_flags"]["variant_label"] = _text_matches_language(
            str(proposal_payload.get("variant_label") or ""),
            prompt.language,
        )
        trial["language_match_flags"]["request_summary"] = _text_matches_language(
            str(proposal_payload.get("request_summary") or ""),
            prompt.language,
        )
        preview_payload, preview_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/proposals/{trial['proposal_id']}/preview",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
        )
        trial["preview_elapsed_seconds"] = preview_elapsed
        trial["preview_success"] = True
        trial["status"] = "preview_succeeded"
        preview_editor_state = dict(preview_payload.get("editor_state") or {})
        preview_profile = dict(preview_editor_state.get("play_profile_view") or {})
        trial["language_match_flags"]["preview_editor_state"] = preview_editor_state.get("language") == prompt.language
        trial["runtime_profile_preserved"] = base_profile.get("runtime_profile") == preview_profile.get("runtime_profile")
        trial["closeout_profile_preserved"] = base_profile.get("closeout_profile") == preview_profile.get("closeout_profile")
        trial["max_turns_preserved"] = base_profile.get("max_turns") == preview_profile.get("max_turns")
    except Exception as exc:  # noqa: BLE001
        trial.update(_error_payload(exc))
        if trial["proposal_id"] is not None:
            trial["status"] = "preview_failed"
        elif trial["session_id"] is not None:
            trial["status"] = "proposal_failed"
        else:
            trial["status"] = "session_failed"
    return trial


def _choose_sampled_prompts(
    trials: list[dict[str, Any]],
    *,
    sample_count: int,
) -> list[dict[str, Any]]:
    successful = [trial for trial in trials if trial.get("preview_success")]
    sorted_trials = sorted(
        successful,
        key=lambda trial: (
            0 if {"story_frame", "rule_pack"}.issubset(set(trial.get("affected_sections") or [])) else 1,
            -len(list(trial.get("affected_sections") or [])),
            int(trial.get("trial_index") or 0),
        ),
    )
    return sorted_trials[:sample_count]


def _run_sampled_full_chain(
    session: requests.Session,
    config: CopilotStabilitySoakConfig,
    *,
    story_record: dict[str, Any],
    prompt_trial: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "selected_prompt_id": prompt_trial.get("prompt_id"),
        "story_id": None,
        "play_session_id": None,
        "apply_success": False,
        "publish_success": False,
        "play_session_success": False,
        "first_turn_success": False,
        "ending_status": None,
        "error_code": None,
        "error_message": None,
    }
    job_id = story_record.get("job_id")
    if not job_id:
        result["error_code"] = "author_unavailable"
        result["error_message"] = "base author story failed"
        return result
    try:
        session_payload, _session_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/sessions",
            request_timeout_seconds=config.request_timeout_seconds,
            json={"hidden": True},
        )
        session_id = str(session_payload["session_id"])
        _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/sessions/{session_id}/messages",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
            json={"content": str(prompt_trial["prompt_text"])},
        )
        proposal_payload, _proposal_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/sessions/{session_id}/proposal",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
        )
        proposal_id = str(proposal_payload["proposal_id"])
        _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/proposals/{proposal_id}/preview",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
        )
        apply_payload, _apply_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/copilot/proposals/{proposal_id}/apply",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
        )
        result["apply_success"] = (
            isinstance(apply_payload.get("proposal"), dict)
            and dict(apply_payload.get("proposal") or {}).get("status") == "applied"
        )
        publish_payload, _publish_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/publish",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        result["publish_success"] = True
        result["story_id"] = publish_payload.get("story_id")
        detail_payload, _detail_elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/stories/{result['story_id']}",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        result["runtime_profile"] = dict(detail_payload.get("play_overview") or {}).get("runtime_profile")
        play_payload, _play_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/play/sessions",
            request_timeout_seconds=config.request_timeout_seconds,
            json={"story_id": result["story_id"]},
        )
        result["play_session_success"] = True
        result["play_session_id"] = play_payload.get("session_id")
        turn_payload, _turn_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/play/sessions/{result['play_session_id']}/turns",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
            json={"input_text": _default_turn_input(str(story_record.get('story_language') or 'en'))},
        )
        result["first_turn_success"] = turn_payload.get("status") in {"active", "completed"}
        result["ending_status"] = turn_payload.get("status")
        if config.include_benchmark_diagnostics and result["play_session_id"]:
            diagnostics, diagnostics_elapsed = _optional_request_json(
                session,
                "GET",
                f"{config.base_url}/benchmark/play/sessions/{result['play_session_id']}/diagnostics",
                request_timeout_seconds=config.request_timeout_seconds,
            )
            result["play_diagnostics"] = diagnostics
            result["play_diagnostics_elapsed_seconds"] = diagnostics_elapsed
    except Exception as exc:  # noqa: BLE001
        result.update(_error_payload(exc))
    return result


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(int(round((len(ordered) - 1) * q)), 0), len(ordered) - 1)
    return round(float(ordered[index]), 3)


def _trial_metrics(trials: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = len(trials)
    proposal_successes = [trial for trial in trials if trial.get("proposal_id")]
    preview_successes = [trial for trial in trials if trial.get("preview_success")]
    unsupported = sum(1 for trial in trials if trial.get("error_code") == "author_copilot_instruction_unsupported")
    provider_failures = sum(
        1
        for trial in trials
        if str(trial.get("error_code") or "").startswith("gateway_")
    )
    preview_consistency_failures = sum(
        1
        for trial in trials
        if trial.get("error_code") == "author_copilot_rewrite_inconsistent"
    )
    language_drift = sum(
        1
        for trial in trials
        if any(flag is False for flag in dict(trial.get("language_match_flags") or {}).values())
    )
    proposal_elapsed_values = [
        float(trial["proposal_elapsed_seconds"])
        for trial in proposal_successes
        if trial.get("proposal_elapsed_seconds") is not None
    ]
    source_distribution: dict[str, int] = {}
    sections_distribution: dict[str, int] = {}
    error_code_distribution: dict[str, int] = {}
    failure_family_distribution: dict[str, int] = {}
    for trial in trials:
        source = str(trial.get("proposal_source") or "")
        if source:
            source_distribution[source] = source_distribution.get(source, 0) + 1
        section_key = "+".join(list(trial.get("affected_sections") or [])) or "none"
        sections_distribution[section_key] = sections_distribution.get(section_key, 0) + 1
        error_code = str(trial.get("error_code") or "")
        if error_code:
            error_code_distribution[error_code] = error_code_distribution.get(error_code, 0) + 1
            family_key = "+".join(list(trial.get("prompt_families") or []))
            failure_family_distribution[family_key] = failure_family_distribution.get(family_key, 0) + 1
    return {
        "trial_count": attempted,
        "proposal_success_rate": _safe_rate(len(proposal_successes), attempted),
        "proposal_unsupported_rate": _safe_rate(unsupported, attempted),
        "proposal_provider_error_rate": _safe_rate(provider_failures, attempted),
        "preview_success_rate": _safe_rate(len(preview_successes), attempted),
        "preview_consistency_failure_rate": _safe_rate(preview_consistency_failures, attempted),
        "language_drift_rate": _safe_rate(language_drift, attempted),
        "proposal_source_distribution": source_distribution,
        "affected_sections_distribution": sections_distribution,
        "error_code_distribution": error_code_distribution,
        "failure_family_distribution": failure_family_distribution,
        "proposal_elapsed_seconds_p50": round(statistics.median(proposal_elapsed_values), 3) if proposal_elapsed_values else 0.0,
        "proposal_elapsed_seconds_p95": _percentile(proposal_elapsed_values, 0.95),
    }


def _aggregate_payload(stories: list[dict[str, Any]]) -> dict[str, Any]:
    trials = [trial for story in stories for trial in list(story.get("prompt_trials") or [])]
    samples = [sample for story in stories for sample in list(story.get("sampled_full_chain_records") or [])]
    by_language: dict[str, dict[str, Any]] = {}
    for language in ("en", "zh"):
        language_trials = [trial for trial in trials if trial.get("story_language") == language]
        language_samples = [sample for story in stories if story.get("story_language") == language for sample in list(story.get("sampled_full_chain_records") or [])]
        metrics = _trial_metrics(language_trials)
        metrics["apply_sample_success_rate"] = _safe_rate(sum(1 for sample in language_samples if sample.get("apply_success")), len(language_samples))
        metrics["publish_play_sample_success_rate"] = _safe_rate(
            sum(1 for sample in language_samples if sample.get("publish_success") and sample.get("play_session_success") and sample.get("first_turn_success")),
            len(language_samples),
        )
        by_language[language] = metrics
    overall = _trial_metrics(trials)
    overall["author_story_success_rate"] = _safe_rate(sum(1 for story in stories if story.get("status") == "author_completed"), len(stories))
    overall["apply_sample_success_rate"] = _safe_rate(sum(1 for sample in samples if sample.get("apply_success")), len(samples))
    overall["publish_play_sample_success_rate"] = _safe_rate(
        sum(1 for sample in samples if sample.get("publish_success") and sample.get("play_session_success") and sample.get("first_turn_success")),
        len(samples),
    )
    return {"overall": overall, "by_language": by_language}


def _render_markdown(payload: dict[str, Any]) -> str:
    aggregate = dict(payload.get("aggregate") or {}).get("overall") or {}
    lines = [
        "# Copilot Random Prompt Stability Soak",
        "",
        f"- Base URL: `{payload.get('base_url')}`",
        f"- Story count: `{payload.get('story_count')}`",
        f"- Prompt count per story: `{payload.get('prompt_count_per_story')}`",
        f"- Language mix: `{payload.get('language_mix')}`",
        "",
        "## Aggregate",
        "",
        f"- Proposal success rate: `{aggregate.get('proposal_success_rate')}`",
        f"- Proposal unsupported rate: `{aggregate.get('proposal_unsupported_rate')}`",
        f"- Proposal provider error rate: `{aggregate.get('proposal_provider_error_rate')}`",
        f"- Preview success rate: `{aggregate.get('preview_success_rate')}`",
        f"- Preview consistency failure rate: `{aggregate.get('preview_consistency_failure_rate')}`",
        f"- Apply sample success rate: `{aggregate.get('apply_sample_success_rate')}`",
        f"- Publish+play sample success rate: `{aggregate.get('publish_play_sample_success_rate')}`",
        f"- Language drift rate: `{aggregate.get('language_drift_rate')}`",
        "",
        "## Diagnostics",
        "",
        f"- Proposal source distribution: `{aggregate.get('proposal_source_distribution')}`",
        f"- Affected sections distribution: `{aggregate.get('affected_sections_distribution')}`",
        f"- Top error codes: `{aggregate.get('error_code_distribution')}`",
        f"- Failure families: `{aggregate.get('failure_family_distribution')}`",
        "",
        "## Soft Flags",
        "",
        f"- `proposal_unsupported_rate > 0.05`: `{float(aggregate.get('proposal_unsupported_rate') or 0) > 0.05}`",
        f"- `preview_success_rate < 0.95`: `{float(aggregate.get('preview_success_rate') or 0) < 0.95}`",
        f"- `language_drift_rate > 0`: `{float(aggregate.get('language_drift_rate') or 0) > 0}`",
        f"- `apply_sample_success_rate < 1.0`: `{float(aggregate.get('apply_sample_success_rate') or 0) < 1.0}`",
        f"- `publish_play_sample_success_rate < 1.0`: `{float(aggregate.get('publish_play_sample_success_rate') or 0) < 1.0}`",
    ]
    return "\n".join(lines) + "\n"


def write_artifacts(config: CopilotStabilitySoakConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"copilot_stability_soak_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def run_copilot_stability_soak(config: CopilotStabilitySoakConfig) -> dict[str, Any]:
    rng = Random(config.seed) if config.seed is not None else Random()
    preflight = _smoke_preflight(_smoke_config_for_preflight(config))
    story_specs = build_story_specs(rng=rng, story_count=config.story_count, language_mix=config.language_mix)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": config.base_url,
        "story_count": config.story_count,
        "prompt_count_per_story": config.prompt_count_per_story,
        "language_mix": config.language_mix,
        "include_benchmark_diagnostics": config.include_benchmark_diagnostics,
        "sample_full_chain_count_per_story": config.sample_full_chain_count_per_story,
        "preflight": preflight,
        "stories": [],
    }
    with requests.Session() as session:
        _authenticate_session(
            session,
            _smoke_config_for_preflight(config),
        )
        for story_spec in story_specs:
            story_record = _run_author_story(
                session,
                config,
                story_spec=story_spec,
                story_key=story_spec.story_key,
            )
            prompt_trials: list[dict[str, Any]] = []
            prompts = build_copilot_prompt_batch(
                rng=rng,
                language=story_spec.language,
                prompt_count=config.prompt_count_per_story,
            )
            if story_record.get("status") == "author_completed":
                for prompt_index, prompt in enumerate(prompts, start=1):
                    prompt_trials.append(
                        _run_prompt_trial(
                            session,
                            config,
                            story_record=story_record,
                            prompt=prompt,
                            prompt_index=prompt_index,
                        )
                    )
            sampled_full_chain_records: list[dict[str, Any]] = []
            if story_record.get("status") == "author_completed" and config.sample_full_chain_count_per_story > 0:
                selected_prompts = _choose_sampled_prompts(
                    prompt_trials,
                    sample_count=config.sample_full_chain_count_per_story,
                )
                if not selected_prompts:
                    sampled_full_chain_records.append({"selected_prompt_id": None, "status": "skipped_no_successful_prompt"})
                else:
                    for prompt_trial in selected_prompts:
                        fresh_story_record = _run_author_story(
                            session,
                            config,
                            story_spec=story_spec,
                            story_key=f"{story_spec.story_key}_sample_{prompt_trial['prompt_id']}",
                        )
                        sampled_full_chain_records.append(
                            _run_sampled_full_chain(
                                session,
                                config,
                                story_record=fresh_story_record,
                                prompt_trial=prompt_trial,
                            )
                        )
            payload["stories"].append(
                {
                    **story_record,
                    "prompt_trials": prompt_trials,
                    "sampled_full_chain_records": sampled_full_chain_records,
                }
            )
    payload["aggregate"] = _aggregate_payload(list(payload["stories"]))
    return payload


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_copilot_stability_soak(config)
    json_path, md_path = write_artifacts(config, payload)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

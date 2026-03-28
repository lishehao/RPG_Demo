from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from time import perf_counter
from typing import Any, Literal

import requests

from rpg_backend.helper.agent import HelperAgentClient, HelperAgentError, HelperRequest
from rpg_backend.llm_gateway import helper_gateway_config_available
from rpg_backend.play.text_quality import (
    contains_play_meta_wrapper_text,
    has_language_contamination,
    has_second_person_reference,
)
from tools.play_benchmarks import live_api_playtest
from tools.play_benchmarks.story_seed_factory import build_story_seed_batch

StoryLanguage = Literal["en", "zh"]
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "play_issue_inspect"
_MOVE_FAMILIES: tuple[str, ...] = (
    "public_pressure",
    "coalition_repair",
    "evidence_lock",
    "resource_control",
    "institutional_audit",
    "protect_legitimacy",
    "force_settlement",
)
_DEFAULT_HELPER_ANALYSIS_MAX_TURNS = 12
_DEFAULT_HELPER_ANALYSIS_CONCURRENCY = 4


@dataclass(frozen=True)
class PlayIssueInspectConfig:
    base_url: str
    output_dir: Path
    launch_server: bool
    story_id: str | None
    language: StoryLanguage
    prompt_count: int
    seed: int | None
    label: str | None
    session_ttl_seconds: int
    target_duration_minutes: int
    managed_server_content_prompt_profile: str | None = None
    helper_analysis_enabled: bool = True
    helper_analysis_max_turns: int = _DEFAULT_HELPER_ANALYSIS_MAX_TURNS
    helper_analysis_concurrency: int = _DEFAULT_HELPER_ANALYSIS_CONCURRENCY


def parse_args(argv: list[str] | None = None) -> PlayIssueInspectConfig:
    parser = argparse.ArgumentParser(description="Inspect play persistence quality by submitting a fixed batch of random player turns.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--launch-server", action="store_true")
    parser.add_argument("--story-id")
    parser.add_argument("--language", choices=("en", "zh"), default="zh")
    parser.add_argument("--prompt-count", type=int, default=10)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--label")
    parser.add_argument("--session-ttl-seconds", type=int, default=3600)
    parser.add_argument("--target-duration-minutes", type=int, default=25)
    parser.add_argument("--managed-server-content-prompt-profile", choices=("plain", "role_conditioned"))
    parser.add_argument("--disable-helper-analysis", action="store_true")
    parser.add_argument("--helper-analysis-max-turns", type=int, default=_DEFAULT_HELPER_ANALYSIS_MAX_TURNS)
    parser.add_argument("--helper-analysis-concurrency", type=int, default=_DEFAULT_HELPER_ANALYSIS_CONCURRENCY)
    args = parser.parse_args(argv)
    return PlayIssueInspectConfig(
        base_url=args.base_url.rstrip("/"),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        launch_server=bool(args.launch_server),
        story_id=str(args.story_id).strip() if args.story_id else None,
        language=str(args.language),  # type: ignore[arg-type]
        prompt_count=max(int(args.prompt_count), 1),
        seed=args.seed,
        label=args.label,
        session_ttl_seconds=max(int(args.session_ttl_seconds), 60),
        target_duration_minutes=min(max(int(args.target_duration_minutes), 10), 25),
        managed_server_content_prompt_profile=args.managed_server_content_prompt_profile,
        helper_analysis_enabled=not bool(args.disable_helper_analysis),
        helper_analysis_max_turns=max(int(args.helper_analysis_max_turns), 1),
        helper_analysis_concurrency=max(int(args.helper_analysis_concurrency), 1),
    )


def _prompt_hint(snapshot: dict[str, Any], *, language: StoryLanguage, rng: Random) -> str:
    prompts = [str(item.get("prompt") or "").strip() for item in list(snapshot.get("suggested_actions") or []) if str(item.get("prompt") or "").strip()]
    if not prompts:
        return ""
    selected = rng.choice(prompts).strip().rstrip("。.")
    if language == "zh":
        return selected.removeprefix("你").strip()
    if selected.lower().startswith("you "):
        return f"I {selected[4:].strip()}".rstrip(".")
    return selected


def _target_label(snapshot: dict[str, Any], *, language: StoryLanguage) -> str:
    names = [str(item.get("name") or "").strip() for item in list(snapshot.get("npc_visuals") or []) if str(item.get("name") or "").strip()]
    if names:
        return "、".join(names[:2]) if language == "zh" else " and ".join(names[:2])
    return "相关的人" if language == "zh" else "the key witnesses"


def _pressure_hint(snapshot: dict[str, Any], *, language: StoryLanguage) -> str:
    consequences = [str(item).strip() for item in list(((snapshot.get("feedback") or {}).get("last_turn_consequences") or [])) if str(item).strip()]
    if consequences:
        return consequences[0].rstrip("。.")
    state_bars = [str(item.get("label") or "").strip() for item in list(snapshot.get("state_bars") or []) if str(item.get("label") or "").strip()]
    if state_bars:
        return state_bars[0]
    return str(snapshot.get("beat_title") or ("眼前的局势" if language == "zh" else "the current crisis"))


def _move_family_candidates(snapshot: dict[str, Any], *, language: StoryLanguage) -> list[str]:
    haystack = " ".join(
        [
            str(snapshot.get("beat_title") or ""),
            " ".join(str(item.get("label") or "") for item in list(snapshot.get("suggested_actions") or [])),
            " ".join(str(item.get("prompt") or "") for item in list(snapshot.get("suggested_actions") or [])),
            " ".join(str(item) for item in list(((snapshot.get("feedback") or {}).get("last_turn_consequences") or []))),
        ]
    ).casefold()
    candidates: list[str] = []
    if any(token in haystack for token in ("record", "ledger", "proof", "evidence", "seal", "witness", "记录", "账", "证", "档案", "证词")):
        candidates.append("evidence_lock")
    if any(token in haystack for token in ("dock", "harbor", "supply", "ration", "resource", "corridor", "码头", "港", "物资", "配给", "走廊")):
        candidates.append("resource_control")
    if any(token in haystack for token in ("audit", "verify", "protocol", "charter", "inspection", "核对", "核验", "程序", "审查")):
        candidates.append("institutional_audit")
    if any(token in haystack for token in ("coalition", "ally", "agreement", "联盟", "盟友", "协定", "同一套流程")):
        candidates.append("coalition_repair")
    if any(token in haystack for token in ("public", "crowd", "chamber", "mandate", "speech", "公开", "会场", "当众", "授权")):
        candidates.append("public_pressure")
    if any(token in haystack for token in ("legitimacy", "authority", "合法", "权威", "公信")):
        candidates.append("protect_legitimacy")
    candidates.extend(["public_pressure", "evidence_lock", "coalition_repair"])
    ordered: list[str] = []
    for item in candidates:
        if item not in ordered:
            ordered.append(item)
    return ordered or list(_MOVE_FAMILIES)


def _build_random_prompt(snapshot: dict[str, Any], *, language: StoryLanguage, rng: Random) -> tuple[str, str]:
    move_family = rng.choice(_move_family_candidates(snapshot, language=language))
    beat_title = str(snapshot.get("beat_title") or ("当前这一步" if language == "zh" else "the current beat")).strip()
    target = _target_label(snapshot, language=language)
    pressure = _pressure_hint(snapshot, language=language)
    prompt_hint = _prompt_hint(snapshot, language=language, rng=rng)
    if language == "zh":
        templates = {
            "public_pressure": [
                f"我先把“{beat_title}”这件事当众摊开，逼{target}把{prompt_hint or pressure}说清，别让它再被压回程序里。",
                f"我直接把会场的注意力拽回“{beat_title}”，要求{target}围着{pressure}给出公开说法。",
            ],
            "coalition_repair": [
                f"我先把分裂的人重新拉回同一套流程里，逼{target}围着“{beat_title}”给出一个谁都看得见的承诺。",
                f"我不让各方各说各话，先按住“{beat_title}”这条线，让{target}在公开流程里重新站队。",
            ],
            "evidence_lock": [
                f"我先把最硬的记录按在台面上，逼{target}围着{prompt_hint or pressure}逐条核对，不让任何人再改写一遍。",
                f"我把能咬住责任链的那份材料先锁死，再让{target}围着“{beat_title}”当场对账。",
            ],
            "resource_control": [
                f"我先把{pressure}这条资源线重新拉回公共视野，逼{target}说明到底是谁在把它变成私下筹码。",
                f"我先稳住“{beat_title}”背后的资源调度，再逼{target}把{prompt_hint or pressure}当众说清。",
            ],
            "institutional_audit": [
                f"我先按住程序不让人跳步，逼{target}围着{prompt_hint or pressure}做一轮逐条核验。",
                f"我不让任何人拿流程当遮羞布，先要求{target}围着“{beat_title}”做公开核对。",
            ],
            "protect_legitimacy": [
                f"我先把“{beat_title}”背后的公信问题顶到台面上，逼{target}说明{pressure}到底还能不能算数。",
                f"我先守住这件事还值得被公众认账的底线，再要求{target}围着{prompt_hint or pressure}公开表态。",
            ],
            "force_settlement": [
                f"我先逼{target}围着“{beat_title}”给出一份当场能执行的结算，不让{pressure}继续拖成更坏的默认局面。",
                f"我不再让局势空转，直接要求{target}围着{prompt_hint or pressure}把最后条件摊清楚。",
            ],
        }
    else:
        templates = {
            "public_pressure": [
                f"I force {target} to answer around {beat_title} in public before {pressure} gets buried again.",
                f"I drag the room back to {beat_title} and make {target} state their position on {prompt_hint or pressure} out loud.",
            ],
            "coalition_repair": [
                f"I pull the fractured sides back into one visible process around {beat_title} and make {target} commit in the open.",
                f"I stop the room from splintering and force {target} to bargain around {pressure} in one shared process.",
            ],
            "evidence_lock": [
                f"I lock the strongest surviving record in place and make {target} verify {prompt_hint or pressure} line by line before anyone revises it.",
                f"I put the hardest piece of evidence on the table and force {target} to answer around {beat_title} under public scrutiny.",
            ],
            "resource_control": [
                f"I pull the real leverage behind {pressure} back into public view and make {target} explain who has been controlling it.",
                f"I stabilize the resource line behind {beat_title} first, then force {target} to answer for {prompt_hint or pressure}.",
            ],
            "institutional_audit": [
                f"I stop the room from skipping steps and make {target} verify {prompt_hint or pressure} in a visible audit.",
                f"I refuse to let procedure hide the damage and force {target} into a line-by-line institutional check around {beat_title}.",
            ],
            "protect_legitimacy": [
                f"I force the room to confront whether {pressure} can still claim public legitimacy and make {target} answer for it.",
                f"I defend the last credible public process around {beat_title} and force {target} to state what still counts as lawful here.",
            ],
            "force_settlement": [
                f"I push {target} to set final terms around {beat_title} now instead of letting {pressure} harden into the default outcome.",
                f"I stop the drift and force {target} to put a workable settlement on the table around {prompt_hint or pressure}.",
            ],
        }
    return rng.choice(templates[move_family]), move_family


def _issue_cluster(turn: dict[str, Any]) -> str:
    if turn.get("persistent_wrapper_hit"):
        return "persistent_wrapper_leak"
    if turn.get("persistent_language_contamination_hit"):
        return "persistent_language_contamination"
    if turn.get("persistent_second_person_missing"):
        return "persistent_second_person_missing"
    if turn.get("render_failure_reason"):
        return str(turn.get("render_failure_reason"))
    if turn.get("render_source") == "fallback":
        return "render_fallback"
    return "clean"


def _normalize_helper_cluster(value: str | None, *, fallback: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    normalized = "".join(char for char in text if char.isalnum() or char == "_").strip("_")
    return normalized or fallback


def _normalize_helper_priority(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"p0", "critical"}:
        return "p0"
    if normalized in {"p1", "high"}:
        return "p1"
    if normalized in {"p2", "medium", "med"}:
        return "p2"
    if normalized in {"p3", "low"}:
        return "p3"
    return "p2"


def _normalize_helper_surface(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"render", "interpret", "persistence", "prompt_quality", "unknown"}:
        return normalized
    return "unknown"


def _excerpt_text(value: str | None, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _helper_issue_request(turn: dict[str, Any], *, language: StoryLanguage) -> HelperRequest:
    issue_cluster = _issue_cluster(turn)
    return HelperRequest(
        system_prompt=(
            "You triage play runtime failures. Return one strict JSON object with keys "
            "cluster_label, priority, failure_surface, rationale, next_probe. "
            "cluster_label must be short snake_case. priority must be one of p0, p1, p2, p3. "
            "failure_surface must be one of render, interpret, persistence, prompt_quality, unknown. "
            "Keep rationale and next_probe under 16 words each."
        ),
        user_payload={
            "language": language,
            "issue_cluster": issue_cluster,
            "render_source": turn.get("render_source"),
            "render_failure_reason": turn.get("render_failure_reason"),
            "interpret_failure_reason": turn.get("interpret_failure_reason"),
            "persistent_wrapper_hit": bool(turn.get("persistent_wrapper_hit")),
            "persistent_language_contamination_hit": bool(turn.get("persistent_language_contamination_hit")),
            "persistent_second_person_missing": bool(turn.get("persistent_second_person_missing")),
            "move_family": turn.get("move_family"),
            "input_text": turn.get("input_text"),
            "narration": _excerpt_text(turn.get("narration"), limit=280),
        },
        max_output_tokens=160,
        operation_name=f"play_issue_helper_{turn.get('session_id')}_{turn.get('turn_index')}",
        allow_raw_text_passthrough=False,
    )


def _helper_issue_examples(triaged_turns: list[dict[str, Any]], *, max_examples: int = 5) -> list[dict[str, Any]]:
    ordered = sorted(
        triaged_turns,
        key=lambda item: (
            _normalize_helper_priority((item.get("helper_triage") or {}).get("priority")),
            str((item.get("helper_triage") or {}).get("cluster_label") or ""),
            int(item.get("global_turn") or 0),
        ),
    )
    examples: list[dict[str, Any]] = []
    for turn in ordered[:max_examples]:
        triage = dict(turn.get("helper_triage") or {})
        examples.append(
            {
                "session_id": turn.get("session_id"),
                "turn_index": turn.get("turn_index"),
                "global_turn": turn.get("global_turn"),
                "issue_cluster": _issue_cluster(turn),
                "cluster_label": triage.get("cluster_label"),
                "priority": triage.get("priority"),
                "failure_surface": triage.get("failure_surface"),
                "rationale": triage.get("rationale"),
                "next_probe": triage.get("next_probe"),
                "render_source": turn.get("render_source"),
                "render_failure_reason": turn.get("render_failure_reason"),
                "interpret_failure_reason": turn.get("interpret_failure_reason"),
                "input_text": turn.get("input_text"),
                "narration_excerpt": _excerpt_text(turn.get("narration")),
            }
        )
    return examples


def _run_helper_issue_analysis(
    *,
    prompt_records: list[dict[str, Any]],
    language: StoryLanguage,
    enabled: bool,
    max_turns: int,
    concurrency: int,
) -> dict[str, Any]:
    if not enabled:
        return {
            "status": "disabled",
            "candidate_turn_count": 0,
            "analyzed_turn_count": 0,
            "failed_turn_count": 0,
            "cluster_distribution": {},
            "priority_distribution": {},
            "failure_surface_distribution": {},
            "examples": [],
        }
    if not helper_gateway_config_available():
        return {
            "status": "skipped_config_missing",
            "candidate_turn_count": 0,
            "analyzed_turn_count": 0,
            "failed_turn_count": 0,
            "cluster_distribution": {},
            "priority_distribution": {},
            "failure_surface_distribution": {},
            "examples": [],
        }

    candidate_turns = [
        turn
        for turn in prompt_records
        if _issue_cluster(turn) != "clean"
    ][:max_turns]
    if not candidate_turns:
        return {
            "status": "no_issue_candidates",
            "candidate_turn_count": 0,
            "analyzed_turn_count": 0,
            "failed_turn_count": 0,
            "cluster_distribution": {},
            "priority_distribution": {},
            "failure_surface_distribution": {},
            "examples": [],
        }

    started_at = perf_counter()
    cluster_distribution: dict[str, int] = {}
    priority_distribution: dict[str, int] = {}
    failure_surface_distribution: dict[str, int] = {}
    failures: list[dict[str, Any]] = []
    triaged_turns: list[dict[str, Any]] = []
    model_name: str | None = None
    transport_style: str | None = None

    def _worker(turn: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        client = HelperAgentClient(transport_style="chat_completions")
        response = client.invoke(_helper_issue_request(turn, language=language))
        raw_payload = dict(response.payload)
        triage = {
            "cluster_label": _normalize_helper_cluster(raw_payload.get("cluster_label"), fallback=_issue_cluster(turn)),
            "priority": _normalize_helper_priority(raw_payload.get("priority")),
            "failure_surface": _normalize_helper_surface(raw_payload.get("failure_surface")),
            "rationale": _excerpt_text(raw_payload.get("rationale"), limit=120),
            "next_probe": _excerpt_text(raw_payload.get("next_probe"), limit=120),
            "model": response.model,
            "transport_style": response.transport_style,
            "elapsed_ms": response.elapsed_ms,
            "fallback_source": response.fallback_source,
            "operation_name": response.operation_name,
        }
        return turn, triage, response.model, response.transport_style

    worker_count = max(1, min(int(concurrency), len(candidate_turns)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_turn = {executor.submit(_worker, turn): turn for turn in candidate_turns}
        for future in as_completed(future_to_turn):
            turn = future_to_turn[future]
            try:
                resolved_turn, triage, response_model, response_transport = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "session_id": turn.get("session_id"),
                        "turn_index": turn.get("turn_index"),
                        "global_turn": turn.get("global_turn"),
                        "error": str(exc),
                    }
                )
                continue
            model_name = model_name or response_model
            transport_style = transport_style or response_transport
            resolved_turn["helper_triage"] = triage
            triaged_turns.append(resolved_turn)
            cluster_distribution[triage["cluster_label"]] = cluster_distribution.get(triage["cluster_label"], 0) + 1
            priority_distribution[triage["priority"]] = priority_distribution.get(triage["priority"], 0) + 1
            failure_surface_distribution[triage["failure_surface"]] = (
                failure_surface_distribution.get(triage["failure_surface"], 0) + 1
            )

    status = "completed" if triaged_turns else "failed"
    top_cluster = None
    if cluster_distribution:
        label, count = sorted(cluster_distribution.items(), key=lambda item: (-item[1], item[0]))[0]
        top_cluster = {"label": label, "count": count}
    return {
        "status": status,
        "candidate_turn_count": len(candidate_turns),
        "analyzed_turn_count": len(triaged_turns),
        "failed_turn_count": len(failures),
        "analysis_concurrency": worker_count,
        "elapsed_ms": max(int((perf_counter() - started_at) * 1000), 0),
        "model": model_name,
        "transport_style": transport_style,
        "cluster_distribution": cluster_distribution,
        "priority_distribution": priority_distribution,
        "failure_surface_distribution": failure_surface_distribution,
        "top_cluster": top_cluster,
        "examples": _helper_issue_examples(triaged_turns),
        "failures": failures,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_note(path: Path, payload: dict[str, Any]) -> None:
    summary = dict(payload.get("summary") or {})
    first_bad = dict(summary.get("first_bad_example") or {})
    helper = dict(payload.get("helper_analysis") or {})
    lines = [
        "# Play Issue Inspect",
        "",
        f"- Passed: `{summary.get('passed')}`",
        f"- Story id: `{payload.get('story_id')}`",
        f"- Language: `{payload.get('language')}`",
        f"- Sessions created: `{summary.get('sessions_created')}`",
        f"- Turns submitted: `{summary.get('turns_submitted')}` / `{payload.get('prompt_count')}`",
        f"- Persistent pollution turn count: `{summary.get('persistent_pollution_turn_count')}`",
        f"- Wrapper leak turn count: `{summary.get('persistent_wrapper_turn_count')}`",
        f"- Language contamination turn count: `{summary.get('persistent_language_contamination_turn_count')}`",
        "",
        "## Render Sources",
        "",
    ]
    for key, value in dict(summary.get("render_source_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(["", "## Failure Reasons", ""])
    for key, value in dict(summary.get("render_failure_reason_distribution") or {}).items():
        lines.append(f"- render `{key}` count=`{value}`")
    for key, value in dict(summary.get("interpret_failure_reason_distribution") or {}).items():
        lines.append(f"- interpret `{key}` count=`{value}`")
    lines.extend(["", "## Issue Clusters", ""])
    for key, value in dict(summary.get("issue_cluster_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(["", "## Helper Triage", ""])
    lines.append(f"- Status: `{helper.get('status')}`")
    if helper.get("model"):
        lines.append(f"- Model: `{helper.get('model')}` transport=`{helper.get('transport_style')}`")
    if helper.get("status") == "completed":
        lines.append(
            f"- Analyzed turns: `{helper.get('analyzed_turn_count')}` / `{helper.get('candidate_turn_count')}`"
        )
        for key, value in dict(helper.get("cluster_distribution") or {}).items():
            lines.append(f"- helper cluster `{key}` count=`{value}`")
        for key, value in dict(helper.get("priority_distribution") or {}).items():
            lines.append(f"- helper priority `{key}` count=`{value}`")
        examples = list(helper.get("examples") or [])
        if examples:
            lines.extend(["", "## Helper Examples", ""])
            for item in examples[:3]:
                lines.append(
                    f"- turn=`{item.get('global_turn')}` cluster=`{item.get('cluster_label')}` priority=`{item.get('priority')}` probe=`{item.get('next_probe')}`"
                )
    elif helper.get("failures"):
        lines.append(f"- Helper failures: `{len(list(helper.get('failures') or []))}`")
    if first_bad:
        lines.extend(
            [
                "",
                "## First Bad Example",
                "",
                f"- Session: `{first_bad.get('session_id')}` turn=`{first_bad.get('turn_index')}`",
                f"- Move family: `{first_bad.get('move_family')}`",
                f"- Input: {first_bad.get('input_text')}",
                f"- Render source: `{first_bad.get('render_source')}` failure=`{first_bad.get('render_failure_reason')}`",
                f"- Narration: {first_bad.get('narration')}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _story_seed(language: StoryLanguage, rng: Random):
    return build_story_seed_batch(rng=rng, story_count=1, language=language)[0]


def _ensure_story(
    session: requests.Session,
    *,
    config: PlayIssueInspectConfig,
    rng: Random,
) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
    live_api_playtest._authenticate_session(session, config.base_url, label=f"play-issue-inspect-{config.language}")
    if config.story_id:
        story_detail, _ = live_api_playtest._get_story_detail(session, config.base_url, config.story_id)
        return config.story_id, story_detail, None

    generated_seed = _story_seed(config.language, rng)
    preview, _ = live_api_playtest._create_story_preview_with_controls(
        session,
        config.base_url,
        generated_seed.seed,
        target_duration_minutes=config.target_duration_minutes,
        language=config.language,
    )
    job, _ = live_api_playtest._create_author_job_with_controls(
        session,
        config.base_url,
        generated_seed.seed,
        str(preview["preview_id"]),
        target_duration_minutes=config.target_duration_minutes,
        language=config.language,
    )
    job_id = str(job["job_id"])
    live_api_playtest._stream_author_job_to_terminal(session, config.base_url, job_id)
    result, _ = live_api_playtest._get_author_job_result(session, config.base_url, job_id)
    if result.get("status") != "completed":
        raise RuntimeError(f"play issue inspect author job did not complete: {result.get('status')}")
    published_story, _ = live_api_playtest._publish_author_job(session, config.base_url, job_id)
    story_id = str(published_story["story_id"])
    story_detail, _ = live_api_playtest._get_story_detail(session, config.base_url, story_id)
    return story_id, story_detail, {
        "generated_seed": generated_seed.seed,
        "job_id": job_id,
        "preview_id": preview.get("preview_id"),
        "published_story": published_story,
    }


def run_play_issue_inspect(config: PlayIssueInspectConfig) -> dict[str, Any]:
    rng = Random(config.seed) if config.seed is not None else Random()
    manager_config = live_api_playtest.LiveApiPlaytestConfig(
        base_url=config.base_url,
        output_dir=config.output_dir,
        label=config.label,
        launch_server=config.launch_server,
        session_ttl_seconds=config.session_ttl_seconds,
        max_turns=None,
        seed=config.seed,
        story_count=1,
        phase_id=None,
        seed_set_id=None,
        arm="candidate",
        baseline_artifact=None,
        managed_server_content_prompt_profile=config.managed_server_content_prompt_profile,
        target_duration_minutes=config.target_duration_minutes,
        agent_transport_style="responses",
        probe_turn_proposal=False,
        stage1_spark_smoke=False,
    )
    session_records: list[dict[str, Any]] = []
    prompt_records: list[dict[str, Any]] = []
    issue_cluster_distribution: dict[str, int] = {}
    render_source_distribution: dict[str, int] = {}
    render_failure_reason_distribution: dict[str, int] = {}
    interpret_failure_reason_distribution: dict[str, int] = {}
    persistent_wrapper_turn_count = 0
    persistent_language_contamination_turn_count = 0
    persistent_second_person_missing_turn_count = 0
    author_context: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory() as tmpdir:
        library_db_path = Path(tmpdir) / "stories.sqlite3" if config.launch_server else None
        manager = live_api_playtest._managed_server(manager_config, library_db_path)
        with manager if config.launch_server else nullcontext():
            session = requests.Session()
            try:
                story_id, story_detail, author_context = _ensure_story(session, config=config, rng=rng)
                while len(prompt_records) < config.prompt_count:
                    created_snapshot, create_elapsed_seconds = live_api_playtest._create_play_session(session, config.base_url, story_id)
                    current_snapshot = created_snapshot
                    current_session_id = str(created_snapshot["session_id"])
                    transcript = [{"speaker": "gm", "text": str(created_snapshot.get("narration") or "")}]
                    session_record = {
                        "session_id": current_session_id,
                        "create_elapsed_seconds": create_elapsed_seconds,
                        "turns": [],
                    }
                    while len(prompt_records) < config.prompt_count and current_snapshot.get("status") == "active":
                        input_text, move_family = _build_random_prompt(current_snapshot, language=config.language, rng=rng)
                        next_snapshot, submit_elapsed_seconds = live_api_playtest._submit_play_turn(
                            session,
                            config.base_url,
                            current_session_id,
                            input_text,
                        )
                        diagnostics, diagnostics_elapsed_seconds = live_api_playtest._get_play_diagnostics(
                            session,
                            config.base_url,
                            current_session_id,
                        )
                        last_trace = dict((diagnostics.get("turn_traces") or [{}])[-1] or {})
                        narration = str(next_snapshot.get("narration") or "")
                        turn_record = {
                            "global_turn": len(prompt_records) + 1,
                            "session_id": current_session_id,
                            "turn_index": next_snapshot.get("turn_index"),
                            "beat_title": next_snapshot.get("beat_title"),
                            "status": next_snapshot.get("status"),
                            "input_text": input_text,
                            "move_family": move_family,
                            "submit_elapsed_seconds": submit_elapsed_seconds,
                            "diagnostics_elapsed_seconds": diagnostics_elapsed_seconds,
                            "narration": narration,
                            "persistent_wrapper_hit": contains_play_meta_wrapper_text(narration),
                            "persistent_language_contamination_hit": has_language_contamination(narration, config.language),
                            "persistent_second_person_missing": not has_second_person_reference(narration, config.language),
                            "render_source": last_trace.get("render_source"),
                            "render_failure_reason": last_trace.get("render_failure_reason"),
                            "interpret_failure_reason": last_trace.get("interpret_failure_reason"),
                            "last_trace": last_trace,
                        }
                        persistent_wrapper_turn_count += int(turn_record["persistent_wrapper_hit"])
                        persistent_language_contamination_turn_count += int(turn_record["persistent_language_contamination_hit"])
                        persistent_second_person_missing_turn_count += int(turn_record["persistent_second_person_missing"])
                        if turn_record["render_source"]:
                            key = str(turn_record["render_source"])
                            render_source_distribution[key] = render_source_distribution.get(key, 0) + 1
                        if turn_record["render_failure_reason"]:
                            key = str(turn_record["render_failure_reason"])
                            render_failure_reason_distribution[key] = render_failure_reason_distribution.get(key, 0) + 1
                        if turn_record["interpret_failure_reason"]:
                            key = str(turn_record["interpret_failure_reason"])
                            interpret_failure_reason_distribution[key] = interpret_failure_reason_distribution.get(key, 0) + 1
                        cluster = _issue_cluster(turn_record)
                        issue_cluster_distribution[cluster] = issue_cluster_distribution.get(cluster, 0) + 1
                        prompt_records.append(turn_record)
                        session_record["turns"].append(turn_record)
                        transcript.append({"speaker": "player", "text": input_text})
                        transcript.append({"speaker": "gm", "text": narration})
                        current_snapshot = next_snapshot
                    session_record["final_status"] = current_snapshot.get("status")
                    session_records.append(session_record)
            finally:
                session.close()

    first_bad_example = next(
        (
            turn
            for turn in prompt_records
            if _issue_cluster(turn) != "clean"
        ),
        None,
    )
    persistent_pollution_turn_count = (
        persistent_wrapper_turn_count + persistent_language_contamination_turn_count + persistent_second_person_missing_turn_count
    )
    helper_analysis = _run_helper_issue_analysis(
        prompt_records=prompt_records,
        language=config.language,
        enabled=config.helper_analysis_enabled,
        max_turns=config.helper_analysis_max_turns,
        concurrency=config.helper_analysis_concurrency,
    )
    summary = {
        "passed": len(prompt_records) == config.prompt_count and persistent_pollution_turn_count == 0,
        "sessions_created": len(session_records),
        "turns_submitted": len(prompt_records),
        "persistent_pollution_turn_count": persistent_pollution_turn_count,
        "persistent_wrapper_turn_count": persistent_wrapper_turn_count,
        "persistent_language_contamination_turn_count": persistent_language_contamination_turn_count,
        "persistent_second_person_missing_turn_count": persistent_second_person_missing_turn_count,
        "render_source_distribution": render_source_distribution,
        "render_failure_reason_distribution": render_failure_reason_distribution,
        "interpret_failure_reason_distribution": interpret_failure_reason_distribution,
        "issue_cluster_distribution": issue_cluster_distribution,
        "first_bad_example": first_bad_example,
        "helper_analysis_status": helper_analysis.get("status"),
        "helper_issue_cluster_distribution": dict(helper_analysis.get("cluster_distribution") or {}),
        "helper_priority_distribution": dict(helper_analysis.get("priority_distribution") or {}),
        "helper_failure_surface_distribution": dict(helper_analysis.get("failure_surface_distribution") or {}),
    }
    return {
        "mode": "play_issue_inspect",
        "base_url": config.base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_server": config.launch_server,
        "story_id": story_id,
        "language": config.language,
        "prompt_count": config.prompt_count,
        "seed": config.seed,
        "author_context": author_context,
        "story_detail": story_detail,
        "sessions": session_records,
        "summary": summary,
        "helper_analysis": helper_analysis,
    }


def write_artifacts(config: PlayIssueInspectConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = config.label or "play_issue_inspect"
    stem = f"{label}_{timestamp}"
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    _write_json(json_path, payload)
    _write_note(md_path, payload)
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_play_issue_inspect(config)
    json_path, md_path = write_artifacts(config, payload)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "passed": bool((payload.get("summary") or {}).get("passed"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

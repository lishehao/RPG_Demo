from __future__ import annotations

import argparse
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


DEFAULT_REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_POLL_TIMEOUT_SECONDS = 180
DEFAULT_SEED = (
    "A municipal archivist finds the blackout ration rolls were altered to punish districts "
    "that backed the reform slate."
)
DEFAULT_TURN_INPUT = (
    "I force the emergency council to compare the sealed ration rolls in public before any "
    "clerk can revise them again."
)


@dataclass(frozen=True)
class HttpProductSmokeConfig:
    base_url: str
    prompt_seed: str
    first_turn_input: str
    poll_interval_seconds: float
    poll_timeout_seconds: float
    request_timeout_seconds: float
    output_path: Path | None
    include_benchmark_diagnostics: bool


def parse_args(argv: list[str] | None = None) -> HttpProductSmokeConfig:
    parser = argparse.ArgumentParser(description="Run a real HTTP author->publish->play smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--prompt-seed", default=DEFAULT_SEED)
    parser.add_argument("--first-turn-input", default=DEFAULT_TURN_INPUT)
    parser.add_argument("--poll-interval-seconds", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--poll-timeout-seconds", type=float, default=DEFAULT_POLL_TIMEOUT_SECONDS)
    parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    parser.add_argument("--output-path")
    parser.add_argument("--include-benchmark-diagnostics", action="store_true")
    args = parser.parse_args(argv)
    return HttpProductSmokeConfig(
        base_url=args.base_url.rstrip("/"),
        prompt_seed=str(args.prompt_seed),
        first_turn_input=str(args.first_turn_input),
        poll_interval_seconds=max(float(args.poll_interval_seconds), 0.05),
        poll_timeout_seconds=max(float(args.poll_timeout_seconds), 1.0),
        request_timeout_seconds=max(float(args.request_timeout_seconds), 1.0),
        output_path=Path(args.output_path).expanduser().resolve() if args.output_path else None,
        include_benchmark_diagnostics=bool(args.include_benchmark_diagnostics),
    )


def _error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"request failed with status {response.status_code}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
    return f"request failed with status {response.status_code}"


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    request_timeout_seconds: float,
    **kwargs: Any,
) -> tuple[dict[str, Any], float]:
    started_at = time.perf_counter()
    response = session.request(method, url, timeout=request_timeout_seconds, **kwargs)
    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    if not response.ok:
        raise RuntimeError(f"{method} {url}: {_error_message(response)}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {url}: expected JSON object payload")
    return payload, elapsed_seconds


def _authenticate_session(
    session: requests.Session,
    config: HttpProductSmokeConfig,
) -> dict[str, Any]:
    response = session.post(
        f"{config.base_url}/auth/register",
        timeout=config.request_timeout_seconds,
        json={
            "display_name": "HTTP Smoke",
            "email": f"http-smoke-{secrets.token_hex(6)}@bench.local",
            "password": "BenchPass123!",
        },
    )
    if not response.ok:
        raise RuntimeError(f"POST {config.base_url}/auth/register: {_error_message(response)}")
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("authenticated"):
        raise RuntimeError("smoke auth registration did not return an authenticated session")
    return payload


def _optional_request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    request_timeout_seconds: float,
    **kwargs: Any,
) -> tuple[dict[str, Any] | None, float]:
    started_at = time.perf_counter()
    response = session.request(method, url, timeout=request_timeout_seconds, **kwargs)
    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    if response.status_code == 404:
        return None, elapsed_seconds
    if not response.ok:
        raise RuntimeError(f"{method} {url}: {_error_message(response)}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {url}: expected JSON object payload")
    return payload, elapsed_seconds


def _stage_timings_summary(diagnostics: dict[str, Any] | None) -> list[dict[str, Any]]:
    if diagnostics is None:
        return []
    rows: list[dict[str, Any]] = []
    for item in list(diagnostics.get("stage_timings") or []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "stage": item.get("stage"),
                "elapsed_ms": item.get("elapsed_ms"),
            }
        )
    return rows


def _poll_author_job(
    session: requests.Session,
    config: HttpProductSmokeConfig,
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


def run_http_product_smoke(config: HttpProductSmokeConfig) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "base_url": config.base_url,
        "prompt_seed": config.prompt_seed,
        "first_turn_input": config.first_turn_input,
        "ok": False,
        "steps": {},
        "contracts": {},
        "ids": {},
        "author": {},
        "play": {},
        "benchmark": {},
    }
    with requests.Session() as session:
        health_payload, health_elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/health",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        summary["steps"]["health"] = {"elapsed_seconds": health_elapsed, "status": health_payload.get("status")}
        auth_payload = _authenticate_session(session, config)
        summary["steps"]["auth"] = {"authenticated": bool(auth_payload.get("authenticated"))}
        summary["contracts"]["auth_user_present"] = isinstance(auth_payload.get("user"), dict)

        preview_payload, preview_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/story-previews",
            request_timeout_seconds=config.request_timeout_seconds,
            json={"prompt_seed": config.prompt_seed},
        )
        summary["steps"]["preview"] = {"elapsed_seconds": preview_elapsed}
        summary["ids"]["preview_id"] = preview_payload.get("preview_id")
        summary["contracts"]["preview_has_flashcards"] = bool(preview_payload.get("flashcards") is not None)
        summary["contracts"]["preview_has_story"] = isinstance(preview_payload.get("story"), dict)

        job_payload, create_job_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs",
            request_timeout_seconds=config.request_timeout_seconds,
            json={
                "prompt_seed": config.prompt_seed,
                "preview_id": preview_payload["preview_id"],
            },
        )
        job_id = str(job_payload["job_id"])
        summary["ids"]["job_id"] = job_id
        summary["steps"]["create_job"] = {"elapsed_seconds": create_job_elapsed}

        author_status, poll_summary = _poll_author_job(session, config, job_id=job_id)
        summary["steps"]["poll_author"] = poll_summary
        summary["author"]["status"] = author_status.get("status")
        summary["author"]["stage"] = dict(author_status.get("progress") or {}).get("stage")

        result_payload, result_elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/author/jobs/{job_id}/result",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        summary["steps"]["get_result"] = {"elapsed_seconds": result_elapsed}
        summary["contracts"]["result_has_summary"] = result_payload.get("summary") is not None
        summary["contracts"]["result_has_bundle"] = result_payload.get("bundle") is not None

        if author_status.get("status") != "completed":
            raise RuntimeError(f"author job '{job_id}' ended with status={author_status.get('status')}")

        publish_payload, publish_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/author/jobs/{job_id}/publish",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        story_id = str(publish_payload["story_id"])
        summary["ids"]["story_id"] = story_id
        summary["steps"]["publish"] = {"elapsed_seconds": publish_elapsed}
        summary["author"]["published_title"] = publish_payload.get("title")

        detail_payload, detail_elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/stories/{story_id}",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        summary["steps"]["story_detail"] = {"elapsed_seconds": detail_elapsed}
        summary["contracts"]["detail_has_play_overview"] = detail_payload.get("play_overview") is not None
        summary["contracts"]["detail_has_presentation"] = detail_payload.get("presentation") is not None
        summary["play"]["runtime_profile"] = dict(detail_payload.get("play_overview") or {}).get("runtime_profile")

        created_session, create_session_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/play/sessions",
            request_timeout_seconds=config.request_timeout_seconds,
            json={"story_id": story_id},
        )
        session_id = str(created_session["session_id"])
        summary["ids"]["session_id"] = session_id
        summary["steps"]["create_session"] = {"elapsed_seconds": create_session_elapsed}
        summary["play"]["opening_status"] = created_session.get("status")
        summary["play"]["opening_beat"] = created_session.get("beat_title")

        turn_payload, submit_turn_elapsed = _request_json(
            session,
            "POST",
            f"{config.base_url}/play/sessions/{session_id}/turns",
            request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
            json={"input_text": config.first_turn_input},
        )
        summary["steps"]["submit_turn"] = {"elapsed_seconds": submit_turn_elapsed}
        summary["play"]["post_turn_status"] = turn_payload.get("status")
        summary["play"]["post_turn_turn_index"] = turn_payload.get("turn_index")
        summary["play"]["post_turn_beat"] = turn_payload.get("beat_title")
        summary["contracts"]["turn_has_feedback"] = turn_payload.get("feedback") is not None
        summary["contracts"]["turn_has_suggested_actions"] = bool(turn_payload.get("suggested_actions"))

        history_payload, history_elapsed = _request_json(
            session,
            "GET",
            f"{config.base_url}/play/sessions/{session_id}/history",
            request_timeout_seconds=config.request_timeout_seconds,
        )
        summary["steps"]["history"] = {"elapsed_seconds": history_elapsed}
        summary["contracts"]["history_entry_count"] = len(list(history_payload.get("entries") or []))

        if config.include_benchmark_diagnostics:
            author_diag, author_diag_elapsed = _optional_request_json(
                session,
                "GET",
                f"{config.base_url}/benchmark/author/jobs/{job_id}/diagnostics",
                request_timeout_seconds=config.request_timeout_seconds,
            )
            play_diag, play_diag_elapsed = _optional_request_json(
                session,
                "GET",
                f"{config.base_url}/benchmark/play/sessions/{session_id}/diagnostics",
                request_timeout_seconds=config.request_timeout_seconds,
            )
            summary["benchmark"] = {
                "author_diagnostics_available": author_diag is not None,
                "play_diagnostics_available": play_diag is not None,
                "author_diagnostics_elapsed_seconds": author_diag_elapsed,
                "play_diagnostics_elapsed_seconds": play_diag_elapsed,
                "author_stage_timings": _stage_timings_summary(author_diag),
                "play_summary": dict((play_diag or {}).get("summary") or {}),
            }

    summary["ok"] = True
    return summary


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_http_product_smoke(config)
    if config.output_path is not None:
        write_output(config.output_path, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

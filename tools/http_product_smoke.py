from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import Settings
from rpg_backend.roster.loader import load_character_roster_runtime_catalog

DEFAULT_REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_POLL_TIMEOUT_SECONDS = 180
DEFAULT_LANGUAGE = "en"
DEFAULT_SEED = (
    "A municipal archivist finds the blackout ration rolls were altered to punish districts "
    "that backed the reform slate."
)
DEFAULT_ZH_SEED = "一名市政档案官发现，停电后的配给名册被人动过手脚，用来惩罚支持改革派的街区。"
DEFAULT_TURN_INPUT = (
    "I force the emergency council to compare the sealed ration rolls in public before any "
    "clerk can revise them again."
)
DEFAULT_ZH_TURN_INPUT = "我要求紧急委员会当众对照被封存的配给名册和账本，逼所有人公开解释差异。"
DEFAULT_COPILOT_MESSAGE = (
    "Broaden the story rules and political texture, push the draft toward public record exposure, "
    "and keep the same runtime lane."
)
DEFAULT_ZH_COPILOT_MESSAGE = "在不改变当前玩法轮廓的前提下，强化公开记录曝光与政治拉扯，让世界规则、角色关系和节拍反馈更鲜明。"
_CJK_CODEPOINT_START = 0x4E00
_CJK_CODEPOINT_END = 0x9FFF
SmokeLanguage = Literal["en", "zh"]


class HttpProductSmokeRequestError(RuntimeError):
    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class HttpProductSmokeFailure(RuntimeError):
    def __init__(self, message: str, *, summary: dict[str, Any], error_code: str | None = None) -> None:
        super().__init__(message)
        self.summary = summary
        self.error_code = error_code


@dataclass(frozen=True)
class HttpProductSmokeConfig:
    base_url: str
    language: SmokeLanguage
    prompt_seed: str
    first_turn_input: str
    copilot_message: str
    poll_interval_seconds: float
    poll_timeout_seconds: float
    request_timeout_seconds: float
    output_path: Path | None
    include_copilot: bool
    include_benchmark_diagnostics: bool


def parse_args(argv: list[str] | None = None) -> HttpProductSmokeConfig:
    parser = argparse.ArgumentParser(description="Run a real HTTP author->publish->play smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--language", choices=("en", "zh"), default=DEFAULT_LANGUAGE)
    parser.add_argument("--prompt-seed")
    parser.add_argument("--first-turn-input")
    parser.add_argument("--copilot-message")
    parser.add_argument("--poll-interval-seconds", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--poll-timeout-seconds", type=float, default=DEFAULT_POLL_TIMEOUT_SECONDS)
    parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    parser.add_argument("--output-path")
    parser.add_argument("--include-copilot", action="store_true")
    parser.add_argument("--include-benchmark-diagnostics", action="store_true")
    args = parser.parse_args(argv)
    return HttpProductSmokeConfig(
        base_url=args.base_url.rstrip("/"),
        language=str(args.language),  # type: ignore[arg-type]
        prompt_seed=str(args.prompt_seed or _default_seed(str(args.language))),
        first_turn_input=str(args.first_turn_input or _default_turn_input(str(args.language))),
        copilot_message=str(args.copilot_message or _default_copilot_message(str(args.language))),
        poll_interval_seconds=max(float(args.poll_interval_seconds), 0.05),
        poll_timeout_seconds=max(float(args.poll_timeout_seconds), 1.0),
        request_timeout_seconds=max(float(args.request_timeout_seconds), 1.0),
        output_path=Path(args.output_path).expanduser().resolve() if args.output_path else None,
        include_copilot=bool(args.include_copilot),
        include_benchmark_diagnostics=bool(args.include_benchmark_diagnostics),
    )


def _default_seed(language: str) -> str:
    return DEFAULT_ZH_SEED if language == "zh" else DEFAULT_SEED


def _default_turn_input(language: str) -> str:
    return DEFAULT_ZH_TURN_INPUT if language == "zh" else DEFAULT_TURN_INPUT


def _default_copilot_message(language: str) -> str:
    return DEFAULT_ZH_COPILOT_MESSAGE if language == "zh" else DEFAULT_COPILOT_MESSAGE


def _contains_cjk_text(value: str) -> bool:
    return any(_CJK_CODEPOINT_START <= ord(ch) <= _CJK_CODEPOINT_END for ch in value)


def _text_matches_language(value: str | None, language: SmokeLanguage) -> bool:
    normalized = str(value or "").strip()
    if not normalized:
        return False
    if language == "zh":
        return _contains_cjk_text(normalized)
    return True


def _load_smoke_settings() -> Settings:
    return Settings()


def _smoke_preflight(config: HttpProductSmokeConfig) -> dict[str, Any]:
    settings = _load_smoke_settings()
    required_llm_fields = {
        "APP_GATEWAY_BASE_URL": settings.resolved_gateway_base_url(),
        "APP_GATEWAY_API_KEY": settings.resolved_gateway_api_key(),
        "APP_GATEWAY_MODEL": settings.resolved_gateway_model(),
    }
    missing_llm = [name for name, value in required_llm_fields.items() if not str(value or "").strip()]
    if missing_llm:
        raise RuntimeError(
            "smoke preflight failed: missing required generation config "
            + ", ".join(missing_llm)
        )
    summary: dict[str, Any] = {
        "llm_configured": True,
        "llm_model": settings.resolved_gateway_model(),
        "backend_default_transport_style": "responses",
        "benchmark_api_enabled": bool(settings.enable_benchmark_api),
        "roster_enabled": bool(settings.roster_enabled),
    }
    if settings.roster_enabled:
        required_embedding_fields = {
            "APP_GATEWAY_EMBEDDING_BASE_URL": settings.resolved_gateway_embedding_base_url(),
            "APP_GATEWAY_EMBEDDING_API_KEY": settings.resolved_gateway_embedding_api_key(),
            "APP_GATEWAY_EMBEDDING_MODEL": settings.resolved_gateway_embedding_model(),
        }
        missing_embedding = [name for name, value in required_embedding_fields.items() if not str(value or "").strip()]
        if missing_embedding:
            raise RuntimeError(
                "smoke preflight failed: roster is enabled but embedding config is incomplete: "
                + ", ".join(missing_embedding)
            )
        catalog = load_character_roster_runtime_catalog(settings.roster_runtime_catalog_path)
        summary.update(
            {
                "roster_runtime_catalog_path": settings.roster_runtime_catalog_path,
                "roster_runtime_catalog_version": catalog.catalog_version,
                "roster_runtime_entry_count": catalog.entry_count,
                "roster_embedding_model": settings.resolved_gateway_embedding_model(),
            }
        )
    return summary


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


def _error_code(response: requests.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return error["code"]
    return None


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
        raise HttpProductSmokeRequestError(
            f"{method} {url}: {_error_message(response)}",
            error_code=_error_code(response),
        )
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
        "language": config.language,
        "prompt_seed": config.prompt_seed,
        "first_turn_input": config.first_turn_input,
        "copilot_message": config.copilot_message if config.include_copilot else None,
        "ok": False,
        "steps": {},
        "contracts": {},
        "ids": {},
        "preflight": {},
        "author": {},
        "copilot": {"enabled": config.include_copilot},
        "play": {},
        "benchmark": {},
    }
    current_step = "preflight"
    try:
        preflight_summary = _smoke_preflight(config)
        summary["preflight"] = preflight_summary
        summary["steps"]["preflight"] = {"ok": True}
        with requests.Session() as session:
            current_step = "health"
            health_payload, health_elapsed = _request_json(session, "GET", f"{config.base_url}/health", request_timeout_seconds=config.request_timeout_seconds)
            summary["steps"]["health"] = {"elapsed_seconds": health_elapsed, "status": health_payload.get("status")}

            current_step = "auth"
            auth_payload = _authenticate_session(session, config)
            summary["steps"]["auth"] = {"authenticated": bool(auth_payload.get("authenticated"))}
            summary["contracts"]["auth_user_present"] = isinstance(auth_payload.get("user"), dict)

            current_step = "preview"
            preview_payload, preview_elapsed = _request_json(
                session,
                "POST",
                f"{config.base_url}/author/story-previews",
                request_timeout_seconds=config.request_timeout_seconds,
                json={"prompt_seed": config.prompt_seed, "language": config.language},
            )
            summary["steps"]["preview"] = {"elapsed_seconds": preview_elapsed}
            summary["ids"]["preview_id"] = preview_payload.get("preview_id")
            summary["contracts"]["preview_has_flashcards"] = bool(preview_payload.get("flashcards") is not None)
            summary["contracts"]["preview_has_story"] = isinstance(preview_payload.get("story"), dict)
            summary["contracts"]["preview_language_matches_request"] = preview_payload.get("language") == config.language

            current_step = "create_job"
            job_payload, create_job_elapsed = _request_json(
                session,
                "POST",
                f"{config.base_url}/author/jobs",
                request_timeout_seconds=config.request_timeout_seconds,
                json={"prompt_seed": config.prompt_seed, "preview_id": preview_payload["preview_id"], "language": config.language},
            )
            job_id = str(job_payload["job_id"])
            summary["ids"]["job_id"] = job_id
            summary["steps"]["create_job"] = {"elapsed_seconds": create_job_elapsed}

            current_step = "poll_author"
            author_status, poll_summary = _poll_author_job(session, config, job_id=job_id)
            summary["steps"]["poll_author"] = poll_summary
            summary["author"]["status"] = author_status.get("status")
            summary["author"]["stage"] = dict(author_status.get("progress") or {}).get("stage")
            summary["author"]["error"] = dict(author_status.get("error") or {}) or None

            current_step = "get_result"
            result_payload, result_elapsed = _request_json(
                session,
                "GET",
                f"{config.base_url}/author/jobs/{job_id}/result",
                request_timeout_seconds=config.request_timeout_seconds,
            )
            summary["steps"]["get_result"] = {"elapsed_seconds": result_elapsed}
            summary["contracts"]["result_has_summary"] = result_payload.get("summary") is not None
            summary["contracts"]["result_has_bundle"] = result_payload.get("bundle") is not None
            summary["contracts"]["result_summary_language_matches_request"] = (
                isinstance(result_payload.get("summary"), dict)
                and dict(result_payload.get("summary") or {}).get("language") == config.language
            )
            if author_status.get("status") != "completed":
                raise RuntimeError(f"author job '{job_id}' ended with status={author_status.get('status')}")

            if config.include_copilot:
                current_step = "editor_state_before_copilot"
                editor_state_before, editor_state_before_elapsed = _request_json(session, "GET", f"{config.base_url}/author/jobs/{job_id}/editor-state", request_timeout_seconds=config.request_timeout_seconds)
                summary["steps"]["editor_state_before_copilot"] = {"elapsed_seconds": editor_state_before_elapsed}
                summary["contracts"]["editor_state_before_language_matches_request"] = editor_state_before.get("language") == config.language
                summary["contracts"]["editor_state_before_has_copilot_view"] = isinstance(editor_state_before.get("copilot_view"), dict)
                before_profile = dict(editor_state_before.get("play_profile_view") or {})
                suggested_instructions = list(dict(editor_state_before.get("copilot_view") or {}).get("suggested_instructions") or [])
                selected_instruction = str(
                    next(
                        (
                            item.get("instruction")
                            for item in suggested_instructions
                            if isinstance(item, dict) and str(item.get("instruction") or "").strip()
                        ),
                        "",
                    )
                    or config.copilot_message
                ).strip()
                summary["copilot"]["instruction_source"] = "suggested" if selected_instruction != config.copilot_message else "default"
                summary["copilot"]["instruction_preview"] = selected_instruction[:120]

                current_step = "copilot_create_session"
                copilot_session_payload, copilot_session_elapsed = _request_json(
                    session,
                    "POST",
                    f"{config.base_url}/author/jobs/{job_id}/copilot/sessions",
                    request_timeout_seconds=config.request_timeout_seconds,
                    json={"hidden": False},
                )
                session_id = str(copilot_session_payload["session_id"])
                summary["steps"]["copilot_create_session"] = {"elapsed_seconds": copilot_session_elapsed}
                summary["copilot"]["session_id"] = session_id

                current_step = "copilot_get_session"
                copilot_loaded_session, copilot_loaded_session_elapsed = _request_json(
                    session,
                    "GET",
                    f"{config.base_url}/author/jobs/{job_id}/copilot/sessions/{session_id}",
                    request_timeout_seconds=config.request_timeout_seconds,
                )
                summary["steps"]["copilot_get_session"] = {"elapsed_seconds": copilot_loaded_session_elapsed}
                rewrite_brief = dict(copilot_loaded_session.get("rewrite_brief") or {})
                summary["contracts"]["copilot_loaded_session_matches_created_session"] = copilot_loaded_session.get("session_id") == session_id
                summary["contracts"]["copilot_loaded_session_has_rewrite_brief"] = bool(rewrite_brief)

                current_step = "copilot_message"
                copilot_message_payload, copilot_message_elapsed = _request_json(
                    session,
                    "POST",
                    f"{config.base_url}/author/jobs/{job_id}/copilot/sessions/{session_id}/messages",
                    request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
                    json={"content": selected_instruction},
                )
                summary["steps"]["copilot_message"] = {"elapsed_seconds": copilot_message_elapsed}
                assistant_messages = [item for item in list(copilot_message_payload.get("messages") or []) if isinstance(item, dict) and item.get("role") == "assistant"]
                last_assistant_message = dict(assistant_messages[-1] or {}) if assistant_messages else {}
                summary["contracts"]["copilot_message_language_matches_request"] = _text_matches_language(str(last_assistant_message.get("content") or ""), config.language)

                current_step = "copilot_proposal"
                copilot_proposal_payload, copilot_proposal_elapsed = _request_json(
                    session,
                    "POST",
                    f"{config.base_url}/author/jobs/{job_id}/copilot/sessions/{session_id}/proposal",
                    request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
                )
                proposal_id = str(copilot_proposal_payload["proposal_id"])
                summary["steps"]["copilot_proposal"] = {"elapsed_seconds": copilot_proposal_elapsed}
                summary["copilot"]["proposal_id"] = proposal_id
                summary["copilot"]["variant_label"] = copilot_proposal_payload.get("variant_label")
                summary["copilot"]["affected_sections"] = list(copilot_proposal_payload.get("affected_sections") or [])
                summary["contracts"]["copilot_variant_label_matches_request_language"] = _text_matches_language(str(copilot_proposal_payload.get("variant_label") or ""), config.language)
                summary["contracts"]["copilot_request_summary_matches_request_language"] = _text_matches_language(str(copilot_proposal_payload.get("request_summary") or ""), config.language)

                current_step = "copilot_preview"
                copilot_preview_payload, copilot_preview_elapsed = _request_json(
                    session,
                    "POST",
                    f"{config.base_url}/author/jobs/{job_id}/copilot/proposals/{proposal_id}/preview",
                    request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
                )
                summary["steps"]["copilot_preview"] = {"elapsed_seconds": copilot_preview_elapsed}
                copilot_preview_editor_state = dict(copilot_preview_payload.get("editor_state") or {})
                summary["copilot"]["preview_revision"] = copilot_preview_editor_state.get("revision")
                summary["contracts"]["copilot_preview_language_matches_request"] = copilot_preview_editor_state.get("language") == config.language

                current_step = "copilot_apply"
                copilot_apply_payload, copilot_apply_elapsed = _request_json(
                    session,
                    "POST",
                    f"{config.base_url}/author/jobs/{job_id}/copilot/proposals/{proposal_id}/apply",
                    request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
                )
                summary["steps"]["copilot_apply"] = {"elapsed_seconds": copilot_apply_elapsed}
                summary["contracts"]["copilot_apply_status_applied"] = isinstance(copilot_apply_payload.get("proposal"), dict) and dict(copilot_apply_payload.get("proposal") or {}).get("status") == "applied"

                current_step = "editor_state_after_copilot_apply"
                editor_state_after, editor_state_after_elapsed = _request_json(session, "GET", f"{config.base_url}/author/jobs/{job_id}/editor-state", request_timeout_seconds=config.request_timeout_seconds)
                summary["steps"]["editor_state_after_copilot_apply"] = {"elapsed_seconds": editor_state_after_elapsed}
                summary["copilot"]["applied_revision"] = editor_state_after.get("revision")
                summary["copilot"]["revision_changed"] = bool(summary["copilot"].get("preview_revision")) and bool(summary["copilot"].get("applied_revision")) and summary["copilot"]["preview_revision"] != summary["copilot"]["applied_revision"]
                after_profile = dict(editor_state_after.get("play_profile_view") or {})
                summary["copilot"]["runtime_profile_preserved"] = before_profile.get("runtime_profile") == after_profile.get("runtime_profile")
                summary["copilot"]["closeout_profile_preserved"] = before_profile.get("closeout_profile") == after_profile.get("closeout_profile")
                summary["copilot"]["max_turns_preserved"] = before_profile.get("max_turns") == after_profile.get("max_turns")
                summary["contracts"]["editor_state_after_language_matches_request"] = editor_state_after.get("language") == config.language

                current_step = "copilot_undo"
                undo_proposal_id = str(
                    dict(editor_state_after.get("copilot_view") or {}).get("undo_proposal_id")
                    or proposal_id
                )
                copilot_undo_payload, copilot_undo_elapsed = _request_json(
                    session,
                    "POST",
                    f"{config.base_url}/author/jobs/{job_id}/copilot/proposals/{undo_proposal_id}/undo",
                    request_timeout_seconds=max(config.request_timeout_seconds, 120.0),
                )
                summary["steps"]["copilot_undo"] = {"elapsed_seconds": copilot_undo_elapsed}
                summary["copilot"]["undo_proposal_id"] = undo_proposal_id
                summary["contracts"]["copilot_undo_response_received"] = isinstance(copilot_undo_payload.get("proposal"), dict)

                current_step = "editor_state_after_copilot_undo"
                editor_state_after_undo, editor_state_after_undo_elapsed = _request_json(
                    session,
                    "GET",
                    f"{config.base_url}/author/jobs/{job_id}/editor-state",
                    request_timeout_seconds=config.request_timeout_seconds,
                )
                summary["steps"]["editor_state_after_copilot_undo"] = {"elapsed_seconds": editor_state_after_undo_elapsed}
                summary["copilot"]["undo_revision"] = editor_state_after_undo.get("revision")
                summary["copilot"]["undo_restored_revision"] = (
                    bool(editor_state_before.get("revision"))
                    and bool(summary["copilot"].get("undo_revision"))
                    and editor_state_before.get("revision") == summary["copilot"]["undo_revision"]
                )
                undo_profile = dict(editor_state_after_undo.get("play_profile_view") or {})
                summary["copilot"]["runtime_profile_preserved_after_undo"] = before_profile.get("runtime_profile") == undo_profile.get("runtime_profile")
                summary["copilot"]["closeout_profile_preserved_after_undo"] = before_profile.get("closeout_profile") == undo_profile.get("closeout_profile")
                summary["copilot"]["max_turns_preserved_after_undo"] = before_profile.get("max_turns") == undo_profile.get("max_turns")
                summary["contracts"]["editor_state_after_undo_language_matches_request"] = editor_state_after_undo.get("language") == config.language

            current_step = "publish"
            publish_payload, publish_elapsed = _request_json(session, "POST", f"{config.base_url}/author/jobs/{job_id}/publish", request_timeout_seconds=config.request_timeout_seconds)
            story_id = str(publish_payload["story_id"])
            summary["ids"]["story_id"] = story_id
            summary["steps"]["publish"] = {"elapsed_seconds": publish_elapsed}
            summary["author"]["published_title"] = publish_payload.get("title")
            summary["contracts"]["published_story_language_matches_request"] = publish_payload.get("language") == config.language

            current_step = "story_detail"
            detail_payload, detail_elapsed = _request_json(session, "GET", f"{config.base_url}/stories/{story_id}", request_timeout_seconds=config.request_timeout_seconds)
            summary["steps"]["story_detail"] = {"elapsed_seconds": detail_elapsed}
            summary["contracts"]["detail_has_play_overview"] = detail_payload.get("play_overview") is not None
            summary["contracts"]["detail_has_presentation"] = detail_payload.get("presentation") is not None
            summary["contracts"]["story_detail_language_matches_request"] = isinstance(detail_payload.get("story"), dict) and dict(detail_payload.get("story") or {}).get("language") == config.language
            summary["play"]["runtime_profile"] = dict(detail_payload.get("play_overview") or {}).get("runtime_profile")

            current_step = "create_session"
            created_session, create_session_elapsed = _request_json(session, "POST", f"{config.base_url}/play/sessions", request_timeout_seconds=config.request_timeout_seconds, json={"story_id": story_id})
            session_id = str(created_session["session_id"])
            summary["ids"]["session_id"] = session_id
            summary["steps"]["create_session"] = {"elapsed_seconds": create_session_elapsed}
            summary["play"]["opening_status"] = created_session.get("status")
            summary["play"]["opening_beat"] = created_session.get("beat_title")
            summary["contracts"]["play_session_language_matches_request"] = created_session.get("language") == config.language

            current_step = "submit_turn"
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
            summary["contracts"]["turn_language_matches_request"] = turn_payload.get("language") == config.language
            summary["contracts"]["turn_narration_matches_request_language"] = _text_matches_language(str(turn_payload.get("narration") or ""), config.language)

            current_step = "history"
            history_payload, history_elapsed = _request_json(session, "GET", f"{config.base_url}/play/sessions/{session_id}/history", request_timeout_seconds=config.request_timeout_seconds)
            summary["steps"]["history"] = {"elapsed_seconds": history_elapsed}
            summary["contracts"]["history_entry_count"] = len(list(history_payload.get("entries") or []))
            summary["contracts"]["history_language_matches_request"] = history_payload.get("language") == config.language

            if config.include_benchmark_diagnostics:
                current_step = "benchmark_diagnostics"
                author_diag, author_diag_elapsed = _optional_request_json(session, "GET", f"{config.base_url}/benchmark/author/jobs/{job_id}/diagnostics", request_timeout_seconds=config.request_timeout_seconds)
                play_diag, play_diag_elapsed = _optional_request_json(session, "GET", f"{config.base_url}/benchmark/play/sessions/{session_id}/diagnostics", request_timeout_seconds=config.request_timeout_seconds)
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
    except Exception as exc:  # noqa: BLE001
        summary["ok"] = False
        summary["failed_step"] = current_step
        summary["error_message"] = str(exc)
        error_code = getattr(exc, "error_code", None)
        if error_code:
            summary["error_code"] = error_code
        raise HttpProductSmokeFailure(str(exc), summary=summary, error_code=error_code) from exc


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    try:
        payload = run_http_product_smoke(config)
        exit_code = 0
    except HttpProductSmokeFailure as exc:
        payload = exc.summary
        exit_code = 1
    if config.output_path is not None:
        write_output(config.output_path, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

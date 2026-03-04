from __future__ import annotations

import json
import time
from typing import Any, Callable

from fastapi import HTTPException
from sqlmodel import Session

from rpg_backend.api.schemas import SessionStepRequest, SessionStepResponse
from rpg_backend.config.settings import get_settings
from rpg_backend.domain.constants import GLOBAL_HELP_ME_PROGRESS_MOVE_ID
from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.llm.base import LLMProviderConfigError
from rpg_backend.llm.factory import get_llm_provider
from rpg_backend.observability.logging import build_input_log_fields, log_event
from rpg_backend.runtime.errors import RuntimeNarrationError, RuntimeRouteError
from rpg_backend.runtime.service import RuntimeService
from rpg_backend.storage.repositories.runtime_events import save_runtime_event
from rpg_backend.storage.repositories.sessions import (
    commit_step_transition_if_turn_matches,
    get_session as get_session_record,
    get_session_action,
)
from rpg_backend.storage.repositories.stories import get_story_version

_SESSION_CONFLICT_ERROR_CODE = "session_conflict_retry"
_SESSION_CONFLICT_MESSAGE = "session advanced by another action; retry with new client_action_id"


def _normalize_step_input(raw_input) -> dict[str, str]:
    if raw_input is None:
        return {"type": "text", "text": ""}

    raw_type = (raw_input.type or "").strip().lower()
    move_id = (raw_input.move_id or "").strip() if raw_input.move_id is not None else ""
    text = raw_input.text or ""

    if raw_type == "button":
        if move_id:
            return {"type": "button", "move_id": move_id}
        return {"type": "button", "move_id": GLOBAL_HELP_ME_PROGRESS_MOVE_ID}

    if raw_type == "text":
        return {"type": "text", "text": text}

    return {"type": "text", "text": text}


def _build_runtime_or_503(provider_factory: Callable[[], Any]) -> RuntimeService:
    try:
        provider = provider_factory()
    except LLMProviderConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "service_unavailable",
                "message": f"llm provider misconfigured: {exc}",
                "retryable": False,
            },
        ) from exc
    return RuntimeService(provider)


def _llm_runtime_failure_detail(exc: RuntimeRouteError | RuntimeNarrationError) -> dict[str, Any]:
    return {
        "error_code": exc.error_code,
        "stage": exc.stage,
        "message": exc.message,
        "provider": exc.provider,
        "retryable": True,
    }


def _provider_name() -> str:
    return "openai"


def _emit_step_replayed_event(
    *,
    db: Session,
    session_id: str,
    story_id: str,
    turn_index: int,
    client_action_id: str,
    session_action_id: str,
    request_id: str,
    note: str,
) -> None:
    save_runtime_event(
        db,
        session_id=session_id,
        turn_index=turn_index,
        event_type="step_replayed",
        payload_json={
            "client_action_id": client_action_id,
            "session_action_id": session_action_id,
            "note": note,
            "request_id": request_id,
        },
    )
    log_event(
        "session_step_replayed",
        level="INFO",
        request_id=request_id,
        session_id=session_id,
        story_id=story_id,
        turn_index=turn_index,
        client_action_id=client_action_id,
    )


def _emit_step_conflicted_event(
    *,
    db: Session,
    session_id: str,
    story_id: str,
    turn_index_expected: int,
    actual_turn_index: int,
    client_action_id: str,
    scene_id_before: str,
    beat_index_before: int,
    request_id: str,
    input_log_fields: dict[str, Any],
) -> None:
    save_runtime_event(
        db,
        session_id=session_id,
        turn_index=turn_index_expected,
        event_type="step_conflicted",
        payload_json={
            "client_action_id": client_action_id,
            "expected_turn_index": turn_index_expected,
            "actual_turn_index": actual_turn_index,
            "scene_id_before": scene_id_before,
            "beat_index_before": beat_index_before,
            "request_id": request_id,
            "note": "optimistic_write_conflict",
        },
    )
    log_event(
        "session_step_conflicted",
        level="WARN",
        request_id=request_id,
        session_id=session_id,
        story_id=story_id,
        turn_index=turn_index_expected,
        client_action_id=client_action_id,
        expected_turn_index=turn_index_expected,
        actual_turn_index=actual_turn_index,
        scene_id_before=scene_id_before,
        beat_index_before=beat_index_before,
        error_code=_SESSION_CONFLICT_ERROR_CODE,
        **input_log_fields,
    )


def _build_session_conflict_detail(
    *,
    session_id: str,
    expected_turn_index: int,
    actual_turn_index: int,
) -> dict[str, Any]:
    return {
        "error_code": _SESSION_CONFLICT_ERROR_CODE,
        "message": _SESSION_CONFLICT_MESSAGE,
        "session_id": session_id,
        "expected_turn_index": expected_turn_index,
        "actual_turn_index": actual_turn_index,
        "retryable": True,
    }


def process_step_request(
    *,
    db: Session,
    session_id: str,
    payload: SessionStepRequest,
    request_id: str,
    provider_factory: Callable[[], Any] = get_llm_provider,
) -> SessionStepResponse:
    settings = get_settings()
    session = get_session_record(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session.ended:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "session_inactive", "message": "inactive session", "retryable": False},
        )

    normalized_input = _normalize_step_input(payload.input)
    turn_index_expected = session.turn_count + 1
    scene_id_before = session.current_scene_id
    beat_index_before = session.beat_index
    input_log_fields = build_input_log_fields(normalized_input, redact_text=settings.obs_redact_input_text)

    existing = get_session_action(db, session_id, payload.client_action_id)
    if existing is not None:
        _emit_step_replayed_event(
            db=db,
            session_id=session.id,
            story_id=session.story_id,
            turn_index=session.turn_count,
            client_action_id=payload.client_action_id,
            session_action_id=existing.id,
            request_id=request_id,
            note="idempotency_replay",
        )
        return SessionStepResponse.model_validate(existing.response_json)

    story_version = get_story_version(db, session.story_id, session.version)
    if story_version is None:
        raise HTTPException(status_code=404, detail="story version not found")

    pack = StoryPack.model_validate(story_version.pack_json)
    runtime = _build_runtime_or_503(provider_factory)
    provider = runtime.provider
    provider_name = _provider_name()
    route_model = getattr(provider, "route_model", None)
    narration_model = getattr(provider, "narration_model", None)

    save_runtime_event(
        db,
        session_id=session.id,
        turn_index=turn_index_expected,
        event_type="step_started",
        payload_json={
            "client_action_id": payload.client_action_id,
            "turn_index_expected": turn_index_expected,
            "input": normalized_input,
            "scene_id_before": scene_id_before,
            "beat_index_before": beat_index_before,
            "provider": provider_name,
            "request_id": request_id,
            "route_model": route_model,
            "narration_model": narration_model,
        },
    )
    log_event(
        "session_step_started",
        level="INFO",
        request_id=request_id,
        session_id=session.id,
        story_id=session.story_id,
        turn_index=turn_index_expected,
        client_action_id=payload.client_action_id,
        scene_id_before=scene_id_before,
        beat_index_before=beat_index_before,
        provider=provider_name,
        route_model=route_model,
        narration_model=narration_model,
        **input_log_fields,
    )

    working_state = json.loads(json.dumps(session.state_json))
    working_beat_progress = json.loads(json.dumps(session.beat_progress_json))
    started_at = time.perf_counter()

    try:
        result = runtime.process_step(
            pack,
            current_scene_id=session.current_scene_id,
            beat_index=session.beat_index,
            state=working_state,
            beat_progress=working_beat_progress,
            action_input=normalized_input,
            dev_mode=payload.dev_mode,
        )
    except (RuntimeRouteError, RuntimeNarrationError) as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        save_runtime_event(
            db,
            session_id=session.id,
            turn_index=turn_index_expected,
            event_type="step_failed",
            payload_json={
                "client_action_id": payload.client_action_id,
                "turn_index_expected": turn_index_expected,
                "scene_id_before": scene_id_before,
                "beat_index_before": beat_index_before,
                "error_code": exc.error_code,
                "stage": exc.stage,
                "message": exc.message,
                "provider": exc.provider,
                "request_id": request_id,
                "route_model": route_model,
                "narration_model": narration_model,
                "duration_ms": duration_ms,
            },
        )
        log_event(
            "session_step_failed",
            level="ERROR",
            request_id=request_id,
            session_id=session.id,
            story_id=session.story_id,
            turn_index=turn_index_expected,
            client_action_id=payload.client_action_id,
            scene_id_before=scene_id_before,
            beat_index_before=beat_index_before,
            error_code=exc.error_code,
            stage=exc.stage,
            message=exc.message,
            provider=exc.provider,
            route_model=route_model,
            narration_model=narration_model,
            duration_ms=duration_ms,
            **input_log_fields,
        )
        raise HTTPException(status_code=503, detail=_llm_runtime_failure_detail(exc)) from exc

    duration_ms = int((time.perf_counter() - started_at) * 1000)

    response_payload = {
        "session_id": session.id,
        "version": session.version,
        "scene_id": result["scene_id"],
        "narration_text": result["narration_text"],
        "recognized": result["recognized"],
        "resolution": result["resolution"],
        "ui": result["ui"],
        "debug": result.get("debug"),
    }

    commit_result = commit_step_transition_if_turn_matches(
        db,
        session_id=session.id,
        expected_turn_count=turn_index_expected - 1,
        new_scene_id=result["scene_id"],
        new_beat_index=result["beat_index"],
        new_state_json=working_state,
        new_beat_progress_json=working_beat_progress,
        new_ended=bool(result["ended"]),
        client_action_id=payload.client_action_id,
        request_json=payload.model_dump(),
        response_json=response_payload,
    )
    if not commit_result.applied:
        replayed = get_session_action(db, session_id, payload.client_action_id)
        if replayed is not None:
            replay_turn_index = max(commit_result.actual_turn_count, session.turn_count)
            _emit_step_replayed_event(
                db=db,
                session_id=session.id,
                story_id=session.story_id,
                turn_index=replay_turn_index,
                client_action_id=payload.client_action_id,
                session_action_id=replayed.id,
                request_id=request_id,
                note="idempotency_replay_after_conflict",
            )
            return SessionStepResponse.model_validate(replayed.response_json)

        actual_turn_index = commit_result.actual_turn_count + 1
        _emit_step_conflicted_event(
            db=db,
            session_id=session.id,
            story_id=session.story_id,
            turn_index_expected=turn_index_expected,
            actual_turn_index=actual_turn_index,
            client_action_id=payload.client_action_id,
            scene_id_before=scene_id_before,
            beat_index_before=beat_index_before,
            request_id=request_id,
            input_log_fields=input_log_fields,
        )
        raise HTTPException(
            status_code=409,
            detail=_build_session_conflict_detail(
                session_id=session.id,
                expected_turn_index=turn_index_expected,
                actual_turn_index=actual_turn_index,
            ),
        )

    turn_index_applied = commit_result.actual_turn_count

    save_runtime_event(
        db,
        session_id=session.id,
        turn_index=turn_index_applied,
        event_type="step_succeeded",
        payload_json={
            "client_action_id": payload.client_action_id,
            "turn_index": turn_index_applied,
            "scene_id_before": scene_id_before,
            "scene_id_after": result["scene_id"],
            "beat_index_before": beat_index_before,
            "beat_index_after": result["beat_index"],
            "ended": bool(result["ended"]),
            "recognized": result["recognized"],
            "resolution": result["resolution"],
            "narration_text": result["narration_text"],
            "request_id": request_id,
            "route_model": route_model,
            "narration_model": narration_model,
            "duration_ms": duration_ms,
        },
    )
    log_event(
        "session_step_succeeded",
        level="INFO",
        request_id=request_id,
        session_id=session.id,
        story_id=session.story_id,
        turn_index=turn_index_applied,
        client_action_id=payload.client_action_id,
        scene_id_before=scene_id_before,
        scene_id_after=result["scene_id"],
        beat_index_before=beat_index_before,
        beat_index_after=result["beat_index"],
        ended=bool(result["ended"]),
        provider=provider_name,
        route_model=route_model,
        narration_model=narration_model,
        route_source=result["recognized"].get("route_source"),
        narration_text_len=len(result["narration_text"] or ""),
        duration_ms=duration_ms,
        **input_log_fields,
    )

    return SessionStepResponse.model_validate(response_payload)

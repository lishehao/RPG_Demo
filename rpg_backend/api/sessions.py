from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.api.errors import ApiError
from rpg_backend.api.route_paths import API_SESSIONS_PREFIX
from rpg_backend.api.schemas import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionGetResponse,
    SessionHistoryResponse,
    SessionHistoryTurn,
    SessionStepRequest,
    SessionStepResponse,
)
from rpg_backend.domain.opening_guidance import build_opening_guidance_for_pack
from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.llm.base import LLMProviderConfigError
from rpg_backend.llm.factory import get_llm_provider
from rpg_backend.observability.context import get_request_id
from rpg_backend.security.deps import require_current_user
from rpg_backend.infrastructure.db.async_session import get_async_session
from rpg_backend.infrastructure.repositories.sessions_async import (
    create_session,
    get_session as get_session_record,
    list_session_actions,
)
from rpg_backend.infrastructure.repositories.stories_async import get_story, get_story_version
from rpg_backend.runtime.service import RuntimeService
from rpg_backend.application.session_step.use_case import process_step_request

router = APIRouter(
    prefix=API_SESSIONS_PREFIX,
    tags=["sessions"],
    dependencies=[Depends(require_current_user)],
)


def _state_summary(state: dict) -> dict[str, int]:
    values = state.get("values", {})
    return {
        "events": len(state.get("events", [])),
        "inventory": len(state.get("inventory", [])),
        "cost_total": int(values.get("cost_total", 0)),
    }


def _resolved_opening_guidance(pack: StoryPack) -> dict[str, Any]:
    guidance = pack.opening_guidance or build_opening_guidance_for_pack(pack)
    return guidance.model_dump(mode="json")


def _build_runtime_or_503() -> RuntimeService:
    try:
        provider = get_llm_provider()
    except LLMProviderConfigError as exc:
        raise ApiError(
            status_code=503,
            code="service_unavailable",
            message=f"llm provider misconfigured: {exc}",
            retryable=False,
        ) from exc
    return RuntimeService(provider)


def _normalize_history_item(index: int, payload: dict[str, Any], *, ended: bool) -> SessionHistoryTurn:
    step = SessionStepResponse.model_validate(payload)
    return SessionHistoryTurn(
        turn_index=index,
        scene_id=step.scene_id,
        narration_text=step.narration_text,
        recognized=step.recognized,
        resolution=step.resolution,
        ui=step.ui,
        ended=ended,
    )


@router.post("", response_model=SessionCreateResponse)
async def create_session_endpoint(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionCreateResponse:
    story = await get_story(db, payload.story_id)
    if story is None:
        raise ApiError(status_code=404, code="not_found", message="story not found", retryable=False)

    story_version = await get_story_version(db, payload.story_id, payload.version)
    if story_version is None:
        raise ApiError(status_code=404, code="not_found", message="story version not found", retryable=False)

    pack = StoryPack.model_validate(story_version.pack_json)
    runtime = _build_runtime_or_503()
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)

    session = await create_session(
        db,
        story_id=payload.story_id,
        version=payload.version,
        current_scene_id=scene_id,
        beat_index=beat_index,
        state_json=state,
        beat_progress_json=beat_progress,
    )

    return SessionCreateResponse(
        session_id=session.id,
        story_id=payload.story_id,
        version=payload.version,
        scene_id=scene_id,
        state_summary=_state_summary(state),
        opening_guidance=_resolved_opening_guidance(pack),
    )


@router.get("/{session_id}", response_model=SessionGetResponse)
async def get_session_endpoint(
    session_id: str,
    dev_mode: bool = Query(default=False),
    db: AsyncSession = Depends(get_async_session),
) -> SessionGetResponse:
    session = await get_session_record(db, session_id)
    if session is None:
        raise ApiError(status_code=404, code="not_found", message="session not found", retryable=False)

    story_version = await get_story_version(db, session.story_id, session.version)
    if story_version is None:
        raise ApiError(status_code=404, code="not_found", message="story version not found", retryable=False)
    pack = StoryPack.model_validate(story_version.pack_json)

    return SessionGetResponse(
        session_id=session.id,
        scene_id=session.current_scene_id,
        beat_progress=session.beat_progress_json,
        ended=session.ended,
        state_summary=_state_summary(session.state_json),
        opening_guidance=_resolved_opening_guidance(pack),
        state=session.state_json if dev_mode else None,
    )


@router.get("/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history_endpoint(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> SessionHistoryResponse:
    session = await get_session_record(db, session_id)
    if session is None:
        raise ApiError(status_code=404, code="not_found", message="session not found", retryable=False)

    actions = await list_session_actions(db, session_id)
    history = [
        _normalize_history_item(index + 1, action.response_json, ended=bool(session.ended and index == len(actions) - 1))
        for index, action in enumerate(actions)
    ]
    return SessionHistoryResponse(session_id=session.id, history=history)


@router.post("/{session_id}/step", response_model=SessionStepResponse, response_model_exclude_none=True)
async def step_session_endpoint(
    session_id: str,
    payload: SessionStepRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
) -> SessionStepResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    return await process_step_request(
        db=db,
        session_id=session_id,
        payload=payload,
        request_id=request_id,
        provider_factory=get_llm_provider,
    )

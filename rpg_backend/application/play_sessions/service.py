from __future__ import annotations

from typing import Any, Callable

from rpg_backend.application.play_sessions.errors import (
    LLMBackendMisconfiguredError,
    SessionNotFoundError,
    StoryNotFoundError,
    StoryVersionNotFoundError,
)
from rpg_backend.application.play_sessions.models import (
    SessionCreateView,
    SessionHistoryTurnView,
    SessionHistoryView,
    SessionStepResult,
    SessionView,
)
from rpg_backend.application.story_draft import resolve_opening_guidance
from rpg_backend.infrastructure.db.transaction import transactional
from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.infrastructure.repositories.sessions_async import (
    create_session,
    get_session as get_session_record,
    list_session_actions,
)
from rpg_backend.infrastructure.repositories.stories_async import get_story, get_story_version
from rpg_backend.llm.base import LLMBackendConfigError
from rpg_backend.runtime.service import RuntimeService
from rpg_backend.runtime.stance import classify_stance


def _trust_label(value: int) -> str:
    if value <= -3:
        return "broken"
    if value <= -1:
        return "shaken"
    if value <= 1:
        return "steady"
    if value <= 3:
        return "strong"
    return "surging"


def _pressure_label(value: int) -> str:
    if value <= 0:
        return "calm"
    if value <= 2:
        return "rising"
    if value <= 4:
        return "high"
    return "critical"


def build_state_summary(state: dict[str, Any], *, npc_names: list[str]) -> dict[str, Any]:
    values = state.get("values", {})
    crew_signals = []
    for name in npc_names:
        trust_value = int(values.get(f"npc_trust::{name}", 0))
        crew_signals.append(
            {
                "name": name,
                "stance": classify_stance(trust_value),
                "label": "pressured" if trust_value < 0 else "supportive" if trust_value > 1 else "watching",
            }
        )
    return {
        "events": len(state.get("events", [])),
        "inventory": len(state.get("inventory", [])),
        "cost_total": int(values.get("cost_total", 0)),
        "pressure": {
            "public_trust": {
                "value": int(values.get("public_trust", 0)),
                "label": _trust_label(int(values.get("public_trust", 0))),
            },
            "resource_stress": {
                "value": int(values.get("resource_stress", 0)),
                "label": _pressure_label(int(values.get("resource_stress", 0))),
            },
            "coordination_noise": {
                "value": int(values.get("coordination_noise", 0)),
                "label": _pressure_label(int(values.get("coordination_noise", 0))),
            },
        },
        "crew_signals": crew_signals,
    }


def build_runtime(bundle_factory: Callable[[], Any]) -> RuntimeService:
    try:
        bundle = bundle_factory()
    except LLMBackendConfigError as exc:
        raise LLMBackendMisconfiguredError(message=f"llm backend misconfigured: {exc}") from exc
    return RuntimeService(
        play_agent=bundle.play_agent,
        agent_model=bundle.model,
        agent_mode=bundle.mode,
    )


async def create_play_session(
    *,
    db,
    story_id: str,
    version: int,
    bundle_factory: Callable[[], Any],
) -> SessionCreateView:
    story = await get_story(db, story_id)
    if story is None:
        raise StoryNotFoundError(story_id=story_id)

    story_version = await get_story_version(db, story_id, version)
    if story_version is None:
        raise StoryVersionNotFoundError(story_id=story_id, version=version)

    pack = StoryPack.model_validate(story_version.pack_json)
    runtime = build_runtime(bundle_factory)
    scene_id, beat_index, state, beat_progress = runtime.initialize_session_state(pack)
    async with transactional(db):
        session = await create_session(
            db,
            story_id=story_id,
            version=version,
            current_scene_id=scene_id,
            beat_index=beat_index,
            state_json=state,
            beat_progress_json=beat_progress,
        )
    return SessionCreateView(
        session_id=session.id,
        story_id=story_id,
        version=version,
        scene_id=scene_id,
        state_summary=build_state_summary(state, npc_names=list(pack.npcs)),
        opening_guidance=resolve_opening_guidance(pack),
    )


async def get_play_session(*, db, session_id: str, dev_mode: bool) -> SessionView:
    session = await get_session_record(db, session_id)
    if session is None:
        raise SessionNotFoundError(session_id=session_id)

    story_version = await get_story_version(db, session.story_id, session.version)
    if story_version is None:
        raise StoryVersionNotFoundError(story_id=session.story_id, version=session.version)
    pack = StoryPack.model_validate(story_version.pack_json)

    return SessionView(
        session_id=session.id,
        scene_id=session.current_scene_id,
        beat_progress=session.beat_progress_json,
        ended=bool(session.ended),
        state_summary=build_state_summary(session.state_json, npc_names=list(pack.npcs)),
        opening_guidance=resolve_opening_guidance(pack),
        state=session.state_json if dev_mode else None,
    )


async def get_play_session_history(*, db, session_id: str) -> SessionHistoryView:
    session = await get_session_record(db, session_id)
    if session is None:
        raise SessionNotFoundError(session_id=session_id)

    actions = await list_session_actions(db, session_id)
    history = []
    for index, action in enumerate(actions, start=1):
        step_result = SessionStepResult.from_payload(action.response_json)
        history.append(
            SessionHistoryTurnView.from_step_result(
                index,
                step_result,
                ended=bool(session.ended and index == len(actions)),
            )
        )
    return SessionHistoryView(session_id=session.id, history=tuple(history))

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.storage.models import Session, SessionAction


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def create_session(
    db: AsyncSession,
    *,
    story_id: str,
    version: int,
    current_scene_id: str,
    beat_index: int,
    state_json: dict,
    beat_progress_json: dict,
) -> Session:
    session = Session(
        story_id=story_id,
        version=version,
        current_scene_id=current_scene_id,
        beat_index=beat_index,
        state_json=state_json,
        beat_progress_json=beat_progress_json,
        ended=False,
        turn_count=0,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    return await db.get(Session, session_id)


async def get_session_action(db: AsyncSession, session_id: str, client_action_id: str) -> SessionAction | None:
    stmt = select(SessionAction).where(
        SessionAction.session_id == session_id,
        SessionAction.client_action_id == client_action_id,
    )
    return (await db.exec(stmt)).first()


@dataclass(frozen=True)
class StepCommitResult:
    applied: bool
    actual_turn_count: int
    reason: str


async def commit_step_transition_if_turn_matches(
    db: AsyncSession,
    *,
    session_id: str,
    expected_turn_count: int,
    new_scene_id: str,
    new_beat_index: int,
    new_state_json: dict,
    new_beat_progress_json: dict,
    new_ended: bool,
    client_action_id: str,
    request_json: dict,
    response_json: dict,
) -> StepCommitResult:
    next_turn_count = expected_turn_count + 1
    now = utc_now()
    update_stmt = (
        update(Session)
        .where(
            Session.id == session_id,
            Session.turn_count == expected_turn_count,
            Session.ended.is_(False),
        )
        .values(
            current_scene_id=new_scene_id,
            beat_index=new_beat_index,
            state_json=new_state_json,
            beat_progress_json=new_beat_progress_json,
            ended=new_ended,
            turn_count=next_turn_count,
            updated_at=now,
        )
    )

    try:
        update_result = await db.exec(update_stmt)
        if update_result.rowcount != 1:
            await db.rollback()
            return StepCommitResult(
                applied=False,
                actual_turn_count=await _read_turn_count(db, session_id, fallback=expected_turn_count),
                reason="turn_conflict",
            )

        db.add(
            SessionAction(
                session_id=session_id,
                client_action_id=client_action_id,
                request_json=request_json,
                response_json=response_json,
            )
        )
        await db.commit()
        return StepCommitResult(applied=True, actual_turn_count=next_turn_count, reason="applied")
    except IntegrityError:
        await db.rollback()
        return StepCommitResult(
            applied=False,
            actual_turn_count=await _read_turn_count(db, session_id, fallback=expected_turn_count),
            reason="idempotency_conflict",
        )


async def _read_turn_count(db: AsyncSession, session_id: str, *, fallback: int) -> int:
    session = await db.get(Session, session_id)
    if session is None:
        return fallback
    return int(session.turn_count)


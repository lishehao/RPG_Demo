from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session as DBSession
from sqlmodel import select

from app.storage.models import Session, SessionAction


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_session(
    db: DBSession,
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
    db.commit()
    db.refresh(session)
    return session


def get_session(db: DBSession, session_id: str) -> Session | None:
    return db.get(Session, session_id)


def save_session(db: DBSession, session: Session) -> Session:
    session.updated_at = utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_action(db: DBSession, session_id: str, client_action_id: str) -> SessionAction | None:
    stmt = select(SessionAction).where(
        SessionAction.session_id == session_id,
        SessionAction.client_action_id == client_action_id,
    )
    return db.exec(stmt).first()


def save_session_action(
    db: DBSession,
    *,
    session_id: str,
    client_action_id: str,
    request_json: dict,
    response_json: dict,
) -> SessionAction:
    action = SessionAction(
        session_id=session_id,
        client_action_id=client_action_id,
        request_json=request_json,
        response_json=response_json,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action

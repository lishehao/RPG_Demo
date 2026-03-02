from __future__ import annotations

from sqlmodel import Session as DBSession
from sqlmodel import desc, select

from app.storage.models import SessionFeedback


def create_session_feedback(
    db: DBSession,
    *,
    session_id: str,
    story_id: str,
    version: int,
    verdict: str,
    reason_tags: list[str],
    note: str | None,
    turn_index: int | None,
) -> SessionFeedback:
    feedback = SessionFeedback(
        session_id=session_id,
        story_id=story_id,
        version=version,
        verdict=verdict,
        reason_tags_json=reason_tags,
        note=note,
        turn_index=turn_index,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_session_feedback(
    db: DBSession,
    *,
    session_id: str,
    limit: int,
) -> list[SessionFeedback]:
    stmt = (
        select(SessionFeedback)
        .where(SessionFeedback.session_id == session_id)
        .order_by(desc(SessionFeedback.created_at))
        .limit(limit)
    )
    return list(db.exec(stmt).all())

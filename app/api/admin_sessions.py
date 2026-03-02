from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.api.schemas import (
    AdminSessionTimelineEvent,
    AdminSessionTimelineResponse,
    SessionFeedbackCreateRequest,
    SessionFeedbackItem,
    SessionFeedbackListResponse,
)
from app.storage.engine import get_session
from app.storage.repositories.runtime_events import list_runtime_events
from app.storage.repositories.session_feedback import create_session_feedback, list_session_feedback
from app.storage.repositories.sessions import get_session as get_session_record

router = APIRouter(prefix="/admin/sessions", tags=["admin"])


def _require_session(db: Session, session_id: str):
    session = get_session_record(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.get("/{session_id}/timeline", response_model=AdminSessionTimelineResponse)
def get_session_timeline_endpoint(
    session_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    order: Literal["asc", "desc"] = Query(default="asc"),
    event_type: str | None = Query(default=None),
    db: Session = Depends(get_session),
) -> AdminSessionTimelineResponse:
    _require_session(db, session_id)
    events = list_runtime_events(
        db,
        session_id=session_id,
        limit=limit,
        order=order,
        event_type=event_type,
    )
    return AdminSessionTimelineResponse(
        session_id=session_id,
        events=[
            AdminSessionTimelineEvent(
                event_id=event.id,
                turn_index=event.turn_index,
                event_type=event.event_type,
                payload=event.payload_json,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


@router.post("/{session_id}/feedback", response_model=SessionFeedbackItem)
def create_session_feedback_endpoint(
    session_id: str,
    payload: SessionFeedbackCreateRequest,
    db: Session = Depends(get_session),
) -> SessionFeedbackItem:
    session = _require_session(db, session_id)
    feedback = create_session_feedback(
        db,
        session_id=session.id,
        story_id=session.story_id,
        version=session.version,
        verdict=payload.verdict,
        reason_tags=list(payload.reason_tags),
        note=payload.note,
        turn_index=payload.turn_index,
    )
    return SessionFeedbackItem(
        feedback_id=feedback.id,
        session_id=feedback.session_id,
        story_id=feedback.story_id,
        version=feedback.version,
        verdict=feedback.verdict,
        reason_tags=list(feedback.reason_tags_json),
        note=feedback.note,
        turn_index=feedback.turn_index,
        created_at=feedback.created_at,
    )


@router.get("/{session_id}/feedback", response_model=SessionFeedbackListResponse)
def list_session_feedback_endpoint(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> SessionFeedbackListResponse:
    _require_session(db, session_id)
    items = list_session_feedback(db, session_id=session_id, limit=limit)
    return SessionFeedbackListResponse(
        session_id=session_id,
        items=[
            SessionFeedbackItem(
                feedback_id=item.id,
                session_id=item.session_id,
                story_id=item.story_id,
                version=item.version,
                verdict=item.verdict,
                reason_tags=list(item.reason_tags_json),
                note=item.note,
                turn_index=item.turn_index,
                created_at=item.created_at,
            )
            for item in items
        ],
    )

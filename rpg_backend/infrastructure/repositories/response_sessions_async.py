from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.storage.models import ResponseSessionCursor


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def get_response_session_cursor(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: str,
    channel: str,
) -> ResponseSessionCursor | None:
    stmt = select(ResponseSessionCursor).where(
        ResponseSessionCursor.scope_type == str(scope_type),
        ResponseSessionCursor.scope_id == str(scope_id),
        ResponseSessionCursor.channel == str(channel),
    )
    return (await db.exec(stmt)).first()


async def upsert_response_session_cursor(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: str,
    channel: str,
    model: str,
    previous_response_id: str,
) -> ResponseSessionCursor:
    existing = await get_response_session_cursor(
        db,
        scope_type=scope_type,
        scope_id=scope_id,
        channel=channel,
    )
    if existing is None:
        existing = ResponseSessionCursor(
            scope_type=str(scope_type),
            scope_id=str(scope_id),
            channel=str(channel),
            model=str(model),
            previous_response_id=str(previous_response_id),
            updated_at=utc_now(),
        )
        db.add(existing)
        await db.flush()
        return existing

    existing.model = str(model)
    existing.previous_response_id = str(previous_response_id)
    existing.updated_at = utc_now()
    db.add(existing)
    await db.flush()
    return existing


async def delete_response_session_cursor(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: str,
    channel: str,
) -> int:
    stmt = delete(ResponseSessionCursor).where(
        ResponseSessionCursor.scope_type == str(scope_type),
        ResponseSessionCursor.scope_id == str(scope_id),
        ResponseSessionCursor.channel == str(channel),
    )
    result = await db.exec(stmt)
    return int(result.rowcount or 0)

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.storage.models import AdminUser


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def get_admin_user_by_email(db: AsyncSession, email: str) -> AdminUser | None:
    normalized = normalize_email(email)
    if not normalized:
        return None
    stmt = select(AdminUser).where(AdminUser.email == normalized)
    return (await db.exec(stmt)).first()


async def get_admin_user_by_id(db: AsyncSession, user_id: str) -> AdminUser | None:
    return await db.get(AdminUser, user_id)


async def list_admin_users(db: AsyncSession, *, limit: int = 100) -> list[AdminUser]:
    stmt = select(AdminUser).order_by(desc(AdminUser.created_at)).limit(limit)
    return list((await db.exec(stmt)).all())


async def update_admin_user_last_login(db: AsyncSession, user: AdminUser) -> AdminUser:
    user.last_login_at = utc_now()
    user.updated_at = utc_now()
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def upsert_bootstrap_admin(
    db: AsyncSession,
    *,
    email: str,
    password_hash: str,
) -> AdminUser:
    normalized = normalize_email(email)
    if not normalized:
        raise ValueError("bootstrap email is empty")

    existing = await get_admin_user_by_email(db, normalized)
    now = utc_now()
    if existing is not None:
        existing.email = normalized
        existing.password_hash = password_hash
        existing.role = "admin"
        existing.is_active = True
        existing.updated_at = now
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    created = AdminUser(
        email=normalized,
        password_hash=password_hash,
        role="admin",
        is_active=True,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(created)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing_after_conflict = await get_admin_user_by_email(db, normalized)
        if existing_after_conflict is None:
            raise
        existing_after_conflict.password_hash = password_hash
        existing_after_conflict.role = "admin"
        existing_after_conflict.is_active = True
        existing_after_conflict.updated_at = utc_now()
        db.add(existing_after_conflict)
        await db.commit()
        await db.refresh(existing_after_conflict)
        return existing_after_conflict

    await db.refresh(created)
    return created


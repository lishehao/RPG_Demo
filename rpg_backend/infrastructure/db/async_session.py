from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.infrastructure.db.async_engine import async_engine


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session


from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlmodel.ext.asyncio.session import AsyncSession


@asynccontextmanager
async def transactional(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    try:
        yield session
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        raise


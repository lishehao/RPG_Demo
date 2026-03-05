from __future__ import annotations

from typing import Any, Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.api.schemas import SessionStepRequest, SessionStepResponse
from rpg_backend.application.session_step.use_case import process_step_request as process_step_request_use_case
from rpg_backend.llm.factory import get_llm_provider


async def process_step_request(
    *,
    db: AsyncSession,
    session_id: str,
    payload: SessionStepRequest,
    request_id: str,
    provider_factory: Callable[[], Any] = get_llm_provider,
) -> SessionStepResponse:
    return await process_step_request_use_case(
        db=db,
        session_id=session_id,
        payload=payload,
        request_id=request_id,
        provider_factory=provider_factory,
    )

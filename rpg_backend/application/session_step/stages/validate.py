from __future__ import annotations

from rpg_backend.api.errors import ApiError
from rpg_backend.api.schemas import SessionStepRequest
from rpg_backend.application.session_step.contracts import StepRequestContext
from rpg_backend.config.settings import get_settings
from rpg_backend.domain.constants import GLOBAL_HELP_ME_PROGRESS_MOVE_ID
from rpg_backend.infrastructure.repositories.sessions_async import get_session as get_session_record
from rpg_backend.observability.logging import build_input_log_fields


def normalize_step_input(raw_input) -> dict[str, str]:
    if raw_input is None:
        return {"type": "text", "text": ""}

    raw_type = (raw_input.type or "").strip().lower()
    move_id = (raw_input.move_id or "").strip() if raw_input.move_id is not None else ""
    text = raw_input.text or ""

    if raw_type == "button":
        if move_id:
            return {"type": "button", "move_id": move_id}
        return {"type": "button", "move_id": GLOBAL_HELP_ME_PROGRESS_MOVE_ID}

    if raw_type == "text":
        return {"type": "text", "text": text}

    return {"type": "text", "text": text}


async def validate_request(
    *,
    db,
    session_id: str,
    payload: SessionStepRequest,
    request_id: str,
) -> StepRequestContext:
    settings = get_settings()
    session = await get_session_record(db, session_id)
    if session is None:
        raise ApiError(status_code=404, code="not_found", message="session not found", retryable=False)
    if session.ended:
        raise ApiError(status_code=409, code="session_inactive", message="inactive session", retryable=False)

    normalized_input = normalize_step_input(payload.input)
    turn_index_expected = session.turn_count + 1
    scene_id_before = session.current_scene_id
    beat_index_before = session.beat_index
    input_log_fields = build_input_log_fields(normalized_input, redact_text=settings.obs_redact_input_text)

    return StepRequestContext(
        db=db,
        request_id=request_id,
        session=session,
        payload=payload,
        normalized_input=normalized_input,
        turn_index_expected=turn_index_expected,
        scene_id_before=scene_id_before,
        beat_index_before=beat_index_before,
        input_log_fields=input_log_fields,
    )

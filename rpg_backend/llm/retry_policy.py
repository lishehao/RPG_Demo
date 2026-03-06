from __future__ import annotations

import json

import httpx
from pydantic import ValidationError

_RETRIABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_RETRY_SCHEDULE_SECONDS = (0.25, 0.8, 1.5)


def is_retriable_llm_error(exc: Exception) -> bool:
    if isinstance(exc, (json.JSONDecodeError, ValidationError, ValueError)):
        return True

    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.RemoteProtocolError,
        ),
    ):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRIABLE_STATUS_CODES

    return False


def retry_delay_seconds(attempt: int, exc: Exception) -> float:
    if isinstance(exc, (json.JSONDecodeError, ValidationError, ValueError)):
        return 0.0

    index = min(max(attempt - 1, 0), len(_RETRY_SCHEDULE_SECONDS) - 1)
    return _RETRY_SCHEDULE_SECONDS[index]

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from rpg_backend.schemas import ErrorEnvelope


class ApiError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def build_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = ErrorEnvelope(
        error={
            "code": code,
            "message": message,
            "retryable": retryable,
            "request_id": request_id,
        }
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


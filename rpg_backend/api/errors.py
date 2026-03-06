from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rpg_backend.api.schemas import ErrorEnvelope
from rpg_backend.observability.context import get_request_id


_STATUS_DEFAULT_CODES: dict[int, str] = {
    400: "request_invalid",
    401: "request_invalid",
    403: "request_invalid",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "service_unavailable",
    500: "service_unavailable",
    502: "service_unavailable",
    503: "service_unavailable",
    504: "service_unavailable",
}


class ApiError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None) or get_request_id()


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
    request_id: str | None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    safe_details = _json_safe(details or {})
    envelope = ErrorEnvelope(
        error={
            "code": code,
            "message": message,
            "retryable": bool(retryable),
            "request_id": request_id,
            "details": safe_details,
        }
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _normalize_http_exception(exc: HTTPException | StarletteHTTPException) -> tuple[str, str, bool, dict[str, Any]]:
    status = int(exc.status_code)
    detail = exc.detail
    default_code = _STATUS_DEFAULT_CODES.get(status, "service_unavailable")
    default_retryable = status >= 500

    if isinstance(detail, dict):
        if "error" in detail and isinstance(detail["error"], dict):
            err = detail["error"]
            code = str(err.get("code") or default_code)
            message = str(err.get("message") or "request failed")
            retryable = bool(err.get("retryable", default_retryable))
            nested_details = err.get("details")
            details_payload = nested_details if isinstance(nested_details, dict) else {}
            return code, message, retryable, details_payload

        code = str(detail.get("error_code") or detail.get("code") or default_code)
        message = str(detail.get("message") or detail.get("detail") or "request failed")
        retryable = bool(detail.get("retryable", default_retryable))
        details_payload: dict[str, Any] = {}
        nested_details = detail.get("details")
        if isinstance(nested_details, dict):
            details_payload.update(nested_details)
        details_payload.update(
            {
                key: value
                for key, value in detail.items()
                if key not in {"error_code", "code", "message", "detail", "details", "retryable"}
            }
        )
        return code, message, retryable, details_payload

    if isinstance(detail, str):
        return default_code, detail, default_retryable, {}

    return default_code, "request failed", default_retryable, {}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            request_id=_request_id(request),
            details=exc.details,
        )

    @app.exception_handler(HTTPException)
    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        request: Request,
        exc: HTTPException | StarletteHTTPException,
    ) -> JSONResponse:
        code, message, retryable, details = _normalize_http_exception(exc)
        return _error_response(
            status_code=int(exc.status_code),
            code=code,
            message=message,
            retryable=retryable,
            request_id=_request_id(request),
            details=details,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="validation_error",
            message="request validation failed",
            retryable=False,
            request_id=_request_id(request),
            details={"errors": exc.errors()},
        )

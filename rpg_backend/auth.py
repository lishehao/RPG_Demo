from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rpg_backend.errors import ApiError

_DEFAULT_ADMIN_EMAIL = "admin@test.com"
_DEFAULT_ADMIN_PASSWORD = "password"
_TOKEN_TTL_HOURS = 12


class TokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, datetime] = {}

    def issue(self) -> str:
        token = token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=_TOKEN_TTL_HOURS)
        self._tokens[token] = expires_at
        return token

    def is_valid(self, token: str) -> bool:
        expires_at = self._tokens.get(token)
        if expires_at is None:
            return False
        if expires_at <= datetime.now(timezone.utc):
            self._tokens.pop(token, None)
            return False
        return True


token_store = TokenStore()
bearer_scheme = HTTPBearer(auto_error=False)


def _admin_email() -> str:
    return (os.getenv("MOCK_ADMIN_EMAIL") or _DEFAULT_ADMIN_EMAIL).strip().lower()


def _admin_password() -> str:
    return os.getenv("MOCK_ADMIN_PASSWORD") or _DEFAULT_ADMIN_PASSWORD


def login_and_issue_token(email: str, password: str) -> str | None:
    normalized_email = (email or "").strip().lower()
    if normalized_email != _admin_email():
        return None
    if password != _admin_password():
        return None
    return token_store.issue()


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if credentials is None:
        raise ApiError(status_code=401, code="unauthorized", message="missing bearer token", retryable=False)

    if (credentials.scheme or "").lower() != "bearer":
        raise ApiError(status_code=401, code="unauthorized", message="invalid authorization scheme", retryable=False)

    token = (credentials.credentials or "").strip()
    if not token:
        raise ApiError(status_code=401, code="unauthorized", message="missing bearer token", retryable=False)

    if not token_store.is_valid(token):
        raise ApiError(status_code=401, code="unauthorized", message="invalid or expired token", retryable=False)

    return token


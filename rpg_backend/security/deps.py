from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.api.errors import ApiError
from rpg_backend.config.settings import get_settings
from rpg_backend.infrastructure.db.async_session import get_async_session
from rpg_backend.infrastructure.repositories.admin_users_async import get_admin_user_by_id
from rpg_backend.security.tokens import TokenValidationError, decode_access_token
from rpg_backend.storage.models import AdminUser

_bearer_scheme = HTTPBearer(auto_error=False)


def _extract_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise ApiError(status_code=401, code="unauthorized", message="missing bearer token", retryable=False)
    if (credentials.scheme or "").lower() != "bearer":
        raise ApiError(status_code=401, code="unauthorized", message="invalid authorization scheme", retryable=False)
    token = (credentials.credentials or "").strip()
    if not token:
        raise ApiError(status_code=401, code="unauthorized", message="missing bearer token", retryable=False)
    return token


async def require_current_user(
    token: str = Depends(_extract_bearer_token),
    db: AsyncSession = Depends(get_async_session),
) -> AdminUser:
    settings = get_settings()
    try:
        claims = decode_access_token(
            token=token,
            secret=settings.auth_jwt_secret,
            issuer=settings.auth_jwt_issuer,
        )
    except TokenValidationError as exc:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="invalid or expired token",
            retryable=False,
            details={"reason": exc.message},
        ) from exc

    user = await get_admin_user_by_id(db, claims.sub)
    if user is None:
        raise ApiError(status_code=401, code="unauthorized", message="user not found", retryable=False)
    if not bool(user.is_active):
        raise ApiError(status_code=403, code="account_inactive", message="account is inactive", retryable=False)
    return user


def require_admin(user: AdminUser = Depends(require_current_user)) -> AdminUser:
    if str(user.role) != "admin":
        raise ApiError(status_code=403, code="forbidden", message="admin role required", retryable=False)
    return user

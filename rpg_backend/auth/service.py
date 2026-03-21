from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
import sqlite3
from uuid import uuid4

from fastapi import Request

from rpg_backend.auth.contracts import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
    AuthUserResponse,
    CurrentActorResponse,
)
from rpg_backend.auth.storage import SQLiteAuthStorage
from rpg_backend.config import Settings, get_settings

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64


class AuthServiceError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RequestUser:
    user_id: str
    display_name: str
    email: str


@dataclass(frozen=True)
class AuthenticatedSession:
    user: RequestUser
    session_id: str
    session_token: str
    expires_at: datetime


def _normalize_email(value: str) -> str:
    normalized = " ".join(value.split()).strip().casefold()
    if not normalized or len(normalized) > 320 or not _EMAIL_PATTERN.match(normalized):
        raise AuthServiceError(
            code="auth_email_invalid",
            message="Enter a valid email address.",
            status_code=400,
        )
    return normalized


def _normalize_display_name(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized or len(normalized) > 120:
        raise AuthServiceError(
            code="auth_display_name_invalid",
            message="Enter a display name between 1 and 120 characters.",
            status_code=400,
        )
    return normalized


def _validate_password(value: str) -> str:
    if len(value) < 8 or len(value) > 200:
        raise AuthServiceError(
            code="auth_password_invalid",
            message="Password must be between 8 and 200 characters.",
            status_code=400,
        )
    return value


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return "$".join(
        [
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n_value, r_value, p_value, salt_encoded, digest_encoded = stored_hash.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_encoded.encode("ascii"))
        expected_digest = base64.urlsafe_b64decode(digest_encoded.encode("ascii"))
        candidate_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=len(expected_digest),
        )
        return hmac.compare_digest(candidate_digest, expected_digest)
    except Exception:  # noqa: BLE001
        return False


def _hash_session_token(session_token: str) -> str:
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def _user_response(user: RequestUser) -> AuthUserResponse:
    return AuthUserResponse(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
    )


class AuthService:
    def __init__(
        self,
        *,
        storage: SQLiteAuthStorage | None = None,
        settings: Settings | None = None,
        now_provider=None,
    ) -> None:
        self._settings = settings or get_settings()
        self._storage = storage or SQLiteAuthStorage(self._settings.runtime_state_db_path)
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        return self._now_provider()

    def _session_expiry(self, now: datetime | None = None) -> datetime:
        started_at = now or self._now()
        return started_at + timedelta(seconds=self._settings.auth_session_ttl_seconds)

    def _build_request_user(self, user_payload: dict[str, str]) -> RequestUser:
        return RequestUser(
            user_id=str(user_payload["user_id"]),
            display_name=str(user_payload["display_name"]),
            email=str(user_payload["email"]),
        )

    def register(self, request: AuthRegisterRequest) -> AuthenticatedSession:
        normalized_email = _normalize_email(request.email)
        display_name = _normalize_display_name(request.display_name)
        password = _validate_password(request.password)
        if self._storage.get_user_by_normalized_email(normalized_email) is not None:
            raise AuthServiceError(
                code="auth_email_taken",
                message="An account with that email already exists.",
                status_code=409,
            )
        user_id = f"usr_{uuid4().hex[:12]}"
        created_at = self._now()
        try:
            self._storage.create_user(
                user_id=user_id,
                email=normalized_email,
                normalized_email=normalized_email,
                display_name=display_name,
                password_hash=_hash_password(password),
                created_at=created_at,
            )
        except sqlite3.IntegrityError as exc:
            raise AuthServiceError(
                code="auth_email_taken",
                message="An account with that email already exists.",
                status_code=409,
            ) from exc
        user = RequestUser(user_id=user_id, display_name=display_name, email=normalized_email)
        return self._create_authenticated_session(user=user, created_at=created_at)

    def login(self, request: AuthLoginRequest) -> AuthenticatedSession:
        normalized_email = _normalize_email(request.email)
        user_payload = self._storage.get_user_by_normalized_email(normalized_email)
        if user_payload is None or not _verify_password(request.password, str(user_payload["password_hash"])):
            raise AuthServiceError(
                code="auth_invalid_credentials",
                message="Invalid email or password.",
                status_code=401,
            )
        user = self._build_request_user(user_payload)
        return self._create_authenticated_session(user=user, created_at=self._now())

    def _create_authenticated_session(self, *, user: RequestUser, created_at: datetime) -> AuthenticatedSession:
        session_token = secrets.token_urlsafe(32)
        session_id = f"ses_{uuid4().hex[:16]}"
        expires_at = self._session_expiry(created_at)
        self._storage.create_session(
            session_id=session_id,
            user_id=user.user_id,
            token_hash=_hash_session_token(session_token),
            created_at=created_at,
            expires_at=expires_at,
            last_seen_at=created_at,
        )
        return AuthenticatedSession(
            user=user,
            session_id=session_id,
            session_token=session_token,
            expires_at=expires_at,
        )

    def resolve_session(self, request: Request) -> AuthenticatedSession | None:
        session_token = request.cookies.get(self._settings.auth_session_cookie_name)
        if not session_token:
            return None
        payload = self._storage.get_session_with_user(_hash_session_token(session_token))
        if payload is None:
            return None
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
        now = self._now()
        if expires_at <= now:
            self._storage.delete_session_by_token_hash(str(payload["token_hash"]))
            return None
        refreshed_expiry = self._session_expiry(now)
        self._storage.touch_session(
            session_id=str(payload["session_id"]),
            expires_at=refreshed_expiry,
            last_seen_at=now,
        )
        return AuthenticatedSession(
            user=self._build_request_user(payload),
            session_id=str(payload["session_id"]),
            session_token=session_token,
            expires_at=refreshed_expiry,
        )

    def logout(self, request: Request) -> None:
        session_token = request.cookies.get(self._settings.auth_session_cookie_name)
        if not session_token:
            return
        self._storage.delete_session_by_token_hash(_hash_session_token(session_token))

    def build_session_response(self, session: AuthenticatedSession | None) -> AuthSessionResponse:
        if session is None:
            return AuthSessionResponse(authenticated=False, user=None)
        return AuthSessionResponse(authenticated=True, user=_user_response(session.user))

    def build_current_actor_response(self, session: AuthenticatedSession) -> CurrentActorResponse:
        return CurrentActorResponse(
            user_id=session.user.user_id,
            display_name=session.user.display_name,
            email=session.user.email,
            is_default=False,
        )

    def require_session(self, request: Request) -> AuthenticatedSession:
        session = self.resolve_session(request)
        if session is None:
            raise AuthServiceError(
                code="auth_session_required",
                message="Sign in required.",
                status_code=401,
            )
        return session

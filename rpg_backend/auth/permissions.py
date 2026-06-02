from __future__ import annotations

from rpg_backend.auth.service import RequestUser
from rpg_backend.config import Settings, get_settings


def _csv_set(raw: str | None) -> set[str]:
    return {item.strip().lower() for item in (raw or "").split(",") if item.strip()}


def can_view_agent_trace(
    user: RequestUser,
    *,
    settings: Settings | None = None,
) -> bool:
    """Return whether this authenticated context may inspect agent trace payloads.

    The current auth layer is username-only and has no role table. Keep the
    gate explicit and centralized so it can later move to a real reviewer/admin
    role without touching narrative endpoints.
    """
    active_settings = settings or get_settings()
    if user.user_id == (active_settings.default_actor_id or "anonymous"):
        return False

    allowed_user_ids = _csv_set(active_settings.agent_trace_reviewer_user_ids)
    if user.user_id.lower() in allowed_user_ids:
        return True

    allowed_usernames = _csv_set(active_settings.agent_trace_reviewer_usernames)
    return user.display_name.strip().lower() in allowed_usernames

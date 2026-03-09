from __future__ import annotations

HEALTH_PATH = "/health"
READY_PATH = "/ready"

API_STORIES_PREFIX = "/stories"
API_SESSIONS_PREFIX = "/sessions"
API_ADMIN_PREFIX = "/admin"
API_AUTHOR_PREFIX = "/author"
API_AUTHOR_RUNS_PREFIX = "/author/runs"
API_AUTHOR_STORIES_PREFIX = "/author/stories"
API_ADMIN_AUTH_PREFIX = "/admin/auth"
API_ADMIN_SESSIONS_PREFIX = "/admin/sessions"
API_ADMIN_USERS_PREFIX = "/admin/users"
API_ADMIN_OBSERVABILITY_PREFIX = "/admin/observability"


def stories_path() -> str:
    return API_STORIES_PREFIX


def story_path(story_id: str) -> str:
    return f"{API_STORIES_PREFIX}/{story_id}"


def story_draft_path(story_id: str) -> str:
    return f"{API_STORIES_PREFIX}/{story_id}/draft"


def story_publish_path(story_id: str) -> str:
    return f"{API_STORIES_PREFIX}/{story_id}/publish"


def story_draft_patch_path(story_id: str) -> str:
    return f"{API_STORIES_PREFIX}/{story_id}/draft"



def author_runs_path() -> str:
    return API_AUTHOR_RUNS_PREFIX


def author_run_path(run_id: str) -> str:
    return f"{API_AUTHOR_RUNS_PREFIX}/{run_id}"


def author_run_events_path(run_id: str) -> str:
    return f"{API_AUTHOR_RUNS_PREFIX}/{run_id}/events"


def author_stories_path() -> str:
    return API_AUTHOR_STORIES_PREFIX


def author_story_path(story_id: str) -> str:
    return f"{API_AUTHOR_STORIES_PREFIX}/{story_id}"


def author_story_runs_path(story_id: str) -> str:
    return f"{API_AUTHOR_STORIES_PREFIX}/{story_id}/runs"


def sessions_path() -> str:
    return API_SESSIONS_PREFIX


def session_path(session_id: str) -> str:
    return f"{API_SESSIONS_PREFIX}/{session_id}"


def session_history_path(session_id: str) -> str:
    return f"{API_SESSIONS_PREFIX}/{session_id}/history"


def session_step_path(session_id: str) -> str:
    return f"{API_SESSIONS_PREFIX}/{session_id}/step"


def admin_session_timeline_path(session_id: str) -> str:
    return f"{API_ADMIN_SESSIONS_PREFIX}/{session_id}/timeline"


def admin_session_feedback_path(session_id: str) -> str:
    return f"{API_ADMIN_SESSIONS_PREFIX}/{session_id}/feedback"


def admin_runtime_errors_path() -> str:
    return f"{API_ADMIN_OBSERVABILITY_PREFIX}/runtime-errors"


def admin_http_health_path() -> str:
    return f"{API_ADMIN_OBSERVABILITY_PREFIX}/http-health"


def admin_llm_call_health_path() -> str:
    return f"{API_ADMIN_OBSERVABILITY_PREFIX}/llm-call-health"


def admin_readiness_health_path() -> str:
    return f"{API_ADMIN_OBSERVABILITY_PREFIX}/readiness-health"


def admin_auth_login_path() -> str:
    return f"{API_ADMIN_AUTH_PREFIX}/login"


def admin_users_path() -> str:
    return API_ADMIN_USERS_PREFIX


def admin_user_path(user_id: str) -> str:
    return f"{API_ADMIN_USERS_PREFIX}/{user_id}"

from __future__ import annotations

from rpg_backend.application.errors import ApplicationError


class AuthorRunNotFoundError(ApplicationError):
    def __init__(self, *, run_id: str) -> None:
        super().__init__(
            status_code=404,
            error_code="author_run_not_found",
            message="author run not found",
            retryable=False,
            details={"run_id": run_id},
        )


class AuthorStoryNotReadyForPublishError(ApplicationError):
    def __init__(self, *, story_id: str, latest_run_status: str | None) -> None:
        super().__init__(
            status_code=409,
            error_code="author_run_not_review_ready",
            message="story is not review_ready for publish",
            retryable=False,
            details={"story_id": story_id, "latest_run_status": latest_run_status},
        )

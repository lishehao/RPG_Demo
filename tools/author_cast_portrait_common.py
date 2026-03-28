from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.author.contracts import AuthorCastPortraitPlanResponse
from rpg_backend.config import get_settings


def default_author_portrait_job_dir(job_id: str) -> Path:
    settings = get_settings()
    return Path(settings.local_author_portrait_dir).expanduser().resolve() / job_id


def default_author_portrait_plan_path(job_id: str) -> Path:
    return default_author_portrait_job_dir(job_id) / "portrait_plan.json"


def default_author_portrait_validation_path(job_id: str) -> Path:
    return default_author_portrait_job_dir(job_id) / "validation.json"


def write_author_portrait_plan(path: str | Path, plan: AuthorCastPortraitPlanResponse) -> Path:
    resolved_path = Path(path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return resolved_path


def load_author_portrait_plan(path: str | Path) -> AuthorCastPortraitPlanResponse:
    resolved_path = Path(path).expanduser().resolve()
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return AuthorCastPortraitPlanResponse.model_validate(payload)

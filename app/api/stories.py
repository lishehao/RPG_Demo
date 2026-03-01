from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.api.schemas import (
    StoryCreateRequest,
    StoryCreateResponse,
    StoryGenerateRequest,
    StoryGenerateResponse,
    StoryGetResponse,
    StoryPublishResponse,
)
from app.domain.linter import lint_story_pack
from app.domain.repair import repair_story_pack
from app.storage.engine import get_session
from app.storage.repositories.stories import (
    create_story,
    get_latest_story_version,
    get_story,
    get_story_version,
    publish_story_version,
)

router = APIRouter(prefix="/stories", tags=["stories"])


@router.post("", response_model=StoryCreateResponse)
def create_story_endpoint(payload: StoryCreateRequest, db: Session = Depends(get_session)) -> StoryCreateResponse:
    story = create_story(db, title=payload.title, pack_json=payload.pack_json)
    return StoryCreateResponse(story_id=story.id, status="draft", created_at=story.created_at)


@router.post("/{story_id}/publish", response_model=StoryPublishResponse)
def publish_story_endpoint(story_id: str, db: Session = Depends(get_session)) -> StoryPublishResponse:
    story = get_story(db, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")

    report = lint_story_pack(story.draft_pack_json)
    if not report.ok:
        raise HTTPException(status_code=422, detail={"errors": report.errors, "warnings": report.warnings})

    version = publish_story_version(db, story)
    return StoryPublishResponse(story_id=story_id, version=version.version, published_at=version.created_at)


@router.post("/generate", response_model=StoryGenerateResponse, status_code=501)
def generate_story_endpoint(payload: StoryGenerateRequest) -> StoryGenerateResponse:
    repair_result = repair_story_pack(pack_json={}, max_attempts=2)
    lint_report = {"errors": ["generator placeholder: not implemented"], "warnings": []}
    return StoryGenerateResponse(
        status="placeholder",
        story_id=None,
        version=None,
        pack=repair_result.pack_json,
        lint_report=lint_report,
        attempts=repair_result.attempts,
        notes=repair_result.notes,
    )


@router.get("/{story_id}", response_model=StoryGetResponse)
def get_story_endpoint(
    story_id: str,
    version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_session),
) -> StoryGetResponse:
    story = get_story(db, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")

    resolved = get_story_version(db, story_id, version) if version else get_latest_story_version(db, story_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="published version not found")

    return StoryGetResponse(story_id=story_id, version=resolved.version, pack=resolved.pack_json)

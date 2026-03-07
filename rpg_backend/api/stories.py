from copy import deepcopy

from fastapi import APIRouter, Depends, Query, Request
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.api.errors import ApiError
from rpg_backend.api.route_paths import API_STORIES_PREFIX
from rpg_backend.api.schemas import (
    StoryCreateRequest,
    StoryCreateResponse,
    StoryDraftGetResponse,
    StoryDraftPatchChange,
    StoryDraftPatchRequest,
    StoryGenerateRequest,
    StoryGenerateResponse,
    StoryGetResponse,
    StoryListItem,
    StoryListResponse,
    StoryPublishResponse,
)
from rpg_backend.domain.opening_guidance import build_opening_guidance_for_pack
from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.observability.context import get_request_id
from rpg_backend.observability.logging import log_event
from rpg_backend.security.deps import require_current_user
from rpg_backend.domain.linter import lint_story_pack
from rpg_backend.generator.errors import GeneratorBuildError
from rpg_backend.generator.pipeline import GeneratorPipeline
from rpg_backend.infrastructure.db.async_session import get_async_session
from rpg_backend.infrastructure.repositories.stories_async import (
    create_story,
    get_latest_story_version,
    get_story,
    get_story_version,
    list_stories,
    publish_story_version,
    update_story_draft,
)

router = APIRouter(
    prefix=API_STORIES_PREFIX,
    tags=["stories"],
    dependencies=[Depends(require_current_user)],
)


def _normalized_draft_pack(pack_json: dict) -> dict:
    try:
        pack = StoryPack.model_validate(pack_json)
    except ValidationError:
        return deepcopy(pack_json)

    if pack.opening_guidance is not None:
        return deepcopy(pack_json)

    normalized = deepcopy(pack_json)
    normalized["opening_guidance"] = build_opening_guidance_for_pack(pack).model_dump(mode="json")
    return normalized


def _build_story_draft_response(*, story, latest_version) -> StoryDraftGetResponse:
    draft_pack = _normalized_draft_pack(story.draft_pack_json)
    return StoryDraftGetResponse(
        story_id=story.id,
        title=story.title,
        created_at=story.created_at,
        draft_pack=draft_pack,
        latest_published_version=latest_version.version if latest_version else None,
        latest_published_at=latest_version.created_at if latest_version else None,
    )


def _find_target_entry(*, entries: list[dict], target_id: str, label: str) -> dict:
    for entry in entries:
        if str(entry.get("id") or entry.get("name") or "") == target_id:
            return entry
    raise ApiError(
        status_code=404,
        code="draft_target_not_found",
        message=f"{label} not found",
        retryable=False,
        details={"target_id": target_id, "target_type": label},
    )


def _apply_story_draft_change(*, pack_json: dict, story_title: str, change: StoryDraftPatchChange) -> tuple[dict, str]:
    updated_pack = deepcopy(pack_json)
    updated_title = story_title

    if change.target_type == "story":
        updated_pack[change.field] = change.value
        if change.field == "title":
            updated_title = change.value
        return updated_pack, updated_title

    if change.target_type == "opening_guidance":
        updated_pack = _normalized_draft_pack(updated_pack)
        opening_guidance = updated_pack.setdefault("opening_guidance", {})
        if change.field.startswith("starter_prompt_"):
            prompts = list(opening_guidance.get("starter_prompts") or ["", "", ""])
            while len(prompts) < 3:
                prompts.append("")
            prompt_index = int(change.field.rsplit("_", 1)[1]) - 1
            prompts[prompt_index] = change.value
            opening_guidance["starter_prompts"] = prompts[:3]
        else:
            opening_guidance[change.field] = change.value
        return updated_pack, updated_title

    if change.target_type == "beat":
        beat = _find_target_entry(entries=updated_pack.get("beats") or [], target_id=change.target_id or "", label="beat")
        beat[change.field] = change.value
        return updated_pack, updated_title

    if change.target_type == "scene":
        scene = _find_target_entry(entries=updated_pack.get("scenes") or [], target_id=change.target_id or "", label="scene")
        scene[change.field] = change.value
        return updated_pack, updated_title

    if change.target_type == "npc":
        npc_profile = _find_target_entry(entries=updated_pack.get("npc_profiles") or [], target_id=change.target_id or "", label="npc")
        npc_profile[change.field] = change.value
        return updated_pack, updated_title

    raise ApiError(status_code=422, code="validation_error", message="unsupported draft patch", retryable=False)


@router.post("", response_model=StoryCreateResponse)
async def create_story_endpoint(
    payload: StoryCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> StoryCreateResponse:
    story = await create_story(db, title=payload.title, pack_json=payload.pack_json)
    return StoryCreateResponse(story_id=story.id, status="draft", created_at=story.created_at)


@router.get("", response_model=StoryListResponse)
async def list_stories_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
) -> StoryListResponse:
    stories = await list_stories(db, limit=limit)
    items: list[StoryListItem] = []
    for story in stories:
        latest_version = await get_latest_story_version(db, story.id)
        items.append(
            StoryListItem(
                story_id=story.id,
                title=story.title,
                created_at=story.created_at,
                has_draft=bool(story.draft_pack_json),
                latest_published_version=latest_version.version if latest_version else None,
                latest_published_at=latest_version.created_at if latest_version else None,
            )
        )
    return StoryListResponse(stories=items)


@router.get("/{story_id}/draft", response_model=StoryDraftGetResponse)
async def get_story_draft_endpoint(
    story_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> StoryDraftGetResponse:
    story = await get_story(db, story_id)
    if story is None:
        raise ApiError(status_code=404, code="not_found", message="story not found", retryable=False)

    latest_version = await get_latest_story_version(db, story_id)
    return _build_story_draft_response(story=story, latest_version=latest_version)


@router.patch("/{story_id}/draft", response_model=StoryDraftGetResponse)
async def patch_story_draft_endpoint(
    story_id: str,
    payload: StoryDraftPatchRequest,
    db: AsyncSession = Depends(get_async_session),
) -> StoryDraftGetResponse:
    story = await get_story(db, story_id)
    if story is None:
        raise ApiError(status_code=404, code="not_found", message="story not found", retryable=False)

    updated_pack = deepcopy(story.draft_pack_json)
    updated_title = story.title
    for change in payload.changes:
        updated_pack, updated_title = _apply_story_draft_change(pack_json=updated_pack, story_title=updated_title, change=change)

    try:
        validated_pack = StoryPack.model_validate(updated_pack)
    except ValidationError as exc:
        raise ApiError(
            status_code=422,
            code="validation_error",
            message="draft patch invalid",
            retryable=False,
            details={"errors": exc.errors()},
        ) from exc

    story = await update_story_draft(
        db,
        story,
        title=updated_title,
        draft_pack_json=validated_pack.model_dump(mode="json"),
    )
    latest_version = await get_latest_story_version(db, story_id)
    return _build_story_draft_response(story=story, latest_version=latest_version)


@router.post("/{story_id}/publish", response_model=StoryPublishResponse)
async def publish_story_endpoint(
    story_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> StoryPublishResponse:
    story = await get_story(db, story_id)
    if story is None:
        raise ApiError(status_code=404, code="not_found", message="story not found", retryable=False)

    report = lint_story_pack(story.draft_pack_json)
    if not report.ok:
        raise ApiError(
            status_code=422,
            code="validation_error",
            message="story lint failed",
            retryable=False,
            details={"errors": report.errors, "warnings": report.warnings},
        )

    version = await publish_story_version(db, story)
    return StoryPublishResponse(story_id=story_id, version=version.version, published_at=version.created_at)


@router.post("/generate", response_model=StoryGenerateResponse)
async def generate_story_endpoint(
    payload: StoryGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
) -> StoryGenerateResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    pipeline = GeneratorPipeline()
    try:
        result = await pipeline.run(
            seed_text=payload.seed_text,
            prompt_text=payload.prompt_text,
            target_minutes=payload.target_minutes,
            npc_count=payload.npc_count,
            style=payload.style,
            variant_seed=payload.variant_seed,
            candidate_parallelism=payload.candidate_parallelism,
            generator_version=payload.generator_version,
            palette_policy=payload.palette_policy,
        )
    except GeneratorBuildError as exc:
        log_event(
            "story_generate_failed",
            level="ERROR",
            request_id=request_id,
            error_code=exc.error_code or "generation_failed_after_regenerates",
            generation_attempts=exc.generation_attempts,
            regenerate_count=exc.regenerate_count,
            generator_version=exc.generator_version,
            variant_seed=exc.variant_seed,
            palette_policy=exc.palette_policy,
            lint_errors_count=len(exc.lint_report.errors),
            lint_warnings_count=len(exc.lint_report.warnings),
            has_prompt=bool((payload.prompt_text or "").strip()),
            has_seed=bool((payload.seed_text or "").strip()),
            prompt_text_len=len(payload.prompt_text or ""),
            seed_text_len=len(payload.seed_text or ""),
            candidate_parallelism=payload.candidate_parallelism,
        )
        raise ApiError(
            status_code=422,
            code=exc.error_code or "generation_failed",
            message="story generation failed",
            retryable=False,
            details={
                "errors": exc.lint_report.errors,
                "warnings": exc.lint_report.warnings,
                "generation_attempts": exc.generation_attempts,
                "regenerate_count": exc.regenerate_count,
                "generator_version": exc.generator_version,
                "variant_seed": exc.variant_seed,
                "palette_policy": exc.palette_policy,
                "candidate_parallelism": exc.candidate_parallelism,
                "attempt_history": exc.attempt_history,
                "notes": exc.notes,
            },
        ) from exc

    fallback_title_source = (payload.seed_text or payload.prompt_text or "generated story").strip()
    title = result.pack.get("title") or f"Generated: {fallback_title_source[:48]}"
    story = await create_story(db, title=title, pack_json=result.pack)
    version: int | None = None
    if payload.publish:
        published = await publish_story_version(db, story)
        version = published.version

    response = StoryGenerateResponse(
        status="ok",
        story_id=story.id,
        version=version,
        pack=result.pack,
        pack_hash=result.pack_hash,
        generation={
            "mode": result.generation_mode,
            "generator_version": result.generator_version,
            "variant_seed": result.variant_seed,
            "palette_policy": result.palette_policy,
            "attempts": result.generation_attempts,
            "regenerate_count": result.regenerate_count,
            "candidate_parallelism": result.candidate_parallelism,
            "compile": {
                "spec_hash": result.spec_hash,
                "spec_summary": result.spec_summary,
            },
            "lint": {"errors": result.lint_report.errors, "warnings": result.lint_report.warnings},
            "attempt_history": result.attempt_history,
        },
    )
    log_event(
        "story_generate_succeeded",
        level="INFO",
        request_id=request_id,
        story_id=story.id,
        version=version,
        generation_mode=result.generation_mode,
        pack_hash=result.pack_hash,
        generator_version=result.generator_version,
        variant_seed=result.variant_seed,
        palette_policy=result.palette_policy,
        generation_attempts=result.generation_attempts,
        regenerate_count=result.regenerate_count,
        lint_errors_count=len(result.lint_report.errors),
        lint_warnings_count=len(result.lint_report.warnings),
        has_prompt=bool((payload.prompt_text or "").strip()),
        has_seed=bool((payload.seed_text or "").strip()),
        prompt_text_len=len(payload.prompt_text or ""),
        seed_text_len=len(payload.seed_text or ""),
        candidate_parallelism=payload.candidate_parallelism,
    )
    return response


@router.get("/{story_id}", response_model=StoryGetResponse)
async def get_story_endpoint(
    story_id: str,
    version: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_async_session),
) -> StoryGetResponse:
    story = await get_story(db, story_id)
    if story is None:
        raise ApiError(status_code=404, code="not_found", message="story not found", retryable=False)

    resolved = await get_story_version(db, story_id, version) if version else await get_latest_story_version(db, story_id)
    if resolved is None:
        raise ApiError(status_code=404, code="not_found", message="published version not found", retryable=False)

    return StoryGetResponse(story_id=story_id, version=resolved.version, pack=resolved.pack_json)

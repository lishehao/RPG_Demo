from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from rpg_backend.api.contracts.author import (
    AuthorRunCreateRequest,
    AuthorRunCreateResponse,
    AuthorRunEventsResponse,
    AuthorRunEventPayload,
    AuthorRunGetResponse,
    AuthorRunArtifactSummary,
    AuthorStoryGetResponse,
    AuthorStoryListItem,
    AuthorStoryListResponse,
)
from rpg_backend.api.error_mapping import api_error_from_application_error
from rpg_backend.api.route_paths import API_AUTHOR_PREFIX
from rpg_backend.application.author_runs.models import CreateAuthorRunCommand
from rpg_backend.application.author_runs.service import author_workflow_service
from rpg_backend.application.errors import ApplicationError
from rpg_backend.infrastructure.db.async_session import get_async_session
from rpg_backend.security.deps import require_current_user

router = APIRouter(prefix=API_AUTHOR_PREFIX, tags=["author"], dependencies=[Depends(require_current_user)])


@router.post("/runs", response_model=AuthorRunCreateResponse, status_code=202)
async def create_author_run_endpoint(
    payload: AuthorRunCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> AuthorRunCreateResponse:
    try:
        view = await author_workflow_service.create_run(db=db, command=CreateAuthorRunCommand(raw_brief=payload.raw_brief))
    except ApplicationError as exc:
        raise api_error_from_application_error(exc) from exc
    return AuthorRunCreateResponse(story_id=view.story_id, run_id=view.run_id, status=view.status, created_at=view.created_at)


@router.get("/runs/{run_id}", response_model=AuthorRunGetResponse)
async def get_author_run_endpoint(
    run_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> AuthorRunGetResponse:
    try:
        view = await author_workflow_service.get_run_view(db=db, run_id=run_id)
    except ApplicationError as exc:
        raise api_error_from_application_error(exc) from exc
    return AuthorRunGetResponse(
        run_id=view.run_id,
        story_id=view.story_id,
        status=view.status,
        current_node=view.current_node,
        raw_brief=view.raw_brief,
        error_code=view.error_code,
        error_message=view.error_message,
        created_at=view.created_at,
        updated_at=view.updated_at,
        completed_at=view.completed_at,
        artifacts=[
            AuthorRunArtifactSummary(
                artifact_type=item.artifact_type,
                artifact_key=item.artifact_key,
                payload=item.payload,
                updated_at=item.updated_at,
            )
            for item in view.artifacts
        ],
    )


@router.get("/runs/{run_id}/events", response_model=AuthorRunEventsResponse)
async def get_author_run_events_endpoint(
    run_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> AuthorRunEventsResponse:
    try:
        events = await author_workflow_service.get_run_events_view(db=db, run_id=run_id)
    except ApplicationError as exc:
        raise api_error_from_application_error(exc) from exc
    return AuthorRunEventsResponse(
        run_id=run_id,
        events=[
            AuthorRunEventPayload(
                event_id=item.event_id,
                node_name=item.node_name,
                event_type=item.event_type,
                payload=item.payload,
                created_at=item.created_at,
            )
            for item in events
        ],
    )


@router.get("/stories", response_model=AuthorStoryListResponse)
async def list_author_stories_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
) -> AuthorStoryListResponse:
    items = await author_workflow_service.list_story_summaries(db=db, limit=limit)
    return AuthorStoryListResponse(
        stories=[
            AuthorStoryListItem(
                story_id=item.story_id,
                title=item.title,
                created_at=item.created_at,
                latest_run_id=item.latest_run_id,
                latest_run_status=item.latest_run_status,
                latest_run_current_node=item.latest_run_current_node,
                latest_run_updated_at=item.latest_run_updated_at,
                latest_published_version=item.latest_published_version,
                latest_published_at=item.latest_published_at,
            )
            for item in items
        ]
    )


@router.get("/stories/{story_id}", response_model=AuthorStoryGetResponse)
async def get_author_story_endpoint(
    story_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> AuthorStoryGetResponse:
    try:
        view = await author_workflow_service.get_story_view(db=db, story_id=story_id)
    except ApplicationError as exc:
        raise api_error_from_application_error(exc) from exc
    latest_run = None
    if view.latest_run is not None:
        latest_run = AuthorRunGetResponse(
            run_id=view.latest_run.run_id,
            story_id=view.latest_run.story_id,
            status=view.latest_run.status,
            current_node=view.latest_run.current_node,
            raw_brief=view.latest_run.raw_brief,
            error_code=view.latest_run.error_code,
            error_message=view.latest_run.error_message,
            created_at=view.latest_run.created_at,
            updated_at=view.latest_run.updated_at,
            completed_at=view.latest_run.completed_at,
            artifacts=[
                AuthorRunArtifactSummary(
                    artifact_type=item.artifact_type,
                    artifact_key=item.artifact_key,
                    payload=item.payload,
                    updated_at=item.updated_at,
                )
                for item in view.latest_run.artifacts
            ],
        )
    return AuthorStoryGetResponse(
        story_id=view.story_id,
        title=view.title,
        created_at=view.created_at,
        latest_run=latest_run,
        latest_published_version=view.latest_published_version,
        latest_published_at=view.latest_published_at,
        draft_pack=view.draft_pack,
    )


@router.post("/stories/{story_id}/runs", response_model=AuthorRunCreateResponse, status_code=202)
async def rerun_author_story_endpoint(
    story_id: str,
    payload: AuthorRunCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> AuthorRunCreateResponse:
    try:
        view = await author_workflow_service.rerun(
            db=db,
            story_id=story_id,
            command=CreateAuthorRunCommand(raw_brief=payload.raw_brief),
        )
    except ApplicationError as exc:
        raise api_error_from_application_error(exc) from exc
    return AuthorRunCreateResponse(story_id=view.story_id, run_id=view.run_id, status=view.status, created_at=view.created_at)

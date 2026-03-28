from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from rpg_backend.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthService,
    AuthServiceError,
    AuthSessionResponse,
    AuthenticatedSession,
    CurrentActorResponse,
)
from rpg_backend.author.contracts import (
    AuthorCopilotApplyResponse,
    AuthorCopilotSessionCreateRequest,
    AuthorCopilotSessionMessageRequest,
    AuthorCopilotSessionResponse,
    AuthorCopilotPreviewResponse,
    AuthorCopilotProposalRequest,
    AuthorCopilotProposalResponse,
    AuthorCopilotUndoResponse,
    AuthorEditorStateResponse,
    AuthorJobCreateRequest,
    AuthorJobResultResponse,
    AuthorJobStatusResponse,
    AuthorPreviewRequest,
    AuthorPreviewResponse,
    AuthorStorySparkRequest,
    AuthorStorySparkResponse,
)
from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.author.jobs import AuthorJobService
from rpg_backend.benchmark.contracts import (
    BenchmarkAuthorJobDiagnosticsResponse,
    BenchmarkPlaySessionDiagnosticsResponse,
)
from rpg_backend.config import Settings, get_settings
from rpg_backend.content_language import ContentLanguage
from rpg_backend.library.contracts import (
    DeleteStoryResponse,
    PublishedStoryCard,
    PublishedStoryDetailResponse,
    PublishedStoryListResponse,
    PublishedStoryListSort,
    PublishedStoryListView,
    StoryVisibility,
    UpdateStoryVisibilityRequest,
)
from rpg_backend.library.service import LibraryServiceError, StoryLibraryService, get_story_library_service as build_story_library_service
from rpg_backend.play.contracts import (
    PlaySessionCreateRequest,
    PlaySessionHistoryResponse,
    PlaySessionSnapshot,
    PlayTurnRequest,
)
from rpg_backend.play.service import PlayServiceError, PlaySessionService
from rpg_backend.roster.loader import ensure_character_roster_runtime_catalog


@dataclass(frozen=True)
class RuntimeServices:
    auth_service: AuthService
    story_library_service: StoryLibraryService
    author_job_service: AuthorJobService
    play_session_service: PlaySessionService


settings = get_settings()
ensure_character_roster_runtime_catalog(settings)
auth_service = AuthService(settings=settings)
story_library_service = build_story_library_service(settings)
author_job_service = AuthorJobService(settings=settings, story_library_service=story_library_service, allow_default_actor_fallback=False)
play_session_service = PlaySessionService(story_library_service=story_library_service, settings=settings, allow_default_actor_fallback=False)


def build_runtime_services(runtime_settings: Settings | None = None) -> RuntimeServices:
    resolved_settings = runtime_settings or get_settings()
    ensure_character_roster_runtime_catalog(resolved_settings)
    resolved_story_library_service = build_story_library_service(resolved_settings)
    return RuntimeServices(
        auth_service=AuthService(settings=resolved_settings),
        story_library_service=resolved_story_library_service,
        author_job_service=AuthorJobService(
            settings=resolved_settings,
            story_library_service=resolved_story_library_service,
            allow_default_actor_fallback=False,
        ),
        play_session_service=PlaySessionService(
            story_library_service=resolved_story_library_service,
            settings=resolved_settings,
            allow_default_actor_fallback=False,
        ),
    )


def get_request_settings(request: Request) -> Settings:
    runtime_settings = getattr(request.app.state, "runtime_settings", None)
    return runtime_settings if runtime_settings is not None else get_settings()


def get_auth_service(request: Request) -> AuthService:
    runtime_services: RuntimeServices | None = getattr(request.app.state, "runtime_services", None)
    return runtime_services.auth_service if runtime_services is not None else auth_service


def get_story_library_service_dependency(request: Request) -> StoryLibraryService:
    runtime_services: RuntimeServices | None = getattr(request.app.state, "runtime_services", None)
    return runtime_services.story_library_service if runtime_services is not None else story_library_service


def get_author_job_service_dependency(request: Request) -> AuthorJobService:
    runtime_services: RuntimeServices | None = getattr(request.app.state, "runtime_services", None)
    return runtime_services.author_job_service if runtime_services is not None else author_job_service


def get_play_session_service_dependency(request: Request) -> PlaySessionService:
    runtime_services: RuntimeServices | None = getattr(request.app.state, "runtime_services", None)
    return runtime_services.play_session_service if runtime_services is not None else play_session_service


def _require_benchmark_api(runtime_settings: Settings) -> None:
    if not runtime_settings.enable_benchmark_api:
        raise HTTPException(status_code=404, detail="Not found")


def _apply_session_cookie(response: Response, session: AuthenticatedSession, *, runtime_settings: Settings) -> None:
    response.set_cookie(
        key=runtime_settings.auth_session_cookie_name,
        value=session.session_token,
        max_age=runtime_settings.auth_session_ttl_seconds,
        httponly=True,
        secure=runtime_settings.auth_session_cookie_secure,
        samesite=runtime_settings.auth_session_cookie_samesite,
        path="/",
        domain=runtime_settings.auth_session_cookie_domain,
    )


def _clear_session_cookie(response: Response, *, runtime_settings: Settings) -> None:
    response.delete_cookie(
        key=runtime_settings.auth_session_cookie_name,
        path="/",
        domain=runtime_settings.auth_session_cookie_domain,
    )


def get_optional_request_session(
    request: Request,
    auth_service_dep: AuthService = Depends(get_auth_service),
) -> AuthenticatedSession | None:
    return auth_service_dep.resolve_session(request)


def get_required_request_session(
    request: Request,
    auth_service_dep: AuthService = Depends(get_auth_service),
) -> AuthenticatedSession:
    return auth_service_dep.require_session(request)


def get_required_request_user(session: AuthenticatedSession = Depends(get_required_request_session)):
    return session.user


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/auth/session", response_model=AuthSessionResponse)
def get_auth_session(session: AuthenticatedSession | None = Depends(get_optional_request_session), auth_service_dep: AuthService = Depends(get_auth_service)) -> AuthSessionResponse:
    return auth_service_dep.build_session_response(session)


@router.post("/auth/register", response_model=AuthSessionResponse)
def register_auth_user(
    payload: AuthRegisterRequest,
    response: Response,
    request: Request,
    auth_service_dep: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    session = auth_service_dep.register(payload)
    _apply_session_cookie(response, session, runtime_settings=get_request_settings(request))
    return auth_service_dep.build_session_response(session)


@router.post("/auth/login", response_model=AuthSessionResponse)
def login_auth_user(
    payload: AuthLoginRequest,
    response: Response,
    request: Request,
    auth_service_dep: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    session = auth_service_dep.login(payload)
    _apply_session_cookie(response, session, runtime_settings=get_request_settings(request))
    return auth_service_dep.build_session_response(session)


@router.post("/auth/logout", status_code=204)
def logout_auth_user(
    request: Request,
    response: Response,
    auth_service_dep: AuthService = Depends(get_auth_service),
) -> Response:
    auth_service_dep.logout(request)
    _clear_session_cookie(response, runtime_settings=get_request_settings(request))
    response.status_code = 204
    return response


@router.get("/me", response_model=CurrentActorResponse)
def get_current_actor(
    session: AuthenticatedSession = Depends(get_required_request_session),
    auth_service_dep: AuthService = Depends(get_auth_service),
) -> CurrentActorResponse:
    return auth_service_dep.build_current_actor_response(session)


@router.post("/author/story-previews", response_model=AuthorPreviewResponse)
def create_story_preview(
    payload: AuthorPreviewRequest,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorPreviewResponse:
    return author_job_service_dep.create_preview(payload, actor_user_id=user.user_id)


@router.post("/author/story-seeds/spark", response_model=AuthorStorySparkResponse)
def create_story_spark(
    payload: AuthorStorySparkRequest,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorStorySparkResponse:
    return author_job_service_dep.create_story_spark(payload, actor_user_id=user.user_id)


@router.post("/author/jobs", response_model=AuthorJobStatusResponse)
def create_author_job(
    payload: AuthorJobCreateRequest,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorJobStatusResponse:
    return author_job_service_dep.create_job(payload, actor_user_id=user.user_id)


@router.get("/author/jobs/{job_id}", response_model=AuthorJobStatusResponse)
def get_author_job(
    job_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorJobStatusResponse:
    return author_job_service_dep.get_job(job_id, actor_user_id=user.user_id)


@router.get("/author/jobs/{job_id}/events")
def stream_author_job_events(
    job_id: str,
    last_event_id: int | None = None,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> StreamingResponse:
    return StreamingResponse(
        author_job_service_dep.stream_job_events(job_id, actor_user_id=user.user_id, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/author/jobs/{job_id}/result", response_model=AuthorJobResultResponse)
def get_author_job_result(
    job_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorJobResultResponse:
    return author_job_service_dep.get_job_result(job_id, actor_user_id=user.user_id)


@router.get("/author/jobs/{job_id}/editor-state", response_model=AuthorEditorStateResponse)
def get_author_job_editor_state(
    job_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorEditorStateResponse:
    return author_job_service_dep.get_job_editor_state(job_id, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/copilot/sessions", response_model=AuthorCopilotSessionResponse)
def create_author_copilot_session(
    job_id: str,
    payload: AuthorCopilotSessionCreateRequest,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotSessionResponse:
    return author_job_service_dep.create_copilot_session(job_id, payload, actor_user_id=user.user_id)


@router.get("/author/jobs/{job_id}/copilot/sessions/{session_id}", response_model=AuthorCopilotSessionResponse)
def get_author_copilot_session(
    job_id: str,
    session_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotSessionResponse:
    return author_job_service_dep.get_copilot_session(job_id, session_id, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/copilot/sessions/{session_id}/messages", response_model=AuthorCopilotSessionResponse)
def append_author_copilot_session_message(
    job_id: str,
    session_id: str,
    payload: AuthorCopilotSessionMessageRequest,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotSessionResponse:
    return author_job_service_dep.append_copilot_session_message(job_id, session_id, payload, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/copilot/sessions/{session_id}/proposal", response_model=AuthorCopilotProposalResponse)
def create_author_copilot_session_proposal(
    job_id: str,
    session_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotProposalResponse:
    return author_job_service_dep.create_copilot_session_proposal(job_id, session_id, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/copilot/proposals", response_model=AuthorCopilotProposalResponse)
def create_author_copilot_proposal(
    job_id: str,
    payload: AuthorCopilotProposalRequest,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotProposalResponse:
    return author_job_service_dep.create_copilot_proposal(job_id, payload, actor_user_id=user.user_id)


@router.get("/author/jobs/{job_id}/copilot/proposals/{proposal_id}", response_model=AuthorCopilotProposalResponse)
def get_author_copilot_proposal(
    job_id: str,
    proposal_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotProposalResponse:
    return author_job_service_dep.get_copilot_proposal(job_id, proposal_id, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/copilot/proposals/{proposal_id}/preview", response_model=AuthorCopilotPreviewResponse)
def preview_author_copilot_proposal(
    job_id: str,
    proposal_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotPreviewResponse:
    return author_job_service_dep.preview_copilot_proposal(job_id, proposal_id, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/copilot/proposals/{proposal_id}/apply", response_model=AuthorCopilotApplyResponse)
def apply_author_copilot_proposal(
    job_id: str,
    proposal_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotApplyResponse:
    return author_job_service_dep.apply_copilot_proposal(job_id, proposal_id, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/copilot/proposals/{proposal_id}/undo", response_model=AuthorCopilotUndoResponse)
def undo_author_copilot_proposal(
    job_id: str,
    proposal_id: str,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> AuthorCopilotUndoResponse:
    return author_job_service_dep.undo_copilot_proposal(job_id, proposal_id, actor_user_id=user.user_id)


@router.post("/author/jobs/{job_id}/publish", response_model=PublishedStoryCard)
def publish_author_job(
    job_id: str,
    visibility: StoryVisibility = Query(default="private"),
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
    story_library_service_dep: StoryLibraryService = Depends(get_story_library_service_dependency),
) -> PublishedStoryCard:
    source = author_job_service_dep.get_publishable_job_source(job_id, actor_user_id=user.user_id)
    return story_library_service_dep.publish_story(
        owner_user_id=user.user_id,
        source_job_id=source.source_job_id,
        prompt_seed=source.prompt_seed,
        summary=source.summary,
        preview=source.preview,
        bundle=source.bundle,
        visibility=visibility,
    )


@router.get(
    "/benchmark/author/jobs/{job_id}/diagnostics",
    response_model=BenchmarkAuthorJobDiagnosticsResponse,
)
def get_author_job_diagnostics(
    job_id: str,
    request: Request,
    user=Depends(get_required_request_user),
    author_job_service_dep: AuthorJobService = Depends(get_author_job_service_dependency),
) -> BenchmarkAuthorJobDiagnosticsResponse:
    _require_benchmark_api(get_request_settings(request))
    return author_job_service_dep.get_job_diagnostics(job_id, actor_user_id=user.user_id)


@router.get("/stories", response_model=PublishedStoryListResponse)
def list_stories(
    q: str | None = Query(default=None, max_length=200),
    theme: str | None = Query(default=None, max_length=80),
    language: ContentLanguage | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    sort: PublishedStoryListSort | None = Query(default=None),
    view: PublishedStoryListView = Query(default="accessible"),
    session: AuthenticatedSession | None = Depends(get_optional_request_session),
    story_library_service_dep: StoryLibraryService = Depends(get_story_library_service_dependency),
) -> PublishedStoryListResponse:
    return story_library_service_dep.list_stories(
        actor_user_id=session.user.user_id if session is not None else None,
        query=q,
        theme=theme,
        language=language,
        limit=limit,
        cursor=cursor,
        sort=sort,
        view=view,
    )


@router.get("/stories/{story_id}", response_model=PublishedStoryDetailResponse)
def get_story(
    story_id: str,
    session: AuthenticatedSession | None = Depends(get_optional_request_session),
    story_library_service_dep: StoryLibraryService = Depends(get_story_library_service_dependency),
) -> PublishedStoryDetailResponse:
    return story_library_service_dep.get_story_detail(
        story_id,
        actor_user_id=session.user.user_id if session is not None else None,
    )


@router.patch("/stories/{story_id}/visibility", response_model=PublishedStoryCard)
def update_story_visibility(
    story_id: str,
    payload: UpdateStoryVisibilityRequest,
    user=Depends(get_required_request_user),
    story_library_service_dep: StoryLibraryService = Depends(get_story_library_service_dependency),
) -> PublishedStoryCard:
    return story_library_service_dep.update_story_visibility(
        actor_user_id=user.user_id,
        story_id=story_id,
        request=payload,
    )


@router.delete("/stories/{story_id}", response_model=DeleteStoryResponse)
def delete_story(
    story_id: str,
    user=Depends(get_required_request_user),
    story_library_service_dep: StoryLibraryService = Depends(get_story_library_service_dependency),
    play_session_service_dep: PlaySessionService = Depends(get_play_session_service_dependency),
) -> DeleteStoryResponse:
    play_session_service_dep.delete_all_sessions_for_story(story_id=story_id)
    story_library_service_dep.delete_story(actor_user_id=user.user_id, story_id=story_id)
    return DeleteStoryResponse(story_id=story_id, deleted=True)


@router.post("/play/sessions", response_model=PlaySessionSnapshot)
def create_play_session(
    payload: PlaySessionCreateRequest,
    user=Depends(get_required_request_user),
    play_session_service_dep: PlaySessionService = Depends(get_play_session_service_dependency),
) -> PlaySessionSnapshot:
    return play_session_service_dep.create_session(payload.story_id, actor_user_id=user.user_id)


@router.get("/play/sessions/{session_id}", response_model=PlaySessionSnapshot)
def get_play_session(
    session_id: str,
    user=Depends(get_required_request_user),
    play_session_service_dep: PlaySessionService = Depends(get_play_session_service_dependency),
) -> PlaySessionSnapshot:
    return play_session_service_dep.get_session(session_id, actor_user_id=user.user_id)


@router.get("/play/sessions/{session_id}/history", response_model=PlaySessionHistoryResponse)
def get_play_session_history(
    session_id: str,
    user=Depends(get_required_request_user),
    play_session_service_dep: PlaySessionService = Depends(get_play_session_service_dependency),
) -> PlaySessionHistoryResponse:
    return play_session_service_dep.get_session_history(session_id, actor_user_id=user.user_id)


@router.post("/play/sessions/{session_id}/turns", response_model=PlaySessionSnapshot)
def submit_play_turn(
    session_id: str,
    payload: PlayTurnRequest,
    user=Depends(get_required_request_user),
    play_session_service_dep: PlaySessionService = Depends(get_play_session_service_dependency),
) -> PlaySessionSnapshot:
    return play_session_service_dep.submit_turn(session_id, payload, actor_user_id=user.user_id)


@router.get(
    "/benchmark/play/sessions/{session_id}/diagnostics",
    response_model=BenchmarkPlaySessionDiagnosticsResponse,
)
def get_play_session_diagnostics(
    session_id: str,
    request: Request,
    user=Depends(get_required_request_user),
    play_session_service_dep: PlaySessionService = Depends(get_play_session_service_dependency),
) -> BenchmarkPlaySessionDiagnosticsResponse:
    _require_benchmark_api(get_request_settings(request))
    return play_session_service_dep.get_session_diagnostics(session_id, actor_user_id=user.user_id)


def create_app(
    *,
    runtime_settings: Settings | None = None,
    runtime_services: RuntimeServices | None = None,
) -> FastAPI:
    resolved_settings = runtime_settings or get_settings()
    app = FastAPI(title="rpg-demo-rebuild")
    cors_origins = resolved_settings.resolved_frontend_dev_cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if runtime_settings is not None:
        app.state.runtime_settings = runtime_settings
    if runtime_services is not None:
        app.state.runtime_services = runtime_services
    app.add_exception_handler(
        AuthorGatewayError,
        lambda _request, exc: JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        ),
    )
    app.add_exception_handler(
        LibraryServiceError,
        lambda _request, exc: JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        ),
    )
    app.add_exception_handler(
        PlayServiceError,
        lambda _request, exc: JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        ),
    )
    app.add_exception_handler(
        AuthServiceError,
        lambda _request, exc: JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        ),
    )
    portrait_dir = Path(resolved_settings.local_portrait_dir).expanduser().resolve()
    author_portrait_dir = Path(resolved_settings.local_author_portrait_dir).expanduser().resolve()
    app.mount(
        "/portraits/roster",
        StaticFiles(directory=str(portrait_dir), check_dir=False),
        name="roster-portraits",
    )
    app.mount(
        "/portraits/author-jobs",
        StaticFiles(directory=str(author_portrait_dir), check_dir=False),
        name="author-job-portraits",
    )
    app.include_router(router)
    return app


app = create_app()

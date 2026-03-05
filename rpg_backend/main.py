from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from rpg_backend.auth import login_and_issue_token, require_auth
from rpg_backend.errors import ApiError, build_error_response
from rpg_backend.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionGetResponse,
    SessionHistoryResponse,
    SessionHistoryTurn,
    SessionStepRequest,
    SessionStepResponse,
    StoryGenerateRequest,
    StoryGenerateResponse,
    StoryListItem,
    StoryListResponse,
)
from rpg_backend.store import store

app = FastAPI(title="RPG Mock Backend", version="1.0.0")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError):
    return build_error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, _: RequestValidationError):
    return build_error_response(
        request,
        status_code=422,
        code="validation_error",
        message="request validation failed",
        retryable=False,
    )


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: HTTPException | StarletteHTTPException):
    status_code = int(exc.status_code)
    if status_code == 404:
        code = "not_found"
        message = "resource not found"
    elif status_code == 401:
        code = "unauthorized"
        message = "unauthorized"
    else:
        code = "request_invalid"
        message = "request failed"
    return build_error_response(
        request,
        status_code=status_code,
        code=code,
        message=message,
        retryable=False,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/admin/auth/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest) -> AdminLoginResponse:
    token = login_and_issue_token(payload.email, payload.password)
    if token is None:
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="invalid email or password",
            retryable=False,
        )
    return AdminLoginResponse(token=token, access_token=token, token_type="bearer")


@app.post("/stories/generate", response_model=StoryGenerateResponse, dependencies=[Depends(require_auth)])
async def generate_story(payload: StoryGenerateRequest) -> StoryGenerateResponse:
    story = store.generate_story(theme=payload.theme, difficulty=payload.difficulty)
    return StoryGenerateResponse(
        story_id=story.story_id,
        title=story.title,
        published=story.published,
    )


@app.get("/stories", response_model=StoryListResponse, dependencies=[Depends(require_auth)])
async def list_stories() -> StoryListResponse:
    items = store.list_stories()
    return StoryListResponse(stories=[StoryListItem(story_id=item.story_id, title=item.title) for item in items])


@app.post("/sessions", response_model=SessionCreateResponse, dependencies=[Depends(require_auth)])
async def create_session(payload: SessionCreateRequest) -> SessionCreateResponse:
    session = store.create_session(story_id=payload.story_id)
    if session is None:
        raise ApiError(status_code=404, code="not_found", message="story not found", retryable=False)
    return SessionCreateResponse(session_id=session.session_id)


@app.get("/sessions/{session_id}", response_model=SessionGetResponse, dependencies=[Depends(require_auth)])
async def get_session(session_id: str) -> SessionGetResponse:
    session = store.get_session(session_id)
    if session is None:
        raise ApiError(status_code=404, code="not_found", message="session not found", retryable=False)
    return SessionGetResponse(
        session_id=session.session_id,
        story_id=session.story_id,
        created_at=session.created_at,
        state=session.state,
    )


@app.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse, dependencies=[Depends(require_auth)])
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    history = store.get_history(session_id)
    if history is None:
        raise ApiError(status_code=404, code="not_found", message="session not found", retryable=False)
    return SessionHistoryResponse(
        history=[
            SessionHistoryTurn(turn=entry.turn, narration=entry.narration, actions=entry.actions)
            for entry in history
        ]
    )


@app.post("/sessions/{session_id}/step", response_model=SessionStepResponse, dependencies=[Depends(require_auth)])
async def step_session(session_id: str, payload: SessionStepRequest) -> SessionStepResponse:
    existing = store.get_session(session_id)
    if existing is None:
        raise ApiError(status_code=404, code="not_found", message="session not found", retryable=False)
    if existing.state != "active":
        raise ApiError(status_code=409, code="session_inactive", message="session is not active", retryable=False)

    step = store.step(
        session_id=session_id,
        move_id=payload.move_id,
        free_text=payload.free_text,
    )
    if step is None:
        raise ApiError(status_code=404, code="not_found", message="session not found", retryable=False)

    return SessionStepResponse(
        turn=step.turn,
        narration=step.narration,
        actions=step.actions,
        risk_hint=step.risk_hint,
    )


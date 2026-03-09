from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from typing_extensions import TypedDict

from rpg_backend.application.author_runs.errors import AuthorRunNotFoundError, AuthorStoryNotReadyForPublishError
from rpg_backend.application.author_runs.models import (
    AuthorRunArtifactView,
    AuthorRunCreateView,
    AuthorRunEventView,
    AuthorRunView,
    AuthorStorySummaryView,
    AuthorStoryView,
    CreateAuthorRunCommand,
)
from rpg_backend.domain.linter import lint_story_pack
from rpg_backend.generator.author_workflow_assembler import assemble_story_pack
from rpg_backend.generator.author_workflow_chains import BeatGenerationChain, PackRepairChain, StoryOverviewChain
from rpg_backend.generator.author_workflow_models import BeatBlueprint, BeatDraft, BeatDraftLLM, BeatOverviewContext, BeatPrefixSummary, StoryOverview, model_to_json_payload
from rpg_backend.generator.author_workflow_errors import PromptCompileError
from rpg_backend.generator.author_workflow_planner import check_beat_blueprints, plan_beat_blueprints_from_overview
from rpg_backend.generator.author_workflow_validators import (
    build_structured_prefix_summary,
    check_story_overview,
    lint_beat_draft,
    project_overview_for_beat_generation,
)
from rpg_backend.infrastructure.db.async_engine import async_engine
from rpg_backend.infrastructure.db.transaction import transactional
from rpg_backend.infrastructure.repositories.author_runs_async import (
    create_author_run,
    create_author_run_event,
    get_author_run,
    get_latest_author_run_for_story,
    list_author_run_artifacts,
    list_author_run_events,
    list_author_runs_for_story,
    list_author_stories,
    update_author_run_status,
    upsert_author_run_artifact,
)
from rpg_backend.infrastructure.repositories.stories_async import create_story, get_latest_story_version, get_story, update_story_draft


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _find_prompt_compile_error(exc: BaseException) -> PromptCompileError | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, PromptCompileError):
            return current
        current = current.__cause__ or current.__context__
    return None


class AuthorWorkflowState(TypedDict, total=False):
    story_id: str
    run_id: str
    raw_brief: str
    overview: StoryOverview
    overview_errors: list[str]
    overview_attempts: int
    beat_blueprints: list[BeatBlueprint]
    beat_plan_errors: list[str]
    beat_plan_attempts: int
    current_beat_index: int
    current_beat_attempts: int
    beat_overview_context: BeatOverviewContext | None
    current_beat_llm: BeatDraftLLM | None
    current_beat_draft: BeatDraft | None
    beat_drafts: list[BeatDraft]
    beat_lint_errors: list[str]
    beat_lint_warnings: list[str]
    prefix_summary: BeatPrefixSummary
    story_pack: dict[str, Any]
    final_lint_errors: list[str]
    final_lint_warnings: list[str]
    repair_count: int
    status: str


def _placeholder_title(raw_brief: str) -> str:
    compact = " ".join((raw_brief or "").strip().split())
    if not compact:
        return "Author Run Draft"
    return compact[:80]


def _artifact_payload_from_state(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _artifact_payload_from_state(item) for key, item in value.items()}
    if isinstance(value, list):
        return {"items": [model_to_json_payload(item) if hasattr(item, "model_dump") else item for item in value]}
    return {"value": value}


def _persist_artifacts_for_update(update: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    artifacts: list[tuple[str, str, dict[str, Any]]] = []
    if "overview" in update:
        artifacts.append(("overview", "", _artifact_payload_from_state(update["overview"])))
    if "overview_errors" in update:
        artifacts.append(("overview_check", "", {"errors": list(update["overview_errors"]) }))
    if "beat_blueprints" in update:
        artifacts.append(("beat_blueprints", "", _artifact_payload_from_state(update["beat_blueprints"])))
    if "beat_plan_errors" in update:
        artifacts.append(("beat_plan_check", "", {"errors": list(update["beat_plan_errors"]) }))
    if "beat_overview_context" in update and update["beat_overview_context"] is not None:
        artifacts.append(("beat_overview_context", str(update.get("current_beat_index", "")), _artifact_payload_from_state(update["beat_overview_context"])))
    if "current_beat_llm" in update and update["current_beat_llm"] is not None:
        beat = update.get("current_beat_draft")
        beat_id = beat.beat_id if hasattr(beat, "beat_id") else str(update.get("current_beat_index", ""))
        artifacts.append(("current_beat_llm", beat_id, _artifact_payload_from_state(update["current_beat_llm"])))
    if "current_beat_draft" in update and update["current_beat_draft"] is not None:
        beat = update["current_beat_draft"]
        beat_id = beat.beat_id if hasattr(beat, "beat_id") else str(update.get("current_beat_index", ""))
        artifacts.append(("current_beat_draft", beat_id, _artifact_payload_from_state(beat)))
    if "beat_drafts" in update:
        for beat in update["beat_drafts"]:
            artifacts.append(("accepted_beat_draft", beat.beat_id, _artifact_payload_from_state(beat)))
    if "beat_lint_errors" in update or "beat_lint_warnings" in update:
        artifacts.append(
            (
                "beat_lint",
                str(update.get("current_beat_index", "")),
                {
                    "errors": list(update.get("beat_lint_errors") or []),
                    "warnings": list(update.get("beat_lint_warnings") or []),
                },
            )
        )
    if "prefix_summary" in update:
        artifacts.append(("prefix_summary", str(update.get("current_beat_index", "")), _artifact_payload_from_state(update["prefix_summary"])))
    if "story_pack" in update:
        artifacts.append(("story_pack", "", _artifact_payload_from_state(update["story_pack"])))
    if "final_lint_errors" in update or "final_lint_warnings" in update:
        artifacts.append(
            (
                "final_lint",
                "",
                {
                    "errors": list(update.get("final_lint_errors") or []),
                    "warnings": list(update.get("final_lint_warnings") or []),
                },
            )
        )
    return artifacts


@dataclass
class _InlineScheduler:
    schedule_func: Callable[[str], Awaitable[None]]
    tasks: set[asyncio.Task]

    async def schedule(self, run_id: str) -> None:
        loop = asyncio.get_running_loop()
        task = loop.create_task(self.schedule_func(run_id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


class AuthorWorkflowService:
    def __init__(
        self,
        *,
        overview_chain_factory: Callable[[], StoryOverviewChain] | None = None,
        beat_chain_factory: Callable[[], BeatGenerationChain] | None = None,
        repair_chain_factory: Callable[[], PackRepairChain] | None = None,
    ) -> None:
        self.overview_chain_factory = overview_chain_factory or StoryOverviewChain
        self.beat_chain_factory = beat_chain_factory or BeatGenerationChain
        self.repair_chain_factory = repair_chain_factory or PackRepairChain
        self._tasks: set[asyncio.Task] = set()
        self.scheduler = _InlineScheduler(schedule_func=self._execute_run, tasks=self._tasks)

    async def create_run(self, *, db: AsyncSession, command: CreateAuthorRunCommand) -> AuthorRunCreateView:
        async with transactional(db):
            story = await create_story(db, title=_placeholder_title(command.raw_brief), pack_json={})
            run = await create_author_run(db, story_id=story.id, raw_brief=command.raw_brief, status="pending")
            await upsert_author_run_artifact(db, run_id=run.id, artifact_type="raw_brief", artifact_key="", payload_json={"text": command.raw_brief})
        await self.scheduler.schedule(run.id)
        return AuthorRunCreateView(story_id=story.id, run_id=run.id, status=run.status, created_at=run.created_at)

    async def rerun(self, *, db: AsyncSession, story_id: str, command: CreateAuthorRunCommand) -> AuthorRunCreateView:
        story = await get_story(db, story_id)
        if story is None:
            raise AuthorRunNotFoundError(run_id=story_id)
        async with transactional(db):
            run = await create_author_run(db, story_id=story_id, raw_brief=command.raw_brief, status="pending")
            await upsert_author_run_artifact(db, run_id=run.id, artifact_type="raw_brief", artifact_key="", payload_json={"text": command.raw_brief})
        await self.scheduler.schedule(run.id)
        return AuthorRunCreateView(story_id=story_id, run_id=run.id, status=run.status, created_at=run.created_at)

    async def get_run_view(self, *, db: AsyncSession, run_id: str) -> AuthorRunView:
        run = await get_author_run(db, run_id)
        if run is None:
            raise AuthorRunNotFoundError(run_id=run_id)
        artifacts = await list_author_run_artifacts(db, run.id)
        return AuthorRunView(
            run_id=run.id,
            story_id=run.story_id,
            status=run.status,
            current_node=run.current_node,
            raw_brief=run.raw_brief,
            error_code=run.error_code,
            error_message=run.error_message,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
            artifacts=[
                AuthorRunArtifactView(
                    artifact_type=item.artifact_type,
                    artifact_key=item.artifact_key,
                    payload=item.payload_json,
                    updated_at=item.updated_at,
                )
                for item in artifacts
            ],
        )

    async def get_run_events_view(self, *, db: AsyncSession, run_id: str) -> list[AuthorRunEventView]:
        run = await get_author_run(db, run_id)
        if run is None:
            raise AuthorRunNotFoundError(run_id=run_id)
        return [
            AuthorRunEventView(
                event_id=item.id,
                node_name=item.node_name,
                event_type=item.event_type,
                payload=item.payload_json,
                created_at=item.created_at,
            )
            for item in await list_author_run_events(db, run_id)
        ]

    async def list_story_summaries(self, *, db: AsyncSession, limit: int) -> list[AuthorStorySummaryView]:
        stories = await list_author_stories(db, limit=limit)
        views: list[AuthorStorySummaryView] = []
        for story in stories:
            latest_run = await get_latest_author_run_for_story(db, story.id)
            latest_version = await get_latest_story_version(db, story.id)
            views.append(
                AuthorStorySummaryView(
                    story_id=story.id,
                    title=story.title,
                    created_at=story.created_at,
                    latest_run_id=latest_run.id if latest_run else None,
                    latest_run_status=latest_run.status if latest_run else None,
                    latest_run_current_node=latest_run.current_node if latest_run else None,
                    latest_run_updated_at=latest_run.updated_at if latest_run else None,
                    latest_published_version=latest_version.version if latest_version else None,
                    latest_published_at=latest_version.created_at if latest_version else None,
                )
            )
        return views

    async def get_story_view(self, *, db: AsyncSession, story_id: str) -> AuthorStoryView:
        story = await get_story(db, story_id)
        if story is None:
            raise AuthorRunNotFoundError(run_id=story_id)
        latest_run = await get_latest_author_run_for_story(db, story_id)
        latest_version = await get_latest_story_version(db, story.id)
        return AuthorStoryView(
            story_id=story.id,
            title=story.title,
            created_at=story.created_at,
            latest_run=await self.get_run_view(db=db, run_id=latest_run.id) if latest_run else None,
            latest_published_version=latest_version.version if latest_version else None,
            latest_published_at=latest_version.created_at if latest_version else None,
            draft_pack=story.draft_pack_json,
        )

    async def assert_publishable(self, *, db: AsyncSession, story: Any) -> None:
        latest_run = await get_latest_author_run_for_story(db, story.id)
        if latest_run is None or latest_run.status != "review_ready":
            raise AuthorStoryNotReadyForPublishError(
                story_id=story.id,
                latest_run_status=latest_run.status if latest_run else None,
            )

    def _build_graph(self):
        from langgraph.graph import END, START, StateGraph

        def tracked(node_name: str, func):
            async def _wrapped(state: AuthorWorkflowState):
                await self._mark_run_node_started(run_id=state["run_id"], node_name=node_name)
                result = func(state)
                if inspect.isawaitable(result):
                    return await result
                return result

            return _wrapped

        async def generate_story_overview(state: AuthorWorkflowState) -> dict[str, Any]:
            feedback = list(state.get("overview_errors") or [])
            raw_brief = state["raw_brief"]
            if feedback:
                raw_brief = f"{raw_brief}\n\nPrevious feedback to fix:\n- " + "\n- ".join(feedback)
            overview = await self.overview_chain_factory().compile(raw_brief=raw_brief)
            return {
                "overview": overview,
                "overview_attempts": int(state.get("overview_attempts", 0)) + 1,
                "overview_errors": [],
                "beat_plan_errors": [],
                "beat_plan_attempts": 0,
            }

        def overview_check(state: AuthorWorkflowState) -> dict[str, Any]:
            return {"overview_errors": check_story_overview(state["overview"]) }

        def route_after_overview_check(state: AuthorWorkflowState) -> str:
            if state.get("overview_errors"):
                return "generate_story_overview" if int(state.get("overview_attempts", 0)) < 3 else "workflow_failed"
            return "plan_beats"

        def plan_beats(state: AuthorWorkflowState) -> dict[str, Any]:
            blueprints = plan_beat_blueprints_from_overview(state["overview"])
            return {
                "beat_blueprints": blueprints,
                "beat_plan_attempts": int(state.get("beat_plan_attempts", 0)) + 1,
                "beat_plan_errors": [],
                "current_beat_index": 0,
                "current_beat_attempts": 0,
                "beat_drafts": [],
                "prefix_summary": build_structured_prefix_summary([]),
            }

        def beat_plan_check(state: AuthorWorkflowState) -> dict[str, Any]:
            return {"beat_plan_errors": check_beat_blueprints(state.get("beat_blueprints") or [])}

        def route_after_beat_plan_check(state: AuthorWorkflowState) -> str:
            if not state.get("beat_plan_errors"):
                return "generate_next_beat"
            if int(state.get("beat_plan_attempts", 0)) < 2:
                return "plan_beats"
            if int(state.get("overview_attempts", 0)) < 3:
                return "generate_story_overview"
            return "workflow_failed"

        async def generate_next_beat(state: AuthorWorkflowState) -> dict[str, Any]:
            beat_index = int(state.get("current_beat_index", 0))
            prior_beats = list(state.get("beat_drafts") or [])
            prefix_summary = build_structured_prefix_summary(prior_beats)
            overview_context = project_overview_for_beat_generation(state["overview"])
            last_accepted_beat = prior_beats[-1].model_dump(mode="json") if prior_beats else None
            chain = self.beat_chain_factory()
            draft = await chain.compile(
                story_id=state["story_id"],
                overview_context=overview_context,
                blueprint=state["beat_blueprints"][beat_index].model_dump(mode="json"),
                last_accepted_beat=last_accepted_beat,
                prefix_summary=prefix_summary,
                lint_feedback=list(state.get("beat_lint_errors") or []),
            )
            update = {
                "beat_overview_context": overview_context,
                "current_beat_draft": draft,
                "current_beat_attempts": int(state.get("current_beat_attempts", 0)) + 1,
                "prefix_summary": prefix_summary,
                "beat_lint_errors": [],
                "beat_lint_warnings": [],
            }
            llm_draft = getattr(chain, "last_beat_draft_llm", None)
            if llm_draft is not None:
                update["current_beat_llm"] = llm_draft
            return update

        def beat_lint(state: AuthorWorkflowState) -> dict[str, Any]:
            beat_index = int(state.get("current_beat_index", 0))
            draft = state.get("current_beat_draft")
            if draft is None:
                return {"beat_lint_errors": ["current beat draft missing"], "beat_lint_warnings": []}
            report = lint_beat_draft(
                overview=state["overview"],
                blueprint=state["beat_blueprints"][beat_index],
                draft=draft,
                prior_beats=list(state.get("beat_drafts") or []),
            )
            update: dict[str, Any] = {
                "beat_lint_errors": list(report.errors),
                "beat_lint_warnings": list(report.warnings),
            }
            if report.ok:
                accepted = [*list(state.get("beat_drafts") or []), draft]
                update.update(
                    {
                        "beat_drafts": accepted,
                        "current_beat_index": beat_index + 1,
                        "current_beat_attempts": 0,
                        "beat_overview_context": None,
                        "current_beat_llm": None,
                        "current_beat_draft": None,
                        "prefix_summary": build_structured_prefix_summary(accepted),
                    }
                )
            return update

        def route_after_beat_lint(state: AuthorWorkflowState) -> str:
            if state.get("beat_lint_errors"):
                return "generate_next_beat" if int(state.get("current_beat_attempts", 0)) < 3 else "workflow_failed"
            if int(state.get("current_beat_index", 0)) < len(state.get("beat_blueprints") or []):
                return "generate_next_beat"
            return "assemble_story_pack"

        def assemble_story_pack_node(state: AuthorWorkflowState) -> dict[str, Any]:
            pack = assemble_story_pack(
                story_id=state["story_id"],
                overview=state["overview"],
                beat_blueprints=list(state.get("beat_blueprints") or []),
                beat_drafts=list(state.get("beat_drafts") or []),
            )
            return {"story_pack": pack}

        def final_lint(state: AuthorWorkflowState) -> dict[str, Any]:
            report = lint_story_pack(state["story_pack"])
            return {"final_lint_errors": list(report.errors), "final_lint_warnings": list(report.warnings)}

        def route_after_final_lint(state: AuthorWorkflowState) -> str:
            if not state.get("final_lint_errors"):
                return "review_ready"
            return "repair_pack" if int(state.get("repair_count", 0)) < 2 else "workflow_failed"

        async def repair_pack(state: AuthorWorkflowState) -> dict[str, Any]:
            repaired = await self.repair_chain_factory().compile(
                story_pack=state["story_pack"],
                lint_errors=list(state.get("final_lint_errors") or []),
                lint_warnings=list(state.get("final_lint_warnings") or []),
                repair_count=int(state.get("repair_count", 0)),
            )
            return {
                "story_pack": repaired.model_dump(mode="json"),
                "repair_count": int(state.get("repair_count", 0)) + 1,
            }

        def review_ready(state: AuthorWorkflowState) -> dict[str, Any]:
            return {"status": "review_ready"}

        def workflow_failed(state: AuthorWorkflowState) -> dict[str, Any]:
            return {"status": "failed"}

        builder = StateGraph(AuthorWorkflowState)
        builder.add_node("generate_story_overview", tracked("generate_story_overview", generate_story_overview))
        builder.add_node("overview_check", tracked("overview_check", overview_check))
        builder.add_node("plan_beats", tracked("plan_beats", plan_beats))
        builder.add_node("beat_plan_check", tracked("beat_plan_check", beat_plan_check))
        builder.add_node("generate_next_beat", tracked("generate_next_beat", generate_next_beat))
        builder.add_node("beat_lint", tracked("beat_lint", beat_lint))
        builder.add_node("assemble_story_pack", tracked("assemble_story_pack", assemble_story_pack_node))
        builder.add_node("final_lint", tracked("final_lint", final_lint))
        builder.add_node("repair_pack", tracked("repair_pack", repair_pack))
        builder.add_node("review_ready", tracked("review_ready", review_ready))
        builder.add_node("workflow_failed", tracked("workflow_failed", workflow_failed))

        builder.add_edge(START, "generate_story_overview")
        builder.add_edge("generate_story_overview", "overview_check")
        builder.add_conditional_edges(
            "overview_check",
            route_after_overview_check,
            {
                "generate_story_overview": "generate_story_overview",
                "plan_beats": "plan_beats",
                "workflow_failed": "workflow_failed",
            },
        )
        builder.add_edge("plan_beats", "beat_plan_check")
        builder.add_conditional_edges(
            "beat_plan_check",
            route_after_beat_plan_check,
            {
                "plan_beats": "plan_beats",
                "generate_story_overview": "generate_story_overview",
                "generate_next_beat": "generate_next_beat",
                "workflow_failed": "workflow_failed",
            },
        )
        builder.add_edge("generate_next_beat", "beat_lint")
        builder.add_conditional_edges(
            "beat_lint",
            route_after_beat_lint,
            {
                "generate_next_beat": "generate_next_beat",
                "assemble_story_pack": "assemble_story_pack",
                "workflow_failed": "workflow_failed",
            },
        )
        builder.add_edge("assemble_story_pack", "final_lint")
        builder.add_conditional_edges(
            "final_lint",
            route_after_final_lint,
            {
                "repair_pack": "repair_pack",
                "review_ready": "review_ready",
                "workflow_failed": "workflow_failed",
            },
        )
        builder.add_edge("repair_pack", "final_lint")
        builder.add_edge("review_ready", END)
        builder.add_edge("workflow_failed", END)
        return builder.compile()

    async def _persist_run_update(self, *, run_id: str, node_name: str, update: dict[str, Any]) -> None:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            run = await get_author_run(db, run_id)
            if run is None:
                return
            async with transactional(db):
                await update_author_run_status(db, run, status="running", current_node=node_name)
                await create_author_run_event(
                    db,
                    run_id=run_id,
                    node_name=node_name,
                    event_type="node_completed",
                    payload_json={key: _artifact_payload_from_state(value) for key, value in update.items()},
                )
                for artifact_type, artifact_key, payload in _persist_artifacts_for_update(update):
                    await upsert_author_run_artifact(
                        db,
                        run_id=run_id,
                        artifact_type=artifact_type,
                        artifact_key=artifact_key,
                        payload_json=payload,
                    )

    async def _mark_run_node_started(self, *, run_id: str, node_name: str) -> None:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            run = await get_author_run(db, run_id)
            if run is None:
                return
            async with transactional(db):
                await update_author_run_status(db, run, status="running", current_node=node_name)
                await create_author_run_event(
                    db,
                    run_id=run_id,
                    node_name=node_name,
                    event_type="node_started",
                    payload_json={},
                )

    async def _complete_run(self, *, run_id: str, final_state: AuthorWorkflowState) -> None:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            run = await get_author_run(db, run_id)
            if run is None:
                return
            story = await get_story(db, run.story_id)
            async with transactional(db):
                if final_state.get("status") == "review_ready" and story is not None and final_state.get("story_pack"):
                    await update_story_draft(
                        db,
                        story,
                        title=final_state["overview"].title,
                        draft_pack_json=final_state["story_pack"],
                    )
                    await update_author_run_status(
                        db,
                        run,
                        status="review_ready",
                        current_node="review_ready",
                        completed=True,
                    )
                    await create_author_run_event(
                        db,
                        run_id=run_id,
                        node_name="review_ready",
                        event_type="run_completed",
                        payload_json={"status": "review_ready"},
                    )
                    return
                latest_error = list(final_state.get("final_lint_errors") or final_state.get("beat_lint_errors") or final_state.get("overview_errors") or final_state.get("beat_plan_errors") or ["workflow failed"])
                await update_author_run_status(
                    db,
                    run,
                    status="failed",
                    current_node="workflow_failed",
                    error_code="author_workflow_failed",
                    error_message=latest_error[0],
                    completed=True,
                )
                await create_author_run_event(
                    db,
                    run_id=run_id,
                    node_name="workflow_failed",
                    event_type="run_completed",
                    payload_json={"status": "failed", "errors": latest_error},
                )

    async def _execute_run(self, run_id: str) -> None:
        async with AsyncSession(async_engine, expire_on_commit=False) as db:
            run = await get_author_run(db, run_id)
            if run is None:
                return
            story = await get_story(db, run.story_id)
            if story is None:
                return
            raw_brief = run.raw_brief
        graph = self._build_graph()
        final_state: AuthorWorkflowState = {
            "story_id": story.id,
            "run_id": run.id,
            "raw_brief": raw_brief,
            "overview_attempts": 0,
            "beat_plan_attempts": 0,
            "current_beat_index": 0,
            "current_beat_attempts": 0,
            "beat_drafts": [],
            "repair_count": 0,
            "prefix_summary": build_structured_prefix_summary([]),
            "status": "running",
        }
        try:
            async for mode, payload in graph.astream(final_state, stream_mode=["updates", "values"]):
                if mode == "updates":
                    for node_name, update in payload.items():
                        await self._persist_run_update(run_id=run_id, node_name=node_name, update=update)
                else:
                    final_state = payload
        except PromptCompileError as exc:
            async with AsyncSession(async_engine, expire_on_commit=False) as db:
                run = await get_author_run(db, run_id)
                if run is None:
                    return
                async with transactional(db):
                    await update_author_run_status(
                        db,
                        run,
                        status="failed",
                        current_node=run.current_node,
                        error_code=exc.error_code,
                        error_message=exc.errors[0] if exc.errors else str(exc),
                        completed=True,
                    )
                    await create_author_run_event(
                        db,
                        run_id=run_id,
                        node_name=run.current_node or "workflow",
                        event_type="run_exception",
                        payload_json={
                            "message": str(exc),
                            "error_code": exc.error_code,
                            "errors": list(exc.errors),
                            "notes": list(exc.notes),
                        },
                    )
                    await upsert_author_run_artifact(
                        db,
                        run_id=run_id,
                        artifact_type="workflow_error",
                        artifact_key=run.current_node or "workflow",
                        payload_json={"error_code": exc.error_code, "errors": list(exc.errors), "notes": list(exc.notes)},
                    )
            return
        except Exception as exc:  # noqa: BLE001
            prompt_exc = _find_prompt_compile_error(exc)
            async with AsyncSession(async_engine, expire_on_commit=False) as db:
                run = await get_author_run(db, run_id)
                if run is None:
                    return
                async with transactional(db):
                    if prompt_exc is not None:
                        await update_author_run_status(
                            db,
                            run,
                            status="failed",
                            current_node=run.current_node,
                            error_code=prompt_exc.error_code,
                            error_message=prompt_exc.errors[0] if prompt_exc.errors else str(prompt_exc),
                            completed=True,
                        )
                        await create_author_run_event(
                            db,
                            run_id=run_id,
                            node_name=run.current_node or "workflow",
                            event_type="run_exception",
                            payload_json={
                                "message": str(prompt_exc),
                                "error_code": prompt_exc.error_code,
                                "errors": list(prompt_exc.errors),
                                "notes": list(prompt_exc.notes),
                            },
                        )
                        await upsert_author_run_artifact(
                            db,
                            run_id=run_id,
                            artifact_type="workflow_error",
                            artifact_key=run.current_node or "workflow",
                            payload_json={"error_code": prompt_exc.error_code, "errors": list(prompt_exc.errors), "notes": list(prompt_exc.notes)},
                        )
                    else:
                        await update_author_run_status(
                            db,
                            run,
                            status="failed",
                            current_node=run.current_node,
                            error_code="author_workflow_exception",
                            error_message=str(exc),
                            completed=True,
                        )
                        await create_author_run_event(
                            db,
                            run_id=run_id,
                            node_name=run.current_node or "workflow",
                            event_type="run_exception",
                            payload_json={"message": str(exc)},
                        )
            return
        await self._complete_run(run_id=run_id, final_state=final_state)


author_workflow_service = AuthorWorkflowService()

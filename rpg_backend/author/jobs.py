from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import tempfile
from typing import Any
from uuid import uuid4

from rpg_backend.author.checkpointer import get_author_checkpointer, graph_config
from rpg_backend.author.contracts import (
    AuthorCacheMetrics,
    AuthorJobCreateRequest,
    AuthorJobProgress,
    AuthorJobResultResponse,
    AuthorStorySummary,
    AuthorJobStatusResponse,
    AuthorPreviewRequest,
    AuthorPreviewResponse,
    DesignBundle,
)
from rpg_backend.author.display import (
    build_progress_snapshot,
)
from rpg_backend.author.gateway import AuthorGatewayError, AuthorLLMGateway, get_author_llm_gateway
from rpg_backend.author.storage import SQLiteAuthorJobStorage
from rpg_backend.author.metrics import (
    estimate_token_cost,
    summarize_cache_metrics,
)
from rpg_backend.author.preview import (
    build_author_preview_from_state,
    build_author_story_summary,
)
from rpg_backend.author.progress import PUBLIC_STAGE_BY_NODE, PUBLIC_STAGE_FLOW, STAGE_INDEX_BY_NODE
from rpg_backend.author.workflow import build_author_graph
from rpg_backend.benchmark.contracts import (
    BenchmarkAuthorJobDiagnosticsResponse,
    BenchmarkAuthorJobEvent,
    BenchmarkStageTiming,
)
from rpg_backend.config import Settings, get_settings


@dataclass
class _AuthorJobRecord:
    job_id: str
    owner_user_id: str
    prompt_seed: str
    preview: AuthorPreviewResponse
    status: str
    progress: AuthorJobProgress
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    cache_metrics: AuthorCacheMetrics | None = None
    llm_call_trace: list[dict[str, Any]] = field(default_factory=list)
    quality_trace: list[dict[str, Any]] = field(default_factory=list)
    source_summary: dict[str, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    condition: threading.Condition = field(default_factory=threading.Condition)
    bundle: Any = None
    summary: Any = None
    error: dict[str, str] | None = None


@dataclass(frozen=True)
class AuthorJobPublishSource:
    source_job_id: str
    owner_user_id: str
    prompt_seed: str
    preview: AuthorPreviewResponse
    summary: Any
    bundle: Any


class AuthorJobService:
    def __init__(
        self,
        *,
        storage: SQLiteAuthorJobStorage | None = None,
        settings: Settings | None = None,
        gateway_factory: Callable[[], AuthorLLMGateway] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._storage = storage or SQLiteAuthorJobStorage(
            self._settings.runtime_state_db_path
            if settings is not None
            else f"{tempfile.gettempdir()}/rpg_demo_author_jobs_{uuid4()}.sqlite3"
        )
        self._checkpointer = get_author_checkpointer(db_path=self._storage.db_path)
        self._gateway_factory = gateway_factory or get_author_llm_gateway
        self._lock = threading.Lock()
        self._jobs: dict[str, _AuthorJobRecord] = {}
        self._conditions: dict[str, threading.Condition] = {}
        self._reconcile_interrupted_jobs()

    @staticmethod
    def _progress_for_stage(stage: str) -> AuthorJobProgress:
        public_stage_to_index = {
            public_stage: index + 1
            for index, (_node_name, public_stage) in enumerate(PUBLIC_STAGE_FLOW)
        }
        stage_index = public_stage_to_index.get(stage, 1)
        return AuthorJobProgress(
            stage=stage,
            stage_index=stage_index,
            stage_total=len(PUBLIC_STAGE_FLOW),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _condition_for(self, job_id: str) -> threading.Condition:
        condition = self._conditions.get(job_id)
        if condition is None:
            condition = threading.Condition()
            self._conditions[job_id] = condition
        return condition

    def _serialize_job_record(self, record: _AuthorJobRecord) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "owner_user_id": record.owner_user_id,
            "prompt_seed": record.prompt_seed,
            "preview": record.preview.model_dump(mode="json"),
            "status": record.status,
            "progress": record.progress.model_dump(mode="json"),
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "finished_at": record.finished_at.isoformat() if record.finished_at is not None else None,
            "cache_metrics": record.cache_metrics.model_dump(mode="json") if record.cache_metrics is not None else None,
            "llm_call_trace": list(record.llm_call_trace),
            "quality_trace": list(record.quality_trace),
            "source_summary": dict(record.source_summary),
            "events": [
                {
                    **event,
                    "emitted_at": event["emitted_at"].isoformat(),
                }
                for event in record.events
            ],
            "bundle": self._dump_value(record.bundle),
            "summary": self._dump_value(record.summary),
            "error": record.error,
        }

    @staticmethod
    def _deserialize_job_record(payload: dict[str, Any]) -> _AuthorJobRecord:
        condition = threading.Condition()
        return _AuthorJobRecord(
            job_id=str(payload["job_id"]),
            owner_user_id=str(payload["owner_user_id"]),
            prompt_seed=str(payload["prompt_seed"]),
            preview=AuthorPreviewResponse.model_validate(payload["preview"]),
            status=str(payload["status"]),
            progress=AuthorJobProgress.model_validate(payload["progress"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            finished_at=datetime.fromisoformat(str(payload["finished_at"])) if payload.get("finished_at") else None,
            cache_metrics=AuthorCacheMetrics.model_validate(payload["cache_metrics"]) if payload.get("cache_metrics") is not None else None,
            llm_call_trace=list(payload.get("llm_call_trace") or []),
            quality_trace=list(payload.get("quality_trace") or []),
            source_summary=dict(payload.get("source_summary") or {}),
            events=[
                {
                    **event,
                    "emitted_at": datetime.fromisoformat(str(event["emitted_at"])),
                }
                for event in (payload.get("events") or [])
            ],
            condition=condition,
            bundle=DesignBundle.model_validate(payload["bundle"]) if payload.get("bundle") is not None else None,
            summary=AuthorStorySummary.model_validate(payload["summary"]) if payload.get("summary") is not None else None,
            error=payload.get("error"),
        )

    @staticmethod
    def _ensure_owner_access(owner_user_id: str, actor_user_id: str, *, resource: str, resource_id: str) -> None:
        if owner_user_id == actor_user_id:
            return
        raise AuthorGatewayError(
            code=f"{resource}_not_found",
            message=f"{resource} '{resource_id}' was not found",
            status_code=404,
        )

    def create_preview(
        self,
        request: AuthorPreviewRequest | AuthorJobCreateRequest,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorPreviewResponse:
        resolved_actor_user_id = actor_user_id or self._settings.default_actor_id
        return self._run_preview_workflow(request.prompt_seed, actor_user_id=resolved_actor_user_id)

    def _get_record(self, job_id: str) -> _AuthorJobRecord:
        cached = self._jobs.get(job_id)
        if cached is not None:
            cached.condition = self._condition_for(job_id)
            return cached
        payload = self._storage.get_job(job_id)
        if payload is None:
            raise AuthorGatewayError(
                code="author_job_not_found",
                message=f"author job '{job_id}' was not found",
                status_code=404,
            )
        record = self._deserialize_job_record(payload)
        record.condition = self._condition_for(job_id)
        self._jobs[job_id] = record
        return record

    def _save_record(self, record: _AuthorJobRecord) -> None:
        self._jobs[record.job_id] = record
        self._storage.save_job(self._serialize_job_record(record))

    def _start_background_job(self, job_id: str, *, resume_from_checkpoint: bool) -> None:
        thread = threading.Thread(target=self._run_job, args=(job_id, resume_from_checkpoint), daemon=True)
        thread.start()

    def _run_preview_workflow(self, prompt_seed: str, *, actor_user_id: str) -> AuthorPreviewResponse:
        preview_id = str(uuid4())
        gateway = self._gateway_factory()
        graph = build_author_graph(gateway=gateway, checkpointer=self._checkpointer)
        config = graph_config(run_id=preview_id)
        for _update in graph.stream(
            {
                "run_id": preview_id,
                "raw_brief": prompt_seed,
            },
            config=config,
            stream_mode="updates",
            interrupt_after=["derive_cast_overview"],
            durability="sync",
        ):
            continue
        snapshot = graph.get_state(config)
        preview = build_author_preview_from_state(
            preview_id=preview_id,
            prompt_seed=prompt_seed,
            state=snapshot.values,
        )
        self._storage.save_preview(
            preview.preview_id,
            preview.model_dump(mode="json"),
            owner_user_id=actor_user_id,
            created_at=self._now(),
        )
        return preview

    def _resolve_preview_for_job(self, request: AuthorJobCreateRequest, *, actor_user_id: str) -> AuthorPreviewResponse:
        preview_payload = self._storage.get_preview(request.preview_id) if request.preview_id else None
        if preview_payload is not None:
            self._ensure_owner_access(
                str(preview_payload["owner_user_id"]),
                actor_user_id,
                resource="author_preview",
                resource_id=str(request.preview_id),
            )
        preview = AuthorPreviewResponse.model_validate(preview_payload["preview"]) if preview_payload is not None else None
        if preview is not None:
            checkpoint = self._checkpointer.get_tuple(graph_config(run_id=preview.preview_id))
            if checkpoint is not None:
                return preview
        return self._run_preview_workflow(request.prompt_seed, actor_user_id=actor_user_id)

    def _refresh_preview_from_state(self, record: _AuthorJobRecord, state: dict[str, Any]) -> None:
        record.preview = build_author_preview_from_state(
            preview_id=record.preview.preview_id,
            prompt_seed=record.prompt_seed,
            state=state,
            existing_preview=record.preview,
        )

    def create_job(self, request: AuthorJobCreateRequest, *, actor_user_id: str | None = None) -> AuthorJobStatusResponse:
        resolved_actor_user_id = actor_user_id or self._settings.default_actor_id
        preview = self._resolve_preview_for_job(request, actor_user_id=resolved_actor_user_id)
        job_id = str(uuid4())
        record = _AuthorJobRecord(
            job_id=job_id,
            owner_user_id=resolved_actor_user_id,
            prompt_seed=request.prompt_seed,
            preview=preview,
            status="running",
            progress=self._progress_for_stage(preview.stage),
        )
        with self._lock:
            record.condition = self._condition_for(job_id)
            self._checkpointer.copy_thread(preview.preview_id, job_id)
            self._save_record(record)
        self._emit_event(job_id, "job_created", self._build_status_event_payload(job_id))
        self._start_background_job(job_id, resume_from_checkpoint=True)
        return self.get_job(job_id, actor_user_id=resolved_actor_user_id)

    def get_job(self, job_id: str, *, actor_user_id: str | None = None) -> AuthorJobStatusResponse:
        resolved_actor_user_id = actor_user_id or self._settings.default_actor_id
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
        return AuthorJobStatusResponse(
            job_id=record.job_id,
            status=record.status,  # type: ignore[arg-type]
            prompt_seed=record.prompt_seed,
            preview=record.preview,
            progress=record.progress,
            progress_snapshot=self._progress_snapshot(record),
            cache_metrics=record.cache_metrics,
            error=record.error,
        )

    def get_job_result(self, job_id: str, *, actor_user_id: str | None = None) -> AuthorJobResultResponse:
        resolved_actor_user_id = actor_user_id or self._settings.default_actor_id
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
        return AuthorJobResultResponse(
            job_id=record.job_id,
            status=record.status,  # type: ignore[arg-type]
            summary=record.summary,
            bundle=record.bundle,
            progress_snapshot=self._progress_snapshot(record),
            cache_metrics=record.cache_metrics,
        )

    def get_publishable_job_source(self, job_id: str, *, actor_user_id: str | None = None) -> AuthorJobPublishSource:
        resolved_actor_user_id = actor_user_id or self._settings.default_actor_id
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
            if record.status != "completed" or record.summary is None or record.bundle is None:
                raise AuthorGatewayError(
                    code="author_job_not_publishable",
                    message=f"author job '{job_id}' is not completed and publishable",
                    status_code=409,
                )
            return AuthorJobPublishSource(
                source_job_id=record.job_id,
                owner_user_id=record.owner_user_id,
                prompt_seed=record.prompt_seed,
                preview=record.preview,
                summary=record.summary,
                bundle=record.bundle,
            )

    def get_job_diagnostics(self, job_id: str, *, actor_user_id: str | None = None) -> BenchmarkAuthorJobDiagnosticsResponse:
        resolved_actor_user_id = actor_user_id or self._settings.default_actor_id
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
            token_usage = record.cache_metrics or summarize_cache_metrics(record.llm_call_trace)
        return BenchmarkAuthorJobDiagnosticsResponse(
            job_id=record.job_id,
            status=record.status,  # type: ignore[arg-type]
            prompt_seed=record.prompt_seed,
            created_at=record.created_at,
            updated_at=record.updated_at,
            finished_at=record.finished_at,
            summary=record.summary,
            error=record.error,
            cache_metrics=record.cache_metrics,
            token_cost_estimate=estimate_token_cost(token_usage),
            llm_call_trace=list(record.llm_call_trace),
            quality_trace=list(record.quality_trace),
            source_summary=dict(record.source_summary),
            stage_timings=self._build_stage_timings(record.events),
            events=self._build_diagnostic_events(record.events),
        )

    def stream_job_events(
        self,
        job_id: str,
        *,
        actor_user_id: str | None = None,
        last_event_id: int | None = None,
        heartbeat_seconds: float = 15.0,
    ):
        resolved_actor_user_id = actor_user_id or self._settings.default_actor_id
        cursor = last_event_id or 0
        while True:
            with self._lock:
                record = self._get_record(job_id)
                self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
                pending = [event for event in record.events if event["id"] > cursor]
                terminal = record.status in {"completed", "failed"}
                condition = self._condition_for(job_id)
            if pending:
                for event in pending:
                    cursor = event["id"]
                    yield self._encode_sse_event(event)
                if terminal:
                    break
                continue
            if terminal:
                break
            with condition:
                notified = condition.wait(timeout=heartbeat_seconds)
            if not notified:
                yield ": keep-alive\n\n"

    def _run_job(self, job_id: str, resume_from_checkpoint: bool = False) -> None:
        with self._lock:
            record = self._get_record(job_id)
            prior_llm_call_trace = list(record.llm_call_trace)
            checkpoint_exists = self._checkpointer.get_tuple(graph_config(run_id=job_id)) is not None
            record.status = "running"
            if not checkpoint_exists:
                record.progress = AuthorJobProgress(
                    stage="running",
                    stage_index=1,
                    stage_total=len(PUBLIC_STAGE_FLOW),
                )
            record.error = None
            if not prior_llm_call_trace:
                record.cache_metrics = summarize_cache_metrics(None)
            record.updated_at = self._now()
            self._save_record(record)
        self._emit_event(
            job_id,
            "job_resumed" if resume_from_checkpoint else "job_started",
            self._build_status_event_payload(job_id),
        )
        gateway = None
        try:
            gateway = self._gateway_factory()
            graph = build_author_graph(gateway=gateway, checkpointer=self._checkpointer)
            config = graph_config(run_id=job_id)
            stream_input = None if checkpoint_exists else {"run_id": job_id, "raw_brief": record.prompt_seed}
            for update in graph.stream(
                stream_input,
                config=config,
                stream_mode="updates",
            ):
                node_name = next(iter(update.keys()))
                if node_name not in PUBLIC_STAGE_BY_NODE:
                    continue
                public_stage = PUBLIC_STAGE_BY_NODE[node_name]
                stage_index = STAGE_INDEX_BY_NODE[node_name]
                snapshot = graph.get_state(config)
                state = snapshot.values
                with self._lock:
                    current = self._get_record(job_id)
                    current.progress = AuthorJobProgress(
                        stage=public_stage,
                        stage_index=stage_index,
                        stage_total=len(PUBLIC_STAGE_FLOW),
                    )
                    self._refresh_preview_from_state(current, state)
                    current.llm_call_trace = [*prior_llm_call_trace, *list(gateway.call_trace)]
                    current.cache_metrics = summarize_cache_metrics(current.llm_call_trace)
                    current.updated_at = self._now()
                    self._save_record(current)
                self._emit_event(job_id, "stage_changed", self._build_status_event_payload(job_id))
            snapshot = graph.get_state(config)
            state = snapshot.values
            bundle = state["design_bundle"]
            summary = build_author_story_summary(
                bundle,
                primary_theme=state.get("primary_theme") or record.preview.theme.primary_theme,
            )
            cache_metrics = summarize_cache_metrics(
                list(gateway.call_trace) if hasattr(gateway, "call_trace") else state.get("llm_call_trace")
            )
            with self._lock:
                current = self._get_record(job_id)
                current.status = "completed"
                current.progress = AuthorJobProgress(
                    stage="completed",
                    stage_index=len(PUBLIC_STAGE_FLOW),
                    stage_total=len(PUBLIC_STAGE_FLOW),
                )
                self._refresh_preview_from_state(current, state)
                current.bundle = bundle
                current.summary = summary
                current.llm_call_trace = [*prior_llm_call_trace, *list(gateway.call_trace)]
                current.quality_trace = list(state.get("quality_trace") or [])
                current.source_summary = {
                    "story_frame_source": str(state.get("story_frame_source") or "unknown"),
                    "beat_plan_source": str(state.get("beat_plan_source") or "unknown"),
                    "route_affordance_source": str(state.get("route_affordance_source") or "unknown"),
                    "ending_source": str(state.get("ending_source") or "unknown"),
                    "gameplay_semantics_source": str(state.get("gameplay_semantics_source") or "unknown"),
                }
                current.cache_metrics = cache_metrics
                current.updated_at = self._now()
                current.finished_at = self._now()
                self._save_record(current)
            self._emit_event(job_id, "job_completed", self._build_result_event_payload(job_id))
        except Exception as exc:  # noqa: BLE001
            llm_call_trace = [
                *prior_llm_call_trace,
                *(list(gateway.call_trace) if gateway is not None else []),
            ]
            cache_metrics = summarize_cache_metrics(llm_call_trace)
            with self._lock:
                current = self._get_record(job_id)
                current.status = "failed"
                current.error = {
                    "code": "author_job_failed",
                    "message": str(exc),
                }
                current.progress = AuthorJobProgress(
                    stage="failed",
                    stage_index=len(PUBLIC_STAGE_FLOW),
                    stage_total=len(PUBLIC_STAGE_FLOW),
                )
                current.llm_call_trace = llm_call_trace
                current.cache_metrics = cache_metrics
                current.updated_at = self._now()
                current.finished_at = self._now()
                self._save_record(current)
            self._emit_event(job_id, "job_failed", self._build_status_event_payload(job_id))

    @staticmethod
    def _encode_sse_event(event: dict[str, Any]) -> str:
        return (
            f"id: {event['id']}\n"
            f"event: {event['event']}\n"
            f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        )

    @staticmethod
    def _dump_value(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return value

    def _build_token_snapshot_payload(self, record: _AuthorJobRecord) -> dict[str, Any]:
        token_usage = record.cache_metrics or summarize_cache_metrics(record.llm_call_trace)
        token_cost_estimate = estimate_token_cost(token_usage)
        return {
            "token_usage": token_usage.model_dump(mode="json"),
            "token_cost_estimate": token_cost_estimate.model_dump(mode="json") if token_cost_estimate else None,
        }

    def _progress_snapshot(self, record: _AuthorJobRecord):
        token_usage = record.cache_metrics or summarize_cache_metrics(record.llm_call_trace)
        return build_progress_snapshot(
            preview=record.preview,
            progress=record.progress,
            token_usage=token_usage,
            token_cost_estimate=estimate_token_cost(token_usage),
        )

    def _build_status_event_payload(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._get_record(job_id)
            payload = {
                "job_id": record.job_id,
                "status": record.status,
                "prompt_seed": record.prompt_seed,
                "preview": record.preview.model_dump(mode="json"),
                "progress": record.progress.model_dump(mode="json"),
                "cache_metrics": record.cache_metrics.model_dump(mode="json") if record.cache_metrics else None,
                "error": record.error,
                "progress_snapshot": self._progress_snapshot(record).model_dump(mode="json"),
            }
            payload.update(self._build_token_snapshot_payload(record))
            return payload

    def _build_result_event_payload(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._get_record(job_id)
            payload = {
                "job_id": record.job_id,
                "status": record.status,
                "progress": record.progress.model_dump(mode="json"),
                "summary": self._dump_value(record.summary),
                "bundle": self._dump_value(record.bundle),
                "cache_metrics": record.cache_metrics.model_dump(mode="json") if record.cache_metrics else None,
                "progress_snapshot": self._progress_snapshot(record).model_dump(mode="json"),
            }
            payload.update(self._build_token_snapshot_payload(record))
            return payload

    def _emit_event(self, job_id: str, event_name: str, payload: dict[str, Any]) -> None:
        with self._lock:
            record = self._get_record(job_id)
            event_id = len(record.events) + 1
            emitted_at = self._now()
            event = {
                "id": event_id,
                "event": event_name,
                "emitted_at": emitted_at,
                "data": payload,
            }
            record.events.append(event)
            record.updated_at = emitted_at
            self._save_record(record)
            condition = self._condition_for(job_id)
        with condition:
            condition.notify_all()

    def _reconcile_interrupted_jobs(self) -> None:
        for payload in self._storage.list_jobs():
            if payload.get("status") not in {"queued", "running"}:
                continue
            record = self._deserialize_job_record(payload)
            with self._lock:
                record.condition = self._condition_for(record.job_id)
                self._save_record(record)
            self._start_background_job(record.job_id, resume_from_checkpoint=True)

    @staticmethod
    def _build_diagnostic_events(events: list[dict[str, Any]]) -> list[BenchmarkAuthorJobEvent]:
        payloads: list[BenchmarkAuthorJobEvent] = []
        for event in events:
            progress = dict(event.get("data", {}).get("progress") or {})
            payloads.append(
                BenchmarkAuthorJobEvent(
                    id=int(event["id"]),
                    event=str(event["event"]),
                    emitted_at=event["emitted_at"],
                    status=event.get("data", {}).get("status"),
                    stage=progress.get("stage"),
                    stage_index=progress.get("stage_index"),
                    stage_total=progress.get("stage_total"),
                )
            )
        return payloads

    @staticmethod
    def _build_stage_timings(events: list[dict[str, Any]]) -> list[BenchmarkStageTiming]:
        stage_events: list[tuple[str, datetime]] = []
        for event in events:
            progress = dict(event.get("data", {}).get("progress") or {})
            stage = progress.get("stage")
            emitted_at = event.get("emitted_at")
            if not isinstance(stage, str) or not isinstance(emitted_at, datetime):
                continue
            if stage_events and stage_events[-1][0] == stage:
                continue
            stage_events.append((stage, emitted_at))
        timings: list[BenchmarkStageTiming] = []
        for index, (stage, started_at) in enumerate(stage_events):
            ended_at = stage_events[index + 1][1] if index + 1 < len(stage_events) else None
            elapsed_ms = None
            if ended_at is not None:
                elapsed_ms = max(int((ended_at - started_at).total_seconds() * 1000), 0)
            timings.append(
                BenchmarkStageTiming(
                    stage=stage,
                    started_at=started_at,
                    ended_at=ended_at,
                    elapsed_ms=elapsed_ms,
                )
            )
        return timings

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
    AuthorCopilotApplyResponse,
    AuthorCopilotMessage,
    AuthorCopilotProposalRequest,
    AuthorCopilotPreviewResponse,
    AuthorCopilotProposalResponse,
    AuthorCopilotSessionCreateRequest,
    AuthorCopilotSessionMessageRequest,
    AuthorCopilotSessionResponse,
    AuthorCopilotUndoResponse,
    AuthorCopilotWorkspaceSnapshot,
    AuthorCastPortraitPlanRequest,
    AuthorCastPortraitPlanResponse,
    AuthorJobCreateRequest,
    AuthorEditorBeatView,
    AuthorEditorCastEntry,
    AuthorEditorNpcRef,
    AuthorEditorPlayProfileView,
    AuthorEditorRulePackView,
    AuthorEditorStateResponse,
    AuthorEditorStoryFrameView,
    AuthorJobProgress,
    AuthorJobResultResponse,
    AuthorStorySummary,
    AuthorStorySparkRequest,
    AuthorStorySparkResponse,
    AuthorJobStatusResponse,
    AuthorPreviewRequest,
    AuthorPreviewResponse,
    DesignBundle,
    StoryGenerationControls,
)
from rpg_backend.author.copilot import (
    apply_copilot_operations,
    build_copilot_locked_boundaries,
    build_copilot_proposal,
    build_copilot_session_reply,
    build_copilot_workspace_snapshot_from_state,
    build_copilot_workspace_view,
    build_initial_rewrite_brief,
    repair_copilot_candidate,
    validate_copilot_candidate,
)
from rpg_backend.author.display import build_progress_snapshot
from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.author.portrait_tasks import build_author_cast_portrait_plan
from rpg_backend.author.planning import (
    coerce_generation_controls,
    generation_controls_equal,
    generation_controls_from_request,
)
from rpg_backend.author.storage import SQLiteAuthorJobStorage
from rpg_backend.llm_gateway import CapabilityGatewayCore, build_gateway_core
from rpg_backend.author.metrics import (
    estimate_token_cost,
    summarize_cache_metrics,
)
from rpg_backend.author.preview import (
    build_author_preview_from_bundle,
    build_author_preview_from_state,
    build_author_story_summary,
)
from rpg_backend.author.sparks import build_story_spark
from rpg_backend.author.progress import (
    AUTHOR_LOADING_NODE_FLOW,
    AUTHOR_LOADING_STAGE_INDEX_BY_NODE,
    PUBLIC_STAGE_BY_NODE,
    PUBLIC_STAGE_FLOW,
)
from rpg_backend.author.workflow import _annotate_author_llm_trace_with_context_locks, build_author_graph
from rpg_backend.benchmark.contracts import (
    BenchmarkAuthorJobDiagnosticsResponse,
    BenchmarkAuthorJobEvent,
    BenchmarkStageTiming,
)
from rpg_backend.content_language import localized_text
from rpg_backend.config import Settings, get_settings
from rpg_backend.library.service import StoryLibraryService, get_story_library_service
from rpg_backend.play.compiler import compile_play_plan
from rpg_backend.product_copy import closeout_profile_label, runtime_profile_label

_PREVIEW_NODE_ORDER: tuple[str, ...] = (
    "focus_brief",
    "plan_brief_theme",
    "plan_generation_intent",
    "generate_story_frame",
    "plan_story_theme",
    "derive_cast_overview",
)

_PREVIEW_DEFAULT_CAPABILITY_BY_NODE: dict[str, str] = {
    "generate_story_frame": "author.story_frame_scaffold",
}

_PREVIEW_DEFAULT_OPERATION_BY_NODE: dict[str, str] = {
    "generate_story_frame": "story_frame_semantics",
}

_CONTEXT_LOCK_REASON_CODES = {
    "context_hash_mismatch",
    "snapshot_invariant_violation",
    "out_of_scope_reference",
    "binding_scaffold_drift",
    "beat_runtime_shard_fallback",
}


def _author_context_lock_diagnostics(
    *,
    llm_call_trace: list[dict[str, Any]],
    quality_trace: list[dict[str, Any]],
    bundle: Any,
) -> dict[str, Any]:
    context_lock_violation_distribution: dict[str, int] = {}
    beat_runtime_shard_drift_distribution: dict[str, int] = {}
    snapshot_stage_distribution: dict[str, int] = {}
    drift_repair_entry_count = 0
    beat_runtime_shard_count = len(list(getattr(bundle, "beat_runtime_shards", []) or [])) if bundle is not None else 0
    beat_runtime_shard_fallback_count = sum(
        1
        for item in list(getattr(bundle, "beat_runtime_shards", []) or [])
        if getattr(item, "fallback_reason", None)
    ) if bundle is not None else 0
    beat_runtime_shard_elapsed_ms = 0
    for item in llm_call_trace:
        snapshot_stage = str(item.get("snapshot_stage") or "").strip()
        if snapshot_stage:
            snapshot_stage_distribution[snapshot_stage] = snapshot_stage_distribution.get(snapshot_stage, 0) + 1
    for item in quality_trace:
        reasons = [str(reason) for reason in list(item.get("reasons") or [])]
        if item.get("stage") == "beat_runtime_shard":
            beat_runtime_shard_elapsed_ms += int(item.get("elapsed_ms") or 0)
        matched_reasons = [reason for reason in reasons if reason in _CONTEXT_LOCK_REASON_CODES]
        if matched_reasons:
            drift_repair_entry_count += 1
        for reason in matched_reasons:
            context_lock_violation_distribution[reason] = context_lock_violation_distribution.get(reason, 0) + 1
            if item.get("stage") == "beat_runtime_shard":
                beat_runtime_shard_drift_distribution[reason] = beat_runtime_shard_drift_distribution.get(reason, 0) + 1
    return {
        "context_lock_violation_distribution": context_lock_violation_distribution,
        "snapshot_stage_distribution": snapshot_stage_distribution,
        "drift_repair_entry_count": drift_repair_entry_count,
        "beat_runtime_shard_count": beat_runtime_shard_count,
        "beat_runtime_shard_fallback_count": beat_runtime_shard_fallback_count,
        "beat_runtime_shard_elapsed_ms": beat_runtime_shard_elapsed_ms,
        "beat_runtime_shard_drift_distribution": beat_runtime_shard_drift_distribution,
    }


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
    roster_catalog_version: str | None = None
    roster_enabled: bool = False
    roster_retrieval_trace: list[dict[str, Any]] = field(default_factory=list)
    copilot_workspace_snapshot: AuthorCopilotWorkspaceSnapshot | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    condition: threading.Condition = field(default_factory=threading.Condition)
    bundle: Any = None
    summary: Any = None
    error: dict[str, str] | None = None
    running_node: str | None = None
    running_substage: str | None = None
    running_slot_index: int | None = None
    running_slot_total: int | None = None
    running_slot_label: str | None = None
    running_capability: str | None = None
    running_started_at: datetime | None = None


@dataclass(frozen=True)
class AuthorJobPublishSource:
    source_job_id: str
    owner_user_id: str
    prompt_seed: str
    preview: AuthorPreviewResponse
    summary: Any
    bundle: Any


class AuthorJobService:
    _MAX_CACHED_TERMINAL_JOBS = 64

    def __init__(
        self,
        *,
        storage: SQLiteAuthorJobStorage | None = None,
        settings: Settings | None = None,
        gateway_factory: Callable[[Settings | None], CapabilityGatewayCore] | None = None,
        story_library_service: StoryLibraryService | None = None,
        allow_default_actor_fallback: bool = True,
    ) -> None:
        self._settings = settings or get_settings()
        self._storage = storage or SQLiteAuthorJobStorage(
            self._settings.runtime_state_db_path
            if settings is not None
            else f"{tempfile.gettempdir()}/rpg_demo_author_jobs_{uuid4()}.sqlite3"
        )
        self._checkpointer = get_author_checkpointer(db_path=self._storage.db_path)
        self._gateway_factory = gateway_factory or build_gateway_core
        self._story_library_service = story_library_service or get_story_library_service(self._settings)
        self._allow_default_actor_fallback = allow_default_actor_fallback
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
        stage_index = public_stage_to_index.get(stage, 0 if stage in {"queued", "running"} else 1)
        return AuthorJobProgress(
            stage=stage,
            stage_index=stage_index,
            stage_total=len(PUBLIC_STAGE_FLOW),
        )

    @staticmethod
    def _initial_author_loading_progress() -> AuthorJobProgress:
        return AuthorJobProgress(
            stage=AUTHOR_LOADING_NODE_FLOW[0],
            stage_index=0,
            stage_total=len(AUTHOR_LOADING_NODE_FLOW),
        )

    @staticmethod
    def _resume_checkpoint_progress() -> AuthorJobProgress:
        return AuthorJobProgress(
            stage=AUTHOR_LOADING_NODE_FLOW[0],
            stage_index=1,
            stage_total=len(AUTHOR_LOADING_NODE_FLOW),
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
            "roster_catalog_version": record.roster_catalog_version,
            "roster_enabled": record.roster_enabled,
            "roster_retrieval_trace": list(record.roster_retrieval_trace),
            "copilot_workspace_snapshot": (
                record.copilot_workspace_snapshot.model_dump(mode="json")
                if record.copilot_workspace_snapshot is not None
                else None
            ),
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
            "running_node": record.running_node,
            "running_substage": record.running_substage,
            "running_slot_index": record.running_slot_index,
            "running_slot_total": record.running_slot_total,
            "running_slot_label": record.running_slot_label,
            "running_capability": record.running_capability,
            "running_started_at": record.running_started_at.isoformat() if record.running_started_at is not None else None,
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
            roster_catalog_version=str(payload["roster_catalog_version"]) if payload.get("roster_catalog_version") else None,
            roster_enabled=bool(payload.get("roster_enabled")),
            roster_retrieval_trace=list(payload.get("roster_retrieval_trace") or []),
            copilot_workspace_snapshot=(
                AuthorCopilotWorkspaceSnapshot.model_validate(payload["copilot_workspace_snapshot"])
                if payload.get("copilot_workspace_snapshot") is not None
                else None
            ),
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
            running_node=str(payload["running_node"]) if payload.get("running_node") else None,
            running_substage=str(payload["running_substage"]) if payload.get("running_substage") else None,
            running_slot_index=int(payload["running_slot_index"]) if payload.get("running_slot_index") is not None else None,
            running_slot_total=int(payload["running_slot_total"]) if payload.get("running_slot_total") is not None else None,
            running_slot_label=str(payload["running_slot_label"]) if payload.get("running_slot_label") else None,
            running_capability=str(payload["running_capability"]) if payload.get("running_capability") else None,
            running_started_at=datetime.fromisoformat(str(payload["running_started_at"])) if payload.get("running_started_at") else None,
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

    def _resolve_actor_user_id(self, actor_user_id: str | None) -> str:
        if actor_user_id is not None:
            return actor_user_id
        if self._allow_default_actor_fallback:
            return self._settings.default_actor_id
        raise AuthorGatewayError(
            code="auth_session_required",
            message="Sign in required.",
            status_code=401,
        )

    def create_preview(
        self,
        request: AuthorPreviewRequest | AuthorJobCreateRequest,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorPreviewResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        return self._run_preview_workflow(
            request.prompt_seed,
            actor_user_id=resolved_actor_user_id,
            language=str(getattr(request, "language", "en") or "en"),
            generation_controls=generation_controls_from_request(request),
        )

    def create_story_spark(
        self,
        request: AuthorStorySparkRequest,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorStorySparkResponse:
        self._resolve_actor_user_id(actor_user_id)
        spark_gateway = None
        if self._settings.resolved_author_spark_mode() == "llm_first":
            spark_gateway = self._gateway_factory(self._settings)
        return build_story_spark(
            language=request.language,
            gateway=spark_gateway,
            settings=self._settings,
        )

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
        self._prune_cached_jobs()

    def _prune_cached_jobs(self) -> None:
        terminal_records = [
            (job_id, record)
            for job_id, record in self._jobs.items()
            if record.status in {"completed", "failed"}
        ]
        if len(terminal_records) <= self._MAX_CACHED_TERMINAL_JOBS:
            return
        terminal_records.sort(
            key=lambda item: (
                item[1].finished_at or item[1].updated_at,
                item[0],
            )
        )
        for job_id, _record in terminal_records[: len(terminal_records) - self._MAX_CACHED_TERMINAL_JOBS]:
            self._jobs.pop(job_id, None)
            self._conditions.pop(job_id, None)

    def _save_copilot_proposal(
        self,
        *,
        owner_user_id: str,
        proposal: AuthorCopilotProposalResponse,
        variant_fingerprint: str | None = None,
        prior_preview: AuthorPreviewResponse | None = None,
        prior_summary: AuthorStorySummary | None = None,
        prior_bundle: DesignBundle | None = None,
        prior_workspace_snapshot: AuthorCopilotWorkspaceSnapshot | None = None,
        prior_record_revision: str | None = None,
    ) -> None:
        stored = self._storage.get_copilot_proposal(proposal.proposal_id)
        resolved_variant_fingerprint = variant_fingerprint or (
            stored["variant_fingerprint"] if stored is not None else proposal.proposal_id
        )
        resolved_prior_preview = prior_preview if prior_preview is not None else (stored["prior_preview"] if stored is not None else None)
        resolved_prior_summary = prior_summary if prior_summary is not None else (stored["prior_summary"] if stored is not None else None)
        resolved_prior_bundle = prior_bundle if prior_bundle is not None else (stored["prior_bundle"] if stored is not None else None)
        resolved_prior_workspace_snapshot = (
            prior_workspace_snapshot
            if prior_workspace_snapshot is not None
            else (stored["prior_workspace_snapshot"] if stored is not None else None)
        )
        resolved_prior_record_revision = (
            prior_record_revision
            if prior_record_revision is not None
            else (stored["prior_record_revision"] if stored is not None else None)
        )
        self._storage.save_copilot_proposal(
            {
                "proposal_id": proposal.proposal_id,
                "proposal_group_id": proposal.proposal_group_id,
                "session_id": proposal.session_id,
                "job_id": proposal.job_id,
                "owner_user_id": owner_user_id,
                "status": proposal.status,
                "base_revision": proposal.base_revision,
                "instruction": proposal.instruction,
                "variant_index": proposal.variant_index,
                "variant_label": proposal.variant_label,
                "supersedes_proposal_id": proposal.supersedes_proposal_id,
                "variant_fingerprint": resolved_variant_fingerprint,
                "created_at": proposal.created_at.isoformat(),
                "updated_at": proposal.updated_at.isoformat(),
                "applied_at": proposal.applied_at.isoformat() if proposal.applied_at is not None else None,
                "prior_preview": resolved_prior_preview,
                "prior_summary": resolved_prior_summary,
                "prior_bundle": resolved_prior_bundle,
                "prior_workspace_snapshot": resolved_prior_workspace_snapshot,
                "prior_record_revision": resolved_prior_record_revision,
                "proposal": proposal.model_dump(mode="json"),
            }
        )

    def _save_copilot_session(
        self,
        *,
        owner_user_id: str,
        session: AuthorCopilotSessionResponse,
    ) -> None:
        self._storage.save_copilot_session(
            {
                "session_id": session.session_id,
                "job_id": session.job_id,
                "owner_user_id": owner_user_id,
                "hidden": session.hidden,
                "status": session.status,
                "base_revision": session.base_revision,
                "last_proposal_id": session.last_proposal_id,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "closed_at": session.closed_at.isoformat() if session.closed_at is not None else None,
                "session": session.model_dump(mode="json"),
            }
        )

    def _get_copilot_session_record(self, session_id: str) -> dict[str, Any]:
        payload = self._storage.get_copilot_session(session_id)
        if payload is None:
            raise AuthorGatewayError(
                code="author_copilot_session_not_found",
                message=f"copilot session '{session_id}' was not found",
                status_code=404,
            )
        return payload

    @staticmethod
    def _session_model(payload: dict[str, Any]) -> AuthorCopilotSessionResponse:
        return AuthorCopilotSessionResponse.model_validate(payload["session"])

    @staticmethod
    def _proposal_model(payload: dict[str, Any]) -> AuthorCopilotProposalResponse:
        return AuthorCopilotProposalResponse.model_validate(payload["proposal"])

    def _active_copilot_session_id_for_job(self, record: _AuthorJobRecord) -> str | None:
        payloads = self._storage.list_copilot_sessions_for_job(record.job_id)
        for payload in payloads:
            if payload.get("hidden"):
                continue
            if str(payload.get("status") or "") == "closed":
                continue
            return str(payload["session_id"])
        return None

    def _latest_applied_proposal_for_session(
        self,
        *,
        job_id: str,
        session_id: str,
    ) -> tuple[dict[str, Any], AuthorCopilotProposalResponse] | None:
        for payload in reversed(self._storage.list_copilot_proposals_for_group(job_id, session_id)):
            proposal = self._proposal_model(payload)
            if proposal.status == "applied":
                return payload, proposal
        return None

    def _undoable_copilot_state_for_record(
        self,
        record: _AuthorJobRecord,
    ) -> tuple[str, dict[str, Any], AuthorCopilotProposalResponse] | None:
        active_session_id = self._active_copilot_session_id_for_job(record)
        if not active_session_id:
            return None
        latest_applied = self._latest_applied_proposal_for_session(job_id=record.job_id, session_id=active_session_id)
        if latest_applied is None:
            return None
        proposal_payload, proposal = latest_applied
        if proposal.applied_at is None or proposal.applied_at.isoformat() != record.updated_at.isoformat():
            return None
        if not all(
            proposal_payload.get(key) is not None
            for key in ("prior_preview", "prior_summary", "prior_bundle", "prior_workspace_snapshot")
        ):
            return None
        return active_session_id, proposal_payload, proposal

    @staticmethod
    def _ensure_copilot_proposal_active(
        proposal: AuthorCopilotProposalResponse,
        *,
        action: str,
    ) -> None:
        if proposal.status == "superseded":
            raise AuthorGatewayError(
                code="author_copilot_proposal_superseded",
                message=f"copilot proposal cannot be used for {action} because a newer variant replaced it",
                status_code=409,
            )
        if proposal.status == "applied":
            raise AuthorGatewayError(
                code="author_copilot_proposal_already_applied",
                message=f"copilot proposal cannot be used for {action} because it was already applied",
                status_code=409,
            )

    def _is_job_publishable(self, record: _AuthorJobRecord) -> bool:
        if record.status != "completed" or record.summary is None or record.bundle is None:
            return False
        if self._story_library_service.has_story_for_source_job(record.job_id):
            return False
        return True

    def _recover_workspace_snapshot_from_checkpoint(
        self,
        *,
        job_id: str,
        bundle: DesignBundle | None,
    ) -> AuthorCopilotWorkspaceSnapshot | None:
        if bundle is None:
            return None
        graph = build_author_graph(gateway=build_gateway_core(self._settings), checkpointer=self._checkpointer)
        snapshot = graph.get_state(graph_config(run_id=job_id))
        state = getattr(snapshot, "values", None) if snapshot is not None else None
        if not isinstance(state, dict) or not state:
            return None
        required_keys = {
            "focused_brief",
            "story_frame_draft",
            "cast_overview_draft",
            "beat_plan_draft",
        }
        if not required_keys.issubset(set(state.keys())):
            return None
        return build_copilot_workspace_snapshot_from_state(state=state, bundle=bundle)

    def _resolve_copilot_workspace_snapshot(self, record: _AuthorJobRecord) -> AuthorCopilotWorkspaceSnapshot:
        if record.copilot_workspace_snapshot is not None:
            return record.copilot_workspace_snapshot
        recovered = self._recover_workspace_snapshot_from_checkpoint(job_id=record.job_id, bundle=record.bundle)
        if recovered is not None:
            record.copilot_workspace_snapshot = recovered
            self._save_record(record)
            return recovered
        raise AuthorGatewayError(
            code="author_copilot_workspace_unavailable",
            message="copilot workspace is unavailable for this draft revision",
            status_code=409,
        )

    def _start_background_job(self, job_id: str, *, resume_from_checkpoint: bool) -> None:
        thread = threading.Thread(target=self._run_job, args=(job_id, resume_from_checkpoint), daemon=True)
        thread.start()

    @staticmethod
    def _next_preview_node_after(last_completed_node: str | None) -> str | None:
        if last_completed_node is None:
            return _PREVIEW_NODE_ORDER[0]
        try:
            index = _PREVIEW_NODE_ORDER.index(last_completed_node)
        except ValueError:
            return None
        next_index = min(index + 1, len(_PREVIEW_NODE_ORDER) - 1)
        return _PREVIEW_NODE_ORDER[next_index]

    def _build_preview_failure_message(
        self,
        *,
        exc: AuthorGatewayError,
        gateway: CapabilityGatewayCore,
        last_completed_node: str | None,
    ) -> str:
        failed_node = self._next_preview_node_after(last_completed_node)
        failed_trace = next(
            (
                item
                for item in reversed(list(getattr(gateway, "call_trace", []) or []))
                if item.get("error_code")
            ),
            None,
        )
        capability = (
            str(failed_trace.get("capability"))
            if failed_trace and failed_trace.get("capability")
            else _PREVIEW_DEFAULT_CAPABILITY_BY_NODE.get(str(failed_node))
        )
        operation = (
            str(failed_trace.get("operation_name") or failed_trace.get("operation"))
            if failed_trace and (failed_trace.get("operation_name") or failed_trace.get("operation"))
            else _PREVIEW_DEFAULT_OPERATION_BY_NODE.get(str(failed_node))
        )
        public_stage = PUBLIC_STAGE_BY_NODE.get(str(failed_node)) if failed_node else None
        timeout_seconds = failed_trace.get("timeout_seconds") if failed_trace else None
        elapsed_ms = failed_trace.get("elapsed_ms") if failed_trace else None
        transport = failed_trace.get("transport_style") or failed_trace.get("transport") if failed_trace else None
        model = failed_trace.get("model") if failed_trace else None
        input_characters = failed_trace.get("input_characters") if failed_trace else None
        system_prompt_characters = failed_trace.get("system_prompt_characters") if failed_trace else None
        sdk_retries_disabled = failed_trace.get("sdk_retries_disabled") if failed_trace else None
        parts = [f"preview failed during {failed_node or 'unknown_stage'}"]
        if public_stage:
            parts.append(f"stage={public_stage}")
        if capability:
            parts.append(f"capability={capability}")
        if operation:
            parts.append(f"operation={operation}")
        if transport:
            parts.append(f"transport={transport}")
        if model:
            parts.append(f"model={model}")
        if timeout_seconds is not None:
            parts.append(f"timeout_seconds={timeout_seconds}")
        if elapsed_ms is not None:
            parts.append(f"elapsed_ms={elapsed_ms}")
        if input_characters is not None:
            parts.append(f"input_characters={input_characters}")
        if system_prompt_characters is not None:
            parts.append(f"system_prompt_characters={system_prompt_characters}")
        if sdk_retries_disabled is not None:
            parts.append(f"sdk_retries_disabled={sdk_retries_disabled}")
        return f"{', '.join(parts)}: {exc.message}"

    def _run_preview_workflow(
        self,
        prompt_seed: str,
        *,
        actor_user_id: str,
        language: str,
        generation_controls,
    ) -> AuthorPreviewResponse:
        preview_id = str(uuid4())
        gateway = self._gateway_factory(self._settings)
        graph = build_author_graph(gateway=gateway, checkpointer=self._checkpointer)
        config = graph_config(run_id=preview_id)
        last_completed_node: str | None = None
        try:
            for update in graph.stream(
                {
                    "run_id": preview_id,
                    "raw_brief": prompt_seed,
                    "language": language,
                    "generation_controls": generation_controls,
                    "preview_mode": True,
                },
                config=config,
                stream_mode="updates",
                interrupt_after=["derive_cast_overview"],
                durability="sync",
            ):
                node_name = next(iter(update.keys()), None)
                if node_name is not None:
                    last_completed_node = str(node_name)
        except AuthorGatewayError as exc:
            raise AuthorGatewayError(
                code=exc.code,
                message=self._build_preview_failure_message(
                    exc=exc,
                    gateway=gateway,
                    last_completed_node=last_completed_node,
                ),
                status_code=exc.status_code,
            ) from exc
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
        requested_language = str(getattr(request, "language", "en") or "en")
        requested_controls = generation_controls_from_request(request)
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
            if preview.language != requested_language:
                preview = None
            else:
                requested_control_fields = {
                    "target_duration_minutes",
                    "tone_direction",
                    "tone_focus",
                    "prose_style",
                } & set(getattr(request, "model_fields_set", set()))
                if requested_control_fields and not generation_controls_equal(
                    requested_controls,
                    preview.generation_controls,
                ):
                    raise AuthorGatewayError(
                        code="author_preview_generation_controls_mismatch",
                        message="preview generation controls do not match the requested author job controls",
                        status_code=409,
                    )
                checkpoint = self._checkpointer.get_tuple(graph_config(run_id=preview.preview_id))
                if checkpoint is not None:
                    return preview
                requested_controls = preview.generation_controls or requested_controls
        return self._run_preview_workflow(
            request.prompt_seed,
            actor_user_id=actor_user_id,
            language=requested_language,
            generation_controls=requested_controls,
        )

    def _refresh_preview_from_state(self, record: _AuthorJobRecord, state: dict[str, Any]) -> None:
        record.preview = build_author_preview_from_state(
            preview_id=record.preview.preview_id,
            prompt_seed=record.prompt_seed,
            state=state,
            existing_preview=record.preview,
        )

    @staticmethod
    def _generation_controls_from_preview(preview: AuthorPreviewResponse) -> StoryGenerationControls | None:
        direct = coerce_generation_controls(preview.generation_controls)
        if direct is not None:
            return direct
        target_duration_minutes = None
        if preview.story_flow_plan is not None:
            target_duration_minutes = preview.story_flow_plan.target_duration_minutes
        elif preview.structure.target_duration_minutes is not None:
            target_duration_minutes = preview.structure.target_duration_minutes
        tone_plan = preview.resolved_tone_plan
        if target_duration_minutes is None and tone_plan is None:
            return None
        return StoryGenerationControls(
            target_duration_minutes=target_duration_minutes,
            tone_direction=tone_plan.tone_direction if tone_plan is not None else None,
            tone_focus=tone_plan.tone_focus if tone_plan is not None else None,
            prose_style=tone_plan.prose_style if tone_plan is not None else None,
        )

    @staticmethod
    def _generation_controls_from_checkpoint_state(state: dict[str, Any] | None) -> StoryGenerationControls | None:
        if not isinstance(state, dict):
            return None
        direct = coerce_generation_controls(state.get("generation_controls"))
        if direct is not None:
            return direct
        bundle_payload = state.get("design_bundle")
        if isinstance(bundle_payload, DesignBundle):
            return coerce_generation_controls(bundle_payload.generation_controls)
        if isinstance(bundle_payload, dict):
            return coerce_generation_controls(bundle_payload.get("generation_controls"))
        return None

    def _resolve_resume_generation_controls(
        self,
        *,
        record: _AuthorJobRecord,
        checkpoint_state: dict[str, Any] | None,
    ) -> StoryGenerationControls:
        preview_controls = self._generation_controls_from_preview(record.preview)
        if preview_controls is not None:
            return preview_controls
        checkpoint_controls = self._generation_controls_from_checkpoint_state(checkpoint_state)
        if checkpoint_controls is not None:
            return checkpoint_controls
        if isinstance(record.bundle, DesignBundle):
            bundle_controls = coerce_generation_controls(record.bundle.generation_controls)
            if bundle_controls is not None:
                return bundle_controls
        return StoryGenerationControls()

    def create_job(self, request: AuthorJobCreateRequest, *, actor_user_id: str | None = None) -> AuthorJobStatusResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        preview = self._resolve_preview_for_job(request, actor_user_id=resolved_actor_user_id)
        job_id = str(uuid4())
        record = _AuthorJobRecord(
            job_id=job_id,
            owner_user_id=resolved_actor_user_id,
            prompt_seed=request.prompt_seed,
            preview=preview,
            status="running",
            progress=self._initial_author_loading_progress(),
        )
        with self._lock:
            record.condition = self._condition_for(job_id)
            self._checkpointer.copy_thread(preview.preview_id, job_id)
            self._save_record(record)
        self._emit_event(job_id, "job_created", self._build_status_event_payload(job_id))
        self._start_background_job(job_id, resume_from_checkpoint=True)
        return self.get_job(job_id, actor_user_id=resolved_actor_user_id)

    def get_job(self, job_id: str, *, actor_user_id: str | None = None) -> AuthorJobStatusResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
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
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
        return AuthorJobResultResponse(
            job_id=record.job_id,
            status=record.status,  # type: ignore[arg-type]
            summary=record.summary,
            publishable=self._is_job_publishable(record),
            progress_snapshot=self._progress_snapshot(record),
            cache_metrics=record.cache_metrics,
        )

    def get_job_editor_state(self, job_id: str, *, actor_user_id: str | None = None) -> AuthorEditorStateResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
            if record.status != "completed" or record.summary is None or record.bundle is None:
                raise AuthorGatewayError(
                    code="author_editor_state_unavailable",
                    message=f"author job '{job_id}' does not have a completed editor state yet",
                    status_code=409,
                )
        return self._build_editor_state(record)

    def create_cast_portrait_plan(
        self,
        job_id: str,
        request: AuthorCastPortraitPlanRequest,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCastPortraitPlanResponse:
        editor_state = self.get_job_editor_state(job_id, actor_user_id=actor_user_id)
        try:
            return build_author_cast_portrait_plan(
                job_id=job_id,
                editor_state=editor_state,
                request=request,
                settings=self._settings,
            )
        except ValueError as exc:
            missing_npc_ids = [item for item in str(exc).split(",") if item]
            raise AuthorGatewayError(
                code="author_cast_portrait_npc_not_found",
                message=f"unknown cast npc ids for portrait plan: {', '.join(missing_npc_ids)}",
                status_code=422,
            ) from exc

    @staticmethod
    def _refresh_session_staleness(
        session: AuthorCopilotSessionResponse,
        *,
        current_revision: str,
    ) -> AuthorCopilotSessionResponse:
        if session.base_revision == current_revision or session.status in {"applied", "closed"}:
            return session
        return session.model_copy(
            update={
                "status": "stale",
                "updated_at": datetime.now(timezone.utc),
            }
        )

    def create_copilot_session(
        self,
        job_id: str,
        request: AuthorCopilotSessionCreateRequest,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotSessionResponse:
        editor_state = self.get_job_editor_state(job_id, actor_user_id=actor_user_id)
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
            self._ensure_copilot_editable(record)
            _workspace_snapshot = self._resolve_copilot_workspace_snapshot(record)
            now = self._now()
            locked_boundaries = build_copilot_locked_boundaries(editor_state=editor_state)
            session = AuthorCopilotSessionResponse(
                session_id=str(uuid4()),
                job_id=job_id,
                status="active",
                hidden=request.hidden,
                base_revision=record.updated_at.isoformat(),
                locked_boundaries=locked_boundaries,
                rewrite_brief=build_initial_rewrite_brief(
                    editor_state=editor_state,
                    locked_boundaries=locked_boundaries,
                ),
                messages=[
                    AuthorCopilotMessage(
                        message_id=str(uuid4()),
                        role="assistant",
                        content=localized_text(
                            editor_state.language,
                            en="I’m ready to reshape this draft globally while keeping its language, premise family, and runtime lane stable. Tell me what you want to change.",
                            zh="我已经准备好在保留语言、核心题材和这版基本玩法的前提下，整体重写这版草稿。告诉我你想把它往哪边推。",
                        ),
                        created_at=now,
                    )
                ],
                last_proposal_id=None,
                created_at=now,
                updated_at=now,
            )
            self._save_record(record)
            self._save_copilot_session(owner_user_id=record.owner_user_id, session=session)
            return session

    def get_copilot_session(
        self,
        job_id: str,
        session_id: str,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotSessionResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        payload = self._get_copilot_session_record(session_id)
        if payload["job_id"] != job_id:
            raise AuthorGatewayError(
                code="author_copilot_session_not_found",
                message=f"copilot session '{session_id}' was not found",
                status_code=404,
            )
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
        session = self._session_model(payload)
        refreshed = self._refresh_session_staleness(session, current_revision=record.updated_at.isoformat())
        if refreshed != session:
            self._save_copilot_session(owner_user_id=record.owner_user_id, session=refreshed)
        return refreshed

    def append_copilot_session_message(
        self,
        job_id: str,
        session_id: str,
        request: AuthorCopilotSessionMessageRequest,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotSessionResponse:
        editor_state = self.get_job_editor_state(job_id, actor_user_id=actor_user_id)
        session = self.get_copilot_session(job_id, session_id, actor_user_id=actor_user_id)
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_copilot_editable(record)
            if session.status in {"stale", "closed", "applied"}:
                raise AuthorGatewayError(
                    code="author_copilot_session_stale",
                    message="copilot session is stale against the current draft revision",
                    status_code=409,
                )
        gateway = None
        try:
            gateway = self._gateway_factory(self._settings)
        except Exception:  # noqa: BLE001
            gateway = None
        assistant_reply, rewrite_brief, _source = build_copilot_session_reply(
            gateway=gateway,
            session=session,
            editor_state=editor_state,
            message=request.content,
        )
        now = self._now()
        updated_session = session.model_copy(
            update={
                "messages": [
                    *session.messages,
                    AuthorCopilotMessage(message_id=str(uuid4()), role="user", content=request.content, created_at=now),
                    AuthorCopilotMessage(message_id=str(uuid4()), role="assistant", content=assistant_reply, created_at=now),
                ],
                "rewrite_brief": rewrite_brief,
                "status": "active",
                "updated_at": now,
            }
        )
        self._save_copilot_session(owner_user_id=record.owner_user_id, session=updated_session)
        return updated_session

    def create_copilot_session_proposal(
        self,
        job_id: str,
        session_id: str,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotProposalResponse:
        editor_state = self.get_job_editor_state(job_id, actor_user_id=actor_user_id)
        session = self.get_copilot_session(job_id, session_id, actor_user_id=actor_user_id)
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_copilot_editable(record)
            workspace_snapshot = self._resolve_copilot_workspace_snapshot(record)
            if session.status in {"stale", "closed", "applied"}:
                raise AuthorGatewayError(
                    code="author_copilot_session_stale",
                    message="copilot session is stale against the current draft revision",
                    status_code=409,
                )
            proposal_group_id = session.session_id
            variant_index = 1
            supersedes_proposal_id: str | None = session.last_proposal_id
            if session.last_proposal_id:
                last_payload = self._storage.get_copilot_proposal(session.last_proposal_id)
                if last_payload is None:
                    raise AuthorGatewayError(
                        code="author_copilot_proposal_not_found",
                        message=f"copilot proposal '{session.last_proposal_id}' was not found",
                        status_code=404,
                    )
                last_proposal = AuthorCopilotProposalResponse.model_validate(last_payload["proposal"])
                variant_index = last_proposal.variant_index + 1
                self._save_copilot_proposal(
                    owner_user_id=record.owner_user_id,
                    proposal=last_proposal.model_copy(update={"status": "superseded", "updated_at": self._now()}),
                )
        gateway = None
        try:
            gateway = self._gateway_factory(self._settings)
        except Exception:  # noqa: BLE001
            gateway = None
        try:
            proposal, variant_fingerprint = build_copilot_proposal(
                gateway=gateway,
                session=session,
                job_id=job_id,
                base_revision=session.base_revision,
                editor_state=editor_state,
                workspace_snapshot=workspace_snapshot,
                instruction=session.rewrite_brief.latest_instruction,
                proposal_group_id=proposal_group_id,
                variant_index=variant_index,
                supersedes_proposal_id=supersedes_proposal_id,
            )
        except ValueError as exc:
            if str(exc) == "instruction_unsupported":
                raise AuthorGatewayError(
                    code="author_copilot_instruction_unsupported",
                    message="copilot could not map this instruction into a supported structural rewrite yet",
                    status_code=422,
                ) from exc
            if str(exc) == "no_more_variants":
                raise AuthorGatewayError(
                    code="author_copilot_no_more_variants",
                    message="copilot does not have another materially different suggestion for this instruction and revision",
                    status_code=409,
                ) from exc
            raise
        updated_session = session.model_copy(
            update={
                "status": "proposal_ready",
                "last_proposal_id": proposal.proposal_id,
                "updated_at": self._now(),
            }
        )
        self._save_copilot_proposal(owner_user_id=record.owner_user_id, proposal=proposal, variant_fingerprint=variant_fingerprint)
        self._save_copilot_session(owner_user_id=record.owner_user_id, session=updated_session)
        return proposal

    def create_copilot_proposal(
        self,
        job_id: str,
        request: AuthorCopilotProposalRequest,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotProposalResponse:
        retry_from_proposal = (
            self.get_copilot_proposal(job_id, request.retry_from_proposal_id, actor_user_id=actor_user_id)
            if request.retry_from_proposal_id
            else None
        )
        if retry_from_proposal is not None:
            self._ensure_copilot_proposal_active(retry_from_proposal, action="retry")
            if retry_from_proposal.session_id is None:
                raise AuthorGatewayError(
                    code="author_copilot_session_not_found",
                    message="copilot proposal is not linked to a live session",
                    status_code=409,
                )
            session = self.get_copilot_session(job_id, retry_from_proposal.session_id, actor_user_id=actor_user_id)
        else:
            session = self.create_copilot_session(
                job_id,
                AuthorCopilotSessionCreateRequest(hidden=True),
                actor_user_id=actor_user_id,
            )
        session = self.append_copilot_session_message(
            job_id,
            session.session_id,
            AuthorCopilotSessionMessageRequest(content=request.instruction),
            actor_user_id=actor_user_id,
        )
        try:
            return self.create_copilot_session_proposal(job_id, session.session_id, actor_user_id=actor_user_id)
        except ValueError as exc:
            if str(exc) == "instruction_unsupported":
                raise AuthorGatewayError(
                    code="author_copilot_instruction_unsupported",
                    message="copilot could not map this instruction into a supported structural rewrite yet",
                    status_code=422,
                ) from exc
            if str(exc) == "no_more_variants":
                raise AuthorGatewayError(
                    code="author_copilot_no_more_variants",
                    message="copilot does not have another materially different suggestion for this instruction and revision",
                    status_code=409,
                ) from exc
            raise

    def get_copilot_proposal(
        self,
        job_id: str,
        proposal_id: str,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotProposalResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        payload = self._storage.get_copilot_proposal(proposal_id)
        if payload is None or payload["job_id"] != job_id:
            raise AuthorGatewayError(
                code="author_copilot_proposal_not_found",
                message=f"copilot proposal '{proposal_id}' was not found",
                status_code=404,
            )
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
        return AuthorCopilotProposalResponse.model_validate(payload["proposal"])

    def preview_copilot_proposal(
        self,
        job_id: str,
        proposal_id: str,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotPreviewResponse:
        proposal = self.get_copilot_proposal(job_id, proposal_id, actor_user_id=actor_user_id)
        self._ensure_copilot_proposal_active(proposal, action="preview")
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_copilot_editable(record)
            if record.updated_at.isoformat() != proposal.base_revision:
                raise AuthorGatewayError(
                    code="author_copilot_proposal_stale",
                    message="copilot proposal is stale against the current editor revision",
                    status_code=409,
                )
            workspace_snapshot = self._resolve_copilot_workspace_snapshot(record)
        gateway = self._gateway_factory(self._settings)
        candidate_snapshot, candidate_bundle = apply_copilot_operations(
            workspace_snapshot=workspace_snapshot,
            proposal=proposal,
            gateway=gateway,
        )
        consistency_reasons = validate_copilot_candidate(
            workspace_snapshot=workspace_snapshot,
            candidate_snapshot=candidate_snapshot,
            bundle=candidate_bundle,
        )
        if consistency_reasons:
            candidate_snapshot, candidate_bundle = repair_copilot_candidate(
                workspace_snapshot=workspace_snapshot,
                candidate_snapshot=candidate_snapshot,
                proposal=proposal,
            )
            consistency_reasons = validate_copilot_candidate(
                workspace_snapshot=workspace_snapshot,
                candidate_snapshot=candidate_snapshot,
                bundle=candidate_bundle,
            )
        if consistency_reasons:
            raise AuthorGatewayError(
                code="author_copilot_rewrite_inconsistent",
                message=f"copilot rewrite preview failed consistency gate: {', '.join(consistency_reasons)}",
                status_code=422,
            )
        candidate_summary = build_author_story_summary(
            candidate_bundle,
            primary_theme=candidate_snapshot.primary_theme,
        )
        candidate_preview = build_author_preview_from_bundle(
            preview_id=record.preview.preview_id,
            prompt_seed=record.prompt_seed,
            bundle=candidate_bundle,
        )
        candidate_record = _AuthorJobRecord(
            job_id=record.job_id,
            owner_user_id=record.owner_user_id,
            prompt_seed=record.prompt_seed,
            preview=candidate_preview,
            status=record.status,
            progress=record.progress,
            created_at=record.created_at,
            updated_at=record.updated_at,
            finished_at=record.finished_at,
            cache_metrics=record.cache_metrics,
            llm_call_trace=list(record.llm_call_trace),
            quality_trace=list(record.quality_trace),
            source_summary=dict(record.source_summary),
            roster_catalog_version=record.roster_catalog_version,
            roster_enabled=record.roster_enabled,
            roster_retrieval_trace=list(record.roster_retrieval_trace),
            copilot_workspace_snapshot=candidate_snapshot,
            events=list(record.events),
            condition=record.condition,
            bundle=candidate_bundle,
            summary=candidate_summary,
            error=record.error,
        )
        return AuthorCopilotPreviewResponse(proposal=proposal, editor_state=self._build_editor_state(candidate_record))

    def apply_copilot_proposal(
        self,
        job_id: str,
        proposal_id: str,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotApplyResponse:
        proposal = self.get_copilot_proposal(job_id, proposal_id, actor_user_id=actor_user_id)
        self._ensure_copilot_proposal_active(proposal, action="apply")
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_copilot_editable(record)
            if record.updated_at.isoformat() != proposal.base_revision:
                raise AuthorGatewayError(
                    code="author_copilot_proposal_stale",
                    message="copilot proposal is stale against the current editor revision",
                    status_code=409,
                )
            if record.bundle is None or record.summary is None:
                raise AuthorGatewayError(
                    code="author_editor_state_unavailable",
                    message=f"author job '{job_id}' does not have a completed editor state yet",
                    status_code=409,
                )
            workspace_snapshot = self._resolve_copilot_workspace_snapshot(record)
            gateway = self._gateway_factory(self._settings)
            updated_snapshot, updated_bundle = apply_copilot_operations(
                workspace_snapshot=workspace_snapshot,
                proposal=proposal,
                gateway=gateway,
            )
            consistency_reasons = validate_copilot_candidate(
                workspace_snapshot=workspace_snapshot,
                candidate_snapshot=updated_snapshot,
                bundle=updated_bundle,
            )
            if consistency_reasons:
                updated_snapshot, updated_bundle = repair_copilot_candidate(
                    workspace_snapshot=workspace_snapshot,
                    candidate_snapshot=updated_snapshot,
                    proposal=proposal,
                )
                consistency_reasons = validate_copilot_candidate(
                    workspace_snapshot=workspace_snapshot,
                    candidate_snapshot=updated_snapshot,
                    bundle=updated_bundle,
                )
            if consistency_reasons:
                raise AuthorGatewayError(
                    code="author_copilot_rewrite_inconsistent",
                    message=f"copilot rewrite failed consistency gate: {', '.join(consistency_reasons)}",
                    status_code=422,
                )
            updated_summary = build_author_story_summary(
                updated_bundle,
                primary_theme=updated_snapshot.primary_theme,
            )
            updated_preview = build_author_preview_from_bundle(
                preview_id=record.preview.preview_id,
                prompt_seed=record.prompt_seed,
                bundle=updated_bundle,
            )
            prior_preview = record.preview
            prior_summary = record.summary
            prior_bundle = record.bundle
            prior_workspace_snapshot = record.copilot_workspace_snapshot or workspace_snapshot
            prior_record_revision = record.updated_at.isoformat()
            applied_at = self._now()
            record.bundle = updated_bundle
            record.summary = updated_summary
            record.preview = updated_preview
            record.copilot_workspace_snapshot = updated_snapshot
            record.updated_at = applied_at
            self._save_record(record)
            applied_proposal = proposal.model_copy(
                update={
                    "status": "applied",
                    "updated_at": applied_at,
                    "applied_at": applied_at,
                }
            )
            self._save_copilot_proposal(
                owner_user_id=record.owner_user_id,
                proposal=applied_proposal,
                prior_preview=prior_preview,
                prior_summary=prior_summary,
                prior_bundle=prior_bundle,
                prior_workspace_snapshot=prior_workspace_snapshot,
                prior_record_revision=prior_record_revision,
            )
            if proposal.session_id:
                session_payload = self._get_copilot_session_record(proposal.session_id)
                session = self._session_model(session_payload)
                self._save_copilot_session(
                    owner_user_id=record.owner_user_id,
                    session=session.model_copy(update={"status": "applied", "last_proposal_id": proposal.proposal_id, "updated_at": applied_at}),
                )
            editor_state = self._build_editor_state(record)
        return AuthorCopilotApplyResponse(
            proposal=applied_proposal,
            editor_state=editor_state,
        )

    def undo_copilot_proposal(
        self,
        job_id: str,
        proposal_id: str,
        *,
        actor_user_id: str | None = None,
    ) -> AuthorCopilotUndoResponse:
        proposal_payload = self._storage.get_copilot_proposal(proposal_id)
        if proposal_payload is None or proposal_payload["job_id"] != job_id:
            raise AuthorGatewayError(
                code="author_copilot_proposal_not_found",
                message=f"copilot proposal '{proposal_id}' was not found",
                status_code=404,
            )
        proposal = self._proposal_model(proposal_payload)
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
            self._ensure_copilot_editable(record)
            if proposal.status != "applied" or proposal.applied_at is None:
                raise AuthorGatewayError(
                    code="author_copilot_proposal_not_undoable",
                    message="copilot proposal is not in an undoable applied state",
                    status_code=409,
                )
            if proposal.session_id is not None:
                latest_applied = self._latest_applied_proposal_for_session(job_id=job_id, session_id=proposal.session_id)
                if latest_applied is None or latest_applied[1].proposal_id != proposal.proposal_id:
                    raise AuthorGatewayError(
                        code="author_copilot_proposal_not_undoable",
                        message="copilot proposal is no longer the latest applied proposal for this session",
                        status_code=409,
                    )
            if record.updated_at.isoformat() != proposal.applied_at.isoformat():
                raise AuthorGatewayError(
                    code="author_copilot_undo_stale",
                    message="copilot undo is stale against the current editor revision",
                    status_code=409,
                )
            if not all(
                proposal_payload.get(key) is not None
                for key in ("prior_preview", "prior_summary", "prior_bundle", "prior_workspace_snapshot")
            ):
                raise AuthorGatewayError(
                    code="author_copilot_proposal_not_undoable",
                    message="copilot proposal does not have a restorable pre-apply snapshot",
                    status_code=409,
                )

            restored_preview = AuthorPreviewResponse.model_validate(proposal_payload["prior_preview"])
            restored_summary = AuthorStorySummary.model_validate(proposal_payload["prior_summary"])
            restored_bundle = DesignBundle.model_validate(proposal_payload["prior_bundle"])
            restored_workspace_snapshot = AuthorCopilotWorkspaceSnapshot.model_validate(proposal_payload["prior_workspace_snapshot"])
            undone_at = self._now()
            record.preview = restored_preview
            record.summary = restored_summary
            record.bundle = restored_bundle
            record.copilot_workspace_snapshot = restored_workspace_snapshot
            record.updated_at = undone_at
            self._save_record(record)

            undone_proposal = proposal.model_copy(
                update={
                    "status": "superseded",
                    "updated_at": undone_at,
                }
            )
            self._save_copilot_proposal(
                owner_user_id=record.owner_user_id,
                proposal=undone_proposal,
                prior_preview=proposal_payload.get("prior_preview"),
                prior_summary=proposal_payload.get("prior_summary"),
                prior_bundle=proposal_payload.get("prior_bundle"),
                prior_workspace_snapshot=proposal_payload.get("prior_workspace_snapshot"),
                prior_record_revision=proposal_payload.get("prior_record_revision"),
            )
            if proposal.session_id:
                session_payload = self._get_copilot_session_record(proposal.session_id)
                session = self._session_model(session_payload)
                self._save_copilot_session(
                    owner_user_id=record.owner_user_id,
                    session=session.model_copy(
                        update={
                            "status": "active",
                            "base_revision": undone_at.isoformat(),
                            "last_proposal_id": None,
                            "updated_at": undone_at,
                        }
                    ),
                )
            editor_state = self._build_editor_state(record)
        return AuthorCopilotUndoResponse(
            proposal=undone_proposal,
            editor_state=editor_state,
        )

    def get_publishable_job_source(self, job_id: str, *, actor_user_id: str | None = None) -> AuthorJobPublishSource:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
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
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._lock:
            record = self._get_record(job_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, resource="author_job", resource_id=job_id)
            token_usage = record.cache_metrics or summarize_cache_metrics(record.llm_call_trace)
            lock_diagnostics = _author_context_lock_diagnostics(
                llm_call_trace=list(record.llm_call_trace),
                quality_trace=list(record.quality_trace),
                bundle=record.bundle,
            )
        return BenchmarkAuthorJobDiagnosticsResponse(
            job_id=record.job_id,
            content_prompt_profile=self._settings.content_prompt_profile,
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
            context_lock_violation_distribution=lock_diagnostics["context_lock_violation_distribution"],
            snapshot_stage_distribution=lock_diagnostics["snapshot_stage_distribution"],
            drift_repair_entry_count=lock_diagnostics["drift_repair_entry_count"],
            beat_runtime_shard_count=lock_diagnostics["beat_runtime_shard_count"],
            beat_runtime_shard_fallback_count=lock_diagnostics["beat_runtime_shard_fallback_count"],
            beat_runtime_shard_elapsed_ms=lock_diagnostics["beat_runtime_shard_elapsed_ms"],
            beat_runtime_shard_drift_distribution=lock_diagnostics["beat_runtime_shard_drift_distribution"],
            roster_catalog_version=record.roster_catalog_version,
            roster_enabled=record.roster_enabled,
            roster_selection_count=sum(1 for item in record.roster_retrieval_trace if item.get("selected_character_id")),
            roster_retrieval_trace=list(record.roster_retrieval_trace),
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
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
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
                record.progress = self._initial_author_loading_progress()
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
            gateway = self._gateway_factory(self._settings)
            def _progress_observer(**running_payload: Any) -> None:
                self._set_running_progress(job_id, **running_payload)

            graph = build_author_graph(
                gateway=gateway,
                checkpointer=self._checkpointer,
                progress_observer=_progress_observer,
            )
            config = graph_config(run_id=job_id)
            checkpoint_snapshot = graph.get_state(config) if checkpoint_exists else None
            checkpoint_state = getattr(checkpoint_snapshot, "values", None) if checkpoint_snapshot is not None else None
            self._set_running_progress(
                job_id,
                running_node="resume_from_preview_checkpoint",
                running_substage="resume_from_preview_checkpoint",
            )
            generation_controls = self._resolve_resume_generation_controls(
                record=record,
                checkpoint_state=checkpoint_state,
            )
            with self._lock:
                current = self._get_record(job_id)
                current.progress = self._resume_checkpoint_progress()
                current.updated_at = self._now()
                self._save_record(current)
            stream_input = None if checkpoint_exists else {
                "run_id": job_id,
                "raw_brief": record.prompt_seed,
                "language": record.preview.language,
                "generation_controls": generation_controls,
            }
            for update in graph.stream(
                stream_input,
                config=config,
                stream_mode="updates",
            ):
                node_name = next(iter(update.keys()))
                if node_name not in AUTHOR_LOADING_STAGE_INDEX_BY_NODE:
                    continue
                stage_index = AUTHOR_LOADING_STAGE_INDEX_BY_NODE[node_name]
                with self._lock:
                    current = self._get_record(job_id)
                    current.running_node = None
                    current.running_substage = None
                    current.running_slot_index = None
                    current.running_slot_total = None
                    current.running_slot_label = None
                    current.running_capability = None
                    current.running_started_at = None
                    current.progress = AuthorJobProgress(
                        stage=node_name,
                        stage_index=stage_index,
                        stage_total=len(AUTHOR_LOADING_NODE_FLOW),
                    )
                    if not resume_from_checkpoint:
                        snapshot = graph.get_state(config)
                        state = snapshot.values
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
            annotated_llm_call_trace = _annotate_author_llm_trace_with_context_locks(
                [*prior_llm_call_trace, *list(gateway.call_trace)],
                state,
            )
            with self._lock:
                current = self._get_record(job_id)
                current.status = "completed"
                current.running_node = None
                current.running_substage = None
                current.running_slot_index = None
                current.running_slot_total = None
                current.running_slot_label = None
                current.running_capability = None
                current.running_started_at = None
                current.progress = AuthorJobProgress(
                    stage="completed",
                    stage_index=len(AUTHOR_LOADING_NODE_FLOW),
                    stage_total=len(AUTHOR_LOADING_NODE_FLOW),
                )
                self._refresh_preview_from_state(current, state)
                current.bundle = bundle
                current.summary = summary
                current.llm_call_trace = annotated_llm_call_trace
                current.quality_trace = list(state.get("quality_trace") or [])
                current.source_summary = {
                    "story_frame_source": str(state.get("story_frame_source") or "unknown"),
                    "beat_plan_source": str(state.get("beat_plan_source") or "unknown"),
                    "beat_runtime_shard_source": str(state.get("beat_runtime_shard_source") or "unknown"),
                    "route_affordance_source": str(state.get("route_affordance_source") or "unknown"),
                    "ending_source": str(state.get("ending_source") or "unknown"),
                    "gameplay_semantics_source": str(state.get("gameplay_semantics_source") or "unknown"),
                }
                current.roster_catalog_version = str(state.get("roster_catalog_version") or "") or None
                current.roster_enabled = bool(state.get("roster_enabled"))
                current.roster_retrieval_trace = list(state.get("roster_retrieval_trace") or [])
                current.copilot_workspace_snapshot = build_copilot_workspace_snapshot_from_state(
                    state=state,
                    bundle=bundle,
                )
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
                current.running_node = None
                current.running_substage = None
                current.running_slot_index = None
                current.running_slot_total = None
                current.running_slot_label = None
                current.running_capability = None
                current.running_started_at = None
                failed_stage_index = current.progress.stage_index
                current.error = {
                    "code": "author_job_failed",
                    "message": str(exc),
                }
                current.progress = AuthorJobProgress(
                    stage="failed",
                    stage_index=max(0, min(failed_stage_index, len(AUTHOR_LOADING_NODE_FLOW))),
                    stage_total=len(AUTHOR_LOADING_NODE_FLOW),
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

    def _set_running_progress(
        self,
        job_id: str,
        *,
        running_node: str,
        running_substage: str,
        running_slot_index: int | None = None,
        running_slot_total: int | None = None,
        running_slot_label: str | None = None,
        running_capability: str | None = None,
    ) -> None:
        with self._lock:
            record = self._get_record(job_id)
            record.running_node = running_node
            record.running_substage = running_substage
            record.running_slot_index = running_slot_index
            record.running_slot_total = running_slot_total
            record.running_slot_label = running_slot_label
            record.running_capability = running_capability
            record.running_started_at = self._now()
            record.updated_at = self._now()
            self._save_record(record)

    def _clear_running_progress(self, job_id: str) -> None:
        with self._lock:
            record = self._get_record(job_id)
            record.running_node = None
            record.running_substage = None
            record.running_slot_index = None
            record.running_slot_total = None
            record.running_slot_label = None
            record.running_capability = None
            record.running_started_at = None
            record.updated_at = self._now()
            self._save_record(record)

    def _progress_snapshot(self, record: _AuthorJobRecord):
        token_usage = record.cache_metrics or summarize_cache_metrics(record.llm_call_trace)
        running_elapsed_ms = None
        if record.running_started_at is not None:
            running_elapsed_ms = max(int((self._now() - record.running_started_at).total_seconds() * 1000), 0)
        return build_progress_snapshot(
            preview=record.preview,
            progress=record.progress,
            token_usage=token_usage,
            token_cost_estimate=estimate_token_cost(token_usage),
            running_node=record.running_node,
            running_substage=record.running_substage,
            running_slot_index=record.running_slot_index,
            running_slot_total=record.running_slot_total,
            running_slot_label=record.running_slot_label,
            running_capability=record.running_capability,
            running_elapsed_ms=running_elapsed_ms,
        )

    def _ensure_copilot_editable(self, record: _AuthorJobRecord) -> None:
        if self._story_library_service.has_story_for_source_job(record.job_id):
            raise AuthorGatewayError(
                code="author_copilot_job_already_published",
                message="copilot edits are only allowed before the job has been published",
                status_code=409,
            )

    def _build_editor_state(self, record: _AuthorJobRecord) -> AuthorEditorStateResponse:
        bundle = record.bundle
        summary = record.summary
        if bundle is None or summary is None:
            raise AuthorGatewayError(
                code="author_editor_state_unavailable",
                message=f"author job '{record.job_id}' does not have a completed editor state yet",
                status_code=409,
            )
        cast_lookup = {member.npc_id: member.name for member in bundle.story_bible.cast}
        play_plan = compile_play_plan(story_id=record.job_id, bundle=bundle)
        runtime_profile_name = runtime_profile_label(
            play_plan.runtime_policy_profile,
            language=bundle.focused_brief.language,
        )
        closeout_profile_name = closeout_profile_label(
            play_plan.closeout_profile,
            language=bundle.focused_brief.language,
        )
        active_session_id = self._active_copilot_session_id_for_job(record)
        undo_state = self._undoable_copilot_state_for_record(record)
        undo_proposal = undo_state[2] if undo_state is not None else None
        return AuthorEditorStateResponse(
            job_id=record.job_id,
            status="completed",
            language=bundle.focused_brief.language,
            revision=record.updated_at.isoformat(),
            publishable=self._is_job_publishable(record),
            focused_brief=bundle.focused_brief,
            summary=summary,
            story_frame_view=AuthorEditorStoryFrameView(
                title=bundle.story_bible.title,
                premise=bundle.story_bible.premise,
                tone=bundle.story_bible.tone,
                stakes=bundle.story_bible.stakes,
                style_guard=bundle.story_bible.style_guard,
                world_rules=list(bundle.story_bible.world_rules),
                truths=list(bundle.story_bible.truth_catalog),
                state_axes=list(bundle.state_schema.axes),
                flags=list(bundle.state_schema.flags),
            ),
            cast_view=[
                AuthorEditorCastEntry(
                    npc_id=member.npc_id,
                    name=member.name,
                    role=member.role,
                    agenda=member.agenda,
                    red_line=member.red_line,
                    pressure_signature=member.pressure_signature,
                    roster_character_id=member.roster_character_id,
                    roster_public_summary=member.roster_public_summary,
                    portrait_url=member.portrait_url,
                    portrait_variants=member.portrait_variants,
                    template_version=member.template_version,
                )
                for member in bundle.story_bible.cast
            ],
            beat_view=[
                AuthorEditorBeatView(
                    beat_id=beat.beat_id,
                    title=beat.title,
                    goal=beat.goal,
                    milestone_kind=beat.milestone_kind,
                    pressure_axis_id=beat.pressure_axis_id,
                    route_pivot_tag=beat.route_pivot_tag,
                    progress_required=beat.progress_required,
                    focus_npcs=[AuthorEditorNpcRef(npc_id=npc_id, name=cast_lookup.get(npc_id, npc_id)) for npc_id in beat.focus_npcs],
                    conflict_npcs=[AuthorEditorNpcRef(npc_id=npc_id, name=cast_lookup.get(npc_id, npc_id)) for npc_id in beat.conflict_npcs],
                    affordance_tags=[affordance.tag for affordance in beat.affordances],
                    blocked_affordances=list(beat.blocked_affordances),
                )
                for beat in bundle.beat_spine
            ],
            rule_pack_view=AuthorEditorRulePackView(
                route_unlock_rules=list(bundle.rule_pack.route_unlock_rules),
                ending_rules=list(bundle.rule_pack.ending_rules),
                affordance_effect_profiles=list(bundle.rule_pack.affordance_effect_profiles),
            ),
            play_profile_view=AuthorEditorPlayProfileView(
                protagonist=bundle.story_bible.cast[0],
                runtime_profile=play_plan.runtime_policy_profile,
                runtime_profile_label=runtime_profile_name,
                closeout_profile=play_plan.closeout_profile,
                closeout_profile_label=closeout_profile_name,
                max_turns=play_plan.max_turns,
                target_duration_minutes=play_plan.target_duration_minutes,
                branch_budget=play_plan.branch_budget,
            ),
            copilot_view=build_copilot_workspace_view(
                language=bundle.focused_brief.language,
                title=bundle.story_bible.title,
                protagonist_name=bundle.story_bible.cast[0].name,
                runtime_profile_label=runtime_profile_name,
                closeout_profile_label=closeout_profile_name,
                premise=bundle.story_bible.premise,
                theme=summary.theme,
                active_session_id=active_session_id,
                undo_available=undo_state is not None,
                undo_proposal_id=undo_proposal.proposal_id if undo_proposal is not None else None,
                undo_request_summary=undo_proposal.request_summary if undo_proposal is not None else None,
            ),
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
                "publishable": self._is_job_publishable(record),
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
        interrupted_job_ids: list[str] = []
        for payload in self._storage.list_jobs():
            if payload.get("status") not in {"queued", "running"}:
                continue
            record = self._deserialize_job_record(payload)
            with self._lock:
                record.condition = self._condition_for(record.job_id)
                self._save_record(record)
            interrupted_job_ids.append(record.job_id)
        for job_id in interrupted_job_ids:
            self._run_job(job_id, resume_from_checkpoint=True)

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

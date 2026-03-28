from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import perf_counter
import tempfile
from typing import Callable
from uuid import uuid4

from rpg_backend.author.contracts import RouteUnlockRule
from rpg_backend.benchmark.contracts import (
    BenchmarkPlaySessionDiagnosticsResponse,
    BenchmarkPlayTraceSummary,
)
from rpg_backend.config import Settings, get_settings
from rpg_backend.llm_gateway import CapabilityGatewayCore, build_gateway_core, text_gateway_config_available
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.play.storage import SQLitePlaySessionStorage
from rpg_backend.play.closeout import (
    EndingJudgeResult,
    PyrrhicCriticResult,
    finalize_turn_ending,
    judge_eligible,
    judge_ending_intent,
    run_pyrrhic_critic,
)
from rpg_backend.play.compiler import compile_play_plan
from rpg_backend.play.contracts import (
    PlayPlan,
    PlayNpcEpilogueReaction,
    PlaySessionHistoryEntry,
    PlaySessionHistoryResponse,
    PlaySessionSnapshot,
    PlaySuggestedAction,
    PlayEnding,
    PlayTurnTrace,
    PlayTurnRequest,
)
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.runtime import (
    apply_turn_resolution,
    PlaySessionState,
    build_initial_session_state,
    build_session_snapshot,
)
from rpg_backend.play.stages import (
    interpret_turn,
    render_turn,
)


class PlayServiceError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class _PlaySessionRecord:
    owner_user_id: str
    plan: PlayPlan
    state: PlaySessionState
    created_at: datetime
    expires_at: datetime
    finished_at: datetime | None
    history: list[PlaySessionHistoryEntry]
    turn_traces: list[PlayTurnTrace]


class PlaySessionService:
    _MAX_CACHED_INACTIVE_SESSIONS = 64

    def __init__(
        self,
        *,
        story_library_service: StoryLibraryService,
        gateway_factory: Callable[[Settings | None], CapabilityGatewayCore] = build_gateway_core,
        settings: Settings | None = None,
        now_provider: Callable[[], datetime] | None = None,
        enable_turn_telemetry: bool = True,
        enable_interpret_repair: bool = True,
        enable_render_repair: bool = True,
        use_tuned_ending_policy: bool = True,
        enable_ending_intent_judge: bool = True,
        enable_pyrrhic_judge_relaxation: bool = True,
        storage: SQLitePlaySessionStorage | None = None,
        allow_default_actor_fallback: bool = True,
    ) -> None:
        self._story_library_service = story_library_service
        self._gateway_factory = gateway_factory
        self._settings = settings or get_settings()
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._storage = storage or SQLitePlaySessionStorage(
            self._settings.runtime_state_db_path
            if settings is not None
            else f"{tempfile.gettempdir()}/rpg_demo_play_sessions_{uuid4()}.sqlite3"
        )
        self._lock = Lock()
        self._session_locks: dict[str, Lock] = {}
        self._sessions: dict[str, _PlaySessionRecord] = {}
        self._allow_default_actor_fallback = allow_default_actor_fallback
        self._enable_turn_telemetry = enable_turn_telemetry
        self._enable_interpret_repair = enable_interpret_repair
        self._enable_render_repair = enable_render_repair
        self._use_tuned_ending_policy = use_tuned_ending_policy
        self._enable_ending_intent_judge = enable_ending_intent_judge
        self._enable_pyrrhic_judge_relaxation = enable_pyrrhic_judge_relaxation

    def _now(self) -> datetime:
        return self._now_provider()

    @staticmethod
    def _serialize_state(state: PlaySessionState) -> dict[str, object]:
        return {
            "session_id": state.session_id,
            "story_id": state.story_id,
            "status": state.status,
            "turn_index": state.turn_index,
            "beat_index": state.beat_index,
            "beat_progress": state.beat_progress,
            "beat_detours_used": state.beat_detours_used,
            "axis_values": dict(state.axis_values),
            "stance_values": dict(state.stance_values),
            "flag_values": dict(state.flag_values),
            "discovered_truth_ids": list(state.discovered_truth_ids),
            "discovered_event_ids": list(state.discovered_event_ids),
            "success_ledger": dict(state.success_ledger),
            "cost_ledger": dict(state.cost_ledger),
            "last_turn_axis_deltas": dict(state.last_turn_axis_deltas),
            "last_turn_stance_deltas": dict(state.last_turn_stance_deltas),
            "last_turn_tags": list(state.last_turn_tags),
            "last_turn_consequences": list(state.last_turn_consequences),
            "narration": state.narration,
            "suggested_actions": [item.model_dump(mode="json") for item in state.suggested_actions],
            "ending": state.ending.model_dump(mode="json") if state.ending is not None else None,
            "epilogue_reactions": [item.model_dump(mode="json") for item in state.epilogue_reactions],
            "session_response_id": state.session_response_id,
            "collapse_pressure_streak": state.collapse_pressure_streak,
            "primary_axis_history": list(state.primary_axis_history),
            "negative_stance_history": list(state.negative_stance_history),
        }

    @staticmethod
    def _deserialize_state(payload: dict[str, object]) -> PlaySessionState:
        return PlaySessionState(
            session_id=str(payload["session_id"]),
            story_id=str(payload["story_id"]),
            status=str(payload["status"]),
            turn_index=int(payload["turn_index"]),
            beat_index=int(payload["beat_index"]),
            beat_progress=int(payload["beat_progress"]),
            beat_detours_used=int(payload["beat_detours_used"]),
            axis_values=dict(payload.get("axis_values") or {}),
            stance_values=dict(payload.get("stance_values") or {}),
            flag_values=dict(payload.get("flag_values") or {}),
            discovered_truth_ids=list(payload.get("discovered_truth_ids") or []),
            discovered_event_ids=list(payload.get("discovered_event_ids") or []),
            success_ledger=dict(payload.get("success_ledger") or {}),
            cost_ledger=dict(payload.get("cost_ledger") or {}),
            last_turn_axis_deltas=dict(payload.get("last_turn_axis_deltas") or {}),
            last_turn_stance_deltas=dict(payload.get("last_turn_stance_deltas") or {}),
            last_turn_tags=list(payload.get("last_turn_tags") or []),
            last_turn_consequences=list(payload.get("last_turn_consequences") or []),
            narration=str(payload.get("narration") or ""),
            suggested_actions=[PlaySuggestedAction.model_validate(item) for item in (payload.get("suggested_actions") or [])],
            ending=PlayEnding.model_validate(payload["ending"]) if payload.get("ending") is not None else None,
            epilogue_reactions=[
                PlayNpcEpilogueReaction.model_validate(item)
                for item in (payload.get("epilogue_reactions") or [])
            ],
            session_response_id=str(payload["session_response_id"]) if payload.get("session_response_id") else None,
            collapse_pressure_streak=int(payload.get("collapse_pressure_streak") or 0),
            primary_axis_history=list(payload.get("primary_axis_history") or []),
            negative_stance_history=list(payload.get("negative_stance_history") or []),
        )

    def _serialize_record(self, record: _PlaySessionRecord) -> dict[str, object]:
        return {
            "session_id": record.state.session_id,
            "owner_user_id": record.owner_user_id,
            "story_id": record.plan.story_id,
            "created_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "finished_at": record.finished_at.isoformat() if record.finished_at is not None else None,
            "plan": record.plan.model_dump(mode="json"),
            "state": self._serialize_state(record.state),
            "history": [entry.model_dump(mode="json") for entry in record.history],
            "turn_traces": [trace.model_dump(mode="json") for trace in record.turn_traces],
        }

    def _deserialize_record(self, payload: dict[str, object]) -> _PlaySessionRecord:
        plan_payload = dict(payload["plan"])
        route_unlock_rules = [
            RouteUnlockRule.model_validate(item)
            for item in (plan_payload.get("route_unlock_rules") or [])
        ]
        plan_payload["route_unlock_rules"] = [rule.model_dump(mode="json") for rule in route_unlock_rules]
        plan = PlayPlan.model_validate(plan_payload)
        plan.route_unlock_rules = route_unlock_rules  # type: ignore[assignment]
        return _PlaySessionRecord(
            owner_user_id=str(payload["owner_user_id"]),
            plan=plan,
            state=self._deserialize_state(dict(payload["state"])),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            finished_at=datetime.fromisoformat(str(payload["finished_at"])) if payload.get("finished_at") else None,
            history=[PlaySessionHistoryEntry.model_validate(item) for item in (payload.get("history") or [])],
            turn_traces=[PlayTurnTrace.model_validate(item) for item in (payload.get("turn_traces") or [])],
        )

    def _save_record(self, record: _PlaySessionRecord) -> None:
        with self._lock:
            self._sessions[record.state.session_id] = record
        self._storage.save_session(self._serialize_record(record))
        self._prune_cached_sessions()

    def _prune_cached_sessions(self) -> None:
        with self._lock:
            inactive_records = [
                (session_id, record)
                for session_id, record in self._sessions.items()
                if record.state.status != "active"
            ]
            if len(inactive_records) <= self._MAX_CACHED_INACTIVE_SESSIONS:
                return
            inactive_records.sort(
                key=lambda item: (
                    item[1].finished_at or item[1].expires_at,
                    item[0],
                )
            )
            for session_id, _record in inactive_records[: len(inactive_records) - self._MAX_CACHED_INACTIVE_SESSIONS]:
                self._sessions.pop(session_id, None)
                self._session_locks.pop(session_id, None)

    def _session_lock_for(self, session_id: str) -> Lock:
        with self._lock:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = Lock()
                self._session_locks[session_id] = lock
            return lock

    @staticmethod
    def _ensure_owner_access(owner_user_id: str, actor_user_id: str, *, session_id: str) -> None:
        if owner_user_id == actor_user_id:
            return
        raise PlayServiceError(
            code="play_session_not_found",
            message=f"play session '{session_id}' was not found",
            status_code=404,
        )

    def _resolve_actor_user_id(self, actor_user_id: str | None) -> str:
        if actor_user_id is not None:
            return actor_user_id
        if self._allow_default_actor_fallback:
            return self._settings.default_actor_id
        raise PlayServiceError(
            code="auth_session_required",
            message="Sign in required.",
            status_code=401,
        )

    def _resolve_gateway(self) -> CapabilityGatewayCore | None:
        if not text_gateway_config_available(self._settings):
            return None
        try:
            return self._gateway_factory(self._settings)
        except Exception:
            return None

    def _get_record(self, session_id: str) -> _PlaySessionRecord:
        with self._lock:
            cached = self._sessions.get(session_id)
        if cached is not None:
            record = cached
        else:
            payload = self._storage.get_session(session_id)
            if payload is None:
                raise PlayServiceError(
                    code="play_session_not_found",
                    message=f"play session '{session_id}' was not found",
                    status_code=404,
                )
            record = self._deserialize_record(payload)
            with self._lock:
                self._sessions[session_id] = record
        return record

    def _expire_record_if_needed(self, record: _PlaySessionRecord) -> None:
        if record.state.status != "active" or self._now() < record.expires_at:
            return
        record.state.status = "expired"
        record.state.suggested_actions = []
        record.state.narration = "This session expired after sitting idle too long. Start a new run from the library."
        record.finished_at = self._now()
        self._save_record(record)

    @staticmethod
    def _add_usage(total: dict[str, int], usage: dict[str, int | str] | None) -> None:
        if not usage:
            return
        for key, value in usage.items():
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            total[str(key)] = total.get(str(key), 0) + int(value)

    @classmethod
    def _aggregate_trace_usage(cls, trace: PlayTurnTrace) -> dict[str, int]:
        usage: dict[str, int] = {}
        cls._add_usage(usage, trace.interpret_usage)
        cls._add_usage(usage, trace.ending_judge_usage)
        cls._add_usage(usage, trace.pyrrhic_critic_usage)
        cls._add_usage(usage, trace.render_usage)
        return usage

    @staticmethod
    def _involved_npc_template_versions(
        plan: PlayPlan,
        resolution,
    ) -> dict[str, str]:
        relevant_npc_ids = {
            npc_id
            for npc_id in resolution.target_npc_ids
            if npc_id and npc_id != plan.protagonist_npc_id
        }
        if resolution.stance_changes:
            stance_npc_ids = {
                stance.npc_id
                for stance in plan.stances
                if stance.stance_id in resolution.stance_changes and stance.npc_id != plan.protagonist_npc_id
            }
            relevant_npc_ids.update(stance_npc_ids)
        template_versions: dict[str, str] = {}
        for member in plan.cast:
            if member.npc_id not in relevant_npc_ids:
                continue
            version = str(member.template_version or "").strip()
            if not version:
                continue
            template_versions[member.npc_id] = version
        return template_versions

    @classmethod
    def _build_trace_summary(cls, traces: list[PlayTurnTrace]) -> BenchmarkPlayTraceSummary:
        interpret_source_distribution: dict[str, int] = {}
        ending_judge_source_distribution: dict[str, int] = {}
        pyrrhic_critic_source_distribution: dict[str, int] = {}
        render_source_distribution: dict[str, int] = {}
        render_primary_path_mode_distribution: dict[str, int] = {}
        render_failure_reason_distribution: dict[str, int] = {}
        interpret_failure_reason_distribution: dict[str, int] = {}
        capability_distribution: dict[str, int] = {}
        provider_distribution: dict[str, int] = {}
        usage_totals: dict[str, int] = {}
        heuristic_interpret_turn_count = 0
        ending_judge_failed_turn_count = 0
        ending_judge_stage1_success_count = 0
        ending_judge_stage2_rescue_count = 0
        pyrrhic_critic_stage1_success_count = 0
        pyrrhic_critic_stage2_rescue_count = 0
        render_plan_stage1_success_count = 0
        render_plan_stage2_rescue_count = 0
        render_narration_stage1_success_count = 0
        render_narration_stage2_rescue_count = 0
        render_direct_primary_success_count = 0
        render_fallback_turn_count = 0
        render_repair_turn_count = 0
        render_stage1_contract_failure_distribution: dict[str, int] = {}
        repair_turn_count = 0
        used_previous_response_turn_count = 0
        session_cache_enabled = False
        ending_id: str | None = None
        end_reason: str | None = None
        for trace in traces:
            interpret_source_distribution[trace.interpret_source] = interpret_source_distribution.get(trace.interpret_source, 0) + 1
            ending_judge_source_distribution[trace.ending_judge_source] = ending_judge_source_distribution.get(trace.ending_judge_source, 0) + 1
            pyrrhic_critic_source_distribution[trace.pyrrhic_critic_source] = pyrrhic_critic_source_distribution.get(trace.pyrrhic_critic_source, 0) + 1
            render_source_distribution[trace.render_source] = render_source_distribution.get(trace.render_source, 0) + 1
            render_primary_path_mode_distribution[trace.render_primary_path_mode] = (
                render_primary_path_mode_distribution.get(trace.render_primary_path_mode, 0) + 1
            )
            if trace.render_failure_reason:
                render_failure_reason_distribution[trace.render_failure_reason] = (
                    render_failure_reason_distribution.get(trace.render_failure_reason, 0) + 1
                )
            if trace.interpret_failure_reason:
                interpret_failure_reason_distribution[trace.interpret_failure_reason] = (
                    interpret_failure_reason_distribution.get(trace.interpret_failure_reason, 0) + 1
                )
            if trace.interpret_source == "heuristic":
                heuristic_interpret_turn_count += 1
            if trace.ending_judge_source == "failed":
                ending_judge_failed_turn_count += 1
            if trace.ending_judge_stage1_success:
                ending_judge_stage1_success_count += 1
            if trace.ending_judge_stage2_rescue:
                ending_judge_stage2_rescue_count += 1
            if trace.pyrrhic_critic_stage1_success:
                pyrrhic_critic_stage1_success_count += 1
            if trace.pyrrhic_critic_stage2_rescue:
                pyrrhic_critic_stage2_rescue_count += 1
            if trace.render_plan_stage1_success:
                render_plan_stage1_success_count += 1
            if trace.render_plan_stage2_rescue:
                render_plan_stage2_rescue_count += 1
            if trace.render_narration_stage1_success:
                render_narration_stage1_success_count += 1
            if trace.render_narration_stage2_rescue:
                render_narration_stage2_rescue_count += 1
            if trace.render_primary_path_mode == "direct_narration" and trace.render_source == "llm":
                render_direct_primary_success_count += 1
            if trace.render_source == "fallback":
                render_fallback_turn_count += 1
            if trace.render_source == "llm_repair":
                render_repair_turn_count += 1
            if trace.render_primary_failure_reason:
                render_stage1_contract_failure_distribution[trace.render_primary_failure_reason] = (
                    render_stage1_contract_failure_distribution.get(trace.render_primary_failure_reason, 0) + 1
                )
            if any(
                attempts > 1
                for attempts in (
                    trace.interpret_attempts,
                    trace.ending_judge_attempts,
                    trace.pyrrhic_critic_attempts,
                    trace.render_attempts,
                )
            ):
                repair_turn_count += 1
            if trace.used_previous_response_id:
                used_previous_response_turn_count += 1
            session_cache_enabled = session_cache_enabled or trace.session_cache_enabled
            for capability in (
                trace.interpret_capability,
                trace.ending_judge_capability,
                trace.pyrrhic_critic_capability,
                trace.render_capability,
            ):
                if capability:
                    capability_distribution[capability] = capability_distribution.get(capability, 0) + 1
            for provider in (
                trace.interpret_provider,
                trace.ending_judge_provider,
                trace.pyrrhic_critic_provider,
                trace.render_provider,
            ):
                if provider:
                    provider_distribution[provider] = provider_distribution.get(provider, 0) + 1
            cls._add_usage(usage_totals, cls._aggregate_trace_usage(trace))
            if trace.resolution.ending_id:
                ending_id = trace.resolution.ending_id
            if trace.resolution.ending_trigger_reason:
                end_reason = trace.resolution.ending_trigger_reason
        return BenchmarkPlayTraceSummary(
            turn_count=len(traces),
            total_turn_elapsed_ms=sum(trace.turn_elapsed_ms for trace in traces),
            total_interpret_elapsed_ms=sum(trace.interpret_elapsed_ms for trace in traces),
            total_ending_judge_elapsed_ms=sum(trace.ending_judge_elapsed_ms for trace in traces),
            total_pyrrhic_critic_elapsed_ms=sum(trace.pyrrhic_critic_elapsed_ms for trace in traces),
            total_render_elapsed_ms=sum(trace.render_elapsed_ms for trace in traces),
            interpret_source_distribution=interpret_source_distribution,
            ending_judge_source_distribution=ending_judge_source_distribution,
            pyrrhic_critic_source_distribution=pyrrhic_critic_source_distribution,
            render_source_distribution=render_source_distribution,
            render_primary_path_mode_distribution=render_primary_path_mode_distribution,
            render_failure_reason_distribution=render_failure_reason_distribution,
            interpret_failure_reason_distribution=interpret_failure_reason_distribution,
            capability_distribution=capability_distribution,
            provider_distribution=provider_distribution,
            heuristic_interpret_turn_count=heuristic_interpret_turn_count,
            ending_judge_failed_turn_count=ending_judge_failed_turn_count,
            ending_judge_stage1_success_rate=round(ending_judge_stage1_success_count / len(traces), 3) if traces else 0.0,
            ending_judge_stage2_rescue_rate=round(ending_judge_stage2_rescue_count / len(traces), 3) if traces else 0.0,
            pyrrhic_critic_stage1_success_rate=round(pyrrhic_critic_stage1_success_count / len(traces), 3) if traces else 0.0,
            pyrrhic_critic_stage2_rescue_rate=round(pyrrhic_critic_stage2_rescue_count / len(traces), 3) if traces else 0.0,
            render_plan_stage1_success_rate=round(render_plan_stage1_success_count / len(traces), 3) if traces else 0.0,
            render_plan_primary_success_rate=round(render_plan_stage1_success_count / len(traces), 3) if traces else 0.0,
            render_plan_stage2_rescue_rate=round(render_plan_stage2_rescue_count / len(traces), 3) if traces else 0.0,
            render_narration_stage1_success_rate=round(render_narration_stage1_success_count / len(traces), 3) if traces else 0.0,
            render_narration_stage2_rescue_rate=round(render_narration_stage2_rescue_count / len(traces), 3) if traces else 0.0,
            render_direct_primary_success_rate=round(render_direct_primary_success_count / len(traces), 3) if traces else 0.0,
            render_fallback_turn_count=render_fallback_turn_count,
            render_repair_entry_rate=round(render_repair_turn_count / len(traces), 3) if traces else 0.0,
            render_stage1_contract_failure_distribution=render_stage1_contract_failure_distribution,
            repair_turn_count=repair_turn_count,
            used_previous_response_turn_count=used_previous_response_turn_count,
            session_cache_enabled=session_cache_enabled,
            usage_totals=usage_totals,
            ending_id=ending_id,
            end_reason=end_reason,
        )

    def create_session(self, story_id: str, *, actor_user_id: str | None = None) -> PlaySessionSnapshot:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        story = self._story_library_service.get_story_record(story_id, actor_user_id=resolved_actor_user_id)
        session_id = str(uuid4())
        plan = compile_play_plan(story_id=story.story.story_id, bundle=story.bundle)
        state = build_initial_session_state(plan, session_id=session_id)
        now = self._now()
        record = _PlaySessionRecord(
            owner_user_id=resolved_actor_user_id,
            plan=plan,
            state=state,
            created_at=now,
            expires_at=now + timedelta(seconds=self._settings.play_session_ttl_seconds),
            finished_at=None,
            history=[
                PlaySessionHistoryEntry(
                    speaker="gm",
                    text=state.narration,
                    created_at=now,
                    turn_index=0,
                )
            ],
            turn_traces=[],
        )
        self._session_lock_for(session_id)
        self._save_record(record)
        return build_session_snapshot(plan, state)

    def get_session(self, session_id: str, *, actor_user_id: str | None = None) -> PlaySessionSnapshot:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._session_lock_for(session_id):
            record = self._get_record(session_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, session_id=session_id)
            self._expire_record_if_needed(record)
            return build_session_snapshot(record.plan, record.state)

    def get_turn_traces(self, session_id: str, *, actor_user_id: str | None = None) -> list[PlayTurnTrace]:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._session_lock_for(session_id):
            record = self._get_record(session_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, session_id=session_id)
            self._expire_record_if_needed(record)
            return list(record.turn_traces)

    def get_session_history(self, session_id: str, *, actor_user_id: str | None = None) -> PlaySessionHistoryResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._session_lock_for(session_id):
            record = self._get_record(session_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, session_id=session_id)
            self._expire_record_if_needed(record)
            return PlaySessionHistoryResponse(
                session_id=session_id,
                story_id=record.plan.story_id,
                language=record.plan.language,
                entries=list(record.history),
            )

    def get_session_diagnostics(self, session_id: str, *, actor_user_id: str | None = None) -> BenchmarkPlaySessionDiagnosticsResponse:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._session_lock_for(session_id):
            record = self._get_record(session_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, session_id=session_id)
            self._expire_record_if_needed(record)
            traces = list(record.turn_traces)
            return BenchmarkPlaySessionDiagnosticsResponse(
                session_id=session_id,
                story_id=record.plan.story_id,
                content_prompt_profile=self._settings.content_prompt_profile,
                status=record.state.status,  # type: ignore[arg-type]
                created_at=record.created_at,
                expires_at=record.expires_at,
                finished_at=record.finished_at,
                turn_traces=[trace.model_dump(mode="json") for trace in traces],
                summary=self._build_trace_summary(traces),
            )

    def submit_turn(self, session_id: str, request: PlayTurnRequest, *, actor_user_id: str | None = None) -> PlaySessionSnapshot:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._session_lock_for(session_id):
            record = self._get_record(session_id)
            self._ensure_owner_access(record.owner_user_id, resolved_actor_user_id, session_id=session_id)
            self._expire_record_if_needed(record)
            input_text = str(request.input_text).strip()
            if not input_text:
                raise PlayServiceError(
                    code="play_turn_input_empty",
                    message="play turn input must not be blank",
                    status_code=422,
                )
            if record.state.status == "expired":
                raise PlayServiceError(
                    code="play_session_expired",
                    message="play session expired; start a new session from the library",
                    status_code=409,
                )
            if record.state.status == "completed":
                raise PlayServiceError(
                    code="play_session_completed",
                    message="play session is already complete",
                    status_code=409,
                )
            selected_action = next(
                (item for item in record.state.suggested_actions if item.suggestion_id == request.selected_suggestion_id),
                None,
            )
            gateway = self._resolve_gateway()
            latest_response_id = record.state.session_response_id
            turn_started_at = perf_counter()
            beat_index_before = record.state.beat_index + 1
            beat_before = record.plan.beats[record.state.beat_index]
            interpret_previous_response_id = latest_response_id
            interpret_started_at = perf_counter()
            interpret_result = interpret_turn(
                plan=record.plan,
                state=record.state,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=interpret_previous_response_id,
                enable_interpret_repair=self._enable_interpret_repair,
            )
            interpret_elapsed_ms = max(int((perf_counter() - interpret_started_at) * 1000), 0)
            if interpret_result.response_id:
                latest_response_id = interpret_result.response_id
            record.state.turn_index += 1
            resolution, ending_context = apply_turn_resolution(
                plan=record.plan,
                state=record.state,
                intent=interpret_result.intent,
                use_tuned_ending_policy=self._use_tuned_ending_policy,
            )
            judge_previous_response_id = latest_response_id
            judge_started_at = perf_counter()
            skip_first_turn_judge = record.state.turn_index <= 1
            if skip_first_turn_judge:
                judge_result = EndingJudgeResult(proposed_ending_id=None, source="skipped", attempts=0)
            else:
                judge_result = judge_ending_intent(
                    plan=record.plan,
                    state=record.state,
                    resolution=resolution,
                    ending_context=ending_context,
                    input_text=input_text,
                    selected_action=selected_action,
                    gateway=gateway,
                    previous_response_id=judge_previous_response_id,
                    enable_ending_intent_judge=self._enable_ending_intent_judge,
                )
            ending_judge_elapsed_ms = max(int((perf_counter() - judge_started_at) * 1000), 0)
            if judge_result.response_id:
                latest_response_id = judge_result.response_id
            pyrrhic_previous_response_id = latest_response_id
            pyrrhic_started_at = perf_counter()
            if skip_first_turn_judge:
                pyrrhic_critic_result = PyrrhicCriticResult(proposed_ending_id=None, source="skipped", attempts=0)
            else:
                pyrrhic_critic_result = run_pyrrhic_critic(
                    plan=record.plan,
                    state=record.state,
                    resolution=resolution,
                    ending_context=ending_context,
                    judge_result=judge_result,
                    gateway=gateway,
                    previous_response_id=pyrrhic_previous_response_id,
                )
            pyrrhic_critic_elapsed_ms = max(int((perf_counter() - pyrrhic_started_at) * 1000), 0)
            if pyrrhic_critic_result.response_id:
                latest_response_id = pyrrhic_critic_result.response_id
            proposed_ending_id = pyrrhic_critic_result.proposed_ending_id or judge_result.proposed_ending_id
            resolution = finalize_turn_ending(
                plan=record.plan,
                state=record.state,
                resolution=resolution,
                ending_context=ending_context,
                proposed_ending_id=proposed_ending_id,
                use_tuned_ending_policy=self._use_tuned_ending_policy,
                enable_pyrrhic_judge_relaxation=self._enable_pyrrhic_judge_relaxation,
            )
            render_previous_response_id = latest_response_id
            render_started_at = perf_counter()
            render_result = render_turn(
                plan=record.plan,
                state=record.state,
                resolution=resolution,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=render_previous_response_id,
                enable_render_repair=self._enable_render_repair,
            )
            render_elapsed_ms = max(int((perf_counter() - render_started_at) * 1000), 0)
            if render_result.response_id:
                latest_response_id = render_result.response_id
            record.state.session_response_id = latest_response_id
            record.state.narration = render_result.narration
            record.state.suggested_actions = [] if record.state.status != "active" else render_result.suggestions
            player_entry_created_at = self._now()
            gm_entry_created_at = self._now()
            record.history.append(
                PlaySessionHistoryEntry(
                    speaker="player",
                    text=input_text,
                    created_at=player_entry_created_at,
                    turn_index=record.state.turn_index,
                )
            )
            record.history.append(
                PlaySessionHistoryEntry(
                    speaker="gm",
                    text=render_result.narration,
                    created_at=gm_entry_created_at,
                    turn_index=record.state.turn_index,
                )
            )
            if record.state.status != "active" and record.finished_at is None:
                record.finished_at = self._now()
            if self._enable_turn_telemetry:
                beat_after = record.plan.beats[record.state.beat_index]
                used_previous_response_id = any(
                    response_id is not None
                    for response_id in (
                        interpret_previous_response_id,
                        judge_previous_response_id,
                        pyrrhic_previous_response_id,
                        render_previous_response_id,
                    )
                )
                usage_totals: dict[str, int] = {}
                self._add_usage(usage_totals, interpret_result.usage or {})
                self._add_usage(usage_totals, judge_result.usage or {})
                self._add_usage(usage_totals, pyrrhic_critic_result.usage or {})
                self._add_usage(usage_totals, render_result.usage or {})
                record.turn_traces.append(
                    PlayTurnTrace(
                        turn_index=record.state.turn_index,
                        created_at=self._now(),
                        player_input=input_text,
                        selected_suggestion_id=request.selected_suggestion_id,
                        interpret_source=interpret_result.source,  # type: ignore[arg-type]
                        ending_judge_source=judge_result.source,  # type: ignore[arg-type]
                        execution_frame=interpret_result.intent.execution_frame,
                        ending_judge_attempts=judge_result.attempts,
                        ending_judge_stage1_success=judge_result.stage1_success,
                        ending_judge_stage2_rescue=judge_result.stage2_rescue,
                        ending_judge_proposed_id=judge_result.proposed_ending_id,  # type: ignore[arg-type]
                        ending_judge_failure_reason=judge_result.failure_reason,
                        ending_judge_response_id=judge_result.response_id,
                        ending_judge_usage=judge_result.usage or {},
                        pyrrhic_critic_source=pyrrhic_critic_result.source,  # type: ignore[arg-type]
                        pyrrhic_critic_attempts=pyrrhic_critic_result.attempts,
                        pyrrhic_critic_stage1_success=pyrrhic_critic_result.stage1_success,
                        pyrrhic_critic_stage2_rescue=pyrrhic_critic_result.stage2_rescue,
                        pyrrhic_critic_proposed_id=pyrrhic_critic_result.proposed_ending_id,  # type: ignore[arg-type]
                        pyrrhic_critic_failure_reason=pyrrhic_critic_result.failure_reason,
                        pyrrhic_critic_response_id=pyrrhic_critic_result.response_id,
                        pyrrhic_critic_usage=pyrrhic_critic_result.usage or {},
                        render_source=render_result.source,  # type: ignore[arg-type]
                        render_primary_path_mode=render_result.primary_path_mode,  # type: ignore[arg-type]
                        interpret_attempts=interpret_result.attempts,
                        render_attempts=render_result.attempts,
                        render_plan_stage1_success=render_result.render_plan_stage1_success,
                        render_plan_stage2_rescue=render_result.render_plan_stage2_rescue,
                        render_narration_stage1_success=render_result.render_narration_stage1_success,
                        render_narration_stage2_rescue=render_result.render_narration_stage2_rescue,
                        interpret_failure_reason=interpret_result.failure_reason,
                        render_failure_reason=render_result.failure_reason,
                        render_primary_failure_reason=render_result.render_primary_failure_reason,
                        render_primary_fallback_source=render_result.render_primary_fallback_source,
                        render_primary_raw_excerpt=render_result.render_primary_raw_excerpt,
                        render_quality_reason_before_repair=render_result.render_quality_reason_before_repair,
                        render_repair_failure_reason=render_result.render_repair_failure_reason,
                        render_repair_raw_excerpt=render_result.render_repair_raw_excerpt,
                        interpret_response_id=interpret_result.response_id,
                        render_response_id=render_result.response_id,
                        interpret_capability=interpret_result.capability,
                        ending_judge_capability=judge_result.capability,
                        pyrrhic_critic_capability=pyrrhic_critic_result.capability,
                        render_capability=render_result.capability,
                        interpret_provider=interpret_result.provider,
                        ending_judge_provider=judge_result.provider,
                        pyrrhic_critic_provider=pyrrhic_critic_result.provider,
                        render_provider=render_result.provider,
                        interpret_model=interpret_result.model,
                        ending_judge_model=judge_result.model,
                        pyrrhic_critic_model=pyrrhic_critic_result.model,
                        render_model=render_result.model,
                        interpret_transport_style=interpret_result.transport_style,
                        ending_judge_transport_style=judge_result.transport_style,
                        pyrrhic_critic_transport_style=pyrrhic_critic_result.transport_style,
                        render_transport_style=render_result.transport_style,
                        interpret_skill_id=interpret_result.skill_id,
                        interpret_skill_version=interpret_result.skill_version,
                        interpret_contract_mode=interpret_result.contract_mode,
                        interpret_context_card_ids=list(interpret_result.context_card_ids or []),
                        interpret_context_packet_characters=interpret_result.context_packet_characters,
                        interpret_repair_mode=interpret_result.repair_mode,
                        ending_judge_skill_id=judge_result.skill_id,
                        ending_judge_skill_version=judge_result.skill_version,
                        ending_judge_contract_mode=judge_result.contract_mode,
                        ending_judge_context_card_ids=list(judge_result.context_card_ids or []),
                        ending_judge_context_packet_characters=judge_result.context_packet_characters,
                        ending_judge_repair_mode=judge_result.repair_mode,
                        pyrrhic_critic_skill_id=pyrrhic_critic_result.skill_id,
                        pyrrhic_critic_skill_version=pyrrhic_critic_result.skill_version,
                        pyrrhic_critic_contract_mode=pyrrhic_critic_result.contract_mode,
                        pyrrhic_critic_context_card_ids=list(pyrrhic_critic_result.context_card_ids or []),
                        pyrrhic_critic_context_packet_characters=pyrrhic_critic_result.context_packet_characters,
                        pyrrhic_critic_repair_mode=pyrrhic_critic_result.repair_mode,
                        render_skill_id=render_result.skill_id,
                        render_skill_version=render_result.skill_version,
                        render_contract_mode=render_result.contract_mode,
                        render_context_card_ids=list(render_result.context_card_ids or []),
                        render_context_packet_characters=render_result.context_packet_characters,
                        render_repair_mode=render_result.repair_mode,
                        interpret_usage=interpret_result.usage or {},
                        render_usage=render_result.usage or {},
                        turn_elapsed_ms=max(int((perf_counter() - turn_started_at) * 1000), 0),
                        interpret_elapsed_ms=interpret_elapsed_ms,
                        ending_judge_elapsed_ms=ending_judge_elapsed_ms,
                        pyrrhic_critic_elapsed_ms=pyrrhic_critic_elapsed_ms,
                        render_elapsed_ms=render_elapsed_ms,
                        session_cache_enabled=bool(getattr(gateway, "use_session_cache", False)),
                        used_previous_response_id=used_previous_response_id,
                        input_tokens=usage_totals.get("input_tokens"),
                        output_tokens=usage_totals.get("output_tokens"),
                        total_tokens=usage_totals.get("total_tokens"),
                        cached_input_tokens=usage_totals.get("cached_input_tokens"),
                        cache_creation_input_tokens=usage_totals.get("cache_creation_input_tokens"),
                        involved_npc_template_versions=self._involved_npc_template_versions(record.plan, resolution),
                        beat_index_before=beat_index_before,
                        beat_title_before=beat_before.title,
                        beat_index_after=record.state.beat_index + 1,
                        beat_title_after=beat_after.title,
                        status_after=record.state.status,  # type: ignore[arg-type]
                        resolution=resolution,
                    )
                )
            self._save_record(record)
            return build_session_snapshot(record.plan, record.state)

    def delete_sessions_for_story(self, *, actor_user_id: str | None = None, story_id: str) -> int:
        resolved_actor_user_id = self._resolve_actor_user_id(actor_user_id)
        with self._lock:
            deleted = self._storage.delete_sessions_for_story(
                story_id=story_id,
                owner_user_id=resolved_actor_user_id if actor_user_id is not None else None,
            )
            stale_session_ids = [
                session_id
                for session_id, record in self._sessions.items()
                if record.plan.story_id == story_id and (actor_user_id is None or record.owner_user_id == resolved_actor_user_id)
            ]
            for session_id in stale_session_ids:
                self._sessions.pop(session_id, None)
                self._session_locks.pop(session_id, None)
        return deleted

    def delete_all_sessions_for_story(self, *, story_id: str) -> int:
        with self._lock:
            deleted = self._storage.delete_sessions_for_story(
                story_id=story_id,
                owner_user_id=None,
            )
            deleted_session_ids = [
                session_id
                for session_id, record in self._sessions.items()
                if record.plan.story_id == story_id
            ]
            for session_id in deleted_session_ids:
                self._sessions.pop(session_id, None)
                self._session_locks.pop(session_id, None)
        return deleted

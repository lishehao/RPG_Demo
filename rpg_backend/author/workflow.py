from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from typing_extensions import TypedDict

from rpg_backend.author.checkpointer import get_author_checkpointer, graph_config
from rpg_backend.author.beat_shards import (
    build_beat_runtime_shard_from_snapshot,
    build_beat_snapshots,
    build_bundle_snapshot,
)
from rpg_backend.author.compiler.beats import build_default_beat_plan_draft
from rpg_backend.author.compiler.brief import focus_brief
from rpg_backend.author.compiler.bundle import build_design_bundle
from rpg_backend.author.compiler.cast import (
    build_cast_member_from_slot,
    derive_cast_overview_draft,
    is_legitimacy_broker_slot,
    plan_cast_topology,
)
from rpg_backend.author.compiler.endings import (
    build_default_ending_intent,
    build_default_ending_rules,
    build_ending_skeleton,
    compile_ending_intent_draft,
    merge_ending_anchor_suggestions,
    normalize_ending_intent_draft,
)
from rpg_backend.author.compiler.router import plan_brief_theme, plan_story_theme
from rpg_backend.author.compiler.rules import (
    build_default_route_affordance_pack,
    build_default_route_opportunity_plan,
    build_default_rule_pack,
    bundle_affordance_tags,
    compile_route_opportunity_plan,
    default_story_function_for_tag,
    merge_rule_pack,
    normalize_ending_rules_draft,
    normalize_route_affordance_pack,
    normalize_rule_pack,
)
from rpg_backend.author.planning import (
    apply_tone_plan_to_beat_plan,
    apply_tone_plan_to_cast_member,
    apply_tone_plan_to_story_frame,
    build_story_flow_plan,
    build_tone_plan,
    coerce_generation_controls,
    coerce_story_flow_plan,
    coerce_tone_plan,
    generation_controls_from_request,
)
from rpg_backend.author.compiler.story import build_default_story_frame_draft
from rpg_backend.author.contracts import (
    AuthorBeatSnapshot,
    AuthorBundleSnapshot,
    AffordanceEffectProfile,
    AuthorBundleRequest,
    BeatPlanDraft,
    BeatRuntimeShard,
    CastDraft,
    CastOverviewDraft,
    DesignBundle,
    EndingIntentDraft,
    EndingRulesDraft,
    FocusedBrief,
    OverviewCastDraft,
    RouteAffordancePackDraft,
    RouteOpportunityPlanDraft,
    StoryFlowPlan,
    StoryGenerationControls,
    StoryFrameDraft,
    TonePlan,
)
from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.author.generation import beats as beat_generation
from rpg_backend.author.generation import cast as cast_generation
from rpg_backend.author.generation import endings as ending_generation
from rpg_backend.author.generation import routes as route_generation
from rpg_backend.author.generation import story_frame as story_generation
from rpg_backend.author.quality.beats import beat_plan_quality_reasons
from rpg_backend.author.quality.cast import (
    cast_member_quality_reasons,
    cast_overview_quality_reasons,
    finalize_cast_member_candidate,
)
from rpg_backend.author.quality.endings import (
    ending_intent_quality_reasons,
    ending_rules_quality_reasons,
)
from rpg_backend.author.quality.routes import route_affordance_pack_quality_reasons
from rpg_backend.author.quality.story import (
    story_frame_quality_reasons,
    story_frame_should_repair,
)
from rpg_backend.author.quality.telemetry import QualityTraceRecord, append_quality_trace
from rpg_backend.config import get_settings
from rpg_backend.llm_gateway import CapabilityGatewayCore, build_gateway_core
from rpg_backend.roster.service import _build_character_roster_service, get_character_roster_service
from rpg_backend.story_profiles import (
    author_theme_from_story_frame_strategy,
    is_generic_author_story_frame_strategy,
    play_runtime_profile_from_bundle,
)


class AuthorState(TypedDict, total=False):
    run_id: str
    raw_brief: str
    language: str
    preview_mode: bool
    generation_controls: StoryGenerationControls
    focused_brief: FocusedBrief
    story_flow_plan: StoryFlowPlan
    resolved_tone_plan: TonePlan
    author_session_response_id: str
    story_frame_draft: StoryFrameDraft
    cast_overview_draft: CastOverviewDraft
    cast_overview_source: str
    cast_member_drafts: list[OverviewCastDraft]
    cast_draft: CastDraft
    cast_topology: str
    cast_topology_reason: str
    brief_primary_theme: str
    brief_theme_modifiers: list[str]
    brief_theme_router_reason: str
    story_frame_strategy: str
    cast_strategy: str
    primary_theme: str
    theme_modifiers: list[str]
    theme_router_reason: str
    beat_plan_strategy: str
    beat_plan_draft: BeatPlanDraft
    story_frame_source: str
    beat_plan_source: str
    route_opportunity_plan_source: str
    route_affordance_source: str
    ending_source: str
    gameplay_semantics_source: str
    roster_catalog_version: str | None
    roster_enabled: bool
    roster_retrieval_trace: list[dict[str, Any]]
    quality_trace: list[QualityTraceRecord]
    route_opportunity_plan_draft: RouteOpportunityPlanDraft
    route_affordance_pack_draft: RouteAffordancePackDraft
    ending_intent_draft: EndingIntentDraft
    ending_rules_draft: EndingRulesDraft
    beat_runtime_shards: list[BeatRuntimeShard]
    beat_snapshots: list[AuthorBeatSnapshot]
    bundle_snapshot: AuthorBundleSnapshot
    beat_runtime_shard_source: str
    beat_runtime_shard_elapsed_ms: int
    beat_runtime_shard_fallback_count: int
    beat_runtime_shard_drift_distribution: dict[str, int]
    beat_runtime_shard_quality_trace: list[QualityTraceRecord]
    design_bundle: DesignBundle
    llm_call_trace: list[dict[str, Any]]


_FALLBACKABLE_GENERATION_ERROR_CODES = {
    "llm_invalid_json",
    "llm_schema_invalid",
    "llm_provider_failed",
    "gateway_text_provider_failed",
}


def _should_fallback_generation_error(exc: AuthorGatewayError) -> bool:
    return exc.code in _FALLBACKABLE_GENERATION_ERROR_CODES


def _cast_stage_budget_seconds(state: AuthorState) -> float:
    flow_plan = coerce_story_flow_plan(state.get("story_flow_plan"))
    target_duration_minutes = flow_plan.target_duration_minutes if flow_plan is not None else 15
    if target_duration_minutes <= 15:
        return 45.0
    if target_duration_minutes <= 17:
        return 50.0
    return 60.0


def _cast_stage_budget_exhausted(started_at: float, *, state: AuthorState) -> bool:
    return (perf_counter() - started_at) >= _cast_stage_budget_seconds(state)


def _notify_progress(
    progress_observer: Callable[..., None] | None,
    *,
    running_node: str,
    running_substage: str,
    running_slot_index: int | None = None,
    running_slot_total: int | None = None,
    running_slot_label: str | None = None,
    running_capability: str | None = None,
) -> None:
    if progress_observer is None:
        return
    progress_observer(
        running_node=running_node,
        running_substage=running_substage,
        running_slot_index=running_slot_index,
        running_slot_total=running_slot_total,
        running_slot_label=running_slot_label,
        running_capability=running_capability,
    )


def _resolved_session_response_id(
    prior_response_id: str | None,
    next_response_id: str | None,
) -> str | None:
    return next_response_id or prior_response_id


def _rule_pack_primary_pressure_axes(bundle: DesignBundle) -> list[str]:
    pressure_axes = {axis.axis_id for axis in bundle.state_schema.axes if axis.kind == "pressure"}
    return [
        axis_id
        for profile in bundle.rule_pack.affordance_effect_profiles
        for axis_id, delta in profile.axis_deltas.items()
        if delta > 0 and axis_id in pressure_axes
    ]


def _gameplay_semantics_quality_reasons(bundle: DesignBundle) -> list[str]:
    reasons: list[str] = []
    pressure_axes = _rule_pack_primary_pressure_axes(bundle)
    if pressure_axes and len(set(pressure_axes)) < 2:
        reasons.append("single_pressure_axis_dominance")
    meaningful_profiles = [
        profile
        for profile in bundle.rule_pack.affordance_effect_profiles
        if profile.axis_deltas or profile.stance_deltas
    ]
    if len(meaningful_profiles) < 4:
        reasons.append("thin_affordance_semantics")
    ending_ids = {rule.ending_id for rule in bundle.rule_pack.ending_rules}
    if len(ending_ids) < 3:
        reasons.append("ending_rule_coverage_narrow")
    distinct_trigger_axes = {
        axis_id
        for rule in bundle.rule_pack.ending_rules
        for axis_id in rule.conditions.min_axes
    }
    if distinct_trigger_axes and len(distinct_trigger_axes) < 2:
        reasons.append("ending_axis_collapse")
    return reasons


_CONTEXT_LOCK_REASON_CODES = {
    "context_hash_mismatch",
    "snapshot_invariant_violation",
    "out_of_scope_reference",
    "binding_scaffold_drift",
    "beat_runtime_shard_fallback",
}


def _annotate_author_llm_trace_with_context_locks(
    llm_call_trace: list[dict[str, Any]],
    state: AuthorState,
) -> list[dict[str, Any]]:
    bundle_snapshot = state.get("bundle_snapshot")
    annotated: list[dict[str, Any]] = []
    for item in list(llm_call_trace or []):
        updated = dict(item)
        capability = str(updated.get("capability") or "")
        if capability == "author.rulepack_generate" and bundle_snapshot is not None:
            updated["snapshot_id"] = bundle_snapshot.snapshot_id
            updated["context_hash"] = bundle_snapshot.context_hash
            updated["required_invariants"] = dict(bundle_snapshot.required_invariants)
            updated["context_lock_status"] = "locked"
            updated["snapshot_stage"] = "bundle_snapshot"
        else:
            updated.setdefault("snapshot_id", None)
            updated.setdefault("context_hash", None)
            updated.setdefault("required_invariants", {})
            updated.setdefault("context_lock_status", "unlocked")
            updated.setdefault("snapshot_stage", "pre_parallel")
        annotated.append(updated)
    return annotated


def _parallel_beat_shard_worker_limit(bundle: DesignBundle) -> int:
    return max(1, min(len(bundle.beat_spine), 4))


def _repaired_affordance_profiles(bundle: DesignBundle) -> list[AffordanceEffectProfile]:
    runtime_profile = play_runtime_profile_from_bundle(bundle).runtime_policy_profile
    axes_by_id = {axis.axis_id: axis for axis in bundle.state_schema.axes}
    pressure_axis_id = next((axis.axis_id for axis in bundle.state_schema.axes if axis.kind == "pressure"), bundle.state_schema.axes[0].axis_id)
    public_axis_id = "public_panic" if "public_panic" in axes_by_id else pressure_axis_id
    resource_axis_id = "resource_strain" if "resource_strain" in axes_by_id else next((axis.axis_id for axis in bundle.state_schema.axes if axis.kind == "resource"), pressure_axis_id)
    leverage_axis_id = "political_leverage" if "political_leverage" in axes_by_id else next((axis.axis_id for axis in bundle.state_schema.axes if axis.kind == "relationship"), pressure_axis_id)
    support_axis_id = "ally_trust" if "ally_trust" in axes_by_id else leverage_axis_id
    exposure_axis_id = "exposure_risk" if "exposure_risk" in axes_by_id else pressure_axis_id
    institutional_axis_id = "system_integrity" if "system_integrity" in axes_by_id else exposure_axis_id
    authored_by_tag = {profile.affordance_tag: profile for profile in bundle.rule_pack.affordance_effect_profiles}
    repaired: list[AffordanceEffectProfile] = []
    for tag in bundle_affordance_tags(bundle):
        authored = authored_by_tag.get(tag)
        axis_deltas: dict[str, int]
        if tag == "reveal_truth":
            if runtime_profile == "warning_record_play":
                axis_deltas = {exposure_axis_id: 1}
            elif runtime_profile == "archive_vote_play":
                axis_deltas = {institutional_axis_id: 1}
            elif runtime_profile in {"bridge_ration_play", "harbor_quarantine_play"}:
                axis_deltas = {resource_axis_id: 1}
            elif runtime_profile in {"blackout_council_play", "public_order_play"}:
                axis_deltas = {public_axis_id: 1}
            else:
                axis_deltas = {exposure_axis_id: 1}
        elif tag in {"build_trust", "unlock_ally"}:
            axis_deltas = {support_axis_id: 1}
        elif tag in {"contain_chaos", "protect_civilians"}:
            axis_deltas = {public_axis_id: -1, leverage_axis_id: 1}
        elif tag == "secure_resources":
            axis_deltas = {resource_axis_id: -1, leverage_axis_id: 1}
        elif tag == "shift_public_narrative":
            axis_deltas = {leverage_axis_id: 1}
        elif tag == "pay_cost":
            axis_deltas = {pressure_axis_id: 1, public_axis_id: 1}
        else:
            axis_deltas = {pressure_axis_id: 1}
        repaired.append(
            AffordanceEffectProfile(
                affordance_tag=tag,
                default_story_function=(authored.default_story_function if authored is not None else default_story_function_for_tag(tag)),  # type: ignore[arg-type]
                axis_deltas=axis_deltas,
                stance_deltas=(authored.stance_deltas if authored is not None else {}),
                can_add_truth=bool(authored.can_add_truth if authored is not None else tag == "reveal_truth"),
                can_add_event=bool(authored.can_add_event if authored is not None else tag in {"shift_public_narrative", "pay_cost", "secure_resources"}),
            )
        )
    return repaired


def _repair_gameplay_semantics_bundle(bundle: DesignBundle) -> DesignBundle:
    normalized_route_affordance_pack = normalize_route_affordance_pack(
        RouteAffordancePackDraft(
            route_unlock_rules=bundle.rule_pack.route_unlock_rules,
            affordance_effect_profiles=_repaired_affordance_profiles(bundle),
        ),
        bundle,
    )
    normalized_endings = normalize_ending_rules_draft(
        EndingRulesDraft(ending_rules=bundle.rule_pack.ending_rules),
        bundle,
    )
    if len({rule.ending_id for rule in normalized_endings.ending_rules}) < 3:
        normalized_endings = build_default_ending_rules(bundle)
    repaired_rule_pack = merge_rule_pack(normalized_route_affordance_pack, normalized_endings)
    return bundle.model_copy(update={"rule_pack": repaired_rule_pack})


def build_author_graph(
    *,
    gateway: CapabilityGatewayCore | None = None,
    checkpointer=None,
    progress_observer: Callable[..., None] | None = None,
):
    resolved_gateway = gateway or build_gateway_core(get_settings())

    def _controls(state: AuthorState) -> StoryGenerationControls | None:
        return coerce_generation_controls(state.get("generation_controls"))

    def _flow_plan(state: AuthorState) -> StoryFlowPlan | None:
        return coerce_story_flow_plan(state.get("story_flow_plan"))

    def _tone_plan(state: AuthorState) -> TonePlan | None:
        return coerce_tone_plan(state.get("resolved_tone_plan"))

    def focus_brief_node(state: AuthorState) -> dict[str, Any]:
        if state.get("focused_brief") is not None:
            return {"focused_brief": state["focused_brief"]}
        return {
            "focused_brief": focus_brief(
                state["raw_brief"],
                language=str(state.get("language") or "en"),
            )
        }

    def generate_story_frame_node(state: AuthorState) -> dict[str, Any]:
        prior_response_id = state.get("author_session_response_id")
        latest_response_id = prior_response_id
        trace = state.get("quality_trace")
        _notify_progress(
            progress_observer,
            running_node="generate_story_frame",
            running_substage="story_frame_generate",
            running_capability="author.story_frame_scaffold",
        )
        try:
            generated = story_generation.generate_story_frame(
                resolved_gateway,
                state["focused_brief"],
                previous_response_id=prior_response_id,
                story_frame_strategy=state.get("story_frame_strategy"),
                story_flow_plan=_flow_plan(state),
                tone_plan=_tone_plan(state),
                preview_mode=bool(state.get("preview_mode")),
            )
        except AuthorGatewayError as exc:
            if not _should_fallback_generation_error(exc):
                raise
            story_frame_draft = build_default_story_frame_draft(state["focused_brief"])
            trace = append_quality_trace(
                trace,
                stage="story_frame",
                source="default",
                outcome="fallback",
                reasons=[exc.code],
            )
            return {
                "story_frame_draft": apply_tone_plan_to_story_frame(
                    story_frame_draft,
                    controls=_controls(state),
                    tone_plan=_tone_plan(state),
                ),
                "story_frame_source": "default",
                "author_session_response_id": latest_response_id,
                "quality_trace": trace,
            }
        story_frame_draft = apply_tone_plan_to_story_frame(
            generated.value,
            controls=_controls(state),
            tone_plan=_tone_plan(state),
        )
        latest_response_id = _resolved_session_response_id(prior_response_id, generated.response_id)
        story_frame_source = "generated"
        story_frame_outcome = "accepted"
        story_frame_reasons = story_frame_quality_reasons(story_frame_draft, state["focused_brief"])
        if bool(state.get("preview_mode")) and story_frame_should_repair(story_frame_reasons):
            story_frame_reasons.append("preview_skipped_story_frame_repair")
        elif story_frame_should_repair(story_frame_reasons):
            _notify_progress(
                progress_observer,
                running_node="generate_story_frame",
                running_substage="story_frame_repair",
                running_capability="author.story_frame_finalize",
            )
            try:
                gleaned = story_generation.glean_story_frame(
                    resolved_gateway,
                    state["focused_brief"],
                    story_frame_draft,
                    previous_response_id=latest_response_id,
                )
                latest_response_id = _resolved_session_response_id(latest_response_id, gleaned.response_id)
                glean_reasons = story_frame_quality_reasons(gleaned.value, state["focused_brief"])
                if not story_frame_should_repair(glean_reasons):
                    story_frame_draft = apply_tone_plan_to_story_frame(
                        gleaned.value,
                        controls=_controls(state),
                        tone_plan=_tone_plan(state),
                    )
                    story_frame_source = "gleaned"
                    story_frame_outcome = "repaired"
                else:
                    story_frame_draft = apply_tone_plan_to_story_frame(
                        build_default_story_frame_draft(state["focused_brief"]),
                        controls=_controls(state),
                        tone_plan=_tone_plan(state),
                    )
                    story_frame_source = "default"
                    story_frame_outcome = "fallback"
                    story_frame_reasons.extend(glean_reasons)
            except AuthorGatewayError as exc:
                if not _should_fallback_generation_error(exc):
                    raise
                _notify_progress(
                    progress_observer,
                    running_node="generate_story_frame",
                    running_substage="story_frame_default_fallback",
                )
                story_frame_draft = apply_tone_plan_to_story_frame(
                    build_default_story_frame_draft(state["focused_brief"]),
                    controls=_controls(state),
                    tone_plan=_tone_plan(state),
                )
                story_frame_source = "default"
                story_frame_outcome = "fallback"
                story_frame_reasons.append(exc.code)
        trace = append_quality_trace(
            trace,
            stage="story_frame",
            source=story_frame_source,  # type: ignore[arg-type]
            outcome=story_frame_outcome,  # type: ignore[arg-type]
            reasons=story_frame_reasons if story_frame_outcome != "accepted" else [],
        )
        return {
            "story_frame_draft": story_frame_draft,
            "story_frame_source": story_frame_source,
            "author_session_response_id": latest_response_id,
            "quality_trace": trace,
        }

    def derive_cast_overview_node(state: AuthorState) -> dict[str, Any]:
        resolved_story_flow_plan = _flow_plan(state)
        preferred_cast_count = (
            resolved_story_flow_plan.recommended_cast_count
            if resolved_story_flow_plan is not None
            else None
        )
        _notify_progress(
            progress_observer,
            running_node="derive_cast_overview",
            running_substage="cast_topology_plan",
        )
        topology_plan = plan_cast_topology(
            state["focused_brief"],
            state["story_frame_draft"],
            preferred_count=preferred_cast_count,
        )
        topology_reason = state.get("cast_topology_reason") or topology_plan.planner_reason
        _notify_progress(
            progress_observer,
            running_node="derive_cast_overview",
            running_substage="cast_overview_compile",
        )
        cast_overview = derive_cast_overview_draft(
            state["focused_brief"],
            state["story_frame_draft"],
            topology_override=state.get("cast_topology") or topology_plan.topology,
        )
        trace = append_quality_trace(
            state.get("quality_trace"),
            stage="cast_overview",
            source="default",
            outcome="accepted",
            reasons=[],
            subject=topology_plan.topology,
        )
        return {
            "cast_overview_draft": cast_overview,
            "cast_overview_source": "default",
            "cast_topology": state.get("cast_topology") or topology_plan.topology,
            "cast_topology_reason": topology_reason,
            "quality_trace": trace,
        }

    def plan_story_theme_node(state: AuthorState) -> dict[str, Any]:
        if state.get("primary_theme") and state.get("cast_strategy") and state.get("beat_plan_strategy"):
            return {
                "primary_theme": state["primary_theme"],
                "theme_modifiers": list(state.get("theme_modifiers") or []),
                "theme_router_reason": state.get("theme_router_reason") or "preview_locked_theme",
                "cast_strategy": state["cast_strategy"],
                "beat_plan_strategy": state["beat_plan_strategy"],
            }
        _notify_progress(
            progress_observer,
            running_node="plan_story_theme",
            running_substage="theme_route_lock",
        )
        decision = plan_story_theme(
            state["focused_brief"],
            state["story_frame_draft"],
        )
        current_primary_theme = str(state.get("primary_theme") or decision.primary_theme)
        current_modifiers = list(state.get("theme_modifiers") or list(decision.modifiers))
        current_router_reason = str(state.get("theme_router_reason") or decision.router_reason)
        story_frame_strategy = str(state.get("story_frame_strategy") or "")
        brief_primary_theme = str(state.get("brief_primary_theme") or current_primary_theme)
        locked_decision = author_theme_from_story_frame_strategy(
            story_frame_strategy,
            modifiers=tuple(current_modifiers),
            router_reason=current_router_reason or "preview_locked_theme",
        )
        if (
            locked_decision is not None
            and not is_generic_author_story_frame_strategy(story_frame_strategy)
            and brief_primary_theme == current_primary_theme == locked_decision.primary_theme
        ):
            return {
                "primary_theme": current_primary_theme,
                "theme_modifiers": current_modifiers,
                "theme_router_reason": current_router_reason,
                "cast_strategy": state.get("cast_strategy") or locked_decision.cast_strategy,
                "beat_plan_strategy": state.get("beat_plan_strategy") or locked_decision.beat_plan_strategy,
            }
        return {
            "primary_theme": current_primary_theme,
            "theme_modifiers": current_modifiers,
            "theme_router_reason": current_router_reason,
            "cast_strategy": state.get("cast_strategy") or decision.cast_strategy,
            "beat_plan_strategy": state.get("beat_plan_strategy") or decision.beat_plan_strategy,
        }

    def plan_brief_theme_node(state: AuthorState) -> dict[str, Any]:
        if state.get("story_frame_strategy") and state.get("cast_strategy") and state.get("brief_primary_theme"):
            return {
                "brief_primary_theme": state["brief_primary_theme"],
                "brief_theme_modifiers": list(state.get("brief_theme_modifiers") or []),
                "brief_theme_router_reason": state.get("brief_theme_router_reason") or "preview_locked_theme",
                "story_frame_strategy": state["story_frame_strategy"],
                "cast_strategy": state["cast_strategy"],
                "primary_theme": state.get("primary_theme") or state["brief_primary_theme"],
                "theme_modifiers": list(state.get("theme_modifiers") or state.get("brief_theme_modifiers") or []),
                "theme_router_reason": state.get("theme_router_reason") or state.get("brief_theme_router_reason") or "preview_locked_theme",
                "beat_plan_strategy": state.get("beat_plan_strategy") or "conservative_direct_draft",
            }
        _notify_progress(
            progress_observer,
            running_node="plan_brief_theme",
            running_substage="theme_route_lock",
        )
        decision = plan_brief_theme(state["focused_brief"])
        return {
            "brief_primary_theme": decision.primary_theme,
            "brief_theme_modifiers": list(decision.modifiers),
            "brief_theme_router_reason": decision.router_reason,
            "story_frame_strategy": decision.story_frame_strategy,
            "primary_theme": decision.primary_theme,
            "theme_modifiers": list(decision.modifiers),
            "theme_router_reason": decision.router_reason,
        }

    def plan_generation_intent_node(state: AuthorState) -> dict[str, Any]:
        controls = _controls(state) or StoryGenerationControls()
        return {
            "generation_controls": controls,
            "story_flow_plan": build_story_flow_plan(
                controls=controls,
                primary_theme=state.get("brief_primary_theme") or state.get("primary_theme"),
            ),
            "resolved_tone_plan": build_tone_plan(
                focused_brief=state["focused_brief"],
                controls=controls,
            ),
        }

    def generate_cast_members_node(state: AuthorState) -> dict[str, Any]:
        prior_response_id = state.get("author_session_response_id")
        latest_response_id = prior_response_id
        existing_members = list(state.get("cast_member_drafts") or [])
        resolved_members: dict[int, OverviewCastDraft] = {
            index: member for index, member in enumerate(existing_members)
        }
        slots = list(state["cast_overview_draft"].cast_slots)
        trace = list(state.get("quality_trace") or [])
        cast_stage_started_at = perf_counter()
        gateway_core = getattr(gateway, "core", None)
        roster_service = (
            _build_character_roster_service(get_settings(), gateway_core=gateway_core)
            if gateway_core is not None
            else get_character_roster_service()
        )
        _notify_progress(
            progress_observer,
            running_node="generate_cast_members",
            running_substage="roster_retrieval",
        )
        roster_selection = roster_service.retrieve_for_cast(
            focused_brief=state["focused_brief"],
            story_frame=state["story_frame_draft"],
            cast_overview=state["cast_overview_draft"],
            primary_theme=state.get("primary_theme") or state.get("brief_primary_theme") or "generic_civic_crisis",
            limit=max(len(slots) - 1, 0),
            story_frame_strategy=state.get("story_frame_strategy"),
        )
        roster_assignments = {
            item.slot_index: item
            for item in roster_selection.assignments
        }
        cast_strategy = state.get("cast_strategy") or "generic_civic_cast"
        pending_generation: list[tuple[int, Any, OverviewCastDraft, list[str]]] = []
        for slot_index in range(len(existing_members), len(slots)):
            slot = slots[slot_index]
            existing_names = {
                member.name
                for _index, member in sorted(resolved_members.items(), key=lambda item: item[0])
            }
            if slot_index in roster_assignments:
                _notify_progress(
                    progress_observer,
                    running_node="generate_cast_members",
                    running_substage="roster_projection",
                    running_slot_index=slot_index + 1,
                    running_slot_total=len(slots),
                    running_slot_label=slot.slot_label,
                )
                roster_member = roster_service.build_cast_member(
                    focused_brief=state["focused_brief"],
                    slot=slot,
                    slot_index=slot_index,
                    existing_names=set(existing_names),
                    retrieved=roster_assignments[slot_index],
                )
                trace = append_quality_trace(
                    trace,
                    stage="cast_member",
                    source="default",
                    outcome="accepted",
                    reasons=["roster_retrieved_character", "story_instance_default_materialized"],
                    slot_index=slot_index,
                    subject=slot.slot_label,
                )
                resolved_members[slot_index] = apply_tone_plan_to_cast_member(
                    roster_member,
                    controls=_controls(state),
                    tone_plan=_tone_plan(state),
                    language=state["focused_brief"].language,
                )
                continue
            fallback_member = build_cast_member_from_slot(
                slot,
                state["focused_brief"],
                slot_index,
                set(existing_names),
            )
            if is_legitimacy_broker_slot(cast_strategy, slot):
                trace = append_quality_trace(
                    trace,
                    stage="cast_member",
                    source="default",
                    outcome="accepted",
                    reasons=["router_forced_deterministic_slot"],
                    slot_index=slot_index,
                    subject=slot.slot_label,
                )
                resolved_members[slot_index] = fallback_member
                continue
            pending_generation.append((slot_index, slot, fallback_member, []))

        if len(pending_generation) >= 3 and not _cast_stage_budget_exhausted(cast_stage_started_at, state=state):
            subset_slots = [slot for _slot_index, slot, _fallback_member, _reasons in pending_generation]
            subset_overview = CastOverviewDraft(
                cast_slots=subset_slots,
                relationship_summary=list(state["cast_overview_draft"].relationship_summary)[:6],
            )
            _notify_progress(
                progress_observer,
                running_node="generate_cast_members",
                running_substage="batch_generate_remaining_cast",
                running_slot_index=1,
                running_slot_total=len(pending_generation),
                running_capability="author.cast_member_generate",
            )
            try:
                batch_generated = cast_generation.generate_story_cast(
                    resolved_gateway,
                    state["focused_brief"],
                    state["story_frame_draft"],
                    subset_overview,
                    previous_response_id=latest_response_id,
                    cast_strategy=cast_strategy,
                )
                latest_response_id = _resolved_session_response_id(latest_response_id, batch_generated.response_id)
                batch_candidates = list(batch_generated.value.cast)
            except AuthorGatewayError as exc:
                if not _should_fallback_generation_error(exc):
                    raise
                batch_candidates = []
                pending_generation = [
                    (slot_index, slot, fallback_member, [exc.code, "batch_generate_failed"])
                    for slot_index, slot, fallback_member, _reasons in pending_generation
                ]
            else:
                unresolved_generation: list[tuple[int, Any, OverviewCastDraft, list[str]]] = []
                for batch_index, (slot_index, slot, fallback_member, prior_reasons) in enumerate(pending_generation):
                    existing_names = {
                        member.name
                        for _index, member in sorted(resolved_members.items(), key=lambda item: item[0])
                    }
                    batch_member = batch_candidates[batch_index] if batch_index < len(batch_candidates) else None
                    if batch_member is None:
                        unresolved_generation.append(
                            (slot_index, slot, fallback_member, [*prior_reasons, "batch_generate_missing_slot"])
                        )
                        continue
                    member_reasons = cast_member_quality_reasons(batch_member, existing_names, slot)
                    finalized_member = finalize_cast_member_candidate(
                        batch_member,
                        state["focused_brief"],
                        slot,
                        existing_names,
                    )
                    if finalized_member is None:
                        unresolved_generation.append(
                            (slot_index, slot, fallback_member, [*prior_reasons, *member_reasons, "batch_generate_needs_repair"])
                        )
                        continue
                    trace = append_quality_trace(
                        trace,
                        stage="cast_member",
                        source="generated",
                        outcome="accepted",
                        reasons=[],
                        slot_index=slot_index,
                        subject=slot.slot_label,
                    )
                    resolved_members[slot_index] = apply_tone_plan_to_cast_member(
                        finalized_member,
                        controls=_controls(state),
                        tone_plan=_tone_plan(state),
                        language=state["focused_brief"].language,
                    )
                pending_generation = unresolved_generation

        for pending_position, (slot_index, slot, fallback_member, prior_reasons) in enumerate(pending_generation, start=1):
            if _cast_stage_budget_exhausted(cast_stage_started_at, state=state):
                remaining_pending = pending_generation[pending_position - 1 :]
                for remaining_slot_index, remaining_slot, remaining_fallback, remaining_reasons in remaining_pending:
                    _notify_progress(
                        progress_observer,
                        running_node="generate_cast_members",
                        running_substage="deterministic_fallback",
                        running_slot_index=remaining_slot_index + 1,
                        running_slot_total=len(slots),
                        running_slot_label=remaining_slot.slot_label,
                    )
                    trace = append_quality_trace(
                        trace,
                        stage="cast_member",
                        source="default",
                        outcome="fallback",
                        reasons=[*remaining_reasons, "cast_stage_budget_exhausted"],
                        slot_index=remaining_slot_index,
                        subject=remaining_slot.slot_label,
                    )
                    resolved_members[remaining_slot_index] = apply_tone_plan_to_cast_member(
                        remaining_fallback,
                        controls=_controls(state),
                        tone_plan=_tone_plan(state),
                        language=state["focused_brief"].language,
                    )
                break

            existing_names = {
                member.name
                for _index, member in sorted(resolved_members.items(), key=lambda item: item[0])
            }
            slot_payload = slot.model_dump(mode="json")
            existing_payload = [
                member.model_dump(mode="json")
                for _index, member in sorted(resolved_members.items(), key=lambda item: item[0])
            ]
            member_source = "generated"
            member_outcome = "accepted"
            member_reasons = list(prior_reasons)
            _notify_progress(
                progress_observer,
                running_node="generate_cast_members",
                running_substage="slot_generate",
                running_slot_index=slot_index + 1,
                running_slot_total=len(slots),
                running_slot_label=slot.slot_label,
                running_capability="author.cast_member_generate",
            )
            try:
                generated = cast_generation.generate_story_cast_member(
                    resolved_gateway,
                    state["focused_brief"],
                    state["story_frame_draft"],
                    slot_payload,
                    existing_payload,
                    previous_response_id=latest_response_id,
                    cast_strategy=cast_strategy,
                )
                latest_response_id = _resolved_session_response_id(latest_response_id, generated.response_id)
                member_seed = generated.value
                member_reasons = [*member_reasons, *cast_member_quality_reasons(member_seed, existing_names, slot)]
            except AuthorGatewayError as exc:
                if not _should_fallback_generation_error(exc):
                    raise
                member_seed = fallback_member
                member_source = "default"
                member_outcome = "fallback"
                member_reasons = [*member_reasons, exc.code]

            finalized_member = finalize_cast_member_candidate(
                member_seed,
                state["focused_brief"],
                slot,
                existing_names,
            )
            if finalized_member is None and member_source != "default":
                _notify_progress(
                    progress_observer,
                    running_node="generate_cast_members",
                    running_substage="slot_repair",
                    running_slot_index=slot_index + 1,
                    running_slot_total=len(slots),
                    running_slot_label=slot.slot_label,
                    running_capability="author.cast_member_repair",
                )
                try:
                    gleaned = cast_generation.glean_story_cast_member(
                        resolved_gateway,
                        state["focused_brief"],
                        state["story_frame_draft"],
                        slot_payload,
                        existing_payload,
                        member_seed.model_dump(mode="json"),
                        previous_response_id=latest_response_id,
                        cast_strategy=cast_strategy,
                    )
                    latest_response_id = _resolved_session_response_id(latest_response_id, gleaned.response_id)
                    glean_reasons = cast_member_quality_reasons(gleaned.value, existing_names, slot)
                    finalized_member = finalize_cast_member_candidate(
                        gleaned.value,
                        state["focused_brief"],
                        slot,
                        existing_names,
                    )
                    if finalized_member is not None:
                        member_source = "gleaned"
                        member_outcome = "repaired"
                        member_reasons = [*member_reasons, *glean_reasons]
                    else:
                        member_reasons = [*member_reasons, *glean_reasons]
                except AuthorGatewayError as exc:
                    if not _should_fallback_generation_error(exc):
                        raise
                    member_reasons.append(exc.code)
            if finalized_member is None:
                finalized_member = fallback_member
                member_source = "default"
                member_outcome = "fallback"
                if not member_reasons:
                    member_reasons = cast_member_quality_reasons(member_seed, existing_names, slot)
            trace = append_quality_trace(
                trace,
                stage="cast_member",
                source=member_source,  # type: ignore[arg-type]
                outcome=member_outcome,  # type: ignore[arg-type]
                reasons=member_reasons if member_outcome != "accepted" else [],
                slot_index=slot_index,
                subject=slot.slot_label,
            )
            resolved_members[slot_index] = apply_tone_plan_to_cast_member(
                finalized_member,
                controls=_controls(state),
                tone_plan=_tone_plan(state),
                language=state["focused_brief"].language,
            )

        ordered_members = [
            resolved_members[index]
            for index in range(len(slots))
            if index in resolved_members
        ]
        return {
            "cast_member_drafts": ordered_members,
            "author_session_response_id": latest_response_id,
            "quality_trace": trace,
            "roster_catalog_version": roster_selection.catalog_version,
            "roster_enabled": roster_selection.roster_enabled,
            "roster_retrieval_trace": list(roster_selection.trace),
        }

    def assemble_cast_node(state: AuthorState) -> dict[str, Any]:
        return {
            "cast_draft": CastDraft(cast=list(state.get("cast_member_drafts") or [])),
        }

    def generate_beat_plan_node(state: AuthorState) -> dict[str, Any]:
        _notify_progress(
            progress_observer,
            running_node="generate_beat_plan",
            running_substage="beat_plan_generate",
            running_capability="author.beat_skeleton_generate",
        )
        prior_response_id = state.get("author_session_response_id")
        latest_response_id = prior_response_id
        trace = state.get("quality_trace")
        beat_strategy = state.get("beat_plan_strategy") or "conservative_direct_draft"
        if beat_strategy == "single_semantic_compile":
            beat_plan_generate = beat_generation.generate_beat_plan
        else:
            beat_plan_generate = beat_generation.generate_beat_plan_conservative
        try:
            generated = beat_plan_generate(
                resolved_gateway,
                state["focused_brief"],
                state["story_frame_draft"],
                state["cast_draft"],
                previous_response_id=prior_response_id,
                primary_theme=state.get("primary_theme"),
                beat_plan_strategy=state.get("beat_plan_strategy"),
                story_flow_plan=_flow_plan(state),
                tone_plan=_tone_plan(state),
            )
        except AuthorGatewayError as exc:
            if not _should_fallback_generation_error(exc):
                raise
            _notify_progress(
                progress_observer,
                running_node="generate_beat_plan",
                running_substage="beat_plan_default_fallback",
            )
            return {
                "beat_plan_draft": apply_tone_plan_to_beat_plan(
                    build_default_beat_plan_draft(
                        state["focused_brief"],
                        story_frame=state["story_frame_draft"],
                        cast_draft=state["cast_draft"],
                        story_flow_plan=_flow_plan(state),
                        tone_plan=_tone_plan(state),
                    ),
                    controls=_controls(state),
                    tone_plan=_tone_plan(state),
                    language=state["focused_brief"].language,
                ),
                "beat_plan_source": "default",
                "quality_trace": append_quality_trace(
                    trace,
                    stage="beat_plan",
                    source="default",
                    outcome="fallback",
                    reasons=[exc.code],
                ),
            }
        latest_response_id = _resolved_session_response_id(prior_response_id, generated.response_id)
        beat_plan_draft = apply_tone_plan_to_beat_plan(
            generated.value,
            controls=_controls(state),
            tone_plan=_tone_plan(state),
            language=state["focused_brief"].language,
        )
        beat_plan_source = "generated"
        beat_plan_outcome = "accepted"
        beat_plan_reasons = beat_plan_quality_reasons(
            beat_plan_draft,
            state["story_frame_draft"],
            state["cast_draft"],
        )
        if beat_plan_reasons:
            _notify_progress(
                progress_observer,
                running_node="generate_beat_plan",
                running_substage="beat_plan_repair",
                running_capability="author.beat_repair",
            )
            try:
                gleaned = beat_generation.glean_beat_plan(
                    resolved_gateway,
                    state["focused_brief"],
                    state["story_frame_draft"],
                    state["cast_draft"],
                    beat_plan_draft,
                    previous_response_id=latest_response_id,
                    primary_theme=state.get("primary_theme"),
                    beat_plan_strategy=state.get("beat_plan_strategy"),
                    story_flow_plan=_flow_plan(state),
                    tone_plan=_tone_plan(state),
                )
                latest_response_id = _resolved_session_response_id(latest_response_id, gleaned.response_id)
                glean_reasons = beat_plan_quality_reasons(
                    gleaned.value,
                    state["story_frame_draft"],
                    state["cast_draft"],
                )
                if not glean_reasons:
                    beat_plan_draft = gleaned.value
                    beat_plan_source = "gleaned"
                    beat_plan_outcome = "repaired"
                else:
                    beat_plan_draft = apply_tone_plan_to_beat_plan(
                        build_default_beat_plan_draft(
                            state["focused_brief"],
                            story_frame=state["story_frame_draft"],
                            cast_draft=state["cast_draft"],
                            story_flow_plan=_flow_plan(state),
                            tone_plan=_tone_plan(state),
                        ),
                        controls=_controls(state),
                        tone_plan=_tone_plan(state),
                        language=state["focused_brief"].language,
                    )
                    beat_plan_source = "default"
                    beat_plan_outcome = "fallback"
                    beat_plan_reasons.extend(glean_reasons)
            except AuthorGatewayError as exc:
                if not _should_fallback_generation_error(exc):
                    raise
                _notify_progress(
                    progress_observer,
                    running_node="generate_beat_plan",
                    running_substage="beat_plan_default_fallback",
                )
                beat_plan_draft = apply_tone_plan_to_beat_plan(
                    build_default_beat_plan_draft(
                        state["focused_brief"],
                        story_frame=state["story_frame_draft"],
                        cast_draft=state["cast_draft"],
                        story_flow_plan=_flow_plan(state),
                        tone_plan=_tone_plan(state),
                    ),
                    controls=_controls(state),
                    tone_plan=_tone_plan(state),
                    language=state["focused_brief"].language,
                )
                beat_plan_source = "default"
                beat_plan_outcome = "fallback"
                beat_plan_reasons.append(exc.code)
        trace = append_quality_trace(
            trace,
            stage="beat_plan",
            source=beat_plan_source,  # type: ignore[arg-type]
            outcome=beat_plan_outcome,  # type: ignore[arg-type]
            reasons=beat_plan_reasons if beat_plan_outcome != "accepted" else [],
        )
        return {
            "beat_plan_draft": beat_plan_draft,
            "beat_plan_source": beat_plan_source,
            "author_session_response_id": latest_response_id,
            "quality_trace": trace,
        }

    def build_design_bundle_node(state: AuthorState) -> dict[str, Any]:
        bundle = build_design_bundle(
            state["story_frame_draft"],
            state["cast_draft"],
            state["beat_plan_draft"],
            state["focused_brief"],
            generation_controls=_controls(state),
            story_flow_plan=_flow_plan(state),
            resolved_tone_plan=_tone_plan(state),
        )
        bundle_snapshot = build_bundle_snapshot(
            bundle=bundle,
            primary_theme=state.get("primary_theme") or state.get("brief_primary_theme") or "generic_civic_crisis",
            story_frame_strategy=str(state.get("story_frame_strategy") or ""),
            cast_strategy=str(state.get("cast_strategy") or ""),
            beat_plan_strategy=str(state.get("beat_plan_strategy") or ""),
        )
        beat_snapshots = build_beat_snapshots(
            bundle=bundle,
            bundle_snapshot=bundle_snapshot,
        )
        return {
            "design_bundle": bundle,
            "bundle_snapshot": bundle_snapshot,
            "beat_snapshots": beat_snapshots,
        }

    def generate_beat_runtime_shards_node(state: AuthorState) -> dict[str, Any]:
        bundle = state["design_bundle"]
        beat_snapshots = list(state.get("beat_snapshots") or [])
        if not beat_snapshots:
            return {
                "beat_runtime_shards": [],
                "beat_runtime_shard_source": "default",
                "beat_runtime_shard_elapsed_ms": 0,
                "beat_runtime_shard_fallback_count": 0,
                "beat_runtime_shard_drift_distribution": {},
                "beat_runtime_shard_quality_trace": [],
            }
        started_at = perf_counter()
        ordered_shards: list[BeatRuntimeShard | None] = [None] * len(beat_snapshots)
        quality_trace: list[QualityTraceRecord] = []
        drift_distribution: dict[str, int] = {}
        fallback_count = 0
        with ThreadPoolExecutor(max_workers=_parallel_beat_shard_worker_limit(bundle)) as executor:
            futures = {
                executor.submit(build_beat_runtime_shard_from_snapshot, snapshot): index
                for index, snapshot in enumerate(beat_snapshots)
            }
            for future in as_completed(futures):
                index = futures[future]
                snapshot = beat_snapshots[index]
                shard, elapsed_ms, reasons = future.result()
                ordered_shards[index] = shard
                if shard.fallback_reason:
                    fallback_count += 1
                for reason in reasons:
                    drift_distribution[reason] = drift_distribution.get(reason, 0) + 1
                quality_trace = append_quality_trace(
                    quality_trace,
                    stage="beat_runtime_shard",
                    source="default" if shard.fallback_reason else "generated",
                    outcome="fallback" if shard.fallback_reason else "accepted",
                    reasons=[*reasons, *(["beat_runtime_shard_fallback"] if shard.fallback_reason else [])],
                    subject=snapshot.beat_id,
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_stage="beat_snapshot",
                    elapsed_ms=elapsed_ms,
                )
        return {
            "beat_runtime_shards": [item for item in ordered_shards if item is not None],
            "beat_runtime_shard_source": "generated" if fallback_count == 0 else "default",
            "beat_runtime_shard_elapsed_ms": max(int((perf_counter() - started_at) * 1000), 0),
            "beat_runtime_shard_fallback_count": fallback_count,
            "beat_runtime_shard_drift_distribution": drift_distribution,
            "beat_runtime_shard_quality_trace": quality_trace,
        }

    def generate_route_opportunity_plan_node(state: AuthorState) -> dict[str, Any]:
        _notify_progress(
            progress_observer,
            running_node="generate_route_opportunity_plan",
            running_substage="route_generate",
            running_capability="author.rulepack_generate",
        )
        design_bundle = state["design_bundle"]
        prior_response_id = state.get("author_session_response_id")
        try:
            generated = route_generation.generate_route_opportunity_plan_result(
                resolved_gateway,
                design_bundle,
                previous_response_id=prior_response_id,
                primary_theme=state.get("primary_theme"),
            )
        except AuthorGatewayError as exc:
            if not _should_fallback_generation_error(exc):
                raise
            _notify_progress(
                progress_observer,
                running_node="generate_route_opportunity_plan",
                running_substage="route_default_fallback",
            )
            return {
                "route_opportunity_plan_draft": build_default_route_opportunity_plan(design_bundle),
                "route_opportunity_plan_source": "default",
                "quality_trace": append_quality_trace(
                    state.get("quality_trace"),
                    stage="route_affordance",
                    source="default",
                    outcome="fallback",
                    reasons=[exc.code],
                ),
            }
        return {
            "route_opportunity_plan_draft": generated.value,
            "route_opportunity_plan_source": "generated",
            "author_session_response_id": _resolved_session_response_id(prior_response_id, generated.response_id),
        }

    def compile_route_affordance_pack_node(state: AuthorState) -> dict[str, Any]:
        _notify_progress(
            progress_observer,
            running_node="compile_route_affordance_pack",
            running_substage="route_compile",
        )
        design_bundle = state["design_bundle"]
        route_affordance_pack = compile_route_opportunity_plan(
            state["route_opportunity_plan_draft"],
            design_bundle,
        )
        route_affordance_source = "compiled" if state.get("route_opportunity_plan_source") == "generated" else "default"
        trace = state.get("quality_trace")
        route_quality_reasons = route_affordance_pack_quality_reasons(route_affordance_pack, design_bundle)
        if route_quality_reasons:
            _notify_progress(
                progress_observer,
                running_node="compile_route_affordance_pack",
                running_substage="route_default_fallback",
            )
            route_affordance_pack = build_default_route_affordance_pack(design_bundle)
            route_affordance_source = "default"
            trace = append_quality_trace(
                trace,
                stage="route_affordance",
                source=route_affordance_source,
                outcome="fallback",
                reasons=route_quality_reasons,
            )
        elif state.get("route_opportunity_plan_source") == "generated":
            trace = append_quality_trace(
                trace,
                stage="route_affordance",
                source=route_affordance_source,
                outcome="accepted",
                reasons=[],
            )
        return {
            "route_affordance_pack_draft": route_affordance_pack,
            "route_affordance_source": route_affordance_source,
            "quality_trace": trace,
        }

    def generate_ending_rules_node(state: AuthorState) -> dict[str, Any]:
        _notify_progress(
            progress_observer,
            running_node="generate_ending_rules",
            running_substage="ending_generate",
            running_capability="author.rulepack_generate",
        )
        design_bundle = state["design_bundle"]
        prior_response_id = state.get("author_session_response_id")
        latest_response_id = prior_response_id
        trace = state.get("quality_trace")
        skeleton = build_ending_skeleton(design_bundle)
        try:
            generated = ending_generation.generate_ending_anchor_suggestions(
                resolved_gateway,
                design_bundle,
                previous_response_id=prior_response_id,
                primary_theme=state.get("primary_theme"),
            )
        except AuthorGatewayError as exc:
            if not _should_fallback_generation_error(exc):
                raise
            _notify_progress(
                progress_observer,
                running_node="generate_ending_rules",
                running_substage="ending_default_fallback",
            )
            ending_intent = normalize_ending_intent_draft(
                build_default_ending_intent(design_bundle),
                design_bundle,
            )
            normalized = build_default_ending_rules(design_bundle)
            trace = append_quality_trace(
                trace,
                stage="ending",
                source="default",
                outcome="fallback",
                reasons=[exc.code],
            )
            return {
                "ending_intent_draft": ending_intent,
                "ending_rules_draft": normalized,
                "ending_source": "default",
                "quality_trace": trace,
            }
        latest_response_id = _resolved_session_response_id(prior_response_id, generated.response_id)
        ending_intent = merge_ending_anchor_suggestions(
            skeleton,
            generated.value,
            design_bundle,
        )
        ending_source = "generated"
        ending_outcome = "accepted"
        ending_reasons = ending_intent_quality_reasons(ending_intent, design_bundle)
        if ending_reasons:
            _notify_progress(
                progress_observer,
                running_node="generate_ending_rules",
                running_substage="ending_repair",
                running_capability="author.rulepack_generate",
            )
            try:
                gleaned = ending_generation.glean_ending_anchor_suggestions(
                    resolved_gateway,
                    design_bundle,
                    generated.value,
                    previous_response_id=latest_response_id,
                    primary_theme=state.get("primary_theme"),
                )
                latest_response_id = _resolved_session_response_id(latest_response_id, gleaned.response_id)
                ending_intent = merge_ending_anchor_suggestions(
                    skeleton,
                    gleaned.value,
                    design_bundle,
                )
                glean_reasons = ending_intent_quality_reasons(ending_intent, design_bundle)
                if not glean_reasons:
                    ending_source = "gleaned"
                    ending_outcome = "repaired"
                else:
                    ending_reasons.extend(glean_reasons)
            except AuthorGatewayError as exc:
                if not _should_fallback_generation_error(exc):
                    raise
                ending_reasons.append(exc.code)
            if ending_intent_quality_reasons(ending_intent, design_bundle):
                _notify_progress(
                    progress_observer,
                    running_node="generate_ending_rules",
                    running_substage="ending_default_fallback",
                )
                ending_intent = normalize_ending_intent_draft(
                    build_default_ending_intent(design_bundle),
                    design_bundle,
                )
                ending_source = "default"
                ending_outcome = "fallback"
        normalized = compile_ending_intent_draft(ending_intent, design_bundle)
        ending_rule_reasons = ending_rules_quality_reasons(normalized, design_bundle)
        if ending_rule_reasons:
            ending_intent = normalize_ending_intent_draft(
                build_default_ending_intent(design_bundle),
                design_bundle,
            )
            normalized = build_default_ending_rules(design_bundle)
            ending_source = "default"
            ending_outcome = "fallback"
            ending_reasons.extend(ending_rule_reasons)
        trace = append_quality_trace(
            trace,
            stage="ending",
            source=ending_source,  # type: ignore[arg-type]
            outcome=ending_outcome,  # type: ignore[arg-type]
            reasons=ending_reasons,
        )
        return {
            "ending_intent_draft": ending_intent,
            "ending_rules_draft": normalized,
            "ending_source": ending_source,
            "author_session_response_id": latest_response_id,
            "quality_trace": trace,
        }

    def merge_parallel_author_outputs_node(state: AuthorState) -> dict[str, Any]:
        design_bundle = state["design_bundle"]
        rule_pack = merge_rule_pack(
            state["route_affordance_pack_draft"],
            state["ending_rules_draft"],
        )
        merged_trace = [*list(state.get("quality_trace") or []), *list(state.get("beat_runtime_shard_quality_trace") or [])]
        return {
            "design_bundle": design_bundle.model_copy(
                update={
                    "rule_pack": rule_pack,
                    "beat_runtime_shards": list(state.get("beat_runtime_shards") or []),
                }
            ),
            "quality_trace": merged_trace,
        }

    def repair_gameplay_semantics_node(state: AuthorState) -> dict[str, Any]:
        _notify_progress(
            progress_observer,
            running_node="repair_gameplay_semantics",
            running_substage="running",
        )
        design_bundle = state["design_bundle"]
        reasons = _gameplay_semantics_quality_reasons(design_bundle)
        if not reasons:
            return {
                "gameplay_semantics_source": "accepted",
                "quality_trace": append_quality_trace(
                    state.get("quality_trace"),
                    stage="gameplay_semantics",
                    source="compiled",
                    outcome="accepted",
                    reasons=[],
                ),
            }
        repaired_bundle = _repair_gameplay_semantics_bundle(design_bundle)
        return {
            "design_bundle": repaired_bundle,
            "gameplay_semantics_source": "repaired",
            "quality_trace": append_quality_trace(
                state.get("quality_trace"),
                stage="gameplay_semantics",
                source="compiled",
                outcome="repaired",
                reasons=reasons,
            ),
        }

    graph = StateGraph(AuthorState)
    graph.add_node("focus_brief", focus_brief_node)
    graph.add_node("plan_brief_theme", plan_brief_theme_node)
    graph.add_node("plan_generation_intent", plan_generation_intent_node)
    graph.add_node("generate_story_frame", generate_story_frame_node)
    graph.add_node("plan_story_theme", plan_story_theme_node)
    graph.add_node("derive_cast_overview", derive_cast_overview_node)
    graph.add_node("generate_cast_members", generate_cast_members_node)
    graph.add_node("assemble_cast", assemble_cast_node)
    graph.add_node("generate_beat_plan", generate_beat_plan_node)
    graph.add_node("build_design_bundle", build_design_bundle_node)
    graph.add_node("generate_beat_runtime_shards", generate_beat_runtime_shards_node)
    graph.add_node("generate_route_opportunity_plan", generate_route_opportunity_plan_node)
    graph.add_node("compile_route_affordance_pack", compile_route_affordance_pack_node)
    graph.add_node("generate_ending_rules", generate_ending_rules_node)
    graph.add_node("merge_parallel_author_outputs", merge_parallel_author_outputs_node)
    graph.add_node("repair_gameplay_semantics", repair_gameplay_semantics_node)
    graph.add_edge(START, "focus_brief")
    graph.add_edge("focus_brief", "plan_brief_theme")
    graph.add_edge("plan_brief_theme", "plan_generation_intent")
    graph.add_edge("plan_generation_intent", "generate_story_frame")
    graph.add_edge("generate_story_frame", "plan_story_theme")
    graph.add_edge("plan_story_theme", "derive_cast_overview")
    graph.add_edge("derive_cast_overview", "generate_cast_members")
    graph.add_edge("generate_cast_members", "assemble_cast")
    graph.add_edge("assemble_cast", "generate_beat_plan")
    graph.add_edge("generate_beat_plan", "build_design_bundle")
    graph.add_edge("build_design_bundle", "generate_beat_runtime_shards")
    graph.add_edge("build_design_bundle", "generate_route_opportunity_plan")
    graph.add_edge("generate_route_opportunity_plan", "compile_route_affordance_pack")
    graph.add_edge("compile_route_affordance_pack", "generate_ending_rules")
    graph.add_edge(["generate_beat_runtime_shards", "generate_ending_rules"], "merge_parallel_author_outputs")
    graph.add_edge("merge_parallel_author_outputs", "repair_gameplay_semantics")
    graph.add_edge("repair_gameplay_semantics", END)
    return graph.compile(checkpointer=checkpointer or get_author_checkpointer())


def run_author_bundle(request: AuthorBundleRequest, *, gateway: CapabilityGatewayCore | None = None) -> "AuthorBundle":
    resolved_gateway = gateway or build_gateway_core(get_settings())
    if hasattr(resolved_gateway, "call_trace"):
        resolved_gateway.call_trace.clear()
    graph = build_author_graph(gateway=resolved_gateway)
    run_id = str(uuid4())
    state = graph.invoke(
        {
            "run_id": run_id,
            "raw_brief": request.raw_brief,
            "language": request.language,
            "generation_controls": generation_controls_from_request(request),
        },
        config=graph_config(run_id=run_id),
    )
    if hasattr(resolved_gateway, "call_trace"):
        state["llm_call_trace"] = _annotate_author_llm_trace_with_context_locks(
            list(resolved_gateway.call_trace),
            state,
        )
    return AuthorBundle(
        run_id=run_id,
        bundle=state["design_bundle"],
        state=state,
    )

class AuthorBundle(BaseModel):
    run_id: str
    bundle: DesignBundle
    state: AuthorState

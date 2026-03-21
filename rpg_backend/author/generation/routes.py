from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rpg_backend.author.compiler.routes import (
    bundle_affordance_tags,
    default_story_function_for_tag,
    normalize_affordance_tag,
)
from rpg_backend.author.compiler.router import plan_bundle_theme
from rpg_backend.author.generation.context import build_author_context_from_bundle
from rpg_backend.author.generation.runner import invoke_structured_generation_with_retries
from rpg_backend.author.normalize import coerce_int
from rpg_backend.author.contracts import DesignBundle, RouteAffordancePackDraft, RouteOpportunityPlanDraft

if TYPE_CHECKING:
    from rpg_backend.author.gateway import AuthorLLMGateway


def _route_opportunity_output_tokens(gateway: "AuthorLLMGateway", primary_theme: str) -> int:
    budget = gateway.max_output_tokens_rulepack
    if budget is None:
        return 1100 if primary_theme == "legitimacy_crisis" else 900
    floor = 900
    if primary_theme == "legitimacy_crisis":
        floor = 1100
    return max(int(budget), floor)


def _route_theme_guidance(primary_theme: str) -> str:
    mapping = {
        "legitimacy_crisis": "Bias unlock routes toward public mandate, coalition fracture, procedural legitimacy, and settlement leverage.",
        "logistics_quarantine_crisis": "Bias unlock routes toward inspections, quarantine lines, supply chokepoints, and scarcity bargaining.",
        "truth_record_crisis": "Bias unlock routes toward records, testimony, disclosure, and public proof.",
        "public_order_crisis": "Bias unlock routes toward panic control, emergency authority, and visible order.",
        "generic_civic_crisis": "Bias unlock routes toward civic pressure and institutional consequence.",
    }
    return mapping.get(primary_theme, mapping["generic_civic_crisis"])


def _normalize_condition_payload(gateway: "AuthorLLMGateway", conditions: Any) -> dict[str, Any]:
    if not isinstance(conditions, dict):
        conditions = {}
    return {
        "required_events": [str(conditions.get("event")).strip()] if conditions.get("event") else list(conditions.get("required_events") or []),
        "required_truths": list(conditions.get("required_truths") or []),
        "required_flags": list(conditions.get("required_flags") or []),
        "min_axes": {str(k): coerce_int(v, 0) for k, v in dict(conditions.get("min_axes") or {}).items()},
        "max_axes": {str(k): coerce_int(v, 0) for k, v in dict(conditions.get("max_axes") or {}).items()},
        "min_stances": {str(k): coerce_int(v, 0) for k, v in dict(conditions.get("min_stances") or {}).items()},
    }


def _default_route_trigger_payload(bundle: DesignBundle, beat_index: int) -> dict[str, Any]:
    beat = bundle.beat_spine[beat_index]
    if beat.required_truths:
        return {"kind": "truth", "target_id": beat.required_truths[0]}
    if beat_index > 0 and bundle.beat_spine[beat_index - 1].required_events:
        return {"kind": "event", "target_id": bundle.beat_spine[beat_index - 1].required_events[0]}
    if bundle.state_schema.flags:
        return {"kind": "flag", "target_id": bundle.state_schema.flags[0].flag_id}
    if bundle.state_schema.axes:
        return {"kind": "axis", "target_id": bundle.state_schema.axes[0].axis_id, "min_value": 2}
    if bundle.state_schema.stances:
        return {"kind": "stance", "target_id": bundle.state_schema.stances[0].stance_id, "min_value": 1}
    return {"kind": "event", "target_id": beat.required_events[0] if beat.required_events else f"{beat.beat_id}.milestone"}


def _normalize_route_opportunity_plan_payload(
    gateway: "AuthorLLMGateway",
    payload: dict[str, Any],
    bundle: DesignBundle,
) -> dict[str, Any]:
    normalized = dict(payload)
    beats_by_id = {beat.beat_id: beat for beat in bundle.beat_spine}
    beat_order = [beat.beat_id for beat in bundle.beat_spine]
    fallback_beat_id = beat_order[0] if beat_order else "b1"
    affordance_by_beat = {
        beat.beat_id: [item.tag for item in beat.affordances]
        for beat in bundle.beat_spine
    }
    axis_ids = {axis.axis_id for axis in bundle.state_schema.axes}
    stance_ids = {stance.stance_id for stance in bundle.state_schema.stances}
    flag_ids = {flag.flag_id for flag in bundle.state_schema.flags}
    truth_ids = {truth.truth_id for truth in bundle.story_bible.truth_catalog}
    event_ids = {event for beat in bundle.beat_spine for event in beat.required_events}
    opportunities = []
    for item in list(normalized.get("opportunities") or normalized.get("route_opportunities") or [])[:8]:
        if not isinstance(item, dict):
            continue
        beat_id = str(item.get("beat_id") or item.get("target") or "").strip()
        if beat_id not in beats_by_id:
            beat_id = fallback_beat_id
        beat_index = beat_order.index(beat_id) if beat_id in beat_order else 0
        unlock_tag = normalize_affordance_tag(
            item.get("unlock_affordance_tag") or item.get("affordance_tag") or affordance_by_beat.get(beat_id, ["build_trust"])[0]
        )
        trigger_rows = []
        for trigger in list(item.get("triggers") or [])[:2]:
            if not isinstance(trigger, dict):
                continue
            kind = str(trigger.get("kind") or trigger.get("type") or "").strip().casefold()
            kind = {
                "required_truth": "truth",
                "truth_id": "truth",
                "min_axis": "axis",
                "axis_id": "axis",
                "min_stance": "stance",
                "stance_id": "stance",
                "required_flag": "flag",
                "flag_id": "flag",
                "required_event": "event",
                "event_id": "event",
            }.get(kind, kind)
            target_id = str(trigger.get("target_id") or trigger.get("id") or trigger.get("ref") or "").strip()
            min_value = coerce_int(trigger.get("min_value"), 0)
            if kind == "truth" and target_id in truth_ids:
                trigger_rows.append({"kind": "truth", "target_id": target_id})
            elif kind == "axis" and target_id in axis_ids:
                trigger_rows.append({"kind": "axis", "target_id": target_id, "min_value": max(1, min(5, min_value or 2))})
            elif kind == "stance" and target_id in stance_ids:
                trigger_rows.append({"kind": "stance", "target_id": target_id, "min_value": max(1, min(3, min_value or 1))})
            elif kind == "flag" and target_id in flag_ids:
                trigger_rows.append({"kind": "flag", "target_id": target_id})
            elif kind == "event" and target_id in event_ids:
                trigger_rows.append({"kind": "event", "target_id": target_id})
        if not trigger_rows:
            trigger_rows.append(_default_route_trigger_payload(bundle, beat_index))
        opportunities.append(
            {
                "beat_id": beat_id,
                "unlock_route_id": str(item.get("unlock_route_id") or item.get("route_id") or f"{beat_id}_{unlock_tag}_route").strip(),
                "unlock_affordance_tag": unlock_tag,
                "triggers": trigger_rows[:2],
            }
        )
    normalized["opportunities"] = opportunities
    normalized.pop("route_opportunities", None)
    return normalized


def _normalize_route_affordance_payload(
    gateway: "AuthorLLMGateway",
    payload: dict[str, Any],
    bundle: DesignBundle,
) -> dict[str, Any]:
    normalized = dict(payload)
    beat_ids = {beat.beat_id for beat in bundle.beat_spine}
    fallback_beat_id = sorted(beat_ids)[0] if beat_ids else "b1"
    affordance_tags = bundle_affordance_tags(bundle)
    affordance_by_beat = {beat.beat_id: [item.tag for item in beat.affordances] for beat in bundle.beat_spine}
    route_unlock_rules = []
    for item in list(normalized.get("route_unlock_rules") or [])[:8]:
        if not isinstance(item, dict):
            continue
        beat_id = str(item.get("beat_id") or item.get("target") or "").strip()
        if beat_id not in beat_ids:
            beat_id = fallback_beat_id
        unlock_tag = normalize_affordance_tag(
            item.get("unlock_affordance_tag") or item.get("affordance_tag") or affordance_by_beat.get(beat_id, ["build_trust"])[0]
        )
        route_unlock_rules.append(
            {
                "rule_id": str(item.get("rule_id") or f"{beat_id}_unlock").strip(),
                "beat_id": beat_id,
                "conditions": _normalize_condition_payload(gateway, item.get("conditions") or item.get("condition") or {}),
                "unlock_route_id": str(item.get("unlock_route_id") or item.get("target") or item.get("rule_id") or beat_id).strip(),
                "unlock_affordance_tag": unlock_tag,
            }
        )
    normalized["route_unlock_rules"] = route_unlock_rules
    profile_by_tag: dict[str, dict[str, Any]] = {}
    for item in list(normalized.get("affordance_effect_profiles") or [])[:12]:
        if not isinstance(item, dict):
            continue
        affordance_tag = normalize_affordance_tag(item.get("affordance_tag") or item.get("tag"))
        profile_by_tag[affordance_tag] = {
            "affordance_tag": affordance_tag,
            "default_story_function": (
                str(item.get("default_story_function") or item.get("story_function") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                if str(item.get("default_story_function") or item.get("story_function") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                in {"advance", "reveal", "stabilize", "detour", "pay_cost"}
                else default_story_function_for_tag(affordance_tag)
            ),
            "axis_deltas": {str(k): coerce_int(v, 0) for k, v in dict(item.get("axis_deltas") or {}).items()},
            "stance_deltas": {str(k): coerce_int(v, 0) for k, v in dict(item.get("stance_deltas") or {}).items()},
            "can_add_truth": bool(item.get("can_add_truth", False)),
            "can_add_event": bool(item.get("can_add_event", False)),
        }
    for affordance_tag in affordance_tags:
        profile_by_tag.setdefault(
            affordance_tag,
            {
                "affordance_tag": affordance_tag,
                "default_story_function": default_story_function_for_tag(affordance_tag),
                "axis_deltas": {},
                "stance_deltas": {},
                "can_add_truth": default_story_function_for_tag(affordance_tag) == "reveal",
                "can_add_event": default_story_function_for_tag(affordance_tag) in {"advance", "pay_cost"},
            },
        )
    normalized["affordance_effect_profiles"] = [profile_by_tag[tag] for tag in affordance_tags][:12]
    return normalized


def generate_route_opportunity_plan_result(
    gateway: "AuthorLLMGateway",
    design_bundle: DesignBundle,
    *,
    previous_response_id: str | None = None,
    primary_theme: str | None = None,
):
    resolved_primary_theme = primary_theme or plan_bundle_theme(design_bundle).primary_theme
    context_packet = build_author_context_from_bundle(design_bundle)
    payload = {"author_context": context_packet}
    system_prompt = (
        "You are the Author Route Opportunity generator. Return one strict JSON object matching RouteOpportunityPlanDraft. "
        "Identify 1-8 route opportunities across the beats in author_context. "
        "Do not generate affordance effect profiles or ending rules. "
        "Each opportunity must include: beat_id, unlock_route_id, unlock_affordance_tag, triggers. "
        "Each trigger must include: kind, target_id, and optional min_value. "
        "Allowed trigger kinds are: truth, axis, stance, flag, event. "
        "Use only ids that already exist in author_context. "
        "Prefer concrete unlock opportunities with 1-2 meaningful triggers over vague coverage. "
        f"{_route_theme_guidance(resolved_primary_theme)}"
    )
    retry_prompt = (
        "Return only one JSON object matching RouteOpportunityPlanDraft. "
        "No markdown, no explanation, no extra keys. "
        "Use concise route ids and only valid trigger ids."
    )
    final_retry_prompt = (
        "Output raw JSON only. Exactly one object with key opportunities. "
        "Each opportunity needs beat_id, unlock_route_id, unlock_affordance_tag, and triggers. No extra keys."
    )
    return invoke_structured_generation_with_retries(
        gateway,
        primary_payload=payload,
        prompts=(system_prompt, retry_prompt, final_retry_prompt),
        previous_response_id=previous_response_id,
        max_output_tokens=_route_opportunity_output_tokens(gateway, resolved_primary_theme),
        operation_name="route_opportunity_generate",
        parse_value=lambda raw_payload: RouteOpportunityPlanDraft.model_validate(
            _normalize_route_opportunity_plan_payload(gateway, raw_payload, design_bundle)
        ),
    )


def generate_route_affordance_pack_result(
    gateway: "AuthorLLMGateway",
    design_bundle: DesignBundle,
    *,
    previous_response_id: str | None = None,
):
    context_packet = build_author_context_from_bundle(design_bundle)
    payload = {"author_context": context_packet}
    system_prompt = (
        "You are the Author Route and Affordance generator. Return one strict JSON object matching RouteAffordancePackDraft. "
        "Create route unlock rules and one affordance effect profile for every affordance tag used in author_context.beats. "
        "Do not generate ending rules. "
        "Use only axis, stance, truth, event, and flag ids that already exist in author_context. "
        "Treat affordance tags as runtime semantics, not literary themes. Prefer tags that imply game-state changes rather than abstract mood words. "
        "Required top-level keys: route_unlock_rules, affordance_effect_profiles. "
        "Keep rules compact, deterministic-friendly, and non-graphic."
    )
    retry_prompt = (
        "Return only one JSON object matching RouteAffordancePackDraft. "
        "No markdown, no explanation, no extra keys. "
        "Use concise route ids and only ids that already exist in author_context."
    )
    final_retry_prompt = (
        "Output raw JSON only. Exactly one object with keys route_unlock_rules and affordance_effect_profiles. "
        "No prose outside JSON. No code fences. No extra keys."
    )
    return invoke_structured_generation_with_retries(
        gateway,
        primary_payload=payload,
        prompts=(system_prompt, retry_prompt, final_retry_prompt),
        previous_response_id=previous_response_id,
        max_output_tokens=gateway.max_output_tokens_rulepack,
        operation_name="route_affordance_generate",
        parse_value=lambda raw_payload: RouteAffordancePackDraft.model_validate(
            _normalize_route_affordance_payload(gateway, raw_payload, design_bundle)
        ),
    )

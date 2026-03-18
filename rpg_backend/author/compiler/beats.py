from __future__ import annotations

import re

from rpg_backend.author.contracts import BeatDraftSpec, BeatPlanDraft, CastDraft, FocusedBrief, StoryFrameDraft


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def _trim(value: str, limit: int) -> str:
    text = _normalize(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").casefold())
    return normalized.strip("_") or "item"


def _unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        lowered = item.casefold()
        if not item or lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(item)
    return ordered


def _normalize_affordance_tag(value: str) -> str:
    normalized = _slug(value)
    mapping = {
        "reveal": "reveal_truth",
        "investigate": "reveal_truth",
        "build_trust": "build_trust",
        "trust": "build_trust",
        "ally": "unlock_ally",
        "unlock_ally": "unlock_ally",
        "panic_control": "contain_chaos",
        "contain_chaos": "contain_chaos",
        "protect": "protect_civilians",
        "protect_civilians": "protect_civilians",
        "authority": "shift_public_narrative",
        "pressure_authority": "shift_public_narrative",
        "resources": "secure_resources",
        "secure_resources": "secure_resources",
        "narrative_shift": "shift_public_narrative",
        "shift_public_narrative": "shift_public_narrative",
        "cost": "pay_cost",
        "pay_cost": "pay_cost",
    }
    affordance_catalog = {
        "reveal_truth",
        "build_trust",
        "contain_chaos",
        "shift_public_narrative",
        "protect_civilians",
        "secure_resources",
        "unlock_ally",
        "pay_cost",
    }
    result = mapping.get(normalized, normalized)
    if result not in affordance_catalog:
        return "build_trust"
    return result


def build_default_beat_plan_draft(
    focused_brief: FocusedBrief,
    *,
    story_frame: StoryFrameDraft,
    cast_draft: CastDraft,
) -> BeatPlanDraft:
    cast_names = [item.name for item in cast_draft.cast]
    axis_ids = [item.template_id for item in story_frame.state_axis_choices]
    truth_texts = [item.text for item in story_frame.truths]

    first_axis = axis_ids[0] if axis_ids else "external_pressure"
    second_axis = axis_ids[1] if len(axis_ids) > 1 else first_axis
    third_axis = axis_ids[2] if len(axis_ids) > 2 else second_axis
    opening_pair = cast_names[:2] or ["The Mediator", "Civic Authority"]
    alliance_pair = cast_names[1:3] if len(cast_names) >= 3 else cast_names[:2] or ["Civic Authority", "Opposition Broker"]
    settlement_pair = [cast_names[0], cast_names[2]] if len(cast_names) >= 3 else alliance_pair[:2]

    lowered = f"{story_frame.title} {story_frame.premise} {focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        beat_blueprints = [
            {
                "title": "The First Nightfall",
                "goal": "Stabilize emergency coordination long enough to learn who benefits from the blackout.",
                "focus_names": opening_pair[:3],
                "conflict_pair": opening_pair[:2],
                "pressure_axis_id": first_axis,
                "milestone_kind": "reveal",
                "route_pivot_tag": "reveal_truth",
                "required_truth_texts": [truth_texts[0] if truth_texts else focused_brief.core_conflict],
                "return_hooks": ["A service failure forces the mediator to choose between speed and legitimacy."],
                "affordance_tags": ["reveal_truth", "contain_chaos", "build_trust"],
            },
            {
                "title": "The Public Ledger",
                "goal": "Turn improvised relief into a civic process the rival factions cannot dismiss as a power grab.",
                "focus_names": alliance_pair[:3],
                "conflict_pair": alliance_pair[:2],
                "pressure_axis_id": second_axis,
                "milestone_kind": "containment",
                "route_pivot_tag": "build_trust",
                "required_truth_texts": [truth_texts[1] if len(truth_texts) > 1 else truth_texts[0] if truth_texts else focused_brief.setting_signal],
                "return_hooks": ["Public patience starts collapsing unless the emergency process becomes legible."],
                "affordance_tags": ["build_trust", "contain_chaos", "secure_resources"],
            },
            {
                "title": "The Dawn Bargain",
                "goal": "Force a visible settlement before the succession vacuum hardens into a new political order.",
                "focus_names": settlement_pair[:3],
                "conflict_pair": settlement_pair[:2],
                "pressure_axis_id": third_axis,
                "milestone_kind": "commitment",
                "route_pivot_tag": "shift_public_narrative",
                "required_truth_texts": [truth_texts[-1] if truth_texts else focused_brief.core_conflict],
                "return_hooks": ["The city will accept one story about the night, and the mediator has to choose it in public."],
                "affordance_tags": ["shift_public_narrative", "build_trust", "pay_cost"],
            },
        ]
    elif any(keyword in lowered for keyword in ("harbor", "port", "trade", "quarantine")):
        beat_blueprints = [
            {
                "title": "The Quarantine Line",
                "goal": "Stabilize the harbor perimeter before panic turns quarantine into factional seizure.",
                "focus_names": opening_pair[:3],
                "conflict_pair": opening_pair[:2],
                "pressure_axis_id": first_axis,
                "milestone_kind": "reveal",
                "route_pivot_tag": "contain_chaos",
                "required_truth_texts": [truth_texts[0] if truth_texts else focused_brief.core_conflict],
                "return_hooks": ["A visible breach forces the harbor crisis into public view."],
                "affordance_tags": ["contain_chaos", "secure_resources", "reveal_truth"],
            },
            {
                "title": "The Dockside Audit",
                "goal": "Expose which faction profits from scarcity before emergency trade powers become permanent leverage.",
                "focus_names": alliance_pair[:3],
                "conflict_pair": alliance_pair[:2],
                "pressure_axis_id": second_axis,
                "milestone_kind": "fracture",
                "route_pivot_tag": "reveal_truth",
                "required_truth_texts": [truth_texts[1] if len(truth_texts) > 1 else truth_texts[0] if truth_texts else focused_brief.setting_signal],
                "return_hooks": ["The audit names winners and losers, and the coalition can no longer stay procedural."],
                "affordance_tags": ["reveal_truth", "shift_public_narrative", "build_trust"],
            },
            {
                "title": "The Harbor Compact",
                "goal": "Lock the city into a recovery bargain before private leverage replaces public authority.",
                "focus_names": settlement_pair[:3],
                "conflict_pair": settlement_pair[:2],
                "pressure_axis_id": third_axis,
                "milestone_kind": "commitment",
                "route_pivot_tag": "build_trust",
                "required_truth_texts": [truth_texts[-1] if truth_texts else focused_brief.core_conflict],
                "return_hooks": ["Once the compact is public, every faction has to decide what cost it will own."],
                "affordance_tags": ["build_trust", "secure_resources", "pay_cost"],
            },
        ]
    else:
        beat_blueprints = [
            {
                "title": "Emergency Council",
                "goal": "Understand what is breaking and who is steering the crisis toward fracture.",
                "focus_names": opening_pair[:3],
                "conflict_pair": opening_pair[:2],
                "pressure_axis_id": first_axis,
                "milestone_kind": "reveal",
                "route_pivot_tag": "reveal_truth",
                "required_truth_texts": [truth_texts[0] if truth_texts else focused_brief.core_conflict],
                "return_hooks": ["A visible public consequence forces the issue."],
                "affordance_tags": ["reveal_truth", "contain_chaos", "build_trust"],
            },
            {
                "title": "Public Strain",
                "goal": "Keep the coalition functional long enough to prove the crisis can still be governed in public.",
                "focus_names": alliance_pair[:3],
                "conflict_pair": alliance_pair[:2],
                "pressure_axis_id": second_axis,
                "milestone_kind": "containment",
                "route_pivot_tag": "build_trust",
                "required_truth_texts": [truth_texts[1] if len(truth_texts) > 1 else truth_texts[0] if truth_texts else focused_brief.setting_signal],
                "return_hooks": ["Delay becomes its own political cost unless someone makes order visible."],
                "affordance_tags": ["build_trust", "contain_chaos", "shift_public_narrative"],
            },
            {
                "title": "Final Settlement",
                "goal": "Force the crisis into a public settlement before pressure hardens into a new balance of power.",
                "focus_names": settlement_pair[:3],
                "conflict_pair": settlement_pair[:2],
                "pressure_axis_id": third_axis,
                "milestone_kind": "commitment",
                "route_pivot_tag": "shift_public_narrative",
                "required_truth_texts": [truth_texts[-1] if truth_texts else focused_brief.core_conflict],
                "return_hooks": ["The coalition must either define the new order or be defined by it."],
                "affordance_tags": ["shift_public_narrative", "build_trust", "pay_cost"],
            },
        ]

    return BeatPlanDraft(
        beats=[
            BeatDraftSpec(
                title=_trim(blueprint["title"], 120),
                goal=_trim(blueprint["goal"], 220),
                focus_names=blueprint["focus_names"],
                conflict_pair=blueprint["conflict_pair"],
                pressure_axis_id=blueprint["pressure_axis_id"],
                milestone_kind=blueprint["milestone_kind"],
                route_pivot_tag=blueprint["route_pivot_tag"],
                required_truth_texts=[_trim(item, 220) for item in blueprint["required_truth_texts"][:3]],
                detour_budget=1,
                progress_required=2,
                return_hooks=[_trim(item, 180) for item in blueprint["return_hooks"][:3]],
                affordance_tags=blueprint["affordance_tags"],
                blocked_affordances=[],
            )
            for blueprint in beat_blueprints
        ]
    )


def compiled_affordance_tags_for_beat(beat: BeatDraftSpec) -> list[str]:
    tags = [beat.route_pivot_tag] if beat.route_pivot_tag else []
    if beat.milestone_kind in {"reveal", "exposure"}:
        tags.append("reveal_truth")
    if beat.milestone_kind in {"fracture"}:
        tags.append("shift_public_narrative")
    if beat.milestone_kind in {"concession"}:
        tags.append("pay_cost")
    if beat.milestone_kind in {"containment"}:
        tags.append("contain_chaos")
    if beat.milestone_kind in {"commitment"}:
        tags.append("unlock_ally")
    if beat.pressure_axis_id in {"external_pressure", "public_panic", "time_window"}:
        tags.append("contain_chaos")
    tags.extend(list(beat.affordance_tags))
    tags.append("build_trust")
    compiled = [_normalize_affordance_tag(tag) for tag in tags if tag]
    compiled = _unique_preserve(compiled)
    for fallback_tag in ("reveal_truth", "build_trust"):
        if len(compiled) >= 2:
            break
        if fallback_tag not in compiled:
            compiled.append(fallback_tag)
    return compiled[:6]


def event_id_for_beat(index: int, beat: BeatDraftSpec) -> str:
    return f"b{index}.{_slug(beat.milestone_kind or 'milestone')}"

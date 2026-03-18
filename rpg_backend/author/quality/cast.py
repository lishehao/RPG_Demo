from __future__ import annotations

from rpg_backend.author.compiler.cast import repair_cast_draft, repair_cast_member
from rpg_backend.author.contracts import (
    CastDraft,
    CastOverviewDraft,
    CastOverviewSlotDraft,
    FocusedBrief,
    OverviewCastDraft,
)


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def _is_generic_cast_overview_text(value: str) -> bool:
    lowered = _normalize(value).casefold()
    generic_fragments = (
        "complicates or supports the protagonist under pressure",
        "protect their institutional stake while the crisis unfolds",
        "will not accept being cut out of the settlement",
        "pushes harder for leverage as public pressure rises",
        "civic role",
        "stakeholder",
    )
    return any(fragment in lowered for fragment in generic_fragments)


def is_placeholder_cast(cast_draft: CastDraft) -> bool:
    return all(item.name.startswith("Civic Figure ") for item in cast_draft.cast)


def is_low_quality_cast_overview(cast_overview: CastOverviewDraft) -> bool:
    return bool(cast_overview_quality_reasons(cast_overview))


def cast_overview_quality_reasons(cast_overview: CastOverviewDraft) -> list[str]:
    reasons: list[str] = []
    unique_roles = {slot.public_role.casefold() for slot in cast_overview.cast_slots}
    generic_markers = 0
    total_markers = 0
    for slot in cast_overview.cast_slots:
        for value in (
            slot.slot_label,
            slot.relationship_to_protagonist,
            slot.agenda_anchor,
            slot.red_line_anchor,
            slot.pressure_vector,
        ):
            total_markers += 1
            if _is_generic_cast_overview_text(value):
                generic_markers += 1
    if len(unique_roles) < min(2, len(cast_overview.cast_slots)):
        reasons.append("cast_overview_role_diversity_too_narrow")
    if generic_markers >= max(4, total_markers // 2):
        reasons.append("cast_overview_generic_text")
    return reasons


def is_generic_cast_text(value: str) -> bool:
    lowered = _normalize(value).casefold()
    generic_fragments = (
        "tries to preserve their role in the crisis",
        "will not lose public legitimacy without resistance",
        "reacts sharply when pressure threatens public order",
        "protect their corner of the city during the crisis",
        "will not accept total collapse without resistance",
        "pushes for quick action whenever the public mood worsens",
        "placeholder agenda",
        "placeholder red line",
        "placeholder pressure signature",
    )
    return any(fragment in lowered for fragment in generic_fragments)


def is_placeholder_cast_member(member: OverviewCastDraft) -> bool:
    return member.name.startswith("Civic Figure ") or member.name.casefold() in {
        "mediator anchor",
        "institutional guardian",
        "leverage broker",
        "archive guardian",
        "coalition rival",
        "civic witness",
        "public advocate",
    }


def looks_like_role_label_name(
    member_name: str,
    slot: CastOverviewSlotDraft,
) -> bool:
    normalized_name = _normalize(member_name).casefold()
    if normalized_name in {
        _normalize(slot.slot_label).casefold(),
        _normalize(slot.public_role).casefold(),
    }:
        return True
    generic_tokens = {
        "mediator",
        "anchor",
        "guardian",
        "broker",
        "witness",
        "rival",
        "authority",
        "advocate",
        "public",
        "civic",
        "institutional",
        "archive",
        "coalition",
        "trade",
        "bloc",
        "player",
        "power",
        "figure",
        "delegate",
    }
    tokens = [token for token in normalized_name.replace("-", " ").split() if token]
    if len(tokens) < 2:
        return True
    nongeneric_tokens = [token for token in tokens if token not in generic_tokens]
    return len(nongeneric_tokens) < 1


def is_low_quality_cast_member(
    member: OverviewCastDraft,
    existing_names: set[str],
    slot: CastOverviewSlotDraft,
) -> bool:
    return bool(cast_member_quality_reasons(member, existing_names, slot))


def cast_member_quality_reasons(
    member: OverviewCastDraft,
    existing_names: set[str],
    slot: CastOverviewSlotDraft,
) -> list[str]:
    reasons: list[str] = []
    if is_placeholder_cast_member(member):
        reasons.append("cast_member_placeholder_name")
    if looks_like_role_label_name(member.name, slot):
        reasons.append("cast_member_role_label_name")
    if member.name in existing_names:
        reasons.append("cast_member_duplicate_name")
    generic_fields = sum(
        1
        for value in (member.agenda, member.red_line, member.pressure_signature)
        if is_generic_cast_text(value)
    )
    if generic_fields >= 2:
        reasons.append("cast_member_generic_fields")
    return reasons


def is_low_quality_cast(cast_draft: CastDraft) -> bool:
    return bool(cast_quality_reasons(cast_draft))


def cast_quality_reasons(cast_draft: CastDraft) -> list[str]:
    reasons: list[str] = []
    generic_fields = 0
    total_fields = 0
    for member in cast_draft.cast:
        for value in (member.agenda, member.red_line, member.pressure_signature):
            total_fields += 1
            if is_generic_cast_text(value):
                generic_fields += 1
    unique_roles = {member.role.casefold() for member in cast_draft.cast}
    if generic_fields >= max(3, total_fields // 2):
        reasons.append("cast_generic_fields")
    if len(unique_roles) < min(2, len(cast_draft.cast)):
        reasons.append("cast_role_diversity_too_narrow")
    return reasons


def finalize_cast_overview_candidate(
    cast_overview: CastOverviewDraft,
    focused_brief: FocusedBrief,
) -> CastOverviewDraft | None:
    del focused_brief
    if is_low_quality_cast_overview(cast_overview):
        return None
    return cast_overview


def finalize_cast_candidate(
    cast_draft: CastDraft,
    focused_brief: FocusedBrief,
    cast_overview: CastOverviewDraft,
) -> CastDraft | None:
    if is_placeholder_cast(cast_draft):
        return None
    repaired = repair_cast_draft(
        cast_draft,
        focused_brief,
        cast_overview,
    )
    if is_low_quality_cast(repaired):
        return None
    return repaired


def finalize_cast_member_candidate(
    member: OverviewCastDraft,
    focused_brief: FocusedBrief,
    slot: CastOverviewSlotDraft,
    existing_names: set[str],
) -> OverviewCastDraft | None:
    repaired = repair_cast_member(member, focused_brief, slot)
    if is_low_quality_cast_member(repaired, existing_names, slot):
        return None
    return repaired

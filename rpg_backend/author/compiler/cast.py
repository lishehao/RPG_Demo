from __future__ import annotations

import re
from dataclasses import dataclass

from rpg_backend.author.contracts import (
    CastDraft,
    CastMemberSemanticsDraft,
    CastOverviewDraft,
    CastOverviewSlotDraft,
    FocusedBrief,
    OverviewCastDraft,
    StoryFrameDraft,
)


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").casefold())
    return normalized.strip("_") or "item"


def _trim(value: str, limit: int) -> str:
    text = _normalize(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


CAST_ARCHETYPE_LIBRARY: dict[str, dict[str, str]] = {
    "civic_mediator": {
        "slot_label": "Mediator Anchor",
        "public_role": "Mediator",
        "agenda_anchor": "Keep the emergency process legitimate long enough to stop the city from splintering.",
        "red_line_anchor": "Will not let emergency pressure erase public consent.",
        "pressure_vector": "Starts bridging hostile sides before every guarantee is secured.",
        "counter_trait": "idealistic in public, quietly controlling in execution",
        "pressure_tell": "Speaks faster, narrows the options, and starts counting who is still willing to stay in the room.",
        "name_bucket": "protagonist",
    },
    "harbor_inspector": {
        "slot_label": "Mediator Anchor",
        "public_role": "Harbor inspector",
        "agenda_anchor": "Keep the quarantine process enforceable without letting trade politics tear the harbor apart.",
        "red_line_anchor": "Will not let emergency decrees turn into unaccountable seizure.",
        "pressure_vector": "Treats every procedural gap as a point where panic and smuggling can rush in together.",
        "counter_trait": "methodical in public, personally restless under delay",
        "pressure_tell": "Starts inspecting details out loud and turning vague claims into hard checkpoints.",
        "name_bucket": "protagonist",
    },
    "archive_guardian": {
        "slot_label": "Institutional Guardian",
        "public_role": "Archive authority",
        "agenda_anchor": "Preserve the institutions and procedures that still make the city governable.",
        "red_line_anchor": "Will not surrender formal authority without a visible procedural reason.",
        "pressure_vector": "Tightens procedure whenever panic, blame, or uncertainty starts to spread.",
        "counter_trait": "severe in public, privately protective of what would be lost",
        "pressure_tell": "Repeats the rules more precisely as the room gets louder and closes off informal exits.",
        "name_bucket": "guardian",
    },
    "port_guardian": {
        "slot_label": "Institutional Guardian",
        "public_role": "Port authority",
        "agenda_anchor": "Keep the harbor operating under rules that still look legitimate to frightened citizens and traders.",
        "red_line_anchor": "Will not let emergency traffic control become private leverage for one faction.",
        "pressure_vector": "Locks movement, paperwork, and access down tighter every time panic jumps a level.",
        "counter_trait": "rigid in public, quietly terrified of systemic collapse",
        "pressure_tell": "Starts reciting manifests, quotas, and access thresholds like a shield against chaos.",
        "name_bucket": "guardian",
    },
    "leverage_broker": {
        "slot_label": "Leverage Broker",
        "public_role": "Political rival",
        "agenda_anchor": "Turn the crisis into leverage over who controls the settlement that comes after it.",
        "red_line_anchor": "Will not accept exclusion from the final settlement.",
        "pressure_vector": "Treats every emergency as proof that someone else should lose authority.",
        "counter_trait": "calculating in public, needy about irrelevance underneath",
        "pressure_tell": "Reframes every setback as evidence that the balance of power must change immediately.",
        "name_bucket": "rival",
    },
    "trade_bloc_rival": {
        "slot_label": "Leverage Broker",
        "public_role": "Trade bloc rival",
        "agenda_anchor": "Convert quarantine chaos into bargaining power over who controls shipping, credit, and recovery.",
        "red_line_anchor": "Will not let the harbor reopen on terms that leave their bloc weakened.",
        "pressure_vector": "Turns every supply shock into a negotiation over power rather than relief.",
        "counter_trait": "polished in public, vengeful about being sidelined",
        "pressure_tell": "Starts offering practical help that always arrives tied to a new concession.",
        "name_bucket": "rival",
    },
    "public_witness": {
        "slot_label": "Civic Witness",
        "public_role": "Public advocate",
        "agenda_anchor": "Force the crisis response to remain publicly accountable while pressure keeps rising.",
        "red_line_anchor": "Will not let elite procedure erase the public record of what happened.",
        "pressure_vector": "Turns ambiguity, secrecy, or procedural drift into public scrutiny.",
        "counter_trait": "morally direct in public, emotionally stubborn in private",
        "pressure_tell": "Stops accepting closed-room assurances and demands that someone say the cost aloud.",
        "name_bucket": "witness",
    },
    "dock_delegate": {
        "slot_label": "Civic Witness",
        "public_role": "Dock delegate",
        "agenda_anchor": "Keep working crews and neighborhood residents from paying for elite quarantine bargains they never approved.",
        "red_line_anchor": "Will not let emergency port rules bury who benefited and who got stranded.",
        "pressure_vector": "Turns private deals into dockside rumors and then into organized pressure.",
        "counter_trait": "plainspoken in public, deeply strategic about crowd mood",
        "pressure_tell": "Starts naming names, losses, and delays until the room can no longer hide behind abstractions.",
        "name_bucket": "witness",
    },
}

CAST_RELATIONSHIP_DYNAMIC_LIBRARY: dict[str, str] = {
    "protagonist_bears_public_weight": "The protagonist stands inside the crisis rather than above it, so every compromise lands as a public burden they personally own.",
    "improvisation_vs_procedure": "This figure needs the protagonist's flexibility but distrusts improvisation once legitimacy is already under strain.",
    "settlement_vs_leverage": "This figure tests whether the protagonist can stabilize the crisis without conceding who gets power after it.",
    "public_record_vs_private_bargain": "This figure turns private bargains into public accountability whenever the room starts deciding too much in secret.",
}

FOUR_SLOT_KEYWORDS: tuple[str, ...] = (
    "blackout",
    "succession",
    "election",
    "harbor",
    "port",
    "trade",
    "quarantine",
    "public",
    "civic",
    "coalition",
)

HARBOR_FOURTH_SLOT_KEYWORDS: tuple[str, ...] = (
    "harbor",
    "port",
    "trade",
    "quarantine",
)


@dataclass(frozen=True)
class CastTopologyPlan:
    topology: str
    slot_archetypes: tuple[str, ...]
    planner_reason: str


def _build_cast_slot_from_archetype(
    archetype_id: str,
    relationship_dynamic_id: str,
) -> CastOverviewSlotDraft:
    archetype = CAST_ARCHETYPE_LIBRARY[archetype_id]
    return CastOverviewSlotDraft(
        slot_label=archetype["slot_label"],
        public_role=archetype["public_role"],
        relationship_to_protagonist=CAST_RELATIONSHIP_DYNAMIC_LIBRARY[relationship_dynamic_id],
        agenda_anchor=archetype["agenda_anchor"],
        red_line_anchor=archetype["red_line_anchor"],
        pressure_vector=archetype["pressure_vector"],
        archetype_id=archetype_id,
        relationship_dynamic_id=relationship_dynamic_id,
        counter_trait=archetype["counter_trait"],
        pressure_tell=archetype["pressure_tell"],
    )


def build_default_cast_overview_draft(focused_brief: FocusedBrief) -> CastOverviewDraft:
    del focused_brief
    return CastOverviewDraft(
        cast_slots=[
            _build_cast_slot_from_archetype("civic_mediator", "protagonist_bears_public_weight"),
            _build_cast_slot_from_archetype("archive_guardian", "improvisation_vs_procedure"),
            _build_cast_slot_from_archetype("leverage_broker", "settlement_vs_leverage"),
        ],
        relationship_summary=[
            CAST_RELATIONSHIP_DYNAMIC_LIBRARY["improvisation_vs_procedure"],
            CAST_RELATIONSHIP_DYNAMIC_LIBRARY["settlement_vs_leverage"],
        ],
    )


def plan_cast_topology(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
) -> CastTopologyPlan:
    haystack = " ".join(
        [
            focused_brief.setting_signal,
            focused_brief.core_conflict,
            story_frame.title,
            story_frame.premise,
        ]
    ).casefold()
    use_four_slot = any(keyword in haystack for keyword in FOUR_SLOT_KEYWORDS)
    protagonist_archetype_id = "civic_mediator"
    if any(keyword in haystack for keyword in ("inspector", "harbor inspector")):
        protagonist_archetype_id = "harbor_inspector"

    guardian_archetype_id = "archive_guardian"
    if any(keyword in haystack for keyword in ("harbor", "port", "trade")):
        guardian_archetype_id = "port_guardian"

    rival_archetype_id = "leverage_broker"
    if any(keyword in haystack for keyword in ("quarantine", "accord", "trade")):
        rival_archetype_id = "trade_bloc_rival"

    slot_archetypes = [
        protagonist_archetype_id,
        guardian_archetype_id,
        rival_archetype_id,
    ]
    planner_reason = "default_three_slot"
    if use_four_slot:
        planner_reason = "keyword_triggered_four_slot"
        fourth_slot = (
            "dock_delegate"
            if any(keyword in haystack for keyword in HARBOR_FOURTH_SLOT_KEYWORDS)
            else "public_witness"
        )
        slot_archetypes.append(fourth_slot)
    return CastTopologyPlan(
        topology="four_slot" if use_four_slot else "three_slot",
        slot_archetypes=tuple(slot_archetypes),
        planner_reason=planner_reason,
    )


def derive_cast_overview_draft(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    *,
    topology_override: str | None = None,
) -> CastOverviewDraft:
    topology_plan = plan_cast_topology(focused_brief, story_frame)
    if topology_override:
        topology_plan = CastTopologyPlan(
            topology=topology_override,
            slot_archetypes=topology_plan.slot_archetypes,
            planner_reason="forced_topology_override",
        )
    cast_slots = [
        _build_cast_slot_from_archetype(topology_plan.slot_archetypes[0], "protagonist_bears_public_weight"),
        _build_cast_slot_from_archetype(topology_plan.slot_archetypes[1], "improvisation_vs_procedure"),
        _build_cast_slot_from_archetype(topology_plan.slot_archetypes[2], "settlement_vs_leverage"),
    ]
    relationship_summary = [
        CAST_RELATIONSHIP_DYNAMIC_LIBRARY["improvisation_vs_procedure"],
        CAST_RELATIONSHIP_DYNAMIC_LIBRARY["settlement_vs_leverage"],
    ]
    if topology_plan.topology == "four_slot":
        cast_slots.append(
            _build_cast_slot_from_archetype(
                topology_plan.slot_archetypes[3],
                "public_record_vs_private_bargain",
            )
        )
        relationship_summary.append(
            CAST_RELATIONSHIP_DYNAMIC_LIBRARY["public_record_vs_private_bargain"]
        )
    return CastOverviewDraft(
        cast_slots=cast_slots[:5],
        relationship_summary=relationship_summary[:6],
    )


def _name_palette_for_brief(focused_brief: FocusedBrief) -> dict[str, list[str]]:
    setting = focused_brief.setting_signal.casefold()
    if any(keyword in setting for keyword in ("archive", "archives", "ledger", "record", "script", "library")):
        return {
            "protagonist": ["Elara Vance", "Iri Vale", "Nera Quill", "Tarin Sloane"],
            "guardian": ["Kaelen Thorne", "Sen Ardin", "Pell Ivar", "Sera Nhal"],
            "rival": ["Mira Solis", "Tal Reth", "Dain Voss", "Cass Vey"],
            "civic": ["Lio Maren", "Risa Vale", "Joren Pell", "Tavi Sern"],
            "witness": ["Ona Pell", "Lio Maren", "Risa Vale", "Tavi Sern"],
        }
    if any(keyword in setting for keyword in ("harbor", "port", "trade", "quarantine", "republic", "dock")):
        return {
            "protagonist": ["Corin Hale", "Mara Vey", "Tessa Vale", "Ilan Dorr"],
            "guardian": ["Jun Pell", "Soren Vale", "Neris Dane", "Hadrin Voss"],
            "rival": ["Tal Reth", "Cass Voren", "Mira Solis", "Dain Vey"],
            "civic": ["Edda Marr", "Korin Pell", "Rhea Doss", "Sel Varan"],
            "witness": ["Edda Marr", "Sel Varan", "Brin Vale", "Rhea Doss"],
        }
    return {
        "protagonist": ["Elara Vance", "Corin Hale", "Mira Vale", "Iri Vale"],
        "guardian": ["Kaelen Thorne", "Sera Pell", "Jun Ardin", "Pell Ivar"],
        "rival": ["Tal Reth", "Mira Solis", "Dain Voss", "Cass Vey"],
        "civic": ["Risa Vale", "Lio Maren", "Tavi Sern", "Neris Dane"],
        "witness": ["Lio Maren", "Ona Pell", "Risa Vale", "Tavi Sern"],
    }


def _cast_slot_bucket(slot: CastOverviewSlotDraft) -> str:
    if slot.archetype_id in {"public_witness", "dock_delegate"}:
        return "witness"
    text = f"{slot.slot_label} {slot.public_role}".casefold()
    if any(keyword in text for keyword in ("mediator", "anchor", "player", "envoy", "inspector", "protagonist")):
        return "protagonist"
    if any(keyword in text for keyword in ("institution", "guardian", "authority", "curator", "scribe", "warden")):
        return "guardian"
    if any(keyword in text for keyword in ("broker", "rival", "opposition", "leverage", "faction", "merchant")):
        return "rival"
    return "civic"


def is_legitimacy_broker_slot(cast_strategy: str, slot: CastOverviewSlotDraft) -> bool:
    if cast_strategy != "legitimacy_cast":
        return False
    slot_text = f"{slot.slot_label} {slot.public_role} {slot.archetype_id or ''}".casefold()
    return any(
        token in slot_text
        for token in (
            "leverage broker",
            "political rival",
            "trade bloc rival",
            "leverage_broker",
            "trade_bloc_rival",
        )
    )


def _generated_name_for_slot(
    slot: CastOverviewSlotDraft,
    focused_brief: FocusedBrief,
    slot_index: int,
    used_names: set[str],
) -> str:
    palette = _name_palette_for_brief(focused_brief)
    bucket = _cast_slot_bucket(slot)
    options = palette[bucket]
    seed = f"{focused_brief.story_kernel}|{focused_brief.setting_signal}|{slot.slot_label}|{slot_index}"
    start = sum(ord(ch) for ch in seed) % len(options)
    for offset in range(len(options)):
        candidate = options[(start + offset) % len(options)]
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
    fallback = f"{options[start]} {slot_index + 1}"
    used_names.add(fallback)
    return fallback


def _looks_like_role_label_name_locally(
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
        "leverage",
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
        "stakeholder",
    }
    tokens = [token for token in normalized_name.replace("-", " ").split() if token]
    if len(tokens) < 2:
        return True
    nongeneric_tokens = [token for token in tokens if token not in generic_tokens]
    return len(nongeneric_tokens) < 1


def _clean_member_detail(detail: str, fallback: str, *, limit: int = 180) -> str:
    text = _trim(detail or fallback, limit)
    if not text:
        return _trim(fallback, limit)
    return text


def _merge_anchor_with_detail(anchor: str, detail: str, *, limit: int = 220) -> str:
    anchor_text = _trim(anchor, limit)
    detail_text = _trim(detail, limit)
    if not detail_text:
        return anchor_text
    if detail_text.casefold() in anchor_text.casefold() or anchor_text.casefold() in detail_text.casefold():
        return anchor_text
    return _trim(f"{anchor_text} {detail_text}", limit)


def build_cast_draft_from_overview(
    cast_overview: CastOverviewDraft,
    focused_brief: FocusedBrief,
) -> CastDraft:
    used_names: set[str] = set()
    return CastDraft(
        cast=[
            OverviewCastDraft(
                name=_generated_name_for_slot(slot, focused_brief, index, used_names),
                role=_trim(slot.public_role, 120),
                agenda=_trim(slot.agenda_anchor, 220),
                red_line=_trim(slot.red_line_anchor, 220),
                pressure_signature=_trim(slot.pressure_vector, 220),
            )
            for index, slot in enumerate(cast_overview.cast_slots)
        ]
    )


def build_cast_member_from_slot(
    slot: CastOverviewSlotDraft,
    focused_brief: FocusedBrief,
    slot_index: int,
    existing_names: set[str],
) -> OverviewCastDraft:
    return OverviewCastDraft(
        name=_generated_name_for_slot(slot, focused_brief, slot_index, existing_names),
        role=_trim(slot.public_role, 120),
        agenda=_trim(slot.agenda_anchor, 220),
        red_line=_trim(slot.red_line_anchor, 220),
        pressure_signature=_trim(slot.pressure_vector, 220),
    )


def compile_cast_member_semantics(
    semantics: CastMemberSemanticsDraft,
    slot: CastOverviewSlotDraft,
    focused_brief: FocusedBrief,
    slot_index: int,
    existing_names: set[str],
) -> OverviewCastDraft:
    fallback_member = build_cast_member_from_slot(
        slot,
        focused_brief,
        slot_index,
        set(existing_names),
    )
    generated_name = _trim(semantics.name, 80)
    if (
        not generated_name
        or generated_name in existing_names
        or generated_name.startswith("Civic Figure ")
        or _looks_like_role_label_name_locally(generated_name, slot)
    ):
        name = fallback_member.name
    else:
        name = generated_name
    agenda_detail = _clean_member_detail(
        semantics.agenda_detail,
        "Uses their position to turn private hesitation into a concrete bargaining advantage.",
    )
    red_line_detail = _clean_member_detail(
        semantics.red_line_detail,
        "The line hardens whenever they think the settlement will erase their public standing.",
    )
    pressure_detail = _clean_member_detail(
        semantics.pressure_detail,
        slot.pressure_tell or "Their instincts sharpen as the room turns brittle.",
    )
    return OverviewCastDraft(
        name=name,
        role=_trim(slot.public_role, 120),
        agenda=_merge_anchor_with_detail(slot.agenda_anchor, agenda_detail, limit=220),
        red_line=_merge_anchor_with_detail(slot.red_line_anchor, red_line_detail, limit=220),
        pressure_signature=_merge_anchor_with_detail(slot.pressure_vector, pressure_detail, limit=220),
    )


def build_default_cast_draft(_: FocusedBrief) -> CastDraft:
    return CastDraft(
        cast=[
            OverviewCastDraft(
                name="The Mediator",
                role="Player anchor",
                agenda="Hold the city together long enough to expose the truth.",
                red_line="Will not deliberately sacrifice civilians for speed.",
                pressure_signature="Feels every compromise as a public burden.",
            ),
            OverviewCastDraft(
                name="Civic Authority",
                role="Institutional power",
                agenda="Preserve order and legitimacy.",
                red_line="Will not publicly yield without visible cause.",
                pressure_signature="Turns every crisis into a test of control.",
            ),
            OverviewCastDraft(
                name="Opposition Broker",
                role="Political rival",
                agenda="Exploit the crisis to reshape power.",
                red_line="Will not accept irrelevance.",
                pressure_signature="Smiles while pressure spreads through the room.",
            ),
        ]
    )


def _is_generic_cast_text(value: str) -> bool:
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


def repair_cast_draft(
    cast_draft: CastDraft,
    focused_brief: FocusedBrief,
    cast_overview: CastOverviewDraft | None = None,
) -> CastDraft:
    role_templates = (
        (
            ("mediator", "envoy", "inspector", "player", "anchor", "negotiator"),
            {
                "agenda": _trim(f"Keep the civic process intact long enough to resolve {focused_brief.core_conflict}.", 220),
                "red_line": "Will not let emergency pressure erase public consent.",
                "pressure_signature": "Reads every compromise in terms of what the public will have to live with next.",
            },
        ),
        (
            ("authority", "curator", "official", "institution", "guardian"),
            {
                "agenda": _trim(f"Preserve institutional continuity inside {focused_brief.setting_signal}.", 220),
                "red_line": "Will not yield formal authority without a visible procedural reason.",
                "pressure_signature": "Tightens procedure whenever panic, blame, or uncertainty starts to spread.",
            },
        ),
        (
            ("broker", "rival", "faction", "opposition", "merchant", "leader"),
            {
                "agenda": _trim(f"Exploit {focused_brief.core_conflict} to reshape who holds leverage after the crisis.", 220),
                "red_line": "Will not accept exclusion from the final settlement.",
                "pressure_signature": "Treats every emergency as proof that someone else should lose authority.",
            },
        ),
    )
    slot_templates = list(cast_overview.cast_slots) if cast_overview else []
    repaired = []
    for index, member in enumerate(cast_draft.cast):
        matching_slot = None
        if slot_templates:
            member_role = member.role.casefold()
            member_name = member.name.casefold()
            for slot in slot_templates:
                if slot.slot_label.casefold() in member_name or slot.public_role.casefold() in member_role or any(
                    keyword in member_role
                    for keyword in slot.public_role.casefold().split()
                    if len(keyword) > 3
                ):
                    matching_slot = slot
                    break
            if matching_slot is None and index < len(slot_templates):
                matching_slot = slot_templates[index]
        role_text = member.role.casefold()
        template = None
        for keywords, candidate in role_templates:
            if any(keyword in role_text for keyword in keywords):
                template = candidate
                break
        if matching_slot is not None:
            template = {
                "agenda": _trim(matching_slot.agenda_anchor, 220),
                "red_line": _trim(matching_slot.red_line_anchor, 220),
                "pressure_signature": _trim(matching_slot.pressure_vector, 220),
            }
        elif template is None:
            template = (
                role_templates[min(index, len(role_templates) - 1)][1]
                if index < len(role_templates)
                else {
                    "agenda": _trim(f"Protect their stake in {focused_brief.setting_signal} while the crisis unfolds.", 220),
                    "red_line": "Will not accept being made irrelevant by emergency decree.",
                    "pressure_signature": "Pushes harder for advantage whenever the public mood turns brittle.",
                }
            )
        repaired.append(
            OverviewCastDraft(
                name=member.name,
                role=member.role,
                agenda=template["agenda"] if _is_generic_cast_text(member.agenda) else member.agenda,
                red_line=template["red_line"] if _is_generic_cast_text(member.red_line) else member.red_line,
                pressure_signature=template["pressure_signature"] if _is_generic_cast_text(member.pressure_signature) else member.pressure_signature,
            )
        )
    return CastDraft(cast=repaired)


def repair_cast_member(
    member: OverviewCastDraft,
    focused_brief: FocusedBrief,
    slot: CastOverviewSlotDraft,
) -> OverviewCastDraft:
    role_text = (member.role or slot.public_role).casefold()
    agenda = member.agenda
    red_line = member.red_line
    pressure_signature = member.pressure_signature
    if _is_generic_cast_text(agenda):
        agenda = slot.agenda_anchor
    if _is_generic_cast_text(red_line):
        red_line = slot.red_line_anchor
    if _is_generic_cast_text(pressure_signature):
        pressure_signature = slot.pressure_vector
    if "mediator" in role_text or "inspector" in role_text or "anchor" in role_text:
        agenda = slot.agenda_anchor if _is_generic_cast_text(member.agenda) else agenda
    elif any(keyword in role_text for keyword in ("guardian", "authority", "institution", "curator", "scribe")):
        agenda = slot.agenda_anchor if _is_generic_cast_text(member.agenda) else agenda
    elif any(keyword in role_text for keyword in ("broker", "rival", "opposition", "merchant", "trade bloc")):
        agenda = slot.agenda_anchor if _is_generic_cast_text(member.agenda) else agenda
    return OverviewCastDraft(
        name=member.name,
        role=_trim(member.role or slot.public_role, 120),
        agenda=_trim(agenda, 220),
        red_line=_trim(red_line, 220),
        pressure_signature=_trim(pressure_signature, 220),
    )

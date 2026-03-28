from __future__ import annotations

from typing import Any

from rpg_backend.author.compiler.cast import compile_cast_member_semantics, is_legitimacy_broker_slot
from rpg_backend.author.compiler.router import plan_story_theme
from rpg_backend.author.generation.runner import invoke_structured_generation_with_retries
from rpg_backend.generation_skill import ContextCard, GenerationSkillPacket
from rpg_backend.author.contracts import (
    CastDraft,
    CastMemberSemanticsDraft,
    CastOverviewDraft,
    CastOverviewSlotDraft,
    FocusedBrief,
    StoryFrameDraft,
)
from rpg_backend.content_language import output_language_instruction, prompt_role_instruction, resolve_content_prompt_profile
from rpg_backend.llm_gateway import CapabilityGatewayCore
from rpg_backend.author.normalize import trim_text, unique_preserve


def _cast_member_max_output_tokens(gateway: CapabilityGatewayCore, cast_strategy: str = "generic_civic_cast") -> int:
    budget = gateway.text_policy("author.cast_member_generate").max_output_tokens
    if budget is None:
        return 360
    floor = 280
    if cast_strategy in {"legitimacy_cast", "public_order_cast", "blackout_referendum_cast", "archive_vote_cast"}:
        floor = 340
    return max(floor, min(int(budget), 520))


def _cast_overview_max_output_tokens(gateway: CapabilityGatewayCore, cast_strategy: str = "generic_civic_cast") -> int:
    budget = gateway.text_policy("author.cast_member_generate").max_output_tokens
    if budget is None:
        return 420
    floor = 360 if cast_strategy == "generic_civic_cast" else 420
    return max(floor, min(int(budget), 560))


def _cast_theme_guidance(cast_strategy: str) -> str:
    mapping = {
        "bridge_ration_cast": "Bias the cast toward bridge stewards, quartermasters, ward delegates, and ration chokepoint bargaining.",
        "harbor_quarantine_cast": "Bias the cast toward harbor wardens, manifest clerks, dock brokers, quarantine enforcers, and civic oversight witnesses.",
        "blackout_referendum_cast": "Bias the cast toward ombudsman-facing delegates, blackout clerks, neighborhood council brokers, and rumor-bearing civic witnesses.",
        "archive_vote_cast": "Bias the cast toward archivists, clerks, witnesses, certifying authorities, and actors who control chain of custody.",
        "warning_record_cast": "Bias the cast toward observatory staff, chamber clerks, warning suppressors, and officials who fear public alarm.",
        "legitimacy_cast": "Bias the cast toward coalition bargaining, public mandates, procedural leverage, and visible civic responsibility.",
        "logistics_cast": "Bias the cast toward inspection authority, supply chokepoints, quarantine enforcement, and scarcity bargaining.",
        "truth_record_cast": "Bias the cast toward records, witnesses, testimony control, evidence custody, and procedural proof.",
        "public_order_cast": "Bias the cast toward panic management, crowd pressure, curfew logic, and emergency authority.",
        "generic_civic_cast": "Bias the cast toward civic procedure, public consequence, and institutional conflict.",
    }
    return mapping.get(cast_strategy, mapping["generic_civic_cast"])


def _cast_skill_packet(
    *,
    skill_id: str,
    capability: str,
    required_output_contract: str,
    task_brief: str,
    extra_payload: dict[str, Any],
    context_cards: tuple[ContextCard, ...],
    repair_note: str | None = None,
    final_contract_note: str | None = None,
    final_retry_extra_payload: dict[str, Any] | None = None,
) -> GenerationSkillPacket:
    return GenerationSkillPacket(
        skill_id=skill_id,
        skill_version="v1",
        capability=capability,
        contract_mode="strict_json_schema",
        role_style=resolve_content_prompt_profile(),
        required_output_contract=required_output_contract,
        context_cards=context_cards,
        task_brief=task_brief,
        repair_mode="schema_repair" if repair_note or final_contract_note else "none",
        repair_note=repair_note,
        final_contract_note=final_contract_note,
        extra_payload=extra_payload,
        final_retry_extra_payload=final_retry_extra_payload,
    )


def _slim_existing_cast(existing_cast: list[dict[str, Any]]) -> list[dict[str, str]]:
    slim_rows = []
    for item in existing_cast:
        if not isinstance(item, dict):
            continue
        slim_rows.append(
            {
                "name": str(item.get("name") or "").strip(),
                "role": str(item.get("role") or "").strip(),
            }
        )
    return slim_rows


def _slim_story_frame(story_frame: StoryFrameDraft) -> dict[str, str]:
    return {
        "title": story_frame.title,
        "premise": story_frame.premise,
        "stakes": story_frame.stakes,
    }


def _normalize_cast_overview_payload(gateway: CapabilityGatewayCore, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    slot_items = []
    for item in list(normalized.get("cast_slots") or normalized.get("roles") or normalized.get("cast") or [])[:5]:
        if not isinstance(item, dict):
            continue
        slot_label = trim_text(item.get("slot_label") or item.get("label") or item.get("name") or "Civic Role", 80)
        public_role = trim_text(item.get("public_role") or item.get("role") or "Stakeholder", 120)
        slot_items.append(
            {
                "slot_label": slot_label,
                "public_role": public_role,
                "relationship_to_protagonist": trim_text(
                    item.get("relationship_to_protagonist") or item.get("relationship") or "Complicates or supports the protagonist under pressure.",
                    180,
                ),
                "agenda_anchor": trim_text(
                    item.get("agenda_anchor") or item.get("agenda") or f"{slot_label} tries to protect their institutional stake while the crisis unfolds.",
                    220,
                ),
                "red_line_anchor": trim_text(
                    item.get("red_line_anchor") or item.get("red_line") or f"{slot_label} will not accept being cut out of the settlement.",
                    220,
                ),
                "pressure_vector": trim_text(
                    item.get("pressure_vector") or item.get("pressure_signature") or f"{slot_label} pushes harder for leverage as public pressure rises.",
                    220,
                ),
            }
        )
    unique_slots = []
    seen_labels: set[str] = set()
    for item in slot_items:
        lowered = item["slot_label"].casefold()
        if lowered in seen_labels:
            continue
        seen_labels.add(lowered)
        unique_slots.append(item)
    while len(unique_slots) < 3:
        index = len(unique_slots) + 1
        unique_slots.append(
            {
                "slot_label": f"Civic Role {index}",
                "public_role": "Stakeholder",
                "relationship_to_protagonist": "Complicates or supports the protagonist under pressure.",
                "agenda_anchor": "Protect their institutional stake while the crisis unfolds.",
                "red_line_anchor": "Will not accept being cut out of the settlement.",
                "pressure_vector": "Pushes harder for leverage as public pressure rises.",
            }
        )
    relationship_summary = [
        trim_text(item, 180)
        for item in list(normalized.get("relationship_summary") or normalized.get("relationships") or [])[:6]
        if trim_text(item, 180)
    ]
    relationship_summary = unique_preserve(relationship_summary)
    if len(relationship_summary) < 2:
        relationship_summary = [
            f"{unique_slots[0]['slot_label']} and {unique_slots[1]['slot_label']} need each other but disagree on procedure.",
            f"{unique_slots[2]['slot_label']} gains leverage whenever public pressure rises.",
        ][: max(2, len(relationship_summary))]
    return {
        "cast_slots": unique_slots[:5],
        "relationship_summary": relationship_summary[:6],
    }


def _normalize_cast_payload(gateway: CapabilityGatewayCore, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    cast_items = []
    for item in list(normalized.get("cast") or [])[:5]:
        if not isinstance(item, dict):
            continue
        name = trim_text(item.get("name") or "Unnamed Figure", 80)
        role = trim_text(item.get("role") or "Civic actor", 120)
        cast_items.append(
            {
                "name": name,
                "role": role,
                "agenda": trim_text(item.get("agenda") or f"{name} tries to preserve their role in the crisis.", 220),
                "red_line": trim_text(item.get("red_line") or f"{name} will not lose public legitimacy without resistance.", 220),
                "pressure_signature": trim_text(
                    item.get("pressure_signature") or f"{name} reacts sharply when pressure threatens public order.",
                    220,
                ),
            }
        )
    unique_cast = []
    seen_names: set[str] = set()
    for item in cast_items:
        lowered = item["name"].casefold()
        if lowered in seen_names:
            continue
        seen_names.add(lowered)
        unique_cast.append(item)
    while len(unique_cast) < 3:
        index = len(unique_cast) + 1
        unique_cast.append(
            {
                "name": f"Civic Figure {index}",
                "role": "Stakeholder",
                "agenda": "Protect their corner of the city during the crisis.",
                "red_line": "Will not accept total collapse without resistance.",
                "pressure_signature": "Pushes for quick action whenever the public mood worsens.",
            }
        )
    return {"cast": unique_cast[:5]}


def _normalize_cast_member_payload(
    gateway: CapabilityGatewayCore,
    payload: dict[str, Any],
    *,
    slot_label: str,
    public_role: str,
    agenda_anchor: str,
    red_line_anchor: str,
    pressure_vector: str,
) -> dict[str, Any]:
    source = payload.get("member") if isinstance(payload.get("member"), dict) else payload
    if not isinstance(source, dict):
        source = {}
    name = trim_text(source.get("name") or slot_label, 80)
    role = trim_text(source.get("role") or public_role, 120)
    return {
        "name": name,
        "role": role,
        "agenda": trim_text(source.get("agenda") or agenda_anchor, 220),
        "red_line": trim_text(source.get("red_line") or red_line_anchor, 220),
        "pressure_signature": trim_text(source.get("pressure_signature") or pressure_vector, 220),
    }


def _normalize_cast_member_semantics_payload(
    gateway: CapabilityGatewayCore,
    payload: dict[str, Any],
    *,
    slot_label: str,
) -> dict[str, Any]:
    source = payload.get("member") if isinstance(payload.get("member"), dict) else payload
    if not isinstance(source, dict):
        source = {}
    name = trim_text(source.get("name") or source.get("person_name") or slot_label, 80)
    agenda_detail = trim_text(
        source.get("agenda_detail")
        or source.get("agenda")
        or source.get("leverage_source")
        or "Uses their position to turn private hesitation into public leverage.",
        180,
    )
    red_line_detail = trim_text(
        source.get("red_line_detail")
        or source.get("red_line")
        or source.get("private_stake")
        or "Refuses to let the settlement erase what they believe the crisis entitles them to protect.",
        180,
    )
    pressure_detail = trim_text(
        source.get("pressure_detail")
        or source.get("pressure_signature")
        or source.get("pressure_instinct")
        or "Their instincts sharpen whenever hesitation starts to look like weakness in public.",
        180,
    )
    return {
        "name": name,
        "agenda_detail": agenda_detail,
        "red_line_detail": red_line_detail,
        "pressure_detail": pressure_detail,
    }


def _cast_slot_from_payload(slot: dict[str, Any]) -> CastOverviewSlotDraft:
    return CastOverviewSlotDraft(
        slot_label=str(slot.get("slot_label") or "Civic Role"),
        public_role=str(slot.get("public_role") or "Stakeholder"),
        relationship_to_protagonist=str(slot.get("relationship_to_protagonist") or "Complicates or supports the protagonist under pressure."),
        agenda_anchor=str(slot.get("agenda_anchor") or "Protect their institutional stake while the crisis unfolds."),
        red_line_anchor=str(slot.get("red_line_anchor") or "Will not accept being cut out of the settlement."),
        pressure_vector=str(slot.get("pressure_vector") or "Pushes harder for leverage as public pressure rises."),
        archetype_id=slot.get("archetype_id"),
        relationship_dynamic_id=slot.get("relationship_dynamic_id"),
        counter_trait=slot.get("counter_trait"),
        pressure_tell=slot.get("pressure_tell"),
    )


def _generate_cast_member_semantics_result(
    gateway: CapabilityGatewayCore,
    *,
    primary_payload: dict[str, Any],
    final_retry_payload: dict[str, Any],
    prompts: tuple[str, ...],
    slot_label: str,
    previous_response_id: str | None,
    cast_strategy: str,
    high_risk_slot: bool = False,
):
    skill_packet = _cast_skill_packet(
        skill_id="author.cast_member.semantics",
        capability="author.cast_member_generate",
        required_output_contract="Return exactly one CastMemberSemanticsDraft JSON object.",
        task_brief=prompts[0],
        extra_payload=primary_payload,
        final_retry_extra_payload=final_retry_payload,
        context_cards=(
            ContextCard("cast_slot_card", primary_payload.get("cast_slot") or final_retry_payload.get("cast_slot") or {}, priority=10),
            ContextCard("existing_cast_card", primary_payload.get("existing_cast") or [], priority=20),
            ContextCard("focused_brief_card", primary_payload.get("focused_brief") or final_retry_payload.get("focused_brief") or {}, priority=30),
            ContextCard("story_frame_hint_card", primary_payload.get("story_frame_hint") or {}, priority=40),
        ),
        repair_note=prompts[1] if len(prompts) > 1 else None,
        final_contract_note=prompts[2] if len(prompts) > 2 else None,
    )
    return invoke_structured_generation_with_retries(
        gateway,
        capability="author.cast_member_generate",
        primary_payload=primary_payload,
        final_retry_payload=final_retry_payload,
        prompts=prompts,
        previous_response_id=previous_response_id,
        max_output_tokens=_cast_member_max_output_tokens(gateway, cast_strategy) + (180 if high_risk_slot else 0),
        operation_name="cast_member_semantics",
        skill_packet=skill_packet,
        parse_value=lambda raw_payload: CastMemberSemanticsDraft.model_validate(
            _normalize_cast_member_semantics_payload(
                gateway,
                raw_payload,
                slot_label=slot_label,
            )
        ),
    )


def generate_cast_overview(
    gateway: CapabilityGatewayCore,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    *,
    previous_response_id: str | None = None,
    cast_strategy: str | None = None,
):
    payload: dict[str, Any] = {
        "story_frame": story_frame.model_dump(mode="json"),
    }
    if not (gateway.text_policy("author.cast_member_generate").use_session_cache and previous_response_id):
        payload["focused_brief"] = focused_brief.model_dump(mode="json")
    resolved_cast_strategy = cast_strategy or plan_story_theme(focused_brief, story_frame).cast_strategy
    system_prompt = (
        "You are the Cast Overview generator. Return one strict JSON object matching CastOverviewDraft. "
        "Do not output markdown. Design 3-5 cast slots that describe the broad social and conflict structure before character specifics are written. "
        "Each cast slot must include: slot_label, public_role, relationship_to_protagonist, agenda_anchor, red_line_anchor, pressure_vector. "
        "Keep the slots distinct in function and pressure behavior. "
        "Also return 2-6 relationship_summary lines that explain the broad conflict web across the cast. "
        f"{prompt_role_instruction(focused_brief.language, en_role='a senior ensemble drama designer', zh_role='资深中文群像角色策划')} "
        f"{output_language_instruction(focused_brief.language)} "
        f"{_cast_theme_guidance(resolved_cast_strategy)}"
    )
    skill_packet = _cast_skill_packet(
        skill_id="author.cast_overview.generate",
        capability="author.cast_member_generate",
        required_output_contract="Return exactly one CastOverviewDraft JSON object.",
        task_brief=system_prompt,
        extra_payload=payload,
        context_cards=(
            ContextCard("story_frame_card", story_frame.model_dump(mode="json"), priority=10),
            ContextCard("focused_brief_card", payload.get("focused_brief") or {}, priority=20),
        ),
    )
    return invoke_structured_generation_with_retries(
        gateway,
        capability="author.cast_member_generate",
        primary_payload=payload,
        prompts=(system_prompt,),
        previous_response_id=previous_response_id,
        max_output_tokens=_cast_overview_max_output_tokens(gateway, resolved_cast_strategy),
        operation_name="cast_overview_generate",
        skill_packet=skill_packet,
        parse_value=lambda raw_payload: CastOverviewDraft.model_validate(
            _normalize_cast_overview_payload(gateway, raw_payload)
        ),
    )


def glean_cast_overview(
    gateway: CapabilityGatewayCore,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    partial_cast_overview: CastOverviewDraft,
    *,
    previous_response_id: str | None = None,
    cast_strategy: str | None = None,
):
    payload: dict[str, Any] = {
        "story_frame": story_frame.model_dump(mode="json"),
        "partial_cast_overview": partial_cast_overview.model_dump(mode="json"),
    }
    if not (gateway.text_policy("author.cast_member_repair").use_session_cache and previous_response_id):
        payload["focused_brief"] = focused_brief.model_dump(mode="json")
    resolved_cast_strategy = cast_strategy or plan_story_theme(focused_brief, story_frame).cast_strategy
    system_prompt = (
        "You are the Cast Overview repair generator. Return one strict JSON object matching CastOverviewDraft. "
        "Improve the existing partial_cast_overview instead of replacing it wholesale. "
        "Keep any specific useful slot labels, roles, and relationship structure that already fit the story. "
        "Replace placeholder or generic slot text with sharper conflict structure. "
        "Return a complete CastOverviewDraft with 3-5 cast slots and 2-6 relationship_summary lines. "
        f"{prompt_role_instruction(focused_brief.language, en_role='a senior ensemble drama editor', zh_role='资深中文角色结构编辑')} "
        f"{output_language_instruction(focused_brief.language)} "
        f"{_cast_theme_guidance(resolved_cast_strategy)}"
    )
    skill_packet = _cast_skill_packet(
        skill_id="author.cast_overview.glean",
        capability="author.cast_member_repair",
        required_output_contract="Return exactly one CastOverviewDraft JSON object.",
        task_brief=system_prompt,
        extra_payload=payload,
        context_cards=(
            ContextCard("story_frame_card", story_frame.model_dump(mode="json"), priority=10),
            ContextCard("partial_cast_overview_card", partial_cast_overview.model_dump(mode="json"), priority=20),
            ContextCard("focused_brief_card", payload.get("focused_brief") or {}, priority=30),
        ),
    )
    return invoke_structured_generation_with_retries(
        gateway,
        capability="author.cast_member_repair",
        primary_payload=payload,
        prompts=(system_prompt,),
        previous_response_id=previous_response_id,
        max_output_tokens=_cast_overview_max_output_tokens(gateway, resolved_cast_strategy),
        operation_name="cast_overview_glean",
        skill_packet=skill_packet,
        parse_value=lambda raw_payload: CastOverviewDraft.model_validate(
            _normalize_cast_overview_payload(gateway, raw_payload)
        ),
    )


def generate_story_cast(
    gateway: CapabilityGatewayCore,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    cast_overview: CastOverviewDraft,
    *,
    previous_response_id: str | None = None,
    cast_strategy: str | None = None,
):
    payload: dict[str, Any] = {
        "story_frame": story_frame.model_dump(mode="json"),
        "cast_overview": cast_overview.model_dump(mode="json"),
    }
    if not (gateway.text_policy("author.cast_member_generate").use_session_cache and previous_response_id):
        payload["focused_brief"] = focused_brief.model_dump(mode="json")
    resolved_cast_strategy = cast_strategy or plan_story_theme(focused_brief, story_frame).cast_strategy
    system_prompt = (
        "You are the NPC Ensemble generator. Return one strict JSON object matching CastDraft. "
        "Do not output markdown. Design 3-5 named civic actors with distinct agendas, red lines, and pressure signatures. "
        "Use cast_overview as a binding scaffold: keep one character per cast slot and preserve each slot's conflict function. "
        "Keep them specific to the existing story frame rather than generic archetypes. "
        "Agendas should realize agenda_anchor, red_line should realize red_line_anchor, "
        "and pressure_signature should realize pressure_vector in concrete character language. "
        f"{prompt_role_instruction(focused_brief.language, en_role='a senior character writer for civic thrillers', zh_role='擅长政治惊悚的资深中文角色编辑')} "
        f"{output_language_instruction(focused_brief.language)} "
        f"{_cast_theme_guidance(resolved_cast_strategy)}"
    )
    skill_packet = _cast_skill_packet(
        skill_id="author.cast_full.generate",
        capability="author.cast_member_generate",
        required_output_contract="Return exactly one CastDraft JSON object.",
        task_brief=system_prompt,
        extra_payload=payload,
        context_cards=(
            ContextCard("story_frame_card", story_frame.model_dump(mode="json"), priority=10),
            ContextCard("cast_overview_card", cast_overview.model_dump(mode="json"), priority=20),
            ContextCard("focused_brief_card", payload.get("focused_brief") or {}, priority=30),
        ),
    )
    return invoke_structured_generation_with_retries(
        gateway,
        capability="author.cast_member_generate",
        primary_payload=payload,
        prompts=(system_prompt,),
        previous_response_id=previous_response_id,
        max_output_tokens=_cast_overview_max_output_tokens(gateway, resolved_cast_strategy),
        operation_name="cast_generate_full",
        skill_packet=skill_packet,
        parse_value=lambda raw_payload: CastDraft.model_validate(_normalize_cast_payload(gateway, raw_payload)),
    )


def generate_story_cast_member(
    gateway: CapabilityGatewayCore,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    cast_slot: dict[str, Any],
    existing_cast: list[dict[str, Any]],
    *,
    previous_response_id: str | None = None,
    cast_strategy: str | None = None,
):
    from rpg_backend.author.gateway import AuthorGatewayError
    from rpg_backend.responses_transport import StructuredResponse

    resolved_cast_strategy = cast_strategy or plan_story_theme(focused_brief, story_frame).cast_strategy
    payload: dict[str, Any] = {
        "story_frame": story_frame.model_dump(mode="json"),
        "cast_slot": cast_slot,
        "existing_cast": existing_cast,
    }
    if gateway.text_policy("author.cast_member_generate").use_session_cache and previous_response_id:
        payload = {
            "story_frame_hint": _slim_story_frame(story_frame),
            "cast_slot": cast_slot,
            "existing_cast": _slim_existing_cast(existing_cast),
            "theme_hint": {
                "cast_strategy": resolved_cast_strategy,
            },
        }
    else:
        payload["focused_brief"] = focused_brief.model_dump(mode="json")
    slot = _cast_slot_from_payload(cast_slot)
    high_risk_slot = is_legitimacy_broker_slot(resolved_cast_strategy, slot)
    final_retry_payload = {
        "cast_slot": cast_slot,
        "existing_cast": existing_cast,
    }
    if not (gateway.text_policy("author.cast_member_generate").use_session_cache and previous_response_id):
        final_retry_payload["focused_brief"] = focused_brief.model_dump(mode="json")
    system_prompt = (
        "You are the NPC semantic generator. Return one strict JSON object matching CastMemberSemanticsDraft. "
        "Do not output markdown. Write exactly one named civic actor for the given cast_slot. "
        "Return only: name, agenda_detail, red_line_detail, pressure_detail. "
        "Keep the slot's public_role and structural function, but do not restate the anchors verbatim. "
        "The new character must differ from existing_cast in tactic and pressure behavior. "
        "Avoid placeholder names and do not use the slot label or public role as the character name. "
        "Use cast_slot.counter_trait and cast_slot.pressure_tell to keep the details concrete. "
        f"{prompt_role_instruction(focused_brief.language, en_role='a senior character writer', zh_role='资深中文人物设定编辑')} "
        f"{output_language_instruction(focused_brief.language)} "
        f"{_cast_theme_guidance(resolved_cast_strategy)}"
    )
    if high_risk_slot:
        system_prompt += (
            " This slot is the coalition rival. Keep the rival concrete, politically calculating, and tightly tied to settlement leverage. "
            "Prefer a short two-word person name. Keep every detail terse and bargaining-focused."
        )
    retry_prompt = (
        "Return only one JSON object with exactly these four string keys: "
        "name, agenda_detail, red_line_detail, pressure_detail. "
        "No markdown, no explanation, no nesting, no extra keys. "
        "Keep each value short and concrete. "
        "Do not use the slot label or public role as the name."
    )
    if high_risk_slot:
        retry_prompt += " This is the coalition rival slot. Make the details about leverage, exclusion, and settlement bargaining."
    final_retry_prompt = (
        "Output raw JSON only. Exactly four keys: name, agenda_detail, red_line_detail, pressure_detail. "
        "Each value must be a short string. No prose outside JSON. No code fences. No extra keys."
    )
    if high_risk_slot:
        final_retry_prompt += " Rival slot only. Keep each detail under twelve words."
    try:
        semantics_result = _generate_cast_member_semantics_result(
            gateway,
            primary_payload=payload,
            final_retry_payload=final_retry_payload,
            prompts=(system_prompt, retry_prompt, final_retry_prompt),
            slot_label=slot.slot_label,
            previous_response_id=previous_response_id,
            cast_strategy=resolved_cast_strategy,
            high_risk_slot=high_risk_slot,
        )
        return StructuredResponse(
            value=compile_cast_member_semantics(
                semantics_result.value,
                slot,
                focused_brief,
                len(existing_cast),
                {str(item.get("name")) for item in existing_cast if item.get("name")},
            ),
            response_id=semantics_result.response_id,
        )
    except AuthorGatewayError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AuthorGatewayError(
            code="llm_schema_invalid",
            message=str(exc),
            status_code=502,
        ) from exc


def glean_story_cast_member(
    gateway: CapabilityGatewayCore,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    cast_slot: dict[str, Any],
    existing_cast: list[dict[str, Any]],
    partial_member: dict[str, Any],
    *,
    previous_response_id: str | None = None,
    cast_strategy: str | None = None,
):
    from rpg_backend.author.gateway import AuthorGatewayError
    from rpg_backend.responses_transport import StructuredResponse

    resolved_cast_strategy = cast_strategy or plan_story_theme(focused_brief, story_frame).cast_strategy
    payload: dict[str, Any] = {
        "story_frame": story_frame.model_dump(mode="json"),
        "cast_slot": cast_slot,
        "existing_cast": existing_cast,
        "partial_member": partial_member,
    }
    if gateway.text_policy("author.cast_member_repair").use_session_cache and previous_response_id:
        payload = {
            "story_frame_hint": _slim_story_frame(story_frame),
            "cast_slot": cast_slot,
            "existing_cast": _slim_existing_cast(existing_cast),
            "partial_member": partial_member,
            "theme_hint": {
                "cast_strategy": resolved_cast_strategy,
            },
        }
    else:
        payload["focused_brief"] = focused_brief.model_dump(mode="json")
    slot = _cast_slot_from_payload(cast_slot)
    high_risk_slot = is_legitimacy_broker_slot(resolved_cast_strategy, slot)
    final_retry_payload = {
        "cast_slot": cast_slot,
        "partial_member": partial_member,
    }
    if not (gateway.text_policy("author.cast_member_repair").use_session_cache and previous_response_id):
        final_retry_payload["focused_brief"] = focused_brief.model_dump(mode="json")
    system_prompt = (
        "You are the NPC semantic repair generator. Return one strict JSON object matching CastMemberSemanticsDraft. "
        "Improve partial_member instead of replacing it wholesale. "
        "Return only: name, agenda_detail, red_line_detail, pressure_detail. "
        "Preserve any good person-like name if it fits the cast_slot. "
        "If the name is too close to cast_slot.slot_label or cast_slot.public_role, replace it with a person-like name. "
        "Sharpen vague details so the character becomes concrete and distinct. "
        f"{prompt_role_instruction(focused_brief.language, en_role='a senior character revision editor', zh_role='资深中文人物润色编辑')} "
        f"{output_language_instruction(focused_brief.language)} "
        f"{_cast_theme_guidance(resolved_cast_strategy)}"
    )
    if high_risk_slot:
        system_prompt += (
            " This slot is the coalition rival. Keep the rival concrete, politically calculating, and tightly tied to settlement leverage. "
            "Prefer a short two-word person name. Keep every detail terse and bargaining-focused."
        )
    retry_prompt = (
        "Repair the member and return only one JSON object with exactly these four string keys: "
        "name, agenda_detail, red_line_detail, pressure_detail. "
        "No markdown, no explanation, no nesting, no extra keys. "
        "If the current name is generic or matches the slot label, replace it with a person-like name."
    )
    if high_risk_slot:
        retry_prompt += " Rival slot only. Make the details about leverage, exclusion, and settlement bargaining."
    final_retry_prompt = (
        "Output raw JSON only. Exactly four keys: name, agenda_detail, red_line_detail, pressure_detail. "
        "Each value must be a short string. No prose outside JSON. No code fences. No extra keys."
    )
    if high_risk_slot:
        final_retry_prompt += " Rival slot only. Keep each detail under twelve words."
    try:
        semantics_result = _generate_cast_member_semantics_result(
            gateway,
            primary_payload=payload,
            final_retry_payload=final_retry_payload,
            prompts=(system_prompt, retry_prompt, final_retry_prompt),
            slot_label=slot.slot_label,
            previous_response_id=previous_response_id,
            cast_strategy=resolved_cast_strategy,
            high_risk_slot=high_risk_slot,
        )
        return StructuredResponse(
            value=compile_cast_member_semantics(
                semantics_result.value,
                slot,
                focused_brief,
                len(existing_cast),
                {str(item.get("name")) for item in existing_cast if item.get("name")},
            ),
            response_id=semantics_result.response_id,
        )
    except AuthorGatewayError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AuthorGatewayError(
            code="llm_schema_invalid",
            message=str(exc),
            status_code=502,
        ) from exc


def glean_story_cast(
    gateway: CapabilityGatewayCore,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    cast_overview: CastOverviewDraft,
    partial_cast: CastDraft,
    *,
    previous_response_id: str | None = None,
):
    payload: dict[str, Any] = {
        "story_frame": story_frame.model_dump(mode="json"),
        "cast_overview": cast_overview.model_dump(mode="json"),
        "partial_cast": partial_cast.model_dump(mode="json"),
    }
    if not (gateway.text_policy("author.cast_member_repair").use_session_cache and previous_response_id):
        payload["focused_brief"] = focused_brief.model_dump(mode="json")
    system_prompt = (
        "You are the NPC Ensemble repair generator. Return one strict JSON object matching CastDraft. "
        "Improve partial_cast instead of discarding it wholesale. "
        "Keep any specific useful names or roles that already fit the story. "
        "Replace placeholder names and generic agenda, red_line, or pressure_signature text with concrete character language. "
        f"{prompt_role_instruction(focused_brief.language, en_role='a senior ensemble cast editor', zh_role='资深中文角色统稿编辑')} "
        f"{output_language_instruction(focused_brief.language)} "
        "Use cast_overview as the binding scaffold and return a complete CastDraft."
    )
    skill_packet = _cast_skill_packet(
        skill_id="author.cast_full.glean",
        capability="author.cast_member_repair",
        required_output_contract="Return exactly one CastDraft JSON object.",
        task_brief=system_prompt,
        extra_payload=payload,
        context_cards=(
            ContextCard("story_frame_card", story_frame.model_dump(mode="json"), priority=10),
            ContextCard("cast_overview_card", cast_overview.model_dump(mode="json"), priority=20),
            ContextCard("partial_cast_card", partial_cast.model_dump(mode="json"), priority=30),
            ContextCard("focused_brief_card", payload.get("focused_brief") or {}, priority=40),
        ),
    )
    return invoke_structured_generation_with_retries(
        gateway,
        capability="author.cast_member_repair",
        primary_payload=payload,
        prompts=(system_prompt,),
        previous_response_id=previous_response_id,
        max_output_tokens=gateway.text_policy("author.cast_member_repair").max_output_tokens,
        operation_name="cast_glean_full",
        skill_packet=skill_packet,
        parse_value=lambda raw_payload: CastDraft.model_validate(_normalize_cast_payload(gateway, raw_payload)),
    )

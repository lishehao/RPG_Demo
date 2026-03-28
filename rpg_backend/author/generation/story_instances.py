from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.author.contracts import (
    CastStoryInstanceSnapshot,
    FocusedBrief,
    OverviewCastDraft,
    StoryFrameDraft,
    StoryInstanceMaterializationSource,
)
from rpg_backend.author.generation.runner import invoke_structured_generation_with_retries
from rpg_backend.generation_skill import ContextCard, GenerationSkillPacket, build_role_style_context
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis
from rpg_backend.content_language import output_language_instruction, prompt_role_instruction
from rpg_backend.llm_gateway import CapabilityGatewayCore
from rpg_backend.responses_transport import StructuredResponse
from rpg_backend.roster.template_profiles import ResolvedCharacterTemplateProfile, resolved_template_profile

if TYPE_CHECKING:
    from rpg_backend.roster.contracts import CharacterRosterEntry


class CharacterStoryInstanceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=120)
    roster_public_summary: str = Field(min_length=1, max_length=220)
    agenda: str = Field(min_length=1, max_length=220)
    red_line: str = Field(min_length=1, max_length=220)
    pressure_signature: str = Field(min_length=1, max_length=220)
    instance_experience_summary: str = Field(min_length=1, max_length=220)
    instance_personality_delta: str = Field(min_length=1, max_length=180)


_EN_FEMALE_TERMS = (
    "she",
    "her",
    "hers",
    "herself",
    "woman",
    "female",
    "girl",
    "lady",
    "mother",
    "daughter",
    "wife",
    "sister",
)
_EN_MALE_TERMS = (
    "he",
    "him",
    "his",
    "himself",
    "man",
    "male",
    "boy",
    "gentleman",
    "father",
    "son",
    "husband",
    "brother",
)
_ZH_FEMALE_TERMS = ("她", "她的", "女士", "小姐", "女人", "女孩", "母亲", "女儿", "妻子", "姐妹")
_ZH_MALE_TERMS = ("他", "他的", "先生", "男人", "男孩", "父亲", "儿子", "丈夫", "兄弟")


def _contains_english_gender_terms(text: str, terms: tuple[str, ...]) -> bool:
    lowered = str(text or "").casefold()
    return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms)


def _contains_chinese_gender_terms(text: str, terms: tuple[str, ...]) -> bool:
    raw = str(text or "")
    return any(term in raw for term in terms)


def _violates_gender_lock(text: str, gender_lock: str | None) -> bool:
    normalized = str(gender_lock or "").strip().casefold()
    if not normalized or not str(text or "").strip():
        return False
    female_hit = _contains_english_gender_terms(text, _EN_FEMALE_TERMS) or _contains_chinese_gender_terms(text, _ZH_FEMALE_TERMS)
    male_hit = _contains_english_gender_terms(text, _EN_MALE_TERMS) or _contains_chinese_gender_terms(text, _ZH_MALE_TERMS)
    if normalized == "female":
        return male_hit
    if normalized == "male":
        return female_hit
    if normalized in {"nonbinary", "unspecified"}:
        return female_hit or male_hit
    return False


def sanitize_story_character_member(
    *,
    base_member: OverviewCastDraft,
    candidate_member: OverviewCastDraft,
    entry: CharacterRosterEntry | None,
) -> OverviewCastDraft:
    violation_fields = story_character_gender_lock_violation_fields(
        candidate_member=candidate_member,
        entry=entry,
    )
    if not violation_fields:
        return candidate_member
    updates: dict[str, str | None] = {
        field_name: getattr(base_member, field_name)
        for field_name in violation_fields
    }
    return candidate_member.model_copy(update=updates)


def story_character_gender_lock_violation_fields(
    *,
    candidate_member: OverviewCastDraft,
    entry: CharacterRosterEntry | None,
) -> tuple[str, ...]:
    gender_lock = str(getattr(entry, "gender_lock", None) or "").strip() or None
    if gender_lock is None:
        return ()
    updates: list[str] = []
    for field_name in ("role", "roster_public_summary", "agenda", "red_line", "pressure_signature"):
        candidate_value = getattr(candidate_member, field_name)
        if candidate_value and _violates_gender_lock(candidate_value, gender_lock):
            updates.append(field_name)
    return tuple(updates)


def _default_instance(
    *,
    base_member: OverviewCastDraft,
) -> CharacterStoryInstanceDraft:
    return CharacterStoryInstanceDraft(
        role=base_member.role,
        roster_public_summary=base_member.roster_public_summary or base_member.agenda,
        agenda=base_member.agenda,
        red_line=base_member.red_line,
        pressure_signature=base_member.pressure_signature,
        instance_experience_summary=base_member.roster_public_summary or base_member.agenda,
        instance_personality_delta="Keeps the same core instincts, but this crisis has sharpened what they choose to emphasize.",
    )


def _normalize_instance_payload(
    payload: dict[str, Any],
    *,
    base_member: OverviewCastDraft,
) -> CharacterStoryInstanceDraft:
    source = payload.get("instance") if isinstance(payload.get("instance"), dict) else payload
    if not isinstance(source, dict):
        source = {}
    fallback = _default_instance(base_member=base_member)
    return CharacterStoryInstanceDraft(
        role=trim_ellipsis(str(source.get("role") or fallback.role), 120),
        roster_public_summary=trim_ellipsis(
            str(source.get("roster_public_summary") or source.get("public_summary") or fallback.roster_public_summary),
            220,
        ),
        agenda=trim_ellipsis(str(source.get("agenda") or fallback.agenda), 220),
        red_line=trim_ellipsis(str(source.get("red_line") or fallback.red_line), 220),
        pressure_signature=trim_ellipsis(str(source.get("pressure_signature") or fallback.pressure_signature), 220),
        instance_experience_summary=trim_ellipsis(
            str(source.get("instance_experience_summary") or fallback.instance_experience_summary),
            220,
        ),
        instance_personality_delta=trim_ellipsis(
            str(source.get("instance_personality_delta") or fallback.instance_personality_delta),
            180,
        ),
    )


def _system_prompts(language: str) -> tuple[str, ...]:
    base = (
        f"{prompt_role_instruction(language, en_role='a senior developmental editor for interactive fiction', zh_role='资深中文互动叙事编辑')} "
        f"{output_language_instruction(language)} "
        "You materialize a story-specific variation of a canonical supporting character. "
        "Return strict JSON matching CharacterStoryInstanceDraft. "
        "You are not creating a new person. "
        "Do not rename the character. Do not change face, portrait, or canonical identity. "
        "Preserve the same personality core, gender lock, and long-term identity, but adapt role phrasing, public summary, agenda, red line, pressure signature, and concrete experience framing to this story. "
        "Large variation is allowed: you may significantly reframe what this person is doing, what they recently lived through, and which part of their temperament now dominates on the page. "
        "The variation should feel like the same person in another timeline of civic pressure, not a new archetype or a softened paraphrase of the template. "
        "Keep the output compact, specific, and story-bound."
    )
    repair = (
        base
        + " Repair invalid output by keeping the same person and returning only the allowed mutable fields."
    )
    return base, repair


def _payload(
    *,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    slot_payload: dict[str, Any],
    entry: CharacterRosterEntry,
    template_profile: ResolvedCharacterTemplateProfile,
    base_member: OverviewCastDraft,
    primary_theme: str | None,
    story_frame_strategy: str | None,
) -> dict[str, Any]:
    return {
        "focused_brief": focused_brief.model_dump(mode="json"),
        "story_frame": {
            "title": story_frame.title,
            "premise": story_frame.premise,
            "tone": story_frame.tone,
            "stakes": story_frame.stakes,
            "style_guard": story_frame.style_guard,
        },
        "slot": slot_payload,
        "primary_theme": primary_theme,
        "story_frame_strategy": story_frame_strategy,
        "canonical_template": {
            "character_id": entry.character_id,
            "name": entry.name_zh if focused_brief.language == "zh" else entry.name_en,
            "role_hint": entry.role_hint_zh if focused_brief.language == "zh" else entry.role_hint_en,
            "public_summary": entry.public_summary_zh if focused_brief.language == "zh" else entry.public_summary_en,
            "agenda_seed": entry.agenda_seed_zh if focused_brief.language == "zh" else entry.agenda_seed_en,
            "red_line_seed": entry.red_line_seed_zh if focused_brief.language == "zh" else entry.red_line_seed_en,
            "pressure_signature_seed": (
                entry.pressure_signature_seed_zh if focused_brief.language == "zh" else entry.pressure_signature_seed_en
            ),
            "gender_lock": template_profile.gender_lock,
            "personality_core": template_profile.personality_core,
            "experience_anchor": template_profile.experience_anchor,
            "identity_lock_notes": template_profile.identity_lock_notes,
            "portrait_locked": True,
        },
        "baseline_instance": {
            "role": base_member.role,
            "roster_public_summary": base_member.roster_public_summary,
            "agenda": base_member.agenda,
            "red_line": base_member.red_line,
            "pressure_signature": base_member.pressure_signature,
        },
    }


def generate_story_character_instance(
    gateway: CapabilityGatewayCore,
    *,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    slot_payload: dict[str, Any],
    entry: CharacterRosterEntry,
    base_member: OverviewCastDraft,
    previous_response_id: str | None = None,
    primary_theme: str | None = None,
    story_frame_strategy: str | None = None,
) -> StructuredResponse[CharacterStoryInstanceDraft]:
    template_profile = resolved_template_profile(entry, focused_brief.language)
    prompts = _system_prompts(focused_brief.language)
    payload = _payload(
        focused_brief=focused_brief,
        story_frame=story_frame,
        slot_payload=slot_payload,
        entry=entry,
        template_profile=template_profile,
        base_member=base_member,
        primary_theme=primary_theme,
        story_frame_strategy=story_frame_strategy,
    )
    role_style, _role_context = build_role_style_context(
        language=focused_brief.language,
        en_role="a senior developmental editor for interactive fiction",
        zh_role="资深中文互动叙事编辑",
    )
    skill_packet = GenerationSkillPacket(
        skill_id="author.character_instance.variation",
        skill_version="v1",
        capability="author.character_instance_variation",
        contract_mode="strict_json_schema",
        role_style=role_style,
        required_output_contract="Return exactly one CharacterStoryInstanceDraft JSON object.",
        context_cards=(
            ContextCard("focused_brief_card", focused_brief.model_dump(mode="json"), priority=10),
            ContextCard("story_frame_card", story_frame.model_dump(mode="json"), priority=20),
            ContextCard("cast_slot_card", slot_payload, priority=30),
            ContextCard("template_profile_card", template_profile.model_dump(mode="json"), priority=40),
            ContextCard("base_member_card", base_member.model_dump(mode="json"), priority=50),
        ),
        task_brief=prompts[0],
        repair_mode="schema_repair",
        repair_note=prompts[1] if len(prompts) > 1 else "Repair invalid output while keeping the same JSON contract.",
        final_contract_note=prompts[2] if len(prompts) > 2 else "Return raw JSON only.",
        extra_payload=payload,
    )
    return invoke_structured_generation_with_retries(
        gateway,
        capability="author.character_instance_variation",
        primary_payload=payload,
        prompts=prompts,
        previous_response_id=previous_response_id,
        max_output_tokens=gateway.text_policy("author.character_instance_variation").max_output_tokens,
        operation_name="character_instance_variation",
        skill_packet=skill_packet,
        parse_value=lambda raw_payload: _normalize_instance_payload(
            raw_payload,
            base_member=base_member,
        ),
    )


def build_story_instance_snapshot(
    *,
    draft: CharacterStoryInstanceDraft,
    base_member: OverviewCastDraft,
    materialization_source: StoryInstanceMaterializationSource,
    gender_lock: str | None,
) -> CastStoryInstanceSnapshot:
    fallback = _default_instance(base_member=base_member)
    experience_summary = normalize_whitespace(draft.instance_experience_summary)
    personality_delta = normalize_whitespace(draft.instance_personality_delta)
    resolved_gender_lock = str(gender_lock or "").strip() or None
    if resolved_gender_lock and _violates_gender_lock(experience_summary, resolved_gender_lock):
        experience_summary = normalize_whitespace(fallback.instance_experience_summary)
    if resolved_gender_lock and _violates_gender_lock(personality_delta, resolved_gender_lock):
        personality_delta = normalize_whitespace(fallback.instance_personality_delta)
    return CastStoryInstanceSnapshot(
        instance_experience_summary=experience_summary,
        instance_personality_delta=personality_delta,
        materialization_source=materialization_source,
    )


def default_story_instance_snapshot(
    *,
    base_member: OverviewCastDraft,
    gender_lock: str | None,
    materialization_source: StoryInstanceMaterializationSource = "default",
) -> CastStoryInstanceSnapshot:
    return build_story_instance_snapshot(
        draft=_default_instance(base_member=base_member),
        base_member=base_member,
        materialization_source=materialization_source,
        gender_lock=gender_lock,
    )


def apply_story_character_instance(
    *,
    base_member: OverviewCastDraft,
    draft: CharacterStoryInstanceDraft,
    entry: CharacterRosterEntry | None = None,
    materialization_source: StoryInstanceMaterializationSource = "generated",
) -> OverviewCastDraft:
    candidate = base_member.model_copy(
        update={
            "role": normalize_whitespace(draft.role),
            "roster_public_summary": normalize_whitespace(draft.roster_public_summary),
            "agenda": normalize_whitespace(draft.agenda),
            "red_line": normalize_whitespace(draft.red_line),
            "pressure_signature": normalize_whitespace(draft.pressure_signature),
            "story_instance": build_story_instance_snapshot(
                draft=draft,
                base_member=base_member,
                materialization_source=materialization_source,
                gender_lock=getattr(entry, "gender_lock", None),
            ),
        }
    )
    return sanitize_story_character_member(
        base_member=base_member,
        candidate_member=candidate,
        entry=entry,
    )

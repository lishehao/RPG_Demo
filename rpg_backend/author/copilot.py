from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.author.compiler.bundle import build_design_bundle
from rpg_backend.author.compiler.routes import bundle_affordance_tags
from rpg_backend.author.compiler.rules import (
    build_default_rule_pack,
    merge_rule_pack,
    normalize_route_affordance_pack,
)
from rpg_backend.author.compiler.endings import normalize_ending_rules_draft
from rpg_backend.author.generation.story_instances import (
    apply_story_character_instance,
    default_story_instance_snapshot,
    generate_story_character_instance,
    sanitize_story_character_member,
)
from rpg_backend.author.contracts import (
    AffordanceEffectProfile,
    AuthorCopilotBeatRewrite,
    AuthorCopilotOperation,
    AuthorCopilotLockedBoundaries,
    AuthorCopilotProposalResponse,
    AuthorCopilotRewriteBrief,
    AuthorCopilotRewritePlan,
    AuthorCopilotRulePackRewrite,
    AuthorCopilotSessionResponse,
    AuthorCopilotSuggestion,
    AuthorCopilotWorkspaceSnapshot,
    AuthorCopilotWorkspaceView,
    AuthorCopilotCastRewrite,
    AuthorCopilotStoryFrameRewrite,
    CastDraft,
    ConditionBlock,
    AuthorEditorStateResponse,
    DesignBundle,
    EndingRule,
    EndingRulesDraft,
    RouteAffordancePackDraft,
    RouteUnlockRule,
)
from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.llm_gateway import CapabilityGatewayCore, GatewayCapabilityError, TextCapabilityRequest
from rpg_backend.author.normalize import normalize_whitespace, slugify, unique_preserve
from rpg_backend.content_language import (
    is_chinese_language,
    localized_text,
    output_language_instruction,
    prompt_role_instruction,
)
from rpg_backend.play.compiler import compile_play_plan
from rpg_backend.roster.contracts import CharacterRosterEntry
from rpg_backend.roster.service import get_character_roster_service
from rpg_backend.roster.template_profiles import template_profile_complete

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_STRUCTURE_REWRITE_PATTERNS = (
    "add a character",
    "remove a character",
    "add another character",
    "remove another character",
    "change the cast topology",
    "change topology",
    "add a beat",
    "remove a beat",
    "change beat count",
    "more beats",
    "fewer beats",
    "change max turns",
    "more turns",
    "change runtime profile",
    "change closeout profile",
    "增加角色",
    "删掉角色",
    "删除角色",
    "增加一幕",
    "加一幕",
    "删掉一幕",
    "删除一幕",
    "调整节拍数量",
    "修改节拍数量",
    "修改角色拓扑",
    "更改玩法轮廓",
    "修改回合上限",
    "增加回合",
    "改变 runtime profile",
)


CopilotIntentStrength = Literal["light", "medium", "strong"]
CopilotStoryFrameEmphasis = Literal["world_rules", "public_record"]
CopilotPoliticalTexture = Literal["factional", "dockside", "public_accountability", "institutional_conflict"]
CopilotProtagonistPressureStyle = Literal["assertive", "procedural", "public_confrontation"]
CopilotCastTexture = Literal["sharper_relationships", "factionalized", "dockside"]
CopilotBeatPressureShape = Literal["public_pressure", "reveal_chain", "costly_escalation"]
CopilotTruthExposureEmphasis = Literal["public_record", "ledger_audit", "corruption_exposure"]
CopilotRuleSemanticsEmphasis = Literal["exposure_routes", "public_accountability", "costly_settlement"]
CopilotUnsupportedReason = Literal["non_rewrite_request", "structure_request_only", "no_supported_dimension"]


class _CopilotEndingTiltIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    toward: Literal["mixed", "pyrrhic", "collapse"]
    intensity: CopilotIntentStrength = "medium"


class _CopilotIntentPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_frame_emphasis: CopilotStoryFrameEmphasis | None = None
    story_frame_intensity: CopilotIntentStrength = "medium"
    political_texture: CopilotPoliticalTexture | None = None
    political_texture_intensity: CopilotIntentStrength = "medium"
    protagonist_pressure_style: CopilotProtagonistPressureStyle | None = None
    protagonist_pressure_intensity: CopilotIntentStrength = "medium"
    cast_texture: CopilotCastTexture | None = None
    cast_texture_intensity: CopilotIntentStrength = "medium"
    beat_pressure_shape: CopilotBeatPressureShape | None = None
    beat_pressure_intensity: CopilotIntentStrength = "medium"
    truth_exposure_emphasis: CopilotTruthExposureEmphasis | None = None
    truth_exposure_intensity: CopilotIntentStrength = "medium"
    ending_tilt: _CopilotEndingTiltIntent | None = None
    rule_semantics_emphasis: CopilotRuleSemanticsEmphasis | None = None
    rule_semantics_intensity: CopilotIntentStrength = "medium"
    unsupported_structure_requested: bool = False
    unsupported_reason: CopilotUnsupportedReason | None = None


class _SynthesizedRewritePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: AuthorCopilotRewritePlan
    request_summary: str = Field(min_length=1, max_length=400)
    variant_label: str = Field(min_length=1, max_length=120)
    affected_sections: list[str] = Field(default_factory=list, max_length=4)
    impact_summary: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)
    fingerprint: str = Field(min_length=1, max_length=240)


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(value in text for value in values)


def _contains_story_terms(*values: str) -> bool:
    lowered = " ".join(values).casefold()
    return _contains_any(lowered, ("harbor", "port", "dock", "quarantine", "港", "码头", "检疫"))


def _contains_cjk_text(value: str) -> bool:
    return bool(_CJK_RE.search(value))


def _text_matches_story_language(value: str | None, language: str | None) -> bool:
    normalized = normalize_whitespace(str(value or ""))
    if not normalized:
        return False
    if is_chinese_language(language):
        return _contains_cjk_text(normalized)
    return True


def _rewrite_brief_matches_story_language(brief: AuthorCopilotRewriteBrief, language: str | None) -> bool:
    return _text_matches_story_language(brief.summary, language)


def _strings_match_story_language(values: list[str], language: str | None) -> bool:
    return all(_text_matches_story_language(value, language) for value in values if normalize_whitespace(value))


def _rewrite_plan_matches_story_language(plan: AuthorCopilotRewritePlan, language: str | None) -> bool:
    if plan.story_frame is not None:
        story_frame = plan.story_frame
        scalar_story_fields = [
            story_frame.title,
            story_frame.premise,
            story_frame.tone,
            story_frame.stakes,
            story_frame.style_guard,
        ]
        if not _strings_match_story_language([value for value in scalar_story_fields if value], language):
            return False
        if not _strings_match_story_language(list(story_frame.world_rules or []), language):
            return False
        if not _strings_match_story_language([item.text for item in story_frame.truths or []], language):
            return False
        if not _strings_match_story_language([item.label for item in story_frame.flags or []], language):
            return False
        if not _strings_match_story_language(
            [item.story_label for item in story_frame.state_axis_choices or [] if item.story_label],
            language,
        ):
            return False
    for item in plan.cast:
        cast_strings = [
            item.name,
            item.role,
            item.agenda,
            item.red_line,
            item.pressure_signature,
        ]
        if not _strings_match_story_language([value for value in cast_strings if value], language):
            return False
    for item in plan.beats:
        beat_strings = [
            item.title,
            item.goal,
            *(item.focus_names or []),
            *(item.conflict_pair or []),
            *(item.required_truth_texts or []),
            *(item.return_hooks or []),
        ]
        if not _strings_match_story_language([value for value in beat_strings if value], language):
            return False
    return True


def _explicit_fields(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_unset=True)


def _intent_has_supported_dimensions(intent: _CopilotIntentPacket | None) -> bool:
    if intent is None:
        return False
    return any(
        (
            intent.story_frame_emphasis,
            intent.political_texture,
            intent.protagonist_pressure_style,
            intent.cast_texture,
            intent.beat_pressure_shape,
            intent.truth_exposure_emphasis,
            intent.ending_tilt,
            intent.rule_semantics_emphasis,
        )
    )


def _intent_strength(text: str, *, default: CopilotIntentStrength = "medium") -> CopilotIntentStrength:
    lowered = text.casefold()
    if _contains_any(
        lowered,
        (
            "slightly",
            "lightly",
            "a bit",
            "轻一点",
            "稍微",
        ),
    ):
        return "light"
    if _contains_any(
        lowered,
        (
            "broaden",
            "push",
            "sharpen",
            "stronger",
            "harder",
            "more ",
            "强化",
            "更鲜明",
            "更强",
            "更偏",
            "更尖锐",
        ),
    ):
        return "strong"
    return default


def _semantic_score(text: str, patterns: tuple[str, ...]) -> int:
    lowered = text.casefold()
    return sum(1 for pattern in patterns if pattern in lowered)


def _is_non_rewrite_brief(text: str) -> bool:
    return _contains_any(
        text.casefold(),
        (
            "tell me a joke",
            "joke about",
            "write a poem",
            "what time is it",
            "讲个笑话",
            "写首诗",
            "几点了",
        ),
    )


def _mentions_structure_rewrite(text: str) -> bool:
    return _contains_any(text.casefold(), _STRUCTURE_REWRITE_PATTERNS)


def _classify_rewrite_intent_heuristically(
    *,
    instruction: str,
    rewrite_brief: str,
    editor_state: AuthorEditorStateResponse,
) -> _CopilotIntentPacket | None:
    combined = normalize_whitespace(f"{instruction}\n{rewrite_brief}")
    lowered = combined.casefold()
    if not lowered:
        return None
    if _is_non_rewrite_brief(combined):
        return _CopilotIntentPacket(unsupported_reason="non_rewrite_request")

    packet = _CopilotIntentPacket(
        unsupported_structure_requested=_mentions_structure_rewrite(combined),
    )

    if _semantic_score(
        lowered,
        (
            "story rules",
            "world rules",
            "world logic",
            "rule system",
            "世界规则",
            "规则逻辑",
            "世界逻辑",
        ),
    ):
        packet.story_frame_emphasis = "world_rules"
        packet.story_frame_intensity = _intent_strength(combined)

    if _semantic_score(
        lowered,
        (
            "public record",
            "record exposure",
            "archive exposure",
            "公开记录",
            "记录曝光",
            "档案曝光",
            "公开档案",
        ),
    ):
        if packet.story_frame_emphasis is None:
            packet.story_frame_emphasis = "public_record"
            packet.story_frame_intensity = _intent_strength(combined)
        packet.truth_exposure_emphasis = "public_record"
        packet.truth_exposure_intensity = _intent_strength(combined)

    if _semantic_score(
        lowered,
        (
            "ledger",
            "audit",
            "rolls",
            "manifest",
            "账本",
            "名册",
            "审计",
            "舱单",
        ),
    ):
        packet.truth_exposure_emphasis = packet.truth_exposure_emphasis or "ledger_audit"
        packet.truth_exposure_intensity = _intent_strength(combined)
        packet.rule_semantics_emphasis = packet.rule_semantics_emphasis or "exposure_routes"

    if _semantic_score(
        lowered,
        (
            "corruption",
            "cover-up",
            "forged",
            "falsified",
            "造假",
            "篡改",
            "掩盖",
            "黑幕",
        ),
    ):
        packet.truth_exposure_emphasis = packet.truth_exposure_emphasis or "corruption_exposure"
        packet.truth_exposure_intensity = _intent_strength(combined)

    if _semantic_score(
        lowered,
        (
            "political texture",
            "political struggle",
            "factional pressure",
            "factions",
            "political pull",
            "政治拉扯",
            "政治肌理",
            "派系",
            "派系压力",
            "联盟博弈",
        ),
    ):
        packet.political_texture = "factional"
        packet.political_texture_intensity = _intent_strength(combined)

    if _semantic_score(
        lowered,
        (
            "public accountability",
            "in public",
            "公开问责",
            "公开解释",
            "当众",
            "对照",
        ),
    ):
        packet.political_texture = packet.political_texture or "public_accountability"
        packet.political_texture_intensity = _intent_strength(combined)
        packet.rule_semantics_emphasis = packet.rule_semantics_emphasis or "public_accountability"

    if _contains_story_terms(
        editor_state.story_frame_view.title,
        editor_state.story_frame_view.premise,
        editor_state.summary.theme,
        lowered,
    ) and _semantic_score(lowered, ("dockside", "dock politics", "more dockside", "less bureaucratic", "码头政治", "不要港口官僚")):
        packet.political_texture = "dockside"
        packet.cast_texture = "dockside"
        packet.political_texture_intensity = _intent_strength(combined)
        packet.cast_texture_intensity = _intent_strength(combined)

    if _semantic_score(
        lowered,
        (
            "relationships sharper",
            "cast more factional",
            "cast more tense",
            "sharper relationships",
            "配角更像派系",
            "角色关系更尖锐",
            "角色关系更紧张",
        ),
    ):
        packet.cast_texture = "factionalized"
        packet.cast_texture_intensity = _intent_strength(combined)

    if _contains_any(lowered, ("更强硬", "更强势", "更硬", "更直接", "harder", "hardline", "more assertive", "more forceful")):
        packet.protagonist_pressure_style = "assertive"
        packet.protagonist_pressure_intensity = _intent_strength(combined)
    elif _semantic_score(lowered, ("procedural", "institutional", "程序强硬", "制度施压")):
        packet.protagonist_pressure_style = "procedural"
        packet.protagonist_pressure_intensity = _intent_strength(combined)
    elif _semantic_score(lowered, ("public confrontation", "公开对抗", "当众逼问", "point-blank")):
        packet.protagonist_pressure_style = "public_confrontation"
        packet.protagonist_pressure_intensity = _intent_strength(combined)

    if _semantic_score(lowered, ("public pressure", "公开压力", "公开施压")):
        packet.beat_pressure_shape = "public_pressure"
        packet.beat_pressure_intensity = _intent_strength(combined)
    elif _semantic_score(lowered, ("reveal chain", "expose the ledger", "record exposure", "记录曝光", "公开记录")):
        packet.beat_pressure_shape = "reveal_chain"
        packet.beat_pressure_intensity = _intent_strength(combined)
    elif _semantic_score(lowered, ("costly", "visible civic cost", "更有代价", "更明显的代价", "代价更重")):
        packet.beat_pressure_shape = "costly_escalation"
        packet.beat_pressure_intensity = _intent_strength(combined)

    if _contains_any(lowered, ("惨胜", "pyrrhic", "harsher ending", "visible civic cost", "代价更明显", "更偏惨胜")):
        packet.ending_tilt = _CopilotEndingTiltIntent(
            toward="pyrrhic",
            intensity=_intent_strength(combined),
        )
        packet.rule_semantics_emphasis = packet.rule_semantics_emphasis or "costly_settlement"
        packet.rule_semantics_intensity = _intent_strength(combined)
    elif _contains_any(lowered, ("collapse", "崩溃结局", "走向崩溃")):
        packet.ending_tilt = _CopilotEndingTiltIntent(
            toward="collapse",
            intensity=_intent_strength(combined),
        )

    if _semantic_score(
        lowered,
        (
            "route semantics",
            "exposure routes",
            "more reveal options",
            "路线语义",
            "更多曝光路线",
            "更多揭露选项",
        ),
    ):
        packet.rule_semantics_emphasis = "exposure_routes"
        packet.rule_semantics_intensity = _intent_strength(combined)

    if not _intent_has_supported_dimensions(packet):
        packet.unsupported_reason = (
            "structure_request_only"
            if packet.unsupported_structure_requested
            else "no_supported_dimension"
        )
        return packet
    return packet


def _normalize_rewrite_intent(
    *,
    gateway: CapabilityGatewayCore | None,
    instruction: str,
    rewrite_brief: str,
    editor_state: AuthorEditorStateResponse,
    locked_boundaries: AuthorCopilotLockedBoundaries,
) -> tuple[_CopilotIntentPacket | None, str]:
    if gateway is not None:
        payload = {
            "instruction": instruction,
            "rewrite_brief": rewrite_brief,
            "editor_state": editor_state.model_dump(mode="json"),
            "locked_boundaries": locked_boundaries.model_dump(mode="json"),
        }
        system_prompt = (
            "You normalize author rewrite requests into a constrained internal intent packet. "
            "Return strict JSON using enum ids only. "
            "Supported keys: story_frame_emphasis, story_frame_intensity, political_texture, political_texture_intensity, "
            "protagonist_pressure_style, protagonist_pressure_intensity, cast_texture, cast_texture_intensity, "
            "beat_pressure_shape, beat_pressure_intensity, truth_exposure_emphasis, truth_exposure_intensity, "
            "ending_tilt, rule_semantics_emphasis, rule_semantics_intensity, unsupported_structure_requested, unsupported_reason. "
            "Enum values: story_frame_emphasis=[world_rules,public_record]; "
            "political_texture=[factional,dockside,public_accountability,institutional_conflict]; "
            "protagonist_pressure_style=[assertive,procedural,public_confrontation]; "
            "cast_texture=[sharper_relationships,factionalized,dockside]; "
            "beat_pressure_shape=[public_pressure,reveal_chain,costly_escalation]; "
            "truth_exposure_emphasis=[public_record,ledger_audit,corruption_exposure]; "
            "rule_semantics_emphasis=[exposure_routes,public_accountability,costly_settlement]; "
            "intent strength=[light,medium,strong]; "
            "unsupported_reason=[non_rewrite_request,structure_request_only,no_supported_dimension]. "
            "ending_tilt is an object with toward=[mixed,pyrrhic,collapse] and intensity=[light,medium,strong]. "
            "Preserve locked boundaries and infer only currently supported Phase 1/2 rewrite dimensions. "
            "If the request mainly asks for unsupported structure edits, set unsupported_structure_requested=true."
        )
        try:
            response = gateway.invoke_text_capability(
                "copilot.reply",
                TextCapabilityRequest(
                    system_prompt=system_prompt,
                    user_payload=payload,
                    max_output_tokens=gateway.text_policy("copilot.reply").max_output_tokens,
                    operation_name="copilot_intent_normalize",
                ),
            )
            intent = _CopilotIntentPacket.model_validate(response.payload)
            if _intent_has_supported_dimensions(intent):
                return intent, "llm"
        except Exception:
            pass
    heuristic_intent = _classify_rewrite_intent_heuristically(
        instruction=instruction,
        rewrite_brief=rewrite_brief,
        editor_state=editor_state,
    )
    if heuristic_intent is not None and _intent_has_supported_dimensions(heuristic_intent):
        return heuristic_intent, "heuristic"
    return heuristic_intent, "heuristic"


def _roster_entry_for_id(character_id: str | None) -> CharacterRosterEntry | None:
    service = get_character_roster_service()
    return service.get_entry_by_id(character_id)


def _localized_roster_projection(entry: CharacterRosterEntry, language: str) -> dict[str, str | None]:
    if is_chinese_language(language):
        return {
            "name": entry.name_zh,
            "public_summary": entry.public_summary_zh,
            "agenda_seed": entry.agenda_seed_zh,
            "red_line_seed": entry.red_line_seed_zh,
            "pressure_seed": entry.pressure_signature_seed_zh,
        }
    return {
        "name": entry.name_en,
        "public_summary": entry.public_summary_en,
        "agenda_seed": entry.agenda_seed_en,
        "red_line_seed": entry.red_line_seed_en,
        "pressure_seed": entry.pressure_signature_seed_en,
    }


def _candidate_route_pack(
    snapshot: AuthorCopilotWorkspaceSnapshot,
    bundle: DesignBundle,
    rewrite: AuthorCopilotRulePackRewrite | None,
) -> RouteAffordancePackDraft:
    base_rule_pack = build_default_rule_pack(bundle)
    route_pack = (
        normalize_route_affordance_pack(snapshot.route_affordance_pack_draft, bundle)
        if snapshot.route_affordance_pack_draft is not None
        else RouteAffordancePackDraft(
            route_unlock_rules=list(base_rule_pack.route_unlock_rules),
            affordance_effect_profiles=list(base_rule_pack.affordance_effect_profiles),
        )
    )
    if rewrite is None:
        return route_pack
    explicit_rewrite = _explicit_fields(rewrite)
    route_updates: dict[str, Any] = {}
    if "route_unlock_rules" in explicit_rewrite and rewrite.route_unlock_rules is not None:
        route_updates["route_unlock_rules"] = list(rewrite.route_unlock_rules or [])
    if "affordance_effect_profiles" in explicit_rewrite and rewrite.affordance_effect_profiles is not None:
        route_updates["affordance_effect_profiles"] = list(rewrite.affordance_effect_profiles or [])
    if route_updates:
        route_pack = route_pack.model_copy(update=route_updates)
    return normalize_route_affordance_pack(route_pack, bundle)


def _candidate_ending_rules(
    snapshot: AuthorCopilotWorkspaceSnapshot,
    bundle: DesignBundle,
    rewrite: AuthorCopilotRulePackRewrite | None,
) -> EndingRulesDraft:
    base_rule_pack = build_default_rule_pack(bundle)
    ending_rules = (
        normalize_ending_rules_draft(snapshot.ending_rules_draft, bundle)
        if snapshot.ending_rules_draft is not None
        else EndingRulesDraft(ending_rules=list(base_rule_pack.ending_rules))
    )
    explicit_rewrite = _explicit_fields(rewrite) if rewrite is not None else {}
    if rewrite is not None and "ending_rules" in explicit_rewrite and rewrite.ending_rules is not None:
        ending_rules = EndingRulesDraft(ending_rules=list(rewrite.ending_rules or []))
    return normalize_ending_rules_draft(ending_rules, bundle)


def _compile_copilot_bundle(
    *,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
    rewrite: AuthorCopilotRulePackRewrite | None,
) -> tuple[AuthorCopilotWorkspaceSnapshot, DesignBundle]:
    bundle = build_design_bundle(
        story_frame=workspace_snapshot.story_frame_draft,
        cast_draft=workspace_snapshot.cast_draft,
        beat_plan_draft=workspace_snapshot.beat_plan_draft,
        focused_brief=workspace_snapshot.focused_brief,
    )
    route_pack = _candidate_route_pack(workspace_snapshot, bundle, rewrite)
    ending_rules = _candidate_ending_rules(workspace_snapshot, bundle, rewrite)
    bundle = bundle.model_copy(update={"rule_pack": merge_rule_pack(route_pack, ending_rules)})
    bundle = _adjust_ending_tilt(bundle=bundle, rewrite=rewrite)
    return (
        workspace_snapshot.model_copy(
            update={
                "route_affordance_pack_draft": route_pack,
                "ending_rules_draft": EndingRulesDraft(ending_rules=list(bundle.rule_pack.ending_rules)),
            }
        ),
        bundle,
    )


def _rewrite_reference_catalog(bundle: DesignBundle) -> dict[str, list[str]]:
    return {
        "beat_ids": [beat.beat_id for beat in bundle.beat_spine],
        "event_ids": [event_id for beat in bundle.beat_spine for event_id in beat.required_events],
        "axis_ids": [axis.axis_id for axis in bundle.state_schema.axes],
        "stance_ids": [stance.stance_id for stance in bundle.state_schema.stances],
        "truth_ids": [truth.truth_id for truth in bundle.story_bible.truth_catalog],
        "flag_ids": [flag.flag_id for flag in bundle.state_schema.flags],
        "ending_ids": [ending.ending_id for ending in bundle.story_bible.ending_catalog],
        "affordance_tags": bundle_affordance_tags(bundle),
    }


def _route_rule_references_valid(
    route_rule: Any,
    *,
    beat_ids: set[str],
    affordance_tags: set[str],
    axis_ids: set[str],
    stance_ids: set[str],
    truth_ids: set[str],
    event_ids: set[str],
    flag_ids: set[str],
) -> bool:
    if route_rule.beat_id not in beat_ids or route_rule.unlock_affordance_tag not in affordance_tags:
        return False
    conditions = route_rule.conditions
    return (
        all(axis_id in axis_ids for axis_id in (*conditions.min_axes.keys(), *conditions.max_axes.keys()))
        and all(stance_id in stance_ids for stance_id in conditions.min_stances.keys())
        and all(truth_id in truth_ids for truth_id in conditions.required_truths)
        and all(event_id in event_ids for event_id in conditions.required_events)
        and all(flag_id in flag_ids for flag_id in conditions.required_flags)
    )


def _ending_rule_references_valid(
    ending_rule: EndingRule,
    *,
    ending_ids: set[str],
    axis_ids: set[str],
    stance_ids: set[str],
    truth_ids: set[str],
    event_ids: set[str],
    flag_ids: set[str],
) -> bool:
    if ending_rule.ending_id not in ending_ids:
        return False
    conditions = ending_rule.conditions
    return (
        all(axis_id in axis_ids for axis_id in (*conditions.min_axes.keys(), *conditions.max_axes.keys()))
        and all(stance_id in stance_ids for stance_id in conditions.min_stances.keys())
        and all(truth_id in truth_ids for truth_id in conditions.required_truths)
        and all(event_id in event_ids for event_id in conditions.required_events)
        and all(flag_id in flag_ids for flag_id in conditions.required_flags)
    )


def _effect_profile_references_valid(
    profile: Any,
    *,
    affordance_tags: set[str],
    axis_ids: set[str],
    stance_ids: set[str],
) -> bool:
    return (
        profile.affordance_tag in affordance_tags
        and all(axis_id in axis_ids for axis_id in profile.axis_deltas.keys())
        and all(stance_id in stance_ids for stance_id in profile.stance_deltas.keys())
    )


def _proposal_matches_story_language(
    *,
    request_summary: str,
    variant_label: str,
    impact_summary: list[str],
    warnings: list[str],
    plan: AuthorCopilotRewritePlan,
    language: str | None,
) -> bool:
    if not _text_matches_story_language(request_summary, language):
        return False
    if not _text_matches_story_language(variant_label, language):
        return False
    for item in (*impact_summary, *warnings):
        if item and not _text_matches_story_language(item, language):
            return False
    return _rewrite_plan_matches_story_language(plan, language)


def _forceful_cast_changes(language: str, role: str) -> dict[str, Any]:
    del role
    return {
        "agenda": localized_text(
            language,
            en="Force a visible answer before delay hardens into private control.",
            zh="在拖延固化成私下控制前，逼出一个公开且无法回避的答案。",
        ),
        "red_line": localized_text(
            language,
            en="Will not let private bargaining decide a public emergency.",
            zh="不会让私下交易替这场公共危机决定结果。",
        ),
        "pressure_signature": localized_text(
            language,
            en="Turns hesitation into deadlines, public accountability, and narrowing choices.",
            zh="会把犹豫迅速压成倒计时、公开责任和越来越窄的选择。",
        ),
    }


def _assertive_variants(language: str, role: str) -> list[tuple[str, dict[str, Any], str, str]]:
    return [
        (
            localized_text(language, en="Public pressure", zh="公开施压"),
            _forceful_cast_changes(language, role),
            localized_text(language, en="Reframe the protagonist as more forceful under pressure.", zh="把主角改成在压力下更强硬、更会逼人表态。"),
            localized_text(language, en="Public-pressure and confrontation play should feel more natural.", zh="公开施压和逼表态的打法会更顺手。"),
        ),
        (
            localized_text(language, en="Institutional hardening", zh="程序强硬"),
            {
                "agenda": localized_text(
                    language,
                    en="Lock the crisis inside documented procedure before anyone can reroute it into back-room bargaining.",
                    zh="在任何人把危机引向私下交易前，先用成文程序把局面锁死。",
                ),
                "red_line": localized_text(
                    language,
                    en="Will not accept undocumented exceptions during a public emergency.",
                    zh="不会接受这场公共危机中的任何无记录例外。",
                ),
                "pressure_signature": localized_text(
                    language,
                    en="Pins every excuse to a named rule, signed record, and visible chain of responsibility.",
                    zh="会把每个借口钉在具体规则、签名记录和可追责链条上。",
                ),
            },
            localized_text(language, en="Make the protagonist more institutionally hard to maneuver around.", zh="让主角更像一个别人绕不过去的程序锚点。"),
            localized_text(language, en="Procedural pushback should feel firmer and more deliberate.", zh="通过制度和程序施压会更有力量。"),
        ),
        (
            localized_text(language, en="Direct confrontation", zh="正面逼问"),
            {
                "agenda": localized_text(
                    language,
                    en="Force every rival to state their position in the open before the city commits to a lie.",
                    zh="在城市正式吞下谎言前，逼每个对手公开表态。",
                ),
                "red_line": localized_text(
                    language,
                    en="Will not let anyone hide behind ambiguity once the stakes are public.",
                    zh="一旦代价已经公开，就不会再容许任何人躲在模糊话术后面。",
                ),
                "pressure_signature": localized_text(
                    language,
                    en="Turns hesitation into public ultimatums, named witnesses, and narrowing time windows.",
                    zh="会把犹豫迅速压成公开最后通牒、点名见证人和不断收紧的时间窗。",
                ),
            },
            localized_text(language, en="Push the protagonist toward sharper direct confrontation.", zh="把主角推向更直接的公开逼问。"),
            localized_text(language, en="Scenes should feel more confrontational and less observational.", zh="场景会更有正面冲突感，而不是仅仅观察局势。"),
        ),
    ]


def _dock_politics_variant_a(language: str) -> list[tuple[int, dict[str, Any]]]:
    return [
        (
            1,
            {
                "role": localized_text(language, en="Dock operations chief", zh="码头调度长"),
                "agenda": localized_text(language, en="Keep the berths moving without surrendering the docks to panic rule.", zh="在不让码头被恐慌拖走的前提下，维持泊位和调度继续运转。"),
                "red_line": localized_text(language, en="Will not let berth control become private leverage.", zh="不会让泊位调度权变成私人筹码。"),
                "pressure_signature": localized_text(language, en="Translates panic into berth windows, labor limits, and concrete chokepoints.", zh="会把恐慌迅速翻译成泊位窗口、工人极限和具体堵点。"),
            },
        ),
        (
            2,
            {
                "role": localized_text(language, en="Shipping guild broker", zh="航运商会代表"),
                "agenda": localized_text(language, en="Turn dock disruption into leverage over who controls the next settlement.", zh="把码头失序变成重新分配结算权的筹码。"),
                "red_line": localized_text(language, en="Will not accept a settlement that leaves the guild outside the new order.", zh="不会接受把商会排除在新秩序之外的结算。"),
                "pressure_signature": localized_text(language, en="Packages practical relief as a concession that always carries a political price.", zh="会把每一份看似务实的援手都包装成必须交换政治代价的让步。"),
            },
        ),
        (
            3,
            {
                "role": localized_text(language, en="Dockworkers union delegate", zh="装卸工会代表"),
                "agenda": localized_text(language, en="Make sure crews and nearby wards do not pay for elite berth bargains.", zh="不让工人和临港街区替精英之间的泊位交易买单。"),
                "red_line": localized_text(language, en="Will not let recovery skip over who got stranded and who profited.", zh="不会让恢复程序跳过“谁被困住、谁获利”这件事。"),
                "pressure_signature": localized_text(language, en="Names losses, names delays, and makes every private bargain public.", zh="会反复点损失、点拖延，把每一次私下交易重新拖到公众面前。"),
            },
        ),
    ]


def _dock_politics_variant_b(language: str) -> list[tuple[int, dict[str, Any]]]:
    return [
        (
            1,
            {
                "role": localized_text(language, en="Berth controller", zh="泊位调度官"),
                "agenda": localized_text(language, en="Control which ships move and make berth access the core political choke point.", zh="把谁能进出泊位变成整场政治博弈的核心卡口。"),
                "red_line": localized_text(language, en="Will not let berth assignments be dictated by panic or elite favoritism.", zh="不会让恐慌或精英偏私决定泊位调配。"),
                "pressure_signature": localized_text(language, en="Counts every lost hour at the quay as leverage that someone else must answer for.", zh="会把码头每浪费的一小时都算成必须有人负责的筹码。"),
            },
        ),
        (
            2,
            {
                "role": localized_text(language, en="Harbor finance broker", zh="港口结算掮客"),
                "agenda": localized_text(language, en="Translate cargo paralysis into control over emergency credit and settlement terms.", zh="把货物流转停滞转成对紧急信用和结算条件的控制权。"),
                "red_line": localized_text(language, en="Will not fund a recovery that leaves their network outside the next settlement.", zh="不会资助一场把自己网络排除在下轮结算之外的恢复。"),
                "pressure_signature": localized_text(language, en="Packages every practical concession as debt that must be paid back politically.", zh="会把每一次看似务实的让步都包装成未来必须偿还的政治债。"),
            },
        ),
        (
            3,
            {
                "role": localized_text(language, en="Waterfront ward organizer", zh="临港街区组织者"),
                "agenda": localized_text(language, en="Keep the docks from being traded away over the heads of crews and nearby wards.", zh="不让码头在工人和临港街区头顶上被拿去交易。"),
                "red_line": localized_text(language, en="Will not accept recovery terms that erase who absorbed the first losses.", zh="不会接受抹掉最先承担损失者的恢复条件。"),
                "pressure_signature": localized_text(language, en="Turns private dealmaking into named grievances and organized turnout on the waterfront.", zh="会把私下交易翻译成码头上有名字、有组织的集体不满。"),
            },
        ),
    ]


def _dock_politics_variant_c(language: str) -> list[tuple[int, dict[str, Any]]]:
    return [
        (
            1,
            {
                "role": localized_text(language, en="Quay security marshal", zh="岸线保安总管"),
                "agenda": localized_text(language, en="Keep the waterfront governable by deciding who can cross each security line.", zh="通过决定谁能越过每一道岸线管制，把港区秩序握在手里。"),
                "red_line": localized_text(language, en="Will not let inspection authority become ceremonial while the docks are carved up in practice.", zh="不会让检查权在纸面上存在、现实里却被架空。"),
                "pressure_signature": localized_text(language, en="Uses access chokepoints, guard rotations, and visible enforcement gaps as political signals.", zh="会把出入口卡点、警卫轮换和执法空档都变成政治信号。"),
            },
        ),
        (
            2,
            {
                "role": localized_text(language, en="Shipping bloc whip", zh="航运集团操盘手"),
                "agenda": localized_text(language, en="Turn each blocked berth and stranded convoy into leverage over the governing coalition.", zh="把每个被堵的泊位和滞留车队都变成重组执政联盟的筹码。"),
                "red_line": localized_text(language, en="Will not let the next governing compact form without their bloc at the center.", zh="不会让下一轮治理妥协在没有自己集团居中的情况下形成。"),
                "pressure_signature": localized_text(language, en="Counts delay, scarcity, and rumor as inputs for the next power deal.", zh="会把拖延、稀缺和流言都当成下一笔权力交易的输入。"),
            },
        ),
        (
            3,
            {
                "role": localized_text(language, en="Longshore union steward", zh="码头工会工头"),
                "agenda": localized_text(language, en="Make labor stoppage and crew safety the axis that every elite plan must answer to.", zh="把停工与工人安全变成所有精英方案都绕不过去的主轴。"),
                "red_line": localized_text(language, en="Will not let workers carry the cost while others write the emergency narrative.", zh="不会让工人承担代价，而别人在上层书写危机叙事。"),
                "pressure_signature": localized_text(language, en="Turns every sealed gate and missing manifest into a labor grievance with names attached.", zh="会把每一道封闭闸口和每一份缺失清单都变成有名字的劳资纠纷。"),
            },
        ),
    ]


def _dock_politics_variants(language: str) -> list[tuple[str, list[tuple[int, dict[str, Any]]], str, str, str]]:
    return [
        (
            localized_text(language, en="Dockside factions", zh="码头派系"),
            _dock_politics_variant_a(language),
            localized_text(language, en="Dockside political thriller", zh="紧张的码头政治惊悚"),
            localized_text(language, en="Shift the social texture away from abstract port bureaucracy and toward dockside political struggle.", zh="把社会纹理从抽象港务官僚，改成更贴近码头政治和工会博弈。"),
            localized_text(language, en="Supporting cast should read more like dockside factions than generic institutions.", zh="配角会更像码头派系，而不是泛化机构代表。"),
        ),
        (
            localized_text(language, en="Berth leverage", zh="泊位筹码"),
            _dock_politics_variant_b(language),
            localized_text(language, en="Harbor leverage thriller", zh="港区筹码惊悚"),
            localized_text(language, en="Recenter the world around berth access, finance, and negotiated leverage at the waterfront.", zh="把世界重心改成围绕泊位、结算和临港筹码展开。"),
            localized_text(language, en="The conflict should feel more like contested harbor leverage than general bureaucracy.", zh="冲突会更像争夺港区筹码，而不是泛化流程管理。"),
        ),
        (
            localized_text(language, en="Waterfront control", zh="岸线控制"),
            _dock_politics_variant_c(language),
            localized_text(language, en="Waterfront control thriller", zh="岸线控制惊悚"),
            localized_text(language, en="Push the setting toward security lines, labor pressure, and coalition bargaining at the quay.", zh="把场景推向岸线管制、劳工压力和码头联盟讨价还价。"),
            localized_text(language, en="The world should read more like a fight over dock control than an institutional hearing.", zh="整个世界会更像围绕港口控制权的争斗，而不是机构听证会。"),
        ),
    ]


def _pyrrhic_variants(language: str) -> list[tuple[str, str, str, list[str], str]]:
    return [
        (
            localized_text(language, en="Trust damage", zh="信任受损"),
            localized_text(language, en="Force a public settlement that stabilizes the crisis even if trust and coalition ties are permanently damaged.", zh="逼出一份能暂时稳住局势的公开结算，即使它会永久损伤信任与联盟。"),
            "medium",
            [
                localized_text(language, en="Third act pressure resolves with more visible cost.", zh="第三幕会更明确地把稳定与代价绑在一起。"),
                localized_text(language, en="Mixed outcomes become harder to reach than pyrrhic ones.", zh="混合结局会变得更难拿，惨胜更容易落地。"),
            ],
            localized_text(language, en="Push the ending shape toward pyrrhic trust damage rather than clean stabilization.", zh="把结局倾向推向以信任受损为核心的惨胜，而不是干净稳定。"),
        ),
        (
            localized_text(language, en="Legitimacy damage", zh="合法性受损"),
            localized_text(language, en="Stabilize the crisis only by exposing how much legitimacy the city has to burn to survive the vote.", zh="让危机只能在烧掉大量合法性的前提下勉强稳住。"),
            "strong",
            [localized_text(language, en="The ending should feel more like survival with institutional damage than restoration.", zh="结局会更像带着制度损伤的求生，而不是恢复如初。")],
            localized_text(language, en="Push the ending toward institutional survival at visible legitimacy cost.", zh="把结局推向靠牺牲合法性换取生存。"),
        ),
        (
            localized_text(language, en="Material cost", zh="物资代价"),
            localized_text(language, en="Lock in a public settlement that holds for now, but only by accepting shortages, stranded crews, and irreversible material loss.", zh="逼出一份暂时能成立的公开结算，但代价是短缺、滞留和无法逆转的物资损失。"),
            "light",
            [localized_text(language, en="The ending should make the cost of stabilization materially visible to the player.", zh="结局会让玩家明显感到“稳住局势”付出的真实物资代价。")],
            localized_text(language, en="Push the ending toward visible logistical loss rather than a merely emotional pyrrhic turn.", zh="把结局推向更具体的物流和物资损失，而不仅是情绪上的惨胜。"),
        ),
    ]


def build_copilot_workspace_view(
    *,
    language: str,
    title: str,
    protagonist_name: str,
    runtime_profile_label: str,
    closeout_profile_label: str,
    premise: str,
    theme: str,
    active_session_id: str | None = None,
    undo_available: bool = False,
    undo_proposal_id: str | None = None,
    undo_request_summary: str | None = None,
) -> AuthorCopilotWorkspaceView:
    suggestions = [
        AuthorCopilotSuggestion(
            suggestion_id="protagonist_assertive",
            label=localized_text(language, en="Sharpen the protagonist", zh="把主角写得更强硬"),
            instruction=localized_text(language, en="Make the protagonist more assertive.", zh="把主角改得更强硬。"),
            rationale=localized_text(
                language,
                en="Use this when the current lead feels too observational and you want public pressure to feel more playable.",
                zh="如果当前主角更像旁观者，而你希望公开施压和逼人表态更好玩，就用这个方向。",
            ),
        ),
        AuthorCopilotSuggestion(
            suggestion_id="ending_pyrrhic",
            label=localized_text(language, en="Push toward pyrrhic", zh="把结局推向惨胜"),
            instruction=localized_text(language, en="Make the third act feel more pyrrhic.", zh="让第三幕更偏惨胜。"),
            rationale=localized_text(
                language,
                en="Use this when stabilization should still come with visible trust, legitimacy, or coalition damage.",
                zh="如果你希望局势虽然稳住，但必须让信任、合法性或联盟关系明显受损，就用这个方向。",
            ),
        ),
    ]

    if _contains_story_terms(title, premise, theme, runtime_profile_label, closeout_profile_label):
        suggestions.append(
            AuthorCopilotSuggestion(
                suggestion_id="dock_politics",
                label=localized_text(language, en="Make it more dockside political", zh="把它改成更有码头政治感"),
                instruction=localized_text(
                    language,
                    en="Shift this away from harbor bureaucracy and toward dock politics.",
                    zh="不要港口官僚味，改得更像码头政治。",
                ),
                rationale=localized_text(
                    language,
                    en="Use this when the current world feels too procedural and you want factions, unions, and leverage brokers to carry the pressure.",
                    zh="如果现在的世界更像流程管理，而你想让派系、工会和掮客来承受主要压力，就用这个方向。",
                ),
            )
        )

    return AuthorCopilotWorkspaceView(
        mode="primary",
        headline=localized_text(
            language,
            en=f"Steer '{title}' with Author Copilot before you publish.",
            zh=f"在发布前，先用 Author Copilot 把《{title}》再打磨一轮。",
        ),
        supporting_text=localized_text(
            language,
            en=f"The draft is ready. Use Copilot to reshape story rules, cast texture, beats, and rule semantics while preserving the current runtime profile ({runtime_profile_label}).",
            zh=f"草稿已经成形。你现在可以用 Copilot 调整世界规则、人物关系、节拍推进和收束方式，同时保留这版的基本玩法（{runtime_profile_label}）。",
        ),
        publish_readiness_text=localized_text(
            language,
            en=f"Publish only after the draft feels final for play. The current closeout tilt is {closeout_profile_label}.",
            zh=f"只有当你确认这版已经适合进入游玩时再发布。眼下这版更偏向 {closeout_profile_label}。",
        ),
        active_session_id=active_session_id,
        undo_available=undo_available,
        undo_proposal_id=undo_proposal_id,
        undo_request_summary=undo_request_summary,
        suggested_instructions=suggestions,
    )


def build_copilot_locked_boundaries(
    *,
    editor_state: AuthorEditorStateResponse,
) -> AuthorCopilotLockedBoundaries:
    return AuthorCopilotLockedBoundaries(
        language=editor_state.language,
        core_story_kernel=editor_state.focused_brief.story_kernel,
        core_conflict=editor_state.focused_brief.core_conflict,
        runtime_profile=editor_state.play_profile_view.runtime_profile,
        closeout_profile=editor_state.play_profile_view.closeout_profile,
        cast_topology=f"{len(editor_state.cast_view)}_slot",
        beat_count=len(editor_state.beat_view),
        max_turns=editor_state.play_profile_view.max_turns,
    )


def build_initial_rewrite_brief(
    *,
    editor_state: AuthorEditorStateResponse,
    locked_boundaries: AuthorCopilotLockedBoundaries,
) -> AuthorCopilotRewriteBrief:
    return AuthorCopilotRewriteBrief(
        summary=localized_text(
            editor_state.language,
            en="Keep the story in the same premise family and runtime lane while preparing for a global rewrite of story rules, cast texture, beats, and rule semantics.",
            zh="保留当前故事的题材骨架和基本玩法，但允许对世界规则、人物关系、节拍推进和收束方式做一次全局重写。",
        ),
        latest_instruction=localized_text(
            editor_state.language,
            en="No user rewrite request yet.",
            zh="用户还没有给出具体重写要求。",
        ),
        user_goals=[],
        preserved_invariants=[
            f"language={locked_boundaries.language}",
            f"runtime_profile={locked_boundaries.runtime_profile}",
            f"closeout_profile={locked_boundaries.closeout_profile}",
            f"cast_topology={locked_boundaries.cast_topology}",
            f"beat_count={locked_boundaries.beat_count}",
            f"max_turns={locked_boundaries.max_turns}",
        ],
        open_questions=[],
    )


def build_copilot_workspace_snapshot_from_state(
    *,
    state: dict[str, Any],
    bundle: DesignBundle,
) -> AuthorCopilotWorkspaceSnapshot:
    play_plan = compile_play_plan(story_id="copilot-workspace", bundle=bundle)
    return AuthorCopilotWorkspaceSnapshot(
        focused_brief=state["focused_brief"],
        story_frame_draft=state["story_frame_draft"],
        cast_overview_draft=state["cast_overview_draft"],
        cast_member_drafts=list(state.get("cast_member_drafts") or []),
        cast_draft=state.get("cast_draft") or CastDraft(cast=list(state.get("cast_member_drafts") or [])),
        beat_plan_draft=state["beat_plan_draft"],
        route_opportunity_plan_draft=state.get("route_opportunity_plan_draft"),
        route_affordance_pack_draft=state.get("route_affordance_pack_draft"),
        ending_intent_draft=state.get("ending_intent_draft"),
        ending_rules_draft=state.get("ending_rules_draft"),
        story_frame_strategy=state.get("story_frame_strategy"),
        primary_theme=str(state.get("primary_theme") or "generic_civic_crisis"),
        theme_modifiers=list(state.get("theme_modifiers") or []),
        cast_topology=str(state.get("cast_topology") or f"{len(bundle.story_bible.cast)}_slot"),
        runtime_profile=play_plan.runtime_policy_profile,
        closeout_profile=play_plan.closeout_profile,
        max_turns=play_plan.max_turns,
    )


def _fallback_session_reply(
    *,
    session: AuthorCopilotSessionResponse,
    message: str,
) -> tuple[str, AuthorCopilotRewriteBrief]:
    goals = unique_preserve([*session.rewrite_brief.user_goals, message.strip()])
    brief = session.rewrite_brief.model_copy(
        update={
            "summary": localized_text(
                session.locked_boundaries.language,
                en=f"Rewrite focus: {message.strip()[:360]}",
                zh=f"本轮重写重点：{message.strip()[:180]}",
            ),
            "latest_instruction": message.strip(),
            "user_goals": goals[:8],
        }
    )
    reply = localized_text(
        session.locked_boundaries.language,
        en=(
            "I can work with that. I will keep the story in the same language, premise family, and runtime lane, "
            "then turn this into a rewrite proposal that updates story frame, cast texture, beats, and rule semantics only where needed."
        ),
        zh=(
            "我可以按这个方向继续。接下来我会保留故事语言、核心题材家族和这版的基本玩法，"
            "再把这次要求整理成一份全局重写提案，只改需要改动的故事框架、人物关系、节拍推进和收束方式。"
        ),
    )
    return reply, brief


def build_copilot_session_reply(
    *,
    gateway: CapabilityGatewayCore | None,
    session: AuthorCopilotSessionResponse,
    editor_state: AuthorEditorStateResponse,
    message: str,
) -> tuple[str, AuthorCopilotRewriteBrief, str]:
    if gateway is None:
        reply, brief = _fallback_session_reply(session=session, message=message)
        return reply, brief, "heuristic"
    payload = {
        "editor_state": editor_state.model_dump(mode="json"),
        "locked_boundaries": session.locked_boundaries.model_dump(mode="json"),
        "current_rewrite_brief": session.rewrite_brief.model_dump(mode="json"),
        "new_user_message": message,
    }
    system_prompt = (
        f"{prompt_role_instruction(editor_state.language, en_role='a senior developmental editor for interactive fiction', zh_role='资深中文互动叙事编辑')} "
        f"{output_language_instruction(editor_state.language)} "
        "You are an authoring copilot for an interactive narrative editor. "
        "Help the user clarify a global story rewrite while preserving locked boundaries. "
        "Return strict JSON with keys assistant_reply and rewrite_brief. "
        "rewrite_brief must include summary, latest_instruction, user_goals, preserved_invariants, open_questions. "
        "All user-visible string values in assistant_reply and rewrite_brief must follow the target story language. "
        "Do not change language, runtime profile, closeout profile, cast topology, beat count, or max turns."
    )
    try:
        response = gateway.invoke_text_capability(
            "copilot.reply",
            TextCapabilityRequest(
                system_prompt=system_prompt,
                user_payload=payload,
                max_output_tokens=gateway.text_policy("copilot.reply").max_output_tokens,
                operation_name="copilot_session_reply",
            ),
        )
        brief = AuthorCopilotRewriteBrief.model_validate(response.payload.get("rewrite_brief") or {})
        assistant_reply = str(response.payload.get("assistant_reply") or "").strip()
        if not assistant_reply:
            raise ValueError("empty assistant reply")
        if not _text_matches_story_language(assistant_reply, editor_state.language):
            raise ValueError("assistant_reply_language_mismatch")
        if not _rewrite_brief_matches_story_language(brief, editor_state.language):
            raise ValueError("rewrite_brief_language_mismatch")
        return assistant_reply, brief, "llm"
    except Exception:  # noqa: BLE001
        reply, brief = _fallback_session_reply(session=session, message=message)
        return reply, brief, "heuristic"


def _build_compat_operations(plan: AuthorCopilotRewritePlan) -> list[AuthorCopilotOperation]:
    operations: list[AuthorCopilotOperation] = []
    if plan.story_frame is not None:
        changes = {
            key: value
            for key, value in _explicit_fields(plan.story_frame).items()
            if value is not None and isinstance(value, (str, int))
        }
        if changes:
            operations.append(
                AuthorCopilotOperation(op="update_story_frame", target="story_frame", changes=changes)
            )
    for cast_patch in plan.cast:
        changes = {
            key: value
            for key, value in _explicit_fields(cast_patch).items()
            if key != "npc_id" and value is not None and isinstance(value, (str, int))
        }
        if changes:
            operations.append(
                AuthorCopilotOperation(op="update_cast_member", target=cast_patch.npc_id, changes=changes)
            )
    for beat_patch in plan.beats:
        changes = {
            key: value
            for key, value in _explicit_fields(beat_patch).items()
            if key != "beat_id" and value is not None and isinstance(value, (str, int))
        }
        if changes:
            operations.append(
                AuthorCopilotOperation(op="update_beat", target=beat_patch.beat_id, changes=changes)
            )
    if plan.rule_pack and plan.rule_pack.toward is not None:
        operations.append(
            AuthorCopilotOperation(
                op="adjust_ending_tilt",
                target="rule_pack",
                changes={},
                toward=plan.rule_pack.toward,
                intensity=plan.rule_pack.intensity,
            )
        )
    return operations[:12]


def _affected_sections(plan: AuthorCopilotRewritePlan) -> list[str]:
    sections: list[str] = []
    if plan.story_frame and _explicit_fields(plan.story_frame):
        sections.append("story_frame")
    if plan.cast:
        sections.append("cast")
    if plan.beats:
        sections.append("beats")
    if plan.rule_pack and _explicit_fields(plan.rule_pack):
        sections.append("rule_pack")
    return unique_preserve(sections)


def _generic_political_cast_changes(
    *,
    language: str,
    intensity: CopilotIntentStrength,
    cast_entries: list[Any],
) -> list[AuthorCopilotCastRewrite]:
    supporting = cast_entries[1:]
    if not supporting:
        return []
    pressure_copy = {
        "light": localized_text(
            language,
            en="Treats each sealed record as leverage that can still be bargained over in public.",
            zh="会把每一份被封起来的记录都当成仍可被公开讨价还价的筹码。",
        ),
        "medium": localized_text(
            language,
            en="Turns sealed records, missing signatures, and procedural delay into factional leverage.",
            zh="会把被封的记录、缺失的签名和程序拖延都翻成派系之间的权力筹码。",
        ),
        "strong": localized_text(
            language,
            en="Uses every sealed record and missing witness as proof that the next settlement is already a power struggle.",
            zh="会把每一份被封的记录和每一位缺席的见证人，都当成“下一轮结算已经是权力争斗”的证据。",
        ),
    }
    agenda_copy = {
        "light": localized_text(
            language,
            en="Make sure any settlement leaves their faction with visible standing in the public record.",
            zh="确保任何结算都要在公开记录里给自己的阵营留下可见位置。",
        ),
        "medium": localized_text(
            language,
            en="Turn the emergency record into leverage over who gets to define the settlement.",
            zh="把这场紧急事件留下的记录变成争夺“谁有资格定义结算”的筹码。",
        ),
        "strong": localized_text(
            language,
            en="Force the settlement to pass through factional bargaining over who owns the public record of the crisis.",
            zh="逼整场结算都必须经过围绕“谁拥有这场危机公开记录”的派系谈判。",
        ),
    }
    red_line_copy = {
        "light": localized_text(
            language,
            en="Will not let the record close before their side is named in it.",
            zh="不会允许记录在自己的阵营还没有被写进去之前就被封存。",
        ),
        "medium": localized_text(
            language,
            en="Will not accept a settlement that hides who gained leverage from the emergency.",
            zh="不会接受任何掩盖“谁借这场危机攫取筹码”的结算。",
        ),
        "strong": localized_text(
            language,
            en="Will not let public order be restored on a record that erases how power was traded during the crisis.",
            zh="不会允许城市在一份抹掉危机中权力交易过程的记录上恢复秩序。",
        ),
    }
    return [
        AuthorCopilotCastRewrite(
            npc_id=entry.npc_id,
            agenda=agenda_copy[intensity],
            red_line=red_line_copy[intensity],
            pressure_signature=pressure_copy[intensity],
        )
        for entry in supporting[:2]
    ]


def _public_record_story_frame_patch(
    *,
    language: str,
    intensity: CopilotIntentStrength,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
) -> AuthorCopilotStoryFrameRewrite:
    world_rules = list(workspace_snapshot.story_frame_draft.world_rules)
    truths = list(workspace_snapshot.story_frame_draft.truths)
    flags = list(workspace_snapshot.story_frame_draft.flags)
    if world_rules:
        world_rules[0] = localized_text(
            language,
            en="Emergency authority only survives if the public record remains visible and contestable.",
            zh="紧急权力只有在公开记录仍然可见、可被争辩时才有正当性。",
        )
    if len(world_rules) > 1:
        world_rules[1] = localized_text(
            language,
            en="Every sealed archive, ledger, or witness statement becomes leverage in the next civic settlement.",
            zh="每一份被封存的档案、账本或证词，都会在下一轮公共结算里变成筹码。",
        )
    if truths:
        truths[0] = truths[0].model_copy(
            update={
                "text": localized_text(
                    language,
                    en="The public record was shaped before the city ever saw the crisis clearly.",
                    zh="在整座城市真正看清危机之前，公开记录就已经被人动过手脚。",
                )
            }
        )
    if len(truths) > 1:
        truths[1] = truths[1].model_copy(
            update={
                "text": localized_text(
                    language,
                    en="Whoever controls the ledger can decide which sacrifice looks legitimate.",
                    zh="谁控制账本，谁就能决定哪一种牺牲会被说成“合理”。",
                )
            }
        )
    if flags:
        flags[0] = flags[0].model_copy(
            update={
                "label": localized_text(
                    language,
                    en="Record Leak",
                    zh="记录泄露",
                ),
                "starting_value": intensity == "strong",
            }
        )
    return AuthorCopilotStoryFrameRewrite(
        tone=localized_text(
            language,
            en="Tense civic thriller with sharper public-record pressure.",
            zh="更强调公开记录压力的紧张公共惊悚感。",
        ),
        world_rules=world_rules,
        truths=truths,
        flags=flags,
    )


def _public_record_beat_patches(
    *,
    language: str,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
    editor_state: AuthorEditorStateResponse,
    intensity: CopilotIntentStrength,
) -> list[AuthorCopilotBeatRewrite]:
    cast_names = [entry.name for entry in editor_state.cast_view]
    if not cast_names:
        return []
    rival_name = cast_names[-1]
    record_truth = localized_text(
        language,
        en="The public record was shaped before the city ever saw the crisis clearly.",
        zh="在整座城市真正看清危机之前，公开记录就已经被人动过手脚。",
    )
    second_truth = localized_text(
        language,
        en="Whoever controls the ledger can decide which sacrifice looks legitimate.",
        zh="谁控制账本，谁就能决定哪一种牺牲会被说成“合理”。",
    )
    patches = [
        AuthorCopilotBeatRewrite(
            beat_id="b1",
            focus_names=[cast_names[0], rival_name],
            conflict_pair=[cast_names[0], rival_name],
            required_truth_texts=[record_truth],
            return_hooks=[
                localized_text(
                    language,
                    en="A sealed ledger entry becomes the one detail nobody can explain away in public.",
                    zh="一条被封存的账目突然成了谁也无法在公众面前糊弄过去的细节。",
                )
            ],
            affordance_tags=["reveal_truth", "shift_public_narrative"],
            blocked_affordances=["build_trust"] if intensity != "light" else [],
        )
    ]
    if len(workspace_snapshot.beat_plan_draft.beats) > 1:
        second_focus = cast_names[1] if len(cast_names) > 1 else rival_name
        patches.append(
            AuthorCopilotBeatRewrite(
                beat_id="b2",
                focus_names=[second_focus, rival_name],
                conflict_pair=[second_focus, rival_name],
                required_truth_texts=[second_truth],
                affordance_tags=["shift_public_narrative", "reveal_truth"],
            )
        )
    return patches


def _rule_semantics_patch(
    *,
    base_bundle: DesignBundle,
    emphasis: CopilotRuleSemanticsEmphasis,
    intensity: CopilotIntentStrength,
) -> AuthorCopilotRulePackRewrite:
    truth_ids = [truth.truth_id for truth in base_bundle.story_bible.truth_catalog]
    beat_ids = [beat.beat_id for beat in base_bundle.beat_spine]
    axes = {axis.axis_id: axis for axis in base_bundle.state_schema.axes}
    exposure_axis = next((axis_id for axis_id, axis in axes.items() if axis.kind == "exposure"), None)
    pressure_axis = next((axis_id for axis_id, axis in axes.items() if axis.kind == "pressure"), base_bundle.state_schema.axes[0].axis_id)
    leverage_axis = next((axis_id for axis_id, axis in axes.items() if axis.kind == "relationship"), pressure_axis)
    if emphasis == "exposure_routes" and beat_ids and truth_ids:
        return AuthorCopilotRulePackRewrite(
            route_unlock_rules=[
                RouteUnlockRule(
                    rule_id=f"{beat_ids[0]}_public_record_route",
                    beat_id=beat_ids[0],
                    conditions={"required_truths": [truth_ids[0]]},
                    unlock_route_id=f"{beat_ids[0]}_public_record_route",
                    unlock_affordance_tag="reveal_truth",
                )
            ],
            affordance_effect_profiles=[
                AffordanceEffectProfile(
                    affordance_tag="reveal_truth",
                    default_story_function="reveal",
                    axis_deltas={exposure_axis or leverage_axis: 1},
                    stance_deltas={},
                    can_add_truth=True,
                    can_add_event=False,
                ),
                AffordanceEffectProfile(
                    affordance_tag="shift_public_narrative",
                    default_story_function="advance",
                    axis_deltas={leverage_axis: 1, pressure_axis: -1 if intensity == "light" else 1},
                    stance_deltas={},
                    can_add_truth=False,
                    can_add_event=True,
                ),
            ],
        )
    if emphasis == "public_accountability":
        return AuthorCopilotRulePackRewrite(
            route_unlock_rules=[
                RouteUnlockRule(
                    rule_id=f"{beat_ids[0]}_public_accountability_route",
                    beat_id=beat_ids[0],
                    conditions={"required_truths": truth_ids[:1]},
                    unlock_route_id=f"{beat_ids[0]}_public_accountability_route",
                    unlock_affordance_tag="shift_public_narrative",
                )
            ] if beat_ids else None,
            toward="mixed",
            intensity="light",
        )
    return AuthorCopilotRulePackRewrite(toward="pyrrhic", intensity=intensity)


def _synthesize_rewrite_plan(
    *,
    editor_state: AuthorEditorStateResponse,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
    base_bundle: DesignBundle,
    intent: _CopilotIntentPacket,
    variant_index: int,
) -> _SynthesizedRewritePlan:
    language = editor_state.language
    story_frame_patch: AuthorCopilotStoryFrameRewrite | None = None
    cast_patches: list[AuthorCopilotCastRewrite] = []
    beat_patches: list[AuthorCopilotBeatRewrite] = []
    rule_pack_patch: AuthorCopilotRulePackRewrite | None = None
    labels: list[str] = []
    request_parts: list[str] = []
    impacts: list[str] = []
    warnings: list[str] = []

    if intent.protagonist_pressure_style == "assertive":
        label, changes, request_summary, impact = _assertive_variants(language, editor_state.cast_view[0].role)[variant_index - 1]
        cast_patches.append(
            AuthorCopilotCastRewrite(
                npc_id=editor_state.cast_view[0].npc_id,
                role=str(changes.get("role")) if changes.get("role") is not None else None,
                agenda=str(changes.get("agenda")) if changes.get("agenda") is not None else None,
                red_line=str(changes.get("red_line")) if changes.get("red_line") is not None else None,
                pressure_signature=str(changes.get("pressure_signature")) if changes.get("pressure_signature") is not None else None,
            )
        )
        labels.append(label)
        request_parts.append(request_summary)
        impacts.append(impact)
    elif intent.protagonist_pressure_style == "procedural":
        label, changes, request_summary, impact = _assertive_variants(language, editor_state.cast_view[0].role)[1]
        cast_patches.append(
            AuthorCopilotCastRewrite(
                npc_id=editor_state.cast_view[0].npc_id,
                agenda=str(changes.get("agenda")) if changes.get("agenda") is not None else None,
                red_line=str(changes.get("red_line")) if changes.get("red_line") is not None else None,
                pressure_signature=str(changes.get("pressure_signature")) if changes.get("pressure_signature") is not None else None,
            )
        )
        labels.append(label)
        request_parts.append(request_summary)
        impacts.append(impact)
    elif intent.protagonist_pressure_style == "public_confrontation":
        label, changes, request_summary, impact = _assertive_variants(language, editor_state.cast_view[0].role)[2]
        cast_patches.append(
            AuthorCopilotCastRewrite(
                npc_id=editor_state.cast_view[0].npc_id,
                agenda=str(changes.get("agenda")) if changes.get("agenda") is not None else None,
                red_line=str(changes.get("red_line")) if changes.get("red_line") is not None else None,
                pressure_signature=str(changes.get("pressure_signature")) if changes.get("pressure_signature") is not None else None,
            )
        )
        labels.append(label)
        request_parts.append(request_summary)
        impacts.append(impact)

    if intent.political_texture == "dockside":
        label, role_changes, tone, request_summary, impact = _dock_politics_variants(language)[variant_index - 1]
        for index, changes in role_changes:
            if index >= len(editor_state.cast_view):
                continue
            cast_patches.append(
                AuthorCopilotCastRewrite(
                    npc_id=editor_state.cast_view[index].npc_id,
                    role=str(changes.get("role")) if changes.get("role") is not None else None,
                    agenda=str(changes.get("agenda")) if changes.get("agenda") is not None else None,
                    red_line=str(changes.get("red_line")) if changes.get("red_line") is not None else None,
                    pressure_signature=str(changes.get("pressure_signature")) if changes.get("pressure_signature") is not None else None,
                )
            )
        story_frame_patch = (story_frame_patch or AuthorCopilotStoryFrameRewrite()).model_copy(update={"tone": tone})
        labels.append(label)
        request_parts.append(request_summary)
        impacts.append(impact)
    elif intent.political_texture is not None or intent.cast_texture is not None:
        intensity = intent.cast_texture_intensity if intent.cast_texture is not None else intent.political_texture_intensity
        cast_patches.extend(
            _generic_political_cast_changes(
                language=language,
                intensity=intensity,
                cast_entries=editor_state.cast_view,
            )
        )
        labels.append(localized_text(language, en="Sharper factions", zh="更尖锐的派系拉扯"))
        request_parts.append(
            localized_text(
                language,
                en="Push the supporting cast toward sharper factional pressure and public accountability.",
                zh="把配角关系推向更明确的派系压力与公开问责。",
            )
        )
        impacts.append(
            localized_text(
                language,
                en="The cast should feel more politically charged and less neutral.",
                zh="角色关系会更有政治张力，不再停留在中性分工上。",
            )
        )

    if intent.story_frame_emphasis is not None or intent.truth_exposure_emphasis is not None:
        story_frame_patch = _public_record_story_frame_patch(
            language=language,
            intensity=intent.story_frame_intensity,
            workspace_snapshot=workspace_snapshot,
        )
        labels.append(localized_text(language, en="Public record pressure", zh="公开记录压力"))
        request_parts.append(
            localized_text(
                language,
                en="Broaden the world rules toward visible public records, sealed ledgers, and contestable legitimacy.",
                zh="把世界规则推向更强调公开记录、封存账本和可争辩合法性的方向。",
            )
        )
        impacts.append(
            localized_text(
                language,
                en="The story frame should make record exposure and civic legitimacy more explicit.",
                zh="故事框架会更明确地把记录曝光与公共合法性写出来。",
            )
        )

    if intent.beat_pressure_shape is not None or intent.truth_exposure_emphasis is not None:
        beat_patches.extend(
            _public_record_beat_patches(
                language=language,
                workspace_snapshot=workspace_snapshot,
                editor_state=editor_state,
                intensity=intent.beat_pressure_intensity,
            )
        )
        labels.append(localized_text(language, en="Exposure beats", zh="曝光型节拍"))
        impacts.append(
            localized_text(
                language,
                en="The opening beats should reward exposing records and forcing public explanation.",
                zh="开场节拍会更鼓励揭露记录并逼出公开解释。",
            )
        )

    if intent.rule_semantics_emphasis is not None:
        rule_pack_patch = _rule_semantics_patch(
            base_bundle=base_bundle,
            emphasis=intent.rule_semantics_emphasis,
            intensity=intent.rule_semantics_intensity,
        )
        labels.append(localized_text(language, en="Semantics pass", zh="语义强化"))
        impacts.append(
            localized_text(
                language,
                en="Routes and ending logic should better reward exposure and public accountability.",
                zh="路线和结局逻辑会更明确地奖励曝光与公开问责。",
            )
        )

    if intent.ending_tilt is not None:
        rule_pack_patch = (rule_pack_patch or AuthorCopilotRulePackRewrite()).model_copy(
            update={
                "toward": intent.ending_tilt.toward,
                "intensity": intent.ending_tilt.intensity,
            }
        )
        labels.append(localized_text(language, en="Costly ending", zh="更有代价的结局"))
        request_parts.append(
            localized_text(
                language,
                en="Push the ending toward a more visibly costly public settlement.",
                zh="把结局推向一场代价更可见的公共结算。",
            )
        )

    if intent.unsupported_structure_requested:
        warnings.append(
            localized_text(
                language,
                en="Structure-level rewrite requests were ignored in this version; Copilot kept the same cast topology, beat count, and runtime lane.",
                zh="这次忽略了结构级改写要求；Copilot 仍保留原有角色拓扑、节拍数量和这套游玩节奏。",
            )
        )

    plan = AuthorCopilotRewritePlan(
        story_frame=story_frame_patch,
        cast=cast_patches,
        beats=beat_patches,
        rule_pack=rule_pack_patch,
    )
    affected_sections = _affected_sections(plan)
    if not affected_sections:
        raise ValueError("instruction_unsupported")
    variant_label = " + ".join(unique_preserve(labels)) or localized_text(language, en="Rewrite proposal", zh="重写提案")
    request_summary = " ".join(unique_preserve(request_parts)).strip() or localized_text(
        language,
        en="Prepare a broader but still safe global rewrite inside the current runtime lane.",
        zh="在不改动当前游玩节奏的前提下，做一份更宽泛但仍然安全的全局重写。",
    )
    return _SynthesizedRewritePlan(
        plan=plan,
        request_summary=request_summary,
        variant_label=variant_label,
        affected_sections=affected_sections,
        impact_summary=unique_preserve(impacts),
        warnings=unique_preserve(warnings),
        fingerprint="|".join(
            [
                f"story:{intent.story_frame_emphasis or 'none'}",
                f"politics:{intent.political_texture or 'none'}",
                f"protagonist:{intent.protagonist_pressure_style or 'none'}",
                f"beats:{intent.beat_pressure_shape or 'none'}",
                f"truth:{intent.truth_exposure_emphasis or 'none'}",
                f"ending:{intent.ending_tilt.toward if intent.ending_tilt else 'none'}",
                f"rules:{intent.rule_semantics_emphasis or 'none'}",
                f"variant:{variant_index}",
            ]
        ),
    )


def _fallback_rewrite_plan(
    *,
    editor_state: AuthorEditorStateResponse,
    instruction: str,
    variant_index: int,
) -> tuple[AuthorCopilotRewritePlan, str, str, list[str], list[str], list[str], str]:
    language = editor_state.language
    lowered = normalize_whitespace(instruction).casefold()
    protagonist = editor_state.cast_view[0]
    final_beat = editor_state.beat_view[-1]
    if variant_index > 3:
        raise ValueError("no_more_variants")
    story_frame_patch: AuthorCopilotStoryFrameRewrite | None = None
    cast_patches: list[AuthorCopilotCastRewrite] = []
    beat_patches: list[AuthorCopilotBeatRewrite] = []
    rule_pack_patch: AuthorCopilotRulePackRewrite | None = None
    impact_summary: list[str] = []
    warnings: list[str] = []
    variant_labels: list[str] = []
    request_summary_parts: list[str] = []
    fingerprint_parts: list[str] = []

    if _contains_any(lowered, ("更强硬", "更强势", "更硬", "更直接", "harder", "hardline", "more assertive", "more forceful")):
        label, changes, request_summary, impact = _assertive_variants(language, protagonist.role)[variant_index - 1]
        cast_patches.append(
            AuthorCopilotCastRewrite(
                npc_id=protagonist.npc_id,
                role=str(changes.get("role")) if changes.get("role") is not None else None,
                agenda=str(changes.get("agenda")) if changes.get("agenda") is not None else None,
                red_line=str(changes.get("red_line")) if changes.get("red_line") is not None else None,
                pressure_signature=str(changes.get("pressure_signature")) if changes.get("pressure_signature") is not None else None,
            )
        )
        request_summary_parts.append(request_summary)
        impact_summary.append(impact)
        variant_labels.append(label)
        fingerprint_parts.append(f"assertive:{variant_index}")

    if _contains_any(lowered, ("惨胜", "pyrrhic")):
        label, goal, intensity, impacts, request_summary = _pyrrhic_variants(language)[variant_index - 1]
        beat_patches.append(
            AuthorCopilotBeatRewrite(
                beat_id=final_beat.beat_id,
                goal=goal,
            )
        )
        rule_pack_patch = AuthorCopilotRulePackRewrite(toward="pyrrhic", intensity=intensity)  # type: ignore[arg-type]
        request_summary_parts.append(request_summary)
        impact_summary.extend(impacts)
        variant_labels.append(label)
        fingerprint_parts.append(f"pyrrhic:{variant_index}")

    if _contains_any(lowered, ("码头政治", "dock politics", "不要港口官僚", "less bureaucratic", "more dockside")):
        label, role_changes, tone, request_summary, impact = _dock_politics_variants(language)[variant_index - 1]
        for index, changes in role_changes:
            if index >= len(editor_state.cast_view):
                continue
            cast_patches.append(
                AuthorCopilotCastRewrite(
                    npc_id=editor_state.cast_view[index].npc_id,
                    role=str(changes.get("role")) if changes.get("role") is not None else None,
                    agenda=str(changes.get("agenda")) if changes.get("agenda") is not None else None,
                    red_line=str(changes.get("red_line")) if changes.get("red_line") is not None else None,
                    pressure_signature=str(changes.get("pressure_signature")) if changes.get("pressure_signature") is not None else None,
                )
            )
        story_frame_patch = AuthorCopilotStoryFrameRewrite(tone=tone)
        request_summary_parts.append(request_summary)
        impact_summary.append(impact)
        variant_labels.append(label)
        fingerprint_parts.append(f"dock:{variant_index}")

    if not (story_frame_patch or cast_patches or beat_patches or rule_pack_patch):
        raise ValueError("instruction_unsupported")

    plan = AuthorCopilotRewritePlan(
        story_frame=story_frame_patch,
        cast=cast_patches,
        beats=beat_patches,
        rule_pack=rule_pack_patch,
    )
    affected_sections = _affected_sections(plan)
    request_summary = " ".join(request_summary_parts).strip()
    variant_label = " + ".join(variant_labels) or localized_text(language, en="Rewrite proposal", zh="重写提案")
    stability_guards = [
        f"language={editor_state.language}",
        f"runtime_profile={editor_state.play_profile_view.runtime_profile}",
        f"closeout_profile={editor_state.play_profile_view.closeout_profile}",
        f"beat_count={len(editor_state.beat_view)}",
        f"cast_count={len(editor_state.cast_view)}",
    ]
    return (
        plan,
        request_summary,
        variant_label,
        affected_sections,
        unique_preserve(impact_summary),
        warnings,
        "|".join(fingerprint_parts),
    )


def build_copilot_proposal(
    *,
    gateway: CapabilityGatewayCore | None,
    session: AuthorCopilotSessionResponse | None,
    job_id: str,
    base_revision: str,
    editor_state: AuthorEditorStateResponse,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
    instruction: str,
    proposal_group_id: str,
    variant_index: int,
    supersedes_proposal_id: str | None = None,
) -> tuple[AuthorCopilotProposalResponse, str]:
    if variant_index > 3:
        raise ValueError("no_more_variants")
    rewrite_brief_text = session.rewrite_brief.summary if session is not None else instruction
    _, base_bundle = _compile_copilot_bundle(workspace_snapshot=workspace_snapshot, rewrite=None)
    locked_boundaries = (
        session.locked_boundaries
        if session is not None
        else build_copilot_locked_boundaries(editor_state=editor_state)
    )
    intent_packet, _intent_source = _normalize_rewrite_intent(
        gateway=gateway,
        instruction=instruction,
        rewrite_brief=rewrite_brief_text,
        editor_state=editor_state,
        locked_boundaries=locked_boundaries,
    )
    if not _intent_has_supported_dimensions(intent_packet):
        if intent_packet is not None and intent_packet.unsupported_reason == "non_rewrite_request":
            raise ValueError("instruction_unsupported")
        if intent_packet is not None and intent_packet.unsupported_reason == "structure_request_only":
            raise ValueError("instruction_unsupported")
        raise ValueError("instruction_unsupported")
    if gateway is not None:
        payload = {
            "editor_state": editor_state.model_dump(mode="json"),
            "workspace_snapshot": workspace_snapshot.model_dump(mode="json"),
            "reference_catalog": _rewrite_reference_catalog(base_bundle),
            "instruction": instruction,
            "rewrite_brief": rewrite_brief_text,
            "locked_boundaries": locked_boundaries.model_dump(mode="json"),
            "normalized_intent": intent_packet.model_dump(mode="json"),
            "variant_index": variant_index,
        }
        system_prompt = (
            f"{prompt_role_instruction(editor_state.language, en_role='a senior rewrite planner for interactive narrative design', zh_role='资深中文互动叙事重写策划')} "
            f"{output_language_instruction(editor_state.language)} "
            "You are an authoring copilot that prepares a global story rewrite proposal for an interactive narrative draft. "
            "Preserve language, premise family, runtime profile, closeout profile, cast count, beat count, and max turns. "
            "Base the rewrite only on normalized_intent; do not invent unsupported scope outside it. "
            "Return strict JSON with keys: request_summary, variant_label, affected_sections, impact_summary, warnings, "
            "story_frame, cast, beats, rule_pack. "
            "story_frame is an object with optional title, premise, tone, stakes, style_guard, world_rules, truths, state_axis_choices, flags. "
            "truths is a full replacement list of objects with text and importance. "
            "flags is a full replacement list of objects with label and starting_value. "
            "state_axis_choices is a patch list of objects with template_id plus optional story_label and starting_value; keep the same axis set and do not add or remove axes. "
            "cast is a list of objects with npc_id and optional name, role, agenda, red_line, pressure_signature, roster_character_id. "
            "beats is a list of objects with beat_id and optional title, goal, focus_names, conflict_pair, milestone_kind, pressure_axis_id, route_pivot_tag, required_truth_texts, detour_budget, progress_required, return_hooks, affordance_tags, blocked_affordances. "
            "rule_pack is an object with optional toward, intensity, route_unlock_rules, affordance_effect_profiles, ending_rules. "
            "Use only existing beat ids, affordance tags, truth ids, event ids, flag ids, stance ids, axis ids, and ending ids. "
            "Keep collapse, pyrrhic, and mixed ending coverage. "
            "All user-visible string values must follow the target story language, while identifiers stay as existing ids. "
            "Do not add or remove characters or beats."
        )
        try:
            response = gateway.invoke_text_capability(
                "copilot.rewrite_plan",
                TextCapabilityRequest(
                    system_prompt=system_prompt,
                    user_payload=payload,
                    max_output_tokens=gateway.text_policy("copilot.rewrite_plan").max_output_tokens,
                    operation_name="copilot_rewrite_plan",
                ),
            )
            plan = AuthorCopilotRewritePlan(
                story_frame=(
                    AuthorCopilotStoryFrameRewrite.model_validate(response.payload.get("story_frame"))
                    if response.payload.get("story_frame") is not None
                    else None
                ),
                cast=[
                    AuthorCopilotCastRewrite.model_validate(item)
                    for item in list(response.payload.get("cast") or [])
                ],
                beats=[
                    AuthorCopilotBeatRewrite.model_validate(item)
                    for item in list(response.payload.get("beats") or [])
                ],
                rule_pack=(
                    AuthorCopilotRulePackRewrite.model_validate(response.payload.get("rule_pack"))
                    if response.payload.get("rule_pack") is not None
                    else None
                ),
            )
            affected_sections = _affected_sections(plan)
            if not affected_sections:
                raise ValueError("rewrite_plan_empty")
            request_summary = str(response.payload.get("request_summary") or instruction).strip()
            variant_label = str(response.payload.get("variant_label") or f"Variant {variant_index}").strip()
            impact_summary = [str(item) for item in list(response.payload.get("impact_summary") or [])][:8]
            warnings = [str(item) for item in list(response.payload.get("warnings") or [])][:8]
            if not _proposal_matches_story_language(
                request_summary=request_summary,
                variant_label=variant_label,
                impact_summary=impact_summary,
                warnings=warnings,
                plan=plan,
                language=editor_state.language,
            ):
                raise ValueError("rewrite_plan_language_mismatch")
            source = "llm"
            fingerprint = f"llm:{variant_index}:{hash(normalize_whitespace(request_summary))}"
        except Exception:  # noqa: BLE001
            synthesized = _synthesize_rewrite_plan(
                editor_state=editor_state,
                workspace_snapshot=workspace_snapshot,
                base_bundle=base_bundle,
                intent=intent_packet,
                variant_index=variant_index,
            )
            plan = synthesized.plan
            request_summary = synthesized.request_summary
            variant_label = synthesized.variant_label
            affected_sections = synthesized.affected_sections
            impact_summary = synthesized.impact_summary
            warnings = synthesized.warnings
            fingerprint = synthesized.fingerprint
            source = "heuristic"
    else:
        synthesized = _synthesize_rewrite_plan(
            editor_state=editor_state,
            workspace_snapshot=workspace_snapshot,
            base_bundle=base_bundle,
            intent=intent_packet,
            variant_index=variant_index,
        )
        plan = synthesized.plan
        request_summary = synthesized.request_summary
        variant_label = synthesized.variant_label
        affected_sections = synthesized.affected_sections
        impact_summary = synthesized.impact_summary
        warnings = synthesized.warnings
        fingerprint = synthesized.fingerprint
        source = "heuristic"

    stability_guards = [
        f"language={editor_state.language}",
        f"runtime_profile={editor_state.play_profile_view.runtime_profile}",
        f"closeout_profile={editor_state.play_profile_view.closeout_profile}",
        f"cast_topology={len(editor_state.cast_view)}_slot",
        f"beat_count={len(editor_state.beat_view)}",
        f"max_turns={editor_state.play_profile_view.max_turns}",
    ]
    operations = _build_compat_operations(plan)
    proposal = AuthorCopilotProposalResponse(
        proposal_id=str(uuid4()),
        proposal_group_id=proposal_group_id,
        session_id=session.session_id if session is not None else None,
        job_id=job_id,
        status="draft",
        source=source,  # type: ignore[arg-type]
        mode="bundle_rewrite",
        instruction=instruction,
        base_revision=base_revision,
        variant_index=variant_index,
        variant_label=variant_label,
        supersedes_proposal_id=supersedes_proposal_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        request_summary=request_summary,
        rewrite_scope="global_story_rewrite",
        rewrite_brief=rewrite_brief_text,
        affected_sections=affected_sections,  # type: ignore[arg-type]
        stability_guards=stability_guards,
        rewrite_plan=plan,
        patch_targets=affected_sections,  # type: ignore[arg-type]
        operations=operations,
        impact_summary=unique_preserve(impact_summary),
        warnings=warnings,
    )
    return proposal, fingerprint


def _adjust_ending_tilt(
    *,
    bundle: DesignBundle,
    rewrite: AuthorCopilotRulePackRewrite | None,
) -> DesignBundle:
    if rewrite is None or rewrite.toward is None:
        return bundle
    pressure_axis_id = next(
        (axis.axis_id for axis in bundle.state_schema.axes if axis.kind == "pressure"),
        bundle.state_schema.axes[0].axis_id,
    )
    adjusted_rules: list[EndingRule] = []
    chosen_priority = {"collapse": 1, "pyrrhic": 2, "mixed": 3}.get(rewrite.toward, 3)
    max_value = {"light": 3, "medium": 2, "strong": 1}.get(rewrite.intensity or "medium", 2)
    for rule in bundle.rule_pack.ending_rules:
        next_rule = rule
        if rule.ending_id == "mixed" and rewrite.toward in {"pyrrhic", "collapse"}:
            condition_payload = rule.conditions.model_dump(mode="json")
            max_axes = dict(condition_payload.get("max_axes") or {})
            current = max_axes.get(pressure_axis_id)
            max_axes[pressure_axis_id] = min(int(current), max_value) if current is not None else max_value
            condition_payload["max_axes"] = max_axes
            next_rule = rule.model_copy(update={"conditions": ConditionBlock.model_validate(condition_payload)})
        if rule.ending_id == rewrite.toward:
            next_rule = next_rule.model_copy(update={"priority": chosen_priority})
        adjusted_rules.append(next_rule)
    normalized = normalize_ending_rules_draft(
        EndingRulesDraft(ending_rules=adjusted_rules),
        bundle,
    )
    return bundle.model_copy(
        update={
            "rule_pack": bundle.rule_pack.model_copy(update={"ending_rules": normalized.ending_rules})
        }
    )


def apply_copilot_operations(
    *,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
    proposal: AuthorCopilotProposalResponse,
    gateway: CapabilityGatewayCore | None = None,
) -> tuple[AuthorCopilotWorkspaceSnapshot, DesignBundle]:
    plan = proposal.rewrite_plan
    story_frame = workspace_snapshot.story_frame_draft
    if plan.story_frame is not None:
        scalar_story_updates = {
            field_name: getattr(plan.story_frame, field_name)
            for field_name in {"title", "premise", "tone", "stakes", "style_guard", "world_rules", "truths", "flags"}
            if field_name in plan.story_frame.model_fields_set and getattr(plan.story_frame, field_name) is not None
        }
        if scalar_story_updates:
            story_frame = story_frame.model_copy(update=scalar_story_updates)
        if "state_axis_choices" in plan.story_frame.model_fields_set:
            axis_patches = {
                patch.template_id: patch
                for patch in (plan.story_frame.state_axis_choices or [])
            }
            patched_axes = []
            for axis in story_frame.state_axis_choices:
                patch = axis_patches.get(axis.template_id)
                if patch is None:
                    patched_axes.append(axis)
                    continue
                axis_update: dict[str, Any] = {}
                if "story_label" in patch.model_fields_set and patch.story_label is not None:
                    axis_update["story_label"] = patch.story_label
                if "starting_value" in patch.model_fields_set and patch.starting_value is not None:
                    axis_update["starting_value"] = patch.starting_value
                patched_axes.append(axis.model_copy(update=axis_update) if axis_update else axis)
            story_frame = story_frame.model_copy(update={"state_axis_choices": patched_axes})
    cast_members = list(workspace_snapshot.cast_member_drafts)
    for patch in plan.cast:
        target_index = next(
            (idx for idx, member in enumerate(cast_members) if slugify(member.name) == patch.npc_id),
            None,
        )
        if target_index is None:
            continue
        member = cast_members[target_index]
        roster_entry = _roster_entry_for_id(member.roster_character_id) if member.roster_character_id else None
        if "roster_character_id" in patch.model_fields_set:
            if patch.roster_character_id:
                entry = _roster_entry_for_id(patch.roster_character_id)
                if entry is not None:
                    roster_entry = entry
                    projection = _localized_roster_projection(entry, workspace_snapshot.focused_brief.language)
                    sibling_names = {
                        existing_member.name
                        for idx, existing_member in enumerate(cast_members)
                        if idx != target_index
                    }
                    projected_name = projection["name"] or member.name
                    if projected_name in sibling_names:
                        projected_name = member.name
                    slot = (
                        workspace_snapshot.cast_overview_draft.cast_slots[target_index]
                        if target_index < len(workspace_snapshot.cast_overview_draft.cast_slots)
                        else None
                    )
                    projected_update: dict[str, Any] = {
                        "name": projected_name,
                        "roster_character_id": entry.character_id,
                        "roster_public_summary": projection["public_summary"],
                        "portrait_url": entry.portrait_url,
                        "portrait_variants": entry.portrait_variants,
                        "template_version": entry.template_version or entry.source_fingerprint,
                    }
                    if slot is not None:
                        projected_update.update(
                            {
                                "role": slot.public_role,
                                "agenda": normalize_whitespace(f"{slot.agenda_anchor} {projection['agenda_seed'] or ''}"),
                                "red_line": normalize_whitespace(f"{slot.red_line_anchor} {projection['red_line_seed'] or ''}"),
                                "pressure_signature": normalize_whitespace(f"{slot.pressure_vector} {projection['pressure_seed'] or ''}"),
                            }
                        )
                    member = member.model_copy(update=projected_update)
                    member = member.model_copy(
                        update={
                            "story_instance": default_story_instance_snapshot(
                                base_member=member,
                                gender_lock=entry.gender_lock,
                            )
                        }
                    )
                    if gateway is not None and slot is not None and template_profile_complete(entry):
                        try:
                            instance = generate_story_character_instance(
                                gateway,
                                focused_brief=workspace_snapshot.focused_brief,
                                story_frame=story_frame,
                                slot_payload=slot.model_dump(mode="json"),
                                entry=entry,
                                base_member=member,
                                primary_theme=workspace_snapshot.primary_theme,
                                story_frame_strategy=workspace_snapshot.story_frame_strategy,
                            )
                            member = apply_story_character_instance(
                                base_member=member,
                                draft=instance.value,
                                entry=entry,
                                materialization_source="generated",
                            )
                        except AuthorGatewayError as exc:
                            del exc
                else:
                    roster_entry = None
                    member = member.model_copy(
                        update={
                            "roster_character_id": patch.roster_character_id,
                            "roster_public_summary": None,
                            "portrait_url": None,
                            "portrait_variants": None,
                            "template_version": None,
                            "story_instance": None,
                        }
                    )
            else:
                roster_entry = None
                member = member.model_copy(
                    update={
                        "roster_character_id": None,
                        "roster_public_summary": None,
                        "portrait_url": None,
                        "portrait_variants": None,
                        "template_version": None,
                        "story_instance": None,
                    }
                )
        explicit_member_updates = {
            key: value
            for key, value in _explicit_fields(patch).items()
            if key not in {"npc_id", "roster_character_id"} and value is not None
        }
        if member.roster_character_id:
            explicit_member_updates.pop("name", None)
        if explicit_member_updates:
            prior_member = member
            member = member.model_copy(update=explicit_member_updates)
            member = sanitize_story_character_member(
                base_member=prior_member,
                candidate_member=member,
                entry=roster_entry,
            )
            if roster_entry is not None and any(
                key in explicit_member_updates
                for key in ("role", "roster_public_summary", "agenda", "red_line", "pressure_signature")
            ):
                member = member.model_copy(update={"story_instance": None})
        cast_members[target_index] = member
    cast_draft = workspace_snapshot.cast_draft.model_copy(update={"cast": cast_members})
    beats = list(workspace_snapshot.beat_plan_draft.beats)
    for patch in plan.beats:
        beat_index = next((idx for idx, _beat in enumerate(beats) if f"b{idx + 1}" == patch.beat_id), None)
        if beat_index is None:
            continue
        beat_updates = {
            key: value
            for key, value in _explicit_fields(patch).items()
            if key != "beat_id" and value is not None
        }
        beats[beat_index] = beats[beat_index].model_copy(update=beat_updates)
    beat_plan_draft = workspace_snapshot.beat_plan_draft.model_copy(update={"beats": beats})
    updated_snapshot = workspace_snapshot.model_copy(
        update={
            "story_frame_draft": story_frame,
            "cast_member_drafts": cast_members,
            "cast_draft": cast_draft,
            "beat_plan_draft": beat_plan_draft,
        }
    )
    return _compile_copilot_bundle(workspace_snapshot=updated_snapshot, rewrite=plan.rule_pack)


def validate_copilot_candidate(
    *,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
    candidate_snapshot: AuthorCopilotWorkspaceSnapshot,
    bundle: DesignBundle,
) -> list[str]:
    reasons: list[str] = []
    if len(candidate_snapshot.cast_draft.cast) != len(workspace_snapshot.cast_draft.cast):
        reasons.append("cast_count_changed")
    if len(bundle.story_bible.cast) != len(workspace_snapshot.cast_draft.cast):
        reasons.append("compiled_cast_count_changed")
    if len(candidate_snapshot.beat_plan_draft.beats) != len(workspace_snapshot.beat_plan_draft.beats):
        reasons.append("beat_count_changed")
    if len(bundle.beat_spine) != len(workspace_snapshot.beat_plan_draft.beats):
        reasons.append("compiled_beat_count_changed")
    if [axis.template_id for axis in candidate_snapshot.story_frame_draft.state_axis_choices] != [
        axis.template_id for axis in workspace_snapshot.story_frame_draft.state_axis_choices
    ]:
        reasons.append("state_axis_choices_changed")
    candidate_cast_names = {member.name for member in candidate_snapshot.cast_draft.cast}
    if len(candidate_cast_names) != len(candidate_snapshot.cast_draft.cast):
        reasons.append("cast_name_duplicate")
    candidate_truth_texts = {truth.text for truth in candidate_snapshot.story_frame_draft.truths}
    candidate_axis_ids = {axis.template_id for axis in candidate_snapshot.story_frame_draft.state_axis_choices}
    for beat in candidate_snapshot.beat_plan_draft.beats:
        if any(name not in candidate_cast_names for name in beat.focus_names):
            reasons.append("beat_focus_reference_missing")
        if any(name not in candidate_cast_names for name in beat.conflict_pair):
            reasons.append("beat_conflict_reference_missing")
        if beat.pressure_axis_id and beat.pressure_axis_id not in candidate_axis_ids:
            reasons.append("beat_axis_reference_missing")
        if any(text not in candidate_truth_texts for text in beat.required_truth_texts):
            reasons.append("beat_required_truth_missing")
    if any(
        member.roster_character_id and _roster_entry_for_id(member.roster_character_id) is None
        for member in candidate_snapshot.cast_draft.cast
    ):
        reasons.append("roster_character_missing")
    beat_npc_ids = {npc_id for beat in bundle.beat_spine for npc_id in (*beat.focus_npcs, *beat.conflict_npcs)}
    cast_npc_ids = {member.npc_id for member in bundle.story_bible.cast}
    if len(cast_npc_ids) != len(bundle.story_bible.cast):
        reasons.append("compiled_cast_identity_duplicate")
    if not beat_npc_ids.issubset(cast_npc_ids):
        reasons.append("beat_npc_reference_missing")
    axis_ids = {axis.axis_id for axis in bundle.state_schema.axes}
    stance_ids = {stance.stance_id for stance in bundle.state_schema.stances}
    truth_ids = {truth.truth_id for truth in bundle.story_bible.truth_catalog}
    event_ids = {event_id for beat in bundle.beat_spine for event_id in beat.required_events}
    flag_ids = {flag.flag_id for flag in bundle.state_schema.flags}
    ending_ids = {ending.ending_id for ending in bundle.story_bible.ending_catalog}
    beat_ids = {beat.beat_id for beat in bundle.beat_spine}
    affordance_tags = set(bundle_affordance_tags(bundle))
    route_pack = candidate_snapshot.route_affordance_pack_draft
    if route_pack is None or not route_pack.affordance_effect_profiles:
        reasons.append("route_affordance_pack_empty")
    else:
        if not route_pack.route_unlock_rules:
            reasons.append("route_unlock_rules_empty")
        for route_rule in route_pack.route_unlock_rules:
            if not _route_rule_references_valid(
                route_rule,
                beat_ids=beat_ids,
                affordance_tags=affordance_tags,
                axis_ids=axis_ids,
                stance_ids=stance_ids,
                truth_ids=truth_ids,
                event_ids=event_ids,
                flag_ids=flag_ids,
            ):
                reasons.append("route_rule_reference_invalid")
                break
        for profile in route_pack.affordance_effect_profiles:
            if not _effect_profile_references_valid(
                profile,
                affordance_tags=affordance_tags,
                axis_ids=axis_ids,
                stance_ids=stance_ids,
            ):
                reasons.append("affordance_profile_reference_invalid")
                break
    ending_rules = candidate_snapshot.ending_rules_draft.ending_rules if candidate_snapshot.ending_rules_draft is not None else bundle.rule_pack.ending_rules
    if not {"collapse", "pyrrhic", "mixed"}.issubset({rule.ending_id for rule in ending_rules}):
        reasons.append("required_endings_missing")
    for ending_rule in ending_rules:
        if not _ending_rule_references_valid(
            ending_rule,
            ending_ids=ending_ids,
            axis_ids=axis_ids,
            stance_ids=stance_ids,
            truth_ids=truth_ids,
            event_ids=event_ids,
            flag_ids=flag_ids,
        ):
            reasons.append("ending_rule_reference_invalid")
            break
    try:
        play_plan = compile_play_plan(story_id="copilot-preview", bundle=bundle)
        if play_plan.runtime_policy_profile != workspace_snapshot.runtime_profile:
            reasons.append("runtime_profile_changed")
        if play_plan.closeout_profile != workspace_snapshot.closeout_profile:
            reasons.append("closeout_profile_changed")
        if play_plan.max_turns != workspace_snapshot.max_turns:
            reasons.append("max_turns_changed")
    except Exception:  # noqa: BLE001
        reasons.append("play_compile_failed")
    return unique_preserve(reasons)


def repair_copilot_candidate(
    *,
    workspace_snapshot: AuthorCopilotWorkspaceSnapshot,
    candidate_snapshot: AuthorCopilotWorkspaceSnapshot,
    proposal: AuthorCopilotProposalResponse,
) -> tuple[AuthorCopilotWorkspaceSnapshot, DesignBundle]:
    safe_rule_rewrite = None
    if proposal.rewrite_plan.rule_pack is not None and (
        proposal.rewrite_plan.rule_pack.toward is not None
        or proposal.rewrite_plan.rule_pack.intensity is not None
    ):
        safe_rule_rewrite = AuthorCopilotRulePackRewrite(
            toward=proposal.rewrite_plan.rule_pack.toward,
            intensity=proposal.rewrite_plan.rule_pack.intensity,
        )
    repaired_snapshot = candidate_snapshot.model_copy(
        update={
            "route_affordance_pack_draft": workspace_snapshot.route_affordance_pack_draft,
            "ending_intent_draft": workspace_snapshot.ending_intent_draft,
            "ending_rules_draft": workspace_snapshot.ending_rules_draft,
        }
    )
    return _compile_copilot_bundle(
        workspace_snapshot=repaired_snapshot,
        rewrite=safe_rule_rewrite,
    )

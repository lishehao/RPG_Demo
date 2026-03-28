from __future__ import annotations

from rpg_backend.content_language import localized_text
from rpg_backend.author.compiler.beats import (
    compiled_affordance_tags_for_beat,
    event_id_for_beat,
)
from rpg_backend.author.planning import ending_summary_for_tone
from rpg_backend.author.contracts import (
    AffordanceEffectProfile,
    AffordanceWeight,
    AxisTemplateId,
    BeatPlanDraft,
    BeatSpec,
    CastDraft,
    CastMember,
    DesignBundle,
    EndingItem,
    EndingRule,
    FocusedBrief,
    OverviewFlagDraft,
    RulePack,
    StateSchema,
    StoryFlowPlan,
    StoryGenerationControls,
    StoryBible,
    StoryFrameDraft,
    TonePlan,
    TruthItem,
)
from rpg_backend.author.normalize import slugify, trim_ellipsis, unique_preserve


AXIS_TEMPLATE_CATALOG: dict[str, dict[str, str | int]] = {
    "external_pressure": {"label": "External Pressure", "kind": "pressure", "min_value": 0, "max_value": 5},
    "public_panic": {"label": "Public Panic", "kind": "pressure", "min_value": 0, "max_value": 5},
    "political_leverage": {"label": "Political Leverage", "kind": "relationship", "min_value": 0, "max_value": 5},
    "resource_strain": {"label": "Resource Strain", "kind": "resource", "min_value": 0, "max_value": 5},
    "system_integrity": {"label": "System Integrity", "kind": "pressure", "min_value": 0, "max_value": 5},
    "ally_trust": {"label": "Ally Trust", "kind": "relationship", "min_value": 0, "max_value": 5},
    "exposure_risk": {"label": "Exposure Risk", "kind": "exposure", "min_value": 0, "max_value": 5},
    "time_window": {"label": "Time Window", "kind": "time", "min_value": 0, "max_value": 5},
}

AXIS_TEMPLATE_CATALOG_ZH: dict[str, str] = {
    "external_pressure": "外部压力",
    "public_panic": "公众恐慌",
    "political_leverage": "政治筹码",
    "resource_strain": "资源紧张",
    "system_integrity": "系统完整性",
    "ally_trust": "盟友信任",
    "exposure_risk": "曝光风险",
    "time_window": "时间窗口",
}

DEFAULT_AXIS_ORDER: tuple[AxisTemplateId, ...] = (
    "external_pressure",
    "public_panic",
    "political_leverage",
)


def _npc_id(name: str) -> str:
    return slugify(name)


def build_design_bundle(
    story_frame: StoryFrameDraft,
    cast_draft: CastDraft,
    beat_plan_draft: BeatPlanDraft,
    focused_brief: FocusedBrief,
    *,
    generation_controls: StoryGenerationControls | None = None,
    story_flow_plan: StoryFlowPlan | None = None,
    resolved_tone_plan: TonePlan | None = None,
) -> DesignBundle:
    cast = [
        CastMember(
            npc_id=_npc_id(item.name),
            name=trim_ellipsis(item.name, 80),
            role=trim_ellipsis(item.role, 120),
            agenda=trim_ellipsis(item.agenda, 220),
            red_line=trim_ellipsis(item.red_line, 220),
            pressure_signature=trim_ellipsis(item.pressure_signature, 220),
            roster_character_id=item.roster_character_id,
            roster_public_summary=item.roster_public_summary,
            portrait_url=item.portrait_url,
            portrait_variants=item.portrait_variants,
            template_version=item.template_version,
            story_instance=item.story_instance,
        )
        for item in cast_draft.cast
    ]
    truths = [
        TruthItem(
            truth_id=f"truth_{index}",
            text=trim_ellipsis(item.text, 220),
            importance=item.importance,
        )
        for index, item in enumerate(story_frame.truths, start=1)
    ]
    truth_id_by_text = {
        item.text: truth.truth_id
        for item, truth in zip(story_frame.truths, truths, strict=False)
    }
    axis_rows: list[dict[str, object]] = []
    seen_axis_ids: set[str] = set()
    for axis in story_frame.state_axis_choices:
        template = AXIS_TEMPLATE_CATALOG[axis.template_id]
        if axis.template_id in seen_axis_ids:
            continue
        seen_axis_ids.add(axis.template_id)
        axis_rows.append(
            {
                "axis_id": axis.template_id,
                "label": trim_ellipsis(
                    axis.story_label
                    or localized_text(
                        focused_brief.language,
                        en=str(template["label"]),
                        zh=AXIS_TEMPLATE_CATALOG_ZH.get(axis.template_id, str(template["label"])),
                    ),
                    80,
                ),
                "kind": template["kind"],
                "min_value": int(template["min_value"]),
                "max_value": int(template["max_value"]),
                "starting_value": max(0, min(int(template["max_value"]), axis.starting_value)),
            }
        )
    for axis_id in DEFAULT_AXIS_ORDER:
        if axis_id in seen_axis_ids:
            continue
        template = AXIS_TEMPLATE_CATALOG[axis_id]
        axis_rows.append(
            {
                "axis_id": axis_id,
                "label": localized_text(
                    focused_brief.language,
                    en=str(template["label"]),
                    zh=AXIS_TEMPLATE_CATALOG_ZH.get(axis_id, str(template["label"])),
                ),
                "kind": template["kind"],
                "min_value": int(template["min_value"]),
                "max_value": int(template["max_value"]),
                "starting_value": 0 if axis_id != "external_pressure" else 1,
            }
        )
        seen_axis_ids.add(axis_id)
        if len(axis_rows) >= 3:
            break
    state_schema = StateSchema.model_validate(
        {
            "axes": axis_rows[:6],
            "stances": [
                {
                    "stance_id": f"{_npc_id(item.name)}_stance",
                    "npc_id": _npc_id(item.name),
                    "label": localized_text(
                        focused_brief.language,
                        en=f"{trim_ellipsis(item.name, 60)} Stance",
                        zh=f"{trim_ellipsis(item.name, 60)}立场",
                    ),
                    "min_value": -2,
                    "max_value": 3,
                    "starting_value": 0,
                }
                for item in cast_draft.cast
            ],
            "flags": [
                {
                    "flag_id": slugify(flag.label),
                    "label": trim_ellipsis(flag.label, 80),
                    "starting_value": bool(flag.starting_value),
                }
                for flag in story_frame.flags
            ],
        }
    )
    bible = StoryBible(
        title=trim_ellipsis(story_frame.title, 120),
        premise=trim_ellipsis(story_frame.premise, 320),
        tone=trim_ellipsis(story_frame.tone, 120),
        stakes=trim_ellipsis(story_frame.stakes, 240),
        style_guard=trim_ellipsis(story_frame.style_guard, 220),
        cast=cast,
        world_rules=[trim_ellipsis(item, 180) for item in story_frame.world_rules],
        truth_catalog=truths,
        ending_catalog=[
            EndingItem(
                ending_id="mixed",
                label=localized_text(focused_brief.language, en="Mixed Outcome", zh="混合结局"),
                summary=ending_summary_for_tone(
                    ending_id="mixed",
                    language=focused_brief.language,
                    tone_plan=resolved_tone_plan,
                )
                or localized_text(
                    focused_brief.language,
                    en="The city survives, but trust and stability remain damaged.",
                    zh="城市保住了，但信任与稳定都已经受损。",
                ),
            ),
            EndingItem(
                ending_id="pyrrhic",
                label=localized_text(focused_brief.language, en="Pyrrhic Outcome", zh="惨胜结局"),
                summary=ending_summary_for_tone(
                    ending_id="pyrrhic",
                    language=focused_brief.language,
                    tone_plan=resolved_tone_plan,
                )
                or localized_text(
                    focused_brief.language,
                    en="Success arrives only through a steep civic or personal cost.",
                    zh="局面稳住时，沉重的公共或个人代价也已经摆到台前。",
                ),
            ),
            EndingItem(
                ending_id="collapse",
                label=localized_text(focused_brief.language, en="Collapse", zh="崩溃结局"),
                summary=ending_summary_for_tone(
                    ending_id="collapse",
                    language=focused_brief.language,
                    tone_plan=resolved_tone_plan,
                )
                or localized_text(
                    focused_brief.language,
                    en="The crisis outruns coordination and the city pays the price.",
                    zh="危机最终跑赢了协调能力，而整座城市为此付出代价。",
                ),
            ),
        ],
    )
    cast_names = {item.name for item in cast_draft.cast}
    cast_id_by_name = {item.name: _npc_id(item.name) for item in cast_draft.cast}
    beat_spine: list[BeatSpec] = []
    for index, beat in enumerate(beat_plan_draft.beats, start=1):
        focus_names = unique_preserve(
            [name for name in (*beat.focus_names, *beat.conflict_pair) if name in cast_names]
        )
        focus_npcs = [cast_id_by_name[name] for name in focus_names][:3]
        conflict_npcs = [cast_id_by_name[name] for name in beat.conflict_pair if name in cast_names][:2]
        affordance_tags = compiled_affordance_tags_for_beat(beat)
        event_id = event_id_for_beat(index, beat)
        beat_spine.append(
            BeatSpec(
                beat_id=f"b{index}",
                title=trim_ellipsis(beat.title, 120),
                goal=trim_ellipsis(beat.goal, 220),
                focus_npcs=focus_npcs,
                conflict_npcs=conflict_npcs,
                pressure_axis_id=beat.pressure_axis_id,
                milestone_kind=beat.milestone_kind,
                route_pivot_tag=beat.route_pivot_tag,
                required_truths=[
                    truth_id_by_text[text]
                    for text in beat.required_truth_texts
                    if text in truth_id_by_text
                ][:4],
                required_events=[event_id],
                detour_budget=beat.detour_budget,
                progress_required=beat.progress_required,
                return_hooks=[trim_ellipsis(item, 180) for item in beat.return_hooks[:3]],
                affordances=[
                    AffordanceWeight(tag=tag, weight=1 + (offset == 0))
                    for offset, tag in enumerate(affordance_tags[:6])
                ],
                blocked_affordances=beat.blocked_affordances[:4],
            )
        )
    return DesignBundle(
        focused_brief=focused_brief,
        generation_controls=generation_controls,
        story_flow_plan=story_flow_plan,
        resolved_tone_plan=resolved_tone_plan,
        story_bible=bible,
        state_schema=state_schema,
        beat_spine=beat_spine,
        rule_pack=RulePack(
            route_unlock_rules=[],
            ending_rules=[EndingRule(ending_id="mixed", priority=100, conditions={})],
            affordance_effect_profiles=[
                AffordanceEffectProfile(
                    affordance_tag="reveal_truth",
                    default_story_function="reveal",
                    axis_deltas={},
                    stance_deltas={},
                    can_add_truth=True,
                    can_add_event=False,
                ),
                AffordanceEffectProfile(
                    affordance_tag="build_trust",
                    default_story_function="advance",
                    axis_deltas={},
                    stance_deltas={},
                    can_add_truth=False,
                    can_add_event=True,
                ),
            ],
        ),
    )

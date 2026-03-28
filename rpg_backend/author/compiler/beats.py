from __future__ import annotations

from rpg_backend.content_language import localized_text
from rpg_backend.author.contracts import (
    BeatDraftSpec,
    BeatPlanDraft,
    CastDraft,
    FocusedBrief,
    StoryFlowPlan,
    StoryFrameDraft,
    TonePlan,
)
from rpg_backend.author.normalize import slugify, trim_ellipsis, unique_preserve


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keyword in keywords)


def _normalize_affordance_tag(value: str) -> str:
    normalized = slugify(value)
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
    story_flow_plan: StoryFlowPlan | None = None,
    tone_plan: TonePlan | None = None,
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
    if _contains_any(lowered, ("blackout", "停电")) and _contains_any(lowered, ("succession", "election", "继承", "选举", "投票")):
        beat_blueprints = [
            {
                "title": localized_text(focused_brief.language, en="The First Nightfall", zh="第一道夜幕"),
                "goal": localized_text(focused_brief.language, en="Stabilize emergency coordination long enough to learn who benefits from the blackout.", zh="先稳住紧急协同，好查清到底是谁从停电中获利。"),
                "focus_names": opening_pair[:3],
                "conflict_pair": opening_pair[:2],
                "pressure_axis_id": first_axis,
                "milestone_kind": "reveal",
                "route_pivot_tag": "reveal_truth",
                "required_truth_texts": [truth_texts[0] if truth_texts else focused_brief.core_conflict],
                "return_hooks": [localized_text(focused_brief.language, en="A service failure forces the mediator to choose between speed and legitimacy.", zh="一次服务失灵逼得调停者必须在速度与正当性之间做出选择。")],
                "affordance_tags": ["reveal_truth", "contain_chaos", "build_trust"],
            },
            {
                "title": localized_text(focused_brief.language, en="The Public Ledger", zh="公开账本"),
                "goal": localized_text(focused_brief.language, en="Turn improvised relief into a civic process the rival factions cannot dismiss as a power grab.", zh="把临时救济变成一套公开程序，让敌对派系无法再把它说成夺权。"),
                "focus_names": alliance_pair[:3],
                "conflict_pair": alliance_pair[:2],
                "pressure_axis_id": second_axis,
                "milestone_kind": "containment",
                "route_pivot_tag": "build_trust",
                "required_truth_texts": [truth_texts[1] if len(truth_texts) > 1 else truth_texts[0] if truth_texts else focused_brief.setting_signal],
                "return_hooks": [localized_text(focused_brief.language, en="Public patience starts collapsing unless the emergency process becomes legible.", zh="如果紧急流程始终说不清楚，公众耐心就会开始崩塌。")],
                "affordance_tags": ["build_trust", "contain_chaos", "secure_resources"],
            },
            {
                "title": localized_text(focused_brief.language, en="The Dawn Bargain", zh="黎明交易"),
                "goal": localized_text(focused_brief.language, en="Force a visible settlement before the succession vacuum hardens into a new political order.", zh="在继承真空固化成新秩序前，逼出一份公开可见的和解。"),
                "focus_names": settlement_pair[:3],
                "conflict_pair": settlement_pair[:2],
                "pressure_axis_id": third_axis,
                "milestone_kind": "commitment",
                "route_pivot_tag": "shift_public_narrative",
                "required_truth_texts": [truth_texts[-1] if truth_texts else focused_brief.core_conflict],
                "return_hooks": [localized_text(focused_brief.language, en="The city will accept one story about the night, and the mediator has to choose it in public.", zh="这座城市最终只会接受关于今夜的一种说法，而调停者必须当众选定它。")],
                "affordance_tags": ["shift_public_narrative", "build_trust", "pay_cost"],
            },
        ]
    elif _contains_any(lowered, ("harbor", "port", "trade", "quarantine", "港口", "码头", "贸易", "检疫", "舱单")):
        beat_blueprints = [
            {
                "title": localized_text(focused_brief.language, en="The Quarantine Line", zh="检疫封线"),
                "goal": localized_text(focused_brief.language, en="Stabilize the harbor perimeter before panic turns quarantine into factional seizure.", zh="在恐慌把检疫变成派系夺取前，先稳住港口边界。"),
                "focus_names": opening_pair[:3],
                "conflict_pair": opening_pair[:2],
                "pressure_axis_id": first_axis,
                "milestone_kind": "reveal",
                "route_pivot_tag": "contain_chaos",
                "required_truth_texts": [truth_texts[0] if truth_texts else focused_brief.core_conflict],
                "return_hooks": [localized_text(focused_brief.language, en="A visible breach forces the harbor crisis into public view.", zh="一道肉眼可见的缺口把港口危机直接推到了公众面前。")],
                "affordance_tags": ["contain_chaos", "secure_resources", "reveal_truth"],
            },
            {
                "title": localized_text(focused_brief.language, en="The Dockside Audit", zh="码头审计"),
                "goal": localized_text(focused_brief.language, en="Expose which faction profits from scarcity before emergency trade powers become permanent leverage.", zh="在紧急贸易权力固化前，揭出究竟是哪一派从短缺中获利。"),
                "focus_names": alliance_pair[:3],
                "conflict_pair": alliance_pair[:2],
                "pressure_axis_id": second_axis,
                "milestone_kind": "fracture",
                "route_pivot_tag": "reveal_truth",
                "required_truth_texts": [truth_texts[1] if len(truth_texts) > 1 else truth_texts[0] if truth_texts else focused_brief.setting_signal],
                "return_hooks": [localized_text(focused_brief.language, en="The audit names winners and losers, and the coalition can no longer stay procedural.", zh="这场审计点出了赢家与输家，联盟再也不可能只停留在程序层面。")],
                "affordance_tags": ["reveal_truth", "shift_public_narrative", "build_trust"],
            },
            {
                "title": localized_text(focused_brief.language, en="The Harbor Compact", zh="港务协定"),
                "goal": localized_text(focused_brief.language, en="Lock the city into a recovery bargain before private leverage replaces public authority.", zh="在私人筹码取代公共权威前，把城市锁进一份恢复协定。"),
                "focus_names": settlement_pair[:3],
                "conflict_pair": settlement_pair[:2],
                "pressure_axis_id": third_axis,
                "milestone_kind": "commitment",
                "route_pivot_tag": "build_trust",
                "required_truth_texts": [truth_texts[-1] if truth_texts else focused_brief.core_conflict],
                "return_hooks": [localized_text(focused_brief.language, en="Once the compact is public, every faction has to decide what cost it will own.", zh="一旦协定公开，每个派系都必须决定自己愿意承担哪一部分代价。")],
                "affordance_tags": ["build_trust", "secure_resources", "pay_cost"],
            },
        ]
    else:
        beat_blueprints = [
            {
                "title": localized_text(focused_brief.language, en="Emergency Council", zh="紧急议会"),
                "goal": localized_text(focused_brief.language, en="Understand what is breaking and who is steering the crisis toward fracture.", zh="先弄清到底哪里在失控，以及是谁在把危机推向裂解。"),
                "focus_names": opening_pair[:3],
                "conflict_pair": opening_pair[:2],
                "pressure_axis_id": first_axis,
                "milestone_kind": "reveal",
                "route_pivot_tag": "reveal_truth",
                "required_truth_texts": [truth_texts[0] if truth_texts else focused_brief.core_conflict],
                "return_hooks": [localized_text(focused_brief.language, en="A visible public consequence forces the issue.", zh="一项肉眼可见的公共后果迫使所有人必须正面处理问题。")],
                "affordance_tags": ["reveal_truth", "contain_chaos", "build_trust"],
            },
            {
                "title": localized_text(focused_brief.language, en="Public Strain", zh="公众拉扯"),
                "goal": localized_text(focused_brief.language, en="Keep the coalition functional long enough to prove the crisis can still be governed in public.", zh="让联盟继续运转下去，好证明这场危机仍能在公开场域里被治理。"),
                "focus_names": alliance_pair[:3],
                "conflict_pair": alliance_pair[:2],
                "pressure_axis_id": second_axis,
                "milestone_kind": "containment",
                "route_pivot_tag": "build_trust",
                "required_truth_texts": [truth_texts[1] if len(truth_texts) > 1 else truth_texts[0] if truth_texts else focused_brief.setting_signal],
                "return_hooks": [localized_text(focused_brief.language, en="Delay becomes its own political cost unless someone makes order visible.", zh="如果迟迟没人把秩序做给公众看，拖延本身就会变成政治代价。")],
                "affordance_tags": ["build_trust", "contain_chaos", "shift_public_narrative"],
            },
            {
                "title": localized_text(focused_brief.language, en="Final Settlement", zh="最终结算"),
                "goal": localized_text(focused_brief.language, en="Force the crisis into a public settlement before pressure hardens into a new balance of power.", zh="在压力固化成新权力格局前，把危机逼进一场公开结算。"),
                "focus_names": settlement_pair[:3],
                "conflict_pair": settlement_pair[:2],
                "pressure_axis_id": third_axis,
                "milestone_kind": "commitment",
                "route_pivot_tag": "shift_public_narrative",
                "required_truth_texts": [truth_texts[-1] if truth_texts else focused_brief.core_conflict],
                "return_hooks": [localized_text(focused_brief.language, en="The coalition must either define the new order or be defined by it.", zh="联盟必须决定新秩序的样子，否则就会被新秩序反过来定义。")],
                "affordance_tags": ["shift_public_narrative", "build_trust", "pay_cost"],
            },
        ]

    target_count = max(2, min(5, story_flow_plan.target_beat_count if story_flow_plan is not None else len(beat_blueprints)))
    selected_blueprints = list(beat_blueprints)
    if target_count == 2:
        selected_blueprints = [beat_blueprints[0], beat_blueprints[-1]]
    elif target_count >= 4 and len(beat_blueprints) == 3:
        midpoint_blueprint = {
            "title": localized_text(focused_brief.language, en="The Narrowing Terms", zh="条件收紧"),
            "goal": localized_text(
                focused_brief.language,
                en="Force the crisis through a narrower public bargain before the final settlement hardens.",
                zh="在最终结算固化前，把危机逼进一轮更狭窄的公开交易。",
            ),
            "focus_names": unique_preserve([*beat_blueprints[1]["focus_names"], *beat_blueprints[2]["focus_names"]])[:3],
            "conflict_pair": list(beat_blueprints[1]["conflict_pair"][:2] or beat_blueprints[2]["conflict_pair"][:2]),
            "pressure_axis_id": beat_blueprints[1]["pressure_axis_id"] or beat_blueprints[2]["pressure_axis_id"],
            "milestone_kind": "concession",
            "route_pivot_tag": "pay_cost",
            "required_truth_texts": list(beat_blueprints[2]["required_truth_texts"][:1] or beat_blueprints[1]["required_truth_texts"][:1]),
            "return_hooks": [
                localized_text(
                    focused_brief.language,
                    en="The next move now has to declare who is paying to keep the settlement alive.",
                    zh="下一步必须公开说明，到底由谁来为维持这场结算继续付账。",
                )
            ],
            "affordance_tags": ["shift_public_narrative", "secure_resources", "pay_cost"],
        }
        if target_count == 4:
            selected_blueprints = [beat_blueprints[0], beat_blueprints[1], midpoint_blueprint, beat_blueprints[2]]
        else:
            late_blueprint = {
                "title": localized_text(focused_brief.language, en="The Public Price", zh="公开代价"),
                "goal": localized_text(
                    focused_brief.language,
                    en="Make the city face what the settlement will cost before anyone can hide the burden in procedure.",
                    zh="在任何人把代价重新藏进程序之前，让整座城市正视这份结算究竟要付什么。",
                ),
                "focus_names": unique_preserve([*beat_blueprints[2]["focus_names"], *beat_blueprints[1]["focus_names"]])[:3],
                "conflict_pair": list(beat_blueprints[2]["conflict_pair"][:2] or beat_blueprints[1]["conflict_pair"][:2]),
                "pressure_axis_id": beat_blueprints[2]["pressure_axis_id"] or beat_blueprints[1]["pressure_axis_id"],
                "milestone_kind": "fracture",
                "route_pivot_tag": "shift_public_narrative",
                "required_truth_texts": list(beat_blueprints[2]["required_truth_texts"][:1]),
                "return_hooks": [
                    localized_text(
                        focused_brief.language,
                        en="The settlement now survives or fails on whether the public accepts its visible cost.",
                        zh="这份结算能不能成立，取决于公众是否接受它现在已经暴露出来的代价。",
                    )
                ],
                "affordance_tags": ["shift_public_narrative", "build_trust", "pay_cost"],
            }
            selected_blueprints = [beat_blueprints[0], beat_blueprints[1], midpoint_blueprint, late_blueprint, beat_blueprints[2]]
    else:
        selected_blueprints = beat_blueprints[:target_count]

    progress_schedule = (
        list(story_flow_plan.progress_required_by_beat[:target_count])
        if story_flow_plan is not None
        else [2 for _ in selected_blueprints]
    )
    if story_flow_plan is None:
        detour_schedule = [1 for _ in selected_blueprints]
    else:
        detour_total = story_flow_plan.detour_budget_total
        detour_schedule = [0 for _ in selected_blueprints]
        preferred_positions = [index for index in range(1, max(len(selected_blueprints) - 1, 1))]
        if not preferred_positions:
            preferred_positions = list(range(len(selected_blueprints)))
        while detour_total > 0 and preferred_positions:
            changed = False
            for index in preferred_positions:
                if detour_total <= 0:
                    break
                if detour_schedule[index] >= 2:
                    continue
                detour_schedule[index] += 1
                detour_total -= 1
                changed = True
            if not changed:
                break

    return BeatPlanDraft(
        beats=[
            BeatDraftSpec(
                title=trim_ellipsis(blueprint["title"], 120),
                goal=trim_ellipsis(blueprint["goal"], 220),
                focus_names=blueprint["focus_names"],
                conflict_pair=blueprint["conflict_pair"],
                pressure_axis_id=blueprint["pressure_axis_id"],
                milestone_kind=blueprint["milestone_kind"],
                route_pivot_tag=blueprint["route_pivot_tag"],
                required_truth_texts=[trim_ellipsis(item, 220) for item in blueprint["required_truth_texts"][:3]],
                detour_budget=detour_schedule[index],
                progress_required=progress_schedule[index],
                return_hooks=[trim_ellipsis(item, 180) for item in blueprint["return_hooks"][:3]],
                affordance_tags=blueprint["affordance_tags"],
                blocked_affordances=[],
            )
            for index, blueprint in enumerate(selected_blueprints)
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
    compiled = unique_preserve(compiled)
    for fallback_tag in ("reveal_truth", "build_trust"):
        if len(compiled) >= 2:
            break
        if fallback_tag not in compiled:
            compiled.append(fallback_tag)
    return compiled[:6]


def event_id_for_beat(index: int, beat: BeatDraftSpec) -> str:
    return f"b{index}.{slugify(beat.milestone_kind or 'milestone')}"

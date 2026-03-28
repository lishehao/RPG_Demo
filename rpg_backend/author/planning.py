from __future__ import annotations

from typing import Any

from rpg_backend.author.contracts import (
    BeatPlanDraft,
    FocusedBrief,
    OverviewCastDraft,
    ProseStyle,
    StoryBranchBudget,
    StoryFlowPlan,
    StoryFrameDraft,
    StoryGenerationControls,
    TonePlan,
)
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis
from rpg_backend.content_language import localized_text

DEFAULT_TARGET_DURATION_MINUTES = 15


def _clean_optional_text(value: str | None, *, limit: int) -> str | None:
    normalized = normalize_whitespace(value or "")
    if not normalized:
        return None
    return trim_ellipsis(normalized, limit)


def generation_controls_from_request(request: Any) -> StoryGenerationControls:
    return StoryGenerationControls(
        target_duration_minutes=getattr(request, "target_duration_minutes", None),
        tone_direction=_clean_optional_text(getattr(request, "tone_direction", None), limit=240),
        tone_focus=getattr(request, "tone_focus", None),
        prose_style=getattr(request, "prose_style", None),
    )


def coerce_generation_controls(value: StoryGenerationControls | dict[str, Any] | None) -> StoryGenerationControls | None:
    if value is None or isinstance(value, StoryGenerationControls):
        return value
    return StoryGenerationControls.model_validate(value)


def generation_controls_equal(left: StoryGenerationControls | None, right: StoryGenerationControls | None) -> bool:
    return (left or StoryGenerationControls()).model_dump(mode="json") == (right or StoryGenerationControls()).model_dump(mode="json")


def resolved_target_duration_minutes(controls: StoryGenerationControls | None) -> int:
    return int((controls.target_duration_minutes if controls is not None else None) or DEFAULT_TARGET_DURATION_MINUTES)


def coerce_story_flow_plan(value: StoryFlowPlan | dict[str, Any] | None) -> StoryFlowPlan | None:
    if value is None or isinstance(value, StoryFlowPlan):
        return value
    return StoryFlowPlan.model_validate(value)


def _target_turn_count(duration_minutes: int) -> int:
    if duration_minutes <= 12:
        return 4
    if duration_minutes <= 16:
        return 6
    if duration_minutes <= 21:
        return 8
    return 10


def _target_beat_count(duration_minutes: int) -> int:
    if duration_minutes <= 12:
        return 2
    if duration_minutes <= 16:
        return 3
    if duration_minutes <= 21:
        return 4
    return 5


def _progress_schedule(target_turn_count: int, target_beat_count: int) -> list[int]:
    schedule = [target_turn_count // target_beat_count] * target_beat_count
    remainder = target_turn_count % target_beat_count
    for index in range(target_beat_count - 1, -1, -1):
        if remainder <= 0:
            break
        schedule[index] += 1
        remainder -= 1
    return [max(1, min(3, value)) for value in schedule]


def _branch_budget(duration_minutes: int) -> StoryBranchBudget:
    if duration_minutes <= 16:
        return "low"
    if duration_minutes <= 21:
        return "medium"
    return "high"


def _route_unlock_budget(branch_budget: StoryBranchBudget) -> int:
    return {"low": 2, "medium": 4, "high": 6}[branch_budget]


def _detour_budget_total(branch_budget: StoryBranchBudget) -> int:
    return {"low": 1, "medium": 2, "high": 3}[branch_budget]


def _minimum_resolution_turn(target_turn_count: int) -> int:
    if target_turn_count <= 4:
        return 3
    if target_turn_count <= 6:
        return 4
    if target_turn_count <= 8:
        return 5
    return 7


def _recommended_cast_count(duration_minutes: int, primary_theme: str | None) -> int:
    if duration_minutes <= 12:
        return 3
    if duration_minutes <= 21:
        return 4
    return 5


def build_story_flow_plan(
    *,
    controls: StoryGenerationControls | None,
    primary_theme: str | None = None,
) -> StoryFlowPlan:
    target_duration_minutes = resolved_target_duration_minutes(controls)
    target_turn_count = _target_turn_count(target_duration_minutes)
    target_beat_count = _target_beat_count(target_duration_minutes)
    branch_budget = _branch_budget(target_duration_minutes)
    return StoryFlowPlan(
        target_duration_minutes=target_duration_minutes,
        target_turn_count=target_turn_count,
        target_beat_count=target_beat_count,
        progress_required_by_beat=_progress_schedule(target_turn_count, target_beat_count),
        branch_budget=branch_budget,
        route_unlock_budget=_route_unlock_budget(branch_budget),
        detour_budget_total=_detour_budget_total(branch_budget),
        recommended_cast_count=_recommended_cast_count(target_duration_minutes, primary_theme),
        minimum_resolution_turn=_minimum_resolution_turn(target_turn_count),
    )


def _focus_guidance(tone_focus: str | None, language: str) -> tuple[str, str, str]:
    mapping = {
        "character": (
            localized_text(language, en="Center personal compromise, private fear, and how public duty lands on specific people.", zh="把个人妥协、私下恐惧，以及公共职责怎么压到具体人物身上写出来。"),
            localized_text(language, en="Show the world through what named people can bear, hide, or justify.", zh="世界怎么压人，要通过角色还能承受什么、会遮住什么、又会替自己辩成什么样子来显出来。"),
            localized_text(language, en="Beat language should foreground personal consequence and emotional leverage.", zh="写节拍时，优先把个人后果和情绪上的拿捏写清楚。"),
        ),
        "relationship": (
            localized_text(language, en="Center alliance strain, loyalty tests, and shifts in trust between people.", zh="把联盟里的拉扯、忠诚测试和信任变化写到台面上。"),
            localized_text(language, en="Let the setting feel shaped by who still trusts whom and what that trust now costs.", zh="世界的紧张感，要落在谁还肯信谁，以及这份信任现在要付出什么代价。"),
            localized_text(language, en="Beat language should foreground negotiations, fractures, and relational cost.", zh="节拍里多写谈判、裂痕和关系代价。"),
        ),
        "institution": (
            localized_text(language, en="Center institutional norms, precedent, authority boundaries, and what systems can still absorb.", zh="把制度惯例、先例、权责边界，以及系统还能吃下多少压力写清楚。"),
            localized_text(language, en="Let the world feel built from procedures, offices, records, and brittle administrative seams.", zh="程序、机构、记录和那些快要绷断的行政接缝，要让读者摸得着。"),
            localized_text(language, en="Beat language should foreground procedure, precedent, and institutional consequence.", zh="节拍里多写程序、先例和制度后果。"),
        ),
        "public_ethics": (
            localized_text(language, en="Center consent, legitimacy, fairness, and what the public is being asked to live with.", zh="核心问题要落在：公众认不认账、公不公平，以及最后该由谁来承受后果。"),
            localized_text(language, en="Let the world feel shaped by public obligation, civic cost, and moral visibility.", zh="世界的压力，要落在公共义务、城市代价和道义上能不能说得过去。"),
            localized_text(language, en="Beat language should foreground legitimacy, visible sacrifice, and civic cost.", zh="节拍里多写公信力、看得见的牺牲和公共代价。"),
        ),
        "procedural": (
            localized_text(language, en="Center verification, sequence, evidence handling, and the discipline of process under pressure.", zh="把核验顺序、证据怎么过手，以及高压下程序还能不能立住写清楚。"),
            localized_text(language, en="Let the world feel built from checkpoints, paper trails, and the cost of procedural slippage.", zh="检查点、文书链和程序一旦失手要付什么代价，都要能让人看见。"),
            localized_text(language, en="Beat language should foreground checkpoints, proof chains, and procedural exposure.", zh="节拍里多写检查点、证明链和程序漏洞怎么露出来。"),
        ),
    }
    return mapping.get(
        tone_focus,
        (
            localized_text(language, en="Keep the tone anchored in named people, concrete institutions, and visible public consequence.", zh="基调要一直落在具体人物、具体制度和看得见的公共后果上。"),
            localized_text(language, en="Keep the world specific, civic, and materially grounded.", zh="世界要具体、要贴着公共生活，也要有摸得着的现实约束。"),
            localized_text(language, en="Keep beat language concrete, scene-facing, and outcome-aware.", zh="节拍文字要具体、贴场景，也别忘了结果会落到谁身上。"),
        ),
    )


def _style_guard_guidance(*, language: str, resolved_tone_signal: str, prose_style: ProseStyle | None) -> str:
    style_suffix = {
        "restrained": localized_text(language, en="Keep the prose restrained, precise, and unsentimental.", zh="文字要克制、利落，不要一激动就往抒情里飘。"),
        "lyrical": localized_text(language, en="Allow the prose to be lyrical, but keep it legible and scene-bound.", zh="可以稍微抒情一点，但句子还是要清楚，镜头还是得落在场景里。"),
        "urgent": localized_text(language, en="Keep the prose urgent, compressed, and pressure-forward.", zh="文字要急、要紧，也要把压力顶在句子前面。"),
    }.get(prose_style, localized_text(language, en="Keep the prose scene-bound and specific.", zh="文字要贴着场景写，也要足够具体。"))
    separator = "。 " if language == "zh" else ". "
    return trim_ellipsis(f"{resolved_tone_signal}{separator}{style_suffix}", 220)


def build_tone_plan(
    *,
    focused_brief: FocusedBrief,
    controls: StoryGenerationControls | None,
) -> TonePlan:
    resolved_controls = controls or StoryGenerationControls()
    resolved_tone_signal = trim_ellipsis(
        _clean_optional_text(resolved_controls.tone_direction, limit=120) or focused_brief.tone_signal,
        120,
    )
    character_guidance, world_guidance, beat_guidance = _focus_guidance(
        resolved_controls.tone_focus,
        focused_brief.language,
    )
    return TonePlan(
        tone_direction=resolved_controls.tone_direction,
        tone_focus=resolved_controls.tone_focus,
        prose_style=resolved_controls.prose_style,
        resolved_tone_signal=resolved_tone_signal,
        style_guard_guidance=_style_guard_guidance(
            language=focused_brief.language,
            resolved_tone_signal=resolved_tone_signal,
            prose_style=resolved_controls.prose_style,
        ),
        character_emphasis_guidance=trim_ellipsis(character_guidance, 220),
        world_texture_guidance=trim_ellipsis(world_guidance, 220),
        beat_language_guidance=trim_ellipsis(beat_guidance, 220),
    )


def coerce_tone_plan(value: TonePlan | dict[str, Any] | None) -> TonePlan | None:
    if value is None or isinstance(value, TonePlan):
        return value
    return TonePlan.model_validate(value)


def has_explicit_tone_controls(controls: StoryGenerationControls | None) -> bool:
    if controls is None:
        return False
    return bool(controls.tone_direction or controls.tone_focus or controls.prose_style)


def apply_tone_plan_to_story_frame(
    story_frame: StoryFrameDraft,
    *,
    controls: StoryGenerationControls | None,
    tone_plan: TonePlan | None,
) -> StoryFrameDraft:
    if tone_plan is None:
        return story_frame
    if not has_explicit_tone_controls(controls):
        return story_frame.model_copy(update={"tone": tone_plan.resolved_tone_signal})
    world_rules = list(story_frame.world_rules)
    if tone_plan.world_texture_guidance not in world_rules:
        if len(world_rules) >= 5:
            world_rules[-1] = tone_plan.world_texture_guidance
        else:
            world_rules.append(tone_plan.world_texture_guidance)
    return story_frame.model_copy(
        update={
            "tone": tone_plan.resolved_tone_signal,
            "style_guard": trim_ellipsis(f"{story_frame.style_guard} {tone_plan.style_guard_guidance}", 220),
            "world_rules": world_rules[:5],
        }
    )


def _tone_suffix(tone_plan: TonePlan, *, kind: str, language: str) -> str:
    focus = tone_plan.tone_focus
    if kind == "agenda":
        mapping = {
            "character": localized_text(language, en="Personal compromise matters as much as policy.", zh="人物自己吞下去的妥协，和政策本身一样重要。"),
            "relationship": localized_text(language, en="Every alliance shift has to stay visible.", zh="每一次关系松动，都得写到能看见。"),
            "institution": localized_text(language, en="Every move now sets precedent inside the institution.", zh="现在的每一步，都会在制度里留下先例。"),
            "public_ethics": localized_text(language, en="The public cost has to remain morally legible.", zh="公共代价得在道义上说得清。"),
            "procedural": localized_text(language, en="The verification path must stay explicit.", zh="核验这条线，不能写虚。"),
        }
    elif kind == "red_line":
        mapping = {
            "character": localized_text(language, en="Will not let the people carrying the burden disappear into abstraction.", zh="不会让真正扛代价的人，被抽象说法吞掉。"),
            "relationship": localized_text(language, en="Will not let convenience erase what this does to trust.", zh="不会让图省事，抹掉这件事对信任造成的伤口。"),
            "institution": localized_text(language, en="Will not let short-term pressure rewrite institutional boundaries in silence.", zh="不会让短期压力在沉默里改写制度边界。"),
            "public_ethics": localized_text(language, en="Will not let legitimacy be purchased by hiding who pays the cost.", zh="不会在遮住“谁来付代价”之后，再去谈什么正当性。"),
            "procedural": localized_text(language, en="Will not let haste sever the chain of proof.", zh="不会让急迫把证明链拦腰切断。"),
        }
    else:
        mapping = {
            "character": localized_text(language, en="Reads pressure through what specific people can still carry.", zh="会从具体人物还能扛住什么里感知压力。"),
            "relationship": localized_text(language, en="Tracks pressure through who still trusts whom.", zh="会从谁还肯信谁里判断压力有多大。"),
            "institution": localized_text(language, en="Feels pressure as institutional strain and precedent risk.", zh="会把压力感成制度拉扯和先例风险。"),
            "public_ethics": localized_text(language, en="Feels pressure as a public legitimacy debt that keeps compounding.", zh="会把压力感成一笔越滚越大的公信债。"),
            "procedural": localized_text(language, en="Feels pressure through broken sequence, missing signatures, and exposed gaps.", zh="会从顺序断裂、签名缺失和程序漏洞里感到压力。"),
        }
    return mapping.get(focus, "")


def apply_tone_plan_to_cast_member(
    member: OverviewCastDraft,
    *,
    controls: StoryGenerationControls | None,
    tone_plan: TonePlan | None,
    language: str,
) -> OverviewCastDraft:
    if tone_plan is None or not has_explicit_tone_controls(controls):
        return member
    return member.model_copy(
        update={
            "agenda": trim_ellipsis(f"{member.agenda} {_tone_suffix(tone_plan, kind='agenda', language=language)}", 220),
            "red_line": trim_ellipsis(f"{member.red_line} {_tone_suffix(tone_plan, kind='red_line', language=language)}", 220),
            "pressure_signature": trim_ellipsis(f"{member.pressure_signature} {_tone_suffix(tone_plan, kind='pressure', language=language)}", 220),
        }
    )


def apply_tone_plan_to_beat_plan(
    beat_plan: BeatPlanDraft,
    *,
    controls: StoryGenerationControls | None,
    tone_plan: TonePlan | None,
    language: str,
) -> BeatPlanDraft:
    if tone_plan is None or not has_explicit_tone_controls(controls):
        return beat_plan
    suffix = {
        "character": localized_text(language, en="Make the personal cost explicit.", zh="把个人代价写明白。"),
        "relationship": localized_text(language, en="Make the alliance strain explicit.", zh="把联盟拉扯写到台面上。"),
        "institution": localized_text(language, en="Make the institutional consequence explicit.", zh="把制度后果写实。"),
        "public_ethics": localized_text(language, en="Make the legitimacy cost explicit.", zh="把公信代价点明。"),
        "procedural": localized_text(language, en="Keep the proof chain visible.", zh="把证明链写清楚。"),
    }.get(tone_plan.tone_focus, tone_plan.beat_language_guidance)
    return BeatPlanDraft(
        beats=[
            beat.model_copy(
                update={
                    "goal": trim_ellipsis(f"{beat.goal} {suffix}", 220),
                    "return_hooks": [trim_ellipsis(f"{hook} {tone_plan.beat_language_guidance}", 180) for hook in beat.return_hooks[:3]],
                }
            )
            for beat in beat_plan.beats
        ]
    )


def ending_summary_for_tone(
    *,
    ending_id: str,
    language: str,
    tone_plan: TonePlan | None,
) -> str | None:
    if tone_plan is None or tone_plan.tone_focus is None:
        return None
    mapping = {
        "character": {
            "mixed": localized_text(language, en="The city holds, but the people carrying it are visibly changed.", zh="城市算是保住了，可真正扛着它的人已经被这场事改得面目全非。"),
            "pyrrhic": localized_text(language, en="Success arrives only after the people holding the line are badly spent.", zh="局面是稳住了，可顶在最前面的人也被这场事硬生生耗空了。"),
            "collapse": localized_text(language, en="The people who might have held the city together are pushed past what they can carry.", zh="那些原本还能把城市拢住的人，被一路逼过了自己能扛的极限。"),
        },
        "relationship": {
            "mixed": localized_text(language, en="The city survives, but trust remains thinner than the settlement suggests.", zh="城市活下来了，可人和人之间那点信任，比这份结算看上去要薄得多。"),
            "pyrrhic": localized_text(language, en="Success arrives only through damaged alliances and unrepaired trust.", zh="局面是稳住了，可联盟已经伤了筋骨，信任也根本没补回来。"),
            "collapse": localized_text(language, en="The coalition fails faster than the city can absorb the fracture.", zh="联盟散掉的速度，比城市来得及消化裂痕还要快。"),
        },
        "institution": {
            "mixed": localized_text(language, en="The system still stands, but the institution keeps the scar.", zh="系统还站着，可制度本身已经被这场事划出了口子。"),
            "pyrrhic": localized_text(language, en="Success arrives only after the institution spends credibility it may not recover.", zh="局面是保住了，可制度也把未必补得回来的公信力先烧掉了。"),
            "collapse": localized_text(language, en="Institutional order fails before the record can hold.", zh="制度秩序先一步失手，连记录也没能守住。"),
        },
        "public_ethics": {
            "mixed": localized_text(language, en="The city survives, but the public cost remains morally unsettled.", zh="城市活下来了，可这笔公共代价在道义上还是没人真正讲得过去。"),
            "pyrrhic": localized_text(language, en="Success arrives only by asking the public to live with a visible moral debt.", zh="局面是稳住了，可公众也被迫继续背着一笔人人看得见的道义欠账。"),
            "collapse": localized_text(language, en="The public burden becomes impossible to justify, and the city breaks with it.", zh="公共负担已经重到没法再自圆其说，城市也跟着一起裂开。"),
        },
        "procedural": {
            "mixed": localized_text(language, en="The city survives, and the process barely holds together.", zh="城市活下来了，程序也只是勉强没彻底散架。"),
            "pyrrhic": localized_text(language, en="Success arrives only after the proof chain is strained to its edge.", zh="局面是稳住了，可证明链也已经被一路扯到了断边。"),
            "collapse": localized_text(language, en="The process breaks before the city can prove what it is doing.", zh="程序先一步断开，城市还没来得及证明自己到底在做什么。"),
        },
    }
    return mapping.get(tone_plan.tone_focus, {}).get(ending_id)

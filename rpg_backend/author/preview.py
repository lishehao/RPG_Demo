from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from rpg_backend.author.compiler.beats import build_default_beat_plan_draft
from rpg_backend.author.compiler.brief import focus_brief
from rpg_backend.author.compiler.cast import build_cast_draft_from_overview, derive_cast_overview_draft, plan_cast_topology
from rpg_backend.author.planning import (
    build_story_flow_plan,
    build_tone_plan,
    coerce_generation_controls,
    coerce_story_flow_plan,
    coerce_tone_plan,
)
from rpg_backend.author.compiler.router import plan_brief_theme
from rpg_backend.story_profiles import author_theme_from_bundle
from rpg_backend.author.compiler.story import build_default_story_frame_draft, sanitize_story_sentence
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis
from rpg_backend.author.contracts import (
    AuthorPreviewBeatSummary,
    AuthorPreviewCastSlotSummary,
    AuthorPreviewResponse,
    AuthorPreviewStory,
    AuthorPreviewStrategies,
    AuthorPreviewStructure,
    AuthorPreviewTheme,
    AuthorStorySummary,
    DesignBundle,
    StoryGenerationControls,
)
from rpg_backend.content_language import localized_text
from rpg_backend.author.display import build_preview_flashcards, theme_label
from rpg_backend.product_text import (
    build_product_premise_fallback,
    sanitize_product_one_liner,
    sanitize_product_story_sentence,
)

_GENERIC_ZH_TITLES = {
    "公议协约",
    "城市协约",
    "公共协约",
    "紧急议会",
    "最终结算",
}


_PREVIEW_TONE_BY_THEME = {
    "legitimacy_crisis": ("Tense civic thriller", "公议惊悚"),
    "logistics_quarantine_crisis": ("Tense bureaucratic thriller", "封线政治惊悚"),
    "truth_record_crisis": ("Procedural suspense", "档案程序悬疑"),
    "public_order_crisis": ("Urgent civic suspense", "高压失序悬疑"),
    "generic_civic_crisis": ("Tense civic drama", "城市压力剧"),
}

_PREVIEW_ROLE_PATTERN = re.compile(
    r"^(?P<subject>(?:a|an|the)\s+(?:[a-z0-9-]+\s+){0,5}"
    r"(?:mediator|envoy|engineer|inspector|archivist|keeper|priest|councilor|guard|messenger|scholar|mayor|agent|negotiator|"
    r"auditor|superintendent|liaison|ombudsman|clerk|marshal|officer|delegate|steward))\s+"
    r"(?P<verb>discovers|finds|uncovers|learns|realizes|spots|proves|reveals|exposes)\s+"
    r"(?P<rest>.+)$",
    flags=re.IGNORECASE,
)


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = {token for token in re.findall(r"[a-z0-9']+", left.casefold()) if len(token) >= 3}
    right_tokens = {token for token in re.findall(r"[a-z0-9']+", right.casefold()) if len(token) >= 3}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(right_tokens), 1)


def _looks_like_seed_echo(candidate: str, prompt_seed: str) -> bool:
    normalized_candidate = normalize_whitespace(candidate)
    normalized_seed = normalize_whitespace(prompt_seed)
    if not normalized_candidate or not normalized_seed:
        return False
    if normalized_seed.casefold() in normalized_candidate.casefold():
        return True
    return _token_overlap_ratio(normalized_candidate, normalized_seed) >= 0.72


def _preview_setting_frame(*, primary_theme: str, prompt_seed: str, focused_brief) -> str:
    lowered = f"{prompt_seed} {focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if primary_theme == "logistics_quarantine_crisis":
        if any(keyword in lowered for keyword in ("bridge", "flood", "ration", "ward", "district", "convoy", "infrastructure")):
            return "a city under ration strain and infrastructure pressure"
        if any(keyword in lowered for keyword in ("harbor", "port", "quarantine", "dock", "shipping")):
            return "a harbor city strained by quarantine politics and supply fear"
        return "a city where scarcity and emergency logistics keep turning relief into leverage"
    if primary_theme == "truth_record_crisis":
        return "a civic archive where public trust depends on records that can still be falsified"
    if primary_theme == "public_order_crisis":
        return "a city under blackout strain and escalating public panic"
    if primary_theme == "legitimacy_crisis":
        return "a civic system where emergency authority is starting to outrun public legitimacy"
    return normalize_whitespace(focused_brief.setting_signal)


def _preview_mandate(*, prompt_seed: str, focused_brief) -> str:
    normalized_kernel = normalize_whitespace(focused_brief.story_kernel or prompt_seed)
    match = _PREVIEW_ROLE_PATTERN.match(normalized_kernel)
    if match:
        subject = normalize_whitespace(match.group("subject"))
        verb = match.group("verb").casefold()
        rest = normalize_whitespace(match.group("rest")).rstrip(".")
        if rest:
            if verb in {"discovers", "finds", "uncovers", "learns", "realizes", "spots"}:
                connector = "must prove" if rest.casefold().startswith("that ") else "must prove that"
            elif verb == "proves":
                connector = "must prove"
            else:
                connector = "must force into the open" if rest.casefold().startswith("that ") else "must force into the open that"
            return trim_ellipsis(f"{subject} {connector} {rest}".strip(), 220)
    lowered = normalized_kernel.casefold()
    if "archivist" in lowered or "clerk" in lowered or "auditor" in lowered:
        return "an archivist must verify one binding public record before the official story hardens"
    if "superintendent" in lowered or "engineer" in lowered:
        return "a superintendent must expose the staged logistics failure before emergency rule hardens into habit"
    if "inspector" in lowered or "officer" in lowered:
        return "an inspector must expose the hidden breach before emergency authority becomes private leverage"
    if "mediator" in lowered or "liaison" in lowered or "ombudsman" in lowered:
        return "a mediator must hold rival institutions in one room long enough to force a binding answer"
    return trim_ellipsis(normalized_kernel, 220)


def _preview_opposition_force(*, primary_theme: str, prompt_seed: str, focused_brief) -> str:
    lowered = f"{prompt_seed} {focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if primary_theme == "logistics_quarantine_crisis":
        if any(keyword in lowered for keyword in ("bridge", "flood", "ration", "ward", "district", "convoy", "infrastructure")):
            return localized_text(focused_brief.language, en="scarcity politics and emergency command keep turning logistics into political leverage", zh="短缺政治与紧急指挥，正在把物流调度改写成权力筹码。")
        return localized_text(focused_brief.language, en="trade pressure and quarantine politics keep turning relief into factional leverage", zh="贸易压力与检疫政治，正在把救济安排改写成派系筹码。")
    if primary_theme == "truth_record_crisis":
        return localized_text(focused_brief.language, en="forged records and procedural denial keep reshaping the public story", zh="伪造记录和程序性否认，正在改写公众最后会相信哪一版说法。")
    if primary_theme == "public_order_crisis":
        return localized_text(focused_brief.language, en="panic, rumor, and emergency messaging keep pushing the city toward open disorder", zh="恐慌、流言和紧急广播，正把整座城市往公开失序上推。")
    if primary_theme == "legitimacy_crisis":
        return localized_text(focused_brief.language, en="institutional panic and mandate politics turn every delay into leverage", zh="机构恐慌和授权博弈，会把每一次拖延都炒成新的筹码。")
    return localized_text(focused_brief.language, en="public pressure keeps turning delay into civic fracture", zh="公众压力会把每一次拖延都推成新的裂口。")


def _preview_tone(*, prompt_seed: str, primary_theme: str, focused_brief, tone_plan=None) -> str:
    if tone_plan is not None:
        return trim_ellipsis(tone_plan.resolved_tone_signal, 120)
    candidate = normalize_whitespace(focused_brief.tone_signal)
    if not candidate or _looks_like_seed_echo(candidate, prompt_seed) or len(candidate.split()) > 8:
        tone_pair = _PREVIEW_TONE_BY_THEME.get(primary_theme, ("Tense civic drama", "城市压力剧"))
        return localized_text(focused_brief.language, en=tone_pair[0], zh=tone_pair[1])
    return trim_ellipsis(candidate, 120)


def build_author_preview_from_seed(prompt_seed: str, *, language: str = "en") -> AuthorPreviewResponse:
    # Deterministic fallback for tests and offline fixtures only.
    # Product preview traffic goes through AuthorJobService._run_preview_workflow()
    # and build_author_preview_from_state() so preview data always comes from the
    # real author checkpoint state rather than a parallel preview-only path.
    focused_brief = focus_brief(prompt_seed, language=language)
    brief_theme = plan_brief_theme(focused_brief)
    generation_controls = StoryGenerationControls()
    story_flow_plan = build_story_flow_plan(
        controls=generation_controls,
        primary_theme=brief_theme.primary_theme,
    )
    tone_plan = build_tone_plan(
        focused_brief=focused_brief,
        controls=generation_controls,
    )
    preview_story = build_default_story_frame_draft(focused_brief)
    preview_premise = preview_story.premise
    if _looks_like_seed_echo(preview_premise, prompt_seed):
        preview_premise = build_product_premise_fallback(
            primary_theme=brief_theme.primary_theme,
            focused_brief=focused_brief,
            prompt_seed=prompt_seed,
            limit=320,
        )
    preview_premise = sanitize_product_story_sentence(
        preview_premise,
        fallback=build_product_premise_fallback(
            primary_theme=brief_theme.primary_theme,
            focused_brief=focused_brief,
            prompt_seed=prompt_seed,
            limit=320,
        ),
        limit=320,
        echo_reference=prompt_seed,
    )
    preview_tone = _preview_tone(
        prompt_seed=prompt_seed,
        primary_theme=brief_theme.primary_theme,
        focused_brief=focused_brief,
        tone_plan=tone_plan,
    )
    topology = plan_cast_topology(
        focused_brief,
        preview_story,
        preferred_count=story_flow_plan.recommended_cast_count,
    )
    cast_overview = derive_cast_overview_draft(
        focused_brief,
        preview_story,
        topology_override=topology.topology,
    )
    cast_draft = build_cast_draft_from_overview(cast_overview, focused_brief)
    beat_plan = build_default_beat_plan_draft(
        focused_brief,
        story_frame=preview_story,
        cast_draft=cast_draft,
        story_flow_plan=story_flow_plan,
        tone_plan=tone_plan,
    )
    expected_npc_count = len(cast_overview.cast_slots)
    expected_beat_count = len(beat_plan.beats)
    return AuthorPreviewResponse(
        preview_id=str(uuid4()),
        prompt_seed=prompt_seed,
        language=focused_brief.language,
        generation_controls=generation_controls,
        story_flow_plan=story_flow_plan,
        resolved_tone_plan=tone_plan,
        focused_brief=focused_brief,
        theme=AuthorPreviewTheme(
            primary_theme=brief_theme.primary_theme,
            modifiers=list(brief_theme.modifiers),
            router_reason=brief_theme.router_reason,
        ),
        strategies=AuthorPreviewStrategies(
            story_frame_strategy=brief_theme.story_frame_strategy,
            cast_strategy=brief_theme.cast_strategy,
            beat_plan_strategy=brief_theme.beat_plan_strategy,
        ),
        structure=AuthorPreviewStructure(
            cast_topology=topology.topology,
            expected_npc_count=expected_npc_count,
            expected_beat_count=expected_beat_count,
            target_duration_minutes=story_flow_plan.target_duration_minutes,
            expected_turn_count=story_flow_plan.target_turn_count,
            branch_budget=story_flow_plan.branch_budget,
        ),
        story=AuthorPreviewStory(
            title=preview_story.title,
            premise=preview_premise,
            tone=preview_tone,
            stakes=preview_story.stakes,
        ),
        cast_slots=[
            AuthorPreviewCastSlotSummary(
                slot_label=item.slot_label,
                public_role=item.public_role,
            )
            for item in cast_overview.cast_slots
        ],
        beats=[
            AuthorPreviewBeatSummary(
                title=item.title,
                goal=item.goal,
                milestone_kind=item.milestone_kind,
            )
            for item in beat_plan.beats
        ],
        flashcards=build_preview_flashcards(
            language=focused_brief.language,
            theme=brief_theme.primary_theme,
            tone=preview_tone,
            cast_topology=topology.topology,
            expected_npc_count=expected_npc_count,
            expected_beat_count=expected_beat_count,
            title=preview_story.title,
            conflict=_preview_opposition_force(
                primary_theme=brief_theme.primary_theme,
                prompt_seed=prompt_seed,
                focused_brief=focused_brief,
            ),
        ),
        stage="brief_parsed",
    )


def _preview_cast_slots_from_members(cast_members: list[object]) -> list[AuthorPreviewCastSlotSummary]:
    return [
        AuthorPreviewCastSlotSummary(
            slot_label=str(getattr(member, "name", "") or ""),
            public_role=str(getattr(member, "role", "") or ""),
            npc_id=getattr(member, "npc_id", None),
            name=str(getattr(member, "name", "") or ""),
            roster_character_id=getattr(member, "roster_character_id", None),
            roster_public_summary=getattr(member, "roster_public_summary", None),
            portrait_url=getattr(member, "portrait_url", None),
            portrait_variants=getattr(member, "portrait_variants", None),
            template_version=getattr(member, "template_version", None),
        )
        for member in cast_members[:5]
    ]


def _state_preview_stage(state: dict[str, Any]) -> str:
    if state.get("design_bundle") is not None:
        return "completed"
    if state.get("ending_rules_draft") is not None:
        return "ending_ready"
    if state.get("route_affordance_pack_draft") is not None:
        return "route_ready"
    if state.get("beat_plan_draft") is not None:
        return "beat_plan_ready"
    if state.get("cast_draft") is not None:
        return "cast_ready"
    if state.get("cast_overview_draft") is not None:
        return "cast_planned"
    if state.get("theme_router_reason") is not None or state.get("primary_theme") is not None:
        return "theme_confirmed"
    if state.get("story_frame_draft") is not None:
        return "story_frame_ready"
    if state.get("brief_primary_theme") is not None:
        return "brief_classified"
    if state.get("focused_brief") is not None:
        return "brief_parsed"
    return "queued"


def _state_expected_beat_count(state: dict[str, Any], existing_preview: AuthorPreviewResponse | None) -> int:
    beat_plan = state.get("beat_plan_draft")
    if beat_plan is not None and getattr(beat_plan, "beats", None):
        return len(beat_plan.beats)
    story_flow_plan = state.get("story_flow_plan")
    if story_flow_plan is not None:
        if hasattr(story_flow_plan, "target_beat_count"):
            return max(int(story_flow_plan.target_beat_count), 1)
        if isinstance(story_flow_plan, dict) and story_flow_plan.get("target_beat_count"):
            return max(int(story_flow_plan["target_beat_count"]), 1)
    if existing_preview is not None:
        return max(int(existing_preview.structure.expected_beat_count), 1)
    return 3


def build_author_preview_from_state(
    *,
    preview_id: str,
    prompt_seed: str,
    state: dict[str, Any],
    existing_preview: AuthorPreviewResponse | None = None,
) -> AuthorPreviewResponse:
    preview_language = (
        str(state.get("language") or "")
        or (existing_preview.language if existing_preview is not None else "en")
    )
    focused_brief = state.get("focused_brief") or (
        existing_preview.focused_brief if existing_preview is not None else focus_brief(prompt_seed, language=preview_language)
    )
    primary_theme = (
        state.get("primary_theme")
        or state.get("brief_primary_theme")
        or (existing_preview.theme.primary_theme if existing_preview is not None else plan_brief_theme(focused_brief).primary_theme)
    )
    generation_controls = coerce_generation_controls(state.get("generation_controls")) or (
        existing_preview.generation_controls if existing_preview is not None else StoryGenerationControls()
    )
    story_flow_plan = coerce_story_flow_plan(state.get("story_flow_plan")) or (
        existing_preview.story_flow_plan
        if existing_preview is not None
        else build_story_flow_plan(
            controls=generation_controls,
            primary_theme=primary_theme,
        )
    )
    tone_plan = coerce_tone_plan(state.get("resolved_tone_plan")) or (
        existing_preview.resolved_tone_plan
        if existing_preview is not None
        else build_tone_plan(
            focused_brief=focused_brief,
            controls=generation_controls,
        )
    )
    theme_modifiers = list(
        state.get("theme_modifiers")
        or state.get("brief_theme_modifiers")
        or (existing_preview.theme.modifiers if existing_preview is not None else [])
    )
    theme_router_reason = str(
        state.get("theme_router_reason")
        or state.get("brief_theme_router_reason")
        or (existing_preview.theme.router_reason if existing_preview is not None else "preview_state")
    )
    story_frame = state.get("story_frame_draft") or (
        existing_preview.story if existing_preview is not None else build_default_story_frame_draft(focused_brief)
    )
    if isinstance(story_frame, AuthorPreviewStory):
        story = story_frame
    else:
        story = AuthorPreviewStory(
            title=getattr(story_frame, "title", existing_preview.story.title if existing_preview is not None else "Untitled Preview"),
            premise=getattr(story_frame, "premise", existing_preview.story.premise if existing_preview is not None else prompt_seed),
            tone=getattr(story_frame, "tone", existing_preview.story.tone if existing_preview is not None else "Tense civic drama"),
            stakes=getattr(
                story_frame,
                "stakes",
                existing_preview.story.stakes if existing_preview is not None else "If the crisis is mishandled, civic order and public trust can fail at the same time.",
            ),
        )
    cast_overview = state.get("cast_overview_draft")
    state_cast_draft = state.get("cast_draft")
    concrete_cast_members = list(getattr(state_cast_draft, "cast", []) or [])
    cast_slots = (
        _preview_cast_slots_from_members(concrete_cast_members)
        if concrete_cast_members
        else [
            AuthorPreviewCastSlotSummary(
                slot_label=item.slot_label,
                public_role=item.public_role,
            )
            for item in getattr(cast_overview, "cast_slots", [])[:5]
        ]
    )
    if not cast_slots and existing_preview is not None:
        cast_slots = list(existing_preview.cast_slots)
    cast_draft = state_cast_draft
    if cast_draft is None and cast_overview is not None:
        try:
            cast_draft = build_cast_draft_from_overview(cast_overview, focused_brief)
        except Exception:
            cast_draft = None
    expected_npc_count = len(getattr(cast_draft, "cast", []) or cast_slots or (existing_preview.cast_slots if existing_preview is not None else []))
    expected_npc_count = max(expected_npc_count, existing_preview.structure.expected_npc_count if existing_preview is not None else 1)
    beat_plan = state.get("beat_plan_draft")
    if beat_plan is None and cast_draft is not None and not existing_preview:
        try:
            beat_plan = build_default_beat_plan_draft(
                focused_brief,
                story_frame=story_frame,
                cast_draft=cast_draft,
                story_flow_plan=story_flow_plan,
                tone_plan=tone_plan,
            )
        except Exception:
            beat_plan = None
    beat_summaries = [
        AuthorPreviewBeatSummary(
            title=item.title,
            goal=item.goal,
            milestone_kind=item.milestone_kind,
        )
        for item in getattr(beat_plan, "beats", [])[:5]
    ]
    if not beat_summaries and existing_preview is not None:
        beat_summaries = list(existing_preview.beats)
    cast_topology = str(
        state.get("cast_topology")
        or (
            existing_preview.structure.cast_topology
            if existing_preview is not None
            else "five_slot"
            if story_flow_plan.recommended_cast_count >= 5
            else "four_slot"
        )
    )
    expected_beat_count = _state_expected_beat_count(state, existing_preview)
    tone = _preview_tone(
        prompt_seed=prompt_seed,
        primary_theme=primary_theme,
        focused_brief=focused_brief,
        tone_plan=tone_plan,
    )
    if not story.tone or _looks_like_seed_echo(story.tone, prompt_seed):
        story = story.model_copy(update={"tone": tone})
    fallback_story = build_default_story_frame_draft(focused_brief)
    fallback_premise = build_product_premise_fallback(
        primary_theme=primary_theme,
        focused_brief=focused_brief,
        prompt_seed=prompt_seed,
        limit=320,
    )
    story = story.model_copy(
        update={
            "title": (
                fallback_story.title
                if focused_brief.language == "zh" and normalize_whitespace(story.title) in _GENERIC_ZH_TITLES
                else story.title
            ),
            "premise": sanitize_product_story_sentence(
                story.premise,
                fallback=fallback_premise or fallback_story.premise,
                limit=320,
                echo_reference=prompt_seed,
            ),
            "stakes": sanitize_story_sentence(
                story.stakes,
                fallback=fallback_story.stakes,
                limit=240,
            ),
        }
    )
    return AuthorPreviewResponse(
        preview_id=preview_id,
        prompt_seed=prompt_seed,
        language=focused_brief.language,
        generation_controls=generation_controls,
        story_flow_plan=story_flow_plan,
        resolved_tone_plan=tone_plan,
        focused_brief=focused_brief,
        theme=AuthorPreviewTheme(
            primary_theme=primary_theme,
            modifiers=theme_modifiers[:8],
            router_reason=theme_router_reason,
        ),
        strategies=AuthorPreviewStrategies(
            story_frame_strategy=str(state.get("story_frame_strategy") or (existing_preview.strategies.story_frame_strategy if existing_preview is not None else "generic_civic_story")),
            cast_strategy=str(state.get("cast_strategy") or (existing_preview.strategies.cast_strategy if existing_preview is not None else "generic_civic_cast")),
            beat_plan_strategy=str(state.get("beat_plan_strategy") or (existing_preview.strategies.beat_plan_strategy if existing_preview is not None else "conservative_direct_draft")),
        ),
        structure=AuthorPreviewStructure(
            cast_topology=cast_topology,
            expected_npc_count=expected_npc_count,
            expected_beat_count=expected_beat_count,
            target_duration_minutes=story_flow_plan.target_duration_minutes,
            expected_turn_count=story_flow_plan.target_turn_count,
            branch_budget=story_flow_plan.branch_budget,
        ),
        story=story,
        cast_slots=cast_slots[:5],
        beats=beat_summaries[:5],
        flashcards=build_preview_flashcards(
            language=focused_brief.language,
            theme=primary_theme,
            tone=story.tone,
            cast_topology=cast_topology,
            expected_npc_count=expected_npc_count,
            expected_beat_count=expected_beat_count,
            title=story.title,
            conflict=_preview_opposition_force(
                primary_theme=primary_theme,
                prompt_seed=prompt_seed,
                focused_brief=focused_brief,
            ),
        ),
        stage=_state_preview_stage(state),
    )
def build_author_story_summary(bundle: DesignBundle, *, primary_theme: str) -> AuthorStorySummary:
    fallback_story = build_default_story_frame_draft(bundle.focused_brief)
    fallback_premise = build_product_premise_fallback(
        primary_theme=primary_theme,
        focused_brief=bundle.focused_brief,
        prompt_seed=bundle.focused_brief.story_kernel,
        limit=320,
    )
    premise = sanitize_product_story_sentence(
        bundle.story_bible.premise,
        fallback=fallback_premise or fallback_story.premise,
        limit=320,
    )
    one_liner = sanitize_product_one_liner(
        premise=premise,
        title=bundle.story_bible.title,
        limit=220,
    )
    return AuthorStorySummary(
        language=bundle.focused_brief.language,
        title=(
            fallback_story.title
            if bundle.focused_brief.language == "zh" and normalize_whitespace(bundle.story_bible.title) in _GENERIC_ZH_TITLES
            else bundle.story_bible.title
        ),
        one_liner=one_liner,
        premise=premise,
        tone=bundle.story_bible.tone,
        theme=theme_label(primary_theme, language=bundle.focused_brief.language),
        npc_count=len(bundle.story_bible.cast),
        beat_count=len(bundle.beat_spine),
        target_duration_minutes=(
            bundle.story_flow_plan.target_duration_minutes
            if bundle.story_flow_plan is not None
            else None
        ),
    )


def build_author_preview_from_bundle(
    *,
    preview_id: str,
    prompt_seed: str,
    bundle: DesignBundle,
) -> AuthorPreviewResponse:
    theme_decision = author_theme_from_bundle(bundle)
    cast_topology = "five_slot" if len(bundle.story_bible.cast) >= 5 else "four_slot" if len(bundle.story_bible.cast) >= 4 else "three_slot"
    story_flow_plan = bundle.story_flow_plan or build_story_flow_plan(
        controls=bundle.generation_controls,
        primary_theme=theme_decision.primary_theme,
    )
    tone_plan = bundle.resolved_tone_plan or build_tone_plan(
        focused_brief=bundle.focused_brief,
        controls=bundle.generation_controls,
    )
    return AuthorPreviewResponse(
        preview_id=preview_id,
        prompt_seed=prompt_seed,
        language=bundle.focused_brief.language,
        generation_controls=bundle.generation_controls,
        story_flow_plan=story_flow_plan,
        resolved_tone_plan=tone_plan,
        focused_brief=bundle.focused_brief,
        theme=AuthorPreviewTheme(
            primary_theme=theme_decision.primary_theme,
            modifiers=list(theme_decision.modifiers),
            router_reason=theme_decision.router_reason,
        ),
        strategies=AuthorPreviewStrategies(
            story_frame_strategy=theme_decision.story_frame_strategy,
            cast_strategy=theme_decision.cast_strategy,
            beat_plan_strategy=theme_decision.beat_plan_strategy,
        ),
        structure=AuthorPreviewStructure(
            cast_topology=cast_topology,
            expected_npc_count=len(bundle.story_bible.cast),
            expected_beat_count=len(bundle.beat_spine),
            target_duration_minutes=story_flow_plan.target_duration_minutes,
            expected_turn_count=story_flow_plan.target_turn_count,
            branch_budget=story_flow_plan.branch_budget,
        ),
        story=AuthorPreviewStory(
            title=bundle.story_bible.title,
            premise=bundle.story_bible.premise,
            tone=bundle.story_bible.tone,
            stakes=bundle.story_bible.stakes,
        ),
        cast_slots=_preview_cast_slots_from_members(list(bundle.story_bible.cast)),
        beats=[
            AuthorPreviewBeatSummary(
                title=beat.title,
                goal=beat.goal,
                milestone_kind=beat.milestone_kind,
            )
            for beat in bundle.beat_spine
        ],
        flashcards=build_preview_flashcards(
            language=bundle.focused_brief.language,
            theme=theme_decision.primary_theme,
            tone=bundle.story_bible.tone,
            cast_topology=cast_topology,
            expected_npc_count=len(bundle.story_bible.cast),
            expected_beat_count=len(bundle.beat_spine),
            title=bundle.story_bible.title,
            conflict=bundle.story_bible.stakes,
        ),
        stage="completed",
    )

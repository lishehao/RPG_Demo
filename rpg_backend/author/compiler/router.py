from __future__ import annotations

from dataclasses import dataclass

from rpg_backend.author.contracts import DesignBundle, FocusedBrief, StoryFrameDraft


@dataclass(frozen=True)
class StoryThemeDecision:
    primary_theme: str
    modifiers: tuple[str, ...]
    router_reason: str
    story_frame_strategy: str
    cast_strategy: str
    beat_plan_strategy: str


def _theme_haystack_from_brief(focused_brief: FocusedBrief) -> str:
    return " ".join(
        [
            focused_brief.story_kernel,
            focused_brief.setting_signal,
            focused_brief.core_conflict,
            focused_brief.tone_signal,
            *focused_brief.hard_constraints,
        ]
    ).casefold()


def _classify_theme(haystack: str, *, router_reason_prefix: str) -> StoryThemeDecision:
    modifiers = _modifier_hits(haystack)
    if any(keyword in haystack for keyword in ("harbor", "port", "trade", "quarantine", "supply", "blockade")):
        return StoryThemeDecision(
            primary_theme="logistics_quarantine_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_logistics_quarantine_keywords",
            story_frame_strategy="logistics_story",
            cast_strategy="logistics_cast",
            beat_plan_strategy="single_semantic_compile",
        )
    if any(keyword in haystack for keyword in ("archive", "ledger", "record", "witness", "testimony", "evidence")):
        return StoryThemeDecision(
            primary_theme="truth_record_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_truth_record_keywords",
            story_frame_strategy="truth_record_story",
            cast_strategy="truth_record_cast",
            beat_plan_strategy="single_semantic_compile",
        )
    if any(keyword in haystack for keyword in ("succession", "election", "vote", "council", "coalition", "legitimacy", "settlement", "throne", "mandate")):
        return StoryThemeDecision(
            primary_theme="legitimacy_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_legitimacy_keywords",
            story_frame_strategy="legitimacy_story",
            cast_strategy="legitimacy_cast",
            beat_plan_strategy="conservative_direct_draft",
        )
    if any(keyword in haystack for keyword in ("blackout", "panic", "riot", "evacuation", "curfew", "breakdown", "martial law")):
        return StoryThemeDecision(
            primary_theme="public_order_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_public_order_keywords",
            story_frame_strategy="public_order_story",
            cast_strategy="public_order_cast",
            beat_plan_strategy="conservative_direct_draft",
        )
    return StoryThemeDecision(
        primary_theme="generic_civic_crisis",
        modifiers=modifiers,
        router_reason=f"{router_reason_prefix}_generic_civic_crisis",
        story_frame_strategy="generic_civic_story",
        cast_strategy="generic_civic_cast",
        beat_plan_strategy="conservative_direct_draft",
    )


def plan_brief_theme(
    focused_brief: FocusedBrief,
) -> StoryThemeDecision:
    return _classify_theme(
        _theme_haystack_from_brief(focused_brief),
        router_reason_prefix="matched_brief",
    )


def _modifier_hits(haystack: str) -> tuple[str, ...]:
    modifiers: list[str] = []
    if any(keyword in haystack for keyword in ("blackout", "outage", "dimmed", "darkness")):
        modifiers.append("blackout")
    if any(keyword in haystack for keyword in ("harbor", "port", "dock", "shipping")):
        modifiers.append("harbor")
    if any(keyword in haystack for keyword in ("archive", "ledger", "record", "witness", "testimony", "evidence")):
        modifiers.append("archive")
    if any(keyword in haystack for keyword in ("quarantine", "cordon", "blockade")):
        modifiers.append("quarantine")
    if any(keyword in haystack for keyword in ("election", "succession", "vote", "mandate")):
        modifiers.append("election")
    if any(keyword in haystack for keyword in ("panic", "riot", "curfew", "evacuation", "martial law")):
        modifiers.append("public_panic")
    return tuple(modifiers)


def plan_story_theme(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
) -> StoryThemeDecision:
    haystack = " ".join(
        [
            focused_brief.story_kernel,
            focused_brief.setting_signal,
            focused_brief.core_conflict,
            story_frame.title,
            story_frame.premise,
            story_frame.stakes,
            *story_frame.world_rules,
        ]
    ).casefold()
    return _classify_theme(
        haystack,
        router_reason_prefix="matched_story",
    )


def plan_bundle_theme(
    bundle: DesignBundle,
) -> StoryThemeDecision:
    haystack = " ".join(
        [
            bundle.focused_brief.story_kernel,
            bundle.focused_brief.setting_signal,
            bundle.focused_brief.core_conflict,
            bundle.story_bible.title,
            bundle.story_bible.premise,
            bundle.story_bible.stakes,
            *bundle.story_bible.world_rules,
            *(item.text for item in bundle.story_bible.truth_catalog),
        ]
    ).casefold()
    return _classify_theme(
        haystack,
        router_reason_prefix="matched_bundle",
    )

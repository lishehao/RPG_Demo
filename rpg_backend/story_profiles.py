from __future__ import annotations

from dataclasses import dataclass
import re

from rpg_backend.author.contracts import DesignBundle, FocusedBrief, StoryFrameDraft


@dataclass(frozen=True)
class AuthorThemeDecision:
    primary_theme: str
    modifiers: tuple[str, ...]
    router_reason: str
    story_frame_strategy: str
    cast_strategy: str
    beat_plan_strategy: str


@dataclass(frozen=True)
class PlayCloseoutProfileDecision:
    play_closeout_profile: str
    router_reason: str
    guidance: str


@dataclass(frozen=True)
class PlayRuntimePolicyDecision:
    runtime_policy_profile: str
    router_reason: str
    guidance: str


def _modifier_hits(haystack: str) -> tuple[str, ...]:
    modifiers: list[str] = []
    if _has_any(haystack, ("blackout", "outage", "dimmed", "darkness")):
        modifiers.append("blackout")
    if _has_any(haystack, ("harbor", "port", "dock", "shipping")):
        modifiers.append("harbor")
    if _has_any(haystack, ("bridge", "flood", "ration", "ward", "district")):
        modifiers.append("infrastructure")
    if _has_any(haystack, ("archive", "ledger", "ledgers", "record", "records", "witness", "witnesses", "testimony", "testimonies", "evidence")):
        modifiers.append("archive")
    if _has_any(haystack, ("quarantine", "cordon", "blockade")):
        modifiers.append("quarantine")
    if _has_any(haystack, ("election", "succession", "vote", "mandate")):
        modifiers.append("election")
    if _has_any(haystack, ("panic", "riot", "curfew", "evacuation", "martial law")):
        modifiers.append("public_panic")
    return tuple(modifiers)


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])")


def _has_any(haystack: str, keywords: tuple[str, ...]) -> bool:
    return any(_keyword_pattern(keyword).search(haystack) for keyword in keywords)


def closeout_profile_guidance(closeout_profile: str) -> str:
    mapping = {
        "record_exposure_closeout": (
            "If the story only stabilizes by exposing lies, restoring a public record, or forcing proof into the open, "
            "prefer pyrrhic over mixed unless pressure is clearly low."
        ),
        "logistics_cost_closeout": (
            "If the city holds together only through rationing, quarantine, bridge control, or emergency supply oversight, "
            "prefer pyrrhic over mixed unless pressure is clearly low."
        ),
        "legitimacy_compact_closeout": (
            "If the settlement holds only through visible concessions, damaged trust, or a forced mandate, "
            "prefer pyrrhic over mixed unless the civic cost is clearly light."
        ),
        "panic_containment_closeout": (
            "If panic is only barely contained, prefer collapse or pyrrhic over mixed. "
            "Use mixed only when public pressure has clearly fallen."
        ),
        "generic_civic_closeout": (
            "Use mixed only for genuinely stable low-cost resolutions. Prefer pyrrhic when success comes with visible civic damage."
        ),
    }
    return mapping.get(closeout_profile, mapping["generic_civic_closeout"])


def runtime_policy_guidance(runtime_policy_profile: str) -> str:
    mapping = {
        "warning_record_play": (
            "Treat private record verification as exposure risk first and public panic second. "
            "Escalate public pressure only when warnings, bells, broadcasts, or public alarms go wide."
        ),
        "archive_vote_play": (
            "Treat quiet record repair as institutional strain or exposure pressure, not automatic public panic. "
            "Allow mixed only when certification stabilizes with low civic cost."
        ),
        "bridge_ration_play": (
            "Treat ration audits and bridge bargaining as external/resource pressure first. "
            "Public panic should rise mainly when the conflict spills into crowds, wards, or emergency announcements."
        ),
        "harbor_quarantine_play": (
            "Treat manifest checks and dock bargaining as resource and civic-pressure moves first. "
            "Public panic should rise mainly on overt public scares, public hearings, or quarantine breakdown."
        ),
        "blackout_council_play": (
            "Treat blackout rumor, loudspeaker messaging, and council fracture as highly public-facing. "
            "Public panic and collapse pressure should escalate faster when shared procedure breaks."
        ),
        "legitimacy_compact_play": (
            "Treat coalition bargains as legitimacy and leverage contests. "
            "Public panic matters, but relational and procedural cost should dominate closeout."
        ),
        "public_order_play": (
            "Treat crowd-facing panic and emergency authority as the primary pressure. "
            "Collapse should remain easier to trigger than mixed when order visibly fails."
        ),
        "generic_civic_play": (
            "Default to civic pressure, visible cost, and relationship strain without overfitting to one domain."
        ),
    }
    return mapping.get(runtime_policy_profile, mapping["generic_civic_play"])


def closeout_preference(
    closeout_profile: str,
    *,
    collapse_signal: bool,
    success_signal: bool,
    cost_signal: bool,
    truth_count: int,
    event_count: int,
    high_pressure_count: int,
    negative_stance_count: int,
    turn_cap_reached: bool,
) -> str:
    if collapse_signal:
        return "prefer_collapse"
    if closeout_profile == "record_exposure_closeout":
        if truth_count >= 2 and success_signal and (cost_signal or high_pressure_count >= 1 or negative_stance_count >= 1):
            return "prefer_pyrrhic"
        return "prefer_mixed"
    if closeout_profile == "logistics_cost_closeout":
        if success_signal and (cost_signal or high_pressure_count >= 1 or turn_cap_reached):
            return "prefer_pyrrhic"
        return "prefer_mixed"
    if closeout_profile == "legitimacy_compact_closeout":
        if success_signal and (cost_signal or negative_stance_count >= 1 or event_count >= 1):
            return "prefer_pyrrhic"
        return "prefer_mixed"
    if closeout_profile == "panic_containment_closeout":
        if high_pressure_count >= 1 and success_signal:
            return "prefer_pyrrhic"
        return "prefer_mixed"
    if success_signal and cost_signal:
        return "prefer_pyrrhic"
    return "prefer_mixed"


def profile_prefers_pyrrhic_fallback(
    closeout_profile: str,
    *,
    success_signal: bool,
    truth_signal: bool,
    moderate_cost_signal: bool,
    strong_cost_signal: bool,
    severe_pressure_signal: bool,
) -> bool:
    if not success_signal or not truth_signal:
        return False
    if closeout_profile in {"record_exposure_closeout", "logistics_cost_closeout"}:
        return moderate_cost_signal
    if closeout_profile == "legitimacy_compact_closeout":
        return moderate_cost_signal or strong_cost_signal
    if closeout_profile == "panic_containment_closeout":
        return strong_cost_signal or severe_pressure_signal
    return strong_cost_signal


def play_runtime_profile_from_bundle(bundle: DesignBundle) -> PlayRuntimePolicyDecision:
    haystack = " ".join(
        [
            bundle.focused_brief.story_kernel,
            bundle.focused_brief.setting_signal,
            bundle.focused_brief.core_conflict,
            bundle.story_bible.title,
            bundle.story_bible.premise,
            bundle.story_bible.stakes,
        ]
    ).casefold()
    if _has_any(haystack, ("observatory", "forecast", "warning", "warnings", "bulletin", "bulletins", "storm", "bells")):
        profile, reason = "warning_record_play", "runtime_warning_record_keywords"
    elif _has_any(haystack, ("archive", "ledger", "ledgers", "record", "records", "transcript", "transcripts", "witness", "witnesses")) and _has_any(haystack, ("vote", "election", "mandate", "certify", "certification")):
        profile, reason = "archive_vote_play", "runtime_archive_vote_keywords"
    elif _has_any(haystack, ("blackout", "referendum", "council", "councils", "neighborhood", "delegate", "delegates", "supply report", "supply reports")):
        profile, reason = "blackout_council_play", "runtime_blackout_council_keywords"
    elif _has_any(haystack, ("bridge", "flood", "ration", "ward", "district", "checkpoint", "allotment")):
        profile, reason = "bridge_ration_play", "runtime_bridge_ration_keywords"
    elif _has_any(haystack, ("harbor", "port", "trade", "shipping", "dock", "quarantine", "blockade", "manifest")):
        profile, reason = "harbor_quarantine_play", "runtime_harbor_quarantine_keywords"
    else:
        author_decision = author_theme_from_brief(bundle.focused_brief)
        strategy = author_decision.story_frame_strategy
        mapping = {
            "legitimacy_story": ("legitimacy_compact_play", "mapped_runtime_legitimacy"),
            "public_order_story": ("public_order_play", "mapped_runtime_public_order"),
            "truth_record_story": ("warning_record_play", "mapped_runtime_truth_record"),
            "logistics_story": ("harbor_quarantine_play", "mapped_runtime_logistics"),
        }
        profile, reason = mapping.get(strategy, ("generic_civic_play", "mapped_runtime_generic"))
    return PlayRuntimePolicyDecision(
        runtime_policy_profile=profile,
        router_reason=reason,
        guidance=runtime_policy_guidance(profile),
    )


def _author_profile_from_haystack(haystack: str, *, router_reason_prefix: str) -> AuthorThemeDecision:
    modifiers = _modifier_hits(haystack)
    logistics_keywords = ("harbor", "port", "trade", "quarantine", "supply", "blockade", "bridge", "flood", "ration", "ward", "district")
    truth_keywords = ("archive", "ledger", "ledgers", "record", "records", "witness", "witnesses", "testimony", "testimonies", "evidence", "proof", "observatory", "forecast", "warning", "warnings", "bulletin", "bulletins")
    legitimacy_keywords = ("succession", "election", "vote", "council", "coalition", "legitimacy", "settlement", "throne", "mandate")
    public_order_keywords = ("blackout", "panic", "riot", "evacuation", "curfew", "breakdown", "martial law")
    bridge_ration_keywords = ("bridge", "flood", "ration", "ward", "district", "checkpoint", "allotment")
    harbor_quarantine_keywords = ("harbor", "port", "trade", "shipping", "dock", "quarantine", "blockade", "manifest")
    blackout_referendum_keywords = ("blackout", "referendum", "council", "councils", "neighborhood", "delegate", "delegates", "supply report", "supply reports")
    archive_vote_keywords = ("archive", "ledger", "ledgers", "record", "records", "transcript", "transcripts", "witness", "witnesses", "testimony", "testimonies", "vote", "election", "mandate", "certify", "certification")
    warning_record_keywords = ("observatory", "forecast", "warning", "warnings", "bulletin", "bulletins", "storm", "bells", "evacuation")

    if _has_any(haystack, logistics_keywords):
        if _has_any(haystack, blackout_referendum_keywords):
            return AuthorThemeDecision(
                primary_theme="logistics_quarantine_crisis",
                modifiers=modifiers,
                router_reason=f"{router_reason_prefix}_blackout_referendum_keywords",
                story_frame_strategy="blackout_referendum_story",
                cast_strategy="blackout_referendum_cast",
                beat_plan_strategy="blackout_referendum_compile",
            )
        if _has_any(haystack, bridge_ration_keywords):
            return AuthorThemeDecision(
                primary_theme="logistics_quarantine_crisis",
                modifiers=modifiers,
                router_reason=f"{router_reason_prefix}_bridge_ration_keywords",
                story_frame_strategy="bridge_ration_story",
                cast_strategy="bridge_ration_cast",
                beat_plan_strategy="bridge_ration_compile",
            )
        if _has_any(haystack, harbor_quarantine_keywords):
            return AuthorThemeDecision(
                primary_theme="logistics_quarantine_crisis",
                modifiers=modifiers,
                router_reason=f"{router_reason_prefix}_harbor_quarantine_keywords",
                story_frame_strategy="harbor_quarantine_story",
                cast_strategy="harbor_quarantine_cast",
                beat_plan_strategy="harbor_quarantine_compile",
            )
        return AuthorThemeDecision(
            primary_theme="logistics_quarantine_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_logistics_quarantine_keywords",
            story_frame_strategy="logistics_story",
            cast_strategy="logistics_cast",
            beat_plan_strategy="single_semantic_compile",
        )
    if _has_any(haystack, truth_keywords):
        if _has_any(haystack, warning_record_keywords):
            return AuthorThemeDecision(
                primary_theme="truth_record_crisis",
                modifiers=modifiers,
                router_reason=f"{router_reason_prefix}_warning_record_keywords",
                story_frame_strategy="warning_record_story",
                cast_strategy="warning_record_cast",
                beat_plan_strategy="warning_record_compile",
            )
        if _has_any(haystack, archive_vote_keywords):
            return AuthorThemeDecision(
                primary_theme="truth_record_crisis",
                modifiers=modifiers,
                router_reason=f"{router_reason_prefix}_archive_vote_keywords",
                story_frame_strategy="archive_vote_story",
                cast_strategy="archive_vote_cast",
                beat_plan_strategy="archive_vote_compile",
            )
        return AuthorThemeDecision(
            primary_theme="truth_record_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_truth_record_keywords",
            story_frame_strategy="truth_record_story",
            cast_strategy="truth_record_cast",
            beat_plan_strategy="single_semantic_compile",
        )
    if _has_any(haystack, legitimacy_keywords):
        return AuthorThemeDecision(
            primary_theme="legitimacy_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_legitimacy_keywords",
            story_frame_strategy="legitimacy_story",
            cast_strategy="legitimacy_cast",
            beat_plan_strategy="conservative_direct_draft",
        )
    if _has_any(haystack, public_order_keywords):
        return AuthorThemeDecision(
            primary_theme="public_order_crisis",
            modifiers=modifiers,
            router_reason=f"{router_reason_prefix}_public_order_keywords",
            story_frame_strategy="public_order_story",
            cast_strategy="public_order_cast",
            beat_plan_strategy="conservative_direct_draft",
        )
    return AuthorThemeDecision(
        primary_theme="generic_civic_crisis",
        modifiers=modifiers,
        router_reason=f"{router_reason_prefix}_generic_civic_crisis",
        story_frame_strategy="generic_civic_story",
        cast_strategy="generic_civic_cast",
        beat_plan_strategy="conservative_direct_draft",
    )


def _play_closeout_profile_from_haystack(haystack: str, *, router_reason_prefix: str) -> PlayCloseoutProfileDecision:
    if _has_any(
        haystack,
        (
            "archive",
            "ledger",
            "ledgers",
            "record",
            "records",
            "witness",
            "witnesses",
            "testimony",
            "testimonies",
            "evidence",
            "proof",
            "observatory",
            "forecast",
            "warning",
            "warnings",
            "bulletin",
            "bulletins",
        ),
    ):
        profile = "record_exposure_closeout"
        reason = f"{router_reason_prefix}_record_exposure_keywords"
    elif _has_any(
        haystack,
        (
            "harbor",
            "port",
            "trade",
            "quarantine",
            "supply",
            "blockade",
            "bridge",
            "flood",
            "ration",
            "ward",
            "district",
        ),
    ):
        profile = "logistics_cost_closeout"
        reason = f"{router_reason_prefix}_logistics_keywords"
    elif _has_any(haystack, ("succession", "election", "vote", "council", "councils", "coalition", "legitimacy", "settlement", "throne", "mandate")):
        profile = "legitimacy_compact_closeout"
        reason = f"{router_reason_prefix}_legitimacy_keywords"
    elif _has_any(haystack, ("blackout", "panic", "riot", "evacuation", "curfew", "breakdown", "martial law")):
        profile = "panic_containment_closeout"
        reason = f"{router_reason_prefix}_public_order_keywords"
    else:
        profile = "generic_civic_closeout"
        reason = f"{router_reason_prefix}_generic_civic_keywords"
    return PlayCloseoutProfileDecision(
        play_closeout_profile=profile,
        router_reason=reason,
        guidance=closeout_profile_guidance(profile),
    )


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


def author_theme_from_brief(focused_brief: FocusedBrief) -> AuthorThemeDecision:
    haystack = _theme_haystack_from_brief(focused_brief)
    return _author_profile_from_haystack(
        haystack,
        router_reason_prefix="matched_brief",
    )


def author_theme_from_story(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
) -> AuthorThemeDecision:
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
    return _author_profile_from_haystack(
        haystack,
        router_reason_prefix="matched_story",
    )


def author_theme_from_bundle(bundle: DesignBundle) -> AuthorThemeDecision:
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
            *(item.summary for item in bundle.story_bible.ending_catalog),
        ]
    ).casefold()
    return _author_profile_from_haystack(
        haystack,
        router_reason_prefix="matched_bundle",
    )


def play_closeout_profile_from_bundle(bundle: DesignBundle) -> PlayCloseoutProfileDecision:
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
            *(item.summary for item in bundle.story_bible.ending_catalog),
        ]
    ).casefold()
    return _play_closeout_profile_from_haystack(
        haystack,
        router_reason_prefix="matched_play_bundle_closeout",
    )

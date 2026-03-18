from __future__ import annotations

from rpg_backend.author.contracts import (
    FocusedBrief,
    OverviewAxisDraft,
    OverviewFlagDraft,
    StoryFrameScaffoldDraft,
    OverviewTruthDraft,
    StoryFrameDraft,
)
from rpg_backend.author.normalize import trim_ellipsis


def _default_story_frame_title(focused_brief: FocusedBrief) -> str:
    lowered = f"{focused_brief.setting_signal} {focused_brief.core_conflict} {focused_brief.story_kernel}".casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        return "The Dimmed Accord"
    if "blackout" in lowered:
        return "The Dimmed City"
    if any(keyword in lowered for keyword in ("harbor", "port", "trade", "quarantine")):
        return "The Harbor Compact"
    if any(keyword in lowered for keyword in ("archive", "ledger", "record")):
        return "The Archive Accord"
    return "The Civic Accord"


def _default_story_frame_setting_frame(focused_brief: FocusedBrief) -> str:
    lowered = focused_brief.setting_signal.casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        return "a city plunged into darkness and political limbo"
    if "blackout" in lowered:
        return "a city struggling through blackout and public uncertainty"
    if any(keyword in lowered for keyword in ("harbor", "port", "trade", "quarantine")):
        return "a harbor city strained by quarantine politics and supply fear"
    if any(keyword in lowered for keyword in ("archive", "ledger", "record")):
        return "a city of archives where civic order depends on trusted records"
    return focused_brief.setting_signal


def _default_story_frame_mandate(focused_brief: FocusedBrief) -> str:
    lowered = focused_brief.story_kernel.casefold()
    if "mediator" in lowered:
        return "a neutral mediator must coordinate rival factions to keep essential services running"
    if "envoy" in lowered:
        return "an envoy must keep rival institutions negotiating long enough to stop the public breakdown"
    if "inspector" in lowered:
        return "an inspector must keep emergency authority legitimate while the city edges toward fracture"
    return focused_brief.story_kernel


def _default_story_frame_opposition_force(focused_brief: FocusedBrief) -> str:
    lowered = f"{focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        return "succession politics and institutional panic turn every delay into leverage"
    if "blackout" in lowered:
        return "fear, scarcity, and procedural drift turn every delay into public fracture"
    if any(keyword in lowered for keyword in ("harbor", "port", "trade", "quarantine")):
        return "trade pressure and quarantine politics keep turning relief into factional leverage"
    return focused_brief.core_conflict


def _default_story_frame_premise(focused_brief: FocusedBrief) -> str:
    return trim_ellipsis(
        f"In {_default_story_frame_setting_frame(focused_brief)}, {_default_story_frame_mandate(focused_brief)} while {_default_story_frame_opposition_force(focused_brief)}.",
        320,
    )


def _default_story_frame_stakes(focused_brief: FocusedBrief) -> str:
    lowered = f"{focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        return "If the coalition cannot keep the emergency response legitimate, the city fractures in public and emergency authority hardens into a new order."
    if any(keyword in lowered for keyword in ("archive", "ledger", "record")):
        return "If civic legitimacy breaks before the crisis stabilizes, the city loses both public trust and the records that keep its institutions governable."
    return "If civic legitimacy breaks before the crisis stabilizes, the city falls into open fracture and the mission fails in public view."


def _default_story_frame_truths(focused_brief: FocusedBrief) -> list[OverviewTruthDraft]:
    return [
        OverviewTruthDraft(text=trim_ellipsis(_default_story_frame_opposition_force(focused_brief), 220), importance="core"),
        OverviewTruthDraft(
            text=trim_ellipsis(
                f"The crisis is shaped by conditions inside {_default_story_frame_setting_frame(focused_brief)}.",
                220,
            ),
            importance="core",
        ),
    ]


def _clean_terminal_punctuation(value: str) -> str:
    text = trim_ellipsis(value, 320)
    while text.endswith(".,") or text.endswith(",.") or text.endswith(".."):
        text = text[:-1]
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return text


def _fallback_title_seed(focused_brief: FocusedBrief, scaffold: StoryFrameScaffoldDraft) -> str:
    title = trim_ellipsis(scaffold.title_seed or _default_story_frame_title(focused_brief), 120)
    return title or trim_ellipsis(_default_story_frame_title(focused_brief), 120)


def compile_story_frame(
    focused_brief: FocusedBrief,
    scaffold: StoryFrameScaffoldDraft,
) -> StoryFrameDraft:
    title = _fallback_title_seed(focused_brief, scaffold)
    setting_frame = trim_ellipsis(scaffold.setting_frame or _default_story_frame_setting_frame(focused_brief), 180)
    protagonist_mandate = trim_ellipsis(scaffold.protagonist_mandate or _default_story_frame_mandate(focused_brief), 220)
    opposition_force = trim_ellipsis(scaffold.opposition_force or _default_story_frame_opposition_force(focused_brief), 220)
    stakes_core = trim_ellipsis(scaffold.stakes_core or _default_story_frame_stakes(focused_brief), 220)
    premise = _clean_terminal_punctuation(
        f"In {setting_frame}, {protagonist_mandate} while {opposition_force}."
    )
    stakes = _clean_terminal_punctuation(
        f"If the coalition fails, {stakes_core}."
        if not stakes_core.casefold().startswith("if ")
        else stakes_core
    )
    style_guard = "Keep the story tense, readable, and grounded in civic consequence rather than spectacle."
    return StoryFrameDraft(
        title=title,
        premise=trim_ellipsis(premise, 320),
        tone=trim_ellipsis(scaffold.tone or focused_brief.tone_signal, 120),
        stakes=trim_ellipsis(stakes, 240),
        style_guard=trim_ellipsis(style_guard, 220),
        world_rules=scaffold.world_rules[:5],
        truths=scaffold.truths[:6],
        state_axis_choices=scaffold.state_axis_choices[:5],
        flags=scaffold.flags[:4],
    )


def build_default_story_frame_draft(focused_brief: FocusedBrief) -> StoryFrameDraft:
    return StoryFrameDraft(
        title=trim_ellipsis(_default_story_frame_title(focused_brief), 120),
        premise=_default_story_frame_premise(focused_brief),
        tone=trim_ellipsis(focused_brief.tone_signal, 120),
        stakes=_default_story_frame_stakes(focused_brief),
        style_guard="Keep the story tense, readable, and grounded in public consequences rather than dark spectacle.",
        world_rules=[
            trim_ellipsis(f"Visible order in {_default_story_frame_setting_frame(focused_brief)} depends on public legitimacy.", 180),
            "The main plot advances in fixed beats even when local tactics vary.",
        ],
        truths=_default_story_frame_truths(focused_brief),
        state_axis_choices=[
            OverviewAxisDraft(template_id="external_pressure", story_label="System Pressure", starting_value=1),
            OverviewAxisDraft(template_id="public_panic", story_label="Public Panic", starting_value=0),
            OverviewAxisDraft(template_id="political_leverage", story_label="Political Leverage", starting_value=2),
        ],
        flags=[
            OverviewFlagDraft(label="Public Cover", starting_value=False),
        ],
    )

from __future__ import annotations

import re

from rpg_backend.author.contracts import (
    FocusedBrief,
    OverviewAxisDraft,
    OverviewFlagDraft,
    StoryFrameScaffoldDraft,
    OverviewTruthDraft,
    StoryFrameDraft,
)
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis


_DANGLING_TERMINALS = {
    "and",
    "or",
    "but",
    "while",
    "to",
    "of",
    "with",
    "before",
    "after",
    "during",
    "amid",
    "amidst",
    "into",
    "onto",
}

_FINITE_ACTION_MARKERS = (
    " must ",
    " keep ",
    " keeps ",
    " hold ",
    " holds ",
    " stop ",
    " stops ",
    " expose ",
    " exposes ",
    " secure ",
    " secures ",
    " verify ",
    " verifies ",
    " protect ",
    " protects ",
    " coordinate ",
    " coordinates ",
    " restore ",
    " restores ",
    " preserve ",
    " preserves ",
    " prevent ",
    " prevents ",
    " negotiate ",
    " negotiates ",
    " contain ",
    " contains ",
    " calm ",
    " calms ",
    " can ",
    " cannot ",
    " lose ",
    " loses ",
    " turn ",
    " turns ",
    " while ",
)


def _clean_story_sentence_text(value: str, *, limit: int) -> str:
    text = normalize_whitespace(value)
    if not text:
        return ""
    text = text.replace(".,", ".").replace(",.", ".")
    text = re.sub(r"\.\s+(while|and|but|as)\b", r", \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;!?])", r"\1", text)
    text = re.sub(r"([.?!]){2,}", r"\1", text)
    stripped = text.rstrip(".!?")
    words = stripped.split()
    while words and words[-1].casefold().strip(",;:") in _DANGLING_TERMINALS:
        words.pop()
    text = " ".join(words).strip()
    if not text:
        return ""
    if text[-1] not in ".!?":
        text = f"{text}."
    return trim_ellipsis(text, limit)


def _looks_fragmentary_story_sentence(value: str) -> bool:
    normalized = normalize_whitespace(value)
    if not normalized:
        return True
    lowered = f" {normalized.casefold()} "
    if any(pattern in lowered for pattern in (" . while ", " . and ", " . but ", " . as ", " .,", " ,. ")):
        return True
    if normalized.endswith((".,", ",.", "..")):
        return True
    stripped = normalized.rstrip(".!?")
    words = stripped.split()
    if words and words[-1].casefold().strip(",;:") in _DANGLING_TERMINALS:
        return True
    if normalized.startswith("In ") and any(token in normalized for token in (". As ", ", As ")):
        return True
    return not any(marker in lowered for marker in _FINITE_ACTION_MARKERS)


def sanitize_story_sentence(
    value: str,
    *,
    fallback: str,
    limit: int,
) -> str:
    cleaned = _clean_story_sentence_text(value, limit=limit)
    if cleaned and not _looks_fragmentary_story_sentence(cleaned) and not _looks_fragmentary_story_sentence(value):
        return cleaned
    fallback_cleaned = _clean_story_sentence_text(fallback, limit=limit)
    if fallback_cleaned:
        return fallback_cleaned
    return cleaned or trim_ellipsis(normalize_whitespace(fallback or value), limit)


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


def sanitize_story_frame_draft(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
) -> StoryFrameDraft:
    fallback = build_default_story_frame_draft(focused_brief)
    return story_frame.model_copy(
        update={
            "title": trim_ellipsis(normalize_whitespace(story_frame.title or fallback.title), 120) or fallback.title,
            "premise": sanitize_story_sentence(
                story_frame.premise,
                fallback=fallback.premise,
                limit=320,
            ),
            "stakes": sanitize_story_sentence(
                story_frame.stakes,
                fallback=fallback.stakes,
                limit=240,
            ),
            "tone": trim_ellipsis(normalize_whitespace(story_frame.tone or fallback.tone), 120) or fallback.tone,
            "style_guard": trim_ellipsis(
                normalize_whitespace(story_frame.style_guard or fallback.style_guard),
                220,
            )
            or fallback.style_guard,
        }
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

from __future__ import annotations

import re

from rpg_backend.content_language import localized_text
from rpg_backend.author.contracts import (
    FocusedBrief,
    OverviewAxisDraft,
    OverviewFlagDraft,
    StoryFrameScaffoldDraft,
    OverviewTruthDraft,
    StoryFrameDraft,
)
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keyword in keywords)


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

_GENERIC_ZH_TITLES = {
    "公议协约",
    "城市协约",
    "公共协约",
    "紧急议会",
    "最终结算",
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

_CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")


def _contains_cjk_text(value: str) -> bool:
    return bool(_CJK_PATTERN.search(value))


def _normalize_terminal_punctuation(value: str) -> str:
    text = normalize_whitespace(value).strip()
    if not text:
        return ""
    preferred = "。" if _contains_cjk_text(text) else "."
    if text[-1] in ".!?。！？":
        stripped = text.rstrip(".!?。！？").rstrip()
        if not stripped:
            return preferred
        return f"{stripped}{preferred}"
    return f"{text}{preferred}"


def _clean_story_sentence_text(value: str, *, limit: int) -> str:
    text = normalize_whitespace(value)
    if not text:
        return ""
    text = (
        text.replace(".,", ".")
        .replace(",.", ".")
        .replace("。.", "。")
        .replace(".。", "。")
        .replace("！.", "！")
        .replace(".！", "！")
        .replace("？.", "？")
        .replace(".？", "？")
    )
    text = re.sub(r"\.\s+(while|and|but|as)\b", r", \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;!?。！？])", r"\1", text)
    text = re.sub(r"([.?!。！？]){2,}", r"\1", text)
    stripped = text.rstrip(".!?。！？")
    words = stripped.split()
    while words and words[-1].casefold().strip(",;:") in _DANGLING_TERMINALS:
        words.pop()
    text = " ".join(words).strip()
    if not text:
        return ""
    text = _normalize_terminal_punctuation(text)
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
    stripped = normalized.rstrip(".!?。！？")
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
    if _contains_any(lowered, ("blackout", "停电")) and _contains_any(lowered, ("succession", "election", "继承", "选举", "投票")):
        return localized_text(focused_brief.language, en="The Dimmed Accord", zh="黯灯协约")
    if _contains_any(lowered, ("bridge", "flood", "ration", "ledger", "桥", "洪水", "配给", "台账")):
        return localized_text(focused_brief.language, en="The Bridge Ledger", zh="桥线账本")
    if _contains_any(lowered, ("blackout", "停电")) and _contains_any(lowered, ("report", "reports", "bulletin", "supply", "通报", "供给")):
        return localized_text(focused_brief.language, en="The Darkened Report", zh="断电通报")
    if _contains_any(lowered, ("blackout", "停电")):
        return localized_text(focused_brief.language, en="The Dimmed City", zh="黯城")
    if _contains_any(lowered, ("harbor", "port", "trade", "quarantine", "港口", "码头", "贸易", "检疫", "舱单")):
        return localized_text(focused_brief.language, en="The Harbor Compact", zh="港务协定")
    if _contains_any(lowered, ("archive", "ledger", "record", "档案", "账本", "记录")):
        return localized_text(focused_brief.language, en="The Archive Accord", zh="档案协约")
    return localized_text(focused_brief.language, en="The Civic Accord", zh="公议协约")


def _default_story_frame_setting_frame(focused_brief: FocusedBrief) -> str:
    lowered = focused_brief.setting_signal.casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        return localized_text(focused_brief.language, en="a city plunged into darkness and political limbo", zh="一座陷在停电和权力真空里的城市")
    if "blackout" in lowered:
        return localized_text(focused_brief.language, en="a city struggling through blackout and public uncertainty", zh="一座在停电余波和人心浮动里勉强运转的城市")
    if any(keyword in lowered for keyword in ("harbor", "port", "trade", "quarantine")):
        return localized_text(focused_brief.language, en="a harbor city strained by quarantine politics and supply fear", zh="一座被检疫封线与断供恐慌压到临界点的港城")
    if any(keyword in lowered for keyword in ("archive", "ledger", "record")):
        return localized_text(focused_brief.language, en="a city of archives where civic order depends on trusted records", zh="一座日常秩序全靠记录还值得相信的档案之城")
    return focused_brief.setting_signal


def _default_story_frame_mandate(focused_brief: FocusedBrief) -> str:
    lowered = focused_brief.story_kernel.casefold()
    if "mediator" in lowered:
        return localized_text(focused_brief.language, en="a neutral mediator must coordinate rival factions to keep essential services running", zh="一名居中调停者必须稳住敌对派系，别让关键服务先断掉")
    if "envoy" in lowered:
        return localized_text(focused_brief.language, en="an envoy must keep rival institutions negotiating long enough to stop the public breakdown", zh="一名出面斡旋的人必须让对立机构继续谈下去，别让公开秩序先散掉")
    if "inspector" in lowered:
        return localized_text(focused_brief.language, en="an inspector must keep emergency authority legitimate while the city edges toward fracture", zh="一名检察官必须在城市滑向分裂前，守住紧急权力还算站得住脚")
    return focused_brief.story_kernel


def _default_story_frame_opposition_force(focused_brief: FocusedBrief) -> str:
    lowered = f"{focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        return localized_text(focused_brief.language, en="succession politics and institutional panic turn every delay into leverage", zh="继承政治和机构恐慌，把每一次拖延都炒成了筹码")
    if "blackout" in lowered:
        return localized_text(focused_brief.language, en="fear, scarcity, and procedural drift turn every delay into public fracture", zh="恐惧、短缺和程序失手，都在把拖延推成公开裂痕")
    if any(keyword in lowered for keyword in ("harbor", "port", "trade", "quarantine")):
        return localized_text(focused_brief.language, en="trade pressure and quarantine politics keep turning relief into factional leverage", zh="贸易压力与检疫政治，正在把救济安排改写成派系筹码")
    return focused_brief.core_conflict


def _default_story_frame_premise(focused_brief: FocusedBrief) -> str:
    return trim_ellipsis(
        localized_text(
            focused_brief.language,
            en=f"In {_default_story_frame_setting_frame(focused_brief)}, {_default_story_frame_mandate(focused_brief)} while {_default_story_frame_opposition_force(focused_brief)}.",
            zh=f"{_default_story_frame_setting_frame(focused_brief)}里，{_default_story_frame_mandate(focused_brief)}。与此同时，{_default_story_frame_opposition_force(focused_brief)}。",
        ),
        320,
    )


def _default_story_frame_stakes(focused_brief: FocusedBrief) -> str:
    lowered = f"{focused_brief.setting_signal} {focused_brief.core_conflict}".casefold()
    if "blackout" in lowered and any(keyword in lowered for keyword in ("succession", "election")):
        return localized_text(focused_brief.language, en="If the coalition cannot keep the emergency response legitimate, the city fractures in public and emergency authority hardens into a new order.", zh="如果联盟撑不住紧急响应还算正当，城市会当众裂开，紧急权力也会顺势长成新秩序。")
    if any(keyword in lowered for keyword in ("archive", "ledger", "record")):
        return localized_text(focused_brief.language, en="If civic legitimacy breaks before the crisis stabilizes, the city loses both public trust and the records that keep its institutions governable.", zh="如果公信力在危机稳住前先断掉，城市不只会失去公众信任，连撑住制度的记录也会一起失手。")
    return localized_text(focused_brief.language, en="If civic legitimacy breaks before the crisis stabilizes, the city falls into open fracture and the mission fails in public view.", zh="如果公信力在危机稳住前先断掉，城市会公开失序，你要守住的事也会当场砸掉。")


def _default_story_frame_truths(focused_brief: FocusedBrief) -> list[OverviewTruthDraft]:
    return [
        OverviewTruthDraft(text=trim_ellipsis(_default_story_frame_opposition_force(focused_brief), 220), importance="core"),
        OverviewTruthDraft(
            text=trim_ellipsis(
                localized_text(
                    focused_brief.language,
                    en=f"The crisis is shaped by conditions inside {_default_story_frame_setting_frame(focused_brief)}.",
                    zh=f"这场危机为什么会长成今天这样，就藏在{_default_story_frame_setting_frame(focused_brief)}自身的条件里。",
                ),
                220,
            ),
            importance="core",
        ),
    ]


def _clean_terminal_punctuation(value: str) -> str:
    text = trim_ellipsis(value, 320)
    while text.endswith((".,", ",.", "..", "。.", ".。", "！！", "！？", "？。", "。。")):
        text = text[:-1]
    return _normalize_terminal_punctuation(text)


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
        localized_text(
            focused_brief.language,
            en=f"In {setting_frame}, {protagonist_mandate} while {opposition_force}.",
            zh=f"在{setting_frame}中，{protagonist_mandate}，而{opposition_force}。",
        )
    )
    stakes = _clean_terminal_punctuation(
        localized_text(
            focused_brief.language,
            en=(
                f"If the coalition fails, {stakes_core}."
                if not stakes_core.casefold().startswith("if ")
                else stakes_core
            ),
            zh=(
                f"如果联盟失手，{stakes_core}。"
                if not stakes_core.startswith("如果")
                else stakes_core
            ),
        )
    )
    style_guard = localized_text(
        focused_brief.language,
        en="Keep the story tense, readable, and grounded in civic consequence rather than spectacle.",
        zh="保持故事紧张、清晰，并把重点放在公共后果而不是奇观上。",
    )
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
    normalized_title = trim_ellipsis(normalize_whitespace(story_frame.title or fallback.title), 120) or fallback.title
    if focused_brief.language == "zh" and normalized_title in _GENERIC_ZH_TITLES:
        normalized_title = fallback.title
    return story_frame.model_copy(
        update={
            "title": normalized_title,
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
        style_guard=localized_text(
            focused_brief.language,
            en="Keep the story tense, readable, and grounded in public consequences rather than dark spectacle.",
            zh="保持故事紧张、清晰，并把重点放在公共后果而不是黑暗奇观上。",
        ),
        world_rules=[
            trim_ellipsis(
                localized_text(
                    focused_brief.language,
                    en=f"Visible order in {_default_story_frame_setting_frame(focused_brief)} depends on public legitimacy.",
                    zh=f"{_default_story_frame_setting_frame(focused_brief)}中的可见秩序依赖公共正当性。",
                ),
                180,
            ),
            localized_text(
                focused_brief.language,
                en="The main plot advances in fixed beats even when local tactics vary.",
                zh="即便局部策略发生变化，主线剧情仍会沿着固定节拍推进。",
            ),
        ],
        truths=_default_story_frame_truths(focused_brief),
        state_axis_choices=[
            OverviewAxisDraft(template_id="external_pressure", story_label=localized_text(focused_brief.language, en="System Pressure", zh="系统压力"), starting_value=1),
            OverviewAxisDraft(template_id="public_panic", story_label=localized_text(focused_brief.language, en="Public Panic", zh="公众恐慌"), starting_value=0),
            OverviewAxisDraft(template_id="political_leverage", story_label=localized_text(focused_brief.language, en="Political Leverage", zh="政治筹码"), starting_value=2),
        ],
        flags=[
            OverviewFlagDraft(label=localized_text(focused_brief.language, en="Public Cover", zh="公开掩护"), starting_value=False),
        ],
    )

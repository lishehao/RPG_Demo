from __future__ import annotations

import re

from rpg_backend.author.compiler.endings import build_default_ending_rules, normalize_ending_rules_draft
from rpg_backend.author.planning import build_story_flow_plan
from rpg_backend.author.compiler.routes import (
    build_default_route_affordance_pack,
    build_deterministic_affordance_profiles,
    bundle_affordance_tags,
    normalize_route_affordance_pack,
)
from rpg_backend.author.compiler.story import build_default_story_frame_draft, sanitize_story_sentence
from rpg_backend.author.contracts import (
    AffordanceEffectProfile,
    AxisDefinition,
    BeatSpec,
    DesignBundle,
    EndingRulesDraft,
    RouteAffordancePackDraft,
)
from rpg_backend.content_language import is_chinese_language, localized_text
from rpg_backend.author.normalize import normalize_whitespace, trim_ellipsis, unique_preserve
from rpg_backend.play.contracts import PlayBeatRuntimeHintCard, PlayBeatRuntimeShard, PlayPlan, PlayProtagonist
from rpg_backend.product_text import (
    build_product_premise_fallback,
    sanitize_product_identity_summary,
    sanitize_product_opening_narration,
    sanitize_product_story_sentence,
)
from rpg_backend.story_profiles import (
    author_theme_from_bundle,
    play_closeout_profile_from_bundle,
    play_runtime_profile_from_bundle,
)


_PLAY_AXIS_FALLBACK_LABELS = {
    "external_pressure": "External Pressure",
    "public_panic": "Public Panic",
    "political_leverage": "Political Leverage",
    "resource_strain": "Resource Strain",
    "system_integrity": "Institutional Strain",
    "ally_trust": "Ally Trust",
    "exposure_risk": "Exposure Risk",
    "time_window": "Time Window",
}

_GENERIC_AXIS_LABELS = {
    "state axis",
    "axis",
    "pressure axis",
    "relationship axis",
    "resource axis",
    "time axis",
    "meter",
}

_MANDATE_GERUND_MAP = {
    "preserving": "preserve",
    "preventing": "prevent",
    "keeping": "keep",
    "restoring": "restore",
    "proving": "prove",
    "holding": "hold",
    "stabilizing": "stabilize",
    "securing": "secure",
    "containing": "contain",
    "binding": "bind",
    "forcing": "force",
}

_MANDATE_TAIL_MARKERS = (
    " triggers ",
    " trigger ",
    " reshapes ",
    " reshape ",
    " driven by ",
)

_MANDATE_NOISE_MARKERS = (
    " while ",
    " when ",
    " during ",
    " amid ",
    " under ",
    " across ",
    " throughout ",
    " against ",
)

_MANDATE_START_VERBS = (
    "prove",
    "protect",
    "prevent",
    "preserve",
    "keep",
    "hold",
    "restore",
    "stabilize",
    "secure",
    "contain",
    "bind",
    "force",
    "trace",
    "understand",
    "verify",
    "maintain",
    "reopen",
    "expose",
)

_OPENING_TEMPLATE_SEEDS = (
    "pressure",
    "hook",
    "stakes",
)

_ROLE_PHRASE_STOPWORDS = {
    "when",
    "during",
    "while",
    "after",
    "before",
    "if",
    "in",
    "amid",
    "under",
}

_ROLE_PREFIX_TRIM_TOKENS = {
    "city",
    "civic",
    "royal",
    "public",
    "neutral",
    "ward",
}

_ROLE_ARTICLES = {"a", "an", "the"}
_MANDATE_MAX_WORDS = 16
_TITLE_PREFIX_STOPWORDS = _ROLE_PHRASE_STOPWORDS | {"before", "after"}

_ROLE_DISCOVERY_PATTERN = re.compile(
    r"^(?:an?|the)\s+[^,]{0,80}\s+"
    r"(?P<verb>discovers|finds|uncovers|learns|realizes|spots|proves|reveals|exposes)\s+"
    r"(?P<rest>.+)$",
    flags=re.IGNORECASE,
)

_ZH_MANDATE_LEADING_CONTEXT = re.compile(r"^在[^，。]{2,80}(?:中|里)，")

_ZH_MANDATE_TEMPLATES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("港口", "码头", "检疫", "舱单", "投票"),
        "在救济投票前查清被篡改的紧急舱单，阻止偏袒性分配被写成既成事实",
    ),
    (
        ("港口", "码头", "检疫", "舱单"),
        "在检疫秩序失控前查清被篡改的舱单，别让港口分配继续被人暗中改写",
    ),
    (
        ("档案", "记录", "账本", "投票"),
        "在表决结果被写成定局前核清被改写的记录",
    ),
    (
        ("桥", "洪水", "配给", "街区"),
        "在配给秩序撕裂街区前稳住调度程序，让桥线继续运转",
    ),
    (
        ("停电", "公投", "议会", "社区"),
        "在停电恐慌把议会谈判冲散前稳住各街区的共同程序",
    ),
    (
        ("联盟", "议会", "调停", "授权"),
        "在危机被人写成单方面授权前守住协商空间",
    ),
    (
        ("警报", "公告", "预报", "观测站"),
        "在警报失去公信力前证明预警属实",
    ),
)


def _merge_affordance_profiles(bundle: DesignBundle) -> list[AffordanceEffectProfile]:
    authored_pack = normalize_route_affordance_pack(
        RouteAffordancePackDraft(
            route_unlock_rules=bundle.rule_pack.route_unlock_rules,
            affordance_effect_profiles=bundle.rule_pack.affordance_effect_profiles,
        ),
        bundle,
    )
    authored_profiles = {profile.affordance_tag: profile for profile in authored_pack.affordance_effect_profiles}
    deterministic_profiles = {
        profile.affordance_tag: profile for profile in build_deterministic_affordance_profiles(bundle)
    }
    merged_profiles: list[AffordanceEffectProfile] = []
    ordered_tags = unique_preserve(
        [*bundle_affordance_tags(bundle), *list(authored_profiles.keys()), *list(deterministic_profiles.keys())]
    )
    for tag in ordered_tags:
        authored = authored_profiles.get(tag)
        fallback = deterministic_profiles.get(tag)
        if authored is None and fallback is None:
            continue
        if authored is None:
            merged_profiles.append(fallback)
            continue
        if fallback is None:
            merged_profiles.append(authored)
            continue
        merged_profiles.append(
            AffordanceEffectProfile(
                affordance_tag=authored.affordance_tag,
                default_story_function=authored.default_story_function or fallback.default_story_function,
                axis_deltas=authored.axis_deltas or fallback.axis_deltas,
                stance_deltas=authored.stance_deltas or fallback.stance_deltas,
                can_add_truth=bool(authored.can_add_truth or fallback.can_add_truth),
                can_add_event=bool(authored.can_add_event or fallback.can_add_event),
            )
        )
    return merged_profiles


def _compiled_route_pack(bundle: DesignBundle) -> RouteAffordancePackDraft:
    authored_pack = normalize_route_affordance_pack(
        RouteAffordancePackDraft(
            route_unlock_rules=bundle.rule_pack.route_unlock_rules,
            affordance_effect_profiles=bundle.rule_pack.affordance_effect_profiles,
        ),
        bundle,
    )
    default_pack = build_default_route_affordance_pack(bundle)
    return RouteAffordancePackDraft(
        route_unlock_rules=authored_pack.route_unlock_rules or default_pack.route_unlock_rules,
        affordance_effect_profiles=_merge_affordance_profiles(bundle),
    )


def _compiled_ending_rules(bundle: DesignBundle):
    authored = normalize_ending_rules_draft(
        EndingRulesDraft(ending_rules=bundle.rule_pack.ending_rules),
        bundle,
    )
    defaults = build_default_ending_rules(bundle)
    merged_by_id = {rule.ending_id: rule for rule in defaults.ending_rules}
    for rule in authored.ending_rules:
        merged_by_id[rule.ending_id] = rule
    return sorted(merged_by_id.values(), key=lambda item: (item.priority, item.ending_id))


def _resolved_axis_label(axis: AxisDefinition) -> str:
    raw = trim_ellipsis(axis.label or "", 80)
    if axis.axis_id == "system_integrity" and axis.kind == "pressure":
        return _PLAY_AXIS_FALLBACK_LABELS["system_integrity"]
    if raw and raw.casefold() not in _GENERIC_AXIS_LABELS:
        return raw
    return _PLAY_AXIS_FALLBACK_LABELS.get(axis.axis_id, axis.axis_id.replace("_", " ").title())


def _compiled_axes(bundle: DesignBundle) -> list[AxisDefinition]:
    return [
        axis.model_copy(update={"label": _resolved_axis_label(axis)})
        for axis in bundle.state_schema.axes
    ]


def _normalized_sentence_key(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text.casefold()).strip()


def _clean_opening_line(raw: str, *, fallback: str | None = None, limit: int = 220) -> str:
    raw_text = normalize_whitespace(raw)
    if _ROLE_DISCOVERY_PATTERN.match(raw_text):
        cleaned = trim_ellipsis(raw_text, limit).rstrip(".")
    else:
        cleaned = sanitize_story_sentence(raw_text, fallback=fallback or raw_text, limit=limit).rstrip(".")
    cleaned = re.sub(r"^(?:in|during|amid|under)\s+[^,]{0,120},\s*", "", cleaned, count=1, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:.")
    return trim_ellipsis(cleaned, limit)


def _rewrite_role_discovery_clause(text: str, *, limit: int = 220) -> str:
    match = _ROLE_DISCOVERY_PATTERN.match(text)
    if match is None:
        return text
    rest = normalize_whitespace(match.group("rest")).strip(" ,;:.")
    if not rest:
        return ""
    if rest.casefold().startswith("that "):
        rest = rest[5:].strip()
    if not rest:
        return ""
    return trim_ellipsis(rest[0].upper() + rest[1:], limit)


def _opening_stakes_line(bundle: DesignBundle, *, protagonist: PlayProtagonist) -> str:
    candidates = [
        bundle.story_bible.stakes,
        bundle.story_bible.premise,
        bundle.focused_brief.core_conflict,
    ]
    mandate_key = _normalized_sentence_key(protagonist.mandate)
    title_key = protagonist.title.casefold()
    for raw in candidates:
        if not raw or not raw.strip():
            continue
        cleaned = _clean_opening_line(
            raw,
            limit=220,
        )
        cleaned = _rewrite_role_discovery_clause(cleaned, limit=220)
        if not cleaned:
            continue
        cleaned_key = _normalized_sentence_key(cleaned)
        if cleaned_key == mandate_key:
            continue
        lowered = cleaned.casefold()
        if lowered.startswith(("when ", "during ", "while ")):
            continue
        gerund_pattern = "|".join(_MANDATE_GERUND_MAP)
        if re.match(
            rf"^(?:an?|the)\s+[^,]{{0,80}}\b(?:must|{gerund_pattern})\b",
            lowered,
            flags=re.IGNORECASE,
        ):
            continue
        if protagonist.title.casefold() in lowered and mandate_key in cleaned_key:
            continue
        if lowered.startswith(f"you are the {title_key}"):
            continue
        if lowered.startswith(f"you are {title_key}"):
            continue
        return cleaned
    return ""


def _opening_hook_line(bundle: DesignBundle, *, protagonist: PlayProtagonist) -> str:
    first_beat = bundle.beat_spine[0]
    beat_title = trim_ellipsis(first_beat.title.rstrip("."), 120)
    beat_goal = _clean_opening_line(first_beat.goal, fallback=beat_title, limit=220)
    beat_goal = _rewrite_role_discovery_clause(beat_goal, limit=220)
    beat_key = _normalized_sentence_key(beat_title)
    goal_key = _normalized_sentence_key(beat_goal)
    mandate_key = _normalized_sentence_key(protagonist.mandate)
    template_seed = f"{bundle.story_bible.title}|{beat_title}|{protagonist.title}"
    template_index = sum(ord(char) for char in template_seed) % len(_OPENING_TEMPLATE_SEEDS)
    if not beat_goal or goal_key in {beat_key, mandate_key}:
        templates = (
            f"Tonight it starts with {beat_title.lower()}.",
            f"The room is already turning around {beat_title.lower()}.",
            f"You step in with {beat_title.lower()} already underway.",
        )
        return templates[template_index]
    templates = (
        f"Tonight it starts with {beat_title.lower()}: {beat_goal}.",
        f"The room is already turning around {beat_title.lower()}: {beat_goal}.",
        f"You step in with {beat_title.lower()} already underway: {beat_goal}.",
    )
    return templates[template_index]


def _clean_opening_line_zh(raw: str, *, limit: int = 220) -> str:
    text = normalize_whitespace(raw).strip().rstrip(".。")
    if not text:
        return ""
    text = _ZH_MANDATE_LEADING_CONTEXT.sub("", text, count=1).strip(" ，；：")
    text = re.sub(r"^如果", "一旦", text, count=1)
    text = re.sub(r"^而", "", text, count=1).strip(" ，；：")
    return trim_ellipsis(text, limit)


def _opening_stakes_line_zh(bundle: DesignBundle, *, protagonist: PlayProtagonist) -> str:
    mandate_key = _normalized_sentence_key(protagonist.mandate)
    for raw in (bundle.story_bible.stakes, bundle.story_bible.premise, bundle.focused_brief.core_conflict):
        cleaned = _clean_opening_line_zh(raw, limit=220)
        if not cleaned:
            continue
        cleaned_key = _normalized_sentence_key(cleaned)
        if cleaned_key == mandate_key:
            continue
        if protagonist.title in cleaned and mandate_key and mandate_key in cleaned_key:
            continue
        return cleaned
    return ""


def _opening_hook_line_zh(bundle: DesignBundle, *, protagonist: PlayProtagonist) -> str:
    first_beat = bundle.beat_spine[0]
    beat_title = trim_ellipsis(first_beat.title.rstrip(".。"), 80)
    beat_goal = _clean_opening_line_zh(first_beat.goal, limit=180)
    beat_key = _normalized_sentence_key(beat_title)
    goal_key = _normalized_sentence_key(beat_goal)
    mandate_key = _normalized_sentence_key(protagonist.mandate)
    template_seed = f"{bundle.story_bible.title}|{beat_title}|{protagonist.title}"
    template_index = sum(ord(char) for char in template_seed) % 3
    if not beat_goal or goal_key in {beat_key, mandate_key}:
        templates = (
            f"今晚先顶到你面前的是{beat_title}，你得先看清谁在失控、谁又在借机拿筹码",
            f"你一出手就撞上{beat_title}，局面已经开始往失控边缘倾斜",
            f"眼前先爆开的就是{beat_title}，你得马上判断断裂点到底落在哪一环",
        )
        return templates[template_index]
    templates = (
        f"今晚先顶到你面前的是{beat_title}：{beat_goal}",
        f"你一出手就撞上{beat_title}：{beat_goal}",
        f"眼前先爆开的就是{beat_title}：{beat_goal}",
    )
    return templates[template_index]


def _opening_narration(bundle: DesignBundle, *, protagonist: PlayProtagonist) -> str:
    if is_chinese_language(bundle.focused_brief.language):
        mandate = protagonist.mandate.rstrip(".。")
        stakes_line = _opening_stakes_line_zh(bundle, protagonist=protagonist)
        hook_line = _opening_hook_line_zh(bundle, protagonist=protagonist)
        lead_templates = (
            f"你是{protagonist.title}，现在得{mandate}",
            f"轮到你以{protagonist.title}的身份出面了：{mandate}",
            f"你眼下要做的，就是以{protagonist.title}的身份{mandate}",
        )
        lead_seed = sum(ord(char) for char in f"{bundle.story_bible.title}|{protagonist.title}|{mandate}") % len(lead_templates)
        parts = [f"{lead_templates[lead_seed]}。"]
        if stakes_line:
            parts.append(f"{stakes_line}。")
        if hook_line:
            parts.append(f"{hook_line}。")
        opening = sanitize_product_opening_narration("".join(part.strip() for part in parts if part.strip()), limit=4000)
        if opening.strip():
            return opening
        return f"你是{protagonist.title}，现在得{mandate}。眼前的第一处压力点已经浮出来了。"
    title = protagonist.title.lower()
    identity = protagonist.identity_summary.rstrip(".")
    stakes_line = _opening_stakes_line(bundle, protagonist=protagonist)
    hook_line = _opening_hook_line(bundle, protagonist=protagonist)
    identity_seed = sum(ord(char) for char in f"{bundle.story_bible.title}|{protagonist.title}|{bundle.focused_brief.story_kernel}") % 3
    if identity_seed == 0:
        lead_line = identity.split(". ", 1)[0]
    elif identity_seed == 1:
        if protagonist_name := getattr(protagonist, "identity_summary", None):
            if protagonist_name.startswith("You are ") and ", the " in protagonist_name:
                name_part = protagonist_name[len("You are "):].split(", the ", 1)[0]
                lead_line = f"You are {name_part}, carrying the city's burden as {title}"
            else:
                lead_line = f"You carry the city's burden as {title}, and your mandate is to {protagonist.mandate.rstrip('.')}"
        else:
            lead_line = f"You carry the city's burden as {title}, and your mandate is to {protagonist.mandate.rstrip('.')}"
    else:
        if protagonist_name := getattr(protagonist, "identity_summary", None):
            if protagonist_name.startswith("You are ") and ", the " in protagonist_name:
                name_part = protagonist_name[len("You are "):].split(", the ", 1)[0]
                lead_line = f"As {name_part}, the {title}, you step into this crisis with one job: {protagonist.mandate.rstrip('.')}"
            else:
                lead_line = f"As the {title}, you step into this crisis with one job: {protagonist.mandate.rstrip('.')}"
        else:
            lead_line = f"As the {title}, you step into this crisis with one job: {protagonist.mandate.rstrip('.')}"
    parts = [f"{lead_line}."]
    if stakes_line:
        parts.append(f"{stakes_line}.")
    if hook_line:
        parts.append(hook_line)
    opening = sanitize_product_opening_narration(" ".join(part.strip() for part in parts if part.strip()), limit=4000)
    if opening.strip():
        return opening
    return f"You are the {title}. Your mandate is to {protagonist.mandate.rstrip('.')}. The first pressure point is already in motion."


def _extract_protagonist_title(bundle: DesignBundle) -> str:
    kernel = " ".join(
        part.strip()
        for part in (
            bundle.focused_brief.story_kernel or "",
            bundle.focused_brief.core_conflict or "",
            bundle.story_bible.premise or "",
            bundle.story_bible.stakes or "",
        )
        if part and part.strip()
    )
    lowered = kernel.casefold()
    if bundle.focused_brief.language == "zh":
        zh_role_patterns = [
            ("港务检察官", "港务检察官"),
            ("桥务工程官", "桥务工程官"),
            ("桥梁工程官", "桥务工程官"),
            ("档案核验官", "档案核验官"),
            ("社区协调员", "社区协调员"),
            ("调停者", "调停者"),
        ]
        for needle, title in zh_role_patterns:
            if needle in kernel:
                return title
    role_patterns = [
        ("archivist", "Archivist"),
        ("harbor inspector", "Harbor Inspector"),
        ("inspector", "Inspector"),
        ("bridge engineer", "Bridge Engineer"),
        ("engineer", "Engineer"),
        ("ombudsman", "Ombudsman"),
        ("mediator", "Mediator"),
        ("market steward", "Market Steward"),
        ("steward", "Steward"),
    ]
    for needle, title in role_patterns:
        if needle in lowered:
            return title

    protagonist_member = bundle.story_bible.cast[0] if bundle.story_bible.cast else None
    role = normalize_whitespace((protagonist_member.role if protagonist_member is not None else "") or "").strip()
    if role and role.casefold() not in {"protagonist", "lead", "player", "mediator"} and len(role.split()) <= 4:
        return trim_ellipsis(role if any(char.isupper() for char in role) else role.title(), 120)

    role_phrase_sources = [
        bundle.focused_brief.story_kernel or "",
        bundle.focused_brief.core_conflict or "",
        bundle.focused_brief.setting_signal or "",
        bundle.story_bible.premise or "",
    ]
    role_phrase_pattern = re.compile(
        r"(?:^|[,.;:]\s*)(?:a|an)\s+([a-z][a-z -]{2,60}?)(?=\s+(?:must|tries|works|seeks|needs|has to|tasked|protects|prevents|keeps|holds|restores|proves|stabilizes|secures|contains|binds|forces)\b)",
        flags=re.IGNORECASE,
    )
    for source in role_phrase_sources:
        for match in role_phrase_pattern.finditer(source):
            phrase = normalize_whitespace(match.group(1)).strip(" ,.;:-")
            if not phrase:
                continue
            tokens = [token for token in phrase.split() if token]
            if not tokens:
                continue
            if tokens[0].casefold() in _ROLE_PREFIX_TRIM_TOKENS and len(tokens) >= 2:
                tokens = tokens[1:]
            if not tokens or tokens[0].casefold() in _ROLE_PHRASE_STOPWORDS:
                continue
            candidate = " ".join(tokens[:4]).title()
            if candidate and candidate.split()[0].casefold() not in _ROLE_PHRASE_STOPWORDS:
                return trim_ellipsis(candidate, 120)
    words = [word for word in kernel.split() if word][:3]
    return trim_ellipsis(" ".join(words).title() or "Civic Lead", 120)


def _normalize_protagonist_title(title: str) -> str:
    normalized = normalize_whitespace(title).strip(" ,.;:-")
    if not normalized:
        return normalized
    tokens = [token for token in normalized.split() if token]
    while tokens and tokens[0].casefold() in _ROLE_ARTICLES:
        tokens = tokens[1:]
    normalized = " ".join(tokens)
    if not normalized:
        return ""
    return trim_ellipsis(normalized.title(), 120)


def _is_malformed_protagonist_title(title: str) -> bool:
    normalized = normalize_whitespace(title).strip()
    if not normalized:
        return True
    tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'-]*", normalized.casefold()) if token]
    if not tokens:
        return True
    return tokens[0] in _TITLE_PREFIX_STOPWORDS


def _fallback_protagonist_mandate(title: str, bundle: DesignBundle) -> str:
    lowered = f"{title} {bundle.focused_brief.story_kernel} {bundle.focused_brief.core_conflict}".casefold()
    if bundle.focused_brief.language == "zh":
        for keywords, template in _ZH_MANDATE_TEMPLATES:
            if all(keyword in lowered for keyword in keywords):
                return template
        if any(keyword in lowered for keyword in ("港口", "检疫", "码头", "舱单")):
            return "在检疫秩序失控前查清被篡改的舱单，别让港口分配继续被人暗中改写"
        if any(keyword in lowered for keyword in ("档案", "记录", "账本")):
            return "在公共叙事彻底定型前核清被改写的记录"
        if any(keyword in lowered for keyword in ("桥", "洪水", "配给", "街区")):
            return "在配给与基础设施压力撕裂街区前稳住共同程序"
        if any(keyword in lowered for keyword in ("调停", "联盟", "议会")):
            return "在危机被人写成既成裂痕前守住协商空间"
        return "在危机硬化成公开裂痕前守住公共正当性"
    if "archivist" in lowered and "warning" in lowered:
        return "prove the warning is real before the record is buried"
    if "archivist" in lowered and any(keyword in lowered for keyword in ("ration", "roll", "ledger", "blackout")):
        return "verify altered ration rolls before blackout panic turns scarcity into punishment"
    if "archivist" in lowered:
        return "protect the public record before trust hardens into panic"
    if "bridge engineer" in lowered or ("engineer" in lowered and "flood" in lowered):
        return "keep the flood defense coalition intact before the wards break apart"
    if "ombudsman" in lowered:
        return "keep the neighborhood councils from breaking apart before panic hardens into street control"
    if "harbor inspector" in lowered:
        return "keep the harbor open under public oversight before scarcity turns quarantine into factional rule"
    if "inspector" in lowered:
        return "keep emergency authority legitimate before pressure turns civic order into private rule"
    if "mediator" in lowered:
        return "keep the coalition negotiating before the crisis hardens into public fracture"
    if "steward" in lowered:
        return "hold the civic line before scarcity turns into leverage"
    return "keep civic order legitimate before the crisis hardens into fracture"


def _clean_mandate_candidate(raw: str) -> str:
    text = normalize_whitespace(raw or "").strip().rstrip(".")
    if not text:
        return ""
    for pattern in (
        r".*?\bmust\s+",
        r".*?\btasked with\s+",
        r".*?\btasked to\s+",
        r".*?\btrying to\s+",
        r".*?\bseeks to\s+",
        r".*?\bworks to\s+",
    ):
        if re.match(pattern, text, flags=re.IGNORECASE):
            text = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()
            break
    text = re.sub(
        r"^(?:an?|the)\s+[^,]{0,80}\s+(?=(?:preserving|preventing|keeping|restoring|proving|holding|stabilizing|securing|containing|binding|forcing)\b)",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(r"^must\s+", "", text, count=1, flags=re.IGNORECASE).strip()
    lowered = text.casefold()
    for gerund, base in _MANDATE_GERUND_MAP.items():
        if lowered.startswith(f"{gerund} "):
            text = f"{base} {text[len(gerund) + 1:]}"
            lowered = text.casefold()
            break
    for marker in _MANDATE_TAIL_MARKERS:
        index = lowered.find(marker)
        if index > 0:
            text = text[:index].rstrip(" ,;:.")
            lowered = text.casefold()
            break
    if lowered.startswith(("in ", "during ", "when ", "while ", "if ")):
        return ""
    if lowered.startswith(("a ", "an ", "the ")):
        return ""
    tokens = [token for token in text.split() if token]
    if tokens:
        last_token = tokens[-1].strip(" ,;:.")
        if len(last_token) == 1:
            for connector in (" before ", " to ", " while ", " after "):
                index = lowered.rfind(connector)
                if index > 0:
                    text = text[:index].rstrip(" ,;:.")
                    break
            else:
                text = " ".join(tokens[:-1]).rstrip(" ,;:.")
    return trim_ellipsis(text, 220)


def _clean_mandate_candidate_zh(raw: str) -> str:
    text = normalize_whitespace(raw or "").strip().rstrip(".。")
    if not text:
        return ""
    text = _ZH_MANDATE_LEADING_CONTEXT.sub("", text, count=1).strip(" ，；：")
    lowered = text.casefold()
    for keywords, template in _ZH_MANDATE_TEMPLATES:
        if all(keyword in lowered for keyword in keywords):
            return template
    if all(keyword in lowered for keyword in ("港口", "舱单")) and any(keyword in lowered for keyword in ("投票", "救济", "偏袒", "忠诚街区", "优先照顾")):
        return "在救济投票前查清被篡改的紧急舱单，阻止偏袒性分配被写成既成事实"
    if all(keyword in lowered for keyword in ("档案", "记录")) and any(keyword in lowered for keyword in ("投票", "表决", "认证")):
        return "在表决结果被写成定局前核清被改写的记录"
    if any(keyword in lowered for keyword in ("桥", "洪水", "配给", "街区")):
        return "在配给秩序撕裂街区前稳住调度程序，让桥线继续运转"
    if any(keyword in lowered for keyword in ("议会", "联盟", "调停", "授权")):
        return "在危机被人写成单方面授权前守住协商空间"
    if any(keyword in lowered for keyword in ("警报", "公告", "预报", "观测站")):
        return "在警报失去公信力前证明预警属实"
    if re.match(r"^在[^。]{6,60}前", text) and any(
        marker in text for marker in ("查清", "查明", "核实", "核清", "守住", "稳住", "证明", "逼出", "拿回")
    ):
        return trim_ellipsis(text, 80)
    return ""


def _protagonist_mandate(bundle: DesignBundle, *, title: str) -> str:
    default = _fallback_protagonist_mandate(title, bundle)
    candidates = [
        bundle.focused_brief.story_kernel,
        bundle.focused_brief.core_conflict,
        bundle.story_bible.premise,
    ]
    for raw in candidates:
        text = _clean_mandate_candidate(raw or "")
        lowered = text.casefold()
        if not text:
            continue
        if is_chinese_language(bundle.focused_brief.language):
            if len(re.findall(r"[A-Za-z]{4,}", text)) >= 2:
                continue
            if cleaned_zh := _clean_mandate_candidate_zh(raw or text):
                return cleaned_zh
            continue
        if len(text.split()) > _MANDATE_MAX_WORDS:
            continue
        if any(char in text for char in ",;:"):
            continue
        if any(marker in lowered for marker in _MANDATE_NOISE_MARKERS):
            continue
        if any(lowered.startswith(f"{verb} ") or lowered == verb for verb in _MANDATE_START_VERBS):
            return text
    return default


def _compile_protagonist(bundle: DesignBundle) -> tuple[PlayProtagonist, str | None, str | None]:
    protagonist_member = bundle.story_bible.cast[0] if bundle.story_bible.cast else None
    protagonist_npc_id = protagonist_member.npc_id if protagonist_member is not None else None
    protagonist_name = protagonist_member.name if protagonist_member is not None else None
    title = _normalize_protagonist_title(_extract_protagonist_title(bundle))
    role_fallback = normalize_whitespace((protagonist_member.role if protagonist_member is not None else "") or "").strip()
    if _is_malformed_protagonist_title(title) and role_fallback:
        title = _normalize_protagonist_title(role_fallback)
    title = title or localized_text(bundle.focused_brief.language, en="Civic Lead", zh="临时主事人")
    mandate = _protagonist_mandate(bundle, title=title)
    overlap = any(
        member is not protagonist_member and title.casefold() in member.role.casefold()
        for member in bundle.story_bible.cast
    )
    if protagonist_name:
        identity_summary = localized_text(
            bundle.focused_brief.language,
            en=f"You are {protagonist_name}, the {title.lower()}. Your mandate is to {mandate.rstrip('.')}",
            zh=f"你是{protagonist_name}，以{title}的身份出面。你现在要{mandate.rstrip('.')}",
        )
    else:
        identity_summary = localized_text(
            bundle.focused_brief.language,
            en=f"You are the {title.lower()}. Your mandate is to {mandate.rstrip('.')}",
            zh=f"你是{title}，现在要{mandate.rstrip('.')}",
        )
    if overlap:
        identity_summary += localized_text(
            bundle.focused_brief.language,
            en=". The named NPCs are rival authorities and witnesses around you, not alternate player avatars",
            zh="。这些具名角色是围着你行动的对手、机构代表和见证者，并不是别的玩家分身",
        )
    identity_summary = sanitize_product_identity_summary(identity_summary, limit=320)
    return PlayProtagonist(
        title=title,
        mandate=mandate,
        identity_summary=identity_summary,
    ), protagonist_npc_id, protagonist_name


def _compress_runtime_beats(
    bundle: DesignBundle,
    *,
    story_flow_plan=None,
) -> list[BeatSpec]:
    beats = list(bundle.beat_spine)
    if len(beats) <= 1:
        return beats
    if story_flow_plan is not None:
        target_count = min(story_flow_plan.target_beat_count, len(beats))
        scheduled_progress = list(story_flow_plan.progress_required_by_beat[:target_count])
        return [
            beat.model_copy(update={"progress_required": scheduled_progress[index]})
            for index, beat in enumerate(beats[:target_count])
        ]

    compressed_progress = [max(1, beat.progress_required) for beat in beats]
    compressed_progress[-1] = 1
    target_total_progress = max(4, len(beats) + 1)
    reduction_order = [*range(1, len(beats) - 1), 0]

    while sum(compressed_progress) > target_total_progress:
        changed = False
        for index in reduction_order:
            if compressed_progress[index] <= 1:
                continue
            compressed_progress[index] -= 1
            changed = True
            if sum(compressed_progress) <= target_total_progress:
                break
        if not changed:
            break

    return [
        beat.model_copy(update={"progress_required": compressed_progress[index]})
        for index, beat in enumerate(beats)
    ]


def _compiled_beat_runtime_shards(bundle: DesignBundle) -> list[PlayBeatRuntimeShard]:
    return [
        PlayBeatRuntimeShard(
            beat_id=item.beat_id,
            snapshot_id=item.snapshot_id,
            snapshot_version=item.snapshot_version,
            context_hash=item.context_hash,
            required_invariants=dict(item.required_invariants),
            focus_npc_ids=list(item.focus_npc_ids),
            conflict_npc_ids=list(item.conflict_npc_ids),
            pressure_axis_id=item.pressure_axis_id,
            required_truth_ids=list(item.required_truth_ids),
            required_event_ids=list(item.required_event_ids),
            route_pivot_tag=item.route_pivot_tag,
            affordance_tags=list(item.affordance_tags),
            blocked_affordances=list(item.blocked_affordances),
            progress_required=item.progress_required,
            interpret_hint_cards=[
                PlayBeatRuntimeHintCard(card_id=card.card_id, content=dict(card.content))
                for card in item.interpret_hint_cards
            ],
            render_hint_cards=[
                PlayBeatRuntimeHintCard(card_id=card.card_id, content=dict(card.content))
                for card in item.render_hint_cards
            ],
            closeout_hint_cards=[
                PlayBeatRuntimeHintCard(card_id=card.card_id, content=dict(card.content))
                for card in item.closeout_hint_cards
            ],
            fallback_reason=item.fallback_reason,
        )
        for item in list(bundle.beat_runtime_shards or [])
    ]


def compile_play_plan(*, story_id: str, bundle: DesignBundle) -> PlayPlan:
    route_pack = _compiled_route_pack(bundle)
    closeout = play_closeout_profile_from_bundle(bundle)
    runtime_policy = play_runtime_profile_from_bundle(bundle)
    author_theme = author_theme_from_bundle(bundle)
    story_flow_plan = bundle.story_flow_plan or build_story_flow_plan(
        controls=bundle.generation_controls,
        primary_theme=author_theme.primary_theme,
    )
    fallback_story = build_default_story_frame_draft(bundle.focused_brief)
    protagonist, protagonist_npc_id, protagonist_name = _compile_protagonist(bundle)
    premise = sanitize_product_story_sentence(
        bundle.story_bible.premise,
        fallback=build_product_premise_fallback(
            primary_theme=author_theme.primary_theme,
            focused_brief=bundle.focused_brief,
            prompt_seed=bundle.focused_brief.story_kernel,
            limit=320,
        )
        or fallback_story.premise,
        limit=320,
    )
    axes = _compiled_axes(bundle)
    beats = _compress_runtime_beats(bundle, story_flow_plan=story_flow_plan)
    max_turns = story_flow_plan.target_turn_count
    stances = [stance for stance in bundle.state_schema.stances if stance.npc_id != protagonist_npc_id]
    return PlayPlan(
        story_id=story_id,
        language=bundle.focused_brief.language,
        story_title=bundle.story_bible.title,
        protagonist=protagonist,
        protagonist_name=protagonist_name,
        protagonist_npc_id=protagonist_npc_id,
        closeout_profile=closeout.play_closeout_profile,
        closeout_router_reason=closeout.router_reason,
        runtime_policy_profile=runtime_policy.runtime_policy_profile,
        runtime_router_reason=runtime_policy.router_reason,
        premise=premise,
        tone=bundle.story_bible.tone,
        style_guard=bundle.story_bible.style_guard,
        cast=bundle.story_bible.cast,
        truths=bundle.story_bible.truth_catalog,
        endings=bundle.story_bible.ending_catalog,
        axes=axes,
        stances=stances,
        flags=bundle.state_schema.flags,
        beats=beats,
        beat_runtime_shards=_compiled_beat_runtime_shards(bundle),
        route_unlock_rules=route_pack.route_unlock_rules,
        ending_rules=_compiled_ending_rules(bundle),
        affordance_effect_profiles=route_pack.affordance_effect_profiles,
        available_affordance_tags=[profile.affordance_tag for profile in route_pack.affordance_effect_profiles],
        max_turns=max_turns,
        target_duration_minutes=story_flow_plan.target_duration_minutes,
        branch_budget=story_flow_plan.branch_budget,
        minimum_resolution_turn=story_flow_plan.minimum_resolution_turn,
        opening_narration=_opening_narration(bundle, protagonist=protagonist),
    )

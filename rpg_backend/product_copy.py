from __future__ import annotations

from rpg_backend.content_language import is_chinese_language, localized_text

BANNED_ZH_SURFACE_TERMS: tuple[str, ...] = (
    "token",
    "npc",
    "stakes",
    "langgraph",
    "improvisation",
)

BANNED_ZH_REGISTER_PATTERNS: tuple[str, ...] = (
    "成型方向",
    "这套游玩节奏",
    "写在中心",
    "世界质感",
    "成功来临时",
    "拽紧",
    "拧成",
    "越绷越紧",
)

_SURFACE_LABELS: dict[str, tuple[str, str]] = {
    "theme": ("Theme", "题材"),
    "tone": ("Tone", "气质"),
    "npc_count": ("NPC Count", "角色数"),
    "beat_count": ("Beat Count", "节拍数"),
    "cast_topology": ("Cast Structure", "人物布局"),
    "title": ("Working Title", "暂定标题"),
    "conflict": ("Core Conflict", "核心冲突"),
    "story_shape": ("Story Shape", "人物布局"),
    "story_premise": ("Story Premise", "故事提要"),
    "story_stakes": ("Story Stakes", "局势代价"),
    "cast_anchor": ("Cast Anchor", "关键人物"),
    "opening_beat": ("Opening Beat", "开场节拍"),
    "final_beat": ("Final Beat", "收束节拍"),
    "generation_status": ("Generation Status", "当前进度"),
    "token_budget": ("Token Budget", "生成消耗"),
}

_SURFACE_PHRASES: dict[str, tuple[str, str]] = {
    "waiting_first_model_call": ("Waiting for first model call", "正在等待首轮生成"),
    "awaiting_cast_release": ("Awaiting cast release", "人物信息稍后补齐"),
    "awaiting_beat_release": ("Awaiting beat release", "节拍信息稍后补齐"),
    "story_open_for_play": ("Open for play", "现在可试玩"),
    "play_engine_label": ("LangGraph play runtime", "试玩引擎"),
    "play_push_momentum": ("Push for momentum", "继续施压"),
}

_THEME_LABELS = {
    "legitimacy_crisis": "Legitimacy crisis",
    "logistics_quarantine_crisis": "Logistics quarantine crisis",
    "truth_record_crisis": "Truth and record crisis",
    "public_order_crisis": "Public order crisis",
    "generic_civic_crisis": "Civic crisis",
}

_THEME_LABELS_ZH = {
    "legitimacy_crisis": "公信失衡",
    "logistics_quarantine_crisis": "封线断供",
    "truth_record_crisis": "记录疑云",
    "public_order_crisis": "失序边缘",
    "generic_civic_crisis": "城市承压",
}

_TOPOLOGY_LABELS = {
    "three_slot": "3-slot pressure triangle",
    "four_slot": "4-slot civic web",
    "five_slot": "5-slot civic ensemble",
}

_TOPOLOGY_LABELS_ZH = {
    "three_slot": "三角拉扯",
    "four_slot": "四方角力",
    "five_slot": "群像棋局",
}

_STAGE_LABELS = {
    "queued": "Queued for generation",
    "running": "Starting generation",
    "resume_from_preview_checkpoint": "Resuming from preview",
    "brief_parsed": "Brief parsed",
    "brief_classified": "Theme classified",
    "story_frame_ready": "Story frame drafted",
    "theme_confirmed": "Theme confirmed",
    "cast_planned": "Cast topology planned",
    "generate_cast_members": "Drafting the cast",
    "assemble_cast": "Assembling the cast",
    "generate_beat_plan": "Mapping the major beats",
    "build_design_bundle": "Building the story package",
    "generate_route_opportunity_plan": "Planning live routes",
    "compile_route_affordance_pack": "Compiling route rules",
    "generate_ending_rules": "Preparing the endings",
    "merge_rule_pack": "Merging the rule pack",
    "repair_gameplay_semantics": "Finalizing play logic",
    "cast_ready": "Cast roster drafted",
    "beat_plan_ready": "Beat plan drafted",
    "route_ready": "Route rules compiled",
    "ending_ready": "Ending rules drafted",
    "completed": "Bundle complete",
    "failed": "Generation failed",
}

_STAGE_LABELS_ZH = {
    "queued": "排队中",
    "running": "开始生成",
    "resume_from_preview_checkpoint": "接续预览草稿",
    "brief_parsed": "种子拆解完成",
    "brief_classified": "题材归位",
    "story_frame_ready": "故事框架成型",
    "theme_confirmed": "题材锁定",
    "cast_planned": "人物关系就位",
    "generate_cast_members": "正在写出人物关系",
    "assemble_cast": "正在整理人物名单",
    "generate_beat_plan": "正在铺排主要节拍",
    "build_design_bundle": "正在拼合故事包",
    "generate_route_opportunity_plan": "正在规划可玩路线",
    "compile_route_affordance_pack": "正在串联路线规则",
    "generate_ending_rules": "正在准备结尾走向",
    "merge_rule_pack": "正在合并路线与结局规则",
    "repair_gameplay_semantics": "正在校正最终玩法逻辑",
    "cast_ready": "人物名单成型",
    "beat_plan_ready": "节拍排布完成",
    "route_ready": "路线规则就位",
    "ending_ready": "结局规则就位",
    "completed": "故事包完成",
    "failed": "生成失败",
}

_STAGE_STATUS_MESSAGES = {
    "queued": "Queued. Preparing generation graph.",
    "running": "Starting generation.",
    "resume_from_preview_checkpoint": "Loading the preview checkpoint before the full author pass continues.",
    "brief_parsed": "Brief parsed. Distilling the story kernel.",
    "brief_classified": "Theme classified. Locking the story route.",
    "story_frame_ready": "Story frame drafted. Title, premise, and stakes are set.",
    "theme_confirmed": "Theme confirmed. Strategy is locked.",
    "cast_planned": "Cast topology planned. Defining the pressure web.",
    "generate_cast_members": "Drafting the cast and the tensions between them.",
    "assemble_cast": "Assembling the cast into a usable story roster.",
    "generate_beat_plan": "Mapping the major progression through the crisis.",
    "build_design_bundle": "Building the story package from frame, cast, and beats.",
    "generate_route_opportunity_plan": "Planning where live choices can open new routes.",
    "compile_route_affordance_pack": "Connecting routes, affordances, and unlock rules.",
    "generate_ending_rules": "Preparing how the story can close.",
    "merge_rule_pack": "Merging route and ending rules into one playable pack.",
    "repair_gameplay_semantics": "Finalizing play logic and edge-case consistency.",
    "cast_ready": "Cast roster drafted. NPC tensions are in place.",
    "beat_plan_ready": "Beat plan drafted. Main progression is mapped.",
    "route_ready": "Route rules compiled. Unlock paths are wired.",
    "ending_ready": "Ending rules drafted. Outcome logic is set.",
    "completed": "Bundle complete. Story package is ready.",
    "failed": "Generation failed. Retry or inspect the error.",
}

_STAGE_STATUS_MESSAGES_ZH = {
    "queued": "已经进入队列，正在排入生成流程。",
    "running": "已经开始生成，正在拉起第一轮结果。",
    "resume_from_preview_checkpoint": "正在接续预览草稿，把完整创作流程从上次的检查点继续往下跑。",
    "brief_parsed": "故事种子已经拆开，正在提炼这次要写的核心局面。",
    "brief_classified": "题材方向已经定住，正在收束故事走向。",
    "story_frame_ready": "标题、故事提要和局势代价已经起好底。",
    "theme_confirmed": "题材方向已经锁定，后面的生成会沿这条线展开。",
    "cast_planned": "人物布局已经排开，正在把彼此之间的压力关系接实。",
    "generate_cast_members": "正在把关键人物和彼此间的张力写出来。",
    "assemble_cast": "正在把人物整理成可直接进入故事的正式名单。",
    "generate_beat_plan": "正在排出这篇故事的主要推进节拍。",
    "build_design_bundle": "正在把框架、人物和节拍拼成完整故事包。",
    "generate_route_opportunity_plan": "正在规划玩家推进时能打开哪些可玩路线。",
    "compile_route_affordance_pack": "正在把路线、行动和解锁条件接起来。",
    "generate_ending_rules": "正在准备这篇故事可能的收束方式。",
    "merge_rule_pack": "正在把路线规则和结局规则并成一套可玩的规则包。",
    "repair_gameplay_semantics": "正在做最后一轮玩法逻辑校正，补齐边角一致性。",
    "cast_ready": "关键人物已经立住，彼此之间的张力也接上了。",
    "beat_plan_ready": "主线推进已经排好，接下来把路线和收束接上。",
    "route_ready": "路线和解锁条件已经接好，故事分流开始成型。",
    "ending_ready": "结局走向已经定好，正在做最后收束。",
    "completed": "故事包已经成型，可以进入下一步。",
    "failed": "这次生成没走完，请重试或查看报错。",
}

_RUNTIME_PROFILE_LABELS_ZH = {
    "warning_record_play": "预警核验",
    "archive_vote_play": "档案表决",
    "bridge_ration_play": "桥线配给",
    "harbor_quarantine_play": "港口封线",
    "blackout_council_play": "停电议会",
    "legitimacy_compact_play": "公议博弈",
    "public_order_play": "秩序保全",
    "generic_civic_play": "城市承压",
}

_CLOSEOUT_PROFILE_LABELS_ZH = {
    "record_exposure_closeout": "记录见光",
    "logistics_cost_closeout": "代价落账",
    "legitimacy_compact_closeout": "公信妥协",
    "panic_containment_closeout": "止慌收束",
    "generic_civic_closeout": "城市收束",
}


def humanize_identifier(value: str) -> str:
    return value.replace("_", " ").strip().title()


def surface_label(key: str, *, language: str = "en") -> str:
    en, zh = _SURFACE_LABELS[key]
    return localized_text(language, en=en, zh=zh)


def surface_phrase(key: str, *, language: str = "en") -> str:
    en, zh = _SURFACE_PHRASES[key]
    return localized_text(language, en=en, zh=zh)


def theme_label(theme: str, *, language: str = "en") -> str:
    if is_chinese_language(language):
        return _THEME_LABELS_ZH.get(theme, humanize_identifier(theme))
    return _THEME_LABELS.get(theme, humanize_identifier(theme))


def topology_label(topology: str, *, language: str = "en") -> str:
    if is_chinese_language(language):
        return _TOPOLOGY_LABELS_ZH.get(topology, humanize_identifier(topology))
    return _TOPOLOGY_LABELS.get(topology, humanize_identifier(topology))


def stage_label(stage: str, language: str = "en") -> str:
    if is_chinese_language(language):
        return _STAGE_LABELS_ZH.get(stage, humanize_identifier(stage))
    return _STAGE_LABELS.get(stage, humanize_identifier(stage))


def stage_status_message(stage: str, language: str = "en") -> str:
    if is_chinese_language(language):
        return _STAGE_STATUS_MESSAGES_ZH.get(stage, stage_label(stage, language))
    return _STAGE_STATUS_MESSAGES.get(stage, stage_label(stage, language))


def runtime_profile_label(profile: str, *, language: str = "en") -> str:
    if is_chinese_language(language):
        return _RUNTIME_PROFILE_LABELS_ZH.get(profile, humanize_identifier(profile))
    return humanize_identifier(profile)


def closeout_profile_label(profile: str, *, language: str = "en") -> str:
    if is_chinese_language(language):
        return _CLOSEOUT_PROFILE_LABELS_ZH.get(profile, humanize_identifier(profile))
    return humanize_identifier(profile)


def usage_summary_text(
    *,
    language: str,
    total_tokens: int | None,
    usd_cost: float | None = None,
) -> str:
    if total_tokens is None:
        return surface_phrase("waiting_first_model_call", language=language)
    if is_chinese_language(language):
        summary = f"累计用量 {int(total_tokens)}"
        if usd_cost is not None:
            summary += f" · 预估 USD {usd_cost:.6f}"
        return summary
    summary = f"{int(total_tokens)} total tokens"
    if usd_cost is not None:
        summary += f" · USD {usd_cost:.6f} est."
    return summary

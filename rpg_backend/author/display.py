from __future__ import annotations

from datetime import datetime

from rpg_backend.content_language import is_chinese_language
from rpg_backend.author.normalize import trim_ellipsis
from rpg_backend.author.contracts import (
    AuthorCacheMetrics,
    AuthorLoadingCastPoolEntry,
    AuthorJobProgress,
    AuthorJobProgressSnapshot,
    AuthorLoadingCard,
    AuthorPreviewFlashcard,
    AuthorPreviewResponse,
    AuthorTokenCostEstimate,
)
from rpg_backend.author.progress import AUTHOR_LOADING_NODE_FLOW
from rpg_backend.product_copy import (
    stage_label,
    stage_status_message,
    surface_label,
    surface_phrase,
    theme_label,
    topology_label,
    usage_summary_text,
)

_AUTHOR_LOADING_NODE_SET = set(AUTHOR_LOADING_NODE_FLOW)
_AUTHOR_LOADING_STAGE_TOTAL = len(AUTHOR_LOADING_NODE_FLOW)

_LEGACY_CAST_READY_STAGES = {
    "cast_ready",
    "beat_plan_ready",
    "route_ready",
    "ending_ready",
    "completed",
}

_LEGACY_BEAT_READY_STAGES = {
    "beat_plan_ready",
    "route_ready",
    "ending_ready",
    "completed",
}

_LEGACY_STORY_FRAME_READY_STAGES = {
    "story_frame_ready",
    "theme_confirmed",
    "cast_planned",
    "cast_ready",
    "beat_plan_ready",
    "route_ready",
    "ending_ready",
    "completed",
}


def _uses_author_loading_node_progress(progress: AuthorJobProgress) -> bool:
    return progress.stage_total == _AUTHOR_LOADING_STAGE_TOTAL and (
        progress.stage in _AUTHOR_LOADING_NODE_SET or progress.stage in {"completed", "failed"}
    )


def _completed_author_loading_nodes(progress: AuthorJobProgress) -> int | None:
    if not _uses_author_loading_node_progress(progress):
        return None
    return max(0, min(progress.stage_index, _AUTHOR_LOADING_STAGE_TOTAL))


def _story_frame_cards_ready(progress: AuthorJobProgress) -> bool:
    completed_nodes = _completed_author_loading_nodes(progress)
    if completed_nodes is not None:
        return True
    return progress.stage in _LEGACY_STORY_FRAME_READY_STAGES


def _cast_cards_ready(progress: AuthorJobProgress) -> bool:
    completed_nodes = _completed_author_loading_nodes(progress)
    if completed_nodes is not None:
        return completed_nodes >= 2
    return progress.stage in _LEGACY_CAST_READY_STAGES


def _cast_pool_ready(progress: AuthorJobProgress) -> bool:
    completed_nodes = _completed_author_loading_nodes(progress)
    if completed_nodes is not None:
        return completed_nodes >= 3
    return progress.stage in _LEGACY_CAST_READY_STAGES


def _beat_cards_ready(progress: AuthorJobProgress) -> bool:
    completed_nodes = _completed_author_loading_nodes(progress)
    if completed_nodes is not None:
        return completed_nodes >= 4
    return progress.stage in _LEGACY_BEAT_READY_STAGES


def _effective_loading_stage(progress: AuthorJobProgress, running_node: str | None) -> str:
    if _uses_author_loading_node_progress(progress) and running_node in _AUTHOR_LOADING_NODE_SET:
        return running_node
    return progress.stage


def _cast_generation_partial(
    *,
    running_substage: str | None,
    running_slot_index: int | None,
    running_slot_total: int | None,
) -> float:
    if running_substage == "roster_retrieval":
        return 0.12
    if running_substage == "batch_generate_remaining_cast":
        return 0.45
    if running_substage in {"roster_projection", "slot_generate", "slot_repair", "deterministic_fallback"}:
        if running_slot_index is None or running_slot_total is None or running_slot_total <= 0:
            return 0.2
        return max(0.15, min(running_slot_index / running_slot_total, 0.92))
    return 0.0


def _beat_plan_partial(running_substage: str | None) -> float:
    if running_substage == "beat_plan_generate":
        return 0.4
    if running_substage == "beat_plan_repair":
        return 0.72
    if running_substage == "beat_plan_default_fallback":
        return 0.9
    return 0.0


def _ending_partial(running_substage: str | None) -> float:
    if running_substage == "ending_generate":
        return 0.4
    if running_substage == "ending_repair":
        return 0.72
    if running_substage == "ending_default_fallback":
        return 0.9
    return 0.0


def _completion_ratio(
    *,
    progress: AuthorJobProgress,
    stage: str,
    running_substage: str | None,
    running_slot_index: int | None,
    running_slot_total: int | None,
) -> float:
    if _uses_author_loading_node_progress(progress):
        completed_nodes = _completed_author_loading_nodes(progress) or 0
        if stage == "completed":
            return 1.0
        partial = 0.0
        if stage == "generate_cast_members" and completed_nodes <= 1:
            partial = _cast_generation_partial(
                running_substage=running_substage,
                running_slot_index=running_slot_index,
                running_slot_total=running_slot_total,
            )
        elif stage == "generate_beat_plan" and completed_nodes <= 4:
            partial = _beat_plan_partial(running_substage)
        elif stage == "generate_ending_rules" and completed_nodes <= 8:
            partial = _ending_partial(running_substage)
        return round(min((completed_nodes + partial) / _AUTHOR_LOADING_STAGE_TOTAL, 1.0), 3)
    if progress.stage_total <= 0:
        return 0.0
    return round(min(progress.stage_index / progress.stage_total, 1.0), 3)


def _running_slot_progress_text(slot_index: int | None, slot_total: int | None, *, language: str) -> str | None:
    if slot_index is None or slot_total is None or slot_total <= 0:
        return None
    if is_chinese_language(language):
        return f"第 {slot_index}/{slot_total} 名角色"
    return f"character {slot_index}/{slot_total}"


def _running_stage_label(
    *,
    stage: str,
    language: str,
    running_substage: str | None,
    running_slot_index: int | None,
    running_slot_total: int | None,
) -> str:
    base = stage_label(stage, language)
    slot_progress = _running_slot_progress_text(running_slot_index, running_slot_total, language=language)
    if running_substage == "story_frame_generate":
        return "正在搭建故事框架" if is_chinese_language(language) else "Drafting the story frame"
    if running_substage == "story_frame_repair":
        return "正在修补故事框架" if is_chinese_language(language) else "Repairing the story frame"
    if running_substage == "story_frame_default_fallback":
        return "故事框架转入兜底" if is_chinese_language(language) else "Story frame fallback"
    if running_substage == "theme_route_lock":
        return "正在锁定题材方向" if is_chinese_language(language) else "Locking the theme route"
    if running_substage == "cast_topology_plan":
        return "正在规划人物拓扑" if is_chinese_language(language) else "Planning cast topology"
    if running_substage == "cast_overview_compile":
        return "正在编排人物关系" if is_chinese_language(language) else "Compiling cast overview"
    if running_substage == "roster_retrieval":
        return "正在匹配角色模板" if is_chinese_language(language) else "Matching cast templates"
    if running_substage == "roster_projection":
        if slot_progress:
            return (
                f"正在落定人物关系 · {slot_progress}"
                if is_chinese_language(language)
                else f"Projecting roster cast · {slot_progress}"
            )
        return "正在落定人物关系" if is_chinese_language(language) else "Projecting roster cast"
    if running_substage == "batch_generate_remaining_cast":
        if slot_progress:
            return (
                f"正在批量写出人物网络 · {slot_progress}"
                if is_chinese_language(language)
                else f"Drafting cast batch · {slot_progress}"
            )
        return "正在批量写出人物网络" if is_chinese_language(language) else "Drafting cast batch"
    if running_substage == "slot_repair":
        if slot_progress:
            return (
                f"正在修补人物关系 · {slot_progress}"
                if is_chinese_language(language)
                else f"Repairing cast slot · {slot_progress}"
            )
        return "正在修补人物关系" if is_chinese_language(language) else "Repairing cast slot"
    if running_substage in {"slot_generate", "deterministic_fallback"} and slot_progress:
        return (
            f"正在勾勒人物关系 · {slot_progress}"
            if is_chinese_language(language)
            else f"Sketching the cast web · {slot_progress}"
        )
    if running_substage == "beat_plan_generate":
        return "正在铺排剧情节拍" if is_chinese_language(language) else "Drafting the beat plan"
    if running_substage == "beat_plan_repair":
        return "正在修补剧情节拍" if is_chinese_language(language) else "Repairing the beat plan"
    if running_substage == "beat_plan_default_fallback":
        return "节拍转入兜底" if is_chinese_language(language) else "Beat plan fallback"
    if running_substage == "route_generate":
        return "正在生成路线规则" if is_chinese_language(language) else "Generating route rules"
    if running_substage == "route_compile":
        return "正在连接路线规则" if is_chinese_language(language) else "Compiling route rules"
    if running_substage == "route_default_fallback":
        return "路线转入兜底" if is_chinese_language(language) else "Route fallback"
    if running_substage == "ending_generate":
        return "正在准备结局规则" if is_chinese_language(language) else "Generating ending rules"
    if running_substage == "ending_repair":
        return "正在修补结局规则" if is_chinese_language(language) else "Repairing ending rules"
    if running_substage == "ending_default_fallback":
        return "结局转入兜底" if is_chinese_language(language) else "Ending fallback"
    return base


def _running_stage_message(
    *,
    stage: str,
    language: str,
    running_substage: str | None,
    running_slot_index: int | None,
    running_slot_total: int | None,
    running_slot_label: str | None,
    running_capability: str | None,
    running_elapsed_ms: int | None,
) -> str:
    slot_text = _running_slot_progress_text(running_slot_index, running_slot_total, language=language)
    slot_label = trim_ellipsis(str(running_slot_label or "").strip(), 40) or None
    elapsed_seconds = (running_elapsed_ms or 0) / 1000
    capability_text = str(running_capability or "").strip() or None
    if running_substage == "story_frame_generate":
        base = (
            "正在根据当前种子搭建标题、故事提要和核心局势。"
            if is_chinese_language(language)
            else "Drafting the title, premise, and core stakes from the current seed."
        )
    elif running_substage == "story_frame_repair":
        base = (
            "第一版故事框架不够稳，正在修补结构和语义锚点。"
            if is_chinese_language(language)
            else "The first story-frame pass was unstable, so the system is repairing its structure and semantic anchors."
        )
    elif running_substage == "story_frame_default_fallback":
        return (
            "故事框架生成不稳定，正在切回默认框架继续推进。"
            if is_chinese_language(language)
            else "Story-frame generation was unstable, so the flow is falling back to the default scaffold."
        )
    elif running_substage == "theme_route_lock":
        return (
            "正在把故事锁到当前最合适的题材方向上。"
            if is_chinese_language(language)
            else "Locking the story into the most suitable theme direction."
        )
    elif running_substage == "cast_topology_plan":
        return (
            "正在决定这篇故事需要几位关键人物，以及他们如何形成拉扯。"
            if is_chinese_language(language)
            else "Deciding how many core characters the story needs and how they should tension each other."
        )
    elif running_substage == "cast_overview_compile":
        return (
            "正在把人物槽位、关系摘要和冲突职责编排成可生成的 cast 结构。"
            if is_chinese_language(language)
            else "Compiling cast slots, relationship summaries, and conflict roles into a generatable cast overview."
        )
    if running_substage == "roster_retrieval":
        return (
            "正在从角色模板库里匹配最合适的人物。"
            if is_chinese_language(language)
            else "Matching the best roster-backed characters for the cast."
        )
    if running_substage == "roster_projection":
        return (
            f"正在用角色模板直接落定{slot_text or '当前角色'}{f'（{slot_label}）' if slot_label else ''}。"
            if is_chinese_language(language)
            else f"Projecting {slot_text or 'the current cast slot'}{f' ({slot_label})' if slot_label else ''} directly from the roster template."
        )
    if running_substage == "batch_generate_remaining_cast":
        base = (
            "正在一次性生成剩余角色，避免逐个串行等待。"
            if is_chinese_language(language)
            else "Generating the remaining cast in one batch instead of slot-by-slot."
        )
    elif running_substage == "slot_repair":
        base = (
            f"正在修补{slot_text or '当前角色'}{f'（{slot_label}）' if slot_label else ''}。"
            if is_chinese_language(language)
            else f"Repairing {slot_text or 'the current cast slot'}{f' ({slot_label})' if slot_label else ''}."
        )
    elif running_substage == "deterministic_fallback":
        base = (
            "模型响应过慢或不稳定，正在用确定性兜底补齐剩余角色。"
            if is_chinese_language(language)
            else "The model path is too slow or unstable, so deterministic fallback is filling the remaining cast."
        )
    elif running_substage == "beat_plan_generate":
        base = (
            "正在把故事推进拆成可游玩的节拍。"
            if is_chinese_language(language)
            else "Turning the story into playable beats."
        )
    elif running_substage == "beat_plan_repair":
        base = (
            "节拍初稿不够稳，正在修补推进顺序和关键转折。"
            if is_chinese_language(language)
            else "The first beat plan was unstable, so progression order and turning points are being repaired."
        )
    elif running_substage == "beat_plan_default_fallback":
        return (
            "节拍生成不稳定，正在切回默认节拍继续收尾。"
            if is_chinese_language(language)
            else "Beat generation was unstable, so the flow is falling back to the default beat plan."
        )
    elif running_substage == "route_generate":
        base = (
            "正在生成路线机会和解锁条件。"
            if is_chinese_language(language)
            else "Generating route opportunities and unlock conditions."
        )
    elif running_substage == "route_compile":
        return (
            "正在把路线机会编译成正式规则。"
            if is_chinese_language(language)
            else "Compiling route opportunities into formal rules."
        )
    elif running_substage == "route_default_fallback":
        return (
            "路线规则不够稳，正在切回默认路线逻辑继续推进。"
            if is_chinese_language(language)
            else "Route logic was unstable, so the flow is falling back to default route rules."
        )
    elif running_substage == "ending_generate":
        base = (
            "正在准备结局锚点和收束条件。"
            if is_chinese_language(language)
            else "Preparing ending anchors and closeout conditions."
        )
    elif running_substage == "ending_repair":
        base = (
            "结局规则初稿不够稳，正在修补收束逻辑。"
            if is_chinese_language(language)
            else "The first ending pass was unstable, so closeout logic is being repaired."
        )
    elif running_substage == "ending_default_fallback":
        return (
            "结局规则不稳定，正在切回默认结局逻辑完成草稿。"
            if is_chinese_language(language)
            else "Ending generation was unstable, so the flow is falling back to default ending logic."
        )
    else:
        if running_substage is None:
            return stage_status_message(stage, language)
        base = (
            f"正在生成{slot_text or '当前角色'}{f'（{slot_label}）' if slot_label else ''}。"
            if is_chinese_language(language)
            else f"Generating {slot_text or 'the current cast slot'}{f' ({slot_label})' if slot_label else ''}."
        )
    if capability_text:
        if is_chinese_language(language):
            return f"{base} 当前调用：{capability_text} · 已等待 {elapsed_seconds:.1f}s"
        return f"{base} Active capability: {capability_text} · waiting {elapsed_seconds:.1f}s"
    return base


def cast_count_value(is_ready: bool, expected_npc_count: int, *, language: str = "en") -> str:
    if is_chinese_language(language):
        status = "名角色已落位" if is_ready else "名角色已排定"
        return f"{expected_npc_count} {status}"
    status = "NPCs drafted" if is_ready else "planned NPCs"
    return f"{expected_npc_count} {status}"


def beat_count_value(is_ready: bool, expected_beat_count: int, *, language: str = "en") -> str:
    if is_chinese_language(language):
        status = "段主节拍已成型" if is_ready else "段主节拍已排定"
        return f"{expected_beat_count} {status}"
    status = "beats drafted" if is_ready else "planned beats"
    return f"{expected_beat_count} {status}"


def build_preview_flashcards(
    *,
    language: str,
    theme: str,
    tone: str,
    cast_topology: str,
    expected_npc_count: int,
    expected_beat_count: int,
    title: str,
    conflict: str,
) -> list[AuthorPreviewFlashcard]:
    return [
        AuthorPreviewFlashcard(card_id="theme", kind="stable", label=surface_label("theme", language=language), value=theme_label(theme, language=language)),
        AuthorPreviewFlashcard(card_id="tone", kind="stable", label=surface_label("tone", language=language), value=tone),
        AuthorPreviewFlashcard(card_id="npc_count", kind="stable", label=surface_label("npc_count", language=language), value=str(expected_npc_count)),
        AuthorPreviewFlashcard(card_id="beat_count", kind="stable", label=surface_label("beat_count", language=language), value=str(expected_beat_count)),
        AuthorPreviewFlashcard(card_id="cast_topology", kind="stable", label=surface_label("cast_topology", language=language), value=topology_label(cast_topology, language=language)),
        AuthorPreviewFlashcard(card_id="title", kind="draft", label=surface_label("title", language=language), value=title),
        AuthorPreviewFlashcard(card_id="conflict", kind="draft", label=surface_label("conflict", language=language), value=conflict),
    ]


def build_loading_cards(
    *,
    preview: AuthorPreviewResponse,
    progress: AuthorJobProgress,
    token_usage: AuthorCacheMetrics,
    token_cost_estimate: AuthorTokenCostEstimate | None,
    running_substage: str | None = None,
    running_slot_index: int | None = None,
    running_slot_total: int | None = None,
    running_slot_label: str | None = None,
    running_capability: str | None = None,
    running_elapsed_ms: int | None = None,
    running_node: str | None = None,
) -> list[AuthorLoadingCard]:
    display_stage = _effective_loading_stage(progress, running_node)
    cards: list[AuthorLoadingCard] = [
        AuthorLoadingCard(card_id="theme", emphasis="stable", label=surface_label("theme", language=preview.language), value=theme_label(preview.theme.primary_theme, language=preview.language)),
        AuthorLoadingCard(
            card_id="structure",
            emphasis="stable",
            label=surface_label("story_shape", language=preview.language),
            value=topology_label(preview.structure.cast_topology, language=preview.language),
        ),
    ]
    usd_cost = None
    if token_usage.total_tokens is not None and token_cost_estimate is not None:
        from rpg_backend.config import get_settings

        usd_cost = token_cost_estimate.estimated_total_cost_rmb * get_settings().resolved_gateway_usd_per_rmb()
    budget_value = usage_summary_text(
        language=preview.language,
        total_tokens=token_usage.total_tokens,
        usd_cost=usd_cost,
    )
    if _story_frame_cards_ready(progress):
        cards.extend(
            [
                AuthorLoadingCard(
                    card_id="working_title",
                    emphasis="draft",
                    label=surface_label("title", language=preview.language),
                    value=preview.story.title,
                ),
                AuthorLoadingCard(
                    card_id="tone",
                    emphasis="stable",
                    label=surface_label("tone", language=preview.language),
                    value=preview.story.tone,
                ),
                AuthorLoadingCard(
                    card_id="story_premise",
                    emphasis="draft",
                    label=surface_label("story_premise", language=preview.language),
                    value=trim_ellipsis(preview.story.premise, 220),
                ),
                AuthorLoadingCard(
                    card_id="story_stakes",
                    emphasis="draft",
                    label=surface_label("story_stakes", language=preview.language),
                    value=trim_ellipsis(preview.story.stakes, 220),
                ),
            ]
        )
    if _cast_cards_ready(progress):
        anchor = preview.cast_slots[0] if preview.cast_slots else None
        cards.extend(
            [
                AuthorLoadingCard(
                    card_id="cast_count",
                    emphasis="stable",
                    label=surface_label("npc_count", language=preview.language),
                    value=cast_count_value(True, preview.structure.expected_npc_count, language=preview.language),
                ),
                AuthorLoadingCard(
                    card_id="cast_anchor",
                    emphasis="draft",
                    label=surface_label("cast_anchor", language=preview.language),
                    value=trim_ellipsis(
                        (
                            f"{anchor.slot_label} · {anchor.public_role}"
                            if anchor is not None
                            else surface_phrase("awaiting_cast_release", language=preview.language)
                        ),
                        220,
                    ),
                ),
            ]
        )
    if _beat_cards_ready(progress):
        opening_beat = preview.beats[0] if preview.beats else None
        final_beat = preview.beats[-1] if preview.beats else None
        cards.extend(
            [
                AuthorLoadingCard(
                    card_id="beat_count",
                    emphasis="stable",
                    label=surface_label("beat_count", language=preview.language),
                    value=beat_count_value(True, preview.structure.expected_beat_count, language=preview.language),
                ),
                AuthorLoadingCard(
                    card_id="opening_beat",
                    emphasis="draft",
                    label=surface_label("opening_beat", language=preview.language),
                    value=trim_ellipsis(
                        (
                            f"{opening_beat.title}: {opening_beat.goal}"
                            if opening_beat is not None
                            else surface_phrase("awaiting_beat_release", language=preview.language)
                        ),
                        220,
                    ),
                ),
                AuthorLoadingCard(
                    card_id="final_beat",
                    emphasis="draft",
                    label=surface_label("final_beat", language=preview.language),
                    value=trim_ellipsis(
                        (
                            f"{final_beat.title}: {final_beat.goal}"
                            if final_beat is not None
                            else surface_phrase("awaiting_beat_release", language=preview.language)
                        ),
                        220,
                    ),
                ),
            ]
        )
    cards.extend(
        [
            AuthorLoadingCard(
                card_id="generation_status",
                emphasis="live",
                label=surface_label("generation_status", language=preview.language),
                value=trim_ellipsis(
                    _running_stage_message(
                        stage=display_stage,
                        language=preview.language,
                        running_substage=running_substage,
                        running_slot_index=running_slot_index,
                        running_slot_total=running_slot_total,
                        running_slot_label=running_slot_label,
                        running_capability=running_capability,
                        running_elapsed_ms=running_elapsed_ms,
                    ),
                    220,
                ),
            ),
            AuthorLoadingCard(
                card_id="token_budget",
                emphasis="live",
                label=surface_label("token_budget", language=preview.language),
                value=budget_value,
            ),
        ]
    )
    return cards


def build_loading_cast_pool(
    *,
    preview: AuthorPreviewResponse,
    progress: AuthorJobProgress,
) -> list[AuthorLoadingCastPoolEntry]:
    if not _cast_pool_ready(progress):
        return []
    entries: list[AuthorLoadingCastPoolEntry] = []
    for slot in preview.cast_slots:
        npc_id = str(slot.npc_id or "").strip()
        name = str(slot.name or slot.slot_label or "").strip()
        if not npc_id or not name:
            continue
        entries.append(
            AuthorLoadingCastPoolEntry(
                npc_id=npc_id,
                name=name,
                role=slot.public_role,
                roster_character_id=slot.roster_character_id,
                roster_public_summary=slot.roster_public_summary,
                portrait_url=slot.portrait_url,
                portrait_variants=slot.portrait_variants,
                template_version=slot.template_version,
            )
        )
    return entries


def build_progress_snapshot(
    *,
    preview: AuthorPreviewResponse,
    progress: AuthorJobProgress,
    token_usage: AuthorCacheMetrics,
    token_cost_estimate: AuthorTokenCostEstimate | None,
    running_node: str | None = None,
    running_substage: str | None = None,
    running_slot_index: int | None = None,
    running_slot_total: int | None = None,
    running_slot_label: str | None = None,
    running_capability: str | None = None,
    running_elapsed_ms: int | None = None,
) -> AuthorJobProgressSnapshot:
    display_stage = _effective_loading_stage(progress, running_node)
    completion_ratio = _completion_ratio(
        progress=progress,
        stage=display_stage,
        running_substage=running_substage,
        running_slot_index=running_slot_index,
        running_slot_total=running_slot_total,
    )
    return AuthorJobProgressSnapshot(
        stage=display_stage,
        stage_label=trim_ellipsis(
            _running_stage_label(
                stage=display_stage,
                language=preview.language,
                running_substage=running_substage,
                running_slot_index=running_slot_index,
                running_slot_total=running_slot_total,
            ),
            120,
        ),
        stage_index=progress.stage_index,
        stage_total=progress.stage_total,
        completion_ratio=round(completion_ratio, 3),
        primary_theme=preview.theme.primary_theme,
        cast_topology=preview.structure.cast_topology,
        expected_npc_count=preview.structure.expected_npc_count,
        expected_beat_count=preview.structure.expected_beat_count,
        preview_title=preview.story.title,
        preview_premise=preview.story.premise,
        stage_message=trim_ellipsis(
            _running_stage_message(
                stage=display_stage,
                language=preview.language,
                running_substage=running_substage,
                running_slot_index=running_slot_index,
                running_slot_total=running_slot_total,
                running_slot_label=running_slot_label,
                running_capability=running_capability,
                running_elapsed_ms=running_elapsed_ms,
            ),
            240,
        ),
        flashcards=list(preview.flashcards),
        loading_cards=build_loading_cards(
            preview=preview,
            progress=progress,
            token_usage=token_usage,
            token_cost_estimate=token_cost_estimate,
            running_substage=running_substage,
            running_slot_index=running_slot_index,
            running_slot_total=running_slot_total,
            running_slot_label=running_slot_label,
            running_capability=running_capability,
            running_elapsed_ms=running_elapsed_ms,
            running_node=running_node,
        ),
        cast_pool=build_loading_cast_pool(preview=preview, progress=progress),
        running_node=running_node,
        running_substage=running_substage,
        running_slot_index=running_slot_index,
        running_slot_total=running_slot_total,
        running_slot_label=running_slot_label,
        running_capability=running_capability,
        running_elapsed_ms=running_elapsed_ms,
    )

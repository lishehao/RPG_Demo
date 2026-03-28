from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from rpg_backend.author.contracts import (
    CastOverviewDraft,
    CastOverviewSlotDraft,
    FocusedBrief,
    StoryFrameDraft,
)
from rpg_backend.roster.contracts import (
    CharacterRosterEntry,
    CharacterRosterSelectionResult,
    RetrievedRosterCharacter,
    RosterSelectionMode,
    RosterSlotTag,
)
from rpg_backend.character_knowledge.contracts import CharacterKnowledgeError
from rpg_backend.character_knowledge.retriever import CharacterKnowledgeRetriever
from rpg_backend.roster.embeddings import CharacterEmbeddingProvider

_EXACT_SLOT_WEIGHT = 4.0
_GENERIC_CIVIC_BACKFILL_WEIGHT = 1.0
_THEME_WEIGHT = 5.0
_SETTING_WEIGHT = 1.5
_CONFLICT_WEIGHT = 1.25
_TONE_WEIGHT = 0.75
_RETRIEVAL_TERMS_WEIGHT = 2.0
_STORY_EMBEDDING_WEIGHT = 2.0
_SLOT_EMBEDDING_WEIGHT = 3.0
_TOP_K_CANDIDATES = 5
_POSITIVE_EMBEDDING_THRESHOLD = 0.05


def build_story_query_text(
    *,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    primary_theme: str,
) -> str:
    return " ".join(
        [
            focused_brief.story_kernel,
            focused_brief.setting_signal,
            focused_brief.core_conflict,
            story_frame.title,
            story_frame.premise,
            story_frame.tone,
            story_frame.stakes,
            primary_theme,
        ]
    )


def build_slot_query_text(slot: CastOverviewSlotDraft) -> str:
    return " ".join(
        [
            slot.slot_label,
            slot.public_role,
            slot.agenda_anchor,
            slot.red_line_anchor,
            slot.pressure_vector,
            slot.archetype_id or "",
        ]
    )


def slot_tag_for_slot(slot: CastOverviewSlotDraft) -> RosterSlotTag:
    text = f"{slot.slot_label} {slot.public_role} {slot.archetype_id or ''}".casefold()
    if any(token in text for token in ("mediator", "anchor", "player", "envoy", "inspector", "protagonist", "调停", "检察官", "工程官", "核验官", "协调员")):
        return "anchor"
    if any(token in text for token in ("guardian", "authority", "archive", "curator", "scribe", "warden", "认证", "文员", "机构", "守门")):
        return "guardian"
    if any(token in text for token in ("broker", "rival", "opposition", "merchant", "bloc", "掮客", "商会", " rival")):
        return "broker"
    if any(token in text for token in ("witness", "delegate", "public", "gallery", "工会", "见证", "代表", "证人")):
        return "witness"
    return "civic"


def _keyword_score(haystack: str, keywords: tuple[str, ...]) -> float:
    lowered = haystack.casefold()
    return float(sum(1 for keyword in keywords if keyword.casefold() in lowered))


def _cosine_similarity(left: list[float] | None, right: tuple[float, ...] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _weighted_embedding_score(
    *,
    query_embedding: list[float] | None,
    entry_embedding: tuple[float, ...] | None,
    weight: float,
) -> float:
    similarity = _cosine_similarity(query_embedding, entry_embedding)
    if similarity <= _POSITIVE_EMBEDDING_THRESHOLD:
        return 0.0
    return similarity * weight


def _top_candidate_payload(candidate: "_RankedRosterCandidate") -> dict[str, object]:
    return {
        "rank": candidate.pool_rank,
        "character_id": candidate.entry.character_id,
        "template_version": candidate.entry.template_version or candidate.entry.source_fingerprint,
        "score": round(candidate.total_score, 6),
        "score_breakdown": candidate.score_breakdown,
    }


@dataclass(frozen=True)
class _RankedRosterCandidate:
    slot_index: int
    slot_tag: RosterSlotTag
    entry: CharacterRosterEntry
    total_score: float
    score_breakdown: dict[str, float]
    pool_rank: int


@dataclass(frozen=True)
class _SlotCandidatePool:
    slot_index: int
    slot_tag: RosterSlotTag
    story_query_text: str
    slot_query_text: str
    query_language: str
    selection_mode: RosterSelectionMode
    embedding_reason: str | None
    candidate_pool_size: int
    candidates: tuple[_RankedRosterCandidate, ...]


@dataclass(frozen=True)
class _AssignmentState:
    candidates: tuple[_RankedRosterCandidate, ...]
    total_score: float
    exact_slot_total: float
    retrieval_terms_total: float


def _resolve_story_embedding(
    *,
    query_text: str,
    embedding_provider: CharacterEmbeddingProvider,
    catalog_has_embeddings: bool,
) -> tuple[list[float] | None, str | None]:
    if not catalog_has_embeddings:
        return None, "embedding_query_unavailable"
    try:
        embedding = embedding_provider.embed_text(query_text)
    except Exception:  # noqa: BLE001
        return None, "story_embedding_query_failed"
    if embedding is None:
        return None, "embedding_query_unavailable"
    return embedding, None


def _resolve_slot_embedding(
    *,
    query_text: str,
    embedding_provider: CharacterEmbeddingProvider,
    catalog_has_embeddings: bool,
) -> tuple[list[float] | None, str | None]:
    if not catalog_has_embeddings:
        return None, "embedding_query_unavailable"
    try:
        embedding = embedding_provider.embed_text(query_text)
    except Exception:  # noqa: BLE001
        return None, "slot_embedding_query_failed"
    if embedding is None:
        return None, "embedding_query_unavailable"
    return embedding, None


def _selection_mode(
    *,
    catalog_has_embeddings: bool,
    story_embedding: list[float] | None,
    slot_embedding: list[float] | None,
) -> RosterSelectionMode:
    if catalog_has_embeddings and (story_embedding is not None or slot_embedding is not None):
        return "embedding+lexical"
    return "lexical_only"


def _embedding_reason(
    *,
    selection_mode: RosterSelectionMode,
    story_embedding_reason: str | None,
    slot_embedding_reason: str | None,
) -> str | None:
    if selection_mode == "lexical_only" and (
        story_embedding_reason == "story_embedding_query_failed"
        or slot_embedding_reason == "slot_embedding_query_failed"
    ):
        return "embedding_query_failed"
    if slot_embedding_reason == "slot_embedding_query_failed":
        return slot_embedding_reason
    if story_embedding_reason == "story_embedding_query_failed":
        return story_embedding_reason
    if selection_mode == "lexical_only":
        return "embedding_query_unavailable"
    return None


def _rank_candidates_for_slot(
    *,
    slot_index: int,
    slot: CastOverviewSlotDraft,
    story_query_text: str,
    query_language: str,
    catalog: tuple[CharacterRosterEntry, ...],
    primary_theme: str,
    story_embedding: list[float] | None,
    slot_embedding: list[float] | None,
    selection_mode: RosterSelectionMode,
    embedding_reason: str | None,
) -> _SlotCandidatePool:
    slot_tag = slot_tag_for_slot(slot)
    slot_query_text = build_slot_query_text(slot)
    scored: list[tuple[float, CharacterRosterEntry, dict[str, float]]] = []
    for entry in catalog:
        exact_slot = _EXACT_SLOT_WEIGHT if slot_tag in entry.slot_tags else 0.0
        civic_backfill = (
            _GENERIC_CIVIC_BACKFILL_WEIGHT
            if exact_slot == 0.0 and "civic" in entry.slot_tags
            else 0.0
        )
        theme = _THEME_WEIGHT if primary_theme in entry.theme_tags else 0.0
        setting = _keyword_score(story_query_text, entry.setting_tags) * _SETTING_WEIGHT
        conflict = _keyword_score(story_query_text, entry.conflict_tags) * _CONFLICT_WEIGHT
        tone = _keyword_score(story_query_text, entry.tone_tags) * _TONE_WEIGHT
        retrieval_terms = _keyword_score(slot_query_text, entry.retrieval_terms) * _RETRIEVAL_TERMS_WEIGHT
        story_embedding_score = _weighted_embedding_score(
            query_embedding=story_embedding,
            entry_embedding=entry.embedding_vector,
            weight=_STORY_EMBEDDING_WEIGHT,
        )
        slot_embedding_score = _weighted_embedding_score(
            query_embedding=slot_embedding,
            entry_embedding=entry.embedding_vector,
            weight=_SLOT_EMBEDDING_WEIGHT,
        )
        has_positive_signal = any(
            score > 0.0
            for score in (
                exact_slot,
                civic_backfill,
                theme,
                setting,
                conflict,
                retrieval_terms,
                story_embedding_score,
                slot_embedding_score,
            )
        )
        if not has_positive_signal:
            continue
        breakdown = {
            "theme": round(theme, 6),
            "exact_slot": round(exact_slot, 6),
            "generic_civic_backfill": round(civic_backfill, 6),
            "setting": round(setting, 6),
            "conflict": round(conflict, 6),
            "tone": round(tone, 6),
            "retrieval_terms": round(retrieval_terms, 6),
            "story_embedding": round(story_embedding_score, 6),
            "slot_embedding": round(slot_embedding_score, 6),
            "rarity": round(entry.rarity_weight, 6),
        }
        total_score = round(sum(breakdown.values()), 6)
        breakdown["total"] = total_score
        scored.append((total_score, entry, breakdown))
    scored.sort(
        key=lambda item: (
            -item[0],
            -item[2]["exact_slot"],
            -item[2]["retrieval_terms"],
            item[1].character_id,
        )
    )
    ranked_candidates = tuple(
        _RankedRosterCandidate(
            slot_index=slot_index,
            slot_tag=slot_tag,
            entry=entry,
            total_score=score,
            score_breakdown=breakdown,
            pool_rank=rank,
        )
        for rank, (score, entry, breakdown) in enumerate(scored[:_TOP_K_CANDIDATES], start=1)
    )
    return _SlotCandidatePool(
        slot_index=slot_index,
        slot_tag=slot_tag,
        story_query_text=story_query_text,
        slot_query_text=slot_query_text,
        query_language=query_language,
        selection_mode=selection_mode,
        embedding_reason=embedding_reason,
        candidate_pool_size=len(scored),
        candidates=ranked_candidates,
    )


def _is_better_assignment(candidate: _AssignmentState, incumbent: _AssignmentState | None) -> bool:
    if incumbent is None:
        return True
    candidate_total = round(candidate.total_score, 6)
    incumbent_total = round(incumbent.total_score, 6)
    if candidate_total != incumbent_total:
        return candidate_total > incumbent_total
    if len(candidate.candidates) != len(incumbent.candidates):
        return len(candidate.candidates) > len(incumbent.candidates)
    candidate_exact = round(candidate.exact_slot_total, 6)
    incumbent_exact = round(incumbent.exact_slot_total, 6)
    if candidate_exact != incumbent_exact:
        return candidate_exact > incumbent_exact
    candidate_terms = round(candidate.retrieval_terms_total, 6)
    incumbent_terms = round(incumbent.retrieval_terms_total, 6)
    if candidate_terms != incumbent_terms:
        return candidate_terms > incumbent_terms
    candidate_ids = tuple(sorted(item.entry.character_id for item in candidate.candidates))
    incumbent_ids = tuple(sorted(item.entry.character_id for item in incumbent.candidates))
    return candidate_ids < incumbent_ids


def _solve_global_assignment(
    *,
    pools: tuple[_SlotCandidatePool, ...],
    limit: int,
) -> tuple[_RankedRosterCandidate, ...]:
    if limit <= 0 or not pools:
        return ()
    best: _AssignmentState | None = None

    def walk(index: int, chosen: tuple[_RankedRosterCandidate, ...], used_character_ids: frozenset[str]) -> None:
        nonlocal best
        if index >= len(pools):
            state = _AssignmentState(
                candidates=chosen,
                total_score=sum(item.total_score for item in chosen),
                exact_slot_total=sum(item.score_breakdown["exact_slot"] for item in chosen),
                retrieval_terms_total=sum(item.score_breakdown["retrieval_terms"] for item in chosen),
            )
            if _is_better_assignment(state, best):
                best = state
            return
        pool = pools[index]
        walk(index + 1, chosen, used_character_ids)
        if len(chosen) >= limit:
            return
        for candidate in pool.candidates:
            if candidate.entry.character_id in used_character_ids:
                continue
            walk(
                index + 1,
                chosen + (candidate,),
                used_character_ids | {candidate.entry.character_id},
            )

    walk(0, (), frozenset())
    return best.candidates if best is not None else ()


def retrieve_roster_assignments(
    *,
    enabled: bool,
    catalog_version: str | None,
    catalog: tuple[CharacterRosterEntry, ...],
    embedding_provider: CharacterEmbeddingProvider,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    cast_overview: CastOverviewDraft,
    primary_theme: str,
    limit: int,
    knowledge_retriever: CharacterKnowledgeRetriever | None = None,
    story_frame_strategy: str | None = None,
) -> CharacterRosterSelectionResult:
    if not enabled:
        return CharacterRosterSelectionResult(
            roster_enabled=False,
            catalog_version=None,
            assignments=(),
            trace=(),
        )
    if limit <= 0:
        return CharacterRosterSelectionResult(
            roster_enabled=True,
            catalog_version=catalog_version,
            assignments=(),
            trace=(),
        )
    story_query_text = build_story_query_text(
        focused_brief=focused_brief,
        story_frame=story_frame,
        primary_theme=primary_theme,
    )
    catalog_has_embeddings = knowledge_retriever is not None or any(entry.embedding_vector is not None for entry in catalog)
    story_embedding, story_embedding_reason = _resolve_story_embedding(
        query_text=story_query_text,
        embedding_provider=embedding_provider,
        catalog_has_embeddings=catalog_has_embeddings,
    )
    slot_pools = []
    for slot_index in range(1, len(cast_overview.cast_slots)):
        slot = cast_overview.cast_slots[slot_index]
        slot_query_text = build_slot_query_text(slot)
        candidate_catalog = catalog
        if knowledge_retriever is not None:
            try:
                recalled_catalog = knowledge_retriever.recall_entries_for_author_slot(
                    query_language=focused_brief.language,
                    story_query_text=story_query_text,
                    slot_query_text=slot_query_text,
                    slot_tag=slot_tag_for_slot(slot),
                    primary_theme=primary_theme,
                    template_affinity=story_frame_strategy,
                )
            except CharacterKnowledgeError:
                recalled_catalog = ()
            if recalled_catalog:
                candidate_catalog = recalled_catalog
        slot_embedding, slot_embedding_reason = _resolve_slot_embedding(
            query_text=slot_query_text,
            embedding_provider=embedding_provider,
            catalog_has_embeddings=any(entry.embedding_vector is not None for entry in candidate_catalog),
        )
        selection_mode = _selection_mode(
            catalog_has_embeddings=any(entry.embedding_vector is not None for entry in candidate_catalog),
            story_embedding=story_embedding,
            slot_embedding=slot_embedding,
        )
        slot_pools.append(
            _rank_candidates_for_slot(
                slot_index=slot_index,
                slot=slot,
                story_query_text=story_query_text,
                query_language=focused_brief.language,
                catalog=candidate_catalog,
                primary_theme=primary_theme,
                story_embedding=story_embedding,
                slot_embedding=slot_embedding,
                selection_mode=selection_mode,
                embedding_reason=_embedding_reason(
                    selection_mode=selection_mode,
                    story_embedding_reason=story_embedding_reason,
                    slot_embedding_reason=slot_embedding_reason,
                ),
            )
        )
    slot_pools = tuple(slot_pools)
    selected_candidates = _solve_global_assignment(pools=slot_pools, limit=limit)
    assignment_by_slot = {candidate.slot_index: candidate for candidate in selected_candidates}
    pool_by_slot = {pool.slot_index: pool for pool in slot_pools}
    assignments = tuple(
        RetrievedRosterCharacter(
            entry=candidate.entry,
            slot_index=candidate.slot_index,
            slot_tag=candidate.slot_tag,
            score=candidate.total_score,
            score_breakdown=candidate.score_breakdown,
            selection_mode=pool_by_slot[candidate.slot_index].selection_mode,
            fallback_reason=pool_by_slot[candidate.slot_index].embedding_reason,
        )
        for candidate in sorted(selected_candidates, key=lambda item: item.slot_index)
    )
    trace: list[dict[str, object]] = []
    for pool in slot_pools:
        selected = assignment_by_slot.get(pool.slot_index)
        if selected is not None:
            fallback_reason = pool.embedding_reason
        elif pool.candidates:
            fallback_reason = "assignment_not_selected"
        else:
            fallback_reason = "no_candidate_match"
        trace.append(
            {
                "slot_index": pool.slot_index,
                "slot_tag": pool.slot_tag,
                "query_language": pool.query_language,
                "story_query_text": pool.story_query_text,
                "slot_query_text": pool.slot_query_text,
                "candidate_pool_size": pool.candidate_pool_size,
                "selected_character_id": selected.entry.character_id if selected is not None else None,
                "selected_template_version": (
                    selected.entry.template_version or selected.entry.source_fingerprint
                    if selected is not None
                    else None
                ),
                "top_candidates": [_top_candidate_payload(candidate) for candidate in pool.candidates],
                "score_breakdown": selected.score_breakdown if selected is not None else None,
                "selection_mode": pool.selection_mode,
                "fallback_reason": fallback_reason,
                "assignment_rank": selected.pool_rank if selected is not None else None,
                "assignment_score": round(selected.total_score, 6) if selected is not None else None,
            }
        )
    knowledge_catalog_version = knowledge_retriever.current_snapshot_version() if knowledge_retriever is not None else None
    return CharacterRosterSelectionResult(
        roster_enabled=True,
        catalog_version=knowledge_catalog_version or catalog_version,
        assignments=assignments,
        trace=tuple(trace),
    )

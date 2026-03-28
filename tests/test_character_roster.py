from __future__ import annotations

from rpg_backend.author.contracts import CastOverviewDraft, CastOverviewSlotDraft, FocusedBrief, StoryFrameDraft
from rpg_backend.roster.admin import build_runtime_catalog, write_runtime_catalog
from rpg_backend.roster.contracts import CharacterRosterEntry, CharacterRosterSourceEntry
from rpg_backend.roster.loader import load_character_roster_runtime_catalog
from rpg_backend.roster.retrieval import (
    _RankedRosterCandidate,
    _SlotCandidatePool,
    _solve_global_assignment,
    build_slot_query_text,
    build_story_query_text,
)
from rpg_backend.roster.service import CharacterRosterService


class _StubEmbeddingProvider:
    def __init__(self, embedding: list[float] | None) -> None:
        self._embedding = embedding

    def embed_text(self, text: str) -> list[float] | None:
        del text
        return self._embedding


class _FailingEmbeddingProvider:
    def embed_text(self, text: str) -> list[float] | None:
        del text
        raise RuntimeError("embedding down")


class _StoryFailingThenWorkingEmbeddingProvider:
    def __init__(self) -> None:
        self._calls = 0

    def embed_text(self, text: str) -> list[float] | None:
        self._calls += 1
        if self._calls == 1:
            raise RuntimeError("story embedding down")
        del text
        return [1.0, 0.0]


def _focused_brief() -> FocusedBrief:
    return FocusedBrief(
        language="en",
        story_kernel="A harbor inspector must expose staged seizures.",
        setting_signal="harbor quarantine and emergency manifests",
        core_conflict="keep the dock coalition from breaking before the vote hardens",
        tone_signal="tense civic thriller",
        hard_constraints=[],
        forbidden_tones=[],
    )


def _story_frame() -> StoryFrameDraft:
    return StoryFrameDraft(
        title="Manifest Fracture",
        premise="A harbor inspector must expose staged seizures before the dock wards fracture in public.",
        tone="Tense civic thriller",
        stakes="If the coalition fails, emergency authority hardens into private control.",
        style_guard="Keep it civic and procedural.",
        world_rules=["Emergency manifests decide leverage.", "The public record changes the balance of power."],
        truths=[
            {"text": "The public record is already under pressure.", "importance": "core"},
            {"text": "One missing manifest can redraw the whole coalition.", "importance": "core"},
        ],
        state_axis_choices=[
            {"template_id": "external_pressure", "story_label": "External Pressure", "starting_value": 1},
            {"template_id": "political_leverage", "story_label": "Political Leverage", "starting_value": 0},
        ],
        flags=[],
    )


def _focused_brief_zh() -> FocusedBrief:
    return FocusedBrief(
        language="zh",
        story_kernel="一名档案核验官必须公开停电后的配给差异。",
        setting_signal="停电后的档案厅和公开听证会",
        core_conflict="在各派把记录武器化之前保住公开程序",
        tone_signal="紧绷的公共程序剧",
        hard_constraints=[],
        forbidden_tones=[],
    )


def _story_frame_zh() -> StoryFrameDraft:
    return StoryFrameDraft(
        title="停电档案",
        premise="一名档案核验官必须在听证会前证明被封存的配给记录遭到篡改。",
        tone="紧绷的公共程序剧",
        stakes="如果程序失效，停电后的资源分配将彻底变成派系勒索。",
        style_guard="保持制度压力与公开记录感。",
        world_rules=["公开记录决定政治筹码。", "停电后的临时配给名册会重新划分权力。"],
        truths=[
            {"text": "被封存的配给账本已经被人动过。", "importance": "core"},
            {"text": "一处缺失的签章足以改变整个街区的供给次序。", "importance": "core"},
        ],
        state_axis_choices=[
            {"template_id": "external_pressure", "story_label": "外部压力", "starting_value": 1},
            {"template_id": "political_leverage", "story_label": "政治筹码", "starting_value": 0},
        ],
        flags=[],
    )


def _cast_overview() -> CastOverviewDraft:
    return CastOverviewDraft(
        cast_slots=[
            CastOverviewSlotDraft(
                slot_label="Mediator Anchor",
                public_role="Harbor inspector",
                relationship_to_protagonist="self",
                agenda_anchor="Keep the emergency process visible.",
                red_line_anchor="Will not let private bargaining replace public procedure.",
                pressure_vector="Feels every sealed corridor as a public risk.",
                archetype_id="civic_mediator",
            ),
            CastOverviewSlotDraft(
                slot_label="Institutional Guardian",
                public_role="Manifest clerk",
                relationship_to_protagonist="guardian",
                agenda_anchor="Keep the chain of custody intact.",
                red_line_anchor="Will not certify missing records.",
                pressure_vector="Turns missing paperwork into procedural pressure.",
                archetype_id="archive_guardian",
            ),
            CastOverviewSlotDraft(
                slot_label="Leverage Broker",
                public_role="Dock broker",
                relationship_to_protagonist="rival",
                agenda_anchor="Convert scarcity into leverage.",
                red_line_anchor="Will not leave the next settlement empty-handed.",
                pressure_vector="Treats every delay as bargaining power.",
                archetype_id="leverage_broker",
            ),
        ],
        relationship_summary=["The harbor process is splitting between procedure and leverage.", "Public trust depends on who can make the manifests legible."],
    )


def _four_slot_cast_overview() -> CastOverviewDraft:
    return CastOverviewDraft(
        cast_slots=[
            CastOverviewSlotDraft(
                slot_label="Mediator Anchor",
                public_role="Harbor inspector",
                relationship_to_protagonist="self",
                agenda_anchor="Keep the emergency process visible.",
                red_line_anchor="Will not let private bargaining replace public procedure.",
                pressure_vector="Feels every sealed corridor as a public risk.",
                archetype_id="civic_mediator",
            ),
            CastOverviewSlotDraft(
                slot_label="Institutional Guardian",
                public_role="Records certifier",
                relationship_to_protagonist="guardian",
                agenda_anchor="Keep the chain of custody intact.",
                red_line_anchor="Will not certify missing records.",
                pressure_vector="Turns missing paperwork into procedural pressure.",
                archetype_id="archive_guardian",
            ),
            CastOverviewSlotDraft(
                slot_label="Public Witness",
                public_role="Public witness",
                relationship_to_protagonist="witness",
                agenda_anchor="Keep the public version of events alive.",
                red_line_anchor="Will not let the room erase who stood in it.",
                pressure_vector="Remembers every stall and flinch in public.",
                archetype_id="witness",
            ),
            CastOverviewSlotDraft(
                slot_label="Leverage Broker",
                public_role="Grid broker",
                relationship_to_protagonist="rival",
                agenda_anchor="Convert scarcity into leverage.",
                red_line_anchor="Will not leave the next settlement empty-handed.",
                pressure_vector="Treats every delay as bargaining power.",
                archetype_id="leverage_broker",
            ),
        ],
        relationship_summary=[
            "The process is splitting between procedure, witness testimony, and leverage.",
            "Public trust depends on whether the record can still be certified in the open.",
        ],
    )


def _source_entry(**overrides) -> CharacterRosterSourceEntry:
    payload = {
        "character_id": "roster_match",
        "slug": "match",
        "name_en": "Match",
        "name_zh": "匹配者",
        "portrait_url": None,
        "public_summary_en": "Embedding-favored manifest clerk.",
        "public_summary_zh": "向量更匹配的舱单文员。",
        "role_hint_en": "Manifest clerk",
        "role_hint_zh": "舱单文员",
        "agenda_seed_en": "Keeps the record visible.",
        "agenda_seed_zh": "让记录保持可见。",
        "red_line_seed_en": "Will not hide the manifests.",
        "red_line_seed_zh": "不会把舱单藏起来。",
        "pressure_signature_seed_en": "Turns every missing stamp into a question.",
        "pressure_signature_seed_zh": "把每个缺失印记都变成问题。",
        "theme_tags": ["logistics_quarantine_crisis"],
        "setting_tags": ["harbor"],
        "tone_tags": ["tense"],
        "conflict_tags": ["public_record"],
        "slot_tags": ["guardian"],
        "retrieval_terms": ["harbor", "manifest"],
        "rarity_weight": 1.0,
    }
    payload.update(overrides)
    return CharacterRosterSourceEntry.from_payload(payload)


def _runtime_entry(**overrides) -> CharacterRosterEntry:
    return build_runtime_catalog((_source_entry(**overrides),)).entries[0]


def test_runtime_catalog_loader_reads_built_catalog_object(tmp_path) -> None:
    source_entries = (_source_entry(),)
    runtime_catalog = build_runtime_catalog(source_entries)
    path = tmp_path / "runtime.json"

    write_runtime_catalog(path, runtime_catalog)
    loaded = load_character_roster_runtime_catalog(path)

    assert loaded.catalog_version == runtime_catalog.catalog_version
    assert loaded.entry_count == 1
    assert loaded.entries[0].retrieval_text
    assert loaded.entries[0].source_fingerprint


def test_story_and_slot_query_builders_include_expected_context_for_en_and_zh() -> None:
    english_story_query = build_story_query_text(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        primary_theme="logistics_quarantine_crisis",
    )
    english_slot_query = build_slot_query_text(_cast_overview().cast_slots[1])
    chinese_story_query = build_story_query_text(
        focused_brief=_focused_brief_zh(),
        story_frame=_story_frame_zh(),
        primary_theme="truth_record_crisis",
    )
    chinese_slot_query = build_slot_query_text(
        CastOverviewSlotDraft(
            slot_label="公共见证",
            public_role="公共见证人",
            relationship_to_protagonist="witness",
            agenda_anchor="让公开版本留在场上。",
            red_line_anchor="不会让房间抹掉见证。",
            pressure_vector="记得每一次拖延和回避。",
            archetype_id="witness",
        )
    )

    assert "Manifest Fracture" in english_story_query
    assert "If the coalition fails" in english_story_query
    assert "Institutional Guardian" in english_slot_query
    assert "Manifest clerk" in english_slot_query
    assert "停电档案" in chinese_story_query
    assert "资源分配将彻底变成派系勒索" in chinese_story_query
    assert "公共见证" in chinese_slot_query
    assert "公共见证人" in chinese_slot_query


def test_roster_service_can_use_embedding_similarity_to_break_ties() -> None:
    matching = build_runtime_catalog((_source_entry(),)).entries[0]
    nonmatching = build_runtime_catalog(
        (
            _source_entry(
                character_id="roster_miss",
                slug="miss",
                name_en="Miss",
                name_zh="偏离者",
            ),
        )
    ).entries[0]
    matching = matching.__class__(**{**matching.to_payload(), "embedding_vector": (1.0, 0.0)})  # type: ignore[arg-type]
    nonmatching = nonmatching.__class__(**{**nonmatching.to_payload(), "embedding_vector": (-1.0, 0.0)})  # type: ignore[arg-type]
    service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=(matching, nonmatching),
        embedding_provider=_StubEmbeddingProvider([1.0, 0.0]),
        max_supporting_cast_selections=1,
    )

    retrieved = service.retrieve_for_cast(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        cast_overview=_cast_overview(),
        primary_theme="logistics_quarantine_crisis",
        limit=1,
    )

    assert len(retrieved.assignments) == 1
    assert retrieved.assignments[0].entry.character_id == "roster_match"
    assert retrieved.trace[0]["selection_mode"] == "embedding+lexical"


def test_roster_service_falls_back_to_lexical_when_query_embedding_fails() -> None:
    matching = _runtime_entry()
    matching = matching.__class__(**{**matching.to_payload(), "embedding_vector": (1.0, 0.0)})  # type: ignore[arg-type]
    service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=(matching,),
        embedding_provider=_FailingEmbeddingProvider(),
        max_supporting_cast_selections=1,
    )

    retrieved = service.retrieve_for_cast(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        cast_overview=_cast_overview(),
        primary_theme="logistics_quarantine_crisis",
        limit=1,
    )

    assert len(retrieved.assignments) == 1
    assert retrieved.trace[0]["selection_mode"] == "lexical_only"
    assert retrieved.trace[0]["fallback_reason"] == "embedding_query_failed"


def test_roster_service_reports_partial_story_embedding_failure_when_slot_embedding_succeeds() -> None:
    matching = _runtime_entry()
    matching = matching.__class__(**{**matching.to_payload(), "embedding_vector": (1.0, 0.0)})  # type: ignore[arg-type]
    service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=(matching,),
        embedding_provider=_StoryFailingThenWorkingEmbeddingProvider(),
        max_supporting_cast_selections=1,
    )

    retrieved = service.retrieve_for_cast(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        cast_overview=_cast_overview(),
        primary_theme="logistics_quarantine_crisis",
        limit=1,
    )

    assert len(retrieved.assignments) == 1
    assert retrieved.trace[0]["selection_mode"] == "embedding+lexical"
    assert retrieved.trace[0]["fallback_reason"] == "story_embedding_query_failed"
    assert retrieved.trace[0]["query_language"] == "en"
    assert retrieved.trace[0]["candidate_pool_size"] >= 1
    assert retrieved.trace[0]["assignment_rank"] == 1
    assert retrieved.trace[0]["assignment_score"] is not None
    assert retrieved.trace[0]["selected_template_version"] == (matching.template_version or matching.source_fingerprint)
    assert "story_query_text" in retrieved.trace[0]
    assert "slot_query_text" in retrieved.trace[0]
    assert retrieved.trace[0]["top_candidates"][0]["template_version"] == (matching.template_version or matching.source_fingerprint)


def test_roster_service_requires_more_than_rarity_to_admit_candidate() -> None:
    service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=(
            _runtime_entry(
                character_id="roster_only_rarity",
                slug="only-rarity",
                name_en="Only Rarity",
                name_zh="只有稀有度",
                theme_tags=["unrelated_theme"],
                setting_tags=["desert"],
                tone_tags=["dry"],
                conflict_tags=["private_intrigue"],
                slot_tags=["witness"],
                retrieval_terms=["sand"],
                rarity_weight=9.0,
            ),
        ),
        embedding_provider=_StubEmbeddingProvider(None),
        max_supporting_cast_selections=1,
    )

    retrieved = service.retrieve_for_cast(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        cast_overview=_cast_overview(),
        primary_theme="logistics_quarantine_crisis",
        limit=1,
    )

    assert not retrieved.assignments
    assert retrieved.trace[0]["candidate_pool_size"] == 0
    assert retrieved.trace[0]["fallback_reason"] == "no_candidate_match"


def test_roster_service_respects_supporting_cast_limit_and_skips_protagonist_slot() -> None:
    service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog(
            (
                _source_entry(),
                _source_entry(
                    character_id="roster_second",
                    slug="second",
                    name_en="Second",
                    name_zh="第二人",
                    slot_tags=["broker"],
                    retrieval_terms=["dock", "broker"],
                ),
            )
        ).entries,
        embedding_provider=_StubEmbeddingProvider(None),
        max_supporting_cast_selections=1,
    )

    retrieved = service.retrieve_for_cast(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        cast_overview=_cast_overview(),
        primary_theme="logistics_quarantine_crisis",
        limit=1,
    )

    assert len(retrieved.assignments) == 1
    assert retrieved.assignments[0].slot_index != 0
    assert all(trace["slot_index"] != 0 for trace in retrieved.trace)


def test_global_assignment_prefers_best_total_over_greedy_slot_order() -> None:
    slot_one = _SlotCandidatePool(
        slot_index=1,
        slot_tag="guardian",
        story_query_text="story",
        slot_query_text="slot one",
        query_language="en",
        selection_mode="lexical_only",
        embedding_reason=None,
        candidate_pool_size=2,
        candidates=(
            _RankedRosterCandidate(
                slot_index=1,
                slot_tag="guardian",
                entry=_runtime_entry(character_id="roster_a", slug="a", name_en="A", name_zh="甲"),
                total_score=9.0,
                score_breakdown={"exact_slot": 0.0, "retrieval_terms": 4.0, "total": 9.0},
                pool_rank=1,
            ),
            _RankedRosterCandidate(
                slot_index=1,
                slot_tag="guardian",
                entry=_runtime_entry(character_id="roster_b", slug="b", name_en="B", name_zh="乙"),
                total_score=6.0,
                score_breakdown={"exact_slot": 4.0, "retrieval_terms": 2.0, "total": 6.0},
                pool_rank=2,
            ),
        ),
    )
    slot_two = _SlotCandidatePool(
        slot_index=2,
        slot_tag="broker",
        story_query_text="story",
        slot_query_text="slot two",
        query_language="en",
        selection_mode="lexical_only",
        embedding_reason=None,
        candidate_pool_size=2,
        candidates=(
            _RankedRosterCandidate(
                slot_index=2,
                slot_tag="broker",
                entry=_runtime_entry(character_id="roster_a", slug="a2", name_en="A2", name_zh="甲二"),
                total_score=8.0,
                score_breakdown={"exact_slot": 4.0, "retrieval_terms": 2.0, "total": 8.0},
                pool_rank=1,
            ),
            _RankedRosterCandidate(
                slot_index=2,
                slot_tag="broker",
                entry=_runtime_entry(character_id="roster_b", slug="b2", name_en="B2", name_zh="乙二"),
                total_score=1.0,
                score_breakdown={"exact_slot": 0.0, "retrieval_terms": 1.0, "total": 1.0},
                pool_rank=2,
            ),
        ),
    )

    assignment = _solve_global_assignment(pools=(slot_one, slot_two), limit=2)

    assert {(item.slot_index, item.entry.character_id) for item in assignment} == {
        (1, "roster_b"),
        (2, "roster_a"),
    }


def test_roster_service_can_select_three_supporting_casts_when_limit_is_three() -> None:
    service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog(
            (
                _source_entry(
                    character_id="roster_archive_certifier",
                    slug="archive-certifier",
                    name_en="Lin Verrow",
                    name_zh="林维若",
                    slot_tags=["guardian", "anchor"],
                    setting_tags=["archive", "record"],
                    conflict_tags=["public_record", "witness"],
                    retrieval_terms=["archive", "record", "certify", "witness", "hearing"],
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier.png",
                ),
                _source_entry(
                    character_id="roster_courtyard_witness",
                    slug="courtyard-witness",
                    name_en="Pei Sorn",
                    name_zh="裴松",
                    slot_tags=["witness", "civic"],
                    setting_tags=["archive", "council"],
                    conflict_tags=["witness", "legitimacy"],
                    retrieval_terms=["witness", "public", "record", "council", "hearing"],
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_courtyard_witness.png",
                ),
                _source_entry(
                    character_id="roster_blackout_grid_broker",
                    slug="grid-broker",
                    name_en="Tarin Dusk",
                    name_zh="塔林·暮岚",
                    slot_tags=["broker", "civic"],
                    setting_tags=["blackout", "grid"],
                    conflict_tags=["public_order", "resource"],
                    retrieval_terms=["blackout", "grid", "district", "broker", "power"],
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_blackout_grid_broker.png",
                ),
            )
        ).entries,
        embedding_provider=_StubEmbeddingProvider(None),
        max_supporting_cast_selections=3,
    )

    retrieved = service.retrieve_for_cast(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        cast_overview=_four_slot_cast_overview(),
        primary_theme="legitimacy_crisis",
        limit=3,
    )

    assert len(retrieved.assignments) == 3
    assert {item.entry.character_id for item in retrieved.assignments} == {
        "roster_archive_certifier",
        "roster_courtyard_witness",
        "roster_blackout_grid_broker",
    }

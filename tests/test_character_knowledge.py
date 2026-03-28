from __future__ import annotations

from dataclasses import dataclass

from rpg_backend.author.contracts import CastOverviewDraft, CastOverviewSlotDraft, FocusedBrief, StoryFrameDraft
from rpg_backend.character_knowledge.contracts import (
    CharacterKnowledgeCandidate,
    CharacterKnowledgeImportSummary,
    CharacterKnowledgeLocalization,
    CharacterKnowledgePortrait,
    CharacterKnowledgeRetrievalDoc,
    CharacterKnowledgeUpsertBundle,
)
from rpg_backend.character_knowledge.documents import (
    build_character_knowledge_bundle,
    build_character_retrieval_docs,
)
from rpg_backend.character_knowledge.indexer import CharacterKnowledgeIndexer
from rpg_backend.character_knowledge.retriever import CharacterKnowledgeRetriever
from rpg_backend.roster.contracts import CharacterRosterEntry, CharacterRosterSourceEntry
from rpg_backend.roster.service import CharacterRosterService


def _source_entry(**overrides) -> CharacterRosterSourceEntry:
    payload = {
        "character_id": "roster_archive_certifier",
        "slug": "archive-certifier",
        "name_en": "Lin Verrow",
        "name_zh": "林维若",
        "portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
        "default_portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
        "portrait_variants": {
            "negative": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/negative/current.png",
            "neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
            "positive": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png",
        },
        "public_summary_en": "A formal certifier who keeps the public archive vote legible.",
        "public_summary_zh": "一名维持档案投票可读性的正式认证官。",
        "role_hint_en": "Archive vote certifier",
        "role_hint_zh": "档案投票认证官",
        "agenda_seed_en": "Keep the certification chain intact.",
        "agenda_seed_zh": "守住认证链条。",
        "red_line_seed_en": "Will not certify altered records.",
        "red_line_seed_zh": "不会认证被改写的记录。",
        "pressure_signature_seed_en": "Turns every missing seal into a public credibility problem.",
        "pressure_signature_seed_zh": "把每一个缺失印章都变成公共可信度问题。",
        "gender_lock": "unspecified",
        "personality_core_en": "Calm in public, exacting under pressure, and difficult to stampede once procedure matters.",
        "personality_core_zh": "公开场合冷静，压力上来时会更苛刻，一旦程序变重要就很难被裹挟。",
        "experience_anchor_en": "A records certifier known for staying with the chain of custody after others want a quicker story.",
        "experience_anchor_zh": "一名长期守着交接链的记录认证官，别人想更快翻页时仍会把链条盯到底。",
        "identity_lock_notes_en": "Keep the same person, the same face, and the same public identity. Do not rename or rewrite them into a different person.",
        "identity_lock_notes_zh": "必须保持同一个人、同一张脸和同一公共身份。不得改名，也不得改写成另一个人。",
        "theme_tags": ["truth_record_crisis"],
        "setting_tags": ["archive"],
        "tone_tags": ["procedural"],
        "conflict_tags": ["public_record"],
        "slot_tags": ["guardian"],
        "retrieval_terms": ["archive", "vote", "certifier"],
        "rarity_weight": 1.0,
    }
    payload.update(overrides)
    return CharacterRosterSourceEntry.from_payload(payload)


def _focused_brief() -> FocusedBrief:
    return FocusedBrief(
        language="en",
        story_kernel="An examiner must certify the archive vote before the false result hardens.",
        setting_signal="archive chamber and public gallery",
        core_conflict="keep the public record intact before mandate brokers reshape the result",
        tone_signal="restrained civic procedural thriller",
        hard_constraints=[],
        forbidden_tones=[],
    )


def _story_frame() -> StoryFrameDraft:
    return StoryFrameDraft(
        title="Archive Vote",
        premise="An examiner must certify the archive vote before a false result locks into public law.",
        tone="Restrained civic procedural thriller",
        stakes="If the chain breaks, the public record becomes a weapon.",
        style_guard="Keep it procedural and public-facing.",
        world_rules=["Certification changes legitimacy.", "Public records shape civic power."],
        truths=[
            {"text": "The certification chain is already under pressure.", "importance": "core"},
            {"text": "A false result will harden if the archive vote is not checked in public.", "importance": "core"},
        ],
        state_axis_choices=[
            {"template_id": "external_pressure", "story_label": "External Pressure", "starting_value": 1},
            {"template_id": "political_leverage", "story_label": "Political Leverage", "starting_value": 0},
        ],
        flags=[],
    )


def _cast_overview() -> CastOverviewDraft:
    return CastOverviewDraft(
        cast_slots=[
            CastOverviewSlotDraft(
                slot_label="Mediator Anchor",
                public_role="Records examiner",
                relationship_to_protagonist="self",
                agenda_anchor="Keep the process visible.",
                red_line_anchor="Will not let private leverage erase the public answer.",
                pressure_vector="Feels every missing stamp as a civic risk.",
                archetype_id="record_examiner",
            ),
            CastOverviewSlotDraft(
                slot_label="Institutional Guardian",
                public_role="Archive certifier",
                relationship_to_protagonist="guardian",
                agenda_anchor="Hold the certification chain together.",
                red_line_anchor="Will not validate a compromised result.",
                pressure_vector="Makes every procedural breach costly.",
                archetype_id="archive_guardian",
            ),
            CastOverviewSlotDraft(
                slot_label="Public Witness",
                public_role="Gallery witness",
                relationship_to_protagonist="witness",
                agenda_anchor="Keep what the public saw inside the record.",
                red_line_anchor="Will not let the room erase testimony.",
                pressure_vector="Turns quiet omissions into visible pressure.",
                archetype_id="witness",
            ),
        ],
        relationship_summary=[
            "The room is split between procedure and leverage.",
            "The public record only holds if witnesses remain legible.",
        ],
    )


class _StubEmbeddingProvider:
    def embed_text(self, text: str) -> list[float] | None:
        del text
        return [1.0, 0.0]


class _FakeKnowledgeRepository:
    def __init__(self) -> None:
        self.ensure_schema_called = 0
        self.active_character_ids = ("legacy_archived",)
        self.upserts: list[tuple[CharacterKnowledgeUpsertBundle, tuple[CharacterKnowledgeRetrievalDoc, ...]]] = []
        self.recorded_runs: list[CharacterKnowledgeImportSummary] = []
        self.archived: list[str] = []
        self.candidates: tuple[CharacterKnowledgeCandidate, ...] = ()

    def ensure_schema(self) -> None:
        self.ensure_schema_called += 1

    def current_snapshot_version(self, *, source_kind: str) -> str | None:
        del source_kind
        return "knowledge_v1"

    def list_active_character_ids(self, *, source_kind: str) -> tuple[str, ...]:
        del source_kind
        return self.active_character_ids

    def upsert_character_bundle(
        self,
        bundle: CharacterKnowledgeUpsertBundle,
        *,
        docs: tuple[CharacterKnowledgeRetrievalDoc, ...],
    ) -> None:
        self.upserts.append((bundle, docs))

    def archive_characters(
        self,
        *,
        source_kind: str,
        character_ids: tuple[str, ...],
        snapshot_version: str,
    ) -> tuple[str, ...]:
        del source_kind, snapshot_version
        self.archived.extend(character_ids)
        return character_ids

    def record_import_run(
        self,
        *,
        source_kind: str,
        import_mode: str,
        snapshot_version: str,
        imported_character_ids: tuple[str, ...],
        archived_character_ids: tuple[str, ...],
        doc_count: int,
    ) -> None:
        self.recorded_runs.append(
            CharacterKnowledgeImportSummary(
                source_kind=source_kind,  # type: ignore[arg-type]
                import_mode=import_mode,  # type: ignore[arg-type]
                snapshot_version=snapshot_version,
                imported_character_ids=imported_character_ids,
                archived_character_ids=archived_character_ids,
                doc_count=doc_count,
            )
        )

    def recall_candidates(
        self,
        *,
        query_mode: str,
        query_language: str,
        query_text: str,
        query_embedding: list[float] | None,
        slot_tag: str | None,
        primary_theme: str | None,
        template_affinity: str | None,
        source_kind: str,
        active_status: str = "active",
        candidate_limit: int = 24,
    ) -> tuple[CharacterKnowledgeCandidate, ...]:
        del (
            query_mode,
            query_language,
            query_text,
            query_embedding,
            slot_tag,
            primary_theme,
            template_affinity,
            source_kind,
            active_status,
            candidate_limit,
        )
        return self.candidates


def _runtime_entry() -> CharacterRosterEntry:
    entry = _source_entry()
    return CharacterRosterEntry(
        character_id=entry.character_id,
        slug=entry.slug,
        name_en=entry.name_en,
        name_zh=entry.name_zh,
        portrait_url=entry.portrait_url,
        default_portrait_url=entry.default_portrait_url,
        portrait_variants=entry.portrait_variants,
        public_summary_en=entry.public_summary_en,
        public_summary_zh=entry.public_summary_zh,
        role_hint_en=entry.role_hint_en,
        role_hint_zh=entry.role_hint_zh,
        agenda_seed_en=entry.agenda_seed_en,
        agenda_seed_zh=entry.agenda_seed_zh,
        red_line_seed_en=entry.red_line_seed_en,
        red_line_seed_zh=entry.red_line_seed_zh,
        pressure_signature_seed_en=entry.pressure_signature_seed_en,
        pressure_signature_seed_zh=entry.pressure_signature_seed_zh,
        personality_core_en=entry.personality_core_en,
        personality_core_zh=entry.personality_core_zh,
        experience_anchor_en=entry.experience_anchor_en,
        experience_anchor_zh=entry.experience_anchor_zh,
        identity_lock_notes_en=entry.identity_lock_notes_en,
        identity_lock_notes_zh=entry.identity_lock_notes_zh,
        theme_tags=entry.theme_tags,
        setting_tags=entry.setting_tags,
        tone_tags=entry.tone_tags,
        conflict_tags=entry.conflict_tags,
        slot_tags=entry.slot_tags,
        retrieval_terms=entry.retrieval_terms,
        retrieval_text="archive vote certifier public record",
        source_fingerprint="fp",
        embedding_vector=(1.0, 0.0),
        rarity_weight=entry.rarity_weight,
        gender_lock=entry.gender_lock,
    )


def test_build_character_retrieval_docs_emits_two_languages_and_five_doc_types() -> None:
    bundle = build_character_knowledge_bundle(
        _source_entry(),
        source_kind="roster_catalog",
        snapshot_version="snapshot_v1",
    )

    docs = build_character_retrieval_docs(bundle)

    assert bundle.gender_lock == "unspecified"
    assert len(docs) == 10
    assert {doc.doc_language for doc in docs} == {"en", "zh"}
    assert {doc.doc_type for doc in docs} == {
        "identity",
        "procedural_role",
        "pressure_profile",
        "template_affinity",
        "public_summary",
    }
    assert any("archive_vote_story" in doc.text for doc in docs if doc.doc_type == "template_affinity")
    assert any("same person" in doc.text.casefold() for doc in docs if doc.doc_type == "template_affinity")


def test_character_knowledge_indexer_imports_docs_and_archives_missing_entries() -> None:
    repository = _FakeKnowledgeRepository()
    indexer = CharacterKnowledgeIndexer(
        repository=repository,
        embedding_provider=_StubEmbeddingProvider(),
        source_kind="roster_catalog",
    )

    summary = indexer.import_source_entries((_source_entry(),), import_mode="replace")

    assert repository.ensure_schema_called == 1
    assert len(repository.upserts) == 1
    assert len(repository.upserts[0][1]) == 10
    assert repository.upserts[0][0].template_version
    assert summary.doc_count == 10
    assert summary.imported_character_ids == ("roster_archive_certifier",)
    assert summary.archived_character_ids == ("legacy_archived",)
    assert repository.recorded_runs[0].snapshot_version == summary.snapshot_version


def test_character_knowledge_retriever_returns_author_entries() -> None:
    repository = _FakeKnowledgeRepository()
    repository.candidates = (
        CharacterKnowledgeCandidate(
            entry=_runtime_entry(),
            matched_doc_type="identity",
            matched_doc_language="en",
            matched_similarity=0.88,
        ),
    )
    retriever = CharacterKnowledgeRetriever(
        repository=repository,
        embedding_provider=_StubEmbeddingProvider(),
        source_kind="roster_catalog",
        candidate_limit=12,
    )

    entries = retriever.recall_entries_for_author_slot(
        query_language="en",
        story_query_text="archive vote chamber",
        slot_query_text="archive certifier",
        slot_tag="guardian",
        primary_theme="truth_record_crisis",
        template_affinity="archive_vote_story",
    )

    assert len(entries) == 1
    assert entries[0].character_id == "roster_archive_certifier"


def test_roster_service_can_use_knowledge_retriever_for_author_binding() -> None:
    repository = _FakeKnowledgeRepository()
    repository.candidates = (
        CharacterKnowledgeCandidate(
            entry=_runtime_entry(),
            matched_doc_type="identity",
            matched_doc_language="en",
            matched_similarity=0.91,
        ),
    )
    retriever = CharacterKnowledgeRetriever(
        repository=repository,
        embedding_provider=_StubEmbeddingProvider(),
        source_kind="roster_catalog",
        candidate_limit=12,
    )
    service = CharacterRosterService(
        enabled=True,
        catalog_version="runtime_v1",
        catalog=(),
        embedding_provider=_StubEmbeddingProvider(),
        max_supporting_cast_selections=3,
        knowledge_retriever=retriever,
    )

    result = service.retrieve_for_cast(
        focused_brief=_focused_brief(),
        story_frame=_story_frame(),
        cast_overview=_cast_overview(),
        primary_theme="truth_record_crisis",
        limit=3,
        story_frame_strategy="archive_vote_story",
    )

    assert result.catalog_version == "knowledge_v1"
    assert len(result.assignments) == 1
    assert result.assignments[0].entry.character_id == "roster_archive_certifier"

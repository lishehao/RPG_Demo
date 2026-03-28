from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from rpg_backend.roster.contracts import CharacterRosterEntry

CharacterKnowledgeActiveStatus = Literal["active", "archived"]
CharacterKnowledgeSourceKind = Literal["roster_catalog"]
CharacterKnowledgeQueryMode = Literal[
    "author_cast_binding",
    "copilot_character_suggestion",
    "play_character_lookup",
]
CharacterKnowledgeDocLanguage = Literal["en", "zh"]
CharacterKnowledgeDocType = Literal[
    "identity",
    "procedural_role",
    "pressure_profile",
    "template_affinity",
    "public_summary",
]
CharacterKnowledgeRosterSlotTag = Literal["anchor", "guardian", "broker", "witness", "civic"]


class CharacterKnowledgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class CharacterKnowledgeLocalization:
    language: CharacterKnowledgeDocLanguage
    name: str
    public_summary: str
    role_hint: str
    agenda: str
    red_line: str
    pressure_signature: str
    personality_core: str | None = None
    experience_anchor: str | None = None
    identity_lock_notes: str | None = None


@dataclass(frozen=True)
class CharacterKnowledgePortrait:
    variant_key: Literal["negative", "neutral", "positive"]
    public_url: str


@dataclass(frozen=True)
class CharacterKnowledgeUpsertBundle:
    character_id: str
    slug: str
    active_status: CharacterKnowledgeActiveStatus
    source_kind: CharacterKnowledgeSourceKind
    roster_state: str
    source_fingerprint: str
    snapshot_version: str
    template_version: str
    gender_lock: Literal["female", "male", "nonbinary", "unspecified"] | None
    rarity_weight: float
    theme_tags: tuple[str, ...]
    setting_tags: tuple[str, ...]
    tone_tags: tuple[str, ...]
    conflict_tags: tuple[str, ...]
    slot_tags: tuple[CharacterKnowledgeRosterSlotTag, ...]
    retrieval_terms: tuple[str, ...]
    template_affinity: tuple[str, ...]
    localizations: tuple[CharacterKnowledgeLocalization, ...]
    portraits: tuple[CharacterKnowledgePortrait, ...]


@dataclass(frozen=True)
class CharacterKnowledgeRetrievalDoc:
    character_id: str
    doc_type: CharacterKnowledgeDocType
    doc_language: CharacterKnowledgeDocLanguage
    text: str
    metadata_json: dict[str, Any]
    source_fingerprint: str
    embedding_vector: tuple[float, ...] | None = None


@dataclass(frozen=True)
class CharacterKnowledgeImportSummary:
    source_kind: CharacterKnowledgeSourceKind
    import_mode: Literal["replace", "upsert"]
    snapshot_version: str
    imported_character_ids: tuple[str, ...]
    archived_character_ids: tuple[str, ...]
    doc_count: int


@dataclass(frozen=True)
class CharacterKnowledgeCandidate:
    entry: "CharacterRosterEntry"
    matched_doc_type: CharacterKnowledgeDocType
    matched_doc_language: CharacterKnowledgeDocLanguage
    matched_similarity: float | None


class CharacterKnowledgeRepository(Protocol):
    def ensure_schema(self) -> None: ...

    def current_snapshot_version(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
    ) -> str | None: ...

    def list_active_character_ids(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
    ) -> tuple[str, ...]: ...

    def upsert_character_bundle(
        self,
        bundle: CharacterKnowledgeUpsertBundle,
        *,
        docs: tuple[CharacterKnowledgeRetrievalDoc, ...],
    ) -> None: ...

    def archive_characters(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
        character_ids: tuple[str, ...],
        snapshot_version: str,
    ) -> tuple[str, ...]: ...

    def record_import_run(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
        import_mode: Literal["replace", "upsert"],
        snapshot_version: str,
        imported_character_ids: tuple[str, ...],
        archived_character_ids: tuple[str, ...],
        doc_count: int,
    ) -> None: ...

    def recall_candidates(
        self,
        *,
        query_mode: CharacterKnowledgeQueryMode,
        query_language: CharacterKnowledgeDocLanguage,
        query_text: str,
        query_embedding: list[float] | None,
        slot_tag: CharacterKnowledgeRosterSlotTag | None,
        primary_theme: str | None,
        template_affinity: str | None,
        source_kind: CharacterKnowledgeSourceKind,
        active_status: CharacterKnowledgeActiveStatus = "active",
        candidate_limit: int = 24,
    ) -> tuple[CharacterKnowledgeCandidate, ...]: ...

    def get_character_entry(
        self,
        *,
        character_id: str,
        source_kind: CharacterKnowledgeSourceKind,
        active_status: CharacterKnowledgeActiveStatus = "active",
    ) -> "CharacterRosterEntry | None": ...

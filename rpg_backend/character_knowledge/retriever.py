from __future__ import annotations

from dataclasses import dataclass

from rpg_backend.character_knowledge.contracts import (
    CharacterKnowledgeCandidate,
    CharacterKnowledgeError,
    CharacterKnowledgeQueryMode,
    CharacterKnowledgeRepository,
    CharacterKnowledgeSourceKind,
)
from rpg_backend.character_knowledge.postgres import build_character_knowledge_repository
from rpg_backend.config import Settings
from rpg_backend.roster.contracts import CharacterRosterEntry, RosterSlotTag
from rpg_backend.roster.embeddings import CharacterEmbeddingProvider, build_character_embedding_provider


@dataclass(frozen=True)
class CharacterKnowledgeRetriever:
    repository: CharacterKnowledgeRepository
    embedding_provider: CharacterEmbeddingProvider
    source_kind: CharacterKnowledgeSourceKind
    candidate_limit: int

    def current_snapshot_version(self) -> str | None:
        return self.repository.current_snapshot_version(source_kind=self.source_kind)

    def get_character_entry(self, character_id: str) -> CharacterRosterEntry | None:
        return self.repository.get_character_entry(
            character_id=character_id,
            source_kind=self.source_kind,
        )

    def recall_candidates(
        self,
        *,
        query_mode: CharacterKnowledgeQueryMode,
        query_language: str,
        query_text: str,
        slot_tag: RosterSlotTag | None,
        primary_theme: str | None,
        template_affinity: str | None,
    ) -> tuple[CharacterKnowledgeCandidate, ...]:
        try:
            query_embedding = self.embedding_provider.embed_text(query_text)
            return self.repository.recall_candidates(
                query_mode=query_mode,
                query_language="zh" if str(query_language).casefold().startswith("zh") else "en",
                query_text=query_text,
                query_embedding=query_embedding,
                slot_tag=slot_tag,
                primary_theme=primary_theme,
                template_affinity=template_affinity,
                source_kind=self.source_kind,
                candidate_limit=self.candidate_limit,
            )
        except Exception as exc:  # noqa: BLE001
            raise CharacterKnowledgeError(f"knowledge repository recall failed: {exc}") from exc

    def recall_entries_for_author_slot(
        self,
        *,
        query_language: str,
        story_query_text: str,
        slot_query_text: str,
        slot_tag: RosterSlotTag,
        primary_theme: str,
        template_affinity: str | None,
    ) -> tuple[CharacterRosterEntry, ...]:
        candidates = self.recall_candidates(
            query_mode="author_cast_binding",
            query_language=query_language,
            query_text=f"{story_query_text} {slot_query_text}".strip(),
            slot_tag=slot_tag,
            primary_theme=primary_theme,
            template_affinity=template_affinity,
        )
        return tuple(candidate.entry for candidate in candidates)


def build_character_knowledge_retriever(
    settings: Settings,
    *,
    embedding_provider: CharacterEmbeddingProvider | None = None,
) -> CharacterKnowledgeRetriever | None:
    repository = build_character_knowledge_repository(settings)
    if repository is None:
        return None
    repository.ensure_schema()
    return CharacterKnowledgeRetriever(
        repository=repository,
        embedding_provider=embedding_provider or build_character_embedding_provider(settings),
        source_kind=settings.character_knowledge_source_kind,  # type: ignore[arg-type]
        candidate_limit=settings.character_knowledge_candidate_limit,
    )

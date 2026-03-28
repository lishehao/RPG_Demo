from __future__ import annotations

from dataclasses import replace

from rpg_backend.character_knowledge.contracts import (
    CharacterKnowledgeImportSummary,
    CharacterKnowledgeRepository,
    CharacterKnowledgeSourceKind,
)
from rpg_backend.character_knowledge.documents import (
    build_character_knowledge_bundle,
    build_character_retrieval_docs,
    snapshot_version_for_entries,
)
from rpg_backend.config import Settings
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from rpg_backend.roster.embeddings import CharacterEmbeddingProvider, build_character_embedding_provider


class CharacterKnowledgeIndexer:
    def __init__(
        self,
        *,
        repository: CharacterKnowledgeRepository,
        embedding_provider: CharacterEmbeddingProvider,
        source_kind: CharacterKnowledgeSourceKind,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._source_kind = source_kind

    def import_source_entries(
        self,
        source_entries: tuple[CharacterRosterSourceEntry, ...],
        *,
        import_mode: str = "replace",
    ) -> CharacterKnowledgeImportSummary:
        self._repository.ensure_schema()
        snapshot_version = snapshot_version_for_entries(source_entries)
        imported_character_ids: list[str] = []
        doc_count = 0
        for entry in source_entries:
            bundle = build_character_knowledge_bundle(
                entry,
                source_kind=self._source_kind,
                snapshot_version=snapshot_version,
            )
            docs = tuple(
                replace(
                    doc,
                    embedding_vector=tuple(float(item) for item in embedding) if embedding is not None else None,
                )
                for doc in build_character_retrieval_docs(bundle)
                for embedding in (self._embedding_provider.embed_text(doc.text),)
            )
            self._repository.upsert_character_bundle(bundle, docs=docs)
            imported_character_ids.append(entry.character_id)
            doc_count += len(docs)
        archived_character_ids: tuple[str, ...] = ()
        if import_mode == "replace":
            keep_ids = frozenset(imported_character_ids)
            existing_ids = set(self._repository.list_active_character_ids(source_kind=self._source_kind))
            to_archive = tuple(sorted(existing_ids - keep_ids))
            if to_archive:
                archived_character_ids = self._repository.archive_characters(
                    source_kind=self._source_kind,
                    character_ids=to_archive,
                    snapshot_version=snapshot_version,
                )
        self._repository.record_import_run(
            source_kind=self._source_kind,
            import_mode="replace" if import_mode == "replace" else "upsert",
            snapshot_version=snapshot_version,
            imported_character_ids=tuple(imported_character_ids),
            archived_character_ids=archived_character_ids,
            doc_count=doc_count,
        )
        return CharacterKnowledgeImportSummary(
            source_kind=self._source_kind,
            import_mode="replace" if import_mode == "replace" else "upsert",
            snapshot_version=snapshot_version,
            imported_character_ids=tuple(imported_character_ids),
            archived_character_ids=archived_character_ids,
            doc_count=doc_count,
        )


def build_character_knowledge_indexer(
    *,
    settings: Settings,
    repository: CharacterKnowledgeRepository,
    embedding_provider: CharacterEmbeddingProvider | None = None,
) -> CharacterKnowledgeIndexer:
    return CharacterKnowledgeIndexer(
        repository=repository,
        embedding_provider=embedding_provider or build_character_embedding_provider(settings),
        source_kind=settings.character_knowledge_source_kind,  # type: ignore[arg-type]
    )

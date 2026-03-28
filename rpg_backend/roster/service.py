from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from rpg_backend.author.compiler.cast import build_cast_member_from_slot
from rpg_backend.author.generation.story_instances import default_story_instance_snapshot
from rpg_backend.author.contracts import (
    CastOverviewDraft,
    CastOverviewSlotDraft,
    FocusedBrief,
    OverviewCastDraft,
    StoryFrameDraft,
)
from rpg_backend.author.normalize import trim_ellipsis
from rpg_backend.character_knowledge.retriever import (
    CharacterKnowledgeRetriever,
    build_character_knowledge_retriever,
)
from rpg_backend.config import Settings, get_settings
from rpg_backend.llm_gateway import CapabilityGatewayCore
from rpg_backend.roster.contracts import (
    CharacterRosterEntry,
    CharacterRosterSelectionResult,
    RetrievedRosterCharacter,
)
from rpg_backend.roster.embeddings import CharacterEmbeddingProvider, build_character_embedding_provider
from rpg_backend.roster.loader import ensure_character_roster_runtime_catalog
from rpg_backend.roster.retrieval import retrieve_roster_assignments


def _localized_entry_text(entry: CharacterRosterEntry, language: str) -> tuple[str, str, str, str, str]:
    if language == "zh":
        return (
            entry.name_zh,
            entry.role_hint_zh,
            entry.public_summary_zh,
            entry.agenda_seed_zh,
            entry.red_line_seed_zh,
        )
    return (
        entry.name_en,
        entry.role_hint_en,
        entry.public_summary_en,
        entry.agenda_seed_en,
        entry.red_line_seed_en,
    )


def _pressure_seed(entry: CharacterRosterEntry, language: str) -> str:
    return entry.pressure_signature_seed_zh if language == "zh" else entry.pressure_signature_seed_en


@dataclass(frozen=True)
class CharacterRosterService:
    enabled: bool
    catalog_version: str | None
    catalog: tuple[CharacterRosterEntry, ...]
    embedding_provider: CharacterEmbeddingProvider
    max_supporting_cast_selections: int
    knowledge_retriever: CharacterKnowledgeRetriever | None = None

    def get_entry_by_id(self, character_id: str | None) -> CharacterRosterEntry | None:
        if not character_id:
            return None
        for entry in self.catalog:
            if entry.character_id == character_id:
                return entry
        if self.knowledge_retriever is not None:
            return self.knowledge_retriever.get_character_entry(character_id)
        return None

    def retrieve_for_cast(
        self,
        *,
        focused_brief: FocusedBrief,
        story_frame: StoryFrameDraft,
        cast_overview: CastOverviewDraft,
        primary_theme: str,
        limit: int | None = None,
        story_frame_strategy: str | None = None,
    ) -> CharacterRosterSelectionResult:
        if limit is None:
            resolved_limit = self.max_supporting_cast_selections
        else:
            resolved_limit = min(max(int(limit), 0), self.max_supporting_cast_selections)
        return retrieve_roster_assignments(
            enabled=self.enabled,
            catalog_version=self.catalog_version,
            catalog=self.catalog,
            embedding_provider=self.embedding_provider,
            focused_brief=focused_brief,
            story_frame=story_frame,
            cast_overview=cast_overview,
            primary_theme=primary_theme,
            limit=resolved_limit,
            knowledge_retriever=self.knowledge_retriever,
            story_frame_strategy=story_frame_strategy,
        )

    def build_cast_member(
        self,
        *,
        focused_brief: FocusedBrief,
        slot: CastOverviewSlotDraft,
        slot_index: int,
        existing_names: set[str],
        retrieved: RetrievedRosterCharacter,
    ) -> OverviewCastDraft:
        fallback = build_cast_member_from_slot(slot, focused_brief, slot_index, set(existing_names))
        name, _role_hint, public_summary, agenda_seed, red_line_seed = _localized_entry_text(retrieved.entry, focused_brief.language)
        pressure_seed = _pressure_seed(retrieved.entry, focused_brief.language)
        final_name = name if name not in existing_names else fallback.name
        member = OverviewCastDraft(
            name=trim_ellipsis(final_name, 80),
            role=trim_ellipsis(slot.public_role, 120),
            agenda=trim_ellipsis(f"{slot.agenda_anchor} {agenda_seed}", 220),
            red_line=trim_ellipsis(f"{slot.red_line_anchor} {red_line_seed}", 220),
            pressure_signature=trim_ellipsis(f"{slot.pressure_vector} {pressure_seed}", 220),
            roster_character_id=retrieved.entry.character_id,
            roster_public_summary=trim_ellipsis(public_summary, 220),
            portrait_url=retrieved.entry.portrait_url,
            portrait_variants=retrieved.entry.portrait_variants,
            template_version=retrieved.entry.template_version or retrieved.entry.source_fingerprint,
        )
        return member.model_copy(
            update={
                "story_instance": default_story_instance_snapshot(
                    base_member=member,
                    gender_lock=retrieved.entry.gender_lock,
                )
            }
        )


def build_character_roster_service(settings: Settings) -> CharacterRosterService:
    return _build_character_roster_service(settings)


def _build_character_roster_service(
    settings: Settings,
    *,
    gateway_core: CapabilityGatewayCore | None = None,
) -> CharacterRosterService:
    embedding_provider = build_character_embedding_provider(settings, gateway_core=gateway_core)
    knowledge_retriever = build_character_knowledge_retriever(
        settings,
        embedding_provider=embedding_provider,
    )
    if not settings.roster_enabled:
        return CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=embedding_provider,
            max_supporting_cast_selections=settings.roster_max_supporting_cast_selections,
            knowledge_retriever=knowledge_retriever,
        )
    runtime_catalog = ensure_character_roster_runtime_catalog(settings)
    return CharacterRosterService(
        enabled=True,
        catalog_version=(
            knowledge_retriever.current_snapshot_version()
            if knowledge_retriever is not None and runtime_catalog is None
            else (runtime_catalog.catalog_version if runtime_catalog is not None else None)
        ),
        catalog=runtime_catalog.entries if runtime_catalog is not None else (),
        embedding_provider=embedding_provider,
        max_supporting_cast_selections=settings.roster_max_supporting_cast_selections,
        knowledge_retriever=knowledge_retriever,
    )


@lru_cache
def get_character_roster_service() -> CharacterRosterService:
    return _build_character_roster_service(get_settings())

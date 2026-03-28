from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.config import Settings
from rpg_backend.roster.contracts import (
    CharacterRosterCatalogError,
    CharacterRosterRuntimeCatalog,
    CharacterRosterSourceEntry,
)


def load_character_roster_source_catalog(path: str | Path) -> tuple[CharacterRosterSourceEntry, ...]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        raise CharacterRosterCatalogError(f"roster source catalog not found: {resolved_path}")
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise CharacterRosterCatalogError("roster source catalog must be a JSON array")
    entries = tuple(CharacterRosterSourceEntry.from_payload(item) for item in payload)
    if not entries:
        raise CharacterRosterCatalogError("roster source catalog must contain at least one entry")
    return entries


def load_character_roster_runtime_catalog(path: str | Path) -> CharacterRosterRuntimeCatalog:
    resolved_path = Path(path)
    if not resolved_path.exists():
        raise CharacterRosterCatalogError(f"roster runtime catalog not found: {resolved_path}")
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CharacterRosterCatalogError("roster runtime catalog must be a JSON object")
    catalog = CharacterRosterRuntimeCatalog.from_payload(payload)
    if not catalog.entries:
        raise CharacterRosterCatalogError("roster runtime catalog must contain at least one entry")
    return catalog


def ensure_character_roster_runtime_catalog(settings: Settings) -> CharacterRosterRuntimeCatalog | None:
    if not settings.roster_enabled:
        return None
    if settings.character_knowledge_enabled and str(settings.character_knowledge_database_url or "").strip():
        return None
    return load_character_roster_runtime_catalog(settings.roster_runtime_catalog_path)

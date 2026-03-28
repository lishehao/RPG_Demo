from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from rpg_backend.roster.contracts import (
    CharacterRosterCatalogError,
    CharacterRosterEntry,
    CharacterRosterRuntimeCatalog,
    CharacterRosterSourceEntry,
)
from rpg_backend.roster.embeddings import CharacterEmbeddingProvider
from rpg_backend.roster.loader import load_character_roster_runtime_catalog, load_character_roster_source_catalog


_SOURCE_REQUIRED_KEYS = {
    "character_id",
    "slug",
    "name_en",
    "name_zh",
    "public_summary_en",
    "public_summary_zh",
    "role_hint_en",
    "role_hint_zh",
    "agenda_seed_en",
    "agenda_seed_zh",
    "red_line_seed_en",
    "red_line_seed_zh",
    "pressure_signature_seed_en",
    "pressure_signature_seed_zh",
    "theme_tags",
    "setting_tags",
    "tone_tags",
    "conflict_tags",
    "slot_tags",
    "retrieval_terms",
}
_SOURCE_OPTIONAL_KEYS = {"portrait_url", "default_portrait_url", "portrait_variants", "rarity_weight"}
_SOURCE_OPTIONAL_KEYS |= {
    "gender_lock",
    "personality_core_en",
    "personality_core_zh",
    "experience_anchor_en",
    "experience_anchor_zh",
    "identity_lock_notes_en",
    "identity_lock_notes_zh",
}
_TAG_VALUE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_HTTP_URL_PATTERN = re.compile(r"^https?://")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _catalog_version(entries: tuple[CharacterRosterSourceEntry, ...]) -> str:
    digest = hashlib.sha256(
        _canonical_json([entry.to_payload() for entry in entries]).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _source_fingerprint(entry: CharacterRosterSourceEntry) -> str:
    digest = hashlib.sha256(_canonical_json(entry.to_payload()).encode("utf-8")).hexdigest()
    return digest[:16]


def build_retrieval_text(entry: CharacterRosterSourceEntry) -> str:
    parts = [
        entry.name_en,
        entry.name_zh,
        entry.role_hint_en,
        entry.role_hint_zh,
        entry.public_summary_en,
        entry.public_summary_zh,
        entry.agenda_seed_en,
        entry.agenda_seed_zh,
        entry.red_line_seed_en,
        entry.red_line_seed_zh,
        entry.pressure_signature_seed_en,
        entry.pressure_signature_seed_zh,
        entry.personality_core_en or "",
        entry.personality_core_zh or "",
        entry.experience_anchor_en or "",
        entry.experience_anchor_zh or "",
        entry.identity_lock_notes_en or "",
        entry.identity_lock_notes_zh or "",
        " ".join(entry.theme_tags),
        " ".join(entry.setting_tags),
        " ".join(entry.tone_tags),
        " ".join(entry.conflict_tags),
        " ".join(entry.slot_tags),
        " ".join(entry.retrieval_terms),
    ]
    return " ".join(part.strip() for part in parts if part.strip())


def validate_source_catalog(path: str | Path) -> tuple[CharacterRosterSourceEntry, ...]:
    resolved_path = Path(path)
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise CharacterRosterCatalogError("roster source catalog must be a non-empty JSON array")
    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    entries: list[CharacterRosterSourceEntry] = []
    for index, raw_entry in enumerate(payload):
        if not isinstance(raw_entry, dict):
            raise CharacterRosterCatalogError(f"roster source entry #{index} must be a JSON object")
        keys = set(raw_entry.keys())
        missing = sorted(_SOURCE_REQUIRED_KEYS - keys)
        if missing:
            raise CharacterRosterCatalogError(
                f"roster source entry #{index} missing required keys: {', '.join(missing)}"
            )
        extra = sorted(keys - _SOURCE_REQUIRED_KEYS - _SOURCE_OPTIONAL_KEYS)
        if extra:
            raise CharacterRosterCatalogError(
                f"roster source entry #{index} has unsupported keys: {', '.join(extra)}"
            )
        entry = CharacterRosterSourceEntry.from_payload(raw_entry)
        if entry.character_id in seen_ids:
            raise CharacterRosterCatalogError(f"duplicate roster character_id: {entry.character_id}")
        if entry.slug in seen_slugs:
            raise CharacterRosterCatalogError(f"duplicate roster slug: {entry.slug}")
        seen_ids.add(entry.character_id)
        seen_slugs.add(entry.slug)
        if entry.portrait_url and not _HTTP_URL_PATTERN.match(entry.portrait_url):
            raise CharacterRosterCatalogError(
                f"roster entry '{entry.character_id}' portrait_url must be http/https when present"
            )
        if entry.default_portrait_url and not _HTTP_URL_PATTERN.match(entry.default_portrait_url):
            raise CharacterRosterCatalogError(
                f"roster entry '{entry.character_id}' default_portrait_url must be http/https when present"
            )
        if entry.portrait_variants:
            invalid_variant_keys = sorted(
                key for key in entry.portrait_variants.keys() if key not in {"negative", "neutral", "positive"}
            )
            if invalid_variant_keys:
                raise CharacterRosterCatalogError(
                    f"roster entry '{entry.character_id}' portrait_variants has unsupported keys: {', '.join(invalid_variant_keys)}"
                )
            invalid_variant_urls = sorted(
                key for key, value in entry.portrait_variants.items() if value and not _HTTP_URL_PATTERN.match(value)
            )
            if invalid_variant_urls:
                raise CharacterRosterCatalogError(
                    f"roster entry '{entry.character_id}' portrait_variants must use http/https URLs for: {', '.join(invalid_variant_urls)}"
                )
        if entry.portrait_variants is not None:
            required_variant_keys = {"positive", "neutral", "negative"}
            actual_variant_keys = set(entry.portrait_variants.keys())
            if actual_variant_keys != required_variant_keys:
                raise CharacterRosterCatalogError(
                    f"roster entry '{entry.character_id}' portrait_variants must contain exactly positive, neutral, negative"
                )
            for key, value in entry.portrait_variants.items():
                if not _HTTP_URL_PATTERN.match(str(value)):
                    raise CharacterRosterCatalogError(
                        f"roster entry '{entry.character_id}' portrait_variants['{key}'] must be http/https"
                    )
            if entry.portrait_url != entry.portrait_variants["neutral"]:
                raise CharacterRosterCatalogError(
                    f"roster entry '{entry.character_id}' portrait_url must equal portrait_variants.neutral"
                )
        for field_name in (
            "name_en",
            "name_zh",
            "public_summary_en",
            "public_summary_zh",
            "role_hint_en",
            "role_hint_zh",
            "agenda_seed_en",
            "agenda_seed_zh",
            "red_line_seed_en",
            "red_line_seed_zh",
            "pressure_signature_seed_en",
            "pressure_signature_seed_zh",
        ):
            value = str(getattr(entry, field_name)).strip()
            if not value:
                raise CharacterRosterCatalogError(
                    f"roster entry '{entry.character_id}' field '{field_name}' cannot be blank"
                )
        if entry.gender_lock is not None and entry.gender_lock not in {"female", "male", "nonbinary", "unspecified"}:
            raise CharacterRosterCatalogError(
                f"roster entry '{entry.character_id}' gender_lock must be female, male, nonbinary, or unspecified"
            )
        template_profile_fields = (
            "personality_core_en",
            "personality_core_zh",
            "experience_anchor_en",
            "experience_anchor_zh",
            "identity_lock_notes_en",
            "identity_lock_notes_zh",
        )
        present_template_profile_fields = [
            field_name
            for field_name in template_profile_fields
            if str(getattr(entry, field_name) or "").strip()
        ]
        if present_template_profile_fields and len(present_template_profile_fields) != len(template_profile_fields):
            raise CharacterRosterCatalogError(
                f"roster entry '{entry.character_id}' template profile must include all localized fields when present"
            )
        if present_template_profile_fields and not str(entry.gender_lock or "").strip():
            raise CharacterRosterCatalogError(
                f"roster entry '{entry.character_id}' template profile requires gender_lock"
            )
        for tag_field in (
            "theme_tags",
            "setting_tags",
            "tone_tags",
            "conflict_tags",
            "slot_tags",
            "retrieval_terms",
        ):
            values = tuple(str(item).strip() for item in getattr(entry, tag_field))
            if not values:
                raise CharacterRosterCatalogError(
                    f"roster entry '{entry.character_id}' field '{tag_field}' must be non-empty"
                )
            if tag_field == "slot_tags":
                invalid = sorted(value for value in values if value not in {"anchor", "guardian", "broker", "witness", "civic"})
            else:
                invalid = sorted(value for value in values if not _TAG_VALUE_PATTERN.match(value))
            if invalid:
                raise CharacterRosterCatalogError(
                    f"roster entry '{entry.character_id}' field '{tag_field}' has invalid values: {', '.join(invalid)}"
                )
        entries.append(entry)
    return tuple(entries)


def read_runtime_catalog_if_present(path: str | Path) -> CharacterRosterRuntimeCatalog | None:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return None
    return load_character_roster_runtime_catalog(resolved_path)


def build_runtime_catalog(
    source_entries: tuple[CharacterRosterSourceEntry, ...],
    *,
    existing_runtime_catalog: CharacterRosterRuntimeCatalog | None = None,
) -> CharacterRosterRuntimeCatalog:
    existing_by_id = {
        entry.character_id: entry
        for entry in (existing_runtime_catalog.entries if existing_runtime_catalog is not None else ())
    }
    runtime_entries: list[CharacterRosterEntry] = []
    for source_entry in source_entries:
        fingerprint = _source_fingerprint(source_entry)
        existing_entry = existing_by_id.get(source_entry.character_id)
        embedding_vector = (
            existing_entry.embedding_vector
            if existing_entry is not None and existing_entry.source_fingerprint == fingerprint
            else None
        )
        runtime_entries.append(
            CharacterRosterEntry(
                character_id=source_entry.character_id,
                slug=source_entry.slug,
                name_en=source_entry.name_en,
                name_zh=source_entry.name_zh,
                portrait_url=source_entry.portrait_url,
                default_portrait_url=source_entry.default_portrait_url,
                portrait_variants=source_entry.portrait_variants,
                public_summary_en=source_entry.public_summary_en,
                public_summary_zh=source_entry.public_summary_zh,
                role_hint_en=source_entry.role_hint_en,
                role_hint_zh=source_entry.role_hint_zh,
                agenda_seed_en=source_entry.agenda_seed_en,
                agenda_seed_zh=source_entry.agenda_seed_zh,
                red_line_seed_en=source_entry.red_line_seed_en,
                red_line_seed_zh=source_entry.red_line_seed_zh,
                pressure_signature_seed_en=source_entry.pressure_signature_seed_en,
                pressure_signature_seed_zh=source_entry.pressure_signature_seed_zh,
                personality_core_en=source_entry.personality_core_en,
                personality_core_zh=source_entry.personality_core_zh,
                experience_anchor_en=source_entry.experience_anchor_en,
                experience_anchor_zh=source_entry.experience_anchor_zh,
                identity_lock_notes_en=source_entry.identity_lock_notes_en,
                identity_lock_notes_zh=source_entry.identity_lock_notes_zh,
                theme_tags=source_entry.theme_tags,
                setting_tags=source_entry.setting_tags,
                tone_tags=source_entry.tone_tags,
                conflict_tags=source_entry.conflict_tags,
                slot_tags=source_entry.slot_tags,
                retrieval_terms=source_entry.retrieval_terms,
                retrieval_text=build_retrieval_text(source_entry),
                source_fingerprint=fingerprint,
                embedding_vector=embedding_vector,
                rarity_weight=source_entry.rarity_weight,
                template_version=fingerprint,
                gender_lock=source_entry.gender_lock,
            )
        )
    return CharacterRosterRuntimeCatalog(
        catalog_version=_catalog_version(source_entries),
        built_at=datetime.now(timezone.utc).isoformat(),
        entry_count=len(runtime_entries),
        entries=tuple(runtime_entries),
    )


def embed_runtime_catalog(
    source_entries: tuple[CharacterRosterSourceEntry, ...],
    *,
    embedding_provider: CharacterEmbeddingProvider,
    existing_runtime_catalog: CharacterRosterRuntimeCatalog | None = None,
    force: bool = False,
) -> CharacterRosterRuntimeCatalog:
    runtime_catalog = build_runtime_catalog(
        source_entries,
        existing_runtime_catalog=existing_runtime_catalog,
    )
    embedded_entries: list[CharacterRosterEntry] = []
    for entry in runtime_catalog.entries:
        embedding_vector = entry.embedding_vector
        if force or embedding_vector is None:
            embedding = embedding_provider.embed_text(entry.retrieval_text)
            embedding_vector = tuple(float(item) for item in embedding) if embedding is not None else None
        embedded_entries.append(
            CharacterRosterEntry(
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
                retrieval_text=entry.retrieval_text,
                source_fingerprint=entry.source_fingerprint,
                embedding_vector=embedding_vector,
                rarity_weight=entry.rarity_weight,
                template_version=entry.template_version,
                gender_lock=entry.gender_lock,
            )
        )
    return CharacterRosterRuntimeCatalog(
        catalog_version=runtime_catalog.catalog_version,
        built_at=datetime.now(timezone.utc).isoformat(),
        entry_count=len(embedded_entries),
        entries=tuple(embedded_entries),
    )


def write_runtime_catalog(path: str | Path, catalog: CharacterRosterRuntimeCatalog) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps(catalog.to_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_source_catalog(path: str | Path, entries: tuple[CharacterRosterSourceEntry, ...]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps([entry.to_payload() for entry in entries], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_and_validate_source_catalog(path: str | Path) -> tuple[CharacterRosterSourceEntry, ...]:
    # Reuse loader parsing so admin and runtime stay on the same data model.
    _ = load_character_roster_source_catalog(path)
    return validate_source_catalog(path)

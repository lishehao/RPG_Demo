from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


RosterSlotTag = Literal["anchor", "guardian", "broker", "witness", "civic"]
RosterSelectionMode = Literal["embedding+lexical", "lexical_only"]
PortraitVariantKey = Literal["positive", "neutral", "negative"]
PortraitVariantsMap = dict[PortraitVariantKey, str]
GenderLock = Literal["female", "male", "nonbinary", "unspecified"]


def _normalize_portrait_variants(payload: Any) -> PortraitVariantsMap | None:
    if not payload:
        return None
    if not isinstance(payload, dict):
        raise CharacterRosterCatalogError("portrait_variants must be a JSON object when present")
    invalid_keys = sorted(str(key) for key in payload.keys() if str(key) not in {"positive", "neutral", "negative"})
    if invalid_keys:
        raise CharacterRosterCatalogError(
            f"portrait_variants has unsupported keys: {', '.join(invalid_keys)}"
        )
    normalized = {
        str(key): str(value)
        for key, value in payload.items()
        if value
    }
    return normalized or None


class CharacterRosterCatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class CharacterRosterSourceEntry:
    character_id: str
    slug: str
    name_en: str
    name_zh: str
    portrait_url: str | None
    default_portrait_url: str | None
    portrait_variants: PortraitVariantsMap | None
    public_summary_en: str
    public_summary_zh: str
    role_hint_en: str
    role_hint_zh: str
    agenda_seed_en: str
    agenda_seed_zh: str
    red_line_seed_en: str
    red_line_seed_zh: str
    pressure_signature_seed_en: str
    pressure_signature_seed_zh: str
    theme_tags: tuple[str, ...]
    setting_tags: tuple[str, ...]
    tone_tags: tuple[str, ...]
    conflict_tags: tuple[str, ...]
    slot_tags: tuple[RosterSlotTag, ...]
    retrieval_terms: tuple[str, ...]
    rarity_weight: float = 1.0
    gender_lock: GenderLock | None = None
    personality_core_en: str | None = None
    personality_core_zh: str | None = None
    experience_anchor_en: str | None = None
    experience_anchor_zh: str | None = None
    identity_lock_notes_en: str | None = None
    identity_lock_notes_zh: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CharacterRosterSourceEntry":
        portrait_variants = _normalize_portrait_variants(payload.get("portrait_variants"))
        portrait_url = str(payload["portrait_url"]) if payload.get("portrait_url") else None
        default_portrait_url = str(payload["default_portrait_url"]) if payload.get("default_portrait_url") else None
        resolved_default_portrait_url = default_portrait_url or portrait_url or (
            portrait_variants.get("neutral") if portrait_variants else None
        )
        return cls(
            character_id=str(payload["character_id"]),
            slug=str(payload["slug"]),
            name_en=str(payload["name_en"]),
            name_zh=str(payload["name_zh"]),
            portrait_url=portrait_url or resolved_default_portrait_url,
            default_portrait_url=resolved_default_portrait_url,
            portrait_variants=portrait_variants,
            public_summary_en=str(payload["public_summary_en"]),
            public_summary_zh=str(payload["public_summary_zh"]),
            role_hint_en=str(payload["role_hint_en"]),
            role_hint_zh=str(payload["role_hint_zh"]),
            agenda_seed_en=str(payload["agenda_seed_en"]),
            agenda_seed_zh=str(payload["agenda_seed_zh"]),
            red_line_seed_en=str(payload["red_line_seed_en"]),
            red_line_seed_zh=str(payload["red_line_seed_zh"]),
            pressure_signature_seed_en=str(payload["pressure_signature_seed_en"]),
            pressure_signature_seed_zh=str(payload["pressure_signature_seed_zh"]),
            personality_core_en=str(payload["personality_core_en"]) if payload.get("personality_core_en") else None,
            personality_core_zh=str(payload["personality_core_zh"]) if payload.get("personality_core_zh") else None,
            experience_anchor_en=str(payload["experience_anchor_en"]) if payload.get("experience_anchor_en") else None,
            experience_anchor_zh=str(payload["experience_anchor_zh"]) if payload.get("experience_anchor_zh") else None,
            identity_lock_notes_en=str(payload["identity_lock_notes_en"]) if payload.get("identity_lock_notes_en") else None,
            identity_lock_notes_zh=str(payload["identity_lock_notes_zh"]) if payload.get("identity_lock_notes_zh") else None,
            theme_tags=tuple(str(item) for item in payload.get("theme_tags") or ()),
            setting_tags=tuple(str(item) for item in payload.get("setting_tags") or ()),
            tone_tags=tuple(str(item) for item in payload.get("tone_tags") or ()),
            conflict_tags=tuple(str(item) for item in payload.get("conflict_tags") or ()),
            slot_tags=tuple(str(item) for item in payload.get("slot_tags") or ()),
            retrieval_terms=tuple(str(item) for item in payload.get("retrieval_terms") or ()),
            rarity_weight=float(payload.get("rarity_weight") or 1.0),
            gender_lock=str(payload["gender_lock"]) if payload.get("gender_lock") else None,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "slug": self.slug,
            "name_en": self.name_en,
            "name_zh": self.name_zh,
            "portrait_url": self.portrait_url,
            "default_portrait_url": self.default_portrait_url,
            "portrait_variants": dict(self.portrait_variants) if self.portrait_variants is not None else None,
            "public_summary_en": self.public_summary_en,
            "public_summary_zh": self.public_summary_zh,
            "role_hint_en": self.role_hint_en,
            "role_hint_zh": self.role_hint_zh,
            "agenda_seed_en": self.agenda_seed_en,
            "agenda_seed_zh": self.agenda_seed_zh,
            "red_line_seed_en": self.red_line_seed_en,
            "red_line_seed_zh": self.red_line_seed_zh,
            "pressure_signature_seed_en": self.pressure_signature_seed_en,
            "pressure_signature_seed_zh": self.pressure_signature_seed_zh,
            "personality_core_en": self.personality_core_en,
            "personality_core_zh": self.personality_core_zh,
            "experience_anchor_en": self.experience_anchor_en,
            "experience_anchor_zh": self.experience_anchor_zh,
            "identity_lock_notes_en": self.identity_lock_notes_en,
            "identity_lock_notes_zh": self.identity_lock_notes_zh,
            "theme_tags": list(self.theme_tags),
            "setting_tags": list(self.setting_tags),
            "tone_tags": list(self.tone_tags),
            "conflict_tags": list(self.conflict_tags),
            "slot_tags": list(self.slot_tags),
            "retrieval_terms": list(self.retrieval_terms),
            "rarity_weight": self.rarity_weight,
            "gender_lock": self.gender_lock,
        }


@dataclass(frozen=True)
class CharacterRosterEntry:
    character_id: str
    slug: str
    name_en: str
    name_zh: str
    portrait_url: str | None
    default_portrait_url: str | None
    portrait_variants: PortraitVariantsMap | None
    public_summary_en: str
    public_summary_zh: str
    role_hint_en: str
    role_hint_zh: str
    agenda_seed_en: str
    agenda_seed_zh: str
    red_line_seed_en: str
    red_line_seed_zh: str
    pressure_signature_seed_en: str
    pressure_signature_seed_zh: str
    theme_tags: tuple[str, ...]
    setting_tags: tuple[str, ...]
    tone_tags: tuple[str, ...]
    conflict_tags: tuple[str, ...]
    slot_tags: tuple[RosterSlotTag, ...]
    retrieval_terms: tuple[str, ...]
    retrieval_text: str
    source_fingerprint: str
    embedding_vector: tuple[float, ...] | None = None
    rarity_weight: float = 1.0
    template_version: str | None = None
    gender_lock: GenderLock | None = None
    personality_core_en: str | None = None
    personality_core_zh: str | None = None
    experience_anchor_en: str | None = None
    experience_anchor_zh: str | None = None
    identity_lock_notes_en: str | None = None
    identity_lock_notes_zh: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CharacterRosterEntry":
        portrait_variants = _normalize_portrait_variants(payload.get("portrait_variants"))
        portrait_url = str(payload["portrait_url"]) if payload.get("portrait_url") else None
        default_portrait_url = str(payload["default_portrait_url"]) if payload.get("default_portrait_url") else None
        resolved_default_portrait_url = default_portrait_url or portrait_url or (
            portrait_variants.get("neutral") if portrait_variants else None
        )
        return cls(
            character_id=str(payload["character_id"]),
            slug=str(payload["slug"]),
            name_en=str(payload["name_en"]),
            name_zh=str(payload["name_zh"]),
            portrait_url=portrait_url or resolved_default_portrait_url,
            default_portrait_url=resolved_default_portrait_url,
            portrait_variants=portrait_variants,
            public_summary_en=str(payload["public_summary_en"]),
            public_summary_zh=str(payload["public_summary_zh"]),
            role_hint_en=str(payload["role_hint_en"]),
            role_hint_zh=str(payload["role_hint_zh"]),
            agenda_seed_en=str(payload["agenda_seed_en"]),
            agenda_seed_zh=str(payload["agenda_seed_zh"]),
            red_line_seed_en=str(payload["red_line_seed_en"]),
            red_line_seed_zh=str(payload["red_line_seed_zh"]),
            pressure_signature_seed_en=str(payload["pressure_signature_seed_en"]),
            pressure_signature_seed_zh=str(payload["pressure_signature_seed_zh"]),
            personality_core_en=str(payload["personality_core_en"]) if payload.get("personality_core_en") else None,
            personality_core_zh=str(payload["personality_core_zh"]) if payload.get("personality_core_zh") else None,
            experience_anchor_en=str(payload["experience_anchor_en"]) if payload.get("experience_anchor_en") else None,
            experience_anchor_zh=str(payload["experience_anchor_zh"]) if payload.get("experience_anchor_zh") else None,
            identity_lock_notes_en=str(payload["identity_lock_notes_en"]) if payload.get("identity_lock_notes_en") else None,
            identity_lock_notes_zh=str(payload["identity_lock_notes_zh"]) if payload.get("identity_lock_notes_zh") else None,
            theme_tags=tuple(str(item) for item in payload.get("theme_tags") or ()),
            setting_tags=tuple(str(item) for item in payload.get("setting_tags") or ()),
            tone_tags=tuple(str(item) for item in payload.get("tone_tags") or ()),
            conflict_tags=tuple(str(item) for item in payload.get("conflict_tags") or ()),
            slot_tags=tuple(str(item) for item in payload.get("slot_tags") or ()),
            retrieval_terms=tuple(str(item) for item in payload.get("retrieval_terms") or ()),
            retrieval_text=str(payload.get("retrieval_text") or ""),
            source_fingerprint=str(payload.get("source_fingerprint") or ""),
            embedding_vector=tuple(float(item) for item in payload.get("embedding_vector") or ()) or None,
            rarity_weight=float(payload.get("rarity_weight") or 1.0),
            template_version=str(payload["template_version"]) if payload.get("template_version") else None,
            gender_lock=str(payload["gender_lock"]) if payload.get("gender_lock") else None,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "slug": self.slug,
            "name_en": self.name_en,
            "name_zh": self.name_zh,
            "portrait_url": self.portrait_url,
            "default_portrait_url": self.default_portrait_url,
            "portrait_variants": dict(self.portrait_variants) if self.portrait_variants is not None else None,
            "public_summary_en": self.public_summary_en,
            "public_summary_zh": self.public_summary_zh,
            "role_hint_en": self.role_hint_en,
            "role_hint_zh": self.role_hint_zh,
            "agenda_seed_en": self.agenda_seed_en,
            "agenda_seed_zh": self.agenda_seed_zh,
            "red_line_seed_en": self.red_line_seed_en,
            "red_line_seed_zh": self.red_line_seed_zh,
            "pressure_signature_seed_en": self.pressure_signature_seed_en,
            "pressure_signature_seed_zh": self.pressure_signature_seed_zh,
            "personality_core_en": self.personality_core_en,
            "personality_core_zh": self.personality_core_zh,
            "experience_anchor_en": self.experience_anchor_en,
            "experience_anchor_zh": self.experience_anchor_zh,
            "identity_lock_notes_en": self.identity_lock_notes_en,
            "identity_lock_notes_zh": self.identity_lock_notes_zh,
            "theme_tags": list(self.theme_tags),
            "setting_tags": list(self.setting_tags),
            "tone_tags": list(self.tone_tags),
            "conflict_tags": list(self.conflict_tags),
            "slot_tags": list(self.slot_tags),
            "retrieval_terms": list(self.retrieval_terms),
            "retrieval_text": self.retrieval_text,
            "source_fingerprint": self.source_fingerprint,
            "embedding_vector": list(self.embedding_vector) if self.embedding_vector is not None else None,
            "rarity_weight": self.rarity_weight,
            "template_version": self.template_version,
            "gender_lock": self.gender_lock,
            "personality_core_en": self.personality_core_en,
            "personality_core_zh": self.personality_core_zh,
            "experience_anchor_en": self.experience_anchor_en,
            "experience_anchor_zh": self.experience_anchor_zh,
            "identity_lock_notes_en": self.identity_lock_notes_en,
            "identity_lock_notes_zh": self.identity_lock_notes_zh,
        }


@dataclass(frozen=True)
class CharacterRosterRuntimeCatalog:
    catalog_version: str
    built_at: str
    entry_count: int
    entries: tuple[CharacterRosterEntry, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CharacterRosterRuntimeCatalog":
        entries = tuple(CharacterRosterEntry.from_payload(item) for item in payload.get("entries") or ())
        entry_count = int(payload.get("entry_count") or 0)
        if entry_count != len(entries):
            raise CharacterRosterCatalogError(
                f"runtime catalog entry_count mismatch: declared={entry_count} actual={len(entries)}"
            )
        if not str(payload.get("catalog_version") or "").strip():
            raise CharacterRosterCatalogError("runtime catalog missing catalog_version")
        if not str(payload.get("built_at") or "").strip():
            raise CharacterRosterCatalogError("runtime catalog missing built_at")
        for entry in entries:
            if not entry.retrieval_text.strip():
                raise CharacterRosterCatalogError(
                    f"runtime catalog entry '{entry.character_id}' missing retrieval_text"
                )
            if not entry.source_fingerprint.strip():
                raise CharacterRosterCatalogError(
                    f"runtime catalog entry '{entry.character_id}' missing source_fingerprint"
                )
        return cls(
            catalog_version=str(payload["catalog_version"]),
            built_at=str(payload["built_at"]),
            entry_count=entry_count,
            entries=entries,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "catalog_version": self.catalog_version,
            "built_at": self.built_at,
            "entry_count": self.entry_count,
            "entries": [entry.to_payload() for entry in self.entries],
        }


@dataclass(frozen=True)
class RetrievedRosterCharacter:
    entry: CharacterRosterEntry
    slot_index: int
    slot_tag: RosterSlotTag
    score: float
    score_breakdown: dict[str, float]
    selection_mode: RosterSelectionMode
    fallback_reason: str | None = None


@dataclass(frozen=True)
class CharacterRosterSelectionResult:
    roster_enabled: bool
    catalog_version: str | None
    assignments: tuple[RetrievedRosterCharacter, ...]
    trace: tuple[dict[str, Any], ...]

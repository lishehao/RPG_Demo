from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from rpg_backend.character_knowledge.contracts import (
    CharacterKnowledgeDocType,
    CharacterKnowledgeLocalization,
    CharacterKnowledgePortrait,
    CharacterKnowledgeRetrievalDoc,
    CharacterKnowledgeSourceKind,
    CharacterKnowledgeUpsertBundle,
)
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from rpg_backend.roster.template_profiles import resolved_template_profile

_TEMPLATE_PREFIX_AFFINITY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("roster_blackout_", ("blackout_referendum_story", "public_order_story")),
    ("roster_bridge_", ("bridge_ration_story", "logistics_story")),
    ("roster_harbor_", ("harbor_quarantine_story", "logistics_story")),
    ("roster_logistics_", ("logistics_story",)),
    ("roster_warning_", ("warning_record_story", "truth_record_story")),
    ("roster_archive_", ("archive_vote_story", "truth_record_story")),
    ("roster_truth_", ("truth_record_story",)),
    ("roster_legitimacy_", ("legitimacy_story",)),
    ("roster_order_", ("public_order_story",)),
    ("roster_generic_", ("generic_civic_story",)),
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_fingerprint_for_entry(entry: CharacterRosterSourceEntry) -> str:
    return hashlib.sha256(_canonical_json(entry.to_payload()).encode("utf-8")).hexdigest()[:16]


def snapshot_version_for_entries(entries: tuple[CharacterRosterSourceEntry, ...]) -> str:
    digest = hashlib.sha256(
        _canonical_json([entry.to_payload() for entry in entries]).encode("utf-8")
    ).hexdigest()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{timestamp}_{digest[:12]}"


def derive_template_affinity(entry: CharacterRosterSourceEntry) -> tuple[str, ...]:
    character_id = entry.character_id.casefold()
    for prefix, affinities in _TEMPLATE_PREFIX_AFFINITY:
        if character_id.startswith(prefix):
            return affinities
    derived: list[str] = []
    for value in (*entry.theme_tags, *entry.setting_tags):
        normalized = str(value).strip()
        if normalized and normalized not in derived:
            derived.append(normalized)
    return tuple(derived) or ("generic_civic_story",)


def build_character_knowledge_bundle(
    entry: CharacterRosterSourceEntry,
    *,
    source_kind: CharacterKnowledgeSourceKind,
    snapshot_version: str,
) -> CharacterKnowledgeUpsertBundle:
    source_fingerprint = source_fingerprint_for_entry(entry)
    profile_en = resolved_template_profile(entry, "en")
    profile_zh = resolved_template_profile(entry, "zh")
    portraits = tuple(
        CharacterKnowledgePortrait(variant_key=variant_key, public_url=public_url)
        for variant_key, public_url in sorted((entry.portrait_variants or {}).items())
        if public_url
    )
    return CharacterKnowledgeUpsertBundle(
        character_id=entry.character_id,
        slug=entry.slug,
        active_status="active",
        source_kind=source_kind,
        roster_state="formal",
        source_fingerprint=source_fingerprint,
        snapshot_version=snapshot_version,
        template_version=source_fingerprint,
        gender_lock=entry.gender_lock,
        rarity_weight=entry.rarity_weight,
        theme_tags=entry.theme_tags,
        setting_tags=entry.setting_tags,
        tone_tags=entry.tone_tags,
        conflict_tags=entry.conflict_tags,
        slot_tags=entry.slot_tags,
        retrieval_terms=entry.retrieval_terms,
        template_affinity=derive_template_affinity(entry),
        localizations=(
            CharacterKnowledgeLocalization(
                language="en",
                name=entry.name_en,
                public_summary=entry.public_summary_en,
                role_hint=entry.role_hint_en,
                agenda=entry.agenda_seed_en,
                red_line=entry.red_line_seed_en,
                pressure_signature=entry.pressure_signature_seed_en,
                personality_core=profile_en.personality_core,
                experience_anchor=profile_en.experience_anchor,
                identity_lock_notes=profile_en.identity_lock_notes,
            ),
            CharacterKnowledgeLocalization(
                language="zh",
                name=entry.name_zh,
                public_summary=entry.public_summary_zh,
                role_hint=entry.role_hint_zh,
                agenda=entry.agenda_seed_zh,
                red_line=entry.red_line_seed_zh,
                pressure_signature=entry.pressure_signature_seed_zh,
                personality_core=profile_zh.personality_core,
                experience_anchor=profile_zh.experience_anchor,
                identity_lock_notes=profile_zh.identity_lock_notes,
            ),
        ),
        portraits=portraits,
    )


def _doc_text(
    bundle: CharacterKnowledgeUpsertBundle,
    localization: CharacterKnowledgeLocalization,
    *,
    doc_type: CharacterKnowledgeDocType,
) -> str:
    shared_tags = " ".join(
        [
            *bundle.theme_tags,
            *bundle.setting_tags,
            *bundle.tone_tags,
            *bundle.conflict_tags,
            *bundle.slot_tags,
            *bundle.retrieval_terms,
            *bundle.template_affinity,
        ]
    ).strip()
    if doc_type == "identity":
        return " ".join(
            part
            for part in (
                localization.name,
                localization.role_hint,
                localization.public_summary,
                localization.personality_core or "",
                localization.experience_anchor or "",
                shared_tags,
            )
            if part.strip()
        )
    if doc_type == "procedural_role":
        return " ".join(
            part
            for part in (
                localization.role_hint,
                localization.agenda,
                localization.red_line,
                localization.experience_anchor or "",
                " ".join(bundle.slot_tags),
                " ".join(bundle.setting_tags),
            )
            if part.strip()
        )
    if doc_type == "pressure_profile":
        return " ".join(
            part
            for part in (
                localization.agenda,
                localization.red_line,
                localization.pressure_signature,
                localization.personality_core or "",
                " ".join(bundle.conflict_tags),
                " ".join(bundle.tone_tags),
            )
            if part.strip()
        )
    if doc_type == "template_affinity":
        return " ".join(
            part
            for part in (
                localization.role_hint,
                " ".join(bundle.template_affinity),
                localization.identity_lock_notes or "",
                " ".join(bundle.theme_tags),
                " ".join(bundle.setting_tags),
                " ".join(bundle.slot_tags),
            )
            if part.strip()
        )
    return " ".join(
        part
        for part in (
            localization.public_summary,
            localization.experience_anchor or "",
            localization.agenda,
            localization.red_line,
            localization.pressure_signature,
            " ".join(bundle.retrieval_terms),
        )
        if part.strip()
    )


def build_character_retrieval_docs(
    bundle: CharacterKnowledgeUpsertBundle,
) -> tuple[CharacterKnowledgeRetrievalDoc, ...]:
    docs: list[CharacterKnowledgeRetrievalDoc] = []
    for localization in bundle.localizations:
        for doc_type in (
            "identity",
            "procedural_role",
            "pressure_profile",
            "template_affinity",
            "public_summary",
        ):
            docs.append(
                CharacterKnowledgeRetrievalDoc(
                    character_id=bundle.character_id,
                    doc_type=doc_type,
                    doc_language=localization.language,
                    text=_doc_text(bundle, localization, doc_type=doc_type),
                    metadata_json={
                        "theme_tags": list(bundle.theme_tags),
                        "setting_tags": list(bundle.setting_tags),
                        "tone_tags": list(bundle.tone_tags),
                        "conflict_tags": list(bundle.conflict_tags),
                        "slot_tags": list(bundle.slot_tags),
                        "retrieval_terms": list(bundle.retrieval_terms),
                        "template_affinity": list(bundle.template_affinity),
                        "template_version": bundle.template_version,
                        "gender_lock": bundle.gender_lock,
                        "source_fingerprint": bundle.source_fingerprint,
                    },
                    source_fingerprint=bundle.source_fingerprint,
                )
            )
    return tuple(docs)

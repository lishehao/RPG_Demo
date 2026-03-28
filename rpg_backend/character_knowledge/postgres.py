from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from typing import Any, Iterator

from rpg_backend.character_knowledge.contracts import (
    CharacterKnowledgeCandidate,
    CharacterKnowledgeDocLanguage,
    CharacterKnowledgeError,
    CharacterKnowledgeQueryMode,
    CharacterKnowledgeRepository,
    CharacterKnowledgeRetrievalDoc,
    CharacterKnowledgeSourceKind,
    CharacterKnowledgeUpsertBundle,
)
from rpg_backend.config import Settings
from rpg_backend.roster.contracts import CharacterRosterEntry, RosterSlotTag


def _vector_literal(values: list[float] | tuple[float, ...] | None) -> str | None:
    if not values:
        return None
    return "[" + ",".join(f"{float(item):.12g}" for item in values) + "]"


def _parse_vector_text(value: str | None) -> tuple[float, ...] | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped or stripped == "[]":
        return None
    if stripped[0] == "[" and stripped[-1] == "]":
        stripped = stripped[1:-1]
    parts = [part.strip() for part in stripped.split(",") if part.strip()]
    return tuple(float(part) for part in parts) if parts else None


class CharacterKnowledgePostgresRepository(CharacterKnowledgeRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.strip()
        if not self._database_url:
            raise CharacterKnowledgeError("character knowledge database URL is required")

    def _psycopg(self):  # type: ignore[no-untyped-def]
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise CharacterKnowledgeError(
                "psycopg is required for the Postgres character knowledge repository"
            ) from exc
        return psycopg, dict_row

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        psycopg, dict_row = self._psycopg()
        connection = psycopg.connect(self._database_url, row_factory=dict_row)
        try:
            yield connection
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        statements = (
            "CREATE EXTENSION IF NOT EXISTS vector",
            """
            CREATE TABLE IF NOT EXISTS character_import_runs (
                run_id BIGSERIAL PRIMARY KEY,
                source_kind TEXT NOT NULL,
                import_mode TEXT NOT NULL,
                snapshot_version TEXT NOT NULL,
                imported_character_ids JSONB NOT NULL,
                archived_character_ids JSONB NOT NULL,
                doc_count INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS characters (
                character_id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                active_status TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                roster_state TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                snapshot_version TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS character_localizations (
                character_id TEXT NOT NULL REFERENCES characters(character_id) ON DELETE CASCADE,
                language TEXT NOT NULL,
                name TEXT NOT NULL,
                public_summary TEXT NOT NULL,
                role_hint TEXT NOT NULL,
                agenda TEXT NOT NULL,
                red_line TEXT NOT NULL,
                pressure_signature TEXT NOT NULL,
                PRIMARY KEY (character_id, language)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS character_metadata (
                character_id TEXT PRIMARY KEY REFERENCES characters(character_id) ON DELETE CASCADE,
                theme_tags TEXT[] NOT NULL,
                setting_tags TEXT[] NOT NULL,
                tone_tags TEXT[] NOT NULL,
                conflict_tags TEXT[] NOT NULL,
                slot_tags TEXT[] NOT NULL,
                retrieval_terms TEXT[] NOT NULL,
                template_affinity TEXT[] NOT NULL,
                gender_lock TEXT,
                rarity_weight DOUBLE PRECISION NOT NULL,
                metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS character_portraits (
                character_id TEXT NOT NULL REFERENCES characters(character_id) ON DELETE CASCADE,
                variant_key TEXT NOT NULL,
                public_url TEXT NOT NULL,
                source_asset_id TEXT,
                version_tag TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (character_id, variant_key)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS character_template_profiles (
                character_id TEXT NOT NULL REFERENCES characters(character_id) ON DELETE CASCADE,
                language TEXT NOT NULL,
                personality_core TEXT NOT NULL,
                experience_anchor TEXT NOT NULL,
                identity_lock_notes TEXT NOT NULL,
                template_version TEXT NOT NULL,
                PRIMARY KEY (character_id, language)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS character_retrieval_docs (
                doc_id BIGSERIAL PRIMARY KEY,
                character_id TEXT NOT NULL REFERENCES characters(character_id) ON DELETE CASCADE,
                doc_type TEXT NOT NULL,
                doc_language TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                source_fingerprint TEXT NOT NULL,
                embedding vector,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_character_import_runs_source_kind_created_at ON character_import_runs (source_kind, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_characters_source_kind_active ON characters (source_kind, active_status)",
            "CREATE INDEX IF NOT EXISTS idx_character_localizations_language ON character_localizations (language, character_id)",
            "CREATE INDEX IF NOT EXISTS idx_character_metadata_theme_tags ON character_metadata USING GIN (theme_tags)",
            "CREATE INDEX IF NOT EXISTS idx_character_metadata_slot_tags ON character_metadata USING GIN (slot_tags)",
            "CREATE INDEX IF NOT EXISTS idx_character_metadata_template_affinity ON character_metadata USING GIN (template_affinity)",
            "CREATE INDEX IF NOT EXISTS idx_character_template_profiles_language ON character_template_profiles (language, character_id)",
            "CREATE INDEX IF NOT EXISTS idx_character_retrieval_docs_character_language ON character_retrieval_docs (character_id, doc_language, doc_type)",
            "ALTER TABLE character_metadata ADD COLUMN IF NOT EXISTS gender_lock TEXT",
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            connection.commit()

    def current_snapshot_version(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
    ) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT snapshot_version
                FROM characters
                WHERE source_kind = %s AND active_status = 'active'
                ORDER BY updated_at DESC, character_id ASC
                LIMIT 1
                """,
                (source_kind,),
            ).fetchone()
        return str(row["snapshot_version"]) if row else None

    def list_active_character_ids(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
    ) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT character_id
                FROM characters
                WHERE source_kind = %s AND active_status = 'active'
                ORDER BY character_id ASC
                """,
                (source_kind,),
            ).fetchall()
        return tuple(str(row["character_id"]) for row in rows)

    def upsert_character_bundle(
        self,
        bundle: CharacterKnowledgeUpsertBundle,
        *,
        docs: tuple[CharacterKnowledgeRetrievalDoc, ...],
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO characters (
                        character_id,
                        slug,
                        active_status,
                        source_kind,
                        roster_state,
                        source_fingerprint,
                        snapshot_version,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (character_id) DO UPDATE SET
                        slug = EXCLUDED.slug,
                        active_status = EXCLUDED.active_status,
                        source_kind = EXCLUDED.source_kind,
                        roster_state = EXCLUDED.roster_state,
                        source_fingerprint = EXCLUDED.source_fingerprint,
                        snapshot_version = EXCLUDED.snapshot_version,
                        updated_at = NOW()
                    """,
                    (
                        bundle.character_id,
                        bundle.slug,
                        bundle.active_status,
                        bundle.source_kind,
                        bundle.roster_state,
                        bundle.source_fingerprint,
                        bundle.snapshot_version,
                    ),
                )
                for localization in bundle.localizations:
                    cursor.execute(
                        """
                        INSERT INTO character_localizations (
                            character_id,
                            language,
                            name,
                            public_summary,
                            role_hint,
                            agenda,
                            red_line,
                            pressure_signature
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (character_id, language) DO UPDATE SET
                            name = EXCLUDED.name,
                            public_summary = EXCLUDED.public_summary,
                            role_hint = EXCLUDED.role_hint,
                            agenda = EXCLUDED.agenda,
                            red_line = EXCLUDED.red_line,
                            pressure_signature = EXCLUDED.pressure_signature
                        """,
                        (
                            bundle.character_id,
                            localization.language,
                            localization.name,
                            localization.public_summary,
                            localization.role_hint,
                            localization.agenda,
                            localization.red_line,
                            localization.pressure_signature,
                        ),
                    )
                    if (
                        str(localization.personality_core or "").strip()
                        and str(localization.experience_anchor or "").strip()
                        and str(localization.identity_lock_notes or "").strip()
                    ):
                        cursor.execute(
                            """
                            INSERT INTO character_template_profiles (
                                character_id,
                                language,
                                personality_core,
                                experience_anchor,
                                identity_lock_notes,
                                template_version
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (character_id, language) DO UPDATE SET
                                personality_core = EXCLUDED.personality_core,
                                experience_anchor = EXCLUDED.experience_anchor,
                                identity_lock_notes = EXCLUDED.identity_lock_notes,
                                template_version = EXCLUDED.template_version
                            """,
                            (
                                bundle.character_id,
                                localization.language,
                                localization.personality_core,
                                localization.experience_anchor,
                                localization.identity_lock_notes,
                                bundle.template_version,
                            ),
                        )
                cursor.execute(
                    """
                    INSERT INTO character_metadata (
                        character_id,
                        theme_tags,
                        setting_tags,
                        tone_tags,
                        conflict_tags,
                        slot_tags,
                        retrieval_terms,
                        template_affinity,
                        gender_lock,
                        rarity_weight,
                        metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (character_id) DO UPDATE SET
                        theme_tags = EXCLUDED.theme_tags,
                        setting_tags = EXCLUDED.setting_tags,
                        tone_tags = EXCLUDED.tone_tags,
                        conflict_tags = EXCLUDED.conflict_tags,
                        slot_tags = EXCLUDED.slot_tags,
                        retrieval_terms = EXCLUDED.retrieval_terms,
                        template_affinity = EXCLUDED.template_affinity,
                        gender_lock = EXCLUDED.gender_lock,
                        rarity_weight = EXCLUDED.rarity_weight,
                        metadata_json = EXCLUDED.metadata_json
                    """,
                    (
                        bundle.character_id,
                        list(bundle.theme_tags),
                        list(bundle.setting_tags),
                        list(bundle.tone_tags),
                        list(bundle.conflict_tags),
                        list(bundle.slot_tags),
                        list(bundle.retrieval_terms),
                        list(bundle.template_affinity),
                        bundle.gender_lock,
                        bundle.rarity_weight,
                        json.dumps(
                            {
                                "theme_tags": list(bundle.theme_tags),
                                "setting_tags": list(bundle.setting_tags),
                                "tone_tags": list(bundle.tone_tags),
                                "conflict_tags": list(bundle.conflict_tags),
                                "slot_tags": list(bundle.slot_tags),
                                "retrieval_terms": list(bundle.retrieval_terms),
                                "template_affinity": list(bundle.template_affinity),
                                "gender_lock": bundle.gender_lock,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                cursor.execute("DELETE FROM character_portraits WHERE character_id = %s", (bundle.character_id,))
                for portrait in bundle.portraits:
                    cursor.execute(
                        """
                        INSERT INTO character_portraits (
                            character_id,
                            variant_key,
                            public_url,
                            source_asset_id,
                            version_tag,
                            updated_at
                        ) VALUES (%s, %s, %s, NULL, %s, NOW())
                        """,
                        (
                            bundle.character_id,
                            portrait.variant_key,
                            portrait.public_url,
                            bundle.snapshot_version,
                        ),
                    )
                cursor.execute("DELETE FROM character_retrieval_docs WHERE character_id = %s", (bundle.character_id,))
                for doc in docs:
                    embedding_literal = _vector_literal(doc.embedding_vector)
                    if embedding_literal is None:
                        cursor.execute(
                            """
                            INSERT INTO character_retrieval_docs (
                                character_id,
                                doc_type,
                                doc_language,
                                text,
                                metadata_json,
                                source_fingerprint,
                                embedding,
                                created_at,
                                updated_at
                            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, NULL, NOW(), NOW())
                            """,
                            (
                                doc.character_id,
                                doc.doc_type,
                                doc.doc_language,
                                doc.text,
                                json.dumps(doc.metadata_json, ensure_ascii=False),
                                doc.source_fingerprint,
                            ),
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO character_retrieval_docs (
                                character_id,
                                doc_type,
                                doc_language,
                                text,
                                metadata_json,
                                source_fingerprint,
                                embedding,
                                created_at,
                                updated_at
                            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s::vector, NOW(), NOW())
                            """,
                            (
                                doc.character_id,
                                doc.doc_type,
                                doc.doc_language,
                                doc.text,
                                json.dumps(doc.metadata_json, ensure_ascii=False),
                                doc.source_fingerprint,
                                embedding_literal,
                            ),
                        )
            connection.commit()

    def archive_characters(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
        character_ids: tuple[str, ...],
        snapshot_version: str,
    ) -> tuple[str, ...]:
        if not character_ids:
            return ()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE characters
                SET active_status = 'archived',
                    snapshot_version = %s,
                    updated_at = NOW()
                WHERE source_kind = %s AND character_id = ANY(%s)
                """,
                (snapshot_version, source_kind, list(character_ids)),
            )
            connection.commit()
        return character_ids

    def record_import_run(
        self,
        *,
        source_kind: CharacterKnowledgeSourceKind,
        import_mode: str,
        snapshot_version: str,
        imported_character_ids: tuple[str, ...],
        archived_character_ids: tuple[str, ...],
        doc_count: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO character_import_runs (
                    source_kind,
                    import_mode,
                    snapshot_version,
                    imported_character_ids,
                    archived_character_ids,
                    doc_count,
                    created_at
                ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, NOW())
                """,
                (
                    source_kind,
                    import_mode,
                    snapshot_version,
                    json.dumps(list(imported_character_ids), ensure_ascii=False),
                    json.dumps(list(archived_character_ids), ensure_ascii=False),
                    doc_count,
                ),
            )
            connection.commit()

    def recall_candidates(
        self,
        *,
        query_mode: CharacterKnowledgeQueryMode,
        query_language: CharacterKnowledgeDocLanguage,
        query_text: str,
        query_embedding: list[float] | None,
        slot_tag: RosterSlotTag | None,
        primary_theme: str | None,
        template_affinity: str | None,
        source_kind: CharacterKnowledgeSourceKind,
        active_status: str = "active",
        candidate_limit: int = 24,
    ) -> tuple[CharacterKnowledgeCandidate, ...]:
        del query_mode
        vector_literal = _vector_literal(query_embedding)
        with self._connect() as connection:
            if vector_literal is None:
                rows = connection.execute(
                    """
                    WITH first_docs AS (
                        SELECT
                            d.character_id,
                            d.doc_type,
                            d.doc_language,
                            d.embedding::text AS embedding_text,
                            ROW_NUMBER() OVER (
                                PARTITION BY d.character_id
                                ORDER BY d.doc_type ASC
                            ) AS char_rank
                        FROM character_retrieval_docs d
                        JOIN characters c ON c.character_id = d.character_id
                        JOIN character_metadata m ON m.character_id = d.character_id
                        WHERE c.source_kind = %s
                          AND c.active_status = %s
                          AND d.doc_language = %s
                          AND (%s::text IS NULL OR %s::text = ANY(m.slot_tags))
                          AND (%s::text IS NULL OR %s::text = ANY(m.theme_tags))
                          AND (%s::text IS NULL OR %s::text = ANY(m.template_affinity))
                    )
                    SELECT
                        c.character_id,
                        c.slug,
                        c.source_fingerprint,
                        c.snapshot_version AS template_version,
                        m.theme_tags,
                        m.setting_tags,
                        m.tone_tags,
                        m.conflict_tags,
                        m.slot_tags,
                        m.retrieval_terms,
                        m.gender_lock,
                        m.rarity_weight,
                        en.name AS name_en,
                        zh.name AS name_zh,
                        en.public_summary AS public_summary_en,
                        zh.public_summary AS public_summary_zh,
                        en.role_hint AS role_hint_en,
                        zh.role_hint AS role_hint_zh,
                        en.agenda AS agenda_seed_en,
                        zh.agenda AS agenda_seed_zh,
                        en.red_line AS red_line_seed_en,
                        zh.red_line AS red_line_seed_zh,
                        en.pressure_signature AS pressure_signature_seed_en,
                        zh.pressure_signature AS pressure_signature_seed_zh,
                        ten.personality_core AS personality_core_en,
                        tzh.personality_core AS personality_core_zh,
                        ten.experience_anchor AS experience_anchor_en,
                        tzh.experience_anchor AS experience_anchor_zh,
                        ten.identity_lock_notes AS identity_lock_notes_en,
                        tzh.identity_lock_notes AS identity_lock_notes_zh,
                        pneu.public_url AS neutral_url,
                        pneg.public_url AS negative_url,
                        ppos.public_url AS positive_url,
                        fd.doc_type,
                        fd.doc_language,
                        fd.embedding_text,
                        NULL::double precision AS similarity
                    FROM first_docs fd
                    JOIN characters c ON c.character_id = fd.character_id
                    JOIN character_metadata m ON m.character_id = c.character_id
                    JOIN character_localizations en ON en.character_id = c.character_id AND en.language = 'en'
                    JOIN character_localizations zh ON zh.character_id = c.character_id AND zh.language = 'zh'
                    LEFT JOIN character_template_profiles ten ON ten.character_id = c.character_id AND ten.language = 'en'
                    LEFT JOIN character_template_profiles tzh ON tzh.character_id = c.character_id AND tzh.language = 'zh'
                    LEFT JOIN character_portraits pneu ON pneu.character_id = c.character_id AND pneu.variant_key = 'neutral'
                    LEFT JOIN character_portraits pneg ON pneg.character_id = c.character_id AND pneg.variant_key = 'negative'
                    LEFT JOIN character_portraits ppos ON ppos.character_id = c.character_id AND ppos.variant_key = 'positive'
                    WHERE fd.char_rank = 1
                    ORDER BY c.character_id ASC
                    """,
                    (
                        source_kind,
                        active_status,
                        query_language,
                        slot_tag,
                        slot_tag,
                        primary_theme,
                        primary_theme,
                        template_affinity,
                        template_affinity,
                    ),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    WITH ranked_docs AS (
                        SELECT
                            d.character_id,
                            d.doc_type,
                            d.doc_language,
                            d.embedding::text AS embedding_text,
                            1 - (d.embedding <=> %s::vector) AS similarity,
                            ROW_NUMBER() OVER (
                                PARTITION BY d.character_id
                                ORDER BY d.embedding <=> %s::vector ASC, d.doc_type ASC
                            ) AS char_rank
                        FROM character_retrieval_docs d
                        JOIN characters c ON c.character_id = d.character_id
                        JOIN character_metadata m ON m.character_id = d.character_id
                        WHERE c.source_kind = %s
                          AND c.active_status = %s
                          AND d.doc_language = %s
                          AND d.embedding IS NOT NULL
                          AND (%s::text IS NULL OR %s::text = ANY(m.slot_tags))
                          AND (%s::text IS NULL OR %s::text = ANY(m.theme_tags))
                          AND (%s::text IS NULL OR %s::text = ANY(m.template_affinity))
                    ),
                    deduped AS (
                        SELECT *
                        FROM ranked_docs
                        WHERE char_rank = 1
                        ORDER BY similarity DESC, character_id ASC
                        LIMIT %s
                    )
                    SELECT
                        c.character_id,
                        c.slug,
                        c.source_fingerprint,
                        c.snapshot_version AS template_version,
                        m.theme_tags,
                        m.setting_tags,
                        m.tone_tags,
                        m.conflict_tags,
                        m.slot_tags,
                        m.retrieval_terms,
                        m.gender_lock,
                        m.rarity_weight,
                        en.name AS name_en,
                        zh.name AS name_zh,
                        en.public_summary AS public_summary_en,
                        zh.public_summary AS public_summary_zh,
                        en.role_hint AS role_hint_en,
                        zh.role_hint AS role_hint_zh,
                        en.agenda AS agenda_seed_en,
                        zh.agenda AS agenda_seed_zh,
                        en.red_line AS red_line_seed_en,
                        zh.red_line AS red_line_seed_zh,
                        en.pressure_signature AS pressure_signature_seed_en,
                        zh.pressure_signature AS pressure_signature_seed_zh,
                        ten.personality_core AS personality_core_en,
                        tzh.personality_core AS personality_core_zh,
                        ten.experience_anchor AS experience_anchor_en,
                        tzh.experience_anchor AS experience_anchor_zh,
                        ten.identity_lock_notes AS identity_lock_notes_en,
                        tzh.identity_lock_notes AS identity_lock_notes_zh,
                        pneu.public_url AS neutral_url,
                        pneg.public_url AS negative_url,
                        ppos.public_url AS positive_url,
                        d.doc_type,
                        d.doc_language,
                        d.embedding_text,
                        d.similarity
                    FROM deduped d
                    JOIN characters c ON c.character_id = d.character_id
                    JOIN character_metadata m ON m.character_id = c.character_id
                    JOIN character_localizations en ON en.character_id = c.character_id AND en.language = 'en'
                    JOIN character_localizations zh ON zh.character_id = c.character_id AND zh.language = 'zh'
                    LEFT JOIN character_template_profiles ten ON ten.character_id = c.character_id AND ten.language = 'en'
                    LEFT JOIN character_template_profiles tzh ON tzh.character_id = c.character_id AND tzh.language = 'zh'
                    LEFT JOIN character_portraits pneu ON pneu.character_id = c.character_id AND pneu.variant_key = 'neutral'
                    LEFT JOIN character_portraits pneg ON pneg.character_id = c.character_id AND pneg.variant_key = 'negative'
                    LEFT JOIN character_portraits ppos ON ppos.character_id = c.character_id AND ppos.variant_key = 'positive'
                    ORDER BY d.similarity DESC NULLS LAST, c.character_id ASC
                    """,
                    (
                        vector_literal,
                        vector_literal,
                        source_kind,
                        active_status,
                        query_language,
                        slot_tag,
                        slot_tag,
                        primary_theme,
                        primary_theme,
                        template_affinity,
                        template_affinity,
                        candidate_limit,
                    ),
                ).fetchall()
        return tuple(self._row_to_candidate(row, query_text=query_text) for row in rows)

    def get_character_entry(
        self,
        *,
        character_id: str,
        source_kind: CharacterKnowledgeSourceKind,
        active_status: str = "active",
    ) -> CharacterRosterEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    c.character_id,
                    c.slug,
                    c.source_fingerprint,
                    c.snapshot_version AS template_version,
                    m.theme_tags,
                    m.setting_tags,
                    m.tone_tags,
                    m.conflict_tags,
                    m.slot_tags,
                    m.retrieval_terms,
                    m.gender_lock,
                    m.rarity_weight,
                    en.name AS name_en,
                    zh.name AS name_zh,
                    en.public_summary AS public_summary_en,
                    zh.public_summary AS public_summary_zh,
                    en.role_hint AS role_hint_en,
                    zh.role_hint AS role_hint_zh,
                    en.agenda AS agenda_seed_en,
                    zh.agenda AS agenda_seed_zh,
                    en.red_line AS red_line_seed_en,
                    zh.red_line AS red_line_seed_zh,
                    en.pressure_signature AS pressure_signature_seed_en,
                    zh.pressure_signature AS pressure_signature_seed_zh,
                    ten.personality_core AS personality_core_en,
                    tzh.personality_core AS personality_core_zh,
                    ten.experience_anchor AS experience_anchor_en,
                    tzh.experience_anchor AS experience_anchor_zh,
                    ten.identity_lock_notes AS identity_lock_notes_en,
                    tzh.identity_lock_notes AS identity_lock_notes_zh,
                    pneu.public_url AS neutral_url,
                    pneg.public_url AS negative_url,
                    ppos.public_url AS positive_url,
                    NULL::text AS doc_type,
                    NULL::text AS doc_language,
                    NULL::text AS embedding_text,
                    NULL::double precision AS similarity
                FROM characters c
                JOIN character_metadata m ON m.character_id = c.character_id
                JOIN character_localizations en ON en.character_id = c.character_id AND en.language = 'en'
                JOIN character_localizations zh ON zh.character_id = c.character_id AND zh.language = 'zh'
                LEFT JOIN character_template_profiles ten ON ten.character_id = c.character_id AND ten.language = 'en'
                LEFT JOIN character_template_profiles tzh ON tzh.character_id = c.character_id AND tzh.language = 'zh'
                LEFT JOIN character_portraits pneu ON pneu.character_id = c.character_id AND pneu.variant_key = 'neutral'
                LEFT JOIN character_portraits pneg ON pneg.character_id = c.character_id AND pneg.variant_key = 'negative'
                LEFT JOIN character_portraits ppos ON ppos.character_id = c.character_id AND ppos.variant_key = 'positive'
                WHERE c.character_id = %s
                  AND c.source_kind = %s
                  AND c.active_status = %s
                LIMIT 1
                """,
                (character_id, source_kind, active_status),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_candidate(row, query_text="").entry

    def _row_to_candidate(self, row: dict[str, Any], *, query_text: str) -> CharacterKnowledgeCandidate:
        negative_url = str(row["negative_url"]) if row.get("negative_url") else None
        neutral_url = str(row["neutral_url"]) if row.get("neutral_url") else None
        positive_url = str(row["positive_url"]) if row.get("positive_url") else None
        portrait_variants = None
        if negative_url or neutral_url or positive_url:
            portrait_variants = {
                key: value
                for key, value in {
                    "negative": negative_url,
                    "neutral": neutral_url,
                    "positive": positive_url,
                }.items()
                if value
            }
        retrieval_text = " ".join(
            part
            for part in (
                str(row["name_en"]),
                str(row["name_zh"]),
                str(row["public_summary_en"]),
                str(row["public_summary_zh"]),
                str(row["role_hint_en"]),
                str(row["role_hint_zh"]),
                str(row["agenda_seed_en"]),
                str(row["agenda_seed_zh"]),
                str(row["red_line_seed_en"]),
                str(row["red_line_seed_zh"]),
                str(row["pressure_signature_seed_en"]),
                str(row["pressure_signature_seed_zh"]),
                str(row.get("personality_core_en") or ""),
                str(row.get("personality_core_zh") or ""),
                str(row.get("experience_anchor_en") or ""),
                str(row.get("experience_anchor_zh") or ""),
                " ".join(row.get("theme_tags") or ()),
                " ".join(row.get("setting_tags") or ()),
                " ".join(row.get("tone_tags") or ()),
                " ".join(row.get("conflict_tags") or ()),
                " ".join(row.get("slot_tags") or ()),
                " ".join(row.get("retrieval_terms") or ()),
                query_text,
            )
            if str(part).strip()
        )
        entry = CharacterRosterEntry(
            character_id=str(row["character_id"]),
            slug=str(row["slug"]),
            name_en=str(row["name_en"]),
            name_zh=str(row["name_zh"]),
            portrait_url=neutral_url,
            default_portrait_url=neutral_url,
            portrait_variants=portrait_variants,
            public_summary_en=str(row["public_summary_en"]),
            public_summary_zh=str(row["public_summary_zh"]),
            role_hint_en=str(row["role_hint_en"]),
            role_hint_zh=str(row["role_hint_zh"]),
            agenda_seed_en=str(row["agenda_seed_en"]),
            agenda_seed_zh=str(row["agenda_seed_zh"]),
            red_line_seed_en=str(row["red_line_seed_en"]),
            red_line_seed_zh=str(row["red_line_seed_zh"]),
            pressure_signature_seed_en=str(row["pressure_signature_seed_en"]),
            pressure_signature_seed_zh=str(row["pressure_signature_seed_zh"]),
            personality_core_en=str(row["personality_core_en"]) if row.get("personality_core_en") is not None else None,
            personality_core_zh=str(row["personality_core_zh"]) if row.get("personality_core_zh") is not None else None,
            experience_anchor_en=str(row["experience_anchor_en"]) if row.get("experience_anchor_en") is not None else None,
            experience_anchor_zh=str(row["experience_anchor_zh"]) if row.get("experience_anchor_zh") is not None else None,
            identity_lock_notes_en=str(row["identity_lock_notes_en"]) if row.get("identity_lock_notes_en") is not None else None,
            identity_lock_notes_zh=str(row["identity_lock_notes_zh"]) if row.get("identity_lock_notes_zh") is not None else None,
            theme_tags=tuple(str(item) for item in row.get("theme_tags") or ()),
            setting_tags=tuple(str(item) for item in row.get("setting_tags") or ()),
            tone_tags=tuple(str(item) for item in row.get("tone_tags") or ()),
            conflict_tags=tuple(str(item) for item in row.get("conflict_tags") or ()),
            slot_tags=tuple(str(item) for item in row.get("slot_tags") or ()),
            retrieval_terms=tuple(str(item) for item in row.get("retrieval_terms") or ()),
            retrieval_text=retrieval_text,
            source_fingerprint=str(row["source_fingerprint"]),
            embedding_vector=_parse_vector_text(str(row["embedding_text"]) if row.get("embedding_text") else None),
            rarity_weight=float(row["rarity_weight"]),
            template_version=str(row["template_version"]) if row.get("template_version") is not None else None,
            gender_lock=str(row["gender_lock"]) if row.get("gender_lock") is not None else None,
        )
        similarity = float(row["similarity"]) if row.get("similarity") is not None else None
        return CharacterKnowledgeCandidate(
            entry=entry,
            matched_doc_type=str(row["doc_type"]),  # type: ignore[arg-type]
            matched_doc_language=str(row["doc_language"]),  # type: ignore[arg-type]
            matched_similarity=similarity,
        )


def build_character_knowledge_repository(settings: Settings) -> CharacterKnowledgeRepository | None:
    database_url = str(settings.character_knowledge_database_url or "").strip()
    if not settings.character_knowledge_enabled or not database_url:
        return None
    return CharacterKnowledgePostgresRepository(database_url)

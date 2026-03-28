from __future__ import annotations

from dataclasses import dataclass
import json
import re
import sqlite3
from pathlib import Path

from rpg_backend.library.contracts import (
    PublishedStoryCard,
    PublishedStoryRecord,
    PublishedStoryThemeFacet,
)
from rpg_backend.library.search_text import build_pinyin_document
from rpg_backend.sqlite_utils import require_sqlite_columns


def _fts_query(value: str) -> str | None:
    terms = re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE)
    if not terms:
        return None
    return " AND ".join(f"{term}*" for term in terms)


@dataclass(frozen=True)
class StoryLibraryPage:
    records: list[PublishedStoryRecord]
    total: int
    theme_facets: list[PublishedStoryThemeFacet]
    next_offset: int | None


@dataclass(frozen=True)
class _LibraryScope:
    actor_user_id: str | None
    include_public: bool
    public_only: bool
    table_alias: str | None = None


@dataclass(frozen=True)
class _LibraryFilters:
    query: str | None
    theme: str | None
    language: str | None


class SQLiteStoryLibraryStorage:
    _SEARCH_COLUMNS: tuple[str, ...] = (
        "story_id",
        "title",
        "one_liner",
        "premise",
        "theme",
        "tone",
        "prompt_seed",
        "title_pinyin",
        "one_liner_pinyin",
        "premise_pinyin",
        "theme_pinyin",
        "tone_pinyin",
        "prompt_seed_pinyin",
    )

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._fts_enabled = True

    def _ensure_parent_dir(self) -> None:
        if self._db_path == ":memory:":
            return
        path = Path(self._db_path)
        if path.parent != Path():
            path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        self._ensure_parent_dir()
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        self._ensure_schema(connection)
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS published_stories (
                story_id TEXT PRIMARY KEY,
                source_job_id TEXT NOT NULL UNIQUE,
                prompt_seed TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                title TEXT NOT NULL DEFAULT '',
                one_liner TEXT NOT NULL DEFAULT '',
                premise TEXT NOT NULL DEFAULT '',
                theme TEXT NOT NULL DEFAULT '',
                tone TEXT NOT NULL DEFAULT '',
                npc_count INTEGER NOT NULL DEFAULT 0,
                beat_count INTEGER NOT NULL DEFAULT 0,
                topology TEXT NOT NULL DEFAULT '',
                owner_user_id TEXT NOT NULL DEFAULT '',
                visibility TEXT NOT NULL DEFAULT 'private',
                summary_json TEXT NOT NULL,
                preview_json TEXT NOT NULL,
                bundle_json TEXT NOT NULL,
                published_at TEXT NOT NULL
            )
            """
        )
        require_sqlite_columns(
            connection,
            table_name="published_stories",
            required_columns=(
                "story_id",
                "source_job_id",
                "prompt_seed",
                "language",
                "title",
                "one_liner",
                "premise",
                "theme",
                "tone",
                "npc_count",
                "beat_count",
                "topology",
                "owner_user_id",
                "visibility",
                "summary_json",
                "preview_json",
                "bundle_json",
                "published_at",
            ),
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_published_stories_published_at ON published_stories (published_at DESC, story_id DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_published_stories_theme ON published_stories (theme COLLATE NOCASE)"
        )
        self._ensure_search_index(connection)
        connection.commit()

    @staticmethod
    def _row_card_payload(row: sqlite3.Row) -> dict[str, object]:
        return {
            "story_id": row["story_id"],
            "language": row["language"],
            "title": row["title"],
            "one_liner": row["one_liner"],
            "premise": row["premise"],
            "theme": row["theme"],
            "tone": row["tone"],
            "npc_count": row["npc_count"],
            "beat_count": row["beat_count"],
            "topology": row["topology"],
            "visibility": row["visibility"],
            "published_at": row["published_at"],
        }

    @classmethod
    def _row_to_record(cls, row: sqlite3.Row) -> PublishedStoryRecord:
        summary_payload = json.loads(str(row["summary_json"]))
        preview_payload = json.loads(str(row["preview_json"]))
        bundle_payload = json.loads(str(row["bundle_json"]))
        story = PublishedStoryCard.model_validate(cls._row_card_payload(row))
        return PublishedStoryRecord.model_validate(
            {
                "story": story.model_dump(mode="json"),
                "owner_user_id": row["owner_user_id"],
                "source_job_id": row["source_job_id"],
                "prompt_seed": row["prompt_seed"],
                "visibility": row["visibility"],
                "summary": summary_payload,
                "preview": preview_payload,
                "bundle": bundle_payload,
            }
        )

    @classmethod
    def _search_document_from_record(cls, record: PublishedStoryRecord) -> tuple[object, ...]:
        return (
            record.story.story_id,
            record.story.title,
            record.story.one_liner,
            record.story.premise,
            record.story.theme,
            record.story.tone,
            record.prompt_seed,
            build_pinyin_document(record.story.title),
            build_pinyin_document(record.story.one_liner),
            build_pinyin_document(record.story.premise),
            build_pinyin_document(record.story.theme),
            build_pinyin_document(record.story.tone),
            build_pinyin_document(record.prompt_seed),
        )


    def _replace_search_document(self, connection: sqlite3.Connection, *, story_id: str, record: PublishedStoryRecord) -> None:
        if not self._fts_enabled:
            return
        try:
            connection.execute(
                "DELETE FROM published_story_search WHERE story_id = ?",
                (story_id,),
            )
            self._insert_search_document(connection, record)
        except sqlite3.OperationalError:
            self._fts_enabled = False

    @classmethod
    def _search_schema_matches(cls, connection: sqlite3.Connection) -> bool:
        rows = connection.execute("PRAGMA table_info(published_story_search)").fetchall()
        if not rows:
            return False
        existing = tuple(str(row["name"]) if isinstance(row, sqlite3.Row) else str(row[1]) for row in rows)
        return existing == cls._SEARCH_COLUMNS

    @classmethod
    def _create_search_index(cls, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS published_story_search
            USING fts5(
                story_id UNINDEXED,
                title,
                one_liner,
                premise,
                theme,
                tone,
                prompt_seed,
                title_pinyin,
                one_liner_pinyin,
                premise_pinyin,
                theme_pinyin,
                tone_pinyin,
                prompt_seed_pinyin,
                tokenize = 'porter unicode61'
            )
            """
        )

    def _ensure_search_index(self, connection: sqlite3.Connection) -> None:
        if not self._fts_enabled:
            return
        try:
            self._create_search_index(connection)
            if not self._search_schema_matches(connection):
                connection.execute("DROP TABLE IF EXISTS published_story_search")
                self._create_search_index(connection)
            if not self._search_schema_matches(connection):
                raise sqlite3.OperationalError("published_story_search schema mismatch")
        except sqlite3.OperationalError:
            self._fts_enabled = False
            return
        story_count = int(
            connection.execute("SELECT COUNT(*) FROM published_stories").fetchone()[0]
        )
        search_count = int(
            connection.execute("SELECT COUNT(*) FROM published_story_search").fetchone()[0]
        )
        if story_count == search_count:
            return
        connection.execute("DELETE FROM published_story_search")
        for row in connection.execute("SELECT * FROM published_stories").fetchall():
            self._insert_search_document(connection, self._row_to_record(row))

    def _insert_search_document(self, connection: sqlite3.Connection, record: PublishedStoryRecord) -> None:
        if not self._fts_enabled:
            return
        try:
            connection.execute(
                f"""
                INSERT INTO published_story_search (
                    {', '.join(self._SEARCH_COLUMNS)}
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._search_document_from_record(record),
            )
        except sqlite3.OperationalError:
            self._fts_enabled = False

    def get_by_source_job_id(self, source_job_id: str) -> PublishedStoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM published_stories
                WHERE source_job_id = ?
                """,
                (source_job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_story(self, story_id: str) -> PublishedStoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM published_stories
                WHERE story_id = ?
                """,
                (story_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    @staticmethod
    def _visibility_clause(*, include_public: bool, table_alias: str | None = None) -> str:
        owner_column = f"{table_alias}.owner_user_id" if table_alias else "owner_user_id"
        visibility_column = f"{table_alias}.visibility" if table_alias else "visibility"
        if include_public:
            return f"({owner_column} = ? OR {visibility_column} = 'public')"
        return f"{owner_column} = ?"

    @staticmethod
    def _public_only_clause(*, table_alias: str | None = None) -> str:
        visibility_column = f"{table_alias}.visibility" if table_alias else "visibility"
        return f"{visibility_column} = 'public'"

    @staticmethod
    def _base_scope(scope: _LibraryScope) -> tuple[list[str], list[object]]:
        if scope.public_only:
            return [SQLiteStoryLibraryStorage._public_only_clause(table_alias=scope.table_alias)], []
        if scope.actor_user_id is None:
            raise ValueError("actor_user_id is required when public_only is false")
        return [SQLiteStoryLibraryStorage._visibility_clause(include_public=scope.include_public, table_alias=scope.table_alias)], [scope.actor_user_id]

    @staticmethod
    def _append_theme_language_filters(
        clauses: list[str],
        params: list[object],
        filters: _LibraryFilters,
        *,
        table_alias: str | None = None,
    ) -> None:
        theme_column = f"{table_alias}.theme" if table_alias else "theme"
        language_column = f"{table_alias}.language" if table_alias else "language"
        if filters.theme:
            clauses.append(f"{theme_column} = ? COLLATE NOCASE")
            params.append(filters.theme.strip())
        if filters.language:
            clauses.append(f"{language_column} = ?")
            params.append(filters.language)

    @staticmethod
    def _build_where_parts(
        scope: _LibraryScope,
        filters: _LibraryFilters,
        *,
        query_mode: str | None = None,
        table_alias: str | None = None,
    ) -> tuple[list[str], list[object]]:
        clauses, params = SQLiteStoryLibraryStorage._base_scope(scope)
        if filters.query and query_mode is not None:
            SQLiteStoryLibraryStorage._append_query_filter(
                clauses,
                params,
                filters.query,
                use_fts=query_mode == "fts",
                table_alias=table_alias,
            )
        SQLiteStoryLibraryStorage._append_theme_language_filters(
            clauses,
            params,
            _LibraryFilters(query=None, theme=filters.theme, language=filters.language),
            table_alias=table_alias,
        )
        return clauses, params

    @staticmethod
    def _append_query_filter(
        clauses: list[str],
        params: list[object],
        query: str,
        *,
        use_fts: bool,
        table_alias: str | None = None,
    ) -> None:
        title_column = f"{table_alias}.title" if table_alias else "title"
        one_liner_column = f"{table_alias}.one_liner" if table_alias else "one_liner"
        premise_column = f"{table_alias}.premise" if table_alias else "premise"
        theme_column = f"{table_alias}.theme" if table_alias else "theme"
        tone_column = f"{table_alias}.tone" if table_alias else "tone"
        prompt_seed_column = f"{table_alias}.prompt_seed" if table_alias else "prompt_seed"
        if use_fts:
            fts_query = _fts_query(query)
            if fts_query:
                clauses.append(
                    """
                    story_id IN (
                        SELECT story_id
                        FROM published_story_search
                        WHERE published_story_search MATCH ?
                    )
                    """
                )
                params.append(fts_query)
                return
        like_value = f"%{query.strip()}%"
        clauses.append(
            f"""
            (
                {title_column} LIKE ? COLLATE NOCASE
                OR {one_liner_column} LIKE ? COLLATE NOCASE
                OR {premise_column} LIKE ? COLLATE NOCASE
                OR {theme_column} LIKE ? COLLATE NOCASE
                OR {tone_column} LIKE ? COLLATE NOCASE
                OR {prompt_seed_column} LIKE ? COLLATE NOCASE
            )
            """
        )
        params.extend([like_value] * 6)

    def list_stories(
        self,
        *,
        actor_user_id: str | None,
        query: str | None = None,
        theme: str | None = None,
        language: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "published_at_desc",
        include_public: bool = True,
        public_only: bool = False,
    ) -> StoryLibraryPage:
        with self._connect() as connection:
            total = self._count_matching_stories(
                connection,
                actor_user_id=actor_user_id,
                query=query,
                theme=theme,
                language=language,
                include_public=include_public,
                public_only=public_only,
            )
            facets = self._theme_facets(
                connection,
                actor_user_id=actor_user_id,
                query=query,
                language=language,
                include_public=include_public,
                public_only=public_only,
            )
            rows = self._search_rows(
                connection,
                actor_user_id=actor_user_id,
                query=query,
                theme=theme,
                language=language,
                limit=limit + 1,
                offset=offset,
                sort=sort,
                include_public=include_public,
                public_only=public_only,
            )
        records = [self._row_to_record(row) for row in rows[:limit]]
        has_more = len(rows) > limit
        next_offset = offset + limit if has_more else None
        return StoryLibraryPage(
            records=records,
            total=total,
            theme_facets=facets,
            next_offset=next_offset,
        )

    def _count_matching_stories(
        self,
        connection: sqlite3.Connection,
        *,
        actor_user_id: str | None,
        query: str | None,
        theme: str | None,
        language: str | None,
        include_public: bool,
        public_only: bool,
    ) -> int:
        scope = _LibraryScope(actor_user_id=actor_user_id, include_public=include_public, public_only=public_only)
        active_filters = _LibraryFilters(query=query, theme=theme, language=language)
        query_mode = "fts" if self._fts_enabled else "like"
        clauses, params = self._build_where_parts(scope, active_filters, query_mode=query_mode)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        row = connection.execute(
            f"SELECT COUNT(*) AS count FROM published_stories {where_clause}",
            params,
        ).fetchone()
        return int(row["count"]) if row is not None else 0

    def _theme_facets(
        self,
        connection: sqlite3.Connection,
        *,
        actor_user_id: str | None,
        query: str | None,
        language: str | None,
        include_public: bool,
        public_only: bool,
    ) -> list[PublishedStoryThemeFacet]:
        scope = _LibraryScope(actor_user_id=actor_user_id, include_public=include_public, public_only=public_only)
        active_filters = _LibraryFilters(query=query, theme=None, language=language)
        query_mode = "fts" if self._fts_enabled else "like"
        clauses, params = self._build_where_parts(scope, active_filters, query_mode=query_mode)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"""
            SELECT theme, COUNT(*) AS count
            FROM published_stories
            {where_clause}
            GROUP BY theme
            ORDER BY count DESC, theme ASC
            """,
            params,
        ).fetchall()
        return [
            PublishedStoryThemeFacet.model_validate(
                {
                    "theme": row["theme"],
                    "count": row["count"],
                }
            )
            for row in rows
            if str(row["theme"]).strip()
        ]

    def _search_rows(
        self,
        connection: sqlite3.Connection,
        *,
        actor_user_id: str | None,
        query: str | None,
        theme: str | None,
        language: str | None,
        limit: int,
        offset: int,
        sort: str,
        include_public: bool,
        public_only: bool,
    ) -> list[sqlite3.Row]:
        if query:
            return self._search_rows_by_query(
                connection,
                actor_user_id=actor_user_id,
                query=query,
                theme=theme,
                language=language,
                limit=limit,
                offset=offset,
                sort=sort,
                include_public=include_public,
                public_only=public_only,
            )
        scope = _LibraryScope(actor_user_id=actor_user_id, include_public=include_public, public_only=public_only)
        filters = _LibraryFilters(query=None, theme=theme, language=language)
        clauses, params = self._build_where_parts(scope, filters)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return connection.execute(
            f"""
            SELECT *
            FROM published_stories
            {where_clause}
            ORDER BY published_at DESC, story_id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    def _search_rows_by_query(
        self,
        connection: sqlite3.Connection,
        *,
        actor_user_id: str | None,
        query: str,
        theme: str | None,
        language: str | None,
        limit: int,
        offset: int,
        sort: str,
        include_public: bool,
        public_only: bool,
    ) -> list[sqlite3.Row]:
        if not self._fts_enabled:
            return self._search_rows_by_like(
                connection,
                actor_user_id=actor_user_id,
                query=query,
                theme=theme,
                language=language,
                limit=limit,
                offset=offset,
                sort=sort,
                include_public=include_public,
                public_only=public_only,
            )
        fts_query = _fts_query(query)
        if fts_query is None:
            return self._search_rows_by_like(
                connection,
                actor_user_id=actor_user_id,
                query=query,
                theme=theme,
                limit=limit,
                offset=offset,
                sort=sort,
                include_public=include_public,
                public_only=public_only,
            )
        order_clause = (
            "rank ASC, stories.published_at DESC, stories.story_id DESC"
            if sort == "relevance"
            else "stories.published_at DESC, stories.story_id DESC"
        )
        scope = _LibraryScope(actor_user_id=actor_user_id, include_public=include_public, public_only=public_only, table_alias="stories")
        filters = _LibraryFilters(query=None, theme=theme, language=language)
        clauses, params = self._build_where_parts(scope, filters, table_alias="stories")
        where_clause = " AND ".join(["published_story_search MATCH ?", *clauses])
        return connection.execute(
            f"""
            SELECT stories.*, bm25(published_story_search) AS rank
            FROM published_story_search
            JOIN published_stories AS stories
                ON stories.story_id = published_story_search.story_id
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
            """,
            [fts_query, *params, limit, offset],
        ).fetchall()

    def _search_rows_by_like(
        self,
        connection: sqlite3.Connection,
        *,
        actor_user_id: str | None,
        query: str,
        theme: str | None,
        language: str | None,
        limit: int,
        offset: int,
        sort: str,
        include_public: bool,
        public_only: bool,
    ) -> list[sqlite3.Row]:
        like_value = f"%{query.strip()}%"
        scope = _LibraryScope(actor_user_id=actor_user_id, include_public=include_public, public_only=public_only)
        filters = _LibraryFilters(query=query, theme=theme, language=language)
        clauses, params = self._build_where_parts(scope, filters, query_mode="like")
        where_clause = " AND ".join(clauses)
        order_clause = (
            """
            (
                (CASE WHEN title LIKE ? COLLATE NOCASE THEN 6 ELSE 0 END)
                + (CASE WHEN one_liner LIKE ? COLLATE NOCASE THEN 4 ELSE 0 END)
                + (CASE WHEN premise LIKE ? COLLATE NOCASE THEN 3 ELSE 0 END)
                + (CASE WHEN theme LIKE ? COLLATE NOCASE THEN 2 ELSE 0 END)
                + (CASE WHEN tone LIKE ? COLLATE NOCASE THEN 1 ELSE 0 END)
                + (CASE WHEN prompt_seed LIKE ? COLLATE NOCASE THEN 1 ELSE 0 END)
            ) DESC,
            published_at DESC,
            story_id DESC
            """
            if sort == "relevance"
            else "published_at DESC, story_id DESC"
        )
        return connection.execute(
            f"""
            SELECT *
            FROM published_stories
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
            """,
            [
                *params,
                *([like_value] * 6 if sort == "relevance" else []),
                limit,
                offset,
            ],
        ).fetchall()

    def insert_story(self, record: PublishedStoryRecord) -> PublishedStoryRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO published_stories (
                    story_id,
                    source_job_id,
                    prompt_seed,
                    language,
                    title,
                    one_liner,
                    premise,
                    theme,
                    tone,
                    npc_count,
                    beat_count,
                    topology,
                    owner_user_id,
                    visibility,
                    summary_json,
                    preview_json,
                    bundle_json,
                    published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.story.story_id,
                    record.source_job_id,
                    record.prompt_seed,
                    record.story.language,
                    record.story.title,
                    record.story.one_liner,
                    record.story.premise,
                    record.story.theme,
                    record.story.tone,
                    record.story.npc_count,
                    record.story.beat_count,
                    record.story.topology,
                    record.owner_user_id,
                    record.visibility,
                    record.summary.model_dump_json(),
                    record.preview.model_dump_json(),
                    record.bundle.model_dump_json(),
                    record.story.published_at.isoformat(),
                ),
            )
            self._insert_search_document(connection, record)
            connection.commit()
        return record

    def update_story_visibility(self, *, story_id: str, visibility: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE published_stories
                SET visibility = ?
                WHERE story_id = ?
                """,
                (visibility, story_id),
            )
            connection.commit()

    def delete_story(self, *, story_id: str, owner_user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM published_stories
                WHERE story_id = ? AND owner_user_id = ?
                """,
                (story_id, owner_user_id),
            )
            if self._fts_enabled:
                try:
                    connection.execute(
                        "DELETE FROM published_story_search WHERE story_id = ?",
                        (story_id,),
                    )
                except sqlite3.OperationalError:
                    self._fts_enabled = False
            connection.commit()
            return cursor.rowcount > 0

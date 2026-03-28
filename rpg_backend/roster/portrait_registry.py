from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Literal

from rpg_backend.sqlite_utils import connect_sqlite, require_sqlite_columns


PortraitVariantKey = Literal["negative", "neutral", "positive"]
PortraitAssetStatus = Literal["generated", "approved", "published", "rejected", "archived"]

_VALID_VARIANT_KEYS = {"negative", "neutral", "positive"}
_VALID_STATUSES = {"generated", "approved", "published", "rejected", "archived"}


def default_portrait_registry_db_path() -> str:
    return "data/character_roster/portrait_manifest.sqlite3"


@dataclass(frozen=True)
class PortraitAssetRecord:
    asset_id: str
    character_id: str
    variant_key: PortraitVariantKey
    candidate_index: int
    status: PortraitAssetStatus
    file_path: str
    public_url: str | None
    prompt_version: str
    prompt_hash: str
    image_model: str
    image_api_base_url: str
    generated_at: str
    approved_at: str | None = None
    published_at: str | None = None
    review_notes: str | None = None


class SQLitePortraitRegistry:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or default_portrait_registry_db_path())
        self._initialize()

    @property
    def db_path(self) -> str:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self._db_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS roster_portrait_assets (
                    asset_id TEXT PRIMARY KEY,
                    character_id TEXT NOT NULL,
                    variant_key TEXT NOT NULL,
                    candidate_index INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    public_url TEXT,
                    prompt_version TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    image_model TEXT NOT NULL,
                    image_api_base_url TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    approved_at TEXT,
                    published_at TEXT,
                    review_notes TEXT
                )
                """
            )
            require_sqlite_columns(
                connection,
                table_name="roster_portrait_assets",
                required_columns=(
                    "asset_id",
                    "character_id",
                    "variant_key",
                    "candidate_index",
                    "status",
                    "file_path",
                    "public_url",
                    "prompt_version",
                    "prompt_hash",
                    "image_model",
                    "image_api_base_url",
                    "generated_at",
                    "approved_at",
                    "published_at",
                    "review_notes",
                ),
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_roster_portrait_assets_character_variant ON roster_portrait_assets (character_id, variant_key, status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_roster_portrait_assets_status ON roster_portrait_assets (status, generated_at DESC)"
            )
            connection.commit()

    def save_asset(self, record: PortraitAssetRecord) -> None:
        if record.variant_key not in _VALID_VARIANT_KEYS:
            raise RuntimeError(f"unsupported portrait variant key: {record.variant_key}")
        if record.status not in _VALID_STATUSES:
            raise RuntimeError(f"unsupported portrait asset status: {record.status}")
        if record.candidate_index < 1:
            raise RuntimeError("candidate_index must be >= 1")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO roster_portrait_assets (
                    asset_id,
                    character_id,
                    variant_key,
                    candidate_index,
                    status,
                    file_path,
                    public_url,
                    prompt_version,
                    prompt_hash,
                    image_model,
                    image_api_base_url,
                    generated_at,
                    approved_at,
                    published_at,
                    review_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    character_id = excluded.character_id,
                    variant_key = excluded.variant_key,
                    candidate_index = excluded.candidate_index,
                    status = excluded.status,
                    file_path = excluded.file_path,
                    public_url = excluded.public_url,
                    prompt_version = excluded.prompt_version,
                    prompt_hash = excluded.prompt_hash,
                    image_model = excluded.image_model,
                    image_api_base_url = excluded.image_api_base_url,
                    generated_at = excluded.generated_at,
                    approved_at = excluded.approved_at,
                    published_at = excluded.published_at,
                    review_notes = excluded.review_notes
                """,
                (
                    record.asset_id,
                    record.character_id,
                    record.variant_key,
                    record.candidate_index,
                    record.status,
                    record.file_path,
                    record.public_url,
                    record.prompt_version,
                    record.prompt_hash,
                    record.image_model,
                    record.image_api_base_url,
                    record.generated_at,
                    record.approved_at,
                    record.published_at,
                    record.review_notes,
                ),
            )
            connection.commit()

    def get_asset(self, asset_id: str) -> PortraitAssetRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM roster_portrait_assets WHERE asset_id = ?",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return PortraitAssetRecord(
            asset_id=str(row["asset_id"]),
            character_id=str(row["character_id"]),
            variant_key=str(row["variant_key"]),
            candidate_index=int(row["candidate_index"]),
            status=str(row["status"]),
            file_path=str(row["file_path"]),
            public_url=str(row["public_url"]) if row["public_url"] is not None else None,
            prompt_version=str(row["prompt_version"]),
            prompt_hash=str(row["prompt_hash"]),
            image_model=str(row["image_model"]),
            image_api_base_url=str(row["image_api_base_url"]),
            generated_at=str(row["generated_at"]),
            approved_at=str(row["approved_at"]) if row["approved_at"] is not None else None,
            published_at=str(row["published_at"]) if row["published_at"] is not None else None,
            review_notes=str(row["review_notes"]) if row["review_notes"] is not None else None,
        )

    def list_assets(
        self,
        *,
        character_id: str | None = None,
        variant_key: PortraitVariantKey | None = None,
        status: PortraitAssetStatus | None = None,
    ) -> tuple[PortraitAssetRecord, ...]:
        clauses: list[str] = []
        params: list[str] = []
        if character_id:
            clauses.append("character_id = ?")
            params.append(character_id)
        if variant_key:
            clauses.append("variant_key = ?")
            params.append(variant_key)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM roster_portrait_assets
                {where}
                ORDER BY character_id ASC, variant_key ASC, candidate_index ASC, generated_at ASC
                """,
                params,
            ).fetchall()
        return tuple(
            PortraitAssetRecord(
                asset_id=str(row["asset_id"]),
                character_id=str(row["character_id"]),
                variant_key=str(row["variant_key"]),
                candidate_index=int(row["candidate_index"]),
                status=str(row["status"]),
                file_path=str(row["file_path"]),
                public_url=str(row["public_url"]) if row["public_url"] is not None else None,
                prompt_version=str(row["prompt_version"]),
                prompt_hash=str(row["prompt_hash"]),
                image_model=str(row["image_model"]),
                image_api_base_url=str(row["image_api_base_url"]),
                generated_at=str(row["generated_at"]),
                approved_at=str(row["approved_at"]) if row["approved_at"] is not None else None,
                published_at=str(row["published_at"]) if row["published_at"] is not None else None,
                review_notes=str(row["review_notes"]) if row["review_notes"] is not None else None,
            )
            for row in rows
        )

    def mark_status(
        self,
        asset_id: str,
        *,
        status: PortraitAssetStatus,
        review_notes: str | None = None,
    ) -> PortraitAssetRecord:
        record = self.get_asset(asset_id)
        if record is None:
            raise RuntimeError(f"portrait asset '{asset_id}' was not found")
        if status not in _VALID_STATUSES:
            raise RuntimeError(f"unsupported portrait asset status: {status}")
        now = datetime.now(timezone.utc).isoformat()
        updated = PortraitAssetRecord(
            asset_id=record.asset_id,
            character_id=record.character_id,
            variant_key=record.variant_key,
            candidate_index=record.candidate_index,
            status=status,
            file_path=record.file_path,
            public_url=record.public_url,
            prompt_version=record.prompt_version,
            prompt_hash=record.prompt_hash,
            image_model=record.image_model,
            image_api_base_url=record.image_api_base_url,
            generated_at=record.generated_at,
            approved_at=now if status == "approved" else record.approved_at,
            published_at=now if status == "published" else record.published_at,
            review_notes=review_notes if review_notes is not None else record.review_notes,
        )
        self.save_asset(updated)
        return updated

    def set_public_url(self, asset_id: str, public_url: str | None) -> PortraitAssetRecord:
        record = self.get_asset(asset_id)
        if record is None:
            raise RuntimeError(f"portrait asset '{asset_id}' was not found")
        updated = PortraitAssetRecord(
            asset_id=record.asset_id,
            character_id=record.character_id,
            variant_key=record.variant_key,
            candidate_index=record.candidate_index,
            status=record.status,
            file_path=record.file_path,
            public_url=public_url,
            prompt_version=record.prompt_version,
            prompt_hash=record.prompt_hash,
            image_model=record.image_model,
            image_api_base_url=record.image_api_base_url,
            generated_at=record.generated_at,
            approved_at=record.approved_at,
            published_at=record.published_at,
            review_notes=record.review_notes,
        )
        self.save_asset(updated)
        return updated

    def archive_other_published_assets(
        self,
        *,
        character_id: str,
        variant_key: PortraitVariantKey,
        keep_asset_id: str,
    ) -> None:
        for record in self.list_assets(character_id=character_id, variant_key=variant_key, status="published"):
            if record.asset_id == keep_asset_id:
                continue
            self.mark_status(record.asset_id, status="archived", review_notes=record.review_notes)

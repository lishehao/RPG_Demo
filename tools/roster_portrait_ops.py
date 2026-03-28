from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
import shutil
from typing import Any

from rpg_backend.config import Settings, get_settings
from rpg_backend.roster.admin import (
    embed_runtime_catalog,
    read_runtime_catalog_if_present,
    validate_source_catalog,
    write_runtime_catalog,
    write_source_catalog,
)
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from rpg_backend.roster.embeddings import build_character_embedding_provider
from rpg_backend.roster.portrait_registry import SQLitePortraitRegistry
from tools.roster_portrait_common import build_public_url, build_published_relative_path


def _unique_asset_ids(asset_ids: Iterable[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in asset_ids:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def review_assets(
    *,
    registry_db_path: str | Path,
    approve_asset_ids: Iterable[str] = (),
    reject_asset_ids: Iterable[str] = (),
    review_notes: str | None = None,
) -> dict[str, object]:
    registry = SQLitePortraitRegistry(registry_db_path)
    approved_ids: list[str] = []
    rejected_ids: list[str] = []
    for asset_id in _unique_asset_ids(approve_asset_ids):
        registry.mark_status(asset_id, status="approved", review_notes=review_notes)
        approved_ids.append(asset_id)
    for asset_id in _unique_asset_ids(reject_asset_ids):
        registry.mark_status(asset_id, status="rejected", review_notes=review_notes)
        rejected_ids.append(asset_id)
    return {
        "registry_db_path": registry.db_path,
        "approved_asset_ids": approved_ids,
        "rejected_asset_ids": rejected_ids,
    }


def publish_assets(
    *,
    registry_db_path: str | Path,
    catalog_path: str | Path,
    runtime_path: str | Path,
    output_dir: str | Path,
    local_portrait_base_url: str,
    asset_ids: Sequence[str],
    source_entries: tuple[CharacterRosterSourceEntry, ...] | None = None,
    embedding_provider_builder: Callable[[Settings], Any] | None = None,
) -> dict[str, Any]:
    selected_asset_ids = _unique_asset_ids(asset_ids)
    if not selected_asset_ids:
        raise RuntimeError("at least one asset_id is required for publish")

    registry = SQLitePortraitRegistry(registry_db_path)
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    published_assets: list[dict[str, str]] = []
    updated_character_ids: set[str] = set()

    for asset_id in selected_asset_ids:
        record = registry.get_asset(asset_id)
        if record is None:
            raise RuntimeError(f"portrait asset '{asset_id}' was not found")
        if record.status not in {"approved", "published"}:
            raise RuntimeError(f"portrait asset '{asset_id}' must be approved before publish")
        source_path = Path(record.file_path)
        if not source_path.exists():
            raise RuntimeError(f"portrait asset file missing on disk: {source_path}")
        registry.archive_other_published_assets(
            character_id=record.character_id,
            variant_key=record.variant_key,
            keep_asset_id=record.asset_id,
        )
        relative_path = build_published_relative_path(
            character_id=record.character_id,
            variant_key=record.variant_key,
        )
        target_path = resolved_output_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        public_url = build_public_url(
            local_portrait_base_url=str(local_portrait_base_url).rstrip("/"),
            relative_path=relative_path,
        )
        registry.set_public_url(record.asset_id, public_url)
        registry.mark_status(record.asset_id, status="published", review_notes=record.review_notes)
        updated_character_ids.add(record.character_id)
        published_assets.append(
            {
                "asset_id": record.asset_id,
                "character_id": record.character_id,
                "variant_key": record.variant_key,
                "public_url": public_url,
            }
        )

    base_source_entries = source_entries or validate_source_catalog(catalog_path)
    updated_entries: list[CharacterRosterSourceEntry] = []
    for entry in base_source_entries:
        if entry.character_id not in updated_character_ids:
            updated_entries.append(entry)
            continue
        published_for_character = registry.list_assets(character_id=entry.character_id, status="published")
        portrait_variants = {item.variant_key: item.public_url for item in published_for_character if item.public_url}
        default_portrait_url = portrait_variants.get("neutral") or entry.default_portrait_url or entry.portrait_url
        payload = entry.to_payload()
        payload["default_portrait_url"] = default_portrait_url
        payload["portrait_url"] = default_portrait_url
        payload["portrait_variants"] = portrait_variants or None
        updated_entries.append(entry.from_payload(payload))
    updated_entries_tuple = tuple(updated_entries)
    write_source_catalog(catalog_path, updated_entries_tuple)

    existing_runtime = read_runtime_catalog_if_present(runtime_path)
    provider_builder = embedding_provider_builder or build_character_embedding_provider
    runtime_catalog = embed_runtime_catalog(
        updated_entries_tuple,
        embedding_provider=provider_builder(get_settings()),
        existing_runtime_catalog=existing_runtime,
        force=False,
    )
    write_runtime_catalog(runtime_path, runtime_catalog)

    return {
        "registry_db_path": registry.db_path,
        "published_assets": published_assets,
        "updated_character_ids": sorted(updated_character_ids),
        "catalog_path": str(Path(catalog_path).expanduser().resolve()),
        "runtime_path": str(Path(runtime_path).expanduser().resolve()),
    }

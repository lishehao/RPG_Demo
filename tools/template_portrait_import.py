from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from rpg_backend.roster.admin import read_runtime_catalog_if_present, validate_source_catalog
from rpg_backend.roster.embeddings import build_character_embedding_provider
from rpg_backend.roster.portrait_registry import PortraitAssetRecord, SQLitePortraitRegistry
from tools.roster_portrait_ops import publish_assets, review_assets
from tools.template_portrait_common import (
    iter_screening_asset_reviews,
    keep_asset_ids_from_screening,
    load_screening,
)

REQUIRED_VARIANTS = {"negative", "neutral", "positive"}
DEFAULT_KEEP_REVIEW_NOTE = "approved from screening_initial keep batch import"


def _default_backup_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return (REPO_ROOT / "artifacts" / "portraits" / "import_backups" / timestamp).resolve()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Replace the formal roster with a reviewed template portrait batch.")
    parser.add_argument("--cast-pack-path", default="artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json")
    parser.add_argument("--screening-json", default="artifacts/portraits/template_trials/screening_initial.json")
    parser.add_argument("--registry-db-path", default=settings.portrait_manifest_db_path)
    parser.add_argument("--catalog-path", default=settings.roster_source_catalog_path)
    parser.add_argument("--runtime-path", default=settings.roster_runtime_catalog_path)
    parser.add_argument("--output-dir", default=settings.local_portrait_dir)
    parser.add_argument("--local-portrait-base-url", default=settings.local_portrait_base_url)
    parser.add_argument("--backup-dir")
    parser.add_argument("--import-mode", choices=("replace",), default="replace")
    return parser.parse_args(argv)


def _copy_path_if_exists(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
        return
    shutil.copy2(source, target)


def _collect_selected_records(
    *,
    registry_db_path: str | Path,
    selected_asset_ids: tuple[str, ...],
    expected_character_ids: set[str],
) -> tuple[PortraitAssetRecord, ...]:
    registry = SQLitePortraitRegistry(registry_db_path)
    selected_records: list[PortraitAssetRecord] = []
    seen_asset_ids: set[str] = set()
    coverage: dict[str, dict[str, str]] = {character_id: {} for character_id in expected_character_ids}
    for asset_id in selected_asset_ids:
        if asset_id in seen_asset_ids:
            raise RuntimeError(f"duplicate asset_id in selected import set: {asset_id}")
        seen_asset_ids.add(asset_id)
        record = registry.get_asset(asset_id)
        if record is None:
            raise RuntimeError(f"selected screening asset '{asset_id}' was not found in the portrait registry")
        if record.character_id not in expected_character_ids:
            raise RuntimeError(
                f"selected screening asset '{asset_id}' belongs to unexpected character '{record.character_id}'"
            )
        if record.candidate_index != 1:
            raise RuntimeError(f"selected screening asset '{asset_id}' must use candidate_index=1")
        file_path = Path(record.file_path)
        if not file_path.exists():
            raise RuntimeError(f"selected screening asset file missing on disk: {file_path}")
        slot = coverage[record.character_id]
        if record.variant_key in slot:
            raise RuntimeError(
                f"character '{record.character_id}' has duplicate selected variant '{record.variant_key}'"
            )
        slot[record.variant_key] = asset_id
        selected_records.append(record)
    missing_by_character = {
        character_id: sorted(REQUIRED_VARIANTS - set(selected_variants.keys()))
        for character_id, selected_variants in coverage.items()
        if set(selected_variants.keys()) != REQUIRED_VARIANTS
    }
    if missing_by_character:
        missing_summary = ", ".join(
            f"{character_id}: {', '.join(missing_variants)}"
            for character_id, missing_variants in sorted(missing_by_character.items())
        )
        raise RuntimeError(f"selected screening assets do not fully cover negative/neutral/positive: {missing_summary}")
    if len(selected_records) != len(expected_character_ids) * len(REQUIRED_VARIANTS):
        raise RuntimeError(
            f"selected screening assets must equal {len(expected_character_ids) * len(REQUIRED_VARIANTS)} "
            f"items but found {len(selected_records)}"
        )
    return tuple(selected_records)


def _archive_removed_published_assets(
    registry: SQLitePortraitRegistry,
    *,
    keep_character_ids: set[str],
) -> list[str]:
    archived_asset_ids: list[str] = []
    for record in registry.list_assets(status="published"):
        if record.character_id in keep_character_ids:
            continue
        registry.mark_status(record.asset_id, status="archived", review_notes=record.review_notes)
        archived_asset_ids.append(record.asset_id)
    return archived_asset_ids


def _cleanup_output_dir_for_replace(output_dir: Path, *, keep_character_ids: set[str]) -> list[str]:
    if not output_dir.exists():
        return []
    removed_dirs: list[str] = []
    for child in output_dir.iterdir():
        if not child.is_dir() or child.name in keep_character_ids:
            continue
        shutil.rmtree(child)
        removed_dirs.append(child.name)
    return sorted(removed_dirs)


def run_import(args: argparse.Namespace) -> dict[str, Any]:
    cast_pack_path = Path(args.cast_pack_path).expanduser().resolve()
    screening_json_path = Path(args.screening_json).expanduser().resolve()
    registry_db_path = Path(args.registry_db_path).expanduser().resolve()
    catalog_path = Path(args.catalog_path).expanduser().resolve()
    runtime_path = Path(args.runtime_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    backup_dir = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else _default_backup_dir()

    cast_pack_entries = validate_source_catalog(cast_pack_path)
    expected_character_ids = {entry.character_id for entry in cast_pack_entries}

    screening = load_screening(screening_json_path)
    all_screening_reviews = list(iter_screening_asset_reviews(screening))
    if not all_screening_reviews:
        raise RuntimeError("screening JSON did not contain any asset reviews")
    non_keep_asset_ids = sorted(
        asset_id
        for _template_name, asset_id, asset_payload in all_screening_reviews
        if str(asset_payload.get("overall_recommendation") or "") != "keep"
    )
    if non_keep_asset_ids:
        raise RuntimeError(
            "screening JSON contains non-keep assets, refusing import: "
            + ", ".join(non_keep_asset_ids[:10])
        )
    selected_asset_ids = tuple(dict.fromkeys(keep_asset_ids_from_screening(screening)))
    selected_records = _collect_selected_records(
        registry_db_path=registry_db_path,
        selected_asset_ids=selected_asset_ids,
        expected_character_ids=expected_character_ids,
    )

    old_source_entries = validate_source_catalog(catalog_path)
    old_runtime_catalog = read_runtime_catalog_if_present(runtime_path)

    backup_dir.mkdir(parents=True, exist_ok=True)
    _copy_path_if_exists(catalog_path, backup_dir / "catalog.json")
    _copy_path_if_exists(runtime_path, backup_dir / "character_roster_runtime.json")
    _copy_path_if_exists(output_dir, backup_dir / "roster")

    review_payload = review_assets(
        registry_db_path=registry_db_path,
        approve_asset_ids=selected_asset_ids,
        review_notes=DEFAULT_KEEP_REVIEW_NOTE,
    )
    registry = SQLitePortraitRegistry(registry_db_path)
    archived_removed_asset_ids = _archive_removed_published_assets(
        registry,
        keep_character_ids=expected_character_ids,
    )
    publish_payload = publish_assets(
        registry_db_path=registry_db_path,
        catalog_path=catalog_path,
        runtime_path=runtime_path,
        output_dir=output_dir,
        local_portrait_base_url=args.local_portrait_base_url,
        asset_ids=selected_asset_ids,
        source_entries=cast_pack_entries,
        embedding_provider_builder=build_character_embedding_provider,
    )
    removed_stale_character_dirs = []
    if args.import_mode == "replace":
        removed_stale_character_dirs = _cleanup_output_dir_for_replace(
            output_dir,
            keep_character_ids=expected_character_ids,
        )

    payload = {
        "import_mode": args.import_mode,
        "cast_pack_path": str(cast_pack_path),
        "screening_json_path": str(screening_json_path),
        "registry_db_path": str(registry_db_path),
        "catalog_path": str(catalog_path),
        "runtime_path": str(runtime_path),
        "output_dir": str(output_dir),
        "backup_dir": str(backup_dir),
        "old_catalog_entry_count": len(old_source_entries),
        "old_runtime_entry_count": old_runtime_catalog.entry_count if old_runtime_catalog is not None else 0,
        "new_catalog_entry_count": len(cast_pack_entries),
        "selected_asset_count": len(selected_asset_ids),
        "selected_asset_ids": list(selected_asset_ids),
        "selected_character_ids": sorted(expected_character_ids),
        "selected_registry_files": [record.file_path for record in selected_records],
        "review_payload": review_payload,
        "publish_payload": publish_payload,
        "archived_removed_asset_ids": archived_removed_asset_ids,
        "removed_stale_character_dirs": removed_stale_character_dirs,
    }
    (backup_dir / "import_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    payload = run_import(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

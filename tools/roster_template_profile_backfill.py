from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from rpg_backend.roster.admin import embed_runtime_catalog, read_runtime_catalog_if_present, validate_source_catalog, write_runtime_catalog, write_source_catalog
from rpg_backend.roster.embeddings import build_character_embedding_provider
from rpg_backend.roster.template_profiles import default_template_profile_fields, template_profile_complete


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Backfill canonical template profile fields for roster entries.")
    parser.add_argument("--source-path", default=settings.roster_source_catalog_path)
    parser.add_argument("--runtime-path", default=settings.roster_runtime_catalog_path)
    parser.add_argument("--skip-runtime-embed", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    source_entries = validate_source_catalog(Path(args.source_path).expanduser().resolve())
    updated_entries = []
    updated_count = 0
    for entry in source_entries:
        if template_profile_complete(entry):
            updated_entries.append(entry)
            continue
        payload = entry.to_payload()
        payload.update(default_template_profile_fields(entry))
        updated_entries.append(entry.from_payload(payload))
        updated_count += 1
    updated_entries_tuple = tuple(updated_entries)
    write_source_catalog(args.source_path, updated_entries_tuple)
    runtime_payload: dict[str, object] | None = None
    if not args.skip_runtime_embed:
        existing_runtime = read_runtime_catalog_if_present(args.runtime_path)
        runtime_catalog = embed_runtime_catalog(
            updated_entries_tuple,
            embedding_provider=build_character_embedding_provider(settings),
            existing_runtime_catalog=existing_runtime,
            force=False,
        )
        write_runtime_catalog(args.runtime_path, runtime_catalog)
        runtime_payload = {
            "catalog_version": runtime_catalog.catalog_version,
            "entry_count": runtime_catalog.entry_count,
        }
    print(
        json.dumps(
            {
                "source_path": str(Path(args.source_path).expanduser().resolve()),
                "runtime_path": str(Path(args.runtime_path).expanduser().resolve()),
                "updated_count": updated_count,
                "entry_count": len(updated_entries_tuple),
                "runtime": runtime_payload,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

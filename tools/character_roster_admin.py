from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from rpg_backend.roster.admin import (
    build_runtime_catalog,
    embed_runtime_catalog,
    read_runtime_catalog_if_present,
    validate_source_catalog,
    write_runtime_catalog,
)
from rpg_backend.roster.embeddings import build_character_embedding_provider


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Manage the character roster source/build pipeline.")
    parser.add_argument(
        "--source-path",
        default=settings.roster_source_catalog_path,
        help="Canonical source catalog JSON path.",
    )
    parser.add_argument(
        "--runtime-path",
        default=settings.roster_runtime_catalog_path,
        help="Runtime catalog JSON path.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Validate the canonical source catalog.")

    embed_parser = subparsers.add_parser("embed", help="Generate or refresh embeddings and write the runtime catalog.")
    embed_parser.add_argument("--force", action="store_true", help="Re-embed all entries instead of incrementally reusing matching vectors.")

    subparsers.add_parser("build", help="Build the runtime catalog using the current source and any reusable embeddings.")

    args = parser.parse_args(argv)
    source_entries = validate_source_catalog(args.source_path)
    if args.command == "validate":
        print(
            f"validated source catalog: entries={len(source_entries)} path={args.source_path}"
        )
        return 0

    existing_runtime = read_runtime_catalog_if_present(args.runtime_path)
    if args.command == "embed":
        catalog = embed_runtime_catalog(
            source_entries,
            embedding_provider=build_character_embedding_provider(settings),
            existing_runtime_catalog=existing_runtime,
            force=bool(args.force),
        )
        write_runtime_catalog(args.runtime_path, catalog)
        embedded_count = sum(1 for entry in catalog.entries if entry.embedding_vector is not None)
        print(
            f"embedded runtime catalog: entries={catalog.entry_count} embedded={embedded_count} version={catalog.catalog_version} path={args.runtime_path}"
        )
        return 0

    catalog = build_runtime_catalog(
        source_entries,
        existing_runtime_catalog=existing_runtime,
    )
    write_runtime_catalog(args.runtime_path, catalog)
    embedded_count = sum(1 for entry in catalog.entries if entry.embedding_vector is not None)
    print(
        f"built runtime catalog: entries={catalog.entry_count} embedded={embedded_count} version={catalog.catalog_version} path={args.runtime_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

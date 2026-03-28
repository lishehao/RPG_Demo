from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from rpg_backend.roster.embeddings import build_character_embedding_provider
from tools.roster_portrait_ops import publish_assets


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Publish approved portrait candidates into runtime mapping.")
    parser.add_argument("--registry-db-path", default=settings.portrait_manifest_db_path)
    parser.add_argument("--catalog-path", default=settings.roster_source_catalog_path)
    parser.add_argument("--runtime-path", default=settings.roster_runtime_catalog_path)
    parser.add_argument("--output-dir", default=settings.local_portrait_dir)
    parser.add_argument("--local-portrait-base-url", default=settings.local_portrait_base_url)
    parser.add_argument("--asset-id", action="append", dest="asset_ids")
    return parser.parse_args(argv)


def run_publish(args: argparse.Namespace) -> dict[str, Any]:
    return publish_assets(
        registry_db_path=args.registry_db_path,
        catalog_path=args.catalog_path,
        runtime_path=args.runtime_path,
        output_dir=args.output_dir,
        local_portrait_base_url=args.local_portrait_base_url,
        asset_ids=tuple(args.asset_ids or ()),
        embedding_provider_builder=build_character_embedding_provider,
    )


def main(argv: list[str] | None = None) -> int:
    payload = run_publish(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.character_knowledge.indexer import build_character_knowledge_indexer
from rpg_backend.character_knowledge.postgres import build_character_knowledge_repository
from rpg_backend.config import get_settings
from rpg_backend.roster.admin import validate_source_catalog


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Import the formal roster catalog into the Postgres character knowledge layer.")
    parser.add_argument("--source-path", default=settings.roster_source_catalog_path)
    parser.add_argument("--import-mode", choices=("replace", "upsert"), default="replace")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    repository = build_character_knowledge_repository(settings)
    if repository is None:
        raise SystemExit(
            "Character knowledge repository is disabled. Set APP_CHARACTER_KNOWLEDGE_ENABLED=1 "
            "and APP_CHARACTER_KNOWLEDGE_DATABASE_URL before importing."
        )
    source_entries = validate_source_catalog(Path(args.source_path).expanduser().resolve())
    indexer = build_character_knowledge_indexer(
        settings=settings,
        repository=repository,
    )
    payload = indexer.import_source_entries(
        source_entries,
        import_mode=args.import_mode,
    )
    print(json.dumps(payload.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rpg_backend.config import Settings
from rpg_backend.narrative.home_story_library import (
    DEFAULT_HOME_STORY_OWNER_ID,
    ensure_default_home_story_library,
)
from rpg_backend.narrative.service import get_narrative_service


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate/persist default Home story templates through the Story Butler pipeline.",
    )
    parser.add_argument("--runtime-db", type=Path, default=None)
    parser.add_argument("--library-db", type=Path, default=None)
    parser.add_argument("--owner-user-id", default=DEFAULT_HOME_STORY_OWNER_ID)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-path", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings_kwargs: dict[str, str] = {}
    if args.runtime_db is not None:
        settings_kwargs["runtime_state_db_path"] = str(args.runtime_db)
    if args.library_db is not None:
        settings_kwargs["story_library_db_path"] = str(args.library_db)
    settings = Settings(**settings_kwargs)
    service = get_narrative_service(settings)
    results = ensure_default_home_story_library(
        service,
        owner_user_id=str(args.owner_user_id),
        limit=args.limit,
    )
    payload = {
        "owner_user_id": str(args.owner_user_id),
        "items": [
            {
                "library_key": result.library_key,
                "created": result.created,
                "template_id": result.template.template_id,
                "title": result.template.title,
                "visibility": result.template.visibility,
                "language": result.template.language,
            }
            for result in results
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output_path is not None:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

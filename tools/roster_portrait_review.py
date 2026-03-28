from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from tools.roster_portrait_ops import review_assets


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Approve or reject generated portrait assets.")
    parser.add_argument("--registry-db-path", default=settings.portrait_manifest_db_path)
    parser.add_argument("--approve-asset-id", action="append", dest="approve_asset_ids")
    parser.add_argument("--reject-asset-id", action="append", dest="reject_asset_ids")
    parser.add_argument("--review-notes")
    return parser.parse_args(argv)


def run_review(args: argparse.Namespace) -> dict[str, object]:
    return review_assets(
        registry_db_path=args.registry_db_path,
        approve_asset_ids=args.approve_asset_ids or (),
        reject_asset_ids=args.reject_asset_ids or (),
        review_notes=args.review_notes,
    )


def main(argv: list[str] | None = None) -> int:
    payload = run_review(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

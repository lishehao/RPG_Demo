#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from rpg_backend.storage.migrations import (
    DatabaseMigrationError,
    get_current_revision,
    get_head_revision,
    run_downgrade,
    run_upgrade,
)


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Database migration helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upgrade_parser = subparsers.add_parser("upgrade", help="upgrade database revision")
    upgrade_parser.add_argument("revision", nargs="?", default="head")

    downgrade_parser = subparsers.add_parser("downgrade", help="downgrade database revision")
    downgrade_parser.add_argument("revision")

    subparsers.add_parser("current", help="show current applied revision")
    subparsers.add_parser("heads", help="show target head revision")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "upgrade":
            run_upgrade(args.revision)
            _print(
                {
                    "status": "ok",
                    "command": "upgrade",
                    "requested_revision": args.revision,
                    "current_revision": get_current_revision(),
                    "head_revision": get_head_revision(),
                }
            )
            return 0

        if args.command == "downgrade":
            run_downgrade(args.revision)
            _print(
                {
                    "status": "ok",
                    "command": "downgrade",
                    "requested_revision": args.revision,
                    "current_revision": get_current_revision(),
                    "head_revision": get_head_revision(),
                }
            )
            return 0

        if args.command == "current":
            _print(
                {
                    "status": "ok",
                    "command": "current",
                    "current_revision": get_current_revision(),
                    "head_revision": get_head_revision(),
                }
            )
            return 0

        if args.command == "heads":
            _print({"status": "ok", "command": "heads", "head_revision": get_head_revision()})
            return 0

        parser.error(f"unsupported command: {args.command}")
        return 2
    except DatabaseMigrationError as exc:
        _print(
            {
                "status": "error",
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

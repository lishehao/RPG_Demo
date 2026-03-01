#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.domain.linter import lint_story_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint a story pack JSON file.")
    parser.add_argument("pack_path", type=Path)
    args = parser.parse_args()

    pack_json = json.loads(args.pack_path.read_text(encoding="utf-8"))
    report = lint_story_pack(pack_json)

    if report.ok:
        print("OK: story pack passed lint checks")
    else:
        print("ERRORS:")
        for err in report.errors:
            print(f"- {err}")

    if report.warnings:
        print("WARNINGS:")
        for warning in report.warnings:
            print(f"- {warning}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

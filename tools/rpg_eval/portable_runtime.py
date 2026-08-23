from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rpg_backend.research_runtime.contracts import RpgEvaluationBundleV1
from rpg_backend.research_runtime.evaluator import evaluate_rpg_bundle


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    bundle = RpgEvaluationBundleV1.model_validate(payload)
    return evaluate_rpg_bundle(bundle).model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a portable RPG turn bundle without provider calls.",
    )
    parser.add_argument("input", type=Path, help="Path to an rpg_evaluation_bundle.v1 JSON file.")
    parser.add_argument("--out", type=Path, help="Optional report output path. Defaults to stdout.")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = evaluate_payload(payload)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

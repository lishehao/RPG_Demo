from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.portraits.prompting import prompt_hash
from tools.author_cast_portrait_common import (
    load_author_portrait_plan,
)

_VALID_VARIANTS = {"negative", "neutral", "positive"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local author cast portrait assets against a plan.")
    parser.add_argument("--plan-path", required=True)
    parser.add_argument("--validation-path")
    return parser.parse_args(argv)


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    plan = load_author_portrait_plan(args.plan_path)
    output_dir = Path(plan.output_dir).expanduser().resolve()
    missing_files: list[str] = []
    invalid_variants: list[str] = []
    hash_mismatches: list[str] = []
    generated_count = 0
    for job in plan.jobs:
        if job.variant_key not in _VALID_VARIANTS and job.variant_key not in invalid_variants:
            invalid_variants.append(job.variant_key)
        if prompt_hash(job.prompt_text) != job.prompt_hash:
            hash_mismatches.append(job.asset_id)
        output_path = output_dir / job.relative_output_path
        if not output_path.exists():
            missing_files.append(str(output_path))
            continue
        try:
            content = output_path.read_bytes()
        except OSError:
            missing_files.append(str(output_path))
            continue
        if not content:
            missing_files.append(str(output_path))
            continue
        generated_count += 1
    payload = {
        "job_id": plan.job_id,
        "revision": plan.revision,
        "subject_count": len(plan.subjects),
        "job_count": len(plan.jobs),
        "generated_count": generated_count,
        "missing_files": missing_files,
        "invalid_variants": invalid_variants,
        "prompt_version": plan.prompt_version,
        "image_model": plan.image_model,
        "hash_mismatches": hash_mismatches,
        "ok": not missing_files and not invalid_variants and not hash_mismatches,
    }
    validation_path = (
        Path(args.validation_path).expanduser().resolve()
        if args.validation_path
        else output_dir / "validation.json"
    )
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["validation_path"] = str(validation_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    payload = run_validation(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

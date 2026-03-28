from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.author_cast_portrait_common import load_author_portrait_plan
from tools.roster_portrait_common import generate_portrait_image


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local portrait assets from an author cast portrait plan.")
    parser.add_argument("--plan-path", required=True)
    parser.add_argument("--api-key")
    parser.add_argument("--request-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--asset-id", action="append", dest="asset_ids")
    return parser.parse_args(argv)


def run_generation(args: argparse.Namespace) -> dict[str, Any]:
    api_key = str(args.api_key or os.environ.get("PORTRAIT_IMAGE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("PORTRAIT_IMAGE_API_KEY is required via --api-key or environment.")
    plan = load_author_portrait_plan(args.plan_path)
    selected_asset_ids = set(args.asset_ids or [])
    generated_asset_ids: list[str] = []
    generated_files: list[str] = []
    output_dir = Path(plan.output_dir).expanduser().resolve()
    with requests.Session() as session:
        for job in plan.jobs:
            if selected_asset_ids and job.asset_id not in selected_asset_ids:
                continue
            image_bytes, mime_type = generate_portrait_image(
                session,
                api_key=api_key,
                image_api_base_url=plan.image_api_base_url,
                image_model=plan.image_model,
                request_timeout_seconds=max(float(args.request_timeout_seconds), 1.0),
                prompt_text=job.prompt_text,
            )
            if mime_type not in {"image/png", "image/x-png", "image/jpeg", "image/jpg"}:
                raise RuntimeError(f"unsupported portrait mime type for {job.asset_id}: {mime_type}")
            output_path = output_dir / job.relative_output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            generated_asset_ids.append(job.asset_id)
            generated_files.append(str(output_path))
    return {
        "job_id": plan.job_id,
        "revision": plan.revision,
        "generated_count": len(generated_asset_ids),
        "generated_asset_ids": generated_asset_ids,
        "generated_files": generated_files,
        "output_dir": str(output_dir),
    }


def main(argv: list[str] | None = None) -> int:
    payload = run_generation(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

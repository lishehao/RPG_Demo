from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from rpg_backend.roster.portrait_registry import PortraitAssetRecord, SQLitePortraitRegistry
from tools.roster_portrait_common import (
    build_reference_relative_output_path,
    detect_image_mime_type,
    generate_portrait_image,
    load_plan_file,
)

_VARIANT_PRIORITY = {"neutral": 0, "negative": 1, "positive": 2}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Generate candidate roster portraits from a plan file.")
    parser.add_argument("--plan-path", required=True)
    parser.add_argument("--registry-db-path", default=settings.portrait_manifest_db_path)
    parser.add_argument("--api-key")
    parser.add_argument("--request-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--asset-id", action="append", dest="asset_ids")
    return parser.parse_args(argv)


def run_generation(args: argparse.Namespace) -> dict[str, Any]:
    api_key = str(args.api_key or os.environ.get("PORTRAIT_IMAGE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("PORTRAIT_IMAGE_API_KEY is required via --api-key or environment.")

    plan = load_plan_file(args.plan_path)
    registry = SQLitePortraitRegistry(args.registry_db_path)
    selected_asset_ids = set(args.asset_ids or [])
    generated_files: list[str] = []
    generated_asset_ids: list[str] = []
    jobs = list(plan.jobs)
    jobs.sort(
        key=lambda job: (
            job.character_id,
            job.candidate_index,
            _VARIANT_PRIORITY.get(job.variant_key, 99),
            job.asset_id,
        )
    )

    with requests.Session() as session:
        for job in jobs:
            if selected_asset_ids and job.asset_id not in selected_asset_ids:
                continue
            reference_image_bytes = None
            reference_mime_type = None
            if job.reference_relative_output_path:
                reference_path = Path(plan.output_dir) / job.reference_relative_output_path
                if not reference_path.exists():
                    raise RuntimeError(
                        f"reference portrait missing for {job.asset_id}: {reference_path}"
                    )
                reference_image_bytes = reference_path.read_bytes()
                reference_mime_type = detect_image_mime_type(reference_image_bytes)
                if reference_mime_type not in {"image/png", "image/jpeg"}:
                    raise RuntimeError(
                        f"unsupported reference portrait mime type for {job.asset_id}: {reference_mime_type}"
                    )
            image_bytes, mime_type = generate_portrait_image(
                session,
                api_key=api_key,
                image_api_base_url=plan.image_api_base_url,
                image_model=plan.image_model,
                request_timeout_seconds=max(float(args.request_timeout_seconds), 1.0),
                prompt_text=job.prompt_text,
                reference_image_bytes=reference_image_bytes,
                reference_mime_type=reference_mime_type,
            )
            if mime_type not in {"image/png", "image/x-png", "image/jpeg", "image/jpg"}:
                raise RuntimeError(f"unsupported portrait mime type for {job.asset_id}: {mime_type}")
            output_path = Path(plan.output_dir) / job.relative_output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            if job.variant_key == "neutral":
                reference_output_path = Path(plan.output_dir) / build_reference_relative_output_path(
                    character_id=job.character_id,
                    candidate_index=job.candidate_index,
                )
                reference_output_path.parent.mkdir(parents=True, exist_ok=True)
                reference_output_path.write_bytes(image_bytes)
            generated_files.append(str(output_path))
            generated_asset_ids.append(job.asset_id)
            registry.save_asset(
                PortraitAssetRecord(
                    asset_id=job.asset_id,
                    character_id=job.character_id,
                    variant_key=job.variant_key,
                    candidate_index=job.candidate_index,
                    status="generated",
                    file_path=str(output_path),
                    public_url=None,
                    prompt_version=plan.prompt_version,
                    prompt_hash=job.prompt_hash,
                    image_model=plan.image_model,
                    image_api_base_url=plan.image_api_base_url,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                )
            )

    return {
        "batch_id": plan.batch_id,
        "registry_db_path": registry.db_path,
        "generated_count": len(generated_asset_ids),
        "generated_asset_ids": generated_asset_ids,
        "generated_files": generated_files,
    }


def main(argv: list[str] | None = None) -> int:
    payload = run_generation(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from rpg_backend.roster.admin import validate_source_catalog
from rpg_backend.roster.portrait_registry import PortraitVariantKey
from tools.roster_portrait_common import (
    DEFAULT_CANDIDATES_PER_VARIANT,
    DEFAULT_IMAGE_API_BASE_URL,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_PROMPT_VERSION,
    DEFAULT_VARIANTS,
    PortraitBatchPlan,
    PortraitGenerationJob,
    build_asset_id,
    build_batch_id,
    build_portrait_prompt,
    build_reference_relative_output_path,
    build_relative_output_path,
    default_jobs_dir,
    default_output_dir,
    prompt_hash,
    write_plan_file,
)

_VARIANT_PRIORITY = {"neutral": 0, "negative": 1, "positive": 2}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Build a roster portrait generation matrix.")
    parser.add_argument("--batch-id")
    parser.add_argument("--plan-path")
    parser.add_argument("--catalog-path", default=settings.roster_source_catalog_path)
    parser.add_argument("--output-dir", default=str(default_output_dir()))
    parser.add_argument("--image-api-base-url", default=DEFAULT_IMAGE_API_BASE_URL)
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--prompt-version", default=DEFAULT_PROMPT_VERSION)
    parser.add_argument("--character-id", action="append", dest="character_ids")
    parser.add_argument("--variant", action="append", dest="variants")
    parser.add_argument("--candidates-per-variant", type=int, default=DEFAULT_CANDIDATES_PER_VARIANT)
    return parser.parse_args(argv)


def build_job_matrix(
    *,
    catalog_path: str | Path,
    character_ids: tuple[str, ...],
    variants: tuple[PortraitVariantKey, ...],
    candidates_per_variant: int,
    prompt_version: str,
    image_model: str,
    image_api_base_url: str,
    output_dir: str | Path,
    batch_id: str | None = None,
) -> PortraitBatchPlan:
    source_entries = validate_source_catalog(catalog_path)
    source_by_id = {entry.character_id: entry for entry in source_entries}
    missing_ids = [character_id for character_id in character_ids if character_id not in source_by_id]
    if missing_ids:
        raise RuntimeError(f"unknown character ids: {', '.join(missing_ids)}")
    invalid_variants = [variant for variant in variants if variant not in {"negative", "neutral", "positive"}]
    if invalid_variants:
        raise RuntimeError(f"unsupported portrait variants: {', '.join(invalid_variants)}")
    if candidates_per_variant < 1:
        raise RuntimeError("candidates_per_variant must be >= 1")

    resolved_batch_id = batch_id or build_batch_id("portrait")
    jobs: list[PortraitGenerationJob] = []
    for character_id in character_ids:
        entry = source_by_id[character_id]
        sorted_variants = tuple(sorted(variants, key=lambda item: (_VARIANT_PRIORITY.get(item, 99), item)))
        for candidate_index in range(1, candidates_per_variant + 1):
            for variant_key in sorted_variants:
                prompt_text = build_portrait_prompt(entry, variant_key=variant_key, prompt_version=prompt_version)
                hashed = prompt_hash(prompt_text)
                asset_id = build_asset_id(
                    character_id=character_id,
                    variant_key=variant_key,
                    candidate_index=candidate_index,
                    prompt_hash=hashed,
                )
                relative_output_path = build_relative_output_path(
                    character_id=character_id,
                    variant_key=variant_key,
                    asset_id=asset_id,
                )
                reference_relative_output_path = None
                if variant_key in {"negative", "positive"}:
                    reference_relative_output_path = build_reference_relative_output_path(
                        character_id=character_id,
                        candidate_index=candidate_index,
                    )
                jobs.append(
                    PortraitGenerationJob(
                        asset_id=asset_id,
                        character_id=character_id,
                        variant_key=variant_key,
                        candidate_index=candidate_index,
                        prompt_text=prompt_text,
                        prompt_hash=hashed,
                        relative_output_path=relative_output_path,
                        reference_relative_output_path=reference_relative_output_path,
                    )
                )
    return PortraitBatchPlan(
        batch_id=resolved_batch_id,
        prompt_version=prompt_version,
        image_model=image_model,
        image_api_base_url=image_api_base_url,
        output_dir=str(Path(output_dir).expanduser().resolve()),
        jobs=tuple(jobs),
    )


def run_plan(args: argparse.Namespace) -> dict[str, Any]:
    variants = tuple(args.variants or DEFAULT_VARIANTS)
    character_ids = tuple(
        args.character_ids
        or (
            "roster_archive_certifier",
            "roster_courtyard_witness",
            "roster_blackout_grid_broker",
        )
    )
    plan = build_job_matrix(
        catalog_path=args.catalog_path,
        character_ids=character_ids,
        variants=variants,
        candidates_per_variant=int(args.candidates_per_variant),
        prompt_version=str(args.prompt_version),
        image_model=str(args.image_model),
        image_api_base_url=str(args.image_api_base_url).rstrip("/"),
        output_dir=args.output_dir,
        batch_id=args.batch_id,
    )
    plan_path = Path(args.plan_path).expanduser().resolve() if args.plan_path else default_jobs_dir() / f"{plan.batch_id}.json"
    write_plan_file(plan_path, plan)
    return {
        "batch_id": plan.batch_id,
        "plan_path": str(plan_path),
        "job_count": len(plan.jobs),
        "character_ids": list(character_ids),
        "variants": list(variants),
        "candidates_per_variant": int(args.candidates_per_variant),
    }


def main(argv: list[str] | None = None) -> int:
    payload = run_plan(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

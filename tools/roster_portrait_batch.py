from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import sys
import time
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import Settings, get_settings
from rpg_backend.roster.portrait_registry import SQLitePortraitRegistry
from tools.roster_portrait_common import (
    DEFAULT_CANDIDATES_PER_VARIANT,
    DEFAULT_IMAGE_API_BASE_URL,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_PROMPT_VERSION,
    DEFAULT_VARIANTS,
    PortraitVariantKey,
    build_portrait_prompt,
    build_image_request_payload,
    default_jobs_dir,
    extract_image_part,
    generate_portrait_image,
    write_plan_file,
)
from tools.roster_portrait_ops import publish_assets, review_assets
from tools.roster_portrait_generate import run_generation
from tools.roster_portrait_plan import build_job_matrix


DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "portraits" / "roster"
DEFAULT_CHARACTER_IDS: tuple[str, ...] = (
    "roster_archive_certifier",
    "roster_courtyard_witness",
    "roster_blackout_grid_broker",
)
VALIDATION_SEED_VARIANTS: tuple[str, ...] = (
    "During a blackout legitimacy hearing, a city archivist must restore one binding public record before rival factions weaponize sealed testimony and the council votes in the dark.",
    "When blackout ledgers, witness notes, and emergency hearing transcripts are quietly altered, a civic archivist must force a public certification before the city accepts a forged mandate.",
    "At a public hearing held during rolling blackouts, a records advocate must expose tampered ledgers and witness-chain gaps before factional brokers lock the city into a false settlement.",
)


@dataclass(frozen=True)
class PortraitBatchConfig:
    api_key: str
    backend_base_url: str
    image_api_base_url: str
    image_model: str
    output_dir: Path
    catalog_path: Path
    runtime_path: Path
    registry_db_path: Path
    character_ids: tuple[str, ...]
    variants: tuple[PortraitVariantKey, ...]
    candidates_per_variant: int
    request_timeout_seconds: float
    local_portrait_base_url: str
    prompt_version: str
    skip_validation: bool
    batch_id: str | None = None


def parse_args(argv: list[str] | None = None) -> PortraitBatchConfig:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Generate, approve, and publish roster portrait variants.")
    parser.add_argument("--api-key")
    parser.add_argument("--backend-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image-api-base-url", default=DEFAULT_IMAGE_API_BASE_URL)
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--catalog-path", default=settings.roster_source_catalog_path)
    parser.add_argument("--runtime-path", default=settings.roster_runtime_catalog_path)
    parser.add_argument("--registry-db-path", default=settings.portrait_manifest_db_path)
    parser.add_argument("--character-id", action="append", dest="character_ids")
    parser.add_argument("--variant", action="append", dest="variants")
    parser.add_argument("--candidates-per-variant", type=int, default=DEFAULT_CANDIDATES_PER_VARIANT)
    parser.add_argument("--request-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--prompt-version", default=DEFAULT_PROMPT_VERSION)
    parser.add_argument("--batch-id")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args(argv)

    api_key = str(args.api_key or __import__("os").environ.get("PORTRAIT_IMAGE_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("PORTRAIT_IMAGE_API_KEY is required via --api-key or environment.")

    character_ids = tuple(args.character_ids or DEFAULT_CHARACTER_IDS)
    variants = tuple(args.variants or DEFAULT_VARIANTS)
    return PortraitBatchConfig(
        api_key=api_key,
        backend_base_url=str(args.backend_base_url).rstrip("/"),
        image_api_base_url=str(args.image_api_base_url).rstrip("/"),
        image_model=str(args.image_model).strip(),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        catalog_path=Path(args.catalog_path).expanduser().resolve(),
        runtime_path=Path(args.runtime_path).expanduser().resolve(),
        registry_db_path=Path(args.registry_db_path).expanduser().resolve(),
        character_ids=character_ids,
        variants=variants,
        candidates_per_variant=max(int(args.candidates_per_variant), 1),
        request_timeout_seconds=max(float(args.request_timeout_seconds), 1.0),
        local_portrait_base_url=str(settings.local_portrait_base_url).rstrip("/"),
        prompt_version=str(args.prompt_version).strip(),
        skip_validation=bool(args.skip_validation),
        batch_id=str(args.batch_id).strip() if args.batch_id else None,
    )


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout_seconds: float,
    **kwargs: Any,
) -> dict[str, Any]:
    response = session.request(method, url, timeout=timeout_seconds, **kwargs)
    if not response.ok:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        raise RuntimeError(f"{method} {url} failed: {payload}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {url} returned non-object payload")
    return payload


def _authenticate(session: requests.Session, backend_base_url: str, *, timeout_seconds: float) -> None:
    payload = {
        "display_name": "Portrait Batch",
        "email": f"portrait-batch-{secrets.token_hex(6)}@bench.local",
        "password": "BenchPass123!",
    }
    body = _request_json(
        session,
        "POST",
        f"{backend_base_url}/auth/register",
        timeout_seconds=timeout_seconds,
        json=payload,
    )
    if not body.get("authenticated"):
        raise RuntimeError("portrait batch auth registration did not authenticate")


def _poll_author_job(
    session: requests.Session,
    backend_base_url: str,
    *,
    job_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    while True:
        payload = _request_json(
            session,
            "GET",
            f"{backend_base_url}/author/jobs/{job_id}",
            timeout_seconds=timeout_seconds,
        )
        if payload.get("status") in {"completed", "failed"}:
            return payload
        if time.perf_counter() - started_at > timeout_seconds:
            raise RuntimeError(f"author job '{job_id}' did not finish within {timeout_seconds:.1f}s")
        time.sleep(1.0)


def _matching_supporting_cast_ids(editor_state: dict[str, Any], target_character_ids: set[str]) -> list[str]:
    cast_view = list(editor_state.get("cast_view") or [])
    if len(cast_view) != 4:
        return []
    supporting = cast_view[1:]
    matched = [
        str(item.get("roster_character_id"))
        for item in supporting
        if item.get("roster_character_id") in target_character_ids and item.get("portrait_url")
    ]
    return matched


def validate_three_cast_story(
    config: PortraitBatchConfig,
    *,
    target_character_ids: tuple[str, ...],
) -> dict[str, Any]:
    if get_settings().roster_max_supporting_cast_selections < 3:
        raise RuntimeError("APP_ROSTER_MAX_SUPPORTING_CAST_SELECTIONS must be set to 3 for three-cast validation")
    target_id_set = set(target_character_ids)
    with requests.Session() as session:
        _authenticate(session, config.backend_base_url, timeout_seconds=config.request_timeout_seconds)
        for seed in VALIDATION_SEED_VARIANTS:
            preview = _request_json(
                session,
                "POST",
                f"{config.backend_base_url}/author/story-previews",
                timeout_seconds=config.request_timeout_seconds,
                json={"prompt_seed": seed, "language": "en"},
            )
            job = _request_json(
                session,
                "POST",
                f"{config.backend_base_url}/author/jobs",
                timeout_seconds=config.request_timeout_seconds,
                json={"prompt_seed": seed, "preview_id": preview["preview_id"], "language": "en"},
            )
            job_id = str(job["job_id"])
            status = _poll_author_job(
                session,
                config.backend_base_url,
                job_id=job_id,
                timeout_seconds=max(config.request_timeout_seconds, 600.0),
            )
            if status.get("status") != "completed":
                continue
            editor_state = _request_json(
                session,
                "GET",
                f"{config.backend_base_url}/author/jobs/{job_id}/editor-state",
                timeout_seconds=config.request_timeout_seconds,
            )
            matched = _matching_supporting_cast_ids(editor_state, target_id_set)
            if len(matched) != 3 or len(set(matched)) != 3:
                continue
            published = _request_json(
                session,
                "POST",
                f"{config.backend_base_url}/author/jobs/{job_id}/publish",
                timeout_seconds=config.request_timeout_seconds,
            )
            story_id = str(published["story_id"])
            detail = _request_json(
                session,
                "GET",
                f"{config.backend_base_url}/stories/{story_id}",
                timeout_seconds=config.request_timeout_seconds,
            )
            manifest_entries = list(dict(detail.get("cast_manifest") or {}).get("entries") or [])
            detail_matched = [
                str(item.get("roster_character_id"))
                for item in manifest_entries[1:]
                if item.get("roster_character_id") in target_id_set and item.get("portrait_url")
            ]
            if len(detail_matched) != 3 or len(set(detail_matched)) != 3:
                continue
            return {
                "matched": True,
                "seed": seed,
                "job_id": job_id,
                "story_id": story_id,
                "matched_supporting_cast_ids": matched,
            }
    raise RuntimeError("validation_story_not_three_roster_cast")


def run_portrait_batch(config: PortraitBatchConfig) -> dict[str, Any]:
    plan = build_job_matrix(
        catalog_path=config.catalog_path,
        character_ids=config.character_ids,
        variants=config.variants,
        candidates_per_variant=config.candidates_per_variant,
        prompt_version=config.prompt_version,
        image_model=config.image_model,
        image_api_base_url=config.image_api_base_url,
        output_dir=config.output_dir,
        batch_id=config.batch_id,
    )
    plan_path = default_jobs_dir() / f"{plan.batch_id}.json"
    write_plan_file(plan_path, plan)

    generated_payload = run_generation(
        argparse.Namespace(
            plan_path=str(plan_path),
            registry_db_path=str(config.registry_db_path),
            api_key=config.api_key,
            request_timeout_seconds=config.request_timeout_seconds,
            asset_ids=None,
        )
    )

    auto_approve_asset_ids = [
        job.asset_id
        for job in plan.jobs
        if job.candidate_index == 1
    ]
    review_assets(
        registry_db_path=config.registry_db_path,
        approve_asset_ids=auto_approve_asset_ids,
        review_notes="auto-approved by roster_portrait_batch wrapper",
    )
    publish_payload = publish_assets(
        registry_db_path=config.registry_db_path,
        catalog_path=config.catalog_path,
        runtime_path=config.runtime_path,
        output_dir=config.output_dir,
        local_portrait_base_url=config.local_portrait_base_url,
        asset_ids=auto_approve_asset_ids,
    )

    payload: dict[str, Any] = {
        "batch_id": plan.batch_id,
        "plan_path": str(plan_path),
        "registry_db_path": str(config.registry_db_path),
        "character_ids": list(config.character_ids),
        "variants": list(config.variants),
        "candidates_per_variant": config.candidates_per_variant,
        "generated_files": generated_payload["generated_files"],
        "published_assets": publish_payload["published_assets"],
        "catalog_path": str(config.catalog_path),
        "runtime_path": str(config.runtime_path),
        "portrait_base_url": config.local_portrait_base_url,
        "validation": None,
    }
    if not config.skip_validation:
        payload["validation"] = validate_three_cast_story(config, target_character_ids=config.character_ids)
    return payload


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_portrait_batch(config)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

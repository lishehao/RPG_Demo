from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.roster_portrait_generate import run_generation
from tools.roster_portrait_plan import build_job_matrix
from tools.roster_portrait_common import write_plan_file
from tools.template_portrait_common import default_template_trials_root, template_character_map


def _load_env_value(name: str) -> str | None:
    candidate = os.environ.get(name)
    if candidate:
        return candidate
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == name and value.strip():
            return value.strip().strip('"').strip("'")
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run portrait generation batches for template-aligned cast trios.")
    parser.add_argument("--cast-pack-path", default="artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json")
    parser.add_argument("--trials-root", default=str(default_template_trials_root()))
    parser.add_argument("--template", action="append", dest="templates")
    parser.add_argument("--skip-template", action="append", dest="skip_templates")
    parser.add_argument("--candidates-per-variant", type=int, default=1)
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--api-key")
    return parser.parse_args(argv)


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
    api_key = str(args.api_key or _load_env_value("PORTRAIT_IMAGE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("PORTRAIT_IMAGE_API_KEY is required via --api-key, environment, or .env.")
    trials_root = Path(args.trials_root).expanduser().resolve()
    mapping = template_character_map(cast_pack_path=args.cast_pack_path)
    selected_templates = list(args.templates or mapping.keys())
    skipped_templates = set(args.skip_templates or [])
    template_results: list[dict[str, Any]] = []
    for template_name in selected_templates:
        if template_name in skipped_templates:
            continue
        character_ids = tuple(item["character_id"] for item in mapping[template_name])
        trial_dir = trials_root / template_name
        plan = build_job_matrix(
            catalog_path=args.cast_pack_path,
            character_ids=character_ids,
            variants=("negative", "neutral", "positive"),
            candidates_per_variant=int(args.candidates_per_variant),
            prompt_version="v1_editorial_dossier",
            image_model="gemini-3.1-flash-image-preview",
            image_api_base_url="https://vip.123everything.com",
            output_dir=trial_dir,
        )
        plan_path = trial_dir / "portrait_plan.json"
        write_plan_file(plan_path, plan)
        generation = run_generation(
            argparse.Namespace(
                plan_path=str(plan_path),
                registry_db_path="data/character_roster/portrait_manifest.sqlite3",
                api_key=api_key,
                request_timeout_seconds=float(args.request_timeout_seconds),
                asset_ids=None,
            )
        )
        template_results.append(
            {
                "template_name": template_name,
                "character_ids": list(character_ids),
                "plan_path": str(plan_path),
                "generated_count": generation["generated_count"],
                "generated_files": generation["generated_files"],
            }
        )
    return {
        "trials_root": str(trials_root),
        "template_results": template_results,
        "template_count": len(template_results),
        "generated_count": sum(int(item["generated_count"]) for item in template_results),
    }


def main(argv: list[str] | None = None) -> int:
    payload = run_batch(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

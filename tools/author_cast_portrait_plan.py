from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.author.contracts import AuthorCastPortraitPlanRequest
from rpg_backend.author.jobs import AuthorJobService
from tools.author_cast_portrait_common import (
    default_author_portrait_job_dir,
    default_author_portrait_plan_path,
    write_author_portrait_plan,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local portrait generation plan for an author job cast.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--npc-id", action="append", dest="npc_ids")
    parser.add_argument("--variant", action="append", dest="variants")
    parser.add_argument("--candidates-per-variant", type=int, default=1)
    parser.add_argument("--prompt-version", default="v1_editorial_dossier")
    parser.add_argument("--actor-user-id")
    parser.add_argument("--output-dir")
    parser.add_argument("--plan-path")
    return parser.parse_args(argv)


def run_plan(args: argparse.Namespace) -> dict[str, Any]:
    service = AuthorJobService()
    request = AuthorCastPortraitPlanRequest(
        npc_ids=list(args.npc_ids or []),
        variants=list(args.variants or ["negative", "neutral", "positive"]),
        candidates_per_variant=int(args.candidates_per_variant),
        prompt_version=str(args.prompt_version),
    )
    plan = service.create_cast_portrait_plan(
        str(args.job_id),
        request,
        actor_user_id=str(args.actor_user_id) if args.actor_user_id else None,
    )
    resolved_output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else default_author_portrait_job_dir(plan.job_id)
    )
    plan = plan.model_copy(update={"output_dir": str(resolved_output_dir)})
    plan_path = (
        Path(args.plan_path).expanduser().resolve()
        if args.plan_path
        else default_author_portrait_plan_path(plan.job_id)
    )
    if not args.plan_path and args.output_dir:
        plan_path = resolved_output_dir / "portrait_plan.json"
    write_author_portrait_plan(plan_path, plan)
    return {
        "job_id": plan.job_id,
        "revision": plan.revision,
        "batch_id": plan.batch_id,
        "language": plan.language,
        "subject_count": len(plan.subjects),
        "job_count": len(plan.jobs),
        "output_dir": plan.output_dir,
        "plan_path": str(plan_path),
    }


def main(argv: list[str] | None = None) -> int:
    payload = run_plan(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

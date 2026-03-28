from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.play_benchmarks import live_stability_matrix

DEFAULT_OUTPUT_DIR = live_stability_matrix.DEFAULT_OUTPUT_DIR


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate per-bucket live stability matrix artifacts.")
    parser.add_argument("--artifacts", nargs="+", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--label")
    return parser.parse_args(argv)


def aggregate_payloads(payloads: list[dict[str, Any]], *, label: str | None = None) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    bucket_ids: list[str] = []
    durations: set[int] = set()
    base_url = ""
    preflight_passed = True
    stage1_smoke_passed = True
    for payload in payloads:
        if not base_url:
            base_url = str(payload.get("base_url") or "")
        bucket_ids.extend([str(item) for item in list(payload.get("bucket_ids") or [])])
        durations.update(int(item) for item in list(payload.get("durations") or []) if int(item) > 0)
        cells.extend(list(payload.get("cells") or []))
        payload_summary = dict(payload.get("summary") or {})
        preflight_passed = preflight_passed and bool(payload_summary.get("preflight_passed", True))
        stage1_smoke_passed = stage1_smoke_passed and bool(payload_summary.get("stage1_smoke_passed", True))
    unique_bucket_ids = sorted(set(bucket_ids))
    summary = live_stability_matrix._build_matrix_summary(  # noqa: SLF001
        cells,
        preflight_passed=preflight_passed,
        stage1_smoke_passed=stage1_smoke_passed,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "label": label,
        "bucket_ids": unique_bucket_ids,
        "durations": sorted(durations),
        "cells": cells,
        "summary": summary,
    }


def write_artifacts(output_dir: Path, label: str | None, payload: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{label or 'live_stability_matrix_aggregate'}_{timestamp}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Live Stability Aggregate",
        "",
        f"- Base URL: `{payload.get('base_url')}`",
        f"- Bucket IDs: `{payload.get('bucket_ids')}`",
        f"- Durations: `{payload.get('durations')}`",
        f"- Overall verdict: `{summary.get('passed')}`",
        f"- Preflight passed: `{summary.get('preflight_passed')}`",
        f"- Stage-1 smoke passed: `{summary.get('stage1_smoke_passed')}`",
        f"- Core gate passed: `{summary.get('core_gate_passed')}`",
        f"- Full-live gate passed: `{summary.get('full_live_gate_passed')}`",
        f"- Cells passed: `{summary.get('cells_passed')}` / `{summary.get('cells_total')}`",
        f"- Core cells passed: `{summary.get('core_cells_passed')}` / `{summary.get('core_cells_total')}`",
        f"- Full-live cells passed: `{summary.get('full_live_cells_passed')}` / `{summary.get('full_live_cells_total')}`",
        f"- Preview pass rate: `{summary.get('preview_pass_rate')}`",
        f"- Author publish pass rate: `{summary.get('author_publish_pass_rate')}`",
        f"- Turn probe pass rate: `{summary.get('turn_probe_pass_rate')}`",
        f"- Strategy consistency pass rate: `{summary.get('strategy_consistency_pass_rate')}`",
        f"- Full live pass rate: `{summary.get('full_live_pass_rate')}`",
        f"- Max observed preview elapsed seconds: `{summary.get('max_observed_preview_elapsed_seconds')}`",
        f"- Max observed author elapsed seconds: `{summary.get('max_observed_author_elapsed_seconds')}`",
        f"- Max observed turn proposal elapsed seconds: `{summary.get('max_observed_turn_proposal_elapsed_seconds')}`",
        "",
        "## Failure Stage Distribution",
        "",
    ]
    for key, value in dict(summary.get("failure_stage_distribution") or {}).items():
        lines.append(f"- `{key}` count=`{value}`")
    lines.extend(["", "## Bucket Pass Matrix", ""])
    for key, value in dict(summary.get("bucket_pass_matrix") or {}).items():
        lines.append(f"- `{key}` passed=`{value}`")
    lines.extend(["", "## Duration Pass Matrix", ""])
    for key, value in dict(summary.get("duration_pass_matrix") or {}).items():
        lines.append(f"- `{key}` passed=`{value}`")
    lines.extend(["", "## Strategy Drift", "", f"- Drift count: `{summary.get('strategy_drift_count')}`"])
    for item in list(summary.get("strategy_drift_cells") or []):
        lines.append(
            f"- `{item.get('bucket_id')}` `duration={item.get('target_duration_minutes')}` "
            f"expected=`{item.get('bucket_strategy_expected')}` "
            f"actual=`{item.get('story_frame_strategy')}` / `{item.get('cast_strategy')}` / `{item.get('beat_plan_strategy')}`"
        )
    lines.extend(["", "## Blocking Cells", ""])
    for item in list(summary.get("blocking_cells") or []):
        lines.append(
            f"- `{item.get('bucket_id')}` `duration={item.get('target_duration_minutes')}` "
            f"stage=`{item.get('failure_stage')}` op=`{item.get('operation')}` route=`{item.get('route')}` "
            f"persona=`{item.get('persona_id')}` turn=`{item.get('turn_index')}` "
            f"error=`{item.get('first_error')}`"
        )
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payloads = [json.loads(Path(path).read_text()) for path in args.artifacts]
    aggregate = aggregate_payloads(payloads, label=args.label)
    json_path, md_path = write_artifacts(Path(args.output_dir).expanduser().resolve(), args.label, aggregate)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "passed": bool((aggregate.get("summary") or {}).get("passed"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

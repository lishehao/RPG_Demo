from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.template_portrait_common import (
    default_template_trials_root,
    load_screening,
    review_field_order,
    template_character_map,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a review sheet for template portrait trial batches.")
    parser.add_argument("--cast-pack-path", default="artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json")
    parser.add_argument("--trials-root", default=str(default_template_trials_root()))
    parser.add_argument("--output-path", default="artifacts/portraits/template_trials/review_sheet.md")
    parser.add_argument("--screening-json")
    return parser.parse_args(argv)

def _screening_for(screening: dict[str, Any], *, template_name: str, asset_id: str) -> dict[str, str]:
    template_payload = screening.get(template_name) or {}
    asset_payload = template_payload.get(asset_id) or {}
    review = {field: str(asset_payload.get(field) or "pending") for field in review_field_order()}
    review["initial_screening_note"] = str(asset_payload.get("initial_screening_note") or "pending")
    return review


def build_review_sheet(args: argparse.Namespace) -> str:
    trials_root = Path(args.trials_root).expanduser().resolve()
    cast_mapping = template_character_map(cast_pack_path=args.cast_pack_path)
    screening = load_screening(args.screening_json)
    lines = [
        "# Template Portrait Review Sheet",
        "",
        f"Trials root: `{trials_root}`",
        "",
        "Legend: use `pass / watch / fail` for review fields; use `keep / regenerate / needs_ui_review_attention` for `overall_recommendation`.",
        "",
    ]
    for template_name, trio in cast_mapping.items():
        template_dir = trials_root / template_name
        plan_path = template_dir / "portrait_plan.json"
        lines.append(f"## `{template_name}`")
        lines.append("")
        lines.append(f"- Trial dir: `{template_dir}`")
        lines.append(f"- Plan path: `{plan_path}`")
        lines.append("- Trio:")
        for member in trio:
            lines.append(f"  - `{member['character_id']}` — {member['name_en']} / {member['name_zh']} — {member['role_hint_en']}")
        lines.append("")
        if not plan_path.exists():
            lines.append("- Status: `missing_trial_plan`")
            lines.append("")
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        jobs = list(plan.get("jobs") or [])
        for job in jobs:
            asset_id = str(job["asset_id"])
            variant = str(job["variant_key"])
            character_id = str(job["character_id"])
            relative_output_path = str(job["relative_output_path"])
            abs_path = (Path(plan["output_dir"]).expanduser().resolve() / relative_output_path).resolve()
            review = _screening_for(screening, template_name=template_name, asset_id=asset_id)
            lines.append(f"### `{asset_id}`")
            lines.append("")
            lines.append(f"- `character_id`: `{character_id}`")
            lines.append(f"- `variant`: `{variant}`")
            lines.append(f"- `file`: `{abs_path}`")
            for field in review_field_order():
                lines.append(f"- `{field}`: `{review[field]}`")
            lines.append(f"- `initial_screening_note`: {review['initial_screening_note']}")
            lines.append("- `ui_agent_notes`: `pending`")
            lines.append("")
        template_payload = screening.get(template_name) or {}
        trio_summary = str(template_payload.get("trio_summary") or "pending")
        lines.append(f"- Trio summary: {trio_summary}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    content = build_review_sheet(args)
    output_path = Path(args.output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(json.dumps({"output_path": str(output_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.llm_gateway import build_gateway_core
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from tools.template_role_matrix_common import (
    TEMPLATE_ROLE_CATALOG,
    TemplateName,
    TemplateRoleDraftResponse,
    build_role_matrix_markdown,
    draft_template_roles,
    finalize_draft_entry,
    template_role_spec_by_name,
    write_json,
    write_text,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draft and finalize template-aligned roster cast packs with the author LLM.")
    parser.add_argument("--template", action="append", dest="templates")
    parser.add_argument("--output-dir", default="artifacts/portraits/cast_content")
    parser.add_argument("--drafts-path")
    parser.add_argument("--json-path")
    parser.add_argument("--matrix-path")
    parser.add_argument("--skip-live-draft", action="store_true")
    parser.add_argument("--seed-drafts-path")
    parser.add_argument("--skip-existing-drafts", action="store_true")
    return parser.parse_args(argv)


def _selected_templates(args: argparse.Namespace) -> tuple[TemplateName, ...]:
    if not args.templates:
        return tuple(spec.template_name for spec in TEMPLATE_ROLE_CATALOG)
    return tuple(str(item) for item in args.templates)  # type: ignore[return-value]


def _load_seed_drafts(path: str | Path) -> dict[str, TemplateRoleDraftResponse]:
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("seed drafts payload must be a JSON object")
    drafts: dict[str, TemplateRoleDraftResponse] = {}
    for template_name, item in payload.items():
        drafts[str(template_name)] = TemplateRoleDraftResponse.model_validate(item)
    return drafts


def _build_final_entries(
    drafts: dict[str, TemplateRoleDraftResponse],
    template_names: tuple[TemplateName, ...],
) -> tuple[list[dict[str, Any]], dict[TemplateName, list[dict[str, Any]]]]:
    final_entries: list[dict[str, Any]] = []
    entries_by_template: dict[TemplateName, list[dict[str, Any]]] = {}
    seen_character_ids: set[str] = set()
    for template_name in template_names:
        spec = template_role_spec_by_name(template_name)
        draft = drafts[template_name]
        template_entries: list[dict[str, Any]] = []
        for index, (slot, role) in enumerate(zip(spec.slots, draft.roles, strict=True), start=1):
            payload = finalize_draft_entry(
                spec=spec,
                slot=slot,
                role_index=index,
                draft=role,
            )
            if payload["character_id"] in seen_character_ids:
                payload["character_id"] = f"{payload['character_id']}_{index}"
                payload["slug"] = f"{payload['slug']}-{index}"
            CharacterRosterSourceEntry.from_payload(payload)
            seen_character_ids.add(payload["character_id"])
            template_entries.append(payload)
            final_entries.append(payload)
        entries_by_template[template_name] = template_entries
    return final_entries, entries_by_template


def _quality_summary(final_entries: list[dict[str, Any]]) -> dict[str, Any]:
    slot_counts = Counter()
    for item in final_entries:
        slot_counts.update(item["slot_tags"])
    return {
        "entry_count": len(final_entries),
        "slot_tag_distribution": dict(slot_counts),
    }


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir).expanduser().resolve()
    template_names = _selected_templates(args)
    drafts_path = Path(args.drafts_path).expanduser().resolve() if args.drafts_path else output_dir / "template_role_drafts_v2.json"
    json_path = Path(args.json_path).expanduser().resolve() if args.json_path else output_dir / "template_aligned_cast_pack_30_v2.json"
    matrix_path = Path(args.matrix_path).expanduser().resolve() if args.matrix_path else output_dir / "template_role_matrix.md"
    if args.seed_drafts_path:
        drafts = _load_seed_drafts(args.seed_drafts_path)
    else:
        drafts = {}
    if not args.skip_live_draft:
        gateway = build_gateway_core()
        for template_name in template_names:
            if args.skip_existing_drafts and template_name in drafts:
                continue
            spec = template_role_spec_by_name(template_name)
            drafts[template_name] = draft_template_roles(gateway, spec)
            write_json(
                drafts_path,
                {key: value.model_dump(mode="json") for key, value in drafts.items()},
            )
    missing_templates = [template_name for template_name in template_names if template_name not in drafts]
    if missing_templates:
        raise RuntimeError(f"missing drafts for templates: {', '.join(missing_templates)}")
    write_json(
        drafts_path,
        {template_name: drafts[template_name].model_dump(mode="json") for template_name in template_names},
    )
    final_entries, entries_by_template = _build_final_entries(drafts, template_names)
    matrix_markdown = build_role_matrix_markdown(
        specs=tuple(template_role_spec_by_name(template_name) for template_name in template_names),
        final_entries_by_template=entries_by_template,
    )
    write_json(json_path, final_entries)
    write_text(matrix_path, matrix_markdown)
    return {
        "drafts_path": str(drafts_path),
        "json_path": str(json_path),
        "matrix_path": str(matrix_path),
        "quality": _quality_summary(final_entries),
    }


def main(argv: list[str] | None = None) -> int:
    payload = run_build(parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from tools.template_role_matrix_build import run_build
from tools.template_role_matrix_common import (
    TEMPLATE_ROLE_CATALOG,
    TemplateRoleDraftEntry,
    TemplateRoleDraftResponse,
    build_template_role_prompt,
    write_json,
)


def _draft_response_for_spec(spec, index_offset: int = 0) -> TemplateRoleDraftResponse:  # noqa: ANN001
    roles = []
    for idx, slot in enumerate(spec.slots, start=1):
        ordinal = idx + index_offset
        roles.append(
            TemplateRoleDraftEntry(
                provisional_role=f"{slot.function}_{ordinal}",
                name_en=f"{spec.template_name.replace('_story', '').title().replace('_', ' ')} Role {ordinal}",
                name_zh=f"{spec.template_name.replace('_story', '')}角色{ordinal}",
                public_summary_en=f"Distinct summary for {spec.template_name} role {ordinal}.",
                public_summary_zh=f"{spec.template_name} 角色 {ordinal} 的中文摘要。",
                role_hint_en=f"{slot.function.title()} Specialist {ordinal}",
                role_hint_zh=f"{slot.function}专员{ordinal}",
                agenda_seed_en=f"Agenda {ordinal} for {spec.template_name}.",
                agenda_seed_zh=f"{spec.template_name} 的议程 {ordinal}。",
                red_line_seed_en=f"Red line {ordinal} for {spec.template_name}.",
                red_line_seed_zh=f"{spec.template_name} 的底线 {ordinal}。",
                pressure_signature_seed_en=f"Pressure signature {ordinal} for {spec.template_name}.",
                pressure_signature_seed_zh=f"{spec.template_name} 的压力表达 {ordinal}。",
                visual_anchor=f"{slot.visual_anchor} {ordinal}",
                silhouette_note=f"{slot.silhouette_anchor} {ordinal}",
                avoid_overlap_with_other_two=slot.avoid_overlap,
            )
        )
    return TemplateRoleDraftResponse(template_name=spec.template_name, roles=roles)


def test_template_role_prompt_mentions_style_lock_and_internal_difference() -> None:
    prompt = build_template_role_prompt(TEMPLATE_ROLE_CATALOG[0])

    assert "semi-realistic editorial civic-fantasy dossier portrait" in prompt
    assert "safe for 4:5 cover crop across author/detail/current play" in prompt
    assert "modern corporate office staging" in prompt
    assert "Each role must be internally distinct in function, pressure style, and visual silhouette." in prompt
    assert "You must provide bilingual fields for every role" in prompt


def test_run_build_can_finalize_seed_drafts_into_v2_pack(tmp_path) -> None:
    seed_payload = {
        spec.template_name: _draft_response_for_spec(spec, index_offset=index * 3).model_dump(mode="json")
        for index, spec in enumerate(TEMPLATE_ROLE_CATALOG)
    }
    seed_path = tmp_path / "seed_drafts.json"
    write_json(seed_path, seed_payload)

    payload = run_build(
        SimpleNamespace(
            templates=None,
            output_dir=str(tmp_path / "out"),
            drafts_path=None,
            json_path=None,
            matrix_path=None,
            skip_live_draft=True,
            seed_drafts_path=str(seed_path),
        )
    )

    final_json_path = Path(payload["json_path"])
    matrix_path = Path(payload["matrix_path"])
    entries = json.loads(final_json_path.read_text(encoding="utf-8"))

    assert len(entries) == 30
    assert matrix_path.exists()
    assert "## `blackout_referendum_story`" in matrix_path.read_text(encoding="utf-8")
    assert payload["quality"]["entry_count"] == 30
    for entry in entries:
        CharacterRosterSourceEntry.from_payload(entry)
    assert len({entry["character_id"] for entry in entries}) == 30

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from tools.template_role_matrix_common import TEMPLATE_ROLE_CATALOG


def default_template_trials_root() -> Path:
    return Path("artifacts/portraits/template_trials").resolve()


def load_template_cast_pack(path: str | Path) -> list[dict[str, Any]]:
    return list(json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8")))


def load_screening(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return dict(json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8")))


def iter_screening_asset_reviews(screening: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for template_name, template_payload in screening.items():
        if not isinstance(template_payload, dict):
            continue
        for asset_id, asset_payload in template_payload.items():
            if asset_id == "trio_summary" or not isinstance(asset_payload, dict):
                continue
            yield str(template_name), str(asset_id), asset_payload


def keep_asset_ids_from_screening(screening: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        asset_id
        for _template_name, asset_id, asset_payload in iter_screening_asset_reviews(screening)
        if str(asset_payload.get("overall_recommendation") or "") == "keep"
    )


def template_character_map(
    *,
    cast_pack_path: str | Path,
) -> dict[str, list[dict[str, Any]]]:
    entries = load_template_cast_pack(cast_pack_path)
    mapping: dict[str, list[dict[str, Any]]] = {}
    for index, spec in enumerate(TEMPLATE_ROLE_CATALOG):
        mapping[spec.template_name] = entries[index * 3 : (index + 1) * 3]
    return mapping


def review_field_order() -> tuple[str, ...]:
    return (
        "template_fit",
        "role_distinctness",
        "silhouette_readability",
        "face_crop_safety",
        "style_lock_match",
        "expression_match",
        "overall_recommendation",
    )

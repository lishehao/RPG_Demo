from __future__ import annotations

import json

import pytest

from rpg_backend.roster.admin import validate_source_catalog
from rpg_backend.roster.contracts import CharacterRosterCatalogError


def _source_entry(**overrides):
    payload = {
        "character_id": "roster_json_test",
        "slug": "json-test",
        "name_en": "Json Test",
        "name_zh": "测试角色",
        "portrait_url": None,
        "public_summary_en": "Loaded from JSON.",
        "public_summary_zh": "从 JSON 载入。",
        "role_hint_en": "Clerk",
        "role_hint_zh": "文员",
        "agenda_seed_en": "Keeps records visible.",
        "agenda_seed_zh": "让记录保持可见。",
        "red_line_seed_en": "Will not hide the file.",
        "red_line_seed_zh": "不会把档案藏起来。",
        "pressure_signature_seed_en": "Turns every missing stamp into a public problem.",
        "pressure_signature_seed_zh": "把每一个缺失印记都变成公共问题。",
        "gender_lock": "unspecified",
        "personality_core_en": "Calm in public, exacting under pressure, and difficult to stampede once procedure matters.",
        "personality_core_zh": "公开场合冷静，压力上来时会更苛刻，一旦程序变重要就很难被裹挟。",
        "experience_anchor_en": "A records-facing civic worker known for staying with the file after everyone else wants a faster story.",
        "experience_anchor_zh": "一名长期面向记录工作的公共人员，别人想更快翻页时，仍会留下来把档案看完。",
        "identity_lock_notes_en": "Keep the same person, the same face, and the same public identity. Do not rename or rewrite them into a different person.",
        "identity_lock_notes_zh": "必须保持同一个人、同一张脸和同一公共身份。不得改名，也不得改写成另一个人。",
        "theme_tags": ["truth_record_crisis"],
        "setting_tags": ["archive"],
        "tone_tags": ["procedural"],
        "conflict_tags": ["public_record"],
        "slot_tags": ["guardian"],
        "retrieval_terms": ["archive", "record"],
        "rarity_weight": 1.0,
    }
    payload.update(overrides)
    return payload


def test_validate_source_catalog_accepts_valid_entry_with_null_portrait(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps([_source_entry()], ensure_ascii=False), encoding="utf-8")

    entries = validate_source_catalog(path)

    assert len(entries) == 1
    assert entries[0].portrait_url is None
    assert entries[0].gender_lock == "unspecified"


def test_validate_source_catalog_accepts_complete_portrait_variants(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    portrait_payload = _source_entry(
        portrait_url="http://127.0.0.1:8000/portraits/roster/roster_json_test__neutral.png",
        portrait_variants={
            "positive": "http://127.0.0.1:8000/portraits/roster/roster_json_test__positive.png",
            "neutral": "http://127.0.0.1:8000/portraits/roster/roster_json_test__neutral.png",
            "negative": "http://127.0.0.1:8000/portraits/roster/roster_json_test__negative.png",
        },
    )
    path.write_text(json.dumps([portrait_payload], ensure_ascii=False), encoding="utf-8")

    entries = validate_source_catalog(path)

    assert entries[0].portrait_variants is not None
    assert entries[0].portrait_variants["neutral"] == entries[0].portrait_url


def test_validate_source_catalog_rejects_duplicate_character_id(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps([_source_entry(), _source_entry(slug="other-slug")], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(CharacterRosterCatalogError, match="duplicate roster character_id"):
        validate_source_catalog(path)


def test_validate_source_catalog_rejects_template_profile_without_gender_lock(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    payload = _source_entry()
    payload.pop("gender_lock", None)
    path.write_text(json.dumps([payload], ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CharacterRosterCatalogError, match="template profile requires gender_lock"):
        validate_source_catalog(path)


def test_validate_source_catalog_rejects_blank_localized_field(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps([_source_entry(name_zh="")], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(CharacterRosterCatalogError, match="name_zh"):
        validate_source_catalog(path)


def test_validate_source_catalog_rejects_incomplete_portrait_variants(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            [
                _source_entry(
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_json_test__neutral.png",
                    portrait_variants={
                        "positive": "http://127.0.0.1:8000/portraits/roster/roster_json_test__positive.png",
                        "neutral": "http://127.0.0.1:8000/portraits/roster/roster_json_test__neutral.png",
                    },
                )
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CharacterRosterCatalogError, match="portrait_variants"):
        validate_source_catalog(path)


def test_validate_source_catalog_rejects_partial_template_profile(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps([_source_entry(identity_lock_notes_zh="")], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(CharacterRosterCatalogError, match="template profile"):
        validate_source_catalog(path)

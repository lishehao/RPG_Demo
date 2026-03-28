from __future__ import annotations

import json

import pytest

from rpg_backend.config import Settings
from rpg_backend.main import build_runtime_services
from rpg_backend.roster.admin import build_runtime_catalog, validate_source_catalog, write_runtime_catalog
from rpg_backend.roster.contracts import CharacterRosterCatalogError


def _write_source_catalog(path) -> None:  # noqa: ANN001
    path.write_text(
        json.dumps(
            [
                {
                    "character_id": "roster_startup",
                    "slug": "startup",
                    "name_en": "Startup",
                    "name_zh": "启动者",
                    "portrait_url": None,
                    "public_summary_en": "A startup fixture.",
                    "public_summary_zh": "一个启动测试角色。",
                    "role_hint_en": "Clerk",
                    "role_hint_zh": "文员",
                    "agenda_seed_en": "Keeps the room ordered.",
                    "agenda_seed_zh": "让场面维持秩序。",
                    "red_line_seed_en": "Will not hide the file.",
                    "red_line_seed_zh": "不会把档案藏起来。",
                    "pressure_signature_seed_en": "Turns each missing signature into pressure.",
                    "pressure_signature_seed_zh": "会把每一次缺签都变成压力。",
                    "theme_tags": ["truth_record_crisis"],
                    "setting_tags": ["archive"],
                    "tone_tags": ["procedural"],
                    "conflict_tags": ["public_record"],
                    "slot_tags": ["guardian"],
                    "retrieval_terms": ["archive", "record"],
                    "rarity_weight": 1.0,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _settings(tmp_path, **overrides) -> Settings:
    source_path = tmp_path / "catalog.json"
    runtime_path = tmp_path / "runtime.json"
    _write_source_catalog(source_path)
    payload = {
        "story_library_db_path": str(tmp_path / "story.sqlite3"),
        "runtime_state_db_path": str(tmp_path / "runtime.sqlite3"),
        "roster_enabled": True,
        "character_knowledge_enabled": False,
        "character_knowledge_database_url": None,
        "roster_source_catalog_path": str(source_path),
        "roster_runtime_catalog_path": str(runtime_path),
    }
    payload.update(overrides)
    return Settings(**payload)


def test_build_runtime_services_fails_when_roster_enabled_and_runtime_missing(tmp_path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(CharacterRosterCatalogError, match="runtime catalog not found"):
        build_runtime_services(settings)


def test_build_runtime_services_succeeds_when_roster_disabled_and_runtime_missing(tmp_path) -> None:
    settings = _settings(tmp_path, roster_enabled=False)

    services = build_runtime_services(settings)

    assert services.author_job_service is not None


def test_build_runtime_services_succeeds_with_knowledge_backend_and_runtime_missing(tmp_path) -> None:
    settings = _settings(
        tmp_path,
        character_knowledge_enabled=True,
        character_knowledge_database_url="postgresql://postgres:postgres@127.0.0.1:5432/rpg_demo",
    )

    services = build_runtime_services(settings)

    assert services.author_job_service is not None


def test_build_runtime_services_fails_when_runtime_catalog_is_invalid(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text(json.dumps({"catalog_version": "bad"}), encoding="utf-8")

    with pytest.raises(CharacterRosterCatalogError):
        build_runtime_services(settings)


def test_build_runtime_services_succeeds_with_valid_runtime_catalog(tmp_path) -> None:
    settings = _settings(tmp_path)
    source_entries = validate_source_catalog(settings.roster_source_catalog_path)
    runtime_catalog = build_runtime_catalog(source_entries)
    write_runtime_catalog(settings.roster_runtime_catalog_path, runtime_catalog)

    services = build_runtime_services(settings)

    assert services.story_library_service is not None

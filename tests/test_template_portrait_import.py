from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rpg_backend.roster.admin import build_runtime_catalog, validate_source_catalog, write_runtime_catalog
from rpg_backend.roster.loader import load_character_roster_runtime_catalog, load_character_roster_source_catalog
from rpg_backend.roster.portrait_registry import PortraitAssetRecord, SQLitePortraitRegistry
from tools.template_portrait_import import run_import


class _StubEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        del text
        return [0.1, 0.2, 0.3]


def _source_payload(character_id: str, *, slot_tag: str = "guardian") -> dict[str, object]:
    slug = character_id.replace("roster_", "").replace("_", "-")
    name_base = slug.replace("-", " ").title()
    return {
        "character_id": character_id,
        "slug": slug,
        "name_en": name_base,
        "name_zh": f"{name_base}中文",
        "portrait_url": None,
        "default_portrait_url": None,
        "portrait_variants": None,
        "public_summary_en": f"{name_base} carries public pressure.",
        "public_summary_zh": f"{name_base} 承担公共压力。",
        "role_hint_en": f"{name_base} role",
        "role_hint_zh": f"{name_base} 角色",
        "agenda_seed_en": f"{name_base} keeps the process visible.",
        "agenda_seed_zh": f"{name_base} 让流程保持可见。",
        "red_line_seed_en": f"{name_base} will not erase the record.",
        "red_line_seed_zh": f"{name_base} 不会抹掉记录。",
        "pressure_signature_seed_en": f"{name_base} turns delay into civic pressure.",
        "pressure_signature_seed_zh": f"{name_base} 会把拖延变成公共压力。",
        "theme_tags": ["truth_record_crisis"],
        "setting_tags": ["archive"],
        "tone_tags": ["procedural"],
        "conflict_tags": ["public_record"],
        "slot_tags": [slot_tag],
        "retrieval_terms": ["archive", "record", slug],
        "rarity_weight": 1.0,
    }


def _write_source_and_runtime(path: Path, payloads: list[dict[str, object]], runtime_path: Path) -> None:
    path.write_text(json.dumps(payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    entries = validate_source_catalog(path)
    write_runtime_catalog(runtime_path, build_runtime_catalog(entries))


def _create_asset(
    registry: SQLitePortraitRegistry,
    *,
    root: Path,
    character_id: str,
    variant_key: str,
    asset_id: str,
    status: str = "generated",
    candidate_index: int = 1,
    create_file: bool = True,
) -> PortraitAssetRecord:
    file_path = root / "trials" / character_id / variant_key / f"{asset_id}.png"
    if create_file:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"\x89PNG\r\n\x1a\nportrait")
    record = PortraitAssetRecord(
        asset_id=asset_id,
        character_id=character_id,
        variant_key=variant_key,  # type: ignore[arg-type]
        candidate_index=candidate_index,
        status=status,  # type: ignore[arg-type]
        file_path=str(file_path),
        public_url=(
            f"http://127.0.0.1:8000/portraits/roster/{character_id}/{variant_key}/current.png"
            if status == "published"
            else None
        ),
        prompt_version="v1_editorial_dossier",
        prompt_hash=f"hash_{asset_id}",
        image_model="gemini-3.1-flash-image-preview",
        image_api_base_url="https://vip.123everything.com",
        generated_at="2026-03-25T00:00:00+00:00",
        published_at="2026-03-25T00:05:00+00:00" if status == "published" else None,
    )
    registry.save_asset(record)
    return record


def _screening_payload(asset_ids: list[str], *, recommendation: str = "keep") -> dict[str, object]:
    payload: dict[str, object] = {"trio_summary": "All portraits read consistently."}
    for asset_id in asset_ids:
        payload[asset_id] = {
            "template_fit": "pass",
            "role_distinctness": "pass",
            "silhouette_readability": "pass",
            "face_crop_safety": "pass",
            "style_lock_match": "pass",
            "expression_match": "pass",
            "overall_recommendation": recommendation,
            "initial_screening_note": "Ready for import.",
        }
    return {"archive_vote_story": payload}


def test_template_portrait_import_replaces_catalog_and_publishes_selected_assets(monkeypatch, tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    runtime_path = tmp_path / "runtime.json"
    output_dir = tmp_path / "roster"
    registry_db_path = tmp_path / "portrait_manifest.sqlite3"
    backup_dir = tmp_path / "backup"
    cast_pack_path = tmp_path / "cast_pack.json"
    screening_path = tmp_path / "screening.json"

    old_payloads = [
        _source_payload("legacy_old"),
        _source_payload("legacy_keeper", slot_tag="witness"),
    ]
    _write_source_and_runtime(catalog_path, old_payloads, runtime_path)
    old_current = output_dir / "legacy_old" / "neutral" / "current.png"
    old_current.parent.mkdir(parents=True, exist_ok=True)
    old_current.write_bytes(b"\x89PNG\r\n\x1a\nold")

    cast_pack_payloads = [
        _source_payload("roster_new_certifier"),
        _source_payload("roster_new_witness", slot_tag="witness"),
        _source_payload("roster_new_broker", slot_tag="broker"),
    ]
    cast_pack_path.write_text(json.dumps(cast_pack_payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = SQLitePortraitRegistry(registry_db_path)
    legacy_asset = _create_asset(
        registry,
        root=tmp_path,
        character_id="legacy_old",
        variant_key="neutral",
        asset_id="legacy_old_neutral",
        status="published",
    )
    asset_ids: list[str] = []
    for character_id in ("roster_new_certifier", "roster_new_witness", "roster_new_broker"):
        for variant_key in ("negative", "neutral", "positive"):
            asset_id = f"{character_id}_{variant_key}"
            _create_asset(
                registry,
                root=tmp_path,
                character_id=character_id,
                variant_key=variant_key,
                asset_id=asset_id,
                status="generated",
            )
            asset_ids.append(asset_id)
    screening_path.write_text(
        json.dumps(_screening_payload(asset_ids), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "tools.template_portrait_import.build_character_embedding_provider",
        lambda settings: _StubEmbeddingProvider(),
    )

    payload = run_import(
        SimpleNamespace(
            cast_pack_path=str(cast_pack_path),
            screening_json=str(screening_path),
            registry_db_path=str(registry_db_path),
            catalog_path=str(catalog_path),
            runtime_path=str(runtime_path),
            output_dir=str(output_dir),
            local_portrait_base_url="http://127.0.0.1:8000",
            backup_dir=str(backup_dir),
            import_mode="replace",
        )
    )

    reloaded_source = load_character_roster_source_catalog(catalog_path)
    reloaded_runtime = load_character_roster_runtime_catalog(runtime_path)
    published_records = registry.list_assets(status="published")
    archived_legacy = registry.get_asset(legacy_asset.asset_id)

    assert payload["old_catalog_entry_count"] == 2
    assert payload["new_catalog_entry_count"] == 3
    assert len(payload["selected_asset_ids"]) == 9
    assert len(reloaded_source) == 3
    assert reloaded_runtime.entry_count == 3
    assert {entry.character_id for entry in reloaded_source} == {
        "roster_new_certifier",
        "roster_new_witness",
        "roster_new_broker",
    }
    assert all(entry.portrait_url == entry.default_portrait_url for entry in reloaded_source)
    assert all(entry.portrait_variants and set(entry.portrait_variants.keys()) == {"negative", "neutral", "positive"} for entry in reloaded_source)
    assert len(published_records) == 9
    assert archived_legacy is not None and archived_legacy.status == "archived"
    assert (backup_dir / "catalog.json").exists()
    assert (backup_dir / "character_roster_runtime.json").exists()
    assert (backup_dir / "roster" / "legacy_old" / "neutral" / "current.png").exists()
    assert (backup_dir / "import_manifest.json").exists()
    assert not (output_dir / "legacy_old").exists()
    assert (output_dir / "roster_new_certifier" / "neutral" / "current.png").exists()
    assert (output_dir / "roster_new_witness" / "positive" / "current.png").exists()


def test_template_portrait_import_rejects_non_keep_screening_assets(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    runtime_path = tmp_path / "runtime.json"
    cast_pack_path = tmp_path / "cast_pack.json"
    screening_path = tmp_path / "screening.json"
    registry_db_path = tmp_path / "portrait_manifest.sqlite3"

    _write_source_and_runtime(catalog_path, [_source_payload("legacy_old")], runtime_path)
    cast_pack_payloads = [_source_payload("roster_new_certifier")]
    cast_pack_path.write_text(json.dumps(cast_pack_payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    screening_path.write_text(
        json.dumps(_screening_payload(["roster_new_certifier_neutral"], recommendation="needs_ui_review_attention"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SQLitePortraitRegistry(registry_db_path)

    with pytest.raises(RuntimeError, match="non-keep assets"):
        run_import(
            SimpleNamespace(
                cast_pack_path=str(cast_pack_path),
                screening_json=str(screening_path),
                registry_db_path=str(registry_db_path),
                catalog_path=str(catalog_path),
                runtime_path=str(runtime_path),
                output_dir=str(tmp_path / "roster"),
                local_portrait_base_url="http://127.0.0.1:8000",
                backup_dir=str(tmp_path / "backup"),
                import_mode="replace",
            )
        )


def test_template_portrait_import_rejects_missing_variant_coverage(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    runtime_path = tmp_path / "runtime.json"
    cast_pack_path = tmp_path / "cast_pack.json"
    screening_path = tmp_path / "screening.json"
    registry_db_path = tmp_path / "portrait_manifest.sqlite3"

    _write_source_and_runtime(catalog_path, [_source_payload("legacy_old")], runtime_path)
    cast_pack_payloads = [_source_payload("roster_new_certifier")]
    cast_pack_path.write_text(json.dumps(cast_pack_payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = SQLitePortraitRegistry(registry_db_path)
    asset_ids: list[str] = []
    for variant_key in ("negative", "neutral"):
        asset_id = f"roster_new_certifier_{variant_key}"
        _create_asset(
            registry,
            root=tmp_path,
            character_id="roster_new_certifier",
            variant_key=variant_key,
            asset_id=asset_id,
        )
        asset_ids.append(asset_id)
    screening_path.write_text(
        json.dumps(_screening_payload(asset_ids), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="do not fully cover"):
        run_import(
            SimpleNamespace(
                cast_pack_path=str(cast_pack_path),
                screening_json=str(screening_path),
                registry_db_path=str(registry_db_path),
                catalog_path=str(catalog_path),
                runtime_path=str(runtime_path),
                output_dir=str(tmp_path / "roster"),
                local_portrait_base_url="http://127.0.0.1:8000",
                backup_dir=str(tmp_path / "backup"),
                import_mode="replace",
            )
        )


def test_template_portrait_import_rejects_assets_outside_cast_pack(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    runtime_path = tmp_path / "runtime.json"
    cast_pack_path = tmp_path / "cast_pack.json"
    screening_path = tmp_path / "screening.json"
    registry_db_path = tmp_path / "portrait_manifest.sqlite3"

    _write_source_and_runtime(catalog_path, [_source_payload("legacy_old")], runtime_path)
    cast_pack_payloads = [_source_payload("roster_new_certifier")]
    cast_pack_path.write_text(json.dumps(cast_pack_payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = SQLitePortraitRegistry(registry_db_path)
    _create_asset(
        registry,
        root=tmp_path,
        character_id="legacy_old",
        variant_key="neutral",
        asset_id="legacy_old_neutral",
    )
    screening_path.write_text(
        json.dumps(_screening_payload(["legacy_old_neutral"]), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unexpected character"):
        run_import(
            SimpleNamespace(
                cast_pack_path=str(cast_pack_path),
                screening_json=str(screening_path),
                registry_db_path=str(registry_db_path),
                catalog_path=str(catalog_path),
                runtime_path=str(runtime_path),
                output_dir=str(tmp_path / "roster"),
                local_portrait_base_url="http://127.0.0.1:8000",
                backup_dir=str(tmp_path / "backup"),
                import_mode="replace",
            )
        )


def test_template_portrait_import_rejects_missing_registry_files(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    runtime_path = tmp_path / "runtime.json"
    cast_pack_path = tmp_path / "cast_pack.json"
    screening_path = tmp_path / "screening.json"
    registry_db_path = tmp_path / "portrait_manifest.sqlite3"

    _write_source_and_runtime(catalog_path, [_source_payload("legacy_old")], runtime_path)
    cast_pack_payloads = [_source_payload("roster_new_certifier")]
    cast_pack_path.write_text(json.dumps(cast_pack_payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = SQLitePortraitRegistry(registry_db_path)
    asset_ids: list[str] = []
    for variant_key in ("negative", "neutral", "positive"):
        asset_id = f"roster_new_certifier_{variant_key}"
        _create_asset(
            registry,
            root=tmp_path,
            character_id="roster_new_certifier",
            variant_key=variant_key,
            asset_id=asset_id,
            create_file=variant_key != "positive",
        )
        asset_ids.append(asset_id)
    screening_path.write_text(
        json.dumps(_screening_payload(asset_ids), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="file missing on disk"):
        run_import(
            SimpleNamespace(
                cast_pack_path=str(cast_pack_path),
                screening_json=str(screening_path),
                registry_db_path=str(registry_db_path),
                catalog_path=str(catalog_path),
                runtime_path=str(runtime_path),
                output_dir=str(tmp_path / "roster"),
                local_portrait_base_url="http://127.0.0.1:8000",
                backup_dir=str(tmp_path / "backup"),
                import_mode="replace",
            )
        )

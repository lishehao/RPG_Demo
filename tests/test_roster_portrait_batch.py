from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from rpg_backend.config import Settings
from rpg_backend.main import create_app
from rpg_backend.roster.admin import build_runtime_catalog, write_runtime_catalog
from rpg_backend.roster.loader import load_character_roster_runtime_catalog, load_character_roster_source_catalog
from rpg_backend.roster.portrait_registry import PortraitAssetRecord, SQLitePortraitRegistry
from tools import roster_portrait_batch, roster_portrait_plan


class _StubEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        del text
        return [0.1, 0.2, 0.3]


def _copy_catalog_subset(tmp_path: Path) -> tuple[Path, Path]:
    source_path = tmp_path / "catalog.json"
    runtime_path = tmp_path / "runtime.json"
    source_entries = tuple(
        entry
        for entry in load_character_roster_source_catalog(
            "/Users/lishehao/Desktop/Project/RPG_Demo/data/character_roster/catalog.json"
        )
        if entry.character_id in set(roster_portrait_batch.DEFAULT_CHARACTER_IDS)
    )
    source_path.write_text(
        json.dumps([entry.to_payload() for entry in source_entries], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_runtime_catalog(runtime_path, build_runtime_catalog(source_entries))
    return source_path, runtime_path


def test_build_image_request_payload_uses_square_512_text_only() -> None:
    payload = roster_portrait_batch.build_image_request_payload("Portrait prompt")

    assert payload["contents"][0]["parts"] == [{"text": "Portrait prompt"}]
    assert payload["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
    assert payload["generationConfig"]["imageConfig"]["aspectRatio"] == "1:1"
    assert payload["generationConfig"]["imageConfig"]["imageSize"] == "512"


def test_build_image_request_payload_can_attach_reference_image() -> None:
    payload = roster_portrait_batch.build_image_request_payload(
        "Portrait prompt",
        reference_image_bytes=b"\x89PNG\r\n\x1a\nref",
        reference_mime_type="image/png",
    )

    assert payload["contents"][0]["parts"][0] == {"text": "Portrait prompt"}
    assert payload["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/png"
    assert payload["contents"][0]["parts"][1]["inline_data"]["data"]


def test_extract_image_part_supports_inline_data_and_inlineData() -> None:
    png_bytes = b"\x89PNG\r\n\x1a\nfake"
    encoded = base64.b64encode(png_bytes).decode("utf-8")

    image_bytes_a, mime_a = roster_portrait_batch.extract_image_part(
        {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": encoded}}]}}]}
    )
    image_bytes_b, mime_b = roster_portrait_batch.extract_image_part(
        {"candidates": [{"content": {"parts": [{"inline_data": {"mime_type": "image/png", "data": encoded}}]}}]}
    )

    assert image_bytes_a == png_bytes
    assert mime_a == "image/png"
    assert image_bytes_b == png_bytes
    assert mime_b == "image/png"


def test_build_job_matrix_creates_character_variant_candidate_matrix(tmp_path) -> None:
    source_path, _runtime_path = _copy_catalog_subset(tmp_path)

    plan = roster_portrait_plan.build_job_matrix(
        catalog_path=source_path,
        character_ids=roster_portrait_batch.DEFAULT_CHARACTER_IDS,
        variants=("negative", "neutral", "positive"),
        candidates_per_variant=2,
        prompt_version="v1_editorial_dossier",
        image_model="gemini-3.1-flash-image-preview",
        image_api_base_url="https://vip.123everything.com",
        output_dir=tmp_path / "portraits",
        batch_id="portrait_test_batch",
    )

    assert plan.batch_id == "portrait_test_batch"
    assert len(plan.jobs) == 18
    assert {job.variant_key for job in plan.jobs} == {"negative", "neutral", "positive"}
    assert {job.candidate_index for job in plan.jobs} == {1, 2}
    assert all(job.relative_output_path.endswith(f"{job.asset_id}.png") for job in plan.jobs)
    first_three = plan.jobs[:3]
    assert [job.variant_key for job in first_three] == ["neutral", "negative", "positive"]
    assert first_three[0].reference_relative_output_path is None
    assert first_three[1].reference_relative_output_path == "roster_archive_certifier/neutral/reference_1.png"
    assert first_three[2].reference_relative_output_path == "roster_archive_certifier/neutral/reference_1.png"


def test_portrait_registry_round_trip_and_publish_archives_previous(tmp_path) -> None:
    registry = SQLitePortraitRegistry(tmp_path / "portrait_manifest.sqlite3")
    first = PortraitAssetRecord(
        asset_id="asset_a",
        character_id="roster_archive_certifier",
        variant_key="neutral",
        candidate_index=1,
        status="approved",
        file_path=str(tmp_path / "a.png"),
        public_url=None,
        prompt_version="v1",
        prompt_hash="hash_a",
        image_model="model",
        image_api_base_url="https://example.com",
        generated_at="2026-03-25T00:00:00+00:00",
    )
    second = PortraitAssetRecord(
        asset_id="asset_b",
        character_id="roster_archive_certifier",
        variant_key="neutral",
        candidate_index=2,
        status="published",
        file_path=str(tmp_path / "b.png"),
        public_url="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
        prompt_version="v1",
        prompt_hash="hash_b",
        image_model="model",
        image_api_base_url="https://example.com",
        generated_at="2026-03-25T00:00:01+00:00",
    )
    registry.save_asset(first)
    registry.save_asset(second)
    registry.mark_status("asset_a", status="published")
    registry.archive_other_published_assets(
        character_id="roster_archive_certifier",
        variant_key="neutral",
        keep_asset_id="asset_a",
    )

    kept = registry.get_asset("asset_a")
    archived = registry.get_asset("asset_b")

    assert kept is not None and kept.status == "published"
    assert archived is not None and archived.status == "archived"


def test_run_portrait_batch_generates_candidates_and_publishes_variants(monkeypatch, tmp_path) -> None:
    source_path, runtime_path = _copy_catalog_subset(tmp_path)
    output_dir = tmp_path / "portraits"
    registry_db_path = tmp_path / "portrait_manifest.sqlite3"

    monkeypatch.setattr(
        "tools.roster_portrait_generate.generate_portrait_image",
        lambda session, *, api_key, image_api_base_url, image_model, request_timeout_seconds, prompt_text, reference_image_bytes=None, reference_mime_type=None: (b"\x89PNG\r\n\x1a\nportrait", "image/png"),
    )
    monkeypatch.setattr(
        "tools.roster_portrait_ops.build_character_embedding_provider",
        lambda settings: _StubEmbeddingProvider(),
    )
    monkeypatch.setattr(
        roster_portrait_batch,
        "validate_three_cast_story",
        lambda config, *, target_character_ids: {"matched": True, "matched_supporting_cast_ids": list(target_character_ids)},
    )

    config = roster_portrait_batch.PortraitBatchConfig(
        api_key="test-key",
        backend_base_url="http://127.0.0.1:8000",
        image_api_base_url="https://vip.123everything.com",
        image_model="gemini-3.1-flash-image-preview",
        output_dir=output_dir,
        catalog_path=source_path,
        runtime_path=runtime_path,
        registry_db_path=registry_db_path,
        character_ids=roster_portrait_batch.DEFAULT_CHARACTER_IDS,
        variants=("negative", "neutral", "positive"),
        candidates_per_variant=2,
        request_timeout_seconds=30.0,
        local_portrait_base_url="http://127.0.0.1:8000",
        prompt_version="v1_editorial_dossier",
        skip_validation=False,
        batch_id="portrait_test_batch",
    )

    payload = roster_portrait_batch.run_portrait_batch(config)
    registry = SQLitePortraitRegistry(registry_db_path)
    reloaded_source = load_character_roster_source_catalog(source_path)
    reloaded_runtime = load_character_roster_runtime_catalog(runtime_path)

    assert payload["batch_id"] == "portrait_test_batch"
    assert len(payload["generated_files"]) == 18
    assert len(payload["published_assets"]) == 9
    assert payload["validation"]["matched"] is True
    assert len(registry.list_assets()) == 18
    assert len(registry.list_assets(status="published")) == 9
    assert all(entry.portrait_url == entry.default_portrait_url for entry in reloaded_source)
    assert all(entry.default_portrait_url for entry in reloaded_source)
    assert all(entry.portrait_variants and set(entry.portrait_variants.keys()) == {"negative", "neutral", "positive"} for entry in reloaded_source)
    assert all((output_dir / entry.character_id / "neutral" / "current.png").exists() for entry in reloaded_source)
    assert all(runtime_entry.default_portrait_url for runtime_entry in reloaded_runtime.entries)


def test_run_generation_uses_neutral_reference_for_non_neutral_variants(monkeypatch, tmp_path) -> None:
    source_path, _runtime_path = _copy_catalog_subset(tmp_path)
    plan = roster_portrait_plan.build_job_matrix(
        catalog_path=source_path,
        character_ids=("roster_archive_certifier",),
        variants=("negative", "neutral", "positive"),
        candidates_per_variant=1,
        prompt_version="v1_editorial_dossier",
        image_model="gemini-3.1-flash-image-preview",
        image_api_base_url="https://vip.123everything.com",
        output_dir=tmp_path / "portraits",
        batch_id="portrait_ref_batch",
    )
    plan_path = tmp_path / "portrait_plan.json"
    roster_portrait_batch.write_plan_file(plan_path, plan)
    captured: list[dict[str, object]] = []

    def fake_generate(session, *, api_key, image_api_base_url, image_model, request_timeout_seconds, prompt_text, reference_image_bytes=None, reference_mime_type=None):  # noqa: ANN001
        del session, api_key, image_api_base_url, image_model, request_timeout_seconds, prompt_text
        captured.append(
            {
                "reference_present": reference_image_bytes is not None,
                "reference_mime_type": reference_mime_type,
            }
        )
        return (b"\x89PNG\r\n\x1a\nportrait", "image/png")

    monkeypatch.setattr("tools.roster_portrait_generate.generate_portrait_image", fake_generate)
    payload = roster_portrait_batch.run_generation(
        type(
            "Args",
            (),
            {
                "plan_path": str(plan_path),
                "registry_db_path": str(tmp_path / "portrait_manifest.sqlite3"),
                "api_key": "test-key",
                "request_timeout_seconds": 30.0,
                "asset_ids": None,
            },
        )()
    )

    assert payload["generated_count"] == 3
    assert (tmp_path / "portraits" / "roster_archive_certifier" / "neutral" / "reference_1.png").exists()
    assert captured[0]["reference_present"] is False
    assert captured[1]["reference_present"] is True
    assert captured[2]["reference_present"] is True
    assert captured[1]["reference_mime_type"] == "image/png"


def test_roster_portrait_static_route_serves_nested_current_file_and_404s_missing(tmp_path) -> None:
    portrait_dir = tmp_path / "portraits" / "roster"
    existing_file = portrait_dir / "roster_archive_certifier" / "neutral" / "current.png"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_bytes(b"\x89PNG\r\n\x1a\nportrait")

    app = create_app(
        runtime_settings=Settings(
            local_portrait_dir=str(portrait_dir),
            roster_enabled=False,
        )
    )
    client = TestClient(app)

    found = client.get("/portraits/roster/roster_archive_certifier/neutral/current.png")
    missing = client.get("/portraits/roster/roster_missing/neutral/current.png")

    assert found.status_code == 200
    assert found.content.startswith(b"\x89PNG")
    assert missing.status_code == 404

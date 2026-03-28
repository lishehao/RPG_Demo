from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from rpg_backend.author.contracts import (
    AuthorCastPortraitArtDirection,
    AuthorCastPortraitPlanRequest,
    AuthorCastPortraitPlanResponse,
    AuthorCastPortraitSubject,
    AuthorCastPortraitTask,
    AuthorJobProgress,
)
from rpg_backend.author.jobs import AuthorJobService, _AuthorJobRecord
from rpg_backend.author.preview import build_author_story_summary
from rpg_backend.author.storage import SQLiteAuthorJobStorage
from rpg_backend.config import Settings
from rpg_backend.main import create_app
from rpg_backend.portraits.prompting import (
    PortraitPromptSubject,
    build_portrait_prompt,
    build_reference_locked_variant_prompt,
    prompt_hash,
)
from rpg_backend.roster.admin import build_runtime_catalog
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from rpg_backend.roster.service import CharacterRosterService
from tests.author_fixtures import author_fixture_bundle
from tests.test_author_product_api import _preview_response
from tools.author_cast_portrait_common import load_author_portrait_plan, write_author_portrait_plan
from tools.author_cast_portrait_generate import run_generation
from tools.author_cast_portrait_plan import run_plan
from tools.author_cast_portrait_validate import run_validation


class _StubEmbeddingProvider:
    def embed_text(self, text: str) -> list[float] | None:
        del text
        return None


def _roster_source_entry(**overrides) -> CharacterRosterSourceEntry:
    payload = {
        "character_id": "roster_archive_certifier",
        "slug": "archive-certifier",
        "name_en": "Lin Verrow",
        "name_zh": "林维若",
        "portrait_url": None,
        "public_summary_en": "A records certifier who treats broken custody chains as civic danger.",
        "public_summary_zh": "一名把保管链断裂视为公共危险的记录认证官。",
        "role_hint_en": "Records certifier",
        "role_hint_zh": "记录认证官",
        "agenda_seed_en": "Keep the chain of custody intact in public.",
        "agenda_seed_zh": "让保管链在公开程序里保持完整。",
        "red_line_seed_en": "Will not certify missing records.",
        "red_line_seed_zh": "不会为缺失记录背书。",
        "pressure_signature_seed_en": "Turns every missing stamp into procedural pressure.",
        "pressure_signature_seed_zh": "会把每一个缺失印记都变成程序压力。",
        "theme_tags": ["truth_record_crisis"],
        "setting_tags": ["archive", "hearing"],
        "tone_tags": ["tense", "procedural"],
        "conflict_tags": ["public_record", "witness"],
        "slot_tags": ["guardian", "anchor"],
        "retrieval_terms": ["archive", "record", "certify", "hearing"],
        "rarity_weight": 1.0,
    }
    payload.update(overrides)
    return CharacterRosterSourceEntry.from_payload(payload)


def _completed_author_service(tmp_path: Path) -> AuthorJobService:
    fixture = author_fixture_bundle()
    cast = list(fixture.design_bundle.story_bible.cast)
    cast[1] = cast[1].model_copy(
        update={
            "roster_character_id": "roster_archive_certifier",
            "roster_public_summary": "A records certifier trusted by no faction precisely because they have blocked all of them before.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": cast})}
    )
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    record = _AuthorJobRecord(
        job_id="job-portrait",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=_preview_response("seed"),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    service._save_record(record)
    return service


def _minimal_plan(tmp_path: Path) -> AuthorCastPortraitPlanResponse:
    output_dir = tmp_path / "author_jobs" / "job-portrait"
    return AuthorCastPortraitPlanResponse(
        job_id="job-portrait",
        revision="2026-03-25T00:00:00+00:00",
        language="en",
        batch_id="author_cast_job-portrait",
        prompt_version="v1_editorial_dossier",
        image_model="gemini-3.1-flash-image-preview",
        image_api_base_url="https://vip.123everything.com",
        output_dir=str(output_dir),
        art_direction=AuthorCastPortraitArtDirection(
            style_label="semi-realistic editorial civic-fantasy dossier portrait",
            generation_aspect_ratio="1:1",
            generation_resolution="512",
            display_ratios=["4:5 author/detail/play"],
            crop_guidance="center-safe readable face zone",
            style_lock="muted dossier style",
            negative_guidance="no glossy photo",
            ui_grade_notes="object-fit cover",
        ),
        subjects=[
            AuthorCastPortraitSubject(
                character_id="author_job-portrait_envoy_iri",
                source_kind="author_cast",
                source_ref="job-portrait:envoy_iri",
                npc_id="envoy_iri",
                roster_character_id=None,
                name="Envoy Iri",
                secondary_name=None,
                role="Envoy",
                public_summary=None,
                agenda="Hold the hearing together.",
                red_line="Will not bury the record.",
                pressure_signature="Turns every delay into public pressure.",
                story_title="Harbor Compact",
                story_premise="A public record is under threat.",
                story_tone="Tense civic fantasy",
                story_style_guard="Keep it civic.",
                world_rules=["Records matter.", "Hearing room pressure matters."],
                visual_tags=["truth_record_crisis", "archive", "tense"],
            )
        ],
        jobs=[
            AuthorCastPortraitTask(
                asset_id="asset_neutral",
                character_id="author_job-portrait_envoy_iri",
                npc_id="envoy_iri",
                variant_key="neutral",
                candidate_index=1,
                prompt_text="neutral prompt",
                prompt_hash=prompt_hash("neutral prompt"),
                relative_output_path="images/envoy_iri/neutral/asset_neutral.png",
            ),
            AuthorCastPortraitTask(
                asset_id="asset_positive",
                character_id="author_job-portrait_envoy_iri",
                npc_id="envoy_iri",
                variant_key="positive",
                candidate_index=1,
                prompt_text="positive prompt",
                prompt_hash=prompt_hash("positive prompt"),
                relative_output_path="images/envoy_iri/positive/asset_positive.png",
            ),
        ],
    )


def test_shared_portrait_prompt_includes_crop_safe_style_lock_and_negative_guidance() -> None:
    prompt = build_portrait_prompt(
        PortraitPromptSubject(
            character_id="author_job-portrait_envoy_iri",
            name_primary="Envoy Iri",
            name_secondary="伊里",
            role="Envoy",
            public_summary="A public envoy under archive pressure.",
            agenda="Hold the hearing together.",
            red_line="Will not bury the record.",
            pressure_signature="Turns every delay into public pressure.",
            story_title="Harbor Compact",
            story_premise="A public record is under threat.",
            story_tone="Tense civic fantasy",
            story_style_guard="Keep it civic.",
            world_rules=("Records matter.", "Hearings bind factions."),
            thematic_pressure=("truth_record_crisis",),
            setting_anchors=("archive hearing",),
            tonal_field=("tense",),
        ),
        variant_key="neutral",
    )

    assert "face fully readable within the center-safe zone" in prompt
    assert "safe for 4:5 cover crop across author, detail, and current play presentation" in prompt
    assert "Painterly editorial illustration" in prompt
    assert "Avoid glossy photography" in prompt
    assert "Avoid modern corporate office staging and generic business portrait setups." not in prompt
    assert "modern corporate office staging" in prompt
    assert "generic business portrait setups" in prompt
    assert "Variant overlay: neutral stance" in prompt


def test_reference_locked_variant_prompt_allows_background_and_clothing_change_while_locking_identity() -> None:
    prompt = build_reference_locked_variant_prompt("Base prompt.")

    assert "same character identity" in prompt
    assert "Preserve facial structure" in prompt
    assert "much more aggressively" in prompt
    assert "Make the expression and upper-body pose change more obvious" in prompt
    assert "Use outfit and background changes as major supporting cues" in prompt
    assert "the face and core identity must remain stable" in prompt


def test_author_service_can_build_portrait_plan_with_roster_enrich_and_subset(monkeypatch, tmp_path) -> None:
    service = _completed_author_service(tmp_path)
    roster_service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog((_roster_source_entry(),)).entries,
        embedding_provider=_StubEmbeddingProvider(),
        max_supporting_cast_selections=3,
    )
    monkeypatch.setattr("rpg_backend.author.portrait_tasks.get_character_roster_service", lambda: roster_service)

    plan = service.create_cast_portrait_plan(
        "job-portrait",
        AuthorCastPortraitPlanRequest(
            npc_ids=["archivist_sen", "broker_tal"],
            variants=["negative", "positive"],
            candidates_per_variant=1,
        ),
    )

    assert plan.output_dir.endswith("/artifacts/portraits/author_jobs/job-portrait")
    assert len(plan.subjects) == 2
    assert len(plan.jobs) == 4
    assert {subject.npc_id for subject in plan.subjects} == {"archivist_sen", "broker_tal"}
    assert next(subject for subject in plan.subjects if subject.npc_id == "archivist_sen").source_kind == "roster"
    assert all(job.relative_output_path.startswith("images/") for job in plan.jobs)
    assert all(job.npc_id in {"archivist_sen", "broker_tal"} for job in plan.jobs)
    assert "face fully readable within the center-safe zone" in plan.jobs[0].prompt_text


def test_author_cast_portrait_plan_script_writes_portrait_plan_json(monkeypatch, tmp_path) -> None:
    plan = _minimal_plan(tmp_path)

    class _FakeService:
        def create_cast_portrait_plan(self, job_id, request, actor_user_id=None):  # noqa: ANN001
            del request, actor_user_id
            return plan.model_copy(update={"job_id": job_id})

    monkeypatch.setattr("tools.author_cast_portrait_plan.AuthorJobService", lambda: _FakeService())

    payload = run_plan(
        SimpleNamespace(
            job_id="job-portrait",
            npc_ids=["envoy_iri"],
            variants=["neutral", "positive"],
            candidates_per_variant=1,
            prompt_version="v1_editorial_dossier",
            actor_user_id=None,
            output_dir=str(tmp_path / "custom_job_dir"),
            plan_path=None,
        )
    )

    plan_path = Path(payload["plan_path"])
    stored = load_author_portrait_plan(plan_path)

    assert plan_path.name == "portrait_plan.json"
    assert stored.job_id == "job-portrait"
    assert stored.output_dir == str((tmp_path / "custom_job_dir").resolve())
    assert payload["job_count"] == len(stored.jobs)


def test_author_cast_portrait_generate_and_validate_write_job_artifacts(monkeypatch, tmp_path) -> None:
    plan = _minimal_plan(tmp_path)
    plan_path = tmp_path / "author_jobs" / "job-portrait" / "portrait_plan.json"
    write_author_portrait_plan(plan_path, plan)
    monkeypatch.setattr(
        "tools.author_cast_portrait_generate.generate_portrait_image",
        lambda session, *, api_key, image_api_base_url, image_model, request_timeout_seconds, prompt_text: (b"\x89PNG\r\n\x1a\nportrait", "image/png"),
    )

    generated = run_generation(
        SimpleNamespace(
            plan_path=str(plan_path),
            api_key="test-key",
            request_timeout_seconds=30.0,
            asset_ids=None,
        )
    )
    validated = run_validation(SimpleNamespace(plan_path=str(plan_path), validation_path=None))

    assert generated["generated_count"] == 2
    assert validated["ok"] is True
    assert Path(validated["validation_path"]).exists()
    assert not validated["missing_files"]
    assert (Path(plan.output_dir) / "images" / "envoy_iri" / "neutral" / "asset_neutral.png").exists()


def test_author_cast_portrait_validate_reports_missing_files_and_hash_mismatch(tmp_path) -> None:
    plan = _minimal_plan(tmp_path)
    broken_plan = plan.model_copy(
        update={
            "jobs": [
                plan.jobs[0].model_copy(update={"prompt_hash": "broken-hash"}),
                plan.jobs[1],
            ]
        }
    )
    plan_path = tmp_path / "author_jobs" / "job-portrait" / "portrait_plan.json"
    write_author_portrait_plan(plan_path, broken_plan)
    output_dir = Path(broken_plan.output_dir)
    existing_file = output_dir / broken_plan.jobs[1].relative_output_path
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_bytes(b"\x89PNG\r\n\x1a\nportrait")

    validated = run_validation(SimpleNamespace(plan_path=str(plan_path), validation_path=None))

    assert validated["ok"] is False
    assert len(validated["missing_files"]) == 1
    assert validated["hash_mismatches"] == ["asset_neutral"]


def test_author_job_portrait_static_route_serves_local_file_and_404s_missing(tmp_path) -> None:
    portrait_dir = tmp_path / "portraits" / "author_jobs"
    existing_file = portrait_dir / "job-portrait" / "images" / "envoy_iri" / "neutral" / "asset_neutral.png"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_bytes(b"\x89PNG\r\n\x1a\nportrait")

    app = create_app(
        runtime_settings=Settings(
            local_author_portrait_dir=str(portrait_dir),
            roster_enabled=False,
        )
    )
    client = TestClient(app)

    found = client.get("/portraits/author-jobs/job-portrait/images/envoy_iri/neutral/asset_neutral.png")
    missing = client.get("/portraits/author-jobs/job-portrait/images/envoy_iri/neutral/missing.png")

    assert found.status_code == 200
    assert found.content.startswith(b"\x89PNG")
    assert missing.status_code == 404

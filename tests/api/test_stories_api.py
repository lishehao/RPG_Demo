from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.domain.linter import LintReport, lint_story_pack
from rpg_backend.generator.prompt_compiler import PromptCompileError, PromptCompileResult
from rpg_backend.generator.spec_schema import StorySpec
from rpg_backend.generator.errors import GeneratorBuildError
from rpg_backend.generator.versioning import GENERATOR_VERSION
from tests.helpers.route_paths import story_draft_patch_path, story_draft_path, story_path, story_publish_path, stories_generate_path, stories_path

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _sample_pack() -> dict:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


def _sample_story_spec() -> StorySpec:
    return StorySpec.model_validate(
        {
            "title": "Signal Rift Protocol",
            "premise": "A city control signal fractures during peak load, forcing an improvised response team into a contested core.",
            "tone": "tense but pragmatic techno-thriller",
            "stakes": "If containment fails, the district grid collapses before dawn.",
            "beats": [
                {
                    "title": "Fault Ignition",
                    "objective": "Identify the true source of the signal split",
                    "conflict": "Conflicting telemetry and political interference",
                    "required_event": "b1.root_cause_locked",
                },
                {
                    "title": "Checkpoint Friction",
                    "objective": "Cross secured corridors to reach the control spine",
                    "conflict": "Security lockdown and public panic",
                    "required_event": "b2.lockdown_rerouted",
                },
                {
                    "title": "Core Arbitration",
                    "objective": "Reconcile rival control plans in the core chamber",
                    "conflict": "Competing priorities split the team",
                    "required_event": "b3.command_resolution",
                },
                {
                    "title": "Dawn Commit",
                    "objective": "Execute irreversible stabilization sequence",
                    "conflict": "Resource depletion and shrinking time window",
                    "required_event": "b4.final_commit",
                },
            ],
            "npcs": [
                {
                    "name": "Mara",
                    "role": "field engineer",
                    "motivation": "prevent systemic collapse",
                    "red_line": "Never cut hospital access to stabilize industry.",
                    "conflict_tags": ["anti_noise"],
                },
                {
                    "name": "Rook",
                    "role": "security lead",
                    "motivation": "protect civilians",
                    "red_line": "No civilian corridor can be abandoned for pace.",
                    "conflict_tags": ["anti_speed"],
                },
                {
                    "name": "Sera",
                    "role": "operations analyst",
                    "motivation": "preserve evidence",
                    "red_line": "No telemetry wipe even under command pressure.",
                    "conflict_tags": ["anti_noise"],
                },
                {
                    "name": "Director Vale",
                    "role": "command authority",
                    "motivation": "retain control",
                    "red_line": "Public command legitimacy cannot collapse.",
                    "conflict_tags": ["anti_resource_burn"],
                },
            ],
            "scene_constraints": [
                "Open with concrete damage and immediate objective framing.",
                "Escalate pressure with checkpoints and contradictory orders.",
                "Force a costly compromise to retain momentum.",
                "Converge to final resolution with one decisive tradeoff.",
            ],
            "move_bias": ["technical", "investigate", "social"],
            "ending_shape": "pyrrhic",
        }
    )


def _error_payload(response) -> dict:
    return response.json()["error"]


def test_story_create_publish_get_flow(client) -> None:
    pack = _sample_pack()

    created = client.post(stories_path(), json={"title": "Demo", "pack_json": pack})
    assert created.status_code == 200
    body = created.json()
    story_id = body["story_id"]
    assert body["status"] == "draft"

    published = client.post(story_publish_path(story_id), json={})
    assert published.status_code == 200
    pub_body = published.json()
    assert pub_body["version"] == 1

    fetched = client.get(f"{story_path(story_id)}?version=1")
    assert fetched.status_code == 200
    get_body = fetched.json()
    assert get_body["story_id"] == story_id
    assert get_body["version"] == 1
    assert get_body["pack"] == pack


def test_publish_rejects_invalid_pack(client) -> None:
    invalid_pack = _sample_pack()
    invalid_pack["moves"][0]["outcomes"] = [
        out for out in invalid_pack["moves"][0]["outcomes"] if out["result"] != "fail_forward"
    ]

    created = client.post(stories_path(), json={"title": "Invalid", "pack_json": invalid_pack})
    story_id = created.json()["story_id"]

    published = client.post(story_publish_path(story_id), json={})
    assert published.status_code == 422


def test_story_list_and_draft_endpoints_return_author_summary(client) -> None:
    pack = _sample_pack()

    created = client.post(stories_path(), json={"title": "Author Story", "pack_json": pack})
    assert created.status_code == 200
    story_id = created.json()["story_id"]

    listed_before_publish = client.get(stories_path())
    assert listed_before_publish.status_code == 200
    items = listed_before_publish.json()["stories"]
    created_item = next(item for item in items if item["story_id"] == story_id)
    assert created_item["title"] == "Author Story"
    assert created_item["has_draft"] is True
    assert created_item["latest_published_version"] is None

    published = client.post(story_publish_path(story_id), json={})
    assert published.status_code == 200

    listed_after_publish = client.get(stories_path())
    published_item = next(item for item in listed_after_publish.json()["stories"] if item["story_id"] == story_id)
    assert published_item["latest_published_version"] == 1
    assert published_item["latest_published_at"]

    draft = client.get(story_draft_path(story_id))
    assert draft.status_code == 200
    draft_body = draft.json()
    assert draft_body["story_id"] == story_id
    assert draft_body["title"] == "Author Story"
    assert draft_body["draft_pack"] == pack
    assert draft_body["latest_published_version"] == 1


def test_story_draft_patch_updates_story_beat_scene_and_npc_fields(client) -> None:
    pack = _sample_pack()
    created = client.post(stories_path(), json={"title": "Editable Story", "pack_json": pack})
    assert created.status_code == 200
    story_id = created.json()["story_id"]

    response = client.patch(
        story_draft_patch_path(story_id),
        json={
            "changes": [
                {"target_type": "story", "field": "title", "value": "Whispers in the Veilwood"},
                {"target_type": "story", "field": "description", "value": "A cleaner review description."},
                {"target_type": "story", "field": "style_guard", "value": "quiet, exact, strategic"},
                {"target_type": "story", "field": "input_hint", "value": "Lead with free input."},
                {"target_type": "beat", "target_id": "b1", "field": "title", "value": "The First Silence Breaks"},
                {"target_type": "scene", "target_id": "sc2", "field": "scene_seed", "value": "Investigate the broken vow under strict silence."},
                {"target_type": "npc", "target_id": pack["npc_profiles"][0]["name"], "field": "red_line", "value": "I will not falsify the ritual record."},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Whispers in the Veilwood"
    assert body["draft_pack"]["title"] == "Whispers in the Veilwood"
    assert body["draft_pack"]["description"] == "A cleaner review description."
    assert body["draft_pack"]["style_guard"] == "quiet, exact, strategic"
    assert body["draft_pack"]["input_hint"] == "Lead with free input."
    assert body["draft_pack"]["beats"][0]["title"] == "The First Silence Breaks"
    assert body["draft_pack"]["scenes"][1]["scene_seed"] == "Investigate the broken vow under strict silence."
    assert body["draft_pack"]["npc_profiles"][0]["red_line"] == "I will not falsify the ritual record."

    refreshed = client.get(story_draft_path(story_id))
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["title"] == "Whispers in the Veilwood"
    assert refreshed_body["draft_pack"]["input_hint"] == "Lead with free input."


def test_story_draft_patch_rejects_invalid_field_combination(client) -> None:
    pack = _sample_pack()
    created = client.post(stories_path(), json={"title": "Invalid Patch", "pack_json": pack})
    story_id = created.json()["story_id"]

    response = client.patch(
        story_draft_patch_path(story_id),
        json={
            "changes": [
                {"target_type": "story", "field": "scene_seed", "value": "bad"}
            ]
        },
    )
    assert response.status_code == 422
    err = _error_payload(response)
    assert err["code"] == "validation_error"


def test_story_draft_patch_returns_404_for_missing_target(client) -> None:
    pack = _sample_pack()
    created = client.post(stories_path(), json={"title": "Missing Target", "pack_json": pack})
    story_id = created.json()["story_id"]

    response = client.patch(
        story_draft_patch_path(story_id),
        json={
            "changes": [
                {"target_type": "scene", "target_id": "sc404", "field": "scene_seed", "value": "bad"}
            ]
        },
    )
    assert response.status_code == 404
    err = _error_payload(response)
    assert err["code"] == "draft_target_not_found"


def test_story_draft_patch_is_atomic_on_validation_failure(client) -> None:
    pack = _sample_pack()
    created = client.post(stories_path(), json={"title": "Atomic Story", "pack_json": pack})
    story_id = created.json()["story_id"]

    response = client.patch(
        story_draft_patch_path(story_id),
        json={
            "changes": [
                {"target_type": "story", "field": "description", "value": "intermediate change"},
                {"target_type": "npc", "target_id": pack["npc_profiles"][0]["name"], "field": "red_line", "value": ""},
            ]
        },
    )
    assert response.status_code == 422
    err = _error_payload(response)
    assert err["code"] == "validation_error"

    refreshed = client.get(story_draft_path(story_id))
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["draft_pack"]["description"] == pack["description"]
    assert refreshed_body["draft_pack"]["npc_profiles"][0]["red_line"] == pack["npc_profiles"][0]["red_line"]


def test_generate_story_success_without_publish(client) -> None:
    response = client.post(
        stories_generate_path(),
        json={
            "seed_text": "Signal collapse in a city reactor.",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["story_id"]
    assert body["version"] is None
    generation = body["generation"]
    assert generation["mode"] == "seed"
    assert body["pack_hash"]
    assert generation["generator_version"] == GENERATOR_VERSION
    assert generation["variant_seed"]
    assert generation["palette_policy"] == "random"
    assert "errors" in generation["lint"]
    assert "warnings" in generation["lint"]
    assert isinstance(generation["attempts"], int)
    assert isinstance(generation["regenerate_count"], int)
    assert isinstance(generation["attempt_history"], list)
    report = lint_story_pack(body["pack"])
    assert report.ok, report.errors


def test_generate_story_success_with_publish(client) -> None:
    response = client.post(
        stories_generate_path(),
        json={
            "seed_text": "Contain the reactor signal.",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["story_id"]
    assert body["version"] >= 1
    generation = body["generation"]
    assert generation["mode"] == "seed"
    assert body["pack_hash"]
    assert generation["generator_version"] == GENERATOR_VERSION
    assert generation["variant_seed"]


def test_generate_with_variant_seed_is_reproducible(client) -> None:
    payload = {
        "seed_text": "Deterministic run",
        "target_minutes": 10,
        "npc_count": 4,
        "variant_seed": "fixed-seed-1",
        "palette_policy": "random",
        "publish": False,
    }
    first = client.post(stories_generate_path(), json=payload)
    second = client.post(stories_generate_path(), json=payload)
    assert first.status_code == 200
    assert second.status_code == 200

    first_body = first.json()
    second_body = second.json()
    assert first_body["pack_hash"] == second_body["pack_hash"]
    assert first_body["generation"]["generator_version"] == second_body["generation"]["generator_version"] == GENERATOR_VERSION
    assert first_body["generation"]["variant_seed"] == second_body["generation"]["variant_seed"] == "fixed-seed-1"


def test_generate_without_variant_seed_returns_actual_seed(client) -> None:
    response = client.post(
        stories_generate_path(),
        json={
            "seed_text": "No explicit variant",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["generation"]["variant_seed"], str)
    assert body["generation"]["variant_seed"]
    assert body["pack_hash"]
    assert body["generation"]["generator_version"] == GENERATOR_VERSION


def test_generate_rejects_unsupported_generator_version(client) -> None:
    response = client.post(
        stories_generate_path(),
        json={
            "seed_text": "version mismatch",
            "target_minutes": 10,
            "npc_count": 4,
            "generator_version": "v99.0",
            "publish": False,
        },
    )
    assert response.status_code == 422
    err = _error_payload(response)
    assert err["code"] == "unsupported_generator_version"
    assert "unsupported_generator_version" in err["details"]["errors"][0]
    assert err["details"]["generator_version"] == GENERATOR_VERSION


def test_generate_story_unrepairable_returns_422(client, monkeypatch) -> None:
    from rpg_backend.api import stories as stories_api
    from rpg_backend.domain.linter import LintReport

    async def _always_fail(*args, **kwargs):
        raise GeneratorBuildError(
            LintReport(errors=["forced failure"], warnings=[]),
            generation_attempts=4,
            regenerate_count=3,
            notes=["forced"],
            generator_version=GENERATOR_VERSION,
            variant_seed="forced-seed",
            palette_policy="random",
            error_code="generation_failed_after_regenerates",
        )

    monkeypatch.setattr(stories_api.GeneratorPipeline, "run", _always_fail)
    response = client.post(
        stories_generate_path(),
        json={
            "seed_text": "broken seed",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": False,
        },
    )
    assert response.status_code == 422
    err = _error_payload(response)
    assert err["code"] == "generation_failed_after_regenerates"
    assert err["details"]["errors"] == ["forced failure"]
    assert err["details"]["generation_attempts"] == 4
    assert err["details"]["regenerate_count"] == 3
    assert err["details"]["notes"] == ["forced"]
    assert err["details"]["generator_version"] == GENERATOR_VERSION
    assert err["details"]["variant_seed"] == "forced-seed"
    assert err["details"]["palette_policy"] == "random"


def test_generate_story_prompt_mode_success_without_publish(client, monkeypatch) -> None:
    sample_spec = _sample_story_spec()
    async def _compile(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return PromptCompileResult(
            spec=sample_spec,
            spec_hash="a" * 64,
            model="test-generator-model",
            attempts=1,
            notes=["prompt compiler mocked"],
        )

    monkeypatch.setattr(
        "rpg_backend.generator.pipeline.PromptCompiler.compile",
        _compile,
    )

    response = client.post(
        stories_generate_path(),
        json={
            "prompt_text": "Generate a reactor crisis story with a pyrrhic ending.",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    generation = body["generation"]
    assert generation["mode"] == "prompt"
    assert body["version"] is None
    assert generation["compile"]["spec_hash"] == "a" * 64
    assert generation["compile"]["spec_summary"]
    report = lint_story_pack(body["pack"])
    assert report.ok, report.errors


def test_generate_story_prompt_mode_success_with_publish(client, monkeypatch) -> None:
    sample_spec = _sample_story_spec()
    async def _compile(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return PromptCompileResult(
            spec=sample_spec,
            spec_hash="b" * 64,
            model="test-generator-model",
            attempts=1,
            notes=["prompt compiler mocked"],
        )

    monkeypatch.setattr(
        "rpg_backend.generator.pipeline.PromptCompiler.compile",
        _compile,
    )

    response = client.post(
        stories_generate_path(),
        json={
            "prompt_text": "Generate a fast, high-pressure containment story.",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    generation = body["generation"]
    assert generation["mode"] == "prompt"
    assert body["version"] >= 1
    assert generation["compile"]["spec_hash"] == "b" * 64


def test_generate_story_rejects_empty_prompt_and_seed(client) -> None:
    response = client.post(
        stories_generate_path(),
        json={
            "seed_text": "   ",
            "prompt_text": "   ",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": False,
        },
    )
    assert response.status_code == 422


def test_generate_story_prompt_compile_failure_422(client, monkeypatch) -> None:
    async def _compile_raise(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise PromptCompileError(
            error_code="prompt_compile_failed",
            errors=["upstream timeout"],
            notes=["prompt compiler failed after retries"],
        )

    monkeypatch.setattr(
        "rpg_backend.generator.pipeline.PromptCompiler.compile",
        _compile_raise,
    )
    response = client.post(
        stories_generate_path(),
        json={
            "prompt_text": "generate from prompt",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": False,
        },
    )
    assert response.status_code == 422
    err = _error_payload(response)
    assert err["code"] == "prompt_compile_failed"
    assert err["details"]["errors"] == ["upstream timeout"]
    assert "prompt compiler failed after retries" in err["details"]["notes"]


def test_generate_story_forwards_candidate_parallelism(client, monkeypatch) -> None:
    from rpg_backend.api import stories as stories_api
    from types import SimpleNamespace

    captured: dict[str, object] = {}
    sample_pack = _sample_pack()

    async def _fake_generate_pack(self, **kwargs):  # noqa: ANN003, ANN202
        captured.update(kwargs)
        return SimpleNamespace(
            pack=sample_pack,
            pack_hash="d" * 64,
            generator_version=GENERATOR_VERSION,
            variant_seed=str(kwargs.get("variant_seed") or "seed"),
            palette_policy="random",
            generation_mode="seed",
            lint_report=LintReport(errors=[], warnings=[]),
            generation_attempts=1,
            regenerate_count=0,
            candidate_parallelism=int(kwargs.get("candidate_parallelism") or 1),
            attempt_history=[],
            spec_hash=None,
            spec_summary=None,
        )

    monkeypatch.setattr(stories_api.GeneratorPipeline, "run", _fake_generate_pack)

    response = client.post(
        stories_generate_path(),
        json={
            "seed_text": "forward candidate_parallelism",
            "target_minutes": 10,
            "npc_count": 4,
            "candidate_parallelism": 3,
            "publish": False,
        },
    )
    assert response.status_code == 200
    assert captured["candidate_parallelism"] == 3

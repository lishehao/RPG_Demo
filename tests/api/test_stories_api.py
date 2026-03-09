from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.domain.linter import LintReport, lint_story_pack
from tests.helpers.route_paths import story_draft_patch_path, story_draft_path, story_path, story_publish_path, stories_path

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _sample_pack() -> dict:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


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
    assert draft_body["draft_pack"]["story_id"] == pack["story_id"]
    assert draft_body["draft_pack"]["title"] == pack["title"]
    assert draft_body["draft_pack"]["opening_guidance"]["intro_text"]
    assert len(draft_body["draft_pack"]["opening_guidance"]["starter_prompts"]) == 3
    assert draft_body["latest_published_version"] == 1


def test_story_draft_patch_updates_opening_guidance_fields(client) -> None:
    pack = _sample_pack()
    created = client.post(stories_path(), json={"title": "Editable Guidance", "pack_json": pack})
    story_id = created.json()["story_id"]

    response = client.patch(
        story_draft_patch_path(story_id),
        json={
            "changes": [
                {"target_type": "opening_guidance", "field": "intro_text", "value": "The city enters a dangerous silence."},
                {"target_type": "opening_guidance", "field": "goal_hint", "value": "Understand what is breaking before you commit."},
                {"target_type": "opening_guidance", "field": "starter_prompt_1", "value": "I inspect the damaged ward first."},
                {"target_type": "opening_guidance", "field": "starter_prompt_2", "value": "I ask the nearest ally what changed."},
                {"target_type": "opening_guidance", "field": "starter_prompt_3", "value": "I move carefully and test the safest action."},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["draft_pack"]["opening_guidance"]["intro_text"] == "The city enters a dangerous silence."
    assert body["draft_pack"]["opening_guidance"]["goal_hint"] == "Understand what is breaking before you commit."
    assert body["draft_pack"]["opening_guidance"]["starter_prompts"] == [
        "I inspect the damaged ward first.",
        "I ask the nearest ally what changed.",
        "I move carefully and test the safest action.",
    ]


def test_story_draft_patch_rejects_invalid_opening_guidance_fields(client) -> None:
    pack = _sample_pack()
    created = client.post(stories_path(), json={"title": "Bad Guidance", "pack_json": pack})
    story_id = created.json()["story_id"]

    response = client.patch(
        story_draft_patch_path(story_id),
        json={
            "changes": [
                {"target_type": "opening_guidance", "field": "starter_prompt_2", "value": ""}
            ]
        },
    )
    assert response.status_code == 422
    err = _error_payload(response)
    assert err["code"] == "validation_error"


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


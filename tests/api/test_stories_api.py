from __future__ import annotations

import json
from pathlib import Path

PACK_PATH = Path("sample_data/story_pack_v1.json")


def _sample_pack() -> dict:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


def test_story_create_publish_get_flow(client) -> None:
    pack = _sample_pack()

    created = client.post("/stories", json={"title": "Demo", "pack_json": pack})
    assert created.status_code == 200
    body = created.json()
    story_id = body["story_id"]
    assert body["status"] == "draft"

    published = client.post(f"/stories/{story_id}/publish", json={})
    assert published.status_code == 200
    pub_body = published.json()
    assert pub_body["version"] == 1

    fetched = client.get(f"/stories/{story_id}?version=1")
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

    created = client.post("/stories", json={"title": "Invalid", "pack_json": invalid_pack})
    story_id = created.json()["story_id"]

    published = client.post(f"/stories/{story_id}/publish", json={})
    assert published.status_code == 422


def test_generate_story_placeholder_endpoint(client) -> None:
    response = client.post(
        "/stories/generate",
        json={
            "seed_text": "Signal collapse in a city reactor.",
            "target_minutes": 10,
            "npc_count": 4,
            "publish": False,
        },
    )
    assert response.status_code == 501
    body = response.json()
    assert body["status"] == "placeholder"
    assert body["story_id"] is None
    assert body["version"] is None
    assert body["attempts"] == 0

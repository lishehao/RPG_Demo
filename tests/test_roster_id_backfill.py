from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from rpg_backend.author.preview import build_author_story_summary
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.play.compiler import compile_play_plan
from rpg_backend.play.storage import SQLitePlaySessionStorage
from tests.author_fixtures import author_fixture_bundle
from tests.test_story_library_api import _preview_response
from tools import roster_id_backfill


def _story_bundle_with_stale_roster_id(old_id: str):
    fixture = author_fixture_bundle()
    cast = list(fixture.design_bundle.story_bible.cast)
    cast[1] = cast[1].model_copy(
        update={
            "roster_character_id": old_id,
            "roster_public_summary": "stale summary",
            "portrait_url": None,
            "portrait_variants": None,
            "template_version": None,
        }
    )
    return fixture.design_bundle.model_copy(
        update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": cast})}
    )


def test_story_backfill_rewrites_stale_bundle_ids(tmp_path, monkeypatch) -> None:
    bundle = _story_bundle_with_stale_roster_id("roster_archive_certifier")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    summary = build_author_story_summary(bundle, primary_theme="legitimacy_crisis")
    preview = _preview_response(bundle=bundle)
    library_service.publish_story(
        owner_user_id="usr_story",
        source_job_id="job-story",
        prompt_seed="seed",
        summary=summary,
        preview=preview,
        bundle=bundle,
        visibility="public",
    )

    monkeypatch.setattr(
        roster_id_backfill,
        "_load_runtime_entries",
        lambda: {
            "roster_archive_vote_certifier": {
                "roster_character_id": "roster_archive_vote_certifier",
                "roster_public_summary": "fresh summary",
                "portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png",
                "portrait_variants": {"neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png"},
                "template_version": "tpl-archive-v2",
            }
        },
    )

    summary_payload = roster_id_backfill._run_story_backfill(db_path=str(tmp_path / "stories.sqlite3"), apply_changes=True)
    assert summary_payload["stories_changed"] == 1
    assert summary_payload["id_remap_counts"]["roster_archive_certifier->roster_archive_vote_certifier"] == 1

    conn = sqlite3.connect(tmp_path / "stories.sqlite3")
    row = conn.execute("select bundle_json from published_stories where source_job_id = 'job-story'").fetchone()
    conn.close()
    bundle_payload = json.loads(row[0])
    member = bundle_payload["story_bible"]["cast"][1]
    assert member["roster_character_id"] == "roster_archive_vote_certifier"
    assert member["roster_public_summary"] == "fresh summary"
    assert member["portrait_url"].endswith("/neutral/current.png")
    assert member["template_version"] == "tpl-archive-v2"


def test_session_backfill_rewrites_stale_plan_ids(tmp_path, monkeypatch) -> None:
    fixture = author_fixture_bundle()
    plan_payload = compile_play_plan(
        story_id="story-session-backfill",
        bundle=fixture.design_bundle,
    ).model_dump(mode="json")
    plan_payload["cast"][1]["roster_character_id"] = "roster_courtyard_witness"
    plan_payload["cast"][1]["portrait_url"] = None
    plan_payload["cast"][1]["portrait_variants"] = None
    plan_payload["cast"][1]["template_version"] = None

    storage = SQLitePlaySessionStorage(str(tmp_path / "runtime.sqlite3"))
    storage.save_session(
        {
            "session_id": "session-1",
            "owner_user_id": "usr_play",
            "story_id": "story-1",
            "created_at": "2026-03-27T00:00:00+00:00",
            "expires_at": "2026-03-28T00:00:00+00:00",
            "finished_at": None,
            "plan": plan_payload,
            "state": {"session_id": "session-1", "story_id": "story-1", "status": "active"},
            "history": [],
            "turn_traces": [],
        }
    )

    monkeypatch.setattr(
        roster_id_backfill,
        "_load_runtime_entries",
        lambda: {
            "roster_archive_gallery_petitioner": {
                "roster_character_id": "roster_archive_gallery_petitioner",
                "roster_public_summary": "gallery witness summary",
                "portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_gallery_petitioner/neutral/current.png",
                "portrait_variants": {"neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_gallery_petitioner/neutral/current.png"},
                "template_version": "tpl-gallery-v2",
            }
        },
    )

    summary_payload = roster_id_backfill._run_session_backfill(db_path=str(tmp_path / "runtime.sqlite3"), apply_changes=True)
    assert summary_payload["sessions_changed"] == 1
    assert summary_payload["id_remap_counts"]["roster_courtyard_witness->roster_archive_gallery_petitioner"] == 1

    conn = sqlite3.connect(tmp_path / "runtime.sqlite3")
    row = conn.execute("select plan_json from play_sessions where session_id = 'session-1'").fetchone()
    conn.close()
    plan = json.loads(row[0])
    member = plan["cast"][1]
    assert member["roster_character_id"] == "roster_archive_gallery_petitioner"
    assert member["portrait_url"].endswith("/neutral/current.png")
    assert member["template_version"] == "tpl-gallery-v2"


def test_backfill_fails_on_unmapped_stale_ids(tmp_path, monkeypatch) -> None:
    bundle = _story_bundle_with_stale_roster_id("roster_unknown_legacy")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    summary = build_author_story_summary(bundle, primary_theme="legitimacy_crisis")
    preview = _preview_response(bundle=bundle)
    library_service.publish_story(
        owner_user_id="usr_story",
        source_job_id="job-story",
        prompt_seed="seed",
        summary=summary,
        preview=preview,
        bundle=bundle,
        visibility="public",
    )

    monkeypatch.setattr(roster_id_backfill, "_load_runtime_entries", lambda: {})

    with pytest.raises(RuntimeError, match="roster_unknown_legacy"):
        roster_id_backfill._run_story_backfill(db_path=str(tmp_path / "stories.sqlite3"), apply_changes=False)

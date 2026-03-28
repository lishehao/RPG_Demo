from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from rpg_backend.author.contracts import AuthorPreviewResponse
from rpg_backend.author.contracts import PortraitVariants
from rpg_backend.author.contracts import StoryGenerationControls
from rpg_backend.author.jobs import AuthorJobPublishSource
from rpg_backend.author.planning import build_story_flow_plan
from rpg_backend.author.preview import build_author_story_summary
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.main import app
from rpg_backend.product_copy import BANNED_ZH_REGISTER_PATTERNS, BANNED_ZH_SURFACE_TERMS
from tests.author_fixtures import author_fixture_bundle
from tests.auth_helpers import ensure_authenticated_client


def _preview_response(
    *,
    bundle=None,
    prompt_seed: str = "An envoy tries to hold an archive city together.",
    primary_theme: str = "legitimacy_crisis",
    modifiers: list[str] | None = None,
) -> AuthorPreviewResponse:
    fixture = author_fixture_bundle()
    bundle = bundle or fixture.design_bundle
    return AuthorPreviewResponse.model_validate(
        {
            "preview_id": "preview-lib-1",
            "prompt_seed": prompt_seed,
            "focused_brief": bundle.focused_brief.model_dump(mode="json"),
            "theme": {
                "primary_theme": primary_theme,
                "modifiers": modifiers or ["succession", "blackout"],
                "router_reason": "test_fixture",
            },
            "strategies": {
                "story_frame_strategy": "legitimacy_story",
                "cast_strategy": "legitimacy_cast",
                "beat_plan_strategy": "single_semantic_compile",
            },
            "structure": {
                "cast_topology": "three_slot",
                "expected_npc_count": len(bundle.story_bible.cast),
                "expected_beat_count": len(bundle.beat_spine),
            },
            "story": {
                "title": bundle.story_bible.title,
                "premise": bundle.story_bible.premise,
                "tone": bundle.story_bible.tone,
                "stakes": bundle.story_bible.stakes,
            },
            "cast_slots": [
                {"slot_label": member.name, "public_role": member.role}
                for member in bundle.story_bible.cast
            ],
            "beats": [
                {
                    "title": beat.title,
                    "goal": beat.goal,
                    "milestone_kind": beat.milestone_kind,
                }
                for beat in bundle.beat_spine
            ],
            "flashcards": [],
            "stage": "brief_parsed",
        }
    )


def _publish_source(
    job_id: str = "job-123",
    *,
    prompt_seed: str = "An envoy tries to hold an archive city together.",
    title: str | None = None,
    premise: str | None = None,
    tone: str | None = None,
    primary_theme: str = "legitimacy_crisis",
    modifiers: list[str] | None = None,
    language: str = "en",
) -> AuthorJobPublishSource:
    fixture = author_fixture_bundle()
    focused_brief = fixture.design_bundle.focused_brief.model_copy(update={"language": language})
    story_bible = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": title or fixture.design_bundle.story_bible.title,
            "premise": premise or fixture.design_bundle.story_bible.premise,
            "tone": tone or fixture.design_bundle.story_bible.tone,
        }
    )
    bundle = fixture.design_bundle.model_copy(update={"focused_brief": focused_brief, "story_bible": story_bible})
    summary = build_author_story_summary(bundle, primary_theme=primary_theme)
    return AuthorJobPublishSource(
        source_job_id=job_id,
        owner_user_id="local-dev",
        prompt_seed=prompt_seed,
        preview=_preview_response(
            bundle=bundle,
            prompt_seed=prompt_seed,
            primary_theme=primary_theme,
            modifiers=modifiers,
        ),
        summary=summary,
        bundle=bundle,
    )


class _FakeAuthorJobService:
    def __init__(self, source: AuthorJobPublishSource) -> None:
        self._source = source

    def get_publishable_job_source(self, job_id: str, *, actor_user_id=None) -> AuthorJobPublishSource:
        del actor_user_id
        assert job_id == self._source.source_job_id
        return self._source


def test_publish_route_is_idempotent_and_story_routes_read_persisted_story(tmp_path) -> None:
    import rpg_backend.main as main_module

    source = _publish_source()
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="library-idempotent@example.com", display_name="Library Owner")
        publish_first = client.post(f"/author/jobs/{source.source_job_id}/publish")
        publish_second = client.post(f"/author/jobs/{source.source_job_id}/publish")
        listing = client.get("/stories")
        detail = client.get(f"/stories/{publish_first.json()['story_id']}")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert publish_first.status_code == 200
    assert publish_second.status_code == 200
    assert publish_first.json()["story_id"] == publish_second.json()["story_id"]
    assert publish_first.json()["topology"] == "3-slot pressure triangle"

    assert listing.status_code == 200
    assert len(listing.json()["stories"]) == 1
    assert listing.json()["stories"][0]["story_id"] == publish_first.json()["story_id"]
    assert listing.json()["stories"][0]["title"] == source.summary.title
    assert listing.json()["meta"]["total"] == 1
    assert listing.json()["meta"]["sort"] == "published_at_desc"

    assert detail.status_code == 200
    assert detail.json()["story"]["story_id"] == publish_first.json()["story_id"]
    assert detail.json()["story"]["language"] == "en"
    assert detail.json()["presentation"]["status"] == "open_for_play"
    assert detail.json()["presentation"]["status_label"] == "Open for play"
    assert detail.json()["presentation"]["dossier_ref"].startswith("Dossier N°")
    assert detail.json()["presentation"]["engine_label"] == "LangGraph play runtime"
    assert detail.json()["structure"]["topology_label"] == publish_first.json()["topology"]
    assert detail.json()["structure"]["beat_outline"]
    assert detail.json()["cast_manifest"]["entries"]
    assert detail.json()["play_overview"]["protagonist"]["title"]
    assert detail.json()["play_overview"]["opening_narration"]
    assert detail.json()["play_overview"]["max_turns"] >= 4


def test_story_detail_contract_stays_content_oriented_for_frontend_scrollspy(tmp_path) -> None:
    import rpg_backend.main as main_module

    source = _publish_source()
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    owner_client = TestClient(app)
    anon_client = TestClient(app)
    try:
        ensure_authenticated_client(owner_client, email="story-detail@example.com", display_name="Detail Owner")
        published = owner_client.post(f"/author/jobs/{source.source_job_id}/publish?visibility=public")
        detail = anon_client.get(f"/stories/{published.json()['story_id']}")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert published.status_code == 200
    assert detail.status_code == 200
    body = detail.json()
    assert body["story"]["title"]
    assert len(body["structure"]["beat_outline"]) >= 1
    assert len(body["cast_manifest"]["entries"]) >= 1
    assert body["presentation"]["status"] == "open_for_play"
    assert body["play_overview"]["protagonist"]["mandate"]
    assert body["play_overview"]["runtime_profile_label"]


def test_story_detail_zh_copy_avoids_banned_terms(tmp_path) -> None:
    import rpg_backend.main as main_module

    source = _publish_source(
        job_id="job-zh-library",
        language="zh",
        title="港务协定",
        premise="港城已经被检疫封线与断供恐慌压到临界点，而一名档案员必须赶在投票前救回被改写的紧急舱单。",
        tone="封线政治惊悚",
        primary_theme="legitimacy_crisis",
    )
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    owner_client = TestClient(app)
    anon_client = TestClient(app)
    try:
        ensure_authenticated_client(owner_client, email="zh-story-detail@example.com", display_name="Detail Owner")
        published = owner_client.post(f"/author/jobs/{source.source_job_id}/publish?visibility=public")
        detail = anon_client.get(f"/stories/{published.json()['story_id']}")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert published.status_code == 200
    assert detail.status_code == 200
    body = detail.json()
    assert body["story"]["language"] == "zh"
    assert body["presentation"]["status_label"] == "现在可试玩"
    assert body["presentation"]["classification_label"] == "公信失衡"
    assert body["presentation"]["engine_label"] == "试玩引擎"
    payload = json.dumps(
        {
            "presentation": body["presentation"],
            "play_overview": body["play_overview"],
        },
        ensure_ascii=False,
    ).casefold()

    for term in BANNED_ZH_SURFACE_TERMS:
        assert term not in payload
    for pattern in BANNED_ZH_REGISTER_PATTERNS:
        assert pattern not in payload


def test_private_story_is_hidden_from_other_actor_until_visibility_changes(tmp_path) -> None:
    import rpg_backend.main as main_module

    source = _publish_source()
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    try:
        ensure_authenticated_client(alice_client, email="alice-library@example.com", display_name="Alice")
        ensure_authenticated_client(bob_client, email="bob-library@example.com", display_name="Bob")
        published = alice_client.post(f"/author/jobs/{source.source_job_id}/publish")
        hidden_list = bob_client.get("/stories")
        hidden_detail = bob_client.get(f"/stories/{published.json()['story_id']}")
        updated = alice_client.patch(
            f"/stories/{published.json()['story_id']}/visibility",
            json={"visibility": "public"},
        )
        public_list = bob_client.get("/stories")
        public_detail = bob_client.get(f"/stories/{published.json()['story_id']}")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert published.status_code == 200
    assert hidden_list.status_code == 200
    assert hidden_list.json()["stories"] == []
    assert hidden_detail.status_code == 404
    assert updated.status_code == 200
    assert updated.json()["visibility"] == "public"
    assert public_list.status_code == 200
    assert [story["story_id"] for story in public_list.json()["stories"]] == [published.json()["story_id"]]
    assert public_list.json()["stories"][0]["viewer_can_manage"] is False
    assert public_detail.status_code == 200
    assert public_detail.json()["presentation"]["visibility"] == "public"
    assert public_detail.json()["presentation"]["viewer_can_manage"] is False
    assert public_detail.json()["story"]["language"] == "en"


def test_story_listing_supports_accessible_mine_and_public_views(tmp_path) -> None:
    import rpg_backend.main as main_module

    alice_source = _publish_source("job-alice")
    bob_source = _publish_source("job-bob", title="Public Harbor Compact")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.story_library_service = library_service
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    try:
        ensure_authenticated_client(alice_client, email="alice-views@example.com", display_name="Alice")
        ensure_authenticated_client(bob_client, email="bob-views@example.com", display_name="Bob")
        main_module.author_job_service = _FakeAuthorJobService(alice_source)
        alice_story = alice_client.post(f"/author/jobs/{alice_source.source_job_id}/publish?visibility=private")
        main_module.author_job_service = _FakeAuthorJobService(bob_source)
        bob_story = bob_client.post(f"/author/jobs/{bob_source.source_job_id}/publish?visibility=public")
        accessible = alice_client.get("/stories")
        mine = alice_client.get("/stories", params={"view": "mine"})
        public_only = alice_client.get("/stories", params={"view": "public"})
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert alice_story.status_code == 200
    assert bob_story.status_code == 200
    assert accessible.status_code == 200
    assert mine.status_code == 200
    assert public_only.status_code == 200

    accessible_ids = [story["story_id"] for story in accessible.json()["stories"]]
    mine_ids = [story["story_id"] for story in mine.json()["stories"]]
    public_ids = [story["story_id"] for story in public_only.json()["stories"]]

    assert accessible.json()["meta"]["view"] == "accessible"
    assert mine.json()["meta"]["view"] == "mine"
    assert public_only.json()["meta"]["view"] == "public"
    assert alice_story.json()["story_id"] in accessible_ids
    assert bob_story.json()["story_id"] in accessible_ids
    assert mine_ids == [alice_story.json()["story_id"]]
    assert public_ids == [bob_story.json()["story_id"]]


def test_story_cursor_is_bound_to_view_dimension(tmp_path) -> None:
    import rpg_backend.main as main_module

    alice_source = _publish_source("job-view-alice")
    bob_source = _publish_source("job-view-bob", title="Public View Story")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.story_library_service = library_service
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    try:
        ensure_authenticated_client(alice_client, email="alice-cursor@example.com", display_name="Alice")
        ensure_authenticated_client(bob_client, email="bob-cursor@example.com", display_name="Bob")
        main_module.author_job_service = _FakeAuthorJobService(alice_source)
        alice_client.post(f"/author/jobs/{alice_source.source_job_id}/publish?visibility=private")
        main_module.author_job_service = _FakeAuthorJobService(bob_source)
        bob_client.post(f"/author/jobs/{bob_source.source_job_id}/publish?visibility=public")
        first_page = alice_client.get("/stories", params={"view": "accessible", "limit": 1})
        mismatched = alice_client.get(
            "/stories",
            params={"view": "public", "limit": 1, "cursor": first_page.json()["meta"]["next_cursor"]},
        )
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert first_page.status_code == 200
    assert first_page.json()["meta"]["next_cursor"] is not None
    assert mismatched.status_code == 400
    assert mismatched.json()["error"]["code"] == "story_cursor_invalid"


def test_owner_can_delete_story_and_non_owner_cannot(tmp_path) -> None:
    import rpg_backend.main as main_module

    source = _publish_source("job-delete")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    try:
        ensure_authenticated_client(alice_client, email="alice-delete@example.com", display_name="Alice")
        ensure_authenticated_client(bob_client, email="bob-delete@example.com", display_name="Bob")
        published = alice_client.post(f"/author/jobs/{source.source_job_id}/publish?visibility=private")
        blocked = bob_client.delete(f"/stories/{published.json()['story_id']}")
        deleted = alice_client.delete(f"/stories/{published.json()['story_id']}")
        detail = alice_client.get(f"/stories/{published.json()['story_id']}")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert published.status_code == 200
    assert blocked.status_code == 404
    assert deleted.status_code == 200
    assert deleted.json() == {"story_id": published.json()["story_id"], "deleted": True}
    assert detail.status_code == 404


def test_story_listing_supports_keyword_search_and_theme_facets(tmp_path) -> None:
    import rpg_backend.main as main_module

    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_library_service = main_module.story_library_service
    main_module.story_library_service = library_service
    client = TestClient(app)
    try:
        harbor_source = _publish_source(
            "job-harbor",
            prompt_seed="A harbor inspector must stop quarantine profiteers before the vote collapses.",
            title="Harbor Compact",
            premise="A harbor inspector must stop quarantine profiteers before the vote collapses.",
            tone="Tense civic fantasy",
            primary_theme="logistics_quarantine_crisis",
            modifiers=["harbor", "quarantine"],
        )
        archive_source = _publish_source(
            "job-archive",
            prompt_seed="An archivist exposes forged ledgers before the certification hearing closes.",
            title="Archive Accord",
            premise="An archivist exposes forged ledgers before the certification hearing closes.",
            tone="Procedural civic suspense",
            primary_theme="truth_record_crisis",
            modifiers=["archive", "ledger"],
        )
        for source in (harbor_source, archive_source):
            library_service.publish_story(
                owner_user_id="usr_search_owner",
                source_job_id=source.source_job_id,
                prompt_seed=source.prompt_seed,
                summary=source.summary,
                preview=source.preview,
                bundle=source.bundle,
                visibility="public",
            )

        search_response = client.get("/stories", params={"q": "harbor"})
        theme_response = client.get("/stories", params={"theme": "Truth and record crisis"})
    finally:
        main_module.story_library_service = original_library_service

    assert search_response.status_code == 200
    assert [story["title"] for story in search_response.json()["stories"]] == ["Harbor Compact"]
    assert search_response.json()["meta"] == {
        "query": "harbor",
        "theme": None,
        "language": None,
        "view": "accessible",
        "sort": "relevance",
        "limit": 20,
        "next_cursor": None,
        "has_more": False,
        "total": 1,
    }
    assert search_response.json()["facets"]["themes"] == [
        {"theme": "Logistics quarantine crisis", "count": 1}
    ]

    assert theme_response.status_code == 200
    assert [story["title"] for story in theme_response.json()["stories"]] == ["Archive Accord"]


def test_story_listing_supports_pinyin_recall_for_chinese_content(tmp_path) -> None:
    import rpg_backend.main as main_module

    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_library_service = main_module.story_library_service
    main_module.story_library_service = library_service
    client = TestClient(app)
    try:
        chinese_source = _publish_source(
            "job-zh-search",
            prompt_seed="公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
            title="公共议程",
            premise="公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
            tone="制度惊悚",
            primary_theme="truth_record_crisis",
            modifiers=["公共", "议程"],
        )
        chinese_summary = chinese_source.summary.model_copy(
            update={
                "language": "zh",
                "title": "公共议程",
                "one_liner": "公共议程正在被人暗中改写。",
                "premise": "公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
                "theme": "公共议程危机",
                "tone": "制度惊悚",
            }
        )
        chinese_preview = chinese_source.preview.model_copy(
            update={
                "language": "zh",
                "prompt_seed": "公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
                "story": chinese_source.preview.story.model_copy(
                    update={
                        "title": "公共议程",
                        "premise": "公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
                        "tone": "制度惊悚",
                    }
                ),
            }
        )
        library_service.publish_story(
            owner_user_id="usr_search_owner",
            source_job_id=chinese_source.source_job_id,
            prompt_seed=chinese_source.prompt_seed,
            summary=chinese_summary,
            preview=chinese_preview,
            bundle=chinese_source.bundle,
            visibility="public",
        )

        raw_query = client.get("/stories", params={"q": "公共"})
        g_query = client.get("/stories", params={"q": "g"})
        go_query = client.get("/stories", params={"q": "go"})
        gong_query = client.get("/stories", params={"q": "gong"})
        gongyi_query = client.get("/stories", params={"q": "gonggongyicheng"})
        initials_query = client.get("/stories", params={"q": "ggyc"})
    finally:
        main_module.story_library_service = original_library_service

    for response in (raw_query, g_query, go_query, gong_query, gongyi_query, initials_query):
        assert response.status_code == 200
        assert [story["title"] for story in response.json()["stories"]] == ["公共议程"]


def test_story_library_storage_rebuilds_search_index_when_pinyin_columns_are_missing(tmp_path) -> None:
    db_path = tmp_path / "stories.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE published_stories (
            story_id TEXT PRIMARY KEY,
            source_job_id TEXT NOT NULL UNIQUE,
            prompt_seed TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            title TEXT NOT NULL DEFAULT '',
            one_liner TEXT NOT NULL DEFAULT '',
            premise TEXT NOT NULL DEFAULT '',
            theme TEXT NOT NULL DEFAULT '',
            tone TEXT NOT NULL DEFAULT '',
            npc_count INTEGER NOT NULL DEFAULT 0,
            beat_count INTEGER NOT NULL DEFAULT 0,
            topology TEXT NOT NULL DEFAULT '',
            owner_user_id TEXT NOT NULL DEFAULT '',
            visibility TEXT NOT NULL DEFAULT 'private',
            summary_json TEXT NOT NULL,
            preview_json TEXT NOT NULL,
            bundle_json TEXT NOT NULL,
            published_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE VIRTUAL TABLE published_story_search
        USING fts5(
            story_id UNINDEXED,
            title,
            one_liner,
            premise,
            theme,
            tone,
            prompt_seed,
            tokenize = 'porter unicode61'
        )
        """
    )
    connection.commit()
    connection.close()

    storage = SQLiteStoryLibraryStorage(str(db_path))
    library_service = StoryLibraryService(storage)
    source = _publish_source(
        "job-pinyin-rebuild",
        prompt_seed="公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
        title="公共议程",
        premise="公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
        primary_theme="truth_record_crisis",
    )
    source_summary = source.summary.model_copy(
        update={
            "language": "zh",
            "title": "公共议程",
            "one_liner": "公共议程正在被人暗中改写。",
            "premise": "公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
            "theme": "公共议程危机",
            "tone": "制度惊悚",
        }
    )
    source_preview = source.preview.model_copy(
        update={
            "language": "zh",
            "prompt_seed": "公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
            "story": source.preview.story.model_copy(
                update={
                    "title": "公共议程",
                    "premise": "公共议程正在被人暗中改写，主角必须在听证会前把被删掉的记录翻出来。",
                    "tone": "制度惊悚",
                }
            ),
        }
    )
    published = library_service.publish_story(
        owner_user_id="usr_rebuild",
        source_job_id=source.source_job_id,
        prompt_seed=source.prompt_seed,
        summary=source_summary,
        preview=source_preview,
        bundle=source.bundle,
        visibility="public",
    )

    rebuilt = sqlite3.connect(db_path)
    rebuilt.row_factory = sqlite3.Row
    columns = [str(row["name"]) for row in rebuilt.execute("PRAGMA table_info(published_story_search)").fetchall()]
    pinyin_row = rebuilt.execute(
        "SELECT title_pinyin, premise_pinyin, prompt_seed_pinyin FROM published_story_search WHERE story_id = ?",
        (published.story_id,),
    ).fetchone()
    rebuilt.close()

    assert "title_pinyin" in columns
    assert "premise_pinyin" in columns
    assert "prompt_seed_pinyin" in columns
    assert pinyin_row is not None
    assert "gong gong yi cheng" in str(pinyin_row["title_pinyin"])


def test_story_listing_can_filter_by_language(tmp_path) -> None:
    import rpg_backend.main as main_module

    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_library_service = main_module.story_library_service
    main_module.story_library_service = library_service
    client = TestClient(app)
    try:
        english_source = _publish_source(
            "job-en",
            title="Harbor Compact",
            premise="A harbor inspector must stop quarantine profiteers before the vote collapses.",
            primary_theme="logistics_quarantine_crisis",
        )
        fixture = author_fixture_bundle()
        zh_bundle = fixture.design_bundle.model_copy(
            update={
                "focused_brief": fixture.focused_brief.model_copy(update={"language": "zh"}),
                "story_bible": fixture.design_bundle.story_bible.model_copy(
                    update={
                        "title": "港务协定",
                        "premise": "一名港口检查官必须在港区分裂前揭开被操纵的检疫扣押。",
                        "tone": "紧张的政治惊悚",
                    }
                ),
            }
        )
        zh_summary = build_author_story_summary(zh_bundle, primary_theme="logistics_quarantine_crisis")
        zh_preview = _preview_response(
            bundle=zh_bundle,
            prompt_seed="一名港口检查官必须在港区分裂前揭开被操纵的检疫扣押。",
            primary_theme="logistics_quarantine_crisis",
            modifiers=["港口", "检疫"],
        )
        zh_source = AuthorJobPublishSource(
            source_job_id="job-zh",
            owner_user_id="local-dev",
            prompt_seed="一名港口检查官必须在港区分裂前揭开被操纵的检疫扣押。",
            preview=zh_preview,
            summary=zh_summary,
            bundle=zh_bundle,
        )
        for source in (english_source, zh_source):
            library_service.publish_story(
                owner_user_id="usr_language_owner",
                source_job_id=source.source_job_id,
                prompt_seed=source.prompt_seed,
                summary=source.summary,
                preview=source.preview,
                bundle=source.bundle,
                visibility="public",
            )

        english = client.get("/stories", params={"language": "en"})
        chinese = client.get("/stories", params={"language": "zh"})
    finally:
        main_module.story_library_service = original_library_service

    assert english.status_code == 200
    assert [story["language"] for story in english.json()["stories"]] == ["en"]
    assert english.json()["meta"]["language"] == "en"
    assert chinese.status_code == 200
    assert [story["language"] for story in chinese.json()["stories"]] == ["zh"]
    assert chinese.json()["meta"]["language"] == "zh"


def test_story_detail_exposes_roster_metadata_when_present(tmp_path) -> None:
    fixture = author_fixture_bundle()
    roster_cast = list(fixture.design_bundle.story_bible.cast)
    roster_cast[1] = roster_cast[1].model_copy(
        update={
            "roster_character_id": "roster_archive_certifier",
            "roster_public_summary": "A records certifier trusted by no faction precisely because they have blocked all of them before.",
            "portrait_url": None,
        }
    )
    bundle = fixture.design_bundle.model_copy(update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": roster_cast})})
    source = AuthorJobPublishSource(
        source_job_id="job-roster-detail",
        owner_user_id="local-dev",
        prompt_seed="An archivist exposes forged ledgers before the certification hearing closes.",
        preview=_preview_response(bundle=bundle, prompt_seed="An archivist exposes forged ledgers before the certification hearing closes.", primary_theme="truth_record_crisis"),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))

    published = library_service.publish_story(
        owner_user_id="usr_roster_owner",
        source_job_id=source.source_job_id,
        prompt_seed=source.prompt_seed,
        summary=source.summary,
        preview=source.preview,
        bundle=source.bundle,
        visibility="public",
    )
    detail = library_service.get_story_detail(published.story_id, actor_user_id=None)

    assert detail.cast_manifest.entries[1].roster_character_id == "roster_archive_certifier"
    assert detail.cast_manifest.entries[1].roster_public_summary


def test_story_detail_exposes_duration_and_branch_budget(tmp_path) -> None:
    fixture = author_fixture_bundle()
    controls = StoryGenerationControls(target_duration_minutes=25)
    flow_plan = build_story_flow_plan(controls=controls, primary_theme="truth_record_crisis")
    bundle = fixture.design_bundle.model_copy(
        update={
            "generation_controls": controls,
            "story_flow_plan": flow_plan,
        }
    )
    source = AuthorJobPublishSource(
        source_job_id="job-duration-detail",
        owner_user_id="local-dev",
        prompt_seed="A records examiner must restore one public record before the vote hardens.",
        preview=_preview_response(
            bundle=bundle,
            prompt_seed="A records examiner must restore one public record before the vote hardens.",
            primary_theme="truth_record_crisis",
        ),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))

    published = library_service.publish_story(
        owner_user_id="usr_duration_owner",
        source_job_id=source.source_job_id,
        prompt_seed=source.prompt_seed,
        summary=source.summary,
        preview=source.preview,
        bundle=source.bundle,
        visibility="public",
    )
    detail = library_service.get_story_detail(published.story_id, actor_user_id=None)

    assert detail.play_overview is not None
    assert detail.play_overview.target_duration_minutes == 25
    assert detail.play_overview.branch_budget == "high"


def test_story_detail_can_expose_three_portrait_urls_when_present(tmp_path) -> None:
    fixture = author_fixture_bundle()
    roster_cast = [
        member.model_copy(
            update={
                "roster_character_id": roster_id,
                "roster_public_summary": f"Summary for {roster_id}.",
                "portrait_url": f"http://127.0.0.1:8000/portraits/roster/{roster_id}.png",
                "portrait_variants": PortraitVariants(
                    positive=f"http://127.0.0.1:8000/portraits/roster/{roster_id}__positive.png",
                    neutral=f"http://127.0.0.1:8000/portraits/roster/{roster_id}.png",
                    negative=f"http://127.0.0.1:8000/portraits/roster/{roster_id}__negative.png",
                ),
            }
        )
        for member, roster_id in zip(
            fixture.design_bundle.story_bible.cast,
            [
                "roster_archive_certifier",
                "roster_courtyard_witness",
                "roster_blackout_grid_broker",
            ],
            strict=False,
        )
    ]
    bundle = fixture.design_bundle.model_copy(
        update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": roster_cast})}
    )
    source = AuthorJobPublishSource(
        source_job_id="job-roster-three-detail",
        owner_user_id="local-dev",
        prompt_seed="An archivist exposes forged ledgers before the certification hearing closes.",
        preview=_preview_response(bundle=bundle, prompt_seed="An archivist exposes forged ledgers before the certification hearing closes.", primary_theme="truth_record_crisis"),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))

    published = library_service.publish_story(
        owner_user_id="usr_roster_owner",
        source_job_id=source.source_job_id,
        prompt_seed=source.prompt_seed,
        summary=source.summary,
        preview=source.preview,
        bundle=source.bundle,
        visibility="public",
    )
    detail = library_service.get_story_detail(published.story_id, actor_user_id=None)

    assert len([entry for entry in detail.cast_manifest.entries if entry.portrait_url]) == 3


def test_story_detail_can_expose_portrait_variants_when_present(tmp_path) -> None:
    fixture = author_fixture_bundle()
    roster_cast = [
        fixture.design_bundle.story_bible.cast[0].model_copy(
            update={
                "roster_character_id": "roster_archive_certifier",
                "roster_public_summary": "Summary for roster_archive_certifier.",
                "portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                "portrait_variants": PortraitVariants(
                    negative="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/negative/current.png",
                    neutral="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                    positive="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png",
                ),
            }
        ),
        *fixture.design_bundle.story_bible.cast[1:],
    ]
    bundle = fixture.design_bundle.model_copy(
        update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": roster_cast})}
    )
    source = AuthorJobPublishSource(
        source_job_id="job-roster-variant-detail",
        owner_user_id="local-dev",
        prompt_seed="An archivist exposes forged ledgers before the certification hearing closes.",
        preview=_preview_response(bundle=bundle, prompt_seed="An archivist exposes forged ledgers before the certification hearing closes.", primary_theme="truth_record_crisis"),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))

    published = library_service.publish_story(
        owner_user_id="usr_roster_owner",
        source_job_id=source.source_job_id,
        prompt_seed=source.prompt_seed,
        summary=source.summary,
        preview=source.preview,
        bundle=source.bundle,
        visibility="public",
    )
    detail = library_service.get_story_detail(published.story_id, actor_user_id=None)

    assert detail.cast_manifest.entries[0].portrait_variants is not None
    assert detail.cast_manifest.entries[0].portrait_variants.positive == "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png"
    assert detail.cast_manifest.entries[1].portrait_variants is None


def test_story_listing_requires_reset_for_pre_migrated_story_columns(tmp_path) -> None:
    db_path = tmp_path / "stories.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE published_stories (
            story_id TEXT PRIMARY KEY,
            source_job_id TEXT NOT NULL UNIQUE,
            prompt_seed TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            one_liner TEXT NOT NULL DEFAULT '',
            premise TEXT NOT NULL DEFAULT '',
            theme TEXT NOT NULL DEFAULT '',
            tone TEXT NOT NULL DEFAULT '',
            npc_count INTEGER NOT NULL DEFAULT 0,
            beat_count INTEGER NOT NULL DEFAULT 0,
            topology TEXT NOT NULL DEFAULT '',
            summary_json TEXT NOT NULL,
            preview_json TEXT NOT NULL,
            bundle_json TEXT NOT NULL,
            published_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()

    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(db_path)))

    with pytest.raises(RuntimeError, match="Reset local artifacts with `python tools/reset_local_databases.py`"):
        library_service.list_stories(actor_user_id=None)



def test_story_listing_paginates_with_cursor(tmp_path) -> None:
    import rpg_backend.main as main_module

    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    original_library_service = main_module.story_library_service
    main_module.story_library_service = library_service
    client = TestClient(app)
    try:
        for index in range(3):
            source = _publish_source(
                f"job-{index}",
                prompt_seed=f"A search seed {index}",
                title=f"Story {index}",
                premise=f"Story premise {index}",
            )
            library_service.publish_story(
                owner_user_id="usr_page_owner",
                source_job_id=source.source_job_id,
                prompt_seed=source.prompt_seed,
                summary=source.summary,
                preview=source.preview,
                bundle=source.bundle,
                visibility="public",
            )

        first_page = client.get("/stories", params={"limit": 1})
        second_page = client.get(
            "/stories",
            params={"limit": 1, "cursor": first_page.json()["meta"]["next_cursor"]},
        )
    finally:
        main_module.story_library_service = original_library_service

    assert first_page.status_code == 200
    assert first_page.json()["meta"]["has_more"] is True
    assert first_page.json()["meta"]["next_cursor"]
    assert len(first_page.json()["stories"]) == 1

    assert second_page.status_code == 200
    assert len(second_page.json()["stories"]) == 1
    assert first_page.json()["stories"][0]["story_id"] != second_page.json()["stories"][0]["story_id"]

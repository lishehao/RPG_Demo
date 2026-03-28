from __future__ import annotations

import time

import rpg_backend.author.jobs as author_jobs_module
from rpg_backend.author.checkpointer import AUTHOR_CHECKPOINT_ALLOWLIST, SQLiteCheckpointSaver, graph_config
from rpg_backend.author.contracts import AuthorJobProgress
from rpg_backend.author.jobs import AuthorJobService, _AuthorJobRecord
from rpg_backend.author.storage import SQLiteAuthorJobStorage
from rpg_backend.author.workflow import build_author_graph
from rpg_backend.config import Settings
from rpg_backend.play.service import PlaySessionService
from rpg_backend.play.storage import SQLitePlaySessionStorage
from tests.author_fixtures import FakeGateway
from tests.test_author_product_api import _preview_response
from tests.test_play_runtime import _no_gateway, _publish_story
from rpg_backend.play.runtime import _ending_by_id, build_epilogue_reactions


def test_author_job_service_resumes_running_job_after_restart(tmp_path) -> None:
    settings = Settings(runtime_state_db_path=str(tmp_path / "runtime.sqlite3"))
    storage = SQLiteAuthorJobStorage(settings.runtime_state_db_path)

    try:
        service = AuthorJobService(storage=storage, settings=settings, gateway_factory=lambda _settings=None: FakeGateway())
        service._save_record(
            _AuthorJobRecord(
                job_id="job-running",
                owner_user_id="local-dev",
                prompt_seed="seed",
                preview=_preview_response("seed"),
                status="running",
                progress=AuthorJobProgress(stage="running", stage_index=1, stage_total=10),
            )
        )

        restarted = AuthorJobService(storage=storage, settings=settings, gateway_factory=lambda _settings=None: FakeGateway())
        for _ in range(100):
            status = restarted.get_job("job-running")
            if status.status in {"completed", "failed"}:
                break
            time.sleep(0.01)

        assert status.status == "completed"
        assert restarted.get_job_result("job-running").summary is not None
    finally:
        pass


def test_play_session_service_restores_session_state_after_restart(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    settings = Settings(
        runtime_state_db_path=str(tmp_path / "runtime.sqlite3"),
        play_session_ttl_seconds=900,
    )
    storage = SQLitePlaySessionStorage(settings.runtime_state_db_path)

    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
        settings=settings,
        storage=storage,
    )
    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I verify the first blackout ledger before anyone can revise it.", "selected_suggestion_id": None})(),
    )

    restarted = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
        settings=settings,
        storage=storage,
    )
    restored = restarted.get_session(created.session_id)
    restored_history = restarted.get_session_history(created.session_id)

    assert restored.session_id == created.session_id
    assert restored.turn_index == updated.turn_index
    assert restored.narration == updated.narration
    assert len(restored_history.entries) == 3

    continued = restarted.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I use the verified record to force a public answer from the council floor.", "selected_suggestion_id": None})(),
    )

    assert continued.turn_index == updated.turn_index + 1


def test_play_session_service_restores_completed_epilogue_reactions_after_restart(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    settings = Settings(
        runtime_state_db_path=str(tmp_path / "runtime.sqlite3"),
        play_session_ttl_seconds=900,
    )
    storage = SQLitePlaySessionStorage(settings.runtime_state_db_path)

    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
        settings=settings,
        storage=storage,
    )
    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.status = "completed"
    record.state.ending = _ending_by_id(record.plan, record.state, "mixed")
    record.state.epilogue_reactions = build_epilogue_reactions(record.plan, record.state)
    record.finished_at = service._now()
    service._save_record(record)

    restarted = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
        settings=settings,
        storage=storage,
    )
    restored = restarted.get_session(created.session_id)

    assert restored.status == "completed"
    assert restored.ending is not None
    assert restored.epilogue_reactions is not None
    assert len(restored.epilogue_reactions) == len(record.state.epilogue_reactions)
    assert restored.epilogue_reactions[0].closing_line == record.state.epilogue_reactions[0].closing_line


def test_sqlite_checkpoint_saver_restores_author_graph_snapshot(tmp_path) -> None:
    db_path = str(tmp_path / "runtime.sqlite3")
    saver = SQLiteCheckpointSaver(db_path).with_allowlist(AUTHOR_CHECKPOINT_ALLOWLIST)
    graph = build_author_graph(gateway=FakeGateway(), checkpointer=saver)
    config = graph_config(run_id="persistent-author-run")

    graph.invoke(
        {
            "run_id": "persistent-author-run",
            "raw_brief": "A civic archivist must hold the city together while a blackout referendum turns the public record into a weapon.",
        },
        config=config,
    )

    restored_graph = build_author_graph(
        gateway=FakeGateway(),
        checkpointer=SQLiteCheckpointSaver(db_path).with_allowlist(AUTHOR_CHECKPOINT_ALLOWLIST),
    )
    snapshot = restored_graph.get_state(config)

    assert snapshot.values["story_frame_draft"].title
    assert snapshot.values["design_bundle"].story_bible.title
    assert snapshot.values["route_affordance_pack_draft"].affordance_effect_profiles


def test_author_job_service_resumes_from_existing_checkpoint_after_restart(tmp_path) -> None:
    settings = Settings(runtime_state_db_path=str(tmp_path / "runtime.sqlite3"))
    storage = SQLiteAuthorJobStorage(settings.runtime_state_db_path)
    preview = _preview_response("A civic archivist must restore one public record during a blackout vote.")
    storage.save_preview(preview.preview_id, preview.model_dump(mode="json"), created_at=AuthorJobService._now())

    saver = SQLiteCheckpointSaver(settings.runtime_state_db_path).with_allowlist(AUTHOR_CHECKPOINT_ALLOWLIST)
    graph = build_author_graph(gateway=FakeGateway(), checkpointer=saver)
    config = graph_config(run_id="checkpoint-job")
    list(
        graph.stream(
            {
                "run_id": "checkpoint-job",
                "raw_brief": preview.prompt_seed,
            },
            config=config,
            stream_mode="updates",
            interrupt_after=["generate_story_frame"],
        )
    )

    storage.save_job(
        {
            "job_id": "checkpoint-job",
            "owner_user_id": "local-dev",
            "prompt_seed": preview.prompt_seed,
            "status": "running",
            "preview": preview.model_dump(mode="json"),
            "progress": AuthorJobProgress(stage="story_frame_ready", stage_index=3, stage_total=10).model_dump(mode="json"),
            "created_at": AuthorJobService._now().isoformat(),
            "updated_at": AuthorJobService._now().isoformat(),
            "finished_at": None,
            "cache_metrics": None,
            "llm_call_trace": [],
            "quality_trace": [],
            "source_summary": {},
            "events": [],
            "summary": None,
            "bundle": None,
            "error": None,
        }
    )

    try:
        restarted = AuthorJobService(storage=storage, settings=settings, gateway_factory=lambda _settings=None: FakeGateway())
        for _ in range(100):
            status = restarted.get_job("checkpoint-job")
            if status.status in {"completed", "failed"}:
                break
            time.sleep(0.01)

        assert status.status == "completed"
        editor_state = restarted.get_job_editor_state("checkpoint-job")
        assert editor_state.story_frame_view.title
        assert editor_state.cast_view
        assert editor_state.beat_view
    finally:
        pass

from __future__ import annotations

import json
import sqlite3

from rpg_backend.play.storage import SQLitePlaySessionStorage
from tools import play_session_text_backfill


def test_play_session_text_backfill_rewrites_polluted_zh_state_and_history(tmp_path) -> None:
    storage = SQLitePlaySessionStorage(str(tmp_path / "runtime.sqlite3"))
    storage.save_session(
        {
            "session_id": "session-zh-cleanup",
            "owner_user_id": "usr-play",
            "story_id": "story-zh-cleanup",
            "created_at": "2026-03-27T00:00:00+00:00",
            "expires_at": "2026-03-28T00:00:00+00:00",
            "finished_at": None,
            "plan": {"story_id": "story-zh-cleanup", "language": "zh"},
            "state": {
                "session_id": "session-zh-cleanup",
                "story_id": "story-zh-cleanup",
                "status": "active",
                "narration": "You keep the scene moving with 佩拉·多恩 as the room reacts in real time. 佩拉·多恩的防线在你持续的逼问下崩塌。",
            },
            "history": [
                {"speaker": "player", "text": "我逼她把原始调度单交出来。"},
                {
                    "speaker": "gm",
                    "text": "SCENE_REACTION：她抬手压住旁席。 AXIS_PAYOFF：你把账页上的缺口当场拖回众人面前。",
                },
            ],
            "turn_traces": [],
        }
    )

    summary = play_session_text_backfill._run_backfill(
        db_path=str(tmp_path / "runtime.sqlite3"),
        apply_changes=True,
    )

    assert summary["sessions_scanned"] == 1
    assert summary["state_rows_changed"] == 1
    assert summary["history_entries_changed"] == 1
    assert summary["unrepairable_sessions"] == []

    conn = sqlite3.connect(tmp_path / "runtime.sqlite3")
    row = conn.execute("select state_json, history_json from play_sessions where session_id = 'session-zh-cleanup'").fetchone()
    conn.close()
    state = json.loads(row[0])
    history = json.loads(row[1])
    assert "You keep the scene moving" not in state["narration"]
    assert "你" in state["narration"]
    assert "SCENE_REACTION" not in history[1]["text"]
    assert "AXIS_PAYOFF" not in history[1]["text"]


def test_play_session_text_backfill_reports_unrepairable_sessions(tmp_path) -> None:
    storage = SQLitePlaySessionStorage(str(tmp_path / "runtime.sqlite3"))
    storage.save_session(
        {
            "session_id": "session-zh-unrepairable",
            "owner_user_id": "usr-play",
            "story_id": "story-zh-unrepairable",
            "created_at": "2026-03-27T00:00:00+00:00",
            "expires_at": "2026-03-28T00:00:00+00:00",
            "finished_at": None,
            "plan": {"story_id": "story-zh-unrepairable", "language": "zh"},
            "state": {
                "session_id": "session-zh-unrepairable",
                "story_id": "story-zh-unrepairable",
                "status": "active",
                "narration": "会场一阵骚动，记录官退开半步。",
            },
            "history": [],
            "turn_traces": [],
        }
    )

    summary = play_session_text_backfill._run_backfill(
        db_path=str(tmp_path / "runtime.sqlite3"),
        apply_changes=False,
    )

    assert summary["state_rows_changed"] == 0
    assert summary["history_entries_changed"] == 0
    assert summary["unrepairable_sessions"] == ["session-zh-unrepairable"]

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from rpg_backend.play.text_quality import (
    contains_play_meta_wrapper_text,
    has_language_contamination,
    has_second_person_reference,
    sanitize_persisted_narration,
)


def _session_language(plan_payload: dict[str, Any]) -> str:
    return str(plan_payload.get("language") or "en")


def _sanitize_gm_text(
    text: str | None,
    *,
    language: str,
) -> tuple[str, dict[str, bool]]:
    raw_text = str(text or "")
    sanitized = sanitize_persisted_narration(raw_text, language=language)
    meta_hit = contains_play_meta_wrapper_text(raw_text)
    contamination_hit = has_language_contamination(raw_text, language)
    return sanitized, {
        "wrapper_hit": meta_hit,
        "language_contamination_hit": contamination_hit,
        "needs_second_person_review": bool(sanitized) and not has_second_person_reference(sanitized, language),
    }


def _run_backfill(*, db_path: str, apply_changes: bool) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    session_rows = conn.execute("SELECT session_id, plan_json, state_json, history_json FROM play_sessions").fetchall()

    sessions_scanned = 0
    state_rows_changed = 0
    history_entries_changed = 0
    wrapper_hits = 0
    language_contamination_hits = 0
    session_ids_changed: list[str] = []
    unrepairable_sessions: list[str] = []

    for row in session_rows:
        sessions_scanned += 1
        session_id = str(row["session_id"])
        plan_payload = json.loads(str(row["plan_json"]))
        state_payload = json.loads(str(row["state_json"]))
        history_payload = json.loads(str(row["history_json"]))
        language = _session_language(plan_payload)
        session_changed = False
        session_unrepairable = False

        state_text = str(state_payload.get("narration") or "")
        sanitized_state_text, state_flags = _sanitize_gm_text(state_text, language=language)
        wrapper_hits += int(state_flags["wrapper_hit"])
        language_contamination_hits += int(state_flags["language_contamination_hit"])
        if sanitized_state_text != state_text:
            if not sanitized_state_text or contains_play_meta_wrapper_text(sanitized_state_text) or has_language_contamination(sanitized_state_text, language):
                session_unrepairable = True
            else:
                state_payload["narration"] = sanitized_state_text
                state_rows_changed += 1
                session_changed = True
        elif state_flags["needs_second_person_review"]:
            session_unrepairable = True

        updated_history: list[dict[str, Any]] = []
        for item in list(history_payload or []):
            entry = dict(item)
            if entry.get("speaker") != "gm":
                updated_history.append(entry)
                continue
            original_text = str(entry.get("text") or "")
            sanitized_text, entry_flags = _sanitize_gm_text(original_text, language=language)
            wrapper_hits += int(entry_flags["wrapper_hit"])
            language_contamination_hits += int(entry_flags["language_contamination_hit"])
            if sanitized_text != original_text:
                if not sanitized_text or contains_play_meta_wrapper_text(sanitized_text) or has_language_contamination(sanitized_text, language):
                    session_unrepairable = True
                else:
                    entry["text"] = sanitized_text
                    history_entries_changed += 1
                    session_changed = True
            elif entry_flags["needs_second_person_review"]:
                session_unrepairable = True
            updated_history.append(entry)

        if session_unrepairable:
            unrepairable_sessions.append(session_id)
            continue
        if session_changed:
            if apply_changes:
                conn.execute(
                    "UPDATE play_sessions SET state_json = ?, history_json = ? WHERE session_id = ?",
                    (
                        json.dumps(state_payload, ensure_ascii=False, separators=(",", ":")),
                        json.dumps(updated_history, ensure_ascii=False, separators=(",", ":")),
                        session_id,
                    ),
                )
            session_ids_changed.append(session_id)

    if apply_changes:
        conn.commit()
    conn.close()
    return {
        "apply": apply_changes,
        "sessions_scanned": sessions_scanned,
        "state_rows_changed": state_rows_changed,
        "history_entries_changed": history_entries_changed,
        "wrapper_hits": wrapper_hits,
        "language_contamination_hits": language_contamination_hits,
        "session_ids_changed": session_ids_changed,
        "unrepairable_sessions": sorted(unrepairable_sessions),
    }


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Backfill persisted play narration/history text using the current play text sanitizer.")
    parser.add_argument("--db-path", default=settings.runtime_state_db_path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    payload = _run_backfill(db_path=str(args.db_path), apply_changes=bool(args.apply))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

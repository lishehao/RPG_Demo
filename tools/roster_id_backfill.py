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
from rpg_backend.roster.legacy_ids import LEGACY_ROSTER_ID_MAP, resolve_legacy_roster_character_id
from rpg_backend.roster.loader import load_character_roster_runtime_catalog


def _load_runtime_entries() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    catalog = load_character_roster_runtime_catalog(settings.roster_runtime_catalog_path)
    return {
        entry.character_id: {
            "roster_character_id": entry.character_id,
            "roster_public_summary": entry.public_summary_zh or entry.public_summary_en,
            "portrait_url": entry.portrait_url,
            "portrait_variants": entry.portrait_variants,
            "template_version": entry.template_version or entry.source_fingerprint,
        }
        for entry in catalog.entries
    }


def _rewrite_cast_entries(
    cast_entries: list[dict[str, Any]],
    *,
    runtime_entries: dict[str, dict[str, Any]],
    id_remap_counts: dict[str, int],
    unmapped_ids: set[str],
) -> bool:
    changed = False
    for item in cast_entries:
        old_id = str(item.get("roster_character_id") or "").strip()
        if not old_id:
            continue
        new_id = resolve_legacy_roster_character_id(old_id)
        runtime_entry = runtime_entries.get(new_id)
        if new_id == old_id:
            if old_id.startswith("roster_") and runtime_entries.get(old_id) is None:
                unmapped_ids.add(old_id)
            continue
        if runtime_entry is None:
            unmapped_ids.add(old_id)
            continue
        item.update(runtime_entry)
        id_remap_counts[f"{old_id}->{new_id}"] = id_remap_counts.get(f"{old_id}->{new_id}", 0) + 1
        changed = True
    return changed


def _run_story_backfill(*, db_path: str, apply_changes: bool) -> dict[str, Any]:
    runtime_entries = _load_runtime_entries()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    id_remap_counts: dict[str, int] = {}
    story_ids_changed: list[str] = []
    unmapped_ids: set[str] = set()

    story_rows = conn.execute("SELECT story_id, bundle_json FROM published_stories").fetchall()
    for row in story_rows:
        bundle = json.loads(str(row["bundle_json"]))
        cast_entries = list(bundle.get("story_bible", {}).get("cast", []) or [])
        if _rewrite_cast_entries(
            cast_entries,
            runtime_entries=runtime_entries,
            id_remap_counts=id_remap_counts,
            unmapped_ids=unmapped_ids,
        ):
            if apply_changes:
                conn.execute(
                    "UPDATE published_stories SET bundle_json = ? WHERE story_id = ?",
                    (json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), row["story_id"]),
                )
            story_ids_changed.append(str(row["story_id"]))

    if unmapped_ids:
        conn.rollback()
        raise RuntimeError(f"unmapped stale roster ids: {', '.join(sorted(unmapped_ids))}")
    if apply_changes:
        conn.commit()
    conn.close()
    return {
        "apply": apply_changes,
        "stories_changed": len(story_ids_changed),
        "id_remap_counts": id_remap_counts,
        "unmapped_ids": [],
        "story_ids_changed": story_ids_changed,
        "known_aliases": LEGACY_ROSTER_ID_MAP,
    }


def _run_session_backfill(*, db_path: str, apply_changes: bool) -> dict[str, Any]:
    runtime_entries = _load_runtime_entries()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    id_remap_counts: dict[str, int] = {}
    session_ids_changed: list[str] = []
    unmapped_ids: set[str] = set()

    session_rows = conn.execute("SELECT session_id, plan_json FROM play_sessions").fetchall()
    for row in session_rows:
        plan = json.loads(str(row["plan_json"]))
        cast_entries = list(plan.get("cast", []) or [])
        if _rewrite_cast_entries(
            cast_entries,
            runtime_entries=runtime_entries,
            id_remap_counts=id_remap_counts,
            unmapped_ids=unmapped_ids,
        ):
            if apply_changes:
                conn.execute(
                    "UPDATE play_sessions SET plan_json = ? WHERE session_id = ?",
                    (json.dumps(plan, ensure_ascii=False, separators=(",", ":")), row["session_id"]),
                )
            session_ids_changed.append(str(row["session_id"]))

    if unmapped_ids:
        conn.rollback()
        raise RuntimeError(f"unmapped stale roster ids: {', '.join(sorted(unmapped_ids))}")
    if apply_changes:
        conn.commit()
    conn.close()
    return {
        "apply": apply_changes,
        "sessions_changed": len(session_ids_changed),
        "id_remap_counts": id_remap_counts,
        "unmapped_ids": [],
        "session_ids_changed": session_ids_changed,
        "known_aliases": LEGACY_ROSTER_ID_MAP,
    }


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Backfill stale roster_character_id values in published story bundles and play session plans.")
    parser.add_argument("--db-path", default=settings.runtime_state_db_path)
    parser.add_argument("--library-db-path", default=settings.story_library_db_path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    library_summary = _run_story_backfill(db_path=args.library_db_path, apply_changes=bool(args.apply))
    runtime_summary = _run_session_backfill(db_path=args.db_path, apply_changes=bool(args.apply))
    payload = {
        "apply": bool(args.apply),
        "stories_changed": library_summary["stories_changed"],
        "sessions_changed": runtime_summary["sessions_changed"],
        "id_remap_counts": {
            **library_summary["id_remap_counts"],
            **{
                key: library_summary["id_remap_counts"].get(key, 0) + runtime_summary["id_remap_counts"].get(key, 0)
                for key in set(library_summary["id_remap_counts"]) | set(runtime_summary["id_remap_counts"])
            },
        },
        "unmapped_ids": [],
        "story_ids_changed": library_summary["story_ids_changed"],
        "session_ids_changed": runtime_summary["session_ids_changed"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

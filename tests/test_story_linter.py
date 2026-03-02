from __future__ import annotations

import json
from pathlib import Path

from rpg_backend.domain.linter import lint_story_pack


FIXTURE = Path("sample_data/story_pack_v1.json")


def test_story_pack_linter_accepts_sample() -> None:
    pack = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = lint_story_pack(pack)
    assert report.ok, report.errors


def test_story_pack_linter_rejects_missing_fail_forward() -> None:
    pack = json.loads(FIXTURE.read_text(encoding="utf-8"))
    move = next(item for item in pack["moves"] if item["id"] == "scan_signal")
    move["outcomes"] = [out for out in move["outcomes"] if out["result"] != "fail_forward"]

    report = lint_story_pack(pack)
    assert not report.ok
    assert any("missing fail_forward" in err for err in report.errors)

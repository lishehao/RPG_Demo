from __future__ import annotations

from pathlib import Path


def test_no_sqlmodel_execute_in_llm_quota_repo() -> None:
    repo_file = (
        Path(__file__).resolve().parents[1]
        / "rpg_backend"
        / "infrastructure"
        / "repositories"
        / "llm_quota_async.py"
    )
    content = repo_file.read_text(encoding="utf-8")
    assert "db.execute(" not in content, "llm quota repository must use db.exec()"

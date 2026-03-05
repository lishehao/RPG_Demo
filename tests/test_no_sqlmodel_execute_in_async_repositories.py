from __future__ import annotations

from pathlib import Path
import re


def test_no_sqlmodel_execute_in_async_repositories() -> None:
    repositories_dir = (
        Path(__file__).resolve().parents[1]
        / "rpg_backend"
        / "infrastructure"
        / "repositories"
    )
    repository_files = sorted(repositories_dir.glob("*_async.py"))
    assert repository_files, "expected async repository files under infrastructure/repositories"

    execute_pattern = re.compile(r"\b(?:db|session)\.execute\(")
    violations = []
    for repo_file in repository_files:
        content = repo_file.read_text(encoding="utf-8")
        if execute_pattern.search(content):
            violations.append(str(repo_file.relative_to(Path(__file__).resolve().parents[1])))

    assert not violations, "async repositories must use db.exec(), found execute() in: " + ", ".join(violations)

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAN_ROOTS = ("rpg_backend", "tests", "scripts")
_NEEDLE_IMPORT = "from rpg_backend.storage.repositories"
_NEEDLE_MODULE = "import rpg_backend.storage.repositories"
_ALLOWLIST = {"tests/test_no_sync_repository_imports.py"}


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        base = _REPO_ROOT / root
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("*.py")))
    return files


def test_no_sync_storage_repository_imports() -> None:
    violations: list[str] = []
    for path in _iter_python_files():
        relative = path.relative_to(_REPO_ROOT).as_posix()
        if relative in _ALLOWLIST:
            continue
        content = path.read_text(encoding="utf-8")
        if _NEEDLE_IMPORT in content or _NEEDLE_MODULE in content:
            violations.append(relative)

    assert not violations, "sync storage.repositories import is forbidden:\n" + "\n".join(violations)

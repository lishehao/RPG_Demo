from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_dev_server_uses_fixed_local_port() -> None:
    vite_config = (ROOT / "frontend2/vite.config.ts").read_text()

    assert 'host: "127.0.0.1"' in vite_config
    assert "port: 8001" in vite_config
    assert "strictPort: true" in vite_config
    assert "http://127.0.0.1:8000" in vite_config
    assert "port: 5173" not in vite_config


def test_local_run_docs_and_tools_use_standard_ports() -> None:
    checked_paths = [
        ROOT / "README.md",
        ROOT / "README.zh.md",
        ROOT / "tools/playwright_launch/runner.py",
        ROOT / "tools/demo_video/capture_admissions_assets.py",
    ]
    combined = "\n".join(path.read_text() for path in checked_paths)

    assert "http://127.0.0.1:8001" in combined
    assert "http://127.0.0.1:8000" in combined
    assert "localhost:5173" not in combined
    assert "127.0.0.1:5173" not in combined

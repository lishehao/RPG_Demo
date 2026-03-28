from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import requests

from tools import browser_product_smoke, http_product_smoke
from tools.play_benchmarks import play_issue_inspect

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "integration_gate"
DEFAULT_BACKEND_HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 8010
DEFAULT_FRONTEND_PORT_START = 4174
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_AUTHOR_GATE_TIMEOUT_SECONDS = 420.0


class FullstackIntegrationGateFailure(RuntimeError):
    def __init__(self, message: str, *, summary: dict[str, Any]) -> None:
        super().__init__(message)
        self.summary = summary


@dataclass(frozen=True)
class FullstackIntegrationGateConfig:
    output_dir: Path
    backend_host: str
    backend_port: int
    frontend_port_start: int
    ui_language: browser_product_smoke.StoryLanguage
    request_timeout_seconds: float
    author_timeout_seconds: float
    max_play_turns: int
    headed: bool
    slow_mo_ms: int
    run_play_issue_inspect: bool
    inspect_prompt_count: int
    inspect_seed: int | None


def parse_args(argv: list[str] | None = None) -> FullstackIntegrationGateConfig:
    parser = argparse.ArgumentParser(description="Run the current full FE/BE integration gate in a disposable local environment.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--backend-host", default=DEFAULT_BACKEND_HOST)
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--frontend-port-start", type=int, default=DEFAULT_FRONTEND_PORT_START)
    parser.add_argument("--ui-language", choices=("en", "zh"), default="en")
    parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    parser.add_argument("--author-timeout-seconds", type=float, default=DEFAULT_AUTHOR_GATE_TIMEOUT_SECONDS)
    parser.add_argument("--max-play-turns", type=int, default=browser_product_smoke.DEFAULT_MAX_PLAY_TURNS)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--skip-play-issue-inspect", action="store_true")
    parser.add_argument("--inspect-prompt-count", type=int, default=10)
    parser.add_argument("--inspect-seed", type=int)
    args = parser.parse_args(argv)
    return FullstackIntegrationGateConfig(
        output_dir=Path(args.output_dir).expanduser().resolve(),
        backend_host=str(args.backend_host),
        backend_port=max(int(args.backend_port), 1),
        frontend_port_start=max(int(args.frontend_port_start), 1),
        ui_language=str(args.ui_language),  # type: ignore[arg-type]
        request_timeout_seconds=max(float(args.request_timeout_seconds), 5.0),
        author_timeout_seconds=max(float(args.author_timeout_seconds), 30.0),
        max_play_turns=max(int(args.max_play_turns), 1),
        headed=bool(args.headed),
        slow_mo_ms=max(int(args.slow_mo_ms), 0),
        run_play_issue_inspect=not bool(args.skip_play_issue_inspect),
        inspect_prompt_count=max(int(args.inspect_prompt_count), 1),
        inspect_seed=int(args.inspect_seed) if args.inspect_seed is not None else None,
    )


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _pick_frontend_port(host: str, start_port: int, *, max_attempts: int = 12) -> int:
    for offset in range(max_attempts):
        candidate = start_port + offset
        if _is_port_free(host, candidate):
            return candidate
    raise RuntimeError(f"could not find a free frontend port starting at {start_port}")


def _wait_for_http_ok(url: str, *, timeout_seconds: float) -> None:
    started_at = time.perf_counter()
    while time.perf_counter() - started_at < timeout_seconds:
        try:
            response = requests.get(url, timeout=1.0)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"{url} did not become healthy within {timeout_seconds:.1f}s")


@contextmanager
def _managed_backend_server(config: FullstackIntegrationGateConfig, run_dir: Path) -> Iterator[str]:
    if not _is_port_free(config.backend_host, config.backend_port):
        raise RuntimeError(f"backend port {config.backend_port} is already in use; refuse to reuse a non-disposable process")
    base_url = f"http://{config.backend_host}:{config.backend_port}"
    log_path = run_dir / "backend_server.log"
    runtime_dir = run_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["APP_STORY_LIBRARY_DB_PATH"] = str(runtime_dir / "story_library.sqlite3")
    env["APP_RUNTIME_STATE_DB_PATH"] = str(runtime_dir / "runtime_state.sqlite3")
    env["APP_ENABLE_BENCHMARK_API"] = "1"
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "rpg_backend.main:app",
                "--host",
                config.backend_host,
                "--port",
                str(config.backend_port),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_http_ok(f"{base_url}/health", timeout_seconds=20.0)
            yield base_url
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


@contextmanager
def _managed_frontend_server(config: FullstackIntegrationGateConfig, run_dir: Path, *, backend_base_url: str, frontend_port: int) -> Iterator[str]:
    app_url = f"http://{config.backend_host}:{frontend_port}"
    log_path = run_dir / "frontend_server.log"
    env = os.environ.copy()
    env["VITE_BACKEND_PROXY_TARGET"] = backend_base_url
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [
                "npm",
                "run",
                "dev",
                "--",
                "--host",
                config.backend_host,
                "--port",
                str(frontend_port),
            ],
            cwd=str(REPO_ROOT / "frontend"),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_http_ok(app_url, timeout_seconds=30.0)
            yield app_url
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def _render_browser_note(payload: dict[str, Any]) -> str:
    play = dict(payload.get("play") or {})
    create = dict(payload.get("create") or {})
    author = dict(payload.get("author") or {})
    detail = dict(payload.get("detail") or {})
    archive_probe = dict(play.get("archive_scroll_probe") or {})
    transcript_probe = dict(play.get("transcript_scroll_probe") or {})
    lines = [
        "# Browser Product Smoke",
        "",
        f"- Passed: `{bool(payload.get('ok'))}`",
        f"- UI language: `{payload.get('ui_language')}`",
        f"- Failed step: `{payload.get('failed_step') or 'none'}`",
        f"- Initial author loading stage: `{(author.get('initial_loading_stage_label') or '')}`",
        f"- Initial author loading completion: `{(author.get('initial_loading_completion') or '')}`",
        f"- Story title: `{detail.get('story_title') or ''}`",
        f"- Spark first seed length: `{len(str(create.get('first_seed') or ''))}`",
        f"- Spark second seed length: `{len(str(create.get('second_seed') or ''))}`",
        f"- Preview expected NPC count: `{create.get('expected_npc_count')}`",
        f"- Preview expected beat count: `{create.get('expected_beat_count')}`",
        f"- Author cast card count: `{author.get('cast_card_count')}`",
        f"- Author template chip count: `{author.get('template_chip_count')}`",
        f"- Play turns run: `{play.get('turns_run')}`",
        f"- Play completed: `{play.get('completed')}`",
        f"- Transcript scrollY: `{transcript_probe.get('scroll_y')}`",
        f"- Transcript target top: `{transcript_probe.get('target_top')}`",
        f"- Archive scrollY: `{archive_probe.get('scroll_y')}`",
        f"- Archive target top: `{archive_probe.get('target_top')}`",
    ]
    if payload.get("error_message"):
        lines.extend(["", "## Error", "", str(payload["error_message"])])
    return "\n".join(lines)


def _render_summary_markdown(summary: dict[str, Any]) -> str:
    backend = dict(summary.get("backend") or {})
    browser = dict(summary.get("browser") or {})
    inspect = dict(summary.get("play_issue_inspect") or {})
    artifacts = dict(summary.get("artifacts") or {})
    inspect_passed = bool(dict(inspect.get("summary") or {}).get("passed")) if inspect else None
    lines = [
        "# Fullstack Integration Gate",
        "",
        f"- Passed: `{bool(summary.get('ok'))}`",
        f"- Failed stage: `{summary.get('failed_stage') or 'none'}`",
        f"- Backend base URL: `{summary.get('backend_base_url')}`",
        f"- App URL: `{summary.get('app_url')}`",
        "",
        "## Verdicts",
        "",
        f"- Backend smoke EN: `{bool(dict(backend.get('en') or {}).get('ok'))}`",
        f"- Backend smoke ZH: `{bool(dict(backend.get('zh') or {}).get('ok'))}`",
        f"- Browser smoke: `{bool(browser.get('ok'))}`",
        f"- Play issue inspect: `{inspect_passed if inspect_passed is not None else 'skipped'}`",
        "",
        "## Artifacts",
        "",
        f"- Backend EN: `{artifacts.get('backend_en')}`",
        f"- Backend ZH: `{artifacts.get('backend_zh')}`",
        f"- Browser JSON: `{artifacts.get('browser_json')}`",
        f"- Browser note: `{artifacts.get('browser_note')}`",
        f"- Inspect JSON: `{artifacts.get('play_issue_inspect_json')}`",
        f"- Inspect note: `{artifacts.get('play_issue_inspect_note')}`",
        f"- Summary JSON: `{artifacts.get('summary_json')}`",
        "",
        "## Logs",
        "",
        f"- Backend log: `{artifacts.get('backend_log')}`",
        f"- Frontend log: `{artifacts.get('frontend_log')}`",
    ]
    if summary.get("error_message"):
        lines.extend(["", "## Error", "", str(summary["error_message"])])
    return "\n".join(lines)


def run_fullstack_integration_gate(config: FullstackIntegrationGateConfig) -> dict[str, Any]:
    run_dir = config.output_dir / f"fullstack_integration_gate_{_now_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    frontend_port = _pick_frontend_port(config.backend_host, config.frontend_port_start)
    backend_en_path = run_dir / "backend_smoke_en.json"
    backend_zh_path = run_dir / "backend_smoke_zh.json"
    browser_json_path = run_dir / "browser_smoke.json"
    browser_note_path = run_dir / "browser_smoke.md"
    summary_json_path = run_dir / "summary.json"
    summary_md_path = run_dir / "summary.md"
    summary: dict[str, Any] = {
        "ok": False,
        "failed_stage": None,
        "error_message": None,
        "backend_base_url": None,
        "app_url": None,
        "backend": {},
        "browser": {},
        "play_issue_inspect": {},
        "artifacts": {
            "backend_log": str(run_dir / "backend_server.log"),
            "frontend_log": str(run_dir / "frontend_server.log"),
            "backend_en": str(backend_en_path),
            "backend_zh": str(backend_zh_path),
            "browser_json": str(browser_json_path),
            "browser_note": str(browser_note_path),
            "play_issue_inspect_json": None,
            "play_issue_inspect_note": None,
            "summary_json": str(summary_json_path),
            "summary_md": str(summary_md_path),
        },
    }
    try:
        with _managed_backend_server(config, run_dir) as backend_base_url:
            summary["backend_base_url"] = backend_base_url
            with _managed_frontend_server(config, run_dir, backend_base_url=backend_base_url, frontend_port=frontend_port) as app_url:
                summary["app_url"] = app_url

                summary["failed_stage"] = "backend_smoke_en"
                try:
                    backend_en = http_product_smoke.run_http_product_smoke(
                        http_product_smoke.HttpProductSmokeConfig(
                            base_url=backend_base_url,
                            language="en",
                        prompt_seed=http_product_smoke.DEFAULT_SEED,
                        first_turn_input=http_product_smoke.DEFAULT_TURN_INPUT,
                        copilot_message=http_product_smoke.DEFAULT_COPILOT_MESSAGE,
                        poll_interval_seconds=http_product_smoke.DEFAULT_POLL_INTERVAL_SECONDS,
                        poll_timeout_seconds=max(config.author_timeout_seconds, http_product_smoke.DEFAULT_POLL_TIMEOUT_SECONDS),
                        request_timeout_seconds=config.request_timeout_seconds,
                            output_path=backend_en_path,
                            include_copilot=True,
                            include_benchmark_diagnostics=False,
                        )
                    )
                except http_product_smoke.HttpProductSmokeFailure as exc:
                    _write_json(backend_en_path, exc.summary)
                    raise
                _write_json(backend_en_path, backend_en)
                summary["backend"]["en"] = backend_en

                summary["failed_stage"] = "backend_smoke_zh"
                try:
                    backend_zh = http_product_smoke.run_http_product_smoke(
                        http_product_smoke.HttpProductSmokeConfig(
                            base_url=backend_base_url,
                            language="zh",
                        prompt_seed=http_product_smoke.DEFAULT_ZH_SEED,
                        first_turn_input=http_product_smoke.DEFAULT_ZH_TURN_INPUT,
                        copilot_message=http_product_smoke.DEFAULT_ZH_COPILOT_MESSAGE,
                        poll_interval_seconds=http_product_smoke.DEFAULT_POLL_INTERVAL_SECONDS,
                        poll_timeout_seconds=max(config.author_timeout_seconds, http_product_smoke.DEFAULT_POLL_TIMEOUT_SECONDS),
                        request_timeout_seconds=config.request_timeout_seconds,
                            output_path=backend_zh_path,
                            include_copilot=True,
                            include_benchmark_diagnostics=False,
                        )
                    )
                except http_product_smoke.HttpProductSmokeFailure as exc:
                    _write_json(backend_zh_path, exc.summary)
                    raise
                _write_json(backend_zh_path, backend_zh)
                summary["backend"]["zh"] = backend_zh

                summary["failed_stage"] = "browser_smoke"
                try:
                    browser_payload = browser_product_smoke.run_browser_product_smoke(
                        browser_product_smoke.BrowserProductSmokeConfig(
                            app_url=app_url,
                            ui_language=config.ui_language,
                            output_path=browser_json_path,
                            headed=config.headed,
                            slow_mo_ms=config.slow_mo_ms,
                            author_timeout_seconds=config.author_timeout_seconds,
                            action_timeout_seconds=max(30.0, min(config.request_timeout_seconds, 60.0)),
                            max_play_turns=config.max_play_turns,
                        )
                    )
                except browser_product_smoke.BrowserProductSmokeFailure as exc:
                    _write_json(browser_json_path, exc.summary)
                    _write_text(browser_note_path, _render_browser_note(exc.summary))
                    raise
                _write_json(browser_json_path, browser_payload)
                _write_text(browser_note_path, _render_browser_note(browser_payload))
                summary["browser"] = browser_payload

                if config.run_play_issue_inspect:
                    summary["failed_stage"] = "play_issue_inspect"
                    inspect_story_id = str(dict(summary["backend"].get("zh") or {}).get("ids", {}).get("story_id") or "")
                    inspect_config = play_issue_inspect.PlayIssueInspectConfig(
                        base_url=backend_base_url,
                        output_dir=run_dir,
                        launch_server=False,
                        story_id=inspect_story_id or None,
                        language="zh",
                        prompt_count=config.inspect_prompt_count,
                        seed=config.inspect_seed,
                        label="play_issue_inspect",
                        session_ttl_seconds=3600,
                        target_duration_minutes=25,
                    )
                    inspect_payload = play_issue_inspect.run_play_issue_inspect(inspect_config)
                    inspect_json_path, inspect_note_path = play_issue_inspect.write_artifacts(inspect_config, inspect_payload)
                    summary["artifacts"]["play_issue_inspect_json"] = str(inspect_json_path)
                    summary["artifacts"]["play_issue_inspect_note"] = str(inspect_note_path)
                    summary["play_issue_inspect"] = inspect_payload

                inspect_ok = True if not config.run_play_issue_inspect else bool(dict(summary["play_issue_inspect"].get("summary") or {}).get("passed"))
                summary["ok"] = bool(backend_en.get("ok")) and bool(backend_zh.get("ok")) and bool(browser_payload.get("ok")) and inspect_ok
                summary["failed_stage"] = None if summary["ok"] else summary["failed_stage"]
                _write_json(summary_json_path, summary)
                _write_text(summary_md_path, _render_summary_markdown(summary))
                return summary
    except Exception as exc:  # noqa: BLE001
        summary["ok"] = False
        summary["error_message"] = str(exc)
        _write_json(summary_json_path, summary)
        _write_text(summary_md_path, _render_summary_markdown(summary))
        raise FullstackIntegrationGateFailure(str(exc), summary=summary) from exc


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    try:
        payload = run_fullstack_integration_gate(config)
        exit_code = 0
    except FullstackIntegrationGateFailure as exc:
        payload = exc.summary
        exit_code = 1
    print(json.dumps(payload, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

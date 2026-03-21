from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any, Literal
from urllib.parse import urlparse

from tools.play_benchmarks.story_seed_factory import build_story_seed_batch


LaunchLayer = Literal["env", "core", "recovery", "parallel"]
BrowserName = Literal["chromium", "webkit", "firefox"]
WorkerMode = Literal["author", "play", "mixed"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "playwright" / "launch_readiness"
DEFAULT_AUTHOR_TIMEOUT_SECONDS = 180.0
DEFAULT_TURN_TIMEOUT_SECONDS = 90.0
DEFAULT_PARALLEL_WORKER_COUNT = 10
DEFAULT_MAX_PLAY_TURNS = 6


@dataclass(frozen=True)
class LaunchReadinessConfig:
    app_url: str
    output_dir: Path
    browsers: tuple[BrowserName, ...]
    layers: tuple[LaunchLayer, ...]
    headed: bool
    slow_mo_ms: int
    author_timeout_seconds: float
    turn_timeout_seconds: float
    max_play_turns: int
    parallel_worker_count: int
    seed: int | None


@dataclass(frozen=True)
class ParallelWorkerSpec:
    worker_id: str
    mode: WorkerMode
    prompt_seed: str | None = None


def parse_args(argv: list[str] | None = None) -> LaunchReadinessConfig:
    parser = argparse.ArgumentParser(description="Run the prelaunch Playwright launch-readiness suite.")
    parser.add_argument("--app-url", default="http://127.0.0.1:5173")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--browsers", default="chromium")
    parser.add_argument("--layers", default="env,core,recovery,parallel")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--author-timeout-seconds", type=float, default=DEFAULT_AUTHOR_TIMEOUT_SECONDS)
    parser.add_argument("--turn-timeout-seconds", type=float, default=DEFAULT_TURN_TIMEOUT_SECONDS)
    parser.add_argument("--max-play-turns", type=int, default=DEFAULT_MAX_PLAY_TURNS)
    parser.add_argument("--parallel-worker-count", type=int, default=DEFAULT_PARALLEL_WORKER_COUNT)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args(argv)
    browser_values = tuple(
        browser.strip()
        for browser in str(args.browsers).split(",")
        if browser.strip()
    )
    layer_values = tuple(
        layer.strip()
        for layer in str(args.layers).split(",")
        if layer.strip()
    )
    valid_browsers = {"chromium", "webkit", "firefox"}
    valid_layers = {"env", "core", "recovery", "parallel"}
    if not browser_values or any(browser not in valid_browsers for browser in browser_values):
        raise SystemExit(f"--browsers must be a comma-separated subset of {sorted(valid_browsers)}")
    if not layer_values or any(layer not in valid_layers for layer in layer_values):
        raise SystemExit(f"--layers must be a comma-separated subset of {sorted(valid_layers)}")
    return LaunchReadinessConfig(
        app_url=str(args.app_url).rstrip("/"),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        browsers=tuple(browser_values),  # type: ignore[arg-type]
        layers=tuple(layer_values),  # type: ignore[arg-type]
        headed=bool(args.headed),
        slow_mo_ms=max(int(args.slow_mo_ms), 0),
        author_timeout_seconds=max(float(args.author_timeout_seconds), 5.0),
        turn_timeout_seconds=max(float(args.turn_timeout_seconds), 5.0),
        max_play_turns=max(int(args.max_play_turns), 1),
        parallel_worker_count=max(int(args.parallel_worker_count), 1),
        seed=args.seed,
    )


def _hash_url(app_url: str, route: str) -> str:
    if route.startswith("#"):
        return f"{app_url}/{route}"
    return f"{app_url}/#{route.lstrip('/')}"


def _load_playwright():
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import expect, sync_playwright

    return sync_playwright, expect, PlaywrightTimeoutError, PlaywrightError


class ObservedPage:
    def __init__(self, page: Any, app_url: str) -> None:
        self.page = page
        self.app_url = app_url.rstrip("/")
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.failed_requests: list[dict[str, Any]] = []
        self.http_errors: list[dict[str, Any]] = []
        page.on("console", self._on_console)
        page.on("pageerror", self._on_page_error)
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

    def _should_ignore_url(self, url: str) -> bool:
        normalized = url.casefold()
        return normalized.endswith("/favicon.ico")

    def _is_product_request(self, url: str) -> bool:
        parsed = urlparse(url)
        app_origin = urlparse(self.app_url)
        if parsed.scheme and parsed.netloc and (parsed.scheme, parsed.netloc) != (app_origin.scheme, app_origin.netloc):
            return False
        return parsed.path.startswith("/author") or parsed.path.startswith("/stories") or parsed.path.startswith("/play")

    def _on_console(self, msg: Any) -> None:
        if msg.type != "error":
            return
        text = msg.text()
        if "favicon.ico" in text:
            return
        self.console_errors.append(text)

    def _on_page_error(self, error: Exception) -> None:
        self.page_errors.append(str(error))

    def _on_request_failed(self, request: Any) -> None:
        url = request.url
        if self._should_ignore_url(url):
            return
        if self._is_product_request(url):
            self.failed_requests.append(
                {
                    "url": url,
                    "method": request.method,
                    "failure": request.failure,
                }
            )

    def _on_response(self, response: Any) -> None:
        url = response.url
        if self._should_ignore_url(url):
            return
        if self._is_product_request(url) and response.status >= 400:
            self.http_errors.append(
                {
                    "url": url,
                    "status": response.status,
                    "status_text": response.status_text(),
                }
            )

    def assert_clean(self) -> None:
        failures: list[str] = []
        if self.console_errors:
            failures.append(f"console_errors={len(self.console_errors)}")
        if self.page_errors:
            failures.append(f"page_errors={len(self.page_errors)}")
        if self.failed_requests:
            failures.append(f"failed_requests={len(self.failed_requests)}")
        if self.http_errors:
            failures.append(f"http_errors={len(self.http_errors)}")
        if failures:
            raise RuntimeError("browser runtime policy failed: " + ", ".join(failures))

    def dump(self) -> dict[str, Any]:
        return {
            "console_errors": list(self.console_errors),
            "page_errors": list(self.page_errors),
            "failed_requests": list(self.failed_requests),
            "http_errors": list(self.http_errors),
        }


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return normalized or "scenario"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def build_parallel_worker_specs(*, worker_count: int, seed: int | None = None) -> list[ParallelWorkerSpec]:
    if worker_count < 3:
        return [
            ParallelWorkerSpec(worker_id=f"worker_{index + 1:02d}", mode="mixed")
            for index in range(worker_count)
        ]
    author_count = max(1, round(worker_count * 0.4))
    play_count = max(1, round(worker_count * 0.4))
    if author_count + play_count >= worker_count:
        play_count = max(1, worker_count - author_count - 1)
    mixed_count = worker_count - author_count - play_count
    while mixed_count < 1 and author_count > 1:
        author_count -= 1
        mixed_count = worker_count - author_count - play_count
    rng = Random(seed) if seed is not None else Random()
    base_seeds = build_story_seed_batch(rng=rng, story_count=5)
    author_seeds: list[str] = []
    while len(author_seeds) < author_count + mixed_count:
        for generated in base_seeds:
            variant_index = len(author_seeds) // len(base_seeds) + 1
            suffix = "" if variant_index == 1 else f" Variant {variant_index}."
            author_seeds.append(f"{generated.seed}{suffix}")
            if len(author_seeds) >= author_count + mixed_count:
                break
    specs: list[ParallelWorkerSpec] = []
    author_seed_index = 0
    for index in range(author_count):
        specs.append(
            ParallelWorkerSpec(
                worker_id=f"author_{index + 1:02d}",
                mode="author",
                prompt_seed=author_seeds[author_seed_index],
            )
        )
        author_seed_index += 1
    for index in range(play_count):
        specs.append(
            ParallelWorkerSpec(
                worker_id=f"play_{index + 1:02d}",
                mode="play",
            )
        )
    for index in range(mixed_count):
        specs.append(
            ParallelWorkerSpec(
                worker_id=f"mixed_{index + 1:02d}",
                mode="mixed",
                prompt_seed=author_seeds[author_seed_index],
            )
        )
        author_seed_index += 1
    return specs


def _wait_for_route(page: Any, route_fragment: str, timeout_seconds: float) -> None:
    page.wait_for_url(re.compile(re.escape(route_fragment)), timeout=int(timeout_seconds * 1000))


def _open_create_story(page: Any, app_url: str, timeout_seconds: float) -> None:
    page.goto(_hash_url(app_url, "#/create-story"), wait_until="domcontentloaded")
    page.get_by_role("heading", name="Input the story seed").wait_for(timeout=int(timeout_seconds * 1000))


def _run_create_preview(page: Any, seed: str, timeout_seconds: float) -> dict[str, Any]:
    textarea = page.locator("textarea.create-seed-input")
    textarea.wait_for(timeout=int(timeout_seconds * 1000))
    textarea.fill(seed)
    page.get_by_role("button", name="Preview Story").click()
    page.get_by_role("button", name="Start Authoring").wait_for(timeout=int(timeout_seconds * 1000))
    title = page.locator(".preview-title-lockup h3").text_content() or ""
    return {
        "preview_title": title.strip(),
    }


def _start_author_job(page: Any, timeout_seconds: float) -> str:
    page.get_by_role("button", name="Start Authoring").click()
    _wait_for_route(page, "#/author-jobs/", timeout_seconds)
    match = re.search(r"#/author-jobs/([^/?]+)", page.url)
    if match is None:
        raise RuntimeError("author loading route did not include a job id")
    return match.group(1)


def _wait_for_publish_ready(page: Any, timeout_seconds: float) -> dict[str, Any]:
    publish_button = page.get_by_role("button", name="Publish to Library")
    publish_button.wait_for(timeout=int(timeout_seconds * 1000))
    return {
        "story_title": (page.locator(".loading-context-card h2").text_content() or "").strip(),
        "job_url": page.url,
    }


def _publish_and_open_detail(page: Any, timeout_seconds: float) -> dict[str, Any]:
    page.get_by_role("button", name="Publish to Library").click()
    _wait_for_route(page, "#/stories", timeout_seconds)
    selected_card = page.locator(".story-card.is-selected").first
    selected_card.wait_for(timeout=int(timeout_seconds * 1000))
    story_title = (selected_card.locator("h4").text_content() or "").strip()
    selected_card.click()
    _wait_for_route(page, "#/stories/", timeout_seconds)
    page.get_by_role("button", name="Start Play Session").wait_for(timeout=int(timeout_seconds * 1000))
    match = re.search(r"#/stories/([^/?]+)", page.url)
    return {
        "story_title": story_title,
        "story_id": match.group(1) if match else None,
        "story_url": page.url,
    }


def _open_library(page: Any, app_url: str, timeout_seconds: float) -> None:
    page.goto(_hash_url(app_url, "#/stories"), wait_until="domcontentloaded")
    page.get_by_role("heading", name="Library", exact=True).wait_for(timeout=int(timeout_seconds * 1000))


def _library_has_story(page: Any) -> bool:
    return page.locator(".story-card").count() > 0


def _ensure_library_story_exists(page: Any, app_url: str, author_timeout_seconds: float) -> dict[str, Any]:
    _open_library(page, app_url, 15.0)
    if _library_has_story(page):
        first_card = page.locator(".story-card").first
        return {
            "provisioned": False,
            "story_title": (first_card.locator("h4").text_content() or "").strip(),
        }
    seed = build_story_seed_batch(story_count=1)[0].seed
    _open_create_story(page, app_url, 15.0)
    _run_create_preview(page, seed, 30.0)
    _start_author_job(page, 15.0)
    _wait_for_publish_ready(page, author_timeout_seconds)
    detail = _publish_and_open_detail(page, 15.0)
    return {
        "provisioned": True,
        "story_title": detail.get("story_title"),
    }


def _open_first_story_detail(page: Any, app_url: str, timeout_seconds: float) -> dict[str, Any]:
    _open_library(page, app_url, timeout_seconds)
    card = page.locator(".story-card").first
    card.wait_for(timeout=int(timeout_seconds * 1000))
    title = (card.locator("h4").text_content() or "").strip()
    card.click()
    _wait_for_route(page, "#/stories/", timeout_seconds)
    return {
        "story_title": title,
        "story_url": page.url,
    }


def _start_play_session(page: Any, timeout_seconds: float) -> dict[str, Any]:
    page.get_by_role("button", name="Start Play Session").click()
    _wait_for_route(page, "#/play/sessions/", timeout_seconds)
    page.locator(".play-input-dock__textarea").wait_for(timeout=int(timeout_seconds * 1000))
    match = re.search(r"#/play/sessions/([^/?]+)", page.url)
    return {
        "session_id": match.group(1) if match else None,
        "session_url": page.url,
        "story_title": (page.locator(".play-sidebar-stats__meta p").first.text_content() or "").strip(),
    }


def _history_count(page: Any) -> int:
    return page.locator(".play-transcript__entry").count()


def _submit_turn(
    page: Any,
    *,
    turn_timeout_seconds: float,
    input_text: str | None = None,
    use_first_suggestion: bool = True,
) -> dict[str, Any]:
    initial_count = _history_count(page)
    if use_first_suggestion and page.locator(".play-suggestion").count() > 0:
        page.locator(".play-suggestion").first.click()
    if input_text is not None:
        page.locator(".play-input-dock__textarea").fill(input_text)
    textarea = page.locator(".play-input-dock__textarea")
    if not textarea.input_value().strip():
        textarea.fill("I force the chamber to confront the strongest available record before the panic spreads any further.")
    submit_button = page.locator(".play-input-dock__submit")
    submit_button.click()
    pending_status = page.locator(".play-input-dock__status")
    pending_status.wait_for(timeout=5000)
    pending_status.wait_for(state="hidden", timeout=int(turn_timeout_seconds * 1000))
    page.wait_for_function(
        """
        (previousCount) => {
          const currentCount = document.querySelectorAll('.play-transcript__entry').length
          return currentCount >= previousCount + 2 || Boolean(document.querySelector('.play-ending-card'))
        }
        """,
        arg=initial_count,
        timeout=int(turn_timeout_seconds * 1000),
    )
    return {
        "history_count_after": _history_count(page),
        "ending_visible": page.locator(".play-ending-card").count() > 0,
        "submit_status_text": (page.locator(".play-input-dock__actions span").text_content() or "").strip(),
    }


def _play_until_terminal(page: Any, *, max_turns: int, turn_timeout_seconds: float) -> dict[str, Any]:
    turn_summaries: list[dict[str, Any]] = []
    for turn_index in range(max_turns):
        textarea = page.locator(".play-input-dock__textarea")
        if textarea.is_disabled() or page.locator(".play-ending-card").count() > 0:
            break
        turn_summaries.append(_submit_turn(page, turn_timeout_seconds=turn_timeout_seconds))
        if page.locator(".play-ending-card").count() > 0:
            break
        if turn_index >= max_turns - 1:
            break
    return {
        "turns_submitted": len(turn_summaries),
        "ended": page.locator(".play-ending-card").count() > 0 or page.locator(".play-input-dock__textarea").is_disabled(),
        "turn_summaries": turn_summaries,
    }


def _scenario_env_gate(page: Any, app_url: str, config: LaunchReadinessConfig) -> dict[str, Any]:
    response = page.context.request.get(f"{app_url}/health", timeout=int(config.turn_timeout_seconds * 1000))
    if not response.ok:
        raise RuntimeError(f"/health failed with status {response.status}")
    health_payload = response.json()
    _open_create_story(page, app_url, 15.0)
    top_nav = page.locator(".studio-topbar__nav")
    top_nav.get_by_role("button", name="Create", exact=True).wait_for(timeout=5000)
    top_nav.get_by_role("button", name="Library", exact=True).wait_for(timeout=5000)
    return {
        "health": health_payload,
        "current_url": page.url,
    }


def _scenario_core_full_flow(page: Any, app_url: str, config: LaunchReadinessConfig, *, seed: str | None = None) -> dict[str, Any]:
    resolved_seed = seed or build_story_seed_batch(story_count=1)[0].seed
    _open_create_story(page, app_url, 15.0)
    preview = _run_create_preview(page, resolved_seed, 30.0)
    job_id = _start_author_job(page, 15.0)
    author = _wait_for_publish_ready(page, config.author_timeout_seconds)
    detail = _publish_and_open_detail(page, 20.0)
    play = _start_play_session(page, 20.0)
    first_turn = _submit_turn(page, turn_timeout_seconds=config.turn_timeout_seconds)
    terminal = _play_until_terminal(page, max_turns=max(config.max_play_turns - 1, 1), turn_timeout_seconds=config.turn_timeout_seconds)
    if not terminal["ended"]:
        raise RuntimeError("play session did not reach a terminal state within the configured turn budget")
    return {
        "seed": resolved_seed,
        "preview": preview,
        "job_id": job_id,
        "author": author,
        "detail": detail,
        "play": play,
        "first_turn": first_turn,
        "terminal": terminal,
        "session_completed": terminal["ended"],
    }


def _scenario_library_search_filter(page: Any, app_url: str, config: LaunchReadinessConfig) -> dict[str, Any]:
    _ensure_library_story_exists(page, app_url, config.author_timeout_seconds)
    _open_library(page, app_url, 15.0)
    first_card = page.locator(".story-card").first
    first_card.wait_for(timeout=15000)
    story_title = (first_card.locator("h4").text_content() or "").strip()
    theme_text = (first_card.locator(".chip").first.text_content() or "").strip()
    query = next((word for word in re.split(r"\\s+", story_title) if len(word) >= 4), story_title)
    page.locator(".studio-search input").fill(query)
    page.wait_for_timeout(700)
    filtered_card = page.locator(".story-card").first
    filtered_card.wait_for(timeout=15000)
    filtered_title = (filtered_card.locator("h4").text_content() or "").strip()
    page.locator(".library-filter select").select_option(value=theme_text)
    page.wait_for_timeout(700)
    themed_card = page.locator(".story-card").first
    themed_card.wait_for(timeout=15000)
    themed_chip = (themed_card.locator(".chip").first.text_content() or "").strip()
    return {
        "search_query": query,
        "search_result_title": filtered_title,
        "theme_filter": theme_text,
        "theme_result": themed_chip,
    }


def _scenario_author_refresh(page: Any, app_url: str, config: LaunchReadinessConfig) -> dict[str, Any]:
    seed = build_story_seed_batch(story_count=1)[0].seed
    _open_create_story(page, app_url, 15.0)
    _run_create_preview(page, seed, 30.0)
    job_id = _start_author_job(page, 15.0)
    page.locator(".loading-progress-meta").wait_for(timeout=10000)
    page.reload(wait_until="domcontentloaded")
    _wait_for_route(page, f"#/author-jobs/{job_id}", 20.0)
    author = _wait_for_publish_ready(page, config.author_timeout_seconds)
    return {
        "job_id": job_id,
        "job_url_after_reload": page.url,
        "story_title": author["story_title"],
    }


def _scenario_play_refresh(page: Any, app_url: str, config: LaunchReadinessConfig) -> dict[str, Any]:
    _ensure_library_story_exists(page, app_url, config.author_timeout_seconds)
    detail = _open_first_story_detail(page, app_url, 15.0)
    play = _start_play_session(page, 20.0)
    _submit_turn(page, turn_timeout_seconds=config.turn_timeout_seconds)
    history_before = _history_count(page)
    session_url = page.url
    page.reload(wait_until="domcontentloaded")
    _wait_for_route(page, session_url.split("/#/", 1)[-1], 20.0)
    page.locator(".play-transcript").wait_for(timeout=15000)
    history_after = _history_count(page)
    if history_after < history_before:
        raise RuntimeError("play transcript shrank after refresh")
    new_page = page.context.new_page()
    try:
        new_page.goto(session_url, wait_until="domcontentloaded")
        new_page.locator(".play-transcript").wait_for(timeout=15000)
        direct_history = new_page.locator(".play-transcript__entry").count()
    finally:
        new_page.close()
    if direct_history < history_before:
        raise RuntimeError("direct session open did not rehydrate transcript history")
    return {
        "story_detail": detail,
        "play": play,
        "history_before_reload": history_before,
        "history_after_reload": history_after,
        "history_after_direct_open": direct_history,
        "session_url": session_url,
    }


def _run_parallel_worker(
    worker: ParallelWorkerSpec,
    config: LaunchReadinessConfig,
    browser_name: BrowserName,
    output_root: Path,
) -> dict[str, Any]:
    sync_playwright, _expect, PlaywrightTimeoutError, PlaywrightError = _load_playwright()
    worker_dir = output_root / "parallel" / browser_name / worker.worker_id
    worker_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.perf_counter()
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name)
        browser = browser_type.launch(headless=not config.headed, slow_mo=config.slow_mo_ms)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        observed = ObservedPage(page, config.app_url)
        try:
            _ensure_library_story_exists(page, config.app_url, config.author_timeout_seconds)
            if worker.mode == "author":
                _scenario_core_full_flow(page, config.app_url, config, seed=worker.prompt_seed)
            elif worker.mode == "play":
                _open_first_story_detail(page, config.app_url, 20.0)
                _start_play_session(page, 20.0)
                _submit_turn(page, turn_timeout_seconds=config.turn_timeout_seconds)
                page.reload(wait_until="domcontentloaded")
                page.locator(".play-transcript").wait_for(timeout=15000)
                _submit_turn(page, turn_timeout_seconds=config.turn_timeout_seconds)
            else:
                _scenario_core_full_flow(page, config.app_url, config, seed=worker.prompt_seed)
            observed.assert_clean()
            context.tracing.stop()
            _write_json(worker_dir / "observed.json", observed.dump())
            browser.close()
            return {
                "worker_id": worker.worker_id,
                "mode": worker.mode,
                "passed": True,
                "elapsed_seconds": round(time.perf_counter() - started_at, 3),
            }
        except (Exception, PlaywrightTimeoutError, PlaywrightError) as exc:  # noqa: BLE001
            try:
                page.screenshot(path=str(worker_dir / "failure.png"), full_page=True)
            except Exception:  # noqa: BLE001
                pass
            try:
                context.tracing.stop(path=str(worker_dir / "trace.zip"))
            except Exception:  # noqa: BLE001
                pass
            _write_json(worker_dir / "observed.json", observed.dump())
            browser.close()
            return {
                "worker_id": worker.worker_id,
                "mode": worker.mode,
                "passed": False,
                "elapsed_seconds": round(time.perf_counter() - started_at, 3),
                "error": str(exc),
            }


def _scenario_parallel(config: LaunchReadinessConfig, browser_name: BrowserName, output_root: Path) -> dict[str, Any]:
    specs = build_parallel_worker_specs(worker_count=config.parallel_worker_count, seed=config.seed)
    worker_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(specs)) as executor:
        futures = [
            executor.submit(_run_parallel_worker, spec, config, browser_name, output_root)
            for spec in specs
        ]
        for future in as_completed(futures):
            worker_results.append(future.result())
    worker_results.sort(key=lambda item: item["worker_id"])
    failures = [item for item in worker_results if not item["passed"]]
    return {
        "worker_count": len(specs),
        "workers": worker_results,
        "passed_workers": len(worker_results) - len(failures),
        "failed_workers": len(failures),
        "passed": len(failures) == 0,
    }


def _run_browser_scenario(
    *,
    scenario_id: str,
    scenario_name: str,
    layer: LaunchLayer,
    browser_name: BrowserName,
    config: LaunchReadinessConfig,
    output_root: Path,
    scenario_fn: Any,
) -> dict[str, Any]:
    sync_playwright, _expect, PlaywrightTimeoutError, PlaywrightError = _load_playwright()
    scenario_slug = _slugify(f"{layer}_{scenario_id}_{browser_name}")
    scenario_dir = output_root / scenario_slug
    scenario_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.perf_counter()
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name)
        browser = browser_type.launch(headless=not config.headed, slow_mo=config.slow_mo_ms)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        observed = ObservedPage(page, config.app_url)
        try:
            details = scenario_fn(page, config.app_url, config)
            observed.assert_clean()
            context.tracing.stop()
            _write_json(scenario_dir / "observed.json", observed.dump())
            _write_json(scenario_dir / "details.json", details)
            browser.close()
            return {
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "layer": layer,
                "browser": browser_name,
                "passed": True,
                "elapsed_seconds": round(time.perf_counter() - started_at, 3),
                "details": details,
                "artifacts_dir": str(scenario_dir.relative_to(REPO_ROOT)),
            }
        except (Exception, PlaywrightTimeoutError, PlaywrightError) as exc:  # noqa: BLE001
            try:
                page.screenshot(path=str(scenario_dir / "failure.png"), full_page=True)
            except Exception:  # noqa: BLE001
                pass
            try:
                context.tracing.stop(path=str(scenario_dir / "trace.zip"))
            except Exception:  # noqa: BLE001
                pass
            _write_json(scenario_dir / "observed.json", observed.dump())
            browser.close()
            return {
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "layer": layer,
                "browser": browser_name,
                "passed": False,
                "elapsed_seconds": round(time.perf_counter() - started_at, 3),
                "error": str(exc),
                "artifacts_dir": str(scenario_dir.relative_to(REPO_ROOT)),
            }


def run_launch_readiness_suite(config: LaunchReadinessConfig) -> dict[str, Any]:
    timestamp = _now_stamp()
    output_root = config.output_dir / timestamp
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    scenarios: list[tuple[str, str, LaunchLayer, Any]] = []
    if "env" in config.layers:
        scenarios.append(("PLW-ENV-001", "Environment Gate", "env", _scenario_env_gate))
    if "core" in config.layers:
        scenarios.extend(
            [
                ("PLW-CORE-001", "Core Author Publish Play Flow", "core", _scenario_core_full_flow),
                ("PLW-CORE-002", "Library Search And Theme Filter", "core", _scenario_library_search_filter),
            ]
        )
    if "recovery" in config.layers:
        scenarios.extend(
            [
                ("PLW-REC-001", "Author Refresh Recovery", "recovery", _scenario_author_refresh),
                ("PLW-REC-002", "Play Refresh Recovery", "recovery", _scenario_play_refresh),
            ]
        )
    for browser_name in config.browsers:
        for scenario_id, scenario_name, layer, scenario_fn in scenarios:
            results.append(
                _run_browser_scenario(
                    scenario_id=scenario_id,
                    scenario_name=scenario_name,
                    layer=layer,
                    browser_name=browser_name,
                    config=config,
                    output_root=output_root,
                    scenario_fn=scenario_fn,
                )
            )
    if "parallel" in config.layers:
        results.append(
            {
                "scenario_id": "PLW-PAR-001",
                "scenario_name": "Parallel Mixed Launch Run",
                "layer": "parallel",
                "browser": config.browsers[0],
                **_scenario_parallel(config, config.browsers[0], output_root),
                "artifacts_dir": str((output_root / "parallel" / config.browsers[0]).relative_to(REPO_ROOT)),
            }
        )
    passed = all(bool(item.get("passed")) for item in results)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_url": config.app_url,
        "config": {
            "browsers": list(config.browsers),
            "layers": list(config.layers),
            "headed": config.headed,
            "slow_mo_ms": config.slow_mo_ms,
            "author_timeout_seconds": config.author_timeout_seconds,
            "turn_timeout_seconds": config.turn_timeout_seconds,
            "max_play_turns": config.max_play_turns,
            "parallel_worker_count": config.parallel_worker_count,
            "seed": config.seed,
        },
        "passed": passed,
        "results": results,
        "output_root": str(output_root),
    }


def _markdown_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# Playwright Launch Readiness",
        "",
        f"- App URL: `{payload['app_url']}`",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Passed: `{payload['passed']}`",
        "",
        "## Results",
        "",
    ]
    for item in payload.get("results", []):
        line = (
            f"- `{item['scenario_id']}` `{item['scenario_name']}` "
            f"browser=`{item['browser']}` layer=`{item['layer']}` passed=`{item.get('passed')}` "
            f"elapsed=`{item.get('elapsed_seconds')}`"
        )
        if item.get("failed_workers") is not None:
            line += f" failed_workers=`{item['failed_workers']}`"
        if item.get("error"):
            line += f" error=`{item['error']}`"
        lines.append(line)
    return "\n".join(lines) + "\n"


def write_artifacts(config: LaunchReadinessConfig, payload: dict[str, Any]) -> tuple[Path, Path]:
    output_root = Path(str(payload["output_root"]))
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "summary.json"
    md_path = output_root / "summary.md"
    _write_json(json_path, payload)
    md_path.write_text(_markdown_summary(payload))
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_launch_readiness_suite(config)
    json_path, md_path = write_artifacts(config, payload)
    print(
        json.dumps(
            {
                "passed": payload["passed"],
                "json": str(json_path),
                "markdown": str(md_path),
                "output_root": payload["output_root"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

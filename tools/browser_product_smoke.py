from __future__ import annotations

import argparse
import json
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse


StoryLanguage = Literal["en", "zh"]

DEFAULT_APP_URL = "http://127.0.0.1:4174"
DEFAULT_AUTHOR_TIMEOUT_SECONDS = 240.0
DEFAULT_ACTION_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_PLAY_TURNS = 10


class BrowserProductSmokeFailure(RuntimeError):
    def __init__(self, message: str, *, summary: dict[str, Any]) -> None:
        super().__init__(message)
        self.summary = summary


@dataclass(frozen=True)
class BrowserProductSmokeConfig:
    app_url: str
    ui_language: StoryLanguage
    output_path: Path | None
    headed: bool
    slow_mo_ms: int
    author_timeout_seconds: float
    action_timeout_seconds: float
    max_play_turns: int


def parse_args(argv: list[str] | None = None) -> BrowserProductSmokeConfig:
    parser = argparse.ArgumentParser(description="Run a real browser FE/BE smoke against the current product flow.")
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    parser.add_argument("--ui-language", choices=("en", "zh"), default="en")
    parser.add_argument("--output-path")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--author-timeout-seconds", type=float, default=DEFAULT_AUTHOR_TIMEOUT_SECONDS)
    parser.add_argument("--action-timeout-seconds", type=float, default=DEFAULT_ACTION_TIMEOUT_SECONDS)
    parser.add_argument("--max-play-turns", type=int, default=DEFAULT_MAX_PLAY_TURNS)
    args = parser.parse_args(argv)
    return BrowserProductSmokeConfig(
        app_url=str(args.app_url).rstrip("/"),
        ui_language=str(args.ui_language),  # type: ignore[arg-type]
        output_path=Path(args.output_path).expanduser().resolve() if args.output_path else None,
        headed=bool(args.headed),
        slow_mo_ms=max(int(args.slow_mo_ms), 0),
        author_timeout_seconds=max(float(args.author_timeout_seconds), 30.0),
        action_timeout_seconds=max(float(args.action_timeout_seconds), 5.0),
        max_play_turns=max(int(args.max_play_turns), 1),
    )


def _hash_url(app_url: str, route: str) -> str:
    if route.startswith("#"):
        return f"{app_url}/{route}"
    return f"{app_url}/#{route.lstrip('/')}"


def _load_playwright():
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    return sync_playwright, PlaywrightTimeoutError, PlaywrightError


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
        return url.casefold().endswith("/favicon.ico")

    def _is_product_request(self, url: str) -> bool:
        parsed = urlparse(url)
        app_origin = urlparse(self.app_url)
        if parsed.scheme and parsed.netloc and (parsed.scheme, parsed.netloc) != (app_origin.scheme, app_origin.netloc):
            return False
        return parsed.path.startswith(("/auth", "/me", "/author", "/stories", "/play"))

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


def _write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy(language: StoryLanguage) -> dict[str, str]:
    if language == "zh":
        return {
            "create_account_tab": "注册账号",
            "display_name": "显示名称",
            "email": "邮箱",
            "password": "密码",
            "create_account_submit": "注册账号",
            "spark_action": "点火一个种子",
            "spark_again": "再来一个",
            "spark_loading": "点火中...",
            "preview_action": "生成预览",
            "draft_action": "生成草稿",
            "cast_extraction_review": "Cast Extraction Review",
            "canonical_anchor": "Canonical Anchor",
            "current_drive": "Current Drive",
            "red_line": "Red Line",
            "pressure_signature": "Pressure Signature",
            "generate_suggestion": "生成建议",
            "apply_changes": "应用改动",
            "undo": "撤销",
            "changes_applied": "改动已应用",
            "changes_undone": "改动已撤销",
            "publish_to_library": "发布到故事库",
            "lead_dossier": "主角档案",
            "cast_files": "人物名单",
            "back_to_library": "返回故事库",
            "start_play": "开始试玩",
            "transcript": "故事进展",
            "archive": "回顾记录",
            "full_transcript": "完整记录",
            "play_loading": "正在载入试玩会话",
            "story_library": "故事库",
        }
    return {
        "create_account_tab": "Create Account",
        "display_name": "Display Name",
        "email": "Email",
        "password": "Password",
        "create_account_submit": "Create Account",
        "spark_action": "Spark a seed",
        "spark_again": "Spark another",
        "spark_loading": "Sparking...",
        "preview_action": "Generate Preview",
        "draft_action": "Generate Draft",
        "cast_extraction_review": "Cast Extraction Review",
        "canonical_anchor": "Canonical Anchor",
        "current_drive": "Current Drive",
        "red_line": "Red Line",
        "pressure_signature": "Pressure Signature",
        "generate_suggestion": "Generate suggestion",
        "apply_changes": "Apply changes",
        "undo": "Undo",
        "changes_applied": "Changes applied",
        "changes_undone": "Changes undone",
        "publish_to_library": "Publish to Library",
        "lead_dossier": "Lead Dossier",
        "cast_files": "Cast Files",
        "back_to_library": "Back to Library",
        "start_play": "Start Play Session",
        "transcript": "Story So Far",
        "archive": "Session Archive",
        "full_transcript": "Full Transcript",
        "play_loading": "Loading play session",
        "story_library": "Library",
    }


def _route_name(page: Any) -> str | None:
    route_value = page.locator("[data-route]").first.get_attribute("data-route")
    return route_value.strip() if route_value else None


def _wait_for_route(page: Any, route_name: str, *, timeout_ms: int) -> None:
    page.locator(f'[data-route="{route_name}"]').first.wait_for(state="visible", timeout=timeout_ms)


def _numeric_text(value: str | None) -> int | None:
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else None


def _wait_for_author_workspace(page: Any, copy: dict[str, str], *, timeout_ms: int) -> None:
    page.get_by_text(copy["cast_extraction_review"], exact=True).wait_for(state="visible", timeout=timeout_ms)


def _select_first_suggested_action(page: Any) -> str | None:
    suggestion = page.locator(".play-suggestion").first
    if suggestion.count() == 0:
        return None
    label = suggestion.locator("strong").text_content()
    suggestion.click()
    return str(label or "").strip() or None


def _submit_turn_from_ui(page: Any, fallback_input: str, *, timeout_ms: int) -> dict[str, Any]:
    transcript_entries_before = page.locator(".play-transcript__entry").count()
    suggested_label = _select_first_suggested_action(page)
    textarea = page.locator(".play-input-dock__textarea")
    if not suggested_label:
        textarea.fill(fallback_input)
    submit = page.locator(".play-input-dock__submit")
    submit.click()
    textarea.wait_for(state="attached", timeout=timeout_ms)
    page.wait_for_function(
        """
        () => {
          if (document.querySelector('.play-transcript-column--archive')) {
            return true;
          }
          const textarea = document.querySelector('.play-input-dock__textarea');
          return Boolean(textarea) && !textarea.disabled;
        }
        """,
        timeout=timeout_ms,
    )
    page.wait_for_timeout(250)
    transcript_entries_after = page.locator(".play-transcript__entry").count()
    return {
        "suggested_label": suggested_label,
        "transcript_entries_before": transcript_entries_before,
        "transcript_entries_after": transcript_entries_after,
        "completed": page.locator(".play-transcript-column--archive").count() > 0,
    }


def _scroll_probe(page: Any, button_label: str) -> dict[str, float]:
    page.get_by_role("button", name=button_label).click()
    page.wait_for_timeout(300)
    metrics = page.evaluate(
        """
        () => {
          const target = document.querySelector('#play-transcript');
          const rect = target ? target.getBoundingClientRect() : null;
          return {
            scrollY: window.scrollY,
            top: rect ? rect.top : null,
          };
        }
        """
    )
    payload = dict(metrics or {})
    return {
        "scroll_y": float(payload.get("scrollY") or 0.0),
        "target_top": float(payload.get("top") or 0.0),
    }


def run_browser_product_smoke(config: BrowserProductSmokeConfig) -> dict[str, Any]:
    sync_playwright, PlaywrightTimeoutError, PlaywrightError = _load_playwright()
    copy = _copy(config.ui_language)
    summary: dict[str, Any] = {
        "ok": False,
        "app_url": config.app_url,
        "ui_language": config.ui_language,
        "failed_step": None,
        "steps": {},
        "ids": {},
        "create": {},
        "author": {},
        "detail": {},
        "play": {},
        "observer": {},
    }
    current_step = "launch_browser"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not config.headed, slow_mo=config.slow_mo_ms)
            context = browser.new_context(viewport={"width": 1440, "height": 1100})
            page = context.new_page()
            observer = ObservedPage(page, config.app_url)
            try:
                current_step = "open_create_story"
                page.goto(_hash_url(config.app_url, "#/create-story"), wait_until="domcontentloaded")
                _wait_for_route(page, "auth", timeout_ms=int(config.action_timeout_seconds * 1000))
                summary["steps"]["open_create_story"] = {"route": _route_name(page)}

                current_step = "register"
                page.get_by_role("button", name=copy["create_account_tab"]).click()
                page.get_by_label(copy["display_name"]).fill("Integration Gate")
                email = f"browser-smoke-{secrets.token_hex(6)}@bench.local"
                page.get_by_label(copy["email"]).fill(email)
                page.get_by_label(copy["password"]).fill("BenchPass123!")
                page.get_by_role("button", name=copy["create_account_submit"]).click()
                _wait_for_route(page, "create-story", timeout_ms=int(config.action_timeout_seconds * 1000))
                summary["steps"]["register"] = {"email": email, "route": _route_name(page)}

                current_step = "spark_first"
                seed_input = page.locator("#story-seed-input")
                preview_button = page.get_by_role("button", name=copy["preview_action"])
                spark_button = page.get_by_role("button", name=copy["spark_action"])
                started_at = time.perf_counter()
                spark_button.click()
                page.get_by_role("button", name=copy["spark_loading"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                if not preview_button.is_disabled():
                    raise RuntimeError("Generate Preview should be disabled while Spark is in flight")
                page.wait_for_function(
                    "() => !!document.querySelector('#story-seed-input')?.value.trim()",
                    timeout=int(config.action_timeout_seconds * 1000),
                )
                first_seed = str(seed_input.input_value()).strip()
                if not first_seed:
                    raise RuntimeError("Spark did not write a seed into the textarea")
                page.get_by_role("button", name=copy["spark_again"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                page.wait_for_function(
                    "() => !document.querySelector('#story-seed-input')?.readOnly",
                    timeout=int(config.action_timeout_seconds * 1000),
                )
                summary["steps"]["spark_first"] = {
                    "elapsed_seconds": round(time.perf_counter() - started_at, 3),
                    "seed_length": len(first_seed),
                }
                summary["create"]["first_seed"] = first_seed
                if page.get_by_role("button", name=copy["draft_action"]).count() > 0:
                    raise RuntimeError("Spark auto-triggered preview unexpectedly")

                current_step = "spark_overwrite_cancel"
                with page.expect_dialog() as cancel_dialog:
                    page.get_by_role("button", name=copy["spark_again"]).click()
                cancel_dialog.value.dismiss()
                page.wait_for_timeout(250)
                cancelled_seed = str(seed_input.input_value()).strip()
                if cancelled_seed != first_seed:
                    raise RuntimeError("Cancelling Spark overwrite changed the seed unexpectedly")
                summary["steps"]["spark_overwrite_cancel"] = {"seed_unchanged": True}

                current_step = "spark_overwrite_accept"
                with page.expect_dialog() as accept_dialog:
                    page.get_by_role("button", name=copy["spark_again"]).click()
                accept_dialog.value.accept()
                page.get_by_role("button", name=copy["spark_loading"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                page.wait_for_function(
                    "(previous) => (document.querySelector('#story-seed-input')?.value || '').trim() && (document.querySelector('#story-seed-input')?.value || '').trim() !== previous",
                    arg=first_seed,
                    timeout=int(config.action_timeout_seconds * 1000),
                )
                second_seed = str(seed_input.input_value()).strip()
                if not second_seed or second_seed == first_seed:
                    raise RuntimeError("Accepted Spark overwrite did not replace the seed")
                page.get_by_role("button", name=copy["spark_again"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                page.wait_for_function(
                    "() => !document.querySelector('#story-seed-input')?.readOnly",
                    timeout=int(config.action_timeout_seconds * 1000),
                )
                summary["steps"]["spark_overwrite_accept"] = {"seed_replaced": True, "seed_length": len(second_seed)}
                summary["create"]["second_seed"] = second_seed

                current_step = "preview"
                page.get_by_role("button", name=copy["preview_action"]).click()
                page.get_by_role("button", name=copy["draft_action"]).wait_for(state="visible", timeout=int(config.author_timeout_seconds * 1000))
                expected_npc_count = _numeric_text(
                    page.locator(".preview-stat-grid > div").filter(has_text="NPC").locator("strong").first.text_content()
                )
                expected_beat_count = _numeric_text(
                    page.locator(".preview-stat-grid > div").filter(has_text="Beat").locator("strong").first.text_content()
                )
                summary["steps"]["preview"] = {"ready": True}
                summary["create"]["expected_npc_count"] = expected_npc_count
                summary["create"]["expected_beat_count"] = expected_beat_count

                current_step = "create_author_job"
                page.get_by_role("button", name=copy["draft_action"]).click()
                _wait_for_route(page, "author-loading", timeout_ms=int(config.action_timeout_seconds * 1000))
                loading_meta = page.locator(".loading-progress-meta span")
                initial_stage_label = str(loading_meta.nth(0).text_content() or "").strip() if loading_meta.count() >= 1 else ""
                initial_completion = str(loading_meta.nth(1).text_content() or "").strip() if loading_meta.count() >= 2 else ""
                summary["steps"]["create_author_job"] = {
                    "route": _route_name(page),
                    "initial_stage_label": initial_stage_label,
                    "initial_completion": initial_completion,
                }
                summary["author"]["initial_loading_stage_label"] = initial_stage_label
                summary["author"]["initial_loading_completion"] = initial_completion

                current_step = "author_workspace"
                _wait_for_author_workspace(page, copy, timeout_ms=int(config.author_timeout_seconds * 1000))
                summary["author"]["cast_card_count"] = page.locator(".author-studio-cast-card").count()
                summary["author"]["template_chip_count"] = page.locator(".author-studio-cast-card__chips .editorial-muted-chip").filter(has_text="Template").count()
                for label in (
                    copy["canonical_anchor"],
                    copy["current_drive"],
                    copy["red_line"],
                    copy["pressure_signature"],
                ):
                    page.get_by_text(label, exact=True).first.wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                summary["steps"]["author_workspace"] = {
                    "cast_card_count": summary["author"]["cast_card_count"],
                    "template_chip_count": summary["author"]["template_chip_count"],
                }

                current_step = "copilot_cycle"
                suggestion_buttons = page.locator(".author-copilot-suggestion")
                if suggestion_buttons.count() > 0:
                    suggestion_buttons.first.click()
                else:
                    copilot_textarea = page.locator(".copilot-composer__field textarea")
                    copilot_textarea.fill(
                        "Tighten the public-stakes framing while preserving the current beats, cast, runtime lane, and ending logic."
                        if config.ui_language == "en"
                        else "在不改变当前节拍、角色、runtime lane 与结局逻辑的前提下，收紧公开风险与政治压力的表达。"
                    )
                page.get_by_role("button", name=copy["generate_suggestion"]).click()
                page.get_by_role("button", name=copy["apply_changes"]).wait_for(state="visible", timeout=int(config.author_timeout_seconds * 1000))
                page.get_by_role("button", name=copy["apply_changes"]).click()
                page.get_by_text(copy["changes_applied"], exact=True).wait_for(state="visible", timeout=int(config.author_timeout_seconds * 1000))
                page.get_by_role("button", name=copy["undo"]).click()
                page.get_by_text(copy["changes_undone"], exact=True).wait_for(state="visible", timeout=int(config.author_timeout_seconds * 1000))
                summary["steps"]["copilot_cycle"] = {"applied_and_undone": True}

                current_step = "publish"
                page.get_by_role("button", name=copy["publish_to_library"]).click()
                _wait_for_route(page, "story-detail", timeout_ms=int(config.action_timeout_seconds * 1000))
                page.get_by_role("button", name=copy["lead_dossier"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                story_title = str(page.locator(".detail-header h1").first.text_content() or "").strip()
                summary["steps"]["publish"] = {"route": _route_name(page), "story_title": story_title}
                summary["detail"]["story_title"] = story_title

                current_step = "detail_tabs"
                page.get_by_role("button", name=copy["cast_files"]).click()
                page.get_by_role("button", name=copy["lead_dossier"]).click()
                summary["steps"]["detail_tabs"] = {"lead_dossier_and_cast_files": True}

                current_step = "detail_back_to_library"
                page.get_by_role("button", name=copy["back_to_library"]).click()
                _wait_for_route(page, "story-library", timeout_ms=int(config.action_timeout_seconds * 1000))
                page.get_by_role("heading", name=copy["story_library"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                if story_title:
                    page.get_by_role("button", name=re.compile(re.escape(story_title))).first.click()
                    _wait_for_route(page, "story-detail", timeout_ms=int(config.action_timeout_seconds * 1000))
                summary["steps"]["detail_back_to_library"] = {"returned_to_library": True, "reopened_story": bool(story_title)}

                current_step = "start_play"
                page.get_by_role("button", name=copy["start_play"]).click()
                _wait_for_route(page, "play-session", timeout_ms=int(config.action_timeout_seconds * 1000))
                page.get_by_role("button", name=copy["transcript"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                summary["steps"]["start_play"] = {"route": _route_name(page)}
                summary["play"]["transcript_scroll_probe"] = _scroll_probe(page, copy["transcript"])

                current_step = "play_turns"
                fallback_turn_input = (
                    "I force the evidence into the public record before anyone can relabel it as rumor."
                    if config.ui_language == "en"
                    else "我逼所有人把证据写进公开记录，防止它再被说成流言。"
                )
                max_turns_text = page.locator("#play-session-meta").text_content() or ""
                derived_turn_cap = max(
                    1,
                    min(config.max_play_turns, _numeric_text(max_turns_text) or config.max_play_turns),
                )
                turns_run = 0
                first_turn_success = False
                while turns_run < derived_turn_cap and page.locator(".play-transcript-column--archive").count() == 0:
                    turn_summary = _submit_turn_from_ui(
                        page,
                        fallback_turn_input,
                        timeout_ms=int(config.author_timeout_seconds * 1000),
                    )
                    turns_run += 1
                    if turns_run == 1 and turn_summary["transcript_entries_after"] > turn_summary["transcript_entries_before"]:
                        first_turn_success = True
                    summary["play"].setdefault("turns", []).append(turn_summary)
                summary["play"]["turns_run"] = turns_run
                summary["play"]["first_turn_success"] = first_turn_success
                summary["play"]["completed"] = page.locator(".play-transcript-column--archive").count() > 0
                if not summary["play"]["completed"]:
                    raise RuntimeError(f"play session did not reach completed state within {derived_turn_cap} turns")

                current_step = "play_archive_navigation"
                page.get_by_role("button", name=copy["archive"]).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                page.get_by_text(copy["full_transcript"], exact=True).wait_for(state="visible", timeout=int(config.action_timeout_seconds * 1000))
                archive_probe = _scroll_probe(page, copy["archive"])
                summary["play"]["archive_scroll_probe"] = archive_probe
                summary["steps"]["play_archive_navigation"] = archive_probe

                observer.assert_clean()
                summary["observer"] = observer.dump()
                summary["ok"] = True
                return summary
            finally:
                context.close()
                browser.close()
    except (Exception, PlaywrightTimeoutError, PlaywrightError) as exc:  # noqa: BLE001
        summary["ok"] = False
        summary["failed_step"] = current_step
        summary["error_message"] = str(exc)
        raise BrowserProductSmokeFailure(str(exc), summary=summary) from exc


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    try:
        payload = run_browser_product_smoke(config)
        exit_code = 0
    except BrowserProductSmokeFailure as exc:
        payload = exc.summary
        exit_code = 1
    if config.output_path is not None:
        _write_output(config.output_path, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

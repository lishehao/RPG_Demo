from __future__ import annotations

from tools import browser_product_smoke


def test_parse_browser_product_smoke_args_defaults() -> None:
    config = browser_product_smoke.parse_args([])

    assert config.app_url == browser_product_smoke.DEFAULT_APP_URL
    assert config.ui_language == "en"
    assert config.output_path is None
    assert config.headed is False
    assert config.slow_mo_ms == 0
    assert config.author_timeout_seconds == browser_product_smoke.DEFAULT_AUTHOR_TIMEOUT_SECONDS
    assert config.action_timeout_seconds == browser_product_smoke.DEFAULT_ACTION_TIMEOUT_SECONDS
    assert config.max_play_turns == browser_product_smoke.DEFAULT_MAX_PLAY_TURNS


def test_parse_browser_product_smoke_args_supports_overrides(tmp_path) -> None:
    output_path = tmp_path / "browser-smoke.json"
    config = browser_product_smoke.parse_args(
        [
            "--app-url",
            "http://127.0.0.1:4999",
            "--ui-language",
            "zh",
            "--output-path",
            str(output_path),
            "--headed",
            "--slow-mo-ms",
            "25",
            "--author-timeout-seconds",
            "300",
            "--action-timeout-seconds",
            "90",
            "--max-play-turns",
            "7",
        ]
    )

    assert config.app_url == "http://127.0.0.1:4999"
    assert config.ui_language == "zh"
    assert config.output_path == output_path.resolve()
    assert config.headed is True
    assert config.slow_mo_ms == 25
    assert config.author_timeout_seconds == 300.0
    assert config.action_timeout_seconds == 90.0
    assert config.max_play_turns == 7

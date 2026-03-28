from __future__ import annotations

import re

import pytest

from rpg_backend.config import Settings
from rpg_backend.author.sparks import build_story_spark
from rpg_backend.author.sparks import _build_simulated_seed_pool
from rpg_backend.author.sparks import _curated_seed_texts
from rpg_backend.author.sparks import _normalize_spark_payload
from tests.author_fixtures import FakeGateway, gateway_with_overrides, repeated_gateway_error


def test_build_story_spark_returns_prompt_seed_from_gateway_when_llm_first_is_enabled() -> None:
    response = build_story_spark(
        language="en",
        gateway=FakeGateway(),
        settings=Settings(author_spark_mode="llm_first"),
    )

    assert response.language == "en"
    assert response.prompt_seed
    assert "record" in response.prompt_seed.casefold() or "mandate" in response.prompt_seed.casefold()


def test_build_story_spark_falls_back_to_local_seed_when_gateway_fails_in_llm_first_mode() -> None:
    gateway = gateway_with_overrides(
        spark_seed_generate=repeated_gateway_error("llm_invalid_json"),
    )

    response = build_story_spark(
        language="zh",
        gateway=gateway,
        settings=Settings(author_spark_mode="llm_first"),
    )

    assert response.language == "zh"
    assert response.prompt_seed
    assert len(response.prompt_seed.replace(" ", "")) <= 120


def test_simulated_spark_pool_builds_thirty_unique_good_seeds_per_language() -> None:
    en_pool = _build_simulated_seed_pool(language="en", seed_count=30, rng_seed=20260326)
    zh_pool = _build_simulated_seed_pool(language="zh", seed_count=30, rng_seed=20260327)

    assert len(en_pool) == 30
    assert len(set(en_pool)) == 30
    assert all(seed for seed in en_pool)
    assert len(zh_pool) == 30
    assert len(set(zh_pool)) == 30
    assert all(seed for seed in zh_pool)


def test_build_story_spark_uses_simulated_pool_by_default_without_gateway() -> None:
    settings = Settings(
        author_spark_mode="simulated_pool",
        author_spark_simulation_seed_count=30,
        author_spark_simulation_delay_min_seconds=0,
        author_spark_simulation_delay_max_seconds=0,
        author_spark_simulation_rng_seed=20260326,
    )

    response = build_story_spark(language="en", settings=settings, sleep_fn=lambda _seconds: None)

    assert response.language == "en"
    assert response.prompt_seed
    assert len(re.findall(r"[a-z0-9']+", response.prompt_seed.casefold())) <= 100


def test_normalize_spark_payload_rejects_english_seed_over_word_cap() -> None:
    payload = {
        "prompt_seed": " ".join(["record"] * 101),
    }

    with pytest.raises(ValueError, match="100 words"):
        _normalize_spark_payload(payload, language="en")


def test_normalize_spark_payload_rejects_chinese_seed_over_char_cap() -> None:
    payload = {
        "prompt_seed": "记" * 121,
    }

    with pytest.raises(ValueError, match="120 Chinese characters"):
        _normalize_spark_payload(payload, language="zh")


def test_curated_chinese_spark_pool_normalizes_under_new_validator() -> None:
    seeds = _curated_seed_texts("zh")
    visible_lengths = [len(re.sub(r"\s+", "", seed)) for seed in seeds]

    assert len(seeds) == 30
    assert all(seed for seed in seeds)
    assert max(visible_lengths) <= 120

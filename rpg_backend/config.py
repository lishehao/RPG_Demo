from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    story_library_db_path: str = "artifacts/story_library.sqlite3"
    runtime_state_db_path: str = "artifacts/runtime_state.sqlite3"
    default_actor_id: str = "local-dev"
    auth_session_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=300)
    auth_session_cookie_name: str = "rpg_demo_session"
    auth_session_cookie_secure: bool = False
    auth_session_cookie_domain: str | None = None
    auth_session_cookie_samesite: str = "lax"
    play_session_ttl_seconds: int = Field(default=900, ge=60)
    enable_benchmark_api: bool = False
    responses_base_url: str | None = None
    responses_api_key: str | None = None
    responses_model: str | None = None
    responses_timeout_seconds: float = Field(default=20.0, gt=0)
    responses_use_session_cache: bool | None = None
    responses_session_cache_header: str = "x-dashscope-session-cache"
    responses_session_cache_value: str = "enable"
    responses_input_price_per_million_tokens_rmb: float = Field(default=0.2, ge=0)
    responses_output_price_per_million_tokens_rmb: float = Field(default=2.0, ge=0)
    responses_usd_per_rmb: float = Field(default=0.14, ge=0)
    responses_session_cache_hit_multiplier: float = Field(default=0.1, ge=0)
    responses_session_cache_creation_multiplier: float = Field(default=1.25, ge=0)
    responses_enable_thinking_play: bool = False
    responses_enable_thinking_author_overview: bool = False
    responses_enable_thinking_author_beat_plan: bool = False
    responses_enable_thinking_author_scene: bool = False
    responses_enable_thinking_author_rulepack: bool = False
    responses_enable_thinking_story_quality_judge: bool = False
    responses_max_output_tokens_author_beat_skeleton: int | None = Field(default=1200, ge=1)
    responses_max_output_tokens_author_beat_repair: int | None = Field(default=1000, ge=1)
    responses_max_output_tokens_play_interpret: int | None = Field(default=280, ge=1)
    responses_max_output_tokens_play_interpret_repair: int | None = Field(default=320, ge=1)
    responses_max_output_tokens_play_ending_judge: int | None = Field(default=180, ge=1)
    responses_max_output_tokens_play_ending_judge_repair: int | None = Field(default=120, ge=1)
    responses_max_output_tokens_play_pyrrhic_critic: int | None = Field(default=120, ge=1)
    responses_max_output_tokens_play_render: int | None = Field(default=560, ge=1)
    responses_max_output_tokens_play_render_repair: int | None = Field(default=720, ge=1)
    responses_max_output_tokens_author_overview: int | None = Field(default=800, ge=1)
    responses_max_output_tokens_author_beat_plan: int | None = Field(default=1500, ge=1)
    responses_max_output_tokens_author_scene: int | None = Field(default=1600, ge=1)
    responses_max_output_tokens_author_rulepack: int | None = Field(default=900, ge=1)
    responses_max_output_tokens_story_quality_judge: int | None = Field(default=700, ge=1)

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

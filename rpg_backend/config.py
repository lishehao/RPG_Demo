from __future__ import annotations

from functools import lru_cache
from typing import Literal

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
    frontend_dev_cors_origins: str = "http://127.0.0.1:4173,http://127.0.0.1:4174,http://127.0.0.1:5173,http://localhost:4173,http://localhost:4174,http://localhost:5173"
    play_session_ttl_seconds: int = Field(default=900, ge=60)
    enable_benchmark_api: bool = False
    local_portrait_base_url: str = "http://127.0.0.1:8000"
    local_portrait_dir: str = "artifacts/portraits/roster"
    local_author_portrait_dir: str = "artifacts/portraits/author_jobs"
    portrait_manifest_db_path: str = "data/character_roster/portrait_manifest.sqlite3"
    content_prompt_profile: Literal["plain", "role_conditioned"] = "role_conditioned"
    gateway_text_provider: Literal["openai_compatible"] | None = None
    gateway_embedding_provider: Literal["openai_compatible"] | None = None
    gateway_base_url: str | None = None
    gateway_responses_base_url: str | None = None
    gateway_api_key: str | None = None
    gateway_model: str | None = None
    gateway_play_model: str | None = None
    helper_gateway_base_url: str | None = None
    helper_gateway_responses_base_url: str | None = None
    helper_gateway_api_key: str | None = None
    helper_gateway_model: str | None = None
    gateway_embedding_base_url: str | None = None
    gateway_embedding_api_key: str | None = None
    gateway_embedding_model: str | None = None
    gateway_timeout_seconds: float | None = Field(default=None, gt=0)
    gateway_timeout_seconds_author: float | None = Field(default=None, gt=0)
    gateway_timeout_seconds_author_story_frame: float | None = Field(default=45.0, gt=0)
    gateway_timeout_seconds_author_cast_generation: float | None = Field(default=15.0, gt=0)
    gateway_timeout_seconds_author_spark: float | None = Field(default=8.0, gt=0)
    gateway_timeout_seconds_benchmark_driver: float | None = Field(default=None, gt=0)
    author_spark_mode: Literal["simulated_pool", "llm_first"] = "simulated_pool"
    author_spark_simulation_seed_count: int = Field(default=30, ge=1, le=200)
    author_spark_simulation_delay_min_seconds: float = Field(default=2.0, ge=0.0)
    author_spark_simulation_delay_max_seconds: float = Field(default=4.0, ge=0.0)
    author_spark_simulation_rng_seed: int = 20260326
    gateway_use_session_cache: bool | None = None
    gateway_session_cache_header: str | None = None
    gateway_session_cache_value: str | None = None
    gateway_text_rate_limit_enabled: bool = True
    gateway_text_rate_limit_per_minute: int = Field(default=480, ge=1)
    gateway_text_rate_limit_10s_cap: int = Field(default=120, ge=1)
    gateway_text_rate_limit_20s_cap: int = Field(default=220, ge=1)
    llm_timeout_seconds: float | None = Field(default=None, gt=0)
    responses_timeout_seconds: float = Field(default=20.0, gt=0)
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
    responses_max_output_tokens_author_cast_generation: int | None = Field(default=520, ge=1)
    responses_max_output_tokens_author_template_role_draft: int | None = Field(default=4200, ge=1)
    responses_max_output_tokens_author_beat_plan: int | None = Field(default=1500, ge=1)
    responses_max_output_tokens_author_scene: int | None = Field(default=1600, ge=1)
    responses_max_output_tokens_author_rulepack: int | None = Field(default=900, ge=1)
    responses_max_output_tokens_author_spark: int | None = Field(default=220, ge=1)
    responses_max_output_tokens_story_quality_judge: int | None = Field(default=700, ge=1)
    roster_enabled: bool = True
    roster_source_catalog_path: str = "data/character_roster/catalog.json"
    roster_runtime_catalog_path: str = "artifacts/character_roster_runtime.json"
    roster_max_supporting_cast_selections: int = Field(default=4, ge=0, le=4)
    character_knowledge_enabled: bool = False
    character_knowledge_database_url: str | None = None
    character_knowledge_source_kind: str = "roster_catalog"
    character_knowledge_candidate_limit: int = Field(default=24, ge=1, le=256)

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    def resolved_gateway_text_provider(self) -> Literal["openai_compatible"]:
        del self
        return "openai_compatible"

    def resolved_frontend_dev_cors_origins(self) -> list[str]:
        return [
            item.strip()
            for item in str(self.frontend_dev_cors_origins or "").split(",")
            if item.strip()
        ]

    def resolved_gateway_embedding_provider(self) -> Literal["openai_compatible"]:
        del self
        return "openai_compatible"

    def resolved_gateway_base_url(
        self,
        *,
        transport_style: Literal["responses", "chat_completions"] = "responses",
    ) -> str:
        if transport_style == "responses":
            return (self.gateway_responses_base_url or self.gateway_base_url or "").strip()
        return (self.gateway_base_url or "").strip()

    def resolved_gateway_api_key(self) -> str:
        return (self.gateway_api_key or "").strip()

    def resolved_gateway_model(self) -> str:
        return (self.gateway_model or "").strip()

    def resolved_gateway_model_for_text_capability(self, capability: str) -> str:
        if capability.startswith("play.") and str(self.gateway_play_model or "").strip():
            return str(self.gateway_play_model or "").strip()
        return self.resolved_gateway_model()

    def resolved_helper_gateway_base_url(
        self,
        *,
        transport_style: Literal["responses", "chat_completions"] = "responses",
    ) -> str:
        if transport_style == "responses":
            return (self.helper_gateway_responses_base_url or self.helper_gateway_base_url or "").strip()
        return (self.helper_gateway_base_url or "").strip()

    def resolved_helper_gateway_api_key(self) -> str:
        return (self.helper_gateway_api_key or "").strip()

    def resolved_helper_gateway_model(self) -> str:
        return (self.helper_gateway_model or "").strip()

    def resolved_gateway_embedding_model(self) -> str:
        return (self.gateway_embedding_model or "").strip()

    def resolved_gateway_embedding_base_url(self) -> str:
        return (self.gateway_embedding_base_url or "").strip()

    def resolved_gateway_embedding_api_key(self) -> str:
        return (self.gateway_embedding_api_key or "").strip()

    def resolved_gateway_timeout_seconds(self) -> float:
        return float(self.gateway_timeout_seconds or self.llm_timeout_seconds or self.responses_timeout_seconds)

    def resolved_gateway_timeout_seconds_for_text_capability(self, capability: str) -> float:
        if capability == "author.spark_seed_generate" and self.gateway_timeout_seconds_author_spark is not None:
            return float(self.gateway_timeout_seconds_author_spark)
        if capability in {"author.cast_member_generate", "author.cast_member_repair", "author.character_instance_variation"} and self.gateway_timeout_seconds_author_cast_generation is not None:
            return float(self.gateway_timeout_seconds_author_cast_generation)
        if capability in {"author.story_frame_scaffold", "author.story_frame_finalize"} and self.gateway_timeout_seconds_author_story_frame is not None:
            return float(self.gateway_timeout_seconds_author_story_frame)
        if capability.startswith("author.") and self.gateway_timeout_seconds_author is not None:
            return float(self.gateway_timeout_seconds_author)
        return self.resolved_gateway_timeout_seconds()

    def resolved_gateway_timeout_seconds_for_benchmark_driver(self) -> float:
        if self.gateway_timeout_seconds_benchmark_driver is not None:
            return float(self.gateway_timeout_seconds_benchmark_driver)
        return self.resolved_gateway_timeout_seconds()

    def resolved_author_spark_mode(self) -> Literal["simulated_pool", "llm_first"]:
        return "llm_first" if self.author_spark_mode == "llm_first" else "simulated_pool"

    def resolved_author_spark_simulation_seed_count(self) -> int:
        return int(self.author_spark_simulation_seed_count)

    def resolved_author_spark_simulation_delay_min_seconds(self) -> float:
        return float(self.author_spark_simulation_delay_min_seconds)

    def resolved_author_spark_simulation_delay_max_seconds(self) -> float:
        return float(self.author_spark_simulation_delay_max_seconds)

    def resolved_author_spark_simulation_rng_seed(self) -> int:
        return int(self.author_spark_simulation_rng_seed)

    def resolved_gateway_use_session_cache(
        self,
        *,
        transport_style: Literal["responses", "chat_completions"] = "responses",
    ) -> bool:
        if transport_style != "responses":
            return False
        if self.gateway_use_session_cache is not None:
            return bool(self.gateway_use_session_cache)
        return "dashscope" in self.resolved_gateway_base_url(transport_style="responses").casefold()

    def resolved_helper_gateway_use_session_cache(
        self,
        *,
        transport_style: Literal["responses", "chat_completions"] = "responses",
    ) -> bool:
        if transport_style != "responses":
            return False
        if self.gateway_use_session_cache is not None:
            return bool(self.gateway_use_session_cache)
        return "dashscope" in self.resolved_helper_gateway_base_url(transport_style="responses").casefold()

    def resolved_gateway_session_cache_header(self) -> str:
        return (self.gateway_session_cache_header or self.responses_session_cache_header).strip()

    def resolved_gateway_session_cache_value(self) -> str:
        return (self.gateway_session_cache_value or self.responses_session_cache_value).strip()

    def resolved_gateway_text_rate_limit_enabled(self) -> bool:
        return bool(self.gateway_text_rate_limit_enabled)

    def resolved_gateway_text_rate_limit_per_minute(self) -> int:
        return int(self.gateway_text_rate_limit_per_minute)

    def resolved_gateway_text_rate_limit_10s_cap(self) -> int:
        return int(self.gateway_text_rate_limit_10s_cap)

    def resolved_gateway_text_rate_limit_20s_cap(self) -> int:
        return int(self.gateway_text_rate_limit_20s_cap)

    def resolved_gateway_text_max_output_tokens(self, capability: str) -> int | None:
        mapping = {
            "author.story_frame_scaffold": self.responses_max_output_tokens_author_overview,
            "author.story_frame_finalize": self.responses_max_output_tokens_author_overview,
            "author.template_role_draft": self.responses_max_output_tokens_author_template_role_draft,
            "author.cast_member_generate": self.responses_max_output_tokens_author_cast_generation,
            "author.cast_member_repair": self.responses_max_output_tokens_author_cast_generation,
            "author.character_instance_variation": self.responses_max_output_tokens_author_cast_generation,
            "author.spark_seed_generate": self.responses_max_output_tokens_author_spark,
            "author.beat_plan_generate": self.responses_max_output_tokens_author_beat_plan,
            "author.beat_skeleton_generate": self.responses_max_output_tokens_author_beat_skeleton,
            "author.beat_repair": self.responses_max_output_tokens_author_beat_repair,
            "author.rulepack_generate": self.responses_max_output_tokens_author_rulepack,
            "play.interpret": self.responses_max_output_tokens_play_interpret,
            "play.interpret_repair": self.responses_max_output_tokens_play_interpret_repair,
            "play.ending_judge": self.responses_max_output_tokens_play_ending_judge,
            "play.pyrrhic_critic": self.responses_max_output_tokens_play_pyrrhic_critic,
            "play.render": self.responses_max_output_tokens_play_render,
            "play.render_repair": self.responses_max_output_tokens_play_render_repair,
            "copilot.reply": self.responses_max_output_tokens_author_overview,
            "copilot.rewrite_plan": self.responses_max_output_tokens_author_rulepack,
        }
        return mapping.get(capability)

    def resolved_gateway_enable_thinking(self, capability: str) -> bool:
        if capability.startswith("play."):
            return bool(self.responses_enable_thinking_play)
        return False

    def resolved_gateway_input_price_per_million_tokens_rmb(self) -> float:
        return self.responses_input_price_per_million_tokens_rmb

    def resolved_gateway_output_price_per_million_tokens_rmb(self) -> float:
        return self.responses_output_price_per_million_tokens_rmb

    def resolved_gateway_session_cache_hit_multiplier(self) -> float:
        return self.responses_session_cache_hit_multiplier

    def resolved_gateway_session_cache_creation_multiplier(self) -> float:
        return self.responses_session_cache_creation_multiplier

    def resolved_gateway_usd_per_rmb(self) -> float:
        return self.responses_usd_per_rmb


@lru_cache
def get_settings() -> Settings:
    return Settings()

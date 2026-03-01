from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "accept-all-rpg"
    app_env: str = "dev"
    debug: bool = False
    database_url: str = "sqlite:///./app.db"
    llm_provider: str = "fake"
    routing_confidence_threshold: float = 0.55

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

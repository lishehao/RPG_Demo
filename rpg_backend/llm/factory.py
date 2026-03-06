from rpg_backend.config.settings import get_settings
from rpg_backend.llm.base import LLMProvider, LLMProviderConfigError
from rpg_backend.llm.worker_client import WorkerClientError, get_worker_client
from rpg_backend.llm.worker_provider import WorkerProvider


def _normalize_model(value: str | None) -> str:
    return (value or "").strip()


def resolve_openai_models(
    route_model: str | None,
    narration_model: str | None,
    model: str | None,
) -> tuple[str, str]:
    default = _normalize_model(model)
    effective_route = _normalize_model(route_model) or default
    effective_narration = _normalize_model(narration_model) or default
    return effective_route, effective_narration


def resolve_openai_generator_model(generator_model: str | None, model: str | None) -> str:
    return _normalize_model(generator_model) or _normalize_model(model)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()

    route_model, narration_model = resolve_openai_models(
        settings.llm_openai_route_model,
        settings.llm_openai_narration_model,
        settings.llm_openai_model,
    )
    if not route_model or not narration_model:
        raise LLMProviderConfigError(
            "openai provider misconfigured; missing route/narration model. "
            "Set APP_LLM_OPENAI_MODEL or both APP_LLM_OPENAI_ROUTE_MODEL and APP_LLM_OPENAI_NARRATION_MODEL"
        )

    try:
        worker_client = get_worker_client()
    except WorkerClientError as exc:
        raise LLMProviderConfigError(f"llm worker misconfigured: {exc.error_code}: {exc.message}") from exc
    return WorkerProvider(
        worker_client=worker_client,
        route_model=route_model,
        narration_model=narration_model,
        timeout_seconds=settings.llm_openai_timeout_seconds,
        route_max_retries=settings.llm_openai_route_max_retries,
        narration_max_retries=settings.llm_openai_narration_max_retries,
        route_temperature=settings.llm_openai_temperature_route,
        narration_temperature=settings.llm_openai_temperature_narration,
    )

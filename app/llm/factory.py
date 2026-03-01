from app.config.settings import get_settings
from app.llm.base import LLMProvider
from app.llm.fake_provider import FakeProvider
from app.llm.openai_provider import OpenAIProvider


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "fake":
        return FakeProvider()
    if provider == "openai":
        return OpenAIProvider()

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

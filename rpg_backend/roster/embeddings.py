from __future__ import annotations

from typing import Protocol

from rpg_backend.config import Settings
from rpg_backend.llm_gateway import (
    CapabilityGatewayCore,
    GatewayCapabilityError,
    EmbeddingCapabilityRequest,
    build_gateway_core,
)


class CharacterEmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> list[float] | None: ...


class NullCharacterEmbeddingProvider:
    def embed_text(self, text: str) -> list[float] | None:
        del text
        return None


class GatewayCharacterEmbeddingProvider:
    def __init__(self, gateway_core: CapabilityGatewayCore) -> None:
        self._gateway_core = gateway_core

    def embed_text(self, text: str) -> list[float] | None:
        try:
            result = self._gateway_core.invoke_embedding_capability(
                "embedding.roster_query",
                EmbeddingCapabilityRequest(
                    text=text,
                    operation_name="embedding.roster_query",
                ),
            )
        except GatewayCapabilityError as exc:
            if exc.code in {"gateway_embedding_config_missing", "gateway_embedding_model_missing"}:
                return None
            raise
        if not result.value:
            return None
        return [float(item) for item in result.value]


def build_character_embedding_provider(
    settings: Settings,
    *,
    gateway_core: CapabilityGatewayCore | None = None,
) -> CharacterEmbeddingProvider:
    resolved_gateway = gateway_core or build_gateway_core(settings)
    if not settings.resolved_gateway_embedding_model():
        return NullCharacterEmbeddingProvider()
    return GatewayCharacterEmbeddingProvider(resolved_gateway)

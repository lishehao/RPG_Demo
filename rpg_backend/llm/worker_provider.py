from __future__ import annotations

from rpg_backend.llm.base import LLMJsonObjectResult, LLMProvider
from rpg_backend.llm.json_gateway import JsonGateway, JsonGatewayError
from rpg_backend.llm.worker_client import WorkerClient


class WorkerProvider(LLMProvider):
    def __init__(
        self,
        *,
        worker_client: WorkerClient,
        route_model: str,
        narration_model: str,
        timeout_seconds: float,
        route_max_retries: int,
        narration_max_retries: int,
        route_temperature: float,
        narration_temperature: float,
    ) -> None:
        self.worker_client = worker_client
        self.gateway_mode = "worker"
        self.route_model = route_model
        self.narration_model = narration_model
        self.timeout_seconds = timeout_seconds
        self.route_max_retries = max(1, min(route_max_retries, 3))
        self.narration_max_retries = max(1, min(narration_max_retries, 3))
        self.route_temperature = route_temperature
        self.narration_temperature = narration_temperature
        self._json_gateway = JsonGateway(default_timeout_seconds=timeout_seconds, worker_client=worker_client)

    async def invoke_json_object(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_retries: int,
        timeout_seconds: float,
    ) -> LLMJsonObjectResult:
        result = await self._json_gateway.call_json_object(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )
        return LLMJsonObjectResult(payload=result.payload, duration_ms=result.duration_ms)

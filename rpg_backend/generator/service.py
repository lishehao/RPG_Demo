from __future__ import annotations

from rpg_backend.generator.errors import GeneratorBuildError
from rpg_backend.generator.pipeline import GeneratorPipeline
from rpg_backend.generator.result_builder import GeneratorBuildResult
from rpg_backend.generator.versioning import PalettePolicy


class GeneratorService:
    def __init__(self, pipeline: GeneratorPipeline | None = None) -> None:
        self._pipeline = pipeline or GeneratorPipeline()

    def generate_pack(
        self,
        *,
        seed_text: str | None = None,
        prompt_text: str | None = None,
        target_minutes: int,
        npc_count: int,
        style: str | None = None,
        variant_seed: str | int | None = None,
        candidate_parallelism: int | None = None,
        generator_version: str | None = None,
        palette_policy: PalettePolicy = "random",
    ) -> GeneratorBuildResult:
        return self._pipeline.run(
            seed_text=seed_text,
            prompt_text=prompt_text,
            target_minutes=target_minutes,
            npc_count=npc_count,
            style=style,
            variant_seed=variant_seed,
            candidate_parallelism=candidate_parallelism,
            generator_version=generator_version,
            palette_policy=palette_policy,
        )


__all__ = ["GeneratorService", "GeneratorBuildError", "GeneratorBuildResult"]

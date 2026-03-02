from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

from app.domain.linter import LintReport, lint_story_pack
from app.generator.builder import build_pack
from app.generator.planner import plan_beats, plan_beats_from_spec
from app.generator.prompt_compiler import PromptCompileError, PromptCompiler
from app.generator.versioning import (
    GENERATOR_VERSION,
    PalettePolicy,
    build_seed_material,
    compute_pack_hash,
    derive_rng,
    normalize_variant_seed,
)

MAX_REGENERATE_RETRIES = 3
MAX_GENERATION_ATTEMPTS = MAX_REGENERATE_RETRIES + 1


@dataclass
class GeneratorBuildResult:
    pack: dict[str, Any]
    pack_hash: str
    generator_version: str
    variant_seed: str
    palette_policy: PalettePolicy
    generation_mode: str
    lint_report: LintReport
    generation_attempts: int
    regenerate_count: int
    spec_hash: str | None = None
    spec_summary: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)


class GeneratorBuildError(RuntimeError):
    def __init__(
        self,
        lint_report: LintReport,
        generation_attempts: int,
        regenerate_count: int,
        notes: list[str],
        generator_version: str | None = None,
        variant_seed: str | None = None,
        palette_policy: PalettePolicy | None = None,
        error_code: str | None = None,
    ):
        super().__init__("story generation failed after regenerate attempts")
        self.lint_report = lint_report
        self.generation_attempts = generation_attempts
        self.regenerate_count = regenerate_count
        self.notes = notes
        self.generator_version = generator_version
        self.variant_seed = variant_seed
        self.palette_policy = palette_policy
        self.error_code = error_code


class GeneratorService:
    @staticmethod
    def _attempt_variant_seed(base_variant_seed: str, attempt_index: int) -> str:
        if attempt_index == 0:
            return base_variant_seed
        return f"{base_variant_seed}#regen{attempt_index}"

    def generate_pack(
        self,
        *,
        seed_text: str | None = None,
        prompt_text: str | None = None,
        target_minutes: int,
        npc_count: int,
        style: str | None = None,
        variant_seed: str | int | None = None,
        generator_version: str | None = None,
        palette_policy: PalettePolicy = "random",
    ) -> GeneratorBuildResult:
        normalized_seed = (seed_text or "").strip()
        normalized_prompt = (prompt_text or "").strip()
        if not normalized_seed and not normalized_prompt:
            raise GeneratorBuildError(
                lint_report=LintReport(errors=["either seed_text or prompt_text must be provided"], warnings=[]),
                generation_attempts=0,
                regenerate_count=0,
                notes=["generator input validation failed"],
                generator_version=GENERATOR_VERSION,
                variant_seed=None,
                palette_policy=palette_policy,
                error_code="generator_input_invalid",
            )

        if palette_policy not in {"random", "balanced", "fixed"}:
            raise GeneratorBuildError(
                lint_report=LintReport(errors=[f"unsupported_palette_policy: '{palette_policy}'"], warnings=[]),
                generation_attempts=0,
                regenerate_count=0,
                notes=["invalid palette policy"],
                generator_version=GENERATOR_VERSION,
                variant_seed=normalize_variant_seed(variant_seed),
                palette_policy=palette_policy,
                error_code="unsupported_palette_policy",
            )

        if generator_version and generator_version != GENERATOR_VERSION:
            raise GeneratorBuildError(
                lint_report=LintReport(
                    errors=[
                        (
                            "unsupported_generator_version: "
                            f"requested='{generator_version}' expected='{GENERATOR_VERSION}'"
                        )
                    ],
                    warnings=[],
                ),
                generation_attempts=0,
                regenerate_count=0,
                notes=["generator version mismatch"],
                generator_version=GENERATOR_VERSION,
                variant_seed=normalize_variant_seed(variant_seed),
                palette_policy=palette_policy,
                error_code="unsupported_generator_version",
            )

        generation_mode = "prompt" if normalized_prompt else "seed"
        seed_material_text = normalized_seed or normalized_prompt
        base_variant_seed = normalize_variant_seed(variant_seed) or secrets.token_hex(8)

        notes = [
            "generator pipeline used",
            "regenerate strategy enabled",
            f"generation_mode={generation_mode}",
            f"generator_version={GENERATOR_VERSION}",
            f"base_variant_seed={base_variant_seed}",
            f"palette_policy={palette_policy}",
            f"max_regenerate_retries={MAX_REGENERATE_RETRIES}",
        ]

        last_lint_report = LintReport(errors=["generation did not start"], warnings=[])
        last_attempt_seed = base_variant_seed

        for attempt_index in range(MAX_GENERATION_ATTEMPTS):
            generation_attempts = attempt_index + 1
            regenerate_count = attempt_index
            attempt_seed = self._attempt_variant_seed(base_variant_seed, attempt_index)
            last_attempt_seed = attempt_seed

            seed_material = build_seed_material(
                seed_text=seed_material_text,
                target_minutes=target_minutes,
                npc_count=npc_count,
                style=style,
                variant_seed=attempt_seed,
                generator_version=GENERATOR_VERSION,
                palette_policy=palette_policy,
            )
            runtime_rng = derive_rng(seed_material)

            notes.append(
                f"generation_attempt={generation_attempts}; regenerate_count={regenerate_count}; variant_seed={attempt_seed}"
            )

            spec_hash: str | None = None
            spec_summary: dict[str, Any] | None = None
            if normalized_prompt:
                try:
                    compiled = PromptCompiler().compile(
                        prompt_text=normalized_prompt,
                        target_minutes=target_minutes,
                        npc_count=npc_count,
                        style=style,
                        attempt_index=attempt_index,
                        attempt_seed=attempt_seed,
                    )
                except PromptCompileError as exc:
                    raise GeneratorBuildError(
                        lint_report=LintReport(errors=exc.errors, warnings=[]),
                        generation_attempts=generation_attempts,
                        regenerate_count=regenerate_count,
                        notes=notes + exc.notes,
                        generator_version=GENERATOR_VERSION,
                        variant_seed=attempt_seed,
                        palette_policy=palette_policy,
                        error_code=exc.error_code,
                    ) from exc

                plan = plan_beats_from_spec(
                    spec=compiled.spec,
                    seed_text=seed_material_text,
                    target_minutes=target_minutes,
                    npc_count=npc_count,
                )
                spec_hash = compiled.spec_hash
                spec_summary = compiled.spec.compact_summary()
                notes.extend(compiled.notes)
                notes.append(f"spec_hash_attempt_{generation_attempts}={spec_hash}")
            else:
                plan = plan_beats(seed_text=seed_material_text, target_minutes=target_minutes, npc_count=npc_count)

            pack = build_pack(plan, style=style, rng=runtime_rng, palette_policy=palette_policy)
            lint_report = lint_story_pack(pack)
            last_lint_report = lint_report

            notes.append(f"lint_ok_attempt_{generation_attempts}={lint_report.ok}")
            if lint_report.ok:
                pack_hash = compute_pack_hash(pack)
                notes.extend(
                    [
                        f"target_steps={plan.target_steps}",
                        f"npc_count={len(plan.npc_names)}",
                        f"variant_seed={attempt_seed}",
                        f"pack_hash={pack_hash}",
                    ]
                )
                return GeneratorBuildResult(
                    pack=pack,
                    pack_hash=pack_hash,
                    generator_version=GENERATOR_VERSION,
                    variant_seed=attempt_seed,
                    palette_policy=palette_policy,
                    generation_mode=generation_mode,
                    lint_report=lint_report,
                    generation_attempts=generation_attempts,
                    regenerate_count=regenerate_count,
                    spec_hash=spec_hash,
                    spec_summary=spec_summary,
                    notes=notes,
                )

            if regenerate_count < MAX_REGENERATE_RETRIES:
                notes.append(f"regenerate_triggered_after_attempt_{generation_attempts}")

        notes.append("generation_failed_after_regenerates")
        raise GeneratorBuildError(
            lint_report=last_lint_report,
            generation_attempts=MAX_GENERATION_ATTEMPTS,
            regenerate_count=MAX_REGENERATE_RETRIES,
            notes=notes,
            generator_version=GENERATOR_VERSION,
            variant_seed=last_attempt_seed,
            palette_policy=palette_policy,
            error_code="generation_failed_after_regenerates",
        )

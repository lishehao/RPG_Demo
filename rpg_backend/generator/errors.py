from __future__ import annotations

from typing import Any

from rpg_backend.domain.linter import LintReport
from rpg_backend.generator.versioning import GENERATOR_VERSION, PalettePolicy


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
        candidate_parallelism: int = 1,
        attempt_history: list[dict[str, Any]] | None = None,
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
        self.candidate_parallelism = candidate_parallelism
        self.attempt_history = attempt_history or []


def build_input_error(
    *,
    lint_errors: list[str],
    notes: list[str],
    error_code: str,
    palette_policy: PalettePolicy,
    variant_seed: str | None,
) -> GeneratorBuildError:
    return GeneratorBuildError(
        lint_report=LintReport(errors=lint_errors, warnings=[]),
        generation_attempts=0,
        regenerate_count=0,
        notes=notes,
        generator_version=GENERATOR_VERSION,
        variant_seed=variant_seed,
        palette_policy=palette_policy,
        error_code=error_code,
        candidate_parallelism=1,
    )


def build_prompt_compile_error(
    *,
    errors: list[str],
    error_code: str,
    generation_attempts: int,
    regenerate_count: int,
    notes: list[str],
    variant_seed: str,
    palette_policy: PalettePolicy,
    candidate_parallelism: int,
    attempt_history: list[dict[str, Any]],
) -> GeneratorBuildError:
    return GeneratorBuildError(
        lint_report=LintReport(errors=errors, warnings=[]),
        generation_attempts=generation_attempts,
        regenerate_count=regenerate_count,
        notes=notes,
        generator_version=GENERATOR_VERSION,
        variant_seed=variant_seed,
        palette_policy=palette_policy,
        error_code=error_code,
        candidate_parallelism=candidate_parallelism,
        attempt_history=attempt_history,
    )


def build_terminal_generation_error(
    *,
    lint_report: LintReport,
    notes: list[str],
    variant_seed: str,
    palette_policy: PalettePolicy,
    candidate_parallelism: int,
    attempt_history: list[dict[str, Any]],
    error_code: str = "generation_failed_after_regenerates",
    generation_attempts: int = 4,
    regenerate_count: int = 3,
) -> GeneratorBuildError:
    return GeneratorBuildError(
        lint_report=lint_report,
        generation_attempts=generation_attempts,
        regenerate_count=regenerate_count,
        notes=notes,
        generator_version=GENERATOR_VERSION,
        variant_seed=variant_seed,
        palette_policy=palette_policy,
        error_code=error_code,
        candidate_parallelism=candidate_parallelism,
        attempt_history=attempt_history,
    )

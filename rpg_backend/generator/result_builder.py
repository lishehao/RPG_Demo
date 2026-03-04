from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rpg_backend.domain.linter import LintReport
from rpg_backend.generator.versioning import PalettePolicy


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
    candidate_parallelism: int
    attempt_history: list[dict[str, Any]] = field(default_factory=list)
    spec_hash: str | None = None
    spec_summary: dict[str, Any] | None = None


def build_attempt_history_record(
    *,
    attempt_index: int,
    variant_seed: str,
    winner_candidate_index: int | None,
    winner_candidate_seed: str | None,
    best_candidate_index: int | None,
    best_candidate_seed: str | None,
    lint_ok: bool,
    candidate_count: int,
) -> dict[str, Any]:
    return {
        "attempt_index": attempt_index,
        "variant_seed": variant_seed,
        "winner_candidate_index": winner_candidate_index,
        "winner_candidate_seed": winner_candidate_seed,
        "best_candidate_index": best_candidate_index,
        "best_candidate_seed": best_candidate_seed,
        "lint_ok": lint_ok,
        "candidate_count": candidate_count,
    }


def append_attempt_notes(
    *,
    notes: list[str],
    generation_attempts: int,
    regenerate_count: int,
    attempt_seed: str,
) -> None:
    notes.append(
        f"generation_attempt={generation_attempts}; regenerate_count={regenerate_count}; variant_seed={attempt_seed}"
    )


def build_success_result(
    *,
    pack: dict[str, Any],
    pack_hash: str,
    generator_version: str,
    variant_seed: str,
    palette_policy: PalettePolicy,
    generation_mode: str,
    lint_report: LintReport,
    generation_attempts: int,
    regenerate_count: int,
    candidate_parallelism: int,
    attempt_history: list[dict[str, Any]],
    spec_hash: str | None,
    spec_summary: dict[str, Any] | None,
) -> GeneratorBuildResult:
    return GeneratorBuildResult(
        pack=pack,
        pack_hash=pack_hash,
        generator_version=generator_version,
        variant_seed=variant_seed,
        palette_policy=palette_policy,
        generation_mode=generation_mode,
        lint_report=lint_report,
        generation_attempts=generation_attempts,
        regenerate_count=regenerate_count,
        candidate_parallelism=candidate_parallelism,
        attempt_history=attempt_history,
        spec_hash=spec_hash,
        spec_summary=spec_summary,
    )

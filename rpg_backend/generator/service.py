from __future__ import annotations

import secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from rpg_backend.config.settings import get_settings
from rpg_backend.domain.linter import LintReport, lint_story_pack
from rpg_backend.generator.builder import build_pack
from rpg_backend.generator.planner import plan_beats, plan_beats_from_spec
from rpg_backend.generator.prompt_compiler import PromptCompileError, PromptCompiler
from rpg_backend.generator.versioning import (
    GENERATOR_VERSION,
    PalettePolicy,
    build_seed_material,
    compute_pack_hash,
    derive_rng,
    normalize_variant_seed,
)

MAX_REGENERATE_RETRIES = 3
MAX_GENERATION_ATTEMPTS = MAX_REGENERATE_RETRIES + 1
MIN_CANDIDATE_PARALLELISM = 1
MAX_CANDIDATE_PARALLELISM = 8


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


@dataclass(frozen=True)
class _CandidateBuildResult:
    candidate_index: int
    candidate_seed: str
    pack: dict[str, Any]
    lint_report: LintReport


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


class GeneratorService:
    @staticmethod
    def _attempt_variant_seed(base_variant_seed: str, attempt_index: int) -> str:
        if attempt_index == 0:
            return base_variant_seed
        return f"{base_variant_seed}#regen{attempt_index}"

    @staticmethod
    def _candidate_variant_seed(attempt_seed: str, candidate_index: int) -> str:
        if candidate_index == 0:
            return attempt_seed
        return f"{attempt_seed}#cand{candidate_index}"

    @staticmethod
    def _resolve_candidate_parallelism(requested: int | None) -> int:
        if requested is not None:
            return max(MIN_CANDIDATE_PARALLELISM, min(MAX_CANDIDATE_PARALLELISM, int(requested)))
        settings = get_settings()
        configured = int(getattr(settings, "generator_candidate_parallelism", 1))
        return max(MIN_CANDIDATE_PARALLELISM, min(MAX_CANDIDATE_PARALLELISM, configured))

    @staticmethod
    def _build_candidate(
        *,
        seed_material_text: str,
        target_minutes: int,
        npc_count: int,
        style: str | None,
        candidate_seed: str,
        plan,
        palette_policy: PalettePolicy,
    ) -> _CandidateBuildResult:
        seed_material = build_seed_material(
            seed_text=seed_material_text,
            target_minutes=target_minutes,
            npc_count=npc_count,
            style=style,
            variant_seed=candidate_seed,
            generator_version=GENERATOR_VERSION,
            palette_policy=palette_policy,
        )
        runtime_rng = derive_rng(seed_material)
        pack = build_pack(plan, style=style, rng=runtime_rng, palette_policy=palette_policy)
        lint_report = lint_story_pack(pack)
        return _CandidateBuildResult(
            candidate_index=0,
            candidate_seed=candidate_seed,
            pack=pack,
            lint_report=lint_report,
        )

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
                candidate_parallelism=1,
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
                candidate_parallelism=1,
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
                candidate_parallelism=1,
            )

        generation_mode = "prompt" if normalized_prompt else "seed"
        seed_material_text = normalized_seed or normalized_prompt
        base_variant_seed = normalize_variant_seed(variant_seed) or secrets.token_hex(8)
        effective_candidate_parallelism = self._resolve_candidate_parallelism(candidate_parallelism)

        notes = [
            "generator pipeline used",
            "regenerate strategy enabled",
            f"generation_mode={generation_mode}",
            f"generator_version={GENERATOR_VERSION}",
            f"base_variant_seed={base_variant_seed}",
            f"palette_policy={palette_policy}",
            f"max_regenerate_retries={MAX_REGENERATE_RETRIES}",
            f"candidate_parallelism={effective_candidate_parallelism}",
        ]
        attempt_history: list[dict[str, Any]] = []

        last_lint_report = LintReport(errors=["generation did not start"], warnings=[])
        last_attempt_seed = base_variant_seed

        for attempt_index in range(MAX_GENERATION_ATTEMPTS):
            generation_attempts = attempt_index + 1
            regenerate_count = attempt_index
            attempt_seed = self._attempt_variant_seed(base_variant_seed, attempt_index)
            last_attempt_seed = attempt_seed

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
                    attempt_history.append(
                        {
                            "attempt_index": generation_attempts,
                            "variant_seed": attempt_seed,
                            "winner_candidate_index": None,
                            "winner_candidate_seed": None,
                            "best_candidate_index": None,
                            "best_candidate_seed": None,
                            "lint_ok": False,
                            "candidate_count": effective_candidate_parallelism,
                        }
                    )
                    raise GeneratorBuildError(
                        lint_report=LintReport(errors=exc.errors, warnings=[]),
                        generation_attempts=generation_attempts,
                        regenerate_count=regenerate_count,
                        notes=notes + exc.notes,
                        generator_version=GENERATOR_VERSION,
                        variant_seed=attempt_seed,
                        palette_policy=palette_policy,
                        error_code=exc.error_code,
                        candidate_parallelism=effective_candidate_parallelism,
                        attempt_history=attempt_history,
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

            candidate_count = effective_candidate_parallelism
            candidates: list[_CandidateBuildResult] = []
            winner: _CandidateBuildResult | None = None

            if candidate_count <= 1:
                candidate = self._build_candidate(
                    seed_material_text=seed_material_text,
                    target_minutes=target_minutes,
                    npc_count=npc_count,
                    style=style,
                    candidate_seed=attempt_seed,
                    plan=plan,
                    palette_policy=palette_policy,
                )
                candidate = _CandidateBuildResult(
                    candidate_index=0,
                    candidate_seed=attempt_seed,
                    pack=candidate.pack,
                    lint_report=candidate.lint_report,
                )
                candidates.append(candidate)
                if candidate.lint_report.ok:
                    winner = candidate
            else:
                with ThreadPoolExecutor(max_workers=candidate_count) as pool:
                    future_map = {}
                    for candidate_index in range(candidate_count):
                        candidate_seed = self._candidate_variant_seed(attempt_seed, candidate_index)
                        future = pool.submit(
                            self._build_candidate,
                            seed_material_text=seed_material_text,
                            target_minutes=target_minutes,
                            npc_count=npc_count,
                            style=style,
                            candidate_seed=candidate_seed,
                            plan=plan,
                            palette_policy=palette_policy,
                        )
                        future_map[future] = (candidate_index, candidate_seed)

                    for future in as_completed(future_map):
                        candidate_index, candidate_seed = future_map[future]
                        try:
                            candidate = future.result()
                            candidate = _CandidateBuildResult(
                                candidate_index=candidate_index,
                                candidate_seed=candidate_seed,
                                pack=candidate.pack,
                                lint_report=candidate.lint_report,
                            )
                        except Exception as exc:  # noqa: BLE001
                            candidate = _CandidateBuildResult(
                                candidate_index=candidate_index,
                                candidate_seed=candidate_seed,
                                pack={},
                                lint_report=LintReport(
                                    errors=[f"candidate_build_exception: {type(exc).__name__}: {exc}"],
                                    warnings=[],
                                ),
                            )
                        candidates.append(candidate)
                        if winner is None and candidate.lint_report.ok:
                            winner = candidate

            if winner is not None:
                lint_report = winner.lint_report
                pack = winner.pack
                last_lint_report = lint_report
                last_attempt_seed = winner.candidate_seed
                attempt_history.append(
                    {
                        "attempt_index": generation_attempts,
                        "variant_seed": attempt_seed,
                        "winner_candidate_index": winner.candidate_index,
                        "winner_candidate_seed": winner.candidate_seed,
                        "best_candidate_index": winner.candidate_index,
                        "best_candidate_seed": winner.candidate_seed,
                        "lint_ok": True,
                        "candidate_count": candidate_count,
                    }
                )
                notes.append(f"lint_ok_attempt_{generation_attempts}=True")
                notes.append(
                    f"attempt_{generation_attempts}_winner=candidate_{winner.candidate_index}:{winner.candidate_seed}"
                )
                pack_hash = compute_pack_hash(pack)
                notes.extend(
                    [
                        f"target_steps={plan.target_steps}",
                        f"npc_count={len(plan.npc_names)}",
                        f"variant_seed={winner.candidate_seed}",
                        f"pack_hash={pack_hash}",
                    ]
                )
                return GeneratorBuildResult(
                    pack=pack,
                    pack_hash=pack_hash,
                    generator_version=GENERATOR_VERSION,
                    variant_seed=winner.candidate_seed,
                    palette_policy=palette_policy,
                    generation_mode=generation_mode,
                    lint_report=lint_report,
                    generation_attempts=generation_attempts,
                    regenerate_count=regenerate_count,
                    candidate_parallelism=effective_candidate_parallelism,
                    attempt_history=attempt_history,
                    spec_hash=spec_hash,
                    spec_summary=spec_summary,
                )

            best_candidate = min(
                candidates,
                key=lambda item: (len(item.lint_report.errors), item.candidate_index),
            )
            attempt_history.append(
                {
                    "attempt_index": generation_attempts,
                    "variant_seed": attempt_seed,
                    "winner_candidate_index": None,
                    "winner_candidate_seed": None,
                    "best_candidate_index": best_candidate.candidate_index,
                    "best_candidate_seed": best_candidate.candidate_seed,
                    "lint_ok": False,
                    "candidate_count": candidate_count,
                }
            )
            last_lint_report = best_candidate.lint_report
            last_attempt_seed = best_candidate.candidate_seed
            notes.append(f"lint_ok_attempt_{generation_attempts}=False")
            notes.append(
                f"attempt_{generation_attempts}_best_candidate="
                f"candidate_{best_candidate.candidate_index}:{best_candidate.candidate_seed}"
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
            candidate_parallelism=effective_candidate_parallelism,
            attempt_history=attempt_history,
        )

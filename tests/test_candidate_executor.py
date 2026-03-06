from __future__ import annotations

from rpg_backend.domain.linter import LintReport
from rpg_backend.generator.candidate_executor import (
    CandidateBuildResult,
    execute_candidates,
)


def test_execute_candidates_single_candidate_path(monkeypatch) -> None:
    import rpg_backend.generator.candidate_executor as candidate_module

    def _fake_build_candidate(**kwargs):  # noqa: ANN003, ANN201
        return CandidateBuildResult(
            candidate_index=0,
            candidate_seed=kwargs["candidate_seed"],
            pack={"seed": kwargs["candidate_seed"]},
            lint_report=LintReport(errors=[], warnings=[]),
        )

    monkeypatch.setattr(candidate_module, "build_candidate", _fake_build_candidate)

    result = execute_candidates(
        seed_material_text="seed-material",
        target_minutes=10,
        npc_count=4,
        style=None,
        attempt_seed="attempt-seed",
        plan=object(),
        palette_policy="random",
        candidate_count=1,
    )

    assert result.candidate_count == 1
    assert len(result.candidates) == 1
    assert result.winner is not None
    assert result.winner.candidate_seed == "attempt-seed"
    assert result.best_candidate.candidate_seed == "attempt-seed"


def test_execute_candidates_parallel_winner_and_best(monkeypatch) -> None:
    import rpg_backend.generator.candidate_executor as candidate_module

    def _fake_build_candidate(**kwargs):  # noqa: ANN003, ANN201
        seed = kwargs["candidate_seed"]
        ok = seed.endswith("#cand1")
        return CandidateBuildResult(
            candidate_index=0,
            candidate_seed=seed,
            pack={"seed": seed},
            lint_report=LintReport(errors=[] if ok else ["forced candidate lint fail"], warnings=[]),
        )

    monkeypatch.setattr(candidate_module, "build_candidate", _fake_build_candidate)

    result = execute_candidates(
        seed_material_text="seed-material",
        target_minutes=10,
        npc_count=4,
        style=None,
        attempt_seed="attempt-seed",
        plan=object(),
        palette_policy="random",
        candidate_count=3,
    )

    assert result.candidate_count == 3
    assert len(result.candidates) == 3
    assert result.winner is not None
    assert result.winner.candidate_seed.endswith("#cand1")
    assert result.best_candidate.candidate_seed.endswith("#cand1")


def test_execute_candidates_converts_exceptions_to_lint_errors(monkeypatch) -> None:
    import rpg_backend.generator.candidate_executor as candidate_module

    def _fake_build_candidate(**kwargs):  # noqa: ANN003, ANN201
        seed = kwargs["candidate_seed"]
        if seed.endswith("#cand2"):
            raise RuntimeError("boom")
        return CandidateBuildResult(
            candidate_index=0,
            candidate_seed=seed,
            pack={"seed": seed},
            lint_report=LintReport(errors=["forced fail"], warnings=[]),
        )

    monkeypatch.setattr(candidate_module, "build_candidate", _fake_build_candidate)

    result = execute_candidates(
        seed_material_text="seed-material",
        target_minutes=10,
        npc_count=4,
        style=None,
        attempt_seed="attempt-seed",
        plan=object(),
        palette_policy="random",
        candidate_count=3,
    )

    assert result.winner is None
    exception_candidate = next(
        candidate for candidate in result.candidates if candidate.candidate_seed.endswith("#cand2")
    )
    assert exception_candidate.lint_report.errors
    assert exception_candidate.lint_report.errors[0].startswith("candidate_build_exception:")

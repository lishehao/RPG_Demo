from __future__ import annotations

from rpg_backend.play.closeout_gate import determine_ending, finalize_turn_ending
from rpg_backend.play.closeout_judge import (
    EndingJudgeResult,
    PyrrhicCriticResult,
    judge_ending_intent,
    repair_ending_intent_judge,
    run_pyrrhic_critic,
)
from rpg_backend.play.closeout_signals import build_ending_judge_signal_payload, judge_eligible

__all__ = [
    "EndingJudgeResult",
    "PyrrhicCriticResult",
    "build_ending_judge_signal_payload",
    "determine_ending",
    "finalize_turn_ending",
    "judge_eligible",
    "judge_ending_intent",
    "repair_ending_intent_judge",
    "run_pyrrhic_critic",
]

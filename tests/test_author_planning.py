from __future__ import annotations

from rpg_backend.author.contracts import FocusedBrief, StoryGenerationControls
from rpg_backend.author.planning import build_story_flow_plan, build_tone_plan


def _focused_brief() -> FocusedBrief:
    return FocusedBrief(
        language="en",
        story_kernel="A records examiner must restore one public record before the vote hardens.",
        setting_signal="archive hall under emergency vote pressure",
        core_conflict="verify altered civic records before rumor replaces the public record",
        tone_signal="Tense procedural thriller",
        hard_constraints=[],
        forbidden_tones=[],
    )


def test_story_flow_plan_maps_soft_duration_targets() -> None:
    expectations = {
        10: (4, 2, [2, 2], "low", 3),
        13: (6, 3, [2, 2, 2], "low", 4),
        17: (8, 4, [2, 2, 2, 2], "medium", 5),
        22: (10, 5, [2, 2, 2, 2, 2], "high", 7),
        25: (10, 5, [2, 2, 2, 2, 2], "high", 7),
    }

    for minutes, (turns, beats, schedule, branch_budget, minimum_resolution_turn) in expectations.items():
        plan = build_story_flow_plan(
            controls=StoryGenerationControls(target_duration_minutes=minutes),
            primary_theme="truth_record_crisis",
        )
        assert plan.target_turn_count == turns
        assert plan.target_beat_count == beats
        assert plan.progress_required_by_beat == schedule
        assert plan.branch_budget == branch_budget
        assert plan.minimum_resolution_turn == minimum_resolution_turn
        if minutes >= 22:
            assert plan.recommended_cast_count == 5


def test_tone_plan_defaults_to_prompt_signal_without_forcing_humanistic_fallback() -> None:
    tone_plan = build_tone_plan(
        focused_brief=_focused_brief(),
        controls=StoryGenerationControls(),
    )

    assert tone_plan.resolved_tone_signal == "Tense procedural thriller"
    assert "public obligation" in tone_plan.world_texture_guidance.casefold() or "specific" in tone_plan.world_texture_guidance.casefold()

from __future__ import annotations

from rpg_backend.author.contracts import BeatPlanDraft, CastDraft, StoryFrameDraft


def beat_plan_quality_reasons(
    beat_plan_draft: BeatPlanDraft,
    story_frame: StoryFrameDraft,
    cast_draft: CastDraft,
) -> list[str]:
    reasons: list[str] = []
    beats = beat_plan_draft.beats
    if len(beats) < 2:
        reasons.append("too_few_beats")
        return reasons
    cast_names = {item.name for item in cast_draft.cast}
    truth_texts = {item.text for item in story_frame.truths}
    axis_ids = {item.template_id for item in story_frame.state_axis_choices}
    covered_names = {
        name
        for beat in beats
        for name in (*beat.focus_names, *beat.conflict_pair)
        if name in cast_names
    }
    if len(cast_names) >= 3 and len(covered_names) < min(3, len(cast_names)):
        reasons.append("cast_coverage_too_narrow")
    used_axes = {beat.pressure_axis_id for beat in beats if beat.pressure_axis_id in axis_ids}
    if len(axis_ids) >= 2 and len(used_axes) < 2:
        reasons.append("axis_coverage_too_narrow")
    if len({beat.milestone_kind for beat in beats}) < min(2, len(beats)):
        reasons.append("milestones_not_diverse")
    if any(not beat.focus_names for beat in beats):
        reasons.append("beat_missing_focus_names")
    if any(not beat.return_hooks for beat in beats):
        reasons.append("beat_missing_return_hooks")
    if any(not beat.route_pivot_tag for beat in beats):
        reasons.append("beat_missing_route_pivot")
    if any(not any(text in truth_texts for text in beat.required_truth_texts) for beat in beats):
        reasons.append("beat_missing_story_truth_alignment")
    return reasons

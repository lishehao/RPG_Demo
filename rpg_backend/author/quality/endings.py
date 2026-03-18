from __future__ import annotations

from rpg_backend.author.contracts import DesignBundle, EndingIntentDraft, EndingRulesDraft


def _has_condition_content(conditions) -> bool:  # noqa: ANN001
    return any(
        getattr(conditions, key)
        for key in (
            "min_axes",
            "max_axes",
            "min_stances",
            "required_truths",
            "required_events",
            "required_flags",
        )
    )


def _has_story_specific_condition(conditions) -> bool:  # noqa: ANN001
    return bool(
        conditions.min_stances
        or conditions.required_truths
        or conditions.required_events
        or conditions.required_flags
    )


def ending_rules_quality_reasons(
    ending_rules_draft: EndingRulesDraft,
    bundle: DesignBundle,
) -> list[str]:
    reasons: list[str] = []
    rules_by_id = {item.ending_id: item for item in ending_rules_draft.ending_rules}
    if "mixed" not in rules_by_id:
        reasons.append("missing_mixed_ending")
    if len(rules_by_id) < 3:
        reasons.append("missing_canonical_endings")
    non_mixed_rules = [item for ending_id, item in rules_by_id.items() if ending_id != "mixed"]
    if len(non_mixed_rules) < 2:
        reasons.append("missing_non_mixed_endings")
    if any(not _has_condition_content(item.conditions) for item in non_mixed_rules):
        reasons.append("non_mixed_endings_missing_conditions")
    if non_mixed_rules and not any(_has_story_specific_condition(item.conditions) for item in non_mixed_rules):
        reasons.append("endings_missing_story_specific_conditions")

    axis_kind_by_id = {item.axis_id: item.kind for item in bundle.state_schema.axes}
    collapse = rules_by_id.get("collapse")
    pyrrhic = rules_by_id.get("pyrrhic")
    if collapse is None or pyrrhic is None:
        reasons.append("missing_collapse_or_pyrrhic")
        return reasons
    if collapse.conditions.max_axes:
        reasons.append("collapse_should_not_use_max_axes")
    if not any(axis_kind_by_id.get(axis_id) == "pressure" for axis_id in collapse.conditions.min_axes):
        reasons.append("collapse_missing_pressure_axis")
    if pyrrhic.conditions.max_axes:
        reasons.append("pyrrhic_should_not_use_max_axes")
    has_success_axis = any(axis_kind_by_id.get(axis_id) != "pressure" for axis_id in pyrrhic.conditions.min_axes)
    has_cost_signal = any(axis_kind_by_id.get(axis_id) == "pressure" for axis_id in pyrrhic.conditions.min_axes) or bool(
        pyrrhic.conditions.required_events or pyrrhic.conditions.required_flags
    )
    if not has_success_axis:
        reasons.append("pyrrhic_missing_success_axis")
    if not has_cost_signal:
        reasons.append("pyrrhic_missing_cost_signal")
    return reasons


def ending_intent_quality_reasons(
    ending_intent_draft: EndingIntentDraft,
    bundle: DesignBundle,
) -> list[str]:
    reasons: list[str] = []
    intent_by_id = {item.ending_id: item for item in ending_intent_draft.ending_intents}
    missing = {"collapse", "pyrrhic", "mixed"} - set(intent_by_id)
    if missing:
        reasons.append("missing_canonical_ending_intents")
        return reasons
    axis_ids = {item.axis_id for item in bundle.state_schema.axes}
    collapse = intent_by_id["collapse"]
    pyrrhic = intent_by_id["pyrrhic"]
    mixed = intent_by_id["mixed"]
    if mixed.axis_ids or mixed.required_truth_ids or mixed.required_event_ids or mixed.required_flag_ids:
        reasons.append("mixed_intent_should_be_fallback_only")
    if not any(item in axis_ids for item in collapse.axis_ids):
        reasons.append("collapse_intent_missing_axis")
    if len([item for item in pyrrhic.axis_ids if item in axis_ids]) < 1:
        reasons.append("pyrrhic_intent_missing_axis")
    return reasons

from __future__ import annotations

from rpg_backend.author.contracts import (
    DesignBundle,
    EndingAnchorSuggestionDraft,
    EndingAnchorSuggestionSpec,
    EndingIntentDraft,
    EndingIntentSpec,
    EndingRule,
    EndingRulesDraft,
)


ENDING_PRIORITY_BY_ID: dict[str, int] = {
    "collapse": 1,
    "pyrrhic": 2,
    "mixed": 10,
}


def _canonical_ending_priority(ending_id: str) -> int:
    return ENDING_PRIORITY_BY_ID.get(ending_id, 100)


def _ending_story_specific_hints(bundle: DesignBundle) -> dict[str, list[str] | str | None]:
    truth_ids = [item.truth_id for item in bundle.story_bible.truth_catalog]
    event_ids = [event for beat in bundle.beat_spine for event in beat.required_events]
    flag_ids = [item.flag_id for item in bundle.state_schema.flags]
    return {
        "primary_truth_id": truth_ids[0] if truth_ids else None,
        "secondary_truth_id": truth_ids[1] if len(truth_ids) > 1 else (truth_ids[0] if truth_ids else None),
        "final_event_id": event_ids[-1] if event_ids else None,
        "opening_event_id": event_ids[0] if event_ids else None,
        "primary_flag_id": flag_ids[0] if flag_ids else None,
    }


def build_ending_skeleton(bundle: DesignBundle) -> EndingIntentDraft:
    pressure_axis = next((axis.axis_id for axis in bundle.state_schema.axes if axis.kind == "pressure"), bundle.state_schema.axes[0].axis_id)
    secondary_axis = next(
        (axis.axis_id for axis in bundle.state_schema.axes if axis.kind != "pressure"),
        next((axis.axis_id for axis in bundle.state_schema.axes if axis.axis_id != pressure_axis), pressure_axis),
    )
    hints = _ending_story_specific_hints(bundle)
    collapse_truths = [hints["primary_truth_id"]] if hints["primary_truth_id"] else []
    pyrrhic_truths = [hints["secondary_truth_id"]] if hints["secondary_truth_id"] else []
    pyrrhic_events = [hints["final_event_id"]] if hints["final_event_id"] else []
    pyrrhic_flags = [hints["primary_flag_id"]] if hints["primary_flag_id"] else []
    return EndingIntentDraft(
        ending_intents=[
            EndingIntentSpec(
                ending_id="collapse",
                priority=1,
                axis_ids=[pressure_axis],
                required_truth_ids=collapse_truths,
            ),
            EndingIntentSpec(
                ending_id="pyrrhic",
                priority=2,
                axis_ids=[secondary_axis, pressure_axis] if secondary_axis != pressure_axis else [pressure_axis],
                required_truth_ids=pyrrhic_truths,
                required_event_ids=pyrrhic_events,
                required_flag_ids=pyrrhic_flags,
            ),
            EndingIntentSpec(
                ending_id="mixed",
                priority=10,
                fallback=True,
            ),
        ],
    )


def build_default_ending_intent(bundle: DesignBundle) -> EndingIntentDraft:
    return build_ending_skeleton(bundle)


def normalize_ending_anchor_suggestions(
    suggestions: EndingAnchorSuggestionDraft,
    bundle: DesignBundle,
) -> EndingAnchorSuggestionDraft:
    axis_ids = {item.axis_id for item in bundle.state_schema.axes}
    truth_ids = {item.truth_id for item in bundle.story_bible.truth_catalog}
    event_ids = {event for beat in bundle.beat_spine for event in beat.required_events}
    flag_ids = {item.flag_id for item in bundle.state_schema.flags}
    rows: list[EndingAnchorSuggestionSpec] = []
    seen_ids: set[str] = set()
    for item in suggestions.ending_anchor_suggestions:
        if item.ending_id in seen_ids:
            continue
        seen_ids.add(item.ending_id)
        rows.append(
            EndingAnchorSuggestionSpec(
                ending_id=item.ending_id,
                axis_ids=[axis_id for axis_id in item.axis_ids if axis_id in axis_ids],
                required_truth_ids=[truth_id for truth_id in item.required_truth_ids if truth_id in truth_ids],
                required_event_ids=[event_id for event_id in item.required_event_ids if event_id in event_ids],
                required_flag_ids=[flag_id for flag_id in item.required_flag_ids if flag_id in flag_ids],
            )
        )
    return EndingAnchorSuggestionDraft(ending_anchor_suggestions=rows)


def merge_ending_anchor_suggestions(
    skeleton: EndingIntentDraft,
    suggestions: EndingAnchorSuggestionDraft,
    bundle: DesignBundle,
) -> EndingIntentDraft:
    normalized_suggestions = normalize_ending_anchor_suggestions(suggestions, bundle)
    suggestion_by_id = {item.ending_id: item for item in normalized_suggestions.ending_anchor_suggestions}
    merged_rows = []
    for intent in skeleton.ending_intents:
        if intent.ending_id == "mixed":
            merged_rows.append(
                EndingIntentSpec(
                    ending_id="mixed",
                    priority=10,
                    fallback=True,
                )
            )
            continue
        suggestion = suggestion_by_id.get(intent.ending_id)
        if suggestion is None:
            merged_rows.append(intent)
            continue
        merged_rows.append(
            EndingIntentSpec(
                ending_id=intent.ending_id,
                priority=_canonical_ending_priority(intent.ending_id),
                axis_ids=suggestion.axis_ids or intent.axis_ids,
                required_truth_ids=suggestion.required_truth_ids or intent.required_truth_ids,
                required_event_ids=suggestion.required_event_ids or intent.required_event_ids,
                required_flag_ids=suggestion.required_flag_ids or intent.required_flag_ids,
                fallback=bool(intent.fallback or intent.ending_id == "mixed"),
            )
        )
    return EndingIntentDraft(ending_intents=merged_rows)


def normalize_ending_intent_draft(
    ending_intent_draft: EndingIntentDraft,
    bundle: DesignBundle,
) -> EndingIntentDraft:
    ending_ids = {item.ending_id for item in bundle.story_bible.ending_catalog}
    axis_ids = {item.axis_id for item in bundle.state_schema.axes}
    truth_ids = {item.truth_id for item in bundle.story_bible.truth_catalog}
    event_ids = {event for beat in bundle.beat_spine for event in beat.required_events}
    flag_ids = {item.flag_id for item in bundle.state_schema.flags}
    normalized_intents = []
    seen_ids: set[str] = set()
    for intent in ending_intent_draft.ending_intents:
        if intent.ending_id not in ending_ids or intent.ending_id in seen_ids:
            continue
        seen_ids.add(intent.ending_id)
        normalized_intents.append(
            EndingIntentSpec(
                ending_id=intent.ending_id,
                priority=_canonical_ending_priority(intent.ending_id),
                axis_ids=[item for item in intent.axis_ids if item in axis_ids],
                required_truth_ids=[item for item in intent.required_truth_ids if item in truth_ids],
                required_event_ids=[item for item in intent.required_event_ids if item in event_ids],
                required_flag_ids=[item for item in intent.required_flag_ids if item in flag_ids],
                fallback=bool(intent.fallback or intent.ending_id == "mixed"),
            )
        )
    if not normalized_intents:
        return build_ending_skeleton(bundle)
    has_mixed = any(item.ending_id == "mixed" for item in normalized_intents)
    if not has_mixed:
        normalized_intents.append(
            EndingIntentSpec(
                ending_id="mixed",
                priority=10,
                fallback=True,
            )
        )
    return EndingIntentDraft(
        ending_intents=sorted(
            normalized_intents,
            key=lambda item: (_canonical_ending_priority(item.ending_id), item.ending_id),
        )
    )


def compile_ending_intent_draft(
    ending_intent_draft: EndingIntentDraft,
    bundle: DesignBundle,
) -> EndingRulesDraft:
    normalized_intent = normalize_ending_intent_draft(ending_intent_draft, bundle)
    defaults = normalize_ending_intent_draft(build_ending_skeleton(bundle), bundle)
    defaults_by_id = {item.ending_id: item for item in defaults.ending_intents}
    intents_by_id = {item.ending_id: item for item in normalized_intent.ending_intents}
    axis_kind_by_id = {item.axis_id: item.kind for item in bundle.state_schema.axes}
    pressure_axis = next((axis.axis_id for axis in bundle.state_schema.axes if axis.kind == "pressure"), bundle.state_schema.axes[0].axis_id)
    secondary_axis = next(
        (axis.axis_id for axis in bundle.state_schema.axes if axis.kind != "pressure"),
        next((axis.axis_id for axis in bundle.state_schema.axes if axis.axis_id != pressure_axis), pressure_axis),
    )

    def merged_intent(ending_id: str) -> EndingIntentSpec:
        default_intent = defaults_by_id[ending_id]
        current = intents_by_id.get(ending_id)
        if current is None:
            return default_intent
        return EndingIntentSpec(
            ending_id=ending_id,
            priority=current.priority,
            axis_ids=current.axis_ids or default_intent.axis_ids,
            required_truth_ids=current.required_truth_ids or default_intent.required_truth_ids,
            required_event_ids=current.required_event_ids or default_intent.required_event_ids,
            required_flag_ids=current.required_flag_ids or default_intent.required_flag_ids,
            fallback=bool(current.fallback or default_intent.fallback),
        )

    compiled_rules = []
    for ending_id in ("collapse", "pyrrhic", "mixed"):
        intent = merged_intent(ending_id)
        if ending_id == "mixed":
            compiled_rules.append(EndingRule(ending_id="mixed", priority=intent.priority, conditions={}))
            continue
        axis_ids = [item for item in intent.axis_ids if item in axis_kind_by_id]
        truth_ids = list(intent.required_truth_ids)
        event_ids = list(intent.required_event_ids)
        flag_ids = list(intent.required_flag_ids)
        if ending_id == "collapse":
            chosen_axis = next((item for item in axis_ids if axis_kind_by_id.get(item) == "pressure"), axis_ids[0] if axis_ids else pressure_axis)
            threshold = 5 if axis_kind_by_id.get(chosen_axis) == "pressure" else 4
            compiled_rules.append(
                EndingRule(
                    ending_id="collapse",
                    priority=intent.priority,
                    conditions={
                        "min_axes": {chosen_axis: threshold},
                        "required_truths": truth_ids[:1],
                        "required_events": event_ids[:1],
                        "required_flags": flag_ids[:1],
                    },
                )
            )
            continue
        success_axis = next((item for item in axis_ids if axis_kind_by_id.get(item) != "pressure"), axis_ids[0] if axis_ids else secondary_axis)
        cost_axis = next((item for item in axis_ids if axis_kind_by_id.get(item) == "pressure" and item != success_axis), pressure_axis)
        min_axes = {success_axis: 5}
        if cost_axis and cost_axis != success_axis:
            min_axes[cost_axis] = max(min_axes.get(cost_axis, 0), 3 if axis_kind_by_id.get(cost_axis) == "pressure" else 2)
        compiled_rules.append(
            EndingRule(
                ending_id="pyrrhic",
                priority=intent.priority,
                conditions={
                    "min_axes": min_axes,
                    "required_truths": truth_ids[:1],
                    "required_events": event_ids[:1],
                    "required_flags": flag_ids[:1],
                },
            )
        )
    return normalize_ending_rules_draft(
        EndingRulesDraft(ending_rules=compiled_rules),
        bundle,
    )


def normalize_ending_rules_draft(
    ending_rules_draft: EndingRulesDraft,
    bundle: DesignBundle,
) -> EndingRulesDraft:
    ending_ids = {item.ending_id for item in bundle.story_bible.ending_catalog}
    axis_ids = {item.axis_id for item in bundle.state_schema.axes}
    stance_ids = {item.stance_id for item in bundle.state_schema.stances}
    truth_ids = {item.truth_id for item in bundle.story_bible.truth_catalog}
    event_ids = {event for beat in bundle.beat_spine for event in beat.required_events}
    flag_ids = {item.flag_id for item in bundle.state_schema.flags}
    normalized_endings = []
    seen_ids: set[str] = set()
    for rule in ending_rules_draft.ending_rules:
        if rule.ending_id not in ending_ids or rule.ending_id in seen_ids:
            continue
        seen_ids.add(rule.ending_id)
        normalized_endings.append(
            EndingRule(
                ending_id=rule.ending_id,
                priority=_canonical_ending_priority(rule.ending_id),
                conditions={
                    "min_axes": {axis_id: value for axis_id, value in rule.conditions.min_axes.items() if axis_id in axis_ids},
                    "max_axes": {axis_id: value for axis_id, value in rule.conditions.max_axes.items() if axis_id in axis_ids},
                    "min_stances": {stance_id: value for stance_id, value in rule.conditions.min_stances.items() if stance_id in stance_ids},
                    "required_truths": [item for item in rule.conditions.required_truths if item in truth_ids],
                    "required_events": [item for item in rule.conditions.required_events if item in event_ids],
                    "required_flags": [item for item in rule.conditions.required_flags if item in flag_ids],
                },
            )
        )
    if not normalized_endings:
        normalized_endings = [EndingRule(ending_id="mixed", priority=_canonical_ending_priority("mixed"), conditions={})]
    return EndingRulesDraft(
        ending_rules=sorted(
            normalized_endings,
            key=lambda item: (_canonical_ending_priority(item.ending_id), item.ending_id),
        ),
    )


def build_default_ending_rules(bundle: DesignBundle) -> EndingRulesDraft:
    return compile_ending_intent_draft(build_ending_skeleton(bundle), bundle)

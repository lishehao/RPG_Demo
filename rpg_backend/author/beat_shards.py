from __future__ import annotations

from hashlib import sha256
import json
from time import perf_counter
from typing import Any

from rpg_backend.author.contracts import (
    AuthorBeatSnapshot,
    AuthorBundleSnapshot,
    BeatRuntimeHintCard,
    BeatRuntimeShard,
    DesignBundle,
)

_SNAPSHOT_VERSION = "v1"
_DRIFT_REASONS = {
    "context_hash_mismatch",
    "snapshot_invariant_violation",
    "out_of_scope_reference",
    "binding_scaffold_drift",
}


def _canonical_hash(payload: dict[str, Any]) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def build_bundle_snapshot(
    *,
    bundle: DesignBundle,
    primary_theme: str,
    story_frame_strategy: str,
    cast_strategy: str,
    beat_plan_strategy: str,
) -> AuthorBundleSnapshot:
    allowed_affordance_tags = sorted(
        {
            profile.affordance_tag
            for profile in bundle.rule_pack.affordance_effect_profiles
        }
        | {
            weight.tag
            for beat in bundle.beat_spine
            for weight in beat.affordances
        }
        | {
            tag
            for beat in bundle.beat_spine
            for tag in beat.blocked_affordances
        }
        | {
            beat.route_pivot_tag
            for beat in bundle.beat_spine
            if beat.route_pivot_tag is not None
        }
    )
    allowed_axis_ids = sorted(
        {
            item.axis_id
            for item in bundle.state_schema.axes
        }
        | {
            beat.pressure_axis_id
            for beat in bundle.beat_spine
            if beat.pressure_axis_id is not None
        }
    )
    invariants = {
        "language": bundle.focused_brief.language,
        "primary_theme": primary_theme,
        "strategy_family": {
            "story_frame_strategy": story_frame_strategy,
            "cast_strategy": cast_strategy,
            "beat_plan_strategy": beat_plan_strategy,
        },
        "allowed_axis_ids": allowed_axis_ids,
        "allowed_truth_ids": [item.truth_id for item in bundle.story_bible.truth_catalog],
        "allowed_event_ids": [
            event_id
            for beat in bundle.beat_spine
            for event_id in beat.required_events
        ],
        "allowed_flag_ids": [item.flag_id for item in bundle.state_schema.flags],
        "allowed_affordance_tags": allowed_affordance_tags,
        "beat_count": len(bundle.beat_spine),
        "cast_slot_count": len(bundle.story_bible.cast),
    }
    context_hash = _canonical_hash(invariants)
    return AuthorBundleSnapshot(
        snapshot_id=f"bundle_{context_hash[:12]}",
        snapshot_version=_SNAPSHOT_VERSION,
        context_hash=context_hash,
        required_invariants=invariants,
    )


def build_beat_snapshots(
    *,
    bundle: DesignBundle,
    bundle_snapshot: AuthorBundleSnapshot,
) -> list[AuthorBeatSnapshot]:
    snapshots: list[AuthorBeatSnapshot] = []
    allowed_focus_ids = {item.npc_id for item in bundle.story_bible.cast}
    for beat in bundle.beat_spine:
        invariants = {
            "language": bundle.focused_brief.language,
            "primary_theme": bundle_snapshot.required_invariants.get("primary_theme"),
            "strategy_family": dict(bundle_snapshot.required_invariants.get("strategy_family") or {}),
            "beat_id": beat.beat_id,
            "allowed_axis_ids": list(bundle_snapshot.required_invariants.get("allowed_axis_ids") or []),
            "allowed_truth_ids": list(bundle_snapshot.required_invariants.get("allowed_truth_ids") or []),
            "allowed_event_ids": list(bundle_snapshot.required_invariants.get("allowed_event_ids") or []),
            "allowed_flag_ids": list(bundle_snapshot.required_invariants.get("allowed_flag_ids") or []),
            "allowed_affordance_tags": list(bundle_snapshot.required_invariants.get("allowed_affordance_tags") or []),
            "allowed_focus_npc_ids": [npc_id for npc_id in beat.focus_npcs if npc_id in allowed_focus_ids],
            "allowed_conflict_npc_ids": [npc_id for npc_id in beat.conflict_npcs if npc_id in allowed_focus_ids],
        }
        hash_payload = {
            "bundle_snapshot_id": bundle_snapshot.snapshot_id,
            "beat_id": beat.beat_id,
            "focus_npc_ids": list(beat.focus_npcs),
            "conflict_npc_ids": list(beat.conflict_npcs),
            "pressure_axis_id": beat.pressure_axis_id,
            "required_truth_ids": list(beat.required_truths),
            "required_event_ids": list(beat.required_events),
            "route_pivot_tag": beat.route_pivot_tag,
            "affordance_tags": [weight.tag for weight in beat.affordances],
            "blocked_affordances": list(beat.blocked_affordances),
            "progress_required": beat.progress_required,
            "required_invariants": invariants,
        }
        context_hash = _canonical_hash(hash_payload)
        snapshots.append(
            AuthorBeatSnapshot(
                snapshot_id=f"beat_{beat.beat_id}_{context_hash[:12]}",
                snapshot_version=_SNAPSHOT_VERSION,
                context_hash=context_hash,
                beat_id=beat.beat_id,
                required_invariants=invariants,
                focus_npc_ids=list(beat.focus_npcs),
                conflict_npc_ids=list(beat.conflict_npcs),
                pressure_axis_id=beat.pressure_axis_id,
                required_truth_ids=list(beat.required_truths),
                required_event_ids=list(beat.required_events),
                route_pivot_tag=beat.route_pivot_tag,
                affordance_tags=[weight.tag for weight in beat.affordances],
                blocked_affordances=list(beat.blocked_affordances),
                progress_required=beat.progress_required,
            )
        )
    return snapshots


def deterministic_beat_runtime_shard(snapshot: AuthorBeatSnapshot) -> BeatRuntimeShard:
    interpret_cards = [
        BeatRuntimeHintCard(
            card_id="beat_card",
            content={
                "beat_id": snapshot.beat_id,
                "focus_npc_ids": list(snapshot.focus_npc_ids),
                "conflict_npc_ids": list(snapshot.conflict_npc_ids),
                "affordance_tags": list(snapshot.affordance_tags),
                "blocked_affordances": list(snapshot.blocked_affordances),
            },
        ),
        BeatRuntimeHintCard(
            card_id="id_scope_card",
            content={
                "allowed_axis_ids": list(snapshot.required_invariants.get("allowed_axis_ids") or []),
                "allowed_truth_ids": list(snapshot.required_invariants.get("allowed_truth_ids") or []),
                "allowed_event_ids": list(snapshot.required_invariants.get("allowed_event_ids") or []),
                "allowed_flag_ids": list(snapshot.required_invariants.get("allowed_flag_ids") or []),
                "allowed_affordance_tags": list(snapshot.required_invariants.get("allowed_affordance_tags") or []),
            },
        ),
    ]
    render_cards = [
        BeatRuntimeHintCard(
            card_id="beat_card",
            content={
                "beat_id": snapshot.beat_id,
                "focus_npc_ids": list(snapshot.focus_npc_ids),
                "conflict_npc_ids": list(snapshot.conflict_npc_ids),
                "pressure_axis_id": snapshot.pressure_axis_id,
                "progress_required": snapshot.progress_required,
            },
        ),
        BeatRuntimeHintCard(
            card_id="anchor_card",
            content={
                "required_truth_ids": list(snapshot.required_truth_ids),
                "required_event_ids": list(snapshot.required_event_ids),
                "route_pivot_tag": snapshot.route_pivot_tag,
                "affordance_tags": list(snapshot.affordance_tags),
                "blocked_affordances": list(snapshot.blocked_affordances),
            },
        ),
    ]
    closeout_cards = [
        BeatRuntimeHintCard(
            card_id="closeout_card",
            content={
                "beat_id": snapshot.beat_id,
                "progress_required": snapshot.progress_required,
                "required_truth_ids": list(snapshot.required_truth_ids),
                "required_event_ids": list(snapshot.required_event_ids),
                "route_pivot_tag": snapshot.route_pivot_tag,
            },
        )
    ]
    return BeatRuntimeShard(
        beat_id=snapshot.beat_id,
        snapshot_id=snapshot.snapshot_id,
        snapshot_version=snapshot.snapshot_version,
        context_hash=snapshot.context_hash,
        required_invariants=dict(snapshot.required_invariants),
        focus_npc_ids=list(snapshot.focus_npc_ids),
        conflict_npc_ids=list(snapshot.conflict_npc_ids),
        pressure_axis_id=snapshot.pressure_axis_id,
        required_truth_ids=list(snapshot.required_truth_ids),
        required_event_ids=list(snapshot.required_event_ids),
        route_pivot_tag=snapshot.route_pivot_tag,
        affordance_tags=list(snapshot.affordance_tags),
        blocked_affordances=list(snapshot.blocked_affordances),
        progress_required=snapshot.progress_required,
        interpret_hint_cards=interpret_cards,
        render_hint_cards=render_cards,
        closeout_hint_cards=closeout_cards,
        fallback_reason=None,
    )


def validate_beat_runtime_shard(
    *,
    shard: BeatRuntimeShard,
    snapshot: AuthorBeatSnapshot,
) -> list[str]:
    reasons: list[str] = []
    if shard.snapshot_id != snapshot.snapshot_id or shard.context_hash != snapshot.context_hash:
        reasons.append("context_hash_mismatch")
    if shard.beat_id != snapshot.beat_id:
        reasons.append("snapshot_invariant_violation")
    allowed_axes = set(snapshot.required_invariants.get("allowed_axis_ids") or [])
    allowed_truths = set(snapshot.required_invariants.get("allowed_truth_ids") or [])
    allowed_events = set(snapshot.required_invariants.get("allowed_event_ids") or [])
    allowed_affordances = set(snapshot.required_invariants.get("allowed_affordance_tags") or [])
    allowed_focus = set(snapshot.required_invariants.get("allowed_focus_npc_ids") or [])
    allowed_conflict = set(snapshot.required_invariants.get("allowed_conflict_npc_ids") or [])
    if shard.pressure_axis_id and shard.pressure_axis_id not in allowed_axes:
        reasons.append("out_of_scope_reference")
    if any(item not in allowed_truths for item in shard.required_truth_ids):
        reasons.append("out_of_scope_reference")
    if any(item not in allowed_events for item in shard.required_event_ids):
        reasons.append("out_of_scope_reference")
    if any(item not in allowed_affordances for item in shard.affordance_tags):
        reasons.append("out_of_scope_reference")
    if any(item not in allowed_affordances for item in shard.blocked_affordances):
        reasons.append("out_of_scope_reference")
    if any(item not in allowed_focus for item in shard.focus_npc_ids):
        reasons.append("binding_scaffold_drift")
    if any(item not in allowed_conflict for item in shard.conflict_npc_ids):
        reasons.append("binding_scaffold_drift")
    return sorted(set(reasons) & _DRIFT_REASONS)


def build_beat_runtime_shard_from_snapshot(snapshot: AuthorBeatSnapshot) -> tuple[BeatRuntimeShard, int, list[str]]:
    started_at = perf_counter()
    shard = deterministic_beat_runtime_shard(snapshot)
    reasons = validate_beat_runtime_shard(shard=shard, snapshot=snapshot)
    if reasons:
        fallback = deterministic_beat_runtime_shard(snapshot)
        fallback = fallback.model_copy(update={"fallback_reason": reasons[0]})
        return fallback, max(int((perf_counter() - started_at) * 1000), 0), reasons
    return shard, max(int((perf_counter() - started_at) * 1000), 0), []

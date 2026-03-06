from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class OutcomePalette:
    palette_id: str
    result_type: Literal["success", "partial", "fail_forward"]
    npc_reactions: tuple[str, ...]
    world_shifts: tuple[str, ...]
    clue_deltas: tuple[str, ...]
    cost_deltas: tuple[str, ...]
    next_hooks: tuple[str, ...]
    effect_profile: tuple[dict[str, object], ...]


OUTCOME_PALETTES: tuple[OutcomePalette, ...] = (
    OutcomePalette(
        palette_id="succ_diplomatic",
        result_type="success",
        npc_reactions=("Your calm tone lowers resistance.", "An ally nods and backs your call."),
        world_shifts=("Two bystanders clear a lane for you.", "A tense standoff softens for a moment."),
        clue_deltas=("A useful route hint slips out.", "You gain a reliable detail about timing."),
        cost_deltas=("You spend almost no extra effort.", "The move costs little beyond attention."),
        next_hooks=("Press the advantage before the window closes.", "Choose who to direct next."),
        effect_profile=(
            {"type": "add_event", "key": "diplomatic_progress"},
            {"type": "inc_state", "key": "trust", "value": 1},
            {"type": "advance_beat_progress", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="succ_discovery",
        result_type="success",
        npc_reactions=("Someone points at a hidden marker.", "A witness confirms your suspicion."),
        world_shifts=("A blocked path reveals a side opening.", "A sensor feed aligns with your hypothesis."),
        clue_deltas=("You secure a concrete clue fragment.", "A pattern finally makes sense."),
        cost_deltas=("You trade focus for clarity, but keep momentum.", "The gain is clean with minor strain."),
        next_hooks=("Follow the freshest clue immediately.", "Use this lead before it degrades."),
        effect_profile=(
            {"type": "add_event", "key": "clue_found"},
            {"type": "set_flag", "key": "fresh_lead", "value": True},
            {"type": "advance_beat_progress", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="succ_stealth",
        result_type="success",
        npc_reactions=("No one notices your shift in position.", "Your partner mirrors your quiet movement."),
        world_shifts=("Patrol focus drifts away from your lane.", "A blind spot opens for a short moment."),
        clue_deltas=("You spot a subtle access pattern.", "You capture a quiet indicator others missed."),
        cost_deltas=("You burn time but keep risk low.", "Careful pacing costs seconds, not safety."),
        next_hooks=("Move now while the blind spot lasts.", "Choose the next silent action."),
        effect_profile=(
            {"type": "add_event", "key": "stealth_window"},
            {"type": "inc_state", "key": "time_spent", "value": 1},
            {"type": "advance_beat_progress", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="succ_technical",
        result_type="success",
        npc_reactions=("Your technical call earns instant trust.", "The engineer on-site follows your lead."),
        world_shifts=("System readouts stabilize in your favor.", "An automated lock cycle pauses."),
        clue_deltas=("Diagnostics expose a useful control path.", "You map an actionable subsystem link."),
        cost_deltas=("You spend power, but avoid chaos.", "It consumes resources, not momentum."),
        next_hooks=("Exploit the stable subsystem now.", "Chain this with a decisive follow-up."),
        effect_profile=(
            {"type": "add_event", "key": "system_stable"},
            {"type": "inc_state", "key": "resource", "value": -1},
            {"type": "advance_beat_progress", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="succ_bold",
        result_type="success",
        npc_reactions=("The team rallies behind your assertive move.", "Your decisiveness cuts through hesitation."),
        world_shifts=("Opposition loses the initiative briefly.", "The situation tilts in your favor."),
        clue_deltas=("You force out a high-value tell.", "A hidden constraint is exposed."),
        cost_deltas=("You accept a manageable risk spike.", "You pay tempo to gain control."),
        next_hooks=("Capitalize before resistance recovers.", "Choose the riskiest high-value option next."),
        effect_profile=(
            {"type": "add_event", "key": "bold_push"},
            {"type": "inc_state", "key": "heat", "value": 1},
            {"type": "advance_beat_progress", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="part_tradeoff",
        result_type="partial",
        npc_reactions=("You get agreement, but only conditionally.", "An ally accepts with visible doubt."),
        world_shifts=("A door opens while another route closes.", "You gain access but trigger scrutiny."),
        clue_deltas=("You get a clue with gaps to resolve.", "Useful info arrives with uncertainty."),
        cost_deltas=("You trade trust for speed.", "You spend leverage to keep moving."),
        next_hooks=("Patch the new weakness on your next move.", "Follow up before the tradeoff worsens."),
        effect_profile=(
            {"type": "add_event", "key": "tradeoff_taken"},
            {"type": "inc_state", "key": "trust", "value": -1},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="part_costly",
        result_type="partial",
        npc_reactions=("The team follows, but looks strained.", "Someone warns this pace is expensive."),
        world_shifts=("Stability improves while resources thin out.", "Immediate danger drops, future risk grows."),
        clue_deltas=("You gain a clue after burning supplies.", "The answer comes at a practical cost."),
        cost_deltas=("Resource pressure increases.", "The win is real, the bill is immediate."),
        next_hooks=("Secure resources before the next push.", "Choose a low-cost move next."),
        effect_profile=(
            {"type": "add_event", "key": "costly_progress"},
            {"type": "inc_state", "key": "resource", "value": -2},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 2},
        ),
    ),
    OutcomePalette(
        palette_id="part_delay",
        result_type="partial",
        npc_reactions=("People comply, but too slowly.", "Your instruction lands, yet timing slips."),
        world_shifts=("The window narrows as clocks advance.", "External pressure increases mid-action."),
        clue_deltas=("You get incomplete timing intel.", "A clue arrives late but still helps."),
        cost_deltas=("You pay with time.", "Momentum slows but does not stop."),
        next_hooks=("Take a speed-oriented action now.", "Use the clue before it expires."),
        effect_profile=(
            {"type": "add_event", "key": "delay_pressure"},
            {"type": "inc_state", "key": "time_spent", "value": 2},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="part_noisy",
        result_type="partial",
        npc_reactions=("Your move works but draws attention.", "Nearby eyes turn toward your lane."),
        world_shifts=("Security posture tightens.", "A third party starts tracking your activity."),
        clue_deltas=("You gain a clue and reveal your intent.", "Information comes with a visibility penalty."),
        cost_deltas=("Heat increases.", "You keep momentum but raise exposure."),
        next_hooks=("Consider a stealth or misdirection move next.", "Use this opening before lockdown escalates."),
        effect_profile=(
            {"type": "add_event", "key": "noisy_progress"},
            {"type": "inc_state", "key": "heat", "value": 2},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="fail_pressure",
        result_type="fail_forward",
        npc_reactions=("Your first attempt misses, and urgency spikes.", "The room stiffens after your misstep."),
        world_shifts=("Time pressure rises sharply.", "Opposition tightens response protocols."),
        clue_deltas=("You learn what does not work.", "A failed angle reveals a safer next path."),
        cost_deltas=("You pay in time and composure.", "The setback costs tempo."),
        next_hooks=("Take a safer action that secures momentum.", "Ask for help and reframe quickly."),
        effect_profile=(
            {"type": "add_event", "key": "pressure_spike"},
            {"type": "inc_state", "key": "time_spent", "value": 2},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 2},
        ),
    ),
    OutcomePalette(
        palette_id="fail_complication",
        result_type="fail_forward",
        npc_reactions=("Your move backfires into argument.", "Coordination fractures under stress."),
        world_shifts=("A new complication enters the scene.", "A side actor interferes unexpectedly."),
        clue_deltas=("You discover a hidden constraint too late.", "The setback exposes a missing dependency."),
        cost_deltas=("Trust and heat both worsen.", "You lose social capital to keep moving."),
        next_hooks=("Stabilize relationships before forcing progress.", "Shift to a move that rebuilds trust."),
        effect_profile=(
            {"type": "add_event", "key": "complication_spawned"},
            {"type": "inc_state", "key": "trust", "value": -1},
            {"type": "inc_state", "key": "heat", "value": 1},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 2},
        ),
    ),
    OutcomePalette(
        palette_id="fail_misread",
        result_type="fail_forward",
        npc_reactions=("You read the signal wrong on first pass.", "A teammate catches the mismatch too late."),
        world_shifts=("You move into a suboptimal lane.", "The wrong assumption burns your margin."),
        clue_deltas=("A false clue is corrected mid-step.", "You recover with a partial correction."),
        cost_deltas=("You pay in confusion and time.", "The correction costs one extra cycle."),
        next_hooks=("Re-check assumptions with a focused scan.", "Take a clarifying move next."),
        effect_profile=(
            {"type": "add_event", "key": "misread_corrected"},
            {"type": "set_flag", "key": "needs_clarify", "value": True},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 1},
        ),
    ),
    OutcomePalette(
        palette_id="fail_sacrifice",
        result_type="fail_forward",
        npc_reactions=("An ally takes a hit to keep the line intact.", "You save the mission by sacrificing resources."),
        world_shifts=("Immediate collapse is avoided at a price.", "You hold position but deplete reserves."),
        clue_deltas=("You gain hard evidence from the failed attempt.", "The loss reveals a critical weak point."),
        cost_deltas=("Resource and morale dip.", "The team survives, but feels the strain."),
        next_hooks=("Secure a recovery step before the final push.", "Choose a stabilizing move next."),
        effect_profile=(
            {"type": "add_event", "key": "sacrifice_made"},
            {"type": "inc_state", "key": "resource", "value": -2},
            {"type": "inc_state", "key": "trust", "value": -1},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 2},
        ),
    ),
    OutcomePalette(
        palette_id="fail_detour",
        result_type="fail_forward",
        npc_reactions=("You are forced into a longer route.", "A fast plan collapses into a detour."),
        world_shifts=("The map shifts and new obstacles appear.", "You must route through a less stable corridor."),
        clue_deltas=("The detour reveals a side clue.", "You spot a secondary route marker."),
        cost_deltas=("You lose speed but keep agency.", "Time slips, options remain."),
        next_hooks=("Take a route-control move next.", "Use the detour clue to reconverge fast."),
        effect_profile=(
            {"type": "add_event", "key": "detour_taken"},
            {"type": "inc_state", "key": "time_spent", "value": 1},
            {"type": "advance_beat_progress", "value": 1},
            {"type": "cost", "value": 1},
        ),
    ),
)


OUTCOME_PALETTE_BY_ID: dict[str, OutcomePalette] = {palette.palette_id: palette for palette in OUTCOME_PALETTES}

from __future__ import annotations

from typing import Any

from rpg_backend.domain.pack_schema import NarrationSlots


def build_echo_commit_hook_parts(
    *,
    slots: NarrationSlots,
    interpreted_intent: str,
    result: str,
    strategy_style: str,
    stance_summary: str | None,
) -> tuple[str, str, str]:
    echo = f"Echo: You commit to '{interpreted_intent or 'an uncertain move'}'."
    commit = (
        "Commit: "
        f"{slots.npc_reaction} {slots.world_shift} {slots.clue_delta} {slots.cost_delta} "
        f"Result: {result}. Strategy style: {strategy_style}."
    )
    if stance_summary:
        commit = f"{commit} {stance_summary}"
    hook = f"Hook: {slots.next_hook}"
    return echo, commit, hook


def build_prompt_slots(
    *,
    slots: NarrationSlots,
    interpreted_intent: str,
    result: str,
    strategy_style: str,
    stance_summary: str | None,
) -> dict[str, Any]:
    echo, commit, hook = build_echo_commit_hook_parts(
        slots=slots,
        interpreted_intent=interpreted_intent,
        result=result,
        strategy_style=strategy_style,
        stance_summary=stance_summary,
    )
    return {
        "echo": echo,
        "commit": commit,
        "hook": hook,
        "strategy_style": strategy_style,
        "stance_summary": stance_summary or "",
    }


def build_narration_context(
    *,
    scene_id: str,
    next_scene_id: str | None,
    interpreted_intent: str,
    move_label: str,
    strategy_style: str,
    result: str,
    costs_summary: str,
    consequences_summary: str,
    stance_summary: str | None,
) -> dict[str, Any]:
    return {
        "scene_id": scene_id,
        "next_scene_id": next_scene_id,
        "interpreted_intent": interpreted_intent,
        "move_label": move_label,
        "strategy_style": strategy_style,
        "result": result,
        "costs_summary": costs_summary,
        "consequences_summary": consequences_summary,
        "stance_summary": stance_summary or "",
    }

from __future__ import annotations

from typing import Any

from rpg_backend.llm.agents import PlayAgent
from rpg_backend.runtime.compiled_pack import CompiledPlayRuntimePack
from rpg_backend.runtime.effects import apply_effects
from rpg_backend.runtime.narration import render_echo_commit_hook
from rpg_backend.runtime.pressure import apply_pressure_recoil
from rpg_backend.runtime.resolver import choose_outcome, resolve_next_scene
from rpg_backend.runtime.results import RuntimeStepResult
from rpg_backend.runtime.router import route_player_action
from rpg_backend.runtime.stance import apply_npc_stance_effects, build_stance_summary
from rpg_backend.runtime.ui import list_ui_moves


async def process_runtime_step(
    *,
    play_agent: PlayAgent,
    compiled_pack: CompiledPlayRuntimePack,
    session_id: str,
    current_scene_id: str,
    beat_index: int,
    state: dict[str, Any],
    beat_progress: dict[str, int],
    action_input: dict[str, Any],
    dev_mode: bool = False,
) -> RuntimeStepResult:
    # Stage 1: resolve current scene + intent routing.
    scene = compiled_pack.scene(current_scene_id)
    current_beat = compiled_pack.beat_at_index(beat_index)
    recognized = await route_player_action(
        play_agent,
        compiled_pack=compiled_pack,
        scene=scene,
        action_input=action_input,
        session_id=session_id,
        state=state,
        beat_progress=beat_progress,
        beat=current_beat,
        beat_index=beat_index,
    )
    chosen_move = compiled_pack.move(recognized["move_id"])

    # Stage 2: deterministic resolution + effect application.
    state.setdefault("values", {})
    state["values"]["last_move"] = chosen_move.id
    state["values"]["runtime_turn"] = int(state["values"].get("runtime_turn", 0)) + 1
    runtime_turn = int(state["values"]["runtime_turn"])

    current_beat_id = scene.beat_id
    outcome = choose_outcome(chosen_move, state, beat_progress, current_beat_id)
    costs, consequences, _ = apply_effects(outcome.effects, state, beat_progress, current_beat_id)

    # Stage 3: deterministic stance/pressure updates.
    stance_snapshot = apply_npc_stance_effects(
        state=state,
        present_npcs=list(scene.present_npcs),
        strategy_style=chosen_move.strategy_style,
        npc_profiles=compiled_pack.npc_profiles_by_name,
    )
    pressure_recoil_triggered = apply_pressure_recoil(
        pack=compiled_pack.pack,
        beat_index=beat_index,
        state=state,
        costs=costs,
        consequences=consequences,
    )

    # Stage 4: scene transition.
    next_scene_id, ended = resolve_next_scene(scene, outcome, state, beat_progress, current_beat_id)
    if next_scene_id is not None:
        current_scene_id = next_scene_id

    beat_index = compiled_pack.beat_index_for_scene(current_scene_id)

    # Stage 5: narration render from resolved facts.
    stance_summary = build_stance_summary(stance_snapshot) if runtime_turn % 2 == 0 else None
    narration_result = await render_echo_commit_hook(
        play_agent,
        outcome.narration_slots,
        recognized["interpreted_intent"],
        outcome.result,
        compiled_pack.pack.style_guard,
        session_id=session_id,
        strategy_style=chosen_move.strategy_style,
        scene_id=scene.id,
        next_scene_id=current_scene_id if not ended else None,
        move_label=chosen_move.label,
        costs_summary="; ".join(costs) if costs else "none",
        consequences_summary="; ".join(consequences) if consequences else "none",
        stance_summary=stance_summary,
    )
    narration_text = str(narration_result["text"])

    debug = None
    if dev_mode:
        debug = {
            "selected_move": chosen_move.id,
            "selected_outcome": outcome.id,
            "selected_strategy_style": chosen_move.strategy_style,
            "pressure_recoil_triggered": pressure_recoil_triggered,
            "stance_snapshot": stance_snapshot,
            "state": state,
            "beat_progress": beat_progress,
        }

    return RuntimeStepResult(
        scene_id=current_scene_id,
        beat_index=beat_index,
        ended=ended,
        narration_text=narration_text,
        recognized=recognized,
        resolution={
            "result": outcome.result,
            "costs_summary": "; ".join(costs) if costs else "none",
            "consequences_summary": "; ".join(consequences) if consequences else "none",
        },
        ui={
            "moves": list_ui_moves(compiled_pack, current_scene_id),
            "input_hint": compiled_pack.pack.input_hint,
        },
        runtime_metrics={
            "interpret_duration_ms": recognized.get("llm_duration_ms"),
            "interpret_gateway_mode": recognized.get("llm_gateway_mode"),
            "interpret_response_id": recognized.get("response_id"),
            "interpret_reasoning_summary": recognized.get("reasoning_summary"),
            "render_duration_ms": narration_result.get("llm_duration_ms"),
            "render_gateway_mode": narration_result.get("llm_gateway_mode"),
            "render_response_id": narration_result.get("response_id"),
            "render_reasoning_summary": narration_result.get("reasoning_summary"),
        },
        debug=debug,
    )

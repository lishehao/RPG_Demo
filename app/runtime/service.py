from __future__ import annotations

from typing import Any

from app.domain.pack_schema import Move, Scene, StoryPack
from app.llm.base import LLMProvider
from app.runtime.effects import apply_effects
from app.runtime.narration import render_echo_commit_hook
from app.runtime.resolver import choose_outcome, resolve_next_scene
from app.runtime.router import route_player_action


class RuntimeService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    @staticmethod
    def _scene_map(pack: StoryPack) -> dict[str, Scene]:
        return {scene.id: scene for scene in pack.scenes}

    @staticmethod
    def _move_map(pack: StoryPack) -> dict[str, Move]:
        return {move.id: move for move in pack.moves}

    @staticmethod
    def _beat_index_by_id(pack: StoryPack) -> dict[str, int]:
        return {beat.id: idx for idx, beat in enumerate(pack.beats)}

    def initialize_session_state(self, pack: StoryPack) -> tuple[str, int, dict[str, Any], dict[str, int]]:
        first_beat = pack.beats[0]
        beat_progress = {beat.id: 0 for beat in pack.beats}
        state = {
            "events": [],
            "inventory": [],
            "flags": {},
            "values": {"cost_total": 0},
        }
        return first_beat.entry_scene_id, 0, state, beat_progress

    def list_ui_moves(self, pack: StoryPack, scene_id: str) -> list[dict[str, Any]]:
        scene_map = self._scene_map(pack)
        move_map = self._move_map(pack)
        scene = scene_map[scene_id]
        move_ids = list(dict.fromkeys(scene.enabled_moves + scene.always_available_moves))
        ui_moves = []
        for move_id in move_ids:
            move = move_map.get(move_id)
            if move is None:
                continue
            ui_moves.append(
                {
                    "move_id": move.id,
                    "label": move.label,
                    "risk_hint": "has fail-forward consequences",
                }
            )
        return ui_moves

    def process_step(
        self,
        pack: StoryPack,
        current_scene_id: str,
        beat_index: int,
        state: dict[str, Any],
        beat_progress: dict[str, int],
        action_input: dict[str, Any],
        *,
        dev_mode: bool = False,
    ) -> dict[str, Any]:
        scene_map = self._scene_map(pack)
        move_map = self._move_map(pack)
        beat_index_by_id = self._beat_index_by_id(pack)

        scene = scene_map[current_scene_id]
        recognized = route_player_action(self.provider, scene, move_map, action_input)
        chosen_move = move_map[recognized["move_id"]]

        state.setdefault("values", {})
        state["values"]["last_move"] = chosen_move.id

        current_beat_id = scene.beat_id
        outcome = choose_outcome(chosen_move, state, beat_progress, current_beat_id)
        costs, consequences, _ = apply_effects(outcome.effects, state, beat_progress, current_beat_id)

        next_scene_id, ended = resolve_next_scene(scene, outcome, state, beat_progress, current_beat_id)
        if next_scene_id is not None:
            current_scene_id = next_scene_id

        next_scene = scene_map[current_scene_id]
        beat_index = beat_index_by_id[next_scene.beat_id]

        narration_text = render_echo_commit_hook(
            self.provider,
            outcome.narration_slots,
            recognized["interpreted_intent"],
            outcome.result,
            pack.style_guard,
        )

        response = {
            "scene_id": current_scene_id,
            "beat_index": beat_index,
            "ended": ended,
            "narration_text": narration_text,
            "recognized": recognized,
            "resolution": {
                "result": outcome.result,
                "costs_summary": "; ".join(costs) if costs else "none",
                "consequences_summary": "; ".join(consequences) if consequences else "none",
            },
            "ui": {
                "moves": self.list_ui_moves(pack, current_scene_id),
                "input_hint": pack.input_hint,
            },
        }

        if dev_mode:
            response["debug"] = {
                "selected_move": chosen_move.id,
                "selected_outcome": outcome.id,
                "state": state,
                "beat_progress": beat_progress,
            }

        return response

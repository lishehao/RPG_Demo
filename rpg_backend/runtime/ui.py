from __future__ import annotations

from typing import Any

from rpg_backend.runtime.compiled_pack import CompiledPlayRuntimePack

STRATEGY_RISK_HINTS = {
    "fast_dirty": "fast but dirty: raises noise and trust risk",
    "steady_slow": "steady but slow: lowers noise but spends time",
    "political_safe_resource_heavy": "politically safe: spends resources to preserve trust",
}


def list_ui_moves(compiled_pack: CompiledPlayRuntimePack, scene_id: str) -> list[dict[str, Any]]:
    move_ids = compiled_pack.scene_move_ids(scene_id)
    ui_moves = []
    for move_id in move_ids:
        move = compiled_pack.moves_by_id.get(move_id)
        if move is None:
            continue
        ui_moves.append(
            {
                "move_id": move.id,
                "label": move.label,
                "risk_hint": STRATEGY_RISK_HINTS.get(move.strategy_style, "has fail-forward consequences"),
            }
        )
    return ui_moves

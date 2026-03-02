from __future__ import annotations

from typing import Any

from rpg_backend.config.settings import get_settings
from rpg_backend.domain.constants import GLOBAL_CLARIFY_MOVE_ID, GLOBAL_HELP_ME_PROGRESS_MOVE_ID
from rpg_backend.domain.pack_schema import Move, Scene
from rpg_backend.llm.base import LLMProvider
from rpg_backend.runtime.errors import RuntimeRouteError


def route_player_action(
    provider: LLMProvider,
    scene: Scene,
    move_map: dict[str, Move],
    action_input: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    threshold = settings.routing_confidence_threshold

    available = list(dict.fromkeys(scene.enabled_moves + scene.always_available_moves))
    fallback_move = (
        GLOBAL_HELP_ME_PROGRESS_MOVE_ID if GLOBAL_HELP_ME_PROGRESS_MOVE_ID in available else GLOBAL_CLARIFY_MOVE_ID
    )
    if fallback_move not in available and available:
        fallback_move = available[0]

    if action_input.get("type") == "button":
        requested = action_input.get("move_id")
        if requested in available:
            return {
                "interpreted_intent": f"button:{requested}",
                "move_id": requested,
                "confidence": 1.0,
                "route_source": "button",
            }
        return {
            "interpreted_intent": f"button:{requested or 'invalid'}",
            "move_id": fallback_move,
            "confidence": 0.25,
            "route_source": "button_fallback",
        }

    text = action_input.get("text") or ""
    scene_context = {
        "moves": [
            {
                "id": move_id,
                "label": move_map[move_id].label,
                "intents": move_map[move_id].intents,
                "synonyms": move_map[move_id].synonyms,
            }
            for move_id in available
            if move_id in move_map
        ],
        "fallback_move": fallback_move,
        "scene_seed": scene.scene_seed,
    }
    provider_name = "openai"

    try:
        routed = provider.route_intent(scene_context, text)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeRouteError(
            error_code="llm_route_failed",
            message=f"route_intent failed after provider retries: {exc}",
            provider=provider_name,
        ) from exc

    chosen_move = routed.move_id
    confidence = float(routed.confidence)
    route_source = "llm"
    if chosen_move not in available:
        raise RuntimeRouteError(
            error_code="llm_route_invalid_move",
            message=f"route_intent returned unavailable move_id: {chosen_move}",
            provider=provider_name,
        )
    elif confidence < threshold:
        raise RuntimeRouteError(
            error_code="llm_route_low_confidence",
            message=f"route_intent confidence {confidence:.4f} below threshold {threshold:.4f}",
            provider=provider_name,
        )

    return {
        "interpreted_intent": routed.interpreted_intent,
        "move_id": chosen_move,
        "confidence": confidence,
        "route_source": route_source,
    }

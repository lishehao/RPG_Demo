from __future__ import annotations

import time
from typing import Any

from rpg_backend.config.settings import get_settings
from rpg_backend.domain.pack_schema import Beat, Scene
from rpg_backend.llm.agents import PlayAgent
from rpg_backend.runtime.compiled_pack import CompiledPlayRuntimePack
from rpg_backend.runtime.errors import RuntimeRouteError
from rpg_backend.runtime.route_context import (
    build_available_move_ids,
    build_llm_available_move_ids,
    build_route_candidates,
    build_route_key_map,
    build_scene_context,
    is_explicit_help_intent,
    resolve_fallback_move_id,
)


async def route_player_action(
    play_agent: PlayAgent,
    *,
    compiled_pack: CompiledPlayRuntimePack,
    scene: Scene,
    action_input: dict[str, Any],
    session_id: str,
    state: dict[str, Any] | None = None,
    beat_progress: dict[str, int] | None = None,
    beat: Beat | None = None,
    beat_index: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    threshold = settings.routing_confidence_threshold

    available_move_ids = build_available_move_ids(scene)
    fallback_move_id = resolve_fallback_move_id(available_move_ids)

    if action_input.get("type") == "button":
        requested = action_input.get("move_id")
        if requested in available_move_ids:
            return {
                "interpreted_intent": f"button:{requested}",
                "move_id": requested,
                "confidence": 1.0,
                "route_source": "button",
            }
        return {
            "interpreted_intent": f"button:{requested or 'invalid'}",
            "move_id": fallback_move_id,
            "confidence": 0.25,
            "route_source": "button_fallback",
        }

    text = action_input.get("text") or ""
    allow_global_help = is_explicit_help_intent(text)
    llm_available_move_ids = build_llm_available_move_ids(
        available_move_ids,
        allow_global_help=allow_global_help,
    )

    route_candidates = build_route_candidates(
        compiled_pack=compiled_pack,
        llm_available_move_ids=llm_available_move_ids,
    )
    route_key_map = build_route_key_map(route_candidates)
    scene_context = build_scene_context(
        scene=scene,
        beat=beat,
        beat_index=beat_index,
        state=state,
        beat_progress=beat_progress,
        allow_global_help=allow_global_help,
        fallback_move_id=fallback_move_id,
        route_candidates=route_candidates,
    )

    llm_backend = "responses"
    gateway_mode = "responses"
    route_started_at = time.perf_counter()

    try:
        routed = await play_agent.interpret_turn(
            session_id=session_id,
            scene_context=scene_context,
            route_candidates=route_candidates,
            text=text,
        )
        route_duration_ms = int(routed.diagnostics.duration_ms)
        gateway_mode = "responses"
    except Exception as exc:  # noqa: BLE001
        route_duration_ms = int((time.perf_counter() - route_started_at) * 1000)
        raise RuntimeRouteError(
            error_code="llm_route_failed",
            message=f"play agent interpret_turn failed: {exc}",
            llm_backend=llm_backend,
            llm_backend_error_code=getattr(exc, "llm_backend_error_code", None) or getattr(exc, "error_code", None),
            llm_duration_ms=route_duration_ms,
            gateway_mode=gateway_mode,
        ) from exc

    route_duration_ms = int(route_duration_ms or ((time.perf_counter() - route_started_at) * 1000))
    chosen_move = route_key_map.get(routed.selected_key)
    confidence = float(routed.confidence)
    route_source = "llm"
    if chosen_move not in llm_available_move_ids:
        raise RuntimeRouteError(
            error_code="llm_route_invalid_move",
            message=f"route chain returned unavailable selected_key: {routed.selected_key}",
            llm_backend=llm_backend,
            llm_duration_ms=route_duration_ms,
            gateway_mode=gateway_mode,
            response_id=routed.diagnostics.response_id,
            reasoning_summary=routed.diagnostics.reasoning_summary,
        )
    elif confidence < threshold:
        raise RuntimeRouteError(
            error_code="llm_route_low_confidence",
            message=f"route chain confidence {confidence:.4f} below threshold {threshold:.4f}",
            llm_backend=llm_backend,
            llm_duration_ms=route_duration_ms,
            gateway_mode=gateway_mode,
            response_id=routed.diagnostics.response_id,
            reasoning_summary=routed.diagnostics.reasoning_summary,
        )

    return {
        "interpreted_intent": routed.interpreted_intent,
        "move_id": chosen_move,
        "confidence": confidence,
        "route_source": route_source,
        "llm_duration_ms": route_duration_ms,
        "llm_gateway_mode": gateway_mode,
        "response_id": routed.diagnostics.response_id,
        "reasoning_summary": routed.diagnostics.reasoning_summary,
    }

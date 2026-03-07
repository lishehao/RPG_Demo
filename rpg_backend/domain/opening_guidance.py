from __future__ import annotations

from typing import Any

from rpg_backend.domain.constants import GLOBAL_MOVE_IDS
from rpg_backend.domain.pack_schema import OpeningGuidance, StoryPack


def _first_sentence(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    for separator in (". ", "! ", "? "):
        if separator in stripped:
            return stripped.split(separator, 1)[0].strip() + separator.strip()
    return stripped


def _clean_move_label(label: str) -> str:
    base = (label or "").split("[", 1)[0].strip()
    return base or (label or "").strip()


def build_opening_guidance_payload(
    *,
    title: str,
    description: str,
    input_hint: str,
    first_beat_title: str,
    first_scene_seed: str,
    first_scene_npcs: list[str],
    first_scene_moves: list[dict[str, str]],
) -> dict[str, Any]:
    title_text = (title or "This story").strip()
    beat_text = (first_beat_title or "the opening beat").strip()
    scene_text = _first_sentence(first_scene_seed) or "The first scene is unstable and already in motion."
    npc_text = ", ".join(first_scene_npcs[:2]) if first_scene_npcs else "your first allies"
    description_text = _first_sentence(description)
    intro_text = (
        f"You are stepping into {title_text}. {description_text} {scene_text} {npc_text} are already part of the opening pressure."
    ).strip()
    goal_hint = (
        f"Start with {beat_text.lower()} in mind: understand what is breaking first, what gets worse if you hesitate, and which ally or clue gives you the safest opening."
    ).strip()

    starter_prompts: list[str] = []
    clean_moves = [move for move in first_scene_moves if move.get("move_id") not in GLOBAL_MOVE_IDS]
    move_phrases = [_clean_move_label(move.get("label", "")) for move in clean_moves[:3]]
    fallback_phrases = [
        "inspect the first unstable clue and look for what is actually failing",
        "ask the most reliable ally what changed just before the pressure spiked",
        "move carefully through the opening scene and test the safest next action",
    ]
    for phrase in move_phrases:
        if phrase:
            starter_prompts.append(f"I {phrase[:1].lower()}{phrase[1:]}." if phrase[:1].isupper() else f"I {phrase}.")
    for phrase in fallback_phrases:
        if len(starter_prompts) >= 3:
            break
        starter_prompts.append(f"I {phrase}.")

    if input_hint.strip():
        goal_hint = f"{goal_hint} {input_hint.strip()}"

    return OpeningGuidance(
        intro_text=intro_text[:320],
        goal_hint=goal_hint[:220],
        starter_prompts=starter_prompts[:3],
    ).model_dump(mode="json")


def build_opening_guidance_for_pack(pack: StoryPack) -> OpeningGuidance:
    beat = pack.beats[0] if pack.beats else None
    scene_map = {scene.id: scene for scene in pack.scenes}
    entry_scene = scene_map.get(beat.entry_scene_id) if beat else None
    move_map = {move.id: move for move in pack.moves}
    first_scene_moves: list[dict[str, str]] = []
    if entry_scene is not None:
        for move_id in entry_scene.enabled_moves + entry_scene.always_available_moves:
            move = move_map.get(move_id)
            if move is None:
                continue
            first_scene_moves.append({"move_id": move.id, "label": move.label})

    payload = build_opening_guidance_payload(
        title=pack.title,
        description=pack.description,
        input_hint=pack.input_hint,
        first_beat_title=beat.title if beat is not None else "the opening beat",
        first_scene_seed=entry_scene.scene_seed if entry_scene is not None else "The opening scene is already unstable.",
        first_scene_npcs=entry_scene.present_npcs if entry_scene is not None else pack.npcs[:2],
        first_scene_moves=first_scene_moves,
    )
    return OpeningGuidance.model_validate(payload)

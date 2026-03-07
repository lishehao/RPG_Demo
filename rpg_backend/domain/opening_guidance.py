from __future__ import annotations

import re
from typing import Any

from rpg_backend.domain.constants import GLOBAL_MOVE_IDS
from rpg_backend.domain.pack_schema import OpeningGuidance, StoryPack

_OBSERVE_KEYWORDS = (
    'trace',
    'scan',
    'inspect',
    'survey',
    'decode',
    'analyze',
    'study',
    'read',
    'look',
)

_ASK_KEYWORDS = (
    'ask',
    'broker',
    'convince',
    'calm',
    'clarify',
    'negotiate',
    'appeal',
    'question',
)


def _first_sentence(text: str) -> str:
    stripped = (text or '').strip()
    if not stripped:
        return ''
    for separator in ('. ', '! ', '? '):
        if separator in stripped:
            return stripped.split(separator, 1)[0].strip() + separator.strip()
    return stripped


def _clean_move_label(label: str) -> str:
    base = (label or '').split('[', 1)[0].strip()
    return base or (label or '').strip()


def _normalized_move_phrase(label: str) -> str:
    phrase = re.sub(r'\s+', ' ', _clean_move_label(label)).strip().rstrip('.')
    return phrase[:1].lower() + phrase[1:] if phrase[:1].isupper() else phrase


def _select_phrase(first_scene_moves: list[dict[str, str]], keywords: tuple[str, ...], *, excluded: set[str] | None = None) -> str | None:
    excluded_phrases = excluded or set()
    for move in first_scene_moves:
        move_id = move.get('move_id') or ''
        if move_id in GLOBAL_MOVE_IDS:
            continue
        phrase = _normalized_move_phrase(move.get('label', ''))
        if not phrase or phrase in excluded_phrases:
            continue
        if any(keyword in phrase for keyword in keywords):
            return phrase
    return None


def _fallback_phrase(first_scene_moves: list[dict[str, str]], *, excluded: set[str] | None = None) -> str | None:
    excluded_phrases = excluded or set()
    for move in first_scene_moves:
        move_id = move.get('move_id') or ''
        if move_id in GLOBAL_MOVE_IDS:
            continue
        phrase = _normalized_move_phrase(move.get('label', ''))
        if phrase and phrase not in excluded_phrases:
            return phrase
    return None


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
    title_text = (title or 'This story').strip()
    beat_text = (first_beat_title or 'the opening beat').strip()
    scene_text = _first_sentence(first_scene_seed) or 'The first scene is unstable and already in motion.'
    lead_npc = first_scene_npcs[0] if first_scene_npcs else 'the nearest ally'
    support_npc_text = ', '.join(first_scene_npcs[:2]) if first_scene_npcs else 'your first allies'
    description_text = _first_sentence(description)
    intro_text = (
        f'You are stepping into {title_text}. {description_text} {scene_text} {support_npc_text} are already part of the opening pressure.'
    ).strip()
    goal_hint = (
        f'Start with {beat_text.lower()} in mind: understand what is breaking first, what gets worse if you hesitate, and which clue or ally gives you the safest opening.'
    ).strip()

    observe_phrase = _select_phrase(first_scene_moves, _OBSERVE_KEYWORDS)
    ask_phrase = _select_phrase(first_scene_moves, _ASK_KEYWORDS, excluded={observe_phrase} if observe_phrase else set())
    action_phrase = _fallback_phrase(first_scene_moves, excluded={phrase for phrase in (observe_phrase, ask_phrase) if phrase})

    observe_prompt = (
        f'I begin by observing the scene closely and {observe_phrase} to uncover the first reliable clue.'
        if observe_phrase
        else 'I begin by observing the scene closely and look for the clearest sign of what is failing.'
    )
    ask_prompt = (
        f'I ask {lead_npc} what changed just before the pressure spiked and what they think matters most.'
    )
    action_prompt = (
        f'I take a decisive first action and {action_phrase} before the pressure spreads any further.'
        if action_phrase
        else 'I take a decisive first action to stabilize the situation before the pressure spreads any further.'
    )

    if input_hint.strip():
        goal_hint = f'{goal_hint} {input_hint.strip()}'

    return OpeningGuidance(
        intro_text=intro_text[:320],
        goal_hint=goal_hint[:220],
        starter_prompts=[observe_prompt, ask_prompt, action_prompt],
    ).model_dump(mode='json')


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
            first_scene_moves.append({'move_id': move.id, 'label': move.label})

    payload = build_opening_guidance_payload(
        title=pack.title,
        description=pack.description,
        input_hint=pack.input_hint,
        first_beat_title=beat.title if beat is not None else 'the opening beat',
        first_scene_seed=entry_scene.scene_seed if entry_scene is not None else 'The opening scene is already unstable.',
        first_scene_npcs=entry_scene.present_npcs if entry_scene is not None else pack.npcs[:2],
        first_scene_moves=first_scene_moves,
    )
    return OpeningGuidance.model_validate(payload)

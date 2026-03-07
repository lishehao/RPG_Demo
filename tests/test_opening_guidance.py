from __future__ import annotations

from rpg_backend.domain.opening_guidance import build_opening_guidance_payload


def test_opening_guidance_payload_builds_observe_ask_act_prompts() -> None:
    payload = build_opening_guidance_payload(
        title='Forest Siege',
        description='A warded city is slipping toward collapse.',
        input_hint='Type anything you want to do, or choose a move.',
        first_beat_title='The First Silence Breaks',
        first_scene_seed='The first ward flickers above a crowded square.',
        first_scene_npcs=['Elira Voss', 'Kaelen Rook'],
        first_scene_moves=[
            {'move_id': 'trace_anomaly', 'label': 'Trace The Anomaly [fast but dirty]'},
            {'move_id': 'convince_guard', 'label': 'Negotiate Passage [politically safe, resource heavy]'},
            {'move_id': 'reroute_power', 'label': 'Reroute Emergency Power [steady but slow]'},
        ],
    )

    prompts = payload['starter_prompts']
    assert len(prompts) == 3
    assert prompts[0].startswith('I begin by observing')
    assert prompts[1].startswith('I ask Elira Voss')
    assert prompts[2].startswith('I take a decisive first action')

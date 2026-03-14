from __future__ import annotations

from types import SimpleNamespace

from rpg_backend.llm.task_specs import (
    AUTHOR_BEAT_PLAN_CHANNEL,
    AUTHOR_OVERVIEW_CHANNEL,
    AUTHOR_SCENE_CHANNEL,
    PLAY_CHANNEL,
    build_readiness_probe_task,
    build_responses_task_spec_bundle,
    validate_readiness_probe_payload,
)


def test_readiness_probe_task_and_payload_validation() -> None:
    spec = build_readiness_probe_task()
    assert spec.task_name == "readiness_probe"
    assert spec.user_payload == "who are you"
    parsed = validate_readiness_probe_payload({"ok": True, "who": "responses-ready"})
    assert parsed.ok is True


def test_responses_task_specs_are_centralized_and_resolved_from_settings() -> None:
    settings = SimpleNamespace(
        responses_enable_thinking_play=False,
        responses_enable_thinking_author_overview=False,
        responses_enable_thinking_author_beat_plan=True,
        responses_enable_thinking_author_scene=True,
        responses_enable_thinking_story_quality_judge=True,
        responses_max_output_tokens_play_interpret=180,
        responses_max_output_tokens_play_render=360,
        responses_max_output_tokens_author_overview=760,
        responses_max_output_tokens_author_beat_plan=1500,
        responses_max_output_tokens_author_scene=1600,
        responses_max_output_tokens_story_quality_judge=640,
    )
    specs = build_responses_task_spec_bundle(settings=settings)  # type: ignore[arg-type]

    assert specs.play_interpret.channel == PLAY_CHANNEL
    assert specs.play_render.channel == PLAY_CHANNEL
    assert specs.author_overview.channel == AUTHOR_OVERVIEW_CHANNEL
    assert specs.author_beat_plan.channel == AUTHOR_BEAT_PLAN_CHANNEL
    assert specs.author_scene.channel == AUTHOR_SCENE_CHANNEL
    assert specs.story_quality_judge.channel is None
    assert specs.play_interpret.enable_thinking is False
    assert specs.author_beat_plan.enable_thinking is True
    assert specs.author_scene.enable_thinking is True
    assert specs.story_quality_judge.enable_thinking is True
    assert specs.play_interpret.output_mode == "strict_json"
    assert specs.play_render.output_mode == "text"
    assert specs.play_interpret.max_output_tokens == 180
    assert specs.play_render.max_output_tokens == 360
    assert specs.author_overview.max_output_tokens == 760
    assert specs.author_beat_plan.max_output_tokens == 1500
    assert specs.author_scene.max_output_tokens == 1600
    assert specs.story_quality_judge.max_output_tokens == 640

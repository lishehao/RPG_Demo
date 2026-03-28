from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from rpg_backend.author.contracts import FocusedBrief
from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.author.generation import beats as beat_generation
from rpg_backend.author.generation import cast as cast_generation
from rpg_backend.author.generation import endings as ending_generation
from rpg_backend.author.generation import routes as route_generation
from rpg_backend.author.generation import story_frame as story_generation
from rpg_backend.llm_gateway import TextCapabilityRequest
from rpg_backend.config import Settings
import rpg_backend.responses_transport as responses_transport_module
from rpg_backend.responses_transport import build_json_transport, usage_to_dict
from tests.author_fixtures import (
    FakeClient,
    FakeChatClient,
    author_fixture_bundle,
    cast_draft,
    cast_overview_draft,
    ending_anchor_suggestion_payload,
    route_opportunity_plan_draft,
    story_frame_draft,
    story_frame_scaffold_draft,
    beat_plan_skeleton_draft,
)


class _StaticGatewayCore:
    def __init__(
        self,
        client,
        *,
        model: str,
        transport_style: str,
        use_session_cache: bool,
    ) -> None:
        self.client = client
        self.model = model
        self.transport_style = transport_style
        self.use_session_cache = use_session_cache
        self.call_trace: list[dict[str, object]] = []
        self._budget_by_capability = {
            "author.story_frame_scaffold": 700,
            "author.story_frame_finalize": 700,
            "author.cast_member_generate": 700,
            "author.cast_member_repair": 700,
            "author.character_instance_variation": 700,
            "author.spark_seed_generate": 220,
            "author.beat_plan_generate": 900,
            "author.beat_skeleton_generate": 900,
            "author.beat_repair": 700,
            "author.rulepack_generate": 900,
            "copilot.reply": 700,
            "copilot.rewrite_plan": 900,
        }
        self._transport = build_json_transport(
            style=transport_style,  # type: ignore[arg-type]
            client=client,  # type: ignore[arg-type]
            model=model,
            timeout_seconds=20.0,
            use_session_cache=use_session_cache,
            temperature=0.2,
            enable_thinking=False,
            provider_failed_code="llm_provider_failed",
            invalid_response_code="llm_invalid_response",
            invalid_json_code="llm_invalid_json",
            error_factory=lambda code, message, status_code: AuthorGatewayError(code=code, message=message, status_code=status_code),
            call_trace=self.call_trace,  # type: ignore[arg-type]
        )

    def text_policy(self, capability: str):
        return SimpleNamespace(
            capability=capability,
            max_output_tokens=self._budget_by_capability.get(capability),
            transport_style=self.transport_style,
            use_session_cache=self.use_session_cache,
            enable_thinking=False,
            model=self.model,
        )

    def invoke_text_capability(self, capability: str, request: TextCapabilityRequest):
        raw = self._transport.invoke_json(
            system_prompt=request.system_prompt,
            user_payload=request.user_payload,
            max_output_tokens=request.max_output_tokens,
            previous_response_id=request.previous_response_id,
            operation_name=request.operation_name,
            plaintext_fallback_key=request.plaintext_fallback_key,
        )
        return SimpleNamespace(
            payload=raw.payload,
            response_id=raw.response_id,
            usage=raw.usage,
            input_characters=raw.input_characters,
            capability=capability,
            provider="test",
            model=self.model,
            transport_style=self.transport_style,
            fallback_source=getattr(raw, "fallback_source", None),
        )


def _gateway(client: FakeClient) -> _StaticGatewayCore:
    return _StaticGatewayCore(
        client,
        model="demo-model",
        transport_style="responses",
        use_session_cache=True,
    )


def _chat_gateway(client: FakeChatClient) -> _StaticGatewayCore:
    return _StaticGatewayCore(
        client,
        model="gemini-2.5-pro",
        transport_style="chat_completions",
        use_session_cache=False,
    )


def test_shared_transport_usage_normalizer_extracts_cache_fields() -> None:
    usage = usage_to_dict(
        {
            "input_tokens": 120,
            "output_tokens": 40,
            "total_tokens": 160,
            "output_tokens_details": {"reasoning_tokens": 12},
            "x_details": [
                {
                    "x_billing_type": "response_api",
                    "prompt_tokens_details": {
                        "cached_tokens": 60,
                        "cache_creation_input_tokens": 20,
                        "cache_type": "ephemeral",
                    },
                }
            ],
        }
    )

    assert usage["input_tokens"] == 120
    assert usage["cached_input_tokens"] == 60
    assert usage["cache_creation_input_tokens"] == 20
    assert usage["billing_type"] == "response_api"
    assert usage["cache_type"] == "ephemeral"


def test_shared_transport_is_single_usage_normalizer_definition() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    matches: list[str] = []
    for path in (repo_root / "rpg_backend").rglob("*.py"):
        if "def usage_to_dict" in path.read_text():
            matches.append(path.relative_to(repo_root).as_posix())
    assert matches == ["rpg_backend/responses_transport.py"]


def test_play_router_module_removed_after_shared_story_profile_refactor() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "rpg_backend" / "play" / "router.py").exists()


def test_gateway_formats_requests_and_parses_models() -> None:
    client = FakeClient(
        [
            story_frame_scaffold_draft().model_dump(mode="json"),
            cast_overview_draft().model_dump(mode="json"),
            cast_draft().model_dump(mode="json"),
            beat_plan_skeleton_draft().model_dump(mode="json"),
        ]
    )
    gateway = _gateway(client)
    focused_brief = author_fixture_bundle().focused_brief

    story_frame = story_generation.generate_story_frame(gateway, focused_brief)
    cast_overview = cast_generation.generate_cast_overview(
        gateway,
        focused_brief,
        story_frame.value,
        previous_response_id=story_frame.response_id,
    )
    cast = cast_generation.generate_story_cast(
        gateway,
        focused_brief,
        story_frame.value,
        cast_overview.value,
        previous_response_id=cast_overview.response_id or story_frame.response_id,
    )
    beat_plan = beat_generation.generate_beat_plan(
        gateway,
        focused_brief,
        story_frame.value,
        cast.value,
        previous_response_id=cast.response_id or story_frame.response_id,
    )

    assert story_frame.value.title == "Archive Blackout"
    assert cast.value.cast[0].name == "Envoy Iri"
    assert beat_plan.value.beats[0].title == "The First Nightfall"
    assert client.calls[0]["model"] == "demo-model"
    assert client.calls[0]["max_output_tokens"] == 900
    assert "Return one strict JSON object matching StoryFrameScaffoldDraft" in client.calls[0]["instructions"]
    assert "Return one strict JSON object matching CastOverviewDraft" in client.calls[1]["instructions"]
    assert "Return one strict JSON object matching CastDraft" in client.calls[2]["instructions"]
    assert "Return one strict JSON object matching BeatPlanSkeletonDraft" in client.calls[3]["instructions"]
    assert client.calls[1]["previous_response_id"] == "resp-1"
    assert client.calls[2]["previous_response_id"] == "resp-2"
    assert client.calls[3]["previous_response_id"] == "resp-3"
    beat_skeleton_payload = json.loads(client.calls[3]["input"])
    assert "author_context" in beat_skeleton_payload
    assert "story_frame" not in beat_skeleton_payload
    assert "cast" not in beat_skeleton_payload


def test_build_openai_client_disables_sdk_retries_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(responses_transport_module, "OpenAI", _FakeOpenAI)

    responses_transport_module.build_openai_client(
        base_url="https://example.com/v1",
        api_key="test-key",
        use_session_cache=False,
        session_cache_header="x-cache",
        session_cache_value="enable",
    )

    assert captured["max_retries"] == 0


def test_build_openai_client_normalizes_full_responses_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(responses_transport_module, "OpenAI", _FakeOpenAI)

    responses_transport_module.build_openai_client(
        base_url="https://example.com/v1/responses",
        api_key="test-key",
        use_session_cache=False,
        session_cache_header="x-cache",
        session_cache_value="enable",
    )

    assert captured["base_url"] == "https://example.com/v1"


def test_preview_mode_reduces_story_frame_scaffold_budget_and_prompt_weight() -> None:
    client = FakeClient([story_frame_scaffold_draft().model_dump(mode="json")])
    gateway = _gateway(client)
    focused_brief = author_fixture_bundle().focused_brief

    story_generation.generate_story_frame(
        gateway,
        focused_brief,
        preview_mode=True,
    )

    assert client.calls[0]["max_output_tokens"] <= 560
    assert "This is for preview only." in client.calls[0]["instructions"]


def test_gateway_session_cache_respects_transport_style() -> None:
    settings = Settings(
        _env_file=None,
        gateway_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        gateway_api_key="test-key",
        gateway_model="gemini-2.5-pro",
    )

    assert settings.resolved_gateway_use_session_cache(transport_style="chat_completions") is False
    assert settings.resolved_gateway_use_session_cache(transport_style="responses") is False


def test_chat_completion_gateway_formats_requests_and_parses_models() -> None:
    client = FakeChatClient(
        [
            story_frame_scaffold_draft().model_dump(mode="json"),
            cast_overview_draft().model_dump(mode="json"),
            cast_draft().model_dump(mode="json"),
            beat_plan_skeleton_draft().model_dump(mode="json"),
        ]
    )
    gateway = _chat_gateway(client)
    focused_brief = author_fixture_bundle().focused_brief

    story_frame = story_generation.generate_story_frame(gateway, focused_brief)
    cast_overview = cast_generation.generate_cast_overview(
        gateway,
        focused_brief,
        story_frame.value,
        previous_response_id=story_frame.response_id,
    )
    cast = cast_generation.generate_story_cast(
        gateway,
        focused_brief,
        story_frame.value,
        cast_overview.value,
        previous_response_id=cast_overview.response_id or story_frame.response_id,
    )
    beat_plan = beat_generation.generate_beat_plan(
        gateway,
        focused_brief,
        story_frame.value,
        cast.value,
        previous_response_id=cast.response_id or story_frame.response_id,
    )

    assert story_frame.value.title == "Archive Blackout"
    assert cast.value.cast[0].name == "Envoy Iri"
    assert beat_plan.value.beats[0].title == "The First Nightfall"
    assert client.calls[0]["model"] == "gemini-2.5-pro"
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert client.calls[0]["messages"][0]["role"] == "system"
    assert client.calls[0]["messages"][1]["role"] == "user"
    assert "previous_response_id" not in client.calls[1]


def test_gateway_compiles_story_frame_from_semantics_without_second_llm_call() -> None:
    client = FakeClient([story_frame_scaffold_draft().model_dump(mode="json")])
    gateway = _gateway(client)

    story_frame = story_generation.generate_story_frame(
        gateway,
        author_fixture_bundle().focused_brief,
    )

    assert story_frame.value.title == "Archive Blackout"
    assert story_frame.response_id == "resp-1"
    assert story_frame.value.premise.startswith("In ")
    assert len(client.calls) == 1


def test_gateway_retries_story_frame_semantics_after_invalid_json() -> None:
    client = FakeClient(["not json at all", story_frame_scaffold_draft().model_dump(mode="json")])
    gateway = _gateway(client)

    story_frame = story_generation.generate_story_frame(
        gateway,
        FocusedBrief(
            story_kernel="A mediator keeping a city together",
            setting_signal="city during a blackout and succession crisis",
            core_conflict="keep a city together while a blackout and succession crisis strains civic order",
            tone_signal="Hopeful civic fantasy.",
            hard_constraints=[],
            forbidden_tones=[],
        ),
    )

    assert len(client.calls) == 2
    assert story_frame.value.title == "Archive Blackout"


def test_gateway_stabilizes_generic_story_frame_scaffold_before_compile() -> None:
    fixture = author_fixture_bundle()
    client = FakeClient(
        [
            {
                "title_seed": "A Mediator Keeping A City Together",
                "setting_frame": "city during a blackout and succession crisis",
                "protagonist_mandate": "a mediator keeping a city together",
                "opposition_force": "keep a city together while a blackout and succession crisis strains civic order",
                "stakes_core": "Prevent coalition collapse.",
                "tone": "hopeful political fantasy",
                "world_rules": fixture.story_frame.world_rules,
                "truths": [item.model_dump(mode="json") for item in fixture.story_frame.truths],
                "state_axis_choices": [item.model_dump(mode="json") for item in fixture.story_frame.state_axis_choices],
                "flags": [item.model_dump(mode="json") for item in fixture.story_frame.flags],
            }
        ]
    )
    gateway = _gateway(client)

    story_frame = story_generation.generate_story_frame(
        gateway,
        FocusedBrief(
            story_kernel="A mediator keeping a city together",
            setting_signal="city during a blackout and succession crisis",
            core_conflict="keep a city together while a blackout and succession crisis strains civic order",
            tone_signal="Hopeful civic fantasy.",
            hard_constraints=[],
            forbidden_tones=[],
        ),
    )

    assert story_frame.value.title == "The Dimmed Accord"
    assert "A Mediator Keeping A City Together" not in story_frame.value.premise


def test_gateway_compiles_beat_plan_from_single_semantics_call() -> None:
    client = FakeClient([beat_plan_skeleton_draft().model_dump(mode="json")])
    gateway = _gateway(client)
    fixture = author_fixture_bundle()

    beat_plan = beat_generation.generate_beat_plan(
        gateway,
        fixture.focused_brief,
        fixture.story_frame,
        fixture.cast_draft,
    )

    assert beat_plan.response_id == "resp-1"
    assert len(client.calls) == 1
    assert [beat.title for beat in beat_plan.value.beats] == [
        "The First Nightfall",
        "The Public Ledger",
        "The Dawn Bargain",
    ]
    assert [beat.milestone_kind for beat in beat_plan.value.beats] == [
        "reveal",
        "containment",
        "commitment",
    ]
    assert all(beat.return_hooks for beat in beat_plan.value.beats)


def test_gateway_retries_beat_plan_skeleton_after_invalid_json() -> None:
    client = FakeClient(["not json at all", beat_plan_skeleton_draft().model_dump(mode="json")])
    gateway = _gateway(client)
    fixture = author_fixture_bundle()

    beat_plan = beat_generation.generate_beat_plan(
        gateway,
        fixture.focused_brief,
        fixture.story_frame,
        fixture.cast_draft,
    )

    assert len(client.calls) == 2
    assert [beat.title for beat in beat_plan.value.beats] == [
        "The First Nightfall",
        "The Public Ledger",
        "The Dawn Bargain",
    ]


def test_gateway_compiles_cast_member_semantics_and_replaces_role_label_name() -> None:
    client = FakeClient(
        [
            {
                "name": "Leverage Broker",
                "agenda_detail": "Uses a private shipping ledger to squeeze concessions out of every public delay.",
                "red_line_detail": "Will burn the room down politically before accepting exclusion from the settlement.",
                "pressure_detail": "Starts framing every compromise as proof that the balance of power must change immediately.",
            }
        ]
    )
    gateway = _gateway(client)
    fixture = author_fixture_bundle()
    slot = fixture.cast_overview.cast_slots[2].model_dump(mode="json")

    member = cast_generation.generate_story_cast_member(
        gateway,
        fixture.focused_brief,
        fixture.story_frame,
        slot,
        existing_cast=[
            fixture.cast_draft.cast[0].model_dump(mode="json"),
            fixture.cast_draft.cast[1].model_dump(mode="json"),
        ],
    )

    assert member.value.name != "Leverage Broker"
    assert member.value.role == "Coalition rival"
    assert "Exploit the blackout to reshape the balance of power." in member.value.agenda
    assert "Will not accept being shut out of the final order." in member.value.red_line
    assert "Frames every emergency as proof that someone else should lose authority." in member.value.pressure_signature


def test_gateway_retries_cast_member_semantics_after_invalid_json() -> None:
    client = FakeClient(
        [
            "not json at all",
            {
                "name": "Mara Kestrel",
                "agenda_detail": "Uses a private relief ledger to force concessions whenever the room stalls.",
                "red_line_detail": "Will take public blame over quiet exclusion from the settlement.",
                "pressure_detail": "Sharpens into open leverage the moment delay starts protecting someone else.",
            },
        ]
    )
    gateway = _gateway(client)
    fixture = author_fixture_bundle()
    slot = fixture.cast_overview.cast_slots[2].model_dump(mode="json")

    member = cast_generation.generate_story_cast_member(
        gateway,
        fixture.focused_brief,
        fixture.story_frame,
        slot,
        existing_cast=[
            fixture.cast_draft.cast[0].model_dump(mode="json"),
            fixture.cast_draft.cast[1].model_dump(mode="json"),
        ],
    )

    assert len(client.calls) == 2
    assert member.value.name == "Mara Kestrel"
    assert "Exploit the blackout to reshape the balance of power." in member.value.agenda


def test_gateway_raises_stable_error_for_invalid_json() -> None:
    client = FakeClient(["not json at all", "not json at all", "not json at all"])
    gateway = _gateway(client)

    try:
        story_generation.generate_story_frame(
            gateway,
            author_fixture_bundle().focused_brief,
        )
    except AuthorGatewayError as exc:
        assert exc.code == "llm_invalid_json"
    else:  # pragma: no cover
        raise AssertionError("Expected AuthorGatewayError")


def test_rule_generation_uses_author_context_packets() -> None:
    client = FakeClient(
        [
            route_opportunity_plan_draft().model_dump(mode="json"),
            ending_anchor_suggestion_payload(),
        ]
    )
    gateway = _gateway(client)
    fixture = author_fixture_bundle()

    route_generation.generate_route_opportunity_plan_result(gateway, fixture.design_bundle, previous_response_id="resp-a")
    ending_generation.generate_ending_anchor_suggestions(gateway, fixture.design_bundle, previous_response_id="resp-b")

    route_payload = json.loads(client.calls[0]["input"])
    ending_payload = json.loads(client.calls[1]["input"])
    assert "author_context" in route_payload
    assert "story_bible" not in route_payload
    assert "state_schema" not in route_payload
    assert "beat_spine" not in route_payload
    assert "author_context" in ending_payload
    assert "story_bible" not in ending_payload


def test_gateway_retries_story_frame_glean_after_invalid_json() -> None:
    client = FakeClient(
        [
            "not json at all",
            story_frame_draft().model_dump(mode="json"),
        ]
    )
    gateway = _gateway(client)
    fixture = author_fixture_bundle()

    repaired = story_generation.glean_story_frame(
        gateway,
        fixture.focused_brief,
        fixture.story_frame,
        previous_response_id="resp-start",
    )

    assert len(client.calls) == 2
    assert repaired.value.title == fixture.story_frame.title
    assert client.calls[0]["previous_response_id"] == "resp-start"
    assert client.calls[1]["previous_response_id"] == "resp-start"


def test_gateway_retries_route_affordance_generation_after_invalid_json() -> None:
    fixture = author_fixture_bundle()
    client = FakeClient(
        [
            "not json at all",
            {
                "route_unlock_rules": [
                    {
                        "rule_id": "b1_unlock",
                        "beat_id": "b1",
                        "conditions": {"required_truths": ["truth_1"]},
                        "unlock_route_id": "b1_reveal_truth_route",
                        "unlock_affordance_tag": "reveal_truth",
                    }
                ],
                "affordance_effect_profiles": [
                    {
                        "affordance_tag": "reveal_truth",
                        "default_story_function": "reveal",
                        "axis_deltas": {"external_pressure": 1},
                        "stance_deltas": {},
                        "can_add_truth": True,
                        "can_add_event": False,
                    }
                ],
            },
        ]
    )
    gateway = _gateway(client)

    pack = route_generation.generate_route_affordance_pack_result(
        gateway,
        fixture.design_bundle,
        previous_response_id="resp-route",
    )

    assert len(client.calls) == 2
    assert pack.value.route_unlock_rules
    assert pack.value.affordance_effect_profiles
    assert client.calls[0]["previous_response_id"] == "resp-route"
    assert client.calls[1]["previous_response_id"] == "resp-route"

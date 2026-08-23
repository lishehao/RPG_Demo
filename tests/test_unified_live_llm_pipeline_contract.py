from __future__ import annotations

import json
from types import SimpleNamespace

from rpg_backend.config import Settings
from rpg_backend.narrative.contracts import StoryBriefAdvisorRequest, StoryGuideCompressedContext, StoryGuideTurnRequest
from rpg_backend.narrative.gateway import NarrativeLLMGateway, get_narrative_gateway
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService, _safe_story_guide_context
from rpg_backend.narrative.story_guide import advance_story_guide_loop, story_butler_voice_policy
from rpg_backend.responses_transport import ResponsesJSONTransport, build_chat_completions_client, usage_to_dict

ROOT_FILES = (
    "frontend2/src/pages/create/create-page.tsx",
    "frontend2/src/api/route-map.ts",
)


class _FakeResponses:
    def __init__(self, output_text: str, usage: dict | None = None) -> None:
        self.output_text = output_text
        self.usage = usage
        self.calls: list[dict] = []

    def create(self, **kwargs):  # noqa: ANN001, ANN201
        self.calls.append(kwargs)
        return SimpleNamespace(id="resp_fake_123", output_text=self.output_text, usage=self.usage)


class _FakeClient:
    def __init__(self, responses: _FakeResponses) -> None:
        self.responses = responses


def _transport(output: dict | str, usage: dict | None = None) -> ResponsesJSONTransport:
    output_text = output if isinstance(output, str) else json.dumps(output)
    return ResponsesJSONTransport(
        client=_FakeClient(_FakeResponses(output_text, usage)),
        model="deepseek-test",
        timeout_seconds=5,
        use_session_cache=True,
        temperature=0.2,
        enable_thinking=False,
        explicit_disable_thinking=True,
        json_object_prompt_only=True,
        provider_failed_code="llm_provider_failed",
        invalid_response_code="llm_invalid_response",
        invalid_json_code="llm_invalid_json",
        error_factory=lambda code, message, status_code: RuntimeError(f"{code}:{status_code}:{message}"),
    )


def test_unified_text_gateway_uses_generic_responses_config_for_narrative_path() -> None:
    settings = Settings(
        responses_base_url="https://api.deepseek.com",
        responses_api_key="redacted-test-key",
        responses_model="deepseek-test",
        responses_play_model="deepseek-test",
    )
    gateway = get_narrative_gateway(settings)

    assert gateway is not None
    assert gateway.model == "deepseek-test"


def test_explicit_responses_key_pools_precede_single_fallback_keys() -> None:
    settings = Settings(
        responses_api_key="generic-current",
        responses_api_keys="generic-stale,generic-current",
        responses_play_api_key="play-current",
        responses_play_api_keys="play-stale,play-current",
        responses_author_api_key="author-current",
        responses_author_api_keys="author-stale,author-current",
    )

    assert settings.responses_api_key_pool() == ("generic-stale", "generic-current")
    assert settings.play_responses_api_key_pool()[:2] == (
        "play-stale",
        "play-current",
    )
    assert settings.author_responses_api_key_pool()[:2] == (
        "author-stale",
        "author-current",
    )


def test_chat_transport_keeps_primary_key_sticky_when_pool_has_stale_keys() -> None:
    client = build_chat_completions_client(
        base_url="https://api.deepseek.com",
        api_key="primary-current",
        api_keys=("primary-current", "stale-old"),
        use_session_cache=False,
        session_cache_header="x-cache",
        session_cache_value="enable",
    )
    completions = client.chat.completions

    assert completions._next_api_key() == "primary-current"  # noqa: SLF001
    assert completions._next_api_key() == "primary-current"  # noqa: SLF001


def test_usage_parser_extracts_input_output_total_and_cache_tokens() -> None:
    usage = usage_to_dict(
        {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "prompt_tokens_details": {"cached_tokens": 5},
        }
    )

    assert usage["input_tokens"] == 11
    assert usage["output_tokens"] == 7
    assert usage["total_tokens"] == 18
    assert usage["cached_input_tokens"] == 5


def test_transport_records_latency_usage_and_repaired_status() -> None:
    transport = _transport(
        '{"reply":"The room is taking shape. Who can push back?",}',
        usage={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
    )

    response = transport.invoke_json(
        system_prompt="Return JSON.",
        user_payload={"message": "Gala goes wrong"},
        operation_name="create.story_butler_turn",
        max_output_tokens=120,
    )

    assert response.payload["reply"].startswith("The room")
    assert transport.call_trace
    trace = transport.call_trace[-1]
    assert trace["operation"] == "create.story_butler_turn"
    assert trace["status"] == "repaired"
    assert trace["repair_count"] == 1
    assert trace["latency_ms"] >= 0
    assert trace["usage"]["input_tokens"] == 12
    assert trace["usage"]["output_tokens"] == 8
    assert trace["usage"]["total_tokens"] == 20


def test_transport_records_missing_usage_as_empty_trace_usage() -> None:
    transport = _transport({"reply": "Who else is in the room?"}, usage=None)

    transport.invoke_json(
        system_prompt="Return JSON.",
        user_payload={"message": "Gala goes wrong"},
        operation_name="create.story_butler_turn",
        max_output_tokens=120,
    )

    assert transport.call_trace[-1]["status"] == "success"
    assert transport.call_trace[-1]["usage"] == {}


def test_story_butler_turn_uses_live_gateway_and_persists_safe_telemetry(tmp_path) -> None:
    transport = _transport(
        {"reply": "The gala has pressure, but I need the person who can push back in the first room."},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48, "cached_input_tokens": 10},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong before a livestream with a publicist and producer.", language="en"),
        owner_user_id="user_live",
    )
    events = service._repo.list_recent_llm_call_events_for_user("user_live")  # noqa: SLF001

    assert response.source == "live"
    assert response.reply.startswith("The gala has pressure")
    assert events
    operations = {event.operation for event in events}
    assert "create.story_butler_context" in operations
    assert "create.story_butler_turn" in operations
    turn_event = next(event for event in events if event.operation == "create.story_butler_turn")
    assert turn_event.status == "success"
    assert turn_event.input_tokens == 30
    assert turn_event.cached_input_tokens == 10
    assert turn_event.output_tokens == 18
    assert turn_event.total_tokens == 48
    serialized = turn_event.model_dump_json()
    assert "redacted-test-key" not in serialized
    assert response.state.context.planner_skill
    assert response.state.context.recent_turns


def test_story_butler_privacy_control_is_not_recorded_as_gateway_fallback(tmp_path) -> None:
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=None,
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="make it public", language="en"),
        owner_user_id="user_privacy",
    )
    events = service._repo.list_recent_llm_call_events_for_user("user_privacy")  # noqa: SLF001

    assert response.source == "policy_control"
    assert response.acceptedText is False
    assert response.settings is not None
    assert response.settings.privacyIntent == "public"
    assert events[0].operation == "create.story_butler_turn"
    assert events[0].source_label == "policy_control"
    assert events[0].status == "success"
    assert events[0].fallback_reason is None


def test_live_context_sanitizer_preserves_deterministic_correction_history() -> None:
    fallback = StoryGuideCompressedContext(
        player_role="Actually make me a reporter instead",
        rejected_or_changed_facts=["superseded player_role: I am a courier carrying the red envelope."],
    )

    context = _safe_story_guide_context(
        {
            "player_role": "Actually make me a reporter instead",
            "rejected_or_changed_facts": [],
        },
        fallback,
        source="live",
    )

    assert context.compression_source == "live"
    assert context.player_role.startswith("Actually make me a reporter")
    assert any("superseded player_role" in fact for fact in context.rejected_or_changed_facts)


def test_story_butler_turn_unwraps_stringified_reply_json(tmp_path) -> None:
    transport = _transport(
        {"reply": '{"reply":"A gala gone wrong already crackles. Who are you in the scene?"}'},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live",
    )

    assert response.source == "live"
    assert response.reply == "A gala gone wrong already crackles. Who are you in the scene?"
    assert '{"reply"' not in response.reply
    assert "}" not in response.reply


def test_story_butler_turn_accepts_natural_text_plaintext_fallback(tmp_path) -> None:
    transport = _transport(
        "A gala gone wrong is a clean spark. Who can lose something public in this room?",
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live",
    )

    assert response.source == "live"
    assert response.reply.startswith("A gala gone wrong is a clean spark")
    assert '{"reply"' not in response.reply


def test_story_butler_turn_recovers_malformed_reply_wrapper(tmp_path) -> None:
    transport = _transport(
        {"reply": '{"reply":"The gala is unstable. Who are you when the trouble starts?",}'},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live",
    )

    assert response.source == "live"
    assert response.reply == "The gala is unstable. Who are you when the trouble starts?"
    assert '{"reply"' not in response.reply
    assert response.ledger is not None


def test_story_butler_fallback_handles_tiny_greeting_with_opening_scene_skill(tmp_path) -> None:
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=None,
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="hi", language="en"),
        owner_user_id="user_fallback",
    )

    assert response.acceptedText is False
    assert response.source == "no_gateway_fallback"
    assert "Story Butler" in response.reply
    policy = story_butler_voice_policy(response, message="hi")
    assert policy["id"] == "opening_scene_prompt"
    assert policy["focus_slot"] == "pressure"
    assert "opening scene spark" in str(policy["job"])


def test_story_butler_sends_voice_skill_policy_to_live_gateway(tmp_path) -> None:
    transport = _transport(
        {"reply": "The gala is already unstable. Who is closest to the trouble when it starts?"},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live",
    )
    request_payload = json.loads(transport.client.responses.calls[-1]["input"])
    voice_skill = request_payload["voice_skill"]

    assert response.source == "live"
    assert response.reply.startswith("The gala is already unstable")
    assert voice_skill["id"] == "role_focus"
    assert voice_skill["focus_slot"] == "player_role"
    assert "gala" in voice_skill["grounding_terms"]
    assert "variation_instruction" in voice_skill


def test_story_butler_repairs_live_reply_that_misses_selected_skill(tmp_path) -> None:
    transport = _transport(
        {"reply": "What contested object, secret, decision, or public pressure must be handled now?"},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="hi", language="en"),
        owner_user_id="user_live",
    )
    request_payload = json.loads(transport.client.responses.calls[-1]["input"])

    assert request_payload["voice_skill"]["id"] == "opening_scene_prompt"
    assert response.source == "live"
    assert "where are we" in response.reply.lower()
    assert "pressure must be handled" not in response.reply.lower()


def test_story_butler_rejects_multi_question_or_repeated_live_rows(tmp_path) -> None:
    repeated = "A gala with the floor about to crack. Who is closest to the trouble when it starts?"
    transport = _transport(
        {"reply": repeated},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    repeated_response = service.create_story_guide_turn(
        StoryGuideTurnRequest(
            message="Gala goes wrong.",
            language="en",
            previous_assistant_reply=repeated,
        ),
        owner_user_id="user_live",
    )

    assert repeated_response.reply != repeated
    assert repeated_response.reply.count("?") <= 1

    transport = _transport(
        {"reply": "A gala sparks quickly. Who are you? Who can push back?"},
        usage={"input_tokens": 30, "output_tokens": 18, "total_tokens": 48},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong.", language="en"),
        owner_user_id="user_live_2",
    )

    assert response.reply.count("?") <= 1
    assert "gala" in response.reply.lower()


def test_story_butler_ready_reply_hands_off_to_automatic_brief_without_a_question(tmp_path) -> None:
    seed = (
        "At a livestream gala, I am the singer's publicist. The singer vanishes ninety seconds before curtain "
        "while the producer, backup dancer, and sponsor fight over a copied badge log. Keep it grounded and social."
    )
    deterministic = advance_story_guide_loop(None, seed, "en")

    assert deterministic.status == "ready_to_brief"
    assert "shaped it below" in deterministic.reply
    assert "?" not in deterministic.reply
    policy = story_butler_voice_policy(deterministic, message=seed)
    assert policy["id"] == "brief_readiness"
    assert "Ask no question" in str(policy["variation_instruction"])

    transport = _transport(
        {"reply": "Want me to shape the Story Brief now, or add one boundary first?"},
        usage={"input_tokens": 42, "output_tokens": 16, "total_tokens": 58},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message=seed, language="en"),
        owner_user_id="user_ready_handoff",
    )

    assert response.status == "ready_to_brief"
    assert response.source == "live"
    assert "shaped it below" in response.reply
    assert "?" not in response.reply


def test_story_butler_accepts_a_long_correction_after_ready_without_overflow() -> None:
    ready = advance_story_guide_loop(
        None,
        (
            "At a livestream gala, I am the backup dancer. The singer vanishes ninety seconds before curtain "
            "while the producer, publicist, and sponsor fight over a copied badge log. Keep it grounded and social."
        ),
        "en",
    )

    correction = advance_story_guide_loop(
        ready.state,
        (
            "Actually, change that: I am the singer's publicist, not the backup dancer. A copied security-badge "
            "log can expose who moved the singer. Keep it grounded, tense, and investigative with no supernatural "
            "elements or arbitrary fantasy details."
        ),
        "en",
    )

    assert correction.status == "ready_to_brief"
    assert correction.state.context.player_role == "singer's publicist"
    assert len(correction.state.context.tone) <= 120
    assert any("superseded player_role" in fact for fact in correction.state.context.rejected_or_changed_facts)


def test_story_guide_handles_me_and_who_as_contextual_short_inputs() -> None:
    first = advance_story_guide_loop(None, "Gala goes wrong.", "en")
    role_answer = advance_story_guide_loop(first.state, "Me", "en")
    who_question = advance_story_guide_loop(first.state, "who", "en")

    assert role_answer.acceptedText is True
    assert role_answer.state.slots["player_role"].filled is True
    assert role_answer.state.slots["player_role"].evidence == "player as themselves"
    assert role_answer.reply.startswith("Noted: you are the player")
    assert "Who is the player" not in role_answer.reply

    assert who_question.acceptedText is False
    assert "If you mean cast" in who_question.reply
    policy = story_butler_voice_policy(who_question, message="who")
    assert policy["id"] == "cast_focus"
    assert "two people" in str(policy["example_moves"])


def test_story_guide_context_tracks_superseded_facts_and_delegated_choices() -> None:
    first = advance_story_guide_loop(None, "A crowded street before a parade turns tense.", "en")
    role = advance_story_guide_loop(first.state, "I am the courier carrying the red envelope.", "en")
    correction = advance_story_guide_loop(role.state, "Actually I am the reporter chasing the missing envelope.", "en")
    delegated = advance_story_guide_loop(first.state, "you can decide for me", "en")

    assert first.state.context.scene_summary
    assert first.state.context.planner_skill == "role_focus"
    assert role.state.context.player_role == "courier"
    assert correction.state.context.player_role == "reporter"
    assert any("superseded player_role" in fact for fact in correction.state.context.rejected_or_changed_facts)
    assert delegated.acceptedText is True
    assert delegated.state.slots["player_role"].filled is True
    assert "Story Butler chooses" in delegated.state.context.player_role
    assert "Who is the player" not in delegated.reply


def test_player_role_correction_removes_role_only_residue_from_active_cast() -> None:
    initial = advance_story_guide_loop(
        None,
        (
            "At an awards gala, a publicist, a singer, and a sponsor discover the reveal is rigged. "
            "The player is a backup dancer who must protect the singer before air."
        ),
        "en",
    )
    corrected = advance_story_guide_loop(
        initial.state,
        "Correction: I am the publicist, not the backup dancer.",
        "en",
    )

    assert corrected.state.context.player_role == "publicist"
    assert "backup dancer" not in corrected.state.context.cast_or_factions
    assert "publicist" not in corrected.state.context.cast_or_factions
    assert "backup dancer" not in corrected.state.context.scene_summary.lower()
    assert "backup dancer" not in corrected.state.context.pressure.lower()
    assert all("backup dancer" not in item.lower() for item in corrected.state.context.constraints)
    assert "singer" in corrected.state.context.cast_or_factions
    assert any(
        "superseded player_role: backup dancer" in fact
        for fact in corrected.state.context.rejected_or_changed_facts
    )

    zh_initial = advance_story_guide_loop(
        None,
        "直播颁奖礼被人操纵。玩家是伴舞，必须在主持人上台前保护歌手。",
        "zh",
    )
    zh_state = zh_initial.state.model_copy(
        update={
            "context": zh_initial.state.context.model_copy(update={"player_role": "伴舞"})
        }
    )
    zh_corrected = advance_story_guide_loop(
        zh_state,
        "修正：我是公关，不是伴舞。",
        "zh",
    )
    assert zh_corrected.state.context.player_role == "公关"
    assert "玩家是伴舞" not in zh_corrected.state.context.scene_summary
    assert "玩家是公关" in zh_corrected.state.context.scene_summary


def test_story_guide_compresses_rich_seed_into_specific_playable_facts() -> None:
    response = advance_story_guide_loop(
        None,
        (
            "At a livestream gala, I'm the missing singer's publicist. "
            "The producer, sponsor representative, and backup dancer are in the room. "
            "A copied badge log can expose who moved her, but if the ninety-second countdown "
            "reaches zero, my team takes the blame."
        ),
        "en",
    )

    context = response.state.context
    assert response.canShapeBrief is True
    assert context.player_role == "singer's publicist"
    assert context.cast_or_factions == [
        "producer",
        "sponsor representative",
        "backup dancer",
    ]
    assert "badge log" in context.pressure.lower()
    assert "countdown" in context.pressure.lower()
    assert context.confirmed_facts == [context.scene_summary, context.pressure]
    assert all(not fact.startswith(("scene:", "player:", "cast:", "pressure:")) for fact in context.confirmed_facts)


def test_story_guide_routes_meta_and_help_without_story_fact_pollution() -> None:
    initial = advance_story_guide_loop(None, "hi", "en")
    meta = advance_story_guide_loop(initial.state, "who are you", "en")
    help_turn = advance_story_guide_loop(meta.state, "what do I type here", "en")
    story = advance_story_guide_loop(help_turn.state, "A crowded street before a parade turns tense.", "en")

    assert initial.acceptedText is False
    assert initial.state.acceptedTurns == []
    assert initial.state.context.last_user_intent == "greeting_smalltalk"
    assert initial.state.context.latest_input_updates_story_facts is False
    assert "hi" not in initial.state.context.scene_summary.lower()

    assert meta.acceptedText is False
    assert "Story Butler" in meta.reply
    assert meta.state.acceptedTurns == []
    assert meta.state.context.last_user_intent == "meta_assistant"
    assert meta.state.context.latest_input_updates_story_facts is False
    assert "who are you" not in meta.state.context.scene_summary.lower()
    assert any("meta_assistant" in item for item in meta.state.context.non_story_user_intents)

    assert help_turn.acceptedText is False
    assert "one question at a time" in help_turn.reply
    assert help_turn.state.context.last_user_intent == "interaction_help"
    assert help_turn.state.context.latest_input_updates_story_facts is False

    assert story.acceptedText is True
    assert story.state.acceptedTurns == ["A crowded street before a parade turns tense."]
    assert "crowded street" in story.state.context.scene_summary.lower()
    assert story.state.context.last_user_intent == "story_seed"
    assert story.state.context.latest_input_updates_story_facts is True


def test_story_guide_noise_and_direct_answer_intents_do_not_loop() -> None:
    noise = advance_story_guide_loop(None, "???", "en")
    seed = advance_story_guide_loop(None, "Gala goes wrong before the livestream.", "en")
    role = advance_story_guide_loop(seed.state, "publicist", "en")
    delegated = advance_story_guide_loop(seed.state, "you can decide for me", "en")

    assert noise.acceptedText is False
    assert "story material" in noise.reply
    assert noise.state.acceptedTurns == []
    assert noise.state.context.last_user_intent == "unclear_noise"
    assert noise.canShapeBrief is False

    assert role.acceptedText is True
    assert role.state.slots["player_role"].filled is True
    assert role.state.slots["player_role"].evidence == "publicist"
    assert role.state.context.last_question_answered
    assert "Who is the player" not in role.reply

    assert delegated.acceptedText is True
    assert delegated.state.slots["player_role"].filled is True
    assert "Story Butler chooses" in delegated.state.slots["player_role"].evidence
    assert "Who is the player" not in delegated.reply


def test_story_guide_context_is_typed_in_frontend_contracts() -> None:
    contracts = open("frontend2/src/api/contracts.ts").read()
    loop_source = open("frontend2/src/shared/lib/story-guide-loop.ts").read()

    for field in (
        "scene_summary",
        "player_role",
        "cast_or_factions",
        "rejected_or_changed_facts",
        "non_story_user_intents",
        "last_user_intent",
        "last_question_answered",
        "latest_input_updates_story_facts",
        "readiness_score",
        "recent_turns",
    ):
        assert field in contracts
        assert field in loop_source


def test_story_butler_turn_falls_back_without_gateway_and_records_no_gateway_event(tmp_path) -> None:
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=None,
    )

    response = service.create_story_guide_turn(
        StoryGuideTurnRequest(message="Gala goes wrong before a livestream with a publicist and producer.", language="en"),
        owner_user_id="user_fallback",
    )
    events = service._repo.list_recent_llm_call_events_for_user("user_fallback")  # noqa: SLF001

    assert response.source == "no_gateway_fallback"
    assert events[0].operation == "create.story_butler_turn"
    assert events[0].source_label == "no_gateway_fallback"
    assert events[0].status == "fallback_used"


def test_story_brief_uses_live_hybrid_copy_without_changing_generation_gate(tmp_path) -> None:
    transport = _transport(
        {
            "premise_summary": "A publicist must decide what to reveal before the awards livestream collapses.",
            "genre_tone": "High-drama backstage pressure with public fallout.",
            "story_kernel": "Protect the witness, manage the producer, and keep the room playable under deadline.",
            "adaptation_note": "Live editor tightened copy while preserving the safety-checked plan.",
            "next_step": "Build the first scene from this Brief.",
        },
        usage={"input_tokens": 80, "output_tokens": 42, "total_tokens": 122},
    )
    service = NarrativeService(
        repository=NarrativeRepository(str(tmp_path / "runtime.sqlite3")),
        gateway=NarrativeLLMGateway(transport=transport, model="deepseek-test"),
    )

    response = service.create_story_brief(
        StoryBriefAdvisorRequest(
            seed=(
                "Ten minutes before an awards livestream, an anxious publicist, a producer, "
                "a backup dancer, and a sponsor representative discover that a famous singer has disappeared."
            ),
            language="en",
            desired_tension_profile="high_drama",
        ),
        owner_user_id="user_brief",
    )
    events = service._repo.list_recent_llm_call_events_for_user("user_brief")  # noqa: SLF001

    assert response.source == "live_hybrid_v1"
    assert response.runtime_source == "live"
    assert response.brief.source == "live_hybrid_v1"
    assert response.can_generate is True
    assert "awards livestream" in response.brief.premise_summary
    assert events[0].operation == "narrative.story_brief"
    assert events[0].total_tokens == 122


def test_create_page_calls_backend_story_guide_turn_and_shows_thinking_row() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    create_page = (root / "frontend2/src/pages/create/create-page.tsx").read_text()
    route_map = (root / "frontend2/src/api/route-map.ts").read_text()

    assert "createNarrativeStoryGuideTurn" in create_page
    assert "guide_context:" in create_page
    assert "scene_summary: guideLoopState.context.scene_summary" in create_page
    assert "guideContext={guideLoopState.context}" in create_page
    assert create_page.count('data-guide-node={activeBriefResponse.can_generate ? "brief_ready" : "brief_not_fit"}') == 1
    assert 'data-guide-node="story_butler_turn"' in create_page
    assert 'data-guide-process="story_guide.live"' in create_page
    assert 'data-guide-stage="slot_focus"' in create_page
    guide_busy_start = create_page.index('{guideBusy ? (')
    guide_busy_end = create_page.index('{activeBriefResponse ? (', guide_busy_start)
    guide_busy_segment = create_page[guide_busy_start:guide_busy_end]
    assert "Reading seed" not in guide_busy_segment
    assert "Finding pressure" not in guide_busy_segment
    assert "Checking boundaries" not in guide_busy_segment
    assert "Choosing next question" not in guide_busy_segment
    assert "guideScanStages" not in guide_busy_segment
    assert "guideScanRail" not in guide_busy_segment
    assert "guideBusy" in create_page
    assert "normalizeGuideReplyText(response.reply)" in create_page
    assert '"reply"\\s*:' in create_page
    assert "/narrative/story-guide/turns" in route_map

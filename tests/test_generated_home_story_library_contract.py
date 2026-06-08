from __future__ import annotations

from typing import Any

import rpg_backend.narrative.service as service_module
from rpg_backend.narrative.contracts import (
    CastMember,
    PlayerRole,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.home_story_library import (
    DEFAULT_HOME_STORY_OWNER_ID,
    DefaultHomeStorySpec,
    ensure_default_home_story_library,
)
from rpg_backend.narrative.gateway import NarrativeLLMGateway
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService
from rpg_backend.responses_transport import ResponsesJSONResponse


class _HomeLibraryGateway:
    model = "deepseek-test"

    def __init__(self) -> None:
        self._trace: list[dict[str, Any]] = []

    def trace_length(self) -> int:
        return len(self._trace)

    def trace_since(self, start_index: int) -> list[dict[str, Any]]:
        return list(self._trace[max(0, int(start_index)) :])

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        operation_name: str,
        max_output_tokens: int | None = None,
        plaintext_fallback_key: str | None = None,
    ) -> ResponsesJSONResponse:
        del system_prompt, user_payload, max_output_tokens, plaintext_fallback_key
        payload = (
            {
                "display_title": "Gala Crash",
                "display_intro": "A publicist has one countdown to save the show and the witness.",
                "premise_summary": "A livestream gala is collapsing around a missing performer.",
                "genre_tone": "high drama",
                "story_kernel": "A witness, a publicist, and a producer fight over what reaches the stage.",
                "next_step": "Ready.",
            }
            if operation_name == "narrative.story_brief"
            else {"reply": "The gala has pressure. Who is closest to the trouble when it starts?"}
        )
        if operation_name == "narrative.opening":
            payload = {"opening": "ok"}
        self._trace.append(
            {
                "operation": operation_name,
                "status": "success",
                "source_label": "live",
                "latency_ms": 7,
                "usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 2,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
                "attempt_index": 1,
                "retry_count": 0,
                "repair_count": 0,
                "response_id": f"resp_{operation_name.replace('.', '_')}",
            }
        )
        return ResponsesJSONResponse(
            payload=payload,
            response_id=f"resp_{operation_name.replace('.', '_')}",
            usage={
                "input_tokens": 10,
                "cached_input_tokens": 2,
                "output_tokens": 5,
                "total_tokens": 15,
            },
            input_characters=40,
        )


def test_default_home_story_library_uses_pipeline_and_dedupes(tmp_path, monkeypatch) -> None:
    spec = DefaultHomeStorySpec(
        library_key="gala_test",
        seed=(
            "Ten minutes before a gala livestream, a publicist, producer, "
            "backup dancer, and sponsor discover the singer vanished."
        ),
    )
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    gateway = _HomeLibraryGateway()
    service = NarrativeService(
        repository=repo,
        gateway=gateway,  # type: ignore[arg-type]
    )

    def fake_opening_with_cap(**kwargs: object):
        resolved_gateway = kwargs["gateway"]
        assert isinstance(resolved_gateway, NarrativeLLMGateway) or hasattr(resolved_gateway, "invoke_json")
        resolved_gateway.invoke_json(  # type: ignore[union-attr]
            system_prompt="Return JSON.",
            user_payload={"seed": kwargs.get("seed")},
            operation_name="narrative.opening",
            max_output_tokens=120,
        )
        return type(
            "Opening",
            (),
            {
                "title": "Gala Crash",
                "advisor_persona": "A precise Story Butler watching the countdown.",
                "cast": [
                    CastMember(
                        character_id="publicist",
                        display_name="publicist",
                        role="player-facing crisis lead",
                        relation_to_protagonist="Must decide what reaches the livestream.",
                    ),
                    CastMember(
                        character_id="producer",
                        display_name="producer",
                        role="pressure holder",
                        relation_to_protagonist="Controls the stage deadline.",
                    ),
                    CastMember(
                        character_id="backup_dancer",
                        display_name="backup dancer",
                        role="witness",
                        relation_to_protagonist="Saw the singer leave.",
                    ),
                ],
                "opening_message": StoryMessage(
                    ord=0,
                    role="narrator",
                    content=(
                        "The gala clock drops under ten minutes while the publicist, "
                        "producer, and backup dancer argue over the missing singer."
                    ),
                    options=[StoryOption(label="Ask the dancer what they saw", hint="Probe", handle="ask")],
                ),
                "player_goals": [],
                "failure_conditions": [],
                "player_role_options": [
                    PlayerRole(
                        role_id="publicist",
                        label="Publicist",
                        public_persona="The publicist trying to keep the gala from collapsing.",
                        hidden_objective="Protect the witness without losing the show.",
                    )
                ],
            },
        )()

    monkeypatch.setattr(service_module, "_generate_story_brief_live_opening_with_cap", fake_opening_with_cap)

    first = ensure_default_home_story_library(
        service,
        owner_user_id=DEFAULT_HOME_STORY_OWNER_ID,
        specs=(spec,),
    )
    second = ensure_default_home_story_library(
        service,
        owner_user_id=DEFAULT_HOME_STORY_OWNER_ID,
        specs=(spec,),
    )
    public_templates = service.list_public_templates(viewer_user_id="guest").items
    events = repo.list_recent_llm_call_events_for_user(DEFAULT_HOME_STORY_OWNER_ID, limit=20)
    operations = [event.operation for event in reversed(events)]

    assert first[0].created is True
    assert first[0].template.visibility == "public"
    assert first[0].template.title == "Gala Crash"
    assert first[0].template.summary_i18n is not None
    assert first[0].template.summary_i18n.en
    assert second[0].created is False
    assert second[0].template.template_id == first[0].template.template_id
    assert len(public_templates) == 1
    assert "create.story_butler_turn" in operations
    assert "narrative.story_brief" in operations
    assert "narrative.opening" in operations
    assert all(event.status == "success" for event in events)
    assert all(event.source_label == "live" for event in events)
    assert all(event.input_tokens == 10 for event in events)
    assert all(event.cached_input_tokens == 2 for event in events)
    assert all(event.output_tokens == 5 for event in events)
    assert all(event.total_tokens == 15 for event in events)

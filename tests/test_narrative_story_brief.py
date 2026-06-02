from __future__ import annotations

from rpg_backend.narrative.brief import build_story_brief, infer_tension_profile
from rpg_backend.narrative.contracts import (
    CastMember,
    CreateTemplateRequest,
    PlayerRole,
    StoryBriefAdvisorRequest,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService


class _OpeningResponder:
    def __init__(self) -> None:
        self.story_brief_payload = None


def test_story_brief_flags_explicit_small_cast_as_not_fit() -> None:
    response = build_story_brief(
        seed="A quiet laundromat ring goes missing: only two people, no villains, low conflict.",
        language="en",
    )

    assert response.can_generate is False
    assert response.brief.runtime_fit_status == "not_fit"
    assert any("3+ active parties" in item for item in response.brief.warnings)
    assert response.brief.revision_suggestions


def test_story_brief_allows_multi_party_no_villain_comedy() -> None:
    response = build_story_brief(
        seed=(
            "A comedy talent show with no villains: the host, the mayor, "
            "the mascot, and the sponsor all need the same prop before curtain."
        ),
        language="en",
    )

    assert response.can_generate is True
    assert response.brief.runtime_fit_status != "not_fit"
    assert response.brief.tension_profile == "comedy"


def test_story_brief_caps_ten_entities_and_explains_compression() -> None:
    seed = (
        "Mars colony talent show departments: Engineering, Hydroponics, Security, "
        "Medicine, Logistics, Culture, Terraforming, Council, AI Core, Children Choir, "
        "Visiting Sponsors, Earth Media before the final broadcast."
    )

    response = build_story_brief(seed=seed, language="en")

    assert response.brief.tension_profile in {"comedy", "fantasy_sci_fi"}
    assert len(response.brief.cast_plan.primary_active_entities) <= 5
    assert len(response.brief.cast_plan.secondary_background_entities) <= 5
    assert response.brief.cast_plan.omitted_entities
    assert response.brief.compressed_constraints


def test_story_brief_classifies_comedy_kernel() -> None:
    seed = "A comedy talent show goes wrong when the mascot, the judge, and the mayor all claim the same prop."

    response = build_story_brief(seed=seed, language="en")

    assert infer_tension_profile(seed) == "comedy"
    assert response.brief.tension_profile == "comedy"
    assert "misunderstanding" in response.brief.story_kernel
    assert response.brief.intervention_card_label == "Callback card"
    assert any("embarrassment" in item for item in response.brief.softened_constraints)


def test_create_story_brief_service_response_is_versioned(tmp_path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    response = service.create_story_brief(
        StoryBriefAdvisorRequest(
            seed="A cozy mystery at a bake sale: teacher, parent organizer, principal, and cupcake thief."
        ),
        owner_user_id="usr_test",
    )

    assert response.brief.schema_version == "story_brief.v1"
    assert response.brief.source == "deterministic_v1"
    assert response.can_generate is True


def test_create_template_passes_confirmed_story_brief_to_opening(
    tmp_path,
    monkeypatch,
) -> None:
    import rpg_backend.narrative.service as service_module

    captured = {}
    brief = build_story_brief(
        seed="A comedy talent show: host, mayor, mascot, judge, and sponsor before curtain.",
        language="en",
    ).brief

    def fake_generate_opening(**kwargs):
        captured["story_brief"] = kwargs.get("story_brief")
        return type(
            "Opening",
            (),
            {
                "title": "Talent Trouble",
                "advisor_persona": "Mina, a backstage friend texting from the lobby.",
                "cast": [
                    CastMember(
                        character_id="host",
                        display_name="Host",
                        role="Host",
                        relation_to_protagonist="Runs the show",
                    ),
                    CastMember(
                        character_id="mayor",
                        display_name="Mayor",
                        role="Mayor",
                        relation_to_protagonist="Public pressure",
                    ),
                    CastMember(
                        character_id="mascot",
                        display_name="Mascot",
                        role="Mascot",
                        relation_to_protagonist="Holds the prop",
                    ),
                ],
                "opening_message": StoryMessage(
                    ord=0,
                    role="narrator",
                    content="The curtain cord sticks while the mascot waves the wrong prop.",
                    options=[StoryOption(label="Ask who swapped it", hint="Probe", handle="ask")],
                ),
                "player_goals": [],
                "failure_conditions": [],
                "player_role_options": [
                    PlayerRole(
                        role_id="host",
                        label="Host",
                        public_persona="The host trying to keep the show moving.",
                        hidden_objective="Keep the sponsor from canceling the event.",
                    )
                ],
            },
        )()

    monkeypatch.setattr(service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    service.create_template(
        CreateTemplateRequest(seed=brief.original_seed, story_brief=brief),
        owner_user_id="usr_test",
    )

    assert captured["story_brief"] == brief

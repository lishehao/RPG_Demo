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


def _cast_names(response) -> list[str]:
    plan = response.brief.cast_plan
    return [
        entity.display_name
        for entity in [*plan.primary_active_entities, *plan.secondary_background_entities, *plan.omitted_entities]
    ]


def _constraint_labels(response) -> list[str]:
    brief = response.brief
    return [
        *brief.preserved_constraints,
        *brief.compressed_constraints,
        *brief.dropped_constraints,
        *brief.softened_constraints,
    ]


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


def test_story_brief_mars_talent_show_preserves_departments_and_event_constraints() -> None:
    seed = (
        "On Mars colony, a comedy talent show involves Engineering, Hydroponics, "
        "Security, Medicine, Culture, Terraforming, Council, AI Core, "
        "Theatre Club, and Earth Media before the final broadcast."
    )

    response = build_story_brief(seed=seed, language="en")
    names = _cast_names(response)
    labels = _constraint_labels(response)

    assert response.brief.tension_profile == "comedy"
    assert "Theatre Club" in names
    assert "On Mars colony" not in names
    assert response.brief.cast_plan.input_entity_count == 10
    assert response.brief.cast_plan.omitted_entities == []
    assert "talent show" in labels
    assert "final broadcast" in labels
    assert all("ring" not in label.lower() for label in labels)


def test_story_brief_filters_tone_mechanisms_from_bake_sale_cast() -> None:
    seed = (
        "At a cozy preschool bake sale, the teacher, parent organizer, principal, "
        "and cupcake baker investigate a missing cupcake with no blackmail, "
        "misunderstandings, embarrassed parents, and a callback joke."
    )

    response = build_story_brief(seed=seed, language="en")
    names = {name.lower() for name in _cast_names(response)}
    labels = {label.lower() for label in _constraint_labels(response)}

    assert response.brief.tension_profile == "cozy_mystery"
    assert {"teacher", "parent organizer", "principal", "cupcake baker"}.issubset(names)
    assert "at" not in names
    assert "no blackmail" not in names
    assert "misunderstandings" not in names
    assert "embarrassed parents" not in names
    assert "callback joke" not in names
    assert "no blackmail" in labels
    assert any("avoid blackmail" in label for label in labels)


def test_story_brief_preserves_named_high_drama_roles() -> None:
    response = build_story_brief(
        seed=(
            "Board vote at midnight: CFO, founder, union observer, investor chair, "
            "and legal counsel fight over a leaked contract."
        ),
        language="en",
    )

    names = set(_cast_names(response))

    assert {"CFO", "founder", "union observer", "investor chair", "legal counsel"}.issubset(names)
    assert "player" not in {name.lower() for name in names}
    assert "rival" not in {name.lower() for name in names}


def test_story_brief_fantasy_eclipse_keeps_factions_and_pressure() -> None:
    response = build_story_brief(
        seed=(
            "In a fantasy library during an eclipse, dragons, ink sprites, an apprentice "
            "spellbook, the head librarian, and a banished dragon clan argue over a cursed index."
        ),
        language="en",
    )

    names = _cast_names(response)
    labels = _constraint_labels(response)

    assert response.brief.tension_profile == "fantasy_sci_fi"
    assert "dragons" in names
    assert "ink sprites" in names
    assert "apprentice spellbook" in names
    assert "banished dragon clan" in names
    assert "eclipse" in labels
    assert all("ring" not in label.lower() for label in labels)
    assert all("time pressure" not in warning.lower() for warning in response.brief.warnings)


def test_story_brief_warns_when_comedy_premise_has_life_or_death_stakes() -> None:
    response = build_story_brief(
        seed=(
            "A comedy on Mars where Engineering, Hydroponics, and Security perform "
            "in a talent show after someone steals the colony oxygen supply."
        ),
        language="en",
        desired_tension_profile="comedy",
    )

    assert response.can_generate is True
    assert response.brief.runtime_fit_status == "needs_revision"
    assert "comedy on Mars" not in _cast_names(response)
    assert {"Engineering", "Hydroponics", "Security"}.issubset(set(_cast_names(response)))
    assert any("life-or-death" in warning.lower() for warning in response.brief.warnings)
    assert any("lower the stakes" in suggestion.lower() for suggestion in response.brief.revision_suggestions)


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

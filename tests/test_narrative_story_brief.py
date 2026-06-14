from __future__ import annotations

from rpg_backend.narrative.brief import (
    build_story_brief,
    check_story_brief_opening_consistency,
    infer_tension_profile,
)
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


class _Opening:
    def __init__(self, *, content: str, cast_names: list[str] | None = None, title: str = "Opening") -> None:
        self.title = title
        self.advisor_persona = "A careful friend outside the room."
        self.cast = [
            CastMember(
                character_id=name.lower().replace(" ", "_"),
                display_name=name[:40],
                role="planned party",
                relation_to_protagonist="Part of the opening pressure.",
            )
            for name in (cast_names or [])
        ]
        self.opening_message = StoryMessage(
            ord=0,
            role="narrator",
            content=content,
            options=[StoryOption(label="Ask a careful question", hint="Probe", handle="ask")],
        )


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


def _constraint_item_labels(response) -> list[str]:
    return [item.label for item in response.brief.constraints]


def _violation_codes(check) -> set[str]:
    return {violation.code for violation in check.violations}


def test_story_brief_flags_explicit_small_cast_as_not_fit() -> None:
    response = build_story_brief(
        seed="A quiet laundromat ring goes missing: only two people, no villains, low conflict.",
        language="en",
    )

    assert response.can_generate is False
    assert response.brief.runtime_fit_status == "not_fit"
    assert any("3+ active parties" in item for item in response.brief.warnings)
    assert response.brief.revision_suggestions


def test_story_brief_preserves_wedding_ring_as_object_phrase() -> None:
    response = build_story_brief(
        seed=(
            "A quiet two-person laundromat story with no villains: one customer "
            "and one attendant try to find a lost wedding ring without conflict, "
            "betrayal, or public pressure."
        ),
        language="en",
    )

    labels = {label.lower() for label in _constraint_labels(response)}
    item_labels = {label.lower() for label in _constraint_item_labels(response)}

    assert "wedding ring" in labels
    assert "wedding" not in labels
    assert "ring" not in labels
    assert "wedding ring" in item_labels
    assert "ring" not in item_labels


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


def test_story_brief_strips_list_introducer_and_dedupes_mars_entities() -> None:
    seed = (
        "On Mars colony, a comedy talent show with ten groups - Hydroponics, "
        "Security, Engineering, Medicine, Culture, Terraforming, Council, AI Core, "
        "Theatre Club, and Earth Media before the final broadcast. "
        "Each group should represent Theatre Club and Earth Media concerns."
    )

    response = build_story_brief(seed=seed, language="en")
    names = _cast_names(response)
    lowered_names = [name.lower() for name in names]

    assert "Hydroponics" in names
    assert "ten groups - Hydroponics" not in names
    assert "represent Theatre Club" not in names
    assert "Earth Media concerns" not in names
    assert "Each" not in names
    assert "Theatre Club" in names
    assert "Earth Media" in names
    assert len(lowered_names) == len(set(lowered_names))
    active_or_background = {
        entity.display_name.lower()
        for entity in [
            *response.brief.cast_plan.primary_active_entities,
            *response.brief.cast_plan.secondary_background_entities,
        ]
    }
    omitted = {entity.display_name.lower() for entity in response.brief.cast_plan.omitted_entities}
    assert active_or_background.isdisjoint(omitted)


def test_story_brief_protects_emphasized_entities_under_ten_entity_cap() -> None:
    seed = (
        "On Mars colony, a comedy talent show with ten groups - Hydroponics, Oxygen, "
        "Security, Medical, Education, Waste Recycling, Transit, Finance, Communications, "
        "Theatre Club, and Earth Media before the final broadcast. "
        "Each group should represent Theatre Club and Earth Media concerns."
    )

    response = build_story_brief(seed=seed, language="en")
    plan = response.brief.cast_plan
    active_or_background = {
        entity.display_name
        for entity in [*plan.primary_active_entities, *plan.secondary_background_entities]
    }
    omitted = {entity.display_name for entity in plan.omitted_entities}

    assert "Theatre Club" in active_or_background
    assert "Earth Media" in active_or_background
    assert "Earth Media" not in omitted
    assert any(
        entity.display_name == "Earth Media" and "explicitly" in entity.rationale.lower()
        for entity in [*plan.primary_active_entities, *plan.secondary_background_entities]
    )
    assert "ten groups -" not in response.brief.premise_summary.lower()
    assert "Hydroponics" in response.brief.premise_summary


def test_story_brief_revision_guidance_does_not_become_cast() -> None:
    base = (
        "On Mars colony, a comedy talent show involves Engineering, Hydroponics, "
        "Security, Medicine, Culture, Terraforming, Council, AI Core, Theatre Club, "
        "and Earth Media before the final broadcast."
    )
    response = build_story_brief(seed=base, language="en")

    for action in response.brief.revision_actions:
        revised = build_story_brief(seed=f"{base}\n\n{action.seed_append}", language="en")
        names = {name.lower() for name in _cast_names(revised)}
        first_word = action.label.split()[0].lower()

        assert first_word not in names
        assert "planner" not in names
        assert "move" not in names
        assert "add" not in names
        assert "lower" not in names
        assert "extra factions" not in names


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


def test_story_brief_small_cozy_prompt_does_not_use_cap_rationale() -> None:
    response = build_story_brief(
        seed=(
            "At a neighborhood bake sale, three parents and a shy teen volunteer "
            "try to find who swapped the cupcake labels. Keep it cozy and funny, "
            "no blackmail, no betrayal, no corporate stakes."
        ),
        language="en",
    )

    plan = response.brief.cast_plan
    planned_names = {
        entity.display_name.lower()
        for entity in [*plan.primary_active_entities, *plan.secondary_background_entities]
    }
    omitted_rationales = [entity.rationale.lower() for entity in plan.omitted_entities]

    assert plan.input_entity_count < 10
    assert "three parents" in planned_names
    assert "shy teen volunteer" in planned_names
    assert all("10-entity planning cap" not in rationale for rationale in omitted_rationales)


def test_cozy_opening_consistency_rejects_accuse_fight_options() -> None:
    brief = build_story_brief(
        seed=(
            "At a neighborhood bake sale, the PTA treasurer, a teen volunteer, "
            "a tired parent, and the cupcake judge argue over a missing recipe card "
            "before judging starts. Keep it cozy and funny: no blackmail, no betrayal, "
            "only misunderstandings, embarrassment, and a callback joke."
        ),
        language="en",
    ).brief
    opening = _Opening(
        title="Recipe Card Mix-Up",
        cast_names=["PTA treasurer", "teen volunteer", "tired parent", "cupcake judge"],
        content=(
            "At the neighborhood bake sale, the PTA treasurer, teen volunteer, tired parent, "
            "and cupcake judge gather around the missing recipe card before judging starts."
        ),
    )
    opening.opening_message.options = [
        StoryOption(
            label="Accuse someone of hiding it to stall the judging",
            hint="Could start a fight",
            handle="accuse",
        )
    ]

    check = check_story_brief_opening_consistency(brief=brief, opening=opening, language="en")

    assert check.status == "fail"
    assert check.should_retry is True
    assert "profile_tone_taboo" in _violation_codes(check)


def test_fantasy_opening_consistency_rejects_scapegoat_role_frame() -> None:
    brief = build_story_brief(
        seed=(
            "In a fantasy library during an eclipse, dragons, ink sprites, an apprentice "
            "spellbook, the head librarian, and a banished dragon clan argue over a cursed index."
        ),
        language="en",
    ).brief
    opening = _Opening(
        title="The Scapegoat",
        cast_names=["dragons", "ink sprites", "apprentice spellbook", "head librarian", "banished dragon clan"],
        content=(
            "In the fantasy library during the eclipse, dragons, ink sprites, an apprentice "
            "spellbook, the head librarian, and a banished dragon clan circle the cursed index."
        ),
    )
    opening.player_role_options = [
        PlayerRole(
            role_id="role-01",
            label="The Scapegoat",
            public_persona="You are blamed whenever the cursed index moves.",
            hidden_objective="Make sure someone else takes the fall before the eclipse ends.",
            leverages_over_npcs=[],
            starting_assets=["A bent page marker"],
        )
    ]

    check = check_story_brief_opening_consistency(brief=brief, opening=opening, language="en")

    assert check.status == "fail"
    assert check.should_retry is True
    assert "profile_tone_taboo" in _violation_codes(check)


def test_story_brief_filters_tone_phrase_from_fantasy_cast() -> None:
    response = build_story_brief(
        seed=(
            "In a floating dragon library, a shy apprentice spellbook, ink sprites, sky pirates, "
            "the Archivist Guild, moon-oracle librarians, and a banished dragon clan argue over "
            "a missing star map before an eclipse in three hours. Keep it fantastical, tense but "
            "playful, and make the eclipse the time pressure."
        ),
        language="en",
    )

    names = {name.lower() for name in _cast_names(response)}
    tone = {item.label.lower() for item in response.brief.tone_constraints}

    assert "tense but playful" not in names
    assert "it fantastical" not in names
    assert "shy apprentice spellbook" in names
    assert "ink sprites" in names
    assert "sky pirates" in names
    assert "banished dragon clan" in names
    assert "tense but playful" in tone


def test_story_brief_separates_negated_constraints_minutes_and_settings_from_cast() -> None:
    response = build_story_brief(
        seed=(
            "Minutes before the school showcase at Mars colony, teacher, principal, "
            "student council, and stage crew handle a missing prop with no violence and no betrayal."
        ),
        language="en",
    )

    names = {name.lower() for name in _cast_names(response)}
    constraints = {item.label.lower() for item in response.brief.constraints}
    tone = {item.label.lower() for item in response.brief.tone_constraints}
    anchors = {item.label.lower() for item in response.brief.time_event_anchors}
    settings = {item.label.lower() for item in response.brief.world_setting_pressure}

    assert {"teacher", "principal", "student council", "stage crew"}.issubset(names)
    assert "minutes" not in names
    assert "no violence" not in names
    assert "no betrayal" not in names
    assert "mars" not in names
    assert "no violence" in constraints
    assert "no betrayal" in constraints
    assert "avoid violence" in tone
    assert "avoid betrayal" in tone
    assert "minutes-before deadline" in anchors
    assert "mars colony" in settings
    assert "mars setting" not in settings
    assert "colony setting" not in settings


def test_story_brief_filters_small_cast_exclusions_from_focus() -> None:
    response = build_story_brief(
        seed=(
            "A quiet two-person laundromat story with no villains: one customer and one attendant "
            "try to find a lost wedding ring without conflict, betrayal, or public pressure."
        ),
        language="en",
    )

    names = {name.lower() for name in _cast_names(response)}
    constraints = {item.label.lower() for item in response.brief.constraints}

    assert response.can_generate is False
    assert response.brief.runtime_fit_status == "not_fit"
    assert "customer" in names
    assert "attendant" in names
    assert "betrayal" not in names
    assert "or public pressure" not in names
    assert "no villains: one customer" not in names
    assert "no villains" in constraints
    assert "avoid public pressure" in constraints


def test_story_brief_filters_exact_small_cast_no_public_pressure_fragments() -> None:
    response = build_story_brief(
        seed=(
            "A quiet two-person laundromat story: one customer and one attendant "
            "try to return a lost wedding ring, no villains, no public pressure, no betrayal."
        ),
        language="en",
    )

    names = {name.lower() for name in _cast_names(response)}
    constraints = {item.label.lower() for item in response.brief.constraints}

    assert response.can_generate is False
    assert response.brief.runtime_fit_status == "not_fit"
    assert {"customer", "attendant"}.issubset(names)
    assert "quiet two-person laundromat story: customer" not in names
    assert "no public pressure" not in names
    assert "betrayal" not in names
    assert "wedding ring" in constraints
    assert "ring" not in constraints
    assert "no villains" in constraints
    assert "avoid public pressure" in constraints


def test_story_brief_filters_laundromat_negated_and_object_focus_fragments() -> None:
    response = build_story_brief(
        seed=(
            "A quiet two-person laundromat story: one customer and one attendant, "
            "no public pressure, no mystery, no conflict, just a wedding ring on a table."
        ),
        language="en",
    )

    primary_names = {
        entity.display_name.lower()
        for entity in response.brief.cast_plan.primary_active_entities
    }
    all_names = {name.lower() for name in _cast_names(response)}
    constraints = {item.label.lower() for item in response.brief.constraints}

    assert response.can_generate is False
    assert response.brief.runtime_fit_status == "not_fit"
    assert {"customer", "attendant"}.issubset(primary_names)
    assert "wedding ring" not in primary_names
    assert "no mystery" not in all_names
    assert "no conflict" not in all_names
    assert "just wedding ring on table" not in all_names
    assert "just a wedding ring on a table" not in all_names
    assert "wedding ring" in constraints
    assert "avoid public pressure" in constraints


def test_story_brief_high_drama_entities_are_not_action_or_pressure_fragments() -> None:
    response = build_story_brief(
        seed=(
            "Minutes before the awards livestream, a famous singer disappears from the control room. "
            "The player is the anxious publicist, the producer wants to keep the livestream moving, "
            "the backup dancer witnessed the singer leave, and the award audience is watching. "
            "The contested pressure is whether to stop the livestream and reveal the disappearance "
            "before sponsors and fans panic; keep it English and high-drama with no gore."
        ),
        language="en",
    )

    primary_names = {
        entity.display_name.lower()
        for entity in response.brief.cast_plan.primary_active_entities
    }
    all_names = {name.lower() for name in _cast_names(response)}
    constraints = {item.label.lower() for item in response.brief.constraints}
    anchors = {item.label.lower() for item in response.brief.time_event_anchors}
    pressure = {item.label.lower() for item in response.brief.world_setting_pressure}

    assert response.can_generate is True
    assert response.brief.runtime_fit_status == "fit"
    assert {"anxious publicist", "producer", "backup dancer", "award audience"}.issubset(primary_names)
    assert "backup dancer witnessed singer leave" not in all_names
    assert "reveal disappearance" not in all_names
    assert "fans panic" not in all_names
    assert "control room" not in all_names
    assert "disappearance" in constraints
    assert "awards livestream" in anchors
    assert "sponsor/fan pressure" in pressure


def test_story_brief_keeps_sentence_form_negated_constraints_out_of_entities() -> None:
    response = build_story_brief(
        seed=(
            "Make it a short English high drama backstage scene where NPCs fight back: "
            "I play a nervous publicist, Producer Han wants the awards livestream to continue, "
            "Rina the backup dancer saw singer Seo Mina leave, sponsors and fans are watching, "
            "and there is no gore."
        ),
        language="en",
        desired_tension_profile="high_drama",
    )

    primary_names = {
        entity.display_name.lower()
        for entity in response.brief.cast_plan.primary_active_entities
    }
    all_entities = [
        *response.brief.cast_plan.primary_active_entities,
        *response.brief.cast_plan.secondary_background_entities,
        *response.brief.cast_plan.omitted_entities,
    ]
    all_names = {entity.display_name.lower() for entity in all_entities}
    all_ids = {entity.entity_id.lower() for entity in all_entities}
    constraints = {item.label.lower() for item in response.brief.constraints}
    preserved = {label.lower() for label in response.brief.preserved_constraints}

    assert response.can_generate is True
    assert response.brief.runtime_fit_status == "fit"
    assert {"nervous publicist", "producer han", "rina backup dancer", "sponsors", "fans"}.issubset(
        primary_names
    )
    assert "there is no gore" not in all_names
    assert "no gore" not in all_names
    assert "there_is_no_gore" not in all_ids
    assert "no_gore" not in all_ids
    assert "no gore" in constraints
    assert "no gore" in preserved
    assert "there is no gore" not in response.brief.premise_summary.lower()


def test_story_brief_filters_exact_high_drama_time_action_fragments_from_entities() -> None:
    response = build_story_brief(
        seed=(
            "Ten minutes before the awards livestream, an anxious publicist deciding whether to "
            "reveal the disappearance faces a producer, a backup dancer witness, fans panicking "
            "outside, and what to hide from sponsors."
        ),
        language="en",
    )

    names = {name.lower() for name in _cast_names(response)}
    constraints = {item.label.lower() for item in response.brief.constraints}
    anchors = {item.label.lower() for item in response.brief.time_event_anchors}
    pressure = {item.label.lower() for item in response.brief.world_setting_pressure}

    assert response.can_generate is True
    assert {"anxious publicist", "producer", "backup dancer", "fans"}.issubset(names)
    assert "ten minutes" not in names
    assert "anxious publicist deciding whether to" not in names
    assert "fans panicking outside" not in names
    assert "what to" not in names
    assert "what to hide" not in names
    assert "what to hide from sponsors" not in names
    assert "disappearance" in constraints
    assert "awards livestream" in anchors
    assert "sponsor/fan pressure" in pressure


def test_story_brief_filters_agent_chat_trapped_clause_from_high_drama_entity() -> None:
    response = build_story_brief(
        seed=(
            "Make it a short English high drama backstage scene where NPCs fight back. "
            "A publicist, producer, backup dancer, sponsor, and missing singer are trapped before "
            "a livestream, and the player must decide what to reveal while fans panic outside."
        ),
        language="en",
        desired_tension_profile="high_drama",
    )

    names = {name.lower() for name in _cast_names(response)}

    assert response.can_generate is True
    assert {"publicist", "producer", "backup dancer", "sponsor", "missing singer"}.issubset(names)
    assert "missing singer are trapped" not in names
    assert "player must" not in names
    assert "are trapped" not in names


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


def test_story_brief_consistency_flags_english_cjk_artifact() -> None:
    brief = build_story_brief(
        seed="In a fantasy library during an eclipse, dragons, ink sprites, and a head librarian argue over a cursed index.",
        language="en",
    ).brief
    check = check_story_brief_opening_consistency(
        brief=brief,
        opening=_Opening(
            content="The eclipse 已经开始 above the library stacks.",
            cast_names=["dragons", "ink sprites", "head librarian"],
        ),
        language="en",
    )

    assert check.status == "fail"
    assert check.should_retry is True
    assert any(v.code == "english_cjk_artifact" for v in check.violations)


def test_story_brief_consistency_flags_forbidden_constraint_contradiction() -> None:
    brief = build_story_brief(
        seed="A cozy bake sale mystery with teacher, principal, parent organizer, and baker; no violence, no betrayal, no blackmail.",
        language="en",
    ).brief
    check = check_story_brief_opening_consistency(
        brief=brief,
        opening=_Opening(
            content="The principal threatens blackmail while a violent betrayal erupts near the cupcake table.",
            cast_names=["teacher", "principal", "parent organizer", "baker"],
        ),
        language="en",
    )

    assert check.status == "fail"
    assert check.should_retry is True
    assert {v.code for v in check.violations} >= {
        "forbidden_no_blackmail_contradiction",
        "forbidden_no_betrayal_contradiction",
        "forbidden_no_violence_contradiction",
    }


def test_story_brief_consistency_fails_missing_emphasized_background_entities() -> None:
    brief = build_story_brief(
        seed=(
            "On Mars colony, a comedy talent show with ten groups - Hydroponics, "
            "Security, Engineering, Medicine, Culture, Terraforming, Council, AI Core, "
            "Theatre Club, and Earth Media before the final broadcast. "
            "Each group should represent Theatre Club and Earth Media concerns."
        ),
        language="en",
    ).brief

    check = check_story_brief_opening_consistency(
        brief=brief,
        opening=_Opening(
            title="Oxygen Heist",
            content=(
                "Engineering, Hydroponics, and Security argue over a backup oxygen tank "
                "while the governor waits outside."
            ),
            cast_names=["Engineering", "Hydroponics", "Security"],
        ),
        language="en",
    )

    assert check.status == "fail"
    assert check.should_retry is True
    assert any(v.code == "brief_emphasized_entity_absent" for v in check.violations)


def test_story_brief_consistency_fails_lower_stakes_mars_escalation() -> None:
    brief = build_story_brief(
        seed=(
            "On Mars colony, a lower-stakes comedy talent show involves Engineering, "
            "Hydroponics, Security, Theatre Club, and Earth Media before the final broadcast; "
            "no violence and no blackmail."
        ),
        language="en",
        desired_tension_profile="comedy",
    ).brief

    check = check_story_brief_opening_consistency(
        brief=brief,
        opening=_Opening(
            title="Oxygen Heist",
            content=(
                "Security accuses Engineering of an Oxygen Heist after a backup oxygen tank "
                "vanishes; Hydroponics risks becoming the scapegoat, and the governor arrives "
                "in ten minutes to decide a permanent position."
            ),
            cast_names=["Engineering", "Hydroponics", "Security"],
        ),
        language="en",
    )

    assert check.status == "fail"
    assert check.should_retry is True
    assert any(v.code == "lower_stakes_profile_escalated" for v in check.violations)


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

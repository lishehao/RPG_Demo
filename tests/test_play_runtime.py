from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from rpg_backend.author.contracts import AuthorPreviewResponse
from rpg_backend.author.preview import build_author_story_summary
from rpg_backend.config import Settings
from rpg_backend.library.service import StoryLibraryService
from rpg_backend.library.storage import SQLiteStoryLibraryStorage
from rpg_backend.main import app
from rpg_backend.play.compiler import _opening_hook_line, compile_play_plan
from rpg_backend.play.gateway import PlayGatewayError
from rpg_backend.play.runtime import (
    _update_feedback_ledgers,
    _update_collapse_pressure_streak,
    apply_turn_resolution,
    build_initial_session_state,
    build_suggested_actions,
    deterministic_narration,
    heuristic_turn_intent,
)
from rpg_backend.play.service import PlayServiceError, PlaySessionService
from rpg_backend.play.stages.render import (
    _has_protagonist_grammar_issue,
    _sanitize_narration,
    _suggestions_target_protagonist,
    _text_mentions_protagonist,
)
from tests.auth_helpers import ensure_authenticated_client
from tests.author_fixtures import author_fixture_bundle
from tests.test_story_library_api import _FakeAuthorJobService, _publish_source


def _preview_response(bundle=None) -> AuthorPreviewResponse:
    fixture = author_fixture_bundle()
    bundle = bundle or fixture.design_bundle
    return AuthorPreviewResponse.model_validate(
        {
            "preview_id": "preview-play-1",
            "prompt_seed": "An envoy tries to hold an archive city together.",
            "focused_brief": fixture.focused_brief.model_dump(mode="json"),
            "theme": {
                "primary_theme": "legitimacy_crisis",
                "modifiers": ["succession", "blackout"],
                "router_reason": "test_fixture",
            },
            "strategies": {
                "story_frame_strategy": "legitimacy_story",
                "cast_strategy": "legitimacy_cast",
                "beat_plan_strategy": "single_semantic_compile",
            },
            "structure": {
                "cast_topology": "three_slot",
                "expected_npc_count": len(bundle.story_bible.cast),
                "expected_beat_count": len(bundle.beat_spine),
            },
            "story": {
                "title": bundle.story_bible.title,
                "premise": bundle.story_bible.premise,
                "tone": bundle.story_bible.tone,
                "stakes": bundle.story_bible.stakes,
            },
            "cast_slots": [
                {"slot_label": member.name, "public_role": member.role}
                for member in bundle.story_bible.cast
            ],
            "beats": [
                {
                    "title": beat.title,
                    "goal": beat.goal,
                    "milestone_kind": beat.milestone_kind,
                }
                for beat in bundle.beat_spine
            ],
            "flashcards": [],
            "stage": "brief_parsed",
        }
    )


def _publish_story(tmp_path, *, bundle=None):
    fixture = author_fixture_bundle()
    bundle = bundle or fixture.design_bundle
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    summary = build_author_story_summary(bundle, primary_theme="legitimacy_crisis")
    story = library_service.publish_story(
        owner_user_id="local-dev",
        source_job_id="job-play-1",
        prompt_seed="An envoy tries to hold an archive city together.",
        summary=summary,
        preview=_preview_response(bundle),
        bundle=bundle,
        visibility="public",
    )
    return library_service, story


class _FakePlayTransport:
    def __init__(self, responses_by_operation):
        self.responses_by_operation = responses_by_operation
        self.max_output_tokens_interpret = 220
        self.max_output_tokens_interpret_repair = 320
        self.max_output_tokens_ending_judge = 180
        self.max_output_tokens_ending_judge_repair = 120
        self.max_output_tokens_pyrrhic_critic = 120
        self.max_output_tokens_render = 420
        self.max_output_tokens_render_repair = 640
        self.use_session_cache = False
        self.call_trace = []
        self._response_index = 0

    def _invoke_json(
        self,
        *,
        system_prompt,
        user_payload,
        max_output_tokens,
        previous_response_id=None,
        operation_name=None,
    ):
        del system_prompt
        queue = self.responses_by_operation.get(operation_name)
        if not queue:
            raise PlayGatewayError(code="play_llm_invalid_json", message=f"missing fake payload for {operation_name}", status_code=502)
        next_item = queue.pop(0)
        self._response_index += 1
        response_id = f"play-{self._response_index}"
        self.call_trace.append(
            {
                "operation": operation_name,
                "response_id": response_id,
                "used_previous_response_id": bool(previous_response_id),
                "max_output_tokens": max_output_tokens,
                "user_payload": user_payload,
                "input_characters": len(str(user_payload)),
                "usage": {},
            }
        )
        if isinstance(next_item, Exception):
            raise next_item
        return SimpleNamespace(
            payload=next_item,
            response_id=response_id,
            usage={},
            input_characters=len(str(user_payload)),
        )


def _no_gateway(_settings=None):
    raise PlayGatewayError(code="play_llm_config_missing", message="disabled_for_test", status_code=500)


def test_compile_play_plan_compresses_three_beat_story_to_short_runtime_budget() -> None:
    fixture = author_fixture_bundle()
    final_beat = fixture.design_bundle.beat_spine[-1].model_copy(
        update={
            "beat_id": "b3",
            "title": "Final Settlement",
            "goal": "Force a public settlement before the archive city fractures for good.",
            "milestone_kind": "commitment",
            "route_pivot_tag": "shift_public_narrative",
            "progress_required": 2,
            "return_hooks": ["The city will accept one public order by dawn."],
        }
    )
    bundle = fixture.design_bundle.model_copy(update={"beat_spine": [*fixture.design_bundle.beat_spine, final_beat]})

    plan = compile_play_plan(story_id="story-short-runtime", bundle=bundle)

    assert [beat.progress_required for beat in plan.beats] == [2, 1, 1]
    assert plan.max_turns == 4
    assert plan.closeout_profile == "record_exposure_closeout"


def test_compile_play_plan_routes_harbor_bundle_to_logistics_closeout_profile() -> None:
    fixture = author_fixture_bundle()
    harbor_brief = fixture.focused_brief.model_copy(
        update={
            "setting_signal": "Harbor quarantine and supply panic grip the port.",
            "core_conflict": "Keep the dock coalition from splintering during emergency rationing.",
        }
    )
    harbor_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Quarantine Harbor",
            "premise": "A harbor inspector must keep the port open under public oversight while quarantine and scarcity drive the city toward fracture.",
            "stakes": "If the compact fails, private emergency control replaces civic authority at the docks.",
            "world_rules": [
                "Harbor access and quarantine enforcement decide who eats and who gets leverage.",
                "Emergency shipping rules become political once scarcity becomes visible.",
            ],
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": harbor_brief,
            "story_bible": harbor_story,
        }
    )

    plan = compile_play_plan(story_id="story-harbor-runtime", bundle=bundle)

    assert plan.closeout_profile == "logistics_cost_closeout"
    assert plan.runtime_policy_profile == "harbor_quarantine_play"


def test_compile_play_plan_routes_archive_vote_bundle_to_archive_runtime_profile() -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "An archivist preserving public trust.",
            "setting_signal": "archive hall during an emergency vote",
            "core_conflict": "verify altered civic records before the result hardens into public truth",
            "tone_signal": "Hopeful civic fantasy",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Voting Ledger",
            "premise": "In a city archive under pressure, an archivist must restore altered records before rumor replaces the public record.",
            "stakes": "If the archive fails, the vote loses legitimacy and the city fractures around competing truths.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
        }
    )

    plan = compile_play_plan(story_id="story-archive-runtime", bundle=bundle)

    assert plan.closeout_profile == "record_exposure_closeout"
    assert plan.runtime_policy_profile == "archive_vote_play"


def test_play_plan_excludes_protagonist_from_visible_stance_bars_and_clarifies_opening(tmp_path) -> None:
    fixture = author_fixture_bundle()
    harbor_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A harbor inspector preventing collapse.",
            "setting_signal": "port city under quarantine and supply panic",
            "core_conflict": "keep the harbor operating while quarantine politics escalate",
            "tone_signal": "Tense civic fantasy",
        }
    )
    harbor_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Quarantine Harbor",
            "premise": "In a harbor city under quarantine, a harbor inspector must keep trade moving while panic spreads through the port.",
            "stakes": "If inspection authority breaks, the city turns scarcity into factional seizure.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": harbor_brief,
            "story_bible": harbor_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert "Envoy Iri" in created.protagonist.identity_summary
    assert "harbor inspector" in created.protagonist.identity_summary.casefold()
    assert "You are the harbor inspector. a harbor inspector" not in created.narration
    assert "The first visible fracture is" not in created.narration
    assert "Envoy Iri" in created.narration
    assert "quarantine politics escalate" not in created.narration.casefold()
    assert "factional seizure" in created.narration.casefold()
    assert "opening pressure" in created.narration.casefold()
    stance_labels = [bar.label for bar in created.state_bars if bar.category == "stance"]
    assert not any("Elara" in label for label in stance_labels)


def test_play_plan_prefers_clean_story_kernel_for_protagonist_mandate(tmp_path) -> None:
    fixture = author_fixture_bundle()
    harbor_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "a harbor inspector preventing a port city from splintering",
            "setting_signal": "harbor during quarantine and supply panic",
            "core_conflict": "a harbor inspector preventing a port city from splintering while quarantine and supply panic strains civic order",
            "tone_signal": "Tense civic fantasy",
        }
    )
    harbor_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Quarantine Harbor",
            "premise": "In Port city under strict quarantine with strained supply lines and inspection chokepoints, Harbor inspector enforcing civic order to prevent splintering during supply panic while Civic fragmentation driven by scarcity fears and unauthorized border crossings.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": harbor_brief,
            "story_bible": harbor_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.title == "Harbor Inspector"
    assert created.protagonist.mandate == "prevent a port city from splintering"
    assert "driven by" not in created.protagonist.identity_summary.casefold()
    assert "In Quarantine Harbor, the crisis is already moving." not in created.narration


def test_play_plan_prefers_cast_role_for_protagonist_title_when_kernel_is_generic(tmp_path) -> None:
    fixture = author_fixture_bundle()
    generic_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "hold the city together",
            "core_conflict": "hold the city together while quarantine politics escalate",
        }
    )
    cast = list(fixture.design_bundle.story_bible.cast)
    cast[0] = cast[0].model_copy(update={"name": "Envoy Iri", "role": "Harbor Inspector"})
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": generic_brief,
            "story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": cast}),
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.title == "Harbor Inspector"
    assert "the hold the city" not in created.protagonist.identity_summary.casefold()


def test_play_plan_prefers_story_kernel_title_over_generic_cast_role(tmp_path) -> None:
    fixture = author_fixture_bundle()
    bundle = fixture.design_bundle.model_copy(deep=True)
    bundle.focused_brief = bundle.focused_brief.model_copy(
        update={
            "story_kernel": "During a blackout referendum, a city ombudsman must keep neighborhood councils from breaking apart",
            "core_conflict": "keep neighborhood councils from breaking apart while a blackout referendum strains civic order",
        }
    )
    bundle.story_bible = bundle.story_bible.model_copy(
        update={
            "cast": [
                fixture.design_bundle.story_bible.cast[0].model_copy(update={"role": "Mediator"}),
                *fixture.design_bundle.story_bible.cast[1:],
            ],
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.title == "Ombudsman"
    assert "the mediator" not in created.protagonist.identity_summary.casefold()
    assert "The first visible fracture is" not in created.narration


def test_play_plan_extracts_role_phrase_from_archive_seed_when_cast_role_is_generic(tmp_path) -> None:
    fixture = author_fixture_bundle()
    bundle = fixture.design_bundle.model_copy(deep=True)
    bundle.focused_brief = bundle.focused_brief.model_copy(
        update={
            "story_kernel": "When sealed chain-of-custody records are altered during a public legitimacy hearing, a civic witness clerk must restore one binding public record before rumor hardens into law.",
            "core_conflict": "restore one binding public record before rumor hardens into law",
        }
    )
    bundle.story_bible = bundle.story_bible.model_copy(
        update={
            "premise": "In a city of archives where civic order depends on trusted records, altered chain-of-custody seals threaten a public legitimacy hearing.",
            "cast": [
                fixture.design_bundle.story_bible.cast[0].model_copy(update={"name": "Elara Vance", "role": "Mediator"}),
                *fixture.design_bundle.story_bible.cast[1:],
            ],
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.title == "Witness Clerk"
    assert "the when sealed" not in created.protagonist.identity_summary.casefold()
    assert "The first pressure point is" not in created.narration


def test_play_plan_falls_back_to_cast_role_when_extracted_title_is_truncated_seed_fragment(tmp_path) -> None:
    fixture = author_fixture_bundle()
    bundle = fixture.design_bundle.model_copy(deep=True)
    bundle.focused_brief = bundle.focused_brief.model_copy(
        update={
            "story_kernel": "When sealed chain-of-custody records are altered",
            "setting_signal": "city during a succession settlement",
            "core_conflict": "When sealed chain-of-custody records are altered while a succession settlement strains civic order",
        }
    )
    bundle.story_bible = bundle.story_bible.model_copy(
        update={
            "premise": "In City hall under succession settlement; civic order strained by disputed inheritance protocols. Verify the integrity of sealed chain-of-custody records before rumors solidify into binding law.",
            "cast": [
                fixture.design_bundle.story_bible.cast[0].model_copy(update={"name": "Elara Vane", "role": "Mediator"}),
                *fixture.design_bundle.story_bible.cast[1:],
            ],
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.title == "Mediator"
    assert "the when sealed" not in created.protagonist.identity_summary.casefold()


def test_play_plan_uses_product_safe_premise_when_story_bible_premise_repeats_clause(tmp_path) -> None:
    fixture = author_fixture_bundle()
    bundle = fixture.design_bundle.model_copy(deep=True)
    bundle.focused_brief = bundle.focused_brief.model_copy(
        update={
            "story_kernel": "When sealed chain-of-custody records are altered",
            "setting_signal": "city during a succession settlement",
            "core_conflict": "When sealed chain-of-custody records are altered while a succession settlement strains civic order",
        }
    )
    bundle.story_bible = bundle.story_bible.model_copy(
        update={
            "premise": "In city during a succession settlement, When sealed chain-of-custody records are altered while When sealed chain-of-custody records are altered while a succession settlement strains civic order.",
            "cast": [
                fixture.design_bundle.story_bible.cast[0].model_copy(update={"name": "Elara Vance", "role": "Mediator"}),
                *fixture.design_bundle.story_bible.cast[1:],
            ],
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.story_title
    detail = library_service.get_story_detail(story.story_id)
    assert detail.story.premise.casefold().count("when sealed chain-of-custody records are altered") <= 1
    assert detail.story.premise.casefold().startswith("in a ")
    assert "must" in detail.story.premise.casefold()
    assert "in city during a succession settlement" not in detail.story.premise.casefold()
    assert "when sealed chain-of-custody records are altered while when sealed" not in created.narration.casefold()


def test_play_opening_narration_avoids_fixed_identity_plus_mandate_template(tmp_path) -> None:
    fixture = author_fixture_bundle()
    blackout_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "During a night-curfew recall vote, a ward mediator must stop staged shortage bulletins from breaking apart the neighborhood councils before the districts seize the grid room by force.",
            "core_conflict": "stop staged shortage bulletins from breaking apart the neighborhood councils",
        }
    )
    blackout_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Civic Accord",
            "premise": "A ward mediator must keep the neighborhood councils aligned while a staged shortage bulletin drives the city toward panic.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": blackout_brief,
            "story_bible": blackout_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert "Your mandate is to" not in created.narration[:160]
    assert not created.narration.startswith("You are Elara Voss, the mediator. Your mandate is to")


def test_play_plan_falls_back_from_noisy_mandate_candidates(tmp_path) -> None:
    fixture = author_fixture_bundle()
    blind_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "a royal archivist proving the warning is real before courtiers bury it triggers open fracture",
            "core_conflict": "prove the warning is real before courtiers bury it triggers open fracture",
            "tone_signal": "Procedural suspense",
        }
    )
    blind_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Blind Record",
            "premise": "In capital, Royal archivist must authenticate and file the observatory's storm warning in the official ledger before courtiers suppress it, while the court strains toward panic.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": blind_brief,
            "story_bible": blind_story,
            "state_schema": fixture.design_bundle.state_schema.model_copy(
                update={
                    "axes": [
                        *fixture.design_bundle.state_schema.axes,
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={
                                "axis_id": "exposure_risk",
                                "label": "Exposure Risk",
                                "kind": "pressure",
                                "starting_value": 0,
                            }
                        ),
                    ]
                }
            ),
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.mandate == "prove the warning is real before courtiers bury it"
    assert "triggers open fracture" not in created.protagonist.identity_summary.casefold()


def test_play_plan_keeps_valid_turn_clause_in_mandate(tmp_path) -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "a municipal archivist proving the ledgers were altered before districts turn violent",
            "core_conflict": "prove the ledgers were altered before districts turn violent",
            "tone_signal": "Procedural suspense",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Blackout Ledger",
            "premise": "A municipal archivist finds the ledgers were altered before districts turn violent.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.mandate == "prove the ledgers were altered before districts turn violent"
    assert "before districts" in created.protagonist.identity_summary.casefold()


def test_play_plan_falls_back_from_long_bridge_mandate_candidate(tmp_path) -> None:
    fixture = author_fixture_bundle()
    bridge_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "a bridge engineer keeping a flood defense coalition intact after forged ration counts pit the upper wards against the river docks",
            "core_conflict": "keep a flood defense coalition intact after forged ration counts pit the upper wards against the river docks reshapes the balance of power",
            "tone_signal": "Tense civic fantasy",
        }
    )
    bridge_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Ledger of Tides",
            "premise": "A bridge engineer must keep a flood defense coalition intact after forged ration counts pit the upper wards against the river docks while the emergency council reshapes the balance of power.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": bridge_brief,
            "story_bible": bridge_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.mandate == "keep the flood defense coalition intact before the wards break apart"
    assert "reshapes the balance of power" not in created.protagonist.identity_summary.casefold()


def test_play_plan_extracts_mandate_from_long_preamble_premise(tmp_path) -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A municipal archivist finds altered ration rolls.",
            "core_conflict": "find the altered ration rolls before coordination collapses",
            "tone_signal": "Procedural suspense",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Altered Ledger",
            "premise": (
                "In a blackout-struck municipal archive where digital records are gone and only sealed ledgers still carry authority, "
                "a municipal archivist "
                "must verify the authenticity of altered ration rolls to expose the political punishment of reform-supporting districts."
            ),
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.mandate != "verify"
    assert created.protagonist.mandate.startswith("verify the authenticity of altered ration rolls")


def test_play_plan_strips_truncated_tail_from_mandate_candidate(tmp_path) -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A municipal archivist finds altered ration rolls.",
            "core_conflict": "find the altered ration rolls before coordination collapses",
            "tone_signal": "Procedural suspense",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Altered Ledger",
            "premise": (
                "In a blackout-struck municipal archive where digital records are gone and only sealed ledgers still carry authority, "
                "a municipal archivist must verify the authenticity of altered ration rolls to expose the political punishment of reform-supporting d."
            ),
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.mandate == "verify the authenticity of altered ration rolls"


def test_play_plan_uses_specific_archivist_ration_fallback(tmp_path) -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A municipal archivist finds the blackout ration rolls were altered to punish districts.",
            "core_conflict": "finds the blackout ration rolls were altered to punish districts. while coordination breaks down",
            "tone_signal": "Procedural suspense",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Rolls of Silence",
            "premise": "In Municipal Archive during blackout-era infrastructure crisis; altered ration ledgers now decide who eats.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.mandate == "verify altered ration rolls before blackout panic turns scarcity into punishment"


def test_play_opening_rewrites_role_discovery_fragments_into_clean_stakes(tmp_path) -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "a municipal archivist must expose altered blackout ration rolls",
            "core_conflict": "expose altered blackout ration rolls before the hearing breaks apart",
            "tone_signal": "Procedural suspense",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Blackout Ledger",
            "premise": "A municipal archivist finds the blackout ration rolls were altered to punish districts that opposed the curfew vote.",
            "stakes": "When the hearing opens, every district will already be watching for proof of retaliation.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert "finds the blackout ration rolls" not in created.narration.casefold()
    assert "The blackout ration rolls were altered to punish districts that opposed the curfew vote." in created.narration


def test_opening_hook_line_avoids_plural_grammar_break() -> None:
    fixture = author_fixture_bundle()
    bundle = fixture.design_bundle.model_copy(
        update={
            "story_bible": fixture.design_bundle.story_bible.model_copy(update={"title": "D"}),
            "beat_spine": [
                fixture.design_bundle.beat_spine[0].model_copy(
                    update={
                        "title": "Forged Reports",
                        "goal": "Trace the forged supply numbers before blackout panic hardens into district blame.",
                    }
                ),
                *fixture.design_bundle.beat_spine[1:],
            ],
        }
    )
    plan = compile_play_plan(story_id="story-hook-grammar", bundle=bundle)

    hook_line = _opening_hook_line(bundle, protagonist=plan.protagonist)

    assert "forged reports starts" not in hook_line.casefold()
    assert "forged reports already underway" in hook_line.casefold()


def test_play_suggestions_prefer_non_player_npc_targets(tmp_path) -> None:
    fixture = author_fixture_bundle()
    harbor_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A harbor inspector preventing collapse.",
            "setting_signal": "port city under quarantine and supply panic",
            "core_conflict": "keep the harbor operating while quarantine politics escalate",
            "tone_signal": "Tense civic fantasy",
        }
    )
    harbor_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Quarantine Harbor",
            "premise": "In a harbor city under quarantine, a harbor inspector must keep trade moving while panic spreads through the port.",
            "stakes": "If inspection authority breaks, the city turns scarcity into factional seizure.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": harbor_brief,
            "story_bible": harbor_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    prompts = [item.prompt for item in created.suggested_actions]
    assert not any("Elara" in prompt for prompt in prompts)


def test_play_suggestions_diversify_targets_after_relationship_shift() -> None:
    plan = compile_play_plan(story_id="story-suggestion-diversity", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-suggestion-diversity")
    state.last_turn_stance_deltas = {
        plan.stances[0].stance_id: 1,
        plan.stances[1].stance_id: -1,
    }

    suggestions = build_suggested_actions(plan, state)

    prompts = [item.prompt for item in suggestions]
    unique_names = {
        npc.name
        for npc in plan.cast
        if npc.npc_id != plan.protagonist_npc_id and any(npc.name in prompt for prompt in prompts)
    }
    assert len(unique_names) >= 2


def test_play_suggestions_use_feedback_specific_variant_copy() -> None:
    plan = compile_play_plan(story_id="story-suggestion-variants", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-suggestion-variants")
    state.last_turn_axis_deltas = {"public_panic": 2}

    suggestions = build_suggested_actions(plan, state)

    labels = [item.label for item in suggestions]
    assert "Cool the crowd" in labels or "Reframe the uproar" in labels


def test_play_session_routes_return_initial_snapshot_and_turn_updates(tmp_path) -> None:
    import rpg_backend.main as main_module

    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Press Sen for proof.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You corner Sen beneath failing lamps and force the sabotage into the open while the rest of the archive floor goes silent around you.",
                    "suggested_actions": [
                        {"label": "Confront the rival", "prompt": "You turn on Broker Tal before he can redirect the panic."},
                        {"label": "Calm the archive floor", "prompt": "You steady the public room before rumor hardens."},
                        {"label": "Call for public accountability", "prompt": "You make the coalition answer to the city in public."},
                    ],
                }
            ],
        }
    )
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )
    original_library_service = main_module.story_library_service
    original_play_service = main_module.play_session_service
    main_module.story_library_service = library_service
    main_module.play_session_service = play_service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="play-routes@example.com", display_name="Play Routes")
        created = client.post("/play/sessions", json={"story_id": story.story_id})
        session_id = created.json()["session_id"]
        fetched = client.get(f"/play/sessions/{session_id}")
        history = client.get(f"/play/sessions/{session_id}/history")
        turned = client.post(
            f"/play/sessions/{session_id}/turns",
            json={"input_text": "I push Archivist Sen for hard proof about the blackout."},
        )
        updated_history = client.get(f"/play/sessions/{session_id}/history")
    finally:
        main_module.story_library_service = original_library_service
        main_module.play_session_service = original_play_service

    assert created.status_code == 200
    assert created.json()["story_id"] == story.story_id
    assert created.json()["beat_index"] == 1
    assert len(created.json()["state_bars"]) == 5
    assert len(created.json()["suggested_actions"]) == 3
    assert created.json()["progress"]["display_percent"] == 0
    assert created.json()["progress"]["total_beats"] >= 1
    assert created.json()["support_surfaces"]["inventory"]["enabled"] is False
    assert created.json()["support_surfaces"]["map"]["enabled"] is False

    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == session_id

    assert history.status_code == 200
    assert history.json()["session_id"] == session_id
    assert history.json()["entries"][0]["speaker"] == "gm"
    assert history.json()["entries"][0]["turn_index"] == 0

    assert turned.status_code == 200
    assert turned.json()["turn_index"] == 1
    assert turned.json()["status"] == "active"
    assert "You corner Sen" in turned.json()["narration"]
    assert len(turned.json()["suggested_actions"]) == 3
    assert turned.json()["protagonist"]["title"]
    assert "feedback" in turned.json()

    assert updated_history.status_code == 200
    assert [entry["speaker"] for entry in updated_history.json()["entries"]] == ["gm", "player", "gm"]
    assert updated_history.json()["entries"][1]["text"] == "I push Archivist Sen for hard proof about the blackout."
    assert updated_history.json()["entries"][2]["turn_index"] == 1
    assert turned.json()["progress"]["display_percent"] > 0


def test_play_session_routes_are_scoped_to_actor(tmp_path) -> None:
    import rpg_backend.main as main_module

    library_service, story = _publish_story(tmp_path)
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
    )
    original_library_service = main_module.story_library_service
    original_play_service = main_module.play_session_service
    main_module.story_library_service = library_service
    main_module.play_session_service = play_service
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    try:
        alice_session = ensure_authenticated_client(alice_client, email="alice-play@example.com", display_name="Alice").json()
        ensure_authenticated_client(bob_client, email="bob-play@example.com", display_name="Bob")
        alice_user_id = str((alice_session.get("user") or {}).get("user_id"))
        published_story = library_service.publish_story(
            owner_user_id=alice_user_id,
            source_job_id="job-owned-story",
            prompt_seed="seed",
            summary=build_author_story_summary(author_fixture_bundle().design_bundle, primary_theme="legitimacy_crisis"),
            preview=_preview_response(),
            bundle=author_fixture_bundle().design_bundle,
        )
        created = alice_client.post("/play/sessions", json={"story_id": published_story.story_id})
        hidden = bob_client.get(f"/play/sessions/{created.json()['session_id']}")
        visible = alice_client.get(f"/play/sessions/{created.json()['session_id']}")
    finally:
        main_module.story_library_service = original_library_service
        main_module.play_session_service = original_play_service

    assert created.status_code == 200
    assert hidden.status_code == 404
    assert visible.status_code == 200


def test_deleting_story_removes_owned_play_sessions(tmp_path) -> None:
    import rpg_backend.main as main_module

    library_service, story = _publish_story(tmp_path)
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
    )
    original_library_service = main_module.story_library_service
    original_play_service = main_module.play_session_service
    main_module.story_library_service = library_service
    main_module.play_session_service = play_service
    client = TestClient(app)
    try:
        auth_payload = ensure_authenticated_client(client, email="play-delete@example.com", display_name="Local Developer").json()
        owner_user_id = str((auth_payload.get("user") or {}).get("user_id"))
        summary = build_author_story_summary(author_fixture_bundle().design_bundle, primary_theme="legitimacy_crisis")
        story = library_service.publish_story(
            owner_user_id=owner_user_id,
            source_job_id="job-delete-owned-play-story",
            prompt_seed="An envoy tries to hold an archive city together.",
            summary=summary,
            preview=_preview_response(),
            bundle=author_fixture_bundle().design_bundle,
            visibility="private",
        )
        created = client.post("/play/sessions", json={"story_id": story.story_id})
        deleted = client.delete(f"/stories/{story.story_id}")
        missing_session = client.get(f"/play/sessions/{created.json()['session_id']}")
    finally:
        main_module.story_library_service = original_library_service
        main_module.play_session_service = original_play_service

    assert created.status_code == 200
    assert deleted.status_code == 200
    assert deleted.json() == {"story_id": story.story_id, "deleted": True}
    assert missing_session.status_code == 404


def test_unauthorized_session_read_does_not_expire_owner_session(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    settings = Settings(
        runtime_state_db_path=str(tmp_path / "runtime.sqlite3"),
        play_session_ttl_seconds=60,
    )
    now = datetime.now(timezone.utc)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
        settings=settings,
        now_provider=lambda: now,
    )

    created = service.create_session(story.story_id, actor_user_id="local-dev")
    service._now_provider = lambda: now + timedelta(seconds=120)

    with pytest.raises(PlayServiceError) as exc_info:
        service.get_session(created.session_id, actor_user_id="bob")

    service._now_provider = lambda: now
    owner_view = service.get_session(created.session_id, actor_user_id="local-dev")

    assert exc_info.value.code == "play_session_not_found"
    assert owner_view.status == "active"


def test_deleting_public_story_removes_sessions_across_owners(tmp_path) -> None:
    import rpg_backend.main as main_module

    source = _publish_source("job-public-delete")
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
    )
    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    original_play_service = main_module.play_session_service
    main_module.author_job_service = _FakeAuthorJobService(source)
    main_module.story_library_service = library_service
    main_module.play_session_service = play_service
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    try:
        ensure_authenticated_client(alice_client, email="alice-public-delete@example.com", display_name="Alice")
        ensure_authenticated_client(bob_client, email="bob-public-delete@example.com", display_name="Bob")
        published = alice_client.post(f"/author/jobs/{source.source_job_id}/publish?visibility=public")
        created = bob_client.post("/play/sessions", json={"story_id": published.json()["story_id"]})
        deleted = alice_client.delete(f"/stories/{published.json()['story_id']}")
        missing_session = bob_client.get(f"/play/sessions/{created.json()['session_id']}")
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service
        main_module.play_session_service = original_play_service

    assert published.status_code == 200
    assert created.status_code == 200
    assert deleted.status_code == 200
    assert missing_session.status_code == 404


def test_play_service_closes_three_beat_story_within_four_turn_short_runtime(tmp_path) -> None:
    fixture = author_fixture_bundle()
    final_beat = fixture.design_bundle.beat_spine[-1].model_copy(
        update={
            "beat_id": "b3",
            "title": "Final Settlement",
            "goal": "Force a public settlement before the archive city fractures for good.",
            "milestone_kind": "commitment",
            "route_pivot_tag": "shift_public_narrative",
            "progress_required": 2,
            "return_hooks": ["The city will accept one public order by dawn."],
        }
    )
    bundle = fixture.design_bundle.model_copy(update={"beat_spine": [*fixture.design_bundle.beat_spine, final_beat]})
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
    )

    snapshot = service.create_session(story.story_id)
    turns = [
        "I investigate the sabotage records and expose the first hidden discrepancy.",
        "I calm the archive floor and keep the coalition from splintering in panic.",
        "I bring the rival and the guardian into one room and force them to answer publicly.",
        "I lock the city into one public settlement before rumor hardens into the new order.",
    ]

    for text in turns:
        snapshot = service.submit_turn(
            snapshot.session_id,
            type("TurnRequest", (), {"input_text": text, "selected_suggestion_id": None})(),
        )

    assert snapshot.turn_index == 4
    assert snapshot.status == "completed"
    assert snapshot.ending is not None


def test_play_service_uses_heuristic_intent_when_interpret_llm_fails(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                PlayGatewayError(code="play_llm_invalid_json", message="bad json", status_code=502),
            ],
            "play_render_turn": [
                {
                    "narration": "You keep the pressure on and pull a hidden fact into the open while the chamber realizes the blackout has an internal author.",
                    "suggested_actions": [
                        {"label": "Lean on the archives", "prompt": "You press for ledger evidence before it disappears."},
                        {"label": "Stabilize the chamber", "prompt": "You calm the room before the panic spreads."},
                        {"label": "Force a concession", "prompt": "You make the coalition pay to keep moving."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I investigate the blackout with Archivist Sen.", "selected_suggestion_id": None})(),
    )

    record = service._sessions[created.session_id]
    assert updated.turn_index == 1
    assert record.state.discovered_truth_ids == ["truth_1"]
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.interpret_source == "heuristic"
    assert trace.render_source == "llm"
    assert trace.interpret_attempts == 2
    assert trace.beat_index_before == 1
    assert trace.beat_index_after == 1
    assert trace.interpret_failure_reason == "play_llm_invalid_json"


def test_play_service_uses_deterministic_narration_when_render_llm_fails(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Press Sen for proof.",
                }
            ],
            "play_render_turn": [
                PlayGatewayError(code="play_llm_invalid_json", message="bad render", status_code=502),
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I demand proof from Archivist Sen.", "selected_suggestion_id": None})(),
    )

    assert "You drag the hidden record into the open" in updated.narration
    assert "You act through" not in updated.narration
    assert len(updated.suggested_actions) == 3
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.interpret_source == "llm"
    assert trace.render_source == "fallback"
    assert trace.render_attempts == 2
    assert trace.interpret_response_id == "play-1"
    assert trace.render_response_id is None
    assert trace.resolution.affordance_tag == "reveal_truth"
    assert trace.render_failure_reason == "play_llm_invalid_json"


def test_play_service_salvages_plaintext_render_without_remote_repair(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Press Sen for proof.",
                }
            ],
            "play_render_turn": [
                "You force the hidden ledger into the open and the archive floor falls into a dangerous hush as the discrepancy becomes undeniable."
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I demand proof from Archivist Sen.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert updated.narration.startswith("You force the hidden ledger into the open")
    assert len(updated.suggested_actions) == 3
    assert trace.render_source == "llm"
    assert trace.render_failure_reason is None


def test_play_service_uses_interpret_repair_before_heuristic_fallback(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                PlayGatewayError(code="play_llm_invalid_json", message="bad json", status_code=502),
            ],
            "play_interpret_repair": [
                {
                    "affordance_tag": "build_trust",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "low",
                    "tactic_summary": "Win Sen over.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You slow the room down and give Sen a reason to stand with you.",
                    "suggested_actions": [
                        {"label": "Push the evidence", "prompt": "You bring the ledger discrepancy into the open."},
                        {"label": "Calm the floor", "prompt": "You keep the chamber from turning ugly."},
                        {"label": "Name the saboteur", "prompt": "You force the rival to answer for the blackout."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I try to win Archivist Sen over quietly.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.interpret_source == "llm_repair"
    assert trace.interpret_attempts == 2
    assert trace.interpret_response_id == "play-2"
    assert trace.resolution.affordance_tag == "build_trust"


def test_play_service_uses_render_repair_when_primary_render_is_low_quality(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Press Sen for proof.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You act through reveal truth involving Archivist Sen.",
                    "suggested_actions": [
                        {"label": "Repeat", "prompt": "Do it again."},
                        {"label": "Repeat", "prompt": "Do it again."},
                        {"label": "Repeat", "prompt": "Do it again."},
                    ],
                }
            ],
            "play_render_repair": [
                {
                    "narration": "You pin Sen's own records under the lamp and force the discrepancy into the center of the room. The silence that follows makes everyone else understand the blackout was engineered, not accidental.",
                    "suggested_actions": [
                        {"label": "Confront the rival", "prompt": "You turn the proof on the rival before he can redirect the blame."},
                        {"label": "Inform the chamber", "prompt": "You carry the proof into the public chamber at once."},
                        {"label": "Lock the archive", "prompt": "You secure the room before the evidence can disappear."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I demand proof from Archivist Sen.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.render_source == "llm_repair"
    assert trace.render_attempts == 2
    assert trace.render_failure_reason == "deterministic_fallback_style"
    assert trace.render_response_id == "play-3"
    assert "pin Sen's own records" in updated.narration


def test_play_service_uses_ending_intent_judge_at_final_beat_handoff(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "build_trust",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "medium",
                    "tactic_summary": "Lock the room in.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "mixed",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You force the final handoff into public view and the room settles for a damaged but workable settlement.",
                    "suggested_actions": [
                        {"label": "Name the cost", "prompt": "You spell out what the city still has to live with."},
                        {"label": "Secure witnesses", "prompt": "You make the public record stick before anyone can rewrite it."},
                        {"label": "Close the chamber", "prompt": "You end the emergency session on your terms."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 2
    record.state.beat_progress = record.plan.beats[record.state.beat_index].progress_required - 1
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the final coalition handoff into public view.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_source == "llm"
    assert trace.ending_judge_proposed_id == "mixed"
    assert trace.resolution.ending_trigger_reason in {
        "judge:mixed",
        "turn_cap:mixed",
        "turn_cap_force:pyrrhic",
        "turn_cap_cost:pyrrhic",
    }


def test_play_service_rejects_illegal_ending_judge_proposal(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Expose it.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "collapse",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You expose the discrepancy, but the chamber is not broken yet and the city still hangs in the balance.",
                    "suggested_actions": [
                        {"label": "Press harder", "prompt": "You push the proof further into the room."},
                        {"label": "Steady the chamber", "prompt": "You keep the room from breaking apart."},
                        {"label": "Name the saboteur", "prompt": "You point directly at the rival now."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = 1
    record.state.axis_values["external_pressure"] = 4

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I reveal the evidence before the room can regroup.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "active"
    assert updated.ending is None
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_source == "llm"
    assert trace.ending_judge_proposed_id == "collapse"
    assert trace.resolution.ending_trigger_reason is None


def test_play_service_skips_first_turn_judge_even_when_pressure_is_hot(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "high",
                    "execution_frame": "public",
                    "tactic_summary": "Expose the ledger immediately.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "collapse",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You expose the discrepancy before the room can bury it, and the chamber recoils as the proof lands in public view.",
                    "suggested_actions": [
                        {"label": "Press the witness", "prompt": "You demand that the witness confirm the altered seal."},
                        {"label": "Lock the record", "prompt": "You move the ledger into the public archive before anyone can touch it."},
                        {"label": "Turn to the gallery", "prompt": "You tell the gallery what the discrepancy now means."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.axis_values["external_pressure"] = 4

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I expose the altered ledger to the whole chamber immediately.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "active"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_source == "skipped"
    assert trace.pyrrhic_critic_source == "skipped"
    assert all(item["operation"] != "play_ending_intent_judge" for item in gateway.call_trace)


def test_play_service_uses_compact_interpret_payload_and_budget(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "execution_frame": "procedural",
                    "tactic_summary": "Force an audit now.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You force the chamber to compare the live seals against the original ledger, and the discrepancy becomes impossible to dismiss.",
                    "suggested_actions": [
                        {"label": "Name the clerk", "prompt": "You identify the clerk who touched the seals last."},
                        {"label": "Fix the record", "prompt": "You demand that the official record be corrected in full view."},
                        {"label": "Hold the floor", "prompt": "You stop the chamber from rushing past the discrepancy."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    service._sessions[created.session_id].state.turn_index = 1
    service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the chamber to compare the live seals against the original ledger.", "selected_suggestion_id": None})(),
    )

    interpret_call = next(item for item in gateway.call_trace if item["operation"] == "play_interpret_turn")
    payload = interpret_call["user_payload"]
    assert "story_premise" not in payload
    assert interpret_call["max_output_tokens"] == 128
    assert all("role" not in npc for npc in payload["npc_catalog"])


def test_play_service_uses_first_turn_fast_path_for_high_confidence_interpret(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_render_turn": [
                {
                    "narration": "You force the chamber to compare the sealed record in public, and the discrepancy lands before anyone can smother it again.",
                    "suggested_actions": [
                        {"label": "Press the witness", "prompt": "You demand that the witness answer for the missing seal."},
                        {"label": "Freeze the record", "prompt": "You hold the public record open until the council cannot walk away from it."},
                        {"label": "Turn to the gallery", "prompt": "You tell the gallery exactly what the discrepancy now means."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the emergency council to compare the sealed record in public before anyone can revise it again.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "active"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.interpret_source == "heuristic"
    assert trace.resolution.affordance_tag == "reveal_truth"
    assert all(item["operation"] != "play_interpret_turn" for item in gateway.call_trace)


def test_play_service_keeps_llm_interpret_for_ambiguous_first_turn(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "build_trust",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "low",
                    "execution_frame": "coalition",
                    "tactic_summary": "Sound people out quietly.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You test the room carefully and keep the next alignment from locking too early.",
                    "suggested_actions": [
                        {"label": "Press the archivist", "prompt": "You ask Archivist Sen what would make the record feel safe to expose."},
                        {"label": "Sound out the broker", "prompt": "You quietly test what Broker Tal would accept before the next public move."},
                        {"label": "Hold the room", "prompt": "You keep the chamber open while you read where the coalition actually stands."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I try to feel out who might move first and see what holds.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.interpret_source == "llm"
    assert any(item["operation"] == "play_interpret_turn" for item in gateway.call_trace)


def test_play_service_uses_ending_judge_repair_when_primary_judge_fails(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "build_trust",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "medium",
                    "tactic_summary": "Lock the room in.",
                }
            ],
            "play_ending_intent_judge": [
                PlayGatewayError(code="play_llm_invalid_json", message="bad judge", status_code=502),
            ],
            "play_ending_intent_judge_repair": [
                {
                    "ending_id": "mixed",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You drag the final bargain into public view and force a damaged but workable settlement to hold.",
                    "suggested_actions": [
                        {"label": "Name the cost", "prompt": "You spell out what the city still has to absorb."},
                        {"label": "Secure witnesses", "prompt": "You make the settlement legible to the public."},
                        {"label": "Close the chamber", "prompt": "You end the emergency sitting on your terms."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 2
    record.state.beat_progress = record.plan.beats[record.state.beat_index].progress_required - 1
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the final coalition handoff into public view.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_source == "llm"
    assert trace.ending_judge_attempts == 2
    assert trace.ending_judge_failure_reason == "play_llm_invalid_json"
    assert trace.ending_judge_response_id == "play-3"
    assert trace.resolution.ending_trigger_reason in {
        "judge:mixed",
        "turn_cap:mixed",
        "turn_cap_force:pyrrhic",
        "turn_cap_cost:pyrrhic",
    }


def test_pyrrhic_judge_relaxation_accepts_near_miss_at_final_beat(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "tactic_summary": "Force the settlement.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "pyrrhic",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You wrench a settlement into place, but everyone in the room can feel what it cost the city to get there.",
                    "suggested_actions": [
                        {"label": "Name the cost", "prompt": "You spell out who will pay for the settlement."},
                        {"label": "Secure the record", "prompt": "You lock the agreement into the public record immediately."},
                        {"label": "Leave the chamber", "prompt": "You end the emergency session before anyone can reopen it."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_pyrrhic_judge_relaxation=True,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 2
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the settlement through at visible civic cost.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.resolution.ending_trigger_reason == "judge_relaxed:pyrrhic"


def test_pyrrhic_judge_relaxation_can_be_disabled(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "tactic_summary": "Force the settlement.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "pyrrhic",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You settle the room, but the compromise still feels damaged and incomplete.",
                    "suggested_actions": [
                        {"label": "Name the damage", "prompt": "You make the public cost visible."},
                        {"label": "Secure the chamber", "prompt": "You keep the bargain from reopening."},
                        {"label": "Record the vote", "prompt": "You force the city to remember how it ended."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_pyrrhic_judge_relaxation=False,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 2
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the settlement through at visible civic cost.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.resolution.ending_trigger_reason == "profile_closeout:pyrrhic"


def test_pyrrhic_critic_can_flip_mixed_judge_to_pyrrhic(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "tactic_summary": "Force the settlement.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "mixed",
                }
            ],
            "play_pyrrhic_critic": [
                {
                    "ending_id": "pyrrhic",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You wrench a settlement into place, but the room knows the city only got there by burning through trust and legitimacy.",
                    "suggested_actions": [
                        {"label": "Name the cost", "prompt": "You spell out the civic damage the deal caused."},
                        {"label": "Secure the record", "prompt": "You lock the agreement into the public record immediately."},
                        {"label": "End the session", "prompt": "You close the emergency chamber before the bargain unravels."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_pyrrhic_judge_relaxation=True,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = 3
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 2
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the settlement through at visible civic cost.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_proposed_id == "mixed"
    assert trace.pyrrhic_critic_source == "llm"
    assert trace.pyrrhic_critic_proposed_id == "pyrrhic"
    assert trace.resolution.ending_trigger_reason == "judge_relaxed:pyrrhic"


def test_turn_cap_closeout_judge_can_land_pyrrhic_without_final_beat_completion(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "tactic_summary": "Force a costly closeout.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "pyrrhic",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You drag the city to a settlement at the last possible moment, and everyone in the room can see what the bargain cost.",
                    "suggested_actions": [
                        {"label": "Name the cost", "prompt": "You tell the city what this settlement cost."},
                        {"label": "Secure the record", "prompt": "You lock the bargain into the public record."},
                        {"label": "Dismiss the chamber", "prompt": "You end the emergency sitting before the deal can unravel."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_pyrrhic_judge_relaxation=True,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 2
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the settlement through and make the city live with the cost.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_source == "llm"
    assert trace.ending_judge_proposed_id == "pyrrhic"
    assert trace.resolution.ending_trigger_reason == "judge_relaxed:pyrrhic"


def test_turn_cap_closeout_can_accept_pyrrhic_before_entering_final_beat(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "tactic_summary": "Force a costly early closeout.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "pyrrhic",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You force a fragile settlement before the final chamber can fully form, and everyone can see what the city had to spend to get there.",
                    "suggested_actions": [
                        {"label": "Name the damage", "prompt": "You make the civic damage visible."},
                        {"label": "Secure witnesses", "prompt": "You lock the bargain into public memory."},
                        {"label": "End the session", "prompt": "You close the emergency sitting now."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_pyrrhic_judge_relaxation=True,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = max(len(record.plan.beats) - 2, 0)
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 2
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force a costly settlement before the final chamber fully forms.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_source == "llm"
    assert trace.ending_judge_proposed_id == "pyrrhic"
    assert trace.resolution.ending_trigger_reason == "judge_relaxed:pyrrhic"


def test_logistics_closeout_profile_accepts_judged_pyrrhic_at_turn_cap_with_moderate_cost(tmp_path) -> None:
    fixture = author_fixture_bundle()
    harbor_brief = fixture.focused_brief.model_copy(
        update={
            "setting_signal": "Harbor quarantine and supply panic grip the port.",
            "core_conflict": "Keep the dock coalition from splintering during emergency rationing.",
        }
    )
    harbor_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Quarantine Harbor",
            "premise": "A harbor inspector must keep the port open under public oversight while quarantine and scarcity drive the city toward fracture.",
            "stakes": "If the compact fails, private emergency control replaces civic authority at the docks.",
            "world_rules": [
                "Harbor access and quarantine enforcement decide who eats and who gets leverage.",
                "Emergency shipping rules become political once scarcity becomes visible.",
            ],
        }
    )
    harbor_bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": harbor_brief,
            "story_bible": harbor_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=harbor_bundle)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "secure_resources",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "medium",
                    "tactic_summary": "Force a dock compact.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "pyrrhic",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You keep the harbor running, but the bargain leaves the city owing a visible civic cost.",
                    "suggested_actions": [
                        {"label": "Name the ration cost", "prompt": "You tell the city what the compact cost."},
                        {"label": "Secure witnesses", "prompt": "You lock the compact into the public record."},
                        {"label": "Dismiss the docks", "prompt": "You end the emergency dock hearing now."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_pyrrhic_judge_relaxation=True,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = max(len(record.plan.beats) - 2, 0)
    record.state.beat_progress = 0
    record.state.axis_values["external_pressure"] = 1
    if "public_panic" in record.state.axis_values:
        record.state.axis_values["public_panic"] = 1
    if "political_leverage" in record.state.axis_values:
        record.state.axis_values["political_leverage"] = 3
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force a dock compact that keeps the port open at visible civic cost.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_proposed_id == "pyrrhic"
    assert trace.resolution.ending_trigger_reason == "judge_relaxed:pyrrhic"


def test_archive_vote_runtime_profile_can_accept_mixed_with_high_proof_and_low_cost(tmp_path) -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "An archivist preserving public trust.",
            "setting_signal": "archive hall during an emergency vote",
            "core_conflict": "verify altered civic records before the result hardens into public truth",
            "tone_signal": "Hopeful civic fantasy",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Voting Ledger",
            "premise": "In a city archive under pressure, an archivist must restore altered records before rumor replaces the public record.",
            "stakes": "If the archive fails, the vote loses legitimacy and the city fractures around competing truths.",
        }
    )
    archive_bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=archive_bundle)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "build_trust",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "medium",
                    "tactic_summary": "Lock the certified record.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "mixed",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You lock the certified ledger into the public archive and the room finally steadies around one accepted record.",
                    "suggested_actions": [
                        {"label": "Close the archive", "prompt": "You seal the room around the certified record."},
                        {"label": "Name the witness line", "prompt": "You record who stood by the chain of custody."},
                        {"label": "End the session", "prompt": "You let the emergency vote settle around one accepted record."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    assert record.plan.runtime_policy_profile == "archive_vote_play"
    record.state.turn_index = 3
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 1
    if "public_panic" in record.state.axis_values:
        record.state.axis_values["public_panic"] = 0
    if "system_integrity" in record.state.axis_values:
        record.state.axis_values["system_integrity"] = 1
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.success_ledger["proof_progress"] = 2
    record.state.success_ledger["settlement_progress"] = 1
    record.state.cost_ledger = {
        "public_cost": 0,
        "relationship_cost": 0,
        "procedural_cost": 0,
        "coercion_cost": 0,
    }
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I certify the corrected ledger and bind the witnesses to the final archive seal.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "mixed"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_proposed_id == "mixed"
    assert trace.resolution.ending_trigger_reason == "judge:mixed"


def test_warning_record_turn_cap_can_resolve_to_mixed_after_pressure_recovers(tmp_path) -> None:
    fixture = author_fixture_bundle()
    blind_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A royal archivist proving the warning is real.",
            "setting_signal": "capital observatory record office under storm threat",
            "core_conflict": "prove the storm bulletin is real before courtiers bury it",
            "tone_signal": "Procedural suspense",
        }
    )
    blind_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Blind Record",
            "premise": "A royal archivist must verify the observatory warning before courtiers suppress it.",
            "stakes": "If the warning is buried, the capital will face the storm unprepared.",
        }
    )
    warning_bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": blind_brief,
            "story_bible": blind_story,
            "state_schema": fixture.design_bundle.state_schema.model_copy(
                update={
                    "axes": [
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={"axis_id": "political_leverage", "label": "Political Leverage", "kind": "relationship", "starting_value": 0}
                        ),
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={"axis_id": "exposure_risk", "label": "Exposure Risk", "kind": "pressure", "starting_value": 0}
                        ),
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={"axis_id": "time_window", "label": "Time Window", "kind": "pressure", "starting_value": 0}
                        ),
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={"axis_id": "external_pressure", "label": "Civic Pressure", "kind": "pressure", "starting_value": 0}
                        ),
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={"axis_id": "public_panic", "label": "Public Panic", "kind": "pressure", "starting_value": 0}
                        ),
                    ],
                }
            ),
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=warning_bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    assert record.plan.runtime_policy_profile == "warning_record_play"
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 5
    record.state.axis_values["exposure_risk"] = 1
    record.state.axis_values["time_window"] = 0
    record.state.axis_values["external_pressure"] = 1
    record.state.axis_values["public_panic"] = 0
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.success_ledger = {
        "proof_progress": 2,
        "coalition_progress": 1,
        "order_progress": 1,
        "settlement_progress": 1,
    }
    record.state.cost_ledger = {
        "public_cost": 1,
        "relationship_cost": 0,
        "procedural_cost": 0,
        "coercion_cost": 0,
    }
    for stance_id in record.state.stance_values:
        record.state.stance_values[stance_id] = 1
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I certify the recovered warning record and let the city settle around one verified account.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "mixed"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.resolution.ending_trigger_reason in {"turn_cap:mixed", "final_beat_default:mixed"}


def test_tuned_collapse_pressure_streak_decays_when_turn_shows_binding_recovery() -> None:
    plan = compile_play_plan(story_id="story-collapse-streak-recovery", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-collapse-streak-recovery")
    state.collapse_pressure_streak = 2
    state.last_turn_axis_deltas = {"public_panic": -1, "political_leverage": 2}
    state.last_turn_stance_deltas = {}
    state.last_turn_consequences = [
        "Visible public pressure eased.",
        "The crisis moved closer to a binding outcome.",
    ]
    state.axis_values["external_pressure"] = 5

    _update_collapse_pressure_streak(
        plan,
        state,
        pressure_axis_id="external_pressure",
        pressure_value=5,
        use_tuned_ending_policy=True,
    )

    assert state.collapse_pressure_streak == 1


def test_pressure_streak_collapse_reframes_to_pyrrhic_when_final_turn_secures_binding_outcome(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "execution_frame": "public",
                    "tactic_summary": "Force the binding order through before the chamber can fracture again.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You force the chamber to accept the binding order, but the city pays for that clarity in fear and resentment.",
                    "suggested_actions": [
                        {"label": "Name the price", "prompt": "You tell the room what this binding order just cost."},
                        {"label": "Stabilize the gallery", "prompt": "You turn toward the gallery before panic spreads any further."},
                        {"label": "Seal the record", "prompt": "You bind the signed order into the public archive immediately."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_ending_intent_judge=False,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.collapse_pressure_streak = 1
    record.state.axis_values["external_pressure"] = 5
    if "public_panic" in record.state.axis_values:
        record.state.axis_values["public_panic"] = 2
    record.state.axis_values["political_leverage"] = 3
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.success_ledger["proof_progress"] = 2
    record.state.success_ledger["settlement_progress"] = 1
    record.state.cost_ledger["public_cost"] = 0
    record.state.cost_ledger["relationship_cost"] = 0
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the binding order through before the chamber can fracture again.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.resolution.ending_trigger_reason in {"collapse_reframed:pyrrhic", "ending_rule:pyrrhic"}


def test_final_beat_binding_outcome_avoids_collapse_when_last_turn_does_not_expand_breakdown(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "execution_frame": "public",
                    "tactic_summary": "I read the signed charter aloud and order the crowd to stand down under the emergency protocol.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You read the signed charter aloud and the city accepts the order, but only after fear has already torn trust apart.",
                    "suggested_actions": [
                        {"label": "Hold the line", "prompt": "You keep the guards between the crowd and the chamber doors."},
                        {"label": "Seal the charter", "prompt": "You bind the emergency protocol into the public archive."},
                        {"label": "Name the cost", "prompt": "You tell the room exactly what this order has already cost."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
        enable_ending_intent_judge=False,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.collapse_pressure_streak = 1
    record.state.axis_values["external_pressure"] = 5
    if "public_panic" in record.state.axis_values:
        record.state.axis_values["public_panic"] = 4
    record.state.axis_values["political_leverage"] = 3
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.success_ledger["proof_progress"] = 2
    record.state.success_ledger["settlement_progress"] = 1
    record.state.cost_ledger["public_cost"] = 0
    record.state.cost_ledger["relationship_cost"] = 1
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I read the signed charter aloud and order the crowd to stand down under the emergency protocol.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.resolution.ending_trigger_reason in {"collapse_reframed:pyrrhic", "ending_rule:pyrrhic"}


def test_play_service_records_turn_trace_for_llm_path(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Press Sen for proof.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You pin the evidence to the table and force the room to look at it before anyone can retreat into procedure or rumor.",
                    "suggested_actions": [
                        {"label": "Press the guardian", "prompt": "You demand the archive guardian answer the discrepancy."},
                        {"label": "Inform the public", "prompt": "You carry the evidence into the public chamber."},
                        {"label": "Secure the room", "prompt": "You lock down the exits until the records are verified."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I demand proof from Archivist Sen.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.turn_index == 1
    assert trace.interpret_source == "llm"
    assert trace.render_source == "llm"
    assert trace.interpret_response_id == "play-1"
    assert trace.render_response_id == "play-2"
    assert trace.beat_title_before == "Opening Pressure"
    assert trace.beat_title_after == "Opening Pressure"
    assert trace.status_after == "active"
    assert trace.resolution.ending_trigger_reason is None


def test_play_service_exposes_public_session_history(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Press Sen for proof.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You pin the evidence to the table and force the room to look at it before anyone can retreat into procedure or rumor.",
                    "suggested_actions": [
                        {"label": "Press the guardian", "prompt": "You demand the archive guardian answer the discrepancy."},
                        {"label": "Inform the public", "prompt": "You carry the evidence into the public chamber."},
                        {"label": "Secure the room", "prompt": "You lock down the exits until the records are verified."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I demand proof from Archivist Sen.", "selected_suggestion_id": None})(),
    )

    history = service.get_session_history(created.session_id)

    assert history.session_id == created.session_id
    assert history.story_id == story.story_id
    assert [entry.speaker for entry in history.entries] == ["gm", "player", "gm"]
    assert history.entries[0].turn_index == 0
    assert history.entries[1].turn_index == 1
    assert history.entries[1].text == "I demand proof from Archivist Sen."


def test_play_service_blocks_pyrrhic_before_final_beat_and_allows_collapse_under_pressure(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)

    def _no_gateway(_settings=None):
        raise PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)

    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
    )

    first_session = service.create_session(story.story_id)
    first_record = service._sessions[first_session.session_id]
    final_event_id = first_record.plan.beats[-1].required_events[0]
    first_record.state.discovered_truth_ids = ["truth_2"]
    first_record.state.discovered_event_ids = [final_event_id]
    first_record.state.flag_values = {flag.flag_id: True for flag in first_record.plan.flags}
    first_record.state.axis_values["political_leverage"] = 5
    first_record.state.axis_values["external_pressure"] = 3

    blocked = service.submit_turn(
        first_session.session_id,
        type("TurnRequest", (), {"input_text": "I negotiate from strength.", "selected_suggestion_id": None})(),
    )

    assert blocked.status == "active"
    assert blocked.ending is None

    first_record.state.beat_index = len(first_record.plan.beats) - 1
    first_record.state.beat_progress = 0
    first_record.state.suggested_actions = []
    allowed = service.submit_turn(
        first_session.session_id,
        type("TurnRequest", (), {"input_text": "I lock the coalition into a brutal compromise.", "selected_suggestion_id": None})(),
    )

    assert allowed.status == "completed"
    assert allowed.ending is not None
    assert allowed.ending.ending_id == "pyrrhic"
    allowed_trace = service.get_turn_traces(first_session.session_id)[1]
    assert allowed_trace.resolution.ending_trigger_reason == "ending_rule:pyrrhic"

    collapse_session = service.create_session(story.story_id)
    collapse_record = service._sessions[collapse_session.session_id]
    collapse_record.state.axis_values["external_pressure"] = 5
    first_overflow = service.submit_turn(
        collapse_session.session_id,
        type("TurnRequest", (), {"input_text": "I force the issue before the city breaks.", "selected_suggestion_id": None})(),
    )

    assert first_overflow.status == "active"
    assert first_overflow.ending is None

    collapsed = service.submit_turn(
        collapse_session.session_id,
        type("TurnRequest", (), {"input_text": "I force the issue again before the city breaks.", "selected_suggestion_id": None})(),
    )

    assert collapsed.status == "completed"
    assert collapsed.ending is not None
    assert collapsed.ending.ending_id == "collapse"
    collapse_trace = service.get_turn_traces(collapse_session.session_id)[1]
    assert collapse_trace.resolution.ending_trigger_reason == "pressure_streak:collapse"


def test_collapse_fallback_reframes_to_pyrrhic_when_judge_pyrrhic_and_success_signals_are_strong(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "tactic_summary": "Force the public settlement through despite the pressure.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "pyrrhic",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You force the settlement into public view and the room accepts it only at obvious civic cost.",
                    "suggested_actions": [
                        {"label": "Name the cost", "prompt": "You tell the chamber exactly what this outcome cost."},
                        {"label": "Secure the record", "prompt": "You lock the settlement into the public record immediately."},
                        {"label": "Dismiss the room", "prompt": "You end the emergency session before the bargain unravels."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = 3
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 5
    if "public_panic" in record.state.axis_values:
        record.state.axis_values["public_panic"] = 2
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.success_ledger["proof_progress"] = 2
    record.state.success_ledger["settlement_progress"] = 1
    record.state.cost_ledger["public_cost"] = 1
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the public settlement through despite the panic outside.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_proposed_id == "pyrrhic"
    assert trace.resolution.ending_trigger_reason in {"judge:pyrrhic", "judge_relaxed:pyrrhic"}


def test_collapse_judge_reframes_to_pyrrhic_when_success_is_real_and_loss_of_control_is_not_total(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "shift_public_narrative",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "high",
                    "execution_frame": "public",
                    "tactic_summary": "Force the settlement into the open before the chamber can bury it again.",
                }
            ],
            "play_ending_intent_judge": [
                {
                    "ending_id": "collapse",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You force the chamber to accept the public settlement, but the cost is obvious in every face left standing in the room.",
                    "suggested_actions": [
                        {"label": "Lock the mandate", "prompt": "You bind the settlement to the public record before anyone can recut it."},
                        {"label": "Name the cost", "prompt": "You tell the room exactly what this victory just burned."},
                        {"label": "Stabilize the crowd", "prompt": "You turn toward the gallery before panic hardens into a riot."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = record.plan.max_turns - 1
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["political_leverage"] = 3
    record.state.axis_values["external_pressure"] = 5
    if "public_panic" in record.state.axis_values:
        record.state.axis_values["public_panic"] = 2
    record.state.discovered_truth_ids = ["truth_1", "truth_2"]
    record.state.discovered_event_ids = [record.plan.beats[-1].required_events[0]]
    record.state.success_ledger["proof_progress"] = 2
    record.state.success_ledger["settlement_progress"] = 1
    record.state.cost_ledger["public_cost"] = 1
    record.state.cost_ledger["relationship_cost"] = 1
    if record.plan.stances:
        record.state.stance_values[record.plan.stances[0].stance_id] = 1
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the public settlement through before the chamber can bury the evidence again.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "pyrrhic"
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.ending_judge_proposed_id == "collapse"
    assert trace.resolution.ending_trigger_reason == "collapse_reframed:pyrrhic"


def test_tuned_ending_policy_delays_pressure_collapse_relative_to_legacy_policy(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)

    def _no_gateway(_settings=None):
        raise PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)

    legacy_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
        use_tuned_ending_policy=False,
    )
    tuned_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=_no_gateway,
        use_tuned_ending_policy=True,
    )

    legacy_session = legacy_service.create_session(story.story_id)
    legacy_record = legacy_service._sessions[legacy_session.session_id]
    legacy_record.state.axis_values["external_pressure"] = 5
    legacy_result = legacy_service.submit_turn(
        legacy_session.session_id,
        type("TurnRequest", (), {"input_text": "I force the issue before the city breaks.", "selected_suggestion_id": None})(),
    )

    tuned_session = tuned_service.create_session(story.story_id)
    tuned_record = tuned_service._sessions[tuned_session.session_id]
    tuned_record.state.axis_values["external_pressure"] = 5
    tuned_result = tuned_service.submit_turn(
        tuned_session.session_id,
        type("TurnRequest", (), {"input_text": "I force the issue before the city breaks.", "selected_suggestion_id": None})(),
    )

    assert legacy_result.status == "completed"
    assert legacy_result.ending is not None
    assert legacy_result.ending.ending_id == "collapse"
    assert tuned_result.status == "active"
    assert tuned_result.ending is None


def test_play_session_sanitizes_opening_premise_and_generic_axis_labels(tmp_path) -> None:
    bundle = author_fixture_bundle().design_bundle.model_copy(deep=True)
    bundle.story_bible = bundle.story_bible.model_copy(
        update={
            "premise": "In a city archive under blackout., As the youngest envoy you must restore the record to. while rival ministries and."
        }
    )
    bundle.state_schema = bundle.state_schema.model_copy(
        update={
            "axes": [
                axis.model_copy(update={"label": "State Axis"})
                for axis in bundle.state_schema.axes
            ]
        }
    )
    library_service, story = _publish_story(tmp_path, bundle=bundle)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert ".," not in created.narration
    assert ". while" not in created.narration.casefold()
    axis_labels = [bar.label for bar in created.state_bars if bar.category == "axis"]
    assert "State Axis" not in axis_labels
    assert axis_labels[:3] == ["External Pressure", "Public Panic", "Political Leverage"]


def test_play_service_completes_after_one_final_beat_turn(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)

    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I lock the final agreement in public view.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "active"
    assert updated.ending is None


def test_play_service_can_resolve_on_entry_to_final_beat_via_handoff(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = 3
    record.state.beat_index = len(record.plan.beats) - 2
    record.state.beat_progress = record.plan.beats[record.state.beat_index].progress_required - 1
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I force the final coalition handoff into public view.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.resolution.ending_trigger_reason is not None


def test_mixed_requires_stability_signal_at_final_beat(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    record.state.turn_index = 3
    record.state.beat_index = len(record.plan.beats) - 1
    record.state.beat_progress = 0
    record.state.axis_values["external_pressure"] = 4
    record.state.axis_values["political_leverage"] = 0
    record.state.discovered_truth_ids = []
    record.state.suggested_actions = []

    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I close the room without really stabilizing it.", "selected_suggestion_id": None})(),
    )

    assert updated.status == "completed"
    assert updated.ending is not None
    assert updated.ending.ending_id == "collapse"


def test_play_service_high_risk_reveal_truth_does_not_auto_drop_stance(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)
    record = service._sessions[created.session_id]
    before = record.state.stance_values["archivist_sen_stance"]

    service.submit_turn(
        created.session_id,
        type(
            "TurnRequest",
            (),
            {"input_text": "I force Archivist Sen to show proof right now.", "selected_suggestion_id": None},
        )(),
    )

    after = record.state.stance_values["archivist_sen_stance"]
    assert after < before


def test_play_session_feedback_tracks_ledgers_and_turn_deltas(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I publicly expose the forged archive record and force Sen to answer.", "selected_suggestion_id": None})(),
    )

    assert updated.feedback is not None
    assert updated.feedback.ledgers.success.proof_progress >= 1
    assert updated.feedback.ledgers.cost.public_cost >= 1
    assert updated.feedback.last_turn_axis_deltas
    assert updated.feedback.last_turn_tags
    assert updated.feedback.last_turn_consequences


def test_play_feedback_does_not_claim_public_pressure_when_only_leverage_moves() -> None:
    fixture = author_fixture_bundle()
    harbor_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "a harbor inspector preventing a port city from splintering",
            "setting_signal": "harbor during quarantine and supply panic",
            "core_conflict": "a harbor inspector preventing a port city from splintering while quarantine and supply panic strains civic order",
        }
    )
    harbor_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Quarantine Harbor",
            "premise": "In Port city under strict quarantine with strained supply lines and inspection chokepoints, Harbor inspector enforcing civic order to prevent splintering during supply panic while Civic fragmentation driven by scarcity fears and unauthorized border crossings.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": harbor_brief,
            "story_bible": harbor_story,
        }
    )
    plan = compile_play_plan(story_id="story-harbor-feedback", bundle=bundle)
    state = build_initial_session_state(plan, session_id="session-harbor-feedback")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="contain_chaos",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            tactic_summary="I steady the dockside hearing before the rumor spreads.",
        ),
    )

    assert resolution.axis_changes.get("public_panic", 0) == 0
    assert state.last_turn_axis_deltas.get("political_leverage", 0) > 0
    assert "public_pressure_rising" not in state.last_turn_tags
    assert "Visible public pressure rose." not in state.last_turn_consequences


def test_heuristic_turn_intent_classifies_execution_frame() -> None:
    plan = compile_play_plan(story_id="story-execution-frame", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-execution-frame")

    coalition_intent = heuristic_turn_intent(
        input_text="I convene a joint audit and ask both factions to sign a shared verification statement together.",
        plan=plan,
        state=state,
    )
    public_intent = heuristic_turn_intent(
        input_text="I step to the public podium and broadcast the exposed ledgers to the whole chamber.",
        plan=plan,
        state=state,
    )
    coercive_intent = heuristic_turn_intent(
        input_text="I order the guards to seize the ledger and force the council to answer immediately.",
        plan=plan,
        state=state,
    )

    assert coalition_intent.execution_frame == "coalition"
    assert public_intent.execution_frame == "public"
    assert coercive_intent.execution_frame == "coercive"


def test_warning_record_runtime_profile_pushes_private_warning_audit_into_exposure_not_public_panic() -> None:
    fixture = author_fixture_bundle()
    blind_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A royal archivist proving the warning is real.",
            "setting_signal": "capital observatory record office under storm threat",
            "core_conflict": "prove the storm bulletin is real before courtiers bury it",
            "tone_signal": "Procedural suspense",
        }
    )
    blind_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Blind Record",
            "premise": "A royal archivist must verify the observatory warning before courtiers suppress it.",
            "stakes": "If the warning is buried, the capital will face the storm unprepared.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": blind_brief,
            "story_bible": blind_story,
            "state_schema": fixture.design_bundle.state_schema.model_copy(
                update={
                    "axes": [
                        *fixture.design_bundle.state_schema.axes,
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={
                                "axis_id": "exposure_risk",
                                "label": "Exposure Risk",
                                "kind": "pressure",
                                "starting_value": 0,
                            }
                        ),
                    ]
                }
            ),
        }
    )
    plan = compile_play_plan(story_id="story-runtime-warning-record", bundle=bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-warning-record")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="reveal_truth",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            tactic_summary="I compare the sealed observatory ledger against the warning bulletin in private before the chamber can bury it.",
        ),
    )

    assert plan.runtime_policy_profile == "warning_record_play"
    assert resolution.axis_changes.get("exposure_risk", 0) > 0
    assert resolution.axis_changes.get("public_panic", 0) == 0


def test_execution_frame_changes_archive_vote_feedback_axis_mapping() -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "An archivist preserving public trust.",
            "setting_signal": "archive hall during an emergency vote",
            "core_conflict": "verify altered civic records before the result hardens into public truth",
            "tone_signal": "Hopeful civic fantasy",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Voting Ledger",
            "premise": "In a city archive under pressure, an archivist must restore altered records before rumor replaces the public record.",
            "stakes": "If the archive fails, the vote loses legitimacy and the city fractures around competing truths.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
            "state_schema": fixture.design_bundle.state_schema.model_copy(
                update={
                    "axes": [
                        *fixture.design_bundle.state_schema.axes,
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={
                                "axis_id": "system_integrity",
                                "label": "Institutional Strain",
                                "kind": "pressure",
                                "starting_value": 0,
                            }
                        ),
                    ]
                }
            ),
        }
    )
    plan = compile_play_plan(story_id="story-runtime-archive-execution-frame", bundle=bundle)

    procedural_state = build_initial_session_state(plan, session_id="session-archive-procedural")
    public_state = build_initial_session_state(plan, session_id="session-archive-public")
    coalition_state = build_initial_session_state(plan, session_id="session-archive-coalition")

    procedural_resolution, _ = apply_turn_resolution(
        plan=plan,
        state=procedural_state,
        intent=SimpleNamespace(
            affordance_tag="reveal_truth",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            execution_frame="procedural",
            tactic_summary="I verify the altered ledger line by line against the sealed archive copy.",
        ),
    )
    public_resolution, _ = apply_turn_resolution(
        plan=plan,
        state=public_state,
        intent=SimpleNamespace(
            affordance_tag="reveal_truth",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            execution_frame="public",
            tactic_summary="I read the forged entries aloud to the gallery before the vote proceeds.",
        ),
    )
    coalition_resolution, _ = apply_turn_resolution(
        plan=plan,
        state=coalition_state,
        intent=SimpleNamespace(
            affordance_tag="reveal_truth",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            execution_frame="coalition",
            tactic_summary="I convene a shared verification with both factions before anyone certifies the result.",
        ),
    )

    assert procedural_resolution.axis_changes.get("system_integrity", 0) > 0
    assert procedural_resolution.axis_changes.get("public_panic", 0) == 0
    assert public_resolution.axis_changes.get("public_panic", 0) > 0
    assert coalition_resolution.axis_changes.get("political_leverage", 0) > 0


def test_repetition_guard_redirects_third_reveal_truth_push_off_repeated_axis() -> None:
    fixture = author_fixture_bundle()
    warning_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A royal archivist proving the warning is real.",
            "setting_signal": "capital observatory record office under storm threat",
            "core_conflict": "prove the storm bulletin is real before courtiers bury it",
            "tone_signal": "Procedural suspense",
        }
    )
    warning_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Blind Record",
            "premise": "A royal archivist must verify the observatory warning before courtiers suppress it.",
            "stakes": "If the warning is buried, the capital will face the storm unprepared.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": warning_brief,
            "story_bible": warning_story,
            "state_schema": fixture.design_bundle.state_schema.model_copy(
                update={
                    "axes": [
                        *fixture.design_bundle.state_schema.axes,
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={
                                "axis_id": "exposure_risk",
                                "label": "Exposure Risk",
                                "kind": "pressure",
                                "starting_value": 0,
                            }
                        ),
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={
                                "axis_id": "system_integrity",
                                "label": "Institutional Strain",
                                "kind": "pressure",
                                "starting_value": 0,
                            }
                        ),
                    ]
                }
            ),
        }
    )
    plan = compile_play_plan(story_id="story-runtime-repetition-guard", bundle=bundle)
    state = build_initial_session_state(plan, session_id="session-repetition-guard")
    state.primary_axis_history = ["exposure_risk", "exposure_risk"]

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="reveal_truth",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            execution_frame="procedural",
            tactic_summary="I compare the sealed observatory ledger against the warning bulletin in private before the chamber can bury it.",
        ),
    )

    assert resolution.axis_changes.get("exposure_risk", 0) == 0
    assert resolution.axis_changes.get("system_integrity", 0) > 0


def test_archive_vote_runtime_profile_pushes_private_verification_into_institutional_strain_not_public_panic() -> None:
    fixture = author_fixture_bundle()
    archive_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "An archivist preserving public trust.",
            "setting_signal": "archive hall during an emergency vote",
            "core_conflict": "verify altered civic records before the result hardens into public truth",
            "tone_signal": "Hopeful civic fantasy",
        }
    )
    archive_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Voting Ledger",
            "premise": "In a city archive under pressure, an archivist must restore altered records before rumor replaces the public record.",
            "stakes": "If the archive fails, the vote loses legitimacy and the city fractures around competing truths.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": archive_brief,
            "story_bible": archive_story,
            "state_schema": fixture.design_bundle.state_schema.model_copy(
                update={
                    "axes": [
                        *fixture.design_bundle.state_schema.axes,
                        fixture.design_bundle.state_schema.axes[0].model_copy(
                            update={
                                "axis_id": "system_integrity",
                                "label": "Institutional Strain",
                                "kind": "pressure",
                                "starting_value": 0,
                            }
                        ),
                    ]
                }
            ),
        }
    )
    plan = compile_play_plan(story_id="story-runtime-archive-vote", bundle=bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-archive-vote")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="reveal_truth",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            tactic_summary="I lock down the records hall and verify the altered vote ledger line by line against the sealed archive copy.",
        ),
    )

    assert plan.runtime_policy_profile == "archive_vote_play"
    assert resolution.axis_changes.get("system_integrity", 0) > 0
    assert resolution.axis_changes.get("public_panic", 0) == 0


def test_blackout_runtime_profile_keeps_public_rumor_exposure_public_facing() -> None:
    fixture = author_fixture_bundle()
    blackout_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A city ombudsman must keep neighborhood councils from breaking apart.",
            "setting_signal": "city during a blackout referendum",
            "core_conflict": "forged supply reports trigger panic across the councils",
            "tone_signal": "Tense civic fantasy",
        }
    )
    blackout_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Blackout Ombudsman",
            "premise": "During a blackout referendum, an ombudsman must keep neighborhood councils from breaking apart after forged supply reports trigger panic.",
            "stakes": "If shared procedure fails, the blackout hardens into district control and rumor rule.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": blackout_brief,
            "story_bible": blackout_story,
        }
    )
    plan = compile_play_plan(story_id="story-runtime-blackout-council", bundle=bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-blackout-council")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="reveal_truth",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            tactic_summary="I go to the public loudspeakers and expose the forged supply reports before the ward delegates can spread new rumors.",
        ),
    )

    assert plan.runtime_policy_profile == "blackout_council_play"
    assert resolution.axis_changes.get("public_panic", 0) > 0


def test_public_semantic_calibration_can_lower_panic_for_reassuring_public_narrative() -> None:
    plan = compile_play_plan(story_id="story-runtime-public-calm", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-public-calm")
    state.axis_values["public_panic"] = 1

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="shift_public_narrative",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            tactic_summary="I go to the public loudspeakers and calmly walk the chamber through the real numbers line by line before panic spreads.",
        ),
    )

    assert resolution.axis_changes.get("public_panic", 0) < 0


def test_public_semantic_calibration_can_raise_panic_for_warning_bells() -> None:
    plan = compile_play_plan(story_id="story-runtime-public-warning", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-public-warning")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="contain_chaos",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="medium",
            tactic_summary="I ring the warning bells and force a public evacuation before the crowd surges through the chamber.",
        ),
    )

    assert resolution.axis_changes.get("public_panic", 0) > 0


def test_render_sanitization_flags_third_person_protagonist_grammar() -> None:
    plan = compile_play_plan(story_id="story-render-grammar", bundle=author_fixture_bundle().design_bundle)
    raw = f"{plan.protagonist_name} steps forward, his voice cutting through the chamber."
    broken = _sanitize_narration(plan, raw)

    assert _text_mentions_protagonist(plan, raw) is True
    assert broken == "You step forward, your voice cutting through the chamber."
    assert _has_protagonist_grammar_issue("you steps forward, his voice cutting through the chamber.") is True


def test_render_sanitization_flags_bodypart_third_person_glitch() -> None:
    plan = compile_play_plan(story_id="story-render-bodypart-glitch", bundle=author_fixture_bundle().design_bundle)
    broken = _sanitize_narration(
        plan,
        "your eyes narrow as he watches the chamberlain scramble for the seal.",
    )

    assert broken.startswith("Your eyes")
    assert _has_protagonist_grammar_issue(broken) is True


def test_render_detects_protagonist_surname_in_suggestions_and_falls_back(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "tactic_summary": "Press Sen for proof.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You pin the proof under the lamp and force the whole chamber to look while the altered ledger entry turns the room against the cover story in real time.",
                    "suggested_actions": [
                        {"label": "Confront Iri", "prompt": "Demand Iri explain the missing record before the chamber breaks."},
                        {"label": "Secure the room", "prompt": "Lock the archive before the evidence disappears."},
                        {"label": "Call witnesses", "prompt": "Bring the witnesses forward before panic outruns the record."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I demand proof from Archivist Sen.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.render_source == "llm"
    assert trace.render_failure_reason is None
    assert not any("Iri" in suggestion.prompt for suggestion in updated.suggested_actions)


def test_render_requires_state_payoff_language_and_falls_back_when_missing(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "execution_frame": "procedural",
                    "tactic_summary": "Verify the ledger in private.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You move carefully through the room and keep the scene from stalling.",
                    "suggested_actions": [
                        {"label": "Press the room", "prompt": "You press the room for more answers."},
                        {"label": "Hold the record", "prompt": "You hold the record steady."},
                        {"label": "Advance the scene", "prompt": "You advance the scene with caution."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I verify the ledger in private before anyone can change it again.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.render_source == "llm_repair"
    assert trace.render_failure_reason == "missing_state_payoff"
    assert "Proof moved into the open." in service.get_session(created.session_id).narration


def test_render_auto_repairs_missing_second_person_before_fallback(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["archivist_sen"],
                    "risk_level": "medium",
                    "execution_frame": "public",
                    "tactic_summary": "Expose the forged report in public.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "Public panic surges as the forged report hits the table and the whole chamber realizes the blackout was staged from inside the archive.",
                    "suggested_actions": [
                        {"label": "Press the guardian", "prompt": "You demand the archive guardian answer the discrepancy."},
                        {"label": "Inform the public", "prompt": "You carry the evidence into the public chamber."},
                        {"label": "Secure the room", "prompt": "You lock down the exits until the records are verified."},
                    ],
                }
            ],
        }
    )
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: gateway,
    )

    created = service.create_session(story.story_id)
    updated = service.submit_turn(
        created.session_id,
        type("TurnRequest", (), {"input_text": "I expose the forged blackout report before the whole chamber.", "selected_suggestion_id": None})(),
    )

    trace = service.get_turn_traces(created.session_id)[0]
    assert trace.render_source == "llm_repair"
    assert trace.render_failure_reason == "missing_second_person"
    assert updated.narration.startswith("You ")


def test_feedback_uses_axis_specific_pressure_tags() -> None:
    plan = compile_play_plan(story_id="story-feedback-axis-tags", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-feedback-axis-tags")

    tags, consequences = _update_feedback_ledgers(
        state,
        plan,
        applied_tag="shift_public_narrative",
        risk_level="medium",
        off_route=False,
        beat_completed=True,
        revealed_truth_ids=[],
        added_event_ids=[],
        axis_deltas={"system_integrity": 1},
        stance_deltas={},
    )

    assert "institutional_strain_rising" in tags
    assert "public_pressure_rising" not in tags
    assert "Institutional strain rose." in consequences


def test_deterministic_narration_excludes_protagonist_name_from_target_clause() -> None:
    plan = compile_play_plan(story_id="story-deterministic-protagonist", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-deterministic-protagonist")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="build_trust",
            target_npc_ids=[plan.protagonist_npc_id, plan.cast[1].npc_id],
            risk_level="medium",
            tactic_summary="I steady the room by binding one ally back into the coalition.",
        ),
    )

    narration = deterministic_narration(plan=plan, state=state, resolution=resolution)

    assert plan.protagonist_name not in narration
    assert "You act through" not in narration


def test_deterministic_narration_carries_last_turn_consequence_into_ending_fallback() -> None:
    plan = compile_play_plan(story_id="story-deterministic-ending-payoff", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-deterministic-ending-payoff")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="shift_public_narrative",
            target_npc_ids=[plan.cast[1].npc_id],
            risk_level="high",
            tactic_summary="I force the chamber to answer in public before the record closes again.",
        ),
    )
    state.last_turn_consequences = [
        "The public ledger breaks the chamber's false calm."
    ]
    state.ending = next(
        ending
        for ending in plan.endings
        if ending.ending_id == "collapse"
    )

    narration = deterministic_narration(plan=plan, state=state, resolution=resolution)

    assert "The public ledger breaks the chamber's false calm." in narration
    assert "The ending locks into" in narration


def test_render_sanitization_repairs_possessive_you_glitch() -> None:
    plan = compile_play_plan(story_id="story-render-possessive", bundle=author_fixture_bundle().design_bundle)
    broken = _sanitize_narration(
        plan,
        f"{plan.protagonist_name} forces the record open while {plan.protagonist_name}'s hand shakes over the seal.",
    )

    assert "you's" not in broken.casefold()
    assert "your hand" in broken.casefold()


def test_render_alias_detection_catches_surname_and_title_variants() -> None:
    plan = compile_play_plan(story_id="story-render-aliases", bundle=author_fixture_bundle().design_bundle)
    plan = plan.model_copy(
        update={
            "protagonist_name": "Councilor Heston Vane",
            "protagonist": plan.protagonist.model_copy(update={"title": "Bridge Engineer"}),
        }
    )

    assert _text_mentions_protagonist(plan, "Physically seize the altered ledger before Vane can order it destroyed.")
    assert _text_mentions_protagonist(plan, "Councilor Vane's allies glare from the gallery.")


def test_render_rejects_suggestions_that_reference_protagonist_by_surname() -> None:
    plan = compile_play_plan(story_id="story-render-suggestion-aliases", bundle=author_fixture_bundle().design_bundle)
    plan = plan.model_copy(
        update={
            "protagonist_name": "High Steward Varen",
            "protagonist": plan.protagonist.model_copy(update={"title": "Archivist"}),
        }
    )

    suggestions = [
        SimpleNamespace(label="Escalate", prompt="Physically seize the altered ledger pages before Varen can order them destroyed."),
        SimpleNamespace(label="Contain", prompt="You move fast to keep the crisis from spilling into open disorder."),
        SimpleNamespace(label="Stabilize", prompt="You work to bring Keeper Elara onto your side before the coalition slips further."),
    ]

    assert _suggestions_target_protagonist(plan, suggestions)


def test_resolution_and_fallback_narration_drop_protagonist_target_ids() -> None:
    plan = compile_play_plan(story_id="story-runtime-protagonist-target", bundle=author_fixture_bundle().design_bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-protagonist-target")

    resolution, _ = apply_turn_resolution(
        plan=plan,
        state=state,
        intent=SimpleNamespace(
            affordance_tag="shift_public_narrative",
            target_npc_ids=[plan.protagonist_npc_id, plan.cast[1].npc_id],
            risk_level="high",
            tactic_summary="I force the chamber to answer in public.",
        ),
    )
    narration = deterministic_narration(plan=plan, state=state, resolution=resolution)

    assert plan.protagonist_npc_id not in resolution.target_npc_ids
    assert plan.protagonist_name not in narration
    assert plan.cast[1].name in narration


def test_play_session_protagonist_card_is_present_and_distinct(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.protagonist is not None
    assert created.protagonist.title
    assert created.protagonist.mandate
    assert created.protagonist.identity_summary
    assert created.progress is not None
    assert created.progress.total_beats >= 1
    assert created.progress.display_percent == 0
    assert created.support_surfaces is not None
    assert created.support_surfaces.inventory.enabled is False
    assert created.support_surfaces.map.enabled is False


def test_play_session_snapshot_stays_content_oriented_for_frontend_scrollspy(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
    )

    created = service.create_session(story.story_id)

    assert created.story_title
    assert created.beat_title
    assert created.protagonist is not None
    assert created.progress is not None
    assert created.progress.max_turns >= 1
    assert len(created.state_bars) >= 1
    assert len(created.suggested_actions) == 3
    assert created.support_surfaces is not None


def test_heuristic_turn_intent_prefers_inventory_semantics_over_force_pay_cost() -> None:
    fixture = author_fixture_bundle()
    harbor_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A harbor inspector preventing a port city from splintering.",
            "setting_signal": "port city under quarantine and supply panic",
            "core_conflict": "keep the harbor operating while quarantine politics escalate",
            "tone_signal": "Tense civic fantasy",
        }
    )
    harbor_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "Quarantine Harbor",
            "premise": "In a harbor city under quarantine, a harbor inspector must keep trade moving while panic spreads through the port.",
            "stakes": "If inspection authority breaks, the city turns scarcity into factional seizure.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": harbor_brief,
            "story_bible": harbor_story,
        }
    )

    plan = compile_play_plan(story_id="story-runtime-harbor-intent", bundle=bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-harbor-intent")

    intent = heuristic_turn_intent(
        input_text="I inspect the harbor manifests myself and force the wardens to account for every missing shipment.",
        plan=plan,
        state=state,
    )

    assert intent.affordance_tag == "secure_resources"
    assert plan.protagonist_npc_id not in intent.target_npc_ids
    assert intent.risk_level == "high"


def test_heuristic_turn_intent_treats_certification_as_public_order_formalization_not_raw_reveal() -> None:
    fixture = author_fixture_bundle()
    warning_brief = fixture.focused_brief.model_copy(
        update={
            "story_kernel": "A royal archivist proving the warning is real.",
            "setting_signal": "capital observatory record office under storm threat",
            "core_conflict": "prove the storm bulletin is real before courtiers bury it",
            "tone_signal": "Procedural suspense",
        }
    )
    warning_story = fixture.design_bundle.story_bible.model_copy(
        update={
            "title": "The Blind Record",
            "premise": "A royal archivist must verify the observatory warning before courtiers suppress it.",
            "stakes": "If the warning is buried, the capital will face the storm unprepared.",
        }
    )
    bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": warning_brief,
            "story_bible": warning_story,
        }
    )

    plan = compile_play_plan(story_id="story-runtime-warning-certify", bundle=bundle)
    state = build_initial_session_state(plan, session_id="session-runtime-warning-certify")

    intent = heuristic_turn_intent(
        input_text="I certify the recovered warning record and let the city settle around one verified account.",
        plan=plan,
        state=state,
    )

    assert intent.affordance_tag == "shift_public_narrative"
    assert intent.execution_frame == "procedural"


def test_play_session_expires_after_ttl(tmp_path) -> None:
    library_service, story = _publish_story(tmp_path)
    current_time = [datetime(2026, 3, 18, tzinfo=timezone.utc)]

    service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(
            PlayGatewayError(code="play_llm_config_missing", message="missing", status_code=500)
        ),
        settings=Settings(play_session_ttl_seconds=60),
        now_provider=lambda: current_time[0],
    )

    created = service.create_session(story.story_id)
    current_time[0] = current_time[0] + timedelta(seconds=61)
    expired = service.get_session(created.session_id)

    assert expired.status == "expired"
    assert "expired" in expired.narration.casefold()

    with pytest.raises(PlayServiceError) as exc_info:
        service.submit_turn(
            created.session_id,
            type("TurnRequest", (), {"input_text": "I keep pushing.", "selected_suggestion_id": None})(),
        )
    assert exc_info.value.code == "play_session_expired"

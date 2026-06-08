from __future__ import annotations

from pathlib import Path

import rpg_backend.narrative.service as narrative_service_module
from rpg_backend.narrative.contracts import (
    CastMember,
    CreateTemplateRequest,
    LocalizedText,
    StoryBriefAdvisorRequest,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService


ROOT = Path(__file__).resolve().parents[1]


def _create_template(
    repo: NarrativeRepository,
    *,
    template_id: str,
    title_i18n: LocalizedText | None = None,
    summary_i18n: LocalizedText | None = None,
) -> None:
    options = [StoryOption(label="Ask the witness", hint="Hold pressure", handle="ask")]
    repo.create_template(
        template_id=template_id,
        owner_user_id="usr_owner",
        seed="A singer disappears before the awards livestream.",
        title="Awards Night Disappearance",
        title_i18n=title_i18n,
        summary_i18n=summary_i18n,
        cast=[
            CastMember(
                character_id="publicist",
                display_name="Anxious publicist",
                role="Player lens",
                relation_to_protagonist="Holding the public room together.",
            ),
            CastMember(
                character_id="producer",
                display_name="Producer",
                role="Pressure holder",
                relation_to_protagonist="Wants the show to continue.",
            ),
        ],
        advisor_persona="A quiet story butler watches the backstage pressure.",
        opening_passage="The control room goes quiet when the singer does not return.",
        opening_options=options,
        player_goals=[],
        failure_conditions=[],
        player_role_options=[],
        visibility="public",
        language="en",
    )
    repo.create_session(
        session_id=f"sess_{template_id}",
        template_id=template_id,
        player_user_id="usr_owner",
    )
    repo.append_story_message(
        f"sess_{template_id}",
        StoryMessage(
            ord=0,
            role="narrator",
            content="The control room goes quiet when the singer does not return.",
            options=options,
        ),
    )


def test_localized_metadata_is_optional_and_roundtrips_when_present(tmp_path: Path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template(repo, template_id="tmpl_default")
    _create_template(
        repo,
        template_id="tmpl_i18n",
        title_i18n=LocalizedText(en="Awards Night Disappearance", zh="颁奖夜失踪"),
        summary_i18n=LocalizedText(en="Singer missing backstage.", zh="歌手在后台失踪。"),
    )

    default = repo.get_template("tmpl_default")
    populated = repo.get_template("tmpl_i18n")

    assert default.title_i18n is None
    assert default.summary_i18n is None
    assert populated.title_i18n
    assert populated.title_i18n.zh == "颁奖夜失踪"
    assert populated.summary_i18n
    assert populated.summary_i18n.en == "Singer missing backstage."


def test_localized_metadata_reaches_summary_and_replay_contracts(tmp_path: Path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    _create_template(
        repo,
        template_id="tmpl_summary_i18n",
        title_i18n=LocalizedText(en="Awards Night Disappearance", zh="颁奖夜失踪"),
        summary_i18n=LocalizedText(en="Singer missing backstage.", zh="歌手在后台失踪。"),
    )
    service = NarrativeService(repository=repo, gateway=None)

    template_summary = service.list_public_templates(viewer_user_id="usr_viewer").items[0]
    session_summary = service.list_my_sessions(player_user_id="usr_owner").items[0]
    replay = service.get_public_replay("sess_tmpl_summary_i18n")

    assert template_summary.title_i18n
    assert template_summary.title_i18n.zh == "颁奖夜失踪"
    assert template_summary.summary_i18n
    assert template_summary.summary_i18n.zh == "歌手在后台失踪。"
    assert session_summary.template_title_i18n
    assert session_summary.template_title_i18n.en == "Awards Night Disappearance"
    assert session_summary.template_summary_i18n
    assert session_summary.template_summary_i18n.en == "Singer missing backstage."
    assert replay.template_title_i18n
    assert replay.template_title_i18n.zh == "颁奖夜失踪"
    assert replay.template_summary_i18n
    assert replay.template_summary_i18n.zh == "歌手在后台失踪。"


def test_generated_templates_store_concise_display_metadata(tmp_path: Path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=None)
    seed = (
        "Ten minutes before a televised charity gala, an anxious publicist, a producer, "
        "a sponsor representative, a backup dancer, and a security lead discover that the headline singer "
        "has vanished from the control room while fans are already chanting outside and the player must decide "
        "what to reveal, what to hold back, and who to protect before the opening speech starts."
    )

    brief_response = service.create_story_brief(
        StoryBriefAdvisorRequest(seed=seed, language="en", desired_tension_profile="high_drama"),
        owner_user_id="usr_owner",
    )
    brief = brief_response.brief
    response = service.create_template(
        CreateTemplateRequest(seed=seed, language="en", visibility="public", story_brief=brief),
        owner_user_id="usr_owner",
    )
    summary = service.list_public_templates(viewer_user_id="usr_viewer").items[0]

    assert brief.display_title
    assert brief.display_intro
    assert len(brief.display_title) <= 52
    assert len(brief.display_intro) <= 118
    assert response.template.title == response.template.title_i18n.en
    assert response.template.summary_i18n
    assert response.template.summary_i18n.en != seed
    assert len(response.template.title_i18n.en or "") <= 52
    assert len(response.template.summary_i18n.en or "") <= 118
    assert "..." not in (response.template.summary_i18n.en or "")
    assert "…" not in (response.template.summary_i18n.en or "")
    assert summary.title_i18n
    assert summary.summary_i18n
    assert summary.summary_i18n.en == response.template.summary_i18n.en


def test_generated_display_intro_avoids_incomplete_trailing_clauses() -> None:
    intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        (
            "Three students, their former mentor, and the archivist clash over a glowing library card "
            "that could prove a scholarship application was switched, but it can also ruin one person's future."
        ),
        language="en",
    )

    assert len(intro) <= 118
    assert intro == "Three students, their former mentor, and the archivist clash over a glowing library card."
    assert "could prove a." not in intro

    weak_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        (
            "Ten minutes before the awards livestream, a missing singer puts a backup dancer, "
            "publicist, producer, and sponsor in"
        ),
        language="en",
    )

    assert weak_intro == ""

    terminal_adverb_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "Three students, their former mentor, and the archivist clash over a glowing library card just",
        language="en",
    )

    assert terminal_adverb_intro == ""

    transitive_fragment_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "Ten minutes before the awards livestream, a missing singer sends a backup dancer, publicist, producer, and sponsor.",
        language="en",
    )
    ceremony_fragment_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "A wedding procession is about to begin when a note reveals a secret. Decide whether to act or let the ceremony.",
        language="en",
    )
    proof_fragment_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "Three students, a former mentor, and an archivist clash over a glowing library card that could prove a scholarship.",
        language="en",
    )
    change_fragment_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "Three students, their former mentor, and the archivist clash over a mysterious library card that could change.",
        language="en",
    )
    terminal_conjunction_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "At a wedding, a mysterious note threatens the ceremony and forces you to expose the secret or.",
        language="en",
    )
    planner_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "High drama scene with backup dancer, anxious publicist, producer, sponsor representative, fans; pressure: awards.",
        language="en",
    )
    clipped_cast_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "Just before closing, a glowing library card sparks a quiet argument among three students, a former mentor.",
        language="en",
    )
    beat_chain_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "secret -> leverage -> confrontation -> relationship shift -> ending.",
        language="en",
    )
    expose_fragment_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "At a high-stakes board gala, a secret recording ignites a power struggle that could destroy the company and expose.",
        language="en",
    )
    care_fragment_intro = narrative_service_module._clean_display_intro(  # noqa: SLF001
        "A glowing library card holds the key to a switched scholarship, but revealing the truth could hurt someone you care.",
        language="en",
    )

    assert transitive_fragment_intro == ""
    assert ceremony_fragment_intro == "A wedding procession is about to begin when a note reveals a secret."
    assert "let the ceremony" not in ceremony_fragment_intro
    assert proof_fragment_intro == ""
    assert change_fragment_intro == ""
    assert terminal_conjunction_intro == ""
    assert planner_intro == ""
    assert clipped_cast_intro == ""
    assert beat_chain_intro == ""
    assert expose_fragment_intro == ""
    assert care_fragment_intro == ""


def test_generated_display_title_keeps_possessives_readable() -> None:
    title = narrative_service_module._clean_display_title("the gala's last secret", language="en")  # noqa: SLF001

    assert title == "The Gala's Last Secret"


def test_frontend_uses_localized_story_metadata_only_for_display_chrome() -> None:
    helper = (ROOT / "frontend2/src/shared/lib/localized-story-metadata.ts").read_text()
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    replay = (ROOT / "frontend2/src/pages/replay/replay-page.tsx").read_text()
    world = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()
    play = (ROOT / "frontend2/src/pages/play/play-page.tsx").read_text()

    assert "metadata?.[lang]" in helper
    assert "return primary" in helper
    assert "getTemplateDisplayTitle" in home
    assert "getSessionDisplayTitle" in home
    assert "getReplayDisplayTitle" in replay
    assert "getTemplateDisplaySummary" in world
    assert "localized-story-metadata" not in play

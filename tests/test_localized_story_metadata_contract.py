from __future__ import annotations

from pathlib import Path

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

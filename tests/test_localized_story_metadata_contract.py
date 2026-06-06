from __future__ import annotations

from pathlib import Path

from rpg_backend.narrative.contracts import (
    CastMember,
    LocalizedText,
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

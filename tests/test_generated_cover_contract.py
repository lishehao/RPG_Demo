from __future__ import annotations

from pathlib import Path

from rpg_backend.narrative.contracts import CastMember, StoryOption
from rpg_backend.narrative.repository import NarrativeRepository


ROOT = Path(__file__).resolve().parents[1]


def test_generated_cover_url_roundtrips_on_template_summary(tmp_path: Path) -> None:
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))

    repo.create_template(
        template_id="tmpl_cover_contract",
        owner_user_id="usr_cover",
        seed="A singer disappears before the awards livestream.",
        title="Awards Night Disappearance",
        cast=[
            CastMember(
                character_id="publicist",
                display_name="Anxious publicist",
                role="player lens",
                relation_to_protagonist="The person holding the room together.",
            ),
            CastMember(
                character_id="producer",
                display_name="Producer",
                role="pressure holder",
                relation_to_protagonist="Wants the show to continue.",
            ),
        ],
        advisor_persona="A quiet story butler watches the backstage pressure.",
        opening_passage="The control room goes quiet when the singer does not return.",
        opening_options=[StoryOption(label="Question the producer", hint="Pressure", handle="question")],
        player_goals=[],
        failure_conditions=[],
        player_role_options=[],
        visibility="public",
        language="en",
        cover_image_url="/webtoons/generated/awards-cover.webp",
    )

    reloaded = repo.get_template("tmpl_cover_contract")
    public = repo.list_public_templates()[0]

    assert reloaded.cover_image_url == "/webtoons/generated/awards-cover.webp"
    assert public.cover_image_url == "/webtoons/generated/awards-cover.webp"


def test_frontend_cover_resolver_prefers_generated_cover_before_internal_shell() -> None:
    source = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()

    assert "cover_image_url?: string | null" in source
    assert "resolveGeneratedCoverUrl" in source
    assert "trimmed.startsWith(\"/webtoons/\")" in source
    assert "trimmed.startsWith(\"https://\")" in source

    generated_check = source.index("const generatedCover = resolveGeneratedCoverUrl(template.cover_image_url)")
    fallback_shell = source.index("const shell = inferShell(template)")
    assert generated_check < fallback_shell

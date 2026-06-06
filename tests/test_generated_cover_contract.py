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
    assert "GENERATED_COVER_FALLBACKS" in source
    assert "inferGeneratedCoverKey" in source
    assert "fallbackCoverCandidates" in source

    generated_check = source.index("const generatedCover = resolveGeneratedCoverUrl(template.cover_image_url)")
    internal_candidates_check = source.index("const [preferred] = fallbackCoverCandidates(template)")
    fallback_shell = source.index("const shell = inferShell(template)")
    assert generated_check < fallback_shell
    assert generated_check < internal_candidates_check < fallback_shell


def test_internal_generated_cover_fallback_assets_are_wired() -> None:
    source = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()
    expected = {
        "generated_entertainment_backstage_disappearance": "cover-entertainment-backstage-disappearance-v1.jpg",
        "generated_office_boardroom_betrayal": "cover-office-boardroom-betrayal-v1.jpg",
        "generated_campus_rain_secret": "cover-campus-rain-secret-v1.jpg",
        "generated_sci_fi_mars_colony_stage": "cover-sci-fi-mars-colony-stage-v1.jpg",
        "generated_fantasy_artifact_auction": "cover-fantasy-artifact-auction-v1.jpg",
        "generated_wedding_aisle_betrayal": "cover-wedding-aisle-betrayal-v1.jpg",
        "generated_family_banquet_inheritance": "cover-family-banquet-inheritance-v1.jpg",
        "generated_rooftop_gala_confrontation": "cover-rooftop-gala-confrontation-v1.jpg",
        "generated_hospital_secret_deadline": "cover-hospital-secret-deadline-v1.jpg",
        "generated_urban_alley_witness": "cover-urban-alley-witness-v1.jpg",
    }

    for key, filename in expected.items():
        assert key in source
        assert filename in source
        assert (ROOT / "frontend2/public/webtoons/covers/generated" / filename).exists()


def test_internal_generated_cover_keyword_priority_favors_setting_before_tone() -> None:
    source = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()

    mars = source.index('key: "generated_sci_fi_mars_colony_stage"')
    artifact = source.index('key: "generated_fantasy_artifact_auction"')
    hospital = source.index('key: "generated_hospital_secret_deadline"')
    wedding = source.index('key: "generated_wedding_aisle_betrayal"')
    entertainment = source.index('key: "generated_entertainment_backstage_disappearance"')
    office = source.index('key: "generated_office_boardroom_betrayal"')
    campus = source.index('key: "generated_campus_rain_secret"')
    family = source.index('key: "generated_family_banquet_inheritance"')
    rooftop = source.index('key: "generated_rooftop_gala_confrontation"')
    alley = source.index('key: "generated_urban_alley_witness"')

    assert mars < artifact < hospital < wedding < entertainment < office < campus < family < rooftop < alley
    assert '"hospital ward"' in source
    assert '"ward"' not in source


def test_visible_template_lists_assign_distinct_internal_fallback_covers() -> None:
    source = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()

    assert "export function assignTemplateCovers" in source
    assert "const usedFallbackCovers = new Set<string>()" in source
    assert "fallbackCoverCandidates(template)" in source
    assert "for (const candidate of candidates)" in source
    assert "if (!usedFallbackCovers.has(candidate))" in source
    assert "generatedCover = resolveGeneratedCoverUrl(template.cover_image_url)" in source
    assert "assigned[template.template_id] = generatedCover" in source
    assert "usedFallbackCovers.add(generatedCover)" in source
    assert "GENERATED_COVER_THEME_SHELLS" in source
    assert "shellVariantSlugs(shell)" in source
    assert "cover-list|" in source

    assert "assignTemplateCovers" in home
    assert "const assignedCovers = assignTemplateCovers(templates)" in home
    assert "cover={assignedCovers[t.template_id]}" in home

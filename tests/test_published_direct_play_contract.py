from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_published_template_cards_start_play_sessions_directly() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    app = (ROOT / "frontend2/src/app/app.tsx").read_text()
    published = home[home.index("const handleStartPublishedTemplate") : home.index("useEffect(() => {")]

    assert "api.startNarrativeSession(templateId)" in published
    assert "onOpenPlay(response.session.session_id)" in published
    assert "startingTemplateRef.current" in published
    assert "onStartTemplate={handleStartPublishedTemplate}" in home
    assert "isStarting={startingTemplateId === tile.template.template_id}" in home
    assert "createNarrativeStoryBrief" not in published
    assert "createNarrativeTemplate" not in published
    home_route = app[app.index('case "home":') : app.index('case "login":')]
    assert "onOpenTemplate" not in home_route


def test_home_plaza_uses_generated_public_templates_not_frontend_presets() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    library = (ROOT / "rpg_backend/narrative/home_story_library.py").read_text()
    script = (ROOT / "tools/seed_home_default_stories.py").read_text()

    assert "saveCreateDraftHandoff" not in home
    assert "source: \"plaza_curated\"" not in home
    assert "CuratedPlazaStory" not in home
    assert "CURATED_PLAZA_STORIES" not in home
    assert "handleStartCuratedStory" not in home
    assert "starterPremiseView" not in home
    assert "starter_premise" not in home
    assert 'data-story-card-kind="preset-story"' not in home
    assert "api.createNarrativeStoryBrief" not in home
    assert "api.createNarrativeTemplate" not in home
    assert "listPublicNarrativeTemplates" in home
    assert "export function publicTemplateDisplayKey" in home
    assert "export function dedupePublicTemplatesForPlaza" in home
    assert "setPublicTemplates(dedupePublicTemplatesForPlaza(res.items))" in home
    assert "api.startNarrativeSession(templateId)" in home
    assert "DEFAULT_HOME_STORY_SPECS" in library
    assert "ensure_default_home_story_library" in library
    assert "service.create_story_guide_turn" in library
    assert "service.create_story_brief" in library
    assert "service.create_template" in library
    assert 'visibility: TemplateVisibility = "public"' in library
    assert "ensure_default_home_story_library(" in script


def test_home_story_area_uses_editorial_mosaic_without_main_story_semantics() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()

    assert "type HomeTileSpan" in home
    assert "type HomeTileArchetype" in home
    assert "const HOME_MOSAIC_RHYTHM" in home
    assert "export function homeTileSpanForItem" in home
    assert "export function homeTileArchetypeForItem" in home
    assert "function assignHomeMosaicSpans" in home
    assert "function HomeEditorialMosaic" in home
    assert 'data-home-editorial-mosaic="true"' in home
    assert "gridTemplateColumns: \"repeat(4, minmax(0, 1fr))\"" in home
    assert "gridAutoRows: \"clamp(172px, 12vw, 190px)\"" in home
    assert "gridAutoFlow: \"dense\" as const" in home
    assert "feature-wide" in home
    assert "feature-tall" in home
    assert "feature-horizontal" in home
    assert "notice-wide" in home
    assert "mainStory" not in home
    assert "leadStory" not in home
    assert "promoted" not in home


def test_home_editorial_tiles_use_regular_rectangular_component_archetypes() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()

    assert "function FullBleedTileImage" in home
    assert "function TileMediaWell" in home
    assert "function PublishedTileComposition" in home
    assert 'data-home-tile-archetype={archetype}' in home
    assert 'data-home-full-bleed="true"' in home
    assert 'data-home-reading-band="true"' in home
    assert 'data-home-tile-text-body="title-deck-action"' in home
    full_bleed = home[home.index("function FullBleedTileImage") : home.index("function TileMediaWell")]
    assert "hpStyles.fullBleedReadingBand" in full_bleed
    assert 'data-home-framed-editorial="true"' in home
    assert 'data-home-media-well={variant}' in home
    archetype_type = home[home.index("type HomeTileArchetype") : home.index("type HomeTileAccentTone")]
    assert '"full_bleed_cinematic"' in archetype_type
    assert '"framed_editorial"' in archetype_type
    assert "character_dossier" not in archetype_type
    assert "dispatch_notice" not in archetype_type
    assert "tall_storyboard" not in archetype_type
    assert 'data-home-storyboard="true"' not in home
    assert 'data-home-cast-dossier="true"' not in home
    assert 'data-home-cast-frame="true"' not in home


def test_home_story_tiles_stay_regular_rectangular_modules() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()

    selector = home[home.index("export function homeTileArchetypeForItem") : home.index("export function getHomeTileCopy")]
    assert "character_dossier" not in selector
    assert "dispatch_notice" not in selector
    assert "tall_storyboard" not in selector
    assert 'variant="sliver"' not in home
    assert 'variant="tall"' not in home
    assert "clipPath" not in home
    assert "polygon(" not in home
    assert "shapeOutside" not in home
    assert "borderRadius: 999" not in home
    assert "hpStyles.dispatchTileLayout" not in home
    assert "hpStyles.tallStoryboardLayout" not in home
    assert "hpStyles.dossierTile" not in home
    assert "hpStyles.castDossier" not in home
    assert "function isSingleRowHomeTileSpan" in home
    assert "return span === \"feature-horizontal\" || span === \"dispatch\" || span === \"notice-wide\"" in home
    assert "return hpStyles.framedTileSplit" in home
    assert "return \"side\"" in home


def test_home_story_tiles_do_not_clip_required_contract_content() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    editorial_tile = home[home.index("editorialTile: {") : home.index("editorialTilePublished:", home.index("editorialTile: {"))]
    media_well = home[home.index("mediaWell: {") : home.index("mediaWellFramed:", home.index("mediaWell: {"))]

    assert 'overflow: "visible"' in editorial_tile
    assert 'overflow: "hidden"' in media_well
    assert "height: \"calc(100% - 24px)\"" in home
    assert "framedTextPanelSplit" in home


def test_home_story_tiles_do_not_use_unreadable_one_by_one_spans() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    span_style = home[home.index("function homeTileSpanStyle") : home.index("function homeTileTitleStyle")]
    span_assigner = home[home.index("export function homeTileSpanForItem") : home.index("function assignHomeMosaicSpans")]

    assert 'if (span === "dispatch") return { gridColumn: "span 2", gridRow: "span 1" }' in span_style
    assert 'return { gridColumn: "span 2", gridRow: "span 1" }' in span_style
    assert 'gridColumn: "span 1", gridRow: "span 1"' not in span_style
    assert 'item.kind === "published_story"' in span_assigner
    assert 'span === "feature-tall"' in span_assigner


def test_home_editorial_tiles_render_generated_playable_story_objects_only() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    strings = (ROOT / "frontend2/src/shared/lib/i18n.ts").read_text()

    helper = home[home.index("export function getHomeTileCopy") : home.index("function publishedStoryView")]
    mosaic = home[home.index("function HomeEditorialMosaic") : home.index("function visibilityLabel")]
    template = home[home.index("function TemplateCard") : home.index("function homeTileSpanStyle")]

    assert "type HomeStoryObjectKind" in home
    assert "type HomeStoryObjectView" in home
    assert "publishedStoryView(" in mosaic
    assert "saveCreateDraftHandoff" not in mosaic
    assert "onStartTemplate(item.template.template_id)" in mosaic
    assert 'data-story-card-kind="published-story"' in template
    assert 'data-home-tile-span={span}' in template
    assert 'data-home-tile-start-state={isStarting ? "starting" : "idle"}' in template
    assert 't("home.card_action")' in helper
    assert "displayView.copy.primaryAction" in template
    assert "editorialTileStarting" in template
    assert "displayView.copy.primaryAction}</TileCommand>" not in template
    assert "HomeTileTextBody" in template
    published_helper = helper[helper.index('kind === "published_story"') : helper.index('kind === "in_progress_run"')]
    assert "Story Butler" not in published_helper
    assert "Story Butler" not in template
    assert "starter_premise" not in home
    assert "Preset story" not in home
    assert '"home.card_action": "Start episode →"' in strings


def test_home_story_tiles_hide_extra_metadata_rows_by_default() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    published = home[home.index("function PublishedTileComposition") : home.index("function FullBleedTileImage")]

    assert "story.promise" not in home
    assert "editorialTileFooter" not in published
    assert "visibilityLabel(" not in published
    assert "played_count" not in published
    assert 'template.cast.map((c) => c.display_name).join(" · ")' not in published


def test_home_story_tiles_render_low_information_body_with_clear_start_action() -> None:
    home = (ROOT / "frontend2/src/pages/home/home-page.tsx").read_text()
    published = home[home.index("function PublishedTileComposition") : home.index("function FullBleedTileImage")]
    body = home[home.index("function HomeTileTextBody") : home.index("function FullBleedTileImage")]

    assert 'data-home-tile-text-body="title-deck-action"' in body
    assert "<TileTitle" in body
    assert "editorialTileDeck" in body
    assert 'data-home-tile-primary-action="true"' in body
    assert 'data-home-tile-start-state={isStarting ? "starting" : "idle"}' in body
    assert "editorialTileActionStarting" in body
    assert "{view.copy.primaryAction}" in body
    assert "<Truncated" not in body
    assert "lineClampStyle" not in body
    assert "TileKicker" not in published
    assert "TileCommand" not in published
    assert "view.copy.typeLabel" not in published
    assert "<HomeTileTextBody" in published

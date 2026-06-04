# Art V12 Asset Completion Handoff

Date: 2026-06-04

Branch: `codex/story-brief-art-v12-asset-completion`

Base: `snapshot/story-brief-v12-integrated-2026-06-04` (`c9733b8641c1e5d0952d6e95f196cffa90c067fb`)

## Visual Decision

- Keep the Cloud3 product shell: dark editorial depth, hard dividers, 2-4px radius, no pill buttons, no nested card stacks.
- Move softness into art surfaces only: homepage plates, play covers, state images, reviewer/portfolio plates, and ending payoff imagery.
- Use contemporary Chinese / East Asian everyday settings and faces where people appear. Avoid Western fantasy, old costume drama, chibi, and fixed protagonist identity.
- Generated art must remain text-safe: no readable text, no pseudo UI, no logos, no interface screenshots, and no decorative writing where core UI text will sit.
- Every active image must identify a product or story surface: create workspace, brief cards, play world cover, reviewer evidence, portfolio proof, ending coda, or empty/loading state.

## Active Assets

All active assets live in `frontend2/public/illustrations/art-v12/` and are optimized WebP files.

| Asset | Size | Surface |
| --- | ---: | --- |
| `home-hero-desktop.webp` | 1774x887 | Homepage desktop hero and story deck |
| `home-hero-mobile.webp` | 852x1846 | Homepage compact/mobile hero |
| `create-guide-workspace.webp` | 1535x1024 | Create / Story Guide Agent background |
| `brief-card-sheet.webp` | 1536x1024 | Neutral cover, Brief Story Card/object-card surfaces, portfolio loop |
| `cover-cozy-social.webp` | 1535x1024 | Cozy/social/comedy play cover |
| `cover-mars-colony-talent.webp` | 1535x1024 | Mars/colony/oxygen/sci-fi play cover |
| `cover-fantasy-modern-library.webp` | 1535x1024 | Modern fantasy/library/eclipse play cover |
| `cover-high-drama-committee.webp` | 1536x1024 | High-drama/social pressure play cover |
| `reviewer-evidence-desk.webp` | 1535x1024 | Reviewer hero/art slot, portfolio inspector, reveal surfaces |
| `portfolio-proof-desk.webp` | 1535x1024 | Portfolio demo poster and video fallback |
| `ending-coda-night.webp` | 1535x1024 | Ending/replay payoff and portfolio final band |
| `empty-state-card-glow.webp` | 1086x1448 | Empty/login state art |
| `loading-dawn-card.webp` | 1024x1536 | Generating/wait-state art |
| `advisor-companion-phone.webp` | 1023x1537 | Advisor/oracle companion vignette |

## Reference Assets

These are included for future art direction, but they should not drive live avatar/cast routing yet.

| Asset | Use |
| --- | --- |
| `reference-character-prop-sheet.webp` | Character and prop production language reference |
| `reference-cast-cluster-community.webp` | Group-cast/community mood reference |

## Rejected Or Deferred Outputs

- Earlier fantasy-library candidate: rejected for pseudo book text and Western/gothic architecture.
- Earlier reviewer and portfolio candidates: rejected for old landscape/wall-art fragments and pseudo UI risk.
- Cast/avatar replacement: deferred. The V12 reference sheets are too fixed for live cast identity and should not flatten dynamic roles.
- Advisor portrait replacement: deferred. `advisor-companion-phone.webp` is a vignette/background, not a portrait pool.

## Code Routing

- `frontend2/src/shared/lib/webtoon-assets.ts`
  - Adds the V12 art base path.
  - Routes generated covers and shared page backgrounds through the V12 pack.
  - Keeps Mars/colony/oxygen/sci-fi setting override intact.
- `frontend2/src/pages/home/home-page.tsx`
  - Uses the mobile-specific homepage plate for compact hero.
- `frontend2/src/pages/portfolio/portfolio-page.tsx`
  - Uses the V12 portfolio proof plate as the video poster.
- `frontend2/src/app/theme.css`
  - Replaces hardcoded generated/soft-east-asian backgrounds with V12 assets.
  - Converts reviewer illustration slots from pale paper/dashed treatment to dark hard image plates.
- `docs/art_direction_handdrawn_storybook.md`
  - Updates active visual rules and the current asset map.

## Page Acceptance Criteria

Homepage:
- Desktop must show dark negative space behind real DOM headline/CTA.
- Mobile 390px must use the vertical hero plate without horizontal overflow or hidden CTA.
- Hero art should feel immersive, not like a generated UI screenshot.

Create and Brief:
- Guide workspace art should support the prompt flow without making the form look like a paper scrapbook.
- Brief/object-card surfaces should read as blank story cards, not fake text.

Play:
- Cozy, Mars, fantasy, and high-drama covers should route by world identity before tone.
- Covers must not drown title, turn metadata, role/goal, latest beat, or actions.

Ending and Replay:
- Ending art should support a resolved coda/payoff first viewport.
- The transcript/history must remain below the result-first summary.

Reviewer and Portfolio:
- Reviewer should stay dark/editorial and evidence-led, not pale case-file paper.
- Portfolio video fallback/poster should not show as an accidental black rectangle.

States:
- Empty, login, and loading art should provide quiet product weight while leaving text and controls readable.

## Mobile Constraints

- Use one column for primary flow at 390px.
- Avoid side-by-side image plus text layouts on mobile unless the image is cropped as a background.
- Keep CTA hit targets rectangular and stable; no pill buttons or chip piles.
- Generated art should crop from the safest text-free region, not from faces or dense prop clusters.

## Risks For Play Tester

- Some V12 images contain tiny non-readable paper/book marks. They are acceptable only behind scrims or away from UI text; if they become visible as pseudo-writing, replace the specific asset.
- `cover-fantasy-modern-library.webp` is intentionally modern fantasy, but it has the highest residual book-spine mark risk.
- `home-hero-desktop.webp` has small story-card thumbnails on the right; verify no overlay makes them look like fake UI.
- Character identity remains unresolved. Do not replace portraits until a proper dynamic East Asian avatar/advisor system exists.

## Next Product Handoff

1. Run full browser smoke on homepage, create, cozy/Mars/fantasy/high-drama play openings, ending/replay, reviewer, portfolio, login, empty, and mobile 390px.
2. If screenshots pass, consider this V12 pack the active production art baseline.
3. Next art batch should be a real character/advisor portrait system, not more page backgrounds.

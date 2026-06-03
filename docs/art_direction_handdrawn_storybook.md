# Illustration-Led Storybook Art Direction

Tiny Stories should feel like a polished product for building and inspecting
AI story runs, with hand-drawn illustration concentrated in the story assets
and reference surfaces. The previous full-parchment UI pass helped establish a
clear identity, but the corrected direction is more restrained: modern,
readable product chrome with illustrated notebook/storyboard assets carrying
the hand-made character.

The target is a premium illustrated case notebook: clean controls, strong text
contrast, warm but not beige-monotone surfaces, and line-art/world imagery in
places where the user is orienting to a story.

## Accepted Soft East Asian Homepage Rule

- The active homepage direction is Korean-premium product chrome with soft
  contemporary Chinese / East Asian hand-drawn art plates layered behind it.
- The homepage hero may use generated background-only illustration when it is
  text-safe, UI-free, and composed with dark negative space for real interface
  copy.
- Do not turn the homepage into a beige/parchment interface. Controls,
  typography, spacing, and CTA hierarchy should stay crisp and product-grade.
- Do not use generated plates that contain readable interface text, pseudo UI,
  signage, logos, watermarks, or foreign-language artifacts.
- Current accepted V1 homepage asset:
  `/illustrations/soft-east-asian/homepage-hero-desktop.webp`.

## Visual Tokens

- `surface`: warm off-white and light cream for product panels.
- `page`: subtle warm-neutral background, not a full parchment sheet.
- `ink`: dark graphite/brown for primary text and borders.
- `muted-ink`: readable secondary text; never low-contrast beige.
- `sepia`: restrained editorial accents, stamps, and small labels.
- `sage`: low-stakes success, cozy guidance, and helpful hints.
- `burnt-orange`: warnings, pressure, and active turn emphasis.
- `graphite-blue`: reviewer/debug/evidence information.
- `illustration-wash`: low-saturation watercolor or pencil wash inside image
  slots, not behind dense text.
- `shadow`: soft product shadow, with only slight hand-made irregularity.
- `radius`: 6-8px for controls and cards.
- `font-ui`: current UI font for controls and dense metadata.
- `font-story`: current narrative serif for prose, titles, and passages.

## Product UI Rules

- UI chrome should be polished first. Prefer clean layout, stable spacing,
  readable controls, and subtle paper/sketch accents.
- Do not make every surface look like parchment. Use warm product panels for
  forms, options, receipts, and reviewer/debug rows.
- Keep CTAs and inputs familiar. They may use ink/sepia accents, but should
  not look like novelty stickers or handmade scrapbooking elements.
- Use texture sparingly: paper grain, tape, ruled lines, and dashed borders are
  accents, not the primary visual system.
- Avoid dense beige-on-beige palettes. Pair warm surfaces with graphite text,
  sage, muted blue, and burnt orange where status needs distinction.
- Motion should remain small and product-like: lift, settle, reveal, or slide.
  Avoid cartoon bounce and long decorative animation.

## Illustration And Asset Rules

Hand-drawn style belongs mainly in content/reference assets:

- hero/reviewer/play cover backgrounds
- generated/story reference panels
- scene/storyboard thumbnails
- role, object, clue, intervention, or reference cards when they represent
  story content
- empty states and portfolio case-study visuals
- future template galleries or episode summaries

Illustrations should support story comprehension. They can be line-art,
watercolor, sketchbook, storyboard, or case-file imagery. They should not
replace basic UI affordances or make controls harder to scan.

## Surface Guidance

### Create

- Keep the seed input and settings clean and product-grade.
- Brief planning can use a small draft/adaptation cue, but the main action path
  should stay clear: write, plan, confirm, generate.
- Story Brief details should remain collapsed-first on mobile.
- Use illustrated hints or examples only as supporting material, not as a wall
  of decorative cards.

### Story Brief

- Treat the Brief as an adaptation contract, not a decorative note.
- Primary cast, background cast, constraints, time anchors, and warnings should
  be structurally clear before they are stylized.
- Compression/omission rationale must be readable and trustworthy.
- Use illustration slots only when they clarify setting, genre, or story
  pressure.

### Play

- Narrative prose must sit on clean, high-contrast surfaces.
- Play cover/header imagery can carry the illustrated style, but it should not
  cross story text or hide controls.
- Cover/reference images should use curated, text-free local illustrations
  first. They may be broad by profile, but must not contain readable unrelated
  language, UI screenshots, or story-specific claims that the premise did not
  earn.
- Options, intervention cards, diary, advisor, and impact receipts stay aligned
  and product-like, with only light notebook accents.
- Keep the verified objective contrast and advisor/header overlap fixes.

### Reviewer

- Reviewer entry should feel like a premium case notebook: clean proof copy,
  stable checklist, visible evidence, and one strong illustrated reference
  panel.
- Runtime Inspector and Agent Trace surfaces should look like a serious ledger,
  not a decorative scrapbook.
- If local AI is unavailable, keep the dependency copy explicit and credible.

## Accessibility And Readability

- Body text must preserve WCAG AA-level contrast where practical.
- Never place important prose over dense hatching, dark images, or watercolor.
- Minimum body size: 15-16px UI text, 17-19px narrative prose. Metadata may go
  to 12px only with strong contrast and short labels.
- Maintain visible `:focus-visible` outlines.
- Honor `prefers-reduced-motion`.
- Mobile layouts should not rotate, overlap, or hide primary actions behind
  decorative elements.

## What Not To Do

- Do not interpret hand-drawn as paper UI everywhere.
- Do not turn the app into a children's book, fantasy poster, or scrapbook.
- Do not use dark fantasy, neon cyberpunk, glossy anime UI, or beige monotone.
- Do not use scribble fonts for body text or important labels.
- Do not draw characters into every UI state.
- Do not add large batches of generated images without a named asset list,
  art-direction review, and repository-size plan.
- Do not let visual texture reduce perceived engineering quality.

## Current Implementation Notes

- Core UI tokens are warm-neutral and restrained.
- Demo-facing generated assets live under `/illustrations/generated/*.webp`.
  They are optimized derivatives of the built-in Image Generation pack, not
  raw 3MB PNG drops.
- Play/template cover surfaces route through generated broad-profile covers:
  neutral storyboard, cozy/comedy, fantasy/sci-fi, Mars/sci-fi, and
  high-drama/social. Selection is deterministic from profile and lightweight
  seed/title/cast keywords.
- Strong setting/world keywords override tone. Mars, colony, oxygen, space,
  sci-fi, faction, orbital, or hydroponics signals use the Mars/sci-fi cover
  even when the story tension profile is comedy/cozy.
- Page-level first-run backgrounds now use generated workspace/evidence images
  instead of dark legacy `/webtoons/ui` backgrounds.
- Empty states, ending/replay hero imagery, oracle vignette, and peak beat
  close-ups use generated notebook/evidence/object-card imagery for demo-safe
  consistency.
- Reviewer and portfolio CSS backgrounds that bypassed the central asset helper
  now point at generated evidence/object/ending images.
- Reviewer mode includes an illustration slot using
  `/illustrations/case-notebook-panel.svg` as a bounded reference asset.
- The small curated SVG story-cover set remains in the repo as a lightweight
  fallback/reference layer, but active template cards prefer the richer
  generated cover set.
- Legacy `/webtoons` assets are deliberately retained for cast portraits and
  advisor portraits until a proper role-reference/advisor batch exists. Do not
  flatten live cast identity with the current two generic generated portraits.
- `frontend2/src/shared/lib/format.ts` still contains an unused legacy shell
  cover table; remove or align it only if a future owner verifies it is dead or
  reactivates that helper.
- The prior hand-drawn repair fixes remain required: play objective contrast,
  reviewer copy consistency, mobile Brief hierarchy, cozy cap rationale, and
  advisor/header overlap.

## P0 Generated Asset Mapping

| Asset | Active use |
| --- | --- |
| `/illustrations/generated/cover-neutral-storyboard-desk.webp` | Home/splash background, neutral generated cover, opening scene fallback |
| `/illustrations/generated/cover-cozy-bake-sale.webp` | Cozy/comedy generated cover |
| `/illustrations/generated/cover-fantasy-library-eclipse.webp` | Fantasy/sci-fi generated cover |
| `/illustrations/generated/cover-sci-fi-mars-colony-talent-show.webp` | Mars/oxygen/colony generated cover |
| `/illustrations/generated/cover-high-drama-boardroom.webp` | High-drama generated cover and pressure/peak visual |
| `/illustrations/generated/reviewer-evidence-board-clean.webp` | Reviewer hero, portfolio inspector, login/evidence surfaces, reveal/peak visual |
| `/illustrations/generated/advisor-notebook-desk.webp` | Create background and oracle vignette |
| `/illustrations/generated/empty-plaza-story-cards.webp` | Empty plaza/shared empty-state imagery |
| `/illustrations/generated/ending-reflection-notebook.webp` | Ending/replay hero and portfolio final visual |
| `/illustrations/generated/object-card-sheet.webp` | Generating background, portfolio loop visual, reversal/peak visual |

| Deferred generated assets | Reason |
| --- | --- |
| `reviewer-evidence-board-candidate-with-possible-marks.png` | Possible pseudo-writing/marking risk |
| `role-portrait-neutral-figure.png` | Too specific for broad live cast identity |
| `role-portrait-comedy-helper.png` | Too specific for broad live cast/advisor identity |

## Future Asset System Notes

- Build a small, named asset kit before scaling: story cover frames, scene
  thumbnails, clue/object cards, role-reference cards, empty-state panels, and
  reviewer evidence boards.
- Prefer reusable asset slots and predictable dimensions over one-off art drops.
- Generated per-story imagery should remain future work until it has prompt
  controls, language/text hygiene, fallback covers, and reviewer-safe asset
  gating. Curated static covers are the default beta strategy.
- Keep assets named by function: `story-cover`, `scene-thumb`,
  `reference-card`, `evidence-board`, `empty-state`.
- When adding generated image assets, keep prompts short, inspect outputs, and
  add only the smallest coherent set needed for a tested surface.

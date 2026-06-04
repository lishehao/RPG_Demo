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
- Current accepted V12 homepage assets:
  `/illustrations/art-v12/home-hero-desktop.webp` and
  `/illustrations/art-v12/home-hero-mobile.webp`.

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
- `radius`: 2-4px for controls, hard plates, and story surfaces.
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
  art-direction review, QA notes, and repository-size plan.
- Do not let visual texture reduce perceived engineering quality.

## Current Implementation Notes

- Core UI tokens follow the Cloud3 hard-plate system: premium dark editorial
  shell, 2-4px radius, no pill buttons, no nested card stacks, no parchment UI
  chrome.
- Active demo-facing art now lives under `/illustrations/art-v12/*.webp`.
  These are optimized WebP derivatives of built-in Image Generation outputs,
  not raw multi-megabyte PNG drops.
- Play/template cover surfaces route through broad-profile V12 covers: neutral
  brief-card desk, cozy/social, Mars/colony, modern fantasy/library, and
  high-drama/committee. Selection stays deterministic from profile and
  lightweight seed/title/cast keywords.
- Strong setting/world keywords override tone. Mars, colony, oxygen, space,
  sci-fi, faction, orbital, or hydroponics signals use the Mars/sci-fi cover
  even when the story tension profile is comedy/cozy.
- Page-level first-run backgrounds now use V12 workspace, loading, empty, and
  mobile-specific homepage assets instead of older generated or webtoon
  backgrounds.
- Reviewer and portfolio CSS backgrounds that bypassed the central asset helper
  now point at V12 reviewer, portfolio, brief-card, and ending images.
- Reviewer illustration slots use dark hard image plates; the pale paper/dashed
  slot treatment is no longer the active Cloud3 rule.
- The small curated SVG story-cover set and older `/illustrations/generated`
  pack remain as lightweight fallback/reference layers, but active demo-facing
  code prefers the V12 set.
- Legacy `/webtoons` assets are deliberately retained for cast portraits,
  advisor portraits, and logo only until a proper role-reference/advisor batch
  exists. Do not flatten live cast identity with generic concept portraits.
- `frontend2/src/shared/lib/format.ts` still contains an unused legacy shell
  cover table; remove or align it only if a future owner verifies it is dead or
  reactivates that helper.

## V12 Asset Mapping

| Asset | Active use |
| --- | --- |
| `/illustrations/art-v12/home-hero-desktop.webp` | Homepage desktop first viewport and story deck |
| `/illustrations/art-v12/home-hero-mobile.webp` | Homepage 390px compact hero |
| `/illustrations/art-v12/create-guide-workspace.webp` | Create / Story Guide Agent background |
| `/illustrations/art-v12/brief-card-sheet.webp` | Neutral cover, Brief Story Card/object-card surfaces, portfolio loop |
| `/illustrations/art-v12/cover-cozy-social.webp` | Cozy/comedy/social generated cover |
| `/illustrations/art-v12/cover-mars-colony-talent.webp` | Mars/oxygen/colony/sci-fi generated cover |
| `/illustrations/art-v12/cover-fantasy-modern-library.webp` | Fantasy/modern-library generated cover |
| `/illustrations/art-v12/cover-high-drama-committee.webp` | High-drama/social pressure generated cover |
| `/illustrations/art-v12/reviewer-evidence-desk.webp` | Reviewer hero/art slot, portfolio inspector, reveal visual |
| `/illustrations/art-v12/portfolio-proof-desk.webp` | Portfolio demo poster and video fallback surface |
| `/illustrations/art-v12/ending-coda-night.webp` | Ending/replay payoff and portfolio final band |
| `/illustrations/art-v12/empty-state-card-glow.webp` | Login and empty/shared waiting surfaces |
| `/illustrations/art-v12/loading-dawn-card.webp` | Generating/wait-state background |
| `/illustrations/art-v12/advisor-companion-phone.webp` | Advisor/oracle vignette, not avatar replacement |

| Reference/deferred V12 assets | Reason |
| --- | --- |
| `/illustrations/art-v12/reference-character-prop-sheet.webp` | Character/prop language reference only; not active UI |
| `/illustrations/art-v12/reference-cast-cluster-community.webp` | Useful group-cast direction, but too fixed for live avatar routing |

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

# Hand-Drawn Storybook Art Direction

This direction keeps Tiny Stories readable as a product while making the
surface feel like a warm sketchbook used to plan, play, and review a story.
The target is hand-made, restrained, and inspectable: imperfect ink edges,
cream paper panels, taped notes, soft watercolor shadows, and charcoal/sepia
linework.

## Visual Tokens

- `paper`: `#f4ead8` cream cards for primary content, never pure white.
- `parchment`: `#e8d6b6` page background with faint fiber/noise texture.
- `ink`: `#2a241d` main text and border strokes.
- `charcoal`: `#4a453d` secondary text and sketched dividers.
- `sepia`: `#7a5733` headings, stamps, and editorial annotations.
- `sage`: `#7f8f70` quiet success, helpful hints, low-stakes affordances.
- `burnt-orange`: `#c06a36` pressure, active turn, deadline, warning emphasis.
- `graphite-blue`: `#53616b` reviewer/debug/meta information.
- `soft-shadow`: `0 10px 24px rgba(65, 45, 25, 0.14)` for paper lift.
- `ink-border`: 1-2px irregular stroke, preferably via SVG/noise border asset
  or border-image, not a perfectly smooth outline.
- `radius`: 6-8px for paper cards and controls; use uneven corner treatment
  only as texture, not layout geometry.
- `font-ui`: current Inter-like UI font for controls and dense metadata.
- `font-story`: current narrative serif for story prose, titles, and passages.

## UI Rules

- Use a full parchment/sketchbook background, then layer cream paper surfaces
  directly on it. Avoid nested cards.
- Cards should look like notes or index cards: slight rotation is allowed only
  for decorative or non-interactive supporting pieces. Functional controls must
  stay aligned.
- Borders should feel hand-inked but still crisp enough to read on mobile.
  Prefer subtle waviness, corner imperfections, stamped labels, and divider
  ticks over heavy illustration.
- CTAs remain ordinary product controls. They may use inked outlines, tape-tab
  labels, or soft orange fill, but must not look like novelty stickers.
- Use hand-drawn object language sparingly: notebook tabs, phone-card snippets,
  sticky notes, desk lamp pools, potted plant silhouettes, stacked index cards,
  pinned storyboard frames.
- Use storyboard panels when the user is comparing states, reviewing a run, or
  inspecting a story arc. Use single large paper sheets when the user is typing
  or reading.
- Motion should be small and paper-like: lift, settle, unfold, ink underline
  reveal. Avoid bouncy cartoon motion and long decorative animations.
- Glows are allowed only for magical/story pressure moments and should be
  muted watercolor washes, not neon halos.

## Surface Examples

### Create

- Main seed input becomes a large notebook page with a sketched margin line and
  soft desk-lamp shadow.
- Settings use compact tabs or taped labels along the page edge: length,
  difficulty, language, visibility, tension profile.
- Example seeds appear as loose index cards in a row or stack. Keep text dense
  enough to scan; no oversized marketing cards.
- The generate action should read as a clear product button, not a drawing.

### Story Brief

- Treat the brief card as the planner's annotated index card.
- Primary cast and background cast can be two side-by-side taped columns, with
  small sketched role icons only if they do not distract from names/rationales.
- Constraints, time anchors, and world pressure should look like annotated
  marginalia or pinned slips, not cast members.
- Warnings and revision actions should use burnt-orange ink and small stamp
  language. The beta/adaptation note stays visible but quiet.
- Omitted cast should feel like a folded "parking lot" slip, reinforcing that
  they are preserved as context but not active in the first runtime window.

### Play

- Story beats read as storyboard panels on paper, with narrator prose given the
  most stable text area.
- Player choices can be phone-card or torn-note controls, but all options must
  align and wrap cleanly.
- Inventory, leverage, pulse, diary, and advisor surfaces should feel like
  desk-side artifacts: clipped cards, sealed note, small ledger row, or margin
  annotations.
- Reviewer trace/debug details should use graphite-blue and ruled-paper rows so
  they feel inspectable without competing with the fiction.

### Reviewer

- Reviewer entry should feel like a curated desk folder: title page, checklist,
  locked seed, and evidence slips.
- The live inspector should use ledger styling, with clearly grouped rows for
  stage, role, inventory, ending, and agent trace.
- Keep the route portfolio-grade: fewer decorative drawings, more readable
  proof objects and stable screenshots/panels.

## Accessibility And Readability

- Body text must preserve at least WCAG AA contrast. Texture must never reduce
  text contrast below readable thresholds.
- Keep narrative prose on clean paper areas. Do not place text over heavy
  watercolor, dense hatching, or illustrated objects.
- Minimum body size: 15-16px UI text, 17-19px narrative prose. Metadata may go
  to 12px only with strong contrast and short labels.
- Maintain visible `:focus-visible` outlines. Inked focus rings should be
  obvious for keyboard users.
- Honor `prefers-reduced-motion`; paper unfold/settle effects should collapse
  to near-instant opacity changes.
- Ensure all functional images or icons have text labels, accessible names, or
  redundant visible copy.
- Mobile cards should not rotate or overlap. Hand-made texture should not
  compromise tap targets or scrolling.

## What Not To Do

- Do not turn the app into a children's book. The tone is warm, literary, and
  professional.
- Do not use dark fantasy, neon cyberpunk, glossy anime UI, or flat beige
  monochrome.
- Do not rely on large decorative hero art for the core workflow.
- Do not use scribble fonts for body text or important labels.
- Do not draw characters into every UI state. Character visuals should support
  story comprehension, not crowd controls.
- Do not use paper texture as an excuse for low contrast or imprecise spacing.
- Do not add generated image assets until the UI token system and reusable
  paper/ink primitives are settled.

## Future Asset System Notes

- Build a small asset kit first: paper grain tile, irregular ink border,
  tape strip, sticky-note background, ruled notebook lines, stamp badge,
  storyboard panel frame, desk object silhouettes.
- Keep assets parametric where possible: CSS masks, border-image slices, and
  repeatable transparent PNGs/SVGs are preferable to one-off screenshots.
- Provide light/dark compatibility only if required; the primary direction is
  warm parchment with dark ink.
- Name assets by function, not mood: `paper-grain`, `ink-border-soft`,
  `tape-strip-top`, `storyboard-frame`, `ledger-row`.
- Before broad rollout, test create, story brief, play, reviewer, ending, and
  mobile widths against the same token set so the art direction does not
  fragment by page.

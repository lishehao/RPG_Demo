# Cloud 3 Full App UI V2

Base: `snapshot/story-brief-main-loop-architecture-v3-2026-06-03` (`8c2e5b3`).

This visual branch is intentionally not rebased onto Product V4 (`snapshot/story-brief-main-loop-v4-fantasy-renderer-2026-06-03` / `fa4a85b`). A follow-up integration pass should merge Product V4 runtime changes with this Art/UI V2 branch after both are validated.

## Applied Rule Set

- Premium dark editorial product shell is the default app chrome.
- Soft contemporary Chinese / East Asian hand-drawn art stays inside hero, cover, reference, and story surfaces.
- UI primitives use hard plates: radius `2-4px`, hard dividers, square buttons, no pill CTAs.
- Display serif is reserved for hero/story headings and narration; UI controls use the UI sans; metadata can use mono.
- No parchment full-page skin, no beige card stack, no nested-card visual treatment.
- Scenario imagery must remain text-safe generated art, not generated UI screenshots.

## Implemented P0 Surfaces

- Homepage V2 first viewport:
  - left DOM headline/CTA zone;
  - right story-desk / Brief Story Card visual deck;
  - bottom scenario rail using existing generated cover plates.
- Create page:
  - dark Story Guide Agent shell;
  - rectangular text input plate;
  - examples/settings/Brief Story Card converted from paper/dashed notes to hard plates.
- Play page:
  - dark sticky header and play column;
  - role/goal/context text hierarchy kept from Product IA;
  - latest beat changed to a high-contrast story plate;
  - action choices, selected state, custom move, resolving state, and retry action converted to hard plate styling.
- Shared tokens:
  - dark shell variables;
  - reduced global radius;
  - modern topbar/drawer primitives.

## Deferred

- Product V4 fantasy renderer integration.
- Full cleanup of every lower-frequency drawer, inspector, reviewer, portfolio, replay, login, and error sub-state.
- Avatar/advisor portrait replacement.
- New generated image batch.

## QA Focus

- 390px mobile homepage: no horizontal overflow and scenario rail remains readable.
- Create empty state and Brief Story Card: no beige parchment feel, no nested-card stack.
- Play opening and after one selection: role/goal, latest beat, and next actions remain the visual priority.
- Cover routing still chooses Mars cover for Mars/colony/oxygen/sci-fi settings.

# Cloud3 Reviewer / Portfolio Visual Repair

Base: `snapshot/story-brief-product-v4-cloud3-ui-v2-integrated-2026-06-03`
(`05a1366372c24aef58af6dbfad275585e561d711`).

## Changed

- Reviewer route now uses the Cloud3 dark editorial shell instead of the pale
  paper/case-file treatment.
- Reviewer hero keeps the evidence-board illustration as an image surface, but
  text and actions sit on a dark hard plate with high contrast.
- Reviewer checklist changed from low-contrast paper cards to a hard divided
  step rail, with single-column dividers on mobile.
- Portfolio demo preview uses the existing local MP4 with a poster-backed
  `<video>` element, so the first viewport does not degrade into a plain black
  rectangle when the YouTube embed poster/autoplay path fails.

## Deferred

- Play action discovery and prose/not-fit copy are Product/R&D follow-up items,
  not part of this visual repair.
- Runtime inspector drawers, replay detail states, login/signed-out gate,
  provider unavailable, and deeper error sub-states still need a dedicated
  lower-frequency Cloud3 cleanup pass.
- Legacy logo/avatar/advisor imagery remains accepted/deferred unless Product
  requests a character-system replacement pass.

## QA Focus

- Reviewer desktop and 390px mobile should read as premium dark Cloud3 surfaces:
  no parchment dominance, no low-contrast title, no dim step cards, no overflow.
- Portfolio desktop and 390px mobile should show an intentional poster-backed
  demo preview before playback, with the YouTube and MP4 links still available.
- Home, create, and play should load without shared-token regressions.

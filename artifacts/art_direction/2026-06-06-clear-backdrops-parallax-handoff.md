# Tiny Stories Clear Backdrops and Parallax Handoff

Project: Tiny Stories - Clearer Backdrop and 3D Parallax Visual Asset Pass
Date: 2026-06-06

## Visual Decision

The Play stage should keep the Korean webtoon/manhwa red-black-gold identity,
but the first beat cannot read as a black fog panel. Prefer the `_clear_v2`
segment assets for high-frequency opening/pressure/reveal/reversal/terminal
beats where UI overlays sit on top of the image.

The new clear variants are background plates, not cover cards. They should
communicate place, pressure, and phase while leaving dark edge space for UI.

## Clear Variant Routing Recommendation

R&D owns resolver wiring. Design recommendation:

1. If a story-specific generated segment image exists, use it first.
2. For the high-frequency themes below, prefer `_clear_v2` variants over older
   darker segment files when the current phase matches:
   - backstage / entertainment
   - office / boardroom
   - campus
   - wedding
   - family / inheritance
3. If no clear variant matches, fall back to the existing phase pool.
4. Do not use these as global UI chrome. They are Play/Create story-surface art.

## Parallax Component Spec

Goal: make the background feel alive behind the UI. This is a subtle depth
effect, not a game scene and not a Three.js showcase.

Recommended layer stack:

1. Background image plane
   - The selected segment image.
   - Full bleed within the Play stage backdrop.
   - Slight oversized scale: 1.04 to 1.08 so movement never exposes edges.

2. Mid light/fog/glass plane
   - CSS or lightweight Three.js transparent plane.
   - Use red/gold soft gradients, stage haze, rain sheen, or glass reflection.
   - Opacity target: 0.10 to 0.22.
   - Blend should lift depth, not reduce readability.

3. Foreground vignette/edge plate
   - Static overlay or plane.
   - Dark left/bottom edges for story text and action UI.
   - Avoid fully black opacity over the image center.

Mouse movement:

- Desktop only.
- Translate background plane about 2 to 6 px from center.
- Rotate or skew light plane about 0.5 to 1.5 degrees maximum.
- Foreground vignette can move 1 to 2 px in the opposite direction.
- Ease movement over 160 to 260 ms.
- Clamp movement tightly; it should feel like lens depth, not camera control.

Mobile:

- Disable pointer parallax below 720 px width.
- If motion remains, use a very slow one-time settle or static image only.
- No horizontal overflow. Overscan the image rather than moving the layout box.

Reduced motion:

- Respect `prefers-reduced-motion: reduce`.
- Use static image, static vignette, no infinite shimmer, no parallax loop.

Performance:

- One active parallax scene at a time.
- Use planes only; no heavy 3D models, no live shadows, no expensive particles.
- Reuse textures and dispose old texture/materials on scene change.
- Prefer CSS transform parallax if Three.js setup adds startup cost or console
  risk. Three.js is optional; the desired effect is depth, not technology.

## UI Overlay Guidance

- Keep title/turn/context overlays on dark edges, not over the brightest focal
  subject.
- Preserve action clarity. Background motion should stop or damp while a choice
  is selected/resolving.
- Avoid blue or SaaS-glass color casts. Use charcoal, red, amber, and muted gold.
- The image must remain legible after the app's actual overlay gradient.

## QA Checklist

- First Play opening beat reads as a place within 2 seconds.
- A player can identify the theme/phase without reading the turn text.
- No readable text, logos, subtitles, fake UI, or watermarks in the image.
- No horizontal overflow at 390 px mobile.
- No continuous animation when reduced motion is enabled.
- No console errors from texture loading or scene cleanup.
- No heavy GPU frame drops from multiple active scenes.

## Asset Evidence

Accepted clear-variant contact sheet:
`/tmp/tiny-stories-clear-play-backdrops-contact-sheet.jpg`

Current clear variants live in:
`frontend2/public/webtoons/segments/*_clear_v2.jpg`

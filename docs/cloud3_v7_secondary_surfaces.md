# Cloud3 V7 Secondary Surfaces QA Repair

Base snapshot: `snapshot/story-brief-product-v6-mobile-cue-brief-polish-2026-06-03`

## Repaired in this pass

- Play reviewer/runtime inspector now uses a dark Cloud3 utility plate instead
  of a pale ruled-paper/dashed inspector surface.
- Agent trace rows use solid dividers, dark readable text, and the existing
  debug/accent hierarchy.
- Advisor floating entry, drawer backdrop, drawer panel, transcript, suggestions,
  composer, and oracle confirmation controls now follow the dark plate/drawer
  system instead of the old brown paper panel treatment.
- Mobile advisor FAB keeps the same DOM and behavior but uses a square Cloud3
  command surface instead of a low-padding pill-like override.

## Audited and left unchanged

- Login and shared empty states were already dark editorial surfaces and did not
  need a P0 repair.
- Replay and ending surfaces already use flat dark hero/section treatment with
  hard dividers, so they were left untouched to avoid changing play-loop UX.
- Reviewer and portfolio remain covered by the prior Cloud3 repair pass and
  should only receive regression smoke checks here.

## Deferred

- Legacy logo/avatar/advisor portrait imagery is still deferred unless it
  actively harms a demo-facing surface.
- Main play-loop action cards, renderer/prose behavior, long-session state, and
  backend runtime are Product/R&D-owned and intentionally out of this patch.
- Deeper trace/evidence information architecture can be revisited after Product
  V6/V7 integration if Play Tester finds reviewer utility gaps.

## Play Tester Checks

- Login desktop and 390px mobile: no horizontal overflow; dark shell remains.
- Play reviewer mode: runtime inspector and agent trace read as dark utility
  plates, not paper notes.
- Advisor drawer desktop and mobile: backdrop, panel, suggestion rows, text input,
  and oracle confirmation are readable and square/plate-like.
- Replay/ending route: no accidental pale paper/card-stack regression.
- Reviewer and portfolio quick regression: no overflow and no old-paper reversion.

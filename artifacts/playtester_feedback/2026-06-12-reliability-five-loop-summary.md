# Tiny Stories Reliability and Interaction Smoothness Five-Loop Summary

Date: 2026-06-12
Scope: product reliability and interaction smoothness for the normal Play loop.
Status: complete for the tested scope. There is no current product blocker from the five-loop sequence.

This artifact freezes the outcome of the five-loop reliability pass. It is not a new feature brief and should not reopen Play/Create/Home scope by itself. Future work should use the local QA fixtures below as regression checks, then change product code only when a new player-facing regression is reproduced.

## Executive Summary

The five-loop sequence closed the most brittle Play interaction paths:

- duplicate Play turn submits are guarded at the parent route level;
- retry failure recovery is visible, stable, and repeatable without damaging live provider paths;
- selected, pending, and resolved action states are rehearsable in a local fixture;
- long-history action discovery has a repeatable Back-to-move rehearsal path;
- normal player UI remains free of provider/model/API/schema/token/debug/trace/COT/raw JSON/fallback/deterministic wording in the tested surfaces.

The loops intentionally avoided live LLM spend after Loop 1 where fixture coverage was sufficient. Live/provider robustness remains a separate validation track from these UI reliability fixtures.

## Loop-by-Loop Evidence

| Loop | Commit / Snapshot | Problem Addressed | User-Visible Improvement | Fixture / Evidence Route | Playtest Verdict and Caveats |
| --- | --- | --- | --- | --- | --- |
| 1 | `8b6dfba fix: guard play turn resubmits` / `snapshot/tiny-stories-reliability-loop1-submit-guard-2026-06-10` | Rapid double-click and Enter repeat could risk duplicate Play turns. | Move submission now has a parent-level in-flight guard; pending state stays clear during live turn resolution. | Normal Play route, live in-app Browser validation. | Accepted. Play Tester verified rapid double-click and rapid Enter repeat did not duplicate turns; two live `advance_turn` events succeeded; 390px had no horizontal overflow. Retry-after-error was not exercised organically. |
| 2 | `79f053d fix: smooth play retry and action discovery` / `snapshot/tiny-stories-reliability-loop2-retry-action-discovery-2026-06-11` | Retry state and long-history action discovery were brittle and hard to validate safely. | Retry banner remains mounted and disabled while retrying; selected move is preserved. Compact/mobile Back-to-move cue helps players return to the action area after long history. | Dev one-shot failure harness; normal Play compact Back-to-move behavior. | Accepted. Play Tester confirmed controlled retry did not duplicate turns and mobile Back-to-move worked at 390px. Caveat: the retry harness was Vite-dev-only. |
| 3 | `44b43d2 fix: add repeatable play retry fixture` / `snapshot/tiny-stories-reliability-loop3-retry-fixture-2026-06-11` | Ongoing QA needed a repeatable failure/retry path that did not depend on Vite-only hash behavior or live provider failure. | Retry failure state can be rehearsed locally with clean, player-safe copy; banner label/body spacing is readable in DOM extraction. | `#/qa/play-retry` | Accepted. Play Tester passed retry fixture behavior and normal Play failure banner presentation. Caveat: exact 390px mobile acceptance was not proven in that run because in-app Browser attach failed and Chrome fallback could not reliably force 390px. |
| 4 | `f597f88 fix: rehearse play action flow states` / `snapshot/tiny-stories-reliability-loop4-action-flow-2026-06-11` | Normal selected -> pending -> resolved action flow needed repeatable fixture coverage. | QA can verify selected move, commit affordance, pending disable state, resolved next action set, hidden polite live-region status, and keyboard number+Enter behavior. | `#/qa/play-action` | Accepted. Play Tester passed the fixture and keyboard behavior; 390px mobile fixture passed. Caveat: in-app Browser pipe failed mid-run, so primary evidence used temporary Chrome/CDP. Loop 2 Back-to-move was not rechecked. |
| 5 | `cf95882 fix: rehearse long-history play action jump` / `snapshot/tiny-stories-reliability-loop5-long-history-action-jump-2026-06-11` | Loop 2 Back-to-move long-history behavior needed a repeatable QA path under an accepted route surface. | The existing Play action fixture now has a `long-history` scenario that uses real `ActionArea`, real Back-to-move behavior, and local selected -> pending -> resolved rehearsal without live calls. | `#/qa/play-action?scenario=long-history` | Accepted. Loop 5 Play Tester passed with no product blocker. Caveat: independent playtest could not produce a fresh 390px viewport because Browser viewport override failed; implementation run had same-route 390px evidence. No live/provider spend by design. |

## QA Route Inventory

### `#/qa/play-retry`

Proves:

- retry banner renders with player-safe copy;
- retry stays mounted and disabled while in flight;
- preserved move can retry safely;
- failure recovery is repeatable without live/provider damage.

Does not prove:

- live provider reliability;
- story quality;
- long-history action discovery.

### `#/qa/play-action`

Proves:

- ordinary action cards are selectable;
- commit/confirm affordance is visible;
- selected, pending, and resolved action states are observable through `data-play-action-state`;
- keyboard number+Enter rehearsal remains available;
- hidden polite status is present for state transitions.

Does not prove:

- retry failure recovery;
- long-history below-fold action discovery unless the `long-history` scenario is used;
- live turn quality or latency.

### `#/qa/play-action?scenario=long-history`

Proves:

- a long transcript can push the real action area below the fold;
- Back-to-move appears when the current action area is away from the viewport;
- clicking Back-to-move scrolls the real action area into view;
- action selection, confirmation, pending, and resolved states remain reachable after the jump;
- no horizontal overflow or technical wording appears in the tested local fixture.

Does not prove:

- live provider behavior;
- every possible story transcript length;
- reviewer evidence paths.

## Accepted Contracts to Preserve

- No duplicate Play turn submits, including rapid double-click and rapid Enter repeat.
- Retry banner remains mounted and disabled while retry is in flight.
- Retry preserves the selected move and recovers without leaking provider/debug/fallback wording.
- Selected, pending, and resolved action states remain observable and player-safe.
- Back-to-move remains available for long-history action discovery in compact/narrow layouts.
- Normal player UI must not expose provider/model/API/schema/token/debug/trace/COT/raw JSON/fallback/deterministic wording.
- 390px narrow layouts should have no horizontal overflow where validated.
- QA routes must stay local-only and must not be linked from the normal player surface.

## Validation Caveats and Future Harness Needs

- The in-app Browser had intermittent screenshot and viewport instability across the sequence. Some runs used Chrome/CDP or non-screenshot DOM evidence when in-app Browser was unavailable. Treat that as tooling caveat, not a product pass/fail by itself.
- Loop 5 ended with accepted playtest despite Browser viewport override instability. The implementation run captured same-route 390px evidence; independent playtest could not reproduce a fresh 390px viewport because of Browser tooling.
- These loops used fixture/local deterministic QA by design after live-provider damage was no longer necessary. They should not be presented as live LLM reliability evidence.
- Live/provider robustness, latency, and story quality remain separate validation tracks. Use live golden-path gates for those, not these local UI fixtures.
- Future harness work should improve first-party viewport/screenshot stability so 390px regressions can be captured consistently without external browser fallback.

## Recommended Next State

- Pause reliability loop feature work.
- Keep the recurring Play Tester available; do not archive it.
- Use `#/qa/play-retry`, `#/qa/play-action`, and `#/qa/play-action?scenario=long-history` as low-cost regression checks before product handoff.
- Reopen product code only if future playtests reproduce a real player-facing regression.
- Keep live LLM validation separate from this fixture suite and run it only when provider-backed behavior is being accepted.

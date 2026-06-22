# Play Page

`play-page.tsx` is the route/container for the active story session. It owns data loading, turn submission, session state, local error/retry state, advisor open/close state, and route callbacks. It should not accumulate new view markup unless the state genuinely belongs at route level.

## File Map

- `play-page.tsx`
  - Route/container orchestration: load story, advance turns, merge turn responses, fetch ending, wire advisor and share callbacks.
- `components/play-flow-panels.tsx`
  - View/helper module for run context, stage header, action area, resolving rows, and action-side local display helpers.
- `components/failed-action-recovery.ts`
  - Passive failed-action recovery copy helper: maps the last attempted action into retry-banner text/chips. `play-page.tsx` still owns retry state, failed action refs, and resubmission behavior.
- `components/story-beat.tsx`
  - Story beat display module: narrator/player beat rendering, latest-beat digest, outcome/intent receipts, leverage payoff, parallax scene banner, and beat intensity helper.
- `components/action-option-card.tsx`
  - Action option display module: forecast chips, collapsed forecast summaries, and selected option detail/readout sections. `ActionArea` still owns selection state, confirmation, motive editing, and submission.
- `components/free-action-prompts.tsx`
  - Free-action prompt display module: context banner, deterministic starter-line copy, and starter-row hooks. `ActionArea` still owns free-input text, motive editing, and submission.
- `components/leverage-summary.tsx`
  - Leverage summary readout module: empty summary, summary button, risk/target chips, and toggle label display. `ActionArea` still owns leverage card arming, reveal CTA, diary/motive editing, and submission.
- `components/run-context-objective.tsx`
  - Passive run-context objective readout: hidden objective and lens hint in compact/regular layouts. `RunContextPanel` still owns inventory item callbacks, status copy composition, and layout branching.
- `components/run-context-progress.tsx`
  - Passive run-context progress meter: turn progressbar label, value, and fill width. `RunContextPanel` still owns inventory item callbacks, status copy composition, and layout branching.
- `components/run-context-stage-label.ts`
  - Passive stage fallback label helper for run-context status copy. `RunContextPanel` still owns stage calculation, translation lookup, status copy composition, inventory item callbacks, and layout branching.
- `components/scene-read-strip.tsx`
  - Passive scene-read strip module: clock readouts, social-heat summary, leverage exposure count, and top NPC pulse labels. `ActionArea` only supplies current values and owns no behavior here.
- `components/selected-move-confirmation.tsx`
  - Selected move confirmation readout module: move number, ready label, target/room chip, and submit summary text. `ActionArea` still owns confirm buttons, motive editing, diary text, submission, and pending flow.
- `components/advisor-panel.tsx`
  - Advisor surface module: floating advisor button, sidechat drawer, advisor suggestions, transcript rendering, deep-read confirmation, and advisor-specific player hooks.
- `components/play-advisor-fixture.tsx`
  - Local QA route fixture for `#/qa/play-advisor`. Mounts the real advisor FAB/sidechat with deterministic local advisor responses for browser evidence.
- `components/ending-screen.tsx`
  - Ending payoff view, result-first action ordering, fallback recap, highlight reel, branch recap, and ending label display helpers.
- `components/play-ending-fixture.tsx`
  - Local QA route fixture for `#/qa/play-ending`. Mounts the real `EndingScreen` with deterministic ending data for browser evidence.
- `components/play-leverage-fixture.tsx`
  - Local QA route fixture for `#/qa/play-leverage`. Mounts the real `ActionArea` with deterministic leverage cards so leverage summary, card arming, and reveal-panel visibility can be browser-smoked without backend or live generation.
- `components/runtime-inspector.tsx`
  - Reviewer-only evaluation drawer and trace/evidence helpers. This owns persisted agent/LLM evidence rendering; normal Play surfaces import it only behind reviewer gating.
- `components/play-reviewer-evidence-fixture.tsx`
  - Local QA route fixture for `#/qa/play-reviewer-evidence`. Mounts the real `RuntimeInspector` with deterministic fresh-run and archived-proof evidence, plus a local-proof boundary note so application evidence is not mistaken for a public benchmark.
- `components/play-editorial-primitives.tsx`
  - Direction A Play primitive kit: `PlayShell`, `MoodPlate`, `StoryTimeline`, and `SceneSupportRail`. These primitives define the story-world mental model and should stay source-owned/local unless a future UI-kit migration is explicitly scoped.
- `play-styles.ts`
  - Play page inline style map.
- `play-types.ts`
  - Local Play types shared between the container and panel module.
- `play-option-label.ts`
  - Shared pure parser for intent-tagged option labels used by Play route summaries, story beats, action cards, and ending fallback recap.
- `hooks/use-compact-layout.ts`
  - Play-specific compact layout media-query hook.

## Accepted Behavior

- Selected move stays visible while resolving.
- Controls lock during turn submission; retry must not double-spend a turn.
- Normal players do not see provider/model/API/schema/debug/trace language.
- Reviewer trace/evidence appears only in reviewer mode.
- Ending payoff stays result-first and visible.
- `#/qa/play-leverage` exercises the real leverage `ActionArea` surface without backend or live generation.
- `#/qa/play-advisor` exercises the real advisor FAB/sidechat without backend or live generation.
- `#/qa/play-ending` exercises the real ending payoff surface without backend or live generation.
- `#/qa/play-reviewer-evidence` exercises the real reviewer evidence drawer without backend or live generation, including fresh and archived-proof cases. The page starts with a local-proof fixture note and points public claims back to repo/demo preflight.
- Mobile 390px must have no horizontal overflow and action/retry controls must remain reachable.
- Play is a story-world scene surface: Narrator/World, scene characters, and You. Story Butler is not the primary Play speaker; advisor behavior stays optional and secondary.

## Future Split Notes

`components/play-flow-panels.tsx` should not keep being split by default. After the passive readout/helper slices, the remaining local helpers and JSX are mostly behavior-adjacent wait boundaries:

- Header progress/navigation stays with `Header` until navigation ownership is explicitly redesigned; the progress copy, responsive header, cover styling, and back-home callback are one chrome unit.
- Run inventory controls stay in `RunContextPanel` because the item buttons own `onUseInventoryItem` wiring and the free-action focus affordance.
- Failed-action retry ownership stays in `play-page.tsx`: failed action refs, error/retry state, recovery banner retry callback, and resubmission routing should not move back into panel chrome.
- Resolving/pending ceremony stays in `play-flow-panels.tsx` until a behavior-level pending-state redesign is scoped; it owns elapsed-time state, live-region status, feedback timeline, and resolving commitment signals.
- Option tag display helpers stay with `ActionArea` because their copy and color semantics are coupled to option cards, selection, confirmation, and action forecasting.
- Resource focus/action helpers stay with the play route and `ActionArea` ownership boundary because they drive actor/resource/inventory focus, option matching, and action affordance copy.
- Keep the confirm button, motive button, diary preview/editor, free-input textarea, pending/resolved ceremony ownership, and leverage reveal behavior inside `ActionArea` until a behavior-level redesign is explicitly scoped. These pieces coordinate callbacks, local text state, disabled/pending guards, focus, and submit routing rather than pure display.
- Backend/provider/live LLM paths stay outside these display modules; normal Play chrome should remain player-safe and should not expose provider/model/API/schema/debug/trace language.

Do not split those in the same patch as a behavior change. Keep source guards and browser smoke around action submission, payoff focus, reviewer gating, and mobile action visibility.

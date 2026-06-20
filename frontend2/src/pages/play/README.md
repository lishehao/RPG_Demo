# Play Page

`play-page.tsx` is the route/container for the active story session. It owns data loading, turn submission, session state, local error/retry state, advisor open/close state, and route callbacks. It should not accumulate new view markup unless the state genuinely belongs at route level.

## File Map

- `play-page.tsx`
  - Route/container orchestration: load story, advance turns, merge turn responses, fetch ending, wire advisor and share callbacks.
- `components/play-flow-panels.tsx`
  - View/helper module for run context, stage header, action area, resolving rows, and action-side local display helpers.
- `components/story-beat.tsx`
  - Story beat display module: narrator/player beat rendering, latest-beat digest, outcome/intent receipts, leverage payoff, parallax scene banner, and beat intensity helper.
- `components/action-option-card.tsx`
  - Action option display module: forecast chips, collapsed forecast summaries, and selected option detail/readout sections. `ActionArea` still owns selection state, confirmation, motive editing, and submission.
- `components/free-action-prompts.tsx`
  - Free-action prompt display module: context banner, deterministic starter-line copy, and starter-row hooks. `ActionArea` still owns free-input text, motive editing, and submission.
- `components/leverage-summary.tsx`
  - Leverage summary readout module: empty summary, summary button, risk/target chips, and toggle label display. `ActionArea` still owns leverage card arming, reveal CTA, diary/motive editing, and submission.
- `components/advisor-panel.tsx`
  - Advisor surface module: floating advisor button, sidechat drawer, advisor suggestions, transcript rendering, deep-read confirmation, and advisor-specific player hooks.
- `components/play-advisor-fixture.tsx`
  - Local QA route fixture for `#/qa/play-advisor`. Mounts the real advisor FAB/sidechat with deterministic local advisor responses for browser evidence.
- `components/ending-screen.tsx`
  - Ending payoff view, result-first action ordering, fallback recap, highlight reel, branch recap, and ending label display helpers.
- `components/play-ending-fixture.tsx`
  - Local QA route fixture for `#/qa/play-ending`. Mounts the real `EndingScreen` with deterministic ending data for browser evidence.
- `components/runtime-inspector.tsx`
  - Reviewer-only evaluation drawer and trace/evidence helpers. This owns persisted agent/LLM evidence rendering; normal Play surfaces import it only behind reviewer gating.
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
- `#/qa/play-advisor` exercises the real advisor FAB/sidechat without backend or live generation.
- `#/qa/play-ending` exercises the real ending payoff surface without backend or live generation.
- Mobile 390px must have no horizontal overflow and action/retry controls must remain reachable.
- Play is a story-world scene surface: Narrator/World, scene characters, and You. Story Butler is not the primary Play speaker; advisor behavior stays optional and secondary.

## Future Split Notes

`components/play-flow-panels.tsx` remains the next split target. Safe boundaries are:

- Remaining `ActionArea` surfaces around leverage card rows and confirmation chrome, but only as separate display-only slices with action submission still owned by `ActionArea`.

Do not split those in the same patch as a behavior change. Keep source guards and browser smoke around action submission, payoff focus, reviewer gating, and mobile action visibility.

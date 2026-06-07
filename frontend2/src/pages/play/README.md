# Play Page

`play-page.tsx` is the route/container for the active story session. It owns data loading, turn submission, session state, local error/retry state, advisor open/close state, and route callbacks. It should not accumulate new view markup unless the state genuinely belongs at route level.

## File Map

- `play-page.tsx`
  - Route/container orchestration: load story, advance turns, merge turn responses, fetch ending, wire advisor and share callbacks.
- `components/play-flow-panels.tsx`
  - View/helper module for run context, reviewer runtime inspector, stage header, ending payoff, story beats, action area, resolving rows, advisor FAB/drawer, and local display helpers.
- `play-styles.ts`
  - Play page inline style map.
- `play-types.ts`
  - Local Play types shared between the container and panel module.
- `hooks/use-compact-layout.ts`
  - Play-specific compact layout media-query hook.

## Accepted Behavior

- Selected move stays visible while resolving.
- Controls lock during turn submission; retry must not double-spend a turn.
- Normal players do not see provider/model/API/schema/debug/trace language.
- Reviewer trace/evidence appears only in reviewer mode.
- Ending payoff stays result-first and visible.
- Mobile 390px must have no horizontal overflow and action/retry controls must remain reachable.

## Future Split Notes

`components/play-flow-panels.tsx` is intentionally the next split target. Safe boundaries are:

- `RuntimeInspector` and trace helpers.
- `EndingScreen`.
- `StoryBeat` plus beat receipt helpers.
- `ActionArea` plus action choice/free-input/leverage rows.
- `AdvisorFab` and `AdvisorSidechat`.

Do not split those in the same patch as a behavior change. Keep source guards and browser smoke around action submission, payoff focus, reviewer gating, and mobile action visibility.

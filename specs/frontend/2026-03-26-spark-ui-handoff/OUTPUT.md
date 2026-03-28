# Spark Create-Page UI Handoff Output

## Plan

- Keep the backend Spark contract as the only truth:
  - `POST /author/story-seeds/spark`
  - response `{ prompt_seed, language }`
- Finish create-page Spark interaction only:
  - on empty create page, Spark fills the textarea and does not auto-preview
  - when seed text or preview already exists, Spark asks for overwrite confirmation via `window.confirm`
  - cancel leaves current seed/preview unchanged
  - accept replaces seed and clears stale preview
- Do not expand Spark into a richer recommendation surface
- Do not touch author editor / cast review in this handoff pass

## Files Changed

- [specs/frontend/2026-03-26-spark-ui-handoff/OUTPUT.md](/Users/lishehao/Desktop/Project/RPG_Demo/specs/frontend/2026-03-26-spark-ui-handoff/OUTPUT.md)

No additional frontend code changes were required in this final verification pass.

Verified unchanged in scope:
- [frontend/src/api/contracts.ts](/Users/lishehao/Desktop/Project/RPG_Demo/frontend/src/api/contracts.ts)
- [frontend/src/api/route-map.ts](/Users/lishehao/Desktop/Project/RPG_Demo/frontend/src/api/route-map.ts)
- [frontend/src/api/http-client.ts](/Users/lishehao/Desktop/Project/RPG_Demo/frontend/src/api/http-client.ts)
- [frontend/src/features/authoring/create-story/model/use-create-story-flow.ts](/Users/lishehao/Desktop/Project/RPG_Demo/frontend/src/features/authoring/create-story/model/use-create-story-flow.ts)
- [frontend/src/widgets/authoring/create-story-workspace.tsx](/Users/lishehao/Desktop/Project/RPG_Demo/frontend/src/widgets/authoring/create-story-workspace.tsx)
- [frontend/src/pages/authoring/create-story-page.tsx](/Users/lishehao/Desktop/Project/RPG_Demo/frontend/src/pages/authoring/create-story-page.tsx)

## Validation

- `cd frontend && npm run check` ✅

## Manual Smoke

- Logged in with `author-spark@example.com`
- Opened `#/create-story`
- Empty state:
  - cleared the existing textarea content first
  - clicked `Spark a seed`
  - request hit `/author/story-seeds/spark`
  - button switched to `Sparking...`, and both `Spark` / `Generate Preview` were disabled while the request was in flight
  - textarea was filled with backend `prompt_seed`
  - previous create-page error copy cleared after the successful Spark response
  - Spark did not auto-trigger preview; preview pane remained `Awaiting Seed` / `No story drafted yet`
- Existing seed:
  - replaced textarea content with manual text
  - clicked `Spark another`
  - cancel on confirm kept the manual text unchanged
  - accept on confirm sent a second request to `/author/story-seeds/spark`
  - accept on confirm replaced the text with a new backend `prompt_seed`
  - Spark still did not auto-trigger preview

## Remaining Risks

- Manual browser smoke did not fully verify the “existing non-null preview gets cleared after confirmed Spark overwrite” case, because the current local preview path remains unstable/slow and was not reliable enough for a clean end-to-end confirmation in this pass.
- Spark still depends on backend availability and response latency; this pass does not add client-side fallback behavior.
- This handoff pass does not cover author editor / cast review or any richer Spark recommendation UI.

# Create Page: Korean Agent Chat

`create-page.tsx` owns the current Story Butler creation flow as a route/container. It holds state, API orchestration, and navigation callbacks. View-only pieces live beside it in local modules.

## File Map

- `create-page.tsx`
  - Route/container state, Story Brief and Generate API calls, guest session prep, transcript state, and navigation.
- `components/create-flow-panels.tsx`
  - View-only panels for busy stages, internal ledger primitives, the Brief settings read, and the Story Brief production slate.
- `create-options.ts`
  - Create constants and option metadata: seed examples, handoff timing, visibility options, budgets, difficulties, language options, tension options.
- `create-types.ts`
  - Create-local types shared by the container and view panels.
- `create-styles.ts`
  - Create page inline style map.
- `hooks/use-compact-layout.ts`
  - Create-specific compact layout media-query hook.

## Current Interaction Contract

1. Home `Write a new story` opens `#/create` without a login/name gate.
2. The page is a Korean webtoon Agent Chat, not a SaaS form.
3. The assistant asks for missing Story Brief slots and redirects unsafe/out-of-spec prompts while keeping pre-Brief chat natural.
4. When enough fields are present, the Story Brief is shaped automatically and appears as an assistant production slate inside the transcript.
5. `Generate and enter story` lives with the Brief slate.
6. Generate creates a template/session and routes to Play.

## Story-Shape Settings

Length, difficulty, story language, and tone are inferred through chat, not shown as a default settings grid.

Examples handled by `shared/lib/story-guide-settings.ts`, with loop orchestration in `shared/lib/story-guide-loop.ts`:

- `short`, `10 min`, `shorter` -> Short run / 8 turns.
- `15 minutes`, `one sitting` -> One sitting / 12 turns.
- `long`, `25 min`, `epic` -> Longer run / 20 turns.
- `hard mode`, `NPCs fight back`, `can I lose`, `gauntlet` -> High-stakes mode.
- `中文`, `make it Chinese`, `用英文写`, `English` -> story language.
- `backstage`, `disappearance`, `public scandal` -> high drama.
- `cozy`, `clues`, `small town` -> cozy mystery.

The inferred read is kept internal during ordinary collection so pre-Brief chat stays one-question-at-a-time. It is surfaced inside the final Brief slate before Generate. If a user correction changes story-shape settings after a Brief is ready, the flow must require reshaping before Generate.

## Visibility

Visibility is the only explicit fixed setting in the default Create flow.

- Default: Just me.
- User chat like `make it public` must not silently publish.
- The initial privacy checkpoint is compact and collapses before ordinary chat continues.
- A later chat privacy intent can reopen a compact confirmation, but visibility changes only after an explicit click.

## Backend Payload

The API payload still uses the backend contract fields:

- `turn_budget`
- `difficulty`
- `language`
- `desired_tension_profile`
- `visibility`
- optional `story_brief`

Only the source of story-shape values changed from visible form controls to the Story Butler inferred state.

## Live Generate UX

- Story Brief planning uses the live/hybrid text path when configured, with deterministic validation/fallback as a reliability layer.
- Opening/template generation may use the live provider path when configured.
- Live opening is capped in backend service code and can recover with a reliable opening while preserving player-safe copy.
- Normal player copy must not mention provider/model/API/schema/debug/fallback/deterministic.

## Future Split Notes

The current split intentionally keeps API orchestration in the container. Further extraction should target view-only pieces first, such as a dedicated `TranscriptLane`, `StoryComposer`, or `VisibilityControl`, without moving Story Brief or Generate state transitions in the same patch.

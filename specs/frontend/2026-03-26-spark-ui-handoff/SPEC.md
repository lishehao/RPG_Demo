# Spark Create-Page UI Handoff

## Purpose

Finish the frontend integration for Spark on the create page, using the backend contract that is already finalized.

This pass is frontend-only. It should not redesign Spark, add new backend fields, or broaden unrelated API contracts.

## Backend Truth

Backend route:
- `POST /author/story-seeds/spark`

Request:
- `{ "language": "en" | "zh" }`

Response:
- `{ "prompt_seed": string, "language": "en" | "zh" }`

These are already the canonical backend semantics and must be treated as fixed.

## Fixed Decisions

- Scope is frontend-only.
- Spark is not a new app mode.
- Spark only fills the seed textarea.
- Spark does not automatically:
  - generate preview
  - create author job
  - navigate away
- UI must not depend on:
  - `seed`
  - `spark_title`
  - `spark_rationale`
  - `/author/story-sparks`
- If the current textarea is non-empty or a preview already exists, clicking Spark must ask for overwrite confirmation before replacing content.
- Use the existing localized Spark copy already present in create-page surface copy, including the existing overwrite-confirm text.
- Use the project's current lightweight confirmation pattern (`window.confirm`) instead of inventing a new modal system in this pass.

## Required UI Behavior

### Create page

- Keep the existing Spark button on the create page.
- On click:
  1. If there is existing seed text or an existing preview, ask for confirmation using the existing localized overwrite-confirm copy.
  2. If the user cancels, do nothing.
  3. If the user confirms, call `createStorySpark({ language })`.
  4. On success:
     - write `response.prompt_seed` into the textarea
     - clear the old preview
     - clear stale error state
  5. Do not auto-trigger preview.

### Loading / error

- While Spark request is in flight:
  - disable the Spark button
  - keep existing loading label behavior
- On API failure:
  - surface the existing localized error handling path
  - do not clear the existing seed unless the request actually succeeds

## Files Allowed To Change

Only touch the minimal Spark path:
- `frontend/src/api/contracts.ts`
- `frontend/src/api/route-map.ts`
- `frontend/src/api/http-client.ts`
- `frontend/src/features/authoring/create-story/model/use-create-story-flow.ts`
- `frontend/src/widgets/authoring/create-story-workspace.tsx`
- `frontend/src/pages/authoring/create-story-page.tsx`

## Files Explicitly Out Of Scope

Do not modify:
- backend files
- author editor workspace / cast extraction review UI
- story detail / play pages
- unrelated API contracts
- copilot flows
- global modal infrastructure

## Acceptance Criteria

1. Spark calls `POST /author/story-seeds/spark`.
2. Spark reads `response.prompt_seed` and does not read `seed`, `spark_title`, or `spark_rationale`.
3. Existing non-empty seed or preview state triggers overwrite confirmation before replacement.
4. Confirmed Spark replaces the textarea value and clears preview.
5. Spark does not auto-preview.
6. Frontend typecheck passes.
7. No unrelated API/contract churn is introduced in this pass.

## Validation

- Run `cd frontend && npm run check`
- Manual browser smoke:
  - empty create page -> Spark fills textarea only
  - create page with existing seed -> Spark asks confirm
  - cancel confirm -> text and preview remain unchanged
  - accept confirm -> text updates and preview clears

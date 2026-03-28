# Author Loading Cast Pool UI Handoff

## Purpose

Finish the frontend integration for the new backend `cast_pool` contract on the author-loading surface.

This pass is frontend-only. It should not redesign preview, change backend contracts, or broaden unrelated author/play UI work.

## Backend Truth

Backend has added a new additive field on progress snapshot:

- `job.progress_snapshot.cast_pool`
- the same snapshot shape may also appear on result/status responses that already include `progress_snapshot`

Each `cast_pool` item is a concrete cast entry, not a sketch slot:

- `npc_id: string`
- `name: string`
- `role: string`
- `roster_character_id?: string | null`
- `roster_public_summary?: string | null`
- `portrait_url?: string | null`
- `portrait_variants?: { positive?: string | null, neutral?: string | null, negative?: string | null } | null`
- `template_version?: string | null`

Backend semantics are fixed:

- preview still remains a lightweight sketch
- `preview.cast_slots` may be sketch-only before `cast_ready`
- `cast_pool` becomes meaningful only once real cast exists, typically from:
  - `cast_ready`
  - `beat_plan_ready`
  - `route_ready`
  - `ending_ready`
  - `completed`

## Fixed Decisions

- Scope is frontend-only.
- Do not change backend files or response shapes.
- Do not force create-preview to render concrete portraits earlier than backend provides them.
- Use `cast_pool` only on the author-loading surface.
- Keep current preview “Cast Sketch” behavior unchanged in this pass.
- Keep author editor behavior unchanged in this pass; it already has its own `cast_view`.
- Portraits are pointer-based URLs only. UI must not assume image copies or uploads.

## Required UI Behavior

### Author loading

- On the author-loading page, if `progressSnapshot.cast_pool.length === 0`:
  - keep current loading UI unchanged
  - do not invent fake concrete cast cards

- If `progressSnapshot.cast_pool.length > 0`:
  - render a concrete cast section on the author-loading surface
  - each card should use:
    - `portrait_variants?.neutral ?? portrait_url` for the image
    - `name`
    - `role`
  - use `npc_id` as the stable key
  - if a portrait URL is absent, keep the existing image fallback behavior / placeholder styling

- The cast section should feel like a lightweight reveal of who the story has actually locked in, not like the final author editor review.
- The section should not replace the rotating loading-card spotlight; it should sit alongside the existing loading context.

### Copy / framing

- Add minimal supporting copy that makes the distinction clear:
  - this is the concrete cast that the running author job has now locked in
  - it is more specific than the earlier preview sketch
- Reuse existing editorial tone and current author-loading visual language.
- Do not introduce a new product term unless needed. `Cast Pool` is backend language, not necessarily UI copy.

## Recommended Placement

- Best insertion point: the right-side loading context area in `author-loading-dashboard`
- Recommended behavior:
  - keep the current story/theme summary block
  - append the concrete cast section below it when `cast_pool` is non-empty

This is preferred over replacing the spotlight card or over adding the section to create-preview.

## Files Allowed To Change

- `frontend/src/widgets/authoring/author-loading-dashboard.tsx`
- `frontend/src/app/styles.css`
- `frontend/src/shared/lib/author-ui-copy.ts`
- `frontend/src/api/contracts.ts`

Only touch `frontend/src/api/contracts.ts` if needed to align with the already-landed backend field. Do not broaden unrelated contracts.

## Files Explicitly Out Of Scope

- backend files
- create-story preview UI behavior
- author editor workspace / copilot review surface
- story detail / play pages
- global image infrastructure
- route map / HTTP client semantics

## Acceptance Criteria

1. Author-loading UI reads `progress_snapshot.cast_pool`.
2. No concrete cast cards are shown before `cast_pool` exists.
3. Once `cast_pool` exists, cards render stable `name`, `role`, and portrait pointer.
4. `npc_id` is used as the React key.
5. Existing loading-card spotlight remains intact.
6. Preview “Cast Sketch” behavior is unchanged.
7. Frontend typecheck passes.

## Validation

- Run `cd frontend && npm run check`
- Manual browser smoke:
  - start an author job
  - before `cast_ready`, loading page shows no concrete cast section
  - once cast is available, concrete cast cards appear
  - portraits use `portrait_variants.neutral ?? portrait_url`
  - completed author editor still works as before

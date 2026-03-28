Read this first:
- `/Users/lishehao/Desktop/Project/RPG_Demo/specs/frontend/2026-03-27-author-cast-pool-ui-handoff/SPEC.md`

Implement the frontend-only author-loading cast-pool integration described there.

Requirements:
- keep scope frontend-only
- treat backend `progress_snapshot.cast_pool` semantics as fixed truth
- do not redesign preview or author editor
- keep the loading-card spotlight intact
- render concrete cast cards only when `cast_pool` is present
- update this file when done:
  `/Users/lishehao/Desktop/Project/RPG_Demo/specs/frontend/2026-03-27-author-cast-pool-ui-handoff/OUTPUT.md`

Do not:
- modify backend files
- change public API routes
- move this feature into create-preview
- replace author editor `cast_view`
- broaden unrelated UI contracts or refactor unrelated pages

When finished:
- update `OUTPUT.md` with:
  - plan
  - files changed
  - validation run
  - manual smoke results
  - remaining risks
- reply in Chinese with a short summary

Read this first:
- `/Users/lishehao/Desktop/Project/RPG_Demo/specs/frontend/2026-03-26-spark-ui-handoff/SPEC.md`

Implement the Spark create-page frontend integration described there.

Requirements:
- keep scope frontend-only
- treat the backend Spark contract as fixed truth
- keep changes limited to the Spark create-page path
- use the existing localized Spark copy and existing lightweight confirmation pattern
- update this file when done:
  `/Users/lishehao/Desktop/Project/RPG_Demo/specs/frontend/2026-03-26-spark-ui-handoff/OUTPUT.md`

Do not:
- modify backend files
- add `seed`, `spark_title`, or `spark_rationale` back into frontend usage
- call `/author/story-sparks`
- redesign Spark into a richer recommendation surface
- broaden unrelated API contracts or refactor unrelated pages

When finished:
- update `OUTPUT.md` with:
  - plan
  - files changed
  - validation run
  - manual smoke results
  - remaining risks
- reply in Chinese with a short summary

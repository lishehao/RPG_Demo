# Runtime Status

## Current Active Runtime

- Backend directly calls Responses API through `ResponsesTransport`.
- Play rail uses one `PlayAgent` abstraction (`interpret_turn`, `render_resolved_turn`).
- Author rail uses one `AuthorAgent` abstraction for `generate_story_overview` + `plan_beat_scenes` + `generate_scene`.
- Responses task metadata (task name, developer prompt, channel, thinking, output mode) is centralized in `rpg_backend/llm/task_specs.py`.
- Responses cursor reuse uses `previous_response_id` persisted in `response_session_cursors`.
- Cursor reuse hard invariant: stored cursor model must equal current model, otherwise cursor is cleared before Responses call.
- Author scene generation expects semantic scene content only; deterministic backend assembly fills structural wiring (scene/move ids, enabled/always-available move lists, outcome ids, and standard per-scene progression exits).
- Current Play runtime modules are `RuntimeService`, `compiled_pack`, `step_engine`, `router` + `route_context`, `narration` + `narration_context`, plus `application/session_step/*` for request/commit/event handling.

## Determinism Boundaries

- Play outcome resolution and effect application remain deterministic in backend runtime.
- Play free-text routing and narration remain the only LLM-dependent parts of the play rail.
- Author `plan_beats/assemble_beat/beat_lint/normalize` remain deterministic.

## Observability Contract

- `llm_gateway_mode` / gateway aggregation use `responses` naming.
- stage naming is `interpret_turn` and `render_resolved_turn`.
- readiness health aggregates `backend` and `responses` services.

## Readiness

- `/ready` checks:
  - database check
  - responses config check
  - direct responses probe check (TTL-cached)

## Deployment/Dev Stack

- Active local stack: postgres + backend + frontend (`./scripts/dev_stack.sh up`).
- No worker startup in active scripts/manifests.

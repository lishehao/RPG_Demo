# Architecture

## System Shape

The backend is the only active server-side runtime component. It calls the upstream Responses API directly with `AsyncOpenAI.responses.create`.

Active abstractions:

- `ResponsesTransport`
- `PlayAgent`
- `AuthorAgent`
- `ResponseSessionStore` (Responses cursor persistence)

Removed from active path:

- internal LLM worker service
- worker client/gateway transport (removed from active runtime)
- legacy multi-chain play runtime paths

## Play Mode

Play Mode is single-agent at the LLM boundary and deterministic for resolution:

1. text input: `interpret_turn` (PlayAgent)
2. backend deterministic resolution/outcome/effects
3. `render_resolved_turn` (PlayAgent)

Button input skips interpretation and directly renders resolved output.

Current backend play runtime modules:

- `rpg_backend/runtime/service.py`
- `rpg_backend/runtime/compiled_pack.py`
- `rpg_backend/runtime/step_engine.py`
- `rpg_backend/runtime/router.py`
- `rpg_backend/runtime/route_context.py`
- `rpg_backend/runtime/narration.py`
- `rpg_backend/runtime/narration_context.py`
- `rpg_backend/application/session_step/*`

Responsibility split:

- `compiled_pack` builds read-only scene/move/beat/NPC indexes for each runtime call
- `route_context` builds route candidates and scene/state snapshots for `router`
- `router` maps free-text input onto an allowed move candidate
- deterministic runtime code resolves outcome/effects/next scene
- `narration_context` builds deterministic prompt slots and narration context payload
- `narration` renders player-facing text from already-resolved facts
- `application/session_step` wraps the runtime with request validation, idempotency, CAS commit, and observability events

Public API shape is unchanged. Admin/dev timeline fields are single-agent:

- `agent_model`
- `agent_mode` (`responses`)
- `response_id` (per call)
- `reasoning_summary` (debug only)

## Author Mode

Author Mode keeps LangGraph topology:

- `generate_story_overview`
- `plan_beats`
- `plan_beat_scenes`
- `generate_scene`
- `assemble_beat`
- `beat_lint`
- `assemble_story_pack`
- `normalize_story_pack`
- `final_lint`
- `review_ready | workflow_failed`

LLM nodes (`generate_story_overview`, `plan_beat_scenes`, `generate_scene`) all use `AuthorAgent` + Responses transport.

`generate_scene` is semantic-first:

- it returns scene seed, present NPCs, local move intent/flavor, and consequence flavor
- it does not own final runtime wiring such as move ids, `enabled_moves`, fixed global move attachment, outcome ids, or standard scene progression exits
- deterministic backend assembly (`assemble_beat`) owns that repetitive structure

Deterministic nodes remain deterministic:

- `plan_beats`
- `assemble_beat`
- `lint`
- `normalize`

`final_lint` failure still routes directly to `workflow_failed` (no repair branch).

## Cursor Persistence

Responses cursor reuse is persisted in table `response_session_cursors`:

- key: `(scope_type, scope_id, channel)`
- fields: `model`, `previous_response_id`, `updated_at`

Channels:

- Play: `play_agent`
- Author: `author_overview`, `author_beat_plan`, `author_scene:<beat_id>`

Cursor invalidation behavior:

- on invalid/expired cursor error, clear stored cursor
- retry once without `previous_response_id`
- save latest `response.id` on success
- if stored cursor model mismatches the current model, clear the cursor before reuse

## Config Contract

Only active LLM config:

- `APP_RESPONSES_BASE_URL`
- `APP_RESPONSES_API_KEY`
- `APP_RESPONSES_MODEL`
- `APP_RESPONSES_TIMEOUT_SECONDS` (`20.0`)
- `APP_RESPONSES_ENABLE_THINKING_PLAY`
- `APP_RESPONSES_ENABLE_THINKING_AUTHOR_OVERVIEW`
- `APP_RESPONSES_ENABLE_THINKING_AUTHOR_BEAT_PLAN`
- `APP_RESPONSES_ENABLE_THINKING_AUTHOR_SCENE`
- `APP_RESPONSES_ENABLE_THINKING_STORY_QUALITY_JUDGE`

No active multi-model route/narration/generator split.

## Observability

Gateway naming is standardized to `responses`.

- LLM call health by gateway mode: `responses | unknown`
- readiness health aggregation: `backend` + `responses`
- runtime stages: `interpret_turn`, `render_resolved_turn`

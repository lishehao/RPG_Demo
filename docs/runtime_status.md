# Runtime Status Matrix

This file maps `docs/architecture.md` sections to current implementation status.

## Implemented
- Accept-All runtime loop (Pass A + Pass B) with deterministic outcome resolution.
- `fail_forward` mandatory linter validation.
- Global fallback routing with `global.help_me_progress`/`global.clarify`.
- Session idempotency by `client_action_id` replay.
- Story draft/publish/get APIs.
- Session create/get/step APIs.
- Sample story pack and canary tests.

## Placeholder
- `POST /stories/generate` exists as a placeholder endpoint and returns `501`.
- Auto-repair service exists as a placeholder API (`app/domain/repair.py`) and does not mutate packs.
- OpenAI LLM provider is a placeholder and not enabled in offline-first mode.

## Planned
- Full one-click story generation pipeline.
- Real auto-repair loops with bounded attempts.
- Stronger narration leak guards and telemetry expansion.

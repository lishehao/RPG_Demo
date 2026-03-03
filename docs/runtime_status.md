# Runtime Status Matrix

This file maps `docs/architecture.md` sections to current implementation status.

## Implemented
- OpenAI strict runtime loop (Pass A + Pass B) with deterministic outcome resolution.
- `fail_forward` mandatory linter validation.
- OpenAI-only routing policy:
  - `openai`: quality-first failfast on route error/invalid move/low confidence
- Text routing convergence:
  - `global.help_me_progress` is excluded from non-help text routing candidates
  - explicit help/stuck intent can still route to `global.help_me_progress`
- Story DSL hard break:
  - `Move.strategy_style` required
  - `StoryPack.npc_profiles[{name, red_line}]` required
  - scene-level strategy triangle coverage is a linter hard error
- Fixed delayed-consequence tracks in runtime state:
  - `public_trust`, `resource_stress`, `coordination_noise`
  - late-beat pressure recoil with cooldown
- NPC stance visibility:
  - runtime tracks `npc_trust::<name>`
  - narration periodically emits stance updates (support/opposition/red-line pressure)
- Prompt authoring strict pipeline:
  - two-stage compile (`outline -> full spec`)
  - max total 3 compile calls
  - strict failure codes (`prompt_outline_invalid`, `prompt_spec_invalid`)
- Session idempotency by `client_action_id` replay.
- Story draft/publish/get APIs.
- Session create/get/step APIs.
- Sample story pack and canary tests.
- Deterministic story generator (`/stories/generate`) with lint + bounded regenerate attempts.
- Eval diagnostics extended (non-hard-gate in phase A):
  - `global_help_route_rate`
  - `non_global_text_route_rate`
  - `strategy_triangle_coverage_rate`
  - `pressure_recoil_trigger_rate`
  - `npc_stance_mentions_per_run_avg`
  - `duplicate_beat_title_run_count`
  - `banned_move_hit_count`

## Planned
- Promote route-convergence KPI to hard gate after repeated stable runs:
  - target `global_help_route_rate <= 0.25`
- Threshold/config externalization for pressure recoil (currently hardcoded runtime constants).

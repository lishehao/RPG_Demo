# Story Architecture v3 (Source of Truth)

This document is the canonical specification for the interactive narrative runtime and story generation model.

## Goals
- 8-12 minutes per playthrough.
- 14-16 turns as runtime pacing target.
- Input handling policy:
  - `openai` provider uses quality-first failfast for route/narration failures.

## Core Structure
Story packs follow:
- Beat -> Scene -> Move -> Outcome

## Beat
- 3-5 beats per story.
- Required fields:
  - `id`
  - `title`
  - `step_budget` (recommended 3-4)
  - `required_events`
  - `npc_quota`
  - `entry_scene_id`
- Aggregate `step_budget` should align with 14-16 turns.

## Scene
- Each scene belongs to one beat.
- `scene_seed` is short structured context (situation, objective, conflict), not long prose.
- `present_npcs`: typically 1-2 in-scene NPCs.
- `enabled_moves`: 4-5 visible moves, never above 6.
- `always_available_moves`: 2-3 global moves; must include at least two from:
  - `global.clarify`
  - `global.look`
  - `global.help_me_progress`
- `enabled_moves` must cover all strategy styles (excluding `global.*`):
  - `fast_dirty`
  - `steady_slow`
  - `political_safe_resource_heavy`
- Branches should reconverge within 1-2 steps.

## Move
- Move is an executable action interface, not a static choice label.
- Move must include `strategy_style`.
- Free-text routes to moves through `intents` and `synonyms`.
- Move supports argument schema via `args_schema`.
- Move has deterministic `resolution_policy`.
- Every move must include:
  - `success`
  - `fail_forward`
- `partial` is recommended.

## NPC Profiles
- StoryPack must include `npc_profiles`.
- Each profile includes:
  - `name`
  - `red_line` (non-negotiable constraint)
- `npc_profiles` and `npcs` must match exactly.

## Outcome
- `result`: `success | partial | fail_forward`
- `effects`: deterministic state deltas.
- `next_scene_id`: optional and may reconverge.
- `narration_slots`:
  - `npc_reaction`
  - `world_shift`
  - `clue_delta`
  - `cost_delta`
  - `next_hook`
- Every step must produce at least one perceivable change.
- `fail_forward` must never stall; it must advance progression (progress delta or event trigger).

## Runtime Two-Pass
### Pass A: Intent Routing
- Button: direct move invocation.
- Free-text: provider route result with `move_id`, `args`, `confidence`, `interpreted_intent`.
- OpenAI-only handling:
  - low confidence/invalid move/route exception failfasts the step.
  - non-help text excludes `global.help_me_progress` from candidate moves.
  - help/stuck intent can re-enable `global.help_me_progress`.

### Pass B: Outcome Resolution
- Deterministic outcome selection.
- Preconditions choose outcome; they never reject execution.
- If success/partial preconditions fail, select fail_forward.
- Apply effects, update progress, transition scene.
- Runtime state includes fixed pressure tracks:
  - `public_trust`
  - `resource_stress`
  - `coordination_noise`
- Final two beats execute pressure-recoil checks; debt can return as extra cost/consequence.
- Runtime tracks `npc_trust::<name>` and derives stance (`support|contested|oppose`) from red-line conflicts.

### Narration
- Provider only renders text from slots.
- Enforce `Echo + Commit + Hook` shape.
- OpenAI-only handling:
  - narration failure failfasts the step.
- Never leak internal fields, IDs, or debug markers.
- Periodically surface stance state in text: who supports, who opposes, whose red line is hit.

## Story Generator Pipeline
Generation flow:
1. Seed/Prompt -> BeatPlan (prompt mode uses strict two-stage compile: outline -> full spec)
2. BeatPlan -> Scenes
3. Scenes -> Moves/Outcomes with strategy triangle + style-linked outcome cost profiles
4. Lint
5. Regenerate whole pack when lint fails (max 3 regenerates / 4 total attempts)
6. Return draft pack, optional publish

## Quality Gates
- Linter must validate schema/reference/invariants.
- Every move has fail_forward.
- Every scene has global moves.
- Every scene has full strategy triangle coverage.
- Duplicate beat titles fail lint.
- Banned moves (for example `inspect_relic`) fail lint.
- Reachability from entry scenes.
- At least one terminal path.
- Pacing compatible with 14-16 turns.

## Evaluation Diagnostics (Phase A: observe/alert)
- `global_help_route_rate`
- `non_global_text_route_rate`
- `strategy_triangle_coverage_rate`
- `pressure_recoil_trigger_rate`
- `npc_stance_mentions_per_run_avg`

These are tracked now as diagnostics and can be promoted to hard gate after stable baselines.

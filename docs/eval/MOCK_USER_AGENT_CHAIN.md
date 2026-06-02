# Narrative Mock-User Agent Chain

This is the local/offline-first agent evaluation chain for Tiny Stories'
product-facing `/narrative/*` runtime. It turns a playthrough into an
inspectable artifact:

```text
observe -> update_memory -> choose_action -> play_turn -> collect_events
-> collect_judges -> judge_trajectory -> summarize_episode
```

The goal is not to claim a production autonomous agent framework. The goal is
to make the narrative runtime auditable: a configurable mock player can play a
story episode, the runtime archives its internal orchestration trace, and the
eval tool records whether each turn and the whole episode behaved coherently.

## External Patterns Used

The implementation adapts mature patterns without importing heavy agent
frameworks:

- OpenAI Agents SDK tracing frames an agent run as a workflow trace composed of
  spans for model calls, tool calls, guardrails, and custom events. This repo
  mirrors that idea locally with `loop_event`, `turn`, `trajectory_judge`, and
  `summary` JSONL records instead of exporting to a remote tracing backend.
  Source: <https://openai.github.io/openai-agents-python/tracing/>
- OpenAI Evals treats evaluation as a repeatable pipeline with datasets,
  graders, and auditable results. This repo keeps deterministic judges first
  and records artifacts before any optional LLM judge is considered.
  Source: <https://platform.openai.com/docs/guides/evals>
- LangGraph memory/persistence distinguishes short-term thread state,
  checkpoints, and longer-term memory stores. This repo only needs
  episode-scoped short-term memory, so `EpisodeMemory` is a compact JSON model
  updated once per turn instead of a graph/checkpointer dependency.
  Sources: <https://docs.langchain.com/oss/python/langgraph/memory>,
  <https://docs.langchain.com/oss/python/langgraph/persistence>
- ReAct-style loops combine observation and action. The mock user follows the
  same shape with deterministic local policies: observe the current story,
  update memory, choose an action, call the runtime, inspect the result, repeat.
  Source: <https://arxiv.org/abs/2210.03629>

## Architecture Layers

Backend runtime:

- `AgentPlan` records the deterministic director/workflow decision for a
  narrator turn.
- `narrative_agent_events` archives `agent_plan`, `step_judge`, and
  `contract_judge` events by session and narrator ordinal.
- `StepJudgeResult` checks whether the narrator turn honored the pre-turn
  agent plan.
- `ContractJudgeResult` checks runtime shape, ids, hidden-info leakage, and
  basic state-delta contract issues.
- Public replay and normal player paths do not expose trace payloads. Trace is
  only returned when reviewer/admin access allows `agent_trace=true`.

Eval tool:

- `tools.rpg_eval.narrative_mock_user` runs a mock user episode.
- `MockUserConfig` controls role, policy, turn budget, freeform rate, leverage
  policy, objective, risk tolerance, seed, reviewer identity, base URL, and
  output paths.
- `EpisodeMemory` stores compressed per-episode state, not full history.
- `AgentLoopEvent` records the named tool/action loop.
- `TrajectoryJudgeResult` evaluates the full episode trace.

Reviewer surface:

- `RuntimeInspector` shows compact Agent Trace fields only when the frontend
  has reviewer/admin trace access.
- It intentionally shows safe summaries: stage/pressure, active NPC intent,
  twist flag, memory counts, and source/version. It does not show hidden
  objectives or leverage text.

## Config Schema

`MockUserConfig` supports:

- `mode`: `fixture` for offline in-process runs, `live` for an existing backend.
- `session_id` or `template_id`: use an existing session or start from a
  template.
- `role_id` / `role_selection`: explicit role, first available, seeded random,
  or protagonist-like.
- `policy`: `option_selector`, `leverage_seeker`, `conflict_escalator`,
  `cautious_negotiator`, `goal_directed`, `random_seeded`, `regression_script`.
- `turn_budget`: maximum mock-user turns.
- `freeform_rate`: deterministic chance of using freeform input rather than a
  preset option.
- `leverage_policy`: `never`, `opportunistic`, `target_active_npc`,
  `random_valid`, or `scripted`.
- `objective`: short target used by the goal-directed policy and memory
  progress checks.
- `risk_tolerance`: low, medium, or high.
- `seed`: reproducibility for role and action choices.
- `reviewer_username`: used by live HTTP mode to request reviewer trace.
- `trace_output_path` and `summary_output_path`.

## Memory Model

`EpisodeMemory` is a compact, sanitized JSON model. It records:

- recent observations, capped to the latest few narrator summaries;
- NPC pulse trends by id and observed NPC ids;
- inventory event counts/references without dumping full hidden state;
- played leverage card id, target NPC id, and action, not leverage text;
- selected option handles;
- unresolved goal/objective progress;
- repeated Step/Contract violation counts;
- policy decision counts and pressure signal count.

The memory model is intentionally deterministic and bounded. It is updated in
the hot path after observation and again after runtime/judge collection, so
each decision can cite a compact memory state without rereading full history.

## Policy and Tool Loop

The policy layer uses small deterministic classes behind a `score_option`
interface. The trace records the policy explanation in `decision_reason`, for
example keyword hits, seeded choice, risk bias, or objective-term hits.

The loop emits named steps:

- `observe`: summarize current visible narrator beat and options.
- `update_memory`: compress current observation into `EpisodeMemory`.
- `choose_action`: select preset/freeform action and optional leverage card.
- `play_turn`: call the narrative runtime through TestClient, service adapter,
  or live HTTP adapter.
- `collect_events`: refresh story history and reviewer trace events.
- `collect_judges`: collect Step/Contract judge status and violation codes.
- `judge_trajectory`: run episode-level checks.
- `summarize_episode`: produce reviewer/eval summary.

## Judge Pipeline

Per-turn judges are archived by the runtime:

- Step Judge: active NPC intent presence, leverage impact, twist/high-pressure
  consequence, and inventory-delta sanity.
- Contract Judge: narrator shape/options, id references, hidden-info leak guard,
  leverage ownership, inventory no-op placeholders, and stage no-op contract.

Trajectory Judge is eval-owned and stored in the episode artifact. It checks:

- episode/turn-budget coherence;
- unique narrator ordinals and trace refresh coherence;
- agent plan visibility and stage progression;
- role coherence;
- objective progress;
- NPC airtime/intent visibility;
- leverage policy exercise and payoff continuity;
- repeated Step/Contract violation codes;
- low-divergence/no-impact episodes;
- ending/stop-condition alignment when available.

It returns `pass`, `warn`, or `fail`, plus check codes, evidence pointers, and a
compact summary.

## Trace Artifact Schema

`--output` writes JSONL records:

- `loop_event`: one named action/tool step.
- `turn`: observation summary, memory before/after, selected action/freeform,
  sanitized leverage summary, runtime output summary, AgentPlan summary,
  Step Judge status/codes, Contract Judge status/codes.
- `trajectory_judge`: versioned episode-level judge result.
- `summary`: turn counts, pass/warn/fail counts, repeated violations,
  trajectory status, and reviewer recommendations.

`--summary-output` writes a compact JSON summary with the final
`TrajectoryJudgeResult` and compressed `EpisodeMemory`.

## Local CLI

Offline fixture run, no live backend and no LLM key:

```bash
python -m tools.rpg_eval.narrative_mock_user \
  --mode fixture \
  --policy leverage_seeker \
  --leverage-policy opportunistic \
  --turns 2 \
  --seed 7 \
  --output artifacts/mock_user_episode.jsonl \
  --summary-output artifacts/mock_user_episode_summary.json
```

Live backend run against an existing session:

```bash
python -m tools.rpg_eval.narrative_mock_user \
  --mode live \
  --base-url http://127.0.0.1:8000 \
  --session <session_id> \
  --policy conflict_escalator \
  --leverage-policy target_active_npc \
  --turns 6 \
  --output artifacts/mock_user_episode.jsonl \
  --summary-output artifacts/mock_user_episode_summary.json
```

Live mode may invoke the existing narrative runtime LLM when advancing turns.
The mock-user policy and judges themselves do not call an LLM.

## Privacy and Cost Boundaries

- Public replay does not expose `agent_events` or `agent_plan`.
- Ordinary player responses do not include agent trace by default.
- Reviewer/admin trace access is explicit and backend-gated.
- Trace artifacts store leverage card ids, targets, and actions, not full
  hidden leverage text.
- The default fixture path is offline and deterministic.
- Optional live runs can incur the existing narrative runtime LLM cost; no live
  LLM judge or per-NPC LLM agent is enabled by default.

## Implemented vs Future Optional

Implemented:

- per-turn AgentPlan archive;
- Step/Contract judges archived per narrator turn;
- reviewer/admin trace gate and compact RuntimeInspector surface;
- deterministic mock user policies;
- bounded EpisodeMemory;
- explicit loop events;
- Trajectory Judge;
- offline fixture CLI and live HTTP mode;
- JSONL and summary JSON artifacts.

Future optional:

- offline LLM policy extension behind an explicit flag;
- batched cast-council/multi-NPC simulation;
- trajectory results persisted into a separate eval run table;
- richer reviewer UI for trajectory artifacts;
- integration with external tracing backends.

## Admissions-Safe Positioning

Tiny Stories can be described as an inspectable AI narrative runtime with a
local player-agent evaluation chain. The project demonstrates typed contracts,
deterministic orchestration, compact memory, traceability, per-turn judges, and
trajectory evaluation. It should not be framed as a validated consumer product,
retention-proven game, or full production autonomous multi-agent framework.

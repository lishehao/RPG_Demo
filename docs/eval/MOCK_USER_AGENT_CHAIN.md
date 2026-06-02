# Narrative Mock-User Agent Chain

This is the live-first agent evaluation chain for Tiny Stories'
product-facing `/narrative/*` runtime. In normal reviewer/demo use, the mock
player calls the running backend and advances the same live narrative runtime
that users see. A deterministic fixture remains for CI and local dry-runs, but
it is not the primary evaluation story. The chain turns a playthrough into an
inspectable artifact:

```text
gold case -> observe -> update_memory -> choose_action -> play_turn
-> collect_events -> collect_judges -> judge_trajectory -> llm_judge
-> report_gates
```

The goal is not to claim a production autonomous agent framework. The goal is
to make the live narrative runtime auditable: a configurable mock player can
play a story episode through the real API, the runtime archives its internal
orchestration trace, deterministic judges produce structured evidence, and the
LLM judge evaluates the run against a gold-case rubric.

## External Patterns Used

The implementation adapts mature patterns without importing heavy agent
frameworks:

- OpenAI Agents SDK tracing frames an agent run as a workflow trace composed of
  spans for model calls, tool calls, guardrails, and custom events. This repo
  mirrors that idea locally with `loop_event`, `turn`, `trajectory_judge`, and
  `summary` JSONL records instead of exporting to a remote tracing backend.
  Source: <https://openai.github.io/openai-agents-python/tracing/>
- OpenAI Evals treats evaluation as a repeatable pipeline with datasets,
  graders, and auditable results. This repo uses gold cases, deterministic
  first-pass judges, a structured LLM judge, and report gates.
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

Gateway/model truth:

- Current repo configuration resolves generic, author, and play gateway settings
  to `https://api.deepseek.com` with model `deepseek-v4-flash`.
- `/narrative/*` uses `get_narrative_gateway()`, which reads
  `resolved_play_responses_base_url()`, `resolved_play_responses_api_key()`, and
  `resolved_play_responses_model()`. In the current configuration, narrative
  play therefore uses the same DeepSeek V4 Flash gateway path as play.
- The transport is OpenAI-compatible `chat/completions`; for DeepSeek models the
  request path explicitly disables thinking, matching the Flash/no-thinking
  runtime expectation.

Eval tool:

- `tools.rpg_eval.narrative_mock_user` runs a mock user episode.
- `tools.rpg_eval.narrative_llm_judge` runs the gold-set evaluation loop:
  gold case -> mock user -> runtime trace -> deterministic judges -> LLM judge
  -> report gates.
- `tools/rpg_eval/gold_sets/narrative_agent_smoke.json` is the CI-safe smoke
  gold set.
- `MockUserConfig` controls role, policy, turn budget, freeform rate, leverage
  policy, objective, risk tolerance, seed, reviewer identity, base URL, and
  output paths.
- `EpisodeMemory` stores compressed per-episode state, not full history.
- `AgentLoopEvent` records the named tool/action loop.
- `TrajectoryJudgeResult` evaluates the full episode trace.
- `LLMJudgeResult` evaluates the whole evidence package against gold-case
  expectations and rubric weights.

Reviewer surface:

- `RuntimeInspector` shows compact Agent Trace fields only when the frontend
  has reviewer/admin trace access.
- It intentionally shows safe summaries: stage/pressure, active NPC intent,
  twist flag, memory counts, and source/version. It does not show hidden
  objectives or leverage text.

## Config Schema

Gold cases define:

- `case_id` and `name`;
- runtime source: deterministic fixture, existing live `session_id`, or live
  `template_id`;
- mock-user config: role, policy, objective, turn budget, leverage policy, risk
  tolerance, seed;
- expected properties and invariants: minimum turns, stage progression,
  leverage use/payoff, hidden-info safety, allowed/forbidden violation codes,
  trajectory/ending expectations;
- judge rubric weights and pass/warn thresholds;
- run label: `ci_stub` or `live_gateway`.

`MockUserConfig` supports:

- `mode`: `live` for the real evaluator path against an existing backend,
  `fixture` only for CI/test dry-runs. The CLI default is `live`.
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

LLM Judge consumes the full evidence package:

- gold case expectations and rubric;
- mock-user config and objective;
- per-turn action decisions, memory summaries, runtime summaries, AgentPlan
  summaries, Step Judge status/codes, and Contract Judge status/codes;
- full `TrajectoryJudgeResult`;
- hidden-info and forbidden-code indicators.

It returns strict `LLMJudgeResult` JSON with schema/version/source/model/gateway,
status, rubric scores, violation codes, expectation matches/misses, reviewer
summary, confidence, and deterministic-vs-LLM disagreement. Live LLM judging
uses the same configured narrative/play gateway path; CI uses a fake judge that
still exercises the strict parser and report shape.

## Trajectory Persistence Boundary

`trajectory_judge` and `llm_judge` are eval-artifact persisted today. That means
the evaluator writes them to JSONL/JSON report artifacts, but the product
runtime does not persist them into `narrative_agent_events`, SQLite session
history, or a public API response.

This is intentional for the current PR. Step and Contract judges are product
turn events because they are generated by `NarrativeService.advance` immediately
after one narrator turn. Trajectory Judge is generated by the external eval
runner after it has collected a whole episode, memory snapshots, policy
decisions, and per-turn judge results. LLM Judge is also evaluator-owned because
it evaluates the run against a gold rubric. Persisting either into
`narrative_agent_events` would require a trusted evaluator write API or direct
repository access from the eval tool, and would blur product runtime events with
evaluator-owned run artifacts.

If reviewer reporting needs database-backed persistence next, the better path
is an eval run registry rather than a product turn event: persist
`run_id`, `session_id`, git sha, gateway config label, policy config, trace path,
summary path, final `TrajectoryJudgeResult`, and final `LLMJudgeResult` in an
eval table or manifest directory. The current PR makes those artifacts
first-class on disk: the report points to per-case trace, summary, LLM input,
and LLM result files.

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

`tools.rpg_eval.narrative_llm_judge --output` writes a run report:

- gold set id/path and gateway snapshot;
- per-case trace, summary, LLM input, and LLM result paths;
- deterministic Step/Contract/Trajectory summary;
- LLM Judge result and disagreement flag;
- aggregate pass/warn/fail counts, repeated violation codes, and report gates.

## Local CLI

CI-safe gold-set smoke, no live backend and no external LLM judge:

```bash
python -m tools.rpg_eval.narrative_llm_judge \
  --gold-set tools/rpg_eval/gold_sets/narrative_agent_smoke.json \
  --mode fixture \
  --llm-judge fake \
  --output artifacts/narrative_llm_judge_report.json
```

Live DeepSeek-backed gold-set run against an existing session. This is the real
evaluation path when the backend is running and live LLM cost is approved:

```bash
python -m tools.rpg_eval.narrative_llm_judge \
  --gold-set <live_gold_set.json> \
  --mode live \
  --llm-judge live \
  --allow-live-llm \
  --base-url http://127.0.0.1:8000 \
  --session <session_id> \
  --output artifacts/narrative_llm_judge_report.json
```

Live DeepSeek-backed run against an existing session. This is the real
reviewer/demo evaluation path and may call the configured narrative runtime LLM
when turns advance:

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

CI/test dry-run, no live backend and no LLM key:

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

The mock-user policy and deterministic judges themselves do not call an LLM. In
live mode, the existing narrative runtime can call DeepSeek V4 Flash through the
configured gateway when creating or advancing story turns, and `--llm-judge
live` can call the same gateway for the LLM-as-judge layer.

## Privacy and Cost Boundaries

- Public replay does not expose `agent_events` or `agent_plan`.
- Ordinary player responses do not include agent trace by default.
- Reviewer/admin trace access is explicit and backend-gated.
- Trace artifacts store leverage card ids, targets, and actions, not full
  hidden leverage text.
- The fixture path is offline and deterministic for CI.
- Live runs can incur the existing narrative runtime LLM cost through DeepSeek
  V4 Flash.
- Live LLM-as-judge calls require explicit `--llm-judge live
  --allow-live-llm`.
- Per-NPC LLM agents are not enabled by default.

## Mock User Ability Assessment

What it can do well:

- It behaves like a real API-level player: it observes visible story state,
  chooses an option or freeform action, optionally plays a leverage card, calls
  `/narrative/*`, refreshes trace events, and repeats.
- It has bounded memory, so decisions can depend on recent observations, NPC
  pulse shifts, used leverage cards, repeated judge failures, and objective
  progress rather than only the current option list.
- It produces auditable rationale for deterministic choices through
  `decision_reason`, and the artifact records the loop step that produced each
  decision.
- It is useful for regression and reviewer readiness: repeated judge failures,
  missing trace, duplicate leverage use, low-divergence turns, and flat
  trajectories become visible without reading the full transcript.
- It now works as the runner inside a gold-set evaluation loop, not only as a
  demo script.

Where it is still weak:

- The policies are deterministic scorers, not long-horizon planners. They can
  prefer escalation, caution, leverage, or objective terms, but they do not build
  a multi-turn plan and revise it after failure.
- Memory is compressed state, not reflective memory. It tracks facts and counts,
  but it does not synthesize new hypotheses or strategy notes.
- There is no retry/self-correction loop after a bad action, failed judge, or
  unexpected runtime output.
- The tool abstraction is visible in the trace, but the action set is still
  narrow: observe, choose, advance, collect, judge. It does not yet search,
  compare alternate actions, simulate counterfactuals, or call an LLM policy.
- It resembles a small deterministic local agent, not a production autonomous
  multi-agent system.

How to measure improvement:

- Trajectory pass/warn/fail rate across templates and roles.
- Objective-progress rate and ending alignment for goal-directed policies.
- Reduction in repeated Step/Contract violation codes.
- Leverage payoff continuity: card played -> target pulse/pressure/inventory
  effect -> later memory effect.
- Divergence and impact: fewer flat/no-impact episodes, more distinct stage and
  NPC-state movement.
- Ending quality signals from the runtime ending/highlight outputs, when
  available.

## Implemented vs Future Optional

Implemented:

- per-turn AgentPlan archive;
- Step/Contract judges archived per narrator turn;
- reviewer/admin trace gate and compact RuntimeInspector surface;
- gold set schema and CI-safe smoke catalog;
- deterministic mock user policies;
- bounded EpisodeMemory;
- explicit loop events;
- Trajectory Judge;
- LLM Judge input package, strict result parser, fake CI judge, and live gateway
  judge path;
- report/gate artifact generation with deterministic-vs-LLM disagreement
  summary;
- live HTTP mode for real evaluator runs;
- offline fixture CLI for CI/test dry-runs;
- JSONL and summary JSON artifacts.

Future optional:

- calibrated multi-case live gold set using stable reviewer sessions/templates;
- optional LLM policy extension behind an explicit flag;
- batched cast-council/multi-NPC simulation;
- trajectory results persisted into a separate eval run table or run registry;
- richer reviewer UI for trajectory artifacts;
- integration with external tracing backends.

## Admissions-Safe Positioning

Tiny Stories can be described as an inspectable AI narrative runtime with a
local player-agent evaluation chain. The project demonstrates typed contracts,
deterministic orchestration, compact memory, traceability, per-turn judges, and
trajectory evaluation. It should not be framed as a validated consumer product,
retention-proven game, or full production autonomous multi-agent framework.

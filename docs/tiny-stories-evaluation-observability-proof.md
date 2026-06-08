# Tiny Stories Evaluation And Observability Proof

Tiny Stories now has a reviewer-only evidence path for the Create/Brief/Play
loop. The goal is productized LLM reliability engineering: repeatable scenario
coverage, persisted runtime traces, per-turn judges, trajectory summaries, and
sanitized latency/usage telemetry. This is not presented as novel ML research
or a general benchmark.

## Evaluation Protocol

The gold protocol lives at
`tools/rpg_eval/gold_sets/tiny_stories_reliability.json`.

It covers seven release-relevant cases:

- arbitrary Story Butler input and smalltalk;
- meta/help input;
- unsafe prompt redirect;
- laundromat not-fit gate;
- supported high-drama awards prompt;
- multi-turn correction and superseded facts;
- Play turn consequence.

The repeatable command is:

```bash
python -m tools.rpg_eval.tiny_stories_reliability_harness \
  --output artifacts/eval_tiny_stories/reliability_protocol_summary.json
```

The command validates the protocol shape and exercises the existing deterministic
trajectory judge with a fixture Play turn. It is CI-safe and does not claim live
provider proof. Final user-facing previews still require Live Pro browser
validation and database telemetry evidence.

## Failure Taxonomy

The first-pass taxonomy is intentionally product-facing:

- `environment`
- `provider`
- `schema`
- `unsafe_redirect`
- `not_fit_gate`
- `story_guide_intent`
- `brief_contract`
- `entity_hygiene`
- `opening_recovery`
- `step_judge`
- `trajectory_judge`
- `telemetry_missing`
- `normal_ui_leak`
- `artifact`

Reviewer reports should use these buckets before falling back to raw exception
labels. Normal player UI must never expose internal exception names, provider
config, token accounting, raw JSON, or trace payloads.

## Step Judge

Each submitted Play turn persists three reviewer trace events in
`narrative_agent_events`:

- `agent_plan`
- `step_judge`
- `contract_judge`

`StepJudgeResult` checks whether the narrator turn honors the pre-turn plan:
active NPC presence, leverage impact, high-pressure consequence, and inventory
delta sanity.

`ContractJudgeResult` checks runtime shape and contract safety: narrator role,
option count/labels, known NPC ids, hidden-info leakage, leverage ownership, and
state-delta sanity.

The Play reviewer drawer maps these persisted judge results into criterion rows:

- player agency preserved;
- consequence follows move;
- Brief contract honored;
- entities remain coherent;
- tone/profile respected;
- options are playable;
- unsafe/out-of-spec drift avoided;
- trajectory advances.

The score is a deterministic reviewer display score derived from criterion
statuses: pass = 100, warn = 68, fail = 35, missing = 0. It is evidence UI, not
a calibrated research metric.

## Trajectory Judge

The in-product reviewer drawer computes a deterministic trajectory trend from
persisted turn events: per-turn Step/Contract status, counts by pass/warn/fail,
and an overall trend. The external mock-user eval chain has a richer
`TrajectoryJudgeResult` in `tools.rpg_eval.narrative_mock_user`; the product
drawer intentionally shows only the compact version needed for reviewers.

## Telemetry

LLM call evidence is persisted in `narrative_llm_call_events` and exposed only
through the reviewer-gated endpoint:

```text
GET /narrative/sessions/:session_id/llm-events
```

Allowed reviewer fields:

- operation label;
- source label;
- status;
- latency and operation latency;
- input tokens;
- cached input tokens when returned;
- output tokens;
- total tokens;
- retry count;
- repair count;
- fallback reason when present.

Disallowed in normal player UI:

- provider/model/API/schema/debug wording;
- raw prompts or tool arguments;
- private reasoning or chain-of-thought;
- raw JSON wrappers;
- auth headers or secrets.

## Grad-Application Framing

Safe phrasing:

> Built an LLM story-game runtime with persisted telemetry, deterministic
> contract judges, a trajectory evaluation harness, and reviewer-only
> observability surfaces for validating live product behavior.

Avoid overclaims:

- do not call the score a validated academic metric;
- do not claim neural judge calibration unless a real calibrated judge is run;
- do not imply normal users see token/debug data;
- do not call deterministic trace checks chain-of-thought.

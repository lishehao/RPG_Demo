# RPG Runtime Evaluation Lab

## Purpose

The RPG Runtime Evaluation Lab is a backend-free reviewer frontend for
comparing stateful RPG-agent runs. It is intentionally broader than Tiny
Stories: another RPG can export one portable JSON bundle and use the same
memory, consequence, agency, trajectory, entity, choice, and boundary checks.

Public route:

```text
#/lab/rpg-evaluation
```

Public deployment: <https://tiny-stories-rpg-evaluation.vercel.app>

The lab is a product reliability diagnostic. Its score is deterministic and
inspectable, but it is not a calibrated academic quality metric. Narrative
appeal and emotional quality still require bounded human review.

## Portable Contract

The input root is `rpg_evaluation_bundle.v1`:

```json
{
  "schema_version": "rpg_evaluation_bundle.v1",
  "run_id": "run-123",
  "system_label": "Candidate runtime",
  "locale": "en",
  "scenario": {
    "scenario_id": "backstage-01",
    "title": "Vanished Before Curtain",
    "genre": "social-pressure mystery",
    "objective": "Find the singer before air.",
    "turn_budget": 12,
    "entity_ids": ["singer", "producer", "publicist"],
    "boundaries": ["No violence"]
  },
  "turns": []
}
```

Each turn contains:

- the player action;
- the player-visible world response;
- the real next-action set;
- typed state deltas;
- clue and opportunity unlocks;
- referenced entity ids;
- bounded objective progress;
- one `rpg_memory.v1` snapshot.

The frontend deliberately does not accept raw prompts, private reasoning,
provider credentials, or tool arguments.

## Memory Contract

`rpg_backend.research_runtime.memory` reduces portable events into a bounded,
auditable snapshot:

- active facts have one current value per namespace/key;
- corrections move the previous value to `superseded_facts`;
- non-story input is retained as conversational evidence but never becomes a
  story fact;
- open threads can be opened and resolved;
- person state is merged by entity id;
- recent events and active facts have explicit budgets;
- diagnostics report event, active, superseded, non-story, dropped, and
  compaction counts.

`project_story_guide_memory()` projects the existing Story Butler compressed
context into the same portable contract. The live Story Butler prompt and
runtime behavior remain unchanged.

## Deterministic Criteria

| Criterion | What it checks |
| --- | --- |
| Memory continuity | No duplicate active fact or active/superseded conflict |
| Memory boundedness | Fact and recency budgets remain bounded |
| Consequence visibility | Each move yields a typed delta, clue, or opportunity |
| Player agency | Each turn preserves at least two distinct next actions |
| Trajectory progress | Objective progress advances without unexplained regression |
| Entity coherence | Referenced people/factions exist in the scenario registry |
| Choice diversity | Full next-action sets change across the trajectory |
| Boundary hygiene | Player text contains no protocol or private-reasoning leakage |

The aggregate score is a readable summary, not a replacement for criterion
rows or evidence.

## CLI

Export a bundle from the lab, then run the same backend evaluator:

```bash
python3.11 -m tools.rpg_eval.portable_runtime run.json --out report.json
```

No provider call is made. Invalid or extra fields fail closed through Pydantic
contracts.

## Frontend Views

- **Overview**: aggregate result, criterion rows, evidence, and baseline comparison.
- **Run trace**: action, world reaction, explicit changes, and next actions per turn.
- **Memory**: active facts, superseded facts, people, open threads, and recent events.
- **Adapter**: compact input shape plus bundle/report downloads.

The built-in candidate and prose-only baseline make the lab usable without a
backend. Imported bundles never leave the browser.

When the full local Tiny Stories backend is running, the same route also accepts
`?session=<session_id>`. An authenticated owner can load a completed live
session, export its server-built bundle, and run the authoritative deterministic
evaluator without copying JSON. This local-only loader is omitted from the
public static build, so the Vercel artifact remains backend-free and cannot
silently claim access to live sessions.

## End-to-End Provenance

The reference runtime keeps one auditable contract across the product chain:

1. Story Butler compacts current facts, corrections, boundaries, open questions,
   and non-story intents.
2. Template creation persists the Story Brief plus a sanitized Story Guide
   context. Raw chat turns are not stored in this research seed.
3. Play turns and endings receive a compact `story_contract` containing current
   truth only. Superseded facts, meta conversation, planner internals, and raw
   model messages are excluded.
4. Session export projects the persisted seed and every completed Play turn into
   `rpg_evaluation_bundle.v1`.
5. The frontend lab and backend evaluator share the same terminal-turn and
   progress-provenance rules. A reported progress value derived from the turn
   budget is labeled `turn_budget_proxy`, not presented as engine ground truth.

The owner-only Reviewer surface links to the session-scoped lab after the first
completed turn. Normal Play remains free of evaluator, token, provider, and
private-reasoning details.

## Vercel Delivery

`frontend2/vercel.json` builds the same React application with
`VITE_PUBLIC_LAB_DEFAULT=true`. The deployment therefore opens the evaluation
lab at the root and skips the initial auth request. No LLM key or backend URL is
needed for the public artifact.

The live Tiny Stories acceptance path remains a separate, configured-backend
validation. A static Vercel demo must not be cited as live-provider proof.

## Strict Live Gate

`tools/rpg_eval/tiny_stories_golden_path_harness.py` is the strict completion
gate. It runs a corrected Story Butler memory sequence, Story Brief, live
opening, 12 live Play turns, ending, persisted session export, and backend
evaluation. Every required provider operation must be `live` or
`live_repaired`, with no fallback reason. The gate preserves exact telemetry
and a deterministic quality summary; neither is a substitute for human
narrative judgment.

## Latest Bounded Live Acceptance

The strict 2026-08-24 run used an isolated runtime database and a configured
live text gateway. It corrected an initially wrong player role, compiled the
current truth into a Story Brief, generated a live opening, completed all 12
Play turns, produced an ending, exported the persisted session, and evaluated
the portable bundle. The sanitized evidence is available as
[`evidence/tiny-stories-12-turn-live-research-runtime-2026-08-24.json`](./evidence/tiny-stories-12-turn-live-research-runtime-2026-08-24.json)
and a compact
[`Markdown report`](./evidence/tiny-stories-12-turn-live-research-runtime-2026-08-24.md).

| Gate | Result |
| --- | --- |
| Required live operations | Story Butler, Story Brief, Opening, 12 Play turns |
| Provider classification | all `live/success`; zero fallback, repair, or retry |
| Play latency | 11,403 ms median; 14,858 ms max |
| Play usage | 99,705 input; 71,680 cached input; 7,665 output; 107,370 total tokens |
| Ending | completed at 12/12, canonical label `共谋` |
| Step / Contract Judge | 12 / 12 rows, all pass |
| Deterministic quality package | all 6 bounded criteria pass |
| Portable evaluator | pass, 100/100, progress provenance `turn_budget_proxy` |
| Memory | 13 active facts; 3 superseded facts; corrected role absent from current truth |

Two shorter bilingual runs separately exercise the same current-truth memory,
Brief, opening, Play, persistence, and evaluator path:

- [English live acceptance](./evidence/rpg-evaluation-live-memory-acceptance-2026-08-24.json):
  pass, portable score 90, opening consistency pass.
- [Chinese live acceptance](./evidence/rpg-evaluation-live-zh-acceptance-2026-08-24.json):
  pass, portable score 90, Chinese Story Butler/Brief/Opening/Play output, opening
  consistency warn retained as a quality limitation.

These runs prove that the bounded reference path can complete through the
configured provider without deterministic fallback. They do not prove general
story quality, calibrated fun, consumer demand, or robustness outside the
tested scenarios. The Browser acceptance also covered English and Chinese
Home, Create, Play, Replay, Portfolio, About, Evaluation, Reviewer, and local QA
routes at desktop and 390 px widths; normal player surfaces had no provider,
schema, token, trace, fallback, raw JSON, or private-reasoning copy.

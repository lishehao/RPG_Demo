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

## Vercel Delivery

`frontend2/vercel.json` builds the same React application with
`VITE_PUBLIC_LAB_DEFAULT=true`. The deployment therefore opens the evaluation
lab at the root and skips the initial auth request. No LLM key or backend URL is
needed for the public artifact.

The live Tiny Stories acceptance path remains a separate, configured-backend
validation. A static Vercel demo must not be cited as live-provider proof.

## Latest Bounded Live Acceptance

The 2026-08-24 local acceptance run used a fresh runtime database and a
configured live text gateway. It exercised Story Butler, Story Brief, opening,
one Play turn, and reviewer telemetry. The durable, sanitized record is
[`evidence/rpg-evaluation-live-acceptance-2026-08-24.json`](./evidence/rpg-evaluation-live-acceptance-2026-08-24.json).

| Operation | Source | Status | Latency | Input | Cached input | Output | Total | Fallback |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `create.story_butler_turn` | live | success | 1,281 ms | 2,389 | 0 | 31 | 2,420 | none |
| `narrative.story_brief` | live | success | 2,207 ms | 1,477 | 0 | 156 | 1,633 | none |
| `narrative.opening` | live | success | 12,635 ms | 2,686 | 0 | 808 | 3,494 | none |
| `narrative.advance_turn` | live | success | 9,312 ms | 6,863 | 0 | 447 | 7,310 | none |

This run proves that the reference path can complete through the configured
live provider without deterministic fallback. It does not prove general story
quality. The opening consistency classifier returned `warn`; that is retained
as a visible quality risk rather than reclassified as success.

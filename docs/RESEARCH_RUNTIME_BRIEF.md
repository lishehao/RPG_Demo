# Tiny Stories Research Runtime Brief

## Decision

Tiny Stories is scoped as a research-grade technical product:

> A controllable and evaluated LLM interactive-narrative runtime, delivered as
> a research specification, a runnable reference implementation, and a
> repeatable evaluation harness.

Interactive storytelling is the experimental carrier. The project does not
claim consumer-market validation, general narrative robustness, or a novel
foundation model.

## Primary Question

How can an underspecified, revisable user intent be compiled into a bounded,
stateful, playable, recoverable, and evaluable interactive narrative under
stochastic LLM outputs?

## Approved Defaults

1. Primary audience: applied-AI R&D, product-systems, and graduate-project reviewers.
2. Secondary audience: interactive-narrative creators and bounded test participants.
3. Public delivery: static evidence and evaluation UI, with invite-controlled or quota-bounded live runs.
4. Content boundary: a small set of modern social-pressure, backstage, workplace, and mystery scenarios.
5. Evidence: deterministic fixtures, bounded live-provider acceptance, structured judges, and small formative human review.
6. Provider strategy: one primary live provider with only bounded comparison runs.
7. Post-research direction: freeze evidence first; reopen consumer beta or creator SDK only if the research reveals a clear opportunity.

## In Scope

- arbitrary-input Story Butler routing and compressed context;
- corrections and superseded-fact handling;
- Story Brief compilation and opening fidelity;
- a 12-turn playable runtime with explicit goals, pressure, people, clues, forecasts, and impacts;
- bounded failure, retry, repair, fallback, idempotency, and persistence;
- reviewer-only telemetry and deterministic/LLM-assisted evaluation;
- Chinese/English and desktop/mobile robustness;
- a portable RPG evaluation bundle and public evaluation frontend.

## Explicit Non-goals

- open UGC marketplace;
- deep emotional-companion positioning;
- adult visual content;
- subscriptions, growth loops, or consumer retention claims;
- multiplayer/social graph;
- production-scale multi-tenant infrastructure;
- calibrated academic metrics or SOTA claims.

## Completion Evidence

The research artifact is complete only when a third party can:

1. understand the claim and its limits;
2. inspect a deterministic success and failure case;
3. run a bounded live path with real telemetry;
4. inspect memory, state, consequences, and evaluator evidence;
5. reproduce the tests and static public demo without secrets.

## Reference Data Path

```text
arbitrary input
  -> intent-aware Story Butler
  -> bounded current-truth memory
  -> Story Brief
  -> persisted template research context
  -> live opening
  -> 12-turn Action Runtime
  -> ending
  -> portable session bundle
  -> deterministic evaluator + Reviewer evidence
```

Corrections are first-class events: the replacement becomes active truth while
the old value remains only in `superseded_facts`. Play and ending prompts use a
sanitized Story Contract rather than the unbounded Create transcript. The
portable evaluator receives explicit terminal-turn and progress-provenance
fields so it can distinguish runtime facts from turn-budget proxies.

The public Vercel lab is deliberately static and backend-free. Live acceptance
is proven separately through a configured local gateway, strict telemetry, and
a 12-turn golden-path artifact. This division keeps the demo reproducible while
preventing a static portfolio surface from being mistaken for live-provider
evidence.

## Current Reference Acceptance

As of 2026-08-24, the strict reference run completes a corrected Story Butler
conversation, Story Brief, live opening, 12 live Play turns, ending, persisted
session export, Reviewer evidence, and portable evaluation with no required
operation falling back. English and Chinese bounded runs verify that current
facts, superseded corrections, story language, and responsive UI state survive
the same chain. The full records live under `docs/evidence/` and intentionally
retain latency, token, source, fallback, provenance, and consistency caveats.

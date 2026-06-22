# Tiny Stories Case Study

Read this as source evidence after the 75s demo. It summarizes what reviewers
can inspect, where that evidence lives in the codebase, and what is still
outside the claim.

Public visibility boundary: cite `#/portfolio`, `#/reviewer`, Story Desk,
Create, Play, and Replay as public application evidence only after
`python3 tools/portfolio_public_evidence_preflight.py` passes. If the public-link check fails,
those routes are local verification targets and demo-video context, not public
proof.

## Problem

Most LLM story demos stop at generated prose. Tiny Stories explores a
product-shaped question: can open-ended generation become a playable, inspectable story system
with state, roles, replay, and evaluation hooks?

## Product Loop

1. A player types one premise.
2. The compiler turns it into cast, role cards, hidden goals, leverage, failure
   conditions, and an opening scene.
3. The player runs a bounded 12-turn session with choices, free-form actions,
   advisor help, inventory shifts, and consequence tracking.
4. The ending compiler turns the actual run history into a label, passage,
   highlights, alternate branches, and a shareable replay.
5. A reviewer can open the evidence path to see the state machine behind the UI.

## Target Player And Content Model

Tiny Stories is aimed at story-first players who want a short interactive drama,
especially on mobile, rather than a blank writing tool, a conventional RPG
inventory screen, or a systems dashboard. The intended consumption rhythm is:
read the current scene, compare a few meaningful moves, act once, see what
changed, and use that consequence to choose the next beat.

That audience assumption drives the UI standard: keep narrative context and
decision context close together, make the "why now" reason visible when a move
opens, keep private motive drafting attached to the selected move, and keep
reviewer evidence separate from the normal player surface. The application claim
is product judgment around a narrow player loop, not proof that the project has
validated retention or broad demand.

## Evidence To Inspect

| Reviewer question | Source evidence |
| --- | --- |
| Does the demo have a current product path rather than a pile of experiments? | `docs/CURRENT_SYSTEM_MAP.md` |
| Does a reviewer get a guided evidence surface? | `frontend2/src/pages/portfolio/`, `#/portfolio`, `#/reviewer` |
| Is the play contract typed and inspectable? | `rpg_backend/narrative/contracts.py`, `frontend2/src/api/contracts.ts` |
| Do choices and consequences persist across turns? | `rpg_backend/narrative/repository.py`, `rpg_backend/narrative/service.py` |
| Are the application claims guarded in source? | `tests/test_navigation_mental_model_contract.py`, `tests/test_play_direction_a_editorial_primitives_contract.py` |

## Why It Is More Than A Chatbot

| Mechanism | Product effect | Engineering surface |
| --- | --- | --- |
| Template/session split | Many players can fork the same story shell and compare endings. | `rpg_backend/narrative/repository.py` |
| Player role contract | The user plays a strategic character with public and private goals. | `PlayerRole`, `PlayerGoal`, `starting_assets` |
| Deterministic turn scaffolding | The model writes inside a paced game frame. | `rpg_backend/narrative/engine.py` |
| Advisor side-channel | Help is contextual but cannot silently alter story state. | `ask_advisor`, advisor message table |
| Replay and fork CTA | A finished run becomes shareable and replayable. | `PublicReplayResponse.template_id` |
| Reviewer mode | Admissions/recruiting reviewers can inspect state and consequence decisions quickly. | `frontend2/src/pages/portfolio/` |

## Safety And Operations

- Authoring and write routes require a real session; anonymous visitors can still
  browse, fork, and play public stories.
- Public deployments can disable expensive legacy authoring endpoints with
  `APP_PUBLIC_DEMO_AUTHORING_ENABLED=false`.
- LLM calls pass through per-IP and per-user/default-actor daily quotas.
- Migration code archives incompatible rows before removing them from active
  tables; startup should not silently delete user data.
- Product metrics emit structured log events for sessions started, sessions
  completed, advisor usage, and replay views.

## Current Limits

This is portfolio-grade AI product-system evidence, not a validated consumer
game or broad adoption proof.
Repeat-play demand, organic sharing, and retention have not been proven. The
next validation step is a small real-user playtest and the report template in
`docs/playtest_report.md`.

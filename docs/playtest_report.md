# Tiny Stories Real-User Playtest Report Template

This file is intentionally a template, not fabricated evidence. Fill it only
after real players complete sessions. Until then, cite this file only as the
planned validation method, not as proof of retention, replay demand, sharing, or
consumer adoption.

## Test Setup

| Field | Value |
| --- | --- |
| Date | TBD |
| Build / commit | TBD |
| Participants | TBD |
| Device mix | TBD |
| Seeds tested | TBD |
| Public-link check result | TBD |
| Local-only surfaces used | TBD |

## Target Player Fit

Recruit story-first players who are willing to read a compact mobile drama, not
only developers or LLM enthusiasts. Record whether each participant normally
enjoys interactive fiction, roleplay, mystery/drama games, or AI writing tools.

| Participant | Reading preference | Mobile game tolerance | Prior AI-story exposure | Fit note |
| --- | --- | --- | --- | --- |
| P1 | TBD | TBD | TBD | TBD |

## Task Script

Use the same script for every participant unless a run fails technically:

1. Start from Story Desk or a shared replay link.
2. Read the opening scene without explanation from the facilitator.
3. Pick a role or start the default story path.
4. Play at least three turns, including one selected-card move and one inner
   motive if the participant notices it naturally.
5. Reach an ending if time allows; otherwise stop after the participant can
   explain what changed after the latest move.
6. Ask the participant to describe what they think the app is, who it is for,
   and whether they would replay or share it.

## Quantitative Metrics

| Metric | Result |
| --- | --- |
| Sessions started | TBD |
| Sessions completed | TBD |
| Completion rate | TBD |
| Average turns played | TBD |
| First-choice time | TBD |
| Chose inner motive | TBD |
| Replay links opened | TBD |
| Advisor used | TBD |
| Role selected manually | TBD |
| Horizontal overflow / clipped text observed | TBD |

## Moment-Level Observations

| Moment | What to observe | Participant evidence | Impact | Follow-up |
| --- | --- | --- | --- | --- |
| Story Desk / entry | Do they understand whether they are choosing, resuming, or writing a story? | TBD | TBD | TBD |
| Opening scene | Can they summarize the current situation and their role without help? | TBD | TBD | TBD |
| First choice | Can they compare moves and explain why one is attractive? | TBD | TBD | TBD |
| Selected confirm | Do they keep the selected move context while finding Submit / motive controls? | TBD | TBD | TBD |
| Inner motive | Do public move and private motive feel clear, optional, and safe to edit? | TBD | TBD | TBD |
| Pending / resolved feedback | Can they say what changed and why the next actions opened? | TBD | TBD | TBD |
| Advisor | Does the advisor feel like help, not an autopilot or hidden submit path? | TBD | TBD | TBD |
| Ending | Do they understand the ending label, recap, share, and replay choices? | TBD | TBD | TBD |
| Replay / fork | Does a shared replay read as a completed memory rather than an active run? | TBD | TBD | TBD |

## UI / Visual Experience Notes

Record observations from the participant's actual device, especially 390px-class
mobile screens:

- Text density: TBD
- Card comparison and spacing: TBD
- Narrative readability: TBD
- Button discoverability: TBD
- Visual polish / trust: TBD
- Any clipped text, awkward scroll, or confusing repeated context: TBD

## Application Evidence Boundary

Use this report conservatively in applications:

- Strong evidence: observed player comprehension, visible UI issues, completed
  sessions, replay/share behavior, and direct quotes from participants.
- Weak evidence: facilitator impressions, one-off praise, local-only QA routes,
  and unverified public links.
- Not evidence: this blank template, internal browser smoke, generated demo
  screenshots, or assumptions that players will replay/share.

Before citing the current app surfaces as public application evidence, run
`python3 tools/portfolio_public_evidence_preflight.py`. If it fails, label the
tested surfaces as local-only evidence and cite the demo video only for
orientation.

## Decision

TBD: continue, pause, or change direction based on observed story
comprehension, choice confidence, feedback clarity, mobile UI comfort,
completion, repeat play, and sharing behavior.

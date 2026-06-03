# Story Brief V11 Demo Candidate Freeze

This document names the accepted Tiny Stories V11 demo candidate and records the
minimum regression package needed to keep the bounded beta/demo path stable.

## Candidate

| Field | Value |
| --- | --- |
| Accepted snapshot | `snapshot/story-brief-product-v11-final-payoff-polish-2026-06-03` |
| Accepted commit | `36bfefaf79699ba3224fc5e100dab812a8622ba3` |
| Play Tester report | `/Users/lishehao/Desktop/Project/Personal/RPG_Demo_refactor/artifacts/playtester_feedback/2026-06-03-v11-final-payoff-polish-9-10-reassessment-playtest.md` |
| Play Tester summary | `/tmp/tiny-stories-v11-final-payoff-polish-9-10/summary.json` |
| Play Tester runtime DB | `/tmp/tiny-stories-v11-final-payoff-polish-9-10-runtime.sqlite3` |

## Accepted Scope

V11 is accepted as a 9.0/10 bounded Tiny Stories beta/demo candidate for:

- Story Guide -> Brief Story Card -> Generate and enter story.
- Cozy 12-turn reliable run with completed payoff and public replay.
- Mars and fantasy regression runs with protected context/tone guards.
- Small-cast not-fit/revise-first behavior.
- Cloud3 main-loop, payoff, replay, reviewer, and secondary-surface quick
  regressions.

This is not a claim that Tiny Stories is a universal consumer story platform.
The reliable path remains deterministic and intentionally bounded.

## Verified V11 Gates

Play Tester verified the accepted snapshot with:

- Valid-flow HTTP >=400 count: 0.
- Valid console warning/error count: 0.
- Cozy final-submit: 12/12 turn POSTs returned 200.
- Cozy DB/UI/API all agreed the run completed and persisted trace rows.
- Final desktop submit opened directly on the payoff panel.
- Mobile payoff remained result-first with no overflow.
- Replay title had no empty quotes.
- Replay changed rows used human-readable labels instead of raw entity ids.
- Mars/fantasy residue guards stayed clean.
- Small-cast not-fit card stayed clean and revise-first.

## Local Regression Package

Run these before moving this candidate or merging follow-up product/UI changes:

```bash
/private/tmp/rpg-demo-story-brief-pyenv/bin/python -m pytest \
  tests/test_v11_demo_candidate_freeze.py \
  tests/test_narrative_create_prompt_shape.py::test_cozy_reliable_final_turn_records_ending_without_gateway \
  tests/test_narrative_create_prompt_shape.py::test_cozy_reliable_turns_remain_varied_over_long_session \
  tests/test_narrative_create_prompt_shape.py::test_mars_reliable_turns_vary_without_escalating_or_losing_background \
  tests/test_narrative_create_prompt_shape.py::test_fantasy_reliable_turns_avoid_comedy_residue_when_prompt_is_playful -q
```

Standard branch validation remains:

```bash
npm --prefix frontend2 run check:cover-routing
npm --prefix frontend2 run check
npm --prefix frontend2 run build
/private/tmp/rpg-demo-story-brief-pyenv/bin/python -m pytest \
  tests/test_narrative_story_brief.py \
  tests/test_narrative_create_prompt_shape.py \
  tests/test_narrative_agent_trace.py \
  tests/test_narrative_release_gate.py \
  tests/test_v11_demo_candidate_freeze.py -q
git diff --check
```

## Residual Risk

- Deterministic prose is now acceptable for the bounded demo, but it can still
  feel patterned over repeated long sessions.
- Small-cast/no-conflict stories remain out of scope unless a separate mode is
  designed.
- Future visual or replay work must preserve the result-first payoff focus and
  replay label contracts recorded in `tests/test_v11_demo_candidate_freeze.py`.

## Next Optional Polish

- Add a maintained Playwright smoke script only if the team wants a reusable
  browser gate instead of Play Tester-run validation bundles.
- Continue prose texture polish after the demo candidate is frozen; do not use
  it to block this candidate unless a new player-facing failure appears.

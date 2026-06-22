# Test Suite Map

The test suite mixes older RPG/authoring coverage with the current Tiny Stories Story Butler -> Play product loop. Use focused suites first, then broaden when shared contracts move.

## Current Product-Loop Guards

- `test_agent_guided_settings_contract.py`
  - Story Butler setting inference and visibility-not-silent behavior.
- `test_navigation_mental_model_contract.py`
  - Route-aware Back/Home placement and source guards against buried page-level Back.
- `test_korean_agent_chat_slot_loop_contract.py`
  - Missing-field loop, readiness, unsafe redirect, not-fit gating.
- `test_korean_agent_chat_reviewer_contract.py`
  - Reviewer launch and evidence copy.
- `test_published_direct_play_contract.py`
  - Published template cards and template detail start Play/session directly.
- `test_generated_cover_contract.py`
  - Generated cover URL preference, internal fallback theme matching, same-screen no-overlap.
- `test_localized_story_metadata_contract.py`
  - Optional localized title/summary roundtrip and display fallback.
- `test_narrative_story_brief.py`
  - Story Brief extraction, not-fit logic, clean entity/focus routing.
- `test_narrative_create_prompt_shape.py`
  - Template/opening generation, reliable recovery, live opening cap, prompt shape.
- `test_narrative_agent_trace.py`
  - Trace persistence and reviewer access.
- `test_narrative_release_gate.py`
  - Release/product guardrails.

## Common Focused Run

```bash
/tmp/tiny-stories-story-desk-pyenv/bin/python -m pytest \
  tests/test_agent_guided_settings_contract.py \
  tests/test_navigation_mental_model_contract.py \
  tests/test_published_direct_play_contract.py \
  tests/test_korean_agent_chat_slot_loop_contract.py \
  tests/test_korean_agent_chat_reviewer_contract.py \
  tests/test_generated_cover_contract.py \
  tests/test_localized_story_metadata_contract.py \
  tests/test_narrative_story_brief.py \
  tests/test_narrative_create_prompt_shape.py \
  tests/test_narrative_agent_trace.py \
  tests/test_narrative_release_gate.py \
  -q
```

## When To Add Tests

- New frontend source contract -> add a focused source guard if browser smoke would be slow/flaky.
- New API/persistence field -> add backend contract/repository roundtrip coverage.
- New Story Brief extraction rule -> add exact prompt regression in `test_narrative_story_brief.py`.
- New opening/session behavior -> add `test_narrative_create_prompt_shape.py` coverage.
- New card or route semantics -> update published/direct-play/navigation tests.
- New asset resolver rule -> update `test_generated_cover_contract.py`.

## Browser Smoke Still Matters

Source guards do not replace browser validation for:

- Create -> Brief -> Generate -> Play.
- Published card -> Play.
- Not-fit card: revise-first, no Generate CTA.
- Reviewer launch -> evidence mode.
- Mobile 390px overflow and action reachability.

For local frontend/backend smoke, prefer isolated ports and temp DBs. Do not depend on or stop the user's existing preview server unless the task explicitly asks for it.

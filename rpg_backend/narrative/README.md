# Narrative Backend Architecture

This folder owns the current Tiny Stories template/session/story loop.

## Files

- `contracts.py`
  - Pydantic request/response and persistence-facing models.
  - Update `frontend2/src/api/contracts.ts` when API-visible shapes change.
- `repository.py`
  - SQLite schema creation, migrations, and persistence.
  - Holds templates, sessions, story messages, endings, replay, and agent trace events.
- `service.py`
  - Main orchestration layer.
  - Handles Story Brief to template, live opening attempt, reliable opening recovery, direct session start, story turns, advisor, replay, and visibility.
- `brief.py`
  - Deterministic Story Brief planner.
  - Owns fit/not-fit, slot extraction, entity hygiene, constraints, key details, and revision actions.
- `gateway.py`
  - Live opening gateway integration.
- `engine.py`
  - Lower-level narrative/runtime primitives.
- `judges.py`
  - Deterministic reviewer evidence and contract/step judge helpers.

## Current Live/Deterministic Boundary

- Story Brief planning is deterministic by design.
- Opening/template generation attempts the live provider when configured, then uses bounded reliable recovery for demo safety.
- The current accepted live opening cap is 45 seconds.
- Play turns may use the live/hybrid chain when provider configuration is present.
- Tests should be deterministic unless explicitly marked/configured for live paths.

Never print API keys or secret values. Refer to `.env.example` for variable names.

## Accepted Product Contracts

- No pre-Create login gate for normal writing.
- Supported Story Brief can Generate and enter Play.
- Not-fit prompts stay revise-first and never expose Generate.
- Exact laundromat not-fit keeps `customer` and `attendant` as focus, preserves `wedding ring` as detail, and does not cast negated phrases.
- High-drama entity extraction must not promote time/action fragments such as `Ten minutes`, `what to`, or `player must`.
- Published templates start Play through the template/session endpoint; do not re-run Story Brief shaping.
- Reviewer launch must work deterministically and show evidence mode without provider/maintainer copy.
- Normal player UI must not receive raw provider/model/API/schema/debug errors.

## Persistence Notes

- Narrative templates include optional `cover_image_url`, `title_i18n`, and `summary_i18n`.
- `cover_image_url` is nullable. Frontend fallback resolver fills absent covers.
- Localized metadata is lightweight display metadata only; story body is generated in the selected story language.
- Agent trace events are reviewer evidence and should stay gated.

## Test Map

- Story Brief extraction and fit: `tests/test_narrative_story_brief.py`.
- Template/opening contract: `tests/test_narrative_create_prompt_shape.py`.
- Trace/reviewer evidence: `tests/test_narrative_agent_trace.py`.
- Release gate: `tests/test_narrative_release_gate.py`.
- Published direct-play: `tests/test_published_direct_play_contract.py`.
- Localized metadata: `tests/test_localized_story_metadata_contract.py`.

Run focused checks after narrative edits:

```bash
/tmp/tiny-stories-story-desk-pyenv/bin/python -m pytest \
  tests/test_narrative_story_brief.py \
  tests/test_narrative_create_prompt_shape.py \
  tests/test_narrative_agent_trace.py \
  tests/test_narrative_release_gate.py \
  -q
```

Add narrower tests for every new entity, fallback, persistence, or session-start rule.

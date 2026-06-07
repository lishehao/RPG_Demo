# Tiny Stories Code Map

This map documents the current Tiny Stories Korean webtoon demo candidate. It is intended for future developers who need to understand where product behavior lives before making changes.

## Active App

- Active frontend: `frontend2`.
- Legacy frontend: `frontend` may exist in older branches or docs, but the current product route and validation target is `frontend2`.
- Frontend entrypoint: `frontend2/src/main.tsx`.
- App/router shell: `frontend2/src/app/app.tsx` and `frontend2/src/app/routes.ts`.
- API route map/client: `frontend2/src/api/route-map.ts`, `frontend2/src/api/http-client.ts`, `frontend2/src/api/client.ts`, and `frontend2/src/api/contracts.ts`.
- Backend app entrypoints are outside this folder map; current story behavior is concentrated in `rpg_backend/narrative/`.

## Frontend Folder Responsibilities

- `frontend2/src/app/`
  - App composition, route parsing, API/auth/language providers, shared theme CSS.
  - Do not add page-specific product logic here unless it is route or provider infrastructure.
- `frontend2/src/pages/home/`
  - Korean webtoon home/library.
  - Published playable cards start or resume Play directly.
  - Starter premise doors route to Create/Agent Chat and must not look like published games.
- `frontend2/src/pages/create/`
  - Korean Agent Chat creation loop.
  - Owns Story Butler transcript UI, prompt starters, Story Brief-as-message, Generate handoff, and explicit visibility row.
  - Story-shape settings are inferred through the Story Butler loop; do not reintroduce a default fixed Length/Difficulty/Language/Tension settings grid.
- `frontend2/src/pages/play/`
  - Main turn loop, current beat/action structure, live resolving states, advisor drawer, ending payoff.
  - Normal player UI must not expose provider/model/API/schema/debug or reviewer trace terms.
- `frontend2/src/pages/replay/`
  - Result-first public replay and Story Desk return loop.
  - Replay can offer a completion CTA near the coda; page-level escape navigation still belongs in the route/header area.
- `frontend2/src/pages/world/`
  - Published template detail / role pick / direct Play entry.
  - Do not re-run Story Brief shaping for an already generated playable template.
- `frontend2/src/pages/portfolio/`
  - Portfolio and reviewer evidence mode.
  - Reviewer can expose trace/evidence language. Normal player routes cannot.
- `frontend2/src/shared/lib/`
  - Cross-page product helpers: i18n, Story Butler loop, asset resolver, localized story metadata, friendly error taxonomy, draft handoff.
- `frontend2/src/shared/ui/`
  - Shared UI primitives such as route-aware header. Keep these generic and avoid embedding page-specific business behavior.

## Backend Narrative Folder Responsibilities

- `rpg_backend/narrative/contracts.py`
  - Pydantic contracts for templates, sessions, Story Briefs, trace events, replay, and API responses.
  - Frontend mirrors many of these in `frontend2/src/api/contracts.ts`; update both sides together.
- `rpg_backend/narrative/repository.py`
  - SQLite persistence and schema migrations for narrative templates, sessions, messages, endings, replay, and trace events.
- `rpg_backend/narrative/service.py`
  - Product orchestration: Story Brief to template, live opening attempt, reliable opening recovery, session start, turn advancement, replay shaping.
  - Live opening is currently capped at 45 seconds before reliable recovery can keep the demo playable.
- `rpg_backend/narrative/brief.py`
  - Deterministic Story Brief extraction, fit/not-fit logic, entity hygiene, pressure/object/detail routing.
- `rpg_backend/narrative/gateway.py`
  - Live LLM gateway access for narrative opening where configured.
- `rpg_backend/narrative/engine.py`
  - Lower-level story engine primitives and runtime helpers.
- `rpg_backend/narrative/judges.py`
  - Deterministic trace/judge objects for reviewer evidence.

## Asset Folder Responsibilities

- `frontend2/public/webtoons/ui/`
  - Page-level backgrounds, logo, loading/auth/create backgrounds.
  - Current Create uses `ui/generated/create-agent-room-bg-v1.png` and `ui/generated/story-butler-avatar-v1.png`.
- `frontend2/public/webtoons/covers/generated/`
  - Art-provided fallback cover library and manifest.
  - R&D wires these paths into resolver logic; R&D does not generate new image assets.
- `frontend2/public/webtoons/shells/`
  - Internal fallback cover shells and variants.
- `frontend2/public/webtoons/segments/`
  - Play-stage scene images by beat phase.
- `frontend2/public/webtoons/avatars/`, `advisors/`, `oracle/`
  - Cast, advisor, and helper portraits.
- `frontend2/public/webtoons/endings/`, `splashes/`, `peaks/`
  - Ending, game state, and peak narration visuals.

## Test Suite Map

- `tests/test_agent_guided_settings_contract.py`
  - Story Butler setting inference, privacy-not-silent behavior, Create settings source guards.
- `tests/test_navigation_mental_model_contract.py`
  - Route-aware navigation and buried Back prevention.
- `tests/test_korean_agent_chat_slot_loop_contract.py`
  - Agent Chat slot loop, missing-field gating, unsafe redirect.
- `tests/test_korean_agent_chat_reviewer_contract.py`
  - Reviewer curated launch and evidence language.
- `tests/test_published_direct_play_contract.py`
  - Published template cards route to Play/session start rather than Create.
- `tests/test_generated_cover_contract.py`
  - Generated cover URL preference, fallback theme matching, same-screen no-overlap assignment.
- `tests/test_localized_story_metadata_contract.py`
  - Localized title/summary metadata defaults and display fallback.
- `tests/test_narrative_story_brief.py`
  - Story Brief extraction, fit/not-fit, entity hygiene, residue guards.
- `tests/test_narrative_create_prompt_shape.py`
  - Template/opening shape, live opening cap/recovery, reliable fallback, prompt contract.
- `tests/test_narrative_agent_trace.py` and `tests/test_narrative_release_gate.py`
  - Trace persistence and release-gate constraints.

## Common Validation Commands

From repo root:

```bash
npm --prefix frontend2 run check
npm --prefix frontend2 run build
git diff --check
git diff --cached --check
```

Focused Python suite used for current product-loop changes:

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

Local browser smoke should use isolated ports and temp DB paths. Prefer the Vite proxy form to avoid CORS drift:

```bash
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:<backend-port> \
  npm --prefix frontend2 run dev -- --host 127.0.0.1 --port <frontend-port>
```

## Ownership Boundaries

- R&D owns backend logic, API/session/persistence contracts, duplicate-click safety, live opening cap/recovery, deterministic slot/Brief logic, and tests for those contracts.
- Design owns frontend matching decisions: navigation placement, primary vs secondary card actions, published-vs-starter visual semantics, cover presentation rules, copy hierarchy, mobile action placement.
- Art owns image generation, image QA, asset manifests, and visual asset expansion.
- Play Tester owns read-only release/product validation and should not be used to patch code.

## Do Not Touch Casually

- No pre-Create login/name gate for normal writing.
- Korean webtoon visual identity for active Create flow.
- Story Butler slot loop and agent-guided settings.
- Published public templates must start/resume Play by default, not reopen Create.
- Cover resolver contract: trusted `cover_image_url` wins; internal fallback/no-overlap handles absent generated covers.
- Localized metadata is lightweight display metadata only; do not force bilingual story body generation.
- Live opening 45-second cap and safe recovery before template/session persistence.
- Normal player UI must not expose provider/model/API/schema/debug/agent trace terms.
- Reviewer evidence mode must remain separate and functional.
- Laundromat not-fit: no Generate CTA, clean `customer`/`attendant` focus, `wedding ring` preserved as detail.
- Mobile 390px should remain first-class with no horizontal overflow.

## Future Refactor Notes

- `frontend2/src/pages/create/create-page.tsx` is intentionally large. A future split should extract view-only components first (`TranscriptLane`, `BriefSlate`, `Composer`, `VisibilityControl`) without moving Story Brief API calls or changing flow semantics.
- `frontend2/src/pages/play/play-page.tsx` is also large. Split only after adding source guards for action submission, resolving states, payoff focus, and reviewer trace separation.
- Do not introduce broad file moves during release hardening unless tests and browser smoke are budgeted for the move.

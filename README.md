# Accept-All Narrative RPG (Backend-First)

Backend-first interactive narrative RPG service with strict Accept-All behavior:
- Any user input maps to a move and executes.
- Preconditions never hard-block progression.
- When success/partial cannot apply, runtime must execute `fail_forward`.

## Stack
- Python 3.11+
- FastAPI + Pydantic v2
- SQLModel + SQLite
- pytest

## Architecture
Code is split by responsibilities:
- `app/domain`: Story Pack DSL schema + linter
- `app/runtime`: Pass A routing + Pass B deterministic resolution + narration composition
- `app/llm`: provider abstraction (`FakeProvider` default, `OpenAIProvider` placeholder)
- `app/storage`: SQLModel entities + repositories
- `app/api`: REST API (stories/sessions)

Runtime architecture source of truth:
- `docs/architecture.md`

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Run server:

```bash
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Configuration
Environment variables use `APP_` prefix.

- `APP_DATABASE_URL` default: `sqlite:///./app.db`
- `APP_LLM_PROVIDER` default: `fake` (`fake|openai`)
- `APP_ROUTING_CONFIDENCE_THRESHOLD` default: `0.55`

## Story Pack and Linter
Global move IDs (required in every scene):
- `global.clarify`
- `global.look`
- `global.help_me_progress`

Sample pack:
- `sample_data/story_pack_v1.json`
- 4 beats
- 15 scenes
- 4 NPCs, each appears at least twice
- branch converges within 1 step (`sc2 -> sc3/sc4 -> sc5`)

Run linter:

```bash
python scripts/lint_story_pack.py sample_data/story_pack_v1.json
```

Auto-repair status:
- Placeholder only (not implemented yet)

## API Flow (curl)

### 1) Create draft story

```bash
curl -sS -X POST http://127.0.0.1:8000/stories \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg title 'City Signal Draft' --argjson pack "$(cat sample_data/story_pack_v1.json)" '{title:$title, pack_json:$pack}')"
```

### 2) Publish story version

```bash
curl -sS -X POST http://127.0.0.1:8000/stories/{story_id}/publish \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### 3) Read published raw pack

```bash
curl -sS "http://127.0.0.1:8000/stories/{story_id}?version=1"
```

### 3.5) Generate story (placeholder)

```bash
curl -sS -X POST http://127.0.0.1:8000/stories/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "seed_text":"A city-wide signal breach",
    "target_minutes":10,
    "npc_count":4,
    "publish":false
  }'
```

### 4) Create session

```bash
curl -sS -X POST http://127.0.0.1:8000/sessions \
  -H 'Content-Type: application/json' \
  -d '{"story_id":"{story_id}","version":1}'
```

### 5) Step with text input (Accept-All)

```bash
curl -sS -X POST http://127.0.0.1:8000/sessions/{session_id}/step \
  -H 'Content-Type: application/json' \
  -d '{
    "client_action_id":"step-1",
    "input":{"type":"text","text":"@@@ random words"},
    "dev_mode":false
  }'
```

### 6) Step with button input

```bash
curl -sS -X POST http://127.0.0.1:8000/sessions/{session_id}/step \
  -H 'Content-Type: application/json' \
  -d '{
    "client_action_id":"step-2",
    "input":{"type":"button","move_id":"global.clarify"},
    "dev_mode":true
  }'
```

### 7) Inspect session state

```bash
curl -sS "http://127.0.0.1:8000/sessions/{session_id}?dev_mode=true"
```

## Idempotency Contract
`POST /sessions/{session_id}/step` uses `client_action_id`.

If the same `client_action_id` is submitted again for the same session:
- returns **HTTP 200**
- returns the **exact first response payload**

Step input tolerance contract:
- malformed action shape in valid JSON (missing `input`, missing `move_id`, invalid `input.type`) is normalized and executed with global fallback moves.
- invalid session state still returns system errors (`404`/`409`).
- invalid JSON syntax can still return framework-level parse errors.

## Tests
Run all tests:

```bash
pytest -q
```

Canary tests included:
- `tests/test_canary_accept_all.py`
- `tests/test_canary_fail_forward.py`
- `tests/test_canary_low_confidence_progress.py`
- `tests/test_canary_story_completion.py`

## Playwright Smoke
A script is provided to do a browser smoke check through the Playwright CLI wrapper:

```bash
scripts/playwright_smoke.sh
```

It expects the server to be running at `http://127.0.0.1:8000` and `npx` available.

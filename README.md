# RPG Demo (UI Reimplementation Mock Backend)

This repository has been hard-reset to provide a **clean backend contract** for frontend teams to reimplement the RPG UI.

## What remains

- Minimal FastAPI mock backend in `rpg_backend/`
- Contract artifact in `contracts/openapi/backend.openapi.json`
- Generated frontend SDK metadata in `frontend/src/shared/api/generated/backend-sdk.ts`
- Frontend handoff contract in `frontend_agent_contract.md`

## What was removed

- Legacy runtime/generator/data-layer backend implementation
- Migration stack and DB artifacts
- Legacy backend-specific test suites and observability tooling

## Backend scope

The mock backend intentionally supports only these routes:

- `POST /admin/auth/login`
- `POST /stories/generate`
- `GET /stories`
- `POST /sessions`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/history`
- `POST /sessions/{session_id}/step`
- `GET /health`

All data is in-memory and reset when the process restarts.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn rpg_backend.main:app --reload
```

Backend base URL:

```text
http://localhost:8000
```

## Contract tooling

Export OpenAPI:

```bash
python -m scripts.export_openapi
```

Generate frontend SDK metadata:

```bash
python -m scripts.generate_frontend_sdk
```

## Authentication default

`POST /admin/auth/login` default credentials:

- `email`: `admin@test.com`
- `password`: `password`

You can override these with env vars:

- `MOCK_ADMIN_EMAIL`
- `MOCK_ADMIN_PASSWORD`


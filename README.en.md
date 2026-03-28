# RPG Demo Rebuild

## What This Is

This is a full-stack interactive narrative demo in a single repo. The product loop is intentionally short:

1. enter an English story seed
2. generate a preview
3. start an author job
4. publish into the library
5. open a story from the library
6. play it through natural-language turns

The project is now on the current product contract and runtime path described in the interface governance docs.

## Stack

- Backend: FastAPI + Pydantic + LangGraph
- Frontend: React 19 + TypeScript + Vite
- Storage: SQLite
- Identity: real cookie-session auth

Main backend domains:

- `rpg_backend/author/`
- `rpg_backend/library/`
- `rpg_backend/play/`
- `rpg_backend/benchmark/`

## Current State

- the real `author -> publish -> play` product loop works
- public library, private owned stories, and protected play sessions are wired correctly
- author jobs, play sessions, and author checkpoints survive restart
- deployment should remain single-host / single-backend-process for now

## Local Run

Copy the local config first:

```bash
cp .env.example .env
```

Canonical runtime configuration:

- `APP_GATEWAY_*`: unified text / embedding gateway configuration
- `APP_HELPER_GATEWAY_*`: dedicated helper-agent config for benchmark or future UI-agent helper calls, isolated from the primary runtime model
- `APP_ROSTER_ENABLED` / `APP_ROSTER_SOURCE_CATALOG_PATH` / `APP_ROSTER_RUNTIME_CATALOG_PATH`: character-roster runtime switch and catalog paths

Recommended text gateway config:

```env
APP_GATEWAY_BASE_URL=https://dashscope-us.aliyuncs.com/compatible-mode/v1
APP_GATEWAY_API_KEY=replace_me
APP_GATEWAY_MODEL=qwen3.5-flash
# Optional: route only play.* capabilities to a stronger model:
# APP_GATEWAY_PLAY_MODEL=qwen3.5-plus
# If the responses endpoint differs from chat_completions, add:
# APP_GATEWAY_RESPONSES_BASE_URL=https://dashscope-us.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1
```

Recommended independent embedding config:

```env
APP_ROSTER_ENABLED=true
APP_ROSTER_SOURCE_CATALOG_PATH=data/character_roster/catalog.json
APP_ROSTER_RUNTIME_CATALOG_PATH=artifacts/character_roster_runtime.json
APP_ROSTER_MAX_SUPPORTING_CAST_SELECTIONS=3
APP_GATEWAY_EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
APP_GATEWAY_EMBEDDING_API_KEY=replace_me
APP_GATEWAY_EMBEDDING_MODEL=gemini-embedding-001
APP_LOCAL_PORTRAIT_BASE_URL=http://127.0.0.1:8000
```

The same `APP_GATEWAY_BASE_URL / API_KEY / MODEL` can be used via either `responses` or `chat_completions`.
Transport selection now belongs to the caller script or gateway entrypoint, not a global env switch.
If your provider exposes a separate responses endpoint, add only `APP_GATEWAY_RESPONSES_BASE_URL`.

If you need to override the session-cache header explicitly, use `APP_GATEWAY_SESSION_CACHE_HEADER` / `APP_GATEWAY_SESSION_CACHE_VALUE`.

If you want a separate internal helper-agent model, add:

```env
APP_HELPER_GATEWAY_BASE_URL=https://api.openai.com/v1
APP_HELPER_GATEWAY_API_KEY=replace_me
APP_HELPER_GATEWAY_MODEL=gpt-5-mini
# If the helper responses endpoint differs from chat_completions, add:
# APP_HELPER_GATEWAY_RESPONSES_BASE_URL=https://api.openai.com/v1
```

Helper mode does not fall back to the main `APP_GATEWAY_*` runtime. When helper mode is enabled, `BASE_URL / API_KEY / MODEL` must all be set.
Benchmark / playtest agents directly reuse the same `APP_HELPER_GATEWAY_*` slot as the experimental provider.
If helper does not support `json_schema` structured output in `chat_completions`, the benchmark agent automatically falls back to the primary `APP_GATEWAY_*`.
The current `www.jnm.lol / gpt-5.4-mini` provider is only validated on `chat_completions`; do not configure a responses endpoint for it unless you have a confirmed working path.

Local portrait batch generation:

```env
PORTRAIT_IMAGE_API_KEY=replace_me
```

Backend:

```bash
pip install -e ".[dev]"
uvicorn rpg_backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

If your local SQLite/runtime artifacts are from an older schema, reset them instead of expecting compatibility repair:

```bash
python tools/reset_local_databases.py
rm -f artifacts/character_roster_runtime.json
python tools/character_roster_admin.py build
```

## Common Validation

Backend tests:

```bash
pytest -q
```

Frontend checks:

```bash
cd frontend
npm run check
```

Real HTTP smoke:

```bash
python tools/http_product_smoke.py --base-url http://127.0.0.1:8000
```

Smoke with benchmark diagnostics:

```bash
python tools/http_product_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --include-benchmark-diagnostics
```

To run the benchmark driver against the separate helper model:

```bash
python tools/play_benchmarks/live_api_playtest.py \
  --base-url http://127.0.0.1:8000 \
  --use-helper-agent \
  --agent-transport-style chat_completions
```

## Deploy

Production domain:

- `https://rpg.shehao.app`

AWS single-host deployment material:

- `deploy/aws_ubuntu/DEPLOY.md`
- `deploy/aws_ubuntu/.env.production.example`
- `deploy/aws_ubuntu/rpg-demo-backend.service`
- `deploy/aws_ubuntu/nginx-rpg-demo.conf`

## Related Docs

- `specs/interface_governance_20260319.md`
- `specs/interface_stability_matrix_20260319.md`
- `frontend/specs/FRONTEND_PRODUCT_SPEC.md`

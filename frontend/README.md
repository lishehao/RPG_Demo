# Frontend Workspace

This frontend is a `Vite + React + TypeScript` app for a real dual-track product:

- `Author Mode` on `/author/*`
- `Play Mode` on `/play/*`

## Route Summary

- `/login`: authentication gate
- `/author/stories`: story generation and story supply
- `/author/stories/:storyId`: draft detail and publish action
- `/play/library`: published story library
- `/play/sessions/:sessionId`: live play runtime

## Design Source

This UI continues from the self-authored Figma review file:

- [Ember Command UI Review](https://www.figma.com/design/H5Lw8e3kT7cpV4lzYDGwuP)

Current direction:

- `Author Mode`: control room / publishing cadence / structured content management
- `Play Mode`: runtime chamber / transcript-first / action deck

## Contract Inputs

- `../frontend_agent_contract.md`
- `src/shared/api/generated/backend-sdk.ts`

## Run

```bash
cd frontend
npm install
npm run dev
```

The Vite server runs on `http://localhost:5173` and proxies `/api/*` to `http://localhost:8000`.

## Build

```bash
cd frontend
npm run build
```

## Local Full-Stack Debug Loop

1. Start database migration:

```bash
python scripts/db_migrate.py upgrade head
```

2. Start worker:

```bash
uvicorn rpg_backend.llm_worker.main:app --host 127.0.0.1 --port 8100
```

3. Start backend:

```bash
uvicorn rpg_backend.main:app --host 127.0.0.1 --port 8000
```

4. Start frontend:

```bash
cd frontend
npm run dev
```

5. Open the app at `http://127.0.0.1:5173/login`

## Manual Verification Path

- Login with the configured admin credentials.
- Enter `Author Mode` on `/author/stories`.
- Generate a draft with `prompt_text` or `seed_text`.
- Open draft detail on `/author/stories/:storyId`.
- Publish the story.
- Move to `Play Mode` on `/play/library`.
- Start a session from the published version.
- In `/play/sessions/:sessionId`, run one button step and one free-text step.
- Refresh the page and confirm the timeline rebuilds from `GET /sessions/{session_id}/history`.

## Current MVP Boundaries

Implemented now:

- author draft generation
- author story list and draft detail
- publish for play
- published play library
- live runtime session with reload-safe history

Not implemented now:

- full visual story editor
- story diffing and branch management
- advanced author operations beyond generate / inspect / publish / handoff to play

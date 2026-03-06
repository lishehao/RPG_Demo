# Frontend Workspace

This frontend is a `Vite + React + TypeScript` app built against the mock backend contract.

## Product Modes

### Login

Route: `/login`

- Entry gate for admin authentication.
- Stores Bearer token and redirects into the product.

### Author Mode

Route: `/dashboard`

- Lightweight author workflow.
- Supports story generation, story list review, and session creation.
- Does **not** implement a full authoring studio.

### Play Mode

Route: `/sessions/:sessionId`

- Restores session metadata and full history.
- Displays narration timeline and surfaced actions.
- Supports both button actions and free-text directives.
- Keeps history stable after page reload.

## Route Summary

- `/login`: access layer
- `/dashboard`: author mode
- `/sessions/:sessionId`: play mode

## Design Source

This UI is based on the self-authored Figma-first review file:

- [Ember Command UI Review](https://www.figma.com/design/H5Lw8e3kT7cpV4lzYDGwuP)

Design baseline:

- `obsidian + parchment + ember` color direction
- expressive title typography
- mission-control shell for author flow
- timeline-first play surface for session runtime

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

## Local Debug Loop

1. Start backend:

```bash
python -m uvicorn rpg_backend.main:app --reload --port 8000
```

2. Start frontend:

```bash
cd frontend
npm run dev
```

3. Open the app at `http://localhost:5173/login`

4. Verify the current supported loop:

- login with `admin@test.com / password`
- enter `Author Mode` on `/dashboard`
- generate a story
- confirm the story appears in the library
- create a session
- enter `Play Mode` on `/sessions/:sessionId`
- trigger a button step
- trigger a free-text step
- refresh the session page and confirm history is restored

## Latest Audit Snapshot

Verified on March 6, 2026:

- login reaches `Author Mode` successfully
- `Author Mode` can generate a story, list it, and create a session
- `Play Mode` can execute button and free-text turns
- refreshing the session route restores narration history from `/sessions/{session_id}/history`
- current layout remains aligned with the existing Figma review file for `Login`, `Dashboard`, and `Session`

Observed residual issue:

- when entering the app without a valid token, the browser console can briefly show unauthorized `GET /stories` requests before the login surface settles; this does not block the current product flow but should be treated as follow-up polish rather than a documented feature

## Current Coverage

Implemented now:

- login
- lightweight author flow
- playable session runtime
- history restoration on reload
- structured error presentation

Not implemented now:

- full story editor
- story version management UI
- publish workflow UI
- advanced author operations beyond generate/list/launch

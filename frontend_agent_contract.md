# frontend_agent_contract.md

## 1. Overview

Frontend implements a two-mode admin product for generated RPG stories:

- `Author Mode`: create and launch stories from the dashboard.
- `Play Mode`: run an active session and inspect narration history.

Backend base URL:

```text
http://localhost:8000
```

All requests and responses use JSON.

### Mock backend semantics

- This backend is a mock contract server.
- Data is stored in process memory only.
- Restarting the backend clears stories, sessions, and histories.
- The current product supports a lightweight author workflow plus a playable runtime.
- The current product does **not** include a full author studio such as story editing, version editing, or publishing workflows.

## 2. Product Modes

### Access Layer

Route: `/login`

Purpose:

- Authenticate the admin user.
- Store Bearer token for protected routes.
- Redirect to `Author Mode` after success.

### Author Mode

Route: `/dashboard`

Purpose:

- Generate a story from `theme + difficulty`.
- List generated stories.
- Create a new session from a story.

Current scope:

- This is a **lightweight author mode**.
- It covers story generation, story library review, and session launch only.
- It does **not** cover story editing, draft comparison, asset management, or publishing controls.

API dependencies:

- `POST /stories/generate`
- `GET /stories`
- `POST /sessions`

### Play Mode

Route: `/sessions/{session_id}`

Purpose:

- Restore and display the full narration timeline.
- Show current available actions.
- Submit either `move_id` or `free_text`.
- Keep the session usable after reload.

API dependencies:

- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/history`
- `POST /sessions/{session_id}/step`

## 3. Route Map

| Route | Product role | Mode |
| --- | --- | --- |
| `/login` | access gate | entry |
| `/dashboard` | story generation + session launch | author |
| `/sessions/{session_id}` | live play surface + history timeline | play |

## 4. Authentication

Authentication header:

```text
Authorization: Bearer <token>
```

All endpoints except login require Bearer token.

### Login

`POST /admin/auth/login`

Request:

```json
{
  "email": "admin@test.com",
  "password": "password"
}
```

Response:

```json
{
  "token": "jwt_or_mock_token",
  "access_token": "jwt_or_mock_token",
  "token_type": "bearer"
}
```

## 5. Story APIs

### Generate story

`POST /stories/generate`

Request:

```json
{
  "theme": "fantasy",
  "difficulty": "medium"
}
```

Response:

```json
{
  "story_id": "uuid",
  "title": "Fantasy - Medium Quest",
  "published": true
}
```

### List stories

`GET /stories`

Response:

```json
{
  "stories": [
    {
      "story_id": "uuid",
      "title": "Fantasy - Medium Quest"
    }
  ]
}
```

## 6. Session APIs

### Create session

`POST /sessions`

Request:

```json
{
  "story_id": "uuid"
}
```

Response:

```json
{
  "session_id": "uuid"
}
```

### Get session

`GET /sessions/{session_id}`

Response:

```json
{
  "session_id": "uuid",
  "story_id": "uuid",
  "created_at": "2026-03-05T12:00:00Z",
  "state": "active"
}
```

### Get session history

`GET /sessions/{session_id}/history`

Response:

```json
{
  "history": [
    {
      "turn": 1,
      "narration": "You wake up in a forest.",
      "actions": [
        {
          "id": "look",
          "label": "Look around"
        },
        {
          "id": "walk",
          "label": "Walk forward"
        }
      ]
    }
  ]
}
```

### Step

`POST /sessions/{session_id}/step`

Request option A:

```json
{
  "move_id": "look"
}
```

Request option B:

```json
{
  "free_text": "I try to climb the tree"
}
```

## 7. Step Response Format

Response:

```json
{
  "turn": 3,
  "narration": "You see a small cabin.",
  "actions": [
    {
      "id": "enter_cabin",
      "label": "Enter the cabin"
    },
    {
      "id": "ignore",
      "label": "Ignore it"
    }
  ],
  "risk_hint": "low"
}
```

Stable fields:

- `turn`
- `narration`
- `actions`
- `risk_hint`

## 8. Error Envelope

All API errors return:

```json
{
  "error": {
    "code": "INVALID_MOVE",
    "message": "Move not allowed",
    "retryable": false,
    "request_id": "abc123"
  }
}
```

## 9. Behavior Matrix

| Behavior | Route | Mode | Current status |
| --- | --- | --- | --- |
| Admin login | `/login` | entry | supported |
| Generate story | `/dashboard` | author | supported |
| List stories | `/dashboard` | author | supported |
| Create session | `/dashboard` | author | supported |
| Show narration history | `/sessions/{session_id}` | play | supported |
| Show move buttons | `/sessions/{session_id}` | play | supported |
| Allow free text input | `/sessions/{session_id}` | play | supported |
| Auto scroll latest turn | `/sessions/{session_id}` | play | supported |
| Restore history after reload | `/sessions/{session_id}` | play | supported |
| Full story editing studio | none | author | not supported |
| Story version management UI | none | author | not supported |
| Publish workflow UI | none | author | not supported |

## 10. Audit Result

Latest audit baseline:

- Verified in local browser flow on March 6, 2026.
- `Author Mode` behavior verified: login, generate story, list stories, create session.
- `Play Mode` behavior verified: button step, free-text step, timeline rendering, reload recovery.
- Current documentation should treat these behaviors as implemented and stable against the current mock backend contract.

## 11. Design Source

Current UI design is a self-authored Figma-first implementation.

Visual baseline:

- Figma review file: [Ember Command UI Review](https://www.figma.com/design/H5Lw8e3kT7cpV4lzYDGwuP)
- Primary reviewed surfaces: `Login`, `Dashboard`, `Session`

Design intent:

- `obsidian + parchment + ember` palette
- dramatic mission-control framing
- lightweight glass panels and timeline-driven play surface

This design source is a review baseline, not an external template dependency.

## 12. Current Product Limits

- `Author Mode` is intentionally lightweight in the current implementation.
- The backend contract does not expose story editing or version lifecycle endpoints.
- Documentation should treat `Dashboard` as the current author surface, not as a full authoring studio.

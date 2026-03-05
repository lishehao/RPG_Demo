# frontend_agent_contract.md

## 1. Overview

Frontend should implement an admin UI for managing RPG sessions and playing generated stories.

Backend base URL:

```text
http://localhost:8000
```

All requests and responses use JSON.

### Mock backend semantics

- This backend is a mock contract server.
- Data is stored in process memory only.
- Restarting the backend clears stories, sessions, and histories.
- Suitable for UI development and API integration tests only, not for production gameplay.

## 2. Authentication

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

## 3. Story APIs

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

## 4. Session APIs

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

## 5. Step Response Format

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

`narration`, `actions`, and `risk_hint` are stable fields.

## 6. Error Envelope

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

## 7. UI Requirements

Frontend should implement:

- Login page
  - Admin login.
- Dashboard
  - Generate story
  - List stories
  - Create session
- Session page
  - Show narration history timeline
  - Show move buttons
  - Allow free text input
  - Auto scroll latest turn
  - Recover story history after page reload via `GET /sessions/{session_id}/history`


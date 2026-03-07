# frontend_agent_contract.md

## 1. Overview

Frontend implements a real two-track product on top of the DB-backed RPG backend:

- `Author Mode`: generate, inspect, and publish stories.
- `Play Mode`: browse published stories, start sessions, and play them through the live runtime.

Backend base URL:

```text
http://localhost:8000
```

All requests and responses use JSON.

## 2. Product Modes

### Access Layer

Route: `/login`

Purpose:

- Authenticate the admin user.
- Store Bearer token.
- Redirect to the author suite.

### Author Mode

Routes:

- `/author/stories`
- `/author/stories/{story_id}`

Purpose:

- Generate a DB-backed story draft with the real LLM pipeline.
- List story supply across drafts and published versions.
- Inspect draft payload.
- Publish a story version so Play Mode can consume it.

Current scope:

- This is an MVP author track.
- It supports generation, story list, story detail, publish, and handoff into Play.
- It does **not** implement a full visual story editor, diffing, or version branch management.

### Play Mode

Routes:

- `/play/library`
- `/play/sessions/{session_id}`

Purpose:

- Browse only published stories.
- Create a playable session from a published version.
- Display narration timeline and action deck.
- Submit both button actions and free-text directives.
- Restore play history after reload.

## 3. Route Map

| Route | Product role | Mode |
| --- | --- | --- |
| `/login` | access gate | entry |
| `/author/stories` | author list + generation | author |
| `/author/stories/{story_id}` | draft detail + publish | author |
| `/play/library` | published story library | play |
| `/play/sessions/{session_id}` | live runtime | play |

## 4. Authentication

Authentication header:

```text
Authorization: Bearer <token>
```

All business endpoints except login require Bearer token.

### Login

`POST /admin/auth/login`

Request:

```json
{
  "email": "admin@example.com",
  "password": "admin123456"
}
```

Response:

```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "expires_at": "timestamp",
  "user": {
    "id": "uuid",
    "email": "admin@example.com",
    "role": "admin",
    "is_active": true,
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "last_login_at": "timestamp"
  }
}
```

## 5. Author APIs

### Create raw draft

`POST /stories`

Request:

```json
{
  "title": "Signal Draft",
  "pack_json": {}
}
```

Response:

```json
{
  "story_id": "uuid",
  "status": "draft",
  "created_at": "timestamp"
}
```

### Generate draft with LLM

`POST /stories/generate`

Request:

```json
{
  "prompt_text": "A city-wide signal breach with a pyrrhic ending.",
  "target_minutes": 10,
  "npc_count": 4,
  "style": "tense, cinematic, strategic",
  "publish": false
}
```

Response:

```json
{
  "status": "ok",
  "story_id": "uuid",
  "version": null,
  "pack": {},
  "pack_hash": "sha256",
  "generation": {
    "mode": "prompt"
  }
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
      "title": "Generated: Signal Draft",
      "created_at": "timestamp",
      "has_draft": true,
      "latest_published_version": 1,
      "latest_published_at": "timestamp"
    }
  ]
}
```

### Get draft detail

`GET /stories/{story_id}/draft`

Response:

```json
{
  "story_id": "uuid",
  "title": "Generated: Signal Draft",
  "created_at": "timestamp",
  "draft_pack": {},
  "latest_published_version": 1,
  "latest_published_at": "timestamp"
}
```

### Patch draft fields

`PATCH /stories/{story_id}/draft`

Request:

```json
{
  "changes": [
    {
      "target_type": "story",
      "field": "title",
      "value": "Whispers in the Veilwood"
    },
    {
      "target_type": "beat",
      "target_id": "b1",
      "field": "title",
      "value": "The First Silence Breaks"
    },
    {
      "target_type": "scene",
      "target_id": "sc2",
      "field": "scene_seed",
      "value": "Investigate the broken vow under strict silence."
    },
    {
      "target_type": "npc",
      "target_id": "Kael",
      "field": "red_line",
      "value": "I will not falsify the ritual record."
    },
    {
      "target_type": "opening_guidance",
      "field": "intro_text",
      "value": "The city enters a dangerous silence."
    },
    {
      "target_type": "opening_guidance",
      "field": "starter_prompt_1",
      "value": "I inspect the damaged ward first."
    }
  ]
}
```

Response:

```json
{
  "story_id": "uuid",
  "title": "Whispers in the Veilwood",
  "created_at": "timestamp",
  "draft_pack": {},
  "latest_published_version": 1,
  "latest_published_at": "timestamp"
}
```

Notes:
- `target_type=story` supports `title`, `description`, `style_guard`, `input_hint`
- `target_type=beat` supports `title`
- `target_type=scene` supports `scene_seed`
- `target_type=npc` supports `red_line`
- `target_type=opening_guidance` supports `intro_text`, `goal_hint`, `starter_prompt_1`, `starter_prompt_2`, `starter_prompt_3`
- Invalid target/field combinations return `422 validation_error`
- Missing beat/scene/npc targets return `404 draft_target_not_found`

### Publish version

`POST /stories/{story_id}/publish`

Response:

```json
{
  "story_id": "uuid",
  "version": 1,
  "published_at": "timestamp"
}
```

### Get published pack

`GET /stories/{story_id}?version=1`

Response:

```json
{
  "story_id": "uuid",
  "version": 1,
  "pack": {}
}
```

## 6. Play APIs

### Create session from published story

`POST /sessions`

Request:

```json
{
  "story_id": "uuid",
  "version": 1
}
```

Response:

```json
{
  "session_id": "uuid",
  "story_id": "uuid",
  "version": 1,
  "scene_id": "sc1",
  "state_summary": {
    "events": 0,
    "inventory": 0,
    "cost_total": 0
  },
  "opening_guidance": {
    "intro_text": "text",
    "goal_hint": "text",
    "starter_prompts": ["text", "text", "text"]
  }
}
```

### Get session state

`GET /sessions/{session_id}`

Response:

```json
{
  "session_id": "uuid",
  "scene_id": "sc1",
  "beat_progress": {},
  "ended": false,
  "state_summary": {
    "events": 0,
    "inventory": 0,
    "cost_total": 0
  },
  "opening_guidance": {
    "intro_text": "text",
    "goal_hint": "text",
    "starter_prompts": ["text", "text", "text"]
  }
}
```

### Get session history

`GET /sessions/{session_id}/history`

Response:

```json
{
  "session_id": "uuid",
  "history": [
    {
      "turn_index": 1,
      "scene_id": "sc2",
      "narration_text": "Narration text.",
      "recognized": {
        "interpreted_intent": "look around",
        "move_id": "scan_signal",
        "confidence": 0.91,
        "route_source": "llm"
      },
      "resolution": {
        "result": "You uncover the first clue.",
        "costs_summary": "none",
        "consequences_summary": "none"
      },
      "ui": {
        "moves": [
          {
            "move_id": "global.help_me_progress",
            "label": "Push forward",
            "risk_hint": "steady but slow"
          }
        ],
        "input_hint": "Describe your next move"
      },
      "ended": false
    }
  ]
}
```

### Step runtime

`POST /sessions/{session_id}/step`

Request:

```json
{
  "client_action_id": "step-001",
  "input": {
    "type": "button",
    "move_id": "global.help_me_progress"
  },
  "dev_mode": false
}
```

or

```json
{
  "client_action_id": "step-002",
  "input": {
    "type": "text",
    "text": "I inspect the reactor seals"
  },
  "dev_mode": false
}
```

Response:

```json
{
  "session_id": "uuid",
  "version": 1,
  "scene_id": "sc3",
  "narration_text": "Narration text.",
  "recognized": {
    "interpreted_intent": "inspect reactor",
    "move_id": "scan_signal",
    "confidence": 0.88,
    "route_source": "llm"
  },
  "resolution": {
    "result": "You gain partial clarity.",
    "costs_summary": "time +1",
    "consequences_summary": "pressure rises"
  },
  "ui": {
    "moves": [
      {
        "move_id": "stabilize_core",
        "label": "Stabilize Core",
        "risk_hint": "politically safe: spends resources to preserve trust"
      }
    ],
    "input_hint": "Describe your next move"
  }
}
```

## 7. Error Envelope

All API errors return:

```json
{
  "error": {
    "code": "service_unavailable",
    "message": "llm provider misconfigured",
    "retryable": false,
    "request_id": "abc123",
    "details": {}
  }
}
```

## 8. UI Behavior Matrix

| Behavior | Route | Mode | Current target |
| --- | --- | --- | --- |
| Login | `/login` | entry | required |
| Generate story draft | `/author/stories` | author | required |
| View story supply | `/author/stories` | author | required |
| Inspect draft detail | `/author/stories/{story_id}` | author | required |
| Publish story | `/author/stories/{story_id}` | author | required |
| Browse published stories | `/play/library` | play | required |
| Start session from published version | `/play/library` | play | required |
| Show narration timeline | `/play/sessions/{session_id}` | play | required |
| Show move buttons | `/play/sessions/{session_id}` | play | required |
| Allow free text input | `/play/sessions/{session_id}` | play | required |
| Restore history after reload | `/play/sessions/{session_id}` | play | required |
| Full visual story editor | none | author | not in MVP |

## 9. Design Source

Visual review source remains the Figma-first review file:

- [Ember Command UI Review](https://www.figma.com/design/H5Lw8e3kT7cpV4lzYDGwuP)

The next phase expands it into separate `Author Suite` and `Play Suite` surfaces.

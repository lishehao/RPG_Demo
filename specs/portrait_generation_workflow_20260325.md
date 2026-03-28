# Portrait Generation Workflow

## Purpose

This document defines the current portrait generation workflow for RPG_Demo.

It exists to keep one operational truth for:

- prompt and visual constraints
- role-content inputs
- batch generation flow
- neutral-as-reference consistency flow
- review and regeneration flow

## Sources Of Truth

Prompt and visual-generation source of truth:

- `/Users/lishehao/Desktop/Project/RPG_Demo/rpg_backend/portraits/prompting.py`

Display crop and grading source of truth:

- `/Users/lishehao/Desktop/Project/RPG_Demo/frontend/src/app/styles.css`

Human-readable style summary:

- `/Users/lishehao/Desktop/Project/RPG_Demo/artifacts/portraits/cast_content/ui_portrait_style_reference.md`

Template-aligned role truth:

- `/Users/lishehao/Desktop/Project/RPG_Demo/artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json`
- `/Users/lishehao/Desktop/Project/RPG_Demo/artifacts/portraits/cast_content/template_role_matrix.md`

## Mainline Flow

### 1. Role truth

Generate or maintain the role source first:

- `template_role_drafts_v2.json` is the live LLM draft layer
- `template_aligned_cast_pack_30_v2.json` is the finalized role-content layer
- `template_role_matrix.md` is the human-readable matrix

The finalized role pack must stay roster-source-compatible and must not include `portrait_url`.

### 2. Plan

Build a plan for one template trio or a selected subset:

```bash
python tools/roster_portrait_plan.py \
  --catalog-path artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json \
  --character-id <id> \
  --character-id <id> \
  --character-id <id> \
  --variant negative \
  --variant neutral \
  --variant positive \
  --candidates-per-variant 1 \
  --output-dir artifacts/portraits/template_trials/<template_name> \
  --plan-path artifacts/portraits/template_trials/<template_name>/portrait_plan.json
```

Current default batch structure is:

- `3 roles`
- `3 variants`
- `1 candidate per variant`

### 3. Generate

Generate images from the plan:

```bash
set -a && source .env && set +a
python tools/roster_portrait_generate.py \
  --plan-path artifacts/portraits/template_trials/<template_name>/portrait_plan.json \
  --request-timeout-seconds 180
```

### 4. Review

Generate a review sheet for UI-agent or human review:

```bash
python tools/template_portrait_review_sheet.py \
  --cast-pack-path artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json \
  --trials-root artifacts/portraits/template_trials \
  --screening-json artifacts/portraits/template_trials/screening_initial.json \
  --output-path artifacts/portraits/template_trials/review_sheet.md
```

Optional contact sheets live under:

- `/Users/lishehao/Desktop/Project/RPG_Demo/artifacts/portraits/template_trials/contact_sheets`

### 5. Regenerate

Regenerate only the roles or variants that failed review.

Do not rerun the whole template unless:

- the trio is fundamentally miscast
- the neutral identity is unusable
- the prompt policy changed in a way that invalidates all 3 variants

## Neutral-As-Reference Consistency Flow

The current consistency flow is:

1. Generate `neutral`
2. Write a stable neutral alias:
   - `character_id/neutral/reference_<candidate_index>.png`
3. Use that neutral alias as the reference image for:
   - `negative`
   - `positive`

This is the current behavior in:

- `/Users/lishehao/Desktop/Project/RPG_Demo/tools/roster_portrait_plan.py`
- `/Users/lishehao/Desktop/Project/RPG_Demo/tools/roster_portrait_generate.py`

## Variant Policy

### Neutral

- institutional baseline
- composed public-facing restraint
- balanced expression
- should act as the reference identity image

### Negative

- expression must be visibly more guarded than neutral
- defensive hand or shoulder posture is preferred
- background can be darker, tighter, more oppressive
- wardrobe can be more closed, layered, protected

### Positive

- expression must be visibly more open than neutral
- positive environment must read as a different scene or a materially different background composition
- it is not enough to reuse the neutral room with warmer light
- wardrobe can open up or soften, but face identity must stay stable

## Review Standard

Per image review fields:

- `template_fit`
- `role_distinctness`
- `silhouette_readability`
- `face_crop_safety`
- `style_lock_match`
- `expression_match`
- `overall_recommendation`
- `initial_screening_note`
- `ui_agent_notes`

Allowed recommendations:

- `keep`
- `regenerate`
- `needs_ui_review_attention`

## Secondary Tools

There is also an `author_cast_portrait_*` toolchain for completed author jobs:

- `/Users/lishehao/Desktop/Project/RPG_Demo/tools/author_cast_portrait_plan.py`
- `/Users/lishehao/Desktop/Project/RPG_Demo/tools/author_cast_portrait_generate.py`
- `/Users/lishehao/Desktop/Project/RPG_Demo/tools/author_cast_portrait_validate.py`

That path is not the current mainline for template portrait production.

Current mainline is:

- template role matrix
- template-aligned cast pack
- roster portrait plan/generate/review
- template portrait batch runner/review sheet

## Cleanup Rule

Keep:

- current `v2` role pack
- current matrix
- current review sheet
- latest screening JSON
- latest reference-consistency sheet for any actively discussed sample

Delete:

- superseded cast packs and indices
- old rerun sheets for the same sample
- one-off debug or trial JSONs that are no longer part of the current chain
- generated junk that points at outdated prompt behavior

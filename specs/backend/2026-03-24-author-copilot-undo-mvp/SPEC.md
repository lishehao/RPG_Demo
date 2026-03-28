# Author Copilot Undo MVP Spec

## Purpose

Add a minimal, product-facing undo capability for Author Copilot so the frontend can offer a real `Undo` action after `Apply changes`.

This pass is intentionally narrow. It should solve:

- "I applied a Copilot suggestion and immediately want to revert it."
- "I refreshed Author Studio and still need to undo the most recent applied Copilot change."

It should **not** become a full revision-history system.

## Fixed Decisions

- Scope is **backend-only** for this pass. Do not modify frontend files.
- Undo is available only for **completed author jobs before publish**.
- Undo is proposal-based, not free-form:
  - route: `POST /author/jobs/{job_id}/copilot/proposals/{proposal_id}/undo`
- Undo only supports the **latest still-current applied proposal** for the job.
- Undo must restore the **exact pre-apply canonical draft state**:
  - `bundle`
  - `summary`
  - `preview`
  - `copilot_workspace_snapshot`
- Undo must reject drift:
  - if the current editor revision no longer matches the applied proposal's resulting revision, undo is no longer available.
- `AuthorCopilotProposalResponse.status` gains a new stable value:
  - `undone`
- `GET /author/jobs/{job_id}/editor-state` remains the canonical completed-state route and should expose whether an undoable latest applied proposal exists.

## Required End State

- Applying a Copilot proposal stores enough internal data to restore the previous draft exactly.
- Calling the undo route on the latest applied proposal restores the exact prior editor state and returns the refreshed `editor_state`.
- After undo:
  - the target proposal is no longer considered active/applied
  - `GET .../editor-state` no longer advertises that proposal as undoable
- Refresh-safe undo must be possible through editor-state metadata, not only through transient apply response state.
- Published jobs still reject Copilot editing and undo.
- Older applied proposals must not remain undoable once the draft has moved on.

## Public Contract Changes

### 1. New route

- `POST /author/jobs/{job_id}/copilot/proposals/{proposal_id}/undo`

Response model:

- `AuthorCopilotUndoResponse`
  - `proposal: AuthorCopilotProposalResponse`
  - `editor_state: AuthorEditorStateResponse`

Semantics:

- target proposal must belong to the job and current actor
- target proposal must currently be the latest undoable applied proposal for that job
- successful undo restores the prior canonical draft and returns the new editor state

### 2. Proposal response additions

`AuthorCopilotProposalResponse.status` must allow:

- `draft`
- `applied`
- `superseded`
- `undone`

Additive fields are allowed if needed, but do not redesign the proposal payload.

### 3. Editor-state additive metadata

Extend `AuthorCopilotWorkspaceView` with a small additive undo block so the frontend can recover undo availability after refresh:

- `undo_available: bool = False`
- `undo_proposal_id: str | None = None`
- `undo_request_summary: str | None = None`

Rules:

- `undo_available` is `true` only when the current draft revision still corresponds to the latest applied Copilot proposal and that proposal can still be undone.
- `undo_proposal_id` points to that proposal.
- `undo_request_summary` is short, human-facing copy derived from the applied proposal already stored on the backend.

Keep this additive and editor-facing. Do not invent a separate history feed.

### 4. Error codes

Add these explicit product-facing errors:

- `author_copilot_undo_stale`
  - current editor revision has moved past the target applied proposal
- `author_copilot_proposal_not_undoable`
  - proposal is not in an undoable state (`draft`, `superseded`, `undone`, or otherwise invalid for undo)

Existing behavior must still apply:

- `author_copilot_job_already_published`
- `author_copilot_proposal_not_found`
- owner scoping / 404 behavior

## Required Implementation Areas

- `rpg_backend/author/contracts.py`
  - add undo response model
  - extend proposal status
  - extend `AuthorCopilotWorkspaceView` undo metadata
- `rpg_backend/main.py`
  - add undo route
- `rpg_backend/author/jobs.py`
  - store apply-time undo baseline
  - implement undo route/service logic
  - compute latest undoable proposal metadata for editor-state
  - reject stale / non-undoable states cleanly
- `rpg_backend/author/storage.py`
  - extend `author_copilot_proposals` persistence for undo baseline and applied revision tracking
- `tests/test_author_product_api.py`
  - add focused API coverage for undo

## Storage / Persistence Direction

Keep this incremental and proposal-local.

Do **not** introduce a new top-level revision-history subsystem.

Recommended persistence shape on `author_copilot_proposals`:

- add `applied_revision TEXT`
  - the post-apply revision written to the job when the proposal was applied
- add `undone_at TEXT`
- add `undo_snapshot_json TEXT`
  - internal-only snapshot containing the exact pre-apply state needed to restore:
    - `bundle`
    - `summary`
    - `preview`
    - `copilot_workspace_snapshot`

This is intentionally internal storage. It does not need to be mirrored 1:1 into the public proposal response.

## Behavioral Rules

### Apply

When applying a proposal:

- capture the exact pre-apply draft state into the proposal's undo snapshot
- compute and persist the resulting `applied_revision`
- mark proposal status `applied`

### Undo

Undo succeeds only if:

- the proposal status is `applied`
- the job is still editable by Copilot
- the job's current revision exactly equals the proposal's stored `applied_revision`
- the proposal has a valid undo snapshot

Undo performs:

- restore the stored pre-apply draft state into the author job record
- update the job revision/timestamp to the undo operation time
- mark proposal status `undone`
- persist `undone_at`
- return the restored `editor_state`

### Editor-state undo metadata

`GET /author/jobs/{job_id}/editor-state` should compute the latest undoable proposal by checking:

- same job
- same owner
- status `applied`
- `applied_revision == record.updated_at.isoformat()`

If none match, undo metadata must be clear / false.

## Acceptance Criteria

1. A newly applied proposal can be undone through the new undo route.
2. Undo restores the exact prior editor state, not a heuristic reconstruction.
3. Refresh-safe UI support exists through `editor-state.copilot_view.undo_*`.
4. If a later edit changed the draft revision, undo on the older proposal returns `author_copilot_undo_stale`.
5. Draft, superseded, or already-undone proposals return `author_copilot_proposal_not_undoable`.
6. Published jobs still reject undo with the existing publish lock behavior.
7. No frontend files are changed in this pass.

## Required Tests

- happy path:
  - apply proposal
  - undo proposal
  - assert restored editor-state content matches pre-apply draft
- refresh-safe metadata:
  - after apply, `GET .../editor-state` exposes `undo_available=true` and the right proposal id/summary
  - after undo, the metadata clears
- stale drift:
  - apply proposal A
  - apply or otherwise change draft again
  - undo A returns `author_copilot_undo_stale`
- invalid states:
  - undo draft proposal -> `author_copilot_proposal_not_undoable`
  - undo superseded proposal -> `author_copilot_proposal_not_undoable`
  - undo already-undone proposal -> `author_copilot_proposal_not_undoable`
- publish guard:
  - published job rejects undo
- persistence:
  - reload service/storage and verify undo still works for the latest applied proposal

## Explicit Non-Goals

- no redo
- no arbitrary multi-step undo stack
- no generic job revision browser
- no frontend implementation in this pass
- no new benchmark-only route

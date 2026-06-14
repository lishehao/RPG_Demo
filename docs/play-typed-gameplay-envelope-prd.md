# Tiny Stories Typed Gameplay Envelope PRD

Status: design review for Pass 3D. No app behavior is implemented here.

Baseline: Pass 3B added a UI-derived gameplay envelope. Pass 3C added optional backend-derived `gameplay_envelope` fields on story history and turn advance responses. The 3C backend seam is useful, but it is still mostly a deterministic projection from goals, turn count, NPC pulse, inventory deltas, and option text.

## Recommendation

Do not make the whole gameplay envelope a strict live LLM output yet. The next pass should add a small live turn metadata block inside the existing `narrative.advance_turn` response shape, then let the backend validate, merge, and downgrade it into the current optional `GameplayEnvelope`.

The reason is practical: the backend already owns stable state, backward compatibility, and recovery. The LLM should only supply semantic labels it is best positioned to know after writing the turn: what changed, why it changed, which clue or opportunity became relevant, and how the next actions differ. Time, objective, inventory count, source labels, and fallback layers should remain backend-owned.

Recommended next pass: **3E Live Turn Metadata Enrichment**.

## 1. Product Goal

The typed gameplay envelope should make Play feel less like "prose plus buttons" and more like a readable game loop:

- Clearer goal: the player should know the current episode promise without rereading the whole opening.
- Visible consequences: after a move, the UI should show what shifted, not only narrate it.
- Clue and opportunity unlocks: when a clue matters, it should become a visible resource.
- NPC state changes: room characters should feel reactive and usable.
- Pressure movement: time, public pressure, danger, trust, or similar tracks should move legibly.
- Next-action relevance: the next action set should feel caused by the last move and current state.

The typed envelope should improve the signal around the latest turn. It should not attempt to become a full simulation engine in one pass.

## 2. Field Ownership

| Category | Owner | Reason |
| --- | --- | --- |
| `objective` / episode goal | Backend first, LLM only at template/opening creation | Goals already exist in `player_goals`, player role objective, and seed/title. Letting every turn rewrite the goal risks drift. LLM can suggest a short current-stage objective later, but not replace the episode objective. |
| Time / turn budget | Backend only | Turn count and budget are exact. LLM should not output time counters. |
| Pressure tracks | Backend-owned structure, LLM may supply semantic deltas | Backend should maintain track ids and bounds. LLM can label why pressure rose or opened this turn. |
| NPC/person state changes | LLM turn output plus backend validation | `npc_pulse` already comes from turn generation and is validated against cast ids. This is a good existing typed channel. Backend should keep validating ids and shifts. |
| Evidence/clue/opportunity unlocks | Hybrid: LLM proposes, backend validates/persists through inventory/opportunity fields | `inventory_delta` is already typed and walked on read. Add opportunity metadata only as optional bounded fields. Backend should reject empty, duplicate, or implausible entries. |
| Action forecast chips | Backend deterministic first, LLM optional hint later | Forecasts must be visible before submit. Current options already contain labels/hints. Backend/frontend heuristics are safer for the first forecast layer. LLM forecast hints can be added only if generated with the next options and validated by count. |
| Resolved impact chips | LLM semantic proposal, backend merged with deterministic pulse/inventory signals | The LLM knows the narrative reason. Backend should convert accepted items into player-facing chips and fall back to pulse/inventory if the LLM omits them. |
| Next-action reasoning/context | LLM soft metadata, reviewer-visible diagnostics only at first | Useful for quality review and future UI, but risky to expose as a large prose block. Keep it short and sanitized. |
| Advisor hints | Separate advisor/person system, not part of primary turn envelope yet | Mixing advisor advice into every turn would blur Play speaker roles and add cost. |
| Inner motive effects | Backend persistence plus LLM semantic impact | The player diary/motive already reaches the turn generator. A live metadata field may mark `motive_acknowledged`, but the backend should not claim a motive changed state unless the turn text or pulse supports it. |

Critical point: the LLM should not own durable counters or source truth. It should supply bounded semantic annotations around the prose it just generated.

## 3. Minimal Typed Envelope Schema

Keep the existing optional `gameplay_envelope` response field. Add a separate internal turn-generation metadata payload, parsed and normalized by the backend. Do not expose raw provider payloads to the frontend.

### LLM Turn Metadata Candidate

This is not a new public API contract by itself. It is an optional block returned by `advance_turn` generation and parsed server-side.

```ts
type TurnGameplayMetadataV1 = {
  state_deltas?: Array<{
    label: string            // max 64 chars
    tone: "gain" | "cost" | "unlock" | "shift"
    target?: "pressure" | "time" | "npc" | "evidence" | "opportunity" | "motive"
    npc_id?: string          // valid cast id only when target is npc
    confidence?: "low" | "medium" | "high"
  }>                         // max 5

  clue_unlocks?: Array<{
    id?: string              // optional stable slug, server may generate
    title: string            // max 48 chars
    summary?: string         // max 120 chars
    state?: "discovered" | "usable"
    supports_option_index?: number
  }>                         // max 3

  opportunity_unlocks?: Array<{
    id?: string
    title: string            // max 48 chars
    summary?: string         // max 120 chars
    supports_option_index?: number
  }>                         // max 3

  next_action_context?: Array<{
    option_index: number
    reason: string           // max 100 chars
  }>                         // max 3, optional reviewer/QA signal first

  motive_effect?: {
    acknowledged: boolean
    label?: string           // max 64 chars
  }
}
```

### Public Response Envelope

Keep the current public shape and add only optional fields if they survive backend normalization:

```ts
type GameplayEnvelope = {
  source: "backend" | "live_enriched" | "ui-derived"
  objective?: string
  tracks?: GameplayPressureTrack[]       // max 6
  action_forecasts?: GameplayChip[][]    // max options x 3 chips
  impact?: GameplayChip[]                // max 6
  opportunities?: GameplayChip[]         // max 6
  confidence?: "derived" | "mixed" | "live"
}
```

`source="live_enriched"` means the backend accepted at least one live metadata item and merged it with backend-owned tracks. It does not mean the entire envelope came from the LLM.

For backward compatibility, existing clients can ignore unknown optional fields. New clients must keep treating missing fields as normal.

## 4. Provider Output Strictness Decision

Ask the live LLM to produce metadata now, but only as a soft optional block in the existing turn JSON, not as a hard requirement for turn success.

Recommended output contract for 3E:

- Keep current required fields: `passage`, `options`, `npc_pulse`.
- Keep current optional `inventory_delta`.
- Add optional `gameplay_metadata`.
- If `gameplay_metadata` is absent or invalid, the turn still succeeds.
- Backend validates and clips every item before it can reach `gameplay_envelope`.

Do not make the whole turn fail because `gameplay_metadata` is malformed. The passage and options are more important to player continuity.

Risks:

- Malformed output: manageable if metadata is optional and parsed with tolerant validators.
- Creative quality degradation: real risk if the prompt overemphasizes state bookkeeping. Keep the metadata prompt short and subordinate.
- Latency/cost: avoid a second LLM call. Piggyback on the existing `narrative.advance_turn` call.
- Fallback complexity: if the turn falls back, the envelope should return backend-derived data, not claim live enrichment.
- Schema drift: version metadata as `gameplay_metadata_v1` or include `schema_version: "gameplay_metadata.v1"` if needed.

Do not use a separate post-processing LLM call in 3E. It doubles cost and latency before proving that player-visible value justifies it.

## 5. Failure And Fallback Model

Layering should be explicit:

1. Backend exact state: turn count, budget, template/player goal, role assets, current inventory, persisted messages.
2. Live metadata accepted from the turn response: semantic deltas, clue/opportunity titles, next-action context.
3. Backend deterministic derivation: NPC pulse, inventory deltas, played leverage, option keyword forecasts.
4. UI-derived fallback: current 3B/3C frontend derivation when the backend envelope is missing or invalid.

When live metadata is missing:

- Return `source="backend"` if backend derivation exists.
- Return no error to the player.
- Record safe reviewer diagnostics such as `metadata_missing` or `metadata_invalid`, count of accepted items, and reason category.

When live metadata contradicts backend truth:

- Backend truth wins.
- Drop invalid npc ids, impossible option indices, duplicate clues, empty labels, and overlong text.
- Do not show raw rejected JSON to players.

When confidence is low:

- Still use backend tracks and deterministic pulse/inventory chips.
- Avoid rendering new clue/opportunity cards based only on weak metadata.
- Prefer a generic impact chip such as "Room pressure shifted" over an invented specific claim.

Player-facing UI must never show provider, model, API, schema, token, debug, raw JSON, judge internals, or source diagnostics. Reviewer mode may show sanitized counts and statuses.

## 6. Implementation Plan

### Pass 3E Scope

1. Add backend internal models for `TurnGameplayMetadataV1`.
2. Update the `advance_turn` prompt contract to ask for optional `gameplay_metadata` after the required narrative fields.
3. Add tolerant parser functions:
   - `_parse_gameplay_metadata(raw, valid_npc_ids, option_count)`
   - `_merge_gameplay_metadata_into_envelope(metadata, backend_envelope)`
4. Update `TurnResult` to carry accepted metadata or accepted chips.
5. Update service response builder:
   - generate the current backend envelope first;
   - merge accepted live metadata into `impact` and `opportunities`;
   - emit `source="live_enriched"` only when at least one live item is accepted.
6. Keep frontend source priority:
   - `live_enriched` or `backend` first;
   - `ui-derived` fallback second.
7. Update tests:
   - valid metadata appears as impact/opportunity chips;
   - invalid metadata is dropped without failing the turn;
   - missing metadata still returns backend envelope;
   - unknown npc id and out-of-range option index are rejected;
   - no player-facing technical leakage;
   - current QA routes still work.

### Migration Strategy

- Keep `gameplay_envelope` optional.
- Keep existing `GameplayEnvelope` fields compatible.
- Add `source="live_enriched"` as an additive source value.
- Existing clients that only understand `backend` or ignore `source` should still render usable data if fields remain the same.
- Do not remove the frontend heuristic derivation.
- Do not alter existing QA routes.

### Browser And Live Validation

Fixture validation:

- `#/qa/play-gameplay-loop`: unchanged full loop.
- `#/qa/play-action`: selected to pending to resolved.
- `#/qa/play-action?scenario=long-history`: Back-to-move and 390px no overflow.

Live validation:

- Use configured local backend health.
- Run one generated or existing live session.
- Submit 2 bounded live turns.
- Verify at least one turn returns `data-gameplay-envelope-source="live_enriched"` if metadata is accepted.
- Verify the same route still works if metadata is absent by using a controlled mock or test gateway.
- Capture telemetry for live calls, but do not print secrets.

Bounded live calls are necessary for 3E because prompt changes can affect narrative quality. Keep the cap to opening plus 2 play turns unless a failure needs one targeted retry.

## 7. Acceptance And Kill Criteria

### Acceptance

- Normal Play shows a backend or live-enriched typed envelope without raw JSON or technical labels.
- At least one live turn produces accepted semantic impact or opportunity metadata that is more specific than current keyword derivation.
- The player can see: objective, pressure tracks, action forecasts, pending receipt/reaction, resolved impact, and any clue/opportunity unlock.
- Existing interaction contracts are preserved: in-place action expansion, motive panel replacement, advisor rail, retry banner, long-history Back-to-move.
- Missing or malformed metadata does not break turn completion.
- Tests prove valid, missing, malformed, and contradictory metadata paths.
- Browser smoke shows no leakage and no horizontal overflow around 390px where viewport control works.

### Kill Criteria

Stop the live metadata approach and continue deterministic backend enrichment if:

- Metadata prompt noticeably degrades passage quality or option relevance.
- Live turns start failing because metadata is treated as required.
- Accepted metadata frequently contradicts backend facts, cast ids, or option indices.
- Latency rises materially because a second call is introduced or repair loops become common.
- The UI needs to explain source/confidence to ordinary players to make the feature understandable.
- Reviewer diagnostics show repeated invalid metadata with no clear player-visible benefit.

If any kill criterion triggers, the safer path is to improve deterministic backend derivation first: richer option-family classification, persisted clue ids from `inventory_delta`, NPC pulse trend summaries, and backend-owned pressure track calculations.

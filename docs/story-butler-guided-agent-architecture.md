# Story Butler guided-agent architecture note

This note records the product/R&D pattern for the Create Story Butler. It is not
a new UI spec.

## References distilled

- OpenAI Agents SDK sessions
  (https://openai.github.io/openai-agents-js/guides/sessions/) model
  conversation memory as a session layer that
  prepends prior items, persists new user/assistant items, and can compact long
  history into a shorter equivalent history. Tiny Stories uses the same shape:
  recent transcript plus a compact state object instead of unbounded raw chat.
- Microsoft Bot Framework waterfall dialogs
  (https://learn.microsoft.com/en-us/azure/bot-service/bot-builder-concept-waterfall-dialogs)
  model guided collection as steps
  that prompt once, wait for the user's answer, and carry state between steps.
  Tiny Stories keeps this one-question rhythm, but lets a policy layer choose
  the next focus rather than using a fixed linear form.

## Implemented pattern

Create uses a hybrid graph:

1. `advance_story_guide_loop` applies deterministic safety, privacy, slot, and
   readiness gates.
2. The Story Butler context compressor updates `StoryGuideCompressedContext`:
   scene summary, player role, cast/factions, pressure, constraints, tone, open
   questions, confirmed facts, superseded facts, recent turns, and readiness.
3. The planner selects a voice skill such as `role_focus`, `cast_focus`,
   `pressure_focus`, `boundary_redirect`, or `brief_readiness`.
4. The live reply call receives only the compact context, current user message,
   previous assistant reply, selected skill, and deterministic contract.
5. Normal Create UI renders only the natural assistant reply and pending process
   rows. It does not render internal ledgers, prompt text, provider/model/API
   labels, token counts, raw JSON, or chain-of-thought.

## Operating rules

- The compact context is the source of continuity. `acceptedTurns` remains for
  seed assembly, but the model should not receive an ever-growing raw transcript.
- Corrections supersede older facts. Older facts may remain in
  `rejected_or_changed_facts`, never as equal truth.
- `you can decide for me` is treated as delegation for the current missing
  field, not as a reason to repeat the same question.
- Home default story seeding uses the same Story Butler -> Story Brief ->
  template chain and therefore benefits from the same context/planner layer.
- Final preview validation must be live-backed and include telemetry evidence
  for context compression, guide reply, Story Brief, opening/template, and play
  turn where those paths are exercised.

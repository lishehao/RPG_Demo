# Shared Frontend Libraries

This folder contains product helpers shared across pages. Avoid turning page-specific behavior into hidden global behavior.

## Files

- `i18n.ts`
  - UI locale strings and `useI18n`.
  - UI language is separate from generated story language.
  - Do not use localized UI strings to imply full bilingual story generation.
- `story-guide-loop.ts`
  - Deterministic Story Butler state machine.
  - Owns slot classification, missing-field prompts, unsafe redirect, not-fit readiness, and inferred story-shape settings.
  - Keep this deterministic unless a task explicitly asks for live-agent inference.
- `webtoon-assets.ts`
  - Central asset resolver for covers, avatars, scenes, endings, peaks, and page backgrounds.
  - `cover_image_url` from backend/provider wins.
  - Internal generated cover fallback then shell fallback fill gaps.
  - `assignTemplateCovers` handles same-screen no-overlap for fallback/internal covers.
- `localized-story-metadata.ts`
  - Selects display title/summary by UI locale when metadata exists.
  - Falls back to primary story title/summary without translating story body.
- `friendly-error.ts`
  - Converts raw errors into player-safe copy.
  - Normal player UI should never show provider/model/API/schema/debug details.
- `create-draft-handoff.ts`
  - Preserves starter premise or typed draft handoff into Create.
- `continue-session.ts`, `bookmarks.ts`, `format.ts`, `motion-presets.ts`
  - Small cross-page helpers.

## Boundary Rules

- R&D may change deterministic logic here when it is covered by tests.
- Design owns display matching rules and copy hierarchy; implement those mechanically once specified.
- Art owns new asset generation. R&D wires accepted asset paths into `webtoon-assets.ts`.

## Tests To Update

- `story-guide-loop.ts` -> `tests/test_korean_agent_chat_slot_loop_contract.py` and `tests/test_agent_guided_settings_contract.py`.
- `webtoon-assets.ts` -> `tests/test_generated_cover_contract.py`.
- `localized-story-metadata.ts` -> `tests/test_localized_story_metadata_contract.py`.
- `friendly-error.ts` -> source guards or browser smoke for player-facing failure copy.

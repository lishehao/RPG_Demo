# Backend UI Requirements

This document tracks only the remaining stable public API gaps for the current frontend.

Already available and now integrated by the frontend:

- `GET /stories` search / filter / cursor / sort support
- `stories`, `meta`, `facets`
- `PublishedStoryDetailResponse.story`
- `PublishedStoryDetailResponse.preview`
- `PublishedStoryDetailResponse.presentation`
- `PublishedStoryDetailResponse.play_overview`
- `PlaySessionSnapshot.protagonist`
- `PlaySessionSnapshot.feedback`
- `PlaySessionSnapshot.progress`
- `PlaySessionSnapshot.support_surfaces`
- `PlaySessionSnapshot.state_bars`
- `PlaySessionSnapshot.suggested_actions`
- `PlaySessionSnapshot.ending`
- `GET /play/sessions/{session_id}/history`

Acceptance:

- frontend can reconstruct a session transcript after refresh
- frontend does not need to read `/benchmark/*`

## Navigation Ownership

- story detail and play session sidebar navigation remain frontend-owned
- scrollspy / active-section behavior must be derived from the rendered page structure, not from new backend metadata
- public APIs should continue exposing stable content fields only:
  - story detail uses `story`, `preview`, `presentation`, `play_overview`
  - play session uses `story_title`, `beat_title`, `progress`, `protagonist`, `state_bars`, `suggested_actions`, `support_surfaces`
- do not add public `section_ids`, `active_section`, `nav_items`, or similar backend-generated UI navigation fields for this feature

## Remaining Public API Gap

- none currently required for the main frontend loop

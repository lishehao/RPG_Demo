# Frontend Architecture

`frontend2` is the active Tiny Stories frontend. Treat older frontend folders as legacy unless a task explicitly targets them.

## Entry Points

- `main.tsx` mounts React.
- `app/app.tsx` wires `LanguageProvider`, `ApiProvider`, `AuthProvider`, and route rendering.
- `app/routes.ts` parses and writes hash routes.
- `app/theme.css` holds global CSS variables and reset-like styling.
- `api/route-map.ts`, `api/http-client.ts`, `api/client.ts`, and `api/contracts.ts` define the frontend API boundary.

## Page Ownership

- `pages/home/`: Story Desk/home, starter premise doors, published story cards, My Stories.
- `pages/create/`: Korean webtoon Agent Chat and Story Brief creation flow. Container, styles, options, local types, and view panels are split inside this folder.
- `pages/play/`: live turn loop, choices/free input, advisor, current beat, ending payoff. Container, styles, local types, layout hook, and panels are split inside this folder.
- `pages/replay/`: public replay and result-first memory loop.
- `pages/world/`: generated template detail and direct Play/session entry.
- `pages/portfolio/`: portfolio and reviewer evidence mode.
- `pages/about/`, `pages/auth/`: secondary surfaces.

## Shared Helpers

- `shared/lib/i18n.ts`: UI strings and locale selection. Story body language is not the same as UI locale.
- `shared/lib/story-guide-loop.ts`: deterministic Story Butler slot loop and assistant state transitions.
- `shared/lib/story-guide-settings.ts`: deterministic story-shape setting inference and privacy-intent classification.
- `shared/lib/webtoon-assets.ts`: webtoon asset resolver, cover fallback, same-screen cover assignment.
- `shared/lib/localized-story-metadata.ts`: lightweight title/summary display fallback.
- `shared/lib/friendly-error.ts`: sanitized player error copy.
- `shared/lib/create-draft-handoff.ts`: home/scenario-to-Create draft handoff.
- `shared/ui/header.tsx`: route-aware top navigation primitive.

## Route Rules

- Home has no Back.
- Create has one explicit top-left Story Desk escape; the composer owns only story progression.
- Published playable cards start/resume Play; starter premise doors route to Create.
- Play/Replay may show local route crumbs, but page-level escape navigation should not be buried near action controls.
- Reviewer evidence mode stays separate from normal player routes.

## Player Copy Rules

Normal player surfaces must not show provider/model/API/schema/debug terms or reviewer trace labels such as `agent_plan` and `contract_judge`. If technical evidence is needed, put it in reviewer mode only.

## Validation

Run after frontend edits:

```bash
npm --prefix frontend2 run check
npm --prefix frontend2 run build
```

When page behavior changes, add focused browser smoke for desktop and 390px mobile.

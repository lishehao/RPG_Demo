# Tiny Stories Play Gameplay Loop PRD

## Goal

Tiny Stories Play should feel like a playable scene, not only a prose chat. Each episode needs a clear objective, visible pressure, usable people/resources, forecasted choice tradeoffs, and explicit state changes after the room responds.

This PRD defines the first game-state loop to prototype in local QA before integrating with the live story engine.

## Core Loop

1. Read scene state: current objective, pressure tracks, people in the room, and discovered clues/opportunities.
2. Choose a move: action cards expose a short forecast of likely costs and benefits.
3. Optional support: the player may add inner motive or use an NPC/advisor/person resource before committing.
4. Submit: the selected move collapses into a receipt.
5. Room reaction: the system shows a larger reacting state while the scene resolves.
6. State changes: resolved deltas update pressure/person/clue state explicitly.
7. Unlock: clues, leverage, or opportunities can become usable.
8. Next action set: available moves change because of the updated state.

## Stable State Model

The first slice should use a small typed state envelope:

```ts
type PlayEpisodeState = {
  episodeGoal: string
  pressure: {
    time: number
    publicPressure: number
    danger?: number
  }
  people: Array<{
    id: string
    name: string
    role: string
    trust: number
    attention: "low" | "watching" | "locked"
    leverage?: string
    mood: string
    available: boolean
  }>
  clues: Array<{
    id: string
    title: string
    state: "undiscovered" | "discovered" | "usable" | "spent"
    unlocksActionIds: string[]
  }>
  opportunities: Array<{
    id: string
    title: string
    state: "locked" | "open" | "spent"
  }>
}
```

First-slice tracks:

- `time`: countdown pressure.
- `publicPressure`: public/livestream scrutiny.
- `lenaTrust`: a person-state shortcut for whether Lena will cooperate.
- `evidence`: discovered clue count.

Action cards carry both forecast and resolved deltas:

```ts
type ActionForecast = {
  label: string
  deltas: string[] // e.g. "Time -1", "Lena trust +1", "Evidence unlocked"
  unlocks?: string[]
}
```

Forecast chips must be visible before the player commits. Resolved deltas must be visible after the room reacts.

## UX Surfaces

- Goal/pressure surface: compact scene objective plus pressure tracks near the top of Play or in the rail.
- Right rail people/resources: scene characters and advisor/friend are resources with availability and local person actions.
- Action card forecasts: every move displays cost/benefit chips before commitment.
- Pending receipt and reaction: after submit, options collapse into `Your move` plus a larger room-reaction panel.
- Delta strip: resolved state changes appear as player-facing deltas.
- Clue/opportunity strip: discovered cards become visible and may unlock the next action set.

## Integration Principle

Prototype fixture first. The first implementation must run locally without live story calls so interaction, state transitions, and QA hooks can be inspected cheaply.

Future live integration should ask the LLM for prose inside a typed game-state envelope. Prose should explain the scene, but typed state should remain authoritative for objectives, tracks, person state, clues, opportunity unlocks, and available actions.

## Acceptance Criteria

- A local QA route shows one complete loop: initial state, forecasts, commit receipt, room reaction, resolved deltas, clue unlock, and changed next actions.
- The fixture exposes stable hooks for browser and source checks: objective, pressure tracks, person actions, clue cards, deltas, unlocked actions, and root fixture.
- Normal Play routes continue to use the accepted action model and remain unchanged by the prototype.
- Player-facing copy contains no provider, model, schema, token, debug, trace, raw JSON, or internal judge language.
- The local slice has no horizontal overflow around 390px.

## Kill Criteria

- If the prototype requires backend or live story calls to demonstrate the loop, it is too large for this pass.
- If the action card state can only be represented as prose with no explicit state delta, the loop is not ready for engine integration.
- If person/advisor resources become decorative only and cannot affect the next action set, the model should be revised before live integration.
- If the typed envelope becomes a broad simulation system in this pass, stop and reduce scope to the smallest inspectable loop.

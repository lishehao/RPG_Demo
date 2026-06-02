# Story Brief Agent / Cast Planner / Tension Profile v2

This line is a product architecture upgrade for Tiny Stories. It is separate
from PR #18's agent evaluation chain.

## Current Runtime Fit

The playable narrative path is:

`POST /narrative/templates` -> `NarrativeService.create_template` ->
`generate_opening` -> persisted template/session -> `#/play/:session_id`.

The current opening runtime works best when the seed already implies:

- 3+ people/entities
- one public conflict
- one secret or contested object
- time pressure or a public decision window

Small two-person/no-villain stories are not supported as a separate mode yet.
They should be revised before full generation.

## Implemented MVP

The first shippable slice is deterministic and testable:

- `StoryBriefAdvisorRequest/Response`
- `StoryBrief`
- `CastPlan`
- `ConstraintDisposition`
- `TensionProfile`
- `POST /narrative/story-briefs`
- create-page brief card before full story generation
- optional `story_brief` on `CreateTemplateRequest`

The brief card is not persisted on the template in this MVP. It is a
pre-generation planning contract that is injected into the opening-generation
payload when the user confirms generation from the brief.

## Cast Planner

The global cast plan can name up to 10 entities. The card separates them into:

- `primary_active_entities`: 3-5 entities the runtime should keep readable
- `secondary_background_entities`: up to 5 background/faction/context entities
- `omitted_entities`: entities beyond the current planning cap

The runtime trace also now includes Director focus metadata:

- `focus_window_npc_ids`
- `background_npc_ids`

This records the intended focus window without rewriting turn generation.

Planner fidelity rules added after playtest:

- entity extraction prefers explicit comma/list/faction segments
- setting openers such as `At`, `In`, `On`, `Mars colony`, and event anchors are not cast
- negated tone constraints such as `no blackmail` stay as constraints, not entities
- abstract tone mechanisms such as `misunderstandings` or `callback joke` are not cast
- event anchors such as `eclipse`, `board vote`, `talent show`, and `final broadcast` count as pressure/constraints
- exact-word matching prevents stray constraints such as `ring` from appearing because of unrelated substrings

## Tension Profiles

Supported enum values:

- `high_drama`: secret -> leverage -> confrontation -> relationship shift -> ending
- `cozy_mystery`: clues -> suspicion -> gentle stakes -> reveal -> repaired trust
- `comedy`: misunderstanding -> embarrassment -> escalation -> reversal -> callback/payoff
- `fantasy_sci_fi`: world rule -> faction pressure -> artifact complication -> reveal -> rule payoff
- `family_social`: old wound -> misread intent -> loyalty test -> reconciliation/rupture

The profile also changes the planned intervention card label:

- high drama: leverage card
- cozy mystery: clue card
- comedy: callback card
- fantasy/sci-fi: artifact card
- family/social: loyalty card

Full play-page terminology and judge profile-specific payoff checks are deferred.

For comedy and cozy briefs, the confirmed generation payload carries a
lower-stakes contract. Opening generation should use misunderstandings,
embarrassment, clues, social pressure, props, callbacks, or gentle reveals
instead of silently escalating into blackmail, revenge, hacking, security
footage, or life-or-death danger. If the premise itself contains life-or-death
stakes such as stolen oxygen, the brief warns that comedy/cozy fidelity needs a
lower-stakes revision.

## Deferred Scope

- Full conversational Brief Agent chatbox with multi-turn repair
- Persisting story briefs on templates
- True 10-character runtime scenes with dynamic per-turn cast pruning in prompts
- Low-conflict/small-cast mode
- Broad tone-preservation rewrite
- Profile-specific card terminology across the whole play UI
- Profile-aware Step/Trajectory judge payoff gates

## Next Implementation Slice

The next contained slice should persist brief metadata on templates, expose it
on reviewer surfaces, then use it to drive profile-aware card terminology and
judge payoff expectations.

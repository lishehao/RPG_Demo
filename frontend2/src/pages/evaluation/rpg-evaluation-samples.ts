import type { RpgEvaluationBundle, RpgMemoryFact, RpgMemorySnapshot } from "./rpg-evaluation-contract"

function fact(id: string, key: string, value: string, turn: number, namespace = "story"): RpgMemoryFact {
  return {
    fact_id: id,
    namespace,
    key,
    value,
    status: "active",
    source_turn: turn,
    source: "runtime",
    confidence: 1,
  }
}

function memory(turn: number, active: RpgMemoryFact[], recent: string[], progress: string): RpgMemorySnapshot {
  return {
    schema_version: "rpg_memory.v1",
    run_id: "awards-candidate-01",
    turn_index: turn,
    objective: "Find the missing singer before the livestream countdown ends.",
    active_facts: active,
    superseded_facts: turn >= 2 ? [{
      ...fact("fact-old-role", "player_role", "Backup dancer", 0),
      status: "superseded",
      superseded_by: "fact-role",
    }] : [],
    open_threads: turn < 3 ? ["Who used the green-room badge after Mina vanished?"] : [],
    entities: [
      { entity_id: "lena", name: "Lena", state: { trust: turn >= 2 ? "warming" : "guarded" }, last_updated_turn: turn },
      { entity_id: "producer_han", name: "Producer Han", state: { pressure: turn >= 3 ? "cornered" : "wary" }, last_updated_turn: turn },
      { entity_id: "dana", name: "Dana Vale", state: { role: "off-the-record advisor" }, last_updated_turn: turn },
    ],
    recent_events: recent.slice(-8),
    episodic_summary: `Objective: find Mina before air. ${progress}`,
    diagnostics: {
      event_count: recent.length + active.length,
      active_fact_count: active.length,
      superseded_fact_count: turn >= 2 ? 1 : 0,
      non_story_event_count: 1,
      dropped_recent_event_count: 0,
      last_compacted_turn: turn,
    },
  }
}

const baseFacts = [
  fact("fact-role", "player_role", "Publicist", 0),
  fact("fact-pressure", "pressure", "Three minutes until air", 0),
  fact("fact-boundary", "content_boundary", "No violence or blackmail", 0, "boundary"),
]

export const CANDIDATE_RPG_BUNDLE: RpgEvaluationBundle = {
  schema_version: "rpg_evaluation_bundle.v1",
  run_id: "awards-candidate-01",
  system_label: "Stateful runtime candidate",
  locale: "en",
  scenario: {
    scenario_id: "awards-livestream",
    title: "Awards Livestream",
    genre: "social-pressure mystery",
    objective: "Find the missing singer before the livestream countdown ends.",
    turn_budget: 12,
    entity_ids: ["lena", "producer_han", "dana"],
    boundaries: ["No violence", "No blackmail", "Keep pressure social and investigative"],
  },
  turns: [
    {
      turn_index: 1,
      player_action: "Freeze the sponsor feed and ask Lena to verify the badge timestamp.",
      world_response: "Lena checks the feed log. The badge was used after Mina vanished, and Producer Han can no longer dismiss the discrepancy.",
      options: ["Question Producer Han", "Send Lena to the corridor", "Protect the feed log"],
      state_deltas: [{ target: "lena", kind: "increase", label: "Lena trust +1", evidence: "You gave her verifiable proof." }],
      clue_unlocks: ["Green-room badge timestamp"],
      opportunity_unlocks: [],
      referenced_entity_ids: ["lena", "producer_han"],
      objective_progress: 0.3,
      memory: memory(1, baseFacts, ["Player: froze the sponsor feed", "Clue: badge timestamp"], "The badge is now evidence."),
    },
    {
      turn_index: 2,
      player_action: "Use the timestamp to make Producer Han name the last badge holder.",
      world_response: "Han admits the badge crossed the service corridor. Lena moves to cover the exit while the room waits for your next call.",
      options: ["Search the service corridor", "Ask Dana to map the sponsor risk", "Call the stage manager as witness"],
      state_deltas: [
        { target: "producer_han", kind: "shift", label: "Han is cornered", evidence: "The timestamp removed his plausible denial." },
        { target: "pressure", kind: "increase", label: "Public pressure rising", evidence: "The feed cannot stay frozen much longer." },
      ],
      clue_unlocks: [],
      opportunity_unlocks: ["Service corridor search"],
      referenced_entity_ids: ["lena", "producer_han", "dana"],
      objective_progress: 0.62,
      memory: memory(2, [...baseFacts, fact("fact-corridor", "search_area", "Service corridor", 2)], ["Player: confronted Han", "World: service corridor identified"], "The search is narrowed."),
    },
    {
      turn_index: 3,
      player_action: "Take Lena and the stage manager into the service corridor before the countdown resumes.",
      world_response: "They find Mina's in-ear monitor beside an unlocked rehearsal room. A voice inside asks whether the sponsor has left.",
      options: ["Answer Mina honestly", "Let Lena speak first", "Secure the rehearsal room door"],
      state_deltas: [{ target: "objective", kind: "increase", label: "Singer located", evidence: "Mina answered from the rehearsal room." }],
      clue_unlocks: ["Mina's in-ear monitor"],
      opportunity_unlocks: ["Private negotiation with Mina"],
      referenced_entity_ids: ["lena", "producer_han"],
      objective_progress: 0.9,
      memory: memory(3, [...baseFacts, fact("fact-location", "singer_location", "Rehearsal room", 3)], ["Player: searched corridor", "World: Mina answered", "Clue: in-ear monitor"], "Mina is found; sponsor pressure remains."),
    },
  ],
}

const weakMemory = memory(1, [fact("weak-role", "player_role", "Someone in the room", 0)], ["World: tension changed"], "No concrete progress recorded.")

export const BASELINE_RPG_BUNDLE: RpgEvaluationBundle = {
  ...CANDIDATE_RPG_BUNDLE,
  run_id: "awards-baseline-01",
  system_label: "Prose-only baseline",
  turns: [1, 2, 3].map((turn) => ({
    turn_index: turn,
    player_action: "Wait and see what happens.",
    world_response: "The room grows more tense, but no one makes a clear move.",
    options: ["Wait", "Wait"],
    state_deltas: [],
    clue_unlocks: [],
    opportunity_unlocks: [],
    referenced_entity_ids: [],
    objective_progress: 0,
    memory: { ...weakMemory, run_id: "awards-baseline-01", turn_index: turn },
  })),
}

export const RPG_EVALUATION_SAMPLES = [CANDIDATE_RPG_BUNDLE, BASELINE_RPG_BUNDLE]

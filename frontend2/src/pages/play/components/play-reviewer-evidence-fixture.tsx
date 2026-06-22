import type { NarrativeAgentEvent, NarrativeStoryHistoryResponse, NarrativeStoryMessage } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"
import { RuntimeInspector } from "./runtime-inspector"

const REVIEWER_LAST_NARRATOR: NarrativeStoryMessage = {
  ord: 2,
  role: "narrator",
  content:
    "Mara freezes the sponsor feed. The missing badge is now visible on the console, and the next choices can press the room instead of guessing.",
  chosen_option_index: null,
  options: [
    {
      label: "[Press] Ask the producer who last held the badge",
      hint: "Use the visible badge to force a concrete answer.",
      handle: "Press",
    },
    {
      label: "[Cover] Keep the livestream paused while Rina checks the corridor",
      hint: "Buy time without turning the room into panic.",
      handle: "Cover",
    },
    {
      label: "[Reveal] Show the reporter the copied timestamp",
      hint: "Move the proof into a public witness's hands.",
      handle: "Reveal",
    },
  ],
  npc_pulse: [
    {
      npc_id: "producer_han",
      state: "wary",
      shift: "wary",
      reason: "The paused feed makes the badge impossible to ignore.",
    },
  ],
  inventory_delta: {
    added: ["Green-room badge"],
    removed: [],
    reason: "The badge moved from rumor to visible proof.",
  },
}

const REVIEWER_STORY: NarrativeStoryHistoryResponse = {
  template: {
    template_id: "qa-reviewer-template",
    owner_user_id: "qa-owner",
    seed: "Missing singer, live awards stream, sponsor pressure; no violence or blackmail.",
    title: "The Missing Singer Broadcast",
    cast: [
      {
        character_id: "producer_han",
        display_name: "Producer Han",
        role: "Livestream producer",
        relation_to_protagonist: "Needs Mira to keep the show from collapsing.",
      },
    ],
    advisor_persona: "A careful story editor who helps Mira reason without choosing for her.",
    player_role_options: [
      {
        role_id: "mira",
        label: "Anxious publicist",
        public_persona: "Seo Mina's publicist under sponsor pressure",
        hidden_objective: "Find the singer without letting the sponsor bury the disappearance.",
        leverages_over_npcs: [],
        starting_assets: ["Copied timestamp"],
      },
    ],
    visibility: "unlisted",
    language: "en",
    play_count: 0,
    created_at: "2026-06-22T00:00:00.000Z",
    is_owner: true,
  },
  session: {
    session_id: "qa-reviewer-evidence",
    template_id: "qa-reviewer-template",
    template_title: "The Missing Singer Broadcast",
    template_seed: "Missing singer, live awards stream, sponsor pressure; no violence or blackmail.",
    player_user_id: "qa-reviewer",
    turn_count: 2,
    turn_budget: 12,
    difficulty: "story",
    player_role: {
      role_id: "mira",
      label: "Anxious publicist",
      public_persona: "Seo Mina's publicist under sponsor pressure",
      hidden_objective: "Find the singer without letting the sponsor bury the disappearance.",
      leverages_over_npcs: [],
      starting_assets: ["Copied timestamp"],
    },
    ending_label: null,
    ending_subtitle: null,
    created_at: "2026-06-22T00:00:00.000Z",
    last_active_at: "2026-06-22T00:00:00.000Z",
  },
  messages: [
    {
      ord: 0,
      role: "narrator",
      content: "The awards livestream is three minutes from air when Seo Mina disappears.",
      chosen_option_index: null,
      options: [],
    },
    {
      ord: 1,
      role: "player",
      content: "[Hold] Ask Producer Han to freeze the sponsor feed.",
      chosen_option_index: null,
      options: [],
    },
    REVIEWER_LAST_NARRATOR,
  ],
  agent_events: [],
  gameplay_envelope: {
    source: "live_enriched",
    objective: "Keep the singer safe and make the room verify the badge.",
  },
}

const ARCHIVED_AGENT_EVENTS: NarrativeAgentEvent[] = [
  {
    event_index: 1,
    ord: 2,
    event_type: "step_judge",
    created_at: "2026-06-22T00:00:01.000Z",
    payload: {
      schema_version: "step_judge.v1",
      source: "deterministic_v1",
      turn_index: 2,
      narrator_ord: 2,
      status: "pass",
      violations: [],
      summary: "Latest beat keeps player-facing consequence, inventory change, and next moves visible.",
    },
  },
  {
    event_index: 2,
    ord: 2,
    event_type: "contract_judge",
    created_at: "2026-06-22T00:00:02.000Z",
    payload: {
      schema_version: "contract_judge.v1",
      source: "deterministic_v1",
      turn_index: 2,
      narrator_ord: 2,
      status: "pass",
      violations: [],
      summary: "Archived contract proof exists, but the reviewer surface should still start from live evidence.",
    },
  },
]

const CASE_LABEL_STYLE = {
  marginBottom: 8,
  color: "rgba(255, 255, 255, 0.74)",
  fontSize: 12,
  fontWeight: 800,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
} as const

const INTRO_STYLE = {
  display: "grid",
  gap: 8,
  padding: "14px",
  border: "1px solid rgba(255, 255, 255, 0.14)",
  borderRadius: 18,
  background: "rgba(255, 255, 255, 0.08)",
  boxShadow: "0 18px 50px rgba(3, 7, 18, 0.24)",
} as const

const INTRO_KICKER_STYLE = {
  color: "rgba(255, 255, 255, 0.68)",
  fontSize: 11,
  fontWeight: 900,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
} as const

const INTRO_TITLE_STYLE = {
  color: "#fff",
  fontSize: 17,
  fontWeight: 900,
  letterSpacing: 0,
  lineHeight: 1.18,
} as const

const INTRO_COPY_STYLE = {
  margin: 0,
  color: "rgba(255, 255, 255, 0.76)",
  fontSize: 12,
  lineHeight: 1.45,
} as const

const CASE_MAP_STYLE = {
  display: "grid",
  gap: 8,
  gridTemplateColumns: "repeat(auto-fit, minmax(126px, 1fr))",
} as const

const CASE_MAP_ITEM_STYLE = {
  display: "grid",
  gap: 3,
  padding: "8px 10px",
  border: "1px solid rgba(255, 255, 255, 0.12)",
  borderRadius: 12,
  background: "rgba(3, 7, 18, 0.2)",
} as const

const CASE_MAP_LABEL_STYLE = {
  color: "#fff",
  fontSize: 12,
  fontWeight: 900,
} as const

const CASE_MAP_NOTE_STYLE = {
  color: "rgba(255, 255, 255, 0.68)",
  fontSize: 11,
  lineHeight: 1.35,
} as const

export function PlayReviewerEvidenceFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "32px",
        gap: 24,
      }}
      data-play-reviewer-evidence-fixture="true"
    >
      <button
        type="button"
        style={ppStyles.backBtn}
        onClick={onBackHome}
      >
        {t("action.back_home")}
      </button>
      <section
        style={{
          width: "min(100%, 860px)",
          display: "grid",
          gap: 16,
        }}
        aria-label="Reviewer evidence fixture"
      >
        <div style={INTRO_STYLE} data-play-reviewer-evidence-fixture-intro="true">
          <span style={INTRO_KICKER_STYLE}>Local reviewer evidence fixture</span>
          <strong style={INTRO_TITLE_STYLE}>Evidence drawer for application review.</strong>
          <p style={INTRO_COPY_STYLE}>
            Fresh live evidence appears first; archived checks appear second. Use this for application review evidence;
            cite public claims only after repo/demo preflight passes.
          </p>
          <div style={CASE_MAP_STYLE} data-play-reviewer-evidence-fixture-case-map="true">
            <span style={CASE_MAP_ITEM_STYLE}>
              <strong style={CASE_MAP_LABEL_STYLE}>1. Fresh evidence limit</strong>
              <span style={CASE_MAP_NOTE_STYLE}>Playable state, visible consequence, no archive overclaim.</span>
            </span>
            <span style={CASE_MAP_ITEM_STYLE}>
              <strong style={CASE_MAP_LABEL_STYLE}>2. Archived checks attached</strong>
              <span style={CASE_MAP_NOTE_STYLE}>Stored checks appear only when archived evidence is attached.</span>
            </span>
          </div>
        </div>
        <div data-play-reviewer-evidence-fixture-case="fresh">
          <div
            data-play-reviewer-evidence-case-label="true"
            data-play-reviewer-evidence-case-label-kind="fresh"
            style={CASE_LABEL_STYLE}
          >
            Fresh evidence limit - live evidence only
          </div>
          <RuntimeInspector
            story={REVIEWER_STORY}
            ending={null}
            lastNarrator={REVIEWER_LAST_NARRATOR}
            turnsRemaining={10}
            liveInventory={["Copied timestamp", "Green-room badge"]}
            effectiveLastInventoryDelta={REVIEWER_LAST_NARRATOR.inventory_delta}
            agentPlan={null}
            agentEvents={[]}
            llmEvents={[]}
            agentTraceAccessGranted={false}
          />
        </div>
        <div data-play-reviewer-evidence-fixture-case="archived">
          <div
            data-play-reviewer-evidence-case-label="true"
            data-play-reviewer-evidence-case-label-kind="archived"
            style={CASE_LABEL_STYLE}
          >
            Archived checks attached - checks available
          </div>
          <RuntimeInspector
            story={REVIEWER_STORY}
            ending={null}
            lastNarrator={REVIEWER_LAST_NARRATOR}
            turnsRemaining={10}
            liveInventory={["Copied timestamp", "Green-room badge"]}
            effectiveLastInventoryDelta={REVIEWER_LAST_NARRATOR.inventory_delta}
            agentPlan={null}
            agentEvents={ARCHIVED_AGENT_EVENTS}
            llmEvents={[]}
            agentTraceAccessGranted={true}
          />
        </div>
      </section>
    </main>
  )
}

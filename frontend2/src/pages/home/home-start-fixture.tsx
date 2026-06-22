import { useMemo, useState } from "react"
import type {
  NarrativeAdvanceTurnRequest,
  NarrativeAdvanceTurnResponse,
  NarrativeSessionSummary,
  NarrativeStartSessionResponse,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
  NarrativeTemplateSummary,
} from "../../api/contracts"
import { PlayPage } from "../play/play-page"
import { HomePage } from "./home-page"

const QA_INTRO_STYLE = {
  display: "grid",
  gap: 6,
  padding: "12px 18px",
  borderBottom: "1px solid rgba(255,255,255,0.12)",
  background: "rgba(12,18,30,0.96)",
  color: "rgba(255,255,255,0.88)",
} as const

const QA_INTRO_KICKER_STYLE = {
  color: "rgba(245,200,120,0.84)",
  fontSize: 11,
  fontWeight: 900,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
} as const

const QA_INTRO_TITLE_STYLE = {
  color: "#ffffff",
  fontSize: 14,
  lineHeight: 1.25,
} as const

const QA_INTRO_COPY_STYLE = {
  margin: 0,
  maxWidth: 720,
  color: "rgba(255,255,255,0.68)",
  fontSize: 12,
  lineHeight: 1.45,
} as const

const QA_HOME_TEMPLATE: NarrativeTemplateSummary = {
  template_id: "qa-home-start-template",
  owner_user_id: "qa-author",
  seed:
    "A stage manager has one hour to stop a sponsor from turning a missing singer into a live scandal.",
  title: "The Last Broadcast Before Dawn",
  title_i18n: {
    en: "The Last Broadcast Before Dawn",
    zh: "黎明前最后一次直播",
  },
  summary_i18n: {
    en:
      "A live music show is about to start, the lead singer is missing, and every quiet choice changes who controls the room.",
    zh:
      "直播演出即将开始，主唱失踪，每一次安静的选择都会改变谁掌控房间。",
  },
  cast: [
    {
      character_id: "mara",
      display_name: "Producer Mara",
      role: "Producer",
      relation_to_protagonist: "She can freeze or restart the countdown.",
      hidden_objective: "Keep the broadcast alive without exposing the missing singer.",
    },
    {
      character_id: "sponsor",
      display_name: "Sponsor Vale",
      role: "Sponsor",
      relation_to_protagonist: "He wants the room to follow his version of the story.",
      hidden_objective: "Turn the missing singer into leverage over the producer.",
    },
  ],
  advisor_persona: "Rin, a production friend who thinks in stage pressure.",
  cover_image_url: null,
  player_goals: [
    {
      goal: "Find the missing singer before the countdown reaches zero",
      stakes: "If the sponsor controls the reveal, the show becomes his story.",
    },
  ],
  failure_conditions: [
    {
      label: "Broadcast lost",
      description: "The countdown reaches zero while the singer remains unaccounted for.",
    },
  ],
  player_role_options: [
    {
      role_id: "stage-manager",
      label: "The Assistant Stage Manager",
      public_persona: "The calm floor lead who can move between producer, dancers, and sponsor.",
      hidden_objective: "Find the missing singer before the countdown reaches zero.",
      leverages_over_npcs: [
        {
          npc_id: "sponsor",
          leverage: "A backstage sign-in sheet showing the sponsor's aide entered the green room.",
        },
      ],
      starting_assets: ["Green-room badge", "Countdown headset"],
    },
  ],
  visibility: "public",
  language: "en",
  play_count: 183,
  created_at: "2026-06-21T18:00:00.000Z",
  is_owner: false,
}

const QA_HOME_ROLE = QA_HOME_TEMPLATE.player_role_options?.[0] ?? null

const QA_HOME_SESSION: NarrativeSessionSummary = {
  session_id: "qa-home-start-session",
  template_id: QA_HOME_TEMPLATE.template_id,
  template_title: QA_HOME_TEMPLATE.title,
  template_seed: QA_HOME_TEMPLATE.seed,
  template_title_i18n: QA_HOME_TEMPLATE.title_i18n,
  template_summary_i18n: QA_HOME_TEMPLATE.summary_i18n,
  player_user_id: "qa-player",
  turn_count: 0,
  turn_budget: 6,
  difficulty: "story",
  player_role: QA_HOME_ROLE,
  ending_label: null,
  ending_subtitle: null,
  ending_tier: null,
  early_terminated: false,
  created_at: "2026-06-21T18:01:00.000Z",
  last_active_at: "2026-06-21T18:01:00.000Z",
}

const QA_HOME_OPENING: NarrativeStoryMessage = {
  ord: 1,
  role: "narrator",
  content:
    "The studio countdown glows red above a silent stage. Producer Mara keeps one hand on the talkback switch while Sponsor Vale drifts toward the camera line, ready to explain the missing singer before anyone else can.",
  chosen_option_index: null,
  npc_pulse: [
    {
      npc_id: "mara",
      state: "holding the room together",
      shift: "steady",
      reason: "She is waiting for your first call.",
    },
    {
      npc_id: "sponsor",
      state: "testing the silence",
      shift: "wary",
      reason: "He wants to define the missing singer first.",
    },
  ],
  inventory_delta: {
    added: ["Green-room badge", "Countdown headset"],
    removed: [],
    reason: "The assistant stage manager starts with the tools needed to hold the room.",
  },
  options: [
    {
      label: "[Hold] Ask Mara to freeze the countdown.",
      hint: "Buys time without making the singer's absence public.",
      handle: "hold",
    },
    {
      label: "[Press] Ask Sponsor Vale why his aide entered the green room.",
      hint: "Turns pressure toward the person trying to own the story.",
      handle: "press",
    },
    {
      label: "[Cover] Send the dancers into a rehearsal loop.",
      hint: "Keeps the audience calm while you trace the missing singer.",
      handle: "cover",
    },
  ],
}

function buildQaHomeStory(): NarrativeStoryHistoryResponse {
  return {
    template: QA_HOME_TEMPLATE,
    session: QA_HOME_SESSION,
    messages: [QA_HOME_OPENING],
    agent_events: [],
    gameplay_envelope: null,
  }
}

function buildQaHomeAdvance(request: NarrativeAdvanceTurnRequest): NarrativeAdvanceTurnResponse {
  const chosenIndex = request.chosen_option_index ?? 0
  const chosen = QA_HOME_OPENING.options[chosenIndex] ?? QA_HOME_OPENING.options[0]
  return {
    player_message: {
      ord: 2,
      role: "player",
      content: chosen.label.replace(/^\[[^\]]+\]\s*/, ""),
      chosen_option_index: chosenIndex,
      options: [],
      diary: request.diary ?? null,
    },
    narrator_message: {
      ord: 3,
      role: "narrator",
      content:
        "Mara catches your signal and the room shifts around the pause. The sponsor notices the delay, but the next choice now belongs to you.",
      chosen_option_index: null,
      npc_pulse: [
        {
          npc_id: "mara",
          state: "ready to follow your lead",
          shift: "warmer",
          reason: "The first move protected the stage clock.",
        },
      ],
      inventory_delta: null,
      options: [
        {
          label: "[Reveal] Show Mara the green-room badge.",
          hint: "Turns the pause into a concrete clue.",
          handle: "reveal",
        },
        {
          label: "[Deflect] Move Sponsor Vale into the hallway.",
          hint: "Keeps him from making the story public too early.",
          handle: "deflect",
        },
        {
          label: "[Search] Check the green-room camera feed.",
          hint: "Uses the bought time to find where the singer went.",
          handle: "search",
        },
      ],
    },
    agent_plan: null,
    agent_events: [],
    gameplay_envelope: null,
    ending: null,
    is_complete: false,
  }
}

export function HomeStartFixture({ onBackHome }: { onBackHome: () => void }) {
  const [view, setView] = useState<"home" | "play">("home")
  const [startedStory, setStartedStory] = useState<NarrativeStoryHistoryResponse | null>(null)

  const homeApi = useMemo(() => ({
    listPublicNarrativeTemplates: async () => ({ items: [QA_HOME_TEMPLATE] }),
    startNarrativeSession: async (): Promise<NarrativeStartSessionResponse> => {
      const story = buildQaHomeStory()
      setStartedStory(story)
      return {
        template: QA_HOME_TEMPLATE,
        session: QA_HOME_SESSION,
        opening: QA_HOME_OPENING,
      }
    },
    listMyNarrativeTemplates: async () => ({ items: [] }),
    listMyNarrativeSessions: async () => ({ items: [] }),
  }), [])

  const playApi = useMemo(() => ({
    getNarrativeStory: async () => startedStory ?? buildQaHomeStory(),
    getNarrativeLLMEvents: async () => ({ items: [] }),
    getNarrativeSessionEnding: async () => null,
    advanceNarrativeTurn: async (
      _sessionId: string,
      request: NarrativeAdvanceTurnRequest,
    ) => buildQaHomeAdvance(request),
  }), [startedStory])

  return (
    <div data-home-start-fixture="true" data-home-start-view={view}>
      {view === "play" ? (
        <PlayPage
          sessionId={QA_HOME_SESSION.session_id}
          onBackHome={onBackHome}
          apiClient={playApi}
        />
      ) : (
        <>
          <section
            aria-label="Local Story Desk start check"
            data-home-start-fixture-intro="true"
            style={QA_INTRO_STYLE}
          >
            <span style={QA_INTRO_KICKER_STYLE}>Local evidence check</span>
            <strong style={QA_INTRO_TITLE_STYLE}>Story Desk card -&gt; readable first turn</strong>
            <p style={QA_INTRO_COPY_STYLE}>
              Mounts the real Story Desk card and real Play first-turn surface with deterministic data.
              Use as local-only application evidence until the public-link check passes.
            </p>
          </section>
          <HomePage
            onOpenCreate={onBackHome}
            onOpenReplay={onBackHome}
            onOpenPlay={() => setView("play")}
            apiClient={homeApi}
          />
        </>
      )}
    </div>
  )
}

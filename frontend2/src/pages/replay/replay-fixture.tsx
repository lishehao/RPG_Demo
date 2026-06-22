import { useState } from "react"
import type {
  NarrativeAdvanceTurnRequest,
  NarrativeAdvanceTurnResponse,
  NarrativeEndingDistributionResponse,
  NarrativePlayerRole,
  NarrativePublicReplayResponse,
  NarrativeStartSessionRequest,
  NarrativeStartSessionResponse,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
  NarrativeTemplateSummary,
} from "../../api/contracts"
import { PlayPage } from "../play/play-page"
import { TemplateDetailPage } from "../world/world-detail-page"
import { ReplayPage } from "./replay-page"

const QA_REPLAY: NarrativePublicReplayResponse = {
  session_id: "qa-replay-completed",
  template_id: "qa-replay-template",
  template_forkable: true,
  template_title: "The Observatory Compact",
  template_seed:
    "A night watcher must expose a forged ledger before the gala closes and the west door guard changes sides.",
  template_title_i18n: null,
  template_summary_i18n: null,
  cover_image_url: null,
  cast: [
    {
      character_id: "victor",
      display_name: "Victor Saye",
      role: "Donor handler",
      relation_to_protagonist: "He can bury the ledger before dawn.",
    },
    {
      character_id: "ilya",
      display_name: "Curator Ilya",
      role: "Archive keeper",
      relation_to_protagonist: "She knows who touched the crescent seal.",
    },
  ],
  advisor_persona: "Dana Vale",
  player_goals: [
    {
      goal: "Make the crescent mark impossible to dismiss",
      stakes: "If Victor leaves with the ledger, the forged donation becomes official.",
    },
  ],
  player_role: {
    role_id: "night-watcher",
    label: "The Night Watcher",
    public_persona: "A quiet staffer trusted with the west archive door.",
    hidden_objective: "Expose the forged ledger before Victor moves it.",
    leverages_over_npcs: [
      {
        npc_id: "victor",
        leverage: "A timestamp showing Victor entered the archive before the donor speech.",
      },
    ],
    starting_assets: ["Ledger key", "Crescent seal rubbing"],
  },
  turn_budget: 6,
  turn_count: 6,
  difficulty: "story",
  completed: true,
  ending: {
    label: "victory",
    subtitle: "Victor could not outrun the proof",
    passage:
      "The gala ends with the ledger open under the observatory lights. Ilya names the seal, Victor loses the room, and the west door stays unlocked long enough for everyone to see the mark.",
    tier: "victory",
    highlights: [
      {
        beat_ord: 2,
        headline: "The first question held the room",
        body_excerpt:
          "You asked who could verify the ledger before Victor pulled the donor circle away.",
        why_pivotal:
          "It turned suspicion into a public test instead of a private accusation.",
      },
      {
        beat_ord: 6,
        headline: "Ilya chose the archive over silence",
        body_excerpt:
          "The curator handed you the key and named the crescent mark while Victor watched.",
        why_pivotal:
          "That made the next move about proof, not persuasion.",
      },
      {
        beat_ord: 10,
        headline: "The final reveal stayed public",
        body_excerpt:
          "You opened the ledger where the donors could see it and forced Victor to answer in the room.",
        why_pivotal:
          "The ending works because witnesses saw both the ledger and the reaction.",
      },
    ],
    branches: [
      {
        pivot_beat_ord: 4,
        chosen_path_summary: "You kept Ilya in the room and made Victor react in public.",
        alternate_path_summary: "If you had chased Victor alone, the ledger could have vanished.",
        alternate_ending_label: "compromised",
        alternate_ending_tier: "compromised",
        rationale: "The public witness pressure is what made the proof durable.",
      },
    ],
  },
  messages: [
    {
      ord: 1,
      role: "narrator",
      content:
        "Rain folds over the observatory glass while Victor gathers the donor circle near the west door. Ilya keeps one hand on the archive key.",
      options: [
        {
          label: "[Ask] Ask Ilya who last touched the crescent seal.",
          hint: "Makes the archive question public before Victor can redirect.",
          handle: "ask",
        },
      ],
      chosen_option_index: 0,
      npc_pulse: [],
      inventory_delta: null,
      diary: null,
      played_leverage: null,
    },
    {
      ord: 2,
      role: "player",
      content: "Ask Ilya who last touched the crescent seal.",
      options: [],
      chosen_option_index: null,
      npc_pulse: [],
      inventory_delta: null,
      diary: "I want Victor to hear that Ilya is not alone.",
      played_leverage: null,
    },
    {
      ord: 3,
      role: "narrator",
      content:
        "Ilya looks at Victor before answering. The pause gives the donors time to turn toward the ledger table.",
      options: [
        {
          label: "[Hold] Keep Victor at the service door.",
          hint: "Boxes him in while the ledger key moves.",
          handle: "hold",
        },
      ],
      chosen_option_index: 0,
      npc_pulse: [],
      inventory_delta: {
        added: ["Ledger key"],
        removed: [],
        reason: "Ilya trusts you enough to hand over the key.",
      },
      diary: null,
      played_leverage: null,
    },
  ],
  advisor_messages: [
    {
      ord: 1,
      role: "player",
      content: "Should I accuse Victor now or keep the proof public?",
    },
    {
      ord: 2,
      role: "advisor",
      content: "Keep it public. The room is your leverage; do not turn this into a private argument.",
    },
  ],
  created_at: "2026-06-22T00:00:00Z",
}

const qaReplayApi = {
  getNarrativePublicReplay: async () => QA_REPLAY,
}

const qaReplayPrimaryRole: NarrativePlayerRole = QA_REPLAY.player_role ?? {
  role_id: "night-watcher",
  label: "The Night Watcher",
  public_persona: "A quiet staffer trusted with the west archive door.",
  hidden_objective: "Expose the forged ledger before Victor moves it.",
  leverages_over_npcs: [
    {
      npc_id: "victor",
      leverage: "A timestamp showing Victor entered the archive before the donor speech.",
    },
  ],
  starting_assets: ["Ledger key", "Crescent seal rubbing"],
}

const qaReplayArchivistRole: NarrativePlayerRole = {
  role_id: "witness-archivist",
  label: "The Witness Archivist",
  public_persona: "An archivist who knows the donor ledger table and can read the room.",
  hidden_objective: "Make the crescent mark impossible to dismiss.",
  leverages_over_npcs: [
    {
      npc_id: "ilya",
      leverage: "Ilya trusts your memory of the ledger shelf order.",
    },
  ],
  starting_assets: ["Archive shelf map", "Old donor seating card"],
}

const QA_REPLAY_TEMPLATE: NarrativeTemplateSummary = {
  template_id: QA_REPLAY.template_id,
  owner_user_id: "qa-owner",
  seed: QA_REPLAY.template_seed,
  title: QA_REPLAY.template_title,
  title_i18n: QA_REPLAY.template_title_i18n,
  summary_i18n: QA_REPLAY.template_summary_i18n,
  cast: QA_REPLAY.cast,
  advisor_persona: QA_REPLAY.advisor_persona,
  cover_image_url: QA_REPLAY.cover_image_url,
  player_goals: QA_REPLAY.player_goals,
  failure_conditions: [
    {
      label: "Ledger leaves the gala",
      description: "Victor moves the forged ledger before anyone can inspect the crescent mark.",
    },
  ],
  player_role_options: [qaReplayPrimaryRole, qaReplayArchivistRole],
  visibility: "unlisted",
  language: "en",
  play_count: 8,
  created_at: QA_REPLAY.created_at,
  is_owner: false,
}

const QA_REPLAY_DISTRIBUTION: NarrativeEndingDistributionResponse = {
  template_id: QA_REPLAY_TEMPLATE.template_id,
  total_completed: 8,
  entries: [
    { label: "victory", count: 5 },
    { label: "compromised", count: 3 },
  ],
}

const QA_REPLAY_OPENING: NarrativeStoryMessage = {
  ord: 1,
  role: "narrator",
  content:
    "Rain folds over the observatory glass while Victor gathers the donor circle near the west door. Ilya keeps one hand on the archive key and watches who looks at the ledger first.",
  chosen_option_index: null,
  options: [
    {
      label: "[Reveal] Show Ilya the crescent seal rubbing.",
      hint: "Start with proof she can verify before Victor notices.",
      handle: "Reveal",
    },
    {
      label: "[Ask] Ask Victor why the donor ledger moved.",
      hint: "Put pressure on Victor while the room is still watching.",
      handle: "Ask",
    },
    {
      label: "[Cover] Keep the west door in view while Ilya checks the shelf.",
      hint: "Buy time without letting the ledger leave the room.",
      handle: "Cover",
    },
  ],
  npc_pulse: [
    {
      npc_id: "victor",
      state: "guarded",
      shift: "wary",
      reason: "He sees you watching the ledger table.",
    },
  ],
  inventory_delta: null,
  diary: null,
  played_leverage: null,
}

function buildQaReplaySession(role: NarrativePlayerRole): NarrativeStartSessionResponse["session"] {
  return {
    session_id: "qa-replay-new-run",
    template_id: QA_REPLAY_TEMPLATE.template_id,
    template_title: QA_REPLAY_TEMPLATE.title,
    template_seed: QA_REPLAY_TEMPLATE.seed,
    template_title_i18n: QA_REPLAY_TEMPLATE.title_i18n,
    template_summary_i18n: QA_REPLAY_TEMPLATE.summary_i18n,
    player_user_id: "qa-local-viewer",
    turn_count: 0,
    turn_budget: 6,
    difficulty: "story",
    player_role: role,
    ending_label: null,
    ending_subtitle: null,
    ending_tier: null,
    early_terminated: false,
    created_at: "2026-06-22T00:05:00Z",
    last_active_at: "2026-06-22T00:05:00Z",
  }
}

function buildQaReplayStartedStory(role: NarrativePlayerRole): NarrativeStoryHistoryResponse {
  return {
    template: QA_REPLAY_TEMPLATE,
    session: buildQaReplaySession(role),
    messages: [QA_REPLAY_OPENING],
    agent_events: [],
    gameplay_envelope: null,
  }
}

function buildQaReplayAdvance(request: NarrativeAdvanceTurnRequest): NarrativeAdvanceTurnResponse {
  const selectedIndex = request.chosen_option_index ?? 0
  const selectedOption = QA_REPLAY_OPENING.options[selectedIndex] ?? QA_REPLAY_OPENING.options[0]
  return {
    player_message: {
      ord: 2,
      role: "player",
      content: selectedOption.label.replace(/^\[[^\]]+\]\s*/, ""),
      chosen_option_index: null,
      options: [],
      npc_pulse: [],
      inventory_delta: null,
      diary: request.diary ?? null,
      played_leverage: null,
    },
    narrator_message: {
      ord: 3,
      role: "narrator",
      content:
        "Ilya follows your cue and draws the room toward the ledger. Victor cannot move it without making the donors ask why.",
      chosen_option_index: null,
      options: [
        {
          label: "[Press] Ask Victor who signed the crescent page.",
          hint: "Use the room's attention before he can split the witnesses.",
          handle: "Press",
        },
        {
          label: "[Search] Check the west shelf while Ilya holds the room.",
          hint: "Look for the missing ledger gap while pressure stays public.",
          handle: "Search",
        },
        {
          label: "[Hold] Keep Victor near the service door.",
          hint: "Stop him from leaving while the proof is still fragile.",
          handle: "Hold",
        },
      ],
      npc_pulse: [
        {
          npc_id: "victor",
          state: "cornered",
          shift: "wary",
          reason: "The donor circle is watching his hands instead of his speech.",
        },
      ],
      inventory_delta: {
        added: ["Ledger page attention"],
        removed: [],
        reason: "The room now sees the crescent mark as evidence.",
      },
      diary: null,
      played_leverage: null,
    },
    agent_plan: null,
    agent_events: [],
    gameplay_envelope: null,
    ending: null,
    is_complete: false,
  }
}

export function ReplayFixture({
  onBackHome,
  onOpenTemplate,
}: {
  onBackHome: () => void
  onOpenTemplate: (templateId: string) => void
}) {
  const [fixtureView, setFixtureView] = useState<"replay" | "template" | "play">("replay")
  const [startedStory, setStartedStory] = useState<NarrativeStoryHistoryResponse | null>(null)

  const qaTemplateApi = {
    getNarrativeTemplate: async () => QA_REPLAY_TEMPLATE,
    getNarrativeEndingDistribution: async () => QA_REPLAY_DISTRIBUTION,
    updateNarrativeTemplateVisibility: async () => QA_REPLAY_TEMPLATE,
    startNarrativeSession: async (
      _templateId: string,
      request?: NarrativeStartSessionRequest,
    ): Promise<NarrativeStartSessionResponse> => {
      const roleIndex = request?.player_role_index ?? 0
      const role = QA_REPLAY_TEMPLATE.player_role_options?.[roleIndex] ?? qaReplayPrimaryRole
      const session = buildQaReplaySession(role)
      setStartedStory(buildQaReplayStartedStory(role))
      return {
        template: QA_REPLAY_TEMPLATE,
        session,
        opening: QA_REPLAY_OPENING,
      }
    },
  }

  const qaPlayApi = {
    getNarrativeStory: async () => startedStory ?? buildQaReplayStartedStory(qaReplayPrimaryRole),
    getNarrativeLLMEvents: async () => ({ items: [] }),
    getNarrativeSessionEnding: async () => null,
    advanceNarrativeTurn: async (
      _sessionId: string,
      request: NarrativeAdvanceTurnRequest,
    ) => buildQaReplayAdvance(request),
  }

  const handleOpenTemplate = (templateId: string) => {
    if (templateId !== QA_REPLAY.template_id) {
      onOpenTemplate(templateId)
      return
    }
    setFixtureView("template")
  }

  return (
    <div data-replay-fixture="true">
      {fixtureView === "template" ? (
        <TemplateDetailPage
          templateId={QA_REPLAY.template_id}
          onBackHome={onBackHome}
          onOpenCreate={onBackHome}
          onSessionStarted={() => setFixtureView("play")}
          apiClient={qaTemplateApi}
        />
      ) : fixtureView === "play" ? (
        <PlayPage
          sessionId="qa-replay-new-run"
          onBackHome={onBackHome}
          apiClient={qaPlayApi}
        />
      ) : (
        <ReplayPage
          sessionId={QA_REPLAY.session_id}
          onBackHome={onBackHome}
          onOpenTemplate={handleOpenTemplate}
          apiClient={qaReplayApi}
        />
      )}
    </div>
  )
}

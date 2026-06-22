import type { NarrativePublicReplayResponse } from "../../api/contracts"
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

export function ReplayFixture({
  onBackHome,
  onOpenTemplate,
}: {
  onBackHome: () => void
  onOpenTemplate: (templateId: string) => void
}) {
  return (
    <div data-replay-fixture="true">
      <ReplayPage
        sessionId={QA_REPLAY.session_id}
        onBackHome={onBackHome}
        onOpenTemplate={onOpenTemplate}
        apiClient={qaReplayApi}
      />
    </div>
  )
}

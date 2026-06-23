import { useState } from "react"
import type { NarrativeEnding, NarrativeStoryMessage } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"
import { EndingScreen } from "./ending-screen"

const ENDING_MESSAGES: NarrativeStoryMessage[] = [
  {
    ord: 0,
    role: "narrator",
    content: "The awards sponsor locks the green-room corridor while the livestream countdown keeps running.",
    options: [],
    chosen_option_index: null,
  },
  {
    ord: 1,
    role: "player",
    content: "[Hold] Ask the producer to freeze the livestream countdown.",
    options: [],
    chosen_option_index: null,
  },
  {
    ord: 2,
    role: "narrator",
    content: "The producer stops the countdown. The sponsor is forced to answer while the missing badge sits in full view.",
    options: [],
    chosen_option_index: null,
  },
  {
    ord: 3,
    role: "player",
    content: "[Reveal] Show the producer the empty green-room badge.",
    options: [],
    chosen_option_index: null,
  },
  {
    ord: 4,
    role: "narrator",
    content: "The badge puts the corridor story on record. The room stops treating the disappearance like gossip.",
    options: [],
    chosen_option_index: null,
  },
  {
    ord: 5,
    role: "player",
    content: "[Press] Tell the sponsor the control-room timestamp is already copied.",
    options: [],
    chosen_option_index: null,
  },
  {
    ord: 6,
    role: "narrator",
    content: "The sponsor gives up the private schedule. The singer is found before the broadcast becomes a cover story.",
    options: [],
    chosen_option_index: null,
  },
]

const HIGHLIGHT_ENDING: NarrativeEnding = {
  label: "自由",
  subtitle: "The room lets the truth leave with you",
  tier: "victory",
  passage:
    "The countdown ends with the sponsor answering in public, not behind another locked door. You leave with the copied timestamp, the singer's route, and enough witnesses that the room cannot fold the story back into rumor.",
  highlights: [
    {
      beat_ord: 2,
      headline: "The countdown stopped",
      body_excerpt: "The producer stops the countdown. The sponsor is forced to answer while the missing badge sits in full view.",
      why_pivotal: "The ending becomes possible because the room has time to verify the badge instead of reacting to panic.",
    },
    {
      beat_ord: 6,
      headline: "The private schedule surfaced",
      body_excerpt: "The sponsor gives up the private schedule. The singer is found before the broadcast becomes a cover story.",
      why_pivotal: "The last move converts public pressure into evidence instead of another accusation.",
    },
  ],
  branches: [
    {
      pivot_beat_ord: 2,
      chosen_path_summary: "You held the countdown long enough to make the sponsor answer in the room.",
      alternate_path_summary: "If you had pushed the sponsor first, the room would split into competing rumors.",
      alternate_ending_label: "妥协",
      alternate_ending_tier: "compromised",
      rationale: "Pressure without time keeps the singer safe, but leaves the cover story partly intact.",
    },
    {
      pivot_beat_ord: 4,
      chosen_path_summary: "You made the badge visible before naming the copied timestamp.",
      alternate_path_summary: "If you had hidden the badge, the timestamp would sound like a threat instead of proof.",
      alternate_ending_label: "复仇",
      alternate_ending_tier: "victory",
      rationale: "The alternate route wins harder, but burns the producer's cooperation.",
    },
  ],
}

const RECAP_ENDING: NarrativeEnding = {
  label: "妥协",
  subtitle: "Enough truth survives to change the room",
  tier: "compromised",
  passage:
    "The broadcast still goes out, but the missing singer is no longer alone inside the sponsor's version of the night. The copied timestamp stays with the producer, and the next morning starts from a fact instead of a whisper.",
  highlights: [],
  branches: [],
}

export function PlayEndingFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [copiedCase, setCopiedCase] = useState<"highlight" | "recap" | null>(null)
  const [lastAction, setLastAction] = useState("")

  const markShared = (caseId: "highlight" | "recap") => {
    setCopiedCase(caseId)
    setLastAction(caseId === "highlight" ? "share-highlight" : "share-recap")
  }
  const markReplay = (caseId: "highlight" | "recap") => {
    setLastAction(caseId === "highlight" ? "replay-highlight" : "replay-recap")
  }
  const markReadFull = (caseId: "highlight" | "recap") => {
    setLastAction(caseId === "highlight" ? "read-full-highlight" : "read-full-recap")
  }

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "32px",
        gap: 34,
      }}
      data-play-ending-fixture="true"
      data-play-ending-fixture-action={lastAction || undefined}
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
          gap: 28,
        }}
        aria-label="Ending recap"
      >
        <div data-play-ending-fixture-case="highlight">
          <EndingScreen
            ending={HIGHLIGHT_ENDING}
            sessionId="qa-ending-highlight"
            templateId="qa-ending-template"
            messages={ENDING_MESSAGES}
            bookmarkedOrds={new Set([4, 6])}
            shareCopied={copiedCase === "highlight"}
            onShare={() => markShared("highlight")}
            onReadFullStory={() => markReadFull("highlight")}
            onPlayAgain={() => markReplay("highlight")}
            onBackHome={onBackHome}
          />
        </div>
        <div data-play-ending-fixture-case="recap">
          <EndingScreen
            ending={RECAP_ENDING}
            sessionId="qa-ending-recap"
            templateId="qa-ending-template"
            messages={ENDING_MESSAGES}
            bookmarkedOrds={new Set()}
            shareCopied={copiedCase === "recap"}
            onShare={() => markShared("recap")}
            onReadFullStory={() => markReadFull("recap")}
            onPlayAgain={() => markReplay("recap")}
            onBackHome={onBackHome}
          />
        </div>
      </section>
    </main>
  )
}

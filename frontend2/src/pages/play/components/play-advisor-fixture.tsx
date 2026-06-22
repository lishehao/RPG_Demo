import { useMemo, useState } from "react"
import { AnimatePresence } from "motion/react"
import type { NarrativeAdvisorAskRequest, NarrativeAdvisorMessage } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { getAdvisorAvatar } from "../../../shared/lib/webtoon-assets"
import { ppStyles } from "../play-styles"
import type { ActionCommitmentSummary } from "../play-types"
import {
  AdvisorFab,
  AdvisorSidechat,
  type AdvisorSidechatApiClient,
} from "./advisor-panel"

const ADVISOR_PERSONA = "Dana Vale, the calm friend reading pressure from the lobby."
const ADVISOR_SESSION_ID = "qa-advisor-session"
const ADVISOR_TEMPLATE_ID = "qa-play-advisor"

const INITIAL_MESSAGES: NarrativeAdvisorMessage[] = [
  {
    ord: 0,
    role: "player",
    content: "I want to ask the producer for help, but I don't want to submit the move yet.",
  },
  {
    ord: 1,
    role: "advisor",
    content:
      "Keep it narrow: ask what the producer can verify in the room, then decide whether that answer earns your move.",
  },
]

const ADVISOR_SUGGESTIONS = [
  "What is the safest way to test the producer before I commit?",
  "Which line keeps pressure on the sponsor without spending my move?",
  "If I use the badge now, what pushback should I expect?",
]

const COMMITMENT_SUMMARY: ActionCommitmentSummary = {
  kind: "option",
  kicker: "Move under review",
  title: "Ask the producer to freeze the livestream countdown",
  detail: "The advisor can test wording and risk; the move is still yours to submit.",
  motive: "Protect the missing singer without tipping off the sponsor.",
}

function advisorAnswerFor(request: NarrativeAdvisorAskRequest): string {
  if (request.oracle_mode) {
    return "Deep read: lead with the countdown, not the accusation. It keeps the producer aligned and makes the sponsor answer after the room has one shared fact."
  }
  if (/badge/i.test(request.question)) {
    return "Use the badge as proof, not as a threat. Ask who had access to the green-room door before you name the sponsor."
  }
  if (/sponsor|pressure/i.test(request.question)) {
    return "Keep the sponsor public but indirect. Ask for the timeline first, then let the contradiction do the pressure."
  }
  return "Start with one verifiable detail. The producer can answer that without taking over, and you still choose the actual move."
}

function createLocalAdvisorApi(): AdvisorSidechatApiClient {
  let nextOrd = INITIAL_MESSAGES.length
  return {
    async getNarrativeAdvisorHistory() {
      return {
        persona: ADVISOR_PERSONA,
        messages: INITIAL_MESSAGES,
      }
    },
    async askNarrativeAdvisor(_sessionId, request) {
      await new Promise((resolve) => window.setTimeout(resolve, 160))
      const player_message: NarrativeAdvisorMessage = {
        ord: nextOrd++,
        role: "player",
        content: request.question,
      }
      const advisor_message: NarrativeAdvisorMessage = {
        ord: nextOrd++,
        role: "advisor",
        content: advisorAnswerFor(request),
      }
      return {
        player_message,
        advisor_message,
        oracle_used: request.oracle_mode === true,
        turn_budget_after: request.oracle_mode ? 3 : null,
      }
    },
  }
}

export function PlayAdvisorFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [advisorOpen, setAdvisorOpen] = useState(false)
  const [turnsRemaining, setTurnsRemaining] = useState(4)
  const [lastAction, setLastAction] = useState("closed")
  const advisorAvatar = getAdvisorAvatar(ADVISOR_TEMPLATE_ID, ADVISOR_PERSONA)
  const localAdvisorApi = useMemo(() => createLocalAdvisorApi(), [])

  const openAdvisor = () => {
    setAdvisorOpen(true)
    setLastAction("open")
  }
  const closeAdvisor = () => {
    setAdvisorOpen(false)
    setLastAction("close")
  }

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "32px",
        gap: 22,
      }}
      data-play-advisor-fixture="true"
      data-play-advisor-fixture-state={advisorOpen ? "open" : "closed"}
      data-play-advisor-fixture-action={lastAction}
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
          width: "min(100%, 820px)",
          display: "grid",
          gap: 14,
          color: "rgba(255,248,232,0.92)",
        }}
        aria-label="Advisor help panel"
      >
        <span style={ppStyles.runKicker}>Second read available</span>
        <h1
          style={{
            margin: 0,
            fontFamily: "var(--font-narrative)",
            fontSize: 28,
            lineHeight: 1.05,
            letterSpacing: 0,
          }}
        >
          Ask before you commit the move
        </h1>
        <p
          style={{
            margin: 0,
            maxWidth: 620,
            color: "rgba(246,239,222,0.76)",
            lineHeight: 1.55,
          }}
        >
          The countdown is still running. Your friend can test risk and wording, but the next story move stays unsubmitted until you choose it.
        </p>
        <div
          style={{
            ...ppStyles.advisorContextLine,
            margin: 0,
            width: "min(100%, 680px)",
            maxWidth: "100%",
            boxSizing: "border-box",
          }}
          data-play-advisor-fixture-context="true"
        >
          <span style={ppStyles.advisorContextKicker}>{COMMITMENT_SUMMARY.kicker}</span>
          <span style={ppStyles.advisorContextText}>
            {COMMITMENT_SUMMARY.title} · {COMMITMENT_SUMMARY.detail}
          </span>
        </div>
      </section>

      <AnimatePresence>
        {!advisorOpen ? (
          <AdvisorFab
            onOpen={openAdvisor}
            avatarUrl={advisorAvatar}
            persona={ADVISOR_PERSONA}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {advisorOpen ? (
          <AdvisorSidechat
            sessionId={ADVISOR_SESSION_ID}
            persona={ADVISOR_PERSONA}
            avatarUrl={advisorAvatar}
            turnsRemaining={turnsRemaining}
            isComplete={false}
            isCommitmentActive
            commitmentSummary={COMMITMENT_SUMMARY}
            suggestions={ADVISOR_SUGGESTIONS}
            apiClient={localAdvisorApi}
            onClose={closeAdvisor}
            onOracleConsumed={(newBudget) => {
              setTurnsRemaining(newBudget)
              setLastAction("deep-read")
            }}
          />
        ) : null}
      </AnimatePresence>
    </main>
  )
}

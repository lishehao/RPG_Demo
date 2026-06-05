import { useRef, useState } from "react"
import { motion } from "motion/react"
import { useApi } from "../../app/api-context"
import { useAuth } from "../../app/auth-context"
import { Header } from "../../shared/ui/header"
import { friendlyError } from "../../shared/lib/friendly-error"
import { useLanguage } from "../../shared/lib/i18n"
import {
  REVIEWER_DEMO_ACTIONS,
  REVIEWER_DEMO_SEED,
  REVIEWER_DEMO_TITLE,
} from "./portfolio-data"

function reviewerLaunchError(err: unknown): string {
  const message = friendlyError(err, "Could not launch the reviewer demo.")
  const lower = message.toLowerCase()
  if (
    lower.includes("ai service isn't configured") ||
    lower.includes("ai service is briefly offline") ||
    lower.includes("can't reach the ai backend") ||
    lower.includes("this move did not connect") ||
    lower.includes("server hit a snag")
  ) {
    return "This curated reviewer run is unavailable in this build. Use the normal author flow, or open a reviewed session link to inspect Runtime Inspector evidence."
  }
  return message
}

export function ReviewerPage({
  onBackHome,
  onOpenCreate,
  onSessionStarted,
}: {
  onBackHome: () => void
  onOpenCreate: () => void
  onSessionStarted: (sessionId: string) => void
}) {
  const api = useApi()
  const auth = useAuth()
  const { setLang } = useLanguage()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inflightRef = useRef(false)

  const handleStart = async () => {
    if (inflightRef.current || auth.loading) return
    inflightRef.current = true
    setBusy(true)
    setError(null)
    setLang("en")
    try {
      if (auth.isAnonymous) {
        await auth.login("portfolio_reviewer")
      }
      const briefResponse = await api.createNarrativeStoryBrief({
        seed: REVIEWER_DEMO_SEED,
        language: "en",
        desired_tension_profile: "high_drama",
      })
      if (!briefResponse.can_generate) {
        throw new Error("The reviewer seed could not be prepared as a playable Brief.")
      }
      const response = await api.createNarrativeTemplate({
        seed: REVIEWER_DEMO_SEED,
        visibility: "unlisted",
        turn_budget: 12,
        difficulty: "story",
        language: "en",
        story_brief: briefResponse.brief,
      })
      onSessionStarted(response.session.session_id)
    } catch (err) {
      setError(reviewerLaunchError(err))
      inflightRef.current = false
      setBusy(false)
    }
  }

  return (
    <div className="reviewer-page">
      <Header onHome={onBackHome} onCreate={onOpenCreate} />
      <main className="reviewer-main">
        <motion.section
          className="reviewer-hero"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, ease: "easeOut" }}
        >
          <div className="story-illustration-slot reviewer-hero__art" aria-hidden="true">
            <span className="story-illustration-slot__label">Runtime evidence board</span>
          </div>
          <span className="ts-tag">Reviewer Mode</span>
          <h1>{REVIEWER_DEMO_TITLE}</h1>
          <p>
            A locked English demo path designed for portfolio review. It starts
            a real session, opens a hand-drawn case-file play surface, and
            exposes the runtime inspector after the reviewed run starts.
          </p>
          <blockquote>"{REVIEWER_DEMO_SEED}"</blockquote>
          <div className="reviewer-actions">
            <button
              className="reviewer-action reviewer-action--primary"
              type="button"
              onClick={() => void handleStart()}
              disabled={busy || auth.loading}
            >
              {busy ? "Launching demo..." : "Start curated run"}
            </button>
            <button className="reviewer-action reviewer-action--secondary" type="button" onClick={onOpenCreate} disabled={busy}>
              Use normal author flow
            </button>
          </div>
          {error ? <div className="reviewer-error">{error}</div> : null}
        </motion.section>

        <ol className="reviewer-checklist" aria-label="Reviewer path">
          {REVIEWER_DEMO_ACTIONS.map((item, idx) => (
            <li key={item}>
              <span>{String(idx + 1).padStart(2, "0")}</span>
              <p>{item}</p>
            </li>
          ))}
        </ol>
      </main>
    </div>
  )
}

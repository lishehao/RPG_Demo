import { useEffect, useRef, useState } from "react"
import { motion } from "motion/react"
import { useApi } from "../../app/api-context"
import { useAuth } from "../../app/auth-context"
import { Header } from "../../shared/ui/header"
import { useLanguage } from "../../shared/lib/i18n"
import {
  REVIEWER_DEMO_ACTIONS,
  REVIEWER_DEMO_SEED,
  REVIEWER_DEMO_TITLE,
} from "./portfolio-data"

type LaunchPhase = "ready" | "auth" | "brief" | "runtime" | "opening"

const REVIEWER_LAUNCH_STEPS: Array<{
  phase: Exclude<LaunchPhase, "ready">
  title: string
  detail: string
}> = [
  {
    phase: "auth",
    title: "Reviewer session",
    detail: "Prepares a temporary reviewer session when the demo needs one.",
  },
  {
    phase: "brief",
    title: "Story brief",
    detail: "Builds the cast, role pressure, and narrative constraints from the locked seed.",
  },
  {
    phase: "runtime",
    title: "Playable run",
    detail: "Creates the first scene, choices, advisor context, and evidence summary reviewers inspect beside play.",
  },
  {
    phase: "opening",
    title: "Evidence mode",
    detail: "Opens the run with reviewer-only evidence summary beside the normal story UI.",
  },
]

const REVIEWER_EVIDENCE_CHECKS = [
  {
    label: "Playable state",
    detail: "The run opens with current next moves and turn budget, not a static transcript.",
  },
  {
    label: "Consequence after one move",
    detail: "Play one move, then verify character reactions and story-item consequences.",
  },
  {
    label: "Evidence limits",
    detail: "The opening shows playable setup; consequence evidence waits until the run produces it.",
  },
  {
    label: "Replay artifact",
    detail: "A completed run should become highlights, Full read, and same-opening restart evidence.",
  },
] as const

const REVIEWER_HERO_PROOF_POINTS = [
  {
    label: "Real run",
    detail: "Launch creates a playable session from the locked seed, not a static mockup.",
  },
  {
    label: "One-move consequence",
    detail: "Take one move and inspect how the room, assets, and next choices change.",
  },
  {
    label: "Evidence boundary",
    detail: "Reviewer evidence stays beside Play and should be cited only after the public-link check passes.",
  },
] as const

const REVIEWER_LAUNCH_ERROR =
  "The reviewer run did not open this time."

const REVIEWER_LAUNCH_RECOVERY =
  "The locked seed and evidence checklist are still here. Retry the reviewer run, review the Portfolio evidence page, write your own story, or return to Story Desk."

const launchPhaseIndex = (phase: LaunchPhase) =>
  REVIEWER_LAUNCH_STEPS.findIndex((step) => step.phase === phase)

function canOpenLocalQaRoute() {
  const host = window.location.hostname
  return host === "localhost" || host === "127.0.0.1" || host === "::1"
}

export function ReviewerPage({
  onBackHome,
  onOpenCreate,
  onOpenPortfolio,
  onSessionStarted,
}: {
  onBackHome: () => void
  onOpenCreate: () => void
  onOpenPortfolio: () => void
  onSessionStarted: (sessionId: string) => void
}) {
  const api = useApi()
  const auth = useAuth()
  const { setLang } = useLanguage()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [launchPhase, setLaunchPhase] = useState<LaunchPhase>("ready")
  const inflightRef = useRef(false)
  const launchPlanRef = useRef<HTMLElement | null>(null)
  const launchErrorRef = useRef<HTMLDivElement | null>(null)
  const localQaAvailable = canOpenLocalQaRoute()

  useEffect(() => {
    setLang("en")
  }, [setLang])

  useEffect(() => {
    if (!busy || launchPhase === "ready") return
    const frame = window.requestAnimationFrame(() => {
      const plan = launchPlanRef.current
      if (!plan) return
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      plan.scrollIntoView({
        behavior: prefersReducedMotion ? "auto" : "smooth",
        block: "start",
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [busy, launchPhase])

  useEffect(() => {
    if (!error) return
    const frame = window.requestAnimationFrame(() => {
      const panel = launchErrorRef.current
      if (!panel) return
      panel.scrollIntoView({
        behavior: "auto",
        block: "center",
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [error])

  const handleStart = async () => {
    if (inflightRef.current || auth.loading) return
    inflightRef.current = true
    setBusy(true)
    setError(null)
    setLaunchPhase(auth.isAnonymous ? "auth" : "brief")
    setLang("en")
    try {
      if (auth.isAnonymous) {
        await auth.login("portfolio_reviewer")
      }
      setLaunchPhase("brief")
      const briefResponse = await api.createNarrativeStoryBrief({
        seed: REVIEWER_DEMO_SEED,
        language: "en",
        desired_tension_profile: "high_drama",
      })
      setLaunchPhase("runtime")
      const response = await api.createNarrativeTemplate({
        seed: REVIEWER_DEMO_SEED,
        visibility: "unlisted",
        turn_budget: 12,
        difficulty: "story",
        language: "en",
        story_brief: briefResponse.brief,
      })
      setLaunchPhase("opening")
      onSessionStarted(response.session.session_id)
    } catch {
      setError(REVIEWER_LAUNCH_ERROR)
      inflightRef.current = false
      setBusy(false)
      setLaunchPhase("ready")
    }
  }

  const activeLaunchIndex = busy ? launchPhaseIndex(launchPhase) : -1

  return (
    <div className="reviewer-page">
      <Header onHome={onBackHome} onCreate={onOpenCreate} showBackButton />
      <main className="reviewer-main">
        <motion.section
          className="reviewer-hero"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, ease: "easeOut" }}
        >
          <span className="ts-tag">Reviewer Mode</span>
          <h1>{REVIEWER_DEMO_TITLE}</h1>
          <p>
            A locked English demo path designed for portfolio review. It starts
            a real session, keeps the player-facing story UI intact, and opens
            a reviewer evidence summary for playable state and the first
            consequence after a move.
          </p>
          <p className="reviewer-local-evidence-note" data-reviewer-local-evidence-note="true">
            Public evidence boundary: inspect the current local build here. For
            application links, cite this reviewer run only after the public-link
            check passes; otherwise use the reviewer cut.
          </p>
          <div className="reviewer-actions">
            <button
              className="reviewer-action reviewer-action--primary"
              type="button"
              onClick={() => void handleStart()}
              disabled={busy || auth.loading}
              data-reviewer-launch-cta={busy ? "starting" : "ready"}
            >
              {busy ? "Launching demo..." : "Start reviewer run"}
            </button>
            <button className="reviewer-action reviewer-action--secondary" type="button" onClick={onOpenCreate} disabled={busy}>
              Write your own story
            </button>
          </div>
          <ul
            className="reviewer-hero-proof"
            aria-label="Reviewer run evidence"
            data-reviewer-hero-proof-strip="true"
          >
            {REVIEWER_HERO_PROOF_POINTS.map((item) => (
              <li key={item.label} data-reviewer-hero-proof-item={item.label}>
                <strong>{item.label}</strong>
                <span>{item.detail}</span>
              </li>
            ))}
          </ul>
          <section
            className="reviewer-evidence-preview"
            aria-label="Evidence to verify after launch"
            data-reviewer-evidence-preview="true"
          >
            <div className="reviewer-evidence-preview__head">
              <span>After launch, verify</span>
              <strong>4 evidence checks</strong>
            </div>
            <ol>
              {REVIEWER_EVIDENCE_CHECKS.map((item) => (
                <li key={item.label} data-reviewer-evidence-preview-item={item.label}>
                  <strong>{item.label}</strong>
                  <p>{item.detail}</p>
                </li>
              ))}
            </ol>
          </section>
          {localQaAvailable ? (
            <a
              className="reviewer-local-evidence-link"
              href="#/qa/play-reviewer-evidence"
              data-reviewer-local-evidence-fixture-link="true"
            >
              Open local evidence check
            </a>
          ) : null}
          <div className="reviewer-seed-summary" data-reviewer-seed-summary="true">
            <span>Locked seed preview</span>
            <strong>Missing singer, live awards stream, sponsor pressure; no violence or blackmail.</strong>
          </div>
          <section
            className="reviewer-launch-plan"
            aria-label="Reviewer launch progress"
            data-reviewer-launch-plan="true"
            data-reviewer-launch-state={busy ? launchPhase : "ready"}
            ref={launchPlanRef}
          >
            <div className="reviewer-launch-plan__head">
              <span>{busy ? "Preparing reviewer run" : "What the start button prepares"}</span>
              <strong>{busy && activeLaunchIndex >= 0 ? REVIEWER_LAUNCH_STEPS[activeLaunchIndex].title : "4 steps"}</strong>
            </div>
            <ol>
              {REVIEWER_LAUNCH_STEPS.map((step, idx) => {
                const state = !busy
                  ? "waiting"
                  : idx < activeLaunchIndex
                    ? "done"
                    : idx === activeLaunchIndex
                      ? "active"
                      : "waiting"
                return (
                  <li
                    key={step.phase}
                    data-reviewer-launch-step={step.phase}
                    data-reviewer-launch-step-state={state}
                  >
                    <span>{String(idx + 1).padStart(2, "0")}</span>
                    <div>
                      <strong>{step.title}</strong>
                      <p>{step.detail}</p>
                    </div>
                  </li>
                )
              })}
            </ol>
          </section>
          <details className="reviewer-seed-details" data-reviewer-seed-details="true">
            <summary>Read locked seed</summary>
            <blockquote>"{REVIEWER_DEMO_SEED}"</blockquote>
          </details>
          {error ? (
            <div
              className="reviewer-error"
              data-reviewer-launch-error="true"
              ref={launchErrorRef}
              role="status"
              aria-live="polite"
            >
              <strong>{error}</strong>
              <p>{REVIEWER_LAUNCH_RECOVERY}</p>
              <div className="reviewer-error__actions" data-reviewer-launch-error-actions="true">
                <button
                  className="reviewer-error__action reviewer-error__action--primary"
                  type="button"
                  onClick={() => void handleStart()}
                  disabled={busy || auth.loading}
                  data-reviewer-launch-error-retry="true"
                >
                  Retry reviewer run
                </button>
                <button
                  className="reviewer-error__action"
                  type="button"
                  onClick={onOpenPortfolio}
                  disabled={busy}
                  data-reviewer-launch-error-portfolio="true"
                >
                  Review portfolio evidence
                </button>
                {localQaAvailable ? (
                  <a
                    className="reviewer-error__action"
                    href="#/qa/play-reviewer-evidence"
                    data-reviewer-launch-error-local-proof="true"
                  >
                    Open local evidence check
                  </a>
                ) : null}
                <button
                  className="reviewer-error__action"
                  type="button"
                  onClick={onOpenCreate}
                  disabled={busy}
                  data-reviewer-launch-error-create="true"
                >
                  Write your own story
                </button>
                <button
                  className="reviewer-error__action"
                  type="button"
                  onClick={onBackHome}
                  disabled={busy}
                  data-reviewer-launch-error-home="true"
                >
                  Story Desk
                </button>
              </div>
            </div>
          ) : null}
        </motion.section>

        <ol className="reviewer-checklist" aria-label="Reviewer run">
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

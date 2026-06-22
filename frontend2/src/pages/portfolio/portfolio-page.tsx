import { useEffect, useState } from "react"
import { motion } from "motion/react"
import { Header } from "../../shared/ui/header"
import { useLanguage } from "../../shared/lib/i18n"
import {
  CASE_STUDY_POINTS,
  EVIDENCE_PACKET_URL,
  INTERACTION_LOOP,
  LOCAL_DEMO_MP4_URL,
  PIPELINE_STEPS,
  PORTFOLIO_METRICS,
  PUBLIC_REPO_URL,
  REVIEWER_DEMO_ACTIONS,
  REVIEWER_DEMO_SEED,
  REVIEWER_DEMO_TITLE,
  SYSTEM_MAP_URL,
  YOUTUBE_DEMO_URL,
} from "./portfolio-data"

const PORTFOLIO_REVIEWER_CUT_POSTER = "/portfolio/admissions-trailer-contact.jpg"

const PORTFOLIO_REVIEW_ORDER = [
  {
    step: "watch",
    title: "Watch 75s reviewer cut",
    detail: "See the bounded product loop before opening the live reviewer path.",
  },
  {
    step: "launch",
    title: "Open Reviewer path",
    detail: "Use #/portfolio -> #/reviewer to verify the locked seed and generated play surface.",
  },
  {
    step: "story-desk-start",
    title: "Verify Story Desk start",
    detail: "Local build only: open a populated Story Desk card and confirm it lands in a readable first turn.",
    localHref: "#/qa/home-start",
    localLabel: "Open local Story Desk start fixture",
  },
  {
    step: "inspect",
    title: "Inspect evidence",
    detail: "Use reviewer mode to check state, advisor boundary, and ending logic.",
    localHref: "#/qa/play-reviewer-evidence",
    localLabel: "Open local evidence fixture",
  },
  {
    step: "replay",
    title: "Verify replay artifact",
    detail: "Local build only: inspect a completed memory with highlights, Full read, advisor side-chat, and same-opening fork framing.",
    localHref: "#/qa/replay",
    localLabel: "Open local replay fixture",
  },
] as const

const PORTFOLIO_EVIDENCE_BOUNDARY = [
  {
    label: "Public artifact",
    detail: "Video and written case study show the intended reviewer journey and product thesis.",
  },
  {
    label: "Checked reviewer path",
    detail: "In the checked build, the Reviewer route lets evaluators inspect playable state, consequences, and evidence hooks.",
  },
  {
    label: "Not claimed",
    detail: "This is portfolio-grade AI product-system evidence, not proof of a launched consumer product or broad user adoption.",
  },
] as const

const PORTFOLIO_REVIEW_LENS = [
  {
    label: "Player loop",
    detail: "Read a scene, compare a few meaningful moves, act once, then follow the consequence.",
  },
  {
    label: "Reviewer path",
    detail: "Watch the 75s cut, launch #/reviewer, then inspect state and consequence evidence.",
  },
  {
    label: "Claim boundary",
    detail: "Portfolio-grade AI product-system evidence, not a launched consumer adoption claim.",
  },
] as const

const PORTFOLIO_TARGET_USER_MODEL = [
  {
    label: "Target player",
    detail:
      "For story-first players who want a compact mobile drama, not a blank writing canvas or a dashboard.",
  },
  {
    label: "Content rhythm",
    detail:
      "Read the current scene, compare a few meaningful moves, act once, then use the consequence to choose the next beat.",
  },
  {
    label: "UI promise",
    detail:
      "Keep narrative context and decision context together; keep reviewer evidence separate from the normal player surface.",
  },
] as const

const PORTFOLIO_PUBLIC_EVIDENCE_GATE = {
  label: "Public evidence gate",
  summary:
    "Public repo and Pages links can lag this local build. If preflight fails, use the reviewer cut for orientation only.",
  detail:
    "Before sending a public GitHub Pages or repository link, run the public-evidence preflight. If it fails, do not cite the current Portfolio, Reviewer path, Story Desk, Create, Play, or Replay routes as public evidence until the intended branch is pushed, deployed, rechecked, and the preflight passes.",
  command: "python3 tools/portfolio_public_evidence_preflight.py",
} as const

function canOpenLocalQaRoute() {
  const host = window.location.hostname
  return host === "localhost" || host === "127.0.0.1" || host === "::1"
}

export function PortfolioPage({
  onBackHome,
  onOpenCreate,
  onOpenReviewer,
}: {
  onBackHome: () => void
  onOpenCreate: () => void
  onOpenReviewer: () => void
}) {
  const [activeStep, setActiveStep] = useState(0)
  const step = PIPELINE_STEPS[activeStep]
  const localQaAvailable = canOpenLocalQaRoute()
  const { setLang } = useLanguage()

  useEffect(() => {
    setLang("en")
  }, [setLang])

  return (
    <div className="portfolio-page">
      <Header onHome={onBackHome} onCreate={onOpenCreate} showBackButton />
      <main className="portfolio-main">
        <motion.section
          className="portfolio-hero"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.36, ease: "easeOut" }}
        >
          <div className="portfolio-hero__content">
            <span className="ts-tag">Portfolio Case Study</span>
            <h1>Tiny Stories is an inspectable AI narrative runtime.</h1>
            <p>
              Watch the 75s reviewer cut first. Tiny Stories is a short,
              story-first mobile episode where players read a scene, compare a
              few meaningful moves, act once, and follow the consequence
              without turning Play into a dashboard.
            </p>
            <ul
              className="portfolio-hero__lens"
              aria-label="Portfolio review lens"
              data-portfolio-hero-lens="true"
            >
              {PORTFOLIO_REVIEW_LENS.map((item) => (
                <li key={item.label} data-portfolio-hero-lens-item={item.label}>
                  <strong>{item.label}</strong>
                  <span>{item.detail}</span>
                </li>
              ))}
            </ul>
            <div className="portfolio-hero__actions">
              <a className="portfolio-action portfolio-action--primary" href={YOUTUBE_DEMO_URL} target="_blank" rel="noreferrer">
                Watch 75s reviewer cut
              </a>
              <button className="portfolio-action portfolio-action--secondary" type="button" onClick={onOpenReviewer}>
                Launch reviewer route
              </button>
            </div>
            <p className="portfolio-hero__evidence-note" data-portfolio-hero-evidence-note="true">
              Use the reviewer cut for orientation only; do not cite the current local route as public evidence until preflight passes.
            </p>
          </div>
          <div className="portfolio-hero__video" aria-label="Tiny Stories reviewer cut preview">
            <a
              className="portfolio-video-card"
              href={YOUTUBE_DEMO_URL}
              target="_blank"
              rel="noreferrer"
              aria-label="Open the 75 second Tiny Stories reviewer cut"
            >
              <img src={PORTFOLIO_REVIEWER_CUT_POSTER} alt="Tiny Stories reviewer cut contact sheet" />
              <span className="portfolio-video-card__badge">75s reviewer cut</span>
            </a>
            <p>
              Start with the reviewer cut, then use the checked Reviewer path to
              inspect state and consequences.
              <br />
              <span className="portfolio-video-card__links" data-portfolio-video-links="true">
                <a href={YOUTUBE_DEMO_URL} target="_blank" rel="noreferrer" data-portfolio-video-link="youtube">Open on YouTube</a>
                <span aria-hidden="true">·</span>
                <a href={LOCAL_DEMO_MP4_URL} data-portfolio-video-link="mp4">Open MP4 backup</a>
              </span>
            </p>
          </div>
          <div className="portfolio-hero__review" data-portfolio-hero-review-frame="true">
            <aside
              className="portfolio-public-evidence-gate"
              aria-label="Public evidence visibility gate"
              data-portfolio-public-evidence-gate="true"
            >
              <strong>{PORTFOLIO_PUBLIC_EVIDENCE_GATE.label}</strong>
              <p data-portfolio-public-evidence-gate-summary="true">{PORTFOLIO_PUBLIC_EVIDENCE_GATE.summary}</p>
              <details data-portfolio-public-evidence-gate-details="true">
                <summary>How to verify public links</summary>
                <p>{PORTFOLIO_PUBLIC_EVIDENCE_GATE.detail}</p>
                <code>{PORTFOLIO_PUBLIC_EVIDENCE_GATE.command}</code>
              </details>
            </aside>
            <ol
              className="portfolio-review-order"
              aria-label="Recommended portfolio review order"
              data-portfolio-review-order="true"
            >
              {PORTFOLIO_REVIEW_ORDER.map((item, idx) => (
                <li key={item.step} data-portfolio-review-step={item.step}>
                  <span>{String(idx + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                    {"localHref" in item ? (
                      localQaAvailable ? (
                        <a
                          href={item.localHref}
                          data-portfolio-review-local-evidence={item.step}
                        >
                          {item.localLabel}
                        </a>
                      ) : (
                        <code data-portfolio-review-local-evidence={item.step}>{item.localHref}</code>
                      )
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </motion.section>

        <section className="portfolio-proofbar" aria-label="Portfolio proof points">
          {PORTFOLIO_METRICS.map((metric) => (
            <div className="portfolio-proofbar__item" key={metric.value}>
              <strong>{metric.value}</strong>
              <span>{metric.label}</span>
            </div>
          ))}
        </section>

        <section
          className="portfolio-section portfolio-target-user"
          aria-label="Target player and content model"
          data-portfolio-target-user-model="true"
        >
          <div className="portfolio-section__head">
            <span className="portfolio-kicker">Target user</span>
            <h2>Who this loop is for.</h2>
            <p>
              The product bet is not infinite AI fiction. It is a compact
              episode where a player can understand the scene, make one strong
              choice at a time, and see why the next choice opened.
            </p>
          </div>
          <div className="portfolio-target-user__grid">
            {PORTFOLIO_TARGET_USER_MODEL.map((item) => (
              <article className="portfolio-target-user__item" key={item.label}>
                <strong>{item.label}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          className="portfolio-section portfolio-evidence-boundary"
          aria-label="Admissions evidence boundary"
          data-portfolio-evidence-boundary="true"
        >
          <div className="portfolio-section__head">
            <span className="portfolio-kicker">Evidence boundary</span>
            <h2>What this page can fairly prove.</h2>
          </div>
          <div className="portfolio-evidence-boundary__grid">
            {PORTFOLIO_EVIDENCE_BOUNDARY.map((item) => (
              <article className="portfolio-evidence-boundary__item" key={item.label}>
                <strong>{item.label}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <div
            className="portfolio-source-evidence"
            aria-label="Source evidence links"
            data-portfolio-source-evidence="true"
          >
            <span>Source evidence</span>
            <p>
              Open the repo and system map to review code, docs, tests, and the
              narrow runtime path behind this demo. These are public-main
              references and may lag the current local build. Before relying on
              public links, run the public-evidence preflight; if it fails,
              use the reviewer cut for orientation only and do not cite the
              current local route as public evidence until preflight passes.
            </p>
            <div>
              <a href={PUBLIC_REPO_URL} target="_blank" rel="noreferrer">GitHub repo</a>
              <a href={SYSTEM_MAP_URL} target="_blank" rel="noreferrer">System map</a>
              <a href={EVIDENCE_PACKET_URL} target="_blank" rel="noreferrer">Evidence packet</a>
            </div>
          </div>
        </section>

        <section className="portfolio-section portfolio-section--two">
          <div>
            <span className="portfolio-kicker">Curated reviewer path</span>
            <h2>{REVIEWER_DEMO_TITLE}</h2>
            <p className="portfolio-lede">
              The demo seed is intentionally dense: live awards stakes, a
              missing singer, sponsor pressure, witness and reporter tension,
              and a publicist forced to decide what to reveal before panic
              spreads. It gives the generator enough dramatic structure to show
              the system at its strongest.
            </p>
            <blockquote className="portfolio-seed">"{REVIEWER_DEMO_SEED}"</blockquote>
          </div>
          <ol className="portfolio-review-list">
            {REVIEWER_DEMO_ACTIONS.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ol>
        </section>

        <section className="portfolio-section">
          <div className="portfolio-section__head">
            <span className="portfolio-kicker">System Inspector</span>
            <h2>What the evaluator should notice</h2>
          </div>
          <div className="portfolio-inspector">
            <div className="portfolio-inspector__tabs" role="tablist" aria-label="System pipeline">
              {PIPELINE_STEPS.map((item, idx) => (
                <button
                  key={item.title}
                  className={idx === activeStep ? "is-active" : ""}
                  type="button"
                  role="tab"
                  aria-selected={idx === activeStep}
                  onClick={() => setActiveStep(idx)}
                >
                  <span>{item.eyebrow}</span>
                  {item.title}
                </button>
              ))}
            </div>
            <motion.div
              className="portfolio-inspector__detail"
              key={step.title}
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
            >
              <span>{step.eyebrow}</span>
              <h3>{step.title}</h3>
              <p>{step.summary}</p>
              <div>{step.proof}</div>
            </motion.div>
          </div>
        </section>

        <section className="portfolio-loop" aria-label="Playable demo loop">
          <div className="portfolio-loop__visual">
            <span className="portfolio-kicker">Playable loop</span>
            <h2>One reviewed path, four product states.</h2>
            <p>
              The portfolio read is strongest when the evaluator can follow the
              product loop and see the artifact each state leaves behind.
            </p>
          </div>
          <ol className="portfolio-loop__steps">
            {INTERACTION_LOOP.map((item) => (
              <li key={item.eyebrow}>
                <span>{item.eyebrow}</span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                  <em>{item.artifact}</em>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="portfolio-section portfolio-case-grid">
          {CASE_STUDY_POINTS.map((item) => (
            <article className="portfolio-case-card" key={item.title}>
              <span className="portfolio-kicker">{item.title}</span>
              <p>{item.body}</p>
            </article>
          ))}
        </section>

        <section className="portfolio-section portfolio-final">
          <span className="portfolio-kicker">Portfolio framing</span>
          <h2>Not a prompt toy. A portfolio-grade AI runtime case study.</h2>
          <p>
            The strongest application story is that you can turn story generation
            into a user-facing workflow: controlled entry, typed state,
            explainable progression, visual polish, and an artifact someone can
            replay or evaluate. The honest claim is product-system evidence, not
            broad market validation.
          </p>
        </section>
      </main>
    </div>
  )
}

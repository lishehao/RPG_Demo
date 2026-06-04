/**
 * Shared loading state — 3-dot bouncing animation in muted text color.
 *
 * Used by every page when waiting for an initial fetch (home, world
 * detail, play, replay). Replaces scattered "加载中…" plain text with
 * a single visual vocabulary so users learn one signal: dots = waiting.
 *
 * Variants:
 * - `inline`: small, sits inside flow (e.g. inside a card's center)
 * - `page`: large block, used as full-page placeholder
 */

import type { CSSProperties } from "react"
import { motion } from "motion/react"

// Bouncing dots use ease-in-out, not the project-standard ease-out:
// the dot needs to slow at BOTH the apex and the floor, not just the
// apex. This is the one place where deviating from EASE_OUT_CURVE is
// correct — kept as a named constant so it's clearly a deliberate
// choice, not a copy-paste mistake.
const BOUNCE_EASE = [0.4, 0, 0.6, 1] as const
const BOUNCE_DURATION_S = 0.96
const STAGGER_PER_DOT_S = 0.16

const DOT_TRANSITION = (idx: number) => ({
  duration: BOUNCE_DURATION_S,
  ease: BOUNCE_EASE,
  repeat: Infinity,
  delay: idx * STAGGER_PER_DOT_S,
})

export function LoadingShim({
  label,
  variant = "page",
}: {
  label?: string
  variant?: "inline" | "page"
}) {
  const wrapStyle =
    variant === "inline" ? styles.wrapInline : styles.wrapPage
  return (
    <div style={wrapStyle} role="status" aria-live="polite">
      <div style={styles.dotRow}>
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            style={styles.dot}
            animate={{ y: [0, -5, 0], opacity: [0.45, 1, 0.45] }}
            transition={DOT_TRANSITION(i)}
          />
        ))}
      </div>
      {label ? <div style={styles.label}>{label}</div> : null}
    </div>
  )
}

const styles: Record<string, CSSProperties> = {
  wrapPage: {
    width: "min(560px, calc(100% - 32px))",
    minHeight: 260,
    margin: "64px auto",
    padding: "54px 36px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    color: "var(--text-faint)",
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.075), rgba(255,255,255,0) 42%), linear-gradient(180deg, rgba(13,15,20,0.94), rgba(8,9,13,0.98))",
    border: "1px solid rgba(245,200,120,0.15)",
    borderTop: "3px solid rgba(208,138,79,0.58)",
    borderRadius: 2,
    boxShadow: "0 28px 86px rgba(0,0,0,0.42), inset 0 1px 0 rgba(255,255,255,0.07)",
  },
  wrapInline: {
    padding: "20px 24px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 10,
    color: "var(--text-faint)",
  },
  dotRow: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  },
  dot: {
    width: 18,
    height: 6,
    borderRadius: 0,
    background: "linear-gradient(90deg, var(--accent), rgba(148,164,109,0.78))",
    display: "inline-block",
  },
  label: {
    fontSize: 13,
    color: "var(--text-faint)",
    fontStyle: "normal",
    letterSpacing: 0,
    fontWeight: 680,
  },
}

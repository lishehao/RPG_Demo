/**
 * Shared EmptyState — used for "not found", "blocked", "auth required"
 * fallback screens. Borrows the empty-plaza visual language from the
 * home page so all dead-end screens feel like the same product family.
 *
 * Variant `notFound`: page-level fallback when a session/template is
 *   missing or inaccessible.
 * Variant `auth`: page-level fallback when login is required.
 *
 * Both render a hero image (plaza), a title, a hint, and an optional
 * primary button.
 */

import type { CSSProperties, ReactNode } from "react"
import { motion } from "motion/react"
import { itemTransition } from "../lib/motion-presets"
import { getEmptyPlazaImage } from "../lib/webtoon-assets"

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <motion.div
      style={styles.wrap}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={itemTransition}
    >
      <div
        style={{
          ...styles.hero,
          backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.05) 0%, rgba(20,16,12,0.62) 78%, var(--bg) 100%), url(${getEmptyPlazaImage()})`,
        }}
      />
      <div style={styles.body}>
        <h2 style={styles.title}>{title}</h2>
        {hint ? <p style={styles.hint}>{hint}</p> : null}
        {action ? <div style={styles.action}>{action}</div> : null}
      </div>
    </motion.div>
  )
}

const styles: Record<string, CSSProperties> = {
  wrap: {
    width: "min(620px, calc(100% - 32px))",
    maxWidth: 620,
    margin: "60px auto",
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.075), rgba(255,255,255,0) 42%), linear-gradient(180deg, rgba(13,15,20,0.95), rgba(8,9,13,0.98))",
    borderRadius: 2,
    border: "1px solid rgba(245,200,120,0.16)",
    borderTop: "3px solid rgba(148,164,109,0.52)",
    boxShadow: "0 30px 92px rgba(0,0,0,0.44), inset 0 1px 0 rgba(255,255,255,0.07)",
    overflow: "hidden",
  },
  hero: {
    width: "100%",
    height: 188,
    backgroundSize: "cover",
    backgroundPosition: "center",
  },
  body: {
    padding: "24px 26px 30px",
    textAlign: "left" as const,
    color: "var(--text-muted)",
  },
  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 25,
    fontWeight: 500,
    color: "var(--text)",
    margin: "0 0 10px",
    lineHeight: 1.35,
  },
  hint: {
    fontSize: 13.5,
    lineHeight: 1.7,
    margin: "0 0 18px",
    fontStyle: "normal" as const,
  },
  action: {
    display: "flex",
    justifyContent: "flex-start",
    gap: 8,
    flexWrap: "wrap",
  },
}

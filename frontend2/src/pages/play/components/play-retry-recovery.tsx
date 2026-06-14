import { useEffect, useState } from "react"
import { motion } from "motion/react"
import { useT } from "../../../shared/lib/i18n"
import { transitions } from "../../../shared/lib/motion-presets"
import { ppStyles } from "../play-styles"

export type PlayRetryRecovery = {
  kicker: string
  title: string
  detail: string
  chips: string[]
}

export function PlayRetryRecoveryBanner({
  recovery,
  error,
  busy,
  compact = false,
  onRetry,
}: {
  recovery: PlayRetryRecovery | null
  error: string
  busy: boolean
  compact?: boolean
  onRetry?: () => void
}) {
  const t = useT()
  const signalLabel = t("play.recovery_signal_label")
  const recoveryKicker = recovery?.kicker ?? t("play.recovery_generic_kicker")
  const recoveryTitle = recovery?.title ?? t("play.recovery_generic_title")
  const recoveryDetail = recovery?.detail ?? t("play.recovery_generic_detail")
  const alertSummary = `${recoveryKicker}. ${recoveryTitle}. ${recoveryDetail} ${signalLabel}: ${error}`
  return (
    <motion.div
      key="play-error"
      data-play-retry-recovery="true"
      style={{
        ...ppStyles.errorInline,
        ...(compact ? ppStyles.errorInlineCompact : null),
      }}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={transitions.snap}
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      aria-label={alertSummary}
    >
      <div style={ppStyles.errorInlineCopy}>
        <span style={ppStyles.errorInlineKicker}>
          {recoveryKicker}
        </span>
        <strong style={ppStyles.errorInlineTitle}>
          {recoveryTitle}
        </strong>
        <span style={ppStyles.errorInlineText}>
          {recoveryDetail}
        </span>
        <span
          style={ppStyles.errorInlineSignal}
          aria-label={`${signalLabel}: ${error}`}
        >
          <span style={ppStyles.errorInlineSignalLabel}>{signalLabel}:</span>{" "}
          <span style={ppStyles.errorInlineSignalBody}>{error}</span>
        </span>
        {recovery?.chips.length ? (
          <span style={ppStyles.errorInlineChips}>
            {recovery.chips.map((chip) => (
              <span key={chip} style={ppStyles.errorInlineChip} title={chip}>{chip}</span>
            ))}
          </span>
        ) : null}
      </div>
      {onRetry ? (
        <button
          type="button"
          style={{
            ...ppStyles.errorInlineRetry,
            ...(busy ? ppStyles.errorInlineRetryDisabled : null),
          }}
          aria-label={t("play.recovery_retry_same_title")}
          title={t("play.recovery_retry_same_title")}
          disabled={busy}
          onClick={onRetry}
        >
          {t("play.recovery_retry_same")}
        </button>
      ) : null}
    </motion.div>
  )
}

export function PlayRetryFailureFixture({ onBackHome }: { onBackHome: () => void }) {
  const t = useT()
  const [busy, setBusy] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!busy) return
    const timer = window.setTimeout(() => {
      setBusy(false)
      setRetryCount((count) => count + 1)
    }, 650)
    return () => window.clearTimeout(timer)
  }, [busy])

  const recovery: PlayRetryRecovery = {
    kicker: t("play.recovery_kicker"),
    title: t("play.recovery_option_title"),
    detail: t("play.recovery_option_detail"),
    chips: [t("play.recovery_chip_choice", { choice: "Tell the producer to hold the livestream." })],
  }

  return (
    <main
      style={{
        ...ppStyles.page,
        minHeight: "100vh",
        padding: "32px",
        gap: 18,
      }}
      data-play-retry-fixture="true"
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
          maxWidth: 760,
          display: "grid",
          gap: 14,
        }}
        aria-label="Play recovery rehearsal"
      >
        <p style={{ margin: 0, color: "rgba(255,245,230,0.76)", lineHeight: 1.5 }}>
          This rehearsal keeps the recovery state repeatable without advancing the story.
        </p>
        <PlayRetryRecoveryBanner
          recovery={recovery}
          error={t("play.error_advance")}
          busy={busy}
          onRetry={() => {
            if (busy) return
            setBusy(true)
          }}
        />
        <p
          style={{ margin: 0, color: "rgba(255,226,178,0.82)", fontSize: 12 }}
          aria-live="polite"
        >
          {busy ? "Retry is held in place." : `Retry cycles completed: ${retryCount}`}
        </p>
      </section>
    </main>
  )
}

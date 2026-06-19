import { motion } from "motion/react"
import { useT } from "../../../shared/lib/i18n"
import { transitions } from "../../../shared/lib/motion-presets"
import { useCompactLayout } from "../hooks/use-compact-layout"
import { ppStyles } from "../play-styles"
import { scrollToPlayActionArea } from "./play-action-jump-utils"

export function PlayActionJumpButton({
  onClick = scrollToPlayActionArea,
  detail,
  compactDetail,
  stage,
}: {
  onClick?: () => void
  detail?: string
  compactDetail?: string
  stage?: string
}) {
  const t = useT()
  const compactJump = useCompactLayout("(max-width: 680px)")
  const detailCopy = compactJump ? compactDetail?.trim() : detail?.trim()
  return (
    <motion.button
      key="play-action-jump"
      type="button"
      data-play-action-jump="true"
      data-play-action-jump-stage={stage}
      data-play-action-jump-compact={compactJump ? "true" : "false"}
      style={{
        ...ppStyles.actionJumpButton,
        ...(compactJump ? ppStyles.actionJumpButtonCompact : null),
      }}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 12 }}
      transition={transitions.snap}
      onPointerDown={onClick}
      onClick={onClick}
      aria-label={t("play.action_jump_title")}
      title={t("play.action_jump_title")}
    >
      <span
        style={{
          ...ppStyles.actionJumpCopy,
          ...(compactJump ? ppStyles.actionJumpCopyCompact : null),
        }}
      >
        <span
          style={{
            ...ppStyles.actionJumpKicker,
            ...(compactJump ? ppStyles.actionJumpKickerCompact : null),
          }}
        >
          {t("play.action_jump_kicker")}
        </span>
        <strong
          style={{
            ...ppStyles.actionJumpText,
            ...(compactJump ? ppStyles.actionJumpTextCompact : null),
          }}
        >
          {t("play.action_jump_label")}
        </strong>
        {detailCopy ? (
          <span style={ppStyles.actionJumpDetail} data-play-action-jump-detail="true">
            {detailCopy}
          </span>
        ) : null}
      </span>
      <span
        style={{
          ...ppStyles.actionJumpArrow,
          ...(compactJump ? ppStyles.actionJumpArrowCompact : null),
        }}
        aria-hidden
      >
        ↓
      </span>
    </motion.button>
  )
}

import { motion } from "motion/react"
import { useT } from "../../../shared/lib/i18n"
import { transitions } from "../../../shared/lib/motion-presets"
import { ppStyles } from "../play-styles"
import { scrollToPlayActionArea } from "./play-action-jump-utils"

export function PlayActionJumpButton({
  onClick = scrollToPlayActionArea,
  detail,
  stage,
}: {
  onClick?: () => void
  detail?: string
  stage?: string
}) {
  const t = useT()
  const detailCopy = detail?.trim()
  return (
    <motion.button
      key="play-action-jump"
      type="button"
      data-play-action-jump="true"
      data-play-action-jump-stage={stage}
      style={ppStyles.actionJumpButton}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 12 }}
      transition={transitions.snap}
      onPointerDown={onClick}
      onClick={onClick}
      aria-label={t("play.action_jump_title")}
      title={t("play.action_jump_title")}
    >
      <span style={ppStyles.actionJumpCopy}>
        <span style={ppStyles.actionJumpKicker}>{t("play.action_jump_kicker")}</span>
        <strong style={ppStyles.actionJumpText}>{t("play.action_jump_label")}</strong>
        {detailCopy ? (
          <span style={ppStyles.actionJumpDetail} data-play-action-jump-detail="true">
            {detailCopy}
          </span>
        ) : null}
      </span>
      <span style={ppStyles.actionJumpArrow} aria-hidden>↓</span>
    </motion.button>
  )
}

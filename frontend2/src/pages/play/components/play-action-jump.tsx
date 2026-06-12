import { motion } from "motion/react"
import { useT } from "../../../shared/lib/i18n"
import { transitions } from "../../../shared/lib/motion-presets"
import { ppStyles } from "../play-styles"
import { scrollToPlayActionArea } from "./play-action-jump-utils"

export function PlayActionJumpButton({ onClick = scrollToPlayActionArea }: { onClick?: () => void }) {
  const t = useT()
  return (
    <motion.button
      key="play-action-jump"
      type="button"
      data-play-action-jump="true"
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
      <span style={ppStyles.actionJumpKicker}>{t("play.action_jump_kicker")}</span>
      <strong style={ppStyles.actionJumpText}>{t("play.action_jump_label")}</strong>
    </motion.button>
  )
}

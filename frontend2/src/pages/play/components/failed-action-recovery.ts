import type { NarrativeStoryMessage } from "../../../api/contracts"
import type { useT } from "../../../shared/lib/i18n"
import type { PlayAdvanceAction } from "../play-types"
import type { PlayRetryRecovery } from "./play-retry-recovery"

function truncateRecoveryText(value: string, max = 64): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

export function buildFailedActionRecovery({
  action,
  options,
  castNameById,
  t,
}: {
  action: PlayAdvanceAction | null
  options: NarrativeStoryMessage["options"]
  castNameById: Record<string, string>
  t: ReturnType<typeof useT>
}): PlayRetryRecovery | null {
  if (!action) return null
  const chips: string[] = []
  if (action.diary?.trim()) {
    chips.push(t("play.recovery_private_attached"))
  }

  if (action.played_leverage) {
    const target = castNameById[action.played_leverage.npc_id] ?? action.played_leverage.npc_id
    chips.unshift(t("play.recovery_chip_target", { target }))
    chips.push(t("play.recovery_chip_evidence", {
      evidence: truncateRecoveryText(action.played_leverage.leverage),
    }))
    return {
      kicker: t("play.recovery_kicker"),
      title: t("play.recovery_leverage_title"),
      detail: t("play.recovery_leverage_detail"),
      chips,
    }
  }

  if (action.free_input?.trim()) {
    chips.unshift(t("play.recovery_chip_move", {
      move: truncateRecoveryText(action.free_input),
    }))
    return {
      kicker: t("play.recovery_kicker"),
      title: t("play.recovery_free_title"),
      detail: t("play.recovery_free_detail"),
      chips,
    }
  }

  if (action.chosen_option_index != null) {
    const option = options[action.chosen_option_index]
    if (option) {
      chips.unshift(t("play.recovery_chip_choice", {
        choice: truncateRecoveryText(option.label),
      }))
    }
    return {
      kicker: t("play.recovery_kicker"),
      title: t("play.recovery_option_title"),
      detail: t("play.recovery_option_detail"),
      chips,
    }
  }

  return null
}

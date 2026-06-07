import type { NarrativePlayedLeverageCard } from "../../api/contracts"

export type PlayAdvanceAction = {
  chosen_option_index?: number
  free_input?: string
  diary?: string
  played_leverage?: NarrativePlayedLeverageCard
}

export type LeverageCardView = {
  card_id: string
  npc_id: string
  target_name: string
  leverage: string
  used: boolean
}

export type ActionCommitmentSummary = {
  kind: "option" | "leverage" | "free"
  kicker: string
  title: string
  detail?: string
  motive?: string
}

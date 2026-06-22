import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"

export type FreeActionFocusContextView = {
  kind: "actor" | "inventory" | "resource"
  id: string
  label: string
  detail: string
}

export type FreeActionStarterMove = {
  label: string
  text: string
}

export function buildFreeActionStarterMoves({
  context,
  t,
}: {
  context: FreeActionFocusContextView | null
  t: ReturnType<typeof useT>
}): FreeActionStarterMove[] {
  if (context?.kind === "actor") {
    return [
      {
        label: t("play.free_starter_actor_ask_label"),
        text: t("play.free_starter_actor_ask_text", { name: context.label }),
      },
      {
        label: t("play.free_starter_actor_pressure_label"),
        text: t("play.free_starter_actor_pressure_text", { name: context.label }),
      },
    ]
  }

  if (context?.kind === "inventory") {
    return [
      {
        label: t("play.free_starter_inventory_show_label"),
        text: t("play.free_starter_inventory_show_text", { item: context.label }),
      },
      {
        label: t("play.free_starter_inventory_ask_label"),
        text: t("play.free_starter_inventory_ask_text", { item: context.label }),
      },
    ]
  }

  if (context?.kind === "resource") {
    if (context.id === "time") {
      return [
        {
          label: t("play.free_starter_time_buy_label"),
          text: t("play.free_starter_time_buy_text"),
        },
        {
          label: t("play.free_starter_time_force_label"),
          text: t("play.free_starter_time_force_text"),
        },
      ]
    }

    if (context.id === "pressure") {
      return [
        {
          label: t("play.free_starter_pressure_calm_label"),
          text: t("play.free_starter_pressure_calm_text"),
        },
        {
          label: t("play.free_starter_pressure_raise_label"),
          text: t("play.free_starter_pressure_raise_text"),
        },
      ]
    }

    return [
      {
        label: t("play.free_starter_evidence_show_label"),
        text: t("play.free_starter_evidence_show_text"),
      },
      {
        label: t("play.free_starter_evidence_trace_label"),
        text: t("play.free_starter_evidence_trace_text"),
      },
    ]
  }

  return [
    {
      label: t("play.free_starter_general_ask_label"),
      text: t("play.free_starter_general_ask_text"),
    },
    {
      label: t("play.free_starter_general_pressure_label"),
      text: t("play.free_starter_general_pressure_text"),
    },
    {
      label: t("play.free_starter_general_time_label"),
      text: t("play.free_starter_general_time_text"),
    },
  ]
}

export function FreeActionContextBanner({ context }: { context: FreeActionFocusContextView }) {
  const t = useT()

  return (
    <div
      style={ppStyles.freeActionContext}
      data-play-free-action-context="true"
      data-play-free-action-context-kind={context.kind}
      data-play-free-action-context-id={context.id}
    >
      <span style={ppStyles.freeActionContextLabel}>
        {context.kind === "actor"
          ? t("play.free_context_actor_label")
          : context.kind === "inventory"
            ? t("play.free_context_inventory_label")
            : t("play.free_context_resource_label")}
      </span>
      <strong style={ppStyles.freeActionContextName}>
        {context.label}
      </strong>
      <span style={ppStyles.freeActionContextDetail}>
        {context.detail}
      </span>
    </div>
  )
}

export function FreeActionStarterRows({
  starters,
  disabled,
  onUseStarter,
}: {
  starters: FreeActionStarterMove[]
  disabled?: boolean
  onUseStarter: (text: string) => void
}) {
  const t = useT()

  if (starters.length === 0) return null

  return (
    <div
      style={ppStyles.freeActionStarters}
      data-play-free-action-starters="true"
      aria-label={t("play.free_starters_label")}
    >
      <span style={ppStyles.freeActionStartersLabel}>
        {t("play.free_starters_label")}
      </span>
      {starters.map((starter) => (
        <button
          key={starter.label}
          type="button"
          style={ppStyles.freeActionStarterButton}
          onClick={() => onUseStarter(starter.text)}
          disabled={disabled}
          data-play-free-action-starter="true"
          title={starter.text}
          aria-label={t("play.free_starter_apply_title", { move: starter.text })}
        >
          <span style={ppStyles.freeActionStarterLabelText}>
            {starter.label}
          </span>
          <span
            style={ppStyles.freeActionStarterPreview}
            data-play-free-action-starter-preview="true"
          >
            {starter.text}
          </span>
        </button>
      ))}
    </div>
  )
}

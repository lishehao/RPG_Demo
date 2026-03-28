import type { ReactNode } from "react"
import { StudioIcon } from "../../shared/ui/studio-icon"

type SidebarItem = {
  icon: "menu_book" | "reorder" | "person" | "history_edu" | "settings" | "north_east"
  label: string
  active?: boolean
  disabled?: boolean
  onSelect?: () => void
}

export function PlayDomainSidebar({
  title,
  subtitle,
  items,
  footer,
}: {
  title: string
  subtitle: string
  items: SidebarItem[]
  footer?: ReactNode
}) {
  return (
    <aside className="play-domain-sidebar">
      <div className="play-domain-sidebar__head">
        <p className="play-domain-sidebar__title">{title}</p>
        <p className="play-domain-sidebar__subtitle">{subtitle}</p>
      </div>

      <nav className="play-domain-sidebar__nav" aria-label={`${title} navigation`}>
        {items.map((item) => (
          <button
            aria-current={item.active ? "location" : undefined}
            aria-disabled={item.disabled ? "true" : undefined}
            className={`play-domain-sidebar__item ${item.active ? "is-active" : ""} ${item.disabled ? "is-disabled" : ""}`}
            disabled={item.disabled}
            key={item.label}
            onClick={item.onSelect}
            title={item.disabled ? `${item.label} coming soon` : undefined}
            type="button"
          >
            <StudioIcon className="play-domain-sidebar__icon" name={item.icon} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      {footer ? <div className="play-domain-sidebar__footer">{footer}</div> : null}
    </aside>
  )
}

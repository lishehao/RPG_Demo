type StudioIconName =
  | "account_circle"
  | "add"
  | "arrow_forward"
  | "autorenew"
  | "history_edu"
  | "hourglass_top"
  | "menu_book"
  | "north_east"
  | "note_add"
  | "person"
  | "remove"
  | "reorder"
  | "search"
  | "settings"

function iconPath(name: StudioIconName) {
  switch (name) {
    case "account_circle":
      return (
        <>
          <circle cx="12" cy="8.2" r="3.2" />
          <path d="M6.8 18.3c1.5-2.6 3.3-3.9 5.2-3.9 2 0 3.7 1.3 5.2 3.9" />
          <circle cx="12" cy="12" r="9" />
        </>
      )
    case "add":
      return <path d="M12 5.5v13M5.5 12h13" />
    case "arrow_forward":
      return <path d="M5 12h12M13 7l5 5-5 5" />
    case "autorenew":
      return <path d="M18.5 9A7 7 0 0 0 6.2 6.4M5.5 5.5v4.2h4.2M5.5 15A7 7 0 0 0 17.8 17.6M18.5 18.5v-4.2h-4.2" />
    case "history_edu":
      return <path d="M6.5 4.5h8l3 3v12h-11zM14.5 4.5v3h3M9 12.5c1.5-2.3 3-3.8 4.5-4.5-1 2.2-1 4.7 0 7.5M8.5 15.5h7" />
    case "hourglass_top":
      return <path d="M7 4.5h10M7 19.5h10M8.5 5.5c0 2.2 1.2 3.7 3.5 5-2.3 1.3-3.5 2.8-3.5 5M15.5 5.5c0 2.2-1.2 3.7-3.5 5 2.3 1.3 3.5 2.8 3.5 5" />
    case "menu_book":
      return <path d="M6 5.5h8.8c1.8 0 3.2 1.4 3.2 3.2v9.8H9.2A3.2 3.2 0 0 0 6 21V5.5Zm0 0v12.3M9.2 18.5h8.8" />
    case "north_east":
      return <path d="M7 17 17 7M9 7h8v8" />
    case "note_add":
      return <path d="M8 4.5h7l4 4V19H8zM15 4.5v4h4M12 10v6M9 13h6" />
    case "person":
      return (
        <>
          <circle cx="12" cy="8.2" r="3.1" />
          <path d="M6.5 18.5c1.7-3 3.6-4.5 5.5-4.5s3.8 1.5 5.5 4.5" />
        </>
      )
    case "remove":
      return <path d="M5.5 12h13" />
    case "reorder":
      return <path d="M6 7.5h12M6 12h12M6 16.5h12" />
    case "search":
      return <path d="M10.5 17a6.5 6.5 0 1 1 4.9-2.2L19 18.4" />
    case "settings":
      return <path d="M12 8.8a3.2 3.2 0 1 1 0 6.4 3.2 3.2 0 0 1 0-6.4Zm0-4.3 1 2.1 2.3.4.8 2.1 2.1.8-.4 2.3 1.5 1.7-1.5 1.7.4 2.3-2.1.8-.8 2.1-2.3.4-1 2.1-1-2.1-2.3-.4-.8-2.1-2.1-.8.4-2.3L4.5 12l1.5-1.7-.4-2.3 2.1-.8.8-2.1 2.3-.4 1-2.1Z" />
  }
}

export function StudioIcon({
  name,
  className,
  title,
}: {
  name: StudioIconName
  className?: string
  title?: string
}) {
  return (
    <svg
      aria-hidden={title ? undefined : true}
      className={["studio-icon", className].filter(Boolean).join(" ")}
      fill="none"
      role={title ? "img" : "presentation"}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      {title ? <title>{title}</title> : null}
      {iconPath(name)}
    </svg>
  )
}

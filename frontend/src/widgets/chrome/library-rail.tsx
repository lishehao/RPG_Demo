export function LibraryRail() {
  const icons = ["shelves", "menu", "history_edu", "settings"]

  return (
    <aside className="library-rail" aria-hidden="true">
      {icons.map((icon) => (
        <span className="material-symbols-outlined library-rail__icon" key={icon}>
          {icon}
        </span>
      ))}
    </aside>
  )
}

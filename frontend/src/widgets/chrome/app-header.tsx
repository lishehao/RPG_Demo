import type { ChangeEvent } from "react"
import type { AuthUserResponse } from "../../index"

export function AppHeader({
  routeName,
  onOpenCreateStory,
  onOpenLibrary,
  authenticated,
  authLoading,
  user,
  onOpenAuth,
  onLogout,
  searchEnabled = false,
  searchValue = "",
  onSearchChange,
}: {
  routeName: "auth" | "create-story" | "author-loading" | "story-library" | "story-detail" | "play-session"
  onOpenCreateStory: () => void
  onOpenLibrary: () => void
  authenticated: boolean
  authLoading: boolean
  user: AuthUserResponse | null
  onOpenAuth: (mode: "login" | "register") => void
  onLogout: () => void
  searchEnabled?: boolean
  searchValue?: string
  onSearchChange?: (value: string) => void
}) {
  const createActive = routeName === "create-story" || routeName === "author-loading"
  const libraryActive = !createActive
  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    onSearchChange?.(event.target.value)
  }

  return (
    <header className="studio-topbar">
      <div className="studio-topbar__brand">
        <button className="studio-brand-mark" onClick={onOpenCreateStory} type="button">
          Narrative Studio
        </button>

        <nav className="studio-topbar__nav">
          <button className={`studio-topbar__link ${createActive ? "is-active" : ""}`} onClick={onOpenCreateStory} type="button">
            Create
          </button>
          <button className={`studio-topbar__link ${libraryActive ? "is-active" : ""}`} onClick={onOpenLibrary} type="button">
            Library
          </button>
        </nav>
      </div>

      <div className="studio-topbar__tools">
        <label className="studio-search">
          <span aria-hidden="true" className="material-symbols-outlined studio-search__icon">
            search
          </span>
          <input
            disabled={!searchEnabled}
            onChange={handleSearchChange}
            placeholder="Search Library..."
            type="text"
            value={searchEnabled ? searchValue : ""}
          />
        </label>

        {authLoading ? (
          <div className="studio-account-switcher">
            <div className="studio-account-switcher__current">
              <span className="material-symbols-outlined">hourglass_top</span>
              <div>
                <strong>Loading session</strong>
                <span>Checking account</span>
              </div>
            </div>
          </div>
        ) : authenticated && user ? (
          <div className="studio-account-switcher">
            <div className="studio-account-switcher__current">
              <span className="material-symbols-outlined">account_circle</span>
              <div>
                <strong>{user.display_name}</strong>
                <span>{user.email}</span>
              </div>
            </div>
            <div className="studio-account-actions">
              <button className="studio-button studio-button--secondary" onClick={onLogout} type="button">
                Sign Out
              </button>
            </div>
          </div>
        ) : (
          <div className="studio-auth-actions">
            <button className="studio-button studio-button--secondary" onClick={() => onOpenAuth("login")} type="button">
              Sign In
            </button>
            <button className="studio-button studio-button--primary" onClick={() => onOpenAuth("register")} type="button">
              Create Account
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

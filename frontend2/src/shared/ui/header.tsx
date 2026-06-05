import { useState } from "react"
import { useAuth } from "../../app/auth-context"
import { LANGUAGE_OPTIONS, useLanguage, type Lang } from "../lib/i18n"

export function Header({
  onHome,
  onCreate,
  showCreateButton = true,
  createVariant = "button",
  showCaseStudy = false,
}: {
  onHome: () => void
  onCreate: () => void
  showCreateButton?: boolean
  createVariant?: "button" | "link"
  showCaseStudy?: boolean
}) {
  const auth = useAuth()
  const { lang, setLang, t } = useLanguage()
  const [menuOpen, setMenuOpen] = useState(false)
  const accountName = auth.user?.display_name?.trim() || "reader"
  const accountInitial = accountName.slice(0, 1).toUpperCase()

  const handleLogin = () => {
    // Hash routes are app-internal; jumping via location.hash keeps Header
    // independent of the navigate prop chain.
    window.location.hash = "#/login"
  }

  const handlePortfolio = () => {
    window.location.hash = "#/portfolio"
  }

  return (
    <header className="topbar">
      <button className="brand" onClick={onHome} type="button">
        <span className="brand-mark">·</span>
        <strong>Tiny Stories</strong>
      </button>

      <div className="topbar-actions">
        {showCaseStudy ? (
          <button className="topbar-link" type="button" onClick={handlePortfolio}>
            {t("header.case_study")}
          </button>
        ) : null}

        <LanguageToggle lang={lang} onSelect={setLang} />

        {showCreateButton && createVariant === "link" ? (
          <button className="topbar-link topbar-create-link" type="button" onClick={() => onCreate()}>
            {t("header.write_story")}
          </button>
        ) : showCreateButton ? (
          <button className="topbar-link topbar-create-link" type="button" onClick={() => onCreate()}>
            {t("header.write_story")}
          </button>
        ) : null}

        {auth.loading ? (
          <span className="topbar-account__hint">...</span>
        ) : auth.isAnonymous ? (
          <button className="topbar-link topbar-login-link" type="button" onClick={handleLogin}>
            {t("header.login")}
          </button>
        ) : (
          <div className="topbar-account">
            <button
              type="button"
              className="topbar-account__pill"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={accountName}
            >
              <span className="topbar-account__avatar">{accountInitial}</span>
              <span className="topbar-account__name">{accountName}</span>
            </button>
            {menuOpen ? (
              <div className="topbar-account__menu" onMouseLeave={() => setMenuOpen(false)}>
                <button
                  type="button"
                  className="topbar-account__menu-item"
                  onClick={() => {
                    void auth.logout()
                    setMenuOpen(false)
                  }}
                >
                  {t("header.logout")}
                </button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </header>
  )
}

function LanguageToggle({ lang, onSelect }: { lang: Lang; onSelect: (next: Lang) => void }) {
  // Two-pill segmented control. If we add a third locale we'll switch
  // to a dropdown, but two fits inline cleanly.
  return (
    <div className="topbar-lang" role="group" aria-label="language">
      {LANGUAGE_OPTIONS.map((opt) => {
        const active = opt.value === lang
        return (
          <button
            key={opt.value}
            type="button"
            className={`topbar-lang__pill${active ? " topbar-lang__pill--active" : ""}`}
            onClick={() => onSelect(opt.value)}
            aria-pressed={active}
          >
            <span className="topbar-lang__full">{opt.label}</span>
            <span className="topbar-lang__short" aria-hidden>
              {opt.value === "zh" ? "中" : "EN"}
            </span>
          </button>
        )
      })}
    </div>
  )
}

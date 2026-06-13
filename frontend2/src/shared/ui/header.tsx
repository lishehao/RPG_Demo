import { useState } from "react"
import { useAuth } from "../../app/auth-context"
import { LANGUAGE_OPTIONS, useLanguage, type Lang } from "../lib/i18n"

type HeaderProps = {
  onHome: () => void
  onCreate?: () => void
  showCreateButton?: boolean
  createVariant?: "button" | "link"
  showBackButton?: boolean
}

export function Header({
  onHome,
  showBackButton = false,
}: HeaderProps) {
  const auth = useAuth()
  const { lang, setLang, t } = useLanguage()
  const [menuOpen, setMenuOpen] = useState(false)
  const accountName = auth.user?.display_name?.trim() || "reader"
  const accountInitial = accountName.slice(0, 1).toUpperCase()
  const accountLabel = t("header.account")

  const handleLogin = () => {
    // Hash routes are app-internal; jumping via location.hash keeps Header
    // independent of the navigate prop chain.
    window.location.hash = "#/login"
  }

  return (
    <header className={`topbar${showBackButton ? " topbar--with-back" : ""}`}>
      <div className="topbar-left">
        {showBackButton ? (
          <button className="topbar-back" onClick={onHome} type="button">
            {t("action.back_home")}
          </button>
        ) : null}
        <button className="brand" onClick={onHome} type="button">
          <span className="brand-mark">·</span>
          <strong>Tiny Stories</strong>
        </button>
      </div>

      <div className="topbar-actions">
        <LanguageToggle lang={lang} onSelect={setLang} />

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
              aria-label={`${accountLabel}: ${accountName}`}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              title={accountName}
            >
              <span className="topbar-account__avatar" aria-hidden>
                {accountInitial}
              </span>
              <span className="topbar-account__label">{accountLabel}</span>
            </button>
            {menuOpen ? (
              <div className="topbar-account__menu" onMouseLeave={() => setMenuOpen(false)} role="menu">
                <div className="topbar-account__menu-title">{accountName}</div>
                <button
                  type="button"
                  className="topbar-account__menu-item"
                  role="menuitem"
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
  const { t } = useLanguage()
  return (
    <div className="topbar-lang" role="group" aria-label={t("header.lang_label")}>
      {LANGUAGE_OPTIONS.map((opt) => {
        const active = opt.value === lang
        return (
          <button
            key={opt.value}
            type="button"
            className={`topbar-lang__pill${active ? " topbar-lang__pill--active" : ""}`}
            onClick={() => onSelect(opt.value)}
            aria-pressed={active}
            aria-label={opt.label}
          >
            <span className="topbar-lang__short" aria-hidden>
              {opt.value === "zh" ? "中" : "EN"}
            </span>
          </button>
        )
      })}
    </div>
  )
}

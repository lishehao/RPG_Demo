import { useLayoutEffect, useRef } from "react"
import type { AuthUserResponse, StoryLanguage } from "../../index"
import { getStudioBrandName } from "../../shared/lib/studio-brand"
import { uiText } from "../../shared/lib/ui-language"
import { StudioIcon } from "../../shared/ui/studio-icon"

export function AppHeader({
  routeName,
  onOpenCreateStory,
  onOpenLibrary,
  authenticated,
  authLoading,
  user,
  onOpenAuth,
  onLogout,
  onPrefetchAuth,
  onPrefetchCreateStory,
  onPrefetchLibrary,
  uiLanguage,
  onUiLanguageChange,
}: {
  routeName: "auth" | "create-story" | "author-loading" | "story-library" | "story-detail" | "play-session"
  onOpenCreateStory: () => void
  onOpenLibrary: () => void
  authenticated: boolean
  authLoading: boolean
  user: AuthUserResponse | null
  onOpenAuth: (mode: "login" | "register") => void
  onLogout: () => void
  onPrefetchAuth: () => void
  onPrefetchCreateStory: () => void
  onPrefetchLibrary: () => void
  uiLanguage: StoryLanguage
  onUiLanguageChange: (language: StoryLanguage) => void
}) {
  const headerRef = useRef<HTMLElement | null>(null)
  const createActive = routeName === "create-story" || routeName === "author-loading"
  const libraryActive =
    routeName === "story-library" || routeName === "story-detail" || routeName === "play-session"
  const showAuthActions = routeName !== "auth" || authLoading || authenticated
  const studioBrandName = getStudioBrandName(uiLanguage)

  useLayoutEffect(() => {
    const node = headerRef.current
    if (!node) {
      return
    }

    const updateTopbarHeight = () => {
      const nextHeight = `${Math.ceil(node.getBoundingClientRect().height)}px`
      document.documentElement.style.setProperty("--studio-topbar-height", nextHeight)
    }

    updateTopbarHeight()
    const observer = new ResizeObserver(updateTopbarHeight)
    observer.observe(node)
    window.addEventListener("resize", updateTopbarHeight)

    return () => {
      observer.disconnect()
      window.removeEventListener("resize", updateTopbarHeight)
    }
  }, [])

  return (
    <header className="studio-topbar" ref={headerRef}>
      <div className="studio-topbar__primary">
        <div className="studio-topbar__brand">
          <button className="studio-brand-mark" onClick={onOpenCreateStory} type="button">
            {studioBrandName}
          </button>

          <nav className="studio-topbar__nav">
            <button
              className={`studio-topbar__link ${createActive ? "is-active" : ""}`}
              onClick={onOpenCreateStory}
              onFocus={onPrefetchCreateStory}
              onMouseEnter={onPrefetchCreateStory}
              type="button"
            >
              {uiText(uiLanguage, { en: "Create", zh: "创作" })}
            </button>
            <button
              className={`studio-topbar__link ${libraryActive ? "is-active" : ""}`}
              onClick={onOpenLibrary}
              onFocus={onPrefetchLibrary}
              onMouseEnter={onPrefetchLibrary}
              type="button"
            >
              {uiText(uiLanguage, { en: "Library", zh: "故事库" })}
            </button>
          </nav>
        </div>

        <div className="studio-language-switch" role="tablist" aria-label={uiText(uiLanguage, { en: "Interface language", zh: "界面语言" })}>
          <button
            aria-selected={uiLanguage === "en"}
            className={`studio-language-switch__option ${uiLanguage === "en" ? "is-active" : ""}`}
            onClick={() => onUiLanguageChange("en")}
            role="tab"
            type="button"
          >
            EN
          </button>
          <button
            aria-selected={uiLanguage === "zh"}
            className={`studio-language-switch__option ${uiLanguage === "zh" ? "is-active" : ""}`}
            onClick={() => onUiLanguageChange("zh")}
            role="tab"
            type="button"
          >
            中文
          </button>
        </div>
      </div>

      <div className="studio-topbar__tools">
        {!showAuthActions ? null : authLoading ? (
          <div className="studio-account-switcher">
            <div className="studio-account-switcher__current">
              <StudioIcon name="hourglass_top" />
              <div>
                <strong>{uiText(uiLanguage, { en: "Loading session", zh: "正在加载会话" })}</strong>
                <span>{uiText(uiLanguage, { en: "Checking account", zh: "检查账号状态" })}</span>
              </div>
            </div>
          </div>
        ) : authenticated && user ? (
          <div className="studio-account-switcher">
            <div className="studio-account-switcher__current">
              <StudioIcon name="account_circle" />
              <div>
                <strong>{user.display_name}</strong>
                <span>{user.email}</span>
              </div>
            </div>
            <div className="studio-account-actions">
              <button className="studio-button studio-button--secondary" onClick={onLogout} type="button">
                {uiText(uiLanguage, { en: "Sign Out", zh: "退出登录" })}
              </button>
            </div>
          </div>
        ) : (
          <div className="studio-auth-actions">
            <button
              className="studio-button studio-button--secondary"
              onClick={() => onOpenAuth("login")}
              onFocus={onPrefetchAuth}
              onMouseEnter={onPrefetchAuth}
              type="button"
            >
              {uiText(uiLanguage, { en: "Sign In", zh: "登录" })}
            </button>
            <button
              className="studio-button studio-button--primary"
              onClick={() => onOpenAuth("register")}
              onFocus={onPrefetchAuth}
              onMouseEnter={onPrefetchAuth}
              type="button"
            >
              {uiText(uiLanguage, { en: "Create Account", zh: "注册账号" })}
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

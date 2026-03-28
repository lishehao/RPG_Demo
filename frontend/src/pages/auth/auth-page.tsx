import { useEffect, useState } from "react"
import type { StoryLanguage } from "../../index"
import { useAuth } from "../../app/providers/auth-provider"
import { getAuthPasswordRuleText, isValidAuthPassword } from "../../shared/lib/auth-password"
import { toErrorCode, toErrorMessage } from "../../shared/lib/errors"
import { getAuthSurfaceCopy } from "../../shared/lib/story-surface-copy"
import { uiText } from "../../shared/lib/ui-language"

export function AuthPage({
  uiLanguage,
  mode,
  nextHash,
  onResolveAuth,
  onModeChange,
  onOpenLibrary,
}: {
  uiLanguage: StoryLanguage
  mode: "login" | "register"
  nextHash?: string
  onResolveAuth: (nextHash?: string) => void
  onModeChange: (mode: "login" | "register") => void
  onOpenLibrary: () => void
}) {
  const auth = useAuth()
  const copy = getAuthSurfaceCopy(uiLanguage)
  const [displayName, setDisplayName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [attemptedSubmit, setAttemptedSubmit] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const passwordRuleText = getAuthPasswordRuleText(uiLanguage)
  const registerPasswordValid = isValidAuthPassword(password)
  const showRegisterPasswordError = mode === "register" && (password.length > 0 || attemptedSubmit) && !registerPasswordValid
  const showRegisterPasswordSuccess = mode === "register" && password.length > 0 && registerPasswordValid

  useEffect(() => {
    setError(null)
    setAttemptedSubmit(false)
  }, [mode])

  const submit = async () => {
    setError(null)
    setAttemptedSubmit(true)

    if (mode === "register" && !registerPasswordValid) {
      return
    }

    setSubmitting(true)
    try {
      if (mode === "register") {
        await auth.register({
          display_name: displayName.trim(),
          email: email.trim(),
          password,
        })
      } else {
        await auth.login({
          email: email.trim(),
          password,
        })
      }
      onResolveAuth(nextHash)
    } catch (nextError) {
      if (mode === "register" && toErrorCode(nextError) === "auth_password_invalid") {
        setError(passwordRuleText)
      } else {
        setError(toErrorMessage(nextError, uiLanguage))
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="editorial-page-shell">
      <section className="editorial-page auth-page">
        <div className="auth-page__panel">
          <div className="auth-page__intro">
            <p className="editorial-kicker">{copy.kicker}</p>
            <h1 className="editorial-display auth-page__title">
              {mode === "register"
                ? copy.createAccountTitle
                : copy.loginTitle}
            </h1>
            <p className="editorial-support">
              {mode === "register"
                ? copy.createAccountBody
                : copy.loginBody}
            </p>
          </div>

          <div className="auth-page__tabs" role="tablist" aria-label={uiText(uiLanguage, { en: "Authentication mode", zh: "认证模式" })}>
            <button
              className={`auth-page__tab ${mode === "login" ? "is-active" : ""}`}
              onClick={() => onModeChange("login")}
              type="button"
            >
              {uiText(uiLanguage, { en: "Sign In", zh: "登录" })}
            </button>
            <button
              className={`auth-page__tab ${mode === "register" ? "is-active" : ""}`}
              onClick={() => onModeChange("register")}
              type="button"
            >
              {uiText(uiLanguage, { en: "Create Account", zh: "注册账号" })}
            </button>
          </div>

          <form
            className="auth-form"
            onSubmit={(event) => {
              event.preventDefault()
              void submit()
            }}
          >
            {mode === "register" ? (
              <label className="auth-form__field">
                <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Display Name", zh: "显示名称" })}</span>
                <input
                  autoComplete="name"
                  onChange={(event) => {
                    setDisplayName(event.target.value)
                    setError(null)
                  }}
                  type="text"
                  value={displayName}
                />
              </label>
            ) : null}

            <label className="auth-form__field">
              <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Email", zh: "邮箱" })}</span>
              <input
                autoComplete="email"
                onChange={(event) => {
                  setEmail(event.target.value)
                  setError(null)
                }}
                type="email"
                value={email}
              />
            </label>

            <label className="auth-form__field">
              <span className="editorial-metadata-label">{uiText(uiLanguage, { en: "Password", zh: "密码" })}</span>
              <input
                autoComplete={mode === "register" ? "new-password" : "current-password"}
                onChange={(event) => {
                  setPassword(event.target.value)
                  setError(null)
                }}
                type="password"
                value={password}
              />
              {mode === "register" ? (
                <p className={`auth-form__hint ${showRegisterPasswordError ? "is-invalid" : showRegisterPasswordSuccess ? "is-valid" : ""}`}>
                  {passwordRuleText}
                </p>
              ) : null}
            </label>

            {error ? <p className="editorial-error">{error}</p> : null}

            <div className="auth-form__actions">
              <button className="studio-button studio-button--primary studio-button--wide" disabled={submitting || (mode === "register" && !registerPasswordValid)} type="submit">
                {submitting
                  ? uiText(uiLanguage, { en: "Submitting...", zh: "提交中..." })
                  : mode === "register"
                    ? uiText(uiLanguage, { en: "Create Account", zh: "注册账号" })
                    : uiText(uiLanguage, { en: "Sign In", zh: "登录" })}
              </button>
            </div>
            <button className="studio-button studio-button--ghost auth-form__browse" onClick={onOpenLibrary} type="button">
              {copy.browseLibrary}
            </button>
          </form>
        </div>
      </section>
    </main>
  )
}

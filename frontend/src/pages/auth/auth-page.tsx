import { useEffect, useState } from "react"
import { useAuth } from "../../app/providers/auth-provider"
import { toErrorMessage } from "../../shared/lib/errors"

export function AuthPage({
  mode,
  nextHash,
  onResolveAuth,
  onOpenLibrary,
}: {
  mode: "login" | "register"
  nextHash?: string
  onResolveAuth: (nextHash?: string) => void
  onOpenLibrary: () => void
}) {
  const auth = useAuth()
  const [activeMode, setActiveMode] = useState<"login" | "register">(mode)
  const [displayName, setDisplayName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setActiveMode(mode)
    setError(null)
  }, [mode])

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      if (activeMode === "register") {
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
      setError(toErrorMessage(nextError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="editorial-page-shell">
      <section className="editorial-page auth-page">
        <div className="auth-page__panel">
          <div className="auth-page__intro">
            <p className="editorial-kicker">Account Access</p>
            <h1 className="editorial-display auth-page__title">
              {activeMode === "register" ? "Create your account" : "Sign in to continue"}
            </h1>
            <p className="editorial-support">
              {activeMode === "register"
                ? "Create an account to save stories, publish dossiers, and continue play sessions."
                : "Sign in to create, publish, and resume sessions under your own account."}
            </p>
          </div>

          <div className="auth-page__tabs" role="tablist" aria-label="Authentication mode">
            <button
              className={`auth-page__tab ${activeMode === "login" ? "is-active" : ""}`}
              onClick={() => setActiveMode("login")}
              type="button"
            >
              Sign In
            </button>
            <button
              className={`auth-page__tab ${activeMode === "register" ? "is-active" : ""}`}
              onClick={() => setActiveMode("register")}
              type="button"
            >
              Create Account
            </button>
          </div>

          <form
            className="auth-form"
            onSubmit={(event) => {
              event.preventDefault()
              void submit()
            }}
          >
            {activeMode === "register" ? (
              <label className="auth-form__field">
                <span className="editorial-metadata-label">Display Name</span>
                <input autoComplete="name" onChange={(event) => setDisplayName(event.target.value)} type="text" value={displayName} />
              </label>
            ) : null}

            <label className="auth-form__field">
              <span className="editorial-metadata-label">Email</span>
              <input autoComplete="email" onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
            </label>

            <label className="auth-form__field">
              <span className="editorial-metadata-label">Password</span>
              <input autoComplete={activeMode === "register" ? "new-password" : "current-password"} onChange={(event) => setPassword(event.target.value)} type="password" value={password} />
            </label>

            {error ? <p className="editorial-error">{error}</p> : null}

            <div className="auth-form__actions">
              <button className="studio-button studio-button--primary studio-button--wide" disabled={submitting} type="submit">
                {submitting ? "Submitting..." : activeMode === "register" ? "Create Account" : "Sign In"}
              </button>
              <button className="studio-button studio-button--secondary studio-button--wide" onClick={onOpenLibrary} type="button">
                Continue to Library
              </button>
            </div>
          </form>
        </div>
      </section>
    </main>
  )
}

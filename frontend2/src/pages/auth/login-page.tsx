import { type CSSProperties, type FormEvent, useEffect, useMemo, useState } from "react"
import { AnimatePresence, motion, useAnimationControls } from "motion/react"
import { useAuth } from "../../app/auth-context"
import { friendlyError } from "../../shared/lib/friendly-error"
import { useT } from "../../shared/lib/i18n"
import { itemTransition } from "../../shared/lib/motion-presets"
import { PAGE_BG } from "../../shared/lib/webtoon-assets"

const USERNAME_PATTERN = /^[A-Za-z0-9_]{2,20}$/

export function LoginPage({
  next,
  onBackHome,
  onOpenCreate: _onOpenCreate,
  onLoggedIn,
}: {
  next?: string
  onBackHome: () => void
  onOpenCreate: () => void
  onLoggedIn: (next?: string) => void
}) {
  void _onOpenCreate
  const auth = useAuth()
  const t = useT()
  const compactLayout = useCompactLayout()
  const [name, setName] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isCreateEntry = next === "create"
  const [customOpen, setCustomOpen] = useState(!isCreateEntry)
  useEffect(() => {
    setCustomOpen(!isCreateEntry)
  }, [isCreateEntry])
  const showCustomName = !isCreateEntry || customOpen || Boolean(name.trim()) || Boolean(error) || submitting
  const showNameSubmit = !isCreateEntry || Boolean(name.trim()) || submitting
  const guestHandle = useMemo(() => `guest_${Math.random().toString(36).slice(2, 8)}`, [])
  // Shake the input row when an error fires, so the user's eye is
  // drawn to the field that needs fixing without us blocking with a
  // modal. Triggered each time `error` becomes truthy — even if the
  // string is identical to the previous one (so spamming the bad
  // submit re-shakes).
  const inputControls = useAnimationControls()
  useEffect(() => {
    if (!error) return
    void inputControls.start({
      x: [0, -7, 6, -4, 3, -1, 0],
      transition: { duration: 0.42 },
    })
  }, [error, inputControls])

  const submitName = async (rawName: string) => {
    if (submitting) return
    const trimmed = rawName.trim()
    if (!USERNAME_PATTERN.test(trimmed)) {
      setError(t("login.error_username_format"))
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await auth.login(trimmed)
      onLoggedIn(next)
    } catch (err) {
      setError(friendlyError(err, t("login.error_generic")))
      setSubmitting(false)
    }
  }
  const submit = async (e?: FormEvent<HTMLFormElement>) => {
    e?.preventDefault?.()
    await submitName(name)
  }

  return (
    <div style={{ ...lpStyles.page, ...(compactLayout ? lpStyles.pageCompact : null) }}>
      <header style={{ ...lpStyles.header, ...(compactLayout ? lpStyles.headerCompact : null) }}>
        <button style={lpStyles.brandLink} onClick={onBackHome}>
          <span
            style={{
              color: "var(--accent)",
              fontSize: 22,
              lineHeight: 1,
              transform: "translateY(-2px)",
              display: "inline-block",
            }}
          >
            ·
          </span>
          <span style={{ fontFamily: "var(--font-narrative)", fontSize: 18 }}>Tiny Stories</span>
        </button>
      </header>

      <main style={{ ...lpStyles.main, ...(compactLayout ? lpStyles.mainCompact : null) }}>
        <motion.form
          style={{ ...lpStyles.card, ...(compactLayout ? lpStyles.cardCompact : null) }}
          onSubmit={submit}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={itemTransition}
        >
          <span className="ts-tag" style={lpStyles.kicker}>
            {t("login.tag")}
          </span>
          <h1 style={{ ...lpStyles.title, ...(compactLayout ? lpStyles.titleCompact : null) }}>
            {isCreateEntry ? t("login.title_create") : t("login.title")}
          </h1>
          <p style={{ ...lpStyles.sub, ...(compactLayout ? lpStyles.subCompact : null) }}>
            {isCreateEntry ? t("login.sub_create") : t("login.sub")}
          </p>

          {isCreateEntry ? (
            <>
              <button
                type="button"
                style={{
                  ...lpStyles.quickStartButton,
                  ...(compactLayout ? lpStyles.quickStartButtonCompact : null),
                }}
                onClick={() => {
                  setName(guestHandle)
                  void submitName(guestHandle)
                }}
                disabled={submitting}
              >
                <span style={lpStyles.quickStartCopy}>
                  <span style={lpStyles.quickStartLabel}>{t("login.guest_primary")}</span>
                  <span style={lpStyles.quickStartMeta}>{t("login.guest_meta", { name: guestHandle })}</span>
                </span>
                <span style={lpStyles.quickStartArrow} aria-hidden>→</span>
              </button>
              {!showCustomName ? (
                <button
                  type="button"
                  style={lpStyles.customNameToggle}
                  onClick={() => setCustomOpen(true)}
                  disabled={submitting}
                >
                  {t("login.custom_label")}
                </button>
              ) : null}
            </>
          ) : null}

          {showCustomName ? (
            <motion.div style={lpStyles.inputWrap} animate={inputControls}>
              <span style={lpStyles.at}>@</span>
              <input
                style={lpStyles.input}
                placeholder={t("login.placeholder")}
                value={name}
                onChange={(e) => {
                  if (error) setError(null) // clear on retype
                  setName(e.target.value.replace(/^@+/, ""))
                }}
                autoFocus
                spellCheck={false}
                autoComplete="off"
                disabled={submitting}
              />
            </motion.div>
          ) : null}

          <AnimatePresence>
            {error ? (
              <motion.div
                key="login-error"
                style={lpStyles.error}
                initial={{ opacity: 0, height: 0, marginTop: 0 }}
                animate={{ opacity: 1, height: "auto", marginTop: 10 }}
                exit={{ opacity: 0, height: 0, marginTop: 0 }}
                transition={itemTransition}
              >
                {error}
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence initial={false}>
            {showNameSubmit ? (
              <motion.button
                key="name-submit"
                type="submit"
                style={{
                  ...lpStyles.submitAction,
                  alignSelf: "flex-start",
                  marginTop: 14,
                  opacity: !name.trim() || submitting ? 0.5 : 1,
                  pointerEvents: !name.trim() || submitting ? "none" : "auto",
                }}
                initial={isCreateEntry ? { opacity: 0, y: -4, height: 0, marginTop: 0 } : false}
                animate={{ opacity: !name.trim() || submitting ? 0.5 : 1, y: 0, height: "auto", marginTop: 14 }}
                exit={isCreateEntry ? { opacity: 0, y: -4, height: 0, marginTop: 0 } : undefined}
                transition={itemTransition}
              >
                {submitting
                  ? t("login.submit_busy")
                  : isCreateEntry
                    ? t("login.submit_create")
                    : t("login.submit_idle")}
              </motion.button>
            ) : null}
          </AnimatePresence>

          {!isCreateEntry || showCustomName ? (
            <p style={{ ...lpStyles.note, ...(compactLayout ? lpStyles.noteCompact : null) }}>
              {isCreateEntry ? t("login.note_create") : t("login.note")}
            </p>
          ) : null}
        </motion.form>
      </main>
    </div>
  )
}

function useCompactLayout(query = "(max-width: 720px)") {
  const [compact, setCompact] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined") return
    const media = window.matchMedia(query)
    const update = () => setCompact(media.matches)
    update()
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [query])
  return compact
}

const lpStyles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100%",
    background: `linear-gradient(90deg, rgba(12,12,16,0.96) 0%, rgba(12,12,16,0.82) 46%, rgba(12,12,16,0.55) 100%), linear-gradient(180deg, rgba(12,12,16,0.14) 0%, var(--bg) 92%), url(${PAGE_BG.login})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
  },
  pageCompact: {
    backgroundPosition: "58% top",
  },
  header: { padding: "18px 40px", borderBottom: "1px solid rgba(255,255,255,0.10)" },
  headerCompact: { padding: "16px 30px" },
  brandLink: { display: "inline-flex", alignItems: "center", gap: 8 },

  main: {
    display: "flex",
    justifyContent: "flex-start",
    alignItems: "flex-start",
    maxWidth: 1100,
    margin: "0 auto",
    padding: "120px 40px 80px",
  },
  mainCompact: {
    padding: "72px 30px 56px",
  },
  card: {
    width: "100%",
    maxWidth: 420,
    display: "flex",
    flexDirection: "column",
    padding: "28px 30px 30px",
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.075), rgba(255,255,255,0) 38%), rgba(7,8,12,0.72)",
    border: "1px solid rgba(245,200,120,0.16)",
    borderLeft: "3px solid rgba(208,138,79,0.62)",
    borderRadius: 2,
    boxShadow: "0 34px 100px rgba(0,0,0,0.46)",
    backdropFilter: "blur(14px)",
  },
  cardCompact: {
    maxWidth: "100%",
    padding: "24px 20px 26px",
  },
  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 28,
    lineHeight: 1.2,
    fontWeight: 400,
    margin: "0 0 10px",
    letterSpacing: 0,
    color: "white",
  },
  titleCompact: {
    fontSize: 25,
    lineHeight: 1.18,
  },
  kicker: {
    display: "inline-block",
    marginBottom: 24,
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  sub: {
    fontSize: 14,
    color: "rgba(255,255,255,0.68)",
    margin: "0 0 22px",
    lineHeight: 1.55,
  },
  subCompact: {
    fontSize: 13.5,
    maxWidth: 320,
  },
  quickStartButton: {
    width: "100%",
    marginBottom: 12,
    padding: "12px 12px 13px",
    background: "rgba(255,255,255,0.045)",
    border: "1px solid rgba(245,200,120,0.15)",
    borderLeft: "3px solid rgba(148,164,109,0.56)",
    borderRadius: 2,
    color: "rgba(255,230,184,0.96)",
    cursor: "pointer",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "baseline",
    columnGap: 8,
    fontFamily: "inherit",
    textAlign: "left" as const,
  },
  quickStartButtonCompact: {
    gridTemplateColumns: "minmax(0, 1fr) 18px",
    columnGap: 7,
  },
  quickStartIndex: {
    color: "rgba(245,200,120,0.64)",
    fontFamily: "var(--font-ui)",
    fontSize: 11,
    lineHeight: 1.25,
    fontWeight: 780,
  },
  quickStartLabel: {
    minWidth: 0,
    fontSize: 13.5,
    fontWeight: 800,
    lineHeight: 1.35,
  },
  quickStartCopy: {
    minWidth: 0,
    display: "grid",
    rowGap: 3,
  },
  quickStartMeta: {
    minWidth: 0,
    color: "rgba(255,255,255,0.48)",
    fontSize: 11.5,
    lineHeight: 1.32,
    fontWeight: 620,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  quickStartArrow: {
    flexShrink: 0,
    color: "rgba(245,200,120,0.84)",
    fontSize: 14,
    lineHeight: 1,
  },
  customNameToggle: {
    width: "fit-content",
    marginBottom: 14,
    padding: "2px 0 4px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.16)",
    borderRadius: 0,
    color: "rgba(255,255,255,0.56)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 12,
    fontWeight: 680,
    lineHeight: 1.35,
    letterSpacing: 0,
    textAlign: "left",
  },
  orLine: {
    display: "grid",
    gridTemplateColumns: "22px minmax(0, 1fr)",
    alignItems: "baseline",
    columnGap: 8,
    marginBottom: 12,
  },
  orIndex: {
    color: "rgba(245,200,120,0.44)",
    fontFamily: "var(--font-ui)",
    fontSize: 11,
    lineHeight: 1.25,
    fontWeight: 780,
  },
  orLabel: {
    color: "rgba(255,255,255,0.54)",
    fontSize: 12,
    lineHeight: 1.35,
    fontWeight: 680,
    letterSpacing: 0,
    textTransform: "none" as const,
  },

  inputWrap: {
    position: "relative",
    display: "flex",
    alignItems: "center",
    background: "rgba(0,0,0,0.22)",
    border: "1px solid rgba(255,255,255,0.16)",
    borderRadius: 2,
    transition: "border-color 200ms",
  },
  at: {
    paddingLeft: 16,
    paddingRight: 4,
    color: "var(--text-faint)",
    fontSize: 16,
    fontFamily: "var(--font-narrative)",
  },
  input: {
    flex: 1,
    height: 52,
    padding: "0 16px 0 4px",
    background: "transparent",
    border: "none",
    outline: "none",
    color: "white",
    fontSize: 16,
  },
  error: {
    fontSize: 12,
    color: "var(--warn)",
    overflow: "hidden",
  },
  submitAction: {
    width: "fit-content",
    padding: "10px 14px 11px",
    background: "rgba(208,138,79,0.18)",
    border: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 2,
    color: "rgba(255,226,172,0.96)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 850,
    letterSpacing: 0,
    textAlign: "left",
  },

  note: {
    marginTop: 18,
    fontSize: 12,
    color: "rgba(255,255,255,0.48)",
    lineHeight: 1.6,
    textAlign: "left",
  },
  noteCompact: {
    maxWidth: 320,
  },
}

/**
 * Map raw API errors to user-readable Chinese / English messages.
 *
 * Inputs: any error thrown by `createHttpApiClient`'s `requestJson` —
 * either an `ApiRequestError` (with statusCode + errorCode) or a network-
 * layer Error (e.g. "Failed to fetch" when offline).
 *
 * The goal is *not* perfect classification — it's "the user sees something
 * grounded and recoverable instead of a stack-trace fragment."
 *
 * Locale is read from localStorage directly (the `LanguageProvider` writes
 * to the same key) so this stays a pure function and call sites don't
 * need to thread `lang` through every error handler.
 */

type ApiErrorLike = {
  message?: string
  statusCode?: number
  errorCode?: string
  name?: string
}

type Lang = "zh" | "en"

const LANG_STORAGE_KEY = "tiny-stories-lang"

// OSS default is English. Mirrors `DEFAULT_LANG` in i18n.ts — kept
// in sync by hand because friendly-error must stay a pure function
// without React imports.
function readLang(): Lang {
  if (typeof window === "undefined") return "en"
  try {
    const raw = window.localStorage.getItem(LANG_STORAGE_KEY)
    if (raw === "zh") return "zh"
    if (raw === "en") return "en"
    return "en"
  } catch {
    return "en"
  }
}

const STATUS_FALLBACKS_ZH: Record<number, string> = {
  400: "这次没有通过，可能是输入太敏感或不合规。",
  401: "登录已过期，请刷新页面重新登录。",
  403: "你看不了这一项——可能是别人的私有内容。",
  404: "这条记录不存在了，可能已经被删除。",
  409: "局面和页面不同步了——可能在另一处已经做了变化，刷新一下试试。",
  422: "输入有问题，看看是不是哪一项填错了。",
  429: "请求太密了，喘口气再来一次。",
  500: "这次没有接上，再试一次或者一会再来。",
  502: "故事线路暂时没接上，再试一次。",
  503: "故事线路暂时很忙，过几分钟再来。",
  504: "房间响应太久了，再试一次。",
}

const STATUS_FALLBACKS_EN: Record<number, string> = {
  400: "This did not go through. Your input may be too sensitive or invalid.",
  401: "Session expired. Please refresh and sign in again.",
  403: "You can't access this — it may be private to someone else.",
  404: "This record no longer exists. It may have been deleted.",
  409: "The run and page are out of sync. Something changed elsewhere; try refreshing.",
  422: "Something in your input isn't right. Check the fields.",
  429: "Too many requests in a short time. Take a breath and try again.",
  500: "This did not land. Try again, or come back in a moment.",
  502: "The story line did not connect. Try again.",
  503: "The story line is briefly busy. Back in a few minutes.",
  504: "The room took too long to answer. Try again.",
}

const ERROR_CODE_FALLBACKS_ZH: Record<string, string> = {
  llm_invalid_json: "故事返回得不完整。可以重试，或先用计划简化人物和约束再生成。",
  llm_provider_failed: "故事线路暂时不在线，稍等再试。",
  llm_invalid_response: "故事这次回了空白，再试一次。",
  turn_invalid: "故事一时接不上你那一步——换个动作或稍等再试。",
  session_complete: "这一局已经走完了——回首页看你的结局。",
  session_forbidden: "这是别人的局，没法直接打开。",
  template_forbidden: "这个故事是私有的。",
  seed_required: "先写一句开头吧。",
  question_required: "想问点什么再发吧。",
  action_required: "选个选项或者写一段动作。",
  option_out_of_range: "选项序号不对，刷一下页面试试。",
  no_opening: "故事还没开始呢——重新进入。",
  no_narrator: "上一段叙述丢了，刷新一下试试。",
  turn_already_advanced: "这一段已经走过了，刷新一下接着玩。",
  llm_unavailable: "这个版本暂时不能续写故事，稍后再试。",
  opening_invalid: "开场草稿没搭起来。可以重试，或生成一个更简单、约束更少的开场。",
  opening_prompt_shape_mismatch: "这个开头还不太适合当前故事形状。试试 3 个以上人物、一个公开冲突、一个秘密/争夺物，再加一点时间压力。",
  opening_brief_consistency_failed: "第一版开场没有足够贴住计划。计划还保留着；请重新搭建一个更紧的开场，或先改一条设定。",
  advisor_invalid: "顾问没说出有效的话，再问一次。",
}

const ERROR_CODE_FALLBACKS_EN: Record<string, string> = {
  llm_invalid_json: "The story came back incomplete. Try again, or simplify the plan before generating.",
  llm_provider_failed: "The story line is briefly offline. Try again shortly.",
  llm_invalid_response: "The story came back blank. Try again.",
  turn_invalid: "The story can't pick up from that move — try a different action, or wait and retry.",
  session_complete: "This run is already finished — go back home to see your ending.",
  session_forbidden: "That's someone else's run; you can't open it directly.",
  template_forbidden: "This story is private.",
  seed_required: "Start with an opening line first.",
  question_required: "Type something to ask first.",
  action_required: "Pick an option or write an action.",
  option_out_of_range: "Option index is off — try refreshing the page.",
  no_opening: "The story hasn't started yet — go back in.",
  no_narrator: "Lost the previous narration. Try a refresh.",
  turn_already_advanced: "This turn already moved forward. Refresh to continue.",
  llm_unavailable: "This build cannot continue the story right now. Try again later.",
  opening_invalid: "The opening draft did not come together. Try again, or generate a simpler opening with fewer constraints.",
  opening_prompt_shape_mismatch: "This premise does not fit the current story shape yet. Try 3+ people, one public conflict, one secret or contested object, and time pressure.",
  opening_brief_consistency_failed: "The first draft did not honor the plan strongly enough. The plan is still saved; build a tighter opening or revise the plan.",
  advisor_invalid: "The advisor didn't say anything usable. Ask again.",
}

const NETWORK_FALLBACK_ZH = "网络好像断了——检查一下连接再试。"
const NETWORK_FALLBACK_EN = "Network seems down — check your connection and retry."

const LIVE_ERROR_COPY_ZH: Record<LiveErrorKind, string> = {
  timeout: "房间响应太久了。本回合没有消耗，你的草稿或动作还保留着。",
  rate_limited: "线路现在很忙。你的草稿或动作还保留着，稍后再试。",
  invalid_response: "场景返回得不完整。你的草稿或动作还在，可以重试。",
  safety_redirect: "这个方向暂时不能进入故事。换一个更适合短剧场的冲突或压力点。",
  provider_unavailable: "现场叙事线暂时没接上。你的草稿或动作还在，可以稍后重试。",
  network: NETWORK_FALLBACK_ZH,
}

const LIVE_ERROR_COPY_EN: Record<LiveErrorKind, string> = {
  timeout: "The room took too long to answer. No turn was spent; your draft or move is still held.",
  rate_limited: "The line is busy. Your draft or move is still held; try again in a moment.",
  invalid_response: "The scene came back incomplete. Your draft or move is still ready.",
  safety_redirect: "That direction cannot enter the story yet. Shift it toward a safer short-scene pressure point.",
  provider_unavailable: "The live story line did not answer. Your draft or move is still here; retry in a moment.",
  network: NETWORK_FALLBACK_EN,
}

const GENERIC_FALLBACK_ZH = "出了点问题，再试一次。"
const GENERIC_FALLBACK_EN = "Something went wrong. Try again."

const GENERIC_PREFIX_ZH = "出了点问题："
const GENERIC_PREFIX_EN = "Something went wrong: "

const NETWORK_PATTERNS = [
  "Failed to fetch",
  "NetworkError",
  "Network request failed",
  "ERR_INTERNET",
  "ERR_NETWORK",
  "ERR_NAME_NOT_RESOLVED",
  "Load failed",
]

const TECHNICAL_MESSAGE_PATTERNS = [
  /\bapi\b/i,
  /\bbackend\b/i,
  /\bendpoint\b/i,
  /\bhttp\b/i,
  /\bjson\b/i,
  /\bllm\b/i,
  /\bmodel\b/i,
  /\bprovider\b/i,
  /\bschema\b/i,
  /\bstack\b/i,
  /\bstatus\s*code\b/i,
  /\btoken\b/i,
  /\btraceback\b/i,
  /\b(get|post|put|patch|delete)\s+\//i,
  /\/narrative\//i,
]

type LiveErrorKind =
  | "timeout"
  | "rate_limited"
  | "invalid_response"
  | "safety_redirect"
  | "provider_unavailable"
  | "network"

const INVALID_RESPONSE_CODES = new Set([
  "llm_invalid_json",
  "llm_invalid_response",
  "play_llm_invalid_json",
  "play_llm_invalid_response",
  "opening_invalid",
])

const PROVIDER_UNAVAILABLE_CODES = new Set([
  "llm_provider_failed",
  "play_llm_provider_failed",
  "llm_unavailable",
  "play_llm_config_missing",
])

function classifyLiveError(err: ApiErrorLike): LiveErrorKind | null {
  const message = err.message ?? ""
  const lowerMessage = message.toLowerCase()
  const status = err.statusCode
  const code = err.errorCode ?? ""

  if (
    err.name === "TypeError" ||
    NETWORK_PATTERNS.some((pattern) => message.includes(pattern))
  ) {
    return "network"
  }
  if (status === 504 || lowerMessage.includes("timeout") || lowerMessage.includes("timed out")) {
    return "timeout"
  }
  if (
    status === 429 ||
    lowerMessage.includes("rate limit") ||
    lowerMessage.includes("too many requests") ||
    lowerMessage.includes("pending requests")
  ) {
    return "rate_limited"
  }
  if (INVALID_RESPONSE_CODES.has(code)) {
    return "invalid_response"
  }
  if (status === 400 && (lowerMessage.includes("safety") || lowerMessage.includes("sensitive"))) {
    return "safety_redirect"
  }
  if (PROVIDER_UNAVAILABLE_CODES.has(code) || status === 502 || status === 503) {
    return "provider_unavailable"
  }
  return null
}

function isLikelyUserFacingMessage(message: string, lang: Lang): boolean {
  const trimmed = message.trim()
  if (!trimmed) return false
  if (TECHNICAL_MESSAGE_PATTERNS.some((pattern) => pattern.test(trimmed))) return false
  const hasChinese = /[一-龥]/.test(trimmed)
  return lang === "zh" ? hasChinese : !hasChinese
}

export function friendlyError(err: unknown, fallback?: string): string {
  const lang = readLang()
  const statusMap = lang === "en" ? STATUS_FALLBACKS_EN : STATUS_FALLBACKS_ZH
  const codeMap = lang === "en" ? ERROR_CODE_FALLBACKS_EN : ERROR_CODE_FALLBACKS_ZH
  const networkMsg = lang === "en" ? NETWORK_FALLBACK_EN : NETWORK_FALLBACK_ZH
  const genericMsg = lang === "en" ? GENERIC_FALLBACK_EN : GENERIC_FALLBACK_ZH
  const genericPrefix = lang === "en" ? GENERIC_PREFIX_EN : GENERIC_PREFIX_ZH

  if (!err) return fallback ?? genericMsg

  // Network errors — these come up as DOMException / TypeError before our
  // ApiRequestError wrapping can run.
  if (typeof err === "object" && err !== null) {
    const e = err as ApiErrorLike
    const message = e.message ?? ""

    // Live story/gateway errors first: keep provider/schema details out of
    // player-facing UI while preserving retry semantics.
    const liveKind = classifyLiveError(e)
    if (liveKind) {
      const liveMap = lang === "en" ? LIVE_ERROR_COPY_EN : LIVE_ERROR_COPY_ZH
      return liveMap[liveKind]
    }

    // Specific API error code first (most precise)
    if (e.errorCode && codeMap[e.errorCode]) {
      return codeMap[e.errorCode]
    }

    // HTTP status fallback
    if (typeof e.statusCode === "number" && statusMap[e.statusCode]) {
      return statusMap[e.statusCode]
    }

    // If the API gave us a sentence in the user's locale already, trust it
    // only when it does not look like a raw runtime or transport error.
    if (isLikelyUserFacingMessage(message, lang) && lang === "zh") {
      return message
    }
    if (isLikelyUserFacingMessage(message, lang) && lang === "en") {
      return message
    }
  }

  if (err instanceof Error && err.message) {
    if (!isLikelyUserFacingMessage(err.message, lang)) return fallback ?? genericMsg
    return fallback ?? `${genericPrefix}${err.message}`
  }

  return fallback ?? genericMsg
}

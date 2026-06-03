// Maps stable story / character / theme keys to visual assets. Demo-facing
// surfaces route through curated/generated, text-free illustration panels;
// older /webtoons/ pools remain only for deferred avatar/advisor identity work
// and catalog/debug references.

const GENERATED_BASE = "/illustrations/generated"

export const GENERATED_ASSETS = {
  coverNeutral: `${GENERATED_BASE}/cover-neutral-storyboard-desk.webp`,
  coverCozy: `${GENERATED_BASE}/cover-cozy-bake-sale.webp`,
  coverFantasy: `${GENERATED_BASE}/cover-fantasy-library-eclipse.webp`,
  coverSciFiMars: `${GENERATED_BASE}/cover-sci-fi-mars-colony-talent-show.webp`,
  coverHighDrama: `${GENERATED_BASE}/cover-high-drama-boardroom.webp`,
  reviewerEvidence: `${GENERATED_BASE}/reviewer-evidence-board-clean.webp`,
  advisorNotebook: `${GENERATED_BASE}/advisor-notebook-desk.webp`,
  emptyPlaza: `${GENERATED_BASE}/empty-plaza-story-cards.webp`,
  endingReflection: `${GENERATED_BASE}/ending-reflection-notebook.webp`,
  objectCardSheet: `${GENERATED_BASE}/object-card-sheet.webp`,
} as const

const SHELLS = [
  "campus_romance",
  "urban_supernatural",
  "wealth_families",
  "entertainment_scandal",
  "office_power",
  // Newer themes covering the most common drama settings that
  // previously fell back to wealth_families. Each ships with five
  // deterministic cover variants.
  "wedding",
  "courtroom",
  "palace_drama",
] as const
type Shell = (typeof SHELLS)[number]
type StoryCoverProfile = "cozy_comedy" | "fantasy_sci_fi" | "high_drama_social" | "neutral"

// Each shell has five variants now; pick is deterministic by template_id hash
// so the same template always shows the same cover, but two templates of the
// same shell get different visuals.
const SHELL_VARIANTS_PER_SHELL = 5

const AVATAR_FEMALE = [
  "female-01",
  "female-02",
  "female-03",
  "female-04",
  "female-05",
  "female-06",
  "female-07",
  "female-08",
  "female-09",
  "female-10",
  // Variant portraits — different ages / costumes. Hash-distributed
  // into the same pool so the cast strip gets visual variety; mild
  // age mismatch risk (e.g. an "elder" portrait assigned to a young
  // role) is tolerated for the variety win.
  "elder-01",
  "student-01",
  "period-01",
  "bride-01",
  "idol-01",
  "lawyer-01",
] as const
const AVATAR_MALE = [
  "male-01",
  "male-02",
  "male-03",
  "male-04",
  "male-05",
  "male-06",
  "male-07",
  "male-08",
  "male-09",
  "male-10",
  "elder-02",
  "student-02",
  "idol-01",
  "lawyer-01",
  "royal-01",
] as const

// Dedicated advisor portrait pool — visually distinct from the cast pool so
// the player's outsider-friend never collides with an NPC face.
const ADVISOR_AVATARS = [
  "advisor-01",
  "advisor-02",
  "advisor-03",
  "advisor-04",
  "advisor-05",
  "advisor-06",
  "advisor-07",
  "advisor-08",
  "advisor-09",
  "advisor-10",
  "advisor-11",
  "advisor-12",
  "advisor-13",
  "advisor-14",
] as const

const SEGMENT_PHASES = ["opening", "pressure", "reversal", "reveal", "terminal"] as const
type SegmentPhase = (typeof SEGMENT_PHASES)[number]

const SEGMENT_PHASE_POOLS: Record<SegmentPhase, readonly string[]> = {
  opening: [
    "opening",
    "opening_rooftop_gala",
    "opening_campus_rain_gate",
    "opening_backstage_vanity",
    "opening_courtroom_waiting",
  ],
  pressure: [
    "pressure",
    "pressure_boardroom_vote",
    "pressure_family_banquet",
    "pressure_press_hallway",
    "pressure_palace_corridor",
  ],
  reversal: [
    "reversal",
    "reversal_elevator_standoff",
    "reversal_wedding_aisle",
  ],
  reveal: [
    "reveal",
    "reveal_hidden_usb",
    "reveal_torn_contract",
    "reveal_phone_reflection",
    "reveal_cctv_room",
  ],
  terminal: [
    "terminal",
    "terminal_rain_crosswalk",
    "terminal_empty_boardroom",
  ],
}

const ENDING_VARIANTS = [
  "burned_alone",
  "burst_reckoning",
  "side",
  "pyrrhic_control",
  "relationship",
] as const

// Backend themes (string-y from the LLM) routed to a closest-fit shell.
// Anything not listed falls back to a stable hash over SHELLS.
const THEME_TO_SHELL: Record<string, Shell> = {
  campus_romance: "campus_romance",
  urban_supernatural: "urban_supernatural",
  wealth_families: "wealth_families",
  entertainment_scandal: "entertainment_scandal",
  office_power: "office_power",
  romance_drama: "campus_romance",
  power_struggle: "office_power",
  family_secret: "wealth_families",
  workplace_intrigue: "office_power",
  betrayal: "entertainment_scandal",
  redemption: "campus_romance",
  mystery: "urban_supernatural",
}

const STORY_COVER_BY_PROFILE: Record<StoryCoverProfile, string> = {
  cozy_comedy: "/illustrations/story-cover-cozy-comedy.svg",
  fantasy_sci_fi: "/illustrations/story-cover-fantasy-sci-fi.svg",
  high_drama_social: "/illustrations/story-cover-high-drama-social.svg",
  neutral: "/illustrations/story-cover-neutral.svg",
}

const TENSION_PROFILE_TO_COVER: Record<string, StoryCoverProfile> = {
  comedy: "cozy_comedy",
  cozy_mystery: "cozy_comedy",
  fantasy_sci_fi: "fantasy_sci_fi",
  high_drama: "high_drama_social",
  family_social: "high_drama_social",
}

const COVER_PROFILE_KEYWORDS: Record<StoryCoverProfile, readonly string[]> = {
  fantasy_sci_fi: [
    "mars", "colony", "oxygen", "space", "planet", "alien", "sci-fi", "sci fi",
    "science fiction", "dragon", "spell", "magic", "magical", "library", "eclipse",
    "wizard", "apprentice", "artifact", "technical", "faction", "clan",
    "火星", "殖民", "氧气", "太空", "星球", "龙", "魔法", "图书馆", "日食",
  ],
  cozy_comedy: [
    "cozy", "comedy", "comic", "funny", "bake sale", "cupcake", "talent show",
    "theatre", "theater", "misunderstanding", "callback", "embarrass", "playful",
    "low stakes", "gentle", "neighborhood", "volunteer", "fun",
    "喜剧", "搞笑", "温馨", "轻松", "误会", "才艺", "烘焙", "纸杯蛋糕",
  ],
  high_drama_social: [
    "board", "vote", "cfo", "founder", "union", "investor", "chair", "company",
    "office", "inheritance", "estate", "will", "scandal", "press", "trial",
    "courtroom", "deadline", "public pressure", "family dinner", "conflict",
    "董事", "投票", "创始", "工会", "投资", "公司", "遗产", "丑闻", "法庭",
  ],
  neutral: [],
}

const STRONG_SCI_FI_SETTING_KEYWORDS = [
  "mars", "colony", "oxygen", "space", "sci-fi", "sci fi", "science fiction",
  "planet", "alien", "orbital", "station", "space station", "airlock",
  "hydroponic", "hydroponics", "faction",
  "火星", "殖民", "氧气", "太空", "星球", "轨道", "空间站", "气闸", "水培",
  "阵营", "派系",
] as const

function hasStrongSciFiSetting(corpus: string): boolean {
  return STRONG_SCI_FI_SETTING_KEYWORDS.some((keyword) => corpus.includes(keyword))
}

function storyCoverFromProfile(profile: StoryCoverProfile): string {
  return STORY_COVER_BY_PROFILE[profile]
}

function generatedCoverFromProfile(profile: StoryCoverProfile, corpus = ""): string {
  const lower = corpus.toLowerCase()
  if (hasStrongSciFiSetting(lower)) {
    return GENERATED_ASSETS.coverSciFiMars
  }
  if (profile === "cozy_comedy") return GENERATED_ASSETS.coverCozy
  if (profile === "fantasy_sci_fi") return GENERATED_ASSETS.coverFantasy
  if (profile === "high_drama_social") return GENERATED_ASSETS.coverHighDrama
  return GENERATED_ASSETS.coverNeutral
}

export function resolveGeneratedCoverForText(corpus: string, explicitProfile?: string | null): string {
  const profile = inferCoverProfileFromText(corpus, explicitProfile)
  return generatedCoverFromProfile(profile, corpus)
}

function countKeywordHits(corpus: string, keywords: readonly string[]): number {
  return keywords.reduce((total, keyword) => total + (corpus.includes(keyword) ? 1 : 0), 0)
}

function inferCoverProfileFromText(corpus: string, explicitProfile?: string | null): StoryCoverProfile {
  const lower = corpus.toLowerCase()
  if (hasStrongSciFiSetting(lower)) return "fantasy_sci_fi"

  const explicit = explicitProfile ? TENSION_PROFILE_TO_COVER[explicitProfile] : undefined
  if (explicit) return explicit

  const hits = {
    fantasy_sci_fi: countKeywordHits(lower, COVER_PROFILE_KEYWORDS.fantasy_sci_fi),
    cozy_comedy: countKeywordHits(lower, COVER_PROFILE_KEYWORDS.cozy_comedy),
    high_drama_social: countKeywordHits(lower, COVER_PROFILE_KEYWORDS.high_drama_social),
  }
  if (hits.fantasy_sci_fi > 0 && hits.fantasy_sci_fi >= hits.cozy_comedy) return "fantasy_sci_fi"
  if (hits.cozy_comedy > 0) return "cozy_comedy"
  if (hits.high_drama_social > 0) return "high_drama_social"
  return "neutral"
}

function stableHash(input: string): number {
  let h = 5381
  for (let i = 0; i < input.length; i += 1) {
    h = ((h << 5) + h + input.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

function pick<T>(pool: readonly T[], key: string): T {
  return pool[stableHash(key) % pool.length] as T
}

function shellVariantSlugs(shell: Shell): string[] {
  return Array.from({ length: SHELL_VARIANTS_PER_SHELL }, (_, idx) => (
    idx === 0 ? shell : `${shell}-0${idx + 1}`
  ))
}

function segmentSlugs(): string[] {
  return SEGMENT_PHASES.flatMap((phase) => [...SEGMENT_PHASE_POOLS[phase]])
}

// ───────── covers ─────────

function shellVariantSlug(shell: Shell, key: string): string {
  // Stable per-key variant pick: -01 (legacy filename) or -02...-05.
  // Adding more variants later requires only bumping SHELL_VARIANTS_PER_SHELL
  // and dropping the new file at /shells/{shell}-NN.jpg.
  if (SHELL_VARIANTS_PER_SHELL <= 1) return shell
  const idx = stableHash(`shell-variant|${key}|${shell}`) % SHELL_VARIANTS_PER_SHELL
  // -01 maps to the legacy filename without suffix to avoid breaking
  // existing assets; -02 onward gets the suffix.
  return idx === 0 ? shell : `${shell}-0${idx + 1}`
}

/** Cover image for a world card / story drawer / world detail hero. */
export function getCoverByStoryId(storyId: string, theme?: string | null): string {
  const corpus = `${theme ?? ""} ${storyId}`
  return resolveGeneratedCoverForText(corpus, theme)
}

// ───────── portraits ─────────

/** Stable per-character avatar. Hash is derived from (storyId + characterId)
 *  so the same character keeps the same face across renders. */
export function getPortraitForCharacter(
  storyId: string,
  characterId: string,
  gender?: "female" | "male" | null,
): string {
  const key = `${storyId}|${characterId}`
  const pool = gender === "male" ? AVATAR_MALE : AVATAR_FEMALE
  return `/webtoons/avatars/${pick(pool, key)}.jpg`
}

export function getDefaultAvatar(gender?: "female" | "male"): string {
  return gender === "male"
    ? "/webtoons/ui/default-avatar-male.jpg"
    : "/webtoons/ui/default-avatar-female.jpg"
}

// ───────── scenes / segments ─────────

/** Background art for the play stage, picked by the current beat phase. */
export function getSceneByPhase(phase: string | null | undefined, key = "default"): string {
  void key
  if (phase === "pressure") return GENERATED_ASSETS.coverHighDrama
  if (phase === "reversal") return GENERATED_ASSETS.objectCardSheet
  if (phase === "reveal") return GENERATED_ASSETS.reviewerEvidence
  if (phase === "terminal") return GENERATED_ASSETS.endingReflection
  return GENERATED_ASSETS.coverNeutral
}

// ───────── endings ─────────

/** Ending artwork. Hash by ending_id so each ending always uses the same canvas. */
export function getEndingArtwork(endingId: string | null | undefined): string {
  void endingId
  return GENERATED_ASSETS.endingReflection
}

// ───────── page-level backgrounds ─────────

export const PAGE_BG = {
  splash: GENERATED_ASSETS.coverNeutral,
  home: GENERATED_ASSETS.coverNeutral,
  create: GENERATED_ASSETS.advisorNotebook,
  generating: GENERATED_ASSETS.objectCardSheet,
  login: GENERATED_ASSETS.reviewerEvidence,
} as const

export const LOGO_URL = GENERATED_ASSETS.objectCardSheet

// ───────── peak narration close-ups ─────────
// 13 cinematic close-up images used as full-bleed banners on "peak"
// narrator beats (broken pulse / inventory delta fired / late-game
// cold shifts). Each peak beat picks one deterministically by hashing
// the message ord, so the same beat always shows the same image but
// adjacent peaks get different visuals — no repeat fatigue.

const PEAK_CLOSEUPS = [
  "peak_face",
  "peak_hand",
  "peak_screen",
  "peak_torn",
  "peak_silence",
  "peak_cold_eye",
  "peak_ring_crack",
  "peak_elevator_button",
  "peak_message_seen",
  "peak_contract_stamp",
  "peak_lip_bite",
  "peak_broken_photo",
  "peak_jade_pendant",
] as const

// ───────── catalog (handy for design review / debugging) ─────────

export const ASSET_CATALOG = {
  generated: Object.values(GENERATED_ASSETS),
  storyCovers: Object.values(STORY_COVER_BY_PROFILE),
  legacyWebtoonsRetained: {
    shells: SHELLS.flatMap((s) => shellVariantSlugs(s).map((slug) => `/webtoons/shells/${slug}.jpg`)),
    avatars: {
      female: AVATAR_FEMALE.map((s) => `/webtoons/avatars/${s}.jpg`),
      male: AVATAR_MALE.map((s) => `/webtoons/avatars/${s}.jpg`),
    },
    advisors: ADVISOR_AVATARS.map((s) => `/webtoons/advisors/${s}.jpg`),
    segments: segmentSlugs().map((s) => `/webtoons/segments/${s}.jpg`),
    endings: ENDING_VARIANTS.map((s) => `/webtoons/endings/${s}.jpg`),
    peaks: PEAK_CLOSEUPS.map((s) => `/webtoons/peaks/${s}.jpg`),
  },
} as const

// ───────── narrative (template/session) helpers ─────────
// The narrative engine doesn't expose shell_id directly, so we infer
// from seed + role text using lightweight keyword matching. Same for
// gender (used to pick a female vs. male portrait pool).

type LooseCast = { character_id: string; display_name: string; role: string; relation_to_protagonist: string }
type LooseTemplate = {
  template_id: string
  seed: string
  title?: string
  cast: LooseCast[]
  story_brief?: {
    tension_profile?: string | null
    genre_tone?: string | null
    story_kernel?: string | null
  } | null
}

const SHELL_KEYWORDS: Record<Shell, readonly string[]> = {
  wealth_families: [
    "豪门", "霸总", "总裁", "继承", "豪宅", "联姻", "家族", "夫人", "千金", "少爷",
    "宴会", "婆媳", "继母", "私生子", "年夜饭", "嫁入", "遗嘱", "红毯",
    "wealth", "heir", "inheritance", "estate", "family", "banquet", "will", "gala",
  ],
  office_power: [
    "总监", "副总", "经理", "项目", "职场", "公司", "高管", "实习", "客户",
    "汇报", "会议", "权力博弈", "竞标", "年会", "述职",
    "office", "company", "board", "merger", "contract", "launch", "legal", "vote",
    "cofounder", "startup", "promotion", "investor",
  ],
  entertainment_scandal: [
    "颁奖", "明星", "搭档", "经纪人", "娱乐圈", "出道", "粉丝", "片场",
    "通告", "代言", "热搜", "狗仔", "发布会", "导演",
    "awards", "livestream", "celebrity", "backstage", "red carpet", "sponsor",
    "scandal", "press", "recording",
  ],
  campus_romance: [
    "高中", "大学", "校园", "同学", "学姐", "学长", "学妹", "教室",
    "宿舍", "毕业", "重逢", "初恋", "妹妹", "哥哥", "校服",
    "campus", "college", "classmate", "reunion", "scholarship", "mentor",
    "first love", "sister", "brother",
  ],
  urban_supernatural: [
    "都市", "怪谈", "灵异", "鬼", "诡异", "失踪", "深夜", "电话", "梦",
    "凶杀", "目击", "怨灵", "诅咒",
    "supernatural", "haunting", "ghost", "curse", "midnight", "missing",
    "witness", "nightmare",
  ],
  wedding: [
    "婚礼", "婚宴", "婚纱", "新娘", "新郎", "伴娘", "伴郎", "证婚人",
    "婚戒", "蜜月", "婚约", "婚书", "嫁妆", "请帖", "敬酒", "教堂",
    "wedding", "bride", "groom",
  ],
  courtroom: [
    "法庭", "庭审", "律师", "法官", "检察官", "证人", "被告", "原告",
    "辩护", "判决", "陪审", "诉讼", "证据", "公诉", "出庭",
    "courtroom", "lawyer", "trial", "verdict",
  ],
  palace_drama: [
    "宫廷", "皇宫", "皇上", "皇后", "嫔妃", "贵妃", "宠妃", "公主",
    "太子", "丞相", "妃嫔", "选秀", "宫斗", "御花园", "凤冠",
    "汉服", "古代", "王朝", "诸侯", "藩王", "宫女",
    "palace", "empress", "concubine", "dynasty",
  ],
}

function inferShell(template: LooseTemplate): Shell {
  const corpus = [
    template.seed,
    template.title ?? "",
    template.cast.map((c) => `${c.role} ${c.relation_to_protagonist}`).join(" "),
  ].join(" ")
  let bestShell: Shell = "wealth_families"
  let bestHits = 0
  for (const shell of SHELLS) {
    const hits = SHELL_KEYWORDS[shell].reduce(
      (n, kw) => n + (corpus.includes(kw) ? 1 : 0),
      0,
    )
    if (hits > bestHits) {
      bestHits = hits
      bestShell = shell
    }
  }
  // No keyword hits → stable hash over the template_id keeps cards visually
  // distinct without misleading the user about subgenre.
  if (bestHits === 0) {
    return pick(SHELLS, template.template_id)
  }
  return bestShell
}

const FEMALE_ROLE_HINTS = [
  "妻", "妻子", "夫人", "母", "妈", "女儿", "妹", "姐", "姑娘", "小姐", "千金",
  "公主", "皇后", "继母", "学姐", "学妹", "女主", "少奶奶", "新娘", "未婚妻",
  "经纪人", "助理", "闺蜜", "情人",
  "wife", "mother", "daughter", "sister", "bride", "fiancee", "girlfriend",
  "queen", "princess", "assistant", "manager",
]
const MALE_ROLE_HINTS = [
  "夫", "丈夫", "父", "爸", "儿子", "弟", "哥", "少爷", "总裁", "霸总",
  "皇帝", "王", "继父", "学长", "男主", "新郎", "未婚夫",
  "husband", "father", "son", "brother", "groom", "fiance", "boyfriend",
  "king", "prince", "ceo", "founder", "cofounder",
]

function inferGender(role: string, relation: string): "female" | "male" {
  const corpus = `${role} ${relation}`
  const female = FEMALE_ROLE_HINTS.some((kw) => corpus.includes(kw))
  const male = MALE_ROLE_HINTS.some((kw) => corpus.includes(kw))
  if (female && !male) return "female"
  if (male && !female) return "male"
  // Tie / no signal — split by character_id hash for a stable spread.
  return stableHash(`${role}|${relation}`) % 2 === 0 ? "female" : "male"
}

/** Cover for a template card / hero.
 * Curated SVG panels are intentionally text-free and broad enough for live
 * generated premises, avoiding old text-heavy JPG covers that could expose
 * unrelated language or mismatched story cues.
 */
export function getCoverForTemplate(template: LooseTemplate): string {
  const corpus = [
    template.seed,
    template.title ?? "",
    template.story_brief?.genre_tone ?? "",
    template.story_brief?.story_kernel ?? "",
    template.cast.map((c) => `${c.display_name} ${c.role} ${c.relation_to_protagonist}`).join(" "),
  ].join(" ")
  return resolveGeneratedCoverForText(corpus, template.story_brief?.tension_profile)
}

/** Stable per-character avatar within a template. */
export function getAvatarForCastMember(
  templateId: string,
  member: LooseCast,
): string {
  const gender = inferGender(member.role, member.relation_to_protagonist)
  const pool = gender === "male" ? AVATAR_MALE : AVATAR_FEMALE
  const key = `${templateId}|${member.character_id}`
  return `/webtoons/avatars/${pick(pool, key)}.jpg`
}

/** Avatar for the advisor FAB / sidechat header. Pulls from a dedicated
 *  /webtoons/advisors/ pool so the advisor never collides with a cast NPC.
 *  The pool already mixes genders, so persona text isn't needed for the
 *  selection — we just hash by template_id for stability. */
export function getAdvisorAvatar(templateId: string, _persona: string): string {
  return `/webtoons/advisors/${pick(ADVISOR_AVATARS, `advisor|${templateId}`)}.jpg`
}

// ───────── ending illustrations ─────────
// One safe reflection canvas replaces the old dark ending set for demo
// screenshots. Ending-specific illustration batches are deferred.
export function getEndingIllustration(label: string | null | undefined): string {
  void label
  return GENERATED_ASSETS.endingReflection
}

// ───────── tier splash banners ─────────
// Legacy tier-specific JPG overlays are disabled for the P0 demo-safe pass.
// The common generated ending canvas now carries the closing visual.

export function getTierSplash(
  tier: "victory" | "compromised" | "collapsed" | null | undefined,
): string | null {
  void tier
  return null
}

// ───────── empty state ─────────

export function getEmptyPlazaImage(): string {
  return GENERATED_ASSETS.emptyPlaza
}

export function getPeakCloseUp(messageOrd: number): string {
  const generatedPeakPool = [
    GENERATED_ASSETS.objectCardSheet,
    GENERATED_ASSETS.reviewerEvidence,
    GENERATED_ASSETS.coverHighDrama,
    GENERATED_ASSETS.endingReflection,
  ] as const
  return pick(generatedPeakPool, `generated-peak|${messageOrd}`)
}

// ───────── advisor oracle vignette ─────────
// Single atmospheric texture layered behind oracle reply bubbles to
// make the "I paid a turn for this" moment feel ritualistic.

export const ORACLE_VIGNETTE = GENERATED_ASSETS.advisorNotebook

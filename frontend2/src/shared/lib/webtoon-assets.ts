// Maps stable story / character / theme keys to webtoon-style illustrations
// in /webtoons/. Keep all path strings here so design output and runtime
// resolution stay in sync — Claude Design references the same URLs verbatim.

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

type AvatarGenderPresentation = "female" | "male"
type AvatarMetadata = {
  slug: string
  gender: AvatarGenderPresentation
  tags: readonly string[]
  avoidTags?: readonly string[]
}

// Local semantic manifest for cast portraits. This is deliberately tag-vector
// shaped rather than role->file hardcoding: future Art/R&D can replace or
// augment the score with embeddings while keeping the same query/filter seam.
const AVATAR_METADATA: readonly AvatarMetadata[] = [
  { slug: "bride-01", gender: "female", tags: ["wedding", "bride", "formal", "young", "family", "relationship"] },
  { slug: "elder-01", gender: "female", tags: ["elder", "family", "inheritance", "period", "traditional", "matriarch", "formal"] },
  { slug: "elder-02", gender: "male", tags: ["elder", "family", "inheritance", "executive", "sponsor", "formal", "mature"] },
  { slug: "female-01", gender: "female", tags: ["professional", "executive", "sponsor", "formal", "office", "elite"] },
  { slug: "female-02", gender: "female", tags: ["entertainment", "celebrity", "performer", "gala", "drama", "stage"] },
  { slug: "female-03", gender: "female", tags: ["professional", "assistant", "lawyer", "office", "formal", "glasses"] },
  { slug: "female-04", gender: "female", tags: ["student", "campus", "casual", "young", "friend"] },
  { slug: "female-05", gender: "female", tags: ["entertainment", "celebrity", "performer", "singer", "gala", "stage"] },
  { slug: "female-06", gender: "female", tags: ["student", "campus", "young", "quiet", "witness"] },
  { slug: "female-07", gender: "female", tags: ["professional", "publicist", "manager", "office", "formal", "glasses"] },
  { slug: "female-08", gender: "female", tags: ["entertainment", "performer", "dancer", "backstage", "edgy", "young"] },
  { slug: "female-09", gender: "female", tags: ["professional", "publicist", "manager", "backstage", "formal", "mature"] },
  { slug: "female-10", gender: "female", tags: ["entertainment", "dancer", "performer", "backstage", "witness", "young"] },
  { slug: "idol-01", gender: "male", tags: ["entertainment", "idol", "singer", "performer", "celebrity", "stage", "young"] },
  { slug: "lawyer-01", gender: "male", tags: ["professional", "lawyer", "executive", "office", "formal", "representative"] },
  { slug: "male-01", gender: "male", tags: ["professional", "executive", "office", "formal", "sharp"] },
  { slug: "male-02", gender: "male", tags: ["entertainment", "performer", "celebrity", "backstage", "edgy"] },
  { slug: "male-03", gender: "male", tags: ["professional", "executive", "lawyer", "office", "formal", "manager"] },
  { slug: "male-04", gender: "male", tags: ["professional", "producer", "manager", "backstage", "entertainment", "formal"] },
  { slug: "male-05", gender: "male", tags: ["entertainment", "celebrity", "performer", "gala", "edgy"] },
  { slug: "male-06", gender: "male", tags: ["student", "campus", "young", "casual"] },
  { slug: "male-07", gender: "male", tags: ["elder", "family", "executive", "sponsor", "mature", "formal"] },
  { slug: "male-08", gender: "male", tags: ["artifact", "letter", "object"], avoidTags: ["character", "portrait"] },
  { slug: "male-09", gender: "male", tags: ["royal", "period", "heir", "family", "formal"] },
  { slug: "male-10", gender: "male", tags: ["elder", "executive", "sponsor", "professional", "mature", "formal"] },
  { slug: "period-01", gender: "female", tags: ["period", "royal", "family", "traditional", "formal"] },
  { slug: "royal-01", gender: "male", tags: ["royal", "period", "heir", "formal", "family"] },
  { slug: "student-01", gender: "female", tags: ["student", "campus", "young", "witness"] },
  { slug: "student-02", gender: "male", tags: ["student", "campus", "young", "witness"] },
] as const

type AvatarQuery = {
  key: string
  gender: AvatarGenderPresentation | null
  weights: Record<string, number>
  avoidTags: readonly string[]
  roleRuleHits: number
}

type AvatarQueryRule = {
  keywords: readonly string[]
  tags: readonly string[]
  avoidTags?: readonly string[]
  gender?: AvatarGenderPresentation
  weight?: number
}

const AVATAR_ROLE_RULES: readonly AvatarQueryRule[] = [
  {
    keywords: ["backup dancer", "dancer", "choreographer", "伴舞", "舞者"],
    tags: ["dancer", "performer", "entertainment", "backstage", "young"],
    avoidTags: ["elder", "executive", "sponsor", "wedding", "bride", "royal", "period", "student"],
    weight: 6,
  },
  {
    keywords: ["singer", "idol", "performer", "celebrity", "actor", "actress", "歌手", "偶像", "演员", "明星"],
    tags: ["entertainment", "performer", "celebrity", "stage"],
    avoidTags: ["elder", "executive", "wedding", "bride", "student"],
    weight: 5,
  },
  {
    keywords: ["publicist", "press agent", "pr manager", "public relations", "manager", "agent", "经纪人", "公关"],
    tags: ["publicist", "professional", "manager", "entertainment", "backstage", "formal"],
    avoidTags: ["student", "wedding", "bride", "royal", "period"],
    weight: 6,
  },
  {
    keywords: ["producer", "director", "showrunner", "制作人", "导演"],
    tags: ["producer", "professional", "manager", "entertainment", "backstage", "formal"],
    avoidTags: ["student", "wedding", "bride", "royal", "period"],
    weight: 6,
  },
  {
    keywords: ["sponsor representative", "sponsor", "representative", "chairwoman", "chairman", "资方", "赞助", "代表"],
    tags: ["sponsor", "executive", "professional", "formal", "mature"],
    avoidTags: ["student", "dancer", "performer", "wedding", "bride", "royal", "period"],
    weight: 6,
  },
  {
    keywords: ["lawyer", "attorney", "legal", "contract counsel", "律师", "法务"],
    tags: ["lawyer", "professional", "office", "formal"],
    avoidTags: ["student", "wedding", "bride", "performer"],
    weight: 6,
  },
  {
    keywords: ["ceo", "founder", "board member", "investor", "executive", "secretary", "assistant", "总裁", "创始人", "董事", "投资人", "秘书", "助理"],
    tags: ["executive", "professional", "office", "formal"],
    avoidTags: ["student", "wedding", "bride", "royal", "period"],
    weight: 5,
  },
  {
    keywords: ["student", "classmate", "campus", "mentor", "professor", "teacher", "学生", "同学", "导师", "教授", "老师"],
    tags: ["student", "campus", "young"],
    avoidTags: ["executive", "sponsor", "wedding", "bride", "royal"],
    weight: 5,
  },
  {
    keywords: ["bride", "groom", "wedding", "fiance", "fiancee", "新娘", "新郎", "婚礼", "未婚"],
    tags: ["wedding", "formal", "relationship", "family"],
    weight: 6,
  },
  {
    keywords: ["elder", "grandfather", "grandmother", "patriarch", "matriarch", "inheritance", "will", "estate", "长辈", "祖父", "祖母", "家主", "继承", "遗嘱"],
    tags: ["elder", "family", "inheritance", "mature", "formal"],
    avoidTags: ["student", "dancer", "performer"],
    weight: 6,
  },
]

const AVATAR_CONTEXT_RULES: readonly AvatarQueryRule[] = [
  {
    keywords: ["backstage", "awards", "livestream", "stage", "singer", "idol", "producer", "fans", "control room", "后台", "直播", "舞台", "颁奖"],
    tags: ["entertainment", "backstage", "stage"],
    avoidTags: ["royal", "period", "wedding", "bride"],
    weight: 2,
  },
  {
    keywords: ["office", "boardroom", "merger", "contract", "company", "investor", "办公室", "董事会", "合同", "公司"],
    tags: ["professional", "office", "executive"],
    avoidTags: ["wedding", "bride", "royal", "period"],
    weight: 2,
  },
  {
    keywords: ["campus", "student", "auditorium", "archive", "library", "school", "校园", "学生", "礼堂", "档案", "图书馆"],
    tags: ["campus", "student"],
    avoidTags: ["executive", "sponsor", "wedding", "bride"],
    weight: 2,
  },
  {
    keywords: ["wedding", "banquet", "bride", "groom", "aisle", "婚礼", "婚宴", "新娘", "新郎"],
    tags: ["wedding", "formal", "family"],
    weight: 2,
  },
  {
    keywords: ["family", "inheritance", "will reading", "mansion", "estate", "家族", "继承", "遗嘱", "豪门"],
    tags: ["family", "inheritance", "formal"],
    weight: 2,
  },
]

const NEUTRAL_PROFESSIONAL_AVATARS = [
  "female-07",
  "female-03",
  "female-01",
  "male-03",
  "lawyer-01",
  "male-10",
] as const

const SEMANTIC_AVATAR_MIN_SCORE = 10

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
type SegmentTheme =
  | "backstage-entertainment"
  | "office-boardroom"
  | "campus"
  | "wedding"
  | "family-inheritance"

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

const SEGMENT_THEME_POOLS: Record<SegmentPhase, Partial<Record<SegmentTheme, readonly string[]>>> = {
  opening: {
    "backstage-entertainment": [
      "opening_backstage_control_room_clear_v2",
      "opening_backstage_control_room",
      "opening_backstage_vanity",
    ],
    "office-boardroom": ["opening_office_night_merger_clear_v2", "opening_office_night_merger"],
    campus: ["opening_campus_auditorium_night_clear_v2", "opening_campus_auditorium_night", "opening_campus_rain_gate"],
    wedding: ["opening_wedding_banquet_hall_clear_v2", "opening_wedding_banquet_hall"],
    "family-inheritance": ["opening_family_will_reading_clear_v2", "opening_family_will_reading"],
  },
  pressure: {
    "backstage-entertainment": [
      "pressure_backstage_press_crush_clear_v2",
      "pressure_backstage_press_crush",
      "pressure_press_hallway",
    ],
    "office-boardroom": ["pressure_office_contract_table_clear_v2", "pressure_office_contract_table", "pressure_boardroom_vote"],
    campus: ["pressure_campus_archive_lock_clear_v2", "pressure_campus_archive_lock"],
    wedding: ["pressure_wedding_family_table_clear_v2", "pressure_wedding_family_table"],
    "family-inheritance": [
      "pressure_family_banquet_standoff_clear_v2",
      "pressure_family_banquet_standoff",
      "pressure_family_banquet",
    ],
  },
  reversal: {
    "office-boardroom": ["reversal_office_elevator_secret_clear_v2", "reversal_office_elevator_secret", "reversal_elevator_standoff"],
    wedding: ["reversal_wedding_dropped_note_clear_v2", "reversal_wedding_dropped_note", "reversal_wedding_aisle"],
  },
  reveal: {
    "backstage-entertainment": ["reveal_backstage_empty_spotlight_clear_v2", "reveal_backstage_empty_spotlight"],
    campus: ["reveal_campus_phone_reflection_clear_v2", "reveal_campus_phone_reflection", "reveal_phone_reflection"],
  },
  terminal: {
    "family-inheritance": ["terminal_family_empty_mansion_clear_v2", "terminal_family_empty_mansion"],
  },
}

const SEGMENT_THEME_RULES: Array<{ theme: SegmentTheme; keywords: readonly string[] }> = [
  {
    theme: "backstage-entertainment",
    keywords: [
      "backstage", "control room", "awards", "livestream", "singer", "idol", "stage", "spotlight",
      "producer", "sponsor", "fans", "press", "celebrity", "show", "后台", "直播", "歌手", "粉丝", "舞台",
    ],
  },
  {
    theme: "office-boardroom",
    keywords: [
      "office", "boardroom", "merger", "contract", "executive", "investor", "company",
      "conference", "elevator", "deadline", "董事会", "并购", "合同", "公司", "会议",
    ],
  },
  {
    theme: "campus",
    keywords: [
      "campus", "student", "auditorium", "archive", "library", "college", "school",
      "scholarship", "confession", "校园", "学生", "礼堂", "档案", "图书馆",
    ],
  },
  {
    theme: "wedding",
    keywords: [
      "wedding", "banquet", "bride", "groom", "aisle", "family table", "dropped note",
      "marriage", "婚礼", "婚宴", "新娘", "新郎", "请帖",
    ],
  },
  {
    theme: "family-inheritance",
    keywords: [
      "family", "inheritance", "will reading", "sealed will", "mansion", "banquet", "estate",
      "heir", "家族", "继承", "遗嘱", "豪门", "宴会",
    ],
  },
]

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
  const slugs = SEGMENT_PHASES.flatMap((phase) => [
    ...SEGMENT_PHASE_POOLS[phase],
    ...Object.values(SEGMENT_THEME_POOLS[phase]).flatMap((pool) => [...(pool ?? [])]),
  ])
  return [...new Set(slugs)]
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
  const themed = theme ? THEME_TO_SHELL[theme] : undefined
  const shell = themed ?? pick(SHELLS, storyId)
  return `/webtoons/shells/${shellVariantSlug(shell, storyId)}.jpg`
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
  const pool = AVATAR_METADATA.filter((meta) => (
    (!gender || meta.gender === gender)
    && !meta.tags.includes("object")
    && !meta.tags.includes("letter")
  ))
  const picked = pick(pool.length > 0 ? pool : AVATAR_METADATA, key)
  return `/webtoons/avatars/${picked.slug}.jpg`
}

export function getDefaultAvatar(gender?: "female" | "male"): string {
  return gender === "male"
    ? "/webtoons/ui/default-avatar-male.jpg"
    : "/webtoons/ui/default-avatar-female.jpg"
}

// ───────── scenes / segments ─────────

/** Background art for the play stage, picked by the current beat phase. */
export function getSceneByPhase(phase: string | null | undefined, key = "default", corpus = ""): string {
  const slug = (SEGMENT_PHASES.find((p) => p === phase) ?? "opening") as SegmentPhase
  const theme = inferSegmentTheme(corpus)
  const themedPool = theme ? SEGMENT_THEME_POOLS[slug][theme] : undefined
  if (themedPool && themedPool.length > 0) {
    return `/webtoons/segments/${themedPool[0]}.jpg`
  }
  return `/webtoons/segments/${pick(SEGMENT_PHASE_POOLS[slug], `segment|${slug}|${key}`)}.jpg`
}

function inferSegmentTheme(corpus: string): SegmentTheme | null {
  const normalized = corpus.toLowerCase()
  for (const rule of SEGMENT_THEME_RULES) {
    if (rule.keywords.some((kw) => normalized.includes(kw.toLowerCase()))) {
      return rule.theme
    }
  }
  return null
}

// ───────── endings ─────────

/** Ending artwork. Hash by ending_id so each ending always uses the same canvas. */
export function getEndingArtwork(endingId: string | null | undefined): string {
  const key = endingId ?? "default"
  return `/webtoons/endings/${pick(ENDING_VARIANTS, key)}.jpg`
}

// ───────── page-level backgrounds ─────────

export const PAGE_BG = {
  splash: "/webtoons/ui/splash.jpg",
  home: "/webtoons/ui/library_bg.jpg",
  create: "/webtoons/ui/generated/create-agent-room-bg-v1.png",
  generating: "/webtoons/ui/loading_bg.jpg",
  login: "/webtoons/ui/auth_bg.jpg",
} as const

export const LOGO_URL = "/webtoons/ui/logo.png"

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
  shells: SHELLS.flatMap((s) => shellVariantSlugs(s).map((slug) => `/webtoons/shells/${slug}.jpg`)),
  avatars: {
    female: AVATAR_FEMALE.map((s) => `/webtoons/avatars/${s}.jpg`),
    male: AVATAR_MALE.map((s) => `/webtoons/avatars/${s}.jpg`),
  },
  advisors: ADVISOR_AVATARS.map((s) => `/webtoons/advisors/${s}.jpg`),
  segments: segmentSlugs().map((s) => `/webtoons/segments/${s}.jpg`),
  endings: ENDING_VARIANTS.map((s) => `/webtoons/endings/${s}.jpg`),
  peaks: PEAK_CLOSEUPS.map((s) => `/webtoons/peaks/${s}.jpg`),
} as const

// ───────── narrative (template/session) helpers ─────────
// The narrative engine doesn't expose shell_id directly, so we infer
// from seed + role text using lightweight keyword matching. Same for
// gender (used to pick a female vs. male portrait pool).

type LooseCast = { character_id: string; display_name: string; role: string; relation_to_protagonist: string }
type LooseLocalizedText = { zh?: string | null; en?: string | null }
type LooseTemplate = {
  template_id: string
  seed: string
  title?: string
  title_i18n?: LooseLocalizedText | null
  summary_i18n?: LooseLocalizedText | null
  cover_image_url?: string | null
  cast: LooseCast[]
  player_role_options?: Array<{ label?: string | null; public_persona?: string | null }> | null
}

type GeneratedCoverKey =
  | "generated_entertainment_backstage_disappearance"
  | "generated_entertainment_backstage_disappearance_v2"
  | "generated_entertainment_press_hallway_v1"
  | "generated_office_boardroom_betrayal"
  | "generated_office_boardroom_betrayal_v2"
  | "generated_office_contract_deadline_v1"
  | "generated_campus_rain_secret"
  | "generated_campus_rain_secret_v2"
  | "generated_campus_auditorium_confession_v1"
  | "generated_sci_fi_mars_colony_stage"
  | "generated_fantasy_artifact_auction"
  | "generated_wedding_aisle_betrayal"
  | "generated_wedding_aisle_betrayal_v2"
  | "generated_wedding_banquet_reveal_v1"
  | "generated_family_banquet_inheritance"
  | "generated_family_banquet_inheritance_v2"
  | "generated_family_will_reading_v1"
  | "generated_rooftop_gala_confrontation"
  | "generated_hospital_secret_deadline"
  | "generated_urban_alley_witness"

const GENERATED_COVER_THEME_SHELLS: Record<GeneratedCoverKey, Shell> = {
  generated_entertainment_backstage_disappearance: "entertainment_scandal",
  generated_entertainment_backstage_disappearance_v2: "entertainment_scandal",
  generated_entertainment_press_hallway_v1: "entertainment_scandal",
  generated_office_boardroom_betrayal: "office_power",
  generated_office_boardroom_betrayal_v2: "office_power",
  generated_office_contract_deadline_v1: "office_power",
  generated_campus_rain_secret: "campus_romance",
  generated_campus_rain_secret_v2: "campus_romance",
  generated_campus_auditorium_confession_v1: "campus_romance",
  generated_sci_fi_mars_colony_stage: "urban_supernatural",
  generated_fantasy_artifact_auction: "palace_drama",
  generated_wedding_aisle_betrayal: "wedding",
  generated_wedding_aisle_betrayal_v2: "wedding",
  generated_wedding_banquet_reveal_v1: "wedding",
  generated_family_banquet_inheritance: "wealth_families",
  generated_family_banquet_inheritance_v2: "wealth_families",
  generated_family_will_reading_v1: "wealth_families",
  generated_rooftop_gala_confrontation: "wealth_families",
  generated_hospital_secret_deadline: "courtroom",
  generated_urban_alley_witness: "urban_supernatural",
}

const GENERATED_COVER_FALLBACKS: Record<GeneratedCoverKey, string> = {
  generated_entertainment_backstage_disappearance:
    "/webtoons/covers/generated/cover-entertainment-backstage-disappearance-v1.jpg",
  generated_entertainment_backstage_disappearance_v2:
    "/webtoons/covers/generated/cover-entertainment-backstage-disappearance-v2.jpg",
  generated_entertainment_press_hallway_v1:
    "/webtoons/covers/generated/cover-entertainment-press-hallway-v1.jpg",
  generated_office_boardroom_betrayal:
    "/webtoons/covers/generated/cover-office-boardroom-betrayal-v1.jpg",
  generated_office_boardroom_betrayal_v2:
    "/webtoons/covers/generated/cover-office-boardroom-betrayal-v2.jpg",
  generated_office_contract_deadline_v1:
    "/webtoons/covers/generated/cover-office-contract-deadline-v1.jpg",
  generated_campus_rain_secret:
    "/webtoons/covers/generated/cover-campus-rain-secret-v1.jpg",
  generated_campus_rain_secret_v2:
    "/webtoons/covers/generated/cover-campus-rain-secret-v2.jpg",
  generated_campus_auditorium_confession_v1:
    "/webtoons/covers/generated/cover-campus-auditorium-confession-v1.jpg",
  generated_sci_fi_mars_colony_stage:
    "/webtoons/covers/generated/cover-sci-fi-mars-colony-stage-v1.jpg",
  generated_fantasy_artifact_auction:
    "/webtoons/covers/generated/cover-fantasy-artifact-auction-v1.jpg",
  generated_wedding_aisle_betrayal:
    "/webtoons/covers/generated/cover-wedding-aisle-betrayal-v1.jpg",
  generated_wedding_aisle_betrayal_v2:
    "/webtoons/covers/generated/cover-wedding-aisle-betrayal-v2.jpg",
  generated_wedding_banquet_reveal_v1:
    "/webtoons/covers/generated/cover-wedding-banquet-reveal-v1.jpg",
  generated_family_banquet_inheritance:
    "/webtoons/covers/generated/cover-family-banquet-inheritance-v1.jpg",
  generated_family_banquet_inheritance_v2:
    "/webtoons/covers/generated/cover-family-banquet-inheritance-v2.jpg",
  generated_family_will_reading_v1:
    "/webtoons/covers/generated/cover-family-will-reading-v1.jpg",
  generated_rooftop_gala_confrontation:
    "/webtoons/covers/generated/cover-rooftop-gala-confrontation-v1.jpg",
  generated_hospital_secret_deadline:
    "/webtoons/covers/generated/cover-hospital-secret-deadline-v1.jpg",
  generated_urban_alley_witness:
    "/webtoons/covers/generated/cover-urban-alley-witness-v1.jpg",
}

const GENERATED_COVER_FALLBACK_POOLS: Partial<Record<GeneratedCoverKey, readonly GeneratedCoverKey[]>> = {
  generated_entertainment_backstage_disappearance: [
    "generated_entertainment_backstage_disappearance",
    "generated_entertainment_backstage_disappearance_v2",
    "generated_entertainment_press_hallway_v1",
  ],
  generated_office_boardroom_betrayal: [
    "generated_office_boardroom_betrayal",
    "generated_office_boardroom_betrayal_v2",
    "generated_office_contract_deadline_v1",
  ],
  generated_campus_rain_secret: [
    "generated_campus_rain_secret",
    "generated_campus_rain_secret_v2",
    "generated_campus_auditorium_confession_v1",
  ],
  generated_wedding_aisle_betrayal: [
    "generated_wedding_aisle_betrayal",
    "generated_wedding_aisle_betrayal_v2",
    "generated_wedding_banquet_reveal_v1",
  ],
  generated_family_banquet_inheritance: [
    "generated_family_banquet_inheritance",
    "generated_family_banquet_inheritance_v2",
    "generated_family_will_reading_v1",
  ],
}

const GENERATED_COVER_RULES: Array<{ key: GeneratedCoverKey; keywords: readonly string[] }> = [
  {
    key: "generated_sci_fi_mars_colony_stage",
    keywords: ["mars", "colony", "oxygen", "space", "sci-fi", "science fiction", "talent show", "火星", "殖民", "氧气"],
  },
  {
    key: "generated_fantasy_artifact_auction",
    keywords: ["artifact", "auction", "relic", "jade", "spellbook", "star-map", "法器", "遗物", "拍卖", "玉"],
  },
  {
    key: "generated_hospital_secret_deadline",
    keywords: ["hospital", "hospital deadline", "hospital ward", "doctor", "medical", "emergency", "injury", "医院", "病房", "医生", "急诊", "伤情"],
  },
  {
    key: "generated_wedding_aisle_betrayal",
    keywords: ["wedding", "aisle", "bride", "groom", "chapel", "marriage", "婚礼", "婚纱", "新娘", "新郎"],
  },
  {
    key: "generated_entertainment_backstage_disappearance",
    keywords: [
      "backstage", "idol", "singer", "livestream", "awards", "disappearance", "fans",
      "celebrity", "red carpet", "missing singer", "后台", "偶像", "歌手", "直播", "颁奖", "粉丝",
    ],
  },
  {
    key: "generated_office_boardroom_betrayal",
    keywords: ["boardroom", "investor", "merger", "contract", "office", "cofounder", "company", "audit", "董事会", "投资人", "并购", "合同", "公司"],
  },
  {
    key: "generated_campus_rain_secret",
    keywords: ["campus", "rain", "student", "archive", "library", "secret", "college", "school", "校园", "雨", "学生", "档案", "图书馆", "秘密"],
  },
  {
    key: "generated_family_banquet_inheritance",
    keywords: ["family", "banquet", "inheritance", "will", "estate", "heir", "wealth", "家族", "宴会", "继承", "遗嘱", "豪门"],
  },
  {
    key: "generated_rooftop_gala_confrontation",
    keywords: ["rooftop", "gala", "confrontation", "champagne", "wealthy", "party", "天台", "酒会", "对峙", "晚宴"],
  },
  {
    key: "generated_urban_alley_witness",
    keywords: ["alley", "witness", "neon", "street", "envelope", "pursuer", "urban", "巷", "目击", "霓虹", "街", "信封"],
  },
]

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

function templateCoverCorpus(template: LooseTemplate): string {
  const metadata = [
    template.title_i18n?.zh,
    template.title_i18n?.en,
    template.summary_i18n?.zh,
    template.summary_i18n?.en,
  ].filter(Boolean).join(" ")
  const corpus = [
    template.seed,
    template.title ?? "",
    metadata,
    template.cast
      .map((c) => `${c.display_name} ${c.role} ${c.relation_to_protagonist}`)
      .join(" "),
  ].join(" ").toLowerCase()
  return corpus
}

function inferGeneratedCoverKey(template: LooseTemplate): GeneratedCoverKey | null {
  const corpus = templateCoverCorpus(template)
  for (const rule of GENERATED_COVER_RULES) {
    if (rule.keywords.some((kw) => corpus.includes(kw.toLowerCase()))) {
      return rule.key
    }
  }
  return null
}

function fallbackCoverCandidates(template: LooseTemplate): string[] {
  const key = inferGeneratedCoverKey(template)
  const shell = key ? GENERATED_COVER_THEME_SHELLS[key] : inferShell(template)
  const generated = key
    ? [...(GENERATED_COVER_FALLBACK_POOLS[key] ?? [key])].map((generatedKey) => (
        GENERATED_COVER_FALLBACKS[generatedKey]
      ))
    : []
  const shellVariants = shellVariantSlugs(shell).map((slug) => `/webtoons/shells/${slug}.jpg`)
  const preferredShell = `/webtoons/shells/${shellVariantSlug(shell, template.template_id)}.jpg`
  const orderedShellVariants = [
    preferredShell,
    ...shellVariants.filter((candidate) => candidate !== preferredShell),
  ]
  return [...generated, ...orderedShellVariants]
}

const FEMALE_ROLE_HINTS = [
  "妻", "妻子", "夫人", "母", "妈", "女儿", "妹", "姐", "姑娘", "小姐", "千金",
  "公主", "皇后", "继母", "学姐", "学妹", "女主", "少奶奶", "新娘", "未婚妻",
  "经纪人", "助理", "闺蜜", "情人",
  "wife", "mother", "daughter", "sister", "bride", "fiancee", "girlfriend",
  "queen", "princess", "assistant", "manager", "actress", "chairwoman", "woman",
  "female", "girl",
]
const MALE_ROLE_HINTS = [
  "夫", "丈夫", "父", "爸", "儿子", "弟", "哥", "少爷", "总裁", "霸总",
  "皇帝", "王", "继父", "学长", "男主", "新郎", "未婚夫",
  "husband", "father", "son", "brother", "groom", "fiance", "boyfriend",
  "king", "prince", "ceo", "founder", "cofounder", "actor", "chairman", "man",
  "male", "boy",
]

function inferGender(...parts: Array<string | null | undefined>): AvatarGenderPresentation | null {
  const corpus = parts.filter(Boolean).join(" ").toLowerCase()
  const female = FEMALE_ROLE_HINTS.some((kw) => corpusHasKeyword(corpus, kw))
  const male = MALE_ROLE_HINTS.some((kw) => corpusHasKeyword(corpus, kw))
  if (female && !male) return "female"
  if (male && !female) return "male"
  return null
}

function avatarCorpusFromContext(context: LooseTemplate | string | null | undefined): string {
  if (!context) return ""
  if (typeof context === "string") return context
  const metadata = [
    context.title_i18n?.zh,
    context.title_i18n?.en,
    context.summary_i18n?.zh,
    context.summary_i18n?.en,
  ].filter(Boolean).join(" ")
  const playerRoles = (context.player_role_options ?? [])
    .map((role) => `${role.label ?? ""} ${role.public_persona ?? ""}`)
    .join(" ")
  return [
    context.seed,
    context.title ?? "",
    metadata,
    playerRoles,
    context.cast.map((c) => `${c.display_name} ${c.role} ${c.relation_to_protagonist}`).join(" "),
  ].join(" ").toLowerCase()
}

function addWeightedTag(weights: Record<string, number>, tag: string, weight: number): void {
  weights[tag] = (weights[tag] ?? 0) + weight
}

function addWeightedTags(weights: Record<string, number>, tags: readonly string[], weight: number): void {
  for (const tag of tags) addWeightedTag(weights, tag, weight)
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function corpusHasKeyword(corpus: string, keyword: string): boolean {
  const normalized = keyword.toLowerCase().trim()
  if (!normalized) return false
  if (/^[a-z0-9][a-z0-9\s-]*[a-z0-9]$|^[a-z0-9]$/i.test(normalized)) {
    const spaced = escapeRegExp(normalized).replace(/\s+/g, "\\s+")
    return new RegExp(`\\b${spaced}\\b`, "i").test(corpus)
  }
  return corpus.includes(normalized)
}

function applyAvatarRules(
  query: AvatarQuery,
  corpus: string,
  rules: readonly AvatarQueryRule[],
  defaultWeight: number,
): number {
  let hits = 0
  for (const rule of rules) {
    if (!rule.keywords.some((keyword) => corpusHasKeyword(corpus, keyword))) continue
    hits += 1
    addWeightedTags(query.weights, rule.tags, rule.weight ?? defaultWeight)
    // The first tag is the rule's identity tag (publicist, dancer, sponsor,
    // etc.). Boost it so a rich contextual match cannot swamp the actual role.
    if (rule.tags[0]) addWeightedTag(query.weights, rule.tags[0], rule.weight ?? defaultWeight)
    if (rule.avoidTags) {
      query.avoidTags = [...new Set([...query.avoidTags, ...rule.avoidTags])]
    }
    if (rule.gender && !query.gender) {
      query.gender = rule.gender
    }
  }
  return hits
}

function buildAvatarQuery(
  templateId: string,
  member: LooseCast,
  context?: LooseTemplate | string | null,
): AvatarQuery {
  const memberCorpus = [
    member.character_id,
    member.display_name,
    member.role,
    member.relation_to_protagonist,
  ].join(" ").toLowerCase()
  const contextCorpus = avatarCorpusFromContext(context)
  const query: AvatarQuery = {
    key: `${templateId}|${member.character_id}`,
    gender: inferGender(member.character_id, member.display_name, member.role, member.relation_to_protagonist),
    weights: {},
    avoidTags: [],
    roleRuleHits: 0,
  }

  applyAvatarRules(query, contextCorpus, AVATAR_CONTEXT_RULES, 2)
  query.roleRuleHits = applyAvatarRules(query, memberCorpus, AVATAR_ROLE_RULES, 5)

  if (query.gender) addWeightedTag(query.weights, query.gender, 2)
  addWeightedTag(query.weights, "character", 4)
  addWeightedTag(query.weights, "portrait", 4)
  return query
}

function avatarIsAllowed(meta: AvatarMetadata, query: AvatarQuery): boolean {
  const tags = new Set([...meta.tags, ...(meta.avoidTags ?? [])])
  if (tags.has("object") || tags.has("letter")) return false
  if (query.avoidTags.some((tag) => tags.has(tag))) return false
  return true
}

function avatarSemanticScore(meta: AvatarMetadata, query: AvatarQuery): number {
  let score = 0
  if (query.gender) {
    score += meta.gender === query.gender ? 4 : -5
  }
  for (const [tag, weight] of Object.entries(query.weights)) {
    if (tag === meta.gender || meta.tags.includes(tag)) score += weight
  }
  return score
}

function stableAvatarTieValue(queryKey: string, slug: string): number {
  return stableHash(`avatar-semantic-tie|${queryKey}|${slug}`)
}

function rankAvatarCandidates(query: AvatarQuery): Array<{ meta: AvatarMetadata; score: number }> {
  return AVATAR_METADATA
    .filter((meta) => avatarIsAllowed(meta, query))
    .map((meta) => ({ meta, score: avatarSemanticScore(meta, query) }))
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return stableAvatarTieValue(query.key, a.meta.slug) - stableAvatarTieValue(query.key, b.meta.slug)
    })
}

function neutralAvatarForQuery(query: AvatarQuery): string {
  const neutral = NEUTRAL_PROFESSIONAL_AVATARS
    .map((slug) => AVATAR_METADATA.find((meta) => meta.slug === slug))
    .filter((meta): meta is AvatarMetadata => Boolean(meta))
    .filter((meta) => !query.gender || meta.gender === query.gender)
  const pool = neutral.length > 0 ? neutral : AVATAR_METADATA.filter((meta) => avatarIsAllowed(meta, query))
  const picked = pick(pool, `neutral-avatar|${query.key}`)
  return picked ? `/webtoons/avatars/${picked.slug}.jpg` : getDefaultAvatar(query.gender ?? undefined)
}

function resolveGeneratedCoverUrl(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  if (!trimmed) return null
  if (/[\n\r"'()\\]/.test(trimmed)) return null
  if (
    trimmed.startsWith("/webtoons/")
    || trimmed.startsWith("/generated/")
    || trimmed.startsWith("/uploads/")
    || trimmed.startsWith("https://")
  ) {
    return trimmed
  }
  return null
}

/** Cover for a template card / hero. Uses variant -01/-02 deterministically
 *  per template so two templates of the same shell get different visuals. */
export function getCoverForTemplate(template: LooseTemplate): string {
  const generatedCover = resolveGeneratedCoverUrl(template.cover_image_url)
  if (generatedCover) return generatedCover
  const [preferred] = fallbackCoverCandidates(template)
  if (preferred) return preferred
  const shell = inferShell(template)
  return `/webtoons/shells/${shellVariantSlug(shell, template.template_id)}.jpg`
}

export function assignTemplateCovers<T extends LooseTemplate>(templates: readonly T[]): Record<string, string> {
  const assigned: Record<string, string> = {}
  const usedFallbackCovers = new Set<string>()
  for (const [index, template] of templates.entries()) {
    const generatedCover = resolveGeneratedCoverUrl(template.cover_image_url)
    if (generatedCover) {
      assigned[template.template_id] = generatedCover
      usedFallbackCovers.add(generatedCover)
      continue
    }
    const candidates = fallbackCoverCandidates(template)
    const preferred = candidates[0] ?? getCoverForTemplate(template)
    let selected = preferred
    if (usedFallbackCovers.has(selected)) {
      for (const candidate of candidates) {
        if (!usedFallbackCovers.has(candidate)) {
          selected = candidate
          break
        }
      }
    }
    if (usedFallbackCovers.has(selected) && candidates.length > 0) {
      selected = candidates[stableHash(`cover-list|${template.template_id}|${index}`) % candidates.length]
    }
    assigned[template.template_id] = selected
    usedFallbackCovers.add(selected)
  }
  return assigned
}

/** Stable per-character avatar within a template. */
export function getAvatarForCastMember(
  templateId: string,
  member: LooseCast,
  context?: LooseTemplate | string | null,
): string {
  const query = buildAvatarQuery(templateId, member, context)
  const [winner] = rankAvatarCandidates(query)
  if (!winner || query.roleRuleHits === 0 || winner.score < SEMANTIC_AVATAR_MIN_SCORE) {
    return neutralAvatarForQuery(query)
  }
  return `/webtoons/avatars/${winner.meta.slug}.jpg`
}

/** Avatar for the advisor FAB / sidechat header. Pulls from a dedicated
 *  /webtoons/advisors/ pool so the advisor never collides with a cast NPC.
 *  The pool already mixes genders, so persona text isn't needed for the
 *  selection — we just hash by template_id for stability. */
export function getAdvisorAvatar(templateId: string, _persona: string): string {
  return `/webtoons/advisors/${pick(ADVISOR_AVATARS, `advisor|${templateId}`)}.jpg`
}

// ───────── ending illustrations ─────────
// Each backend ENDING_LABELS entry maps to a Codex-generated v2 illustration
// at /webtoons/endings/v2/{slug}.jpg. The mapping is deliberate (not random)
// so the same label always shows the same image — the visual symbolism of
// the ending is part of the shareable identity.

const ENDING_LABEL_TO_SLUG: Record<string, string> = {
  孤狼: "loner",
  共谋: "conspiracy",
  复仇: "vengeance",
  和解: "reconciliation",
  牺牲: "sacrifice",
  自由: "liberation",
  沉沦: "fallen",
  救赎: "redemption",
  失控: "unraveling",
  反噬: "backfire",
  同谋: "ally",
  决裂: "severance",
  回归: "return",
  破碎: "broken",
  夺回: "reclaim",
}

/** Illustration for an ending label. Falls back to 'unraveling' for any
 *  label not in the table (which would be a bug — backend snaps off-pool
 *  labels to '失控' anyway). */
export function getEndingIllustration(label: string | null | undefined): string {
  if (!label) return "/webtoons/endings/v2/unraveling.jpg"
  const slug = ENDING_LABEL_TO_SLUG[label] ?? "unraveling"
  return `/webtoons/endings/v2/${slug}.jpg`
}

// ───────── tier splash banners ─────────
// Victory / compromised / collapsed splashes layer over the ending
// illustration to amplify the emotional beat of the closing screen.
// All three tiers now have their own splash so the trio feels intentional.

export function getTierSplash(
  tier: "victory" | "compromised" | "collapsed" | null | undefined,
): string | null {
  if (tier === "victory") return "/webtoons/splashes/victory.jpg"
  if (tier === "collapsed") return "/webtoons/splashes/game_over.jpg"
  if (tier === "compromised") return "/webtoons/splashes/compromised.jpg"
  return null
}

// ───────── empty state ─────────

export function getEmptyPlazaImage(): string {
  return "/webtoons/empty/plaza.jpg"
}

export function getPeakCloseUp(messageOrd: number): string {
  const slug = pick(PEAK_CLOSEUPS, `peak|${messageOrd}`)
  return `/webtoons/peaks/${slug}.jpg`
}

// ───────── advisor oracle vignette ─────────
// Single atmospheric texture layered behind oracle reply bubbles to
// make the "I paid a turn for this" moment feel ritualistic.

export const ORACLE_VIGNETTE = "/webtoons/oracle/vignette.jpg"

import type { Lang } from "./i18n"

export type StoryGuideTensionProfile =
  | "high_drama"
  | "cozy_mystery"
  | "comedy"
  | "fantasy_sci_fi"
  | "family_social"

export type StoryGuideSettingDeltas = {
  turnBudget?: 8 | 12 | 20
  difficulty?: "story" | "gauntlet"
  language?: Lang
  tensionProfile?: StoryGuideTensionProfile
  privacyIntent?: "private" | "unlisted" | "public"
}

export function inferStoryGuideSettings(text: string, lang: Lang = "en"): StoryGuideSettingDeltas {
  const lower = text.toLowerCase()
  const settings: StoryGuideSettingDeltas = {}

  if (/\b(short|quick|shorter|10\s*(min|minute|minutes)|short run)\b/i.test(text) || /短一点|短篇|十分钟|10分钟/.test(text)) {
    settings.turnBudget = 8
  } else if (/\b(long|longer|25\s*(min|minute|minutes)|epic)\b/i.test(text) || /长一点|长篇|史诗|25分钟|二十五分钟/.test(text)) {
    settings.turnBudget = 20
  } else if (/\b(15\s*(min|minute|minutes)|one sitting)\b/i.test(text) || /15分钟|十五分钟|一口气|一坐/.test(text)) {
    settings.turnBudget = 12
  }

  if (
    /\b(hard mode|npc(?:s)? fight back|make it dangerous|can i lose|gauntlet)\b/i.test(text) ||
    /博弈|反击|会输|高难|危险一点/.test(text)
  ) {
    settings.difficulty = "gauntlet"
  } else if (/\b(story mode|easy mode|gentle mode|can't lose|cannot lose)\b/i.test(text) || /故事模式|轻松|不要输/.test(text)) {
    settings.difficulty = "story"
  }

  if (/\b(make it chinese|switch (?:it )?to chinese|change (?:it )?to chinese|in chinese|chinese language|write in chinese)\b/i.test(text) || /中文|改成中文|切到中文|用中文|简体中文/.test(text)) {
    settings.language = "zh"
  } else if (/\b(make it english|switch (?:it )?to english|change (?:it )?to english|in english|english language|write in english)\b/i.test(text) || /英文|英语|改成英文|切到英文|用英文写|用英语写/.test(text)) {
    settings.language = "en"
  } else {
    const cjkCount = (text.match(/[\u3400-\u9fff]/g) ?? []).length
    const latinCount = (text.match(/[A-Za-z]/g) ?? []).length
    if (cjkCount >= 6 && cjkCount > latinCount / 2) {
      settings.language = "zh"
    } else if (latinCount >= 16 && latinCount > cjkCount * 2) {
      settings.language = "en"
    } else if (lang === "zh" || lang === "en") {
      settings.language = lang
    }
  }

  if (/\b(mars|colony|artifact|relic|auction|faction|clan|dragon|eclipse|star-?map|sci[- ]?fi|science fiction)\b/i.test(text) || /火星|殖民地|神器|拍卖|阵营|氏族|龙族|日食|星图|科幻|奇幻/.test(text)) {
    settings.tensionProfile = "fantasy_sci_fi"
  } else if (/\b(backstage|disappearance|public scandal|livestream|awards?|idol|singer|producer|public fallout)\b/i.test(text) || /后台|失踪|直播|颁奖|偶像|主唱|制作人|舆论/.test(text)) {
    settings.tensionProfile = "high_drama"
  } else if (/\b(funny|awkward|misunderstanding|comedy|comic)\b/i.test(text) || /喜剧|搞笑|尴尬|误会/.test(text)) {
    settings.tensionProfile = "comedy"
  } else if (/\b(cozy|clues?|small town|gentle mystery)\b/i.test(text) || /轻悬疑|温和悬疑|线索|小镇/.test(text)) {
    settings.tensionProfile = "cozy_mystery"
  } else if (/\b(family|banquet|wedding|relationship rupture|inheritance|will reading)\b/i.test(text) || /家庭|家宴|婚礼|继承|遗嘱|关系破裂/.test(text)) {
    settings.tensionProfile =
      /\b(betrayal|scandal|deadline|public|disappearance|blackmail)\b/i.test(text) || /背叛|丑闻|期限|公开|失踪/.test(text)
        ? "high_drama"
        : "family_social"
  } else if (/\b(high drama|dramatic|thriller|pressure)\b/i.test(text) || /高戏剧|戏剧|惊悚|压力/.test(text)) {
    settings.tensionProfile = "high_drama"
  } else if (/\b(slice of life|social pressure|social)\b/i.test(text) || /日常|社交/.test(text)) {
    settings.tensionProfile = "family_social"
  }

  const privacyIntent = detectPrivacyIntent(lower)
  if (privacyIntent) settings.privacyIntent = privacyIntent

  return settings
}

function detectPrivacyIntent(lower: string): StoryGuideSettingDeltas["privacyIntent"] | null {
  if (
    /\b(just me|only me|private|keep it private|no one else)\b/.test(lower) ||
    /只有我|仅自己|私有|不要公开/.test(lower)
  ) {
    return "private"
  }
  if (
    /\b(link only|unlisted|share by link|only by link|with the link)\b/.test(lower) ||
    /链接可见|凭链接|仅链接|通过链接/.test(lower)
  ) {
    return "unlisted"
  }
  if (
    /\b(make it public|publish it|everyone can play|publicly visible|put it on the plaza)\b/.test(lower) ||
    /公开发布|广场公开|所有人能玩|大家都能玩/.test(lower)
  ) {
    return "public"
  }
  return null
}

export function isPrivacyOnlyRequest(text: string): boolean {
  const normalized = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim()
  if (!normalized) return false
  if (normalized.length > 64) return false
  if (/\b(public pressure|public scandal|public fallout|publicist)\b/.test(normalized)) return false
  return Boolean(
    /\b(just me|only me|private|keep it private|link only|unlisted|share by link|make it public|publish it|everyone can play|publicly visible|put it on the plaza)\b/.test(normalized) ||
      /只有我|仅自己|私有|不要公开|链接可见|凭链接|仅链接|公开发布|广场公开|所有人能玩|大家都能玩/.test(normalized),
  )
}

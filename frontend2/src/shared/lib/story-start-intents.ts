import type { NarrativeTensionProfile } from "../../api/contracts"
import type { Lang, StringKey } from "./i18n"
import { GENERATED_ASSETS } from "./webtoon-assets"

export type StoryStartIntentId =
  | "cozy-social"
  | "fantasy-library"
  | "mars-colony"
  | "slow-mystery"
  | "slice-of-life"
  | "high-drama"

export type StoryStartIntent = {
  id: StoryStartIntentId
  titleKey: StringKey
  moodKey: StringKey
  pressureKey: StringKey
  ruleKey: StringKey
  hookKey: StringKey
  image: string
  tensionProfile: NarrativeTensionProfile
  seedDraft: Record<Lang, string>
}

export const STORY_START_INTENTS: readonly StoryStartIntent[] = [
  {
    id: "cozy-social",
    titleKey: "story_intent_cozy_title",
    moodKey: "story_intent_cozy_mood",
    pressureKey: "story_intent_cozy_pressure",
    ruleKey: "story_intent_cozy_rule",
    hookKey: "story_intent_cozy_hook",
    image: GENERATED_ASSETS.coverCozy,
    tensionProfile: "cozy_mystery",
    seedDraft: {
      en: "A cozy bake sale where three parents and a shy teen volunteer need to figure out why the recipe card disappeared before judging starts. No blackmail, no betrayal, no violence.",
      zh: "一场温暖的义卖烘焙比赛里，三位家长和害羞的少年志愿者要弄清楚评审前食谱卡为什么不见了。不要勒索、背叛或暴力。",
    },
  },
  {
    id: "fantasy-library",
    titleKey: "story_intent_fantasy_title",
    moodKey: "story_intent_fantasy_mood",
    pressureKey: "story_intent_fantasy_pressure",
    ruleKey: "story_intent_fantasy_rule",
    hookKey: "story_intent_fantasy_hook",
    image: GENERATED_ASSETS.coverFantasy,
    tensionProfile: "fantasy_sci_fi",
    seedDraft: {
      en: "Inside a floating dragon library during an eclipse, a shy apprentice spellbook and the banished dragon clan both claim the missing star map before the doors seal.",
      zh: "月蚀时的浮空龙族图书馆里，害羞的学徒魔法书和被放逐的龙族氏族都声称失踪星图与自己有关，而大门即将封闭。",
    },
  },
  {
    id: "mars-colony",
    titleKey: "story_intent_mars_title",
    moodKey: "story_intent_mars_mood",
    pressureKey: "story_intent_mars_pressure",
    ruleKey: "story_intent_mars_rule",
    hookKey: "story_intent_mars_hook",
    image: GENERATED_ASSETS.coverSciFiMars,
    tensionProfile: "comedy",
    seedDraft: {
      en: "At a Mars colony talent show, the Theatre Club, Earth Media, and a nervous oxygen technician all need the missing callback card explained before the livestream starts.",
      zh: "火星殖民地才艺秀开播前，剧社、地球媒体和紧张的氧气技术员都需要弄清楚那张失踪的提示卡到底去了哪里。",
    },
  },
  {
    id: "slow-mystery",
    titleKey: "story_intent_slow_mystery_title",
    moodKey: "story_intent_slow_mystery_mood",
    pressureKey: "story_intent_slow_mystery_pressure",
    ruleKey: "story_intent_slow_mystery_rule",
    hookKey: "story_intent_slow_mystery_hook",
    image: GENERATED_ASSETS.coverNeutral,
    tensionProfile: "cozy_mystery",
    seedDraft: {
      en: "In a quiet archive room before closing, a librarian, a visiting donor, and a retired mapmaker notice the town ledger has been moved to the wrong shelf.",
      zh: "闭馆前的安静档案室里，图书管理员、来访捐赠人和退休地图师发现镇志账册被放到了错误的书架上。",
    },
  },
  {
    id: "slice-of-life",
    titleKey: "story_intent_slice_title",
    moodKey: "story_intent_slice_mood",
    pressureKey: "story_intent_slice_pressure",
    ruleKey: "story_intent_slice_rule",
    hookKey: "story_intent_slice_hook",
    image: GENERATED_ASSETS.emptyPlaza,
    tensionProfile: "family_social",
    seedDraft: {
      en: "In a rainy neighborhood stationery shop, the owner, a student volunteer, and a regular customer must decide who gets the last handmade notebook before the farewell party.",
      zh: "雨天的社区文具店里，店主、学生志愿者和熟客必须在告别会前决定最后一本手作笔记本该给谁。",
    },
  },
  {
    id: "high-drama",
    titleKey: "story_intent_high_drama_title",
    moodKey: "story_intent_high_drama_mood",
    pressureKey: "story_intent_high_drama_pressure",
    ruleKey: "story_intent_high_drama_rule",
    hookKey: "story_intent_high_drama_hook",
    image: GENERATED_ASSETS.coverHighDrama,
    tensionProfile: "high_drama",
    seedDraft: {
      en: "Minutes before a board gala vote, my cofounder, my ex with a recording, and the legal lead all pressure me to explain the missing merger file.",
      zh: "董事会晚宴投票前几分钟，我的联合创始人、拿着录音的前任和法务负责人都逼我解释那份失踪的并购文件。",
    },
  },
] as const

const STORY_START_INTENT_BY_ID = new Map<StoryStartIntentId, StoryStartIntent>(
  STORY_START_INTENTS.map((intent) => [intent.id, intent]),
)

export function isStoryStartIntentId(value: string | null | undefined): value is StoryStartIntentId {
  return Boolean(value && STORY_START_INTENT_BY_ID.has(value as StoryStartIntentId))
}

export function getStoryStartIntent(id: string | null | undefined): StoryStartIntent | null {
  if (!isStoryStartIntentId(id)) return null
  return STORY_START_INTENT_BY_ID.get(id) ?? null
}

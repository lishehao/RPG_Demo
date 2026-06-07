import type { NarrativeDifficulty, NarrativeTemplateLanguage, NarrativeTemplateVisibility } from "../../api/contracts"
import type { Lang, StringKey } from "../../shared/lib/i18n"
import type { TensionProfileChoice } from "./create-types"

export const SEED_EXAMPLE_KEYS: StringKey[] = [
  "create.example_seed_1",
  "create.example_seed_2",
  "create.example_seed_3",
  "create.example_seed_4",
]
export const STORY_BUTLER_AVATAR = "/webtoons/ui/generated/story-butler-avatar-v1.png"
export const LONG_GENERATE_HANDOFF_THRESHOLD_MS = 30_000
export const LONG_GENERATE_HANDOFF_MIN_MS = 2_000

export const VISIBILITY_OPTION_IDS: NarrativeTemplateVisibility[] = ["private", "unlisted", "public"]

type TensionProfileOptionMeta = {
  id: TensionProfileChoice
  labelKey: StringKey
  descKey: StringKey
}

export const TENSION_PROFILE_OPTIONS: TensionProfileOptionMeta[] = [
  {
    id: "auto",
    labelKey: "create.tension_auto_label",
    descKey: "create.tension_auto_desc",
  },
  {
    id: "high_drama",
    labelKey: "create.tension_high_drama_label",
    descKey: "create.tension_high_drama_desc",
  },
  {
    id: "cozy_mystery",
    labelKey: "create.tension_cozy_mystery_label",
    descKey: "create.tension_cozy_mystery_desc",
  },
  {
    id: "comedy",
    labelKey: "create.tension_comedy_label",
    descKey: "create.tension_comedy_desc",
  },
  {
    id: "fantasy_sci_fi",
    labelKey: "create.tension_fantasy_sci_fi_label",
    descKey: "create.tension_fantasy_sci_fi_desc",
  },
  {
    id: "family_social",
    labelKey: "create.tension_family_social_label",
    descKey: "create.tension_family_social_desc",
  },
]

export function briefKey(seed: string, language: NarrativeTemplateLanguage, tensionProfile: TensionProfileChoice): string {
  return `${seed.trim()}\n${language}\n${tensionProfile}`
}

export function makeGuestHandle(): string {
  return `guest_${Math.random().toString(36).slice(2, 8)}`
}

type BudgetOptionMeta = {
  budget: number
  labelKey: StringKey
  timeKey: StringKey
  descKey: StringKey
}

export const BUDGET_OPTIONS: BudgetOptionMeta[] = [
  {
    budget: 8,
    labelKey: "create.budget_short_label",
    timeKey: "create.budget_short_time",
    descKey: "create.budget_short_desc",
  },
  {
    budget: 12,
    labelKey: "create.budget_medium_label",
    timeKey: "create.budget_medium_time",
    descKey: "create.budget_medium_desc",
  },
  {
    budget: 20,
    labelKey: "create.budget_long_label",
    timeKey: "create.budget_long_time",
    descKey: "create.budget_long_desc",
  },
]

type DifficultyOptionMeta = {
  id: NarrativeDifficulty
  labelKey: StringKey
  taglineKey: StringKey
  descKey: StringKey
}

export const DIFFICULTY_OPTIONS: DifficultyOptionMeta[] = [
  {
    id: "story",
    labelKey: "create.difficulty_story_label",
    taglineKey: "create.difficulty_story_tagline",
    descKey: "create.difficulty_story_desc",
  },
  {
    id: "gauntlet",
    labelKey: "create.difficulty_gauntlet_label",
    taglineKey: "create.difficulty_gauntlet_tagline",
    descKey: "create.difficulty_gauntlet_desc",
  },
]

// Story-language options — controls the locale of generated narration
// and NPC dialogue. Immutable per template once created.
export const STORY_LANGUAGE_OPTIONS: Record<Lang, Array<{
  id: NarrativeTemplateLanguage
  label: string
  desc: string
}>> = {
  zh: [
    { id: "zh", label: "中文", desc: "NPC 对白和叙述都用简体中文" },
    { id: "en", label: "英文", desc: "Narration and NPC dialogue in English" },
  ],
  en: [
    { id: "zh", label: "Chinese", desc: "Narration and NPC dialogue in Simplified Chinese" },
    { id: "en", label: "English", desc: "Narration and NPC dialogue in English" },
  ],
}

export const VISIBILITY_KEY_MAP: Record<
  NarrativeTemplateVisibility,
  { labelKey: StringKey; descKey: StringKey }
> = {
  private: {
    labelKey: "create.visibility_private_label",
    descKey: "create.visibility_private_desc",
  },
  unlisted: {
    labelKey: "create.visibility_unlisted_label",
    descKey: "create.visibility_unlisted_desc",
  },
  public: {
    labelKey: "create.visibility_public_label",
    descKey: "create.visibility_public_desc",
  },
}

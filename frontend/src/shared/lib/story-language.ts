import type { StoryLanguage } from "../../api/contracts"
import { normalizeUiLanguage } from "./ui-language"

export function normalizeStoryLanguage(language?: StoryLanguage | string | null): StoryLanguage {
  return language === "zh" ? "zh" : "en"
}

export function formatStoryLanguageLabel(
  language?: StoryLanguage | string | null,
  uiLanguage: StoryLanguage | string = "en",
) {
  const storyLanguage = normalizeStoryLanguage(language)
  return normalizeUiLanguage(uiLanguage) === "zh"
    ? storyLanguage === "zh"
      ? "简体中文"
      : "英文"
    : storyLanguage === "zh"
      ? "Simplified Chinese"
      : "English"
}

export function formatStoryLanguageChip(language?: StoryLanguage | string | null) {
  return normalizeStoryLanguage(language) === "zh" ? "ZH" : "EN"
}

export function formatStoryOutputLabel(
  language?: StoryLanguage | string | null,
  uiLanguage: StoryLanguage | string = "en",
) {
  const storyLanguage = normalizeStoryLanguage(language)
  return normalizeUiLanguage(uiLanguage) === "zh"
    ? storyLanguage === "zh"
      ? "中文输出"
      : "英文输出"
    : storyLanguage === "zh"
      ? "Chinese Output"
      : "English Output"
}

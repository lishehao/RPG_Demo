import type { StoryLanguage } from "../../api/contracts"

export const UI_LANGUAGE_STORAGE_KEY = "rpg-demo.ui-language"

export function normalizeUiLanguage(language?: StoryLanguage | string | null): StoryLanguage {
  return language === "zh" ? "zh" : "en"
}

export function readStoredUiLanguage(): StoryLanguage {
  if (typeof window === "undefined") {
    return "en"
  }
  return normalizeUiLanguage(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY))
}

export function writeStoredUiLanguage(language: StoryLanguage) {
  if (typeof window === "undefined") {
    return
  }
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, normalizeUiLanguage(language))
}

export function uiText(language: StoryLanguage | string | null | undefined, values: { en: string; zh: string }) {
  return normalizeUiLanguage(language) === "zh" ? values.zh : values.en
}

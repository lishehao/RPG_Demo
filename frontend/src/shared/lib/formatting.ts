import type { PublishedStoryCard, StoryLanguage } from "../../index"
import { normalizeUiLanguage } from "./ui-language"

export function formatPublishedAt(value: string, uiLanguage: StoryLanguage | string = "en"): string {
  return new Date(value).toLocaleString(normalizeUiLanguage(uiLanguage) === "zh" ? "zh-CN" : "en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export function progressWidth(currentValue: number, minValue: number, maxValue: number): string {
  const range = Math.max(1, maxValue - minValue)
  const bounded = Math.min(maxValue, Math.max(minValue, currentValue))
  return `${((bounded - minValue) / range) * 100}%`
}

export function sortStoriesByNewest(stories: PublishedStoryCard[]): PublishedStoryCard[] {
  return [...stories].sort((left, right) => {
    return new Date(right.published_at).getTime() - new Date(left.published_at).getTime()
  })
}

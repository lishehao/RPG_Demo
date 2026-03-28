import type { StoryLanguage } from "../../index"
import { normalizeUiLanguage } from "./ui-language"

export function getStudioBrandName(uiLanguage: StoryLanguage | string = "en") {
  return normalizeUiLanguage(uiLanguage) === "zh" ? "叙事会馆" : "Narrative Studio"
}

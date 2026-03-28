import type { StoryLanguage } from "../../index"
import { normalizeUiLanguage } from "./ui-language"

export const AUTH_PASSWORD_MIN_LENGTH = 8
export const AUTH_PASSWORD_MAX_LENGTH = 200

export function isValidAuthPassword(value: string) {
  return value.length >= AUTH_PASSWORD_MIN_LENGTH && value.length <= AUTH_PASSWORD_MAX_LENGTH
}

export function getAuthPasswordRuleText(uiLanguage: StoryLanguage | string = "en") {
  return normalizeUiLanguage(uiLanguage) === "zh"
    ? "密码长度需在 8 到 200 个字符之间。"
    : "Password must be 8 to 200 characters."
}

import type { StoryLanguage } from "../../index"
import { normalizeUiLanguage } from "./ui-language"

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error
      ? error.name === "AbortError"
      : false
}

export function toErrorMessage(error: unknown, uiLanguage: StoryLanguage | string = "en"): string {
  if (error instanceof Error) {
    return error.message
  }

  return normalizeUiLanguage(uiLanguage) === "zh" ? "出了点问题。" : "Something went wrong."
}

export function toErrorCode(error: unknown): string | null {
  if (typeof error === "object" && error && "errorCode" in error) {
    const value = (error as { errorCode?: unknown }).errorCode
    return typeof value === "string" && value.trim() ? value : null
  }
  return null
}

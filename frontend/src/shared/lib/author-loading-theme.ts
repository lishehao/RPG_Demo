const AUTHOR_LOADING_THEME_IMAGE_PATHS: Record<string, string> = {
  logistics_quarantine_crisis: "/theme-loading/logistics_quarantine_crisis.webp",
  truth_record_crisis: "/theme-loading/truth_record_crisis.webp",
  legitimacy_crisis: "/theme-loading/legitimacy_crisis.webp",
  public_order_crisis: "/theme-loading/public_order_crisis.webp",
  generic_civic_crisis: "/theme-loading/generic_civic_crisis.webp",
}

export function getAuthorLoadingThemeImagePath(themeId?: string | null): string | null {
  if (!themeId) {
    return null
  }
  return AUTHOR_LOADING_THEME_IMAGE_PATHS[themeId] ?? null
}

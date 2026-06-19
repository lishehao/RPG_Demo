export function cleanNarrativeDisplayText(text: string): string {
  return text
    .replace(/([.!?])\.+(?=\s|[A-Z])/g, "$1")
    .replace(/([!?])\.(?=\s|[A-Z])/g, "$1")
    .replace(/([.!?])([A-Z][a-z])/g, "$1 $2")
    .replace(/[ \t]{2,}/g, " ")
}

// Parse an option label that may start with an intent tag like "[挑拨] xxx".
// Returns { tag: "挑拨", body: "xxx" } or { tag: null, body: full label }.
// Used so the UI can render the tag as a colored chip + the action body
// as plain text, giving players a visual scan-tag for what the choice
// means before reading the full action.
export function parseOptionLabel(label: string): { tag: string | null; body: string } {
  const m = label.match(/^\s*[\[【]([^\]】]{1,8})[\]】]\s*(.*)$/)
  if (m) {
    return { tag: m[1].trim(), body: (m[2] ?? "").trim() }
  }
  return { tag: null, body: label }
}

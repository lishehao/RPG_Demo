import type { ReactNode } from "react"

export function AppShell({ children }: { children: ReactNode }) {
  return <div className="studio-shell">{children}</div>
}

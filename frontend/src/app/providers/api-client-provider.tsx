import { createContext, type ReactNode, useContext } from "react"
import type { FrontendApiClient } from "../../index"

const ApiClientContext = createContext<FrontendApiClient | null>(null)

export function ApiClientProvider({
  children,
  client,
}: {
  children: ReactNode
  client: FrontendApiClient
}) {
  return <ApiClientContext.Provider value={client}>{children}</ApiClientContext.Provider>
}

export function useApiClient(): FrontendApiClient {
  const client = useContext(ApiClientContext)
  if (!client) {
    throw new Error("Api client is not available.")
  }
  return client
}

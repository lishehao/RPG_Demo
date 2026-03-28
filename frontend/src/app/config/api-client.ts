import { createHttpApiClient, type FrontendApiClient } from "../../index"

let cachedClient: FrontendApiClient | null = null
let cachedSignature = ""

function clientSignature(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ""
  return `http:${baseUrl}`
}

export function getDefaultApiClient(): FrontendApiClient {
  const signature = clientSignature()
  if (cachedClient && cachedSignature === signature) {
    return cachedClient
  }

  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? window.location.origin

  cachedClient = createHttpApiClient(baseUrl)
  cachedSignature = signature
  return cachedClient
}

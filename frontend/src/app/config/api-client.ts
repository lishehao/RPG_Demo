import { createHttpApiClient, createPlaceholderApiClient, type FrontendApiClient } from "../../index"

let cachedClient: FrontendApiClient | null = null
let cachedSignature = ""

function clientSignature(): string {
  const mode = import.meta.env.VITE_API_MODE === "placeholder" ? "placeholder" : "http"
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ""
  return `${mode}:${baseUrl}`
}

export function getDefaultApiClient(): FrontendApiClient {
  const signature = clientSignature()
  if (cachedClient && cachedSignature === signature) {
    return cachedClient
  }

  const mode = import.meta.env.VITE_API_MODE === "placeholder" ? "placeholder" : "http"
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? window.location.origin

  cachedClient = mode === "http" ? createHttpApiClient(baseUrl) : createPlaceholderApiClient()
  cachedSignature = signature
  return cachedClient
}

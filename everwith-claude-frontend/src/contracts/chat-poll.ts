/** Adopter implementation of the reference's `./chat-poll`: collapse identical concurrent reads. */
const flights = new Map<string, Promise<unknown>>()
export function deduplicateChatRead<T>(_request: unknown, key: string, read: () => Promise<T>): Promise<T> {
  const existing = flights.get(key)
  if (existing) return existing as Promise<T>
  const flight = read().finally(() => flights.delete(key))
  flights.set(key, flight)
  return flight
}

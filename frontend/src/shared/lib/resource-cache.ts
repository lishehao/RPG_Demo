type CacheEntry<TValue> = {
  value: TValue
  expiresAt: number
}

export function readCachedValue<TValue>(cache: Map<string, CacheEntry<TValue>>, key: string): TValue | null {
  const entry = cache.get(key)
  if (!entry) {
    return null
  }
  if (entry.expiresAt <= Date.now()) {
    cache.delete(key)
    return null
  }
  return entry.value
}

export function writeCachedValue<TValue>(
  cache: Map<string, CacheEntry<TValue>>,
  key: string,
  value: TValue,
  ttlMs: number,
) {
  cache.set(key, {
    value,
    expiresAt: Date.now() + ttlMs,
  })
}

export function deleteCachedValue(cache: Map<string, unknown>, key: string) {
  cache.delete(key)
}

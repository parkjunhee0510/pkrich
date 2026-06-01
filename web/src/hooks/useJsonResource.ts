import { useEffect, useState } from 'react'

type JsonResourceCacheEntry = {
  data?: unknown
  hasData: boolean
  error: string | null
  promise?: Promise<unknown>
}

const jsonResourceCache = new Map<string, JsonResourceCacheEntry>()

function loadJsonResource<T>(relativePath: string): Promise<T> {
  const cached = jsonResourceCache.get(relativePath)
  if (cached?.promise) {
    return cached.promise as Promise<T>
  }

  const promise = fetch(`${import.meta.env.BASE_URL}${relativePath}`, { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      return response.json() as Promise<T>
    })
    .then((json) => {
      jsonResourceCache.set(relativePath, {
        data: json,
        hasData: true,
        error: null,
      })
      return json
    })
    .catch((err: Error) => {
      const previous = jsonResourceCache.get(relativePath)
      jsonResourceCache.set(relativePath, {
        data: previous?.data,
        hasData: previous?.hasData ?? false,
        error: err.message,
      })
      throw err
    })

  jsonResourceCache.set(relativePath, {
    data: cached?.data,
    hasData: cached?.hasData ?? false,
    error: cached?.error ?? null,
    promise,
  })

  return promise
}

export function useJsonResource<T>(relativePath: string) {
  const cached = jsonResourceCache.get(relativePath)
  const [data, setData] = useState<T | null>(() => (cached?.hasData ? cached.data as T : null))
  const [error, setError] = useState<string | null>(() => (cached?.hasData ? null : cached?.error ?? null))

  useEffect(() => {
    let cancelled = false

    loadJsonResource<T>(relativePath)
      .then((json: T) => {
        if (!cancelled) {
          setData(json)
          setError(null)
        }
      })
      .catch((err: Error) => {
        const latest = jsonResourceCache.get(relativePath)
        if (!cancelled && !latest?.hasData) {
          setError(err.message)
        }
      })

    return () => {
      cancelled = true
    }
  }, [relativePath])

  const loading = data === null && error === null
  return { data, loading, error }
}

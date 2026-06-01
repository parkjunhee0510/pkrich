import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useJsonResource } from './useJsonResource'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function jsonResponse<T>(payload: T) {
  return {
    ok: true,
    json: () => Promise.resolve(payload),
  } as Response
}

describe('useJsonResource', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps cached JSON visible on remount instead of showing a page skeleton again', async () => {
    const path = 'output/data/cached-resource-test.json'
    const payload = { schema_version: 1, value: 'ready' }
    const refresh = createDeferred<Response>()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(payload))
      .mockReturnValueOnce(refresh.promise)

    const first = renderHook(() => useJsonResource<typeof payload>(path))

    await waitFor(() => expect(first.result.current.loading).toBe(false))
    expect(first.result.current.data).toEqual(payload)

    first.unmount()

    const second = renderHook(() => useJsonResource<typeof payload>(path))

    expect(second.result.current.data).toEqual(payload)
    expect(second.result.current.loading).toBe(false)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    await act(async () => {
      refresh.resolve(jsonResponse(payload))
      await refresh.promise
    })
  })
})

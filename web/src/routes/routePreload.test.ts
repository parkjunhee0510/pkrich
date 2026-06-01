import { describe, expect, it, vi } from 'vitest'
import {
  createRouteChunkWarmup,
  createRoutePreloader,
  getRoutePathFromHref,
  resolveRouteChunkId,
  type RouteChunkId,
  type RouteModuleLoaders,
} from './routePreload'

describe('route preloading', () => {
  it.each([
    ['/', 'dashboard'],
    ['/ticker/AAPL', 'tickerDetail'],
    ['/portfolio', 'portfolio'],
    ['/prices', 'priceHistory'],
    ['/signals', 'signals'],
    ['/chat', 'chat'],
    ['/scenario', 'scenario'],
    ['/backtest', 'backtest'],
    ['/admin', 'admin'],
    ['/calendar', 'calendar'],
    ['/sectors', 'sectors'],
    ['/sectors/semiconductors', 'sectorDetail'],
    ['/policy', 'policyImpact'],
    ['/risk-intel', 'riskIntel'],
    ['/api-status', 'apiStatus'],
    ['/missing', 'notFound'],
  ] satisfies Array<[string, RouteChunkId]>)('maps %s to %s', (pathname, chunkId) => {
    expect(resolveRouteChunkId(pathname)).toBe(chunkId)
  })

  it('preloads a route chunk once and reuses the in-flight promise for matching dynamic routes', () => {
    const tickerDetailPromise = Promise.resolve({ default: 'TickerDetail' })
    const loaders = {
      tickerDetail: vi.fn(() => tickerDetailPromise),
    } satisfies Partial<RouteModuleLoaders>
    const preloadRoutePath = createRoutePreloader(loaders)

    const first = preloadRoutePath('/ticker/AAPL')
    const second = preloadRoutePath('/ticker/AMD')

    expect(first).toBe(tickerDetailPromise)
    expect(second).toBe(tickerDetailPromise)
    expect(loaders.tickerDetail).toHaveBeenCalledTimes(1)
  })

  it('returns null when no loader is registered for a route chunk', () => {
    const preloadRoutePath = createRoutePreloader({})

    expect(preloadRoutePath('/portfolio')).toBeNull()
  })

  it('normalizes same-origin hrefs with a basename and ignores external links', () => {
    expect(
      getRoutePathFromHref(
        'https://example.com/pkrich/ticker/AAPL?tab=chart',
        'https://example.com',
        '/pkrich',
      ),
    ).toBe('/ticker/AAPL')
    expect(
      getRoutePathFromHref('https://example.com/portfolio', 'https://example.com', '/'),
    ).toBe('/portfolio')
    expect(
      getRoutePathFromHref('https://other.example.com/portfolio', 'https://example.com', '/'),
    ).toBeNull()
  })

  it('warms route chunks in order after the first idle slot and does not reload warmed chunks', () => {
    const calls: string[] = []
    const loaders = {
      dashboard: vi.fn(() => {
        calls.push('dashboard')
        return Promise.resolve('dashboard')
      }),
      tickerDetail: vi.fn(() => {
        calls.push('tickerDetail')
        return Promise.resolve('tickerDetail')
      }),
      portfolio: vi.fn(() => {
        calls.push('portfolio')
        return Promise.resolve('portfolio')
      }),
    } satisfies Partial<RouteModuleLoaders>
    const scheduledCallbacks: Array<() => void> = []
    const warmRouteChunks = createRouteChunkWarmup(loaders, {
      routeOrder: ['dashboard', 'tickerDetail', 'portfolio'],
      schedule: (callback) => {
        scheduledCallbacks.push(callback)
        return scheduledCallbacks.length
      },
      cancel: vi.fn(),
    })

    warmRouteChunks('/ticker/AAPL')
    expect(calls).toEqual([])

    scheduledCallbacks.shift()?.()
    expect(calls).toEqual(['dashboard'])

    scheduledCallbacks.shift()?.()
    expect(calls).toEqual(['dashboard', 'portfolio'])

    warmRouteChunks('/portfolio')
    scheduledCallbacks.splice(0).forEach((callback) => callback())

    expect(loaders.dashboard).toHaveBeenCalledTimes(1)
    expect(loaders.tickerDetail).not.toHaveBeenCalled()
    expect(loaders.portfolio).toHaveBeenCalledTimes(1)
  })
})

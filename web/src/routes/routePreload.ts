import type { ComponentType } from 'react'

export type RouteChunkId =
  | 'dashboard'
  | 'tickerDetail'
  | 'portfolio'
  | 'priceHistory'
  | 'signals'
  | 'chat'
  | 'scenario'
  | 'backtest'
  | 'admin'
  | 'calendar'
  | 'sectors'
  | 'sectorDetail'
  | 'policyImpact'
  | 'riskIntel'
  | 'apiStatus'
  | 'notFound'

type RouteComponentModule = { default: ComponentType }
type RouteComponentLoader = () => Promise<RouteComponentModule>
export type RouteModuleLoaders = Partial<Record<RouteChunkId, () => Promise<unknown>>>
type ScheduleIdleCallback = (callback: () => void) => number
type CancelIdleCallback = (handle: number) => void

type RouteChunkWarmupOptions = {
  routeOrder?: RouteChunkId[]
  schedule?: ScheduleIdleCallback
  cancel?: CancelIdleCallback
}

const DEFAULT_ROUTE_WARMUP_ORDER: RouteChunkId[] = [
  'dashboard',
  'tickerDetail',
  'portfolio',
  'priceHistory',
  'signals',
  'riskIntel',
  'sectors',
  'sectorDetail',
  'policyImpact',
  'calendar',
  'scenario',
  'backtest',
  'chat',
  'apiStatus',
  'admin',
  'notFound',
]

export const routeModuleLoaders = {
  dashboard: () => import('../pages/Dashboard').then((module) => ({ default: module.Dashboard })),
  tickerDetail: () => import('../pages/TickerDetail').then((module) => ({ default: module.TickerDetail })),
  portfolio: () => import('../pages/Portfolio').then((module) => ({ default: module.Portfolio })),
  priceHistory: () => import('../pages/PriceHistory').then((module) => ({ default: module.PriceHistory })),
  signals: () => import('../pages/Signals').then((module) => ({ default: module.Signals })),
  chat: () => import('../pages/Chat').then((module) => ({ default: module.Chat })),
  scenario: () => import('../pages/Scenario').then((module) => ({ default: module.Scenario })),
  backtest: () => import('../pages/Backtest').then((module) => ({ default: module.Backtest })),
  admin: () => import('../pages/Admin').then((module) => ({ default: module.Admin })),
  calendar: () => import('../pages/Calendar').then((module) => ({ default: module.Calendar })),
  sectors: () => import('../pages/Sectors').then((module) => ({ default: module.Sectors })),
  sectorDetail: () => import('../pages/SectorDetail').then((module) => ({ default: module.SectorDetail })),
  policyImpact: () => import('../pages/PolicyImpact').then((module) => ({ default: module.PolicyImpact })),
  riskIntel: () => import('../pages/RiskIntel').then((module) => ({ default: module.RiskIntel })),
  apiStatus: () => import('../pages/ApiStatus').then((module) => ({ default: module.ApiStatus })),
  notFound: () => import('../pages/NotFound').then((module) => ({ default: module.NotFound })),
} satisfies Record<RouteChunkId, RouteComponentLoader>

const STATIC_ROUTE_CHUNKS: Record<string, RouteChunkId> = {
  '/': 'dashboard',
  '/portfolio': 'portfolio',
  '/prices': 'priceHistory',
  '/signals': 'signals',
  '/chat': 'chat',
  '/scenario': 'scenario',
  '/backtest': 'backtest',
  '/admin': 'admin',
  '/calendar': 'calendar',
  '/sectors': 'sectors',
  '/policy': 'policyImpact',
  '/risk-intel': 'riskIntel',
  '/api-status': 'apiStatus',
}

export function resolveRouteChunkId(pathname: string): RouteChunkId {
  const normalizedPathname = normalizePathname(pathname)

  if (normalizedPathname.startsWith('/ticker/')) {
    return 'tickerDetail'
  }

  if (normalizedPathname.startsWith('/sectors/')) {
    return 'sectorDetail'
  }

  return STATIC_ROUTE_CHUNKS[normalizedPathname] ?? 'notFound'
}

export function createRoutePreloader(loaders: RouteModuleLoaders) {
  const inFlightPreloads = new Map<RouteChunkId, Promise<unknown>>()

  return function preloadRoutePath(pathname: string): Promise<unknown> | null {
    const chunkId = resolveRouteChunkId(pathname)
    const loader = loaders[chunkId]

    if (!loader) {
      return null
    }

    const existingPreload = inFlightPreloads.get(chunkId)
    if (existingPreload) {
      return existingPreload
    }

    try {
      const preload = loader()
      inFlightPreloads.set(chunkId, preload)
      preload.catch(() => {
        inFlightPreloads.delete(chunkId)
      })
      return preload
    } catch (error) {
      inFlightPreloads.delete(chunkId)
      throw error
    }
  }
}

export const preloadRoutePath = createRoutePreloader(routeModuleLoaders)

export function createRouteChunkWarmup(
  loaders: RouteModuleLoaders,
  options: RouteChunkWarmupOptions = {},
) {
  const preloadPath = createRoutePreloader(loaders)
  const routeOrder = options.routeOrder ?? DEFAULT_ROUTE_WARMUP_ORDER
  const schedule = options.schedule ?? scheduleRouteWarmup
  const scheduledHandles = new Set<number>()
  let hasStarted = false

  return function warmRouteChunks(currentPathname = window.location.pathname) {
    if (hasStarted) {
      return
    }

    hasStarted = true
    const currentChunkId = resolveRouteChunkId(currentPathname)
    const warmupQueue = routeOrder.filter((chunkId) => chunkId !== currentChunkId)
    let queueIndex = 0

    const warmNextChunk = () => {
      const chunkId = warmupQueue[queueIndex]
      queueIndex += 1

      if (!chunkId) {
        return
      }

      void preloadPath(routePathForChunk(chunkId))

      if (queueIndex < warmupQueue.length) {
        const handle = schedule(warmNextChunk)
        scheduledHandles.add(handle)
      }
    }

    const handle = schedule(warmNextChunk)
    scheduledHandles.add(handle)
  }
}

export const warmRouteChunksInIdle = createRouteChunkWarmup(routeModuleLoaders)

export function getRoutePathFromHref(
  href: string,
  origin: string,
  basename: string,
): string | null {
  let url: URL

  try {
    url = new URL(href, origin)
  } catch {
    return null
  }

  if (url.origin !== origin) {
    return null
  }

  const normalizedBasename = normalizeBasename(basename)
  let pathname = url.pathname || '/'

  if (normalizedBasename !== '/') {
    if (pathname === normalizedBasename) {
      pathname = '/'
    } else if (pathname.startsWith(`${normalizedBasename}/`)) {
      pathname = pathname.slice(normalizedBasename.length) || '/'
    } else {
      return null
    }
  }

  return normalizePathname(pathname)
}

function normalizeBasename(basename: string): string {
  const normalized = normalizePathname(basename || '/')
  return normalized === '' ? '/' : normalized
}

function normalizePathname(pathname: string): string {
  const [pathnameWithoutSearch] = pathname.split(/[?#]/)
  const withLeadingSlash = pathnameWithoutSearch.startsWith('/')
    ? pathnameWithoutSearch
    : `/${pathnameWithoutSearch}`

  if (withLeadingSlash === '/') {
    return '/'
  }

  return withLeadingSlash.replace(/\/+$/, '')
}

function scheduleRouteWarmup(callback: () => void): number {
  const requestIdleCallback = window.requestIdleCallback
  if (typeof requestIdleCallback === 'function') {
    return requestIdleCallback.call(
      window,
      () => callback(),
      { timeout: 2000 },
    )
  }

  return window.setTimeout(callback, 400)
}

function routePathForChunk(chunkId: RouteChunkId): string {
  switch (chunkId) {
    case 'dashboard':
      return '/'
    case 'tickerDetail':
      return '/ticker/__warmup__'
    case 'portfolio':
      return '/portfolio'
    case 'priceHistory':
      return '/prices'
    case 'signals':
      return '/signals'
    case 'chat':
      return '/chat'
    case 'scenario':
      return '/scenario'
    case 'backtest':
      return '/backtest'
    case 'admin':
      return '/admin'
    case 'calendar':
      return '/calendar'
    case 'sectors':
      return '/sectors'
    case 'sectorDetail':
      return '/sectors/__warmup__'
    case 'policyImpact':
      return '/policy'
    case 'riskIntel':
      return '/risk-intel'
    case 'apiStatus':
      return '/api-status'
    case 'notFound':
      return '/__warmup__'
  }
}

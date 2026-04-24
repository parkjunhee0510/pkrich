import type { DashboardData, DailyEntry, TickerAnalysisData } from '../types'
import type { DashboardRepository } from './DashboardRepository'

const BASE = import.meta.env.BASE_URL
const INDEX_URL = `${BASE}output/data/index.json`
const DASHBOARD_URL = `${BASE}output/data/dashboard.json`
const DASHBOARD_HISTORY_URL = `${BASE}output/data/dashboard_history.json`

interface LatestShard {
  schema_version: number
  date: string
  ticker: string
  payload: TickerAnalysisData
}

interface HistoryShard {
  schema_version: number
  ticker: string
  days: Array<{ date: string } & TickerAnalysisData>
}

interface DashboardIndexPayload {
  schema_version: number
  date: string
  market_overview: DashboardData['days'][number]['market_overview']
  macro_context?: DashboardData['days'][number]['macro_context']
  market_regime?: DashboardData['days'][number]['market_regime']
  pm_view?: DashboardData['days'][number]['pm_view']
  portfolio_summary?: DashboardData['days'][number]['portfolio_summary']
  portfolio_risk?: DashboardData['days'][number]['portfolio_risk']
  signal_stats?: DashboardData['signal_stats']
  weekly_summary?: DashboardData['weekly_summary']
  tickers: TickerAnalysisData[]
}

interface DashboardHistoryPayload {
  schema_version: number
  days: DashboardData['days']
  signal_stats?: DashboardData['signal_stats']
  weekly_summary?: DashboardData['weekly_summary']
}

async function fetchJson<T>(url: string, refreshToken: number): Promise<T | null> {
  try {
    const res = await fetch(`${url}?ts=${refreshToken}`, { cache: 'no-store' })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

export class StaticJsonRepository implements DashboardRepository {
  async loadDashboard(refreshToken: number): Promise<DashboardData> {
    const latestIndex = await this.loadDashboardIndex(refreshToken)
    const history = await this.loadDashboardHistory(refreshToken)

    if (latestIndex) {
      const latestDay: DailyEntry = {
        date: latestIndex.date,
        market_overview: Array.isArray(latestIndex.market_overview) ? latestIndex.market_overview : [],
        macro_context: latestIndex.macro_context ?? null,
        market_regime: latestIndex.market_regime ?? null,
        pm_view: latestIndex.pm_view ?? null,
        portfolio_summary: latestIndex.portfolio_summary ?? null,
        portfolio_risk: latestIndex.portfolio_risk ?? null,
        tickers: Array.isArray(latestIndex.tickers) ? latestIndex.tickers : [],
      }

      const mergedDays = history?.days?.length
        ? [
            ...history.days.filter((day) => day.date !== latestDay.date),
            latestDay,
          ].sort((left, right) => left.date.localeCompare(right.date))
        : [latestDay]

      return {
        schema_version: latestIndex.schema_version,
        days: mergedDays,
        signal_stats: latestIndex.signal_stats ?? history?.signal_stats ?? { recent_signals: [], summary_by_direction: {} },
        weekly_summary: latestIndex.weekly_summary ?? history?.weekly_summary,
      }
    }

    if (history?.days?.length) {
      return {
        schema_version: history.schema_version,
        days: history.days,
        signal_stats: history.signal_stats ?? { recent_signals: [], summary_by_direction: {} },
        weekly_summary: history.weekly_summary,
      }
    }

    throw new Error('Dashboard data unavailable')
  }

  private async loadDashboardIndex(refreshToken: number): Promise<DashboardIndexPayload | null> {
    const latestIndex = await fetchJson<DashboardIndexPayload>(INDEX_URL, refreshToken)
    if (latestIndex) return latestIndex

    const legacyDashboard = await fetchJson<DashboardHistoryPayload & DashboardIndexPayload>(DASHBOARD_URL, refreshToken)
    if (legacyDashboard?.tickers) {
      return legacyDashboard as DashboardIndexPayload
    }

    return null
  }

  private async loadDashboardHistory(refreshToken: number): Promise<DashboardHistoryPayload | null> {
    const history = await fetchJson<DashboardHistoryPayload>(DASHBOARD_HISTORY_URL, refreshToken)
    if (history?.days?.length) {
      return history
    }

    const legacyDashboard = await fetchJson<DashboardHistoryPayload>(DASHBOARD_URL, refreshToken)
    if (legacyDashboard?.days?.length) {
      return legacyDashboard
    }

    return null
  }

  async loadTickerLatest(ticker: string, refreshToken: number): Promise<TickerAnalysisData | null> {
    const normalized = ticker.trim().toUpperCase()
    if (!normalized) return null
    const url = `${BASE}output/data/tickers/${normalized}/latest.json`
    const shard = await fetchJson<LatestShard>(url, refreshToken)
    return shard?.payload ?? null
  }

  async loadTickerHistory(ticker: string, refreshToken: number): Promise<DailyEntry[]> {
    const normalized = ticker.trim().toUpperCase()
    if (!normalized) return []
    const url = `${BASE}output/data/tickers/${normalized}/history.json`
    const shard = await fetchJson<HistoryShard>(url, refreshToken)
    if (!shard?.days) return []
    return shard.days.map((day) => ({
      date: day.date,
      market_overview: [],
      tickers: [day as TickerAnalysisData],
    }))
  }
}

export const staticRepository: DashboardRepository = new StaticJsonRepository()

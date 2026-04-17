import type { DashboardData, DailyEntry, TickerAnalysisData } from '../types'

export interface DashboardRepository {
  loadDashboard(refreshToken: number): Promise<DashboardData>
  loadTickerLatest(ticker: string, refreshToken: number): Promise<TickerAnalysisData | null>
  loadTickerHistory(ticker: string, refreshToken: number): Promise<DailyEntry[]>
}

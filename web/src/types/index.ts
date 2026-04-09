export interface MarketOverviewEntry {
  label: string
  symbol: string
  price: string
  change: string
}

export interface NewsReference {
  title: string
  source: string
  published_at: string
  link: string
}

export interface SecFilingReference {
  tag: string
  title: string
  form_type: string
  published_at: string
  link: string
  source: string
}

export interface UpcomingEvent {
  type: string
  label: string
  date: string
  days_until: string
}

export interface QuarterlyFinancialRow {
  quarter: string
  revenue: string
  operating_income: string
  eps: string
}

export interface NewsTone {
  label: 'bullish' | 'neutral' | 'bearish'
  score: number
}

export interface TickerAnalysisData {
  ticker: string
  name: string
  date: string
  summary: string
  key_news: string[]
  news_references: NewsReference[]
  financial_highlights: string[]
  risks_or_watchpoints: string[]
  signal_or_takeaway: string
  data_snapshot: Record<string, string>
  fundamentals: Record<string, string>
  quarterly_financials: QuarterlyFinancialRow[]
  upcoming_events: UpcomingEvent[]
  news_tone: NewsTone
  period_changes: Record<string, string>
  sec_filing_tags: string[]
  sec_filings: SecFilingReference[]
}

export interface DailyEntry {
  date: string
  market_overview: MarketOverviewEntry[]
  tickers: TickerAnalysisData[]
}

export interface DashboardData {
  days: DailyEntry[]
}

export interface PriceHistoryRow {
  date: string
  ticker: string
  price: string
  daily_change: string
  market_cap: string
  trailing_pe: string
  eps: string
  '52w_high': string
  '52w_low': string
}

export interface TickerTimelineEntry {
  date: string
  price: string
  daily_change: string
  signal_or_takeaway: string
  top_news_summary: string
  top_news_link: string
  news_tone: NewsTone
  upcoming_events: UpcomingEvent[]
}

export type TickerTimelinesData = Record<string, TickerTimelineEntry[]>

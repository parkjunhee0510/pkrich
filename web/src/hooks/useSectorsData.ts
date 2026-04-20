import { useJsonResource } from './useJsonResource'

export interface SectorsPricePoint {
  date: string
  close: number
}

export interface SectorsNewsItem {
  title: string
  source: string
  published_at: string
  link: string
}

export interface SectorsTicker {
  ticker: string
  name: string
  price: string
  currency: string
  change_percent: string
  history: SectorsPricePoint[]
  news: SectorsNewsItem[]
  error: string
}

export interface SectorsBenchmark {
  ticker: string
  name: string
  price: string
  currency: string
  change_percent: string
  history: SectorsPricePoint[]
  error: string
}

export interface SectorsSector {
  id: string
  name: string
  description: string
  tickers: SectorsTicker[]
  benchmark?: SectorsBenchmark
}

export interface SectorsPayload {
  schema_version: number
  updated_at: string
  sectors: SectorsSector[]
}

export function useSectorsData() {
  return useJsonResource<SectorsPayload>('output/data/sectors.json')
}

export type OptionsLiveRecency = 'delayed_15m'

export interface OptionsContract {
  contract: string
  underlying_ticker?: string
  type?: 'call' | 'put' | string
  expiration_date?: string
  strike_price?: number
  label?: string
}

export interface OptionsContractLookupPayload {
  status: string
  ticker: string
  recency: OptionsLiveRecency
  contracts: OptionsContract[]
  message: string
}

export interface OptionsAggregateEvent {
  type: 'aggregate'
  source: 'polygon_options'
  recency: OptionsLiveRecency
  channel: 'A'
  contract: string
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
  accumulated_volume: number
  vwap: number | null
}

export interface OptionsStatusEvent {
  type: 'status'
  status: string
  recency: OptionsLiveRecency
  message: string
}

export type OptionsLiveEvent = OptionsAggregateEvent | OptionsStatusEvent

import { useMemo } from 'react'
import { useOptionsLive } from '../hooks/useOptionsLive'
import { OptionAggregateChart } from './OptionAggregateChart'

const STATUS_LABELS: Record<string, string> = {
  idle: 'READY',
  loading: 'LOADING',
  connecting: 'CONNECTING',
  connected: 'CONNECTED',
  missing_credentials: 'NO KEY',
  provider_auth_failed: 'AUTH FAILED',
  provider_no_access: 'NO ACCESS',
  invalid_contract: 'INVALID',
  provider_disconnected: 'DISCONNECTED',
  rate_limited: 'RATE LIMITED',
  error: 'ERROR',
}

interface OptionsLivePanelProps {
  ticker: string
  underlyingPrice?: number | null
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  return typeof value === 'number' ? value.toFixed(digits) : 'N/A'
}

function emptyStateCopy(status: string, selectedContract: string, message: string) {
  if (status === 'missing_credentials') {
    return {
      title: 'API key required',
      body: 'Set POLYGON_API_KEY or MASSIVE_API_KEY on the API server, then restart it.',
    }
  }
  if (status === 'provider_no_access' || status === 'provider_auth_failed') {
    return {
      title: 'Provider access check needed',
      body: message || 'The selected key could not access the delayed options aggregate stream.',
    }
  }
  if (status === 'invalid_contract') {
    return {
      title: 'Invalid option contract',
      body: 'Paste one explicit Polygon option contract such as O:AAPL260116C00200000.',
    }
  }
  if (!selectedContract) {
    return {
      title: 'No option contract selected',
      body: message || 'Load contracts from the API or paste one explicit option contract.',
    }
  }
  if (status === 'connecting' || status === 'connected') {
    return {
      title: 'Waiting for the first aggregate',
      body: 'Options second aggregates update only when the selected contract trades.',
    }
  }
  return {
    title: 'No option aggregate yet',
    body: message || 'The stream is open, but no second aggregate has arrived for this contract.',
  }
}

export function OptionsLivePanel({ ticker, underlyingPrice }: OptionsLivePanelProps) {
  const state = useOptionsLive(ticker, { enabled: Boolean(ticker), underlyingPrice })
  const latest = state.latest
  const emptyState = emptyStateCopy(state.status, state.selectedContract, state.message)
  const diagnostics = useMemo(
    () => [
      ['Last', formatNumber(latest?.close)],
      ['Open', formatNumber(latest?.open)],
      ['High', formatNumber(latest?.high)],
      ['Low', formatNumber(latest?.low)],
      ['VWAP', formatNumber(latest?.vwap)],
      ['Volume', latest ? String(latest.volume) : 'N/A'],
    ],
    [latest],
  )

  return (
    <section className="options-live-panel ticker-detail-section-shell" aria-label={`${ticker} 옵션 계약 패널`}>
      <div className="options-live-header">
        <div>
          <h3>옵션 계약</h3>
          <span className="section-kicker">Options Starter aggregate stream</span>
        </div>
        <div className="options-live-status-row">
          <span className="period-badge">DELAYED 15m</span>
          <span className={`options-live-status options-live-status-${state.status}`}>
            {STATUS_LABELS[state.status] ?? state.status.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="options-live-controls">
        <select
          aria-label="옵션 계약 선택"
          value={state.selectedContract}
          onChange={(event) => state.setSelectedContract(event.target.value)}
        >
          <option value="">계약 선택</option>
          {state.contracts.map((contract) => (
            <option key={contract.contract} value={contract.contract}>
              {contract.label ?? contract.contract}
            </option>
          ))}
        </select>
        <input
          aria-label="옵션 계약 직접 입력"
          value={state.manualContract}
          onChange={(event) => state.setManualContract(event.target.value)}
          placeholder="O:AAPL260116C00200000"
        />
        <button type="button" className="secondary-action-button" onClick={state.selectManualContract}>
          적용
        </button>
      </div>

      {latest ? (
        <div className="options-live-diagnostics">
          {diagnostics.map(([label, value]) => (
            <div key={label} className="price-action-card">
              <span className="price-action-label">{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      ) : (
        <div className="options-live-empty" role="status">
          <strong>{emptyState.title}</strong>
          <span>{emptyState.body}</span>
        </div>
      )}

      <OptionAggregateChart rows={state.rows} contract={state.selectedContract || `${ticker} option`} />
    </section>
  )
}

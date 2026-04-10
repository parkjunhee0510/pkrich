import { useEffect, useState } from 'react'
import { useDashboardData } from '../hooks/useDashboardData'

export function Scenario() {
  const { data, loading, error } = useDashboardData()
  const [targetTicker, setTargetTicker] = useState('')
  const [adjustmentPct, setAdjustmentPct] = useState(5)

  useEffect(() => {
    document.title = '시나리오 분석 · Stock Research'
  }, [])

  const latestDay = data?.days?.[data.days.length - 1]
  const positions = latestDay?.portfolio_risk?.positions_by_weight ?? []
  const tickers = Array.from(new Set(positions.map((position) => position.ticker)))
  const selectedPosition = positions.find((position) => position.ticker === targetTicker)
  const scenarioSummary = !selectedPosition || !latestDay?.portfolio_risk
    ? null
    : (() => {
        const currentWeight = selectedPosition.weight_pct
        const nextWeight = Math.max(0, currentWeight + adjustmentPct)
        const currentRisk = selectedPosition.atr_risk_usd
        const multiplier = currentWeight > 0 ? nextWeight / currentWeight : 1
        const nextRisk = currentRisk * multiplier
        const totalRisk = latestDay.portfolio_risk.total_atr_risk_usd ?? 0
        return {
          currentWeight: currentWeight.toFixed(1),
          nextWeight: nextWeight.toFixed(1),
          currentRisk: currentRisk.toFixed(2),
          nextRisk: nextRisk.toFixed(2),
          totalRisk: totalRisk.toFixed(2),
          totalRiskDelta: (nextRisk - currentRisk).toFixed(2),
        }
      })()

  if (loading) return <p className="status">Loading scenario...</p>
  if (error) return <p className="status error">{error}</p>
  if (!latestDay?.portfolio_risk) return <p className="status">포트폴리오 리스크 데이터가 없습니다.</p>

  return (
    <div className="portfolio-page">
      <div className="dashboard-header">
        <h2>시나리오 분석</h2>
      </div>

      <div className="portfolio-editor-toolbar">
        <div>
          <strong>가정 변경</strong>
          <p>특정 종목 비중을 가정으로 조정해 ATR 리스크와 집중도 변화를 빠르게 확인합니다.</p>
        </div>
      </div>

      <div className="dashboard-controls" style={{ marginTop: '1rem' }}>
        <select className="dashboard-filter" value={targetTicker} onChange={(event) => setTargetTicker(event.target.value)}>
          <option value="">종목 선택</option>
          {tickers.map((ticker) => (
            <option key={ticker} value={ticker}>{ticker}</option>
          ))}
        </select>
        <label className="account-size-control">
          <span>비중 조정 (%p)</span>
          <input type="number" step={1} value={adjustmentPct} onChange={(event) => setAdjustmentPct(Number(event.target.value) || 0)} />
        </label>
      </div>

      {scenarioSummary ? (
        <div className="portfolio-summary-grid">
          <ScenarioCard label="현재 비중" value={`${scenarioSummary.currentWeight}%`} />
          <ScenarioCard label="가정 후 비중" value={`${scenarioSummary.nextWeight}%`} />
          <ScenarioCard label="현재 ATR 리스크" value={`$${scenarioSummary.currentRisk}`} />
          <ScenarioCard label="가정 후 ATR 리스크" value={`$${scenarioSummary.nextRisk}`} sub={`변화 ${Number(scenarioSummary.totalRiskDelta) >= 0 ? '+' : ''}$${scenarioSummary.totalRiskDelta}`} />
        </div>
      ) : (
        <p className="status">종목을 선택하면 시나리오 요약이 계산됩니다.</p>
      )}
    </div>
  )
}

function ScenarioCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="portfolio-summary-card">
      <div className="portfolio-card-label">{label}</div>
      <div className="portfolio-card-value">{value}</div>
      {sub ? <div className="portfolio-card-sub">{sub}</div> : null}
    </div>
  )
}

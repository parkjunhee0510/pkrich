import { useEffect, useMemo, useState } from 'react'
import { useDashboardData } from '../hooks/useDashboardData'
import { TablePageSkeleton } from '../components/Skeleton'
import { ErrorState } from '../components/ErrorState'

type AdjustmentMap = Record<string, number>

export function Scenario() {
  const { data, loading, error } = useDashboardData()
  const [adjustments, setAdjustments] = useState<AdjustmentMap>({})

  useEffect(() => {
    document.title = '시나리오 분석 · Stock Research'
  }, [])

  const latestDay = data?.days?.[data.days.length - 1]
  const risk = latestDay?.portfolio_risk
  const positions = useMemo(() => risk?.positions_by_weight ?? [], [risk?.positions_by_weight])
  const correlationPairs = useMemo(() => risk?.correlation_pairs ?? [], [risk?.correlation_pairs])

  const scenario = useMemo(() => buildScenarioSummary(positions, correlationPairs, adjustments), [positions, correlationPairs, adjustments])

  if (loading) return <TablePageSkeleton title="시나리오 분석" />
  if (error) return <ErrorState message={error} />
  if (!risk) return <p className="status">포트폴리오 리스크 데이터가 없습니다.</p>

  return (
    <div className="portfolio-page">
      <div className="dashboard-header">
        <h1>시나리오 분석</h1>
      </div>

      <div className="portfolio-editor-toolbar">
        <div>
          <strong>멀티 종목 비중 조정</strong>
          <p>여러 종목의 가정 비중을 함께 바꾸고 총 ATR 리스크, 섹터 노출, 집중도 변화를 비교합니다.</p>
        </div>
      </div>

      <div className="watchlist-table-shell u-mt-4">
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>티커</th>
              <th>현재 비중</th>
              <th>현재 ATR 리스크</th>
              <th>조정 (%p)</th>
              <th>가정 후 비중</th>
              <th>가정 후 ATR 리스크</th>
            </tr>
          </thead>
          <tbody>
            {scenario.positions.map((position) => (
              <tr key={position.ticker}>
                <td>{position.ticker}</td>
                <td>{position.currentWeight.toFixed(1)}%</td>
                <td>${position.currentRisk.toFixed(2)}</td>
                <td>
                  <input
                    className="scenario-adjustment-input"
                    type="number"
                    step={1}
                    aria-label={`${position.ticker} 목표 비중 조정`}
                    value={adjustments[position.ticker] || ''}
                    placeholder="0"
                    onChange={(event) =>
                      setAdjustments((current) => ({
                        ...current,
                        [position.ticker]: event.target.value === '' ? 0 : Number(event.target.value),
                      }))
                    }
                  />
                </td>
                <td>{position.nextWeight.toFixed(1)}%</td>
                <td>${position.nextRisk.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="portfolio-summary-grid u-mt-4">
        <ScenarioCard label="총 ATR 리스크" value={`$${scenario.totalRisk.toFixed(2)}`} sub={`기존 $${scenario.currentTotalRisk.toFixed(2)}`} />
        <ScenarioCard
          label="리스크 변화"
          value={`${scenario.totalRiskDelta >= 0 ? '+' : ''}$${scenario.totalRiskDelta.toFixed(2)}`}
          sub={`${scenario.totalRiskDeltaPct >= 0 ? '+' : ''}${scenario.totalRiskDeltaPct.toFixed(1)}%`}
        />
        <ScenarioCard label="최대 비중" value={`${scenario.maxWeight.toFixed(1)}%`} sub={scenario.maxTicker ? `${scenario.maxTicker} 기준` : 'N/A'} />
        <ScenarioCard label="상위 3종목 비중" value={`${scenario.top3Weight.toFixed(1)}%`} sub="집중도 체크" />
      </div>

      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>섹터 노출 변화</h3>
            <p className="section-kicker">현재 대비 가정 후 비중</p>
          </div>
        </div>
        <div className="signal-summary-grid">
          {Object.entries(scenario.sectorExposure).map(([sector, exposure]) => (
            <SummaryMetricCard
              key={sector}
              label={sector}
              value={`${exposure.next.toFixed(1)}%`}
              note={`현재 ${exposure.current.toFixed(1)}%`}
            />
          ))}
        </div>
      </section>

      {scenario.correlationWarnings.length > 0 ? (
        <section className="ticker-detail-section-shell">
          <h3>상관관계 경고</h3>
          <div className="detail-note-card">
            <ul className="news-list">
              {scenario.correlationWarnings.map((warning) => (
                <li key={warning} className="news-item">
                  {warning}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  )
}

function buildScenarioSummary(
  positions: Array<{ ticker: string; weight_pct: number; atr_risk_usd: number; sector?: string }>,
  correlationPairs: Array<{ ticker_1: string; ticker_2: string; warning: string }>,
  adjustments: AdjustmentMap,
) {
  const scenarioPositions = positions.map((position) => {
    const adjustment = adjustments[position.ticker] ?? 0
    const nextWeight = Math.max(0, position.weight_pct + adjustment)
    const multiplier = position.weight_pct > 0 ? nextWeight / position.weight_pct : 1
    const nextRisk = position.atr_risk_usd * multiplier
    return {
      ticker: position.ticker,
      sector: position.sector ?? 'Unknown',
      currentWeight: position.weight_pct,
      nextWeight,
      currentRisk: position.atr_risk_usd,
      nextRisk,
      adjustment,
    }
  })

  const currentTotalRisk = scenarioPositions.reduce((sum, position) => sum + position.currentRisk, 0)
  const totalRisk = scenarioPositions.reduce((sum, position) => sum + position.nextRisk, 0)
  const totalRiskDelta = totalRisk - currentTotalRisk
  const totalRiskDeltaPct = currentTotalRisk > 0 ? (totalRiskDelta / currentTotalRisk) * 100 : 0
  const sortedByWeight = [...scenarioPositions].sort((left, right) => right.nextWeight - left.nextWeight)
  const maxPosition = sortedByWeight[0]

  const sectorExposure = scenarioPositions.reduce<Record<string, { current: number; next: number }>>((acc, position) => {
    const current = acc[position.sector] ?? { current: 0, next: 0 }
    current.current += position.currentWeight
    current.next += position.nextWeight
    acc[position.sector] = current
    return acc
  }, {})

  const positivelyAdjusted = new Set(
    scenarioPositions.filter((position) => position.adjustment > 0).map((position) => position.ticker),
  )
  const correlationWarnings = correlationPairs
    .filter((pair) => positivelyAdjusted.has(pair.ticker_1) && positivelyAdjusted.has(pair.ticker_2))
    .map((pair) => `${pair.ticker_1}/${pair.ticker_2}: ${pair.warning}`)

  return {
    positions: scenarioPositions,
    currentTotalRisk,
    totalRisk,
    totalRiskDelta,
    totalRiskDeltaPct,
    maxWeight: maxPosition?.nextWeight ?? 0,
    maxTicker: maxPosition?.ticker ?? '',
    top3Weight: sortedByWeight.slice(0, 3).reduce((sum, position) => sum + position.nextWeight, 0),
    sectorExposure,
    correlationWarnings,
  }
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

function SummaryMetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="signal-summary-card">
      <div className="signal-summary-direction">{label}</div>
      <div className="signal-summary-count">{value}</div>
      <div className="signal-summary-row">
        <span className="signal-summary-label">메모</span>
        <span>{note}</span>
      </div>
    </div>
  )
}

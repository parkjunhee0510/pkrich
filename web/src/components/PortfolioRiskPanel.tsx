import type { PortfolioRisk } from '../types'

function formatMoney(value?: number): string {
  if (value == null) return 'N/A'
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function PortfolioRiskPanel({ risk }: { risk?: PortfolioRisk | null }) {
  if (!risk) {
    return null
  }

  const topPositions = (risk.positions_by_weight ?? []).slice(0, 5)
  const sectorExposure = Object.entries(risk.sector_exposure ?? {}).sort(([, left], [, right]) => right - left)

  return (
    <section className="portfolio-risk-panel">
      <div className="section-header-with-kicker">
        <div>
          <h3>포트폴리오 리스크</h3>
          <p className="section-kicker">집중도, 2ATR 기준 손실 범위, 포지션별 위험 기여를 함께 봅니다.</p>
        </div>
      </div>

      <div className="portfolio-risk-summary-grid">
        <RiskSummaryCard label="총 ATR 리스크" value={formatMoney(risk.total_atr_risk_usd)} />
        <RiskSummaryCard label="2ATR 최대 낙폭" value={formatMoney(risk.max_drawdown_2atr_usd)} sub={risk.max_drawdown_2atr_pct} />
        <RiskSummaryCard label="총 평가금액" value={formatMoney(risk.total_market_value)} />
      </div>

      {risk.concentration_warning ? <p className="portfolio-risk-warning">{risk.concentration_warning}</p> : null}

      {(risk.sector_concentration_alerts ?? []).length > 0 && (
        <div className="portfolio-risk-alerts">
          {risk.sector_concentration_alerts!.map((alert, i) => (
            <p key={i} className="portfolio-risk-warning">{alert}</p>
          ))}
        </div>
      )}

      {(risk.correlation_pairs ?? []).length > 0 && (
        <div className="portfolio-risk-card" style={{ marginBottom: '1rem' }}>
          <span className="price-action-label">High Correlation Pairs</span>
          <div className="portfolio-risk-list">
            {risk.correlation_pairs!.map((pair) => (
              <div key={`${pair.ticker_1}-${pair.ticker_2}`} className="portfolio-risk-row">
                <div>
                  <strong>{pair.ticker_1} / {pair.ticker_2}</strong>
                  <small>{pair.warning}</small>
                </div>
                <div className="portfolio-risk-values">
                  <span className="correlation-badge">{pair.correlation}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="portfolio-risk-grid">
        <div className="portfolio-risk-card">
          <span className="price-action-label">Top Risk Contributors</span>
          {topPositions.length > 0 ? (
            <div className="portfolio-risk-list">
              {topPositions.map((position) => (
                <div key={`${position.ticker}-${position.market_value}`} className="portfolio-risk-row">
                  <div>
                    <strong>{position.ticker}</strong>
                    <small>{position.sector ?? 'Sector N/A'}</small>
                  </div>
                  <div className="portfolio-risk-values">
                    <span>{position.weight_pct.toFixed(1)}%</span>
                    <small>{formatMoney(position.atr_risk_usd)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty">리스크 기여 데이터가 없습니다.</p>
          )}
        </div>

        <div className="portfolio-risk-card">
          <span className="price-action-label">Sector Exposure</span>
          {sectorExposure.length > 0 ? (
            <div className="portfolio-sector-list">
              {sectorExposure.map(([sector, weight]) => (
                <div key={sector} className="portfolio-sector-row">
                  <div className="portfolio-sector-head">
                    <strong>{sector}</strong>
                    <span>{weight.toFixed(1)}%</span>
                  </div>
                  <div className="portfolio-sector-bar">
                    <div className="portfolio-sector-bar-fill" style={{ width: `${Math.min(weight, 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty">섹터 노출 데이터가 없습니다.</p>
          )}
        </div>
      </div>
    </section>
  )
}

function RiskSummaryCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="portfolio-summary-card portfolio-risk-summary-card">
      <div className="portfolio-card-label">{label}</div>
      <div className="portfolio-card-value">{value}</div>
      {sub ? <div className="portfolio-card-sub">{sub}</div> : null}
    </div>
  )
}

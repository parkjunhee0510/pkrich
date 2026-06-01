import type { PortfolioRisk } from '../types'

function formatMoney(value?: number): string {
  if (value == null) return 'N/A'
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPct(value?: number | null): string {
  if (value == null) return 'N/A'
  return `${value.toFixed(2)}%`
}

function formatGradeLabel(grade?: string): string {
  if (!grade) return '리스크 보통'
  const labels: Record<string, string> = {
    A: 'A · 안정',
    B: 'B · 보통',
    C: 'C · 집중',
    D: 'D · 위험',
  }
  return labels[grade] ?? grade
}

function riskToneClass(grade?: string): string {
  switch (grade) {
    case 'A':
      return 'risk-grade-a'
    case 'C':
      return 'risk-grade-c'
    case 'D':
      return 'risk-grade-d'
    default:
      return 'risk-grade-b'
  }
}

function hhiStatus(hhi?: number): string {
  if (hhi == null) return '데이터 부족'
  if (hhi >= 2500) return '집중 위험'
  if (hhi >= 1800) return '집중 경계'
  if (hhi <= 1000) return '분산 양호'
  return '보통'
}

function gaugeWidth(hhi?: number): number {
  if (hhi == null) return 0
  return Math.max(0, Math.min(100, hhi / 35))
}

function correlationShade(value: number | null | undefined): string {
  if (value == null) return 'var(--bone)'
  const alpha = Math.min(0.9, Math.max(0.12, Math.abs(value)))
  if (value >= 0) return `color-mix(in srgb, var(--hazard) ${Math.round(alpha * 100)}%, var(--paper))`
  return `color-mix(in srgb, var(--info-block) ${Math.round(alpha * 100)}%, var(--paper))`
}

function buildDrawdownPath(points: Array<{ date: string; drawdown_pct: number }>): string {
  if (points.length < 2) return ''
  const width = 220
  const height = 58
  const maxMagnitude = Math.max(...points.map((point) => Math.abs(point.drawdown_pct)), 1)
  return points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width
      const normalized = Math.abs(point.drawdown_pct) / maxMagnitude
      const y = 6 + normalized * (height - 12)
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

export function PortfolioRiskPanel({ risk }: { risk?: PortfolioRisk | null }) {
  if (!risk) {
    return null
  }

  const topPositions = (risk.positions_by_weight ?? []).slice(0, 5)
  const sectorExposure = Object.entries(risk.sector_exposure ?? {}).sort(([, left], [, right]) => right - left)
  const matrix = risk.correlation_matrix ?? {}
  const tickers = Object.keys(matrix)
  const drawdownSeries = risk.mdd_20d_series ?? []
  const drawdownPath = buildDrawdownPath(drawdownSeries)

  return (
    <section className="portfolio-risk-panel">
      <div className="section-header-with-kicker">
        <div>
          <h3>Portfolio Risk</h3>
          <p className="section-kicker">집중도, 상관관계, 변동성 기준으로 현재 포트폴리오의 리스크 구조를 보여줍니다.</p>
        </div>
      </div>

      <div className="portfolio-risk-summary-grid">
        <RiskSummaryCard label="리스크 등급" value={formatGradeLabel(risk.risk_grade)} className={riskToneClass(risk.risk_grade)} />
        <RiskSummaryCard label="HHI 집중도" value={risk.hhi != null ? risk.hhi.toFixed(0) : 'N/A'} sub={hhiStatus(risk.hhi)} />
        <RiskSummaryCard label="Portfolio Beta" value={risk.portfolio_beta != null ? risk.portfolio_beta.toFixed(2) : 'N/A'} />
        <RiskSummaryCard label="1일 VaR 95%" value={formatPct(risk.var_95)} sub="예상 최대 손실" />
      </div>

      {risk.concentration_warning ? <p className="portfolio-risk-warning">{risk.concentration_warning}</p> : null}

      {(risk.sector_concentration_alerts ?? []).length > 0 && (
        <div className="portfolio-risk-alerts">
          {risk.sector_concentration_alerts!.map((alert, index) => (
            <p key={index} className="portfolio-risk-warning">{alert}</p>
          ))}
        </div>
      )}

      <div className="portfolio-risk-grid">
        <div className="portfolio-risk-card">
          <span className="price-action-label">HHI Gauge</span>
          <div className="portfolio-risk-gauge">
            <div className="portfolio-risk-gauge-bar">
              <div className="portfolio-risk-gauge-fill" style={{ width: `${gaugeWidth(risk.hhi)}%` }} />
            </div>
            <div className="portfolio-risk-gauge-scale">
              <span>0</span>
              <span>1000</span>
              <span>2500+</span>
            </div>
          </div>
          <p className="portfolio-risk-note">현재 상태: {hhiStatus(risk.hhi)}</p>
        </div>

        <div className="portfolio-risk-card">
          <span className="price-action-label">MDD 20D</span>
          <div className="portfolio-risk-chart">
            {drawdownPath ? (
              <svg viewBox="0 0 220 58" className="portfolio-risk-sparkline" role="img" aria-label="20일 최대 낙폭 차트">
                <path d={drawdownPath} fill="none" stroke="var(--hazard)" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
              </svg>
            ) : (
              <p className="empty">차트를 그릴 과거 데이터가 아직 부족합니다.</p>
            )}
          </div>
          <p className="portfolio-risk-note">최근 20거래일 최대 낙폭: {formatPct(risk.mdd_20d)}</p>
        </div>
      </div>

      {(risk.correlation_pairs ?? []).length > 0 && (
        <div className="portfolio-risk-card u-mb-4">
          <span className="price-action-label">고상관 종목 쌍</span>
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

      <div className="portfolio-risk-grid">
        <div className="portfolio-risk-card">
          <span className="price-action-label">상관관계 히트맵</span>
          {tickers.length > 1 ? (
            <div className="portfolio-correlation-grid">
              <div className="portfolio-correlation-row header">
                <span />
                {tickers.map((ticker) => (
                  <span key={`head-${ticker}`}>{ticker}</span>
                ))}
              </div>
              {tickers.map((left) => (
                <div key={left} className="portfolio-correlation-row">
                  <span className="portfolio-correlation-label">{left}</span>
                  {tickers.map((right) => {
                    const value = matrix[left]?.[right]
                    return (
                      <span
                        key={`${left}-${right}`}
                        className="portfolio-correlation-cell"
                        style={{ background: correlationShade(value) }}
                      >
                        {value == null ? 'N/A' : value.toFixed(2)}
                      </span>
                    )
                  })}
                </div>
              ))}
            </div>
          ) : (
            <p className="empty">히트맵을 만들기 위한 종목 수나 가격 이력이 아직 부족합니다.</p>
          )}
        </div>

        <div className="portfolio-risk-card">
          <span className="price-action-label">리스크 완화 제안</span>
          {(risk.recommendations ?? []).length > 0 ? (
            <ul className="portfolio-risk-recommendations">
              {risk.recommendations!.map((item, index) => (
                <li key={`${index}-${item}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="empty">표시할 리스크 완화 제안이 없습니다.</p>
          )}
        </div>
      </div>
    </section>
  )
}

function RiskSummaryCard({ label, value, sub, className = '' }: { label: string; value: string; sub?: string; className?: string }) {
  return (
    <div className={`portfolio-summary-card portfolio-risk-summary-card ${className}`.trim()}>
      <div className="portfolio-card-label">{label}</div>
      <div className="portfolio-card-value">{value}</div>
      {sub ? <div className="portfolio-card-sub">{sub}</div> : null}
    </div>
  )
}

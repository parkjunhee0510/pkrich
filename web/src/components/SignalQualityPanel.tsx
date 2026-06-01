import { useEffect, useState } from 'react'

const SIGNAL_QUALITY_URL = `${import.meta.env.BASE_URL}output/data/signal_quality.json`

type ICDecayFactor = {
  factor: string
  ic: { '1d'?: number | null; '5d'?: number | null; '20d'?: number | null }
  n: { '1d'?: number; '5d'?: number; '20d'?: number }
  monotonic_decay: boolean
}

type ICDecayPayload = {
  status: string
  sample_sizes: { '1d'?: number; '5d'?: number; '20d'?: number }
  factors: ICDecayFactor[]
}

type RollingICPoint = { window_end: string; ic: number; n: number }

type RollingICFactor = {
  factor: string
  series: RollingICPoint[]
  latest_ic: number
  lifetime_avg_ic: number
  fatigue: boolean
}

type RollingICPayload = {
  status: string
  sample_size?: number
  horizon?: number
  window_days?: number
  step_days?: number
  factors: RollingICFactor[]
}

type KellyDirection = {
  status: string
  n: number
  hit_rate?: number
  avg_win?: number
  avg_loss?: number
  payoff_ratio?: number | null
  kelly_full?: number
  kelly_half?: number
}

type KellyPayload = {
  status: string
  horizon: number
  haircut: number
  by_direction: Record<string, KellyDirection>
}

type TurnoverPoint = { date: string; tickers: number; turnover: number }

type TurnoverPayload = {
  status: string
  sample_size: number
  avg_turnover?: number
  points: TurnoverPoint[]
}

type SignalQualityPayload = {
  schema_version?: number
  error?: string
  ic_decay?: ICDecayPayload
  rolling_ic?: RollingICPayload
  kelly?: KellyPayload
  turnover?: TurnoverPayload
}

export function SignalQualityPanel() {
  const [payload, setPayload] = useState<SignalQualityPayload | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const response = await fetch(SIGNAL_QUALITY_URL, { cache: 'no-store' })
        if (!response.ok) return
        const json: SignalQualityPayload = await response.json()
        if (!cancelled) setPayload(json)
      } catch {
        // optional — silent
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  if (!payload) return null
  if (payload.error) {
    return (
      <section className="ticker-detail-section-shell">
        <div className="section-header-with-kicker">
          <div>
            <h3>시그널 품질 (Phase A)</h3>
            <p className="section-kicker">signal_quality.json 로드 실패: {payload.error}</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="ticker-detail-section-shell">
      <div className="section-header-with-kicker">
        <div>
          <h3>시그널 품질 (IC / Kelly / Turnover)</h3>
          <p className="section-kicker">
            팩터별 IC 지평선 감쇠 + 90일 롤링 IC · 방향별 half-Kelly · 시그널 세트 day-over-day 변화율
          </p>
        </div>
      </div>

      <ICDecayTable payload={payload.ic_decay} />
      <RollingICTable payload={payload.rolling_ic} />
      <KellyCards payload={payload.kelly} />
      <TurnoverSummary payload={payload.turnover} />
    </section>
  )
}

function ICDecayTable({ payload }: { payload?: ICDecayPayload }) {
  if (!payload || payload.status !== 'ok' || payload.factors.length === 0) {
    return (
      <>
        <h4 className="u-mt-3">IC 감쇠 (1D → 5D → 20D)</h4>
        <p className="empty">
          평가된 시그널이 부족합니다 (1D={payload?.sample_sizes?.['1d'] ?? 0} /
          5D={payload?.sample_sizes?.['5d'] ?? 0} /
          20D={payload?.sample_sizes?.['20d'] ?? 0}).
        </p>
      </>
    )
  }

  return (
    <>
      <h4 className="u-mt-3">IC 감쇠 (Spearman ρ, 지평선별)</h4>
      <div className="watchlist-table-shell">
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>IC 1D</th>
              <th>IC 5D</th>
              <th>IC 20D</th>
              <th>N (5D)</th>
              <th>단조 감쇠</th>
            </tr>
          </thead>
          <tbody>
            {payload.factors.map((row) => (
              <tr key={row.factor}>
                <td>{row.factor}</td>
                <td>{formatIC(row.ic['1d'])}</td>
                <td>{formatIC(row.ic['5d'])}</td>
                <td>{formatIC(row.ic['20d'])}</td>
                <td>{row.n['5d'] ?? 0}</td>
                <td>
                  {row.monotonic_decay ? (
                    <span className="status">OK</span>
                  ) : (
                    <span className="status" style={{ background: '#c98a2e' }}>flat/inverted</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="section-kicker u-mt-2">
        건강한 팩터는 |IC_1D| ≥ |IC_5D| ≥ |IC_20D|. flat/inverted는 레짐 변화 또는 누수 의심.
      </p>
    </>
  )
}

function RollingICTable({ payload }: { payload?: RollingICPayload }) {
  if (!payload || payload.status !== 'ok' || payload.factors.length === 0) {
    return (
      <>
        <h4 className="u-mt-4">롤링 IC (90일 윈도우)</h4>
        <p className="empty">
          롤링 IC 계산에 필요한 데이터가 부족합니다 (N={payload?.sample_size ?? 0}).
        </p>
      </>
    )
  }
  return (
    <>
      <h4 className="u-mt-4">
        롤링 IC ({payload.window_days ?? 90}일 / {payload.step_days ?? 15}일 스텝)
      </h4>
      <div className="watchlist-table-shell">
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>최신 IC</th>
              <th>누적 평균 IC</th>
              <th>시리즈 길이</th>
              <th>상태</th>
              <th>트렌드</th>
            </tr>
          </thead>
          <tbody>
            {payload.factors.map((row) => (
              <tr key={row.factor}>
                <td>{row.factor}</td>
                <td>{formatIC(row.latest_ic)}</td>
                <td>{formatIC(row.lifetime_avg_ic)}</td>
                <td>{row.series.length}</td>
                <td>
                  {row.fatigue ? (
                    <span className="status" style={{ background: '#d98a7b' }}>fatigue</span>
                  ) : (
                    <span className="status">ok</span>
                  )}
                </td>
                <td style={{ minWidth: 120 }}>
                  <RollingSparkline series={row.series} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function RollingSparkline({ series }: { series: RollingICPoint[] }) {
  if (series.length < 2) return <span>—</span>
  const values = series.map((p) => p.ic)
  const min = Math.min(...values, -0.1)
  const max = Math.max(...values, 0.1)
  const range = max - min || 1
  const w = 100
  const h = 28
  const points = series
    .map((p, i) => {
      const x = (i / (series.length - 1)) * w
      const y = h - ((p.ic - min) / range) * h
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const zeroY = h - ((0 - min) / range) * h
  const last = values[values.length - 1]
  const color = last >= 0 ? '#26a69a' : '#ef5350'
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <line x1={0} x2={w} y1={zeroY} y2={zeroY} stroke="rgba(128,128,128,0.3)" strokeWidth={0.5} />
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={points} />
    </svg>
  )
}

function KellyCards({ payload }: { payload?: KellyPayload }) {
  if (!payload || payload.status !== 'ok') {
    return (
      <>
        <h4 className="u-mt-4">Kelly 베팅 사이즈 (방향별)</h4>
        <p className="empty">방향별 샘플이 부족합니다.</p>
      </>
    )
  }
  const entries = Object.entries(payload.by_direction)
  return (
    <>
      <h4 className="u-mt-4">
        Kelly 베팅 사이즈 (half-Kelly, haircut ×{payload.haircut})
      </h4>
      <div className="signal-summary-grid">
        {entries.map(([direction, d]) => {
          if (d.status !== 'ok') {
            return (
              <div key={direction} className="signal-summary-card">
                <div className="signal-summary-direction">{direction}</div>
                <div className="signal-summary-count">N/A</div>
                <div className="signal-summary-row">
                  <span className="signal-summary-label">N</span>
                  <span>{d.n}</span>
                </div>
                <div className="signal-summary-row">
                  <span className="signal-summary-label">상태</span>
                  <span>insufficient_data</span>
                </div>
              </div>
            )
          }
          return (
            <div key={direction} className="signal-summary-card">
              <div className="signal-summary-direction">{direction}</div>
              <div className="signal-summary-count">
                {((d.kelly_half ?? 0) * 100).toFixed(1)}%
              </div>
              <div className="signal-summary-row">
                <span className="signal-summary-label">적중률</span>
                <span>{((d.hit_rate ?? 0) * 100).toFixed(1)}%</span>
              </div>
              <div className="signal-summary-row">
                <span className="signal-summary-label">payoff</span>
                <span>
                  {d.payoff_ratio !== null && d.payoff_ratio !== undefined
                    ? d.payoff_ratio.toFixed(2)
                    : 'N/A'}
                </span>
              </div>
              <div className="signal-summary-row">
                <span className="signal-summary-label">N</span>
                <span>{d.n}</span>
              </div>
              <div className="signal-summary-row">
                <span className="signal-summary-label">Full Kelly</span>
                <span>{((d.kelly_full ?? 0) * 100).toFixed(1)}%</span>
              </div>
            </div>
          )
        })}
      </div>
      <p className="section-kicker u-mt-2">
        f* = p - (1 - p) / b. half-Kelly가 실전 베팅 상한. 0이면 신호 에지 없음.
      </p>
    </>
  )
}

function TurnoverSummary({ payload }: { payload?: TurnoverPayload }) {
  if (!payload || payload.status !== 'ok' || payload.points.length === 0) {
    return (
      <>
        <h4 className="u-mt-4">시그널 세트 턴오버</h4>
        <p className="empty">일자 수가 부족합니다 (N={payload?.sample_size ?? 0}).</p>
      </>
    )
  }
  const recent = payload.points.slice(-20)
  return (
    <>
      <h4 className="u-mt-4">시그널 세트 턴오버 (Jaccard 변화율)</h4>
      <div className="signal-summary-grid u-mb-3">
        <div className="signal-summary-card">
          <div className="signal-summary-direction">평균 턴오버</div>
          <div className="signal-summary-count">
            {((payload.avg_turnover ?? 0) * 100).toFixed(1)}%
          </div>
          <div className="signal-summary-row">
            <span className="signal-summary-label">샘플 일수</span>
            <span>{payload.sample_size}</span>
          </div>
          <div className="signal-summary-row">
            <span className="signal-summary-label">해석</span>
            <span>
              {(payload.avg_turnover ?? 0) > 0.6
                ? '휩쏘 의심'
                : (payload.avg_turnover ?? 0) < 0.1
                  ? '정체 의심'
                  : '정상 범위'}
            </span>
          </div>
        </div>
      </div>
      <div className="watchlist-table-shell">
        <table className="watchlist-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>활성 티커</th>
              <th>턴오버</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((p) => (
              <tr key={p.date}>
                <td>{p.date}</td>
                <td>{p.tickers}</td>
                <td>{(p.turnover * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function formatIC(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(3)}`
}

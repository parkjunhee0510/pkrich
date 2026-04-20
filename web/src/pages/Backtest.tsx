import { useEffect, useMemo } from 'react'
import { EquityCurveChart } from '../components/EquityCurveChart'
import { useDashboardData } from '../hooks/useDashboardData'
import { useJsonResource } from '../hooks/useJsonResource'
import { ErrorState } from '../components/ErrorState'
import { TablePageSkeleton } from '../components/Skeleton'
import type { BacktestSummary, BacktestTickerRow, MonthlySummaryData, RoutingOutcomePayload } from '../types'

export function Backtest() {
  const { data: dashboardData, loading: dashboardLoading, error: dashboardError } = useDashboardData()
  const { data: backtest, loading: backtestLoading, error: backtestError } = useJsonResource<BacktestSummary>('output/data/backtest_summary.json')
  const { data: monthly, loading: monthlyLoading, error: monthlyError } = useJsonResource<MonthlySummaryData>('output/data/monthly_summary.json')
  const { data: routingOutcome, loading: routingLoading, error: routingError } = useJsonResource<RoutingOutcomePayload>('output/data/routing_outcome.json')

  useEffect(() => {
    document.title = '백테스트 · 주간 성과'
  }, [])

  const loading = dashboardLoading || backtestLoading || monthlyLoading || routingLoading
  const error = dashboardError || backtestError || monthlyError || routingError
  const latestDay = dashboardData?.days[dashboardData.days.length - 1]
  const signalMeta = dashboardData?.signal_stats?.meta_analysis
  const topTickerRows = useMemo(() => monthly?.top_tickers ?? [], [monthly])
  const topSectorRows = useMemo(() => monthly?.top_sectors ?? [], [monthly])
  const tickerRows = useMemo<Array<BacktestTickerRow | { ticker: string; signals: number; avg_return: string; win_rate: string }>>(
    () => backtest?.ticker_rows ?? signalMeta?.ticker_performance ?? [],
    [backtest?.ticker_rows, signalMeta?.ticker_performance],
  )

  if (loading) return <TablePageSkeleton title="백테스트 / 주간 성과" />
  if (error) return <ErrorState message={error} />

  const routingSummary = routingOutcome?.summary
  const routingPeriods = routingOutcome?.periods ?? []
  const latestRoutingRun = routingOutcome?.latest_run && 'run_date' in routingOutcome.latest_run ? routingOutcome.latest_run : null
  const routingHasEvaluatedData = (routingOutcome?.evaluated_signals ?? 0) > 0
  const routingDeepOnlyState = Boolean(
    routingSummary &&
    routingSummary.deep_selected_count > 0 &&
    routingSummary.economy_only_count === 0,
  )

  return (
    <div className="signals-page">
      <div className="dashboard-header">
        <h2>백테스트 / 주간 성과</h2>
      </div>

      <div className="signal-summary-grid">
        <SummaryMetricCard label="전략" value={backtest?.strategy ?? 'N/A'} note={backtest?.status ?? 'no_data'} />
        <SummaryMetricCard label="신호 수" value={`${backtest?.signals ?? 0}`} note="20거래일 평가 완료 bull / bear 시그널" />
        <SummaryMetricCard label="승률" value={backtest?.win_rate ?? 'N/A'} note={`평균 ${backtest?.avg_return ?? 'N/A'}`} />
        <SummaryMetricCard label="누적 수익률" value={backtest?.cumulative_return ?? 'N/A'} note={`최고 ${backtest?.best_return ?? 'N/A'} / 최저 ${backtest?.worst_return ?? 'N/A'}`} />
      </div>

      {backtest?.status === 'awaiting_evaluation' ? (
        <section className="signals-meta-section">
          <div className="detail-note-card">
            <p>{backtest.message ?? '아직 20거래일 평가를 기다리는 signal이 있습니다.'}</p>
            {backtest.first_eval_date ? (
              <p className="detail-section-summary">
                {backtest.first_eval_date}부터 백테스트 통계 집계가 시작됩니다. 현재 대기 중인 signal은 {backtest.pending_signals ?? 0}건입니다.
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      {backtest?.equity_curve && backtest.equity_curve.length > 1 ? (
        <section className="ticker-detail-section-shell">
          <EquityCurveChart points={backtest.equity_curve} title="전략 누적 수익 곡선" />
        </section>
      ) : null}

      {(backtest?.bull || backtest?.bear) ? (
        <section className="signals-meta-section">
          <div className="section-header-with-kicker">
            <div>
              <h3>방향별 성과</h3>
              <p className="section-kicker">bull / bear 시그널을 분리해서 비교합니다.</p>
            </div>
          </div>
          <div className="signal-summary-grid">
            <SummaryMetricCard
              label="강세"
              value={`${backtest?.bull?.signals ?? 0} signals`}
              note={`승률 ${backtest?.bull?.win_rate ?? 'N/A'} · 평균 ${backtest?.bull?.avg_return ?? 'N/A'}`}
            />
            <SummaryMetricCard
              label="약세"
              value={`${backtest?.bear?.signals ?? 0} signals`}
              note={`승률 ${backtest?.bear?.win_rate ?? 'N/A'} · 평균 ${backtest?.bear?.avg_return ?? 'N/A'}`}
            />
          </div>
        </section>
      ) : null}

      {routingSummary ? (
        <section className="signals-meta-section">
          <div className="section-header-with-kicker">
            <div>
              <h3>라우팅 성과 비교</h3>
              <p className="section-kicker">deep 재분석 대상과 economy-only 종목의 20거래일 성과를 비교해, 2차 검토가 실제로 의미 있었는지 봅니다.</p>
            </div>
          </div>
          {!routingHasEvaluatedData ? (
            <div className="detail-note-card">
              <p>
                아직 20거래일 사후 평가가 끝난 signal 표본이 없어 비교 수치가 비어 있습니다.
                라우팅 실행과 signal 수익률 이력이 더 쌓이면 여기서 deep 선택군과 economy-only 성과가 자동으로 비교됩니다.
              </p>
              {routingDeepOnlyState ? (
                <p className="detail-section-summary">
                  현재는 설정상 대부분 종목이 deep 재분석 대상으로 들어가서 economy-only 비교군도 비어 있습니다.
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="signal-summary-grid">
            <SummaryMetricCard
              label="Deep 선택 평균"
              value={formatPercentValue(routingSummary.deep_selected_avg_return_20d)}
              note={buildRoutingMetricNote(
                routingSummary.deep_selected_hit_rate,
                routingSummary.deep_selected_count,
                'deep 재분석 표본이 아직 없습니다.',
              )}
            />
            <SummaryMetricCard
              label="Economy-only 평균"
              value={formatPercentValue(routingSummary.economy_only_avg_return_20d)}
              note={
                routingSummary.economy_only_count === 0
                  ? '현재 비교군이 없습니다. 이번 구간에서는 economy-only로 남은 종목이 없었습니다.'
                  : buildRoutingMetricNote(
                    routingSummary.economy_only_hit_rate,
                    routingSummary.economy_only_count,
                    'economy-only 표본이 아직 없습니다.',
                  )
              }
            />
            <SummaryMetricCard
              label="성과 차이"
              value={formatPercentValue(routingSummary.avg_return_delta_20d)}
              note={
                routingSummary.avg_return_delta_20d === null
                  ? '두 그룹이 모두 쌓여야 차이를 계산할 수 있습니다.'
                  : `히트율 차이 ${formatRatio(routingSummary.hit_rate_delta)}`
              }
            />
            <SummaryMetricCard
              label="포트폴리오 우선"
              value={formatPercentValue(routingSummary.portfolio_priority_avg_return_20d)}
              note={
                latestRoutingRun?.portfolio_priority
                  ? buildRoutingMetricNote(
                    routingSummary.portfolio_priority_hit_rate,
                    routingSummary.portfolio_priority_count,
                    '포트폴리오 우선 표본이 아직 없습니다.',
                  )
                  : '현재는 포트폴리오 우선 라우팅이 꺼져 있습니다.'
              }
            />
          </div>

          {routingPeriods.length > 0 ? (
            <div className="watchlist-table-shell">
              <table className="watchlist-table">
                <thead>
                  <tr>
                    <th>기간</th>
                    <th>Deep 평균</th>
                    <th>Economy 평균</th>
                    <th>수익률 차이</th>
                    <th>Deep 히트율</th>
                    <th>Economy 히트율</th>
                    <th>포트폴리오 우선</th>
                  </tr>
                </thead>
                <tbody>
                  {routingPeriods.map((period) => (
                    <tr key={period.period}>
                      <td>{period.period}</td>
                      <td>{formatPercentValue(period.deep_selected_avg_return_20d)}</td>
                      <td>{formatPercentValue(period.economy_only_avg_return_20d)}</td>
                      <td>{formatPercentValue(period.avg_return_delta_20d)}</td>
                      <td>{formatRatio(period.deep_selected_hit_rate)}</td>
                      <td>{formatRatio(period.economy_only_hit_rate)}</td>
                      <td>
                        {formatPercentValue(period.portfolio_priority_avg_return_20d)}
                        <div className="section-kicker">{period.portfolio_priority_count}건 / {formatRatio(period.portfolio_priority_hit_rate)}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {latestRoutingRun ? (
            <div className="signal-summary-grid">
              <SummaryMetricCard
                label="최신 라우팅 실행"
                value={latestRoutingRun.run_date}
                note={`deep pass ${latestRoutingRun.deep_pass_count}건 · 범위 ${latestRoutingRun.trigger_range.join(' ~ ')}`}
              />
              <SummaryMetricCard
                label="포트폴리오 우선"
                value={latestRoutingRun.portfolio_priority ? '활성' : '비활성'}
                note={`일일 제한 ${latestRoutingRun.max_daily_ensemble === 0 ? '무제한' : latestRoutingRun.max_daily_ensemble}`}
              />
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>월간 리포트</h3>
            <p className="section-kicker">
              {monthly?.month ?? 'N/A'} · {monthly?.start_date ?? 'N/A'} ~ {monthly?.end_date ?? 'N/A'} · {monthly?.trading_days ?? 0} trading days
            </p>
          </div>
        </div>
        <div className="signal-summary-grid">
          <SummaryMetricCard
            label="상위 종목"
            value={topTickerRows[0] ? `${topTickerRows[0].ticker} ${topTickerRows[0].avg_daily_change}` : 'N/A'}
            note={topTickerRows[1] ? `${topTickerRows[1].ticker} ${topTickerRows[1].avg_daily_change}` : '데이터 없음'}
          />
          <SummaryMetricCard
            label="상위 섹터"
            value={topSectorRows[0] ? `${topSectorRows[0].sector} ${topSectorRows[0].avg_daily_change}` : 'N/A'}
            note={topSectorRows[1] ? `${topSectorRows[1].sector} ${topSectorRows[1].avg_daily_change}` : '데이터 없음'}
          />
          <SummaryMetricCard
            label="리서치 범위"
            value={`${latestDay?.tickers.length ?? 0} tickers`}
            note={signalMeta?.status === 'ok' ? `${signalMeta.total_evaluated} evaluated signals` : '신호 메타 분석 준비 중'}
          />
        </div>
      </section>

      {tickerRows.length > 0 ? (
        <section className="signals-meta-section">
          <div className="section-header-with-kicker">
            <div>
              <h3>종목별 성과</h3>
              <p className="section-kicker">시그널 히스토리 기준 평균 수익률과 승률입니다.</p>
            </div>
          </div>
          <div className="watchlist-table-shell">
            <table className="watchlist-table">
              <thead>
                <tr>
                  <th>티커</th>
                  <th>신호 수</th>
                  <th>평균 수익</th>
                  <th>승률</th>
                  <th>강세</th>
                  <th>약세</th>
                  <th>최고</th>
                  <th>최저</th>
                </tr>
              </thead>
              <tbody>
                {tickerRows.map((row) => (
                  <tr key={row.ticker}>
                    <td>{row.ticker}</td>
                    <td>{row.signals}</td>
                    <td>{row.avg_return}</td>
                    <td>{row.win_rate}</td>
                    <td>{'bull_signals' in row ? row.bull_signals : 'N/A'}</td>
                    <td>{'bear_signals' in row ? row.bear_signals : 'N/A'}</td>
                    <td>{'best_return' in row ? row.best_return : 'N/A'}</td>
                    <td>{'worst_return' in row ? row.worst_return : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
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

function formatPercentValue(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '데이터 축적 중'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatRatio(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '데이터 축적 중'
  return `${value.toFixed(1)}%`
}

function buildRoutingMetricNote(
  hitRate: number | null | undefined,
  count: number,
  emptyMessage: string,
) {
  if (count <= 0) {
    return emptyMessage
  }
  return `히트율 ${formatRatio(hitRate)} · ${count}건`
}

import { useEffect, useMemo } from 'react'
import { useDashboardData } from '../hooks/useDashboardData'
import { useJsonResource } from '../hooks/useJsonResource'
import { ErrorState } from '../components/ErrorState'
import { TablePageSkeleton } from '../components/Skeleton'
import type { BacktestSummary, MonthlySummaryData } from '../types'

export function Backtest() {
  const { data: dashboardData, loading: dashboardLoading, error: dashboardError } = useDashboardData()
  const {
    data: backtest,
    loading: backtestLoading,
    error: backtestError,
  } = useJsonResource<BacktestSummary>('output/data/backtest_summary.json')
  const {
    data: monthly,
    loading: monthlyLoading,
    error: monthlyError,
  } = useJsonResource<MonthlySummaryData>('output/data/monthly_summary.json')

  useEffect(() => {
    document.title = '백테스트 · Stock Research'
  }, [])

  const loading = dashboardLoading || backtestLoading || monthlyLoading
  const error = dashboardError || backtestError || monthlyError
  const latestDay = dashboardData?.days[dashboardData.days.length - 1]
  const signalMeta = dashboardData?.signal_stats?.meta_analysis
  const topTickerRows = useMemo(() => monthly?.top_tickers ?? [], [monthly])
  const topSectorRows = useMemo(() => monthly?.top_sectors ?? [], [monthly])

  if (loading) return <TablePageSkeleton title="백테스트 / 월간 성과" />
  if (error) return <ErrorState message={error} />

  return (
    <div className="signals-page">
      <div className="dashboard-header">
        <h2>백테스트 / 월간 성과</h2>
      </div>

      <div className="signal-summary-grid">
        <SummaryMetricCard label="전략" value={backtest?.strategy ?? 'N/A'} note={backtest?.status ?? 'no_data'} />
        <SummaryMetricCard label="신호 수" value={`${backtest?.signals ?? 0}`} note="20거래일 평가 완료 강세 신호" />
        <SummaryMetricCard label="승률" value={backtest?.win_rate ?? 'N/A'} note={`평균 ${backtest?.avg_return ?? 'N/A'}`} />
        <SummaryMetricCard label="누적 수익률" value={backtest?.cumulative_return ?? 'N/A'} note={`최고 ${backtest?.best_return ?? 'N/A'} / 최저 ${backtest?.worst_return ?? 'N/A'}`} />
      </div>

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

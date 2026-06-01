import { useEffect, useMemo } from 'react'
import { ErrorState } from '../components/ErrorState'
import { TablePageSkeleton } from '../components/Skeleton'
import { useJsonResource } from '../hooks/useJsonResource'
import type { ApiProviderSummary, ApiProviderState, ApiStatusSummary, ApiTickerMatrixRow } from '../types'

const PROVIDER_LABELS: Record<string, string> = {
  yfinance: 'yfinance',
  alpha_vantage: 'Alpha Vantage',
  polygon: 'Polygon',
  fmp: 'FMP',
  finnhub: 'Finnhub',
  sec_edgar: 'SEC EDGAR',
  ir_rss: 'IR RSS',
}

const PROVIDER_DESCRIPTIONS: Record<string, { summary: string; fields: string[] }> = {
  yfinance: {
    summary: '기본 시세와 재무 스냅샷을 담당하는 핵심 무료 공급자입니다.',
    fields: ['현재가/등락률', '52주 고저점', 'SMA/거래량', 'Forward EPS 일부', '포지셔닝 기본값'],
  },
  alpha_vantage: {
    summary: '실적 기대치와 이벤트 보강에 쓰는 보조 공급자입니다.',
    fields: ['EPS 추정치', 'earnings surprise', 'earnings calendar', 'Forward EPS fallback', 'EPS 성장률 fallback'],
  },
  polygon: {
    summary: '옵션 흐름과 파생 수급 맥락을 보강합니다.',
    fields: ['options flow', 'unusual activity', 'call/put 흐름', '옵션 기반 심리'],
  },
  fmp: {
    summary: '심화 펀더멘털과 수급 보강용 공급자입니다. 현재는 rate limit 영향이 큽니다.',
    fields: ['key metrics', 'financial ratios', 'dividend history', 'company profile', 'insider/기관/estimate 확장 데이터'],
  },
  finnhub: {
    summary: '애널리스트 추천 추세와 일부 거시 일정을 보강합니다.',
    fields: ['recommendation trends', 'economic calendar 일부', '리비전 방향 힌트'],
  },
  sec_edgar: {
    summary: '공식 SEC 공시를 수집해 hard catalyst를 식별합니다.',
    fields: ['10-K/10-Q/8-K', 'Item 2.02/5.02', '공시 날짜', '공시 링크', '촉매 강도 분류'],
  },
  ir_rss: {
    summary: '기업 공식 IR/뉴스룸 피드를 통해 회사 발표를 직접 가져옵니다.',
    fields: ['IR RSS', 'Newsroom feed', '공식 보도자료', '기업 발표 일정/헤드라인'],
  },
}

const OVERALL_LABELS: Record<ApiProviderSummary['overall_status'], string> = {
  active: '정상',
  partial: '부분 사용',
  limited: '제한',
  failing: '실패',
  idle: '미사용',
}

const STATE_LABELS: Record<ApiProviderState, string> = {
  used: 'used',
  failed: 'failed',
  throttled: 'throttled',
  unavailable: 'unavailable',
  not_used: '-',
}

type ApiStatusData = {
  summary: ApiStatusSummary
  matrix: ApiTickerMatrixRow[]
}

export function ApiStatus() {
  const { data: summary, loading: summaryLoading, error: summaryError } =
    useJsonResource<ApiStatusSummary>('output/data/api_status.json')
  const { data: matrix, loading: matrixLoading, error: matrixError } =
    useJsonResource<ApiTickerMatrixRow[]>('output/data/api_ticker_matrix.json')

  useEffect(() => {
    document.title = 'API 상태 · Stock Research'
  }, [])

  const data = useMemo<ApiStatusData | null>(
    () => (summary && matrix ? { summary, matrix } : null),
    [summary, matrix],
  )
  const loading = (summaryLoading || matrixLoading) && !data
  const error = summaryError || matrixError

  const providerEntries = useMemo(
    () => Object.entries(data?.summary.providers ?? {}),
    [data?.summary.providers],
  )

  if (loading) return <TablePageSkeleton title="API 상태" />
  if (error) return <ErrorState message={error} />
  if (!data) return <p className="status">API 상태 데이터가 아직 없습니다.</p>

  return (
    <div className="api-status-page">
      <header className="page-header">
        <div className="page-header__eyebrow">DIAGNOSTICS · API STATUS</div>
        <div className="page-header__row">
          <h2 className="page-header__headline">API 상태</h2>
          <div className="page-header__actions">
            <span className={`api-state-pill ${data.summary.pipeline_completed ? 'state-used' : 'state-failed'}`}>
              {data.summary.pipeline_completed ? 'pipeline completed' : 'pipeline incomplete'}
            </span>
            <span className="status">{data.summary.run_date}</span>
          </div>
        </div>
        <p className="page-header__meta">
          최신 파이프라인 실행 기준으로 공급자별 건강 상태와 티커별 실제 사용 여부를 확인합니다.
        </p>
      </header>

      <div className="api-provider-grid">
        <OpenAiUsageCard summary={data.summary} />
        {providerEntries.map(([providerKey, provider]) => (
          <ProviderCard key={providerKey} providerKey={providerKey} provider={provider} />
        ))}
      </div>

      <section className="signals-meta-section">
        <div className="section-header-with-kicker">
          <div>
            <h3>티커별 API 매트릭스</h3>
            <p className="section-kicker">
              각 종목이 최신 실행에서 어떤 공급자를 실제로 사용했는지, 비어 있었는지, 실패했는지 한눈에 봅니다.
            </p>
          </div>
        </div>

        <div className="watchlist-table-shell">
          <table className="watchlist-table api-status-table">
            <thead>
              <tr>
                <th>티커</th>
                <th>이름</th>
                <th>섹터</th>
                <th>yfinance</th>
                <th>Alpha Vantage</th>
                <th>Polygon</th>
                <th>FMP</th>
                <th>Finnhub</th>
                <th>SEC EDGAR</th>
                <th>IR RSS</th>
              </tr>
            </thead>
            <tbody>
              {data.matrix.map((row) => (
                <tr key={row.ticker}>
                  <td>{row.ticker}</td>
                  <td>{row.name}</td>
                  <td>{row.sector || '-'}</td>
                  <td><ApiStatePill state={row.yfinance} /></td>
                  <td><ApiStatePill state={row.alpha_vantage} /></td>
                  <td><ApiStatePill state={row.polygon} /></td>
                  <td><ApiStatePill state={row.fmp} /></td>
                  <td><ApiStatePill state={row.finnhub} /></td>
                  <td><ApiStatePill state={row.sec_edgar} /></td>
                  <td><ApiStatePill state={row.ir_rss} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="api-status-log-path">
          <span className="signal-summary-label">로그 파일</span>
          <code>{data.summary.log_path}</code>
        </div>
      </section>
    </div>
  )
}

function ProviderCard({
  providerKey,
  provider,
}: {
  providerKey: string
  provider: ApiProviderSummary
}) {
  return (
    <div className={`api-provider-card provider-${provider.overall_status}`}>
      <div className="api-provider-head">
        <strong>{PROVIDER_LABELS[providerKey] ?? providerKey}</strong>
        <span className={`api-state-pill ${stateClassForOverall(provider.overall_status)}`}>
          {OVERALL_LABELS[provider.overall_status]}
        </span>
      </div>
      <p className="api-provider-description">
        {PROVIDER_DESCRIPTIONS[providerKey]?.summary ?? '이 공급자의 역할 설명이 아직 없습니다.'}
      </p>
      <div className="api-provider-metrics">
        <ProviderMetric label="used" value={provider.used_tickers} />
        <ProviderMetric label="throttled" value={provider.throttled_tickers} />
        <ProviderMetric label="unavailable" value={provider.unavailable_tickers} />
        <ProviderMetric label="failed" value={provider.failed_tickers} />
        <ProviderMetric label="not used" value={provider.not_used_tickers} />
      </div>
      <div className="api-provider-fields">
        {(PROVIDER_DESCRIPTIONS[providerKey]?.fields ?? []).map((field) => (
          <span key={field} className="api-provider-field-chip">
            {field}
          </span>
        ))}
      </div>
    </div>
  )
}

function OpenAiUsageCard({ summary }: { summary: ApiStatusSummary }) {
  const llm = summary.llm
  const modelEntries = Object.entries(llm.models_used ?? {})
  const quality = llm.quality
  const hallucinationPct =
    typeof quality?.hallucination_ratio === 'number'
      ? `${(quality.hallucination_ratio * 100).toFixed(1)}%`
      : 'N/A'

  return (
    <div className={`api-provider-card provider-${llm.used ? 'active' : 'idle'}`}>
      <div className="api-provider-head">
        <strong>OpenAI</strong>
        <span className={`api-state-pill ${llm.used ? 'state-used' : 'state-not-used'}`}>
          {llm.used ? '사용됨' : '미사용'}
        </span>
      </div>
      <p className="api-provider-description">
        최신 파이프라인 실행에서 실제 LLM 분석이 수행됐는지, 어떤 모델을 썼는지, 비용이 어느 정도였는지 보여줍니다.
      </p>
      <div className="api-provider-metrics">
        <ProviderMetric label="latest model" valueText={llm.latest_model || 'N/A'} />
        <ProviderMetric label="estimated cost" valueText={`$${Number(llm.estimated_cost_usd ?? 0).toFixed(4)}`} />
        <ProviderMetric label="planned batches" value={llm.planned_batches} />
        <ProviderMetric label="completed batches" value={llm.completed_batches} />
        <ProviderMetric label="failed batches" value={llm.failed_batches} />
        <ProviderMetric label="validation fails" value={llm.validation_failures} />
        <ProviderMetric label="validated tickers" value={quality?.validated_ticker_count ?? 0} />
        <ProviderMetric label="schema violations" value={quality?.schema_violation_count ?? 0} />
        <ProviderMetric label="fact warnings" value={quality?.fact_warning_count ?? 0} />
        <ProviderMetric label="hallucination ratio" valueText={hallucinationPct} />
      </div>
      <div className="api-provider-fields">
        {modelEntries.length > 0 ? (
          modelEntries.map(([model, count]) => (
            <span key={model} className="api-provider-field-chip">
              {model} × {count}
            </span>
          ))
        ) : (
          <span className="api-provider-field-chip">이번 실행의 모델 기록이 없어 사용 모델을 표시할 수 없음</span>
        )}
        {quality?.run_date ? (
          <span className="api-provider-field-chip">
            품질 기준일 {quality.run_date}
          </span>
        ) : null}
        {typeof quality?.consistency_warning_count === 'number' ? (
          <span className="api-provider-field-chip">
            일관성 경고 {quality.consistency_warning_count}
          </span>
        ) : null}
        {typeof quality?.hallucination_warning_count === 'number' ? (
          <span className="api-provider-field-chip">
            환각 의심 {quality.hallucination_warning_count}
          </span>
        ) : null}
      </div>
    </div>
  )
}

function ProviderMetric({ label, value, valueText }: { label: string; value?: number; valueText?: string }) {
  return (
    <div className="api-provider-metric">
      <span className="signal-summary-label">{label}</span>
      <strong>{valueText ?? value ?? 0}</strong>
    </div>
  )
}

function ApiStatePill({ state }: { state: ApiProviderState }) {
  return <span className={`api-state-pill ${stateClassForState(state)}`}>{STATE_LABELS[state]}</span>
}

function stateClassForOverall(status: ApiProviderSummary['overall_status']): string {
  switch (status) {
    case 'active':
      return 'state-used'
    case 'partial':
      return 'state-caution'
    case 'limited':
      return 'state-unavailable'
    case 'failing':
      return 'state-failed'
    default:
      return 'state-not-used'
  }
}

function stateClassForState(state: ApiProviderState): string {
  switch (state) {
    case 'used':
      return 'state-used'
    case 'failed':
      return 'state-failed'
    case 'throttled':
      return 'state-caution'
    case 'unavailable':
      return 'state-unavailable'
    default:
      return 'state-not-used'
  }
}

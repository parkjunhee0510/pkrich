import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { TickerImpact } from '../types'
import { usePolicyData } from '../hooks/usePolicyData'
import { ErrorState } from '../components/ErrorState'
import { DashboardSkeleton } from '../components/Skeleton'

const CATEGORY_LABELS: Record<string, string> = {
  interest_rate: '금리',
  antitrust: '반독점',
  export_control: '수출 통제',
  subsidy: '보조금',
  tariff: '관세',
  ira: 'IRA',
  chips_act: 'CHIPS Act',
  fda: 'FDA',
  defense_budget: '국방',
  energy_policy: '에너지',
  banking: '은행',
  defense: '국방',
  energy: '에너지',
  other: '기타',
}

const CATEGORY_TONE: Record<string, 'positive' | 'negative' | 'caution' | 'info' | 'accent'> = {
  ira: 'positive',
  chips_act: 'positive',
  subsidy: 'positive',
  fda: 'caution',
  antitrust: 'negative',
  export_control: 'negative',
  tariff: 'negative',
  banking: 'caution',
  defense: 'info',
  defense_budget: 'info',
  energy: 'info',
  energy_policy: 'info',
  interest_rate: 'caution',
  other: 'info',
}

const DIRECTION_LABELS: Record<TickerImpact['direction'], string> = {
  positive: '긍정',
  negative: '부정',
  neutral: '중립',
}

const STRENGTH_LABELS: Record<TickerImpact['strength'], string> = {
  direct: '직접',
  indirect: '간접',
  neutral: '중립',
}

function impactTone(direction: TickerImpact['direction']): 'positive' | 'negative' | 'caution' {
  if (direction === 'positive') return 'positive'
  if (direction === 'negative') return 'negative'
  return 'caution'
}

export function PolicyImpact() {
  const { data, loading, error } = usePolicyData()
  const [activeCategory, setActiveCategory] = useState<string>('all')

  useEffect(() => {
    document.title = '정책·규제 영향도 · Stock Research'
  }, [])

  const categoriesPresent = useMemo(() => {
    if (!data) return [] as string[]
    return Array.from(new Set(data.events.map((e) => e.category))).sort()
  }, [data])

  const filteredEvents = useMemo(() => {
    if (!data) return []
    return activeCategory === 'all'
      ? data.events
      : data.events.filter((e) => e.category === activeCategory)
  }, [data, activeCategory])

  const totalTickers = data ? Object.keys(data.tailwind_scores).length : 0

  if (loading) return <DashboardSkeleton />

  // 404 / missing file = policy stage hasn't run yet (graceful degradation).
  // Show a friendly empty state, not an ErrorState.
  if (error) {
    const isMissing = /(^|\s)4\d\d(\s|$)/.test(error)
    if (isMissing) {
      return (
        <div className="policy-impact-page">
          <header className="page-header">
            <div className="page-header__eyebrow">RESEARCH · POLICY IMPACT</div>
            <div className="page-header__row">
              <h1 className="page-header__headline">정책·규제 영향도</h1>
            </div>
            <p className="page-header__meta">
              아직 분석 데이터가 준비되지 않았습니다. 다음 파이프라인 실행에서 생성됩니다.
            </p>
          </header>
          <p className="status">
            <code>output/data/policy_impact.json</code> 파일이 없습니다 — <code>python main.py</code>를 한 번 실행해 정책 stage를 활성화하세요.
            (OPENAI_API_KEY 필요)
          </p>
        </div>
      )
    }
    return <ErrorState message={`policy_impact.json: ${error}`} />
  }

  if (!data) return null

  return (
    <div className="policy-impact-page">
      <header className="page-header">
        <div className="page-header__eyebrow">RESEARCH · POLICY IMPACT</div>
        <div className="page-header__row">
          <h1 className="page-header__headline">정책·규제 영향도</h1>
          <div className="page-header__actions">
            <span className="chip tone-info--soft">{data.events.length}건 이벤트</span>
            <span className="chip tone-accent--soft">{totalTickers}종목 점수</span>
          </div>
        </div>
        <p className="page-header__meta">
          기준일 {data.date} · 범주별 정책 이벤트와 워치리스트 종목별 영향도 점수.
        </p>
      </header>

      <div className="policy-filter-row" role="tablist" aria-label="카테고리 필터">
        <button
          type="button"
          className={`chip ${activeCategory === 'all' ? 'tone-accent--solid' : 'tone-accent--soft'}`}
          onClick={() => setActiveCategory('all')}
        >
          전체 ({data.events.length})
        </button>
        {categoriesPresent.map((cat) => {
          const tone = CATEGORY_TONE[cat] ?? 'info'
          const active = activeCategory === cat
          const count = data.events.filter((e) => e.category === cat).length
          return (
            <button
              key={cat}
              type="button"
              className={`chip ${active ? `tone-${tone}--solid` : `tone-${tone}--soft`}`}
              onClick={() => setActiveCategory(cat)}
            >
              {CATEGORY_LABELS[cat] ?? cat} ({count})
            </button>
          )
        })}
      </div>

      {filteredEvents.length === 0 ? (
        <p className="status">선택한 카테고리에 해당하는 이벤트가 없습니다.</p>
      ) : (
        <ul className="policy-event-list">
          {filteredEvents.map((event) => {
            const impacts = data.impacts_by_event[event.id] ?? []
            const ranked = [...impacts].sort(
              (a, b) => Math.abs(b.score) * b.confidence - Math.abs(a.score) * a.confidence,
            )
            const tone = CATEGORY_TONE[event.category] ?? 'info'
            return (
              <li key={event.id} className="surface-card policy-event-card">
                <div className="policy-event-head">
                  <span className={`chip tone-${tone}--soft`}>
                    {CATEGORY_LABELS[event.category] ?? event.category}
                  </span>
                  <span className="badge tone-accent--soft">
                    확신도 {event.confidence.toFixed(2)}
                  </span>
                  {typeof event.age_days === 'number' ? (
                    <span className="badge tone-info--soft">발견 D+{event.age_days}</span>
                  ) : null}
                  {event.effective_through ? (
                    <span className="badge tone-caution--soft">만료 {event.effective_through}</span>
                  ) : null}
                  {typeof event.decay_weight === 'number' && event.decay_weight < 0.99 ? (
                    <span className="badge tone-accent--outline">가중치 {event.decay_weight.toFixed(2)}</span>
                  ) : null}
                  <span className="status">{event.source_domain}</span>
                </div>
                <a
                  href={event.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="type-headline policy-event-headline"
                >
                  {event.headline}
                </a>
                <p className="type-body policy-event-summary">{event.summary}</p>
                {ranked.length > 0 ? (
                  <div className="policy-impact-rows">
                    {ranked.map((impact, idx) => (
                      <div key={`${event.id}-${impact.ticker}-${idx}`} className="policy-impact-row">
                        <Link to={`/ticker/${impact.ticker}`} className="type-body-strong">
                          {impact.ticker}
                        </Link>
                        <span className={`chip tone-${impactTone(impact.direction)}--soft`}>
                          {DIRECTION_LABELS[impact.direction]} · {STRENGTH_LABELS[impact.strength]}
                        </span>
                        <span className="badge tone-accent--soft">
                          점수 {impact.score >= 0 ? '+' : ''}
                          {impact.score.toFixed(2)}
                        </span>
                        {impact.confidence < 0.5 ? (
                          <span className="chip tone-caution--soft">낮은 확신도</span>
                        ) : null}
                        <span className="type-meta policy-impact-rationale">
                          {impact.rationale}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="status">관련 종목 영향도 데이터 없음.</p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

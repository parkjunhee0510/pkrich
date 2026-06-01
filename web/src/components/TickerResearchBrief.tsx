import type { TodayPriorityQueueItem } from '../utils/todayPriorityQueue'

type TickerResearchBriefProps = {
  ticker: string
  item: TodayPriorityQueueItem | null
}

export function TickerResearchBrief({ ticker, item }: TickerResearchBriefProps) {
  const normalizedTicker = ticker.toUpperCase()

  if (!item) {
    return (
      <section
        className="ticker-research-brief ticker-detail-section-shell"
        aria-labelledby="ticker-research-brief-title"
      >
        <div className="section-header-with-kicker">
          <div>
            <h3 id="ticker-research-brief-title">오늘 올라온 이유</h3>
            <p className="section-kicker">{normalizedTicker} 점검 맥락</p>
          </div>
          <span className="ticker-research-brief-badge">Queue 없음</span>
        </div>

        <p className="ticker-research-brief-summary">
          오늘 우선 점검 큐에는 포함되지 않았습니다.
        </p>
        <p className="ticker-research-brief-next">
          공식 판단과 기존 상세 데이터를 기준으로 확인하세요.
        </p>
      </section>
    )
  }

  return (
    <section
      className={`ticker-research-brief ticker-detail-section-shell today-priority-tone-${item.tone}`}
      aria-labelledby="ticker-research-brief-title"
    >
      <div className="section-header-with-kicker">
        <div>
          <h3 id="ticker-research-brief-title">오늘 올라온 이유</h3>
          <p className="section-kicker">
            {item.ticker} · Score {Math.round(item.priorityScore)} · {item.officialAction}
          </p>
        </div>
        <span className="ticker-research-brief-badge">{formatPriorityLabel(item.priorityLabel)}</span>
      </div>

      <div className="ticker-research-brief-grid" role="group" aria-label={`${item.ticker} 점검 신호`}>
        <div className="ticker-research-brief-card">
          <span>리스크</span>
          <strong>{formatSignalLabel(item.riskLabel)}</strong>
        </div>
        <div className="ticker-research-brief-card">
          <span>기회</span>
          <strong>{formatSignalLabel(item.opportunityLabel)}</strong>
        </div>
        <div className="ticker-research-brief-card">
          <span>근거</span>
          <strong>{formatSignalLabel(item.evidenceLabel)}</strong>
        </div>
      </div>

      {item.reasons.length > 0 ? (
        <div className="ticker-research-brief-reasons">
          <strong>핵심 논점</strong>
          <ul>
            {item.reasons.map((reason) => (
              <li key={reason}>{formatReasonForDisplay(reason)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="ticker-research-brief-next">{item.nextCheck}</p>
    </section>
  )
}

const PRIORITY_LABELS_KO: Record<string, string> = {
  'Risk and opportunity review': '리스크/기회 동시 점검',
  'Risk-led review': '리스크 우선 점검',
  'Opportunity-led review': '기회 우선 점검',
  'Evidence review': '근거 우선 점검',
  Review: '점검',
}

const SIGNAL_LABELS_KO: Record<string, string> = {
  'Risk high': '리스크 높음',
  'Risk medium': '리스크 중간',
  'Risk watch': '리스크 관찰',
  'Risk unknown': '리스크 정보 없음',
  'Risk none': '리스크 없음',
  'Opportunity high': '기회 높음',
  'Opportunity medium': '기회 중간',
  'Opportunity watch': '기회 관찰',
  'Opportunity none': '기회 없음',
  'Evidence unknown': '근거 상태 미확인',
  'Evidence missing': '근거 부족',
  'Evidence refresh needed': '근거 갱신 필요',
  'Evidence stale': '근거 오래됨',
  'Evidence covered': '근거 확인됨',
}

const REASON_LABELS_KO: Record<string, string> = {
  'Risk intelligence alert': '리스크 인텔 알림',
  'BUY with high conviction': '높은 확신도의 BUY 판단',
  'BUY action under review': 'BUY 판단 검토 필요',
  'Bullish news tone': '뉴스 톤 강세',
  'Relative volume above 1.2': '상대 거래량 1.2배 이상',
  'Positive relative strength': '시장/섹터 대비 상대 강도 양호',
  'Search evidence coverage is missing': '검색 근거 커버리지 누락',
  'Priority evidence was not refreshed': '우선 갱신 대상 근거가 갱신되지 않음',
  'Search evidence cache is stale': '검색 근거 캐시가 오래됨',
  'BUY action needs human review': 'BUY 판단 수동 확인 필요',
  'AVOID action needs human review': 'AVOID 판단 수동 확인 필요',
}

function formatPriorityLabel(label: string): string {
  return PRIORITY_LABELS_KO[label] ?? label
}

function formatSignalLabel(label: string): string {
  return SIGNAL_LABELS_KO[label] ?? label
}

function formatReasonForDisplay(reason: string): string {
  const actionChange = reason.match(/^Action changed from ([A-Z]+) to ([A-Z]+)$/)
  if (actionChange) {
    return `공식 판단이 ${actionChange[1]}에서 ${actionChange[2]}로 변경됨`
  }

  return REASON_LABELS_KO[reason] ?? reason
}

import type { TickerDecisionData, TradeFrame, UpcomingEvent } from '../types'
import { parsePrice } from '../utils/format'
import type { CatalystFeedItem, PositionSizingSummary, TraderActionPlan } from '../utils/trader'

type TraderDecisionBoardProps = {
  actionPlan: TraderActionPlan
  latestCatalyst: CatalystFeedItem | null
  dashboardSizing: PositionSizingSummary
  targetPrice?: string
  tradeFrame?: TradeFrame
  decision?: TickerDecisionData | null
  previousDecision?: TickerDecisionData | null
  upcomingEvents?: UpcomingEvent[]
  currentPrice?: string
}

type CounterSignal = {
  key: string
  label: string
  score: number
  reason: string
}

type TimelineEvent = {
  key: string
  label: string
  date: string
  daysUntil: number
  dayLabel: string
  timing: string
  leftPercent: number
}

const FACTOR_LABELS: Record<string, string> = {
  valuation: '밸류에이션',
  momentum: '모멘텀',
  catalyst_recency: '촉매',
  signal_track_record: '시그널 이력',
  news_tone: '뉴스 톤',
  regime_adjustment: '매크로 적합도',
  earnings_pattern: '실적 셋업',
  fundamentals: '펀더멘털',
  macro_event: '거시 충격',
  portfolio_risk: '포트폴리오 리스크',
  peer_rank: '피어 랭크',
}

const FACTOR_GROUPS: Record<string, string> = {
  valuation: '밸류',
  momentum: '모멘텀',
  catalyst_recency: '촉매',
  signal_track_record: '시그널',
  news_tone: '뉴스',
  regime_adjustment: '매크로',
  earnings_pattern: '실적',
  fundamentals: '펀더멘털',
  macro_event: '거시',
  portfolio_risk: '포트폴리오',
  peer_rank: '피어 비교',
}

const COUNTER_SIGNAL_COPY: Record<string, string> = {
  valuation: '밸류 부담이 남아 상단 확장성을 제한합니다.',
  momentum: '추세 강도가 약해지면 진입 명분이 빠르게 훼손될 수 있습니다.',
  catalyst_recency: '가까운 촉매가 약하거나 이미 소화돼 추가 동력이 제한됩니다.',
  signal_track_record: '과거 유사 시그널의 재현성이 충분히 확인되지 않았습니다.',
  news_tone: '최근 뉴스 흐름이 기대를 강하게 밀어주지 못하고 있습니다.',
  regime_adjustment: '현재 시장 환경과 종목 성격의 궁합이 완전히 맞지 않습니다.',
  earnings_pattern: '실적 전후 변동성 또는 패턴 불확실성이 남아 있습니다.',
  fundamentals: '기초 체력 대비 기대가 앞서 있을 수 있습니다.',
  macro_event: '최근 거시 충격 이벤트가 현재 업종에 추가 변동성 또는 역풍을 만들 수 있습니다.',
  portfolio_risk: '기존 포트폴리오 집중도가 신규 진입 매력을 깎습니다.',
  peer_rank: '동종 peer 대비 상대 우위가 충분히 강하지 않습니다.',
}

export function TraderDecisionBoard({
  actionPlan,
  latestCatalyst,
  dashboardSizing,
  targetPrice,
  tradeFrame,
  decision,
  previousDecision,
  upcomingEvents = [],
  currentPrice,
}: TraderDecisionBoardProps) {
  const entryLabel = tradeFrame?.entry_price || actionPlan.entry
  const stopLabel = tradeFrame?.stop_loss || tradeFrame?.invalidation_price || actionPlan.invalidation
  const targetLabel = [tradeFrame?.target_1, tradeFrame?.target_2].filter(Boolean).join(' / ') || targetPrice || '목표가 미확인'
  const sizingNote = tradeFrame?.position_size_note || `10,000 USD 기준 ${dashboardSizing.positionShares}`
  const riskReward = tradeFrame?.risk_reward_ratio || dashboardSizing.riskReward
  const factorEntries = Object.entries(decision?.factors ?? {})
    .sort(([, left], [, right]) => Math.abs(right) - Math.abs(left))
  const categoryTotals = factorEntries.reduce<Record<string, number>>((acc, [key, value]) => {
    const group = FACTOR_GROUPS[key] ?? '기타'
    acc[group] = (acc[group] ?? 0) + value
    return acc
  }, {})
  const categoryEntries = Object.entries(categoryTotals)
    .sort(([, left], [, right]) => Math.abs(right) - Math.abs(left))
  const convictionDelta = decision && previousDecision ? decision.conviction - previousDecision.conviction : null
  const factorDeltaEntries = factorEntries
    .map(([key, value]) => {
      const previousValue = previousDecision?.factors?.[key] ?? 0
      return {
        key,
        label: FACTOR_LABELS[key] ?? key,
        delta: value - previousValue,
      }
    })
    .filter((entry) => entry.delta !== 0)
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))
  const counterSignals = buildCounterSignals(factorEntries)
  const timelineEvents = buildTimelineEvents(upcomingEvents)
  const eventRules = buildEventRules(timelineEvents)
  const reevaluationTriggers = buildReevaluationTriggers({
    currentPrice,
    tradeFrame,
    targetPrice,
    decision,
  })

  return (
    <section className="dashboard-panel-section trader-decision-board-section">
      <div className="section-header-with-kicker">
        <div>
          <h3>의사결정 보드</h3>
          <p className="section-kicker">
            방향, 진입존, 무효화, 다음 catalyst, 2ATR 스탑, 리스크/리워드를 첫 화면에서 바로 확인합니다.
          </p>
        </div>
      </div>

      <div className="decision-board-grid">
        <div className="price-action-card">
          <span className="price-action-label">방향</span>
          <strong>{actionPlan.direction}</strong>
          <span className="price-action-subtext">{actionPlan.thesis}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">진입존</span>
          <strong>{entryLabel}</strong>
          <span className="price-action-subtext">시그널 또는 트레이드 프레임 기준</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">손절 / 무효화</span>
          <strong>{stopLabel}</strong>
          <span className="price-action-subtext">{tradeFrame?.watch_period ?? '관찰 기간 확인 필요'}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">다음 Catalyst</span>
          <strong>{actionPlan.nextCatalyst}</strong>
          <span className="price-action-subtext">{latestCatalyst?.tag ?? '공시/뉴스 모니터링'}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">포지션 사이징</span>
          <strong>{dashboardSizing.stopPrice}</strong>
          <span className="price-action-subtext">{sizingNote}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">목표가 / R:R</span>
          <strong>{riskReward}</strong>
          <span className="price-action-subtext">{targetLabel}</span>
        </div>
      </div>

      <div className="decision-board-timing-grid">
        <article className="decision-board-panel decision-board-panel-wide">
          <span className="decision-board-panel-label">D-day 타임라인</span>
          {timelineEvents.length > 0 ? (
            <>
              <div className="decision-timeline-bar">
                <div className="decision-timeline-track" />
                {timelineEvents.map((event) => (
                  <div
                    key={event.key}
                    className="decision-timeline-marker"
                    style={{ left: `${event.leftPercent}%` }}
                  >
                    <span className="decision-timeline-dot" />
                    <span className="decision-timeline-caption">{event.dayLabel}</span>
                  </div>
                ))}
              </div>
              <div className="decision-timeline-events">
                {timelineEvents.map((event) => (
                  <div key={`${event.key}-card`} className="decision-timeline-event-card">
                    <strong>{event.label}</strong>
                    <span>{event.date}{event.timing ? ` · ${event.timing}` : ''}</span>
                    <span>{event.dayLabel}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="decision-board-panel-copy">가까운 예정 이벤트가 없어 일반 일정 관리 규칙을 적용합니다.</p>
          )}
        </article>

        <article className="decision-board-panel">
          <span className="decision-board-panel-label">이벤트 직전 행동 규칙</span>
          <ul className="decision-board-list">
            {eventRules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </article>

        <article className="decision-board-panel">
          <span className="decision-board-panel-label">재평가 트리거</span>
          <strong className="decision-board-panel-value">{decision?.valid_until || '상시 재평가'}</strong>
          <ul className="decision-board-list">
            {reevaluationTriggers.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </article>
      </div>

      {decision ? (
        <div className="decision-board-analysis">
          <div className="decision-board-analysis-grid">
            <article className="decision-board-panel decision-board-panel-wide">
              <span className="decision-board-panel-label">확신도 분해</span>
              <strong className="decision-board-panel-value">{decision.conviction}점</strong>
              <div className="decision-board-category-grid">
                {categoryEntries.map(([group, value]) => (
                  <span
                    key={group}
                    className={`decision-board-category-chip ${value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral'}`}
                  >
                    {group} {value > 0 ? '+' : ''}{value.toFixed(0)}
                  </span>
                ))}
              </div>
              <div className="decision-board-factor-table" role="table" aria-label="확신도 점수표">
                <div className="decision-board-factor-row decision-board-factor-head" role="row">
                  <span role="columnheader">요소</span>
                  <span role="columnheader">구분</span>
                  <span role="columnheader">점수</span>
                </div>
                {factorEntries.map(([key, value]) => (
                  <div key={key} className="decision-board-factor-row" role="row">
                    <span role="cell">{FACTOR_LABELS[key] ?? key}</span>
                    <span role="cell">{FACTOR_GROUPS[key] ?? '기타'}</span>
                    <span
                      role="cell"
                      className={`decision-board-factor-score ${value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral'}`}
                    >
                      {value > 0 ? '+' : ''}{value.toFixed(0)}
                    </span>
                  </div>
                ))}
              </div>
            </article>

            <article className="decision-board-panel">
              <span className="decision-board-panel-label">전일 대비 델타</span>
              <strong className="decision-board-panel-value">
                {convictionDelta === null ? 'N/A' : `${decision.conviction} (${convictionDelta >= 0 ? '↑' : '↓'}${Math.abs(convictionDelta)})`}
              </strong>
              {previousDecision ? (
                <>
                  <p className="decision-board-panel-copy">전일 {previousDecision.conviction}점 대비 변화입니다.</p>
                  <ul className="decision-board-list">
                    {factorDeltaEntries.length > 0 ? factorDeltaEntries.slice(0, 3).map((entry) => (
                      <li key={entry.key}>
                        <strong>{entry.label}</strong> {entry.delta > 0 ? '+' : ''}{entry.delta.toFixed(0)}
                      </li>
                    )) : (
                      <li>주요 factor 변화는 크지 않습니다.</li>
                    )}
                  </ul>
                </>
              ) : (
                <p className="decision-board-panel-copy">직전 decision snapshot이 없어 델타를 계산하지 않았습니다.</p>
              )}
            </article>

            <article className="decision-board-panel">
              <span className="decision-board-panel-label">반대 신호 카운터</span>
              <strong className="decision-board-panel-value">{counterSignals.length}개</strong>
              <ul className="decision-board-list">
                {counterSignals.map((signal) => (
                  <li key={signal.key}>
                    <strong>{signal.label} {signal.score > 0 ? '+' : ''}{signal.score.toFixed(0)}</strong>
                    <span>{signal.reason}</span>
                  </li>
                ))}
              </ul>
            </article>
          </div>
        </div>
      ) : null}
    </section>
  )
}

function buildTimelineEvents(upcomingEvents: UpcomingEvent[]): TimelineEvent[] {
  const sorted = [...upcomingEvents]
    .map((event, index) => {
      const daysUntil = parseInt(event.days_until, 10)
      return {
        event,
        index,
        daysUntil: Number.isFinite(daysUntil) ? Math.max(daysUntil, 0) : 999,
      }
    })
    .sort((left, right) => left.daysUntil - right.daysUntil || left.index - right.index)
    .slice(0, 4)

  if (sorted.length === 0) {
    return []
  }

  const maxDay = Math.max(...sorted.map((item) => item.daysUntil), 1)
  return sorted.map(({ event, index, daysUntil }) => ({
    key: `${event.type}-${event.date}-${index}`,
    label: event.label || event.type || '이벤트',
    date: event.date || 'N/A',
    daysUntil,
    dayLabel: `D-${daysUntil}`,
    timing: event.timing || '',
    leftPercent: Math.min(100, Math.max(0, (daysUntil / maxDay) * 100)),
  }))
}

function buildEventRules(timelineEvents: TimelineEvent[]): string[] {
  if (timelineEvents.length === 0) {
    return ['예정 이벤트가 멀어 기본 진입 규칙을 유지합니다.']
  }

  const nearest = timelineEvents[0]
  const rules: string[] = []

  if (nearest.daysUntil <= 1) {
    rules.push(`${nearest.label} D-1 이내: 신규 진입보다 기존 포지션 관리 우선`)
  } else if (nearest.daysUntil <= 3) {
    rules.push(`${nearest.label} D-3 이내: 신규 진입 금지, 기존 포지션만 유지 또는 축소`)
  } else if (nearest.daysUntil <= 7) {
    rules.push(`${nearest.label} D-7 구간: 분할 진입만 허용, 추격 매수 금지`)
  } else {
    rules.push(`${nearest.label} 전까지 기준 가격대만 유지되면 계획대로 관찰`)
  }

  if (timelineEvents.some((event) => /earnings|실적/i.test(event.label) && event.daysUntil <= 7)) {
    rules.push('실적 전후 1거래일은 갭 리스크를 기본 가정하고 비중을 줄입니다.')
  }
  if (timelineEvents.some((event) => /dividend|배당/i.test(event.label) && event.daysUntil <= 3)) {
    rules.push('배당락 전후 수급 왜곡 가능성을 감안해 단기 추격 진입을 피합니다.')
  }

  return rules.slice(0, 3)
}

function buildReevaluationTriggers(params: {
  currentPrice?: string
  tradeFrame?: TradeFrame
  targetPrice?: string
  decision?: TickerDecisionData | null
}): string[] {
  const current = parsePrice(params.currentPrice ?? '')
  const upgrade = pickUpgradePrice(current, params.tradeFrame, params.targetPrice)
  const downgrade = pickDowngradePrice(current, params.tradeFrame)
  const validUntil = params.decision?.valid_until || '유효기간 만료 시점'

  const rules = [
    `유효기간 기준: ${validUntil} 도달 시 현재 시나리오를 기본 재평가합니다.`,
    upgrade
      ? `${upgrade.label} ${formatPrice(upgrade.value)} 상향 돌파 시 한 단계 긍정 시나리오로 재평가`
      : '상향 돌파 트리거는 명시된 목표가 확인 후 재설정합니다.',
    downgrade
      ? `${downgrade.label} ${formatPrice(downgrade.value)} 하향 이탈 시 방어 모드로 강등 재평가`
      : '하단 방어 트리거는 무효화 가격 확인 후 재설정합니다.',
  ]

  return rules
}

function pickUpgradePrice(current: number, tradeFrame?: TradeFrame, targetPrice?: string) {
  const candidates = [
    { label: '1차 목표가', value: parsePrice(tradeFrame?.target_1 ?? '') },
    { label: '2차 목표가', value: parsePrice(tradeFrame?.target_2 ?? '') },
    { label: '애널리스트 목표가', value: parsePrice(targetPrice ?? '') },
  ].filter((candidate) => candidate.value > 0 && candidate.value > current)

  if (candidates.length > 0) {
    return candidates.sort((left, right) => left.value - right.value)[0]
  }
  if (current > 0) {
    return { label: '단기 돌파선', value: current * 1.03 }
  }
  return null
}

function pickDowngradePrice(current: number, tradeFrame?: TradeFrame) {
  const candidates = [
    { label: '손절가', value: parsePrice(tradeFrame?.stop_loss ?? '') },
    { label: '무효화 가격', value: parsePrice(tradeFrame?.invalidation_price ?? '') },
  ].filter((candidate) => candidate.value > 0 && (current <= 0 || candidate.value < current))

  if (candidates.length > 0) {
    return candidates.sort((left, right) => right.value - left.value)[0]
  }
  if (current > 0) {
    return { label: '단기 방어선', value: current * 0.97 }
  }
  return null
}

function buildCounterSignals(factorEntries: Array<[string, number]>): CounterSignal[] {
  const weakestFirst = [...factorEntries].sort((left, right) => left[1] - right[1])
  const selected: CounterSignal[] = []
  const seen = new Set<string>()

  for (const [key, score] of weakestFirst) {
    if (seen.has(key)) continue
    if (score < 0 || selected.length === 0) {
      selected.push({
        key,
        label: FACTOR_LABELS[key] ?? key,
        score,
        reason: COUNTER_SIGNAL_COPY[key] ?? '추가 확인이 필요한 약점 요인입니다.',
      })
      seen.add(key)
    }
    if (selected.length >= 3) break
  }

  if (selected.length < 3) {
    for (const [key, score] of weakestFirst) {
      if (seen.has(key)) continue
      selected.push({
        key,
        label: FACTOR_LABELS[key] ?? key,
        score,
        reason: COUNTER_SIGNAL_COPY[key] ?? '추가 확인이 필요한 약점 요인입니다.',
      })
      seen.add(key)
      if (selected.length >= 3) break
    }
  }

  return selected
}

function formatPrice(value: number): string {
  return `${value.toFixed(2)} USD`
}

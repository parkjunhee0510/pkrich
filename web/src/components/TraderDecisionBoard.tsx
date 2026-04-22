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
  valuation: '밸류 매력도',
  momentum: '가격 흐름',
  catalyst_recency: '최근 재료',
  signal_track_record: '과거 신호 성과',
  news_tone: '뉴스 분위기',
  regime_adjustment: '시장 분위기 적합도',
  earnings_pattern: '실적 흐름',
  fundamentals: '기초 체력',
  macro_event: '거시 충격',
  portfolio_risk: '포트폴리오 쏠림',
  peer_rank: '비슷한 종목 대비 위치',
}

const FACTOR_GROUPS: Record<string, string> = {
  valuation: '밸류',
  momentum: '가격 흐름',
  catalyst_recency: '재료',
  signal_track_record: '신호',
  news_tone: '뉴스',
  regime_adjustment: '시장',
  earnings_pattern: '실적',
  fundamentals: '기초 체력',
  macro_event: '거시',
  portfolio_risk: '포트폴리오',
  peer_rank: '비교 종목',
}

const COUNTER_SIGNAL_COPY: Record<string, string> = {
  valuation: '현재 가격 부담이 남아 있어 추가 상승 여력이 제한될 수 있습니다.',
  momentum: '주가 흐름이 충분히 강하지 않아 진입 명분이 약해질 수 있습니다.',
  catalyst_recency: '가까운 재료가 약하거나 이미 반영되어 새 동력이 부족할 수 있습니다.',
  signal_track_record: '비슷한 과거 신호의 성과가 충분히 좋지 않아 확신을 낮춥니다.',
  news_tone: '최근 뉴스 흐름이 기대를 강하게 뒷받침하지 못하고 있습니다.',
  regime_adjustment: '지금 시장 분위기와 이 종목의 성격이 완전히 잘 맞지는 않습니다.',
  earnings_pattern: '실적 전후 변동성이나 이익 흐름 불확실성이 남아 있습니다.',
  fundamentals: '기초 체력 대비 기대가 앞서 있을 가능성이 있습니다.',
  macro_event: '최근 거시 충격이 이 업종에 추가 변동성을 만들 수 있습니다.',
  portfolio_risk: '기존 보유 비중과 겹쳐서 새 진입 매력이 줄어들 수 있습니다.',
  peer_rank: '비슷한 종목과 비교했을 때 상대적인 강점이 충분히 뚜렷하지 않습니다.',
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
  const targetLabel = [tradeFrame?.target_1, tradeFrame?.target_2].filter(Boolean).join(' / ') || targetPrice || '목표가 확인 필요'
  const sizingNote = tradeFrame?.position_size_note || `계좌 10,000 USD 기준 ${dashboardSizing.positionShares}`
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
  const counterSignals = buildCounterSignals(factorEntries, decision?.factor_reasoning)
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
          <h3>매매 판단 요약</h3>
          <p className="section-kicker">
            지금 판단, 진입 가격대, 손절선, 다음 일정, 목표가를 한 화면에서 빠르게 확인합니다.
          </p>
        </div>
      </div>

      <div className="decision-board-grid">
        <div className="price-action-card">
          <span className="price-action-label">지금 판단</span>
          <strong>{actionPlan.direction}</strong>
          <span className="price-action-subtext">{actionPlan.thesis}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">진입 가격대</span>
          <strong>{entryLabel}</strong>
          <span className="price-action-subtext">한 번에 들어가기보다 분할 진입 기준으로 보세요.</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">손절선 / 판단 취소 가격</span>
          <strong>{stopLabel}</strong>
          <span className="price-action-subtext">{tradeFrame?.watch_period ?? '관찰 기간을 함께 확인하세요.'}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">다음 재료</span>
          <strong>{actionPlan.nextCatalyst}</strong>
          <span className="price-action-subtext">{latestCatalyst?.tag ?? '공시와 뉴스 흐름을 함께 확인 중입니다.'}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">권장 비중</span>
          <strong>{dashboardSizing.stopPrice}</strong>
          <span className="price-action-subtext">{sizingNote}</span>
        </div>
        <div className="price-action-card">
          <span className="price-action-label">목표가 / 기대 대비 위험</span>
          <strong>{riskReward}</strong>
          <span className="price-action-subtext">{targetLabel}</span>
        </div>
      </div>

      <div className="decision-board-timing-grid">
        <article className="decision-board-panel decision-board-panel-wide">
          <span className="decision-board-panel-label">다가오는 일정</span>
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
            <p className="decision-board-panel-copy">가까운 일정이 없어서 일반적인 진입 규칙을 기준으로 보면 됩니다.</p>
          )}
        </article>

        <article className="decision-board-panel">
          <span className="decision-board-panel-label">일정 전 행동 규칙</span>
          <ul className="decision-board-list">
            {eventRules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </article>

        <article className="decision-board-panel">
          <span className="decision-board-panel-label">다시 판단해야 하는 가격</span>
          <strong className="decision-board-panel-value">{decision?.valid_until || '상시 재점검'}</strong>
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
              <span className="decision-board-panel-label">전일 대비 변화</span>
              <strong className="decision-board-panel-value">
                {convictionDelta === null ? 'N/A' : `${decision.conviction} (${convictionDelta >= 0 ? '↑' : '↓'}${Math.abs(convictionDelta)})`}
              </strong>
              {previousDecision ? (
                <>
                  <p className="decision-board-panel-copy">전일 {previousDecision.conviction}점과 비교한 변화입니다.</p>
                  <ul className="decision-board-list">
                    {factorDeltaEntries.length > 0 ? factorDeltaEntries.slice(0, 3).map((entry) => (
                      <li key={entry.key}>
                        <strong>{entry.label}</strong> {entry.delta > 0 ? '+' : ''}{entry.delta.toFixed(0)}
                      </li>
                    )) : (
                      <li>주요 점수 변화는 크지 않습니다.</li>
                    )}
                  </ul>
                </>
              ) : (
                <p className="decision-board-panel-copy">직전 판단 기록이 없어 변화 폭은 아직 비교할 수 없습니다.</p>
              )}
            </article>

            <article className="decision-board-panel">
              <span className="decision-board-panel-label">발목 잡는 요소</span>
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
    return ['예정된 이벤트가 없으니 기본 진입 규칙을 우선 적용합니다.']
  }

  const nearest = timelineEvents[0]
  const rules: string[] = []

  if (nearest.daysUntil <= 1) {
    rules.push(`${nearest.label} D-1 이내: 새 진입보다 기존 비중 관리가 우선입니다.`)
  } else if (nearest.daysUntil <= 3) {
    rules.push(`${nearest.label} D-3 이내: 신규 진입은 피하고, 기존 비중만 줄이거나 유지하는 편이 안전합니다.`)
  } else if (nearest.daysUntil <= 7) {
    rules.push(`${nearest.label} D-7 구간: 분할 진입만 고려하고 추격 매수는 피하는 편이 좋습니다.`)
  } else {
    rules.push(`${nearest.label} 전까지는 기준 가격대를 지키는지 확인하며 계획대로 관찰합니다.`)
  }

  if (timelineEvents.some((event) => /earnings|실적/i.test(event.label) && event.daysUntil <= 7)) {
    rules.push('실적 전후 하루는 변동성이 커질 수 있어 비중을 보수적으로 잡는 편이 좋습니다.')
  }
  if (timelineEvents.some((event) => /dividend|배당/i.test(event.label) && event.daysUntil <= 3)) {
    rules.push('배당 전후에는 가격이 흔들릴 수 있어 짧은 추격 진입은 신중하게 보세요.')
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
    `기본 재점검 시점은 ${validUntil}입니다. 그전에도 상황이 바뀌면 다시 판단합니다.`,
    upgrade
      ? `${upgrade.label} ${formatPrice(upgrade.value)}를 넘기면 더 긍정적인 시나리오로 다시 봅니다.`
      : '상향 판단 기준 가격은 목표가가 더 구체적으로 잡히면 함께 보강됩니다.',
    downgrade
      ? `${downgrade.label} ${formatPrice(downgrade.value)} 아래로 내려가면 방어적으로 다시 판단합니다.`
      : '하단 방어 기준 가격은 손절선이 더 구체화되면 함께 보강됩니다.',
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
    return { label: '단기 돌파 기준', value: current * 1.03 }
  }
  return null
}

function pickDowngradePrice(current: number, tradeFrame?: TradeFrame) {
  const candidates = [
    { label: '손절선', value: parsePrice(tradeFrame?.stop_loss ?? '') },
    { label: '판단 취소 가격', value: parsePrice(tradeFrame?.invalidation_price ?? '') },
  ].filter((candidate) => candidate.value > 0 && (current <= 0 || candidate.value < current))

  if (candidates.length > 0) {
    return candidates.sort((left, right) => right.value - left.value)[0]
  }
  if (current > 0) {
    return { label: '단기 방어 기준', value: current * 0.97 }
  }
  return null
}

function buildCounterSignals(
  factorEntries: Array<[string, number]>,
  factorReasoning?: Record<string, string>,
): CounterSignal[] {
  const weakestFirst = [...factorEntries].sort((left, right) => left[1] - right[1])
  const selected: CounterSignal[] = []
  const seen = new Set<string>()
  const buildReason = (key: string): string => {
    const base = COUNTER_SIGNAL_COPY[key] ?? '추가 확인이 필요한 약점 요소입니다.'
    const detail = factorReasoning?.[key]?.trim()
    return detail ? `${base} ${detail}` : base
  }

  for (const [key, score] of weakestFirst) {
    if (seen.has(key)) continue
    if (score < 0 || selected.length === 0) {
      selected.push({
        key,
        label: FACTOR_LABELS[key] ?? key,
        score,
        reason: buildReason(key),
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
        reason: buildReason(key),
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

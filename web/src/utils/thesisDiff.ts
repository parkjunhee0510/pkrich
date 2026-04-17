import type { TickerAnalysisData } from '../types'

export interface ThesisDiffItem {
  key: 'decision' | 'signal' | 'trade_frame'
  label: string
  changed: boolean
  before: string
  after: string
  emphasis?: string
}

export interface ThesisDiffResult {
  changed: boolean
  headline: string
  summary: string
  changedCount: number
  items: ThesisDiffItem[]
}

export function buildThesisDiff(
  current: TickerAnalysisData,
  previous: TickerAnalysisData,
): ThesisDiffResult {
  const previousAction = formatAction(previous.decision?.action)
  const currentAction = formatAction(current.decision?.action)
  const previousConviction = typeof previous.decision?.conviction === 'number' ? previous.decision.conviction : null
  const currentConviction = typeof current.decision?.conviction === 'number' ? current.decision.conviction : null
  const convictionDelta = currentConviction !== null && previousConviction !== null
    ? currentConviction - previousConviction
    : null

  const decisionChanged = previousAction !== currentAction || convictionDelta !== 0
  const signalChanged = normalizeText(previous.signal_or_takeaway) !== normalizeText(current.signal_or_takeaway)
  const tradeFrameChanged = normalizeText(previous.trade_frame?.base_scenario) !== normalizeText(current.trade_frame?.base_scenario)

  const items: ThesisDiffItem[] = [
    {
      key: 'decision',
      label: '결정 변화',
      changed: decisionChanged,
      before: formatDecisionSummary(previousAction, previousConviction),
      after: formatDecisionSummary(currentAction, currentConviction),
      emphasis: buildDecisionEmphasis(previousAction, currentAction, convictionDelta),
    },
    {
      key: 'signal',
      label: '핵심 시그널',
      changed: signalChanged,
      before: previous.signal_or_takeaway || 'N/A',
      after: current.signal_or_takeaway || 'N/A',
      emphasis: signalChanged ? '핵심 테이크어웨이 문구가 바뀌었습니다.' : '핵심 시그널 문구는 유지됐습니다.',
    },
    {
      key: 'trade_frame',
      label: '기본 시나리오',
      changed: tradeFrameChanged,
      before: previous.trade_frame?.base_scenario || 'N/A',
      after: current.trade_frame?.base_scenario || 'N/A',
      emphasis: tradeFrameChanged ? '트레이드 기본 시나리오가 재조정됐습니다.' : '기본 시나리오는 유지됐습니다.',
    },
  ]

  const changedCount = items.filter((item) => item.changed).length
  const changed = changedCount > 0

  return {
    changed,
    changedCount,
    headline: buildHeadline(changedCount, previousAction, currentAction, convictionDelta),
    summary: buildSummary(changedCount, signalChanged, tradeFrameChanged, convictionDelta),
    items,
  }
}

function buildHeadline(
  changedCount: number,
  previousAction: string,
  currentAction: string,
  convictionDelta: number | null,
): string {
  if (previousAction !== currentAction) {
    return `판단이 ${previousAction}에서 ${currentAction}로 조정됐습니다.`
  }
  if (convictionDelta !== null && convictionDelta !== 0) {
    return `확신도가 ${Math.abs(convictionDelta)}포인트 ${convictionDelta > 0 ? '상승' : '하락'}했습니다.`
  }
  if (changedCount > 0) {
    return `티커에 대한 해석이 ${changedCount}개 축에서 바뀌었습니다.`
  }
  return '전일 대비 핵심 시각은 대체로 유지됐습니다.'
}

function buildSummary(
  changedCount: number,
  signalChanged: boolean,
  tradeFrameChanged: boolean,
  convictionDelta: number | null,
): string {
  if (changedCount === 0) {
    return '결정, 시그널, 기본 시나리오 모두 큰 변화 없이 이어지고 있습니다.'
  }

  const parts: string[] = []
  if (convictionDelta !== null && convictionDelta !== 0) {
    parts.push(`확신도는 ${convictionDelta > 0 ? '강화' : '완화'}됐습니다`)
  }
  if (signalChanged) {
    parts.push('핵심 시그널 문구가 업데이트됐습니다')
  }
  if (tradeFrameChanged) {
    parts.push('기본 시나리오가 재정렬됐습니다')
  }
  return `${parts.join(', ')}.`
}

function buildDecisionEmphasis(
  previousAction: string,
  currentAction: string,
  convictionDelta: number | null,
): string {
  if (previousAction !== currentAction) {
    return `행동 의견이 ${previousAction} -> ${currentAction}로 바뀌었습니다.`
  }
  if (convictionDelta !== null && convictionDelta !== 0) {
    return `확신도 변화: ${convictionDelta > 0 ? '+' : ''}${convictionDelta}p`
  }
  return '행동 의견과 확신도는 유지됐습니다.'
}

function formatDecisionSummary(action: string, conviction: number | null): string {
  if (conviction === null) {
    return action
  }
  return `${action} · 확신도 ${conviction}`
}

function formatAction(value?: string): string {
  if (value === 'buy') return '매수'
  if (value === 'avoid') return '회피'
  return '관찰'
}

function normalizeText(value?: string): string {
  return (value ?? '').trim().replace(/\s+/g, ' ')
}

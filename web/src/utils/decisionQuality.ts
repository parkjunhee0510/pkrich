import type { TickerAnalysisData } from '../types'

export type DecisionQualityLabel =
  | 'high quality'
  | 'watch quality'
  | 'low quality'
  | 'unknown'

export interface DecisionQuality {
  label: DecisionQualityLabel
  score: number | null
  className: string
  detail: string
  hasGate: boolean
  penalty: number | null
}

export function classifyDecisionQuality(ticker: TickerAnalysisData): DecisionQuality {
  const meta = ticker.decision?.confidence_meta
  const score = normalizeScore(meta?.data_quality_score ?? meta?.data_quality)
  const penalty = normalizeScore(meta?.confidence_penalty)
  const hasGate = meta?.data_quality_gate?.would_cap_action === true

  if (score === null) {
    return {
      label: 'unknown',
      score: null,
      className: 'today-decision-quality-unknown',
      detail: 'quality unknown',
      hasGate,
      penalty,
    }
  }

  if (score < 0.6) {
    return {
      label: 'low quality',
      score,
      className: 'today-decision-quality-low',
      detail: `quality ${score.toFixed(2)}`,
      hasGate,
      penalty,
    }
  }

  if (score < 0.8) {
    return {
      label: 'watch quality',
      score,
      className: 'today-decision-quality-watch',
      detail: `quality ${score.toFixed(2)}`,
      hasGate,
      penalty,
    }
  }

  return {
    label: 'high quality',
    score,
    className: 'today-decision-quality-high',
    detail: `quality ${score.toFixed(2)}`,
    hasGate,
    penalty,
  }
}

function normalizeScore(value: number | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

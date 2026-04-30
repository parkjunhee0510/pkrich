import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { MarketRegimeData } from '../types'
import type { SectorMoodInsight, SectorMoodResult } from '../utils/sectorMood'
import { MarketMoodSectorBriefing } from './MarketMoodSectorBriefing'

const regime: MarketRegimeData = {
  regime: 'risk_on',
  confidence: 72,
  drivers: {
    vix: 'VIX 안정',
    nasdaq: 'NASDAQ 강세',
  },
  implication: '성장 섹터 우선 확인',
  assessed_at: '2026-04-30T00:00:00Z',
}

const focusInsight: SectorMoodInsight = {
  sector: 'Semiconductors',
  sectorLabel: '반도체',
  tickerCount: 2,
  classification: 'focus',
  fitLabel: '정합 높음',
  averageDailyChange: 1.8,
  positiveTickerRatio: 1,
  topGainer: { ticker: 'NVDA', conviction: 88, dailyChange: 2.4 },
  topLoser: { ticker: 'AMD', conviction: 82, dailyChange: 1.2 },
  representativeTickers: [
    { ticker: 'NVDA', conviction: 88, dailyChange: 2.4 },
    { ticker: 'AMD', conviction: 82, dailyChange: 1.2 },
  ],
  priceFlowScore: 0.8,
  regimeFitScore: 0.7,
  tickerSignalScore: 0.8,
  eventExposureScore: 0,
  score: 0.7,
  macroEvidence: [],
  rationale: 'risk_on 분위기와 가격 흐름이 같은 방향입니다.',
}

const watchInsight: SectorMoodInsight = {
  sector: 'Utilities',
  sectorLabel: '유틸리티',
  tickerCount: 2,
  classification: 'watch',
  fitLabel: '정합 낮음',
  averageDailyChange: -0.5,
  positiveTickerRatio: 0,
  topGainer: { ticker: 'NEE', conviction: 42, dailyChange: -0.4 },
  topLoser: { ticker: 'NEE', conviction: 42, dailyChange: -0.4 },
  representativeTickers: [
    { ticker: 'NEE', conviction: 42, dailyChange: -0.4 },
  ],
  priceFlowScore: -0.4,
  regimeFitScore: -0.6,
  tickerSignalScore: 0,
  eventExposureScore: -0.5,
  score: -0.5,
  macroEvidence: [
    {
      type: 'macro',
      date: '2026-04-30',
      days_until: '0',
      label: '금리 민감 섹터 변동성 부담',
    },
  ],
  rationale: 'risk_on 분위기와 정합도가 낮아 우선순위를 낮춰 확인합니다.',
}

const sectorMood: SectorMoodResult = {
  hasSectorData: true,
  insights: [focusInsight, watchInsight],
  focus: [focusInsight],
  watch: [watchInsight],
  neutral: [],
}

function renderBriefing(result: SectorMoodResult = sectorMood) {
  return render(
    <MemoryRouter>
      <MarketMoodSectorBriefing marketRegime={regime} sectorMood={result} />
    </MemoryRouter>,
  )
}

describe('MarketMoodSectorBriefing', () => {
  it('renders regime, focus sectors, watch sectors, ticker chips, and readable rationale', () => {
    renderBriefing()

    expect(screen.getByText('오늘의 시장 해석')).toBeInTheDocument()
    expect(screen.getByText('주목 섹터')).toBeInTheDocument()
    expect(screen.getByText('주의 섹터')).toBeInTheDocument()
    expect(screen.getAllByText('반도체').length).toBeGreaterThan(0)
    expect(screen.getAllByText('유틸리티').length).toBeGreaterThan(0)

    const nvdaLink = screen.getByRole('link', { name: 'NVDA' })
    expect(nvdaLink).toHaveAttribute('href', '/ticker/NVDA')
    expect(screen.getByText(/우선순위를 낮춰 확인합니다\./)).toBeInTheDocument()
    expect(screen.getByText('금리 민감 섹터 변동성 부담')).toBeInTheDocument()
  })

  it('renders compact empty state when sector data is missing', () => {
    renderBriefing({
      hasSectorData: false,
      insights: [],
      focus: [],
      watch: [],
      neutral: [],
      emptyReason: '섹터 데이터 부족',
    })

    expect(screen.getByText('섹터 데이터 부족')).toBeInTheDocument()
    expect(screen.queryByText('매도')).not.toBeInTheDocument()
  })
})

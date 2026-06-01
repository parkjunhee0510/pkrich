import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { PortfolioCommandCenter } from './PortfolioCommandCenter'
import {
  PORTFOLIO_RISK_TERM_HELP,
  type PortfolioCommandCenterData,
} from '../utils/portfolioCommandCenter'

const commandCenterData: PortfolioCommandCenterData = {
  hasData: true,
  counts: {
    events: 1,
    swaps: 1,
    insights: 2,
  },
  queue: [
    {
      id: 'event:AMD',
      type: 'event',
      ticker: 'AMD',
      title: '실적 발표',
      summary: '실적 발표 전 변동성이 커질 수 있습니다.',
      meta: 'D-2 · 30% 비중',
      score: 92,
      severity: 'high',
      destination: '/ticker/AMD',
      termHelp: PORTFOLIO_RISK_TERM_HELP.event,
      reasons: ['실적 변동성'],
      reviewPoints: ['포지션 크기 확인'],
    },
    {
      id: 'swap:AAPL:CAT',
      type: 'swap',
      ticker: 'AAPL',
      relatedTicker: 'CAT',
      title: 'AAPL -> CAT 교체 검토',
      summary: 'AAPL 집중 완화를 위해 대체 후보를 검토합니다.',
      meta: '섹터 분산 · 점수 76',
      score: 76,
      severity: 'medium',
      destination: '/ticker/AAPL',
      termHelp: PORTFOLIO_RISK_TERM_HELP.swap,
      reasons: ['집중도 완화'],
      reviewPoints: ['AAPL 비중과 CAT 신규 비중 비교'],
    },
  ],
  insights: [
    {
      id: 'hhi',
      label: 'HHI 집중도',
      value: '3,400',
      detail: 'Technology 비중이 높습니다.',
      severity: 'high',
      termHelp: PORTFOLIO_RISK_TERM_HELP.hhi,
    },
    {
      id: 'beta',
      label: 'Portfolio Beta',
      value: '1.24',
      detail: '시장 상승과 하락에 더 크게 반응할 수 있습니다.',
      severity: 'medium',
      termHelp: PORTFOLIO_RISK_TERM_HELP.beta,
    },
  ],
}

function renderCommandCenter(data = commandCenterData) {
  return render(
    <MemoryRouter>
      <PortfolioCommandCenter data={data} asOf="2026-05-13" />
    </MemoryRouter>,
  )
}

describe('PortfolioCommandCenter', () => {
  it('renders a prioritized queue, detail links, and Korean term explanations', () => {
    renderCommandCenter()

    expect(screen.getByRole('heading', { name: 'Portfolio Command Center' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /AMD.*실적 발표/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('실적 발표 전 변동성이 커질 수 있습니다.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AMD 상세' })).toHaveAttribute('href', '/ticker/AMD')
    expect(screen.getByText('HHI 집중도')).toBeInTheDocument()
    expect(screen.getByText(PORTFOLIO_RISK_TERM_HELP.hhi)).toBeInTheDocument()
  })

  it('switches the inline detail pane without leaving the page', () => {
    renderCommandCenter()

    fireEvent.click(screen.getByRole('button', { name: /AAPL.*CAT 교체 검토/ }))

    expect(screen.getByText('AAPL 집중 완화를 위해 대체 후보를 검토합니다.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AAPL 상세' })).toHaveAttribute('href', '/ticker/AAPL')
    expect(screen.getByRole('link', { name: 'CAT 상세' })).toHaveAttribute('href', '/ticker/CAT')
  })

  it('renders nothing when command center data is empty', () => {
    const { container } = renderCommandCenter({
      hasData: false,
      counts: {
        events: 0,
        swaps: 0,
        insights: 0,
      },
      queue: [],
      insights: [],
    })

    expect(container.firstChild).toBeNull()
  })
})

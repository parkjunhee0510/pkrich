import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { RiskIntelPanel } from './RiskIntelPanel'
import type { RiskIntelGraphPayload, RiskIntelSummaryPayload } from '../types'

const summary: RiskIntelSummaryPayload = {
  schema_version: '1.0.0',
  as_of: '2026-05-19',
  status: 'ok',
  cards: [
    {
      id: 'alert:export-control-nvda-2026-05-19',
      alert_level: 'alert',
      alert_level_label_ko: '경보',
      title_ko: '경보: NVDA 리스크 경로',
      summary_ko: '수출통제 강화는 AI 칩 공급망에 부담으로 작용할 수 있습니다.',
      affected_sectors: ['sector:semiconductors'],
      affected_tickers: [
        { ticker: 'NVDA', exposure_type: 'holding', exposure_label_ko: '보유', is_holding: true },
        { ticker: 'AMD', exposure_type: 'watchlist', exposure_label_ko: '관심', is_holding: false },
      ],
      evidence_counts: { explicit: 1, inferred: 1, social: 0, market: 0 },
      top_evidence_refs: ['record:policy:event-export'],
      rationale_ko: '정책 이슈가 섹터와 종목으로 연결되어 주의가 필요합니다.',
      detail_node_id: 'issue:export-control:event-export',
      score: 0.74,
      raw_score: 0.74,
      score_kind: 'final',
    },
  ],
  counts: { cards: 1, alert_paths: 1 },
  source_tier_status: { tier2: 'skipped_not_enabled', tier3: 'skipped_not_enabled' },
  empty_states: { ko: '표시할 리스크 경로가 없습니다.' },
  generation: { run_id: 'run:2026-05-19-risk-intel' },
  derived_from_graph_run_id: 'run:2026-05-19-risk-intel',
}

const graph: RiskIntelGraphPayload = {
  schema_version: '1.0.0',
  as_of: '2026-05-19',
  status: 'ok',
  generation: { run_id: 'run:2026-05-19-risk-intel' },
  nodes: [
    { id: 'issue:export-control:event-export', node_type: 'issue', label_ko: '수출통제 강화', label: 'Export control' },
    { id: 'sector:semiconductors', node_type: 'sector', label_ko: '반도체', label: 'Semiconductors' },
    { id: 'ticker:NVDA', node_type: 'ticker', label_ko: 'NVDA', label: 'NVDA' },
  ],
  edges: [
    {
      id: 'edge:issue:export-control:event-export:sector:semiconductors',
      source_id: 'issue:export-control:event-export',
      target_id: 'sector:semiconductors',
      relationship_label_ko: '영향 가능',
      evidence_type: 'inferred',
      evidence_label_ko: '도메인 추론',
      confidence: 0.72,
      severity_delta: -0.6,
      evidence_refs: ['record:policy:event-export'],
      inference_refs: ['rule:export-control:semiconductors:v1'],
      explanation_ko: '수출통제 강화는 반도체 공급망 리스크로 이어질 수 있습니다.',
    },
    {
      id: 'edge:sector:semiconductors:ticker:NVDA',
      source_id: 'sector:semiconductors',
      target_id: 'ticker:NVDA',
      relationship_label_ko: '노출',
      evidence_type: 'explicit',
      evidence_label_ko: '명시 근거',
      confidence: 0.87,
      severity_delta: -0.6,
      evidence_refs: ['record:policy:event-export'],
      inference_refs: [],
      explanation_ko: 'NVDA는 반도체 섹터 노출로 연결됩니다.',
    },
  ],
  alert_paths: [
    {
      id: 'alert:export-control-nvda-2026-05-19',
      canonical_issue_id: 'issue:export-control:event-export',
      target_group_type: 'ticker',
      target_group_id: 'ticker:NVDA',
      alert_level: 'alert',
      alert_level_label_ko: '경보',
      path_node_ids: ['issue:export-control:event-export', 'sector:semiconductors', 'ticker:NVDA'],
      path_edge_ids: [
        'edge:issue:export-control:event-export:sector:semiconductors',
        'edge:sector:semiconductors:ticker:NVDA',
      ],
      affected_sector_ids: ['sector:semiconductors'],
      affected_ticker_ids: ['ticker:NVDA'],
      representative_target_id: 'ticker:NVDA',
      raw_score: 0.74,
      score: 0.74,
      score_kind: 'final',
      caps_applied: [],
      guardrails_applied: ['alert_requires_evidence_refs'],
      top_evidence_refs: ['record:policy:event-export'],
      rationale_ko: '정책 이슈가 섹터와 종목으로 연결되어 주의가 필요합니다.',
    },
  ],
  health_warnings: [],
}

describe('RiskIntelPanel', () => {
  it('renders Korean risk cards and a network map', () => {
    render(
      <MemoryRouter>
        <RiskIntelPanel summary={summary} graph={graph} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '리스크 인텔리전스' })).toBeInTheDocument()
    expect(screen.getByText('경보: NVDA 리스크 경로')).toBeInTheDocument()
    expect(screen.getByText('수출통제 강화는 AI 칩 공급망에 부담으로 작용할 수 있습니다.')).toBeInTheDocument()
    expect(screen.getByText('가중 점수 0.74')).toBeInTheDocument()

    const tickerList = screen.getByLabelText('영향 종목')
    expect(within(tickerList).getByRole('link', { name: 'NVDA' })).toBeInTheDocument()
    expect(within(tickerList).getByText('보유')).toBeInTheDocument()
    expect(within(tickerList).getByRole('link', { name: 'AMD' })).toBeInTheDocument()
    expect(within(tickerList).getByText('관심')).toBeInTheDocument()

    expect(screen.getByLabelText('리스크 전파 네트워크')).toBeInTheDocument()
    expect(screen.getByText('수출통제 강화')).toBeInTheDocument()
    expect(screen.getByText('반도체')).toBeInTheDocument()
  })

  it('renders an empty state without failing when cards are missing', () => {
    render(
      <MemoryRouter>
        <RiskIntelPanel
          summary={{ ...summary, cards: [], counts: { cards: 0, alert_paths: 0 } }}
          graph={{ ...graph, nodes: [], edges: [], alert_paths: [] }}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('표시할 리스크 경로가 없습니다.')).toBeInTheDocument()
  })
})

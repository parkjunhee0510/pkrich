import { Link } from 'react-router-dom'

import type { MacroContext, MarketRegimeData, TickerAnalysisData } from '../types'
import {
  deriveSectorMoodInsights,
  formatSectorPercent,
  type SectorMoodClassification,
  type SectorMoodInsight,
  type SectorMoodResult,
} from '../utils/sectorMood'

interface MarketMoodSectorBriefingProps {
  marketRegime?: MarketRegimeData | null
  macroContext?: MacroContext | null
  tickers?: TickerAnalysisData[]
  sectorMood?: SectorMoodResult
}

const REGIME_LABELS: Record<MarketRegimeData['regime'], string> = {
  risk_on: '공격적으로 보기 좋은 흐름',
  neutral: '중립 흐름',
  risk_off: '조심스럽게 봐야 하는 흐름',
  reflation: '리플레이션 구간',
  defensive_bias: '방어적 흐름',
}

const CLASSIFICATION_LABELS: Record<SectorMoodClassification, string> = {
  focus: '주목',
  watch: '주의',
  neutral: '중립',
}

function getRegimeLabel(marketRegime: MarketRegimeData | null | undefined): string {
  if (!marketRegime?.regime) return '시장 분위기 정보 없음'
  return REGIME_LABELS[marketRegime.regime] ?? '시장 분위기 정보 없음'
}

function getRegimeCopy(marketRegime: MarketRegimeData | null | undefined): string {
  return marketRegime?.implication
    || '섹터 흐름은 확인 가능하지만 시장 분위기 데이터가 아직 충분하지 않습니다.'
}

function collectEvidence(insights: SectorMoodInsight[]): string[] {
  const evidence = new Set<string>()

  for (const insight of insights) {
    for (const item of insight.macroEvidence) {
      const text = item.summary_ko || item.label || item.market_bias || item.description
      if (text) evidence.add(text)
    }
  }

  return [...evidence].slice(0, 3)
}

function SectorLane({
  title,
  tone,
  insights,
  emptyMessage,
}: {
  title: string
  tone: 'focus' | 'watch'
  insights: SectorMoodInsight[]
  emptyMessage: string
}) {
  return (
    <section className={`market-mood-lane market-mood-lane-${tone}`}>
      <h3>{title}</h3>
      {insights.length > 0 ? (
        <div className="market-mood-sector-list">
          {insights.map((insight) => (
            <SectorItem key={insight.sector} insight={insight} />
          ))}
        </div>
      ) : (
        <p className="market-mood-lane-empty">{emptyMessage}</p>
      )}
    </section>
  )
}

function SectorItem({ insight }: { insight: SectorMoodInsight }) {
  return (
    <article className="market-mood-sector-item">
      <div className="market-mood-sector-main">
        <div className="market-mood-sector-title-row">
          <h4>{insight.sectorLabel || insight.sector}</h4>
          <span className="market-mood-fit-pill">{insight.fitLabel}</span>
        </div>
        <p>{insight.rationale}</p>
        <div className="market-mood-ticker-row">
          {insight.representativeTickers.map((ticker) => (
            <Link
              key={ticker.ticker}
              className="market-mood-ticker-chip"
              to={`/ticker/${ticker.ticker}`}
            >
              {ticker.ticker}
            </Link>
          ))}
        </div>
      </div>
      <div className="market-mood-sector-metric">
        <strong>{formatSectorPercent(insight.averageDailyChange)}</strong>
        <span>{insight.tickerCount}종목</span>
      </div>
    </article>
  )
}

function ComparisonPanel({ insights }: { insights: SectorMoodInsight[] }) {
  return (
    <section className="market-mood-comparison-panel">
      <h3>섹터 전체 비교</h3>
      <div className="market-mood-comparison-table">
        <div className="market-mood-comparison-row market-mood-comparison-head">
          <span>섹터</span>
          <span>등락</span>
          <span>판정</span>
          <span>대표 종목</span>
        </div>
        {insights.map((insight) => (
          <div key={insight.sector} className="market-mood-comparison-row">
            <span>{insight.sectorLabel || insight.sector}</span>
            <span>{formatSectorPercent(insight.averageDailyChange)}</span>
            <span>{CLASSIFICATION_LABELS[insight.classification]}</span>
            <span>{insight.representativeTickers.map((ticker) => ticker.ticker).join(', ') || 'N/A'}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function EvidencePanel({ evidence }: { evidence: string[] }) {
  if (evidence.length === 0) return null

  return (
    <section className="market-mood-evidence-panel">
      <h3>매크로 근거</h3>
      <ul>
        {evidence.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}

export function MarketMoodSectorBriefing({
  marketRegime,
  macroContext,
  tickers = [],
  sectorMood,
}: MarketMoodSectorBriefingProps) {
  const result = sectorMood ?? deriveSectorMoodInsights({ tickers, marketRegime, macroContext })
  const driverValues = Object.values(marketRegime?.drivers ?? {}).slice(0, 4)
  const evidence = collectEvidence(result.insights)

  return (
    <section className="market-mood-sector-briefing">
      <div className="market-mood-briefing-grid">
        <section className="market-mood-regime-card">
          <span className="market-mood-eyebrow">오늘의 시장 해석</span>
          <div className="market-mood-regime-row">
            <h2>{getRegimeLabel(marketRegime)}</h2>
            {marketRegime?.confidence !== undefined ? (
              <span className="market-mood-confidence">신뢰도 {marketRegime.confidence}%</span>
            ) : null}
          </div>
          <p className="market-mood-regime-copy">{getRegimeCopy(marketRegime)}</p>
          {driverValues.length > 0 ? (
            <div className="market-mood-driver-row">
              {driverValues.map((driver) => (
                <span key={driver} className="market-mood-driver-chip">
                  {driver}
                </span>
              ))}
            </div>
          ) : null}
        </section>

        {!result.hasSectorData ? (
          <div className="market-mood-empty">
            {result.emptyReason ?? '섹터 데이터 부족'}
          </div>
        ) : (
          <>
            <div className="market-mood-lanes">
              <SectorLane
                title="주목 섹터"
                tone="focus"
                insights={result.focus}
                emptyMessage="강하게 주목할 섹터가 아직 선별되지 않았습니다."
              />
              <SectorLane
                title="주의 섹터"
                tone="watch"
                insights={result.watch}
                emptyMessage="뚜렷한 주의 섹터가 없습니다."
              />
            </div>
            <div className="market-mood-support-grid">
              <ComparisonPanel insights={result.insights} />
              <EvidencePanel evidence={evidence} />
            </div>
          </>
        )}
      </div>
    </section>
  )
}

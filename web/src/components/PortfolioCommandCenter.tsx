import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { InfoTooltip } from './InfoTooltip'
import type {
  PortfolioCommandCenterData,
  PortfolioCommandQueueItem,
  PortfolioCommandQueueType,
  PortfolioCommandSeverity,
  PortfolioRiskInsight,
} from '../utils/portfolioCommandCenter'

type PortfolioCommandCenterProps = {
  data: PortfolioCommandCenterData
  asOf?: string
}

const TYPE_LABELS: Record<PortfolioCommandQueueType, string> = {
  event: '이벤트',
  swap: '교체',
  concentration: '집중',
  correlation: '상관',
}

const SEVERITY_LABELS: Record<PortfolioCommandSeverity, string> = {
  high: '높음',
  medium: '중간',
  low: '낮음',
}

export function PortfolioCommandCenter({ data, asOf }: PortfolioCommandCenterProps) {
  const [selectedId, setSelectedId] = useState(data.queue[0]?.id ?? '')
  const selectedItem = useMemo(
    () => data.queue.find((item) => item.id === selectedId) ?? data.queue[0] ?? null,
    [data.queue, selectedId],
  )

  if (!data.hasData) {
    return null
  }

  return (
    <section className="portfolio-command-center" aria-labelledby="portfolio-command-center-title">
      <div className="section-header-with-kicker">
        <div>
          <h3 id="portfolio-command-center-title">Portfolio Command Center</h3>
          <p className="section-kicker">
            오늘 점검할 보유 종목과 리스크 지표를 한 화면에서 정리합니다.
            {asOf ? ` 기준일 ${asOf}.` : ''}
          </p>
        </div>
        <div className="portfolio-command-counts" aria-label="Command Center 요약">
          <span>{data.counts.events} 이벤트</span>
          <span>{data.counts.swaps} 교체 후보</span>
          <span>{data.counts.insights} 리스크</span>
        </div>
      </div>

      <div className="portfolio-command-layout">
        <div className="portfolio-command-queue-panel">
          <div className="portfolio-command-panel-head">
            <h4>오늘 점검 큐</h4>
            <span>{data.queue.length}건</span>
          </div>

          {data.queue.length > 0 ? (
            <div className="portfolio-command-queue" role="list">
              {data.queue.map((item) => (
                <QueueButton
                  key={item.id}
                  item={item}
                  selected={item.id === selectedItem?.id}
                  onSelect={() => setSelectedId(item.id)}
                />
              ))}
            </div>
          ) : (
            <p className="dashboard-priority-empty">오늘 우선 점검할 보유 종목은 없습니다.</p>
          )}
        </div>

        <div className="portfolio-command-detail-panel">
          {selectedItem ? <QueueDetail item={selectedItem} /> : <EmptyDetail />}
        </div>

        <div className="portfolio-command-risk-panel">
          <div className="portfolio-command-panel-head">
            <h4>리스크 해석</h4>
            <span>{data.insights.length}개</span>
          </div>

          {data.insights.length > 0 ? (
            <div className="portfolio-command-risk-grid">
              {data.insights.map((insight) => (
                <RiskInsightCard key={insight.id} insight={insight} />
              ))}
            </div>
          ) : (
            <p className="dashboard-priority-empty">표시할 리스크 지표가 아직 없습니다.</p>
          )}
        </div>
      </div>
    </section>
  )
}

function QueueButton({
  item,
  selected,
  onSelect,
}: {
  item: PortfolioCommandQueueItem
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`portfolio-command-queue-item severity-${item.severity} ${selected ? 'active' : ''}`.trim()}
      aria-pressed={selected}
      aria-label={`${item.ticker} ${item.title} ${item.meta} 점수 ${formatScore(item.score)}`}
      onClick={onSelect}
    >
      <span className="portfolio-command-queue-topline">
        <span className="portfolio-command-type">{TYPE_LABELS[item.type]}</span>
        <strong>{item.ticker}</strong>
        {item.relatedTicker ? <span>{item.relatedTicker}</span> : null}
      </span>
      <span className="portfolio-command-title">{item.title}</span>
      <span className="portfolio-command-meta">{item.meta}</span>
    </button>
  )
}

function QueueDetail({ item }: { item: PortfolioCommandQueueItem }) {
  return (
    <article className={`portfolio-command-detail severity-${item.severity}`}>
      <div className="portfolio-command-detail-head">
        <div>
          <span className="portfolio-command-type">{TYPE_LABELS[item.type]}</span>
          <h4>{item.title}</h4>
        </div>
        <span className="portfolio-command-score">Score {formatScore(item.score)}</span>
      </div>

      <p className="portfolio-command-detail-summary">{item.summary}</p>

      <div className="portfolio-command-badges">
        <span>{item.meta}</span>
        <span>위험도 {SEVERITY_LABELS[item.severity]}</span>
        <InfoTooltip content={item.termHelp} />
      </div>

      <DetailList title="근거" items={item.reasons} />
      <DetailList title="확인할 점" items={item.reviewPoints} />

      <div className="portfolio-command-links">
        <Link to={item.destination}>{item.ticker} 상세</Link>
        {item.relatedTicker ? <Link to={`/ticker/${item.relatedTicker}`}>{item.relatedTicker} 상세</Link> : null}
      </div>
    </article>
  )
}

function RiskInsightCard({ insight }: { insight: PortfolioRiskInsight }) {
  return (
    <article className={`portfolio-command-risk-card severity-${insight.severity}`}>
      <div className="portfolio-command-risk-head">
        <span>{insight.label}</span>
        <InfoTooltip content={insight.termHelp} />
      </div>
      <strong>{insight.value}</strong>
      <p>{insight.detail}</p>
    </article>
  )
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  const visibleItems = items.filter(Boolean)
  if (visibleItems.length === 0) {
    return null
  }

  return (
    <div className="portfolio-command-detail-list">
      <strong>{title}</strong>
      <ul>
        {visibleItems.slice(0, 3).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function EmptyDetail() {
  return (
    <article className="portfolio-command-detail empty">
      <h4>점검 큐 없음</h4>
      <p>현재 같은 페이지에서 열어볼 우선 검토 항목이 없습니다.</p>
    </article>
  )
}

function formatScore(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

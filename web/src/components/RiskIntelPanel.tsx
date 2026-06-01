import { Link } from 'react-router-dom'
import type {
  RiskIntelAlertLevel,
  RiskIntelGraphNode,
  RiskIntelGraphPayload,
  RiskIntelSummaryCard,
  RiskIntelSummaryPayload,
} from '../types'

type RiskIntelPanelProps = {
  summary: RiskIntelSummaryPayload | null | undefined
  graph?: RiskIntelGraphPayload | null
  compact?: boolean
}

const STATUS_LABELS: Record<string, string> = {
  ok: '정상',
  partial: '부분',
  degraded: '저하',
  error: '오류',
}

const LEVEL_TONE: Record<RiskIntelAlertLevel, string> = {
  alert: 'risk-intel-level-alert',
  warning: 'risk-intel-level-warning',
  observation: 'risk-intel-level-observation',
}

export function RiskIntelPanel({ summary, graph, compact = false }: RiskIntelPanelProps) {
  const cards = summary?.cards ?? []
  const visibleCards = compact ? cards.slice(0, 3) : cards
  const emptyMessage = summary?.empty_states?.ko ?? '표시할 리스크 경로가 없습니다.'

  return (
    <section className={`risk-intel-panel${compact ? ' risk-intel-panel-compact' : ''}`} aria-labelledby="risk-intel-title">
      <div className="risk-intel-head">
        <div>
          <span className="type-eyebrow">RISK INTELLIGENCE</span>
          <h2 id="risk-intel-title">리스크 인텔리전스</h2>
          <p>정책·안보·사회 이슈가 섹터와 종목으로 전파되는 경로를 추적합니다.</p>
        </div>
        <div className="risk-intel-status-row">
          {summary ? (
            <>
              <span className={`risk-intel-status risk-intel-status-${summary.status}`}>
                {STATUS_LABELS[summary.status] ?? summary.status}
              </span>
              <span className="risk-intel-meta">{summary.as_of}</span>
              <span className="risk-intel-meta">경로 {summary.counts.alert_paths}개</span>
            </>
          ) : (
            <span className="risk-intel-status risk-intel-status-partial">대기</span>
          )}
          {compact ? (
            <Link to="/risk-intel" className="risk-intel-link">
              전체 네트워크 보기
            </Link>
          ) : null}
        </div>
      </div>

      {visibleCards.length > 0 ? (
        <div className="risk-intel-layout">
          <div className="risk-intel-card-list">
            {visibleCards.map((card) => (
              <RiskIntelCard key={card.id} card={card} />
            ))}
          </div>
          {!compact ? <RiskIntelNetworkMap graph={graph} /> : null}
        </div>
      ) : (
        <div className="risk-intel-empty">{emptyMessage}</div>
      )}
    </section>
  )
}

function RiskIntelCard({ card }: { card: RiskIntelSummaryCard }) {
  const levelTone = LEVEL_TONE[card.alert_level] ?? LEVEL_TONE.observation
  const score = typeof card.score === 'number' ? card.score : null
  const evidenceTotal = Object.values(card.evidence_counts ?? {}).reduce((sum, count) => sum + Number(count || 0), 0)

  return (
    <article className={`risk-intel-card ${levelTone}`}>
      <div className="risk-intel-card-meta">
        <span className="risk-intel-level-badge">{card.alert_level_label_ko}</span>
        {score !== null ? <span className="risk-intel-score">가중 점수 {score.toFixed(2)}</span> : null}
        <span className="risk-intel-evidence">근거 {evidenceTotal}개</span>
      </div>
      <h3>{card.title_ko}</h3>
      <p>{card.summary_ko}</p>
      <div className="risk-intel-chip-row" aria-label="영향 종목">
        {card.affected_tickers.map((ticker) => (
          <span
            key={`${card.id}-${ticker.ticker}-${ticker.exposure_type}`}
            className={`risk-intel-ticker-chip ${ticker.is_holding ? 'is-holding' : 'is-watchlist'}`}
          >
            <Link to={`/ticker/${ticker.ticker}`}>{ticker.ticker}</Link>
            <span>{ticker.exposure_label_ko}</span>
          </span>
        ))}
      </div>
      {card.affected_sectors.length > 0 ? (
        <div className="risk-intel-sector-row">
          {card.affected_sectors.map((sector) => (
            <span key={`${card.id}-${sector}`}>{cleanNodeLabel(sector)}</span>
          ))}
        </div>
      ) : null}
      {card.caps_applied && card.caps_applied.length > 0 ? (
        <p className="risk-intel-cap-note">상한 적용: {card.caps_applied.join(', ')}</p>
      ) : null}
    </article>
  )
}

function RiskIntelNetworkMap({ graph }: { graph?: RiskIntelGraphPayload | null }) {
  const path = graph?.alert_paths?.[0]
  const pathNodeIds = path?.path_node_ids ?? graph?.nodes?.slice(0, 4).map((node) => node.id) ?? []
  const nodes = pathNodeIds
    .map((nodeId) => graph?.nodes.find((node) => node.id === nodeId))
    .filter((node): node is RiskIntelGraphNode => Boolean(node))
  const nodeIdSet = new Set(nodes.map((node) => node.id))
  const edges = (graph?.edges ?? []).filter((edge) => nodeIdSet.has(edge.source_id) && nodeIdSet.has(edge.target_id))

  if (!graph || nodes.length === 0) {
    return (
      <div className="risk-intel-map-empty" aria-label="리스크 전파 네트워크">
        네트워크 경로 데이터가 아직 없습니다.
      </div>
    )
  }

  const positioned = nodes.map((node, index) => ({
    node,
    x: nodes.length === 1 ? 50 : 14 + (index * 72) / Math.max(nodes.length - 1, 1),
    y: index % 2 === 0 ? 42 : 58,
  }))

  return (
    <div className="risk-intel-map-shell">
      <div className="risk-intel-map-head">
        <strong>전파 네트워크</strong>
        <span>{graph.as_of}</span>
      </div>
      <svg className="risk-intel-map" viewBox="0 0 100 78" role="img" aria-label="리스크 전파 네트워크">
        <title>리스크 전파 네트워크</title>
        {edges.map((edge) => {
          const source = positioned.find((item) => item.node.id === edge.source_id)
          const target = positioned.find((item) => item.node.id === edge.target_id)
          if (!source || !target) return null
          return (
            <g key={edge.id}>
              <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} />
              <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 4}>
                {edge.relationship_label_ko ?? edge.evidence_label_ko ?? edge.evidence_type}
              </text>
            </g>
          )
        })}
        {positioned.map(({ node, x, y }) => (
          <g key={node.id} className={`risk-intel-node risk-intel-node-${node.node_type}`}>
            <circle cx={x} cy={y} r="7.5" />
            <text x={x} y={y + 18}>
              {node.label_ko || node.label || cleanNodeLabel(node.id)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

function cleanNodeLabel(value: string): string {
  const [, label = value] = value.split(':')
  return label.replace(/[-_]/g, ' ')
}

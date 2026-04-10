import type { TradeFrame } from '../types'
import type { CatalystFeedItem, PositionSizingSummary, TraderActionPlan } from '../utils/trader'

type TraderDecisionBoardProps = {
  actionPlan: TraderActionPlan
  latestCatalyst: CatalystFeedItem | null
  dashboardSizing: PositionSizingSummary
  targetPrice?: string
  tradeFrame?: TradeFrame
}

export function TraderDecisionBoard({
  actionPlan,
  latestCatalyst,
  dashboardSizing,
  targetPrice,
  tradeFrame,
}: TraderDecisionBoardProps) {
  const entryLabel = tradeFrame?.entry_price || actionPlan.entry
  const stopLabel = tradeFrame?.stop_loss || tradeFrame?.invalidation_price || actionPlan.invalidation
  const targetLabel = [tradeFrame?.target_1, tradeFrame?.target_2].filter(Boolean).join(' / ') || targetPrice || '목표가 미확인'
  const sizingNote = tradeFrame?.position_size_note || `10,000 USD 기준 ${dashboardSizing.positionShares}`
  const riskReward = tradeFrame?.risk_reward_ratio || dashboardSizing.riskReward

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
    </section>
  )
}

# Portfolio Command Center Design

## Status

Approved for implementation planning.

## Context

The current `/portfolio` page already combines portfolio summary cards, an equity curve, PM review data, portfolio risk analysis, a holdings table, and local lot editing. The latest generated data includes usable `portfolio_summary`, `portfolio_risk`, and `pm_view` payloads. The page is functionally rich, but its first screen does not yet make the daily portfolio-manager workflow obvious: which held names deserve attention first, why they matter, and which portfolio-level risks are driving the review.

This design keeps the backend output schema unchanged and improves the frontend by deriving a thin, deterministic review layer from existing data.

## Goals

- Make the first viewport answer: "What should I inspect first today?"
- Combine PM review speed with portfolio risk interpretation.
- Keep the page focused on held positions and swap candidates, not the full watchlist.
- Explain risk terms such as HHI, beta, VaR, correlation, and ATR risk in Korean.
- Preserve official `buy` / `watch` / `avoid` decisions as read-only context.
- Reuse existing `pm_view`, `portfolio_risk`, `portfolio_summary`, and ticker analysis payloads.

## Non-Goals

- No backend or output schema expansion in this phase.
- No new decision engine, factor weighting, or trading automation.
- No buy/sell/trim command language.
- No broad redesign of dashboard, ticker detail, scenario, or admin pages.
- No recomputation of official portfolio risk metrics in the frontend.

## User Experience

Add a new first-screen `Portfolio Command Center` above the current summary cards.

Desktop layout:

```text
[Portfolio Command Center]
┌───────────────────────────────┬───────────────────────────────┐
│ 오늘의 PM 점검 큐              │ 핵심 리스크 인사이트           │
│ - 이벤트 노출                  │ - HHI / 집중도                 │
│ - 교체 검토 후보              │ - 섹터 쏠림                    │
│ - 집중 리스크                  │ - 베타 / VaR                   │
│ - 고상관 리스크                │ - 다음 확인 액션               │
└───────────────────────────────┴───────────────────────────────┘

[선택된 큐 항목 상세]
[기존 손익 요약]
[P&L 차트]
[상세 PortfolioRiskPanel]
[보유 종목 테이블]
```

Mobile layout stacks in this order:

1. PM review queue
2. Risk insight list
3. Selected queue detail
4. Existing summary and risk sections

The command center should be dense, operational, and scannable. It should not look like a marketing hero or a decorative card wall. It should feel like a portfolio review console.

## Queue Scope

The review queue includes only:

- current holdings
- swap candidates related to current holdings

It should not include unrelated watchlist opportunities. The dashboard and watchlist remain the right surfaces for broad opportunity discovery.

Queue item types:

- `event`: held ticker with near-term event exposure from `pm_view.event_exposure_items`
- `swap`: held ticker and candidate pair from `pm_view.swap_candidates`
- `concentration`: large risk contributor from `portfolio_risk.positions_by_weight`
- `correlation`: high-correlation pair from `portfolio_risk.correlation_pairs`

## Derived Data Contract

Create a frontend utility at `web/src/utils/portfolioCommandCenter.ts`.

Input:

```ts
buildPortfolioCommandCenter({
  portfolioSummary,
  portfolioRisk,
  pmView,
  tickers,
})
```

Output:

```ts
{
  queueItems: PortfolioCommandQueueItem[]
  riskInsights: PortfolioRiskInsight[]
  selectedDefaultItemId: string | null
  emptyState: string | null
}
```

This utility is a review-priority formatter, not a decision engine. It must not mutate source payloads or reinterpret official decisions.

## Queue Ordering

Sort deterministically:

1. Event exposure items by descending `event_risk_score`
2. Swap candidates by descending `swap_candidate_score`
3. Concentration items by descending `weight_pct`, then `atr_risk_usd`
4. Correlation items in source order, with stable ticker-pair keys
5. Final tie-break by ticker or stable item id

Limit the visible first-screen queue to the top 5 items. Lower-priority items can remain available only if the implementation adds an explicit "show more" interaction; otherwise keep the first phase focused.

The first implementation phase will not add "show more". It will render the top 5 queue items and select the first item as `selectedDefaultItemId`.

## Risk Insights

Build `riskInsights` from existing `portfolio_risk` fields:

- HHI concentration from `hhi`
- sector concentration from `sector_exposure`
- market sensitivity from `portfolio_beta`
- daily downside estimate from `var_95`
- high-correlation pressure from `correlation_pairs`
- optional ATR risk context from `positions_by_weight` and `total_atr_risk_usd`

Risk insight copy should be action-oriented but not prescriptive. Use "확인", "비교", "점검", and "시나리오에서 확인" instead of execution language.

Examples:

- "HHI 4304.3은 집중 위험 구간입니다. 상위 포지션 기여도를 먼저 확인하세요."
- "Technology 비중이 59.6%로 가장 큽니다. AAPL, AMD, IONQ 노출을 함께 점검하세요."
- "Portfolio beta 1.32로 시장 조정 민감도가 높습니다. 시나리오 페이지에서 기술주 비중 변화를 비교할 수 있습니다."
- "고상관 종목쌍은 같은 방향으로 흔들릴 수 있습니다. 각 thesis의 약한 지점을 비교하세요."

## Term Help

Risk terms need inline help text or accessible tooltips.

Required explanations:

- HHI: "포트폴리오가 몇 개 종목에 쏠려 있는지 보는 집중도 지표입니다. 높을수록 특정 종목 영향이 큽니다."
- Beta: "시장 전체가 1% 움직일 때 포트폴리오가 얼마나 민감하게 움직이는지 보는 값입니다."
- VaR 95%: "일반적인 하루 변동 환경에서 이 정도 손실을 넘을 가능성이 5% 정도라는 추정치입니다."
- Correlation: "두 종목이 같은 방향으로 움직이는 경향입니다. 높으면 분산 효과가 약해질 수 있습니다."
- ATR risk: "최근 변동폭 기준으로 포지션이 흔들릴 수 있는 달러 리스크입니다."

The help text must be available to keyboard and screen-reader users. If the existing `InfoTooltip` supports this pattern, reuse it. Otherwise render compact inline helper text rather than hover-only explanations.

## Components

Add or extract these frontend units:

```text
Portfolio.tsx
├─ PortfolioCommandCenter
│  ├─ PortfolioReviewQueue
│  ├─ PortfolioRiskInsightList
│  └─ PortfolioQueueDetail
├─ SummaryCard grid
├─ EquityCurveChart
├─ PortfolioRiskPanel
└─ holdings table
```

`PortfolioCommandCenter` owns the selected queue item state and receives the derived command-center payload.

`PortfolioReviewQueue` renders scannable queue rows with type badges, ticker links where appropriate, score/risk labels, and short reasons.

`PortfolioRiskInsightList` renders 3-5 insight rows with term explanations and optional links to `/scenario` when a what-if comparison is useful.

`PortfolioQueueDetail` renders details for the selected queue item:

- Event: event label, D-day, risk score, reasons, review points, ticker detail link
- Swap: held ticker, candidate ticker, score, overlap context, reasons, review points, both ticker detail links
- Concentration: ticker, weight, ATR risk, sector, review copy, scenario link
- Correlation: ticker pair, correlation, warning, both ticker detail links

`PortfolioActionsReview` should be absorbed by the command center or removed after the new flow covers the same PM review information. Implementation can first add the command center and then remove the duplicate section once parity is confirmed.

## Empty And Partial States

The page must render safely with partial data.

- No portfolio: "보유 종목이 없어 PM 점검 큐를 만들 수 없습니다. 편집 모드에서 lot를 추가하면 보유 종목 기준으로 큐가 생성됩니다."
- No `pm_view`: "PM 검토 데이터가 아직 없습니다. 보유 종목 리스크와 현재 포지션 기준으로 기본 큐를 구성합니다."
- No `portfolio_risk`: "리스크 분석 데이터가 없어 손익/보유 종목 정보만 표시합니다."
- No queue items: "오늘은 우선 점검할 이벤트/교체 후보가 없습니다. 아래 포지션 테이블과 리스크 패널에서 정기 점검을 이어갈 수 있습니다."

If `pm_view` is missing but `portfolio_risk.positions_by_weight` exists, still build concentration queue items. If `portfolio_risk` is missing, preserve the existing summary cards and holdings table.

## Styling

Use existing portfolio and dashboard visual language:

- dense operational panels
- 8px-or-less radius if radius is used
- no nested card-in-card layouts
- no oversized hero treatment
- no decorative gradient/orb backgrounds
- stable dimensions for queue rows, insight rows, and badges
- responsive 2-column to 1-column layout

Long Korean and English text must wrap cleanly in queue rows, badges, and detail panels.

## Testing

Utility tests for `portfolioCommandCenter` should cover:

- event queue creation and score ordering
- swap candidate queue creation with held and candidate ticker references
- concentration queue creation from `positions_by_weight`
- correlation queue creation from `correlation_pairs`
- HHI, beta, VaR, sector exposure, correlation, and ATR risk insight generation
- required term explanations
- safe fallback when `pm_view`, `portfolio_risk`, or `portfolio_summary` is missing
- deterministic tie-break behavior

Component tests should cover:

- `PortfolioCommandCenter` renders queue and risk insights
- clicking a queue item changes the detail panel
- event, swap, concentration, and correlation detail links render correctly
- term explanations are visible or accessible
- empty states render without null crashes

Verification commands during implementation:

```bash
cd web && npm test -- --run
cd web && npm run build
python -m compileall main.py src tests
```

If layout changes are significant, also verify `/portfolio` in the browser at desktop and mobile widths.

## Documentation Updates

When implemented, update `docs/ui-ux-structure.md` to describe the command center as the first portfolio-page surface. If new data assumptions are added, update `docs/output.md`; this design intentionally avoids that for the first implementation phase.

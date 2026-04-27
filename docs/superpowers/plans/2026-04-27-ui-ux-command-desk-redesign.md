# UI/UX Command Desk Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cozy premium command-desk first screen that puts today's PM/trader action queue above the existing dashboard detail surfaces.

**Architecture:** Keep `Dashboard` as the data-loading page and add presentation-only command-desk components. Move command queue mapping into a focused utility so the component stays small and the fallback behavior is testable by TypeScript compilation. Reuse current `cozy.css` tokens with explicit `cozy-premium-command-*` classes.

**Tech Stack:** React 19, TypeScript, Vite, React Router, existing `useDashboardData()`, existing `cozy.css` token override layer.

---

## File Structure

- Create: `web/src/utils/commandDesk.ts`
- Responsibility: Convert existing `DailyEntry`, `PMPriorityQueueItem`, and ticker data into UI-ready command queue and workspace card models. No React, no DOM, no fetching.

- Create: `web/src/components/DailyCommandQueue.tsx`
- Responsibility: Render command hero, action cards, workspace cards, and empty state using models from `commandDesk.ts`.

- Modify: `web/src/pages/Dashboard.tsx`
- Responsibility: Import the new component, build the command-desk model from already-loaded data, place it above the existing quick bar and detail panels, and remove the older duplicated PM queue/priority hero from the top path.

- Modify: `web/src/styles/cozy.css`
- Responsibility: Add an isolated `Cozy Premium Command Desk` CSS section using existing cozy tokens.

- Modify: `docs/superpowers/specs/2026-04-27-ui-ux-command-desk-redesign-design.md`
- Responsibility: Add a short implementation note only if the implementation deviates from this plan. If implementation follows this plan exactly, do not edit the spec.

---

### Task 1: Add Command Desk Mapping Utility

**Files:**
- Create: `web/src/utils/commandDesk.ts`
- Verify: `web/src/types/index.ts`

- [ ] **Step 1: Create `web/src/utils/commandDesk.ts` with UI model types and builders**

Use `apply_patch` to add the file with this complete content:

```ts
import type { DailyEntry, PMPriorityQueueItem, TickerAnalysisData } from '../types'
import { computeSetupScore, getLatestCatalystItem, getNextEarningsEvent } from './trader'

export type CommandQueueTone = 'urgent' | 'watch' | 'info' | 'quiet'
export type CommandQueueSource = 'pm' | 'fallback'
export type CommandWorkspaceTone = 'pm' | 'trader' | 'market' | 'system'

export interface CommandQueueItem {
  id: string
  title: string
  typeLabel: string
  ticker?: string
  relatedTicker?: string
  score?: number
  summary: string
  reasons: string[]
  destination: string
  tone: CommandQueueTone
  source: CommandQueueSource
}

export interface CommandQueueCounts {
  urgent: number
  watch: number
  info: number
}

export interface CommandWorkspaceCardModel {
  id: 'pm' | 'trader' | 'market' | 'system'
  title: string
  eyebrow: string
  summary: string
  metric: string
  href: string
  tone: CommandWorkspaceTone
  disabled?: boolean
}

export interface CommandDeskModel {
  asOf: string
  marketLabel: string
  queueItems: CommandQueueItem[]
  counts: CommandQueueCounts
  workspaces: CommandWorkspaceCardModel[]
  emptyTitle: string
  emptyBody: string
}

export function buildCommandDeskModel(day: DailyEntry, sortedTickers: TickerAnalysisData[]): CommandDeskModel {
  const queueItems = buildCommandQueueItems(day, sortedTickers)
  return {
    asOf: day.pm_view?.as_of || day.date,
    marketLabel: buildMarketLabel(day),
    queueItems,
    counts: countQueueItems(queueItems),
    workspaces: buildWorkspaceCards(day, sortedTickers),
    emptyTitle: '오늘 바로 처리할 우선순위가 없습니다.',
    emptyBody: '보유 리스크, 실적 일정, 강한 재료가 조용한 날입니다. 워치리스트와 시스템 상태를 가볍게 확인하세요.',
  }
}

export function buildCommandQueueItems(day: DailyEntry, sortedTickers: TickerAnalysisData[]): CommandQueueItem[] {
  const pmItems = (day.pm_view?.today_priority_queue ?? []).slice(0, 6).map(mapPmPriorityItem)
  if (pmItems.length > 0) {
    return pmItems
  }
  return buildFallbackQueueItems(sortedTickers)
}

function mapPmPriorityItem(item: PMPriorityQueueItem, index: number): CommandQueueItem {
  return {
    id: `pm-${item.priority_type}-${item.ticker}-${item.related_ticker ?? 'none'}-${index}`,
    title: formatQueueTitle(item),
    typeLabel: priorityLabel(item.priority_type),
    ticker: item.ticker,
    relatedTicker: item.related_ticker ?? undefined,
    score: item.today_priority_score,
    summary: item.summary,
    reasons: item.reasons.filter(Boolean).slice(0, 3),
    destination: normalizeDestination(item.destination, item.ticker),
    tone: priorityTone(item.priority_type, item.today_priority_score),
    source: 'pm',
  }
}

function buildFallbackQueueItems(sortedTickers: TickerAnalysisData[]): CommandQueueItem[] {
  return sortedTickers
    .map((ticker) => {
      const setup = computeSetupScore(ticker)
      const catalyst = getLatestCatalystItem(ticker)
      const earnings = getNextEarningsEvent(ticker)
      const earningsDays = parseEventDays(earnings?.days_until)
      const isUrgent = catalyst?.level === 'hard' || (Number.isFinite(earningsDays) && earningsDays <= 3)
      const isWatch = setup.score >= 60 || catalyst?.level === 'medium' || (Number.isFinite(earningsDays) && earningsDays <= 7)

      if (!isUrgent && !isWatch) {
        return null
      }

      const reasons = [
        catalyst ? `${catalyst.tag} · ${catalyst.source}` : '',
        earnings ? `${earnings.label} D-${earnings.days_until}${earnings.timing ? ` · ${earnings.timing}` : ''}` : '',
        setup.tags.slice(0, 2).join(' · '),
      ].filter(Boolean)

      return {
        id: `fallback-${ticker.ticker}`,
        title: `${ticker.ticker} 확인`,
        typeLabel: isUrgent ? '긴급 확인' : '관찰 우선',
        ticker: ticker.ticker,
        score: ticker.decision?.conviction ?? setup.score,
        summary: ticker.signal_or_takeaway || ticker.summary || '오늘 신호를 다시 확인하세요.',
        reasons,
        destination: `/ticker/${ticker.ticker}`,
        tone: isUrgent ? 'urgent' : 'watch',
        source: 'fallback',
      } satisfies CommandQueueItem
    })
    .filter((item): item is CommandQueueItem => item !== null)
    .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))
    .slice(0, 6)
}

function buildWorkspaceCards(day: DailyEntry, sortedTickers: TickerAnalysisData[]): CommandWorkspaceCardModel[] {
  const pmView = day.pm_view
  const pmCount =
    (pmView?.swap_candidates?.length ?? 0) +
    (pmView?.event_exposure_items?.length ?? 0) +
    (pmView?.today_priority_queue?.length ?? 0)
  const topSetup = sortedTickers[0]
  const hardCatalysts = day.tickers.filter((ticker) => getLatestCatalystItem(ticker)?.level === 'hard').length
  const earningsSoon = day.tickers.filter((ticker) => {
    const days = parseEventDays(getNextEarningsEvent(ticker)?.days_until)
    return Number.isFinite(days) && days <= 7
  }).length
  const marketRegime = day.market_regime?.regime || '시장 상태 대기'
  const overviewCount = day.market_overview?.length ?? 0

  return [
    {
      id: 'pm',
      title: 'PM Review',
      eyebrow: '보유 리스크',
      summary: pmCount > 0 ? '교체 후보, 이벤트 노출, PM 우선순위를 확인합니다.' : '오늘 PM 전용 경고는 조용합니다.',
      metric: pmCount > 0 ? `${pmCount}건` : '안정',
      href: '/portfolio',
      tone: 'pm',
    },
    {
      id: 'trader',
      title: 'Trader Setups',
      eyebrow: '진입 후보',
      summary: topSetup ? `${topSetup.ticker} 중심으로 강한 재료와 실적 임박 후보를 봅니다.` : '표시할 트레이더 후보가 없습니다.',
      metric: `${hardCatalysts} hard · ${earningsSoon} D-7`,
      href: '#watchlist',
      tone: 'trader',
      disabled: !topSetup,
    },
    {
      id: 'market',
      title: 'Market Context',
      eyebrow: '장세 맥락',
      summary: day.market_regime?.implication || '매크로, 섹터, 시장 지표를 함께 확인합니다.',
      metric: marketRegime,
      href: '#market-context',
      tone: 'market',
      disabled: !day.market_regime && overviewCount === 0,
    },
    {
      id: 'system',
      title: 'System Health',
      eyebrow: '운영 상태',
      summary: 'API 상태, 품질, 비용, 백테스트 화면으로 이동합니다.',
      metric: 'Ops',
      href: '/api-status',
      tone: 'system',
    },
  ]
}

function countQueueItems(items: CommandQueueItem[]): CommandQueueCounts {
  return items.reduce(
    (counts, item) => {
      if (item.tone === 'urgent') counts.urgent += 1
      else if (item.tone === 'watch') counts.watch += 1
      else counts.info += 1
      return counts
    },
    { urgent: 0, watch: 0, info: 0 },
  )
}

function buildMarketLabel(day: DailyEntry): string {
  if (day.market_regime?.regime) {
    return day.market_regime.regime
  }
  const firstOverview = day.market_overview?.[0]
  if (firstOverview) {
    return `${firstOverview.label} ${firstOverview.change}`
  }
  return '시장 맥락 대기'
}

function formatQueueTitle(item: PMPriorityQueueItem): string {
  if (item.related_ticker) {
    return `${item.ticker} ↔ ${item.related_ticker}`
  }
  return `${item.ticker} 확인`
}

function priorityLabel(priorityType: string): string {
  if (priorityType === 'swap_review') return '교체 검토'
  if (priorityType === 'event_review') return '이벤트 점검'
  if (priorityType === 'decision_change') return '판단 변화'
  if (priorityType === 'risk_warning') return '리스크 점검'
  return '오늘 확인'
}

function priorityTone(priorityType: string, score: number): CommandQueueTone {
  if (priorityType === 'event_review' || priorityType === 'risk_warning' || score >= 80) {
    return 'urgent'
  }
  if (priorityType === 'swap_review' || score >= 60) {
    return 'watch'
  }
  return 'info'
}

function normalizeDestination(destination: string, ticker: string): string {
  if (destination.startsWith('/')) return destination
  if (destination === 'portfolio') return '/portfolio'
  return `/ticker/${ticker}`
}

function parseEventDays(value?: string): number {
  if (!value) return Number.POSITIVE_INFINITY
  const parsed = Number.parseInt(value, 10)
  return Number.isNaN(parsed) ? Number.POSITIVE_INFINITY : parsed
}
```

- [ ] **Step 2: Run TypeScript build to verify the new utility compiles**

Run:

```powershell
cd web
npm run build
```

Expected: `tsc -b` and `vite build` complete without TypeScript errors. If Vite asset output changes under `web/dist`, do not commit `web/dist` unless the repository already tracks a required dist change for this branch.

- [ ] **Step 3: Commit the utility**

Run:

```powershell
git add web/src/utils/commandDesk.ts
git commit -m "feat: add command desk data model"
```

---

### Task 2: Add Daily Command Queue Components

**Files:**
- Create: `web/src/components/DailyCommandQueue.tsx`
- Depends on: `web/src/utils/commandDesk.ts`

- [ ] **Step 1: Create `web/src/components/DailyCommandQueue.tsx`**

Use `apply_patch` to add the file with this complete content:

```tsx
import { Link } from 'react-router-dom'
import type { CommandDeskModel, CommandQueueItem, CommandWorkspaceCardModel } from '../utils/commandDesk'

type DailyCommandQueueProps = {
  model: CommandDeskModel
}

export function DailyCommandQueue({ model }: DailyCommandQueueProps) {
  const hasQueue = model.queueItems.length > 0

  return (
    <section className="cozy-premium-command-desk" aria-labelledby="command-desk-title">
      <div className="cozy-premium-command-hero">
        <div className="cozy-premium-command-copy">
          <span className="cozy-eyebrow">
            <span className={`dot ${model.counts.urgent > 0 ? 'bad' : model.counts.watch > 0 ? 'warn' : ''}`} />
            Daily Command Queue
          </span>
          <h2 id="command-desk-title" className="cozy-headline">
            오늘 먼저 볼 일만 정리했습니다.
          </h2>
          <p className="cozy-impl">
            {model.asOf} 기준 · {model.marketLabel}
          </p>
          <div className="cozy-premium-command-counts" aria-label="오늘 우선순위 요약">
            <span>
              <b>{model.counts.urgent}</b>
              긴급
            </span>
            <span>
              <b>{model.counts.watch}</b>
              관찰
            </span>
            <span>
              <b>{model.counts.info}</b>
              참고
            </span>
          </div>
        </div>

        <div className="cozy-premium-command-panel">
          <div className="cozy-premium-command-panel-head">
            <span>Action Queue</span>
            <strong>{hasQueue ? `${model.queueItems.length}건` : 'Quiet'}</strong>
          </div>

          {hasQueue ? (
            <div className="cozy-premium-action-list">
              {model.queueItems.map((item) => (
                <CommandActionCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <CommandEmptyState title={model.emptyTitle} body={model.emptyBody} />
          )}
        </div>
      </div>

      <CommandWorkspaceGrid cards={model.workspaces} />
    </section>
  )
}

function CommandActionCard({ item }: { item: CommandQueueItem }) {
  return (
    <article className={`cozy-premium-action-card tone-${item.tone}`}>
      <div className="cozy-premium-action-card-main">
        <div>
          <span className="cozy-premium-action-type">{item.typeLabel}</span>
          <h3>{item.title}</h3>
        </div>
        {typeof item.score === 'number' ? <strong className="cozy-premium-action-score">{Math.round(item.score)}점</strong> : null}
      </div>
      <p>{item.summary}</p>
      {item.reasons.length > 0 ? (
        <ul>
          {item.reasons.map((reason) => (
            <li key={`${item.id}-${reason}`}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <Link className="cozy-premium-action-link" to={item.destination}>
        {item.ticker ? `${item.ticker} 확인하기` : '자세히 보기'}
      </Link>
    </article>
  )
}

function CommandWorkspaceGrid({ cards }: { cards: CommandWorkspaceCardModel[] }) {
  return (
    <div className="cozy-premium-workspace-grid" aria-label="워크스페이스 바로가기">
      {cards.map((card) => (
        <CommandWorkspaceCard key={card.id} card={card} />
      ))}
    </div>
  )
}

function CommandWorkspaceCard({ card }: { card: CommandWorkspaceCardModel }) {
  const content = (
    <>
      <span className="cozy-premium-workspace-eyebrow">{card.eyebrow}</span>
      <div className="cozy-premium-workspace-title-row">
        <h3>{card.title}</h3>
        <strong>{card.metric}</strong>
      </div>
      <p>{card.summary}</p>
    </>
  )

  if (card.disabled) {
    return <article className={`cozy-premium-workspace-card tone-${card.tone} is-disabled`}>{content}</article>
  }

  if (card.href.startsWith('#')) {
    return (
      <a className={`cozy-premium-workspace-card tone-${card.tone}`} href={card.href}>
        {content}
      </a>
    )
  }

  return (
    <Link className={`cozy-premium-workspace-card tone-${card.tone}`} to={card.href}>
      {content}
    </Link>
  )
}

function CommandEmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="cozy-premium-command-empty">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  )
}
```

- [ ] **Step 2: Run TypeScript build and confirm the component compiles**

Run:

```powershell
cd web
npm run build
```

Expected: Build passes. If it fails on a missing type import, fix the import path in `DailyCommandQueue.tsx` and rerun until the build passes.

- [ ] **Step 3: Commit the component**

Run:

```powershell
git add web/src/components/DailyCommandQueue.tsx
git commit -m "feat: add daily command queue component"
```

---

### Task 3: Wire Command Desk Into Dashboard

**Files:**
- Modify: `web/src/pages/Dashboard.tsx`
- Depends on: `web/src/components/DailyCommandQueue.tsx`
- Depends on: `web/src/utils/commandDesk.ts`

- [ ] **Step 1: Add imports**

In `web/src/pages/Dashboard.tsx`, add these imports near the existing component and utility imports:

```ts
import { DailyCommandQueue } from '../components/DailyCommandQueue'
import { buildCommandDeskModel } from '../utils/commandDesk'
```

Remove this import because the command desk supersedes the old top PM queue placement:

```ts
import { PmDailyQueue } from '../components/PmDailyQueue'
```

- [ ] **Step 2: Build the command desk model**

After the existing `dashboardPriorityCards` memo, add this memo:

```ts
  const commandDesk = useMemo(
    () => buildCommandDeskModel(day, sortedWatchlistTickers),
    [day, sortedWatchlistTickers],
  )
```

- [ ] **Step 3: Render the command desk above the quick bar**

In the JSX, place the new component after the dashboard header and before `<div className="dashboard-quick-bar">`:

```tsx
      <DailyCommandQueue model={commandDesk} />
```

- [ ] **Step 4: Remove the old top PM queue render**

Delete this line from the JSX:

```tsx
      <PmDailyQueue pmView={day.pm_view} />
```

Keep the existing `dashboard-priority-section`, `TodaySetupBoard`, accordion sections, and `WatchlistTable` for now. This preserves detail surfaces below the new first-screen hero.

- [ ] **Step 5: Add anchor IDs for workspace cards**

Add `id="market-context"` to the market accordion section:

```tsx
      <div id="market-context">
        <DashboardAccordionSection
          title="오늘 시장 분위기"
          summary={`${day.market_regime?.regime ?? '시장 분위기 정보 없음'} · 매크로와 섹터 흐름`}
        >
          <MarketRegimeBanner regime={day.market_regime} />
          <MacroNarrativePanel narrative={day.macro_context?.macro_narrative} regime={day.market_regime} />
          <MacroContextBar macroContext={day.macro_context} />
          <MarketOverview entries={day.market_overview} />
          <SectorSummary tickers={day.tickers} />
        </DashboardAccordionSection>
      </div>
```

Wrap the watchlist render with `id="watchlist"`:

```tsx
      <div id="watchlist">
        {sortedWatchlistTickers.length > 0 ? (
          <WatchlistTable tickers={sortedWatchlistTickers} accountSize={accountSize} density={density} />
        ) : (
          <div className="dashboard-empty-state">
            <strong>{emptyState.title}</strong>
            <p>{emptyState.body}</p>
          </div>
        )}
      </div>
```

- [ ] **Step 6: Run build**

Run:

```powershell
cd web
npm run build
```

Expected: Build passes with no TypeScript errors.

- [ ] **Step 7: Commit dashboard integration**

Run:

```powershell
git add web/src/pages/Dashboard.tsx
git commit -m "feat: surface command desk on dashboard"
```

---

### Task 4: Add Cozy Premium Command Desk Styles

**Files:**
- Modify: `web/src/styles/cozy.css`

- [ ] **Step 1: Append the command desk CSS section**

Add this section near the bottom of `web/src/styles/cozy.css`, after the existing cozy premium component styles:

```css
/* ============================================================
   Cozy Premium Command Desk
   ============================================================ */

.cozy-premium-command-desk {
  display: grid;
  gap: 18px;
  margin: 0 0 22px;
}

.cozy-premium-command-hero {
  display: grid;
  grid-template-columns: minmax(0, 0.85fr) minmax(320px, 1.15fr);
  gap: 20px;
  align-items: stretch;
  padding: 24px;
  background:
    radial-gradient(circle at 12% 0%, rgba(255,255,255,.92), transparent 34%),
    linear-gradient(180deg, var(--cozy-paper) 0%, var(--cozy-paper-2) 100%);
  border: 1px solid var(--cozy-border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-lg);
  position: relative;
  overflow: hidden;
}

.cozy-premium-command-hero::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  background: linear-gradient(90deg, var(--cozy-gold), var(--cozy-gold-2), var(--cozy-good));
}

.cozy-premium-command-copy {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 18px;
  min-width: 0;
}

.cozy-premium-command-copy .cozy-headline {
  max-width: 720px;
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(2rem, 5vw, 4.2rem);
  line-height: .95;
  letter-spacing: -0.04em;
}

.cozy-premium-command-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.cozy-premium-command-counts span {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-width: 88px;
  padding: 10px 12px;
  background: rgba(255,255,255,.65);
  border: 1px solid var(--cozy-border-color);
  border-radius: var(--radius-chip);
  color: var(--cozy-muted);
}

.cozy-premium-command-counts b {
  color: var(--cozy-ink);
  font-size: 1.35rem;
  line-height: 1;
}

.cozy-premium-command-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  padding: 16px;
  background: rgba(255,253,245,.72);
  border: 1px solid var(--cozy-border-color);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow);
}

.cozy-premium-command-panel-head,
.cozy-premium-action-card-main,
.cozy-premium-workspace-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.cozy-premium-command-panel-head span,
.cozy-premium-action-type,
.cozy-premium-workspace-eyebrow {
  color: var(--cozy-gold);
  font-size: .74rem;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.cozy-premium-action-list {
  display: grid;
  gap: 10px;
}

.cozy-premium-action-card {
  display: grid;
  gap: 9px;
  padding: 14px;
  background: var(--cozy-cream);
  border: 1px solid var(--cozy-border-color);
  border-left: 5px solid var(--cozy-gold-soft);
  border-radius: 14px;
  color: var(--cozy-ink);
}

.cozy-premium-action-card.tone-urgent { border-left-color: var(--cozy-bad); }
.cozy-premium-action-card.tone-watch { border-left-color: var(--cozy-warn); }
.cozy-premium-action-card.tone-info { border-left-color: var(--cozy-good); }

.cozy-premium-action-card h3 {
  margin: 2px 0 0;
  font-family: var(--font-sans);
  font-size: 1rem;
  letter-spacing: -0.01em;
}

.cozy-premium-action-score {
  flex: 0 0 auto;
  padding: 5px 8px;
  border-radius: var(--radius-pill);
  background: var(--cozy-gold-soft);
  color: var(--cozy-ink);
  font-size: .8rem;
}

.cozy-premium-action-card p {
  margin: 0;
  color: var(--cozy-ink-soft);
}

.cozy-premium-action-card ul {
  margin: 0;
  padding-left: 1.05rem;
  color: var(--cozy-muted);
  font-size: .9rem;
}

.cozy-premium-action-link {
  justify-self: start;
  color: var(--cozy-gold);
  font-weight: 700;
}

.cozy-premium-command-empty {
  padding: 18px;
  background: var(--cozy-cream);
  border: 1px dashed var(--cozy-border-color);
  border-radius: 14px;
}

.cozy-premium-command-empty p {
  margin: 6px 0 0;
  color: var(--cozy-muted);
}

.cozy-premium-workspace-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.cozy-premium-workspace-card {
  display: grid;
  gap: 10px;
  min-height: 150px;
  padding: 18px;
  background: var(--cozy-cream);
  border: 1px solid var(--cozy-border-color);
  border-top: 4px solid var(--cozy-gold-soft);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow);
  color: var(--cozy-ink);
  text-decoration: none;
  transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
}

.cozy-premium-workspace-card:hover {
  transform: translateY(-2px);
  background: var(--cozy-paper);
  box-shadow: var(--shadow-lg);
}

.cozy-premium-workspace-card.tone-pm { border-top-color: var(--cozy-gold); }
.cozy-premium-workspace-card.tone-trader { border-top-color: var(--cozy-good); }
.cozy-premium-workspace-card.tone-market { border-top-color: var(--cozy-warn); }
.cozy-premium-workspace-card.tone-system { border-top-color: var(--cozy-muted); }

.cozy-premium-workspace-card.is-disabled {
  opacity: .68;
  pointer-events: none;
}

.cozy-premium-workspace-card h3 {
  margin: 0;
  font-family: var(--font-sans);
  font-size: 1rem;
}

.cozy-premium-workspace-card p {
  margin: 0;
  color: var(--cozy-muted);
  font-size: .92rem;
}

.cozy-premium-workspace-title-row strong {
  flex: 0 0 auto;
  color: var(--cozy-ink);
}

@media (max-width: 1100px) {
  .cozy-premium-command-hero {
    grid-template-columns: 1fr;
  }

  .cozy-premium-workspace-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .cozy-premium-command-hero {
    padding: 18px;
  }

  .cozy-premium-command-counts span {
    flex: 1 1 92px;
  }

  .cozy-premium-workspace-grid {
    grid-template-columns: 1fr;
  }

  .cozy-premium-action-card-main,
  .cozy-premium-workspace-title-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

- [ ] **Step 2: Run build**

Run:

```powershell
cd web
npm run build
```

Expected: Build passes. CSS changes should not create TypeScript changes.

- [ ] **Step 3: Commit styles**

Run:

```powershell
git add web/src/styles/cozy.css
git commit -m "style: add cozy command desk styling"
```

---

### Task 5: Manual Verification And Final Polish

**Files:**
- Modify only files touched in prior tasks if verification reveals a concrete issue.
- Do not modify generated output files unless the user explicitly asks for refreshed output data.

- [ ] **Step 1: Run final production build**

Run:

```powershell
cd web
npm run build
```

Expected: Build passes. Record any warnings in the final response.

- [ ] **Step 2: Start the local dev server**

Run:

```powershell
cd web
npm run dev -- --host 127.0.0.1 --port 5173
```

Expected: Vite prints a local URL at `http://127.0.0.1:5173/`.

- [ ] **Step 3: Browser-check desktop dashboard**

Open `http://127.0.0.1:5173/`.

Expected visible results:

- The first dashboard content after the header is the cozy command desk.
- The hero headline reads `오늘 먼저 볼 일만 정리했습니다.`
- Queue counts are visible for `긴급`, `관찰`, and `참고`.
- Action cards link to ticker details or portfolio.
- Workspace cards for `PM Review`, `Trader Setups`, `Market Context`, and `System Health` are visible.
- Existing quick bar, dashboard priority cards, setup board, accordions, and watchlist remain below.

- [ ] **Step 4: Browser-check anchor navigation**

Click these workspace cards:

- `Trader Setups`
- `Market Context`
- `System Health`

Expected:

- `Trader Setups` scrolls to the watchlist area.
- `Market Context` scrolls to the market context accordion wrapper.
- `System Health` navigates to `/api-status`.

- [ ] **Step 5: Browser-check mobile width**

Use browser responsive mode or resize below `680px`.

Expected:

- Hero becomes single-column.
- Action cards stack vertically.
- Workspace cards stack vertically.
- Text remains readable and sticky controls do not cover the command desk.

- [ ] **Step 6: Verify Git status scope**

Run:

```powershell
git status --short
```

Expected changed files from this implementation:

```text
web/src/utils/commandDesk.ts
web/src/components/DailyCommandQueue.tsx
web/src/pages/Dashboard.tsx
web/src/styles/cozy.css
```

Existing unrelated generated `output/` changes may still appear. Do not stage or commit them for this UI implementation.

- [ ] **Step 7: Commit final verification fixes if any were needed**

If Step 3, 4, or 5 required a code or CSS correction, commit only those corrections:

```powershell
git add web/src/utils/commandDesk.ts web/src/components/DailyCommandQueue.tsx web/src/pages/Dashboard.tsx web/src/styles/cozy.css
git commit -m "fix: polish command desk dashboard"
```

If no correction was needed, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Today's action queue at top: Task 3 renders `DailyCommandQueue` above the quick bar and old top PM queue.
- PM/trader/market/system workspace cards: Task 1 builds four card models, Task 2 renders them.
- `cozy.css` token reuse: Task 4 uses existing `--cozy-*`, `--radius-*`, and `--shadow-*` tokens.
- No data contract changes: Task 1 uses `DailyEntry`, `PMPriorityQueueItem`, and existing ticker helpers only.
- Fallback and empty states: Task 1 builds fallback queue, Task 2 renders `CommandEmptyState`.
- Responsive behavior: Task 4 includes desktop, tablet, and mobile rules.
- Verification: Task 5 covers build, desktop browser, anchors, mobile, and git scope.

Placeholder scan:

- The plan does not use TBD/TODO placeholders.
- Each code-writing step includes concrete code or exact replacement snippets.
- Each verification step has exact commands and expected results.

Type consistency:

- `CommandDeskModel`, `CommandQueueItem`, and `CommandWorkspaceCardModel` are defined in Task 1 and imported by Task 2.
- `buildCommandDeskModel(day, sortedWatchlistTickers)` is defined in Task 1 and used in Task 3.
- CSS class names in Task 2 match the styles in Task 4.

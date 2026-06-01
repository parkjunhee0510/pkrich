# Dashboard News Desk Design

Status: Approved design
Date: 2026-05-28
Scope: Dashboard UI/UX redesign only

## Summary

Redesign the Dashboard first screen into a Korean "news desk" style overview. The user should immediately understand today's market situation, important news, market and real-asset moves, affected sectors, affected tickers, and practical items to check today.

The first implementation should reorganize existing frontend data into a clearer presentation layer. It must not change the existing API interface, output schema, or investment/business logic.

## Goals

- Make the Dashboard easier to scan at a glance, like a market news desk.
- Show today's situation, news, market changes, sector impact, ticker impact, and action/check items together.
- Add real-asset context such as oil and gold when existing output data provides it.
- Replace English finance jargon with user-friendly Korean terms.
- Reduce perceived page navigation delay by avoiding long full-page skeleton states.
- Keep existing Dashboard features available below the new summary experience.
- Maintain shadcn/ui direction and existing app conventions.
- Improve accessibility, keyboard navigation, focus visibility, mobile touch targets, and dark-mode contrast.
- Remove pill-shaped and semicircular DIV/card/row designs from the Dashboard redesign.
- Keep bundle size growth minimal by using local utilities and existing components where possible.

## Non-Goals

- Do not add a new external news fetch in the first phase.
- Do not change output schema.
- Do not change existing API interfaces.
- Do not change investment decision or scoring business logic.
- Do not add trading automation.
- Do not redesign every app page in this task.
- Do not introduce a new component library beyond the existing shadcn/ui direction.
- Do not create a marketing-style landing page.

## Approved Direction

The selected approach is a hybrid, staged redesign:

- Phase 1: Build a frontend-only news desk view model from existing Dashboard outputs.
- Phase 2: If the shape proves stable, consider promoting repeated logic into a generated artifact such as `news_desk.json`.

The approved layout approach is a split news desk:

- Left side: market, sector, macro, and real-asset changes.
- Right side: news desk feed, risks, evidence checks, and ticker impact.

The approved feed strategy is hybrid:

- Top: three plain-language "today's key sentences".
- Then: news -> affected sector -> affected ticker -> action/check item.

## Existing Data Inputs

The first implementation should use existing data already available to the Dashboard. Expected sources include:

- Dashboard daily entry data from `useDashboardData`.
- `market_overview` for index and broad market moves.
- `macro_context` for rates, dollar, oil, gold, credit, and macro context where available.
- `market_regime` for market mood.
- existing ticker data for price, action, conviction, news, and references.
- risk intelligence summary data from existing hooks.
- search evidence and quality/reliability loop data from existing hooks.
- existing Dashboard-derived structures such as decision strip, priority queue, action change feed, and sector mood.

Real-asset data should be integrated when available from existing outputs:

- WTI oil
- gold
- dollar
- US 10-year yield
- copper if already available and useful

Missing real-asset data should not block the Dashboard. The UI should show a local empty or partial-data state for that area.

## Terminology

English jargon should be hidden from the primary Dashboard UI. Use short Korean labels and easy Korean state values.

| Existing / internal term | User-facing Korean |
| --- | --- |
| Regime | 시장 분위기 |
| risk_on | 위험자산 선호 |
| risk_off | 안전자산 선호 |
| neutral | 중립 |
| reflation | 경기민감 자산 선호 |
| defensive_bias | 방어적 시장 |
| Breadth | 상승 확산도 |
| Mixed | 종목별 혼조 |
| Vol | 변동성 |
| Calm | 안정적 |
| stale evidence | 근거 갱신 필요 |
| provider error | 데이터 확인 필요 |

The UI must not rely on color alone to communicate meaning. Directional values should include Korean text such as `상승`, `하락`, `안정`, `혼조`, or `확인 필요`.

## Information Architecture

The redesigned Dashboard first screen should have this order:

1. Today's key sentences
2. Today's situation panel
3. Real-asset and market move strip
4. News desk feed
5. Today's priority/check queue
6. Affected sectors and affected tickers
7. Existing detailed Dashboard sections

Existing Dashboard sections should remain available, but the top of the page should shift from table-heavy analysis to a concise situation overview.

### Desktop Layout

Desktop should use a two-column structure after the top situation area:

```text
Top
Today's situation panel + real-asset / market move strip

Main
Left: market changes / sector changes / today's priority queue
Right: news desk feed / risk / evidence checks / ticker impact

Bottom
Decision changes / risk intelligence / setup boards / full watchlist
```

### Mobile Layout

Mobile should use a single-column structure:

```text
1. Today's key sentences
2. Today's situation panel
3. Real-asset and market changes
4. News desk feed
5. Today's priority queue
6. Affected sectors and affected tickers
7. Existing detailed sections
```

The mobile layout should avoid hiding too much behind accordions. The first screen should show the most useful summary, with details continuing naturally below.

## Component Structure

The first implementation should keep the boundary between data hooks, view-model construction, and UI components clear.

Proposed files:

- `web/src/utils/newsDesk.ts`
- `web/src/components/DashboardNewsDesk.tsx`

Proposed component structure:

```text
Dashboard.tsx
  - existing data hooks remain
  - builds newsDeskViewModel with useMemo
  - passes the view model into DashboardNewsDesk

DashboardNewsDesk
  - TodaySituationPanel
  - MarketMoveStrip
  - NewsDeskFeed
  - NewsDeskImpactList
```

The exact file split can follow existing codebase conventions during implementation. The important boundary is that display-only normalization and ranking should live in a small pure utility, while components focus on rendering and accessibility.

## View Model

Create a display-only news desk view model from existing data.

The view model should include:

- `headlines`: three short Korean key sentences.
- `situation`: market mood, breadth, volatility, confidence, and key drivers.
- `marketMoves`: indexes, rates, dollar, oil, gold, and available real-asset/macro items.
- `feedItems`: ranked news desk items.
- `impacts`: affected sectors and tickers.
- `states`: loading, empty, partial error, and stale evidence flags.

The view model must not mutate source data and must not change business logic decisions. It only normalizes and ranks display information.

## News Desk Feed Ranking

The feed should not be a simple chronological news list. It should rank items by market relevance and actionability.

Candidate sources:

- high-impact macro changes or events.
- risk intelligence alerts and affected tickers/sectors.
- search evidence freshness and provider warnings.
- action change feed and today decision strip changes.
- ticker news and references already available in existing outputs.
- sector mood focus or watch sectors.
- real-asset moves such as oil, gold, dollar, and US 10-year yield.

Ranking criteria:

1. Broad market impact.
2. Size or importance of market, macro, or real-asset move.
3. Relevance to portfolio, watchlist, priority tickers, or affected sectors.
4. Risk or evidence-quality concern.
5. Clear action/check item for today.

Feed ordering should be deterministic. When two items have the same priority, use stable tie-breakers such as category order, ticker symbol, source id, or title.

Feed card structure:

```text
[category]
Title
Why it matters
Affected: assets / sectors / tickers
Today's check item
```

Suggested categories:

- 시장 변화
- 매크로
- 리스크
- 뉴스
- 근거 점검
- 종목 변화

Desktop should show up to six feed items by default. Mobile should show three feed items first, with a 44px or taller "더보기" control for the rest.

## Existing Section Placement

| Existing area | New placement | Treatment |
| --- | --- | --- |
| `MarketOverview` | 상단 `시장 변화` | Use easier Korean labels and summarize first. |
| `MacroContextBar` | `실물자산/매크로 변화` | Emphasize oil, gold, dollar, and rates. |
| `TodayPriorityQueue` | Below news desk as `오늘 점검 큐` | Preserve function; use square rows. |
| `TodayDecisionStrip` | Lower `판단 변화` detail | Preserve existing decision-change behavior. |
| `ActionChangeFeed` | Part of feed plus lower detail | Reduce duplicated meaning, keep detail available. |
| `RiskIntelPanel` | Right summary plus lower detail | Show summary near top, detail below. |
| `WatchlistTable` | Lower full list | Preserve existing table features. |
| `TraderDashboardPanels` | Lower detailed board | Preserve existing information. |

## Loading, Empty, and Error States

The Dashboard should move away from long full-page skeletons and toward area-level states.

### Loading

Only show skeletons when the relevant data is actually loading.

Preferred loading behavior:

- If no data exists yet, show small skeletons for the top summary and key panels.
- During page navigation, keep previously loaded data visible when possible.
- If only one data source is slow, show loading only in that panel.
- Avoid large table skeletons on the Dashboard first screen.

Avoid:

- full-page skeletons during normal route transitions.
- long `table-page-skeleton` exposure on the Dashboard.
- skeletons when stale but usable data is already available.
- skeletons that push layout height dramatically.

### Empty

Use calm Korean empty states:

```text
오늘 크게 달라진 시장 이슈는 없습니다.
시장 변화와 점검 큐는 계속 확인할 수 있습니다.
```

```text
오늘 우선 확인할 종목은 없습니다.
기존 관찰 목록은 아래에서 확인할 수 있습니다.
```

```text
유가와 금 가격 데이터를 불러오지 못했습니다.
다른 시장 지표는 계속 표시됩니다.
```

Empty states should be square or lightly rounded panels, not pill-shaped badges or decorative illustrations.

### Error

Prefer panel-level errors over full-page errors.

Examples:

```text
뉴스 근거를 불러오지 못했습니다.
시장 변화와 종목 목록은 계속 확인할 수 있습니다.
```

```text
리스크 요약을 불러오지 못했습니다.
오늘의 가격 변화와 점검 큐는 계속 표시됩니다.
```

Error states should include accessible text, clear contrast, and a retry control only when the existing data hook supports retry behavior.

## Visual Rules

The UI should be square, structured, and information-oriented.

Global shape rule:

```text
Cards, rows, panels, badges, and state labels must not use pill or semicircular shapes.
```

Radius guidance:

| Element | Radius |
| --- | --- |
| page panel | 6px or less |
| card | 6px or less |
| row | 4px or less |
| button | existing shadcn/ui default unless it creates a pill look |
| badge / label | 4px or less |
| table row | none or 4px or less |
| empty/error/loading box | 6px or less |

Disallow:

- semicircular summary cards.
- capsule or pill tone badges.
- rounded priority rows with large radius.
- decorative rounded background blocks.
- state information communicated only by a colored pill.

Allow:

- thin bordered square panels.
- small-radius rows.
- left-border or top-border state emphasis.
- text labels with icons.
- color plus text for state direction.

## Design Tokens

Use existing shadcn/ui token direction and reduce hardcoded colors.

Base token families:

- `background`
- `foreground`
- `card`
- `card-foreground`
- `muted`
- `muted-foreground`
- `border`
- `accent`
- `accent-foreground`
- `destructive`
- `destructive-foreground`
- `ring`

News desk semantic CSS variables may be added for presentation only:

- `--newsdesk-positive`
- `--newsdesk-negative`
- `--newsdesk-warning`
- `--newsdesk-info`
- `--newsdesk-neutral`

These tokens must not become API or output-schema concepts.

Spacing should be consistent:

| Use | Size |
| --- | --- |
| section gap | 24px |
| desktop panel padding | 16px or 20px |
| mobile panel padding | 12px or 16px |
| row gap | 8px or 12px |
| dense list item padding | 10px to 12px |

Typography should keep the Dashboard dense but readable:

- one clear page heading level.
- compact section titles.
- card titles slightly stronger than body text.
- muted descriptions with adequate contrast.
- tabular numeric styling where useful.
- no viewport-width-based font scaling.
- no negative letter spacing.

## Accessibility

Accessibility requirements:

- Body text should meet WCAG AA contrast, targeting 4.5:1 or better.
- Large text should meet 3:1 or better.
- Dark-mode muted text must remain readable.
- All interactive controls need visible `focus-visible` styling.
- Focus ring should be clear in both light and dark mode.
- Icon-only buttons require `aria-label`.
- Decorative icons should use `aria-hidden`.
- Loading regions can use `aria-busy` when useful.
- Skeleton visuals should be hidden from screen readers when they are decorative.
- Error messages should use an appropriate accessible alert pattern.
- Color must not be the only way to understand positive, negative, warning, or neutral state.
- Keyboard tab order should follow the visual reading order.

Mobile touch target requirements:

- Buttons: at least 44px tall.
- Icon buttons: at least 44px by 44px.
- More buttons: at least 44px tall.
- Menu items: at least 44px tall.
- Table row actions: touchable area should reach 44px where feasible.

Menu/dropdown requirements:

- More menus must render above page content.
- Portal/z-index layering must prevent menus from being buried under other DIVs.
- Keyboard navigation should remain usable.

## Motion

Motion should be functional and restrained:

- Hover may change background and border color.
- Transitions should usually be 150ms to 200ms.
- Prefer transitions on color, background-color, border-color, and box-shadow.
- Avoid large scale effects.
- Avoid noisy route animations.
- Avoid heavy skeleton shimmer.

## Hydration and Render Stability

Avoid common hydration mismatch sources:

- Do not call `new Date()` directly during render for generated UI content.
- Do not use `Math.random()` for ids or React keys.
- Avoid locale formatting that can produce inconsistent server/client output unless existing app patterns already handle it.
- Keep feed ordering deterministic.
- Keep empty/loading/data DOM transitions structurally stable where practical.

Reduce unnecessary re-renders:

- Build the news desk view model with a pure utility.
- Use `useMemo` in `Dashboard.tsx` for the view model.
- Use stable ids as list keys.
- Avoid index keys for ranked feed cards.
- Avoid repeating sort/filter operations directly inside render.
- Use `useCallback` only when it prevents real prop churn.
- Avoid passing newly created large objects into existing heavy panels unless needed.

## Testing and Verification

Implementation should run:

```text
npm run lint
npm run build
npm run test
npm run audit:ui
```

Run `npm run audit:performance` if available and practical after the UI implementation.

Suggested unit/component test coverage:

- Korean terminology normalization.
- market move item construction for oil, gold, dollar, and rates.
- deterministic news desk feed sorting.
- empty state view model.
- partial error state view model.
- same input produces stable ids and ordering.
- top three headline sentences render.
- `더보기` button has an accessible label and adequate touch target.
- panel-level empty/error states render.
- no Dashboard-first-screen use of long table skeletons.

Manual or browser verification should cover:

- first Dashboard load.
- navigating away from Dashboard.
- returning to Dashboard.
- mobile viewport layout.
- more menu z-index behavior.
- news feed "더보기" behavior.
- keyboard tab order.
- focus-visible visibility.
- dark mode contrast.
- no pill or semicircular card/row/panel shapes.

## Documentation

This design document is the approved spec for the Dashboard news desk redesign.

After implementation, write a concise change summary document using the repository's existing documentation style. It should include:

- changed files.
- reasons for each change.
- existing features preserved.
- commands run.
- verification result.
- remaining risks.

## Acceptance Criteria

The implementation is acceptable when:

- Dashboard first screen reads as a news desk style overview.
- Today's situation, news, market changes, real-asset moves, affected sectors, affected tickers, and check items are visible.
- Oil and gold are shown when existing output data includes them.
- English finance jargon is replaced with clear Korean terminology in the primary Dashboard UI.
- Existing Dashboard features remain available.
- Existing API interfaces remain unchanged.
- Existing output schema remains unchanged.
- Existing business logic remains unchanged.
- Long full-page skeleton exposure during page navigation is avoided.
- `table-page-skeleton` does not dominate the Dashboard first screen.
- More menus are not buried under page content.
- Pill-shaped and semicircular DIV/card/row designs are removed from the redesigned Dashboard.
- Mobile touch targets are at least 44px.
- Keyboard navigation and focus-visible states are clear.
- Light and dark mode contrast meet the intended accessibility bar.
- `npm run lint`, `npm run build`, and `npm run test` pass.
- `npm run audit:ui` passes or any findings are documented and resolved.
- A change summary document is written after implementation.

## Remaining Risks

- Existing generated data may not always include complete oil, gold, dollar, or rate values. The first implementation should handle partial data gracefully.
- Some older CSS may still contain rounded shapes outside the Dashboard scope. This task should remove Dashboard-relevant pill and semicircular shapes without broad unrelated refactors.
- Performance gains depend on the current routing and data hook behavior. The implementation should focus on reducing perceived delay and unnecessary skeleton exposure without changing API contracts.
- If the existing Dashboard file is already large, the implementation should extract small display components only where it directly supports this redesign.

## App-Wide Information Architecture Design

Date: 2026-04-28

## Summary

Redesign the entire web app information architecture around a mixed PM/trader workspace model.

The app should stop feeling like a flat collection of analysis pages and instead behave like a connected operating surface for five jobs:

1. understand the market
2. review current holdings
3. discover new opportunities
4. read and compare research
5. monitor research-system health

The selected direction is a `Workspace Hub` with five top-level areas:

- `브리핑`
- `포트폴리오`
- `기회`
- `리서치`
- `운영`

The first screen must answer: `지금 시장이 어떤 상태지?`

The first viewport should prioritize `시장 브리핑 + 핵심 포지션`.

This redesign is scoped to frontend information architecture, routing, page responsibility, and presentation hierarchy. It must not change pipeline contracts, collector/analyzer/decision behavior, datastore behavior, or output generation in the first phase.

## Goals

- Reorganize the app around user workspaces instead of a flat feature menu.
- Make the home screen a market-briefing workspace instead of a generic dashboard.
- Separate current-holdings review from opportunity discovery.
- Make sector/theme exploration the primary path into ticker discovery.
- Reposition research as a note library, with chat as a supporting tool.
- Expand operations into a research operations console that exposes system trust and health.

## Non-Goals

- No backend or pipeline contract changes in the first phase.
- No new LLM calls or model behavior changes.
- No rewrite of every data component at once.
- No trading automation.
- No attempt to solve real-time execution workflows.

## Approved Direction

The user approved:

- user model: `PM + 트레이더 혼합`
- first-screen question: `지금 시장이 어떤 상태지?`
- first viewport structure: `시장 브리핑 + 핵심 포지션`
- navigation philosophy: 4-5 top-level work areas instead of many peer tabs
- opportunity flow: `섹터/테마 -> 종목`
- research model: `리서치 노트 라이브러리`
- operations model: `리서치 운영 콘솔`
- overall IA option: `Workspace Hub`

## Product Frame

The app becomes an investment operating workspace instead of a dashboard with many sibling pages.

Top-level workspaces:

1. `브리핑`: read market state and today’s context
2. `포트폴리오`: inspect held exposures, risk, and rebalance questions
3. `기회`: move from sectors/themes into candidate tickers
4. `리서치`: read, compare, and revisit research notes
5. `운영`: monitor pipeline, quality, cost, and output trust

This changes the mental model from "which tool page do I need?" to "which job am I doing right now?"

## Navigation Model

### Primary navigation

Primary app navigation should expose only:

- `브리핑`
- `포트폴리오`
- `기회`
- `리서치`
- `운영`

### Secondary navigation

Each workspace owns its own local navigation, such as tabs, segmented controls, or sub-routes. Secondary navigation should appear only inside the active workspace and should not leak unrelated app sections back into the global header.

### Global utilities

The app shell should preserve a small set of always-available utilities:

- global ticker / sector / note search
- as-of date and freshness status
- quick ticker jump
- compact system freshness indicator

### Reclassification of current routes

Existing routes should be reorganized conceptually as follows:

- `Dashboard` -> `브리핑`
- `Portfolio`, `Scenario` -> `포트폴리오`
- `Sectors`, `SectorDetail`, parts of `Signals`, parts of `Calendar` -> `기회`
- `TickerDetail`, note-reading flows, `Chat`, parts of `PriceHistory` -> `리서치`
- `Admin`, `API Status`, `Backtest` -> `운영`

The first implementation pass may keep some existing technical routes while changing labels, entry points, page ownership, and menu structure.

## Workspace Design

### 1. 브리핑

`브리핑` is the app home and default landing workspace.

Its first responsibility is to answer `지금 시장이 어떤 상태지?`

#### First viewport structure

- `시장 브리핑`
  - market regime
  - macro narrative
  - major sector strength/weakness
  - notable events
- `핵심 포지션`
  - highest-importance held names
  - risk-sensitive holdings
  - positions that need review today

#### Below-the-fold sections

- `오늘 액션`
- `섹터 이동`
- `신호 변화`
- `캘린더`

The home page should prioritize context before action. It should feel like a briefing desk, not a watchlist dump.

### 2. 포트폴리오

`포트폴리오` is for current holdings and exposure management.

Primary concerns:

- concentration risk
- correlation
- sector bias
- event exposure
- rebalance questions
- what-if scenario review

Suggested subareas:

- `포트폴리오 개요`
- `핵심 보유 점검`
- `리스크/상관`
- `시나리오`

This workspace should never feel like opportunity discovery. It is for defending, resizing, and reviewing what is already owned.

### 3. 기회

`기회` is for discovering new candidates.

The entry point should be `섹터/테마`, not a raw ticker table.

Suggested flow:

1. `섹터 지도`
2. `테마/촉매 보기`
3. `섹터 상세`
4. `후보 종목 리스트`

This preserves the user-approved journey:

`시장 -> 섹터/테마 -> 종목 -> 판단`

Ticker tables remain useful, but they should appear late in the flow rather than as the dominant first surface.

### 4. 리서치

`리서치` becomes a note library rather than a chat-first interface.

Suggested subareas:

- `리서치 홈`
- `노트 라이브러리`
- `노트 상세`
- `비교 보기`
- `대화형 보조`

`TickerDetail` should evolve from a dense analysis page into a more document-like research note with a clearer reading order and stronger comparison affordances.

Chat remains available, but as a helper for exploration rather than the primary front door to analysis.

### 5. 운영

`운영` becomes a research operations console.

Suggested subareas:

- `파이프라인 상태`
- `데이터 품질`
- `모델/비용`
- `산출물 검증`
- `평가/회고`

This area should help a PM or trader answer "can I trust what I am seeing?" instead of feeling like a developer-only admin surface.

## Cross-Cutting Rules

### Shared context

All workspaces should share:

- the same as-of date context
- consistent freshness/status language
- visible stale or missing-data indicators

### Drilldown consistency

The preferred drilldown path is:

`시장 -> 섹터 -> 종목 -> 노트/포지션`

Pages should avoid breaking this hierarchy with unrelated shortcuts that blur task boundaries.

### Context-aware ticker views

The same ticker may be opened from multiple workspaces, but the surrounding context should shift:

- from `기회`: candidate evaluation first
- from `포트폴리오`: held-position review first
- from `리서치`: note reading and comparison first

This can be achieved through layout emphasis, entry panels, breadcrumbs, or workspace-aware framing without requiring different ticker data contracts.

### Action affordances

Even read-heavy screens should expose clear next steps, such as:

- open sector detail
- compare notes
- inspect position risk
- return to briefing

The app should not strand the user inside passive reading surfaces.

## Route Migration Shape

The redesign should be implemented as a phased reclassification, not a full rewrite.

### Phase 1 migration principles

- preserve existing data loading through current hooks and repositories
- preserve current JSON contracts
- preserve current route-level components where possible
- change app shell, labels, hierarchy, and page composition first

### Likely migration sequence

1. introduce new app-shell navigation and workspace labels
2. redefine `/` as `브리핑`
3. regroup current pages under workspace ownership
4. refactor page intros and first-view hierarchy
5. add workspace-local navigation and cross-links
6. refine ticker detail context and research-library flows

## Error and Empty State Expectations

- Missing optional sections should degrade gracefully inside the workspace that owns them.
- Empty opportunity data should still preserve the sector/theme framing.
- Missing operations data should show muted unavailable states rather than collapsing the operations workspace.
- Empty or stale data should be explained in-context, not hidden behind generic error text.

## Testing and Validation

The redesign should be considered successful when:

- a user can understand market state from the first screen within 10 seconds
- portfolio review and opportunity discovery no longer feel mixed together
- research feels like a library of notes before it feels like a chatbot
- operations feels like a trust console, not a developer-only page
- the new IA works without requiring backend contract changes in phase 1

Implementation verification should include:

- desktop and mobile walkthrough of top-level navigation
- first-screen scan test for `브리핑`
- task-based validation for:
  - check current holdings
  - move from sector to ticker candidate
  - open a research note and compare it
  - inspect system trust/health

## Documentation Impact

Implementation should update frontend-facing docs that describe app structure, route purpose, or navigation hierarchy.

Most backend layer docs should remain unchanged because this design does not alter the pipeline invariant or data contracts in phase 1.

Likely documentation touchpoints during implementation:

- `docs/ui-ux-structure.md`
- any frontend route map or README that reflects current navigation

## Self-Review

- Placeholder scan: no TBD or TODO items remain.
- Consistency check: the approved user model, navigation philosophy, workspace boundaries, and first-screen goal are aligned.
- Scope check: phase 1 is frontend IA and presentation restructuring, not a backend redesign.
- Ambiguity check: opportunity flow, research model, and operations model are all explicit.

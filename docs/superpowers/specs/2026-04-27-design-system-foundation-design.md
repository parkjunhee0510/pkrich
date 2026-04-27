# Design System Foundation — Design Spec

**Date:** 2026-04-27
**Scope:** UI/UX 시스템 통일 — 토큰·타이포·여백·카드·pill·페이지 헤더 5개 서브시스템을 cozy-premium 테마 위에 정합된 단일 디자인 시스템으로 정리.
**Status:** Plans A & B landed (tokens, typography utilities, spacing migration + lint). Plans C–E pending.

---

## 1. Goal

cozy-premium 테마(편집/매거진 + 웜 모던) 위에 시스템 차원의 일관성을 부여한다. 페이지마다 들쭉날쭉한 타이포 스케일·카드 padding·pill 색·헤더 레이아웃을 단일 토큰/유틸 매트릭스로 묶어, 신규 컴포넌트가 1시간 내 시스템 정합으로 완성되고, 사용자는 진입 즉시 정보 위계를 잡을 수 있게 한다.

## 2. Architecture

**3-tier 토큰 시스템:**
- **Tier 1 — Primitives:** 색·폰트·radius 원시값 (현재 `parts/tokens.css`의 `--cozy-*`, `--font-*` 등 그대로).
- **Tier 2 — Roles:** 의미 토큰 (`--color-bg-card`, `--color-positive`, `--type-headline`, `--space-card-pad` 등). 컴포넌트는 이 층만 참조.
- **Tier 3 — Component variants:** 컴포넌트 전용 토큰(`--shadow-card`, `--space-card-pad-hero` 등).

**5-plan 분할:**
- Plan A: 토큰 + 타이포 (기반)
- Plan B: 여백/리듬
- Plan C: 카드 시스템
- Plan D: pill/색 시스템
- Plan E: 페이지 헤더 패턴

각 plan 독립 머지 가능. A→B→C→D→E 순서 권장(D·E는 부분 병렬 가능).

**비목표 (YAGNI):**
- 다크모드 (현재 단일 라이트 테마, 별도 프로젝트)
- React 컴포넌트 라이브러리화 (CSS 차원만 — `<PageHeader>` 컴포넌트는 Plan E에서 결정)
- 모션/트랜지션 시스템 (별도 스프린트)
- 모바일 반응형 재설계 (기존 미디어쿼리 유지)

## 3. Token System (Tier 2 신규)

기존 `parts/tokens.css`(188줄)에 의미 토큰 블록을 추가. 기존 토큰은 유지하되 alias로 정리.

### 3.1 색 역할 (Roles)

```
/* 표면/배경 */
--color-bg-page          /* 페이지 배경, var(--cozy-cream-2) */
--color-bg-card          /* 카드 배경, var(--paper) */
--color-bg-card-raised   /* hero 카드 배경 (gradient 또는 paper-2) */

/* 텍스트 */
--color-fg-headline      /* 본 제목, var(--cozy-ink) */
--color-fg-body          /* 본문, var(--cozy-ink-soft) */
--color-fg-eyebrow       /* eyebrow, var(--cozy-gold) */
--color-fg-muted         /* 보조 텍스트, var(--cozy-muted) */

/* 보더 */
--color-border-subtle    /* 1px hairline, var(--cozy-border-color) */
--color-border-strong    /* 1.5px gold, var(--cozy-gold) */

/* 의미 색 5개 */
--color-positive         /* BUY, beat, risk-on */
--color-negative         /* AVOID, miss, risk-off */
--color-caution          /* WATCH, neutral, FED */
--color-info             /* 컨텍스트, 보조 정보 */
--color-accent           /* 점수, hero accent (gold) */
```

각 의미 색은 3쌍의 sub-token을 가진다 (solid / soft / outline):

```
--color-{role}                  /* solid bg */
--color-{role}-fg               /* solid bg 위 텍스트 (white 또는 dark) */
--color-{role}-soft-bg          /* 18% opacity tint */
--color-{role}-soft-fg          /* tint 위 어두운 텍스트 */
--color-{role}-soft-border      /* tint 위 보더 (30% opacity) */
--color-{role}-outline-fg       /* outline 텍스트 */
--color-{role}-outline-border   /* outline 보더 */
```

### 3.2 컴포넌트 토큰 (Tier 3)

```
--space-card-pad: 20px
--space-card-pad-hero: 24px
--space-card-gap: 16px
--space-section-gap: 24px
--space-page-pad: 32px
--radius-card: 14px
--radius-pill: 999px
--radius-chip: 8px
--radius-badge: 6px
--shadow-card: 0 2px 0 0 rgba(184,134,47,.18), 0 8px 22px -10px rgba(122,90,46,.28)
```

### 3.3 기존 토큰 처리

- `--paper`, `--ink`, `--cozy-*` 등 Tier 1 그대로 유지.
- `--surface`, `--color-surface` 같은 중복 alias → Tier 2 기본 토큰이 흡수.
- `--neg-block`, `--pos-block`, `--regime-color-*` 등 도메인 토큰은 Tier 2와 별도 유지(스펙 외 도메인).

## 4. Typography Scale (선택: B Modern Balanced)

```
--type-display     Georgia 28px / 700 / 1.2  / -0.3px      페이지 메인 타이틀, hero
--type-headline    Georgia 24px / 700 / 1.25 / -0.2px      카드 제목, 섹션 제목
--type-title       Georgia 20px / 700 / 1.3                서브 카드, 모달
--type-body        Inter 13px / 400 / 1.55                 본문
--type-body-strong Inter 13px / 600 / 1.5  / tabular-nums  강조 본문 (가격, 수치)
--type-meta        Inter 12px / 400 / 1.5                  메타라인, 보조 텍스트
--type-eyebrow     Inter 10px / 600 / uppercase / 1.5px tracking  eyebrow, 라벨
--type-mono        Inter 13px / 500 / tabular-nums         숫자 강조
```

각 타입은 단일 CSS 변수가 아니라 **유틸리티 클래스**(`.type-*`)로 묶어 적용. font-family + size + weight + line-height + letter-spacing + color를 한 번에.

**적용 규칙:**
- `<h1>`/`<h2>`/`<h3>`은 의미 마크업으로만(스타일 리셋). 시각 위계는 `.type-*` 유틸로.
- 컴포넌트 CSS에서 `font-size: 14px` 같은 직접 값 금지 → stylelint warning.
- Display는 페이지당 1개(메인 타이틀, hero 메인). Headline은 카드/섹션 제목, 페이지에 여러 개 가능.

## 5. Spacing/Rhythm (선택: B Standard 8pt)

```
--space-1   4px    /* hairline gap (chip 안 아이콘+텍스트) */
--space-2   8px    /* 작은 gap (chip 사이) */
--space-3   12px   /* 중간 gap (pill row) */
--space-4   16px   /* 카드 간 gap, 카드 안 단락 사이 */
--space-5   20px   /* 카드 padding */
--space-6   24px   /* 헤더 padding, 섹션 사이 */
--space-7   32px   /* 페이지 헤더 ↔ 본문 사이 */
--space-8   40px   /* 페이지 상단 패딩 */
--space-9   48px   /* 큰 섹션 분리 */
```

**예외 허용:** 1px / 1.5px (보더 두께), pill·chip 내부 micro-padding은 8pt 비강제.

**리듬 규칙:**
- 카드 안: `space-card-pad`(20). 안쪽 요소 간격 `space-3`(12) 또는 `space-4`(16).
- 카드 사이: `space-card-gap`(16). 그리드 모두 동일.
- 섹션 사이: `space-6`(24). 페이지 헤더 ↔ 첫 카드 그리드는 `space-7`(32).

**stylelint:** `padding/margin/gap`은 토큰 또는 `0`/`auto`만 허용 → 위반 시 warning.

## 6. Card System (선택: B Warm Shadow base + C Editorial Frame as hero)

### 6.1 `.surface-card` — 기본 카드 (95% 적용)

- 배경: `var(--color-bg-card)`
- 보더: 1px solid `var(--color-border-subtle)`
- 그림자: `var(--shadow-card)` (warm gold hard-bottom)
- radius: `var(--radius-card)` (14px)
- padding: `var(--space-card-pad)` (20)

### 6.2 `.surface-card--hero` — Hero variant (페이지당 최대 1–2개)

- 배경: `var(--color-bg-card-raised)`
- 보더: 1.5px solid `var(--color-border-strong)`
- 상단 골드 라인: 3px gold (Editorial Frame 시그니처)
- 그림자: 없음 (보더가 무게)
- padding: `var(--space-card-pad-hero)` (24)

**적용:** Market Regime Banner (현행 cozy-premium-banner), Top Conviction 자리, Macro Narrative hero.

### 6.3 `.surface-card--list-row` — List row variant

- 배경: 카드 베이스와 동일하지만 `border-bottom`만
- 그림자 없음, radius 0
- padding: `var(--space-3) var(--space-card-pad)` (12 / 20)

**적용:** 신호 통계 행, 위원회 배지 행, API status 행.

### 6.4 호버

- `.surface-card`: 그림자 깊어지고 보더 색이 gold-soft로. transform 없음.
- `.surface-card--hero`: 변화 없음.
- `.surface-card--list-row`: 배경 `rgba(255,255,255,0.4)`.

### 6.5 기존 클래스 매핑

| 현재 | 신규 |
|---|---|
| `.watchlist-card`, `.decision-card`, `.api-provider-card`, `.earnings-hero-card` | `.surface-card` |
| `.market-regime-banner.cozy-premium-banner`, `.top-conviction-card` | `.surface-card--hero` |
| `.api-provider-row`, `.signal-row` | `.surface-card--list-row` |

도메인 modifier(`.watchlist-card.setup-tone-high` 등)는 보존.

## 7. Pill / Badge / Chip System (선택: B Tiered)

### 7.1 모양 (구조 클래스)

```
.pill   radius 999px / padding 4px 14px / weight 700 / font 11px
.chip   radius 8px   / padding 4px 10px / weight 600 / font 11px
.badge  radius 6px   / padding 3px 8px  / weight 700 / font 10px
```

### 7.2 의미 색 5개 × 강도 3종 매트릭스

```
.tone-{role}--solid    /* 진한 채움, white/dark text. 카드당 최대 1개. */
.tone-{role}--soft     /* 18% tint bg + dark text + 30% border. 메타·보조 기본형. */
.tone-{role}--outline  /* white bg + colored border. 비활성 / 후보. */
```

`{role}`: positive / negative / caution / info / accent

### 7.3 사용 예

```html
<span class="pill tone-positive--solid">BUY</span>
<span class="chip tone-positive--soft">EPS BEAT</span>
<span class="chip tone-caution--soft">FED 5/1</span>
<span class="badge tone-accent--soft">78</span>
<span class="chip tone-negative--outline">옵션 매도 후보</span>
```

### 7.4 규칙

- 카드당 solid는 1개 제한 (위계 보장).
- 같은 의미는 항상 같은 색. "BUY"는 어디 나와도 `--color-positive`.
- stylelint: 색 리터럴(#xxx)을 카드/pill 클래스 안에서 직접 사용하면 error.

### 7.5 기존 매핑 (예)

| 현재 | 신규 |
|---|---|
| `.watchlist-decision-pill.decision-pill-buy` | `.pill.tone-positive--solid` |
| `.watchlist-decision-pill.decision-pill-watch` | `.pill.tone-caution--solid` |
| `.watchlist-decision-pill.decision-pill-avoid` | `.pill.tone-negative--solid` |
| `.regime-driver-chip` | `.chip.tone-info--soft` |
| `.options-chip.options-chip-bearish` | `.chip.tone-negative--soft` |
| `.setup-score-badge` (점수) | `.badge.tone-accent--soft` |

## 8. Page Header Pattern (선택: B Editorial Slot)

### 8.1 4-슬롯 구조

```
┌─────────────────────────────────────────────────────────┐
│ [eyebrow]                                                │  Slot 1
│ [headline]                          [actions]            │  Slot 2 + 4
│ [meta]                                                   │  Slot 3
└─────────────────────────────────────────────────────────┘
```

| Slot | 클래스 | 스타일 | 필수? |
|---|---|---|---|
| eyebrow | `.page-header__eyebrow` | `.type-eyebrow` (10px uppercase gold), 섹션 경로 | 선택 |
| headline | `.page-header__headline` | `.type-display` (28px serif), 서술형 | 필수 |
| meta | `.page-header__meta` | `.type-meta` (12px gold), 데이터 기준일·요약 | 선택 |
| actions | `.page-header__actions` | flex row of buttons / chips | 선택 |

### 8.2 컨테이너 스펙

```css
.page-header {
  padding: var(--space-6);
  background: var(--color-bg-page);
  border-radius: var(--radius-card);
  border: 1px solid var(--color-border-subtle);
  margin-bottom: var(--space-6);
}
.page-header__row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--space-4);
}
```

### 8.3 페이지별 적용 예

**워치리스트** (4슬롯 모두):
```
PORTFOLIO · WATCHLIST           (eyebrow)
관심 종목 12개          [필터][+ 추가]
2026-04-27 · BUY 4 · WATCH 6 · AVOID 2
```

**티커 상세** (eyebrow + headline + meta):
```
WATCHLIST · TICKER
Apple Inc.
$214.32  +1.24% · 마지막 분석 2026-04-27
```

**시그널 통계** (eyebrow + headline + actions):
```
ANALYTICS
시그널 정확도 추적          [기간: 30D ▾]
```

### 8.4 규칙

- headline은 **서술형 정보값** ("관심 종목 12개" vs 단순 "워치리스트"). 정적 라벨 아닌 실시간 상태 반영.
- eyebrow = 메뉴 그룹(상위) → 페이지 이름(현재) 컨텍스트 경로.
- meta는 짧게. 이상이면 카드로 분리.
- actions 우측 정렬, 최대 2–3개. 4개 이상이면 toolbar 별도 구역.
- Layout.tsx의 `cozy-nav-date`(상단 nav 안 날짜)는 유지(별도 시그널).

### 8.5 컴포넌트화 (Open Question)

Plan E 시작 시 결정: CSS만 적용할지, `<PageHeader eyebrow="..." headline="..." meta="..." actions={...} />` props 컴포넌트로 만들지.

## 9. Migration Strategy

| Plan | 범위 | 의존성 |
|---|---|---|
| **A** | Tier 2 의미 토큰 + Tier 3 컴포넌트 토큰 + `.type-*` 8개 유틸 | — |
| **B** | `--space-1`...`--space-9` + 컴포넌트 별칭 + 핵심 3군데 토큰 참조 교체 | A |
| **C** | `.surface-card`, `--hero`, `--list-row` 정의 + 기존 카드에 alias 추가 | A, B |
| **D** | `.pill/.chip/.badge` × `.tone-{role}--{treatment}` 매트릭스 + 매핑 표 | A |
| **E** | `.page-header__*` + 5개 라우트 적용 (옵션: `<PageHeader>` 컴포넌트) | A, B (D·E는 부분 병렬 가능) |

**파일 위치 (모두 신규):**
- `web/src/styles/parts/typography.css` (Plan A)
- `web/src/styles/parts/components/cards.css` (Plan C)
- `web/src/styles/parts/components/tone.css` (Plan D)
- `web/src/styles/parts/components/page-header.css` (Plan E)

`global.css`의 `@import` 순서에 추가.

**검증 표준 (모든 plan):**
- `npm run build` 성공
- `npm run lint:css` 새 error 없음 (warning 증가 OK)
- 5개 핵심 페이지 시각 비교(워치리스트 / 결정 보드 / 티커 상세 / 포트폴리오 / 시그널)
- Layout.tsx 네비게이션·헤더 작동 확인

## 10. Success Criteria

**정량:**
- Tier 2 의미 토큰 ≥ 20개 정의
- `.type-*` 유틸 8개 도입
- 카드 정의 15+ → **3종 variant** 통합
- pill/badge/chip 50+ → 모양 3 × 의미 5 × 강도 3 매트릭스(실 클래스 ≤ 15개)
- 페이지 헤더 ≥ 5개 라우트에 4슬롯 적용
- `!important` 44 → ≤ 30
- stylelint warning 34 → ≤ 10
- CSS 번들 크기 변화 ±5% 이내

**정성:**
- 첫눈에 "좋은 신호 / 나쁜 신호" 판정 가능
- 페이지 진입 시 제목·메타·액션 동일 위치
- 카드 padding/gap 페이지마다 동일
- 신규 컴포넌트 추가 시 토큰만 참조해 1시간 내 완성

## 11. Non-Success Signals

- 시각 회귀: 5개 핵심 페이지에서 의도치 않은 변화
- `npm run build` 실패
- 새 색 리터럴 도입(stylelint error)
- spec에 없는 1회용 클래스 추가

## 12. Open Questions

1. **PageHeader 컴포넌트화** — Plan E 시작 전 결정. CSS만 vs props 컴포넌트.
2. **pill 마이그레이션 방식** — alias 레이어 vs 직접 마크업 교체. 직접 교체는 .tsx 변경 많음.
3. **도메인 특수 색 흡수** — `--regime-color-*`, setup-tone 등을 의미 색 시스템에 흡수할지 별도 유지할지. 흡수가 깔끔하지만 설명력 약화 위험.

각 plan 작성 단계에서 해당 plan에 영향 있는 question을 결정.

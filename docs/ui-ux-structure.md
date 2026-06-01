# UI/UX 구조 문서

> 작성일: 2026-04-22
> 대상: `web/` (React + TypeScript + Vite, React Router)
> 목적: 현재 프런트엔드 전체 UI/UX 구조를 한눈에 파악할 수 있도록 정리

---

## 1. 전체 개요

**준희의 포트폴리오**는 한국어 기반의 정량 주식 리서치 대시보드입니다. 트레이더와 분석가가 매일의 신호, 실적, 섹터, 포트폴리오 리스크를 빠르게 스캔하고 종목 상세로 드릴다운할 수 있도록 설계되어 있습니다.

- **빌드/런타임**: Vite + React 18 + TypeScript
- **라우팅**: `react-router-dom` (BrowserRouter, 지연 로딩)
- **차트**: `lightweight-charts`, 자체 SVG 스파크라인
- **DnD**: `@dnd-kit` (워치리스트 순서)
- **데이터 소스**: 정적 JSON (`StaticJsonRepository`) + 선택적 실시간 폴링
- **상태**: 커스텀 훅 중심 (전역 스토어 없음), `localStorage`로 사용자 설정 저장

---

## 2. 레이아웃 (`components/Layout.tsx`)

```
┌──────────────────────────────────────────────┐
│ [준희의 포트폴리오]            [≡ 햄버거]    │  ← header
│ ┌───────────────────────────────────────┐    │
│ │ 워치리스트 · 시세 · 포트폴리오 · …    │    │  ← header-nav (반응형)
│ └───────────────────────────────────────┘    │
├──────────────────────────────────────────────┤
│                                              │
│                 <Routes />                   │  ← main (Suspense)
│                                              │
└──────────────────────────────────────────────┘
```

### 네비게이션 항목 (11개)

| 레이블 | 경로 |
|---|---|
| 워치리스트 | `/` |
| 시세 | `/prices` |
| 포트폴리오 | `/portfolio` |
| 시그널 통계 | `/signals` |
| 섹터 탐색 | `/sectors` |
| 시나리오 | `/scenario` |
| 백테스트 | `/backtest` |
| 리서치 채팅 | `/chat` |
| Admin | `/admin` |
| 캘린더 | `/calendar` |
| API 상태 | `/api-status` |

### 키보드 단축키
- `/` : 대시보드 검색창 포커스
- `R` : 페이지 새로고침
- `Esc` : 햄버거 메뉴 닫기 / 포커스 해제
- `더보기` 메뉴: `Enter`/`Space` 또는 `ArrowDown`/`ArrowUp`으로 열기, `ArrowDown`/`ArrowUp`/`Home`/`End`로 항목 이동, `Esc`로 닫기

### 반응형
- `≤ 768px`: 햄버거 토글, compact 밀도
- `> 768px`: 네비게이션 바 상시 노출, comfortable 밀도

---

## 3. 디자인 시스템 (`styles/`)

두 개의 테마 레이어가 토글 가능하게 공존합니다.

### 3.1 Brutalist (기본, `global.css`)
- **팔레트**: 종이·잉크
  - 배경: `#ece7d8` bone · `#f5f1e4` paper
  - 텍스트: `#0a0a0a` ink
  - 신호: 🟢 `#0a7b2f` · 🔴 `#b81414` · 🟡 `#a15c00`
  - 강조: 번트 앰버 `#d96000`
- **타이포**: Space Mono / JetBrains Mono (모노스페이스 우선)
- **라운딩**: `0px`
- **섀도**: 하드 섀도 `4px 4px 0 0 #0a0a0a`
- **오버레이**: 23px 반복 그리드 노이즈

### 3.2 Cozy (대체, `cozy.css`)
- **팔레트**: 파스텔
  - 배경: 크림/스카이블루/핑크 방사형 그라디언트
  - 텍스트: `#5a3e1b` cozy-ink
  - 신호: 민트 · 로즈 · 피치
- **타이포**: Gowun Dodum (한글), Gaegu (보조)
- **라운딩**: `14px`, 소프트 드롭섀도

### 3.3 공통 토큰
- 상태 블록: `--pos-block` / `--neg-block` / `--caution-block` / `--info-block`
- 대비 전경: `--on-pos-block` 등
- 밀도 모드: `compact` / `comfortable` / `focus`

---

## 4. 페이지별 구조

### 4.1 Dashboard `/` — 워치리스트
일일 종목 스캔과 우선순위 추출의 메인 허브.
- **핵심 위젯**: `WatchlistTable`, `TraderDashboardPanels` (TodaySetupBoard · EarningsBoard · SignalPerformanceBoard · CatalystFeed), `MarketRegimeBanner`, `MacroContextBar`, `MarketOverview`
- **Today Priority Queue**: 첫 화면 근처에 일일 점검 큐를 표시한다. 리스크, 기회, 근거 상태, 공식 판단 변화 맥락을 읽기전용으로 합쳐 오늘 먼저 열어볼 종목을 제안하며, 큐 점수는 화면용 우선순위일 뿐 공식 `buy/watch/avoid` 판단을 바꾸지 않는다.
- **인터랙션**: 섹터 필터, 계좌 규모 선택(10K–100K), 정렬 모드(점수/실적/촉매), 검색창 (`/` 단축키), 워치리스트 DnD 정렬

### 4.2 TickerDetail `/ticker/:ticker` — 종목 상세
단일 종목 깊이 있는 분석.
- **섹션**: 가격 차트(`PriceChart`), 결정 카드(`DecisionCard` / `TraderDecisionBoard`), 펀더멘털 스냅샷(`DataSnapshot`), EPS 서프라이즈(`EpsSurpriseChart`), 52주 배지(`FiftyTwoWeekBadge`), SEC 공시(`SecFilingBadges`), 뉴스(`NewsItem`), 거시경제 영향(티커별 macro sensitivity), 매크로 컨텍스트, 타임라인
- **Ticker Research Brief**: 오늘 점검 큐에 오른 이유를 종목 상세 상단에서 보여준다. 리스크, 기회, 근거 상태, 핵심 사유, 다음 확인점을 요약하고, 큐에 없는 종목은 중립 fallback을 표시해 기존 상세 흐름을 유지한다.
- **인터랙션**: 차트 모드 전환 (캔들↔라인), 이벤트 타임라인 기간 토글

### 4.3 PriceHistory `/prices` — 시세
다중 종목 OHLCV 테이블 + 차트.
- **인터랙션**: 기간 필터(1W·1M·3M·6M·1Y·ALL), 티커 선택/검색, 열 정렬

### 4.4 Portfolio `/portfolio` — 포트폴리오
포지션 추적과 리스크 평가.
- **핵심**: `PortfolioCommandCenter`, `EquityCurveChart`, `PortfolioRiskPanel`(등급 A–D, HHI, `CorrelationHeatmap`), 포지션 편집 모드
- **Command Center**: PM 이벤트 노출, 교체 후보, 종목 집중도, 고상관 페어를 우선순위 큐로 합쳐 요약 카드보다 먼저 표시한다.
- **리스크 용어 설명**: HHI, Beta, VaR, 상관계수, 이벤트 노출, 교체 후보, ATR은 `InfoTooltip`으로 같은 화면에서 한국어 설명을 제공한다.
- **인터랙션**: 큐 항목 클릭 시 같은 페이지에서 상세 근거/확인점을 전환하고, 관련 종목은 `/ticker/:ticker` 상세로 연결한다. 주식 수/평균 단가 입력, 통화(USD/KRW), 로컬 저장(`useLocalPortfolioEditor`)도 유지한다.
- **Quick edit**: 편집 모드는 모든 lot 행을 바로 보여주며 티커는 목록에서 클릭 선택하고, 수량, 평균단가, 통화, 삭제, 추가, 저장을 한 화면에서 처리한다. 티커 선택 메뉴는 popover z-index 토큰을 사용하고 모바일에서는 1열로 접혀 편집 행에 묻히지 않게 유지한다.
- **Quick edit default cost**: 신규 또는 평균단가가 비어 있는 lot에서 티커를 선택하면 현재가를 평균단가 기본값으로 채운다. 자동 입력된 평균단가는 티커를 다시 바꿀 때 새 티커 현재가로 갱신하고, 사용자가 직접 입력한 non-zero 평균단가는 보존한다.

### 4.5 Signals `/signals` — 시그널 통계
과거 신호 성과 집계.
- **섹션**: 방향별 요약(bull/bear/neutral), 티커별 승률/평균 수익
- **인터랙션**: 방향 필터, 정렬

### 4.6 Sectors `/sectors` & SectorDetail `/sectors/:id`
섹터 읽기전용 탐색.
- **핵심**: 섹터 카드 그리드, `SectorPerformanceBars`, `Sparkline`, 52주 강도 배지, 섹터 내 종목 벤치마크

### 4.7 Scenario `/scenario` — 시나리오
포트폴리오 가중치 what-if 분석.
- **인터랙션**: 멀티 종목 가중치 슬라이더, ATR 리스크 재계산

### 4.8 Backtest `/backtest` — 백테스트
전략 누적 수익/월간 성과.
- **핵심**: `EquityCurveChart`, 월간 상위 종목/섹터

### 4.9 Chat `/chat` — 리서치 채팅
AI 기반 종목 질의.
- **인터랙션**: 텍스트 입력, Ctrl+Enter 제출, 대화 히스토리 `localStorage`

### 4.10 Calendar `/calendar` — 캘린더
실적/배당/이벤트 일정.
- **인터랙션**: 이벤트 타입 필터, 검색, 긴급도 배지(3/7/14일)

### 4.11 ApiStatus `/api-status` — API 상태
데이터 공급자 모니터링 (정상/부분/제한 표시).

### 4.12 Admin `/admin`
모델 품질·비용·캘리브레이션 관리자 뷰.
- **핵심**: `SignalQualityPanel`, 앙상블 품질 리포트, 비용 로그, 캘리브레이션 지표

### 4.13 NotFound `*`
404 안내.

---

## 5. 재사용 컴포넌트 라이브러리 (`components/`)

### 5.1 데이터 시각화
| 컴포넌트 | 설명 |
|---|---|
| `PriceChart` | lightweight-charts 기반 캔들/라인 + 거래량 |
| `EquityCurveChart` | 누적 수익 SVG 곡선 |
| `EpsSurpriseChart` | EPS 추정 vs 실적 바 차트 |
| `Sparkline` | 미니 SVG 라인 |
| `CorrelationHeatmap` | 포트폴리오 상관 행렬 히트맵 |
| `SectorPerformanceBars` | 섹터 상대 성과 막대 |

### 5.2 의사결정 & 신호
| 컴포넌트 | 설명 |
|---|---|
| `DecisionCard` | buy/watch/avoid 카드 + 요인 기여도, 신뢰도 낮은 이유 열 (factor reasoning) |
| `TraderDecisionBoard` | 앙상블 합의도 + 요인별 스코어, 발목 잡는 요소(매크로 충격 포함) |
| `TraderDashboardPanels` | TodaySetup · Earnings · Catalyst · SignalPerformance 보드 묶음 |
| `SignalBadge` | bull/bear/neutral 배지 |
| `SignalQualityPanel` | 모델 품질 지표 (Admin) |

### 5.3 컨텍스트
| 컴포넌트 | 설명 |
|---|---|
| `MarketRegimeBanner` | 시장 체제(강세/약세/전환) 배너 |
| `MacroContextBar` | 매크로 노출(고/중/저) |
| `MacroNarrativePanel` | 거시 서사 텍스트 |
| `MarketOverview` | 지수/섹터 요약 |
| `SectorSummary` · `SectorBenchmark` | 섹터 단위 요약/비교 |
| `NewsItem` | 뉴스 헤드라인 카드 |
| `SecFilingBadges` | 10-K / 10-Q / 8-K 영향도 배지 |
| `FiftyTwoWeekBadge` | 52주 고저 대비 위치 |
| `DataSnapshot` | 키:값 통계 카드 |

### 5.4 기본/유틸
| 컴포넌트 | 설명 |
|---|---|
| `Layout` | 헤더 · 네비 · 메인 셸 |
| `Skeleton` | DashboardSkeleton · TablePageSkeleton · TickerDetailSkeleton · InlineLoadingState |
| `ErrorState` | 오류 메시지 |
| `InfoTooltip` | 물음표 호버 툴팁 |
| `WatchlistTable` | DnD 가능한 워치리스트 테이블 |
| `PortfolioCommandCenter` | 포트폴리오 PM 검토 큐 + 리스크 용어 설명 |
| `PortfolioRiskPanel` | 리스크 등급·HHI·드로다운 |

---

## 6. 데이터 흐름 (`hooks/`)

```
StaticJsonRepository (정적 JSON)
         │
         ▼
┌──────────────────────────────────────┐
│ useDashboardData (중앙 훅, 폴링 옵션) │
└──────────────────────────────────────┘
         │ DashboardData
         ├─ days[] (일자별)
         │   ├─ market_overview
         │   ├─ tickers[] (TickerAnalysisData)
         │   ├─ portfolio_summary
         │   └─ portfolio_risk
         ├─ signal_stats
         └─ macro_context
```

| 훅 | 용도 |
|---|---|
| `useDashboardData` | 메인 데이터 소스, 폴링(`pollIntervalMs`, 기본 60s) |
| `useTickerAnalysis` | 종목별 심화 분석 샤드 |
| `useTickerHistory` · `useTickerTimeline` | 종목 이력/타임라인 |
| `usePriceHistory` / `usePriceHistoryLive` | OHLCV 정적/실시간 |
| `useSectorsData` | 섹터 목록 + 구성 종목 |
| `useLocalPortfolioEditor` | 포트폴리오 편집 localStorage 상태 |
| `useLocalResearchAutomation` | 로컬 자동화 상태 |
| `useJsonResource` | 범용 JSON 로더 (로딩/에러 처리) |

---

## 7. 인터랙션 패턴 요약

- **필터/검색**: 섹터, 기간, 이벤트 타입, 방향(bull/bear), 티커 검색
- **정렬**: 테이블 열 클릭 정렬, 커스텀 워치리스트 DnD
- **편집 폼**: 포지션(수량·단가·통화), 시나리오 가중치 슬라이더
- **차트 조작**: 기간 토글, 캔들/라인 전환
- **지속성**: `localStorage`에 워치리스트 순서, 포트폴리오 편집, 대화 히스토리
- **로딩/에러**: `Skeleton`·`InlineLoadingState`·`ErrorState`, Suspense fallback. 페이지 전환은 전체 skeleton을 남발하지 않고, 차트/타임라인 같은 부분 로딩은 접근성 있는 inline status로 처리한다.

---

## 8. 성능 및 접근성

- **코드 스플릿**: 모든 페이지 `React.lazy` + `Suspense`
- **메모이제이션**: `useMemo`로 필터/정렬 결과 캐싱
- **시맨틱**: `header` / `nav` / `main`, 햄버거 `aria-label`·`aria-expanded`, 포털 메뉴 `role="menu"` / `role="menuitem"`
- **키보드**: `/`, `R`, `Esc` 단축키와 더보기 메뉴 roving focus
- **반응형 밀도**: compact / comfortable / focus

---

## 9. 디렉터리 맵

```
web/src/
├── App.tsx              # 라우터 + Suspense 셸
├── main.tsx             # 엔트리
├── components/          # 25+ 재사용 컴포넌트
├── pages/               # 14개 라우트 페이지
├── hooks/               # 데이터/편집 훅
├── data/                # StaticJsonRepository
├── types/               # TypeScript 타입 정의
├── utils/               # 포맷터, 정렬 유틸
├── assets/              # 이미지/아이콘
└── styles/
    ├── global.css       # brutalist 기본 테마
    └── cozy.css         # 파스텔 대체 테마
```

---

## 10. 향후 개선 후보

- 페이지 간 일관된 필터 상태(URL 쿼리 동기화)
- 다크모드 토큰화 (brutalist/cozy 외 추가 테마)
- 접근성 감사(대비, 포커스 링, 스크린리더 라벨)
- 대시보드 위젯 재배치(사용자 커스터마이즈)
- 모바일 테이블의 카드 뷰 대체

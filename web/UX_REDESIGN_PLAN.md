# 트레이딩 의사결정 강화 계획



---



# UX Redesign Plan 검토 및 통합 실행 계획 (2026-04-10)



## Context

`web/UX_REDESIGN_PLAN.md`(341 lines)는 대시보드 UX 개편을 위한 방향 문서로 작성되었지만, 실제 코드를 탐색한 결과 **Stage 1 권장 항목의 약 80%가 이미 구현되어 있음**. 문서를 그대로 따라가면 중복 작업이 발생하므로, 남은 작업만 체감 개선 순으로 재정렬한다.



## 타당성 평가



### 설계 원칙: **타당함**

- "스캔 → 선택 → 상세 진입" 흐름, 의사결정 프리뷰, 색 의미 고정, 구조화된 카드 등 원칙은 전문 트레이더 워크플로우와 일치.

- 정보량보다 우선순위 표현을 먼저 개선한다는 접근은 현재 대시보드 문제(정보 과밀)에 정확히 부합.



### 문제점: **현실과 진행 상태 인식 차이**

문서는 "아직 해야 할 일" 관점으로 쓰여 있지만, 실제 코드(`TraderDashboardPanels.tsx`, `WatchlistTable.tsx`, `trader.ts`)를 보면 Stage 1 대부분이 이미 라이브다.



## 이미 구현된 항목 (재작업 불필요)



| UX 플랜 항목 | 실제 구현 위치 |

|---|---|

| Today Setup 카드 (3~5개, 점수, 이유 태그) | `TraderDashboardPanels.tsx:8-59` |

| Setup Score + Focus 라벨 + 기여 요인 | `trader.ts:103-179` (`computeSetupScore`) |

| Earnings Board (오늘/D-3/D-7/D-21 타임라인) | `TraderDashboardPanels.tsx:61-107` |

| Catalyst Feed Hard/Medium/Soft 탭 + 부제 | `TraderDashboardPanels.tsx:109-181` |

| Signal Performance Board | `TraderDashboardPanels.tsx:183-207` |

| 4단 카드 구조(헤더/수치/칩/Action·Positioning·Sizing) | `WatchlistTable.tsx:36-130` |

| Stat 카드 톤 (Price/Change/7D·30D/Earnings) | `WatchlistTable.tsx:59-82` |

| Action 한 줄 요약 + 펼치기 진입존/무효화/다음 촉매 | `WatchlistTable.tsx:100-114` (`<details>`) |

| 2ATR 스탑 / 보유 주 수 / R/R 사이징 | `trader.ts:340-366` (`buildPositionSizingSummary`) |

| 계좌 크기 10K/50K/100K 프리셋 | `Dashboard.tsx:138-161` |

| 트레이더 필터 칩 6종 | `Dashboard.tsx:163-194` |

| 카드 정렬 (점수/실적 임박/하드 촉매) | `Dashboard.tsx:208-232` |



## 남은 작업 (우선순위 재정렬)



### P0 — 즉시 체감 개선



1. **Positioning 2×2 미니 그리드**

   - 현재: `WatchlistTable.tsx:116-120`에서 `buildDashboardPositioningSummary` 한 줄 요약만 노출.

   - 변경: 2×2 그리드로 `공매도 % / 애널리스트 / 기관 보유 / 옵션 IV` 노출.

   - 파일: `web/src/components/WatchlistTable.tsx`, `web/src/utils/trader.ts`(새 헬퍼 `buildPositioningGrid`), `web/src/styles/global.css`(`.watchlist-positioning-grid`).

   - 재사용: `ticker.fundamentals`의 `short_float_pct`, `analyst_recommendation`, `held_by_institutions`, `implied_volatility`는 이미 수집 완료.



2. **상세페이지 통합 "트레이더 의사결정 보드"**

   - 현재: `TickerDetail.tsx`에서 방향/진입존/무효화/catalyst/2ATR 스탑/R/R가 여러 섹션에 분산.

   - 변경: 페이지 최상단 고정 요약 카드 하나 추가.

   - 파일: `web/src/pages/TickerDetail.tsx`, `web/src/components/TraderDecisionBoard.tsx`(신규), `trader.ts`의 `extractActionPlan` + `buildPositionSizingSummary` 재사용.



3. **Sticky Quick Bar (상단 고정 조작 바)**

   - 현재: 검색/섹터/계좌/필터 칩이 상단에 이어지며 흐름을 끊음.

   - 변경: 스크롤 시 검색 + 섹터 + 계좌 + 정렬 칩을 `position: sticky`로 고정.

   - 파일: `web/src/pages/Dashboard.tsx`(컨테이너 구조 수정), `web/src/styles/global.css`(`.dashboard-quick-bar`).



### P1 — 사용성 고도화



4. **용어 툴팁 (ATR, RVOL, RS vs SPY, beat/miss, Forward vs TTM)**

   - 방식: `<abbr title>` 또는 신규 `InfoTooltip` 컴포넌트 — 의존성 추가 없이 CSS hover.

   - 파일: `web/src/components/InfoTooltip.tsx`(신규 ~30 lines), `WatchlistTable.tsx` Stat 라벨, `TraderDashboardPanels.tsx` kicker.



5. **빈 상태 친절 메시지**

   - 현재: `Dashboard.tsx:236`, CatalystFeed `"표시할 촉매가 없습니다."` 등 N/A 수준.

   - 변경: 상황 기반 대체 제안 — 예 `"오늘은 하드 촉매가 없습니다. 대신 실적 임박 종목을 먼저 보세요."`

   - 파일: `Dashboard.tsx`, `TraderDashboardPanels.tsx`.



6. **카드 밀도 모드 (Compact / Comfortable / Focus)**

   - 방식: Dashboard 상단 토글 → `data-density` 속성 → CSS 변수로 padding/font-size.

   - 파일: `Dashboard.tsx`(state + toggle), `global.css`.

   - 스코프: 패딩·폰트·gap만 — 레이아웃 구조 유지, 회귀 리스크 최소화.



### P2 — 접근성/품질



7. **색 의미 표준화 감사**

   - 현재 `--color-up/down/neutral` 외에 ad-hoc `stat-tone-*` 클래스 혼재.

   - 작업: `global.css`의 사용 색을 4개 팔레트(초록/노랑/빨강/보라)로 수렴, 동일 상태가 다른 색을 쓰지 않도록 정리.



8. **키보드 포커스 & 모바일 아코디언**

   - 토글/필터 칩 `<button>`은 이미 포커스 가능 — `focus-visible` outline 명확화.

   - 모바일: `TickerDetail.tsx`의 긴 섹션을 `<details>` 기본 접힘으로 변환(데스크톱은 CSS로 열림 유지).



### 제외 — 현 시점에서 과잉 투자



- 점수 가중치 보기 / 사용자 프리셋 / 관심 모드별 보기(Stage 3): 단일 유저 운영 중이라 사용 패턴 관찰 후 결정.

- Catalyst Feed 기사 중요도 재설명: 이미 `catalystNote` 부제가 노출됨.



## 핵심 파일 요약



| 파일 | 변경 |

|---|---|

| `web/src/components/WatchlistTable.tsx` | Positioning 2×2 그리드 교체, 툴팁 주입 |

| `web/src/utils/trader.ts` | `buildPositioningGrid()` 신규 (`buildDashboardPositioningSummary`는 상세 페이지에서 계속 사용) |

| `web/src/pages/Dashboard.tsx` | Sticky Quick Bar, 밀도 토글, 빈 상태 메시지 |

| `web/src/pages/TickerDetail.tsx` | 상단 `TraderDecisionBoard` 삽입, 긴 섹션 `<details>` |

| `web/src/components/TraderDecisionBoard.tsx` | 신규 — 방향/진입존/무효화/catalyst/2ATR/R/R 단일 카드 |

| `web/src/components/InfoTooltip.tsx` | 신규 — CSS hover 기반 |

| `web/src/components/TraderDashboardPanels.tsx` | kicker 툴팁, 빈 상태 메시지 개선 |

| `web/src/styles/global.css` | quick-bar sticky, positioning-grid, 밀도 data-attr, focus-visible, 색 팔레트 감사 |



## Verification



자동 테스트는 없으므로 `pnpm dev`로 수동 회귀 확인.



1. `cd web && pnpm build` — Vite 빌드 성공(TS 에러 0).

2. `pnpm dev` 후:

   - [ ] 스크롤 시 Quick Bar 상단 고정

   - [ ] Positioning 2×2 그리드에 short_float / analyst / institutions / IV 표시

   - [ ] `/ticker/AAPL` 최상단 의사결정 보드 카드 렌더링

   - [ ] ATR/RVOL 라벨 hover 시 툴팁

   - [ ] Compact/Comfortable/Focus 토글 시 카드 패딩 변경

   - [ ] 필터 조합 빈 상태에 친절 메시지

3. Chrome DevTools Device Mode(iPhone 12)에서 `/ticker/AAPL` 섹션 아코디언 동작 확인.

4. Python 파이프라인 영향 없음 — 테스트 재실행 불필요.



---



## 구현 완료 상태 (2026-04-09 기준)



Phase 1-5 **모두 구현 완료** (사용자가 직접 구현). 다음 테스트 파일 전부 존재:

- `tests/test_price_action.py` ✓ (ATR, RVOL, gap, SMA, RS 계산)

- `tests/test_earnings_setup.py` ✓

- `tests/test_earnings_beat_miss.py` ✓

- `tests/test_signal_tracker.py` ✓

- `tests/test_trade_frame.py` ✓

- `tests/test_sec_item_parsing.py` ✓



---



## 현재 작업: EarningsSetup N/A 수정 + 추가 개선



### 진단 결과



**데이터 파이프라인 자체는 정상**: `forward_eps`, `earnings_growth` 모두 `price.py` line 232-233에서 `CollectedTickerData`에 올바르게 저장되고, `_build_fundamentals()`가 `research_note.py` line 717-730에서 올바르게 `fundamentals` dict에 포함시킴. 렌더링 버그 없음.



**N/A 원인별 분류:**



| 필드 | 원인 | 수정 가능 여부 |

|------|------|---------------|

| Forward EPS | yfinance `forwardEps` = None (일부 종목에서 미제공) | 부분 수정 가능 |

| Forward vs TTM | Forward EPS가 N/A이므로 계산 불가 | Forward EPS 수정 시 연동 해결 |

| EPS Growth | yfinance `earningsGrowth` = None | 부분 수정 가능 |

| 최근 분기 추정 EPS | yfinance 하드코드 N/A; AV API key 필요 | AV key 설정 시 해결 |

| 최근 분기 결과 (beat/miss) | 동일 | AV key 설정 시 해결 |

| **다음 실적 체크포인트** | **`_EVENT_LOOKAHEAD_DAYS = 14`로 실적일(보통 20-90일 후) 필터링** | **즉시 수정 가능** |



---



## 수정 작업 1: 다음 실적 체크포인트 (즉시 수정)



**파일**: `src/collector/price.py` line 29



**문제**: `_EVENT_LOOKAHEAD_DAYS = 14` — 14일 초과 이벤트 전부 제거. 실적 발표일은 보통 2-12주 후.



**수정**:

```python

_EVENT_LOOKAHEAD_DAYS = 14      # 배당락일 등 단기 이벤트

_EARNINGS_LOOKAHEAD_DAYS = 90   # 실적 발표일 (분기 주기 = ~90일)

```



`_normalize_upcoming_events()` 내부 line 643:

```python

# 기존

if days_until < 0 or days_until > _EVENT_LOOKAHEAD_DAYS:



# 변경

max_days = _EARNINGS_LOOKAHEAD_DAYS if event_type == "earnings" else _EVENT_LOOKAHEAD_DAYS

if days_until < 0 or days_until > max_days:

```



---



## 수정 작업 2: Forward EPS / EPS Growth 개선



**파일**: `src/collector/price.py`



**추가 소스 시도 순서**:

1. yfinance `info.get('forwardEps')` → 이미 수집 중

2. yfinance `info.get('epsForward')` → 이미 시도 중

3. `_derive_forward_eps(price, info.get('forwardPE'))` → 이미 시도 중

4. **신규**: yfinance `ticker.analyst_price_targets`에서 `'consensusMeanEps'` 추출 시도



EPS Growth 추가 소스:

1. yfinance `info.get('earningsGrowth')` → 이미 수집

2. yfinance `info.get('earningsQuarterlyGrowth')` → 이미 시도

3. **신규**: quarterly_financials에서 최근 2분기 EPS 비교로 YoY 직접 계산

   ```python

   if len(qf) >= 4:  # 4분기 전과 현재 비교

       yoy_growth = (current_eps - year_ago_eps) / abs(year_ago_eps)

   ```



---



## 수정 작업 3: 최근 분기 beat/miss (Alpha Vantage 의존성 명시)



**현재 상태**: `ALPHAVANTAGE_API_KEY` 설정 시 자동으로 `_extract_alpha_quarterly_financials()`에서 제공됨. API key 없으면 N/A는 불가피.



**추가 개선**: yfinance `ticker.earnings_history` DataFrame 시도

```python

eh = getattr(ticker, 'earnings_history', None)

# columns: epsActual, epsEstimate, epsDifference, surprisePercent

```



`_extract_yfinance_quarterly_financials()` 내부에서 `earnings_history`가 있으면 `estimated_eps` / `surprise_pct` / `beat_miss` 채우기.



---



## 구현 순서



1. `src/collector/price.py`: `_EVENT_LOOKAHEAD_DAYS` → `_EARNINGS_LOOKAHEAD_DAYS` 분리 (5분)

2. `src/collector/price.py`: `_extract_yfinance_quarterly_financials()`에 `ticker.earnings_history` 활용 (20분)

3. `src/collector/price.py`: EPS Growth yfinance quarterly 비교 fallback (15분)

4. 기존 테스트 40개 통과 확인: `python -m unittest discover tests/ -v`



---



## Context (원래 계획)



---



## 현재 코드 상태 (탐색 결과)



### 수집 레이어 (price.py)

- yfinance `ticker.history(period="6mo", interval="1d")` 이미 받음 → High/Low 컬럼 있으나 미사용

- `volume`, `averageVolume` 이미 수집 → RVOL 계산 가능

- `previousClose`, `regularMarketPrice` 수집 → gap% 계산 가능

- `fiftyDayAverage`, `twoHundredDayAverage` 수집 → SMA 위치 계산 가능

- `fiftyTwoWeekHigh`, `fiftyTwoWeekLow` 수집 → 52주 위치 계산 가능

- EPS consensus/beat/miss: Alpha Vantage `earnings.quarterlyEarnings`에 `estimatedEPS`, `surprise`, `surprisePercentage` 있음



### SEC 공시 (sec_edgar.py)

- `_RELEVANT_FORMS` 에서 8-K, 10-Q, 10-K 등 수집

- 카테고리 분류: 텍스트 키워드 패턴 매칭 (dividend, proxy 등)

- 8-K Item number 파싱 **미구현** — "Item 2.02", "Item 5.02" 등 title/description 파싱 추가 가능



### 뉴스 신선도 (news_rss.py)

- `_news_rank_key()`: 30일 선형 감소 이미 있음

- hard/soft catalyst 구분 명시 없음

- "thesis recap" 류 필터링 없음



### AI 분석 (research_note.py)

- JSON 스키마: `summary`, `key_news`, `financial_highlights`, `risks_or_watchpoints`, `signal_or_takeaway` 5개 필드

- bull/base/bear 시나리오, 무효화 가격 **없음** → 스키마 확장 필요



### 웹 프론트 (TickerDetail.tsx)

- 섹션: 헤더, 최신 공시 카드, 가격 차트, 요약, 다가오는 일정, 뉴스, SEC 공시, 재무 하이라이트, 분기 재무, 리스크, 스냅샷, 타임라인, 시그널

- ATR/RVOL/상대강도 섹션 **없음**

- 트레이드 프레임 섹션 **없음**



---



## Phase 1: 가격 행동 맥락 강화 (ATR / RVOL / Gap / 상대강도)



### 목적

"왜 지금 건드릴 만한 차트인지" 데이터 추가



### 수정 파일



**`src/types.py`** — `CollectedTickerData`에 필드 추가:

```python

atr_14d: str = "N/A"          # 14일 ATR (절대값)

atr_percent: str = "N/A"      # ATR / price * 100 (변동성 %)

relative_volume: str = "N/A"  # volume / avg_volume_3m

gap_percent: str = "N/A"      # (open - prev_close) / prev_close * 100

price_vs_sma50: str = "N/A"   # (price - sma50) / sma50 * 100

price_vs_sma200: str = "N/A"  # (price - sma200) / sma200 * 100

week52_position: str = "N/A"  # (price - 52w_low) / (52w_high - 52w_low) * 100

rs_vs_spy: str = "N/A"        # price_change_30d - SPY_30d_change

```



**`src/collector/price.py`** — `_collect_single_ticker()` 내부에 계산 추가:

- `_calc_atr_14d(history)`: High/Low/Close에서 True Range 14일 평균

- `_calc_gap_percent(info)`: `regularMarketOpen` vs `previousClose`

- `_calc_relative_volume(info)`: `volume` / `averageVolume`

- `_calc_price_vs_sma(price, sma)`: 이미 sma_50, sma_200 수집 중이므로 비율만 계산

- `_calc_week52_position(price, high, low)`: (price - low) / (high - low) * 100

- RS 계산: `collect_market_overview()`가 이미 ^GSPC 30d 수집 → 별도로 전달하거나 market overview에서 30d 변화 추출



ATR 계산 로직:

```python

def _calc_atr_14d(history) -> tuple[float | None, float | None]:

    # history["High"], history["Low"], history["Close"] 접근

    # True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)

    # ATR = 14일 평균 TR

```



**`src/output/markdown.py`** — `render_ticker_markdown()`의 "## 데이터 스냅샷" 또는 별도 "## 가격 행동" 섹션:

```

## 가격 행동 맥락

- ATR(14): 5.23 (2.02%)

- Relative Volume: 1.42x

- Gap: +0.8%

- vs SMA50: +3.2% (위)

- vs SMA200: +8.1% (위)

- 52주 위치: 73%

- RS vs SPY(30D): +4.1%

```



**`src/output/json_export.py`** — `_serialize_analysis()`에 `price_action` 필드 추가



**`web/src/pages/TickerDetail.tsx`** — DataSnapshot 또는 별도 PriceActionCard 컴포넌트



### 테스트

- `tests/test_price_action.py` 신규 — ATR, RVOL, gap, SMA 위치 계산 단위 테스트



---



## Phase 2: 실적 기대치 레이어 (EPS Consensus / Beat / Miss)



### 목적

"시장이 원래 뭘 기대했고, 실제가 얼마나 달랐는지" 표시



### 데이터 소스

Alpha Vantage `EARNINGS` API → `quarterlyEarnings` 배열:

```json

{

  "fiscalDateEnding": "2025-12-31",

  "reportedDate": "2026-01-29",

  "reportedEPS": "2.40",

  "estimatedEPS": "2.35",

  "surprise": "0.05",

  "surprisePercentage": "2.1277"

}

```



yfinance `info`에서도 일부 수집 가능:

- `info.get('epsTrailingTwelveMonths')` → TTM EPS

- `info.get('epsForward')` → Forward EPS (consensus)

- `info.get('earningsGrowth')` → YoY EPS 성장률



### 수정 파일



**`src/types.py`** — `quarterly_financials` 항목 필드 확장:

- 기존: `quarter, revenue, operating_income, eps`

- 추가: `estimated_eps, surprise_pct, beat_miss` ("beat"/"miss"/"in-line")



**`src/collector/price.py`**:

- `_extract_yfinance_quarterly_financials()`: 현재 EPS만 수집. `forwardEps` 추가

- `_extract_alpha_quarterly_financials()`: `estimatedEPS`, `surprise`, `surprisePercentage` 추가

- `_classify_beat_miss(reported, estimated)`: 5% 이상 → "beat", -5% 이하 → "miss", 나머지 → "in-line"



**`src/output/markdown.py`** — `_render_quarterly_financials()`:

```markdown

| 분기 | 매출 | EPS | EPS추정 | 서프라이즈 | 결과 |

|------|------|-----|---------|-----------|------|

| 2025-Q4 | 124.3B | 2.40 | 2.35 | +2.1% | ✅ beat |

| 2025-Q3 | 119.6B | 2.30 | 2.38 | -3.4% | ❌ miss |

```



**`web/src/types/index.ts`** — `QuarterlyFinancialRow` 확장:

```typescript

interface QuarterlyFinancialRow {

  quarter: string

  revenue: string

  operating_income: string

  eps: string

  estimated_eps?: string

  surprise_pct?: string

  beat_miss?: 'beat' | 'miss' | 'in-line'

}

```



**`web/src/pages/TickerDetail.tsx`** — 분기 재무 테이블에 beat/miss 배지 컬럼 추가



### 테스트

- `tests/test_earnings_beat_miss.py` — beat/miss 분류 로직 단위 테스트



---



## Phase 3: 8-K Item 세분화 + Hard/Soft Catalyst 구분



### 목적

"같은 8-K라도 Item 2.02(실적)와 Item 5.02(CEO 교체)는 완전히 다름"



### 8-K Item 우선순위 매핑 (추가할 상수)

```python

_8K_ITEM_MAP = {

    "2.02": ("실적 발표", "hard", 200),     # Results of Operations

    "5.02": ("임원 교체", "hard", 180),     # Director/Officer Changes

    "1.01": ("주요 계약", "hard", 160),     # Material Definitive Agreement

    "8.01": ("기타 중요 공시", "medium", 120),

    "7.01": ("Reg FD 공시", "medium", 100),

    "1.05": ("중요 사이버보안", "hard", 150),

    "2.01": ("자산 취득/처분", "medium", 130),

}

```



### 수정 파일



**`src/collector/sec_edgar.py`**:

- `_parse_8k_item_number(title_or_description)`: 정규식으로 "Item X.XX" 패턴 추출

  ```python

  import re

  _ITEM_PATTERN = re.compile(r'item\s+(\d+\.\d+)', re.IGNORECASE)

  ```

- `_classify_filing_category()` 수정: 8-K는 item number로 분류 우선



**`src/utils/sec_filings.py`**:

- 반환 dict에 `catalyst_type: "hard" | "soft" | "medium"` 추가

- 반환 dict에 `importance_score: int` 추가



**`src/collector/news_rss.py`** — `_news_rank_key()` 수정:

- 현재: SEC 공시 태그 기반 점수 (실적 140, 배당 110 등)

- 변경: `importance_score` 기반으로 직접 반영

- 신선도 하향 로직 강화: soft catalyst (일반 뉴스)는 3일 이상이면 급감

  ```python

  # 현재: age_score = max(0, 30 - days_old)  (30일 선형)

  # 변경: catalyst_type에 따라 감쇠 속도 차별화

  if catalyst_type == "hard":

      age_score = max(0, 30 - days_old)   # 기존 유지

  elif catalyst_type == "medium":

      age_score = max(0, 14 - days_old)   # 14일 이후 0점

  else:  # soft

      age_score = max(0, 7 - days_old)    # 7일 이후 0점

  ```

- "thesis recap" 필터: 제목에 "why", "how", "what is", "explained", "recap", "analysis of" 포함 시 -30점



**`web/src/types/index.ts`** — `SecFilingReference` 확장:

```typescript

interface SecFilingReference {

  tag: string

  title: string

  form_type: string

  item_number?: string       // "2.02", "5.02" 등

  catalyst_type?: 'hard' | 'medium' | 'soft'

  importance_score?: number

  published_at: string

  link: string

  source: string

}

```



**`web/src/pages/TickerDetail.tsx`** — 공시 카드에 catalyst 배지 추가:

- 🔴 hard catalyst (2.02, 5.02 등)

- 🟡 medium catalyst

- ⚪ soft catalyst



### 테스트

- `tests/test_sec_item_parsing.py` — 8-K item 파싱 단위 테스트



---



## Phase 4: AI 트레이드 프레임 (Bull/Base/Bear + 무효화 가격)



### 목적

"어디서 틀렸다고 볼지" — 시나리오와 무효화 가격 출력



### AI JSON 스키마 확장



**`src/analyzer/research_note.py`** — `_response_schema()` 수정:



기존 스키마 필드 + 추가:

```python

"trade_frame": {

    "type": "object",

    "properties": {

        "bull_scenario": {"type": "string"},   # 상승 시나리오 조건

        "base_scenario": {"type": "string"},   # 기본 시나리오 (가장 가능성 높음)

        "bear_scenario": {"type": "string"},   # 하락 리스크 시나리오

        "invalidation_price": {"type": "string"},  # 이 가격 밑으로 가면 bear 확정

        "watch_period": {"type": "string"}     # 관찰 기간 (e.g., "2026-04-15 실적 전까지")

    },

    "required": ["bull_scenario", "base_scenario", "bear_scenario", "invalidation_price", "watch_period"]

}

```



프롬프트 추가 지시:

```

For trade_frame:

- bull_scenario: what conditions would push this higher (catalyst, chart breakout, etc.)

- base_scenario: most likely outcome given current data

- bear_scenario: what would cause a meaningful drop

- invalidation_price: specific price level that would confirm bear scenario (e.g. "below 50D SMA at 245.3")

- watch_period: how long this analysis is valid (e.g. "until earnings on 2026-04-30" or "next 5 trading days")

Keep each field under 2 sentences. Use specific price levels where possible.

```



**`src/types.py`** — `TickerAnalysis`에 필드 추가:

```python

trade_frame: dict[str, str] = field(default_factory=dict)

# keys: bull_scenario, base_scenario, bear_scenario, invalidation_price, watch_period

```



**`src/output/markdown.py`** — `render_ticker_markdown()`에 섹션 추가:

```markdown

## 트레이드 프레임

- **Bull**: 실적 beat + guidance 상향 시 52주 고점 재테스트

- **Base**: 현재 레인지 내 횡보, 실적 대기

- **Bear**: 52주 고점 275 저항 돌파 실패 + 거래량 감소

- **무효화**: SMA50 (245.3) 하향 이탈 시

- **관찰 기간**: 2026-04-30 실적 발표 전까지

```



**Fallback 시 기본값**: 가격/SMA 기반 rule-based 생성

```python

def _build_fallback_trade_frame(data: CollectedTickerData) -> dict[str, str]:

    # SMA50 기반 무효화 가격 자동 생성

    # 등락률 기반 시나리오 템플릿

```



**`src/output/json_export.py`** — `_serialize_analysis()`에 `trade_frame` 필드 추가



**`web/src/types/index.ts`** — `TradeFrame` 인터페이스 추가:

```typescript

interface TradeFrame {

  bull_scenario: string

  base_scenario: string

  bear_scenario: string

  invalidation_price: string

  watch_period: string

}

```



**`web/src/pages/TickerDetail.tsx`** — TradeFrame 섹션 추가:

- 3열 카드 (Bull 🟢 / Base 🟡 / Bear 🔴)

- 무효화 가격 + 관찰 기간 하단 표시



### 테스트

- `tests/test_trade_frame.py` — fallback 트레이드 프레임 생성 단위 테스트



---



## Phase 5: 시그널 사후 성과 추적



### 목적

"어떤 시그널 조합이 실제로 먹히는지" 자동 추적



### 데이터 모델



`output/data/signal_tracker.csv`:

```

signal_date, ticker, signal_type, signal_direction, signal_price, 

catalyst_tag, news_tone, trade_frame_scenario,

return_1d, return_5d, return_20d,

evaluated_1d, evaluated_5d, evaluated_20d

```

- `signal_direction`: bull / bear / neutral (signal_or_takeaway에서 파생)

- `evaluated_*`: False 초기화 → 기간 경과 시 True로 업데이트



### 수정 파일



**`src/utils/signal_tracker.py`** 신규:

```python

def record_signals(analyses: list[TickerAnalysis], run_date: date, price_lookup: dict[str, float]) -> None:

    """오늘 시그널을 CSV에 기록"""



def update_signal_returns(csv_path: Path, run_date: date, price_lookup: dict[str, float]) -> int:

    """1d/5d/20d 경과한 시그널의 실제 수익률 업데이트. 업데이트된 row 수 반환"""



def load_signal_stats(csv_path: Path) -> dict[str, Any]:

    """시그널 타입별 승률, 평균 수익률 통계 계산"""

```



**`src/pipeline.py`** 수정:

```python

# collect 이후

price_lookup = {ticker: data.price for ticker, data in collected.items() if data.price}

signal_tracker.update_signal_returns(signal_csv_path, effective_date, price_lookup)



# write_outputs 이후

signal_tracker.record_signals(analyses, effective_date, price_lookup)

```



**`src/output/markdown.py`** — `render_weekly_markdown()` 수정:

```markdown

## 시그널 검증 결과 (지난 20거래일)

| 날짜 | 종목 | 방향 | 촉매 | 1D | 5D | 20D |

|------|------|------|------|-----|-----|-----|

| 04-01 | AAPL | bull | 8-K 2.02 | +1.2% | +3.4% | +5.1% |

| 03-25 | NVDA | bear | miss | -2.1% | -4.3% | - |



**bull 시그널 5일 승률: 64% (평균 +2.1%)**

```



**`src/output/json_export.py`** — `dashboard.json`에 `signal_stats` 섹션 추가



**`web/src/pages/TickerDetail.tsx`** — 종목별 시그널 히스토리 미니 뷰 (타임라인에 통합)



### 테스트

- `tests/test_signal_tracker.py` — 시그널 기록, 수익률 업데이트, 통계 계산 단위 테스트



---



## 추가: 뉴스 신선도 강화 (Phase 3에 통합)



이미 Phase 3에서 `_news_rank_key()` 수정 시 함께 처리:

- hard catalyst (실적/SEC/IR): 30일 감쇠 유지

- medium catalyst (Bloomberg, Reuters 속보): 14일 감쇠

- soft catalyst (일반 해설, thesis recap): 7일 감쇠 + thesis recap 키워드 -30점



---



## 구현 순서 및 파일 요약



| Phase | 핵심 변경 파일 | 신규 파일 |

|-------|---------------|---------|

| 1 (ATR/RVOL/Gap/RS) | `price.py`, `types.py`, `markdown.py`, `json_export.py`, `TickerDetail.tsx` | `tests/test_price_action.py` |

| 2 (EPS beat/miss) | `price.py`, `markdown.py`, `json_export.py`, `types/index.ts`, `TickerDetail.tsx` | `tests/test_earnings_beat_miss.py` |

| 3 (8-K Item/Catalyst) | `sec_edgar.py`, `sec_filings.py`, `news_rss.py`, `types/index.ts`, `TickerDetail.tsx` | `tests/test_sec_item_parsing.py` |

| 4 (트레이드 프레임) | `research_note.py`, `types.py`, `markdown.py`, `json_export.py`, `types/index.ts`, `TickerDetail.tsx` | `tests/test_trade_frame.py` |

| 5 (시그널 추적) | `pipeline.py`, `markdown.py`, `json_export.py`, `TickerDetail.tsx` | `src/utils/signal_tracker.py`, `tests/test_signal_tracker.py` |



## 설계 원칙 준수 사항

- 모든 계산은 `collect` 또는 `utils` 단계에서 수행 — `analyzer`/`output`에서 외부 API 호출 없음

- 각 Phase는 독립 배포 가능 — 하나 실패해도 다른 Phase에 영향 없음

- Alpha Vantage beat/miss 데이터는 기존 fallback 로직 내에서 보완 (KEY 없으면 N/A)

- 기존 테스트 40개 모두 통과 유지



## 검증 방법

```bash

# 각 Phase 완료 후

python -m unittest discover tests/ -v



# Phase 1 완료 후: price_action 필드가 종목 노트에 출력되는지 확인

python main.py  # ENABLE_EXTERNAL_FETCH=false 환경에서 fallback 모드



# Phase 5 완료 후: signal_tracker.csv 생성 및 weekly 노트에 검증 결과 출력 확인

```



---



---



# Phase 6-8: 전문 트레이더 추가 기능 & 품질 개선



## 현황 진단 (탐색 결과 기준)



**이미 구현된 것 (Phase 1-5):**

- ATR(14), RVOL, Gap%, SMA50/200 위치, 52주 포지션, RS vs SPY ✓

- 실적 beat/miss (Alpha Vantage key 있을 때) ✓

- Trade Frame (bull/base/bear + 무효화가격) ✓

- Signal Tracker (1D/5D/20D 수익률 추적) ✓

- 8-K Item 분류, hard/soft catalyst 구분 ✓



**여전히 빠진 핵심 데이터 (yfinance에서 무료로 수집 가능):**

- 공매도 비율 (Short Float %) → `info.get('shortPercentOfFloat')`

- 애널리스트 컨센서스 (매수/중립/매도 + 목표가) → `info.get('targetMeanPrice')`, `recommendationMean`

- 내부자/기관 보유 비율 → `info.get('heldPercentInsiders')`, `info.get('heldPercentInstitutions')`

- 옵션 내재변동성 → `info.get('impliedVolatility')`



**답변 품질 문제:**

- GPT 프롬프트에 price_action 데이터(ATR, RVOL, RS) 포함 안 됨 → LLM이 가격 맥락 없이 서술

- `financial_highlights`가 너무 서술적, 수치 미포함 (마진율, FCF, ROIC)

- `signal_or_takeaway`가 단순 방향 서술 — 진입존·손절가 없음

- `trade_frame` 프롬프트에 ATR 값이 없어 구체적 스탑 계산 불가



---



## Phase 6: 데이터 수집 확장 (yfinance 추가 필드)



### 목적

공매도·기관·내부자·목표가 — 스마트머니 포지션 파악



### 수정: `src/collector/price.py` + `src/types.py`



**`CollectedTickerData`에 추가할 필드:**

```python

short_float_pct: str = "N/A"        # 공매도 비율 (% of float)

short_ratio: str = "N/A"            # 공매도 커버링 일수

analyst_target_price: str = "N/A"   # 애널리스트 평균 목표가

analyst_recommendation: str = "N/A" # Strong Buy / Buy / Hold / Sell / Strong Sell

analyst_count: str = "N/A"          # 추정 참여 애널리스트 수

held_by_insiders: str = "N/A"       # 내부자 보유 비율 (%)

held_by_institutions: str = "N/A"   # 기관 보유 비율 (%)

implied_volatility: str = "N/A"     # 옵션 IV (연환산)

```



**`price.py` 수집 로직 (기존 yfinance `info` dict에서 추가):**

```python

short_float_pct = _format_percentage(info.get('shortPercentOfFloat'))

short_ratio = _format_ratio(info.get('shortRatio'))

analyst_target_price = _format_price(info.get('targetMeanPrice'))

analyst_recommendation = _map_recommendation(info.get('recommendationMean'))

analyst_count = str(info.get('numberOfAnalystOpinions') or 'N/A')

held_by_insiders = _format_percentage(info.get('heldPercentInsiders'))

held_by_institutions = _format_percentage(info.get('heldPercentInstitutions'))

implied_volatility = _format_percentage(info.get('impliedVolatility'))

```



**`_map_recommendation(score)` 신규 헬퍼:**

```python

def _map_recommendation(score: float | None) -> str:

    # yfinance: 1.0=Strong Buy, 2.0=Buy, 3.0=Hold, 4.0=Sell, 5.0=Strong Sell

    if score is None: return "N/A"

    if score <= 1.5: return "Strong Buy"

    if score <= 2.5: return "Buy"

    if score <= 3.5: return "Hold"

    if score <= 4.5: return "Sell"

    return "Strong Sell"

```



**`src/analyzer/research_note.py` `_build_fundamentals()` 확장:**

- 위 8개 필드를 `fundamentals` dict에 추가



**`src/output/markdown.py` 출력:**

```markdown

## 포지셔닝 데이터

- 공매도: 3.2% of float (커버 2.1일)

- 애널리스트: Buy (18명, 목표가 $310.50)

- 내부자 보유: 0.07% / 기관 보유: 61.3%

- 옵션 IV: 28.4% (연환산)

```



**`web/src/pages/TickerDetail.tsx`:** 기존 "데이터 스냅샷" 섹션에 카드 추가 또는 별도 "포지셔닝" 섹션



### 테스트

- `tests/test_positioning_data.py` 신규 — `_map_recommendation()` 경계값, `_format_percentage()` N/A 처리



---



## Phase 7: GPT 프롬프트 품질 강화



### 목적

LLM이 수집된 정량 데이터를 실제로 활용하도록 프롬프트 개선



### 문제 (현재 `src/analyzer/research_note.py`)

- 프롬프트에 `price_action` 필드(ATR, RVOL, RS vs SPY)가 포함되지 않음

- `trade_frame` 프롬프트에 구체적 가격 레벨(SMA50, 52W High) 미전달

- `signal_or_takeaway`가 1줄 서술 — 진입존/손절/목표가 없음

- `financial_highlights`가 정성적 — 마진율, FCF 수치 누락



### 수정: `src/analyzer/research_note.py`



**① 프롬프트 컨텍스트 블록 추가:**



각 종목 데이터를 LLM에 전달할 때 price_action 블록을 포함:

```python

def _build_ticker_context(analysis_input: dict) -> str:

    """LLM에 전달할 종목 컨텍스트 문자열 생성"""

    price_action = analysis_input.get("price_action", {})

    pa_block = ""

    if price_action:

        pa_block = f"""

[Price Action]

ATR(14): {price_action.get('atr_14d', 'N/A')} ({price_action.get('atr_percent', 'N/A')})

RVOL: {price_action.get('relative_volume', 'N/A')}

vs SMA50: {price_action.get('price_vs_sma50', 'N/A')}

vs SMA200: {price_action.get('price_vs_sma200', 'N/A')}

52W Position: {price_action.get('week52_position', 'N/A')}

RS vs SPY(30D): {price_action.get('rs_vs_spy', 'N/A')}

"""

    return pa_block

```



**② `trade_frame` 프롬프트 지시 강화:**

```

For trade_frame, use the provided price action data:

- invalidation_price: prefer SMA50 level when available; otherwise use ATR-based stop (price - 2×ATR)

- bull_scenario: reference specific resistance levels (52W High, analyst target)

- watch_period: use next earnings date if within 60 days, otherwise "다음 주요 catalyst"

```



**③ `signal_or_takeaway` 지시 강화:**

```

signal_or_takeaway: 한 문장. 형식: "[방향] — [핵심 catalyst] | 진입존 [가격범위] / 무효화 [가격]"

예시: "매수 관찰 — 실적 beat 기대 | 진입존 $245–250 / SMA50($242) 이탈 시 손절"

```



**④ `financial_highlights` 지시 강화:**

```

financial_highlights: 3개. 각 항목에 수치 포함 필수.

예시: "영업이익률 30.2% (전년 대비 +1.8%p)", "FCF yield 4.1%", "부채비율 42% (업종 평균 60%)"

```



**검증:** `python -m unittest tests/test_research_note_prompt.py` — 프롬프트에 price_action 블록 포함 여부 assert



---



## Phase 8: MD 출력 답변 품질 개선



### 목적

실제 트레이더가 읽을 때 "액션이 바로 보이는" 포맷으로 개선



### 현재 문제점



1. **"## 데이터 스냅샷"**: 가격/P/E/배당만 있음 — ATR, RVOL, RS 없음

2. **"## 재무 하이라이트"**: 서술 위주 — 실제 숫자 없음

3. **"## 트레이드 프레임"**: 이미 구현되었으나 ATR 기반 포지션 사이징 힌트 없음

4. **Weekly Summary**: 섹터 퍼포먼스 비교 없음



### 수정 내용



**① `src/output/markdown.py` — 스냅샷 섹션에 포지셔닝 데이터 통합:**

```markdown

## 데이터 스냅샷

| 항목 | 값 |

|------|-----|

| 현재가 | $247.96 |

| ATR(14) | 5.23 (2.1%) |

| Relative Volume | 1.42x |

| vs SMA50 | +3.2% (위) |

| vs SMA200 | +8.1% (위) |

| 52주 위치 | 73% |

| RS vs SPY(30D) | +4.1% |

| 공매도 | 3.2% float |

| 애널리스트 | Buy (18명, 목표 $310) |

| 기관 보유 | 61.3% |

| 옵션 IV | 28.4% |

```



**② ATR 기반 포지션 사이징 힌트 추가 (트레이드 프레임 하단):**

```markdown

## 포지션 사이징 참고

- ATR(14): $5.23 → 1% 리스크 기준 포지션: $10,000 계좌 → 100달러 리스크 / 5.23 ≈ 19주

- 2ATR 스탑 기준: 무효화가 $247.96 − 10.46 = **$237.50**

```



구현: `_render_position_sizing_hint(price_action: dict, account_size_hint: float = 10000) -> str`



**③ Weekly Summary 섹터 퍼포먼스 블록 추가:**



현재: 상위/하위 종목 목록만 있음

추가: 섹터별 평균 수익률 집계

```markdown

## 섹터 퍼포먼스

| 섹터 | 종목수 | 평균 주간 등락 |

|------|--------|---------------|

| Technology | 5 | +2.3% |

| Healthcare | 3 | -0.8% |

```



구현: `_render_sector_performance(analyses: list[TickerAnalysis]) -> str` — `fundamentals['sector']` 기반 집계



**④ `web/src/pages/TickerDetail.tsx` — 포지션 사이징 카드 추가 (Phase 6 데이터 활용):**

- ATR × 2 스탑 자동 표시

- 목표가까지 리스크/리워드 비율



---



## 전체 우선순위 및 구현 순서



| 순서 | 작업 | 난이도 | 영향도 | 파일 |

|------|------|--------|--------|------|

| 1 | N/A 수정 #1: `_EARNINGS_LOOKAHEAD_DAYS = 90` | 🟢 5분 | 높음 | `price.py:29` |

| 2 | N/A 수정 #2: `ticker.earnings_history` → beat/miss | 🟡 20분 | 높음 | `price.py` |

| 3 | N/A 수정 #3: EPS Growth quarterly fallback | 🟡 15분 | 중간 | `price.py` |

| 4 | Phase 6: short_float, analyst_target, IV 수집 추가 | 🟢 30분 | 높음 | `price.py`, `types.py`, `research_note.py`, `markdown.py` |

| 5 | Phase 7: GPT 프롬프트에 price_action 컨텍스트 주입 | 🟡 45분 | 매우 높음 | `research_note.py` |

| 6 | Phase 8: MD 스냅샷 + ATR 포지션 사이징 힌트 | 🟡 30분 | 높음 | `markdown.py` |

| 7 | Phase 8: Weekly 섹터 퍼포먼스 블록 | 🟡 30분 | 중간 | `markdown.py`, `weekly_summary.py` |

| 8 | Phase 6: React 대시보드 포지셔닝 섹션 | 🔴 60분 | 중간 | `TickerDetail.tsx`, `types/index.ts` |



**검증 (각 단계 후):**

```bash

python -m unittest discover tests/ -v   # 기존 테스트 통과 확인

python main.py --dry-run               # 실제 수집 없이 파이프라인 실행

```
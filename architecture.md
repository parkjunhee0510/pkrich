# 주식 리서치 자동화 시스템 — 설계 문서

> **상태**: v3  
> **작성일**: 2026-04-10  
> **작성자**: 박준희  

---

## 1. 개요

### 1.1 해결하는 문제

미국 주식 투자 시 관심 종목(10~30개)의 시세, 재무, 뉴스를 매일 수동으로 확인하는 데 시간이 많이 소요된다. 정보가 여러 소스에 흩어져 있어 일관된 판단 근거를 만들기 어렵다.

### 1.2 목표

- 관심 종목의 시세/재무/뉴스를 **자동으로 수집**하고, AI가 **구조화된 리서치 노트**를 생성
- 일일/주간 Markdown 노트 및 React 웹 대시보드로 데이터 시각화
- **시그널 트래킹**: AI 판단의 실제 수익률 추적 (1D/5D/20D)
- **포트폴리오 관리**: 보유 종목 현황, 평가손익 자동 계산
- **SEC/IR 뉴스 통합**: SEC EDGAR 공시 + 기업 IR RSS 직접 수집
- Obsidian vault에 `.md` 파일로 저장하여 누적 기록 관리 (선택적)
- **월 운영 비용 $5 이하** 유지

### 1.3 비목표 (Non-Goals)

- 자동 매매 / 트레이딩 봇이 아님
- 실시간 시세 모니터링이 아님 (일 1회 배치)
- 투자 추천/조언 시스템이 아님 — 정보 정리 도구

---

## 2. 아키텍처

### 2.1 시스템 구성도

```
┌─────────────────────────────────────────────────────┐
│                  GitHub Actions                      │
│           (cron: UTC 22:00, 월-금 자동 실행)          │
└──────────────────────┬──────────────────────────────┘
                       │ trigger
                       ▼
┌─────────────────────────────────────────────────────┐
│               pipeline.py (오케스트레이션)             │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │             수집 (Collector)                 │    │
│  │  ┌──────────────────────────────────────┐   │    │
│  │  │  price.py                            │   │    │
│  │  │  1순위: yfinance                      │   │    │
│  │  │  2순위: Stooq (가격 fallback)         │   │    │
│  │  │  3순위: Alpha Vantage (재무 fallback) │   │    │
│  │  │  시장 개요: ^GSPC, ^NDX              │   │    │
│  │  │  Price Action: ATR, RVOL, Gap, RS    │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  │  ┌──────────────────────────────────────┐   │    │
│  │  │  news_rss.py  — Google News RSS      │   │    │
│  │  │  news_search.py — DuckDuckGo 보강    │   │    │
│  │  │  ir_rss.py — 기업 IR RSS 직접 수집   │   │    │
│  │  │  sec_edgar.py — SEC EDGAR 공시 수집   │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │             분석 (Analyzer)                  │    │
│  │  research_note.py                            │    │
│  │  OpenAI Responses API, 5종목/배치            │    │
│  │  models.yaml 프로파일 (economy/standard/deep)│    │
│  │  → 실패 시 fallback (등락률 기반 한국어 노트) │    │
│  │  → cost_tracker: 실시간 API 비용 추적        │    │
│  │  → token_estimator: 사전 토큰 예산 체크      │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              후처리 (Post-processing)        │    │
│  │  portfolio.py → 포트폴리오 평가손익 계산      │    │
│  │  signal_tracker.py → 시그널 기록 + 수익률 추적│    │
│  │  earnings_setup.py → 실적 컨센서스 데이터 구축│    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              출력 (Output)                   │    │
│  │  markdown.py  → daily + weekly + tickers .md│    │
│  │  json_export.py → dashboard/price/timeline  │    │
│  │  obsidian.py  → Obsidian vault 미러 (선택적) │    │
│  │  slack.py     → Slack webhook 요약 (선택적)  │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              저장 (Datastore)                │    │
│  │  datastore.py — 추상 인터페이스              │    │
│  │  datastore_csv.py — CSV 백엔드              │    │
│  │  datastore_sqlite.py — SQLite 백엔드        │    │
│  │  DATASTORE_BACKEND 환경변수로 전환           │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              로깅 (Logging)                  │    │
│  │  pipeline_logging.py                         │    │
│  │  logs/pipeline/YYYY-MM-DD.jsonl              │    │
│  │  logs/pipeline/YYYY-MM-DD.summary.json       │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                       │
           Git auto-commit (output/**)
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           deploy-dashboard.yml                       │
│           React 대시보드 빌드 → GitHub Pages 배포    │
└─────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
1. GitHub Actions cron 트리거 (UTC 22:00 = KST 07:00, 미 장 마감 후)
2. watchlist.yaml에서 관심 종목 목록 로드
3. portfolio.yaml에서 보유 종목/매입 단가 로드
4. yfinance로 각 종목의 시세/재무 데이터 수집 (6개월 히스토리 포함)
   → 6개월 히스토리에서 7D / 30D 가격 변화율 직접 계산
   → Price Action 지표: ATR, RVOL, Gap%, SMA 포지셔닝, RS vs SPY
   → 가격 수집 실패 시 Stooq fallback
   → 재무/이벤트 수집 실패 시 Alpha Vantage fallback (KEY 설정 시)
5. ^GSPC (S&P 500), ^NDX (NASDAQ 100)으로 시장 개요 수집
6. 뉴스 수집 (4개 소스 병합):
   a. Google News RSS — 종목별 최신 뉴스 집계
   b. DuckDuckGo Search — 종목명 + 키워드 검색 보강
   c. IR RSS — 기업 공식 뉴스룸/IR 피드 직접 수집
   d. SEC EDGAR — 8-K/10-K/10-Q 등 공시 수집
   → 뉴스 소스 우선순위 + importance_score 기반 정렬
7. 수집된 데이터를 5종목씩 배치로 OpenAI Responses API에 전달
   → models.yaml 프로파일 기반 모델 선택
   → token_estimator로 사전 토큰 예산 체크
   → cost_tracker로 실시간 API 비용 추적
   → API 실패 시 등락률 기반 deterministic fallback 분석
8. 후처리:
   a. 포트폴리오 평가손익 계산 (portfolio.py)
   b. 시그널 기록 및 과거 시그널 수익률 업데이트 (signal_tracker.py)
   c. 실적 컨센서스 데이터 구축 (earnings_setup.py)
9. Markdown 출력: 일일 노트, 주간 노트, 종목별 상세 노트 생성
10. JSON 출력: dashboard.json, price_history.json, ticker_timelines.json 생성
    → web/public/output/data/에 자동 동기화
11. Datastore에 시세 이력 저장 (CSV 또는 SQLite)
12. Obsidian 동기화 (OBSIDIAN_VAULT_PATH 설정 시)
13. Slack 요약 발송 (SLACK_WEBHOOK_URL 설정 시, 포트폴리오 포함)
14. 파이프라인 이벤트 로그 기록 (JSONL + 요약 JSON)
15. Git auto-commit → GitHub Pages 대시보드 자동 배포
```

---

## 3. 컴포넌트 상세 설계

### 3.1 스케줄러 — GitHub Actions

**선택 이유**: 무료 (월 2,000분), 안정적, 코드와 동일 레포에서 관리

```yaml
# .github/workflows/stock-research.yml
name: Daily Stock Research
on:
  schedule:
    - cron: '0 22 * * 1-5'  # UTC 22:00 = 미국 장 마감 후 (월-금)
  workflow_dispatch:          # 수동 실행 가능

jobs:
  research:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m unittest discover -s tests -v
      - run: python main.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "daily: generate stock research outputs"
          file_pattern: "output/**"
```

**예상 실행 시간**: 종목 20개 기준 약 3~5분 → 월 ~100분 (무료 범위 내)

### 3.2 데이터 수집 모듈

#### 3.2.1 시세/재무 — 3단계 fallback 체인

**1순위: yfinance (무료)**

```
수집 항목:
├─ 일일 시세: 종가, 변동률 (6개월 히스토리 기반)
├─ 기간 변화율: 7일 / 30일 변화율 (6개월 히스토리에서 직접 계산)
├─ 기본 지표: PER (trailing), 시가총액, EPS (TTM)
├─ 추가 지표: Volume, P/B (Price/Book), Dividend Yield
├─ 기술 지표: 52주 고/저, 50일/200일 이동평균선
├─ 분기 재무: 최근 4분기 매출/영업이익/EPS
├─ 이벤트: 실적 발표일, 배당 일정 (upcoming_events)
├─ 공매도: Short Float %, Short Ratio
├─ 애널리스트: 목표가, 추천, 애널리스트 수
├─ 보유 비율: Insider %, Institution %
├─ 내재 변동성: Implied Volatility
├─ Price Action 지표:
│   ├─ ATR (14일), ATR %
│   ├─ Relative Volume (당일 거래량 / 3개월 평균)
│   ├─ Gap % (전일 종가 대비 당일 시가)
│   ├─ SMA 50/200 대비 포지션 (%)
│   ├─ 52주 범위 내 포지션 (%)
│   └─ RS vs SPY (20일 상대강도)
└─ 시장 개요: ^GSPC (S&P 500), ^NDX (NASDAQ 100) 직접 지수
```

**2순위: Stooq (가격 fallback)**  
yfinance에서 종가/변동률 수집 실패 시 Stooq CSV API로 대체 수집.

**3순위: Alpha Vantage (재무/이벤트 fallback)**  
`ALPHAVANTAGE_API_KEY` 설정 시 yfinance 재무/이벤트 누락 보완. 무료 티어 일 25회 제한.

**제약**: yfinance는 비공식 API이므로 과도한 호출 시 차단 가능. 종목당 1회 호출, 요청 간 1초 딜레이 적용.

#### 3.2.2 뉴스 수집 — 4개 소스 (무료)

| 소스 | 모듈 | URL/방식 | 용도 |
|---|---|---|---|
| Google News | `news_rss.py` | `news.google.com/rss/search?q={ticker}` | 종목별 최신 뉴스 집계 |
| DuckDuckGo | `news_search.py` | `ddgs` 패키지 | 종목명 + 키워드 검색 보강 |
| IR RSS | `ir_rss.py` | watchlist.yaml의 `ir_rss_feeds` | 기업 공식 뉴스룸/IR 피드 |
| SEC EDGAR | `sec_edgar.py` | `data.sec.gov/submissions/CIK{cik}.json` | 8-K/10-K/10-Q 등 공시 |

**뉴스 통합 전략**:
- `output.yaml`에서 소스별 우선순위 점수 관리 (Reuters: 5, SEC EDGAR: 4, Bloomberg: 3 등)
- 각 뉴스 아이템에 `importance_score` 부여
- SEC 공시: `form_type`과 `item_number`로 카탈리스트 유형 자동 분류
- IR RSS: `ir_source_names`로 소스명 매핑 (apple.com → "Apple Newsroom")
- 소스당 최대 표시 건수 제한 (`news_source_max_items_per_source`)
- `ENABLE_EXTERNAL_FETCH=false` 시 외부 네트워크 호출 비활성화

**SEC EDGAR 공시 분류**:

| Form Type | 카테고리 | 카탈리스트 유형 |
|---|---|---|
| 8-K | 기타 공시 | medium |
| 10-K | 연간보고서 | low |
| 10-Q | 분기보고서 | low |
| DEF 14A | 주주총회 | low |

### 3.3 AI 분석 — OpenAI Responses API

**모델 프로파일 시스템** (`config/models.yaml`):

| 프로파일 | 모델 | Context Window | 월 예상 비용 |
|---|---|---|---|
| `economy` (기본) | gpt-5.4-mini | 400K | ~$0.31 |
| `standard` | gpt-5.4 | 400K | ~$3.00 |
| `deep` | o3-mini | 200K | ~$8.00 |

선택: `OPENAI_MODEL_PROFILE` 환경변수 또는 `OPENAI_MODEL` 직접 지정.

**프롬프트 전략**:

```
입력 (종목당 ~1,500 토큰):
├─ 시세/재무 데이터 (JSON)
├─ Price Action 지표
├─ 뉴스 헤드라인 5~10개 (SEC 공시, IR 뉴스 포함)
└─ 시스템 프롬프트 (리서치 노트 포맷 지정, 한국어 출력 지시)

출력 (종목당 ~800 토큰, strict JSON schema):
├─ summary: 핵심 요약
├─ key_news: 뉴스별 한국어 요약 (입력 순서 유지)
├─ financial_highlights: 재무 하이라이트 목록
├─ risks_or_watchpoints: 리스크/주의 항목
├─ signal_or_takeaway: 한줄 시그널
└─ trade_frame: 매매 프레임 (시나리오, 진입/손절/목표)

※ news_tone은 news_tone.py (keyword 분석), 7D/30D 변화율은 price.py (yfinance 히스토리)
  에서 독립적으로 계산되어 markdown.py에서 병합됨 — AI 출력 스키마에 포함되지 않음
```

**배치 전략**: 종목을 5개씩 그룹으로 묶어 배치별 API 호출 (`_BATCH_SIZE = 5`). `token_estimator.py`로 사전 토큰 예산 체크. `BATCH_SIZE` 환경변수로 조절 가능.

**비용 추적**: `cost_tracker.py`가 매 API 응답의 `usage` 필드에서 실시간 비용 계산. `pipeline_logging`에 누적 기록.

**Fallback**: OpenAI API 실패(키 미설정 포함) 시 등락률/뉴스 기반 deterministic 한국어 노트 생성. 등락률 크기에 따라 시그널 문구 차등화.

### 3.4 후처리 모듈

#### 3.4.1 포트폴리오 트래킹

`config/portfolio.yaml`에서 보유 종목/매입 단가 로드. `portfolio.py`가 수집된 시세와 결합하여 포지션별 평가손익 계산.

```
PortfolioSummary:
├─ positions: [PortfolioPosition, ...]
│   ├─ ticker, shares, avg_cost, currency
│   ├─ market_price, market_value, cost_basis
│   └─ unrealized_pnl, unrealized_return_pct
├─ total_market_value
├─ total_cost_basis
├─ total_unrealized_pnl
└─ total_unrealized_return_pct
```

#### 3.4.2 시그널 트래커

`signal_tracker.py`가 AI의 `signal_or_takeaway` 판단을 CSV에 기록하고, 이후 파이프라인 실행 시 실제 수익률(1D/5D/20D)을 역추적하여 업데이트.

```
signal_tracker.csv 필드:
├─ signal_date, ticker, signal_type, signal_direction
├─ signal_price, catalyst_tag, news_tone
├─ trade_frame_scenario
├─ return_1d, return_5d, return_20d
└─ evaluated_1d, evaluated_5d, evaluated_20d
```

시그널 방향은 한국어/영어 키워드 매칭으로 자동 분류 (bullish: 상승/강세/반등, bearish: 하락/약세/조정 등).

#### 3.4.3 실적 컨센서스 (Earnings Setup)

`earnings_setup.py`가 분기 재무 데이터와 이벤트 일정을 종합하여 실적 셋업 데이터 구축:

- Forward EPS vs TTM EPS 비교
- EPS Growth 정규화
- 최근 분기 추정 EPS / 서프라이즈 % / Beat-Miss 판정
- 다음 실적 발표 체크포인트 (D-N 형식)

### 3.5 출력 형식

#### Markdown 노트

```
output/
├── daily/
│   ├── 2026-04-08.md          # 일일 종합 요약
│   ├── 2026-04-09.md
│   └── weekly/
│       └── 2026-W15.md        # 주간 리서치 노트
├── tickers/
│   ├── AAPL/
│   │   ├── 2026-04-08.md      # 종목별 상세 노트
│   │   └── ...
│   ├── MSFT/
│   └── NVDA/
└── data/
    ├── price_history.csv       # 시세 이력 누적
    ├── signal_tracker.csv      # 시그널 트래킹 이력
    ├── dashboard.json          # 웹 대시보드용 전체 데이터
    ├── price_history.json      # 웹 차트용 가격 이력
    └── ticker_timelines.json   # 종목별 타임라인
```

**일일 종합 노트 구조**:

```markdown
# 일일 리서치 - 2026-04-08

## 시장 개요
S&P 500: 5,234.18 (+0.45%) | NASDAQ 100: 16,892.33 (+0.62%)

## 포트폴리오 현황
| 종목 | 수량 | 평균단가 | 현재가 | 평가손익 | 수익률 |

## 관심 종목 요약
| 티커 | 가격 | 등락률 | 한줄 판단 |

## 주요 움직임

## 주요 뉴스 링크

## 점검 항목

## 다가오는 일정

## 시그널 트래킹 통계
```

**종목 노트 구조**:

```markdown
# AAPL - Apple Inc. (2026-04-08)

## 요약
## 주요 뉴스
## 재무 하이라이트
## 리스크 / 체크포인트
## 데이터 스냅샷
## Fundamentals
## Price Action
## 실적 컨센서스 셋업
## 최근 변화 비교 (7D / 30D / 뉴스 톤)
## 최근 4분기 재무
## 다가오는 일정
## 매매 프레임 (Trade Frame)
## 최근 타임라인 (최근 3일)
## 시그널 / 한줄 결론
```

**주간 노트**: 해당 주 거래일 데이터를 집계하여 상위 등락 종목, 반복 뉴스, 시그널 검증 결과, 주간 Action Items 제공.

#### JSON 출력 3종

| 파일 | 내용 | 용도 |
|---|---|---|
| `dashboard.json` | 전체 날짜별 분석 데이터 (티커, 시그널, 뉴스톤, 이벤트, SEC 공시 등) | 웹 대시보드 메인 |
| `price_history.json` | 날짜별 종가/등락률 배열 | 웹 가격 차트 |
| `ticker_timelines.json` | 종목별 날짜 타임라인 (최대 90일) | 웹 타임라인 뷰 |

파이프라인 실행 시 `web/public/output/data/`로 자동 동기화.

#### Obsidian 동기화 (선택적)

`OBSIDIAN_VAULT_PATH` 설정 시 `.md` 파일을 자동 복사:
- `${OBSIDIAN_VAULT_PATH}/pkrich/daily/YYYY-MM-DD.md`
- `${OBSIDIAN_VAULT_PATH}/pkrich/tickers/{TICKER}/YYYY-MM-DD.md`

CSV/JSON은 Obsidian으로 복사하지 않음. `output/`이 항상 source of truth.

#### Slack 알림 (완전 구현)

`SLACK_WEBHOOK_URL` 설정 시 일일 실행 후 아래 항목을 Slack Incoming Webhook으로 발송:

- 실행 날짜
- 시장 개요 (S&P 500, NASDAQ 100)
- 상위 3개 등락 종목
- 포트폴리오 현황 요약
- 점검 항목
- 다가오는 일정 최대 3건
- 생성된 일일/주간 노트 경로

미설정 또는 전송 실패 시 warning 로그만 남기고 파이프라인 계속 진행.

### 3.6 데이터 저장 (Datastore)

추상 `Datastore` 인터페이스로 CSV/SQLite 백엔드 전환 지원.

| 백엔드 | 환경변수 | 특징 |
|---|---|---|
| CSV (기본) | `DATASTORE_BACKEND=csv` | 단순, Git 추적 용이 |
| SQLite | `DATASTORE_BACKEND=sqlite` | 쿼리 유연, 대규모 데이터 적합 |

**Datastore 인터페이스**:
- `append_prices(analyses)` — 시세 이력 추가
- `load_period_changes(run_date)` — 기간별 변화율 조회
- `query_prices(tickers)` — 히스토리 가격 조회

`migrate_csv_to_sqlite.py`로 CSV → SQLite 마이그레이션 지원.

### 3.7 웹 대시보드

React 19 (Vite 8 + TypeScript 6 + Recharts 3) 기반 정적 사이트. GitHub Pages로 자동 배포.

**페이지 구성**:

| 페이지 | 컴포넌트 | 기능 |
|---|---|---|
| Dashboard | `Dashboard.tsx` | 시장 개요, 워치리스트, 섹터 요약 |
| Ticker Detail | `TickerDetail.tsx` | 가격 차트, 분기 재무, 뉴스, 타임라인 |
| Portfolio | `Portfolio.tsx` | 포트폴리오 현황, 평가손익 |
| Signals | `Signals.tsx` | 시그널 트래커, 수익률 검증 |
| Calendar | `Calendar.tsx` | 이벤트/일정 캘린더 |

**주요 컴포넌트**:
- `WatchlistTable.tsx` — 워치리스트 그리드
- `TraderDashboardPanels.tsx` — 트레이더 대시보드 패널
- `MarketOverview.tsx` — 시장 지수
- `PriceChart.tsx` — 가격 차트 (Recharts)
- `SectorSummary.tsx` — 섹터별 성과
- `SecFilingBadges.tsx` — SEC 공시 배지
- `SignalBadge.tsx` — 시그널 상태 배지
- `NewsItem.tsx` — 뉴스 표시
- `DataSnapshot.tsx` — 핵심 지표

**커스텀 훅**:
- `useDashboardData.ts` — dashboard.json 로드
- `usePriceHistory.ts` — price_history.json 로드
- `useTickerTimeline.ts` — ticker_timelines.json 로드

**배포**: `deploy-dashboard.yml`이 `web/**` 또는 `output/data/**` 변경 시 자동 빌드 → GitHub Pages 배포 (Node 22).

---

## 4. 설정 파일

### 4.1 watchlist.yaml

```yaml
watchlist:
  - ticker: AAPL
    name: Apple Inc.
    sector: Technology
    keywords: ["iPhone", "services revenue", "AI"]
    cik: "0000320193"                          # SEC EDGAR CIK
    ir_rss_feeds:                               # 기업 IR RSS 피드
      - "https://www.apple.com/newsroom/rss-feed.rss"
    sec_filing_tag_priority:                    # SEC 공시 카테고리별 우선순위
      실적: 160
```

### 4.2 models.yaml

3단계 모델 프로파일. `default_profile`로 기본 선택.

```yaml
default_profile: economy
profiles:
  economy:
    model: gpt-5.4-mini
    input_cost_per_1m_tokens: 0.25
    output_cost_per_1m_tokens: 2.0
  standard:
    model: gpt-5.4
    input_cost_per_1m_tokens: 1.25
    output_cost_per_1m_tokens: 10.0
  deep:
    model: o3-mini
    input_cost_per_1m_tokens: 1.10
    output_cost_per_1m_tokens: 4.40
```

### 4.3 output.yaml

출력 표시 설정:
- `sector_display_order` — 섹터 정렬 순서
- `news_source_priority` — 뉴스 소스별 우선순위 점수
- `news_source_max_items_per_source` — 소스당 최대 표시 건수
- `sec_filing_tag_priority` — SEC 공시 카테고리 우선순위
- `ir_source_names` — IR RSS 호스트명 → 소스명 매핑
- `hide_fallback_news_without_links` — 링크 없는 fallback 뉴스 숨김

---

## 5. 기술 결정 및 트레이드오프

### 결정 1: GitHub Actions vs. 로컬 cron

| 기준 | GitHub Actions ✅ | 로컬 cron |
|---|---|---|
| 비용 | 무료 | 무료 |
| 안정성 | 높음 (클라우드) | PC 종료 시 중단 |
| 설정 복잡도 | 중간 | 낮음 |
| 결과물 관리 | Git 자동 커밋 | 별도 동기화 필요 |

→ Obsidian vault를 Git으로 관리하면 결과물 배포까지 한 번에 해결.

### 결정 2: OpenAI GPT 계열 vs. Claude Haiku

| 기준 | GPT mini ✅ | Claude Haiku |
|---|---|---|
| Input 단가 | 저렴 | 상대적으로 높음 |
| Output 단가 | 저렴 | 상대적으로 높음 |
| Web Search 내장 | ❌ (별도 구현) | ✅ (추가 비용) |
| 구조화 출력 | Responses API strict mode | 유사 지원 |

→ 토큰 단가 절약. Web search는 DuckDuckGo로 무료 대체.

### 결정 3: 뉴스 수집을 별도 모듈 vs. AI에 위임

| 기준 | 별도 수집 (RSS+DDG+IR+SEC) ✅ | AI web_search 위임 |
|---|---|---|
| 비용 | 무료 | 건당 과금 |
| 제어력 | 소스/개수 명시적 통제 | AI 판단에 의존 |
| 코드 복잡도 | 약간 높음 | 낮음 |
| 공시 커버리지 | SEC EDGAR 직접 수집 | 누락 가능 |

→ 비용 0원 + 수집 소스 투명성 확보 + SEC 공시 완전 커버가 핵심 제약에 부합.

### 결정 4: 파일 기반 저장 vs. DB

| 기준 | Datastore 추상화 ✅ | 단일 백엔드 |
|---|---|---|
| 유연성 | CSV/SQLite 런타임 전환 | 고정 |
| Git 호환 | CSV 모드에서 완벽 | SQLite는 Git 부적합 |
| 쿼리 성능 | SQLite 모드에서 우수 | CSV는 대규모 시 느림 |
| 마이그레이션 | CSV→SQLite 도구 제공 | — |

→ 현재 규모(20종목)에서는 CSV 기본. 데이터 누적 시 SQLite 전환 가능.

---

## 6. 프로젝트 구조

```
pkrich/
├── .github/
│   └── workflows/
│       ├── stock-research.yml      # 일일 파이프라인 실행 + 테스트
│       └── deploy-dashboard.yml    # 웹 대시보드 빌드/배포
├── config/
│   ├── watchlist.yaml              # 관심 종목 목록 (CIK, IR RSS 포함)
│   ├── models.yaml                 # AI 모델 프로파일 (economy/standard/deep)
│   ├── output.yaml                 # 뉴스 소스 우선순위, 섹터 순서, SEC 태그
│   └── portfolio.yaml              # 포트폴리오 보유 종목/매입 단가
├── src/
│   ├── __init__.py
│   ├── types.py                    # 데이터 클래스 (7개 frozen dataclass)
│   ├── pipeline.py                 # 메인 오케스트레이션
│   ├── collector/
│   │   ├── price.py                # yfinance → Stooq → Alpha Vantage fallback
│   │   ├── news_rss.py             # Google News RSS 수집
│   │   ├── news_search.py          # DuckDuckGo 검색 보강
│   │   ├── ir_rss.py               # 기업 IR RSS 피드 수집
│   │   └── sec_edgar.py            # SEC EDGAR 공시 수집
│   ├── analyzer/
│   │   └── research_note.py        # OpenAI 배치 분석 + deterministic fallback
│   ├── output/
│   │   ├── markdown.py             # daily / weekly / ticker .md 생성
│   │   ├── json_export.py          # dashboard / price_history / timeline JSON
│   │   ├── obsidian.py             # Obsidian vault 미러링
│   │   └── slack.py                # Slack webhook 요약 발송
│   └── utils/
│       ├── config.py               # YAML 설정 로더 (watchlist, portfolio, 매핑)
│       ├── cost_tracker.py         # OpenAI API 비용 실시간 추적
│       ├── datastore.py            # Datastore 추상 인터페이스
│       ├── datastore_csv.py        # CSV 백엔드
│       ├── datastore_sqlite.py     # SQLite 백엔드
│       ├── earnings_setup.py       # 실적 컨센서스 데이터 구축
│       ├── env.py                  # 환경변수 로더
│       ├── migrate_csv_to_sqlite.py # CSV→SQLite 마이그레이션 도구
│       ├── model_config.py         # models.yaml 프로파일 로더
│       ├── network.py              # 네트워크 유틸리티
│       ├── news_tone.py            # 뉴스 감성 분석 (bullish/bearish/neutral)
│       ├── period_changes.py       # 7D / 30D 가격 변화율 계산 (CSV 누적 기반, 보조)
│       ├── pipeline_logging.py     # 구조화 파이프라인 이벤트 로깅
│       ├── portfolio.py            # 포트폴리오 평가손익 계산
│       ├── quarterly_financials.py # 분기 재무 YoY 비교 포맷팅
│       ├── sec_filings.py          # SEC 공시 메타데이터 파싱
│       ├── signal_tracker.py       # 시그널 기록 + 수익률 추적
│       ├── ticker_timelines.py     # 종목별 날짜 타임라인 집계
│       ├── token_estimator.py      # OpenAI 토큰 사전 예산 체크
│       └── weekly_summary.py       # 주간 리서치 노트 생성
├── web/                            # React 대시보드 (Vite 8 + TypeScript 6 + Recharts 3)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx       # 대시보드 메인
│   │   │   ├── TickerDetail.tsx    # 종목 상세
│   │   │   ├── Portfolio.tsx       # 포트폴리오
│   │   │   ├── Signals.tsx         # 시그널 트래커
│   │   │   └── Calendar.tsx        # 이벤트 캘린더
│   │   ├── components/
│   │   │   ├── Layout.tsx
│   │   │   ├── WatchlistTable.tsx
│   │   │   ├── TraderDashboardPanels.tsx
│   │   │   ├── MarketOverview.tsx
│   │   │   ├── PriceChart.tsx
│   │   │   ├── SectorSummary.tsx
│   │   │   ├── SecFilingBadges.tsx
│   │   │   ├── SignalBadge.tsx
│   │   │   ├── NewsItem.tsx
│   │   │   └── DataSnapshot.tsx
│   │   ├── hooks/
│   │   │   ├── useDashboardData.ts
│   │   │   ├── usePriceHistory.ts
│   │   │   └── useTickerTimeline.ts
│   │   ├── types/
│   │   │   └── index.ts            # TypeScript 인터페이스 (12+)
│   │   ├── utils/
│   │   │   ├── format.ts
│   │   │   └── trader.ts
│   │   ├── styles/
│   │   │   └── global.css
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   │   └── output/data/            # JSON 자동 동기화 대상
│   ├── package.json
│   └── vite.config.ts
├── output/                         # 생성된 리서치 노트 (Git 관리)
│   ├── daily/
│   │   └── weekly/
│   ├── tickers/
│   └── data/
├── logs/
│   └── pipeline/
│       ├── YYYY-MM-DD.jsonl        # 이벤트 스트림
│       └── YYYY-MM-DD.summary.json # 컴포넌트 통계 요약
├── scripts/                        # PowerShell 유틸리티 스크립트
├── tests/                          # 유닛 테스트 (31개)
├── main.py
├── requirements.txt
└── README.md
```

---

## 7. 데이터 모델

### 7.1 Python 데이터 클래스 (`types.py`)

| 클래스 | 용도 | 주요 필드 |
|---|---|---|
| `WatchlistItem` | 관심 종목 설정 | ticker, name, sector, keywords, cik, ir_rss_feeds |
| `NewsItem` | 수집된 뉴스 | title, source, link, form_type, catalyst_type, importance_score |
| `CollectedTickerData` | 수집된 시세/재무 | 35+ 필드 (가격, 기술지표, 재무, Price Action) |
| `TickerAnalysis` | AI 분석 결과 | summary, key_news, signal, trade_frame, fundamentals, price_action |
| `PortfolioHolding` | 보유 종목 설정 | ticker, shares, avg_cost, currency |
| `PortfolioPosition` | 포지션 평가 | market_price/value, cost_basis, unrealized_pnl |
| `PortfolioSummary` | 포트폴리오 종합 | positions, total_market_value, total_pnl |

### 7.2 TypeScript 인터페이스 (`web/src/types/index.ts`)

MarketOverviewEntry, NewsReference, SecFilingReference, UpcomingEvent, QuarterlyFinancialRow, PriceAction, EarningsSetup, NewsTone, TradeFrame, TickerAnalysisData, PortfolioData, PortfolioPosition, PortfolioSummary, SignalTrackerData

---

## 8. 환경변수

| 변수 | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 (미설정 시 fallback 분석) |
| `OPENAI_MODEL` | ❌ | 모델 직접 지정 (프로파일 무시) |
| `OPENAI_MODEL_PROFILE` | ❌ | 모델 프로파일 선택 (economy/standard/deep) |
| `BATCH_SIZE` | ❌ | 배치 크기 오버라이드 (기본: 5) |
| `SLACK_WEBHOOK_URL` | ❌ | Slack 알림 활성화 |
| `OBSIDIAN_VAULT_PATH` | ❌ | Obsidian vault 동기화 경로 |
| `ALPHAVANTAGE_API_KEY` | ❌ | Alpha Vantage 재무 fallback 활성화 |
| `DATASTORE_BACKEND` | ❌ | 저장 백엔드 (csv/sqlite, 기본: csv) |
| `ENABLE_EXTERNAL_FETCH` | ❌ | 외부 네트워크 호출 (기본: true) |

---

## 9. 비용 요약

| 항목 | 월 비용 |
|---|---|
| GitHub Actions | $0 (무료 티어) |
| yfinance / Stooq | $0 |
| RSS / DuckDuckGo / IR RSS | $0 |
| SEC EDGAR | $0 |
| Alpha Vantage (선택) | $0 (무료 티어, 일 25회 제한) |
| OpenAI API — economy (20종목, 일 1회) | ~$0.31 |
| OpenAI API — standard | ~$3.00 |
| OpenAI API — deep | ~$8.00 |
| Slack Webhook | $0 |
| GitHub Pages | $0 |
| **총 월 비용 (economy)** | **~$0.31** |

30종목으로 확장 시에도 ~$0.47/월. 목표($5) 대비 10배 이상 여유.

---

## 10. 테스트

31개 테스트 파일로 주요 모듈 커버리지 확보:

| 영역 | 테스트 파일 |
|---|---|
| Analyzer | test_analyzer_batching, test_analyzer_logging, test_analyzer_schema, test_research_note_prompt |
| Collector | test_price_collection, test_price_action, test_news_collection, test_ir_rss, test_sec_edgar, test_sec_item_parsing |
| Output | test_output, test_weekly_markdown, test_slack, test_obsidian |
| Utils | test_config, test_env, test_datastore, test_model_config, test_news_tone, test_period_changes, test_quarterly_financials, test_earnings_setup, test_earnings_beat_miss, test_positioning_data, test_signal_tracker, test_trade_frame, test_weekly_summary |
| Pipeline | test_pipeline, test_batch_strategy, test_fallback_analysis |
| Portfolio | test_portfolio |

GitHub Actions에서 `python -m unittest discover -s tests -v`로 파이프라인 실행 전 자동 검증.

---

## 11. 로깅

`pipeline_logging.py`가 파이프라인 전 단계에서 구조화 이벤트를 기록.

**이벤트 스트림** (`logs/pipeline/YYYY-MM-DD.jsonl`):
```json
{"ts": "2026-04-08T22:05:01Z", "component": "collector", "level": "info", "event": "price_fetched", "ticker": "AAPL", "provider": "yfinance"}
{"ts": "2026-04-08T22:05:03Z", "component": "collector", "level": "warning", "event": "price_fallback", "ticker": "MSFT", "provider": "stooq"}
{"ts": "2026-04-08T22:06:10Z", "component": "analyzer", "level": "info", "event": "batch_completed", "cost_usd": 0.0023}
```

**요약 리포트** (`logs/pipeline/YYYY-MM-DD.summary.json`):
- 컴포넌트별 warning/error count
- 티커별 fallback 여부
- 소스별 실패 횟수
- provider 사용 횟수
- API 비용 누적
- 최근 에러 목록
- 티커별 top scored headline

---

## 12. 구현 로드맵

| Phase | 범위 | 상태 |
|---|---|---|
| **Phase 1** | yfinance 수집 + RSS + OpenAI 노트 생성 + .md 출력 | ✅ 완료 |
| **Phase 2** | GitHub Actions 배포 + Git 자동 커밋 | ✅ 완료 |
| **Phase 3** | Slack 알림 구현 | ✅ 완료 |
| **Phase 4** | DuckDuckGo 뉴스 보강 + 프롬프트 튜닝 | ✅ 완료 |
| **Phase 5** | Stooq / Alpha Vantage fallback, 뉴스 톤/기간 변화 | ✅ 완료 |
| **Phase 6** | React 웹 대시보드 + GitHub Pages 배포 | ✅ 완료 |
| **Phase 7** | 주간 노트, Obsidian 동기화, JSON 3종 출력, 구조화 로깅 | ✅ 완료 |
| **Phase 8** | yfinance 히스토리 기반 7D/30D 직접 계산, CollectedTickerData 확장 | ✅ 완료 |
| **Phase 9** | 배치 전략 확장 (token_estimator + 동적 배치 분할, BATCH_SIZE 환경변수) | ✅ 완료 |
| **Phase 10** | 모델 업그레이드 (models.yaml 프로파일, model_config.py, cost_tracker.py) | ✅ 완료 |
| **Phase 11** | SQLite 마이그레이션 (Datastore 추상화, CSV/SQLite 백엔드, DATASTORE_BACKEND 전환) | ✅ 완료 |
| **Phase 12** | 포트폴리오 트래킹 (portfolio.yaml, portfolio.py, 일일 노트 포트폴리오 현황 섹션) | ✅ 완료 |
| **Phase 13** | SEC EDGAR 공시 수집 (sec_edgar.py, 8-K/10-K/10-Q 자동 분류) | ✅ 완료 |
| **Phase 14** | 기업 IR RSS 직접 수집 (ir_rss.py, watchlist.yaml CIK/IR 설정) | ✅ 완료 |
| **Phase 15** | 시그널 트래커 (signal_tracker.py, 수익률 1D/5D/20D 역추적) | ✅ 완료 |
| **Phase 16** | 실적 컨센서스 셋업 (earnings_setup.py, Forward/TTM EPS, Beat/Miss) | ✅ 완료 |
| **Phase 17** | Price Action 지표 (ATR, RVOL, Gap%, RS vs SPY, SMA 포지셔닝) | ✅ 완료 |
| **Phase 18** | 매매 프레임 (trade_frame: 시나리오, 진입/손절/목표) | ✅ 완료 |
| **Phase 19** | 웹 대시보드 확장 (Portfolio, Signals, Calendar 페이지, SEC 배지) | ✅ 완료 |

---

## 13. 리스크 및 완화 방안

| 리스크 | 영향 | 완화 |
|---|---|---|
| yfinance API 차단 | 시세 수집 불가 | Stooq fallback 구현됨; 요청 딜레이 적용 |
| Stooq 수집 실패 | 가격 누락 | Alpha Vantage fallback 구현됨 (KEY 설정 시) |
| Alpha Vantage 일 25회 한도 | 재무 fallback 불가 | 가격은 Stooq로 독립 수집; Alpha Vantage는 재무/이벤트만 보완 |
| OpenAI 가격 인상 | 비용 증가 | models.yaml 프로파일로 모델 교체 용이; economy 기본 |
| GitHub Actions 무료 한도 초과 | 실행 중단 | 월 100분 내외 사용, 한도(2,000분) 대비 여유 |
| DuckDuckGo rate limit | 뉴스 보강 실패 | Graceful degradation — 검색 실패 시 RSS+IR+SEC 뉴스만으로 노트 생성 |
| RSS 피드 구조 변경 | 파싱 오류 | try/except + 파이프라인 경고 로그, feedparser 라이브러리로 표준 처리 |
| SEC EDGAR API 변경 | 공시 수집 실패 | Graceful degradation — SEC 실패 시 다른 뉴스 소스로 보완 |
| 시그널 트래커 데이터 무결성 | 잘못된 수익률 계산 | evaluated 플래그로 중복 계산 방지; 가격 이력 기반 검증 |

---

## 14. 향후 확장 고려 사항

| 항목 | 필요 조건 | 비고 |
|---|---|---|
| **한국 주식 추가** | pykrx + 한경/매경 RSS | 환율 처리 레이어 필요 |
| **가격 알림** | 목표가 도달 시 Slack/이메일 알림 | watchlist.yaml에 `alert_price` 필드 추가 |
| **포트폴리오 웹 대시보드 고도화** | 수익률 차트, 섹터 비중, 리밸런싱 제안 | 현재 기본 현황 표시 구현 완료 |
| **월간 리포트** | 월별 종목 성과/포트폴리오 수익률 요약 .md | weekly_summary.py 패턴 재사용 가능 |
| **시그널 정확도 대시보드** | 시그널 방향별 적중률 통계 | signal_tracker.csv 기반 집계 |

---

## 15. 의존성

### Python (`requirements.txt`)

| 패키지 | 버전 | 용도 |
|---|---|---|
| yfinance | ≥ 0.2.54 | 시세/재무 수집 |
| feedparser | ≥ 6.0.11 | RSS 피드 파싱 |
| ddgs | ≥ 9.6.1 | DuckDuckGo 뉴스 검색 |
| openai | ≥ 1.75.0 | AI 분석 API |
| PyYAML | ≥ 6.0.2 | YAML 설정 파싱 |

### Web (`web/package.json`)

| 패키지 | 버전 | 용도 |
|---|---|---|
| react | ^19.2.4 | UI 프레임워크 |
| react-dom | ^19.2.4 | DOM 렌더링 |
| react-router-dom | ^7.14.0 | 클라이언트 라우팅 |
| recharts | ^3.8.1 | 차트 시각화 |
| typescript | ~6.0.2 | 타입 시스템 |
| vite | ^8.0.4 | 빌드 도구 |

# 주식 리서치 자동화 시스템 — 설계 문서

> **상태**: v5
> **작성일**: 2026-04-17
> **작성자**: 박준희  

---

## 1. 개요

### 1.1 해결하는 문제

미국 주식 투자 시 관심 종목(10~30개)의 시세, 재무, 뉴스를 매일 수동으로 확인하는 데 시간이 많이 소요된다. 정보가 여러 소스에 흩어져 있어 일관된 판단 근거를 만들기 어렵다.

### 1.2 목표

- 관심 종목의 시세/재무/뉴스를 **자동으로 수집**하고, AI가 **구조화된 리서치 노트**를 생성
- 일일/주간 Markdown 노트 및 React 웹 대시보드로 데이터 시각화
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
│  │  │  Provider Architecture (Phase 1-0e) │   │    │
│  │  │  orchestrator.py + registry.py      │   │    │
│  │  │  ┌─ P1: YFinanceProvider            │   │    │
│  │  │  │      (시세/재무/기술/포지셔닝)    │   │    │
│  │  │  ├─ P2: FMPProvider / FinnhubProvider│   │    │
│  │  │  │      PolygonProvider             │   │    │
│  │  │  ├─ P2: StooqProvider (가격 fallback)│   │    │
│  │  │  └─ P3: AlphaVantageProvider        │   │    │
│  │  │         (재무/이벤트 fallback)       │   │    │
│  │  │  시장 개요: ^GSPC, ^NDX             │   │    │
│  │  │  (레거시: price.py — fallback=false) │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  │  ┌──────────────────────────────────────┐   │    │
│  │  │  news_rss.py  — Google News RSS      │   │    │
│  │  │  news_search.py — DuckDuckGo 보강    │   │    │
│  │  │  ir_rss.py    — 회사 공식 IR RSS     │   │    │
│  │  │  sec_edgar.py — SEC EDGAR 공시       │   │    │
│  │  │                (8-K/10-Q/10-K +       │   │    │
│  │  │                 importance score)     │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │             분석 (Analyzer)                  │    │
│  │  research_note.py                            │    │
│  │  OpenAI Responses API (strict JSON)          │    │
│  │  모델 프로파일 (economy/standard/deep)        │    │
│  │  동적 배치 분할 (token_estimator 기반)        │    │
│  │  cost_tracker.py로 API 비용 누적 기록         │    │
│  │  → 실패 시 다요소 점수 기반 fallback          │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │         포트폴리오 & 시그널 (State)            │    │
│  │  portfolio.py  — 보유 × 현재가 → 손익 계산   │    │
│  │  signal_tracker.py — 저수준 CSV helper       │    │
│  │  Datastore.record_signals / update_returns / │    │
│  │     load_signal_stats_data (v5 추상화)        │    │
│  │     → CSV + SQLite dual-write                │    │
│  │  ensemble routing — portfolio_priority,      │    │
│  │     routing_log 방출 (v5)                    │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │           파생 (analyzer/derive) — v5         │    │
│  │  backtest_summary / monthly_summary /        │    │
│  │  earnings_setup / sec_filings /              │    │
│  │  ticker_timelines / weekly_summary /         │    │
│  │  per-ticker derivations                       │    │
│  │  → orchestration이 미리 계산, output은 write │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              출력 (Output)                   │    │
│  │  markdown.py  → daily + weekly + tickers .md│    │
│  │                 (+ 포트폴리오 / 실적 셋업)    │    │
│  │  json_export.py → legacy dashboard/price/   │    │
│  │                   timeline + signal_stats    │    │
│  │  sharded_export.py → data/index.json +      │    │
│  │                      tickers/<T>/latest.json │    │
│  │                      + history.json (v5)     │    │
│  │  cost_log.py  → data/cost_log.json (v5)     │    │
│  │  routing_log → data/routing_log.json (v5)   │    │
│  │  obsidian.py  → Obsidian vault 미러 (선택적) │    │
│  │  slack.py     → Slack webhook 요약 (선택적)  │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │          저장 (Datastore 추상화)              │    │
│  │  datastore.py       — 추상 인터페이스         │    │
│  │  datastore_csv.py   — CSV 백엔드 (기본)      │    │
│  │  datastore_sqlite.py — SQLite 백엔드          │    │
│  │  DATASTORE_BACKEND 환경변수로 전환            │    │
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
│           (Dashboard / TickerDetail / Portfolio /    │
│            Signals / Backtest / Calendar /           │
│            Chat / Scenario)                         │
└─────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
1. GitHub Actions cron 트리거 (UTC 22:00 = KST 07:00, 미 장 마감 후)
2. watchlist.yaml + portfolio.yaml 로드 (관심 종목 + 보유 포지션)
3. yfinance로 각 종목의 시세/재무/포지셔닝 데이터 수집 (6개월 히스토리 포함)
   → 6개월 히스토리에서 7D / 30D 가격 변화율 직접 계산
   → ATR(14), RVOL, Gap%, SMA50/200 위치, 52W 위치, RS vs SPY 계산
   → 포지셔닝: 공매도 %, 애널리스트 목표가/추천, 기관/내부자 보유, 옵션 IV
   → 가격 수집 실패 시 Stooq fallback
   → 재무/이벤트 수집 실패 시 Alpha Vantage fallback (KEY 설정 시)
4. ^GSPC (S&P 500), ^NDX (NASDAQ 100)으로 시장 개요 수집
5. Google News RSS + DuckDuckGo Search로 종목별 뉴스 수집/보강
6. IR RSS (회사 공식 뉴스룸) + SEC EDGAR 공시 수집
   → 8-K Item 번호 파싱 (2.02 실적, 5.02 임원 교체 등)
   → hard/medium/soft catalyst 분류 + importance_score 부여
7. 수집 데이터를 OpenAI Responses API에 전달 (strict JSON schema)
   → MODEL_PROFILE (economy/standard/deep)과 token_estimator 기반
     동적 배치 크기 결정 (BATCH_SIZE 환경변수 오버라이드 가능)
   → cost_tracker.py가 호출별 토큰/비용 누적 기록
   → API 실패 시 다요소 점수 기반 deterministic fallback 분석
8. 포트폴리오 현황 계산 (현재 시세 × 보유 수 → 평가금액/손익)
9. 시그널 사후 업데이트: signal_tracker.csv 에서 1D/5D/20D 경과된
   과거 시그널에 실제 수익률 기록
10. 오늘 시그널 기록: 각 종목의 signal_or_takeaway → CSV에 append
11. signal_stats 로드: bull/bear/neutral별 승률·평균 수익률 계산
12. Markdown 출력: 일일 노트(포트폴리오 섹션 포함), 주간 노트,
    종목별 상세 노트 생성
13. JSON 출력: dashboard.json (portfolio_summary, signal_stats 포함),
    price_history.json, ticker_timelines.json 생성
    → web/public/output/data/에 자동 동기화
14. Obsidian 동기화 (OBSIDIAN_VAULT_PATH 설정 시)
    → Slack 요약 발송 (SLACK_WEBHOOK_URL 설정 시)
    → 파이프라인 이벤트 로그 기록 (JSONL + 요약 JSON)
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
      - run: python main.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          ALPHAVANTAGE_API_KEY: ${{ secrets.ALPHAVANTAGE_API_KEY }}
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "daily: 리서치 노트 자동 생성"
          file_pattern: "output/**"
```

**예상 실행 시간**: 종목 20개 기준 약 3~5분 → 월 ~100분 (무료 범위 내)

### 3.2 데이터 수집 모듈

#### 3.2.0 Provider 아키텍처 (Phase 1-0e, 기본 경로)

`pipeline.py`는 `ENABLE_ORCHESTRATOR_PRIMARY`(기본 `true`)에 따라 `CollectionOrchestrator`를 통해 수집합니다. 각 `DataProvider`는 우선순위(priority)와 레이트 리미트를 선언하고, 오케스트레이터가 순서대로 실행 후 필드 단위로 병합합니다.

| Priority | Provider | 담당 영역 |
|---|---|---|
| 1 | `YFinanceProvider` | 시세 / 재무 / 기술지표 / 포지셔닝 / 이벤트 |
| 2 | `FMPProvider` | 재무비율 / 기업 개요 / 애널리스트 추정치 |
| 2 | `FinnhubProvider` | 애널리스트 추천 트렌드 / 동종업체 |
| 2 | `PolygonProvider` | 옵션 플로우 (Max Pain / GEX / IV Skew) |
| 2 | `StooqProvider` | 가격 fallback (yfinance 실패 시) |
| 3 | `AlphaVantageProvider` | 재무 / 이벤트 gap-fill (KEY 설정 시) |

레거시 `collect_market_data()` 경로는 `ENABLE_ORCHESTRATOR_PRIMARY=false` 환경변수로 복원 가능.

#### 3.2.1 시세/재무 — 수집 항목 상세

**YFinanceProvider (P1)**

```
수집 항목:
├─ 일일 시세: 종가, 변동률 (6개월 히스토리 기반)
├─ 기간 변화율: 7일 / 30일 변화율 (6개월 히스토리에서 직접 계산)
├─ 기본 지표: PER (trailing), 시가총액, EPS (TTM)
├─ 추가 지표: Volume, 3개월 평균 거래량, P/B, Dividend Yield
├─ 실적 지표: Forward EPS, Earnings Growth (YoY)
├─ 기술 지표 (가격 행동):
│  ├─ 52주 고/저, 50일/200일 이동평균선
│  ├─ ATR(14), ATR % (가격 대비 변동성)
│  ├─ Relative Volume (현재 거래량 / 3개월 평균)
│  ├─ Gap % (오픈가 vs 전일 종가)
│  ├─ Price vs SMA50 / SMA200 (퍼센트)
│  ├─ 52W Position (0~100, 52주 레인지 내 위치)
│  └─ RS vs SPY (30일 상대강도)
├─ 포지셔닝 지표:
│  ├─ 공매도: short_float_pct, short_ratio
│  ├─ 애널리스트: target_price, recommendation(Strong Buy~Sell), count
│  ├─ 보유: held_by_insiders, held_by_institutions
│  └─ 옵션: implied_volatility (연환산)
├─ 분기 재무: 최근 4분기 매출/영업이익/EPS
│  └─ earnings_history 기반 estimated_eps, surprise_pct, beat/miss 분류
├─ 이벤트: 실적 발표일(최대 90일 앞), 배당 일정(최대 14일)
└─ 시장 개요: ^GSPC (S&P 500), ^NDX (NASDAQ 100) 직접 지수
```

**StooqProvider (P2, 가격 fallback)**  
yfinance에서 종가/변동률 수집 실패 시 Stooq CSV API로 대체 수집.

**AlphaVantageProvider (P3, 재무/이벤트 fallback)**  
`ALPHAVANTAGE_API_KEY` 설정 시 yfinance 재무/이벤트 누락 보완. 무료 티어 분당 5회, 일 500회 제한.

**제약**: yfinance는 비공식 API이므로 과도한 호출 시 차단 가능. 종목당 1회 호출, `RateLimit(calls_per_minute=60, burst=20)` 적용.

#### 3.2.2 뉴스 수집 — RSS + DuckDuckGo (무료)

**RSS 소스 목록**:

| 소스 | URL 패턴 | 용도 |
|---|---|---|
| Google News | `news.google.com/rss/search?q={ticker}` | 종목별 최신 뉴스 집계 |

**Yahoo Finance / Reuters 도메인 제한 검색**: Yahoo Finance와 Reuters 도메인을 site: 쿼리로 제한하여 신뢰도 높은 소스 우선 수집.

**DuckDuckGo 보강**: `duckduckgo-search` 패키지로 종목명 + 키워드 검색. 무료, rate limit 주의.

```
검색 쿼리 예시:
  "{ticker} {company_name} earnings news 2026"
  "{ticker} analyst rating upgrade downgrade"
```

#### 3.2.3 공시 / IR 수집 — SEC EDGAR + 회사 공식 RSS

**`src/collector/sec_edgar.py`** — SEC EDGAR API 기반 공시 수집:

- `watchlist.yaml`의 각 종목 `cik` 값을 이용해 EDGAR submissions API 호출
- 수집 대상 폼: 8-K, 10-Q, 10-K, DEF 14A, 20-F, 6-K 등
- **8-K Item 번호 파싱**: title/description에서 "Item X.XX" 정규식 추출 후 카테고리화

  | Item | 의미 | Catalyst 등급 | Importance |
  |---|---|---|---|
  | 2.02 | 실적 발표 (Results of Operations) | **hard** | 200 |
  | 5.02 | 임원 교체 (Director/Officer Changes) | **hard** | 180 |
  | 1.01 | 주요 계약 (Material Definitive Agreement) | **hard** | 160 |
  | 1.05 | 중요 사이버보안 사고 | **hard** | 150 |
  | 2.01 | 자산 취득/처분 | **medium** | 130 |
  | 8.01 | 기타 중요 공시 | **medium** | 120 |
  | 7.01 | Reg FD 공시 | **medium** | 100 |

- 출력: `sec_filing_tags`, `catalyst_type`, `importance_score`, `published_at`, `form_type`

**`src/collector/ir_rss.py`** — 회사 공식 IR/뉴스룸 RSS:

- `watchlist.yaml`의 `ir_feeds` 배열에 정의된 RSS URL 수집
- 예: Apple Newsroom, Microsoft Source, NVIDIA Newsroom, Tesla IR
- 공식 출처이므로 news_rss보다 높은 신뢰도 가중치 부여

**뉴스 신선도 스코어 차별화** (`news_rss._news_rank_key`):

| Catalyst 등급 | 신선도 감쇠 |
|---|---|
| hard (SEC 2.02/5.02, 공식 IR) | 30일 선형 감소 |
| medium (Bloomberg/Reuters 속보) | 14일 선형 감소 |
| soft (일반 해설, thesis recap) | 7일 선형 감소 |

"why", "how", "explained", "recap", "analysis of" 키워드 포함 뉴스는 -30점.

### 3.3 AI 분석 — OpenAI Responses API

**모델**: 환경변수 `OPENAI_MODEL`로 설정 (기본값: `gpt-5.4-mini`). 뉴스 요약 및 구조화 작업에 충분한 성능.

**프롬프트 전략**:

```
입력 (종목당 ~2,000 토큰):
├─ 시세/재무/포지셔닝 데이터 (JSON)
├─ [Price] 블록 — 가격/통화/변동률/6개월 히스토리 요약
├─ [Key Levels] 블록 — SMA50/200, 52W High/Low, ATR, RVOL, RS vs SPY
├─ 뉴스 헤드라인 5~10개 + SEC 공시 importance 순 정렬
└─ 시스템 프롬프트 ("professional equity research analyst" 역할,
                    정량적 증거 강제, 구체적 가격 레벨 요구, 한국어 출력)

출력 (종목당 ~1,200 토큰, strict JSON schema):
├─ summary: 2 문장 핵심 요약 (상황 + catalyst 타임라인)
├─ key_news: 뉴스별 한국어 요약 (입력 순서 유지, 최대 5)
├─ financial_highlights: 재무 하이라이트 (숫자 필수, 최대 5)
├─ risks_or_watchpoints: 리스크/주의 항목 (측정 가능 트리거 강제, 최대 4)
├─ signal_or_takeaway: 방향 + 진입존 + 무효화 가격 포함 한 문장
├─ fundamentals: 시가총액/PE/Forward EPS/EPS Growth/배당 등 딕셔너리
├─ price_action: ATR/RVOL/Gap/SMA 위치/52W 위치/RS 딕셔너리
├─ trade_frame:
│  ├─ bull_scenario — 상승 시나리오 + 구체적 저항선
│  ├─ base_scenario — 기본 시나리오
│  ├─ bear_scenario — 하락 리스크 시나리오
│  ├─ invalidation_price — SMA50 또는 2×ATR 기반 명시 가격
│  └─ watch_period — 관찰 기간 (다음 실적/다음 주요 이벤트)
├─ quarterly_financials, upcoming_events, news_references
└─ data_snapshot (렌더링용)

※ news_tone은 news_tone.py (keyword 분석)에서 독립적으로 계산되어
  markdown.py에서 병합됨. AI 출력 스키마에는 포함되지 않음.
```

**모델 프로파일 시스템 (Phase 10)**

환경변수 `MODEL_PROFILE`로 아래 프로파일 선택 (기본 `standard`):

- `config/models.yaml`: profile → model_name / max_tokens / temperature 매핑
- `src/utils/model_config.py`: 프로파일 로더 및 유효성 검사
- `src/utils/token_estimator.py`: 입력 토큰 예측 → 배치 크기 동적 결정
  (하나의 배치가 토큰 한도 초과 시 자동으로 절반 분할, 최대 6회 재귀)
- `src/utils/cost_tracker.py`: 호출별 input/output 토큰 × 단가 누적 기록

**배치 전략**: 기본 5종목/배치 (`BATCH_SIZE` 환경변수). token_estimator가 예상 토큰이 한도를 넘으면 배치를 동적으로 분할. 검증 실패(빈 문자열·schema 위반)도 같은 split 메커니즘으로 재시도 후에만 fallback으로 넘어감.

**Fallback**: OpenAI API 실패(키 미설정 포함) 또는 검증 실패 시 deterministic 한국어 노트 생성. **단순 등락률이 아닌 다요소 점수**(price momentum + SMA 위치 + RS vs SPY + RVOL)로 bull/bear 스코어를 계산해 시그널 문구를 차등화. `_build_fallback_trade_frame`이 SMA50 및 ATR 기반으로 무효화 가격을 자동 생성하며, `_build_fallback_risks`는 SMA200 이탈·높은 공매도·고 IV 조건 감지 시 리스크 항목을 추가.

**비용 추정 (종목 20개, 일 1회)**:

| 항목 | 토큰 | 일 비용 | 월 비용 |
|---|---|---|---|
| Input (20종목) | ~30,000 | $0.0045 | $0.10 |
| Output (20종목) | ~16,000 | $0.0096 | $0.21 |
| **합계** | | | **~$0.31** |

→ 월 $1 미만. 목표($30) 대비 충분한 여유.

### 3.4 출력 형식

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
    ├── dashboard.json          # 웹 대시보드용 전체 데이터
    ├── price_history.json      # 웹 차트용 가격 이력
    └── ticker_timelines.json   # 종목별 타임라인
```

**일일 종합 노트 구조**:

```markdown
# 일일 리서치 - 2026-04-08

## 시장 개요
S&P 500: 5,234.18 (+0.45%) | NASDAQ 100: 16,892.33 (+0.62%)

## 관심 종목 요약
| 티커 | 가격 | 등락률 | 한줄 판단 |

## 주요 움직임

## 주요 뉴스 링크

## 점검 항목

## 다가오는 일정
```

**종목 노트 구조**:

```markdown
# AAPL - Apple Inc. (2026-04-08)

## 요약
## 주요 뉴스
## 재무 하이라이트
## 리스크 / 체크포인트
## 데이터 스냅샷
## 최근 변화 비교 (7D / 30D / 뉴스 톤)
## 최근 4분기 재무
## 다가오는 일정
## 최근 타임라인 (최근 3일)
## 시그널 / 한줄 결론
```

**주간 노트**: 해당 주 거래일 데이터를 집계하여 상위 등락 종목, 반복 뉴스, 주간 Action Items 제공.

#### JSON 출력

**공용 (파이프라인마다 생성)**

| 파일 | 내용 | 용도 |
|---|---|---|
| `dashboard.json` | 최근 1일 전체 payload (legacy, v5 기준 `EMIT_LEGACY_DASHBOARD` 플래그로 유지) | 대시보드 fallback |
| `dashboard_history.json` | 최근 90일 전체 payload (legacy) | 히스토리 fallback |
| `price_history.json` | 날짜별 종가/등락률 배열 | 웹 가격 차트 |
| `ticker_timelines.json` | 종목별 날짜 타임라인 (최대 90일) | 웹 타임라인 뷰 |
| `backtest_summary.json` | bull/bear 시그널 20D 성과 | Backtest 페이지 |
| `monthly_summary.json` | 월간 통계 | 월간 뷰 |
| `signal_tracker.csv` | 시그널 기록 (CSV, SQLite와 dual-write) | 백테스트/디버깅 |

**샤딩 (v5, `EMIT_SHARDED_DASHBOARD=true` 기본)**

| 파일 | 내용 | 용도 |
|---|---|---|
| `index.json` | 경량 요약 (market context + 티커별 10개 핵심 필드) | Dashboard eager load 대상 |
| `tickers/<T>/latest.json` | 티커별 풀 payload (최신 1일) | TickerDetail 진입 시 lazy fetch |
| `tickers/<T>/history.json` | 티커별 히스토리 (최대 90일) | TickerDetail 히스토리 뷰 |

**감사/관측 (v5)**

| 파일 | 내용 | 용도 |
|---|---|---|
| `routing_log.json` | 각 티커의 ensemble routing 결정 (conviction / in_portfolio / selected_for_deep / reason) | deep pass 의사결정 감사 |
| `cost_log.json` | per-run LLM 비용 분해 (profile × input/output tokens × 단가) | 비용 추적 (진행 중) |

파이프라인 실행 시 `web/public/output/data/`로 자동 동기화 (샤드 디렉토리 포함).

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
- 점검 항목
- 다가오는 일정 최대 3건
- 생성된 일일/주간 노트 경로

미설정 또는 전송 실패 시 warning 로그만 남기고 파이프라인 계속 진행.

### 3.5 웹 대시보드

React (Vite + TypeScript + Recharts) 기반 정적 사이트. GitHub Pages로 자동 배포.

**데이터 레이어 (v5 Repository 패턴)**

`web/src/data/DashboardRepository.ts` 인터페이스로 데이터 로드를 추상화. 구현체는 `StaticJsonRepository` (정적 JSON fetch). 페이지별 접근 패턴:

| 페이지 | 로드 방식 | 파일 |
|---|---|---|
| Dashboard / Backtest / Signals 등 | eager `loadDashboard()` | `dashboard.json` + `dashboard_history.json` (legacy) |
| TickerDetail | 우선 lazy `loadTickerLatest()`, 미스 시 fallback | `tickers/<T>/latest.json` + `history.json` |

샤드 히트 시 TickerDetail은 `dashboard.json` 전체를 받지 않고 단일 티커 payload만 fetch. `useDashboardData({ enabled: false })` 옵션으로 조건부 skip 가능.

**주요 기능**:
- 날짜 선택
- 티커/종목명 검색
- 섹터 필터
- `7D`, `30D` 변화 표시
- 뉴스 톤 배지 (bullish/bearish/neutral)
- 다가오는 일정 배지
- Ticker Detail 페이지: 가격 차트, 분기 재무 테이블, 타임라인 30일/90일 토글

**페이지 구성**:

| 페이지 | 경로 | 설명 |
|---|---|---|
| Dashboard | `/` | 메인 대시보드 (워치리스트, 섹터 퍼포먼스, 시장 개요, 매크로) |
| Ticker Detail | `/ticker/:ticker` | 종목 상세 (차트, EPS 서프라이즈, 분기 재무, 트레이드 프레임, 타임라인) |
| Portfolio | `/portfolio` | 포트폴리오 현황, 손익, 리스크 분석, 에쿼티 커브 |
| Signals | `/signals` | 시그널 이력 및 성과 통계 |
| Backtest | `/backtest` | 20거래일 bull 시그널 백테스트 결과 |
| Calendar | `/calendar` | 실적 발표/이벤트 캘린더 |
| Chat | `/chat` | 한국어 Q&A 인터페이스 |
| Scenario | `/scenario` | What-if 시나리오 분석 |

**배포**: `deploy-dashboard.yml`이 `web/**` 또는 `output/data/**` 변경 시 자동 빌드 → GitHub Pages 배포.

---

## 4. 기술 결정 및 트레이드오프

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

| 기준 | 별도 수집 (RSS+DDG) ✅ | AI web_search 위임 |
|---|---|---|
| 비용 | 무료 | 건당 과금 |
| 제어력 | 소스/개수 명시적 통제 | AI 판단에 의존 |
| 코드 복잡도 | 약간 높음 | 낮음 |

→ 비용 0원 + 수집 소스 투명성 확보가 핵심 제약에 부합.

### 결정 4: 파일 기반 저장 vs. DB

| 기준 | 파일 (CSV + .md) ✅ | SQLite |
|---|---|---|
| 복잡도 | 낮음 | 중간 |
| Obsidian 호환 | 완벽 | 별도 변환 필요 |
| 이력 조회 | Git log + CSV | SQL 쿼리 |
| 전환 비용 | — | 나중에 마이그레이션 가능 |

→ 현재 규모(20종목)에서 DB는 과잉. 필요 시 CSV→SQLite 마이그레이션은 쉬움.

---

## 5. 프로젝트 구조

```
pkrich/
├── .github/
│   └── workflows/
│       ├── stock-research.yml      # 일일 파이프라인 실행
│       └── deploy-dashboard.yml    # 웹 대시보드 빌드/배포
├── config/
│   ├── watchlist.yaml              # 관심 종목 목록
│   ├── output.yaml                 # 뉴스 소스 우선순위, 섹터 표시 순서 등
│   ├── models.yaml                 # LLM 모델 프로파일 (economy/standard/deep)
│   └── portfolio.yaml              # 포트폴리오 보유 종목
├── src/
│   ├── __init__.py
│   ├── types.py                    # 데이터 클래스 (frozen dataclass)
│   ├── pipeline.py                 # 메인 오케스트레이션
│   ├── collector/
│   │   ├── base.py                 # DataProvider ABC, ProviderResult, RateLimit 타입
│   │   ├── orchestrator.py         # CollectionOrchestrator — 우선순위별 provider 실행
│   │   ├── orchestrated_collection.py  # pipeline.py용 drop-in 어댑터
│   │   ├── registry.py             # ProviderRegistry — 등록/조회
│   │   ├── rate_limiter.py         # 토큰 버킷 레이트 리미터
│   │   ├── bootstrap.py            # 기본 provider 인스턴스 초기화
│   │   ├── cache.py                # 수집 결과 캐시 (메모리)
│   │   ├── shadow_compare.py       # 레거시 vs 오케스트레이터 결과 비교 (shadow mode)
│   │   ├── providers/              # 구체적 DataProvider 구현체
│   │   │   ├── yfinance_provider.py    # P1: 시세/재무/기술지표/포지셔닝
│   │   │   ├── fmp_provider.py         # P2: Financial Modeling Prep 재무
│   │   │   ├── finnhub_provider.py     # P2: Finnhub 애널리스트/동종업체
│   │   │   ├── polygon_provider.py     # P2: Polygon.io 옵션 플로우
│   │   │   ├── stooq_provider.py       # P2: Stooq 가격 fallback
│   │   │   ├── alphavantage_provider.py # P3: Alpha Vantage 재무/이벤트 fallback
│   │   │   └── news/                   # 뉴스 전용 providers
│   │   │       ├── google_news_news_provider.py
│   │   │       ├── duckduckgo_news_provider.py
│   │   │       ├── ir_rss_news_provider.py
│   │   │       └── sec_edgar_news_provider.py
│   │   ├── helpers/                # 순수 함수 헬퍼 (부작용 없음)
│   │   │   ├── formatters.py       # 모든 포매터 (format_ratio, format_large_number 등)
│   │   │   ├── earnings.py         # EPS/성장률 추출 헬퍼
│   │   │   └── yfinance_helpers.py # yfinance 전용 추출 함수 (select_price_snapshot 등)
│   │   ├── price.py                # 레거시 수집 경로 (ENABLE_ORCHESTRATOR_PRIMARY=false 시)
│   │   ├── news_rss.py             # Google News RSS 수집
│   │   ├── news_search.py          # DuckDuckGo / Yahoo / Reuters 검색 보강
│   │   ├── news_base.py            # 뉴스 provider 공통 베이스
│   │   ├── news_orchestrator.py    # 뉴스 수집 오케스트레이터
│   │   ├── news_shadow_compare.py  # 뉴스 shadow 비교
│   │   ├── ir_rss.py               # 회사 공식 IR/보도자료 RSS
│   │   ├── sec_edgar.py            # SEC EDGAR 공시 수집
│   │   ├── sec_form4.py            # SEC Form 4 내부자 거래 파싱 (무료 fallback)
│   │   ├── fmp.py                  # FMP 저수준 API 클라이언트
│   │   ├── finnhub.py              # Finnhub 저수준 API 클라이언트
│   │   ├── polygon_options.py      # Polygon.io 옵션 플로우 (Max Pain/GEX/IV Skew)
│   │   ├── options.py              # yfinance 옵션 요약
│   │   ├── technicals.py           # RSI/MACD/Bollinger + ATR/RVOL/Gap/SMA 계산
│   │   └── macro.py                # 매크로 캘린더 + 수익률/DXY/구리
│   ├── analyzer/
│   │   ├── research_note.py        # OpenAI 배치 분석 + deterministic fallback
│   │   ├── weekly_insight.py       # 주간 3문장 시장 요약 생성
│   │   ├── ensemble.py             # economy → deep → tie-break 합의 + routing (v5: portfolio_priority, routing_log)
│   │   ├── orchestrator.py         # AnalysisOrchestrator — 모듈 DAG 실행
│   │   ├── registry.py             # ModuleRegistry
│   │   ├── ab_test.py              # 주간 prompt A/B
│   │   ├── modules/                # AnalysisModule 구현체들
│   │   ├── prompts/                # 프롬프트 템플릿 레지스트리
│   │   └── derive/                 # (v5) 파생 계산 레이어
│   │       ├── __init__.py         # backtest_summary / monthly_summary /
│   │       │                        #   earnings_* / sec_filings /
│   │       │                        #   ticker_timelines / weekly_summary re-export
│   │       └── ticker.py           # per-ticker derivations (earnings/sec)
│   ├── output/
│   │   ├── markdown.py             # daily / weekly / ticker .md 생성
│   │   ├── json_export.py          # legacy dashboard / price_history / timeline JSON (write-only, v5)
│   │   ├── sharded_export.py       # (v5) index.json + tickers/<T>/latest|history.json
│   │   ├── cost_log.py             # (v5) per-run LLM 비용 분해
│   │   ├── schema.py               # (v5) 공용 SCHEMA_VERSION 상수
│   │   ├── obsidian.py             # Obsidian vault 미러링
│   │   ├── slack.py                # Slack webhook 요약 발송
│   │   ├── ab_test.py              # A/B 결과 출력
│   │   ├── analysis_quality.py     # 분석 품질 메트릭 출력
│   │   ├── api_status.py           # API 상태 매트릭스 출력
│   │   └── alert.py                # 알림 규칙 평가 (가격/변동률 조건)
│   ├── utils/
│   │   ├── config.py               # YAML 설정 로더
│   │   ├── env.py                  # 환경변수 로더
│   │   ├── network.py              # 네트워크 유틸리티
│   │   ├── news_tone.py            # 뉴스 감성 분석 (bullish/bearish/neutral)
│   │   ├── period_changes.py       # 7D / 30D 가격 변화율 계산 (CSV 누적 기반, 보조)
│   │   ├── pipeline_logging.py     # 구조화 파이프라인 이벤트 로깅
│   │   ├── ticker_timelines.py     # 종목별 날짜 타임라인 집계
│   │   ├── weekly_summary.py       # 주간 리서치 노트 생성
│   │   ├── monthly_summary.py      # 월간 요약 통계
│   │   ├── portfolio.py            # 포트폴리오 P&L 계산
│   │   ├── portfolio_risk.py       # 포트폴리오 리스크 분석 (섹터 집중도, 상관관계, 포지션 사이징)
│   │   ├── signal_tracker.py       # 시그널 기록 및 수익률 사후 검증
│   │   ├── cost_tracker.py         # OpenAI API 비용 추적
│   │   ├── model_config.py         # 모델 프로파일 로더
│   │   ├── token_estimator.py      # 배치 토큰 예측
│   │   ├── datastore.py            # 추상 Datastore 인터페이스 (v5: signal API 포함)
│   │   ├── datastore_csv.py        # CSV 백엔드
│   │   ├── datastore_sqlite.py     # SQLite 백엔드 (v5: signal dual-write 오버라이드)
│   │   ├── migrate_csv_to_sqlite.py   # price_history CSV → SQLite 마이그레이션
│   │   ├── migrate_signal_tracker.py  # (v5) signal_tracker CSV → SQLite 백필
│   │   ├── earnings_history.py     # 실적 Beat/Miss 분석
│   │   ├── earnings_setup.py       # Forward EPS / 실적 D-Day 표시
│   │   ├── quarterly_financials.py # 분기 재무 YoY 비교
│   │   └── sec_filings.py          # SEC 공시 태그 추출/필터링
│   ├── api/
│   │   └── main.py                 # FastAPI REST API 서버
│   ├── backtester/
│   │   └── engine.py               # 20거래일 bull 시그널 백테스트
│   ├── chat/
│   │   └── engine.py               # 대시보드 데이터 기반 한국어 Q&A
│   └── cli/
│       └── notify_failure.py       # 파이프라인 실패 시 Slack 알림 CLI
├── web/                            # React 대시보드 (Vite + TypeScript + Recharts)
│   ├── src/
│   │   ├── components/
│   │   ├── data/                   # (v5) Repository 레이어
│   │   │   ├── DashboardRepository.ts  # 인터페이스
│   │   │   └── StaticJsonRepository.ts # 정적 JSON 구현체
│   │   ├── hooks/
│   │   │   ├── useDashboardData.ts     # repo 경유, enabled 플래그 지원
│   │   │   └── useTickerAnalysis.ts    # (v5) 티커 샤드 lazy fetch
│   │   ├── pages/
│   │   ├── types/
│   │   └── utils/
│   ├── public/
│   │   └── output/data/            # JSON 자동 동기화 대상 (샤드 디렉토리 포함)
│   └── package.json
├── output/                         # 생성된 리서치 노트 (Git 관리)
│   ├── daily/
│   │   └── weekly/
│   ├── tickers/
│   └── data/
│       ├── dashboard.json          # legacy (EMIT_LEGACY_DASHBOARD 플래그, v5)
│       ├── dashboard_history.json  # legacy
│       ├── index.json              # (v5) 샤딩: 경량 요약
│       ├── tickers/<T>/latest.json # (v5) 샤딩: 티커별 풀 payload
│       ├── tickers/<T>/history.json# (v5) 샤딩: 티커별 히스토리
│       ├── routing_log.json        # (v5) ensemble routing 감사
│       ├── cost_log.json           # (v5) LLM 비용 분해
│       ├── price_history.{csv,json,sqlite}
│       ├── signal_tracker.csv      # + SQLite signal_history (dual-write, v5)
│       └── ...
├── logs/
│   └── pipeline/
│       ├── YYYY-MM-DD.jsonl        # 이벤트 스트림
│       └── YYYY-MM-DD.summary.json # 컴포넌트 통계 요약
├── tests/
├── main.py
├── requirements.txt
└── README.md
```

### watchlist.yaml 예시

```yaml
watchlist:
  - ticker: AAPL
    name: Apple Inc.
    sector: Technology
    keywords: ["iPhone", "services revenue", "AI"]
    exclude_keywords: ["lawsuit recap"]
  - ticker: NVDA
    name: NVIDIA Corp.
    sector: Semiconductors
    keywords: ["GPU", "data center", "AI chips"]
```

---

## 6. 비용 요약

| 항목 | 월 비용 |
|---|---|
| GitHub Actions | $0 (무료 티어) |
| yfinance / Stooq | $0 |
| RSS / DuckDuckGo | $0 |
| Alpha Vantage (선택) | $0 (무료 티어, 일 25회 제한) |
| FMP (선택) | $0 (무료 티어) |
| Finnhub (선택) | $0 (무료 티어) |
| Polygon (선택) | ~$9 (옵션 데이터, Basic 플랜) |
| OpenAI API (20종목, 일 1회) | ~$0.31 |
| Slack Webhook | $0 |
| GitHub Pages | $0 |
| **총 월 비용** | **~$0.31** |

30종목으로 확장 시에도 ~$0.47/월. 목표($5) 대비 10배 이상 여유.

---

## 7. 로깅

`pipeline_logging.py`가 파이프라인 전 단계에서 구조화 이벤트를 기록.

**이벤트 스트림** (`logs/pipeline/YYYY-MM-DD.jsonl`):
```json
{"ts": "2026-04-08T22:05:01Z", "component": "collector", "level": "info", "event": "price_fetched", "ticker": "AAPL", "provider": "yfinance"}
{"ts": "2026-04-08T22:05:03Z", "component": "collector", "level": "warning", "event": "price_fallback", "ticker": "MSFT", "provider": "stooq"}
```

**요약 리포트** (`logs/pipeline/YYYY-MM-DD.summary.json`):
- 컴포넌트별 warning/error count
- 티커별 fallback 여부
- 소스별 실패 횟수
- provider 사용 횟수
- 최근 에러 목록
- 티커별 top scored headline

---

## 8. 구현 로드맵

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
| **Phase 13** | FMP/Finnhub/Polygon 연동 (재무비율, 내부자 거래, 기관 보유, 옵션 플로우, 애널리스트 트렌드) | ✅ 완료 |
| **Phase 14** | SEC Form 4 내부자 거래 파싱, 기술 지표 (RSI/MACD/Bollinger), 매크로 컨텍스트 | ✅ 완료 |
| **Phase 15** | 포트폴리오 리스크 분석 (섹터 집중도, 상관관계, ATR 포지션 사이징), 알림 규칙 | ✅ 완료 |
| **Phase 16** | 시그널 트래커 (1D/5D/20D 수익률 검증), 백테스트 엔진, 월간 요약 | ✅ 완료 |
| **Phase 17** | FastAPI REST API, Chat Q&A 엔진, 웹 대시보드 확장 (8 페이지) | ✅ 완료 |
| **Phase 1-0e** | Provider 아키텍처 도입 (DataProvider ABC, CollectionOrchestrator, ProviderRegistry, RateLimit) — yfinance/FMP/Finnhub/Polygon/Stooq/AlphaVantage를 우선순위 provider로 등록, shadow mode 검증 후 orchestrator 기본 경로 전환, 순수 포매터·기술지표·yfinance 헬퍼·EPS 헬퍼를 독립 모듈로 분리, price.py 1946줄 → 1491줄 축소 | ✅ 완료 |
| **Phase 18 (v5)** | 레이어 경계 정비 + 샤딩 + 라우팅 감사 — (1) `Datastore`에 signal API 통합 + CSV/SQLite dual-write, `migrate_signal_tracker` 추가; (2) `src/analyzer/derive/` 네임스페이스 신설, output/에서 파생 로직 제거, `tests/test_output_boundary.py`로 import 경계 enforce; (3) `sharded_export.py` — `index.json` + `tickers/<T>/{latest,history}.json` 방출 (`EMIT_SHARDED_DASHBOARD` 플래그); (4) 프론트 `DashboardRepository` 인터페이스 + `StaticJsonRepository`, `useTickerAnalysis` 훅 — TickerDetail 진입 시 샤드 lazy fetch, `dashboard.json` 요청 skip; (5) `LlmRateLimiter` (RPM+TPM 복합 토큰 버킷); (6) ensemble routing 정교화 — `portfolio_priority`, `routing_log.json` 방출; (7) pre-existing 3 test errors 해소, unused imports 정리 (521/521 PASS) | ✅ 완료 |

---

## 9. 리스크 및 완화 방안

| 리스크 | 영향 | 완화 |
|---|---|---|
| yfinance API 차단 | 시세 수집 불가 | Stooq fallback 구현됨; 요청 딜레이 적용 |
| Stooq 수집 실패 | 가격 누락 | Alpha Vantage fallback 구현됨 (KEY 설정 시) |
| Alpha Vantage 일 25회 한도 | 재무 fallback 불가 | 가격은 Stooq로 독립 수집; Alpha Vantage는 재무/이벤트만 보완 |
| OpenAI 가격 인상 | 비용 증가 | 모델 교체 용이하도록 `OPENAI_MODEL` 환경변수 추상화 |
| GitHub Actions 무료 한도 초과 | 실행 중단 | 월 100분 내외 사용, 한도(2,000분) 대비 여유 |
| DuckDuckGo rate limit | 뉴스 보강 실패 | Graceful degradation — 검색 실패 시 RSS 뉴스만으로 노트 생성 |
| RSS 피드 구조 변경 | 파싱 오류 | try/except + 파이프라인 경고 로그, feedparser 라이브러리로 표준 처리 |

---

## 10. 향후 확장 고려 사항

Phase 9~17에서 배치 전략 확장, 모델 업그레이드, SQLite, 포트폴리오 트래킹, 리스크 분석, 시그널 추적, API, Chat, 웹 대시보드 확장을 완료. Phase 18 (v5) 에서 레이어 경계·샤딩·라우팅 감사까지 정비.

**단기 후보 (v5 기반에서 자연스러운 연장)**

| 항목 | 필요 조건 | 근거 |
|---|---|---|
| **cost_log 완성** | per-profile × input/output 토큰 분해 + routing_log와 join → "deep pass ROI" 뷰 | `cost_tracker` + Phase 18 routing_log |
| **JSON schema snapshot 테스트** | 각 output/data/*.json 픽스처 diff + `SCHEMA_VERSION` 게이트 | 대형 리팩터 이후 schema drift 방지 |
| **Dashboard index.json 완전 전환** | Dashboard.tsx를 `index.json` + 디테일 lazy fetch로 마이그, 30일 green 후 `EMIT_LEGACY_DASHBOARD=false` | PR4/5/5.5 기반 |
| **Signal outcome 대시보드** | `signal_tracker`(SQLite) × `routing_log` 결합 → deep pass 히트율/수익률 차이 | v5로 두 소스 구조화 완료 |

**중장기**

| 항목 | 필요 조건 | 비고 |
|---|---|---|
| **한국 주식 추가** | pykrx + 한경/매경 RSS | 환율 처리 레이어 필요 |
| **Intraday 부분 refresh** | `pipeline.collect_only()` 분리, 프론트 polling | Phase 18 레이어 분리가 전제 |
| **Multi-run diff 뷰** | ticker history 샤드 활용 — `signal_or_takeaway` / `trade_frame` / `decision` 변화 강조 UI | 데이터는 이미 샤드에 존재 |
| **Config 중앙화** | 흩어진 env flags (ENABLE_*, EMIT_*) → Settings 객체 (pydantic) | 현재 마찰 크지 않음 |

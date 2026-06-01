# 주식 리서치 자동화 시스템 — 설계 문서

> **상태**: v5
> **작성일**: 2026-04-15  
> **최종 업데이트**: 2026-05-19
> **작성자**: 박준희  

---

## 1. 개요

### 1.1 해결하는 문제

미국 주식 투자 시 관심 종목(10~30개)의 시세, 재무, 뉴스를 매일 수동으로 확인하는 데 시간이 많이 소요된다. 정보가 여러 소스에 흩어져 있어 일관된 판단 근거를 만들기 어렵다.

### 1.2 목표

- 관심 종목의 시세/재무/뉴스를 **자동으로 수집**하고, AI가 **구조화된 리서치 노트**를 생성
- 일일/주간 Markdown 노트 및 React 웹 대시보드로 데이터 시각화
- Obsidian vault에 `.md` 파일로 저장하여 누적 기록 관리 (선택적)

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
│  │  signal_tracker.py — 시그널 기록 +            │    │
│  │                      1D/5D/20D 수익률 업데이트 │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │              출력 (Output)                   │    │
│  │  markdown.py  → daily + weekly + tickers .md│    │
│  │                 (+ 포트폴리오 / 실적 셋업)    │    │
│  │  json_export.py → dashboard/price/timeline  │    │
│  │                  (+ portfolio_summary +      │    │
│  │                   signal_stats)              │    │
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
│            Chat / Scenario / Risk Intel)             │
└─────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
1. GitHub Actions cron 트리거 (UTC 22:00 = KST 07:00, 미 장 마감 후)
2. main.py가 CLI 플래그에 따라 run_pipeline(), collect_only(), sector scan을 분기
3. watchlist.yaml + portfolio.yaml + models.yaml + search_evidence.yaml 로드
4. Collector가 시장/시세/재무/뉴스/공시/매크로/정책/피어 후보를 정규화
   → 가격 수집 실패 시 Stooq 등 fallback
   → 누락 가격은 datastore 가격 이력으로 보강
   → 실제 시장일(effective market date)을 가격 이력에서 감지
5. 포트폴리오 현황, 매크로 민감도, 시장 레짐, 매크로 내러티브 생성
6. Analyzer가 ModuleRegistry 순서대로 결정론 모듈 → LLM 모듈을 실행
   → raw payload와 fallback payload를 모두 유지
   → strict JSON schema, validator, hallucination guard 적용
   → LLM evidence manifest를 hash-only JSONL로 기록
7. AnalysisEnsemble이 economy 전체 분석 후 Smart Model Router로 deep review 후보를 선별
   → max_daily_ensemble cap 안에서만 deep/tie-break 경로 실행
   → BudgetGuard가 shadow/enforce 설정에 따라 optional LLM 경로를 평가
8. Committee가 growth/value/risk/macro/PM 역할별 리뷰를 생성
   → committee output은 presentation/review 데이터이며 공식 결정의 source of truth가 아님
9. State refresh가 과거 시그널 1D/5D/20D 수익률과 triple-barrier label을 갱신
10. Decision layer가 rule-based factor scoring으로 buy/watch/avoid를 생성
    → data_quality_score, search_evidence_score, gate metadata는 confidence_meta에 기록
    → 기본 gate 모드는 shadow이며, enforce는 명시적 환경변수로만 사용
11. Collector search evidence 경로가 cache-first payload를 만들고, 필요 시 provider mode로 우선 후보를 refresh
    → 기본은 cache mode라 정상 daily run에서 live search 비용이 발생하지 않음
12. Datastore가 현재 run의 signal row와 decision metadata를 기록
13. Output layer가 Markdown, sharded JSON, web-public mirror, audit/quality/cost/routing/performance artifact를 생성
14. Risk Intelligence Graph가 policy impact, search evidence, portfolio/watchlist, sector exposure를 읽어 정적 네트워크 artifact를 생성
    → Phase 1 daily batch는 외부 Tier 2 web search provider를 호출하지 않고 기존 cache/schema만 사용
15. Search audit, risk intelligence, analysis performance, routing outcome, performance baseline/trends는 read-only telemetry/설명 artifact로 기록
16. Slack/alert, pipeline JSONL/summary, API status, GitHub Pages 배포가 후속 처리
```

### 2.3 현재 아키텍처 불변식

현재 파이프라인의 핵심 불변식은 다음 순서를 보존하는 것이다.

```
collect -> analyze -> state -> output -> store -> log
```

레이어 경계:

- Collector: 외부 API, provider fallback, rate limit, cache-first search evidence를 소유한다.
- Analyzer: LLM prompt, structured output, module DAG, ensemble, committee, evidence manifest, search audit를 소유한다.
- Decision: 공식 `buy` / `watch` / `avoid`, conviction, factor reasoning, confidence metadata를 소유한다.
- State: signal tracker, realized return, triple-barrier label, signal statistics를 재현 가능하게 관리한다.
- Output: Markdown/JSON/web mirror/health report를 쓰고 risk intelligence 설명 artifact를 만들되 decision을 재계산하지 않는다.
- Datastore: 가격 이력, signal row, analysis run metadata의 단일 persistence boundary다.
- Logging: 관측성 artifact를 만들되 business behavior를 바꾸지 않는다.
- Web: `output/data`의 정적 소비자이며 공식 결정, 성능 telemetry, routing telemetry를 재계산하지 않는다.

### 2.4 현재 주요 산출물

`output/data`가 웹과 자동화 소비자의 source of truth다. 대표 산출물:

- `index.json`, `dashboard_history.json`, `tickers/<TICKER>/latest.json`, `tickers/<TICKER>/history.json`
- `price_history.json`, `ticker_timelines.json`, `api_status.json`, `api_ticker_matrix.json`
- `analysis_quality.json`, `validation_warnings.json`, `cost_log.json`
- `routing_log.json`, `routing_log_history.json`, `routing_outcome.json`
- `search_evidence.json`, `search_audit.json`
- `risk_intel_graph.json`, `risk_intel_summary.json`, `risk_intel_refresh_log.json`
- `analysis_performance.json`, `performance_baseline.json`, `performance_trends.json`
- `signal_quality.json`, `backtest_summary.json`, `monthly_summary.json`, `factor_audit.json`
- `llm_evidence/<DATE>.jsonl`, `llm_audit/<DATE>.json`

이 중 search evidence, search audit, risk intelligence, routing outcome, analysis performance, performance baseline/trends, backtest summary는 관측/검토/설명용 산출물이다. 공식 decision을 덮어쓰거나 factor weight를 재학습하는 입력으로 사용하지 않는다.

Risk intelligence artifact의 `generation.scoring_config_version`은 score weights/threshold/cap/half-life/hop-decay 변경을 추적하고, `generation.confidence_config_version`은 edge confidence band table 변경을 추적한다. 두 버전이 바뀌면 calibration fixture와 output health check가 함께 갱신되어야 한다.

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

→ 월 $1 미만. 목표($5) 대비 충분한 여유.

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

#### 주요 JSON 출력

| 파일 | 내용 | 용도 |
|---|---|---|
| `dashboard.json` | 전체 날짜별 분석 데이터 (티커, 시그널, 뉴스톤, 이벤트 등) | 웹 대시보드 메인 |
| `price_history.json` | 날짜별 종가/등락률 배열 | 웹 가격 차트 |
| `ticker_timelines.json` | 종목별 날짜 타임라인 (최대 90일) | 웹 타임라인 뷰 |
| `risk_intel_graph.json` | 정책/안보/사회 이슈와 섹터/종목 전파 경로, 점수 breakdown, health metadata | `/risk-intel` 네트워크 맵 |
| `risk_intel_summary.json` | 한국어 카드 요약, 보유/관심 종목 구분, top-N alert/warning 카드 | 대시보드 compact risk card |
| `risk_intel_refresh_log.json` | manual refresh 후보 patch와 provider counter 계약 | 후속 manual refresh 운영 로그 |

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
- 점검 항목
- 다가오는 일정 최대 3건
- 생성된 일일/주간 노트 경로

미설정 또는 전송 실패 시 warning 로그만 남기고 파이프라인 계속 진행.

### 3.5 웹 대시보드

React (Vite + TypeScript + Recharts) 기반 정적 사이트. GitHub Pages로 자동 배포.

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
| Risk Intel | `/risk-intel` | 정책/안보/사회 이슈가 섹터와 보유/관심 종목으로 전파되는 네트워크 맵 |

**배포**: `deploy-dashboard.yml`이 `web/**` 또는 `output/data/**` 변경 시 자동 빌드 → GitHub Pages 배포.

### 3.6 현재 운영 레이어 보정

현재 코드는 초기 v4 설계보다 모듈화가 더 진행되어 있으며, 다음 파일군을 우선 기준으로 본다.

| 레이어 | 현재 주요 파일 | 책임 |
|---|---|---|
| Pipeline | `src/pipeline.py`, `main.py` | daily full run, collect-only, optional sector scan 분기 |
| Collector | `src/collector/orchestrator.py`, `src/collector/providers/*`, `src/collector/search_evidence.py` | 외부 데이터 수집, fallback, search evidence cache/provider 경로 |
| Analyzer | `src/analyzer/orchestrator.py`, `src/analyzer/ensemble.py`, `src/analyzer/smart_router.py`, `src/analyzer/modules/*` | module DAG, economy/deep/tie-break ensemble, Smart Model Router |
| Committee | `src/analyzer/committee.py`, `src/analyzer/committee_prompt.py` | 역할별 debate, PM summary, presentation-only review |
| Decision | `src/decision/decision_layer.py`, `src/decision/factors/*`, `src/decision/search_quality.py` | rule-based official action, conviction, quality gate metadata |
| State | `src/utils/signal_tracker.py`, `src/utils/signal_metadata_backfill.py` | signal row, realized return, triple-barrier label, legacy metadata backfill |
| Datastore | `src/utils/datastore.py`, `src/utils/datastore_csv.py`, `src/utils/datastore_sqlite.py` | CSV/SQLite persistence abstraction |
| Output | `src/output/*`, `src/output/json_writer.py`, `src/output/web_sync_contract.py` | Markdown/JSON/report/web mirror, risk intelligence artifact, safe JSON write/parse-back |
| Performance | `src/utils/performance_metrics.py`, `src/utils/performance_analytics.py`, `src/output/performance.py`, `src/output/analysis_performance.py` | read-only run quality, signal performance, routing/evidence/cost telemetry |
| Web | `web/src/*`, `web/vite.config.ts` | static artifact consumption; local dev bridge only in Vite serve mode |

Local Vite 개발 서버는 `/api/local-research/*`와 `/api/local-portfolio/*` bridge를 제공해 watchlist 추가, portfolio 저장, `python main.py` 실행을 도울 수 있다. 이 bridge는 production static build에 포함되는 business logic이 아니며, decision/analyzer/provider 책임을 대신하지 않는다.

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
│   │   └── weekly_insight.py       # 주간 3문장 시장 요약 생성
│   ├── output/
│   │   ├── markdown.py             # daily / weekly / ticker .md 생성
│   │   ├── json_export.py          # dashboard / price_history / timeline / backtest / monthly JSON
│   │   ├── obsidian.py             # Obsidian vault 미러링
│   │   ├── slack.py                # Slack webhook 요약 발송
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
│   │   ├── datastore.py            # 추상 Datastore 인터페이스
│   │   ├── datastore_csv.py        # CSV 백엔드
│   │   ├── datastore_sqlite.py     # SQLite 백엔드
│   │   ├── migrate_csv_to_sqlite.py  # CSV → SQLite 마이그레이션
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
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── types/
│   │   └── utils/
│   ├── public/
│   │   └── output/data/            # JSON 자동 동기화 대상
│   └── package.json
├── output/                         # 생성된 리서치 노트 (Git 관리)
│   ├── daily/
│   │   └── weekly/
│   ├── tickers/
│   └── data/
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

현재 비용 통제는 `config/models.yaml`의 profile, module override, ensemble cap, BudgetGuard가 함께 담당한다. BudgetGuard의 기본 모드는 shadow이며 `ensemble_deep`, `ensemble_tie_break`, `committee_deep`, `macro_narrative`, `policy_impact`, `search_evidence` 같은 optional 고비용 경로를 사전 평가한다.

`config/search_evidence.yaml`의 기본값은 `mode: cache`다. OpenAI Web Search provider mode는 명시적으로 켜고 API key/rate limit/cap을 확인한 경우에만 사용한다. Smart Model Router가 search evidence priority ticker를 넘기더라도 `max_search_tickers_per_run` cap을 늘리거나 추가 호출을 만들면 안 된다.

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

운영 리포트는 `output/data`에도 파생된다.

- `analysis_quality.json`: validation, hallucination, warning trend
- `cost_log.json`: profile별 cost/token/call, BudgetGuard decision, routing count
- `routing_outcome.json`: deep review selection, priority skip, router score, estimated cost
- `performance_baseline.json`, `performance_trends.json`: JSON health, cost, quality, evidence, signal telemetry
- `analysis_performance.json`: signal performance, conviction calibration, regime performance, factor attribution, action-change reasons

이 리포트들은 관측성 산출물이며 decision layer의 공식 결정을 변경하지 않는다.

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
| **Phase 18** | Analyzer module DAG, economy/deep/tie-break ensemble, BudgetGuard shadow telemetry, LLM evidence manifest | ✅ 완료 |
| **Phase 19** | Multi-role committee review, PM view, decision confidence metadata, data/search quality gate shadow mode | ✅ 완료 |
| **Phase 20** | Cache-first search evidence, optional OpenAI Web Search provider boundary, search audit, web evidence badges | ✅ 완료 |
| **Phase 21** | Smart Model Router, routing log/history/outcome, performance baseline/trends, analysis performance artifact | ✅ 완료 |
| **Phase 22** | Portfolio command center, local portfolio edit bridge, safe web-public output sync contract | ✅ 완료 |
| **Phase 23** | Risk Intelligence Graph Phase 1: 정책/안보/사회 이슈 네트워크 artifact, score/cap/health 검증, 한국어 dashboard card와 `/risk-intel` 맵 | ✅ 완료 |

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

Phase 18~23까지 ensemble, committee, search evidence, performance telemetry, portfolio command center, risk intelligence graph가 들어왔기 때문에 향후 확장은 "정확도와 운영 신뢰도 개선" 중심으로 제한한다. 실시간 매매, 주문 실행, 복잡한 상시 서버 인프라는 계속 비목표다.

### 10.1 P1 실행 트랙

P1은 새 기능 확장보다 운영 신뢰도를 높이는 트랙이다. 기본 정책은 report/shadow mode에서 충분한 증거를 쌓은 뒤, 필요할 때만 enforce 또는 provider mode를 명시적으로 켜는 것이다.

| 트랙 | 목표 | 검증 산출물 | 완료 기준 |
|---|---|---|---|
| Search evidence provider 검증 | cache-only 계약을 유지한 채 제한된 live provider 검증으로 근거 coverage와 freshness를 높일 수 있는지 확인 | `search_evidence.json`, `search_audit.json`, `performance_baseline.json`의 evidence summary, provider call/error log | 기본 `mode: cache` 유지, 제한 실행에서 provider error와 stale-cache reuse가 구분되고, `max_search_tickers_per_run` cap이 보존됨 |
| BudgetGuard report/enforce 검토 | optional LLM 경로의 would-block이 품질과 비용에 미치는 영향을 측정하고 enforce 전환 조건을 정의 | `cost_log.json`의 BudgetGuard counts, guarded path outcomes, routing counts, deep-pass value summary | 월 $5 목표 안에서 shadow decision 표본이 충분하고, enforce 전환 시 skipped path와 품질 손실 기준이 문서화됨 |
| Analysis performance 품질 루프 | signal 결과, conviction calibration, regime/factor별 성과를 관측해 decision 품질 개선 후보를 찾음 | `analysis_performance.json`, `signal_quality.json`, `routing_outcome.json`, `backtest_summary.json` | 지표가 공식 decision을 자동 변경하지 않고, 개선 후보는 별도 shadow/report 실험으로만 연결됨 |
| Output schema 안정화 | 생성 JSON과 web mirror 계약을 깨지 않도록 schema 최소 조건과 fixture를 강화 | `python -m src.cli.output_health_check`, output schema snapshot, web-public mirror byte match | 신규/변경 payload는 additive 우선이고, breaking change는 migration 및 fixture 업데이트가 함께 있음 |

P1 공통 검증:

- `python -m compileall main.py src tests`
- 관련 단위 테스트: search evidence, BudgetGuard/model config, analysis performance, output health/schema
- 생성 artifact 검증: `python -m src.cli.output_health_check`

| 우선순위 | 항목 | 필요 조건 | 경계/주의 |
|---|---|---|---|
| P1 | Search evidence provider 검증 | OpenAI Web Search request shape 검증, `SEARCH_EVIDENCE_MODE=openai` 제한 실행, cache hit/stale-cache 지표 확인 | 기본값은 계속 `cache`; `max_search_tickers_per_run` cap을 늘리지 않음 |
| P1 | BudgetGuard report/enforce 전환 검토 | shadow decision 누적, would-block 대비 품질 영향 분석, 일별/월별 비용 리포트 확인 | enforce 전환은 명시적 운영 결정 필요; 공식 decision 품질 저하 여부를 먼저 측정 |
| P1 | Analysis performance 품질 루프 | `analysis_performance.json`, `signal_quality.json`, `routing_outcome.json`의 표본 수 확대 | 성능 지표는 관측용이며 factor weight나 공식 decision을 자동 변경하지 않음 |
| P1 | Output schema 안정화 | `output_health_check`, snapshot fixture, web mirror byte-for-byte 검증 확대 | schema 변경은 additive 우선; breaking change는 migration 문서 필요 |
| P1 | Risk intelligence calibration | `risk_intel_graph.json` calibration fixture, score/cap/band 회귀, stale rule health warning 표본 확대 | Phase 1 daily batch는 Tier 2 provider를 호출하지 않음; alert는 설명 artifact이며 공식 decision을 변경하지 않음 |
| P2 | 한국 주식 추가 | pykrx, 한국 거래소 캘린더, 한경/매경/전자공시 RSS, KRW/USD 환율 레이어 | Collector 전용 provider로 격리; 미국 주식 payload와 혼합 시 통화/휴장일 표준화 필요 |
| P2 | Portfolio tax/cash layer | 현금, 입출금, 배당, 실현손익, 환전 단가 입력 모델 | 투자/세무 조언이 아니라 기록/계산 레이어로 제한 |
| P2 | Sector explorer 고도화 | sector ETF provider, 섹터별 breadth, 정책 tailwind, peer rank 개선 | sector payload는 output artifact이며 official ticker decision을 대체하지 않음 |
| P2 | LLM audit gate 운영화 | `src.eval.runner` 정기 실행, R3 evidence consistency, numeric grounding, contradiction trend 확인 | audit 실패는 먼저 관측/리포트; pipeline hard fail은 별도 정책 필요 |
| P2 | Local workflow 안전장치 | local portfolio editor delete/overwrite UX, watchlist 중복 방지, dev bridge status 개선 | Vite local bridge는 개발 편의 기능이며 production logic이 아님 |
| P3 | Factor calibration 실험 | purged walk-forward, factor attribution 표본 확대, regime별 calibration 리포트 | 자동 재학습 금지; shadow/report mode로만 비교 |
| P3 | Datastore retention/compaction | SQLite history growth 측정, 오래된 generated artifact 보존 정책, index 최적화 | datastore API를 우회하지 않음 |
| P3 | Multi-currency/risk dashboard | KRW/USD, sector/country exposure, beta/macro sensitivity 통합 표시 | 웹은 finalized JSON 소비자; risk 계산은 state/utils/output 경계 안에서 수행 |

확장 판단 기준:

- 비용이 월 $5 목표를 넘지 않거나 초과 사유가 문서화되어야 한다.
- 외부 API 호출은 collector 경계 안에 있어야 한다.
- 공식 `buy` / `watch` / `avoid`는 decision layer만 생성한다.
- 성능, 라우팅, 검색 근거, audit 산출물은 기본적으로 read-only telemetry다.
- 웹과 GitHub Actions는 business logic의 source of truth가 아니다.

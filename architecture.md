# 주식 리서치 자동화 시스템 — 설계 문서

> **상태**: v2  
> **작성일**: 2026-04-09  
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
│  │  │  price.py                            │   │    │
│  │  │  1순위: yfinance                      │   │    │
│  │  │  2순위: Stooq (가격 fallback)         │   │    │
│  │  │  3순위: Alpha Vantage (재무 fallback) │   │    │
│  │  │  시장 개요: ^GSPC, ^NDX              │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  │  ┌──────────────────────────────────────┐   │    │
│  │  │  news_rss.py  — Google News RSS      │   │    │
│  │  │  news_search.py — DuckDuckGo 보강    │   │    │
│  │  └──────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌─────────────────────────────────────────────┐    │
│  │             분석 (Analyzer)                  │    │
│  │  research_note.py                            │    │
│  │  OpenAI Responses API, 5종목/배치            │    │
│  │  → 실패 시 fallback (등락률 기반 한국어 노트) │    │
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
3. yfinance로 각 종목의 시세/재무 데이터 수집 (6개월 히스토리 포함)
   → 6개월 히스토리에서 7D / 30D 가격 변화율 직접 계산
   → 가격 수집 실패 시 Stooq fallback
   → 재무/이벤트 수집 실패 시 Alpha Vantage fallback (KEY 설정 시)
4. ^GSPC (S&P 500), ^NDX (NASDAQ 100)으로 시장 개요 수집
5. Google News RSS에서 관련 뉴스 헤드라인 수집
6. DuckDuckGo Search로 종목별 최신 뉴스 보강
7. 수집된 데이터를 5종목씩 배치로 OpenAI Responses API에 전달
   → API 실패 시 등락률 기반 deterministic fallback 분석
8. Markdown 출력: 일일 노트, 주간 노트, 종목별 상세 노트 생성
9. JSON 출력: dashboard.json, price_history.json, ticker_timelines.json 생성
   → web/public/output/data/에 자동 동기화
10. Obsidian 동기화 (OBSIDIAN_VAULT_PATH 설정 시)
11. Slack 요약 발송 (SLACK_WEBHOOK_URL 설정 시)
12. 파이프라인 이벤트 로그 기록 (JSONL + 요약 JSON)
13. Git auto-commit → GitHub Pages 대시보드 자동 배포
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
└─ 시장 개요: ^GSPC (S&P 500), ^NDX (NASDAQ 100) 직접 지수
```

**2순위: Stooq (가격 fallback)**  
yfinance에서 종가/변동률 수집 실패 시 Stooq CSV API로 대체 수집.

**3순위: Alpha Vantage (재무/이벤트 fallback)**  
`ALPHAVANTAGE_API_KEY` 설정 시 yfinance 재무/이벤트 누락 보완. 무료 티어 일 25회 제한.

**제약**: yfinance는 비공식 API이므로 과도한 호출 시 차단 가능. 종목당 1회 호출, 요청 간 1초 딜레이 적용.

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

### 3.3 AI 분석 — OpenAI Responses API

**모델**: 환경변수 `OPENAI_MODEL`로 설정 (기본값: `gpt-5.4-mini`). 뉴스 요약 및 구조화 작업에 충분한 성능.

**프롬프트 전략**:

```
입력 (종목당 ~1,500 토큰):
├─ 시세/재무 데이터 (JSON)
├─ 뉴스 헤드라인 5~10개
└─ 시스템 프롬프트 (리서치 노트 포맷 지정, 한국어 출력 지시)

출력 (종목당 ~800 토큰, strict JSON schema):
├─ summary: 핵심 요약
├─ key_news: 뉴스별 한국어 요약 (입력 순서 유지)
├─ financial_highlights: 재무 하이라이트 목록
├─ risks_or_watchpoints: 리스크/주의 항목
└─ signal_or_takeaway: 한줄 시그널

※ news_tone은 news_tone.py (keyword 분석), 7D/30D 변화율은 price.py (yfinance 히스토리)
  에서 독립적으로 계산되어 markdown.py에서 병합됨 — AI 출력 스키마에 포함되지 않음
```

**배치 전략**: 종목을 5개씩 그룹으로 묶어 배치별 API 호출 (`_BATCH_SIZE = 5`). 호출 횟수 감소 및 시스템 프롬프트 토큰 절약.

**Fallback**: OpenAI API 실패(키 미설정 포함) 시 등락률/뉴스 기반 deterministic 한국어 노트 생성. 등락률 크기에 따라 시그널 문구 차등화.

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

#### JSON 출력 3종

| 파일 | 내용 | 용도 |
|---|---|---|
| `dashboard.json` | 전체 날짜별 분석 데이터 (티커, 시그널, 뉴스톤, 이벤트 등) | 웹 대시보드 메인 |
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
│   └── output.yaml                 # 뉴스 소스 우선순위, 섹터 표시 순서 등
├── src/
│   ├── __init__.py
│   ├── types.py                    # 데이터 클래스 (frozen dataclass)
│   ├── pipeline.py                 # 메인 오케스트레이션
│   ├── collector/
│   │   ├── price.py                # yfinance → Stooq → Alpha Vantage fallback
│   │   ├── news_rss.py             # Google News RSS 수집
│   │   └── news_search.py          # DuckDuckGo / Yahoo / Reuters 검색 보강
│   ├── analyzer/
│   │   └── research_note.py        # OpenAI 배치 분석 + deterministic fallback
│   ├── output/
│   │   ├── markdown.py             # daily / weekly / ticker .md 생성
│   │   ├── json_export.py          # dashboard / price_history / timeline JSON
│   │   ├── obsidian.py             # Obsidian vault 미러링
│   │   └── slack.py                # Slack webhook 요약 발송
│   └── utils/
│       ├── config.py               # YAML 설정 로더
│       ├── env.py                  # 환경변수 로더
│       ├── network.py              # 네트워크 유틸리티
│       ├── news_tone.py            # 뉴스 감성 분석 (bullish/bearish/neutral)
│       ├── period_changes.py       # 7D / 30D 가격 변화율 계산 (CSV 누적 기반, 보조)
│       ├── pipeline_logging.py     # 구조화 파이프라인 이벤트 로깅
│       ├── ticker_timelines.py     # 종목별 날짜 타임라인 집계
│       └── weekly_summary.py       # 주간 리서치 노트 생성
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

현재 미구현 항목. 나머지(배치 전략 확장, 모델 업그레이드, SQLite, 포트폴리오 트래킹)는 Phase 9~12에서 완료.

| 항목 | 필요 조건 | 비고 |
|---|---|---|
| **한국 주식 추가** | pykrx + 한경/매경 RSS | 환율 처리 레이어 필요 |
| **가격 알림** | 목표가 도달 시 Slack/이메일 알림 | watchlist.yaml에 `alert_price` 필드 추가 |
| **포트폴리오 웹 대시보드** | 웹 대시보드에 포트폴리오 현황 섹션 추가 | 현재 daily .md에만 표시, JSON export 미포함 |
| **월간 리포트** | 월별 종목 성과/포트폴리오 수익률 요약 .md | weekly_summary.py 패턴 재사용 가능 |

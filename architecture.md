# 주식 리서치 자동화 시스템 — 설계 문서

> **상태**: Draft v1  
> **작성일**: 2026-04-08  
> **작성자**: 박준희  

---

## 1. 개요

### 1.1 해결하는 문제

미국 주식 투자 시 관심 종목(10~30개)의 시세, 재무, 뉴스를 매일 수동으로 확인하는 데 시간이 많이 소요된다. 정보가 여러 소스에 흩어져 있어 일관된 판단 근거를 만들기 어렵다.

### 1.2 목표

- 관심 종목의 시세/재무/뉴스를 **자동으로 수집**하고, AI가 **구조화된 리서치 노트**를 생성
- 매일 Obsidian vault에 `.md` 파일로 저장하여 누적 기록 관리
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
│              (cron: 매일 장 마감 후)                   │
└──────────────────────┬──────────────────────────────┘
                       │ trigger
                       ▼
┌─────────────────────────────────────────────────────┐
│                 Python 스크립트                       │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   yfinance   │  │  RSS 수집기  │  │ DuckDuckGo │ │
│  │  시세/재무   │  │  섹터 뉴스   │  │  뉴스 보강  │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
│         │                 │                │         │
│         └─────────┬───────┘────────────────┘         │
│                   ▼                                  │
│         ┌──────────────────┐                         │
│         │  OpenAI API      │                         │
│         │  (GPT-4o mini)   │                         │
│         │  리서치 노트 생성 │                         │
│         └────────┬─────────┘                         │
│                  │                                   │
│         ┌────────▼─────────┐                         │
│         │   출력 생성기     │                         │
│         │  .md / Slack     │                         │
│         └──────────────────┘                         │
└─────────────────────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌───────────┐ ┌──────────┐ ┌─────────┐
   │ Obsidian  │ │   CSV    │ │  Slack  │
   │ vault .md │ │ 시세이력  │ │ webhook │
   │ (Phase 1) │ │ (Phase 1)│ │(Phase 2)│
   └───────────┘ └──────────┘ └─────────┘
```

### 2.2 데이터 흐름

```
1. GitHub Actions cron 트리거 (UTC 22:00 = KST 07:00, 미 장 마감 후)
2. watchlist.yaml에서 관심 종목 목록 로드
3. yfinance로 각 종목의 시세/재무 데이터 수집
4. RSS 피드에서 관련 뉴스 헤드라인 수집
5. DuckDuckGo Search로 종목별 최신 뉴스 보강
6. 수집된 데이터를 OpenAI API (GPT-4o mini)에 전달
7. 구조화된 리서치 노트 .md 생성
8. Git commit & push → Obsidian vault 자동 동기화
9. (Phase 2) Slack webhook으로 요약 알림 발송
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
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "daily: 리서치 노트 자동 생성"
```

**예상 실행 시간**: 종목 20개 기준 약 3~5분 → 월 ~100분 (무료 범위 내)

### 3.2 데이터 수집 모듈

#### 3.2.1 시세/재무 — yfinance (무료)

```
수집 항목:
├─ 일일 시세: 종가, 변동률, 거래량
├─ 기본 지표: PER, PBR, 시가총액, 배당수익률
├─ 재무 요약: 매출, 영업이익, EPS (최근 4분기)
└─ 기술 지표: 52주 고/저, 이동평균선 위치
```

**제약**: yfinance는 비공식 API이므로 과도한 호출 시 차단 가능. 종목당 1회 호출, 요청 간 1초 딜레이 적용.

#### 3.2.2 뉴스 수집 — RSS + DuckDuckGo (무료)

**RSS 소스 목록**:

| 소스 | URL 패턴 | 용도 |
|---|---|---|
| Seeking Alpha | `/feed/...` | 종목별 분석 |
| Yahoo Finance | RSS feed | 시장 전반 |
| Reuters Business | RSS feed | 글로벌 뉴스 |

**DuckDuckGo 보강**: `duckduckgo-search` 파이썬 패키지로 종목명 + 키워드 검색. 무료, rate limit 주의.

```
검색 쿼리 예시:
  "{ticker} {company_name} earnings news 2026"
  "{ticker} analyst rating upgrade downgrade"
```

### 3.3 AI 분석 — OpenAI API (GPT-4o mini)

**모델 선택 근거**: 비용 최소화가 최우선. GPT-4o mini ($0.15/1M in, $0.60/1M out)는 뉴스 요약 및 구조화 작업에 충분한 성능.

**프롬프트 전략**:

```
입력 (종목당 ~1,500 토큰):
├─ 시세/재무 데이터 (JSON)
├─ 뉴스 헤드라인 5~10개
└─ 시스템 프롬프트 (리서치 노트 포맷 지정)

출력 (종목당 ~800 토큰):
├─ 핵심 요약 (3줄)
├─ 주요 뉴스 & 의미
├─ 재무 하이라이트
├─ 관심 포인트 / 리스크
└─ 데이터 스냅샷 테이블
```

**배치 전략**: 종목을 5개씩 그룹으로 묶어 1회 API 호출 → 호출 횟수 감소, 시스템 프롬프트 토큰 절약.

**비용 추정 (종목 20개, 일 1회)**:

| 항목 | 토큰 | 일 비용 | 월 비용 |
|---|---|---|---|
| Input (20종목) | ~30,000 | $0.0045 | $0.10 |
| Output (20종목) | ~16,000 | $0.0096 | $0.21 |
| **합계** | | | **~$0.31** |

→ 월 $1 미만. 목표($5) 대비 충분한 여유.

### 3.4 출력 형식

#### Obsidian .md — 리서치 노트 (Phase 1)

```
output/
├── daily/
│   ├── 2026-04-08.md          # 일일 종합 요약
│   └── ...
├── tickers/
│   ├── AAPL/
│   │   ├── 2026-04-08.md      # 종목별 상세 노트
│   │   └── ...
│   ├── MSFT/
│   └── ...
└── data/
    └── price_history.csv       # 시세 이력 누적
```

**일일 종합 노트 구조**:

```markdown
# Daily Research — 2026-04-08

## Market Overview
S&P 500: 5,234.18 (+0.45%) | NASDAQ: 16,892.33 (+0.62%)

## Watchlist Summary
| Ticker | Price | Change | Signal |
|--------|-------|--------|--------|
| AAPL   | $198  | +1.2%  | 52주 고점 근접 |
| ...    |       |        |        |

## Top Movers
- **NVDA** (+3.4%): AI 서버 수주 확대 보도...
- **TSLA** (-2.1%): 유럽 판매량 감소 우려...

## Action Items
- [ ] AAPL 실적 발표 (4/15) 전 포지션 점검
- [ ] META 목표가 상향 — 근거 확인 필요
```

#### Slack 알림 (Phase 2)

Incoming Webhook (무료)으로 일일 요약 3~5줄 발송. 상세 내용은 Obsidian 노트 링크.

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

### 결정 2: OpenAI GPT-4o mini vs. Claude Haiku

| 기준 | GPT-4o mini ✅ | Claude Haiku |
|---|---|---|
| Input 단가 | $0.15/1M | $0.25/1M |
| Output 단가 | $0.60/1M | $1.25/1M |
| Web Search 내장 | ❌ (별도 구현) | ✅ (추가 비용) |
| 구조화 출력 | JSON mode 지원 | 유사 지원 |

→ 토큰 단가 40% 절약. Web search는 DuckDuckGo로 무료 대체.

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
stock-research-automation/
├── .github/
│   └── workflows/
│       └── stock-research.yml
├── config/
│   └── watchlist.yaml          # 관심 종목 목록
├── src/
│   ├── __init__.py
│   ├── collector/
│   │   ├── price.py            # yfinance 시세/재무 수집
│   │   ├── news_rss.py         # RSS 뉴스 수집
│   │   └── news_search.py      # DuckDuckGo 검색 보강
│   ├── analyzer/
│   │   └── research_note.py    # OpenAI API 리서치 노트 생성
│   ├── output/
│   │   ├── markdown.py         # .md 파일 생성
│   │   └── slack.py            # Slack webhook 알림
│   └── utils/
│       └── config.py           # 설정 로더
├── output/                     # 생성된 리서치 노트 (Git 관리)
│   ├── daily/
│   ├── tickers/
│   └── data/
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
  - ticker: NVDA
    name: NVIDIA Corp.
    sector: Semiconductors
    keywords: ["GPU", "data center", "AI chips"]
  - ticker: MSFT
    name: Microsoft Corp.
    sector: Technology
    keywords: ["Azure", "Copilot", "cloud"]
```

---

## 6. 비용 요약

| 항목 | 월 비용 |
|---|---|
| GitHub Actions | $0 (무료 티어) |
| yfinance | $0 |
| RSS / DuckDuckGo | $0 |
| OpenAI API (20종목, 일 1회) | ~$0.31 |
| Slack Webhook | $0 |
| **총 월 비용** | **~$0.31** |

30종목으로 확장 시에도 ~$0.47/월. 목표($5) 대비 10배 이상 여유.

---

## 7. 단계별 구현 로드맵

| Phase | 범위 | 예상 소요 |
|---|---|---|
| **Phase 1** | yfinance 수집 + RSS + GPT-4o mini 노트 생성 + .md 출력 | 1~2일 |
| **Phase 2** | GitHub Actions 배포 + Git 자동 커밋 | 반나절 |
| **Phase 3** | Slack 알림 추가 | 2시간 |
| **Phase 4** | DuckDuckGo 뉴스 보강 + 프롬프트 튜닝 | 1일 |

---

## 8. 리스크 및 완화 방안

| 리스크 | 영향 | 완화 |
|---|---|---|
| yfinance API 차단 | 시세 수집 불가 | 요청 딜레이 적용, 백업으로 Alpha Vantage 무료 티어 (일 25회) |
| OpenAI 가격 인상 | 비용 증가 | 모델 교체 용이하도록 추상화 레이어 설계 |
| GitHub Actions 무료 한도 초과 | 실행 중단 | 월 100분 내외 사용, 한도(2,000분) 대비 여유 |
| DuckDuckGo rate limit | 뉴스 보강 실패 | Graceful degradation — 검색 실패 시 RSS 뉴스만으로 노트 생성 |
| RSS 피드 구조 변경 | 파싱 오류 | try/except + 알림, feedparser 라이브러리로 표준 처리 |

---

## 9. 향후 확장 고려 사항

현재 설계에서는 제외하되, 나중에 검토할 수 있는 항목:

- **한국 주식 추가**: pykrx 라이브러리 + 한경/매경 RSS
- **SQLite 마이그레이션**: 종목 간 비교, 이력 트렌드 분석이 필요해지면
- **Excel 리포트**: 월간/주간 포트폴리오 성과 정리가 필요해지면
- **모델 업그레이드**: GPT-4o로 전환 시 더 깊은 분석 가능 (비용 증가 수반)
- **포트폴리오 트래킹**: 보유 종목 수익률 자동 계산

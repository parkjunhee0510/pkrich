# 주식 리서치 자동화

저비용 배치 기반으로 미국 주식 리서치 노트를 생성하는 프로젝트입니다.

파이프라인 흐름은 아래를 유지합니다.

1. `config/watchlist.yaml` 로드
2. `src/collector`에서 시세/재무/뉴스 수집
3. `src/analyzer`에서 배치 LLM 분석
4. `src/output`에서 Markdown/JSON/Slack 출력
5. 결과물을 `output/`와 웹/Obsidian 대상으로 동기화

## 핵심 특징

- GitHub Actions 기반 일일 배치 실행
- OpenAI 배치 분석과 배치별 fallback
- Google News RSS + Yahoo Finance/Reuters/AP/CNBC/MarketWatch 도메인 제한 검색 + DuckDuckGo 보강 수집
- SEC EDGAR 공시 + 기업 IR/보도자료 RSS 보강 수집
- yfinance 우선, 가격은 Stooq fallback, 재무/이벤트는 Alpha Vantage optional fallback
- 일간 노트, 종목 노트, 주간 노트, 웹 대시보드 JSON 자동 생성
- Obsidian Markdown 미러링 지원
- 구조화 파이프라인 로그 및 요약 리포트 생성

## 빠른 시작

### 1. 의존성 설치

```bash
python --version
pip install -r requirements.txt
```

웹 대시보드를 함께 쓰려면:

```bash
cd web
npm install
```

### 2. 환경 변수 설정

`.env.example`을 복사해 `.env`를 만듭니다.

```bash
cp .env.example .env
```

| 변수 | 필수 | 설명 |
|------|------|------|
| `OPENAI_API_KEY` | O | OpenAI API 키 |
| `OPENAI_MODEL` | X | 기본값 `gpt-5.4-mini` |
| `OPENAI_MODEL_PROFILE` | X | `config/models.yaml`의 profile 선택. 기본값 `economy` |
| `SLACK_WEBHOOK_URL` | X | Slack 요약 알림 webhook |
| `ENABLE_EXTERNAL_FETCH` | X | 기본값 `true`, `false`면 외부 수집 비활성화 |
| `OBSIDIAN_VAULT_PATH` | X | 설정 시 Markdown을 `${OBSIDIAN_VAULT_PATH}/pkrich/` 아래로 미러링 |
| `ALPHAVANTAGE_API_KEY` | X | yfinance 누락 시 재무/이벤트 fallback에 사용 |
| `DATASTORE_BACKEND` | X | `csv` 또는 `sqlite`, 기본값 `csv` |
| `BATCH_SIZE` | X | 동적 배치 대신 수동 종목 수 override |

주의:
- `OBSIDIAN_VAULT_PATH`는 따옴표 없이 넣는 것을 권장합니다.
- `output/`이 항상 source of truth이며, Obsidian은 미러 대상입니다.
- `config/models.yaml`이 없으면 기본 내장 profile로 동작합니다.
- `config/portfolio.yaml`이 없으면 포트폴리오 섹션은 생성되지 않습니다.

### 3. 관심 종목 설정

모든 티커는 `config/watchlist.yaml`에서만 관리합니다.

```yaml
watchlist:
  - ticker: AAPL
    name: Apple Inc.
    sector: Technology
    keywords: ["iPhone", "services revenue", "AI"]
    exclude_keywords: ["lawsuit recap"]
    cik: "0000320193"
    ir_rss_feeds: ["https://www.apple.com/newsroom/rss-feed.rss"]
    ir_source_names:
      apple.com: Apple Newsroom
    sec_filing_tag_priority:
      실적: 160
```

- `keywords`: 뉴스 검색에 우선 반영
- `exclude_keywords`: 제목 기준 제외 필터
- `cik`: SEC EDGAR 공시 수집에 사용
- `ir_rss_feeds`: 공식 IR/보도자료 RSS feed 목록
- `ir_source_names`: 해당 종목에만 적용할 IR 브랜드명 override
- `sec_filing_tag_priority`: 해당 종목에만 적용할 SEC 공시 태그 가중치 override

모델 profile은 `config/models.yaml`에서 관리합니다.

```yaml
default_profile: economy
profiles:
  economy:
    model: gpt-5.4-mini
    context_window: 400000
    max_output_tokens: 32000
```

포트폴리오 추적은 선택 사항이며 `config/portfolio.yaml`을 사용합니다.

```yaml
holdings:
  - ticker: AAPL
    shares: 10
    avg_cost: 150
    currency: USD
```

### 4. 실행

```bash
python main.py
```

## 생성 결과물

### Markdown

- `output/daily/YYYY-MM-DD.md`: 일일 리서치
- `output/daily/weekly/YYYY-Www.md`: 주간 리서치
- `output/tickers/{TICKER}/YYYY-MM-DD.md`: 종목별 상세 노트

종목 노트에는 아래가 포함됩니다.

- 요약
- 주요 뉴스
- 재무 하이라이트
- 리스크 / 체크포인트
- 데이터 스냅샷
- 최근 변화 비교 (`7D`, `30D`, 뉴스 톤)
- 최근 4분기 재무
- 다가오는 일정
- 최근 타임라인 요약
- 시그널 / 한줄 결론

일일 노트에는 `## SEC 공시` 섹션이 추가되어, 당일 반영된 SEC EDGAR 공시를 종목별로 모아 볼 수 있습니다.

### 데이터 파일

- `output/data/price_history.csv`
- `output/data/dashboard.json`
- `output/data/price_history.json`
- `output/data/ticker_timelines.json`
- `output/data/price_history.sqlite` (`DATASTORE_BACKEND=sqlite`일 때)

### 로그

- `logs/pipeline/YYYY-MM-DD.jsonl`
- `logs/pipeline/YYYY-MM-DD.summary.json`

요약 로그에는 아래가 포함됩니다.

- 컴포넌트별 warning/error count
- ticker별 fallback 여부
- source별 실패 횟수
- provider 사용 횟수
- 모델별 usage 집계
- `daily_api_cost_usd`
- 최근 에러 목록
- ticker별 top scored headline

## 웹 대시보드

`python main.py` 실행 시 아래 JSON이 자동으로 `web/public/output/data/`로 동기화됩니다.

- `dashboard.json`
- `price_history.json`
- `ticker_timelines.json`

개발 서버 실행:

```bash
cd web
npm run dev
```

주요 기능:
- 날짜 선택
- 티커/종목명 검색
- 섹터 필터
- `7D`, `30D` 변화 표시
- 뉴스 톤 표시
- SEC 공시 태그 배지 표시 (`[실적]`, `[배당]`, `[주주총회]`, `[기타 공시]`)
- 다가오는 일정 배지
- Ticker detail 타임라인 30일/90일 보기
- daily JSON에 포트폴리오 요약 포함

## Obsidian 연동

`OBSIDIAN_VAULT_PATH`를 설정하면 아래 경로로 Markdown이 자동 복사됩니다.

- `${OBSIDIAN_VAULT_PATH}/pkrich/daily/YYYY-MM-DD.md`
- `${OBSIDIAN_VAULT_PATH}/pkrich/tickers/{TICKER}/YYYY-MM-DD.md`

CSV/JSON은 Obsidian으로 복사하지 않습니다.

## Slack 알림

`SLACK_WEBHOOK_URL`이 있으면 일일 실행 후 성공 요약을 보냅니다.

포함 항목:
- 실행 날짜
- 시장 개요
- 상위 3개 움직임
- 포트폴리오 요약(설정된 경우)
- 점검 항목
- 다가오는 일정 최대 3건
- 생성된 일일/주간 노트 경로

Webhook 미설정이나 전송 실패는 warning 로그만 남기고 파이프라인은 계속 진행합니다.

## 데이터 소스 정책

- 가격/재무 1차: `yfinance`
- 가격/지수 fallback: `Stooq`
- 재무/이벤트 fallback: `Alpha Vantage` (optional)
- 뉴스: Google News RSS, Yahoo Finance/Reuters/AP/CNBC/MarketWatch 도메인 제한 검색, DuckDuckGo 보강
- 뉴스 보강: SEC EDGAR 공시, 기업 IR/보도자료 RSS
- 출처 쏠림 방지: `config/output.yaml`의 `news_source_max_items_per_source`로 소스별 최대 비중 제한
- IR 브랜드명은 `config/output.yaml`의 `ir_source_names`에서 쉽게 바꿀 수 있습니다.
- 특정 종목만 별도 브랜드명을 쓰고 싶으면 `config/watchlist.yaml`의 `ir_source_names`가 전역 설정보다 우선합니다.

모든 외부 수집 실패는 가능한 범위에서 graceful degradation으로 처리합니다.

## Datastore

- 기본 backend는 `csv`
- `DATASTORE_BACKEND=sqlite`로 바꾸면 SQLite upsert/query를 사용합니다.
- 웹 호환을 위해 `price_history.csv`는 backend와 무관하게 계속 생성됩니다.
- CSV -> SQLite one-shot 마이그레이션 스크립트:

```bash
python -m src.utils.migrate_csv_to_sqlite
```

## 테스트

```bash
python -m unittest discover -s tests -v
python -m compileall main.py src tests
```

웹 빌드 확인:

```bash
cd web
npm run build
```

## GitHub Actions

- `stock-research.yml`: 일일 파이프라인 실행
- `deploy-dashboard.yml`: 웹 대시보드 빌드/배포

기본 브랜치는 `main`입니다.

## 디렉터리 구조

```text
output/
├── daily/
│   └── weekly/
├── tickers/
└── data/
```

```text
src/
├── collector/
├── analyzer/
├── output/
└── utils/
```

## 설계 원칙

- 배치 아키텍처 유지
- `collect -> analyze -> output` 레이어 분리 유지
- analyzer/output에서 외부 API 직접 호출 금지
- GitHub Actions에는 비즈니스 로직을 넣지 않음
- 비용 증가가 큰 변경은 피하고, free source 우선

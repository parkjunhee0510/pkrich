# Roadmap

## 현재 상태

```
collect → analyze → output → web dashboard
(일 1회 배치)    (OpenAI)   (static JSON)   (React SPA)
```

**파이프라인:** `stock-research.yml` 매일 22:00 UTC (월~금) 자동 실행  
**티커:** 11종목 / 6섹터 (Tech·Energy·Industrials·Staples·Services·Utilities)  
**Pages:** Dashboard / TickerDetail / Signals / Backtest / Portfolio / Calendar / Scenario / Chat / ApiStatus

---

## Phase 1 — 데이터 수집 아키텍처 + 품질 강화

> collector 레이어를 확장 가능한 플러그인 구조로 전환한 뒤, 해당 구조 위에 신규 데이터를 추가한다.

### 1-0. Collector 아키텍처 리팩토링 (선행 과제)

#### 현재 문제점

| 문제 | 현황 | 영향 |
|------|------|------|
| God-module | `price.py` 1,946줄이 13개 수집원 직접 호출 | 새 소스 추가 시 price.py 수정 필수 |
| 순차 실행 | 티커별 0.1s sleep, 전체 직렬 순회 | 50종목 확장 시 수집만 10분+ |
| 네이브 rate limit | 소스별 sleep 기반 | 실행 초반 burst, 후반 starvation |
| 캐시 없음 | Alpha Vantage 인메모리 캐시, 교차 실행 시 소멸 | 매 실행마다 동일 API 재호출 |
| fallback 하드코딩 | if/elif 분기로 fallback 순서 고정 | fallback 우선순위 변경 시 코드 수정 |

#### 1-0a. Provider 인터페이스 도입

```python
# src/collector/base.py (신규)
class DataProvider(ABC):
    name: str
    provides: set[str]           # {"price", "fundamentals", "options", ...}
    priority: int                # 낮을수록 우선
    rate_limit: RateLimit        # 토큰 버킷 설정

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def collect(self, ticker: str, ctx: CollectionContext) -> PartialTickerData: ...
```

- 각 수집원(yfinance, FMP, Finnhub, Polygon...)이 `DataProvider` 구현
- `provides` 필드로 어떤 데이터 유형을 제공하는지 선언
- `priority`로 같은 유형 제공 시 우선순위 자동 결정 (fallback chain 자동화)

#### 1-0b. Provider Registry + Orchestrator

```python
# src/collector/registry.py (신규)
class ProviderRegistry:
    def register(self, provider: DataProvider) -> None: ...
    def providers_for(self, data_type: str) -> list[DataProvider]: ...  # priority순

# src/collector/orchestrator.py (신규)
class CollectionOrchestrator:
    def collect_all(self, watchlist, run_date) -> dict[str, CollectedTickerData]:
        # 1. 데이터 유형별 provider chain 자동 구성
        # 2. 티커별 병렬 수집 (ThreadPoolExecutor)
        # 3. 결과 병합: 우선순위 높은 provider 데이터가 이김
        # 4. 실패 시 자동 fallback → 다음 priority provider
```

- **price.py god-module 분해**: 기존 로직을 provider별 파일로 분리
  - `providers/yfinance_provider.py`
  - `providers/alphavantage_provider.py`
  - `providers/fmp_provider.py`
  - `providers/finnhub_provider.py`
  - `providers/polygon_provider.py`
  - `providers/sec_provider.py`
  - `providers/stooq_provider.py`
- **pipeline.py 변경**: `collect_market_data()` → `orchestrator.collect_all()` 로 교체

#### 1-0c. 중앙 Rate Limiter

```python
# src/collector/rate_limiter.py (신규)
class TokenBucketLimiter:
    def __init__(self, calls_per_minute: int): ...
    async def acquire(self) -> None: ...  # 토큰 소진 시 대기

# 설정: config/providers.yaml (신규)
providers:
  yfinance:     { rate: 30/min, priority: 1 }
  alphavantage: { rate: 5/min,  priority: 3 }
  fmp:          { rate: 120/min, priority: 2 }
  finnhub:      { rate: 60/min,  priority: 2 }
  polygon:      { rate: 5/min,  priority: 2 }
  sec_edgar:    { rate: 10/min, priority: 1 }
```

- provider별 rate limit을 YAML 설정으로 외부화
- 토큰 버킷 알고리즘으로 burst 방지 + 공정 분배

#### 1-0d. 교차 실행 캐시

```python
# src/collector/cache.py (신규)
class ResponseCache:
    # SQLite 기반, output/data/api_cache.sqlite
    def get(self, provider, ticker, date) -> dict | None: ...
    def set(self, provider, ticker, date, data, ttl_hours) -> None: ...
```

- TTL 기반 캐시 (fundamentals: 24h, price: 4h, news: 12h)
- API 실패 시 만료된 캐시라도 stale 데이터로 반환 (graceful degradation 강화)
- GitHub Actions 환경에서는 `output/data/api_cache.sqlite` 를 artifact로 보존

#### 1-0e. 마이그레이션 전략

| 단계 | 작업 | 리스크 |
|------|------|--------|
| Step 1 | `base.py`, `registry.py`, `rate_limiter.py`, `cache.py` 생성 | 없음 (신규) |
| Step 2 | `yfinance_provider.py` 먼저 분리, orchestrator에서 호출 | 낮음 (가장 안정적인 소스) |
| Step 3 | `price.py`의 yfinance 로직 제거, orchestrator 경유로 전환 | 중간 (통합 테스트 필수) |
| Step 4 | 나머지 provider 하나씩 분리 (FMP → Finnhub → Polygon → SEC → Stooq → AlphaVantage) | 낮음 (각각 독립) |
| Step 5 | `price.py` → thin wrapper (하위 호환), 최종 제거 | 낮음 |

---

### 1-1. 티커별 병렬 수집

- **전제:** 1-0b Orchestrator 완료 후
- **작업:** `CollectionOrchestrator.collect_all()` 에 `ThreadPoolExecutor(max_workers=4)` 적용
- **제약:**
  - provider별 rate limiter가 병렬 환경에서도 글로벌 제한 준수
  - yfinance는 내부적으로 thread-safe 아님 → 별도 lock 또는 프로세스 분리
- **효과:** 11종목 기준 수집 시간 ~60% 단축, 50종목 확장 시 선형 증가 방지

### 1-2. 섹터 ETF 상대강도 수집

- **전제:** 1-0a Provider 인터페이스 완료 후
- **작업:**
  - `providers/sector_etf_provider.py` 신규 생성 (DataProvider 구현)
  - `provides: {"sector_rs"}`, `priority: 1`
  - XLK / XLE / XLI / XLY / XLU / XLC 6개 ETF 수집
- **설정:**
  ```yaml
  # config/watchlist.yaml 확장
  sector_etf_map:
    Technology: XLK
    Energy: XLE
    Industrials: XLI
    Consumer Staples: XLY
    Communication Services: XLC
    Utilities: XLU
  ```
- **분석 연동:** `decision_layer.py` momentum 팩터에 `rs_vs_sector_etf` 가중치 추가
- **출력:** `data_snapshot["RS vs Sector ETF"]`, TickerDetail 카드 표시

### 1-3. 옵션 플로우 요약 강화

- **작업:**
  - `providers/polygon_provider.py` 에 OI 변화량 계산 추가 (전일 snapshot vs 당일)
  - 교차 실행 캐시(1-0d)에서 전일 OI snapshot 자동 참조
  - 대형 거래 감지: single leg volume > OI × 0.3 → unusual activity flag
- **분류:** PCR 3일 추세 → `options_tone` (bullish / neutral / bearish) 자동 태깅
- **출력:** `options_summary.tone`, `options_summary.unusual_activity`
- **UI:** TickerDetail Options 섹션에 톤 배지 + 이상 거래 알림 표시

### 1-4. 실적 서프라이즈 이력 자동 분류

- **작업:**
  - `src/utils/earnings_pattern.py` 신규 생성 (순수 수식, LLM 불필요)
  - 입력: `quarterly_financials` 배열 (이미 수집됨)
  - 출력:
    - `beat_streak`: 연속 beat 횟수 (0~N)
    - `surprise_trend`: improving / deteriorating / stable (최근 4분기 서프라이즈 % 기울기)
    - `avg_surprise_pct`: 평균 서프라이즈 비율
- **분석 연동:** `decision_layer.py` `earnings_pattern` 팩터에 streak/trend 반영
- **UI:** EpsSurpriseChart 하단에 패턴 텍스트 + 연속 beat 배지

### 1-5. Insider 거래 감지 강화

- **현황:** `sec_form4.py` 존재, FMP insider도 존재, 양쪽 데이터 통합 안 됨
- **작업:**
  - `providers/insider_provider.py` 신규 (DataProvider 구현)
  - FMP insider (priority 1) → SEC Form 4 (priority 2) fallback 자동화
  - 집계 로직: 30일 window → 순매수/순매도 금액 합산
- **분류:**
  - 순매수 $100K+ → `insider_tone: bullish` (hard signal)
  - 순매도 $500K+ → `insider_tone: bearish` (risk flag)
  - 그 외 → `insider_tone: neutral`
- **분석 연동:** `decision_layer.py` 에 `insider_activity` 팩터 추가 (9번째)
- **출력:** TickerDetail 타임라인에 Form 4 항목 표시, Watchlist 카드에 insider 배지

### 1-6. 신규 Provider 확장 가이드

> 1-0 아키텍처 완료 후 신규 데이터 소스 추가는 아래 3단계로 완료된다.

```
Step 1. providers/ 에 DataProvider 구현체 작성
Step 2. config/providers.yaml 에 rate·priority 설정
Step 3. 끝 — Registry가 자동 발견, Orchestrator가 자동 호출
```

예시: Reddit sentiment provider 추가 시

```python
# src/collector/providers/reddit_provider.py
class RedditSentimentProvider(DataProvider):
    name = "reddit"
    provides = {"social_sentiment"}
    priority = 3

    def is_available(self) -> bool:
        return bool(os.getenv("REDDIT_CLIENT_ID"))

    def collect(self, ticker, ctx):
        # r/wallstreetbets, r/stocks mention volume + sentiment
        ...
```

---

## Phase 2 — 시그널 검증 고도화

> `signal_tracker.csv` 14개 컬럼 기반에서 분석 고도화

### 2-1. 수익 추적 GitHub Actions 자동화

- **현황:** 1D/5D/20D 백필이 `main.py` 실행 시에만 수행
- **작업:** `stock-research.yml` 에 별도 `backfill` job 추가 (매일 파이프라인 완료 후 실행)
- **로직:** `src/utils/signal_tracker.py` → `backfill_returns()` 함수 분리, 독립 호출 가능하게
- **효과:** 주말·공휴일 이후에도 5D/20D 수익 자동 업데이트

### 2-2. 종목별 신호 등급화 (A/B/C)

- **기준:**
  - A: 5D 승률 ≥ 60%, 신호 수 ≥ 10
  - B: 5D 승률 ≥ 45%, 신호 수 ≥ 5
  - C: 그 외
- **작업:** `src/utils/signal_tracker.py` 에 `compute_ticker_grade()` 추가
- **출력:** `meta_analysis.ticker_grade` 맵 → Dashboard 티커 카드에 등급 배지 표시
- **의사결정 반영:** `decision_layer.py` `signal_track_record` 팩터에 등급 가중치 적용

### 2-3. 촉매 유형별 최적 홀딩 기간 분석

- **현황:** `catalyst_tag` 컬럼 존재, 그룹별 분석 없음
- **작업:** `src/backtester/engine.py` 에 `by_catalyst` 분석 추가
  - 8-K / 실적 / 뉴스 / 기타 → 각 그룹의 1D·5D·20D 평균 수익 비교
  - 최대 수익 구간(peak return day) 추정
- **출력:** `backtest_summary.json` 에 `by_catalyst` 섹션 추가
- **UI:** Backtest 페이지에 촉매별 최적 홀딩 기간 테이블 추가

### 2-4. False Signal 패턴 요약

- **작업:** `src/analyzer/` 에 `signal_postmortem.py` 신규 생성
- **로직:** 5D 수익 < -3% 인 신호 추출 → 공통 특징(시장 레짐, VIX 수준, 촉매 유형) 분석
- **LLM 사용:** 월 1회 배치 실행 (비용 최소화)
- **출력:** `weekly_summary` 에 `false_signal_patterns` 섹션 추가

---

## Phase 3 — 대시보드 UX 확장

### 3-1. Watchlist 필터 / 정렬

- **작업:** `web/src/pages/Dashboard.tsx` 컨트롤 바 확장
- **필터 옵션:**
  - 섹터 (Technology / Energy / Industrials / ...)
  - 액션 (buy / watch / avoid)
  - SetupScore 범위 슬라이더
  - 실적 D-day ≤ 7일 토글
- **정렬:** SetupScore 내림차순 / 등락률 / 시가총액
- **상태 관리:** URL 쿼리스트링에 저장 (새로고침 유지)

### 3-2. 알림 시스템

- **채널:** Slack (기존 `SLACK_WEBHOOK_URL` 활용)
- **조건별 알림:**
  - 실적 D-3 이하 진입
  - 목표가 ±5% 이내 도달
  - SetupScore 전일 대비 +15 이상 급등
  - 시그널 발생 후 20D 평가 완료
- **작업:** `src/output/` 에 `alerts.py` 신규 생성, `pipeline.py` 에서 호출
- **포맷:** 티커 / 조건 / 현재값 / 링크 (GitHub Pages URL)

### 3-3. Scenario 페이지 고도화

- **현황:** 포트폴리오 비중 조정 UI, ATR 리스크 재계산까지 구현됨
- **추가 작업:**
  - 매크로 시나리오 프리셋 (금리 상승 / 달러 강세 / 리세션) 버튼
  - 시나리오별 섹터 민감도 자동 적용 (`macro_sensitivity.py` 연동)
  - 예상 포트폴리오 P&L 변화 시각화

### 3-4. 모바일 최적화

- **현황:** 데스크탑 중심 레이아웃, `@media (max-width: 768px)` 일부만 존재
- **작업:**
  - Watchlist 카드 → 모바일에서 핵심 정보만 노출 (compact 모드 자동 활성화)
  - TickerDetail 섹션 → accordion 기본 접힘 처리
  - 네비게이션 → 햄버거 메뉴 또는 하단 탭바

---

## Phase 4 — 분석 아키텍처 + 확장

> Phase 1이 collector 레이어를 플러그인 구조로 전환했듯이, Phase 4는 analyzer·decision 레이어를 확장 가능한 구조로 전환한다.

### 4-0. Analyzer 아키텍처 리팩토링 (선행 과제)

#### 현재 문제점

| 문제 | 현황 | 영향 |
|------|------|------|
| God-module | `research_note.py` 2,066줄에 LLM 호출·배치·프롬프트·파싱·폴백 전부 | 새 분석 유형 추가 시 research_note.py 수정 필수 |
| 프롬프트 결합 | 시스템 프롬프트에 밸류에이션·트레이드·뉴스 규칙 혼재 (826줄~) | 한 규칙 수정이 전체 분석 품질에 영향 |
| 팩터 하드코딩 | decision_layer.py 8개 팩터가 코드에 직접 구현 | 팩터 추가/제거 시 코드 수정 + 정규화 공식 변경 |
| 단일 LLM 경로 | 모든 티커가 동일 프롬프트 → 한 번의 API 호출 | 분석 유형별 전문화 불가 |
| 정규화 공식 고정 | `(raw + 50) / 170 * 100` 하드코딩 | 팩터 범위 변경 시 수동 재계산 필수 |

#### 4-0a. AnalysisModule 인터페이스 도입

```python
# src/analyzer/base.py (신규)
class AnalysisModule(ABC):
    name: str
    requires: set[str]           # {"price_action", "fundamentals", ...}
    produces: set[str]           # {"valuation_score", "trade_frame", ...}
    priority: int                # 실행 순서 (낮을수록 먼저)
    llm_required: bool           # False면 순수 수식 모듈

    @abstractmethod
    def analyze(self, ctx: AnalysisContext) -> ModuleResult: ...

    def estimate_tokens(self, ctx: AnalysisContext) -> int: ...
```

- 각 분석 관심사(밸류에이션, 트레이드 프레임, 뉴스 톤, 리스크 등)를 독립 모듈로 분리
- `requires` 로 입력 데이터 의존성 선언 → 실행 순서 자동 결정
- `produces` 로 출력 필드 선언 → 다운스트림 모듈이 참조 가능
- `llm_required: False` 모듈은 LLM 비용 없이 실행 (수식 기반)

#### 4-0b. AnalysisOrchestrator + ModuleRegistry

```python
# src/analyzer/registry.py (신규)
class ModuleRegistry:
    def register(self, module: AnalysisModule) -> None: ...
    def resolve_order(self) -> list[AnalysisModule]: ...  # DAG 토폴로지 정렬

# src/analyzer/orchestrator.py (신규)
class AnalysisOrchestrator:
    def analyze_all(self, tickers, collected_data, macro_context) -> list[TickerAnalysis]:
        # 1. 모듈 의존성 DAG 구성 (requires ↔ produces 매칭)
        # 2. 비-LLM 모듈 먼저 실행 (수식 기반 → 결과를 LLM 컨텍스트에 주입)
        # 3. LLM 모듈 배치 최적화 (토큰 버짓 내에서 병합)
        # 4. 결과 병합 → TickerAnalysis 조립
```

- **research_note.py god-module 분해**: 기존 로직을 모듈별 파일로 분리
  - `modules/valuation_module.py` — 밸류에이션 점수 (수식 기반, LLM 불필요)
  - `modules/trade_frame_module.py` — ATR 기반 진입/손절/목표 계산 (수식)
  - `modules/news_analysis_module.py` — 뉴스 톤 + 촉매 분류 (LLM)
  - `modules/research_narrative_module.py` — 핵심 서사 생성 (LLM, 기존 summary/key_news/highlights)
  - `modules/risk_assessment_module.py` — 리스크 포인트 식별 (LLM)
  - `modules/signal_takeaway_module.py` — 최종 시그널 방향 결정 (LLM, 다른 모듈 결과 종합)
- **pipeline.py 변경**: `analyze_tickers()` → `orchestrator.analyze_all()` 로 교체

#### 4-0c. PromptTemplate 시스템

```python
# src/analyzer/prompts/base.py (신규)
class PromptTemplate:
    name: str
    version: str                 # 버전 관리 (A/B 테스트용)
    system_template: str         # Jinja2 또는 f-string
    user_template: str
    output_schema: dict          # JSON Schema 정의

    def render_system(self, ctx: PromptContext) -> str: ...
    def render_user(self, ticker_data: dict) -> str: ...
    def validate_response(self, response: dict) -> bool: ...
```

- **프롬프트 외부화**: 현재 코드에 인라인된 프롬프트를 템플릿 파일로 분리
  - `prompts/research_v1.py` — 현재 프롬프트 (호환성 유지)
  - `prompts/research_v2.py` — 개선 버전 (A/B 테스트 가능)
- **버전 관리**: `config/models.yaml`에서 프롬프트 버전 선택
  ```yaml
  economy:
    model: gpt-5.4-mini
    prompt_version: research_v1
  deep:
    model: o3-mini
    prompt_version: research_v2
  ```
- **스키마 검증**: 모듈별 출력 스키마를 `output_schema`로 정의 → LLM 응답 자동 검증

#### 4-0d. DecisionFactor 플러그인 시스템

```python
# src/decision/base.py (신규)
class DecisionFactor(ABC):
    name: str
    weight_range: tuple[int, int]  # (min, max) from YAML
    description: str

    @abstractmethod
    def score(self, analysis: TickerAnalysis, collected: CollectedTickerData,
              regime: MarketRegime, signal_stats: dict) -> FactorScore: ...

@dataclass(frozen=True)
class FactorScore:
    value: int           # 실제 점수
    confidence: float    # 0.0~1.0 신뢰도
    reasoning: str       # 한국어 설명
```

- 각 팩터를 독립 클래스로 분리
  - `factors/valuation_factor.py`
  - `factors/momentum_factor.py`
  - `factors/catalyst_factor.py`
  - `factors/signal_record_factor.py`
  - `factors/news_tone_factor.py`
  - `factors/regime_factor.py`
  - `factors/earnings_factor.py`
  - `factors/fundamentals_factor.py`
- **자동 정규화**: 팩터 등록 시 `weight_range` 읽어서 정규화 공식 자동 계산
  ```python
  # src/decision/scorer.py (신규)
  class ConvictionScorer:
      def calculate(self, factor_scores: list[FactorScore]) -> int:
          total_min = sum(f.weight_range[0] for f in self.factors)
          total_max = sum(f.weight_range[1] for f in self.factors)
          raw = sum(s.value for s in factor_scores)
          return int((raw - total_min) / (total_max - total_min) * 100)
  ```
- **팩터 추가 = 3단계**:
  1. `factors/` 에 `DecisionFactor` 구현체 작성
  2. `config/decision_weights.yaml` 에 범위 추가
  3. 끝 — Registry가 자동 발견, Scorer가 정규화 자동 조정

#### 4-0e. 레짐 의존 팩터 가중치

```yaml
# config/decision_weights.yaml 확장
factors:
  valuation:      { min: 0,   max: 20 }
  momentum:       { min: 0,   max: 20 }
  catalyst:       { min: -10, max: 20 }
  signal_record:  { min: -10, max: 15 }
  news_tone:      { min: -5,  max: 10 }
  regime:         { min: -15, max: 15 }
  earnings:       { min: -10, max: 10 }
  fundamentals:   { min: 0,   max: 10 }

# 레짐별 팩터 승수 (기본 1.0)
regime_multipliers:
  risk_on:
    momentum: 1.3        # 모멘텀 중시
    valuation: 0.8       # 밸류에이션 덜 중요
    catalyst: 1.2
  risk_off:
    valuation: 1.4       # 밸류에이션 방어적 종목 선호
    momentum: 0.7        # 모멘텀 신뢰도 하락
    fundamentals: 1.3    # 펀더멘탈 안전 마진 중시
  neutral:
    # 모든 팩터 1.0 (기본)

thresholds:
  buy: 65
  buy_risk_off: 75
  avoid: 35
```

- 시장 레짐에 따라 팩터별 가중치 동적 조정
- YAML 설정만으로 레짐별 전략 튜닝 가능 (코드 수정 없음)
- `ConvictionScorer`가 현재 레짐의 승수를 자동 적용

#### 4-0f. 마이그레이션 전략

| 단계 | 작업 | 리스크 |
|------|------|--------|
| Step 1 | `base.py`, `registry.py`, `orchestrator.py`, `prompts/base.py` 생성 | 없음 (신규) |
| Step 2 | `valuation_module.py` + `trade_frame_module.py` 수식 모듈 먼저 분리 | 낮음 (LLM 불필요, 검증 용이) |
| Step 3 | `research_narrative_module.py` 분리 — 기존 프롬프트 그대로 이관 | 중간 (LLM 응답 호환성 검증) |
| Step 4 | 나머지 LLM 모듈 하나씩 분리 (news → risk → signal_takeaway) | 낮음 (각각 독립) |
| Step 5 | `decision/base.py` + `scorer.py` 생성, 8개 팩터 분리 | 중간 (정규화 결과 일치 검증) |
| Step 6 | `research_note.py` → thin wrapper (하위 호환), 최종 제거 | 낮음 |

**검증 전략**: 마이그레이션 중 기존 `research_note.py` 결과와 신규 orchestrator 결과를 병렬 실행하여 diff 비교 (shadow mode)

---

### 4-1. 포트폴리오 리스크 분석 모듈 (비용 없음)

- **전제:** 4-0a AnalysisModule 인터페이스 완료 후
- **작업:** `src/analyzer/modules/portfolio_risk_module.py` (AnalysisModule 구현, `llm_required: False`)
- **계산 (순수 수식):**
  - 섹터 편중도: HHI 지수 = Σ(섹터비중²), 1,000 이하 분산양호 / 2,500+ 집중위험
  - 포트폴리오 베타: 개별 베타 × 비중 가중합
  - 상관관계 행렬: 30일 price_history 기반 종목 간 피어슨 상관계수
  - 최대 낙폭(MDD): 롤링 20일 최대 드로다운 추정
  - Value at Risk(VaR): 95% 신뢰구간 1일 예상 최대 손실
- **출력 타입:**
  ```python
  @dataclass(frozen=True)
  class PortfolioRiskMetrics:
      hhi: float
      portfolio_beta: float
      correlation_matrix: dict[str, dict[str, float]]
      mdd_20d: float
      var_95: float
      risk_grade: str  # A(안정) / B(보통) / C(집중) / D(위험)
      recommendations: list[str]  # 한국어 리스크 완화 제안
  ```
- **Decision 연동:** 신규 `portfolio_risk_factor.py` — 종목이 이미 집중된 섹터에 속하면 conviction 감점
- **UI:** Portfolio 페이지에 리스크 대시보드 섹션 (HHI 게이지, 상관관계 히트맵, MDD 차트)

### 4-2. Peer 비교 분석 프레임워크

- **전제:** Phase 1-2 (섹터 ETF) 데이터 수집 완료 후
- **작업:** `src/analyzer/modules/peer_comparison_module.py` (AnalysisModule 구현)

#### 4-2a. 자동 Peer 선정 엔진

```python
# src/analyzer/peer_selector.py (신규)
class PeerSelector:
    def select_peers(self, ticker, sector, market_cap) -> list[PeerInfo]:
        # 1. 섹터 ETF 구성 종목 로드 (Phase 1-2 데이터)
        # 2. 시가총액 ±50% 범위 필터
        # 3. 상위 3~5개 peer 선정 (유동성, 데이터 가용성 기준)
        # 4. 캐시 (peer 구성은 월 1회 갱신이면 충분)
```

#### 4-2b. 퍼센타일 랭킹 시스템

- **지표별 섹터 내 퍼센타일**:
  - PER 퍼센타일 (낮을수록 저평가)
  - RS 30D 퍼센타일 (높을수록 모멘텀 강)
  - ROE 퍼센타일
  - 매출 성장률 퍼센타일
  - 배당수익률 퍼센타일 (해당 시)
- **출력:** `peer_rank: {per_pctl: 25, rs_pctl: 78, roe_pctl: 60}` → "PER 하위 25% (저평가), 모멘텀 상위 22%"
- **LLM 연동:** `research_narrative_module` 프롬프트에 퍼센타일 데이터 주입 (토큰 ~50개 추가)
- **Decision 연동:** 신규 `peer_rank_factor.py` — PER 하위 30% + RS 상위 30% = +8점 (value-momentum sweet spot)

### 4-3. 멀티 모델 합의 시스템

- **현황:** 모든 티커가 단일 모델·단일 프롬프트로 분석
- **목표:** 중요한 결정(buy/avoid)에 대해 복수 시각 확보

#### 4-3a. 분석 앙상블 엔진

```python
# src/analyzer/ensemble.py (신규)
class AnalysisEnsemble:
    def analyze_with_consensus(self, ticker, collected, modules) -> EnsembleResult:
        # conviction ≥ 60 또는 ≤ 40인 티커만 앙상블 대상 (비용 절약)
        # 1차: economy 모델 전체 분석 (기본 파이프라인)
        # 2차: 앙상블 대상만 deep 모델로 재분석 (다른 프롬프트 버전)
        # 합의: 두 분석의 방향이 일치 → 신뢰도 상승
        #       불일치 → 'conflicted' 플래그 + 양쪽 reasoning 표시
```

#### 4-3b. 비용 제어

- **트리거 조건:** conviction이 buy/avoid 경계(35, 65) ±10 범위일 때만 2차 분석
- **예상 비용:** 11종목 중 ~3개가 경계 → deep 모델 3회 추가 ≈ $0.5/일
- **월간 추가:** ~$15
- **설정:**
  ```yaml
  # config/models.yaml 확장
  ensemble:
    enabled: true
    trigger_range: [25, 75]  # conviction이 이 범위 안에 있을 때만
    second_model: deep
    second_prompt: research_v2
    max_daily_ensemble: 5     # 하루 최대 앙상블 횟수 (비용 캡)
  ```

#### 4-3c. 합의 시각화

- **UI:** DecisionCard에 합의 배지 표시
  - ✓✓ (양 모델 일치) → 높은 신뢰
  - ✓✗ (불일치) → 주의 필요, 양쪽 reasoning 툴팁 표시
- **출력:** `decision.ensemble_agreement: "agree" | "conflict" | "single"`

### 4-5. 주간 인사이트 구조화 엔진

- **현황:** 3문장 고정 포맷 (`weekly_insight.py`), 인사이트 깊이 부족

#### 4-5a. 구조화된 주간 보고서

```python
# src/analyzer/modules/weekly_insight_module.py (AnalysisModule 구현)
class WeeklyInsightModule(AnalysisModule):
    produces = {"weekly_report"}
    llm_required = True

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        # 입력: 주간 decision 이력, signal 결과, regime 변화, macro 이벤트
        # 출력: 6개 구조화 섹션
```

- **보고서 구조:**
  ```
  1. 시장 환경 요약 — VIX 레짐 변화, 매크로 이벤트 영향, 섹터 로테이션
  2. 핵심 이동 종목 Top 3 — 주간 등락 + 촉매 + decision 변화
  3. 시그널 성과 리뷰 — 이번 주 발생 시그널의 1D/5D 수익 요약
  4. 리스크 포인트 — 포트폴리오 집중 리스크, 다음 주 매크로 이벤트
  5. 다음 주 액션 플랜 — conviction 상위 종목 + 촉매 일정
  6. 포트폴리오 제안 — 비중 조정 아이디어 (리스크 모듈 연동)
  ```
-
### 4-6. 분석 품질 자동 검증 파이프라인

> 분석이 확장될수록 품질 보증이 중요해진다.

#### 4-6a. LLM 응답 검증기

```python
# src/analyzer/validator.py (신규)
class ResponseValidator:
    def validate(self, response: dict, schema: dict, ticker_data: dict) -> ValidationResult:
        # 1. 스키마 검증: 필수 필드 존재, 타입 일치
        # 2. 사실 검증: LLM이 만든 가격/수치가 실제 데이터와 ±5% 이내
        # 3. 일관성: news_tone과 signal_or_takeaway 방향 불일치 감지
        # 4. 환각 감지: key_news에 수집되지 않은 뉴스 제목이 있으면 플래그
```

- **검증 실패 시:** 해당 필드 fallback 값으로 대체 + `validation_warnings` 로깅
- **메트릭 수집:** 일별 환각 비율, 스키마 위반 횟수 → `output/data/analysis_quality.json`

#### 4-6b. 분석 A/B 테스트 프레임워크

```python
# src/analyzer/ab_test.py (신규)
class ABTestRunner:
    def run_test(self, tickers, variant_a: PromptTemplate, variant_b: PromptTemplate):
        # 동일 데이터에 두 프롬프트 적용
        # 결과 비교: 사실 정확도, 시그널 품질 (사후 수익으로 평가)
        # 결과 저장: output/data/ab_test_results.json
```

- **실행:** 주 1회 배치 (일요일), 무작위 5종목 대상
- **비용:** ~$1/주 (두 프롬프트 × 5종목 × economy 모델)
- **목적:** 프롬프트 개선의 효과를 데이터로 검증

### 4-7. 신규 DecisionFactor 확장 가이드

> 4-0d 아키텍처 완료 후 신규 팩터 추가는 아래 3단계로 완료된다.

```
Step 1. factors/ 에 DecisionFactor 구현체 작성
Step 2. config/decision_weights.yaml 에 범위 추가
Step 3. 끝 — Registry가 자동 발견, Scorer가 정규화 자동 조정
```

예시: Options Skew 팩터 추가 시

```python
# src/decision/factors/options_skew_factor.py
class OptionsSkewFactor(DecisionFactor):
    name = "options_skew"
    weight_range = (-5, 10)
    description = "풋/콜 IV 스큐 기반 시장 센티먼트"

    def score(self, analysis, collected, regime, signal_stats):
        pcr = analysis.options_summary.get("put_call_ratio", 1.0)
        if pcr < 0.7:
            return FactorScore(value=8, confidence=0.7, reasoning="PCR 0.7 미만: 콜 우세")
        elif pcr > 1.3:
            return FactorScore(value=-5, confidence=0.8, reasoning="PCR 1.3 이상: 풋 우세")
        return FactorScore(value=0, confidence=0.5, reasoning="PCR 중립")
```

예시: 신규 AnalysisModule 추가 시

```
Step 1. modules/ 에 AnalysisModule 구현체 작성
Step 2. requires/produces 선언 → Orchestrator가 실행 순서 자동 결정
Step 3. LLM 모듈이면 prompts/ 에 PromptTemplate 추가
Step 4. 끝 — Registry가 자동 발견, 결과가 TickerAnalysis에 병합
```

---

## 비용 제약 원칙

```
목표: < $50/month

- LLM 신규 호출 추가 시 반드시 배치로 묶기
- 무료 데이터 소스 우선 (yfinance, SEC EDGAR)
- 유료 API (Finnhub, Polygon) 는 fallback 에만 사용
- 비용 모니터링: GET /api/analytics/cost 로 확인
- 교차 실행 캐시로 불필요한 API 재호출 제거
```

---

## 의존성 맵

```
Phase 1-0 (수집 아키텍처)
  ├─ 1-1 (병렬 수집)     ← Orchestrator 필요
  ├─ 1-2 (섹터 ETF)     ← Provider 인터페이스 필요
  ├─ 1-3 (옵션 강화)     ← 교차 실행 캐시 필요
  ├─ 1-5 (Insider 통합)  ← Provider fallback chain 필요
  └─ 1-6 (확장 가이드)   ← Registry 완료 후 문서화

Phase 1 (데이터)
  ├─ Phase 2-2 (등급화)   ← 1-2 섹터 RS 필요
  ├─ Phase 2-3 (촉매분석) ← 1-4 실적패턴 필요
  └─ Phase 4-2 (peer)     ← 1-2 섹터 ETF 필요

Phase 1-4 (실적패턴)      ← 독립적, 아키텍처 리팩토링 없이도 가능

Phase 2 (시그널)
  └─ Phase 4-5 (인사이트) ← 2-1 자동화 완료 후 데이터 충분해야 의미 있음

Phase 3 (UX)              ← 독립적, 언제든 진행 가능

Phase 4-0 (분석 아키텍처)
  ├─ 4-1 (포트폴리오 리스크) ← AnalysisModule 인터페이스 필요
  ├─ 4-2 (peer 비교)        ← ModuleRegistry + Phase 1-2 섹터 ETF 필요
  ├─ 4-3 (멀티모델 합의)    ← PromptTemplate 시스템 + DecisionFactor 플러그인 필요
  ├─ 4-4 (Chat 전환)        ← AnalysisOrchestrator (모듈 결과 재사용)
  ├─ 4-5 (주간 인사이트)    ← AnalysisModule + Phase 2-1 자동화
  ├─ 4-6 (품질 검증)        ← PromptTemplate 스키마 검증
  └─ 4-7 (확장 가이드)      ← Registry 완료 후 문서화

Phase 4-0d (DecisionFactor 플러그인)
  └─ 4-0e (레짐 의존 가중치) ← Scorer 자동 정규화 필요

Phase 4-1 (리스크 모듈)
  └─ 4-5 (주간 인사이트)    ← 리스크 데이터 → 섹션 6 포트폴리오 제안

Phase 4-2 (peer 비교)
  └─ 4-4 (Chat)             ← peer 비교 응답 카드
```

---

## 신규 파일 목록

### Phase 1 — 수집 레이어

```
src/collector/
  ├─ base.py                         # DataProvider ABC
  ├─ registry.py                     # ProviderRegistry 자동 발견
  ├─ orchestrator.py                 # 병렬 수집 + fallback 병합
  ├─ rate_limiter.py                 # TokenBucketLimiter
  ├─ cache.py                        # SQLite 교차 실행 캐시
  └─ providers/
      ├─ __init__.py
      ├─ yfinance_provider.py        # price.py에서 분리
      ├─ alphavantage_provider.py
      ├─ fmp_provider.py
      ├─ finnhub_provider.py
      ├─ polygon_provider.py
      ├─ sec_provider.py
      ├─ stooq_provider.py
      ├─ insider_provider.py         # FMP + Form4 통합
      └─ sector_etf_provider.py      # 신규

src/utils/
  └─ earnings_pattern.py             # 실적 패턴 분류 (수식)

config/
  └─ providers.yaml                  # provider별 rate·priority 설정
```

### Phase 4 — 분석 레이어

```
src/analyzer/
  ├─ base.py                         # AnalysisModule ABC
  ├─ registry.py                     # ModuleRegistry (DAG 토폴로지 정렬)
  ├─ orchestrator.py                 # AnalysisOrchestrator (배치 + 병합)
  ├─ validator.py                    # LLM 응답 검증기 (환각 감지)
  ├─ ensemble.py                     # 멀티 모델 합의 엔진
  ├─ ab_test.py                      # A/B 테스트 프레임워크
  ├─ peer_selector.py                # 자동 Peer 선정 엔진
  ├─ prompts/
  │   ├─ base.py                     # PromptTemplate ABC
  │   ├─ research_v1.py              # 현재 프롬프트 (호환)
  │   └─ research_v2.py              # 개선 프롬프트 (A/B 테스트)
  └─ modules/
      ├─ __init__.py
      ├─ valuation_module.py         # 밸류에이션 (수식, LLM 불필요)
      ├─ trade_frame_module.py       # 진입/손절/목표 (수식)
      ├─ news_analysis_module.py     # 뉴스 톤 + 촉매 분류 (LLM)
      ├─ research_narrative_module.py # 핵심 서사 (LLM)
      ├─ risk_assessment_module.py   # 리스크 식별 (LLM)
      ├─ signal_takeaway_module.py   # 시그널 방향 (LLM)
      ├─ portfolio_risk_module.py    # 포트폴리오 리스크 (수식)
      ├─ peer_comparison_module.py   # Peer 퍼센타일 랭킹
      ├─ weekly_insight_module.py    # 주간 보고서 (LLM)
      └─ weekly_factor_attribution.py # 팩터 기여도 (수식)

src/decision/
  ├─ base.py                         # DecisionFactor ABC + FactorScore
  ├─ scorer.py                       # ConvictionScorer (자동 정규화)
  └─ factors/
      ├─ __init__.py
      ├─ valuation_factor.py
      ├─ momentum_factor.py
      ├─ catalyst_factor.py
      ├─ signal_record_factor.py
      ├─ news_tone_factor.py
      ├─ regime_factor.py
      ├─ earnings_factor.py
      ├─ fundamentals_factor.py
      ├─ portfolio_risk_factor.py    # 신규: 섹터 집중 감점
      ├─ peer_rank_factor.py         # 신규: value-momentum 스위트스팟
      └─ options_skew_factor.py      # 신규: PCR 기반 센티먼트

src/chat/
  ├─ context_assembler.py            # 의도별 컨텍스트 자동 조합
  └─ session.py                      # 대화 이력 (SQLite)

output/data/
  ├─ analysis_quality.json           # 환각 비율, 스키마 위반 메트릭
  ├─ ab_test_results.json            # 프롬프트 A/B 테스트 결과
  └─ chat_sessions.sqlite            # 대화 세션 저장
```

---

## 비고

- **Non-Goals:** 실시간 시스템, 자동매매, 복잡한 인프라
- **완료 기준:** 파이프라인 end-to-end 정상 실행 / 아키텍처 레이어(collect→analyze→output) 유지 / 비용 동결

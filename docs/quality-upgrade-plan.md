# 주식 리서치 품질 향상 플랜

> **예산**: $40/월 | **최대 종목 수**: 40개 | **현재 모델**: gpt-5.4 (standard)

---

## 1. 현황 진단

### 핵심 문제
이미 코딩된 **4개의 신규 수집기가 파이프라인에 연결되지 않은 채 방치**되어 있다.  
`CollectedTickerData`에 6개 필드가 정의되어 있으나 매번 **빈 값**으로 LLM에 전달된다.

| 수집기 | 파일 | 상태 | 제공 데이터 |
|---|---|---|---|
| Finnhub | `src/collector/finnhub.py` | ❌ 미연결 | 애널리스트 추천 추세 |
| FMP | `src/collector/fmp.py` | ❌ 미연결 | EPS 리비전, 내부자 거래, 기관 변동, 어닝 서프라이즈 |
| Polygon.io | `src/collector/polygon_options.py` | ❌ 미연결 | 옵션 플로우, 스마트머니 시그널 |
| SEC Form 4 | `src/collector/sec_form4.py` | ❌ 미연결 | 내부자 거래 (무료 폴백) |

### 항상 비어있는 필드 (`src/types.py` → `CollectedTickerData`)

```
analyst_estimate_revisions   # FMP: EPS 상향/하향 방향 및 변화율
insider_transactions         # FMP/SEC: 임원 매수·매도 내역
institutional_changes        # FMP: 기관투자자 비중 변동
fmp_earnings_surprises       # FMP: 최근 8분기 어닝 비트/미스 이력
options_flow                 # Polygon: PCR, 이상 옵션 거래량, 스마트머니
recommendation_trends        # Finnhub: 매수/중립/매도 추세 변화
```

---

## 2. API 용량 계산 (40종목 기준, 1일 1회 실행)

| API | 호출수/실행 | Rate Limit | 실제 소요 시간 | 판정 |
|---|---|---|---|---|
| **FMP Starter** | 40종목 × 4 엔드포인트 = **160 calls** | 250 calls/일 | ~80초 (0.5초 딜레이) | ✅ 64% 소진, 2회 실행도 가능 |
| **Polygon.io Starter** | 40종목 × 1 call = **40 calls** | **5 calls/min** ⚠️ | **~8분** (12초 간격 필요) | ✅ 1회/일이면 OK |
| **Finnhub** (무료) | 40종목 × 1 call = **40 calls** | 60 calls/min | ~8초 (0.2초 딜레이) | ✅ 여유 |
| **SEC Form 4** | 40 calls (폴백 시) | 무제한 공개 API | — | ✅ 여유 |

> **⚠️ Polygon.io 중요**: Starter 플랜은 **5 calls/min** (12초 간격 필수).  
> 현재 코드 `_REQUEST_DELAY = 1.2`초는 **rate limit 초과 발생** → Step 1 구현 시 **`12.0`으로 반드시 수정**.  
> 수정 후 40종목 처리에 약 8분 소요, 1일 1회 실행 예산 내 문제 없음.

> **FMP**: 40종목 × 4 엔드포인트 = 160 calls/run (250/일의 64%).  
> 하루 2회 실행 시 320 calls → Starter 초과 → $49 플랜 필요.  
> 1일 1회라면 여유 90 calls 있음.

### LLM 비용 추정 (o3-mini, deep profile)

| 항목 | 계산 | 결과 |
|---|---|---|
| 안전 토큰 예산 | (200,000 × 0.8) − 100,000 | **60,000 tokens/배치** |
| 종목당 토큰 | 기존 3,500 + 신규 필드 ~1,000 | ~4,500 tokens |
| 배치당 종목 수 | 60,000 ÷ 4,500 | ~13종목 |
| 40종목 배치 수 | 40 ÷ 13 | **3~4 배치/실행** |
| 일 비용 | 4배치 × (60k×$1.10 + 8k×$4.40) / 1M | ~$0.55/일 |
| **월 비용** | $0.55 × 22 거래일 | **~$12/월** |

---

## 3. 월 예산 배분

| 항목 | 월 비용 | 비고 |
|---|---|---|
| FMP Starter API | **$19** | 250 calls/일, 40종목×4 = 160 calls/run (64% 소진) |
| Polygon.io Starter | **$9** | 5 calls/min, 40종목 처리 ~8분 |
| o3-mini LLM (deep) | **~$12** | 40종목 기준 / 8~20종목이면 ~$8 |
| Finnhub | **$0** | 무료 (60 calls/min) |
| SEC Form 4 | **$0** | 공개 엔드포인트 |
| **합계** | **~$40** | 40종목 기준 예산 딱 맞음 |

> 8~20종목 운영 시: $19 + $9 + $8 = **$36/월** (여유 $4)  
> 종목 수를 줄이면 Polygon 처리 시간도 비례해 감소 (8종목 ≈ 96초).

---

## 4. 구현 계획

---

### Step 1 — 수집기 연결

**파일**: `src/collector/price.py`  
**위치**: `_collect_single_ticker()` 함수 → `return CollectedTickerData(...)` 직전 (line 320)

> **참고**: `price.py`에는 `CollectedTickerData()` 생성자가 2곳 있음.
> - Line 320: `_collect_single_ticker()` 정상 경로 → **6개 필드 추가 필요**
> - Line 371: `_fallback_market_data()` 폴백 경로 → **수정 불필요** (`src/types.py`의 `field(default_factory=...)` 기본값이 자동으로 빈 값 할당)

#### 1-0. (필수 선행) Polygon.io rate limit 버그 수정

**파일**: `src/collector/polygon_options.py` line 20

```python
# 현재 (버그)
_REQUEST_DELAY = 1.2  # Polygon Starter: 5 calls/min

# 수정 후
_REQUEST_DELAY = 12.0  # Polygon Starter: 5 calls/min (12초 간격 필수)
```

> Polygon Starter는 5 calls/min 한도. 기존 1.2초는 50 calls/min 시도 → rate limit 초과.

#### 1-1. 파일 상단 import 추가 (line 16 이후)

```python
from src.collector.finnhub import is_finnhub_ready, collect_finnhub_recommendations
from src.collector.fmp import (
    is_fmp_ready,
    collect_fmp_analyst_estimates,
    collect_fmp_insider_trading,
    collect_fmp_institutional_holders,
    collect_fmp_earnings_surprises,
)
from src.collector.polygon_options import is_polygon_ready, collect_options_flow
from src.collector.sec_form4 import collect_insider_transactions
```

#### 1-2. 수집 블록 추가 (6개 필드, 각각 독립 try/except)

```python
# ── Finnhub: 애널리스트 추천 추세 (무료) ────────────────────────────────
recommendation_trends: list[dict[str, str]] = []
if is_finnhub_ready():
    try:
        recommendation_trends = collect_finnhub_recommendations(item.ticker)
    except Exception:
        pass

# ── 내부자 거래: FMP 우선 → SEC Form 4 폴백 ─────────────────────────────
insider_transactions: list[dict[str, str]] = []
if is_fmp_ready():
    try:
        insider_transactions = collect_fmp_insider_trading(item.ticker, run_date)
    except Exception:
        pass
if not insider_transactions and item.cik:
    try:
        insider_transactions = collect_insider_transactions(item.cik, run_date)
    except Exception:
        pass

# ── FMP: EPS 추정 리비전 ────────────────────────────────────────────────
analyst_estimate_revisions: dict[str, str] = {}
if is_fmp_ready():
    try:
        analyst_estimate_revisions = collect_fmp_analyst_estimates(item.ticker, run_date)
    except Exception:
        pass

# ── FMP: 기관투자자 비중 변동 ───────────────────────────────────────────
institutional_changes: dict[str, str] = {}
if is_fmp_ready():
    try:
        institutional_changes = collect_fmp_institutional_holders(item.ticker)
    except Exception:
        pass

# ── FMP: 어닝 서프라이즈 이력 ───────────────────────────────────────────
fmp_earnings_surprises: list[dict[str, str]] = []
if is_fmp_ready():
    try:
        fmp_earnings_surprises = collect_fmp_earnings_surprises(item.ticker)
    except Exception:
        pass

# ── Polygon.io: 옵션 플로우 ─────────────────────────────────────────────
options_flow: dict[str, str] = {}
if is_polygon_ready():
    try:
        options_flow = collect_options_flow(item.ticker, run_date)
    except Exception:
        pass
```

#### 1-3. `CollectedTickerData()` 생성자에 6개 필드 추가

```python
return CollectedTickerData(
    # ... 기존 필드 그대로 유지 ...
    analyst_estimate_revisions = analyst_estimate_revisions,
    insider_transactions       = insider_transactions,
    institutional_changes      = institutional_changes,
    fmp_earnings_surprises     = fmp_earnings_surprises,
    options_flow               = options_flow,
    recommendation_trends      = recommendation_trends,
)
```

---

### Step 2 — LLM 모델 업그레이드

**파일**: `config/models.yaml`

```yaml
default_profile: deep   # standard(gpt-5.4) → deep(o3-mini)
```

> o3-mini 컨텍스트 200k → 안전 예산 60k/배치.  
> 기존 `_build_batches_for_analysis()`의 배치 분할 로직이 자동 처리 — 코드 변경 없음.

---

### Step 3 — 프롬프트 반영

**파일**: `src/analyzer/research_note.py`

#### 3-1. `_build_payload()` — 6개 필드 추가

`'options_summary': market.options_summary` 다음 줄에:

```python
'analyst_estimate_revisions': market.analyst_estimate_revisions,
'insider_transactions':       market.insider_transactions[:6],
'institutional_changes':      market.institutional_changes,
'fmp_earnings_surprises':     market.fmp_earnings_surprises[:4],
'options_flow':               market.options_flow,
'recommendation_trends':      market.recommendation_trends[:3],
```

#### 3-2. 렌더러 함수 4개 추가 (`_render_options_summary` 함수 다음)

```python
def _render_analyst_revisions(rev: dict) -> str:
    if not rev or not isinstance(rev, dict):
        return 'N/A'
    return (
        f"EPS revision {rev.get('revision_pct', 'N/A')} "
        f"({rev.get('direction', 'N/A')}) | current ${rev.get('current_eps', 'N/A')}"
    )


def _render_insider_transactions(txns: list) -> str:
    if not txns or not isinstance(txns, list):
        return 'N/A'
    parts = [
        f"{tx.get('title','?')} {tx.get('type','?')} {tx.get('value','?')} ({tx.get('date','')})"
        for tx in txns[:3]
        if isinstance(tx, dict)
    ]
    return '; '.join(parts) if parts else 'N/A'


def _render_options_flow(flow: dict) -> str:
    if not flow or not isinstance(flow, dict):
        return 'N/A'
    parts = []
    if pcr := flow.get('put_call_volume_ratio'):
        parts.append(f"PCR {pcr} ({flow.get('flow_sentiment', '')})")
    if unusual := flow.get('unusual_activity'):
        parts.append(f"unusual: {unusual}")
    if iv := flow.get('avg_iv'):
        parts.append(f"avg IV {iv}")
    return ' | '.join(parts) if parts else 'N/A'


def _render_recommendation_trends(trends: list) -> str:
    if not trends or not isinstance(trends, list):
        return 'N/A'
    t = trends[0]
    buys  = int(t.get('strong_buy', 0)) + int(t.get('buy', 0))
    sells = int(t.get('sell', 0))       + int(t.get('strong_sell', 0))
    return (
        f"{t.get('period', '')} {t.get('consensus', 'N/A')} "
        f"({t.get('trend', '')}): {buys}B/{t.get('hold','0')}H/{sells}S"
    )
```

#### 3-3. `_build_ticker_context()` — compact 블록 4줄 추가

`[Earnings History]` 섹션 바로 다음에:

```python
f"[Analyst Revisions]  {_render_analyst_revisions(analysis_input.get('analyst_estimate_revisions', {}))}\n"
f"[Insider Activity]   {_render_insider_transactions(analysis_input.get('insider_transactions', []))}\n"
f"[Options Flow]       {_render_options_flow(analysis_input.get('options_flow', {}))}\n"
f"[Recommendation]     {_render_recommendation_trends(analysis_input.get('recommendation_trends', []))}\n"
```

**출력 예시:**
```
[Analyst Revisions]  EPS revision +3.2% (up) | current $6.80
[Insider Activity]   CEO buy $1.2M (2026-03-15); CFO sale $400K (2026-02-20)
[Options Flow]       PCR 0.42 (bullish) | unusual: CALL vol=8500 | avg IV 34.2%
[Recommendation]     2026-03 Strong Buy (upgrading): 14B/4H/1S
```

#### 3-4. `_build_user_prompt()` — 신규 시그널 해석 지침 추가

`trade_frame` 설명 다음 블록에 추가:

```
## New Signal Integration (신규 시그널 활용 지침)

analyst_estimate_revisions
  - direction="up"   → financial_highlights에 "EPS 컨센서스 +X% 상향 조정 (vs 30일 전)" 포함
  - direction="down" → risks_or_watchpoints에 하향 조정 위험 명시

insider_transactions
  - C-suite buy (30일 이내) → bullish 구조적 시그널; 내부자 매수가 = stop_loss 기준점으로 활용
  - 대규모 매도 (>$1M, 복수 임원 동시) → risks_or_watchpoints에 언급
  - 옵션 행사(exercise)는 bearish 시그널로 취급하지 않음

options_flow
  - PCR < 0.5 → bullish 포지셔닝; signal_or_takeaway [Options] 항목에 반영
  - unusual call (vol > 5× OI) → 스마트머니 매수 가능성; 단, 가격 확인 조건 명시
  - 높은 avg_iv → stop 범위를 ATR 기반보다 넓게 허용

recommendation_trends
  - trend="upgrading"   → financial_highlights에 컨센서스 이동 명시 (기간 + 건수 포함)
  - trend="downgrading" → 모멘텀과 상충 시 risks_or_watchpoints에 언급

fmp_earnings_surprises
  - quarterly_financials와 동시에 있으면 fmp_earnings_surprises 우선 사용 (8분기 제공)
```

---

### Step 4 — Deep Dive 에이전트 라우팅 (선택)

**파일**: `src/pipeline.py`  
고신뢰도 종목을 자동 감지하여 별도 심층 분석(o3-mini) 실행.

#### 컨빅션 스코어 함수 추가

```python
def _score_conviction(data: CollectedTickerData) -> int:
    """
    0~3점 신뢰도 점수.
    2점 이상이면 deep 프로필로 별도 분석 실행.
    """
    score = 0
    flow = data.options_flow or {}

    # 시그널 1: 옵션 스마트머니
    if flow.get('flow_sentiment') == 'bullish' and flow.get('unusual_activity'):
        score += 1

    # 시그널 2: C-suite 내부자 매수
    if any(tx.get('type') == 'buy' for tx in (data.insider_transactions or [])):
        score += 1

    # 시그널 3: EPS 추정 상향 조정
    if (data.analyst_estimate_revisions or {}).get('direction') == 'up':
        score += 1

    return score
```

#### 파이프라인 분기 추가 (`analyze_tickers` 호출 직전, line 42)

```python
# 컨빅션 스코어 2점 이상 → deep 프로필로 별도 심층 분석
high_conviction = [
    item for item in watchlist
    if _score_conviction(collected[item.ticker]) >= 2
]
normal_items = [item for item in watchlist if item not in high_conviction]

# 일반 종목: 기존 배치 처리
analyses = analyze_tickers(
    normal_items, collected, news_map, effective_date,
    macro_context=macro_context,
    signal_history_map=signal_history_map,
)

# 고신뢰도 종목: deep 프로필 별도 분석
if high_conviction:
    deep_analyses = analyze_tickers(
        high_conviction, collected, news_map, effective_date,
        macro_context=macro_context,
        signal_history_map=signal_history_map,
        model_profile_name="deep",          # analyze_tickers에 파라미터 추가 필요
    )
    analyses = analyses + deep_analyses
```

> `analyze_tickers()`에 `model_profile_name: str | None = None` 파라미터 추가 후  
> `_analyze_with_openai()`까지 전달하여 env var 변경 없이 모델 오버라이드.

---

## 5. 수정 파일 요약

| 파일 | 변경 내용 |
|---|---|
| `src/collector/polygon_options.py` | **`_REQUEST_DELAY = 12.0` 버그 수정 (필수)** |
| `src/collector/price.py` | import 4개 추가, 수집 블록 6개, `CollectedTickerData()` 필드 6개 (line 320만) |
| `src/analyzer/research_note.py` | payload 6개 필드, 렌더러 함수 4개, compact context 4줄, 프롬프트 지침 추가 |
| `config/models.yaml` | `default_profile: deep` |
| `src/pipeline.py` | (선택) `_score_conviction()` + 분기 라우팅 |

---

## 6. 검증 순서

| 단계 | 방법 | 기대 결과 |
|---|---|---|
| 1 | `ENABLE_EXTERNAL_FETCH=false` dry run | 6개 필드 빈값으로 파이프라인 정상 완료 |
| 2 | Finnhub 키만 설정 후 단일 종목 실행 | `[Recommendation]` 실제 값 출력 확인 |
| 3 | FMP 키 설정 후 AAPL 실행 | `[Analyst Revisions]`, `[Insider Activity]` 실제 값 확인 |
| 4 | Polygon 키 설정 후 실행 | `[Options Flow]` PCR 실제 값 확인 + **429 오류 없는지 확인** |
| 5 | 40종목 전체 실행 시간 측정 | Polygon 수집이 ~8분에 완료되는지 확인 (12초 × 40) |
| 6 | 첫 주 운영 후 이벤트 로그 확인 | `estimated_cost_usd` < $0.60/일 유지 |

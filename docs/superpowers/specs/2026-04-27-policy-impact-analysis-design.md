# Policy/Regulation Impact Analysis — Design Spec

**Date:** 2026-04-27
**Status:** Draft for review
**Owner:** pkrich daily research pipeline

## 1. Goal

정책·규제 뉴스(금리, 반독점, 수출 규제, 보조금, 관세, IRA, CHIPS Act, FDA, 국방 예산, 에너지 정책)가 watchlist 종목군에 미치는 영향을 매일 1회 자동 해석하여:

1. 종목별 `policy_tailwind_score` (-1.0 ~ +1.0) 산출 → decision layer의 9번째 팩터로 conviction에 반영
2. 이벤트 단위·종목 단위 양쪽 뷰를 갖는 `policy_impact.json` 산출물 → 신규 `/policy` 페이지에서 read-only 노출

핵심 비기능 요구사항: **정확도**(소스 그라운딩, 회귀 테스트셋 정확도 ≥ 80%)와 **컨텍스트 길이 견고성**(watchlist 200개·이벤트 20건 동시 처리 가능).

## 2. Architecture (layer placement)

기존 `collect → analyze → decide → store → output` 레이어 순서를 따른다.

```
src/collector/policy_events.py    (NEW, 외부 호출 — OpenAI web_search)
   ↓ list[PolicyEvent]
src/analyzer/policy_impact.py     (NEW, LLM 매핑 — pure function of inputs)
   ↓ PolicyImpactReport
src/decision/decision_layer.py    (MODIFIED — factor 9 추가)
   ↓ TickerDecision (conviction 반영)
src/output/policy_json.py         (NEW — policy_impact.json 산출)
src/output/json_export.py         (MODIFIED — dashboard.json에 정책 요약 주입)
web/pages/PolicyImpact.tsx        (NEW — read-only)
```

`_run_sector_scan`처럼 정책 분석 실패가 메인 파이프라인을 죽이지 않도록 **isolated try/except** 로 감싼다 (`graceful-degradation.md` 준수).

## 3. Data Contracts (frozen dataclasses, `src/types.py`)

```python
@dataclass(frozen=True)
class PolicyEvent:
    id: str                      # sha1(headline + source_url + published_at)[:12]
    category: str                # one of POLICY_CATEGORIES
    headline: str
    summary: str                 # ≤ 120 tokens, normalized by Stage 1
    raw_excerpt: str             # original web_search snippet (for audit)
    source_url: str              # required, non-empty
    source_domain: str
    published_at: str            # ISO8601, must be within last 48h at scan time
    confidence: float            # 0.0–1.0 from Stage 1

@dataclass(frozen=True)
class TickerImpact:
    ticker: str
    direction: str               # "positive" | "negative" | "neutral"
    strength: str                # "direct" | "indirect" | "neutral"
    score: float                 # signed, [-1.0, +1.0]
    confidence: float            # 0.0–1.0
    rationale: str               # ≤ 200 chars

@dataclass(frozen=True)
class PolicyImpactReport:
    date: str
    events: list[PolicyEvent]
    impacts_by_event: dict[str, list[TickerImpact]]   # event_id -> impacts
    impacts_by_ticker: dict[str, list[TickerImpact]]  # ticker -> impacts
    tailwind_scores: dict[str, float]                 # ticker -> [-1, +1] aggregate
    metadata: dict                                    # tokens, model, timings
```

`POLICY_CATEGORIES = ["interest_rate", "antitrust", "export_control", "subsidy", "tariff", "ira", "chips_act", "fda", "defense_budget", "energy_policy", "other"]`

## 4. Pipeline (two-stage LLM)

### Stage 1 — Event extraction (`src/collector/policy_events.py`)

- **Input:** none (date = today)
- **Tool:** OpenAI Responses API with `web_search` tool, model = `OPENAI_MODEL_PROFILE=deep` (override-able via `policy.model_profile` in `models.yaml`)
- **Prompt:** 지난 24시간 미국·글로벌 정책/규제 이벤트를 10개 카테고리(위 목록)에서 모두 스캔. 각 이벤트당 출처 URL 필수.
- **Structured Output (JSON Schema):** `list[PolicyEvent]` (raw_excerpt 포함)
- **Filters (post-call):**
  - `source_url` 빈 값 → 폐기
  - `published_at` 24h 초과 → 폐기
  - 도메인 화이트리스트(`config/policy_sources.yaml`의 `trusted_domains`) 매치 시 confidence +0.2, 블로그/SNS는 −0.3
  - 동일 `id` 중복 제거 (해시 기준)
- **캐시:** 어제 본 이벤트 ID는 `output/data/policy_events_cache.json`에 7일치 보관 → Stage 2 재호출 회피

### Stage 2 — Impact mapping (`src/analyzer/policy_impact.py`)

- **Input:** `list[PolicyEvent]`, watchlist with ticker context
- **Ticker context** (`config/ticker_policy_context.yaml`, 한 종목당 ≤ 80 토큰):
  ```yaml
  NVDA:
    sector: semiconductor
    business: "AI accelerator GPUs; data center dominant"
    exposure: [export_control_china, antitrust_ftc]
    china_revenue_pct: 17
  ```
  초기 빌드는 LLM이 1회성으로 채우고 사람이 검수. 신규 종목 추가 시 빈 항목은 LLM이 보강.
- **사전 필터링 (token reduction):** 이벤트 카테고리 → 관련 섹터 매핑 (`config/policy_sources.yaml`의 `category_to_sectors`) → 해당 섹터 종목만 후보군에 포함. 후보군이 50개 초과 시 25개씩 청크 분할, 각 청크별 호출 후 결과 머지.
- **Structured Output:** `dict[event_id, list[TickerImpact]]`
- **Score normalization:**
  - `strength=direct`: |score| ∈ [0.7, 1.0]
  - `strength=indirect`: |score| ∈ [0.3, 0.5]
  - `strength=neutral`: score = 0
  - 부호는 `direction`에서 결정 (positive=+, negative=−)
- **Aggregate `tailwind_scores`:**
  ```
  raw = sum(impact.score * impact.confidence
            for impact in impacts_by_ticker[t]
            if impact.confidence >= 0.5)
  tailwind_scores[t] = clip(raw, -1.0, +1.0)
  ```
  confidence < 0.5 인 임팩트는 집계 제외(독립 페이지엔 "low confidence" 라벨로 표시).

### Stage 3 — Decision integration (`src/decision/decision_layer.py`)

- 9번째 팩터 `policy_tailwind` 추가
- `config/decision_weights.yaml`에 regime별 가중치 신설:
  ```yaml
  risk_on:    { ..., policy_tailwind: 0.05 }
  neutral:    { ..., policy_tailwind: 0.08 }
  risk_off:   { ..., policy_tailwind: 0.10 }
  ```
  보수적 시작값. `tune_weights.py` 그리드 서치에 자동 포함.
- 누락 처리(graceful degradation): `tailwind_scores`에 종목 없음 → 팩터 가중치 재정규화(다른 8팩터 합이 1이 되도록).

## 5. Accuracy Guards

1. **소스 그라운딩 강제** — `source_url` 필수, 도메인 화이트리스트 가산점 / 블로그·SNS 감점.
2. **2단계 분리 호출** — 추출과 매핑을 분리. 각 단계 Structured Outputs로 형식 오류 0%.
3. **종목 컨텍스트 사전 빌드** — `ticker_policy_context.yaml`로 LLM 추측 제거.
4. **Confidence + rationale 의무화** — confidence < 0.5는 score 집계 제외.
5. **회귀 테스트셋** — `tests/fixtures/policy_events_golden.json`에 과거 명확 케이스 10–20개(예: 2022 CHIPS Act → INTC/TSM 수혜, 2023 export control → NVDA 직접 리스크). 매 배포 전 Stage 2를 fixture로 재실행, top-3 영향 종목 정확도 ≥ 80% 미달 시 빌드 실패.

## 6. Context-Length Guards

1. **Watchlist 청크 분할 + 사전 필터링** — 카테고리 → 섹터 → 종목으로 후보군 축소. 50개 초과 시 25개씩 청크.
2. **종목 컨텍스트 압축** — LLM 입력은 종목당 ≤ 80 토큰. 사람 가독용 풀버전과 분리 저장.
3. **이벤트 본문 요약** — Stage 1 직후 ≤ 120 토큰으로 정규화. 원본은 `raw_excerpt`로 보관, Stage 2 프롬프트에 미포함.
4. **토큰 예산 가드레일** — `tiktoken`으로 입력 카운트. 100K 초과 시 자동 청크, 200K 초과 시 에러+Slack. `pipeline_logging.py`에 `policy.tokens.stage1`, `policy.tokens.stage2` 메트릭 기록.
5. **그레이스풀 디그라데이션** — 청크 일부 실패 시 성공분만 반영, 실패 종목은 `tailwind_score=null`로 누락 처리.
6. **캐시 + 증분 갱신** — 이벤트 ID 해시 캐시(7일). 어제 매핑한 이벤트는 LLM 재호출 안 함, watchlist 변경분만 재매핑.

## 7. Outputs

### `output/data/policy_impact.json`
```json
{
  "date": "2026-04-27",
  "model": "deep",
  "events": [ /* PolicyEvent[] */ ],
  "impacts_by_event": { "evt_a1b2c3": [ /* TickerImpact[] */ ] },
  "impacts_by_ticker": { "NVDA": [ /* TickerImpact[] */ ] },
  "tailwind_scores": { "NVDA": -0.62, "INTC": +0.31 },
  "metadata": { "tokens_in": 12345, "tokens_out": 6789, "duration_ms": 18230 }
}
```

### `dashboard.json` 보강
- 종목별 `policy_tailwind` 필드 + top 1–2 driver event 헤드라인 인라인.
- 사이즈 압박 시 헤드라인은 `policy_impact.json`만 두고 dashboard엔 score만.

### Markdown
- `output/daily/YYYY-MM-DD.md`에 "Policy Drivers" 섹션 추가 (top 5 events + 영향 종목).

### Web (`/policy`)
- 이벤트 리스트 + 카테고리 필터 + 종목 클릭 시 상세 (rationale 포함).
- 종목 상세 페이지(`TickerDetail.tsx`)에 "Policy Exposure" 카드 추가.

## 8. Config Additions

- `config/policy_sources.yaml` (NEW) — `trusted_domains`, `category_to_sectors` 매핑.
- `config/ticker_policy_context.yaml` (NEW) — 종목별 압축 컨텍스트.
- `config/decision_weights.yaml` (MODIFIED) — `policy_tailwind` 가중치.
- `config/models.yaml` (MODIFIED) — `policy.model_profile` 키.

## 9. Testing

- **Unit:** Stage 1 필터(URL/24h/도메인 가산점), Stage 2 score normalization, aggregate clipping, decision factor 재정규화.
- **Integration:** Mock OpenAI client으로 e2e — 이벤트 → 임팩트 → conviction 반영 전 과정.
- **Regression:** `tests/test_policy_golden.py` — golden fixture, 정확도 ≥ 80% 게이트.
- **Graceful degradation:** Stage 1/2 실패 시 메인 파이프라인 통과, `tailwind_score=null` 처리.

## 10. Operational Notes

- 일 1회 배치, GitHub Actions에서 실행. 추가 비용 추정 ≤ $0.10/일 (deep 모델 2~3회 호출).
- `pipeline_logging.py`에 `policy.stage1.events_count`, `policy.stage2.tickers_scored`, `policy.cache_hits`, `policy.tokens.*` 기록.
- Slack 알림: 200K 토큰 초과 또는 회귀 정확도 < 80% 시.

## 11. Out of Scope (for v1)

- 실시간(스트리밍) 정책 모니터링.
- 한국·중국·EU 자국 정책 (미국·글로벌 우선, 추후 확장).
- 정책 이벤트의 시계열 영향 추적(이번 산출물은 일 단위 스냅샷).
- 옵션·채권 등 비주식 자산 영향.

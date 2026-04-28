# LLM Quality Audit (One-Shot Diagnostic) Design

Date: 2026-04-28

## Summary

이 프로젝트의 `analyze` 단계에서 사용되는 모든 LLM 기능에 대해 일회성 진단 보고서를 산출하는 새로운 평가 모듈(`src/eval/`)을 추가한다. 14개 검사 차원(입력 일관성 4, 출력 정확성 5, 패스 간 결정성 3, 운영 신호 2)을 한 번에 측정해 어디가 흔들리고 있는지를 식별하고, 우선순위가 매겨진 개선 백로그를 제공한다.

산출물은 사람용 마크다운(`docs/reports/llm-audit-YYYY-MM-DD.md`)과 기계용 JSON(`output/data/llm_audit/YYYY-MM-DD.json`) 두 개다. 파이프라인의 입력 데이터·출력·로그·시그널 트래커는 read-only로만 접근하며, 부수효과는 위 두 산출 파일과 `D1` 검사에서 발생하는 LLM 재호출 비용뿐이다.

## Goals

- `src/analyzer/` 5개 영역(`research_note`, `committee`, `committee_role`, `macro_narrative`, `modules/*`)에 대해 14개 차원 진단을 한 명령으로 산출.
- 입력 일관성·출력 정확성·결정성·운영 신호를 한 보고서에서 비교 가능하게 한다.
- 각 검사를 독립 모듈로 격리해 부분 실행과 비용 격리를 보장한다.
- D1(의미적 드리프트)의 LLM 재실행 비용을 캡과 dry-run으로 통제한다.
- 모든 발견(finding)을 재현 가능한 좌표(`ticker, date, module, jsonpath`)로 기록한다.
- 일회성 진단이지만, 동일 모듈 구조를 향후 CI 게이트(phase 2)나 일일 모니터링(phase 3)으로 그대로 승격할 수 있도록 한다.

## Non-Goals

- 파이프라인의 collect/analyze/decide/store/output 어떤 단계도 변경하지 않는다.
- LLM 출력 스키마, `config/models.yaml`, 워치리스트 등 운영 설정을 수정하지 않는다.
- CI 자동 실행, 일일 모니터링 대시보드, 실시간 알림은 본 phase의 범위가 아니다.
- 외부 데이터 수집(`ENABLE_EXTERNAL_FETCH`)을 활성화하지 않는다 — audit는 read-only.
- 자동 코드 수정·자동 PR 생성은 하지 않는다. recommendation은 사람이 검토한다.

## Approved Direction

사용자가 선택한 사항:

- 초점: 전체(D) — 입력 일관성 + 출력 정확성 + 결정성 + 측정 루프.
- 결과물: A — 일회성 진단 보고서.
- 검사 차원: 모두(ALL 14) — 별도 우선순위 지정 없음.
- 재실행 정책: R-replay — 대표 ticker 5개 × 3회.
- 분석 윈도우: W-14 — 최근 14일.
- 아키텍처: C안 — 플러그형 체크 모듈 + 오케스트레이터.

## Architecture

신규 코드는 모두 `src/eval/` 하위에 추가한다. 파이프라인 코드(`src/collector/`, `src/analyzer/`, `src/decision/`, `src/output/`, `src/utils/`)는 변경하지 않는다.

```
src/eval/
├── __init__.py
├── runner.py              # CLI + 오케스트레이션
├── config.py              # 임계치, 샘플링, 체크 레지스트리
├── data_sources.py        # output/data + logs/pipeline 로더 (read-only)
├── replay.py              # D1 재실행 (llm_runtime 재사용, 비용 가드)
├── report.py              # 마크다운 + JSON 렌더러
└── checks/
    ├── base.py            # BaseCheck, CheckResult, Finding
    ├── i1_schema_stability.py
    ├── i2_missingness.py
    ├── i3_format_consistency.py
    ├── i4_input_size_drift.py
    ├── o1_schema_compliance.py
    ├── o2_numeric_grounding.py
    ├── o3_citation_integrity.py
    ├── o4_language_consistency.py
    ├── o5_contradiction.py
    ├── d1_semantic_drift.py
    ├── d2_committee_agreement.py
    ├── d3_signal_volatility.py
    ├── r1_pipeline_summary.py
    └── r2_retry_distribution.py

tests/eval/
├── test_runner.py
├── fixtures/              # 작은 합성 daily JSON·로그
└── checks/
    └── test_<id>.py × 14

docs/reports/
└── llm-audit-YYYY-MM-DD.md

output/data/llm_audit/
└── YYYY-MM-DD.json
```

`src/analyzer/modules/*.py`의 모듈식 패턴을 미러한다. `decide` 단계와 동일하게 입력은 read-only이며 부수효과가 없다.

## Execution Interface

```bash
python -m src.eval.runner                            # 기본: W-14, ALL 14 체크
python -m src.eval.runner --checks I1,O2             # 부분 실행
python -m src.eval.runner --window 7                 # 윈도우 변경
python -m src.eval.runner --skip-replay              # D1 비활성 (무료 모드)
python -m src.eval.runner --replay-tickers AAPL,MSFT # D1 대상 명시
python -m src.eval.runner --max-replay-cost-usd 1.0  # 비용 캡 (기본 1.0)
python -m src.eval.runner --dry-run                  # 비용 추정만
python -m src.eval.runner --suffix evening           # 동일 날짜 별도 산출
python -m src.eval.runner --check-links              # O3-(b) 링크 HEAD 활성
python -m src.eval.runner --yes                      # confirm 프롬프트 skip (CI용)
```

## Data Flow

### 입력 소스 (read-only)

| 소스 | 경로 | 용도 |
|------|------|------|
| 일일 티커 출력 | `output/data/tickers/<TICKER>/daily/<DATE>.json`, `latest.json` | I1~I4, O1~O5 |
| 파이프라인 로그 | `logs/pipeline/YYYY-MM-DD.jsonl`, `*.summary.json` | R1, R2, D2 |
| 위원회 raw 출력 | `logs/pipeline/*.jsonl` 안의 LLM 이벤트 | D2, D3, O5 |
| 시그널 트래커 | `output/data/signal_tracker.csv` | O5 보강 |
| 워치리스트 | `config/watchlist.yaml` | 샘플링 |
| 모델 설정 | `config/models.yaml`, `OPENAI_MODEL_PROFILE` | replay 정합성 |

### 출력 (write)

- `docs/reports/llm-audit-YYYY-MM-DD.md`
- `output/data/llm_audit/YYYY-MM-DD.json`

### 흐름

```
runner.py
  └─ data_sources.load_window(W=14)
       └─ AuditDataset (frozen dataclass)
            ├─ I1~I4, R1·R2 (순수 dict 분석)
            ├─ O1~O5 (스키마 + 정규식 + lex)
            ├─ D2·D3 (committee 로그 집계)
            └─ D1 replay (선택적, 비용 가드 통과 시)
       └─ List[CheckResult]
            └─ report.render() → md + json
```

### 데이터 모델

```python
@dataclass(frozen=True)
class AuditDataset:
    window_start: date
    window_end: date
    tickers: tuple[str, ...]
    daily: Mapping[Ticker, Mapping[date, dict]]
    logs: tuple[PipelineEvent, ...]
    summaries: Mapping[date, dict]
    model_profile: str

@dataclass(frozen=True)
class Finding:
    ticker: str | None
    date: date | None
    module: str | None
    jsonpath: str | None
    detail: Mapping[str, Any]

@dataclass(frozen=True)
class CheckResult:
    check_id: str
    severity: Literal["info", "warn", "fail", "pass"]
    pass_rate: float
    findings: tuple[Finding, ...]
    metrics: Mapping[str, float]
    recommendation: str | None
```

### 실패 격리

한 체크가 raise → runner가 `CheckResult(severity="fail", findings=[error trace])`로 기록 후 다음 체크 진행. D1 replay 실패 시에도 다른 13개 체크는 정상 산출된다.

## Check Specifications

각 체크의 임계치는 `src/eval/config.py`에 중앙화되며 보고서에도 함께 표기된다.

### Input Consistency (I)

**I1. Schema stability**
- 입력: 14일치 daily JSON
- 신호: 필드 셋의 일별 차집합, 타입 변동
- 임계치: 필드 누락 ≤2% pass / ≤10% warn / 초과 fail

**I2. Missingness pattern**
- 신호: 필드별 None/빈배열 비율 매트릭스
- 임계치: 결측 <30% pass / 30~60% warn / >60% fail (옵션·내부자 등 본질적 옵셔널 필드는 화이트리스트)

**I3. Format consistency**
- 신호: 동일 필드의 다중 포맷 (예: `published_at`이 ISO와 RFC822 혼재)
- 임계치: 포맷 종류 ≤1 pass / 2 warn / ≥3 fail
- 알려진 케이스: AAPL `news_references[*].published_at`에서 `2026-01-30`과 `Fri, 30 Jan 2026 08:00:00 GMT` 혼재 확인됨

**I4. Input size drift**
- 신호: ticker별 prompt token 수의 14일 변동계수(CV)
- 출처: `pipeline.summary.json`의 token usage
- 임계치: CV ≤0.20 pass / 0.40 warn / 초과 fail

### Output Accuracy (O)

**O1. JSON schema compliance**
- 신호: 각 모듈의 `response_schema`로 출력 재검증
- 임계치: 100% pass; 1건이라도 위반 시 fail

**O2. Numeric grounding**
- 신호: `summary` 텍스트에서 정규식으로 추출한 숫자가 동일 ticker의 collected 데이터와 ε=0.5% 허용오차로 매칭되는지
- 임계치: 매칭률 ≥95% pass / 85~95% warn / <85% fail
- 한계: 정규식 미스 시 false positive 가능 → 보고서 methodology에 명기

**O3. Citation integrity**
- 신호 (a): `key_news` 항목이 `news_references[*].title`에 존재(정확 일치 OR 토큰 유사도 ≥0.85)
- 신호 (b): `news_references[*].link` HTTP HEAD 200 비율 (옵션, `--check-links`로만 활성, 100건 샘플 캡)
- 임계치: (a) ≥98% pass; (b) ≥90% pass

**O4. Language consistency**
- 신호: ticker별 `summary`의 한국어 비율 표준편차, 영어 fallback 패턴 빈도
- 임계치: σ ≤0.15 pass / >0.30 fail

**O5. Contradiction detection**
- 신호: `summary`(어조 lex), `risk_assessment.severity`, `research_narrative.outlook`의 방향 일치
- 임계치: 3-way 합의 ≥85% pass / 70~85% warn / <70% fail

### Determinism (D) — replay 비용 발생

**D1. Semantic drift**
- 입력: 5 ticker × 3회 재실행 (워치리스트 상위 + 옵션 모듈 사용 + fallback 잦은 1개)
- 신호: 액션 라벨 일치율, summary embedding cosine 유사도(로컬 sentence-transformers), 인용 헤드라인 jaccard
- 임계치: action 일치 100% pass / 67% warn / <67% fail; embedding ≥0.90 pass / 0.80~0.90 warn
- 비용 가드: `--max-replay-cost-usd 1.0` 초과 시 abort, dry-run 시 예상 비용만 출력

**D2. Committee agreement**
- 신호: 동일 ticker × 동일 날짜의 PM eco/deep/risk 등 역할 출력 비교 — 액션 분포, conviction 분산
- 임계치: 합의 ≥75% pass / 60~75% warn / <60% fail

**D3. LLM signal volatility**
- 신호: `decision_layer`가 받는 LLM 도출 신호 필드(`narrative_strength`, `news_sentiment_score` 등)의 14일 표준편차
- 임계치: 정규화 0~1 가정, std ≤0.25 pass / >0.40 fail

### Operational Signals (R) — 로그만 사용

**R1. Pipeline summary**
- 신호: 14일치 `*.summary.json` 집계 — fallback rate, schema retry count, model usage drift, daily_api_cost_usd 추세
- 임계치: fallback rate ≤5% pass / 5~15% warn / >15% fail

**R2. Retry/failure distribution**
- 신호: ticker × 모듈 매트릭스의 retry/fail 카운트
- 임계치: ticker당 14일 retry ≤2 pass / 3~5 warn / >5 fail

## Report Format

### Human-readable (`docs/reports/llm-audit-YYYY-MM-DD.md`)

```markdown
# LLM Audit Report — 2026-04-28
**Window:** 2026-04-15 ~ 2026-04-28 (14d) | **Tickers:** N | **Replay:** 5×3 (cost: $X)
**Overall verdict:** F fail / W warn / P pass (out of 14)

## 1. Executive Summary (≤300 words)
가장 시급한 3가지 + 빠른 승리 3가지 + 추가 조사 항목.

## 2. Verdict Matrix
| ID | Dimension | Severity | Pass rate | Top finding | Affected |
| ... |

## 3. 차원별 상세 (14개 섹션)
각 차원: 임계치, 측정 결과, 14일 trend(ASCII sparkline), Top findings (최대 10), Recommendation (S/M/L 난이도).

## 4. 우선순위 개선 백로그
영향 × 난이도로 가중된 ranked 표.

## 5. Methodology
윈도우, 임계치 출처, 측정 한계, replay 비용 내역.

## 6. Appendix
실행 명령, git sha, 모델 profile, 환경 변수 dump.
```

스타일: 마크다운 vanilla, 텍스트 표 + ASCII sparkline(`▁▂▂▃▅▆█`), 한국어 본문 + 영어 식별자.

### Machine-readable (`output/data/llm_audit/YYYY-MM-DD.json`)

```jsonc
{
  "schema_version": 1,
  "audit_date": "2026-04-28",
  "window": {"start": "2026-04-15", "end": "2026-04-28", "days": 14},
  "tickers_audited": ["..."],
  "model_profile": "economy",
  "git_sha": "abcd1234",
  "replay": {
    "enabled": true,
    "tickers": ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"],
    "runs_per_ticker": 3,
    "cost_usd": 0.34,
    "cost_cap_usd": 1.0
  },
  "summary": {"total_checks": 14, "pass": 5, "warn": 6, "fail": 3, "overall_severity": "warn"},
  "checks": [
    {
      "check_id": "I3",
      "dimension": "format_consistency",
      "severity": "fail",
      "pass_rate": 0.71,
      "thresholds": {"pass": ">=0.95", "warn": ">=0.85"},
      "metrics": {"fields_with_multi_format": 2, "worst_field": "published_at"},
      "findings": [
        {"field": "published_at",
         "formats_seen": ["ISO-8601", "RFC822", "free"],
         "examples": ["2026-01-30", "Fri, 30 Jan 2026 08:00:00 GMT"],
         "affected_tickers": 38}
      ],
      "recommendation": {
        "summary": "collector 단계에서 ISO-8601 강제 정규화",
        "difficulty": "S",
        "files_hint": ["src/collector/news.py", "src/collector/sec.py"]
      }
    }
  ]
}
```

`schema_version`을 두어 phase 2/3 호환을 유지한다. `recommendation.files_hint`는 휴리스틱이며 자동 변경 트리거가 아니다.

### Console output

```
[I1] schema_stability        pass  99.2% (1.3s)
[I3] format_consistency      FAIL  71%   (1.1s)  → published_at multi-format
[O2] numeric_grounding       warn  91%   (4.2s)
[D1] semantic_drift          warn  ...   (replay: 5×3, $0.34, 47s)
─────────────────────────────────────────────
14 checks: 5 pass / 6 warn / 3 fail
Report: docs/reports/llm-audit-2026-04-28.md
JSON:   output/data/llm_audit/2026-04-28.json
```

## Cost & Execution Model

### Cost estimate (R-replay)

| 항목 | 값 |
|------|-----|
| Replay 호출 수 | 5 ticker × 3 회 = 15 |
| 호출당 추정 토큰 | ~3K in / ~1K out (research_note 평균) |
| **총 예상 비용 / 1회 audit** | **$0.30 ~ $0.80** (economy profile 기준, 실측치는 보고서 기록) |

### Cost guards (필수)

- `--max-replay-cost-usd` 기본 1.0, 초과 시 D1 abort, 이미 든 비용 보고서 기록.
- `--dry-run`: token-count 추정만 출력, 실제 호출 없음.
- replay 시작 전 콘솔에 예상 비용 출력 + 5초 confirm 대기. CI는 `--yes`로 skip.

### Time estimate

| 단계 | 예상 시간 |
|------|----------|
| 데이터 로딩 | 5~15s |
| I1~I4, R1·R2 | 5~10s |
| O1~O5 (link-check OFF) | 10~30s |
| D2·D3 | 5~15s |
| D1 replay (직렬) | 30~90s |
| 보고서 렌더 | 1~2s |
| **총합** | **약 1~3분** |

병렬화는 phase 2 이후. 일회성 진단에서는 직렬 실행이 단순하고 안전하다.

### Idempotency

같은 날 두 번 실행 시 같은 파일 덮어쓰기. 비교가 필요하면 `--suffix <name>`로 별도 파일.

### Environment

- 로컬 실행 우선. CI 자동 실행은 본 phase 범위 밖.
- `OPENAI_API_KEY`는 D1에만 필요. 나머지 12개 체크는 키 없이도 구동.
- `OPENAI_MODEL_PROFILE`은 audit 시점 운영 값과 동일하게 사용. 다르면 fail-fast 경고.
- `ENABLE_EXTERNAL_FETCH=false` 강제 — collector 단계 호출 금지.

### Safety summary

| 위험 | 방어 |
|------|------|
| API 비용 폭주 | `--max-replay-cost-usd`, `--dry-run`, confirm 대기 |
| 운영 데이터 손상 | audit는 read-only, write는 신규 두 경로뿐 |
| Profile mismatch | 시작 시 비교 후 다르면 fail-fast |
| Replay 네트워크 오류 | retry 1회, 실패 시 D1만 fail |
| 휴리스틱 false positive | 보수적 임계치 + methodology 섹션에 한계 명기 |
| 외부 링크 HEAD 호출 | 기본 OFF, `--check-links` 활성 시 100건 캡 |

### Permissions & secrets

신규 시크릿/권한 없음. `.env` 그대로. 산출물에 API 키나 raw 토큰 기록 금지(model profile 이름만).

## Test Strategy

프로젝트 표준(`python -m unittest discover -s tests -v`)을 따른다.

### 단위 테스트 (차원당 최소 3 케이스)

`tests/eval/checks/test_<id>.py` — 각 체크에 대해:

- Happy path: 정상 데이터 → `severity="pass"`, `pass_rate=1.0`
- Boundary: 임계치 ±ε → severity 전이 검증
- Failure mode: 의도적 오염 → 정확한 finding 생성

### Fixture

`tests/eval/fixtures/`에 작은 익명 daily JSON 2~3개 + 합성 로그 jsonl(10 이벤트 이내). 실제 ticker 데이터는 fixture로 쓰지 않는다(시간 지나면 깨짐). `make_dataset(...)` 헬퍼로 케이스별 변형 생성.

### 통합 테스트 — `tests/eval/test_runner.py`

- `--skip-replay`로 14체크 모두 실행 → CheckResult 14개 + 산출 파일 2개
- 잘못된 윈도우(`--window 1` 미만) → 명확한 에러
- 한 체크가 raise → 다른 13개 정상 완료 (격리 검증)
- 보고서 md·JSON의 schema 셀프 체크

### D1 replay 테스트 (실제 API 호출 금지)

- `replay.py`의 LLM 호출부는 의존성 주입 가능
- `FakeLLMClient`로 mock (deterministic / drifty 두 모드)
- `--dry-run` 모드: 실제 호출 0회, 비용 추정 출력 검증
- 비용 캡 초과 시나리오: mock 누적이 캡 위로 올라가면 D1만 abort

### 골든 파일

`tests/eval/fixtures/golden/audit_report_sample.md` — 합성 dataset에 대한 산출물 골든 비교. 실데이터 골든은 금지. 업데이트는 `UPDATE_GOLDENS=1` 환경 변수로.

### Lint / type / coverage

- `python -m compileall src/eval` — syntax check
- 타입 힌트 strict (mypy 활성 시 `src/eval/**/*.py` 포함)
- frozen dataclass 우선
- 커버리지 목표:
  - `src/eval/checks/*.py`: 단위 100% (14 체크 × 평균 3 케이스 = 42 테스트)
  - `runner.py`, `report.py`, `data_sources.py`: ≥85%
  - `replay.py` 분기: ≥90%

### 실행 시간 예산

| 그룹 | 목표 |
|------|------|
| 단위 테스트 (14×3) | < 5초 |
| 통합 테스트 | < 10초 |
| 전체 `tests/eval/` | < 15초 |

## Open Questions

이 spec에는 의도적으로 비워둔 자리표시자가 없으나, 구현 시점에 확인할 사항:

- `config/models.yaml`의 economy profile 단가는 구현 시 실측치로 갱신해 비용 추정 표를 보정한다.
- O3-(b) 링크 HEAD의 100건 샘플 cap 비율이 실제 키뉴스 분포와 맞는지 첫 실행 후 재조정 여지.
- O5 contradiction의 lex 사전은 한국어·영어 양방향이 필요하며, 첫 실행에서 false positive 비율을 보고 임계치 보정.

이 항목들은 구현 PR에서 코멘트로 남기고, 본 spec의 임계치는 변경하지 않는다(임계치는 `config.py`에서만 조정).

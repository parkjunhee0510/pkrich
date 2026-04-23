# Final Decision Confidence Design

## Summary

최종 종목 판단의 신뢰도를 높이기 위해, 기존 `factor -> conviction -> action` 구조 위에 별도의 `confidence meta` 레이어를 추가한다.

이번 설계의 목표는 `점수를 더 공격적으로 올리는 것`이 아니라 `잘못된 고확신을 줄이는 것`이다. 따라서 기존 factor scoring은 유지하고, 그 결과를 `데이터 품질`, `증거 커버리지`, `증거 일관성`, `모델 합의`로 보정해 최종 conviction을 다시 계산한다.

핵심 원칙:

* 기존 factor/scorer 구조는 최대한 유지한다.
* analyzer와 decision의 레이어 경계를 깨지 않는다.
* 보정은 설명 가능하고 테스트 가능해야 한다.
* 초기 rollout은 shadow mode로 시작해 기존 conviction과 차이를 비교한다.

## Problem Statement

현재 최종 종목 판단 신뢰도를 깎는 원인은 한 가지가 아니다.

* 입력 데이터 결측과 `N/A`가 많다.
* 일부 문자열은 인코딩 깨짐이나 포맷 손상 문제가 있다.
* validator 경고가 발생해도 최종 conviction에는 직접 반영되지 않는다.
* factor 점수는 높아도 증거가 부족하거나 서로 충돌하는 경우가 있다.
* ensemble disagreement가 최종 conviction을 직접 보수화하지는 않는다.

결과적으로 `좋은 점수 = 높은 확신`으로 해석되는 구간이 있고, 이때 실제 증거 품질보다 conviction이 과대평가될 수 있다.

## Goals

* 데이터 품질이 낮은 티커의 과도한 high-conviction 판단을 줄인다.
* 증거가 충분하고 서로 일관된 티커는 기존 conviction을 거의 유지한다.
* economy/deep/3차 검토가 갈릴 때 최종 conviction을 보수화한다.
* 최종 conviction이 왜 보정되었는지 UI와 JSON에서 설명 가능하게 만든다.
* 기존 output/web payload를 비파괴적으로 확장한다.

## Non-Goals

* factor scoring 로직을 전면 재작성하지 않는다.
* ML 기반 meta-learner를 이번 단계에 도입하지 않는다.
* analyzer 레이어에서 final conviction을 직접 계산하지 않는다.
* 외부 API나 추가 수집 경로를 새로 만들지 않는다.

## Proposed Architecture

### New module

신규 파일:

* `src/decision/confidence.py`

역할:

* `data_quality`
* `evidence_coverage`
* `evidence_consistency`
* `model_agreement`
* `confidence_gate`
* `final_conviction`

계산 전담

### Decision flow changes

기존 흐름:

1. factor registry 실행
2. factor score 계산
3. scorer가 conviction 계산
4. threshold로 action 결정

변경 흐름:

1. factor registry 실행
2. factor score 계산
3. scorer가 `raw_conviction` 계산
4. `confidence.py`가 confidence meta 계산
5. `confidence_gate`로 `final_conviction` 계산
6. `final_conviction` 기준으로 action 결정
7. reason과 output에 confidence meta 반영

### Layer boundary

* analyzer는 기존처럼 구조화 분석과 consensus metadata를 생산한다.
* decision은 analyzer 결과와 quality summary를 입력으로 받아 최종 판단을 조립한다.
* output은 `raw_conviction`, `confidence_meta`, `final_conviction`을 직렬화만 한다.

즉 신뢰 보정의 정본은 `decision/`이다.

## Inputs

`confidence.py`가 읽는 입력은 아래로 제한한다.

* `TickerAnalysis`
* `CollectedTickerData`
* `MarketRegime`
* `signal_stats`
* `analysis_consensus_by_ticker`
* `analysis_quality_by_ticker`
* `portfolio_risk`

중요한 점:

* validator raw 로그 전체를 직접 넘기지 않는다.
* decision은 티커별 요약값만 읽는다.

예상 quality summary shape:

```python
{
    "fact_warning_count": 1,
    "hallucination_warning_count": 0,
    "consistency_warning_count": 0,
    "fallback_used": False,
    "encoding_issue_detected": False,
}
```

예상 consensus summary shape:

```python
{
    "status": "agreed" | "conflicted" | "not_applicable",
    "direction_agreement": True | False,
    "had_tie_break": True | False,
}
```

## Confidence Meta Definitions

### 1. data_quality

입력 데이터와 analysis quality가 얼마나 믿을 만한지를 나타낸다.

반영 요소:

* 필수 필드 결측률
* `N/A` 비율
* 깨진 문자열 감지
* `fact_warning_count`
* `hallucination_warning_count`
* fallback 사용 여부

초기 계산 방식:

* 시작점 `1.0`
* 필수 필드 결측이 늘수록 감점
* hallucination warning은 큰 감점
* fallback과 encoding issue도 감점

예상 구간:

* `0.85 ~ 0.95`: 데이터 양호
* `0.60 ~ 0.80`: 일부 결측
* `0.20 ~ 0.50`: 경고/손상 많음

### 2. evidence_coverage

판단에 필요한 핵심 증거 축이 얼마나 채워졌는지 나타낸다.

초기 6축:

* 가격/추세
* 펀더멘털
* 뉴스
* 실적/이벤트
* peer 비교
* 거시/포트폴리오

계산 방식:

* 각 축마다 최소 유효 데이터가 있으면 점수 부여
* 총 충족 축 / 전체 축 비율로 계산

예:

* 6축 중 5축 유효 -> `0.83`
* 6축 중 3축 유효 -> `0.50`

### 3. evidence_consistency

서로 다른 증거가 같은 방향을 가리키는지 나타낸다.

초기 비교쌍:

* news tone vs price momentum
* momentum vs final action
* macro event vs sector direction
* peer rank vs action
* earnings pattern vs signal takeaway

계산 방식:

* 일치하면 가점
* 충돌하면 감점
* 강한 충돌은 더 큰 감점

예상 구간:

* `0.75 ~ 0.90`: 대체로 정렬
* `0.45 ~ 0.65`: 혼합
* `0.20 ~ 0.40`: 강한 충돌

### 4. model_agreement

여러 모델/경로의 판단이 얼마나 같은 결론을 내는지 나타낸다.

초기 규칙:

* 앙상블 미대상: `0.60`
* economy/deep 일치: `0.90`
* 불일치 후 3차로 정리: `0.65`
* 최종 conflict 유지: `0.40`

이 값은 점수 가산이 아니라 과신 억제용으로 사용한다.

## Confidence Gate Formula

초기 결합식:

```python
confidence_gate = (
    0.40 * data_quality
    + 0.25 * evidence_coverage
    + 0.20 * evidence_consistency
    + 0.15 * model_agreement
)
```

이유:

* 현재 가장 큰 문제는 데이터 품질이므로 `data_quality` 비중을 가장 높게 둔다.
* ensemble agreement는 아직 일부 티커에만 적용되므로 비중을 낮게 둔다.

## Final Conviction Formula

초기 보정식:

```python
final_conviction = round(raw_conviction * (0.60 + 0.40 * confidence_gate))
```

효과:

* confidence gate가 낮아도 conviction이 0으로 붕괴하지 않는다.
* confidence gate가 높을수록 raw conviction을 더 많이 보존한다.
* 과도한 고확신을 줄이되, 기존 factor 구조를 훼손하지 않는다.

## Hard Guardrails

v1에는 설명 가능한 상한 규칙을 둔다.

예상 규칙:

* `data_quality < 0.35` -> `final_conviction` 상한 `59`
* `data_quality < 0.25` -> `buy` action 금지
* `hallucination_warning_count >= 2` -> `final_conviction` 상한 `54`
* `confidence_gate < 0.40` and `raw_conviction >= 70` -> 최소 1단계 보수화 검토

목적은 `데이터가 엉성한데도 buy 75+` 같은 케이스를 막는 것이다.

## Output Changes

`TickerDecision`는 비파괴적으로 확장한다.

추가 필드:

* `raw_conviction: int`
* `confidence_meta: dict`
  * `data_quality`
  * `evidence_coverage`
  * `evidence_consistency`
  * `model_agreement`
  * `confidence_gate`

유지되는 필드:

* `conviction` -> 최종 보정된 conviction
* `action`
* `reason`
* `factors`

이 구조는 기존 consumer가 `conviction`만 읽더라도 깨지지 않는다.

## Reasoning Changes

최종 reason에는 confidence meta를 반영한 한 줄을 추가한다.

예:

* `데이터 품질과 증거 일관성이 높아 판단 신뢰도가 양호합니다`
* `실적/peer 데이터가 부족해 확신도를 보수적으로 조정했습니다`
* `모델 판단이 갈려 최종 확신도를 일부 낮췄습니다`

이유:

* 사용자는 점수가 왜 바뀌었는지 알아야 한다.
* 단순히 conviction만 낮아지면 설명력이 떨어진다.

## Rollout Plan

### Phase 1: shadow mode

* `confidence.py` 추가
* `raw_conviction`, `confidence_meta`, `final_conviction` 계산
* action은 아직 기존 conviction 기준 유지
* diff/log만 쌓아 비교

### Phase 2: decision switch

* action 기준을 `final_conviction`으로 전환
* 기존 결과와 buy/watch/avoid 분포 비교
* 극단값과 conflict case를 샘플링 검토

### Phase 3: UI exposure

* decision card에 `원점수 -> 보정 후 점수` 노출
* confidence meta breakdown 노출
* “왜 보정되었는지” 문구 노출

### Phase 4: calibration tuning

* routing_outcome, signal_tracker, decision history를 통해
* confidence_gate 구간별 성과 비교
* gate 가중치와 guardrail 수치 미세조정

## Testing Plan

신규:

* `tests/test_decision_confidence.py`

확장:

* `tests/test_decision_layer.py`

핵심 검증:

* 결측 많은 티커는 `final_conviction < raw_conviction`
* 품질 높은 티커는 점수가 과도하게 깎이지 않음
* agreement 낮을 때 고확신이 줄어듦
* hard guardrail이 작동함
* output shape가 기존 consumer를 깨지 않음

## Risks

* 초기 gate가 너무 보수적이면 buy 후보가 과도하게 줄 수 있다.
* quality summary 설계가 엉성하면 confidence meta가 또 다른 노이즈가 될 수 있다.
* 앙상블 비대상 티커에 대한 `model_agreement` 중립값이 실제보다 관대하거나 빡빡할 수 있다.

## Mitigations

* shadow mode로 먼저 raw/final diff를 비교한다.
* v1은 단순 가중합과 명시적 guardrail만 사용한다.
* quality summary는 decision이 필요한 최소 항목만 받는다.
* calibration은 Phase 4에서만 수행하고, v1에는 넣지 않는다.

## Open Decisions Resolved For v1

이 설계에서 v1은 아래처럼 고정한다.

* 정본 위치는 `src/decision/confidence.py`
* confidence meta는 decision layer에서 계산
* 기존 factor scoring은 유지
* output은 비파괴 확장
* rollout은 `shadow -> switch -> UI -> calibration`

## Success Criteria

* 고확신 오판 케이스가 줄어든다.
* 데이터 품질이 낮은 티커의 conviction이 체계적으로 보수화된다.
* 사용자가 최종 판단을 왜 덜 믿어야 하는지 설명할 수 있다.
* 기존 pipeline invariant와 layer boundary를 유지한다.

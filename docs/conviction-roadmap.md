# Conviction Quality Roadmap

Step 1-6 완료 이후의 확장 계획. 각 작업은 **샘플 축적량**과 **선행 의존성** 기준으로 Phase 1-5에 배치.

---

## 상승 기대효과 — Step 1-6이 서로 곱해지는 방식

### 1. 폐루프 자체가 각 단계를 정량화 가능하게 만든다
Step 1(피드백 기록)이 없었다면 나머지는 전부 직감 기반. 이제 `conviction / action / regime / factors_json`이 `signal_tracker.csv`에 박혀있어서:

- **Step 2** 앙상블 보정 효과 → `calibration.json`의 Brier score 변화로 측정
- **Step 3** 레짐 가중치 → regime별 Spearman으로 측정
- **Step 4** factor audit → IR 수치로 어떤 factor를 버릴지 결정
- **Step 6** 그리드 서치 → 목적함수 자체가 Step 1 데이터 없이는 정의 불가

즉 Step 1은 나머지 전부의 전제, Step 6는 그 데이터를 다시 Step 3 가중치로 되먹이는 **컨트롤 루프**.

### 2. 교차 검증이 가능해짐
- Step 4 IR이 약하다고 말한 factor → Step 6 그리드 서치가 실제로 낮은 multiplier를 고르는지 대조
- Step 5 α 메트릭과 절대 메트릭의 decile 성능 차이 → 워치리스트 편향 크기를 수치화
- Step 2 앙상블 spread가 큰 시그널이 Step 1 calibration에서 실제로 덜 신뢰할 만한지 검증

### 3. 자기참조 루프 해체 효과 누적
Step 4의 `news_tone → direction → signal_track_record` 분리 덕분에:
- Step 1 피드백이 "실제 의사결정 품질"을 측정 (이전엔 자기예측에 가까웠음)
- Step 6 그리드 서치의 Spearman이 과적합 없이 해석 가능

### 4. 변동성 스케일 통일
Step 5 `alpha_5d`(워치리스트 대비) + Step 6 `build_ticker_neutral_bands`(±1σ) →
- 저변동주 KO와 고변동주 IONQ를 같은 conviction 체계로 비교 가능
- 이전엔 IONQ의 ±10% 노이즈를 +10% 수익으로 잘못 크레딧함

---

## 작업 순서

### Phase 1 — 데이터 축적 기간 (Now ~ 1개월, 0 샘플 요구)

지금 당장 가능한 셋. 다른 모든 단계의 관측·검증 기반이 된다.

| # | 작업 | 공수 | 목적 |
|---|------|------|------|
| 1 | 자동 리포트 파이프라인 | ~1h | `tune_weights` 산출물을 Admin에 표시. 자동 쓰기 금지, 수동 승인 게이트. |
| 2 | Calibration drift 감지 | ~30min | Brier score 30일 이동평균 + 트렌드 차트. 레짐 전환/모델 열화 조기 경보. |
| 3 | **Walk-forward CV** | ~2h | 후견편향 없는 평가. **이후 모든 튜닝 결정의 품질이 이 한 기능에 달려있음.** |

**먼저 할 한 가지: #3 Walk-forward CV.** 2시간 투자로 honest evaluation 확보 → Phase 2 이후 모든 업데이트가 정당화 가능해짐.

### Phase 2 — 첫 번째 튜닝 사이클 (샘플 100+, ~1.5개월)

| # | 작업 | 공수 | 목적 |
|---|------|------|------|
| 4 | 첫 가중치 업데이트 + A/B 레일 | ~2h | 제안 multiplier로 `conviction_challenger` 컬럼 병행 기록. 가중치 변경해도 역사 단절 없음. |
| 5 | Weak factor 감쇠 | ~30min | `peer_rank` IR이 |0.1| 미만이면 weight_range 절반으로. 완전 제거는 보류. |

### Phase 3 — 스케일 전환 (샘플 300+, ~2-3개월)

| # | 작업 | 공수 | 목적 |
|---|------|------|------|
| 6 | SQLite 전면 전환 | ~3h | `DATASTORE_BACKEND=sqlite` 기본값화. Phase 4 I/O 집약 작업 대비. |
| 7 | Action-conditional threshold | ~2h | `conviction × regime × catalyst_type` 3D 컷오프 테이블. |

### Phase 4 — 정식 최적화 (샘플 500+, ~3-6개월)

| # | 작업 | 공수 | 목적 |
|---|------|------|------|
| 8 | Gradient descent | ~4h | scipy.optimize로 연속 multiplier 탐색. 243 그리드 → 정밀도 향상. |
| 9 | Factor interaction 탐색 | ~4h | `momentum × catalyst_recency` 등 2-way 교호항. |
| 10 | Slippage/비용 모델 | ~3h | `net_return_5d` 컬럼 추가, 목적함수를 순수익으로. |

### Phase 5 — 장기 구조 개선 (샘플 1000+, 6개월+)

| # | 작업 | 공수 | 목적 |
|---|------|------|------|
| 11 | Out-of-watchlist 백테스트 | ~1-2주 | S&P500 전 종목 가상 파이프라인. 생존편향 최종 해결. |
| 12 | Meta-learner (XGBoost) | ~1주 | 8-factor 선형 합산 → 비선형 모델. SHAP로 해석 유지. |
| 13 | Regime HMM 재학습 | ~1주 | 룰 기반 regime → 데이터 기반. 3-state 최적성 재검증. |

---

## 작업별 파일

### Phase 1

| # | 작업 | 수정 | 신규 |
|---|------|------|------|
| 1 | 자동 리포트 | `src/output/json_export.py`, `web/src/pages/Admin.tsx` | — |
| 2 | Drift 감지 | `src/decision/calibration.py`, `web/src/pages/Admin.tsx` | — |
| 3 | Walk-forward CV | `src/decision/tune_weights.py` | `tests/test_tune_weights_walkforward.py` |

### Phase 2

| # | 작업 | 수정 | 신규 |
|---|------|------|------|
| 4 | 가중치 업데이트 + A/B | `config/decision_weights.yaml`, `src/utils/signal_tracker.py` (FIELDNAMES), `src/decision/decision_layer.py`, `src/pipeline.py` | — |
| 5 | Weak factor 감쇠 | `config/decision_weights.yaml` | — |

### Phase 3

| # | 작업 | 수정 | 신규 |
|---|------|------|------|
| 6 | SQLite 전환 | `src/utils/datastore.py` (기본값), `src/utils/datastore_sqlite.py`, `.env.example`, CI 워크플로우 | — |
| 7 | Action-conditional threshold | `src/decision/tune_weights.py`, `src/decision/decision_layer.py`, `config/decision_weights.yaml` | — |

### Phase 4

| # | 작업 | 수정 | 신규 |
|---|------|------|------|
| 8 | Gradient descent | `src/decision/tune_weights.py` | `requirements.txt` (scipy 추가) |
| 9 | Factor interaction | `src/decision/scorer.py`, `src/decision/tune_weights.py`, `src/decision/factor_audit.py` | — |
| 10 | Slippage/비용 모델 | `src/utils/signal_tracker.py` (신규 컬럼), `src/decision/calibration.py`, `src/decision/tune_weights.py` | `src/utils/cost_model.py` |

### Phase 5

| # | 작업 | 수정 | 신규 |
|---|------|------|------|
| 11 | Out-of-watchlist 백테스트 | `src/pipeline.py` (universe 주입점) | `src/backtest/universe_replay.py`, `src/backtest/historical_universe.py` |
| 12 | Meta-learner | `src/decision/scorer.py` (optional branch) | `src/decision/meta_learner.py`, `src/decision/shap_explain.py` |
| 13 | Regime HMM | `src/decision/market_regime.py` | `src/decision/regime_hmm.py`, `src/decision/regime_training.py` |

---

## 순서 결정 기준

| 기준 | 적용 |
|------|------|
| **의존성** | #1(리포트) → #4(업데이트) → #8(gradient). #3(CV) 없이 #8 가면 과적합. |
| **샘플 요구량** | #1-3는 0 샘플, #4-5는 100+, #7-8은 500+, #11-13은 1000+. |
| **리스크** | 자동 쓰기(#4)는 항상 수동 게이트. 구조 변경(#6 SQLite, #11 universe 확장)은 샘플 안정기에. |
| **코드량** | 작은 것부터: #2(30min) → #5(30min) → #1(1h) → #3(2h) → ... |

---

## 완료된 선행 작업 (참고)

| Step | 핵심 산출물 | 주요 파일 |
|------|-------------|-----------|
| 1 | 피드백 루프 닫기 | `src/utils/signal_tracker.py`, `src/decision/calibration.py`, `src/output/json_export.py` |
| 2 | 앙상블 → conviction 실반영 | `src/analyzer/ensemble.py` |
| 3 | 레짐 조건부 가중치 | `config/decision_weights.yaml` |
| 4 | Factor 중복/누수 감사 | `src/decision/factor_audit.py`, `src/decision/factors/signal_record_factor.py` |
| 5 | 생존편향 / 룩어헤드 방어 | `src/collector/price.py`, `src/utils/signal_tracker.py` (benchmark/alpha) |
| 6 | 가중치 튜닝 루프 | `src/decision/tune_weights.py`, `src/utils/signal_tracker.py` (neutral bands) |

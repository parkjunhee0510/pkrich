# Phase 4 리팩토링 검증 & 고도화 제안

> 작성일: 2026-04-16
> 대상: Phase 4-0 ~ 4-6 Analyzer/Decision 아키텍처 리팩토링 결과

---

## ✅ 완료 검증

### Phase 4-0 — Analyzer 아키텍처 리팩토링 (완료)

| 영역 | 파일 | 상태 |
|------|------|------|
| 4-0a AnalysisModule 인터페이스 | `src/analyzer/base.py` | ✅ `AnalysisModule`·`StructuredLLMModule`·`AnalysisContext`·`ModuleResult` |
| 4-0b ModuleRegistry (DAG) | `src/analyzer/registry.py` | ✅ `requires`/`produces` 토폴로지 정렬 + cycle 감지 |
| 4-0b Orchestrator | `src/analyzer/orchestrator.py` | ✅ 비-LLM 먼저, LLM 다음, `execution_mode`로 앙상블용 `llm_only` 지원 |
| 4-0b 모듈 분해 | `src/analyzer/modules/` | ✅ valuation / trade_frame / news_analysis / research_narrative / risk_assessment / signal_takeaway / portfolio_risk / peer_comparison / weekly_insight |
| 4-0c PromptTemplate | `src/analyzer/prompts/` | ✅ v1/v2 + registry (`get_prompt_template`) |
| 4-0d DecisionFactor 플러그인 | `src/decision/factors/` | ✅ 10개 팩터 + auto-discovery + `weight_range` 자동 바인딩 |
| 4-0d ConvictionScorer | `src/decision/scorer.py` | ✅ 자동 정규화 |
| 4-0e 레짐 승수 | `config/decision_weights.yaml` | ✅ risk_on / risk_off / neutral 승수 + thresholds |
| 4-0f 마이그레이션 | `src/analyzer/modules/legacy_research_note.py` | ✅ thin wrapper 유지 |

### Phase 4-1 ~ 4-6 (완료)

- **4-1 포트폴리오 리스크** — `PortfolioRiskModule` + `portfolio_risk_factor.py` ✅
- **4-2 Peer 비교** — `PeerComparisonModule` + `peer_selector.py` + `peer_rank_factor.py` ✅
- **4-3 멀티모델 합의** — `src/analyzer/ensemble.py` (경계 conviction 트리거, consensus 적용) ✅
- **4-5 주간 인사이트** — `WeeklyInsightModule` (242줄) ✅
- **4-6 품질 검증** — `src/analyzer/validator.py` + `src/analyzer/ab_test.py` ✅

### ⚠️ 테스트 실패 5건 (모두 테스트 쪽 문제)

1. **`tests/test_decision_registry.py:14-24`** — config에 `peer_rank` 누락. 4-2에서 팩터 추가됐는데 테스트 fixture가 stale.
2. **`tests/test_quality_upgrade.py:5`** — 제거된 `_score_conviction` import. 리팩토링 후 남은 dangling 테스트.
3. **`tests/test_pipeline.py` (2건)** — Windows `tempfile` + SQLite 핸들 cleanup 경합 (`price_history.sqlite` 삭제 불가). 파이프라인 자체는 통과, 정리 단계에서 `NotADirectoryError` → datastore_sqlite에 명시적 `close()` 호출 필요.

---

## 🎯 추가 고도화 제안

### A. 즉시 처리 (스탭 작업)

1. **Stale 테스트 3건 수리**
   - `test_decision_registry` 픽스처에 `peer_rank` 추가
   - `test_quality_upgrade` 신규 `FactorRegistry` 기반으로 포팅
   - SQLite 커넥션 명시적 close
2. **`src/analyzer/research_note.py` 2,168줄 최종 제거**
   현재 `legacy_research_note.py`만 wrapper로 쓰고 있으니 본체는 삭제 가능한지 grep으로 확인 후 정리

### B. 관찰 가능성 (고도화 1순위 — 데이터 없이는 튜닝 불가)

| 제안 | 이유 |
|------|------|
| **모듈별 실행 메트릭 수집** | 현재 `orchestrator.diagnostics`에 모듈 이름만 있음. 모듈별 `duration_ms` · `tokens_used` · `cache_hit` · `validation_warnings` 수집 → `output/data/module_metrics.jsonl` |
| **일일 품질 대시보드** | validator가 warning을 기록하지만 UI에 노출 안 됨. 웹 대시보드에 `/analysis-quality` 페이지 (환각률·스키마 위반·팩터 신뢰도 분포) |
| **팩터 기여도 시각화** | FactorScore의 `reasoning`이 이미 있음. TickerDetail에서 "왜 conviction 68인가?" 펼침 카드로 표시 (팩터별 +/- 막대) |
| **비용 메트릭** | Phase 4-3 앙상블 도입으로 비용 편차 커짐. 일별 `$cost_by_model` + `cost_by_module` 로깅 |

### C. 캐싱·효율성 (비용 절감)

| 제안 | 효과 |
|------|------|
| **AnalysisModule 결과 캐시** | 수식 기반 모듈(valuation, trade_frame, portfolio_risk)은 입력 hash 같으면 재실행 불필요. SQLite 캐시 (TTL=당일) |
| **Incremental Analysis** | 전일 대비 가격/뉴스/펀더멘탈 변화 없는 티커는 LLM 재호출 skip, 기존 narrative 재사용 (+ 날짜 스탬프 갱신) |
| **Batch Prompt 최적화** | 현재 티커별 배치. `StructuredLLMModule.estimate_tokens`가 정의됐으나 동적 batch sizing은 미사용 → token budget 기준 auto-pack |
| **Schema 캐시 warm-up** | `prompts/registry.py`에서 모든 템플릿을 매 호출 로드. startup에서 1회 렌더링 후 immutable 보관 |

### D. 팩터·모듈 확장 (로드맵 예시 기반)

| 우선순위 | 신규 팩터/모듈 | 비고 |
|---------|---------------|------|
| ⭐ 높음 | `options_skew_factor.py` | 로드맵 예시, 데이터 이미 수집 (PCR). 3단계로 추가 가능 |
| ⭐ 높음 | `insider_factor.py` | Phase 1-5와 연동. `sec_form4` + FMP insider 통합 감지 |
| 중 | `macro_sensitivity_module.py` | 섹터별 금리·달러 민감도. `macro_sensitivity.py` 이미 util로 존재 → 모듈 승격 |
| 중 | `sector_rotation_module.py` | 섹터 ETF RS (Phase 1-2)가 완료되면 섹터 간 순환 모멘텀 점수 |
| 낮음 | `social_sentiment_module.py` | Reddit/StockTwits. 데이터 소스 라이선스 검토 필요 |

### E. 품질·신뢰성

1. **Shadow mode 자동 회귀**
   프롬프트 버전 업(v1→v2)시 양쪽 병렬 실행 → 3일간 diff 모니터, 회귀 시 자동 롤백
2. **Validator 확장**
   현재 환각·스키마만. 추가:
   - (a) 숫자 범위 sanity (PER 음수, RSI 100 초과 감지)
   - (b) 내부 일관성 (signal은 bullish인데 target_price < current_price)
3. **AB 테스트 자동 결론**
   `ab_test.py`가 결과만 저장. 주간 배치로 winner 자동 판정 + `config/models.yaml` PR 제안 (manual merge)
4. **Cycle detection 테스트**
   `ModuleRegistry.resolve_order`에 순환 의존성 단위 테스트 추가 (현재 미검증)

### F. 사용자 경험 (Phase 3 미진행 분)

1. **Factor Explainer UI** — DecisionCard 하단 "왜?" 버튼 → 팩터별 점수·reasoning 카드 애니메이션
2. **앙상블 불일치 알림** — `decision.ensemble_agreement == "conflict"` 일 때 대시보드 상단 배너
3. **주간 보고서 Markdown → 이메일** — `WeeklyInsightModule` 결과를 SMTP 또는 Slack 주간 다이제스트로

### G. 의사결정 레이어 진화

1. **팩터 가중치 learning**
   `signal_tracker.csv`에 팩터 점수 히스토리를 기록하고, 5D 실현 수익 회귀로 가중치 최적화 (월 1회 배치, YAML PR 제안)
2. **레짐 자동 탐지 고도화**
   현재 VIX 단일 지표. 금리 변화율·달러 강도·spread 추가 → 3-factor regime
3. **Position Sizing 모듈**
   현재 `trade_frame`은 진입/손절만. Kelly-lite 기반 권장 포지션 크기 추가 (portfolio_risk VaR 연계)

---

## 📌 권장 순서

| 주차 | 작업 | 목표 |
|------|------|------|
| 1주차 | Stale 테스트 3건 수리 + `research_note.py` 2,168줄 최종 제거 | **기술 부채 청산** |
| 2주차 | 모듈별 실행 메트릭 + 비용 추적 | **관찰 가능성 확보** |
| 3주차 | `options_skew_factor` + `insider_factor` | **플러그인 아키텍처 실사용 검증** (3단계 레시피가 정말 쉬운지) |
| 4주차~ | Incremental Analysis + Factor Explainer UI | **비용 절감 + UX** |

가장 ROI 높은 건 **B(관찰) + C(캐싱)** 입니다.
리팩토링이 잘 됐는지는 결국 "새 팩터 추가가 정말 3단계인가"를 써봐야 검증되므로 D의 `options_skew_factor`도 조기에 해보길 권합니다.

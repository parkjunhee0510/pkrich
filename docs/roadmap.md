1. 측정 레이어 (먼저 해야 할 것)
개선할 수 없는 것은 측정되지 않은 것. 현재는 signal_tracker에 리턴만 있고 시그널 품질 지표가 빈약함.

기능	설명	왜 먼저인가
Information Coefficient (IC) 추적	팩터별로 Spearman(factor_score, return_5d) 롤링 90일/180일	어떤 팩터가 진짜 예측력이 있는지 가시화. 현재 weight tuning은 conviction 전체만 보고 팩터별 기여도는 불명.
IC decay 곡선	1D/5D/20D IC를 시간 축에 그려 "이 신호는 며칠간 유효한가"	단타 팩터(catalyst_recency)와 중기 팩터(fundamentals)를 분리 관리
Hit rate × Payoff asymmetry	방향 맞춘 비율 × 평균 승/패 크기 → Kelly fraction 추정	컨빅션이 같아도 승률 높고 payoff 작은 신호 vs 반대 신호 구분
팩터 턴오버	신호 세트가 얼마나 자주 바뀌는지 (포트폴리오 turnover proxy)	거래비용 현실화 — IC 높아도 턴오버 너무 높으면 실전 수익 없음
구현: src/decision/signal_quality.py 신설 → factor_audit와 연동, dashboard에 IC panel 추가. ~반나절.

2. 견고성 (신뢰도 강화)
현재 tune_weights는 한 번의 grid search. 과적합 리스크 높음.

기능	설명
Walk-forward validation	tune_weights를 3개월 단위 rolling window로 평가. 단일 243 조합 grid 대신 "각 월별 최적 → 다음 월 OOS 성능" 검증
Purged K-fold (López de Prado 방식)	5D 리턴 라벨 겹침 문제 해결 → 5일 gap + embargo로 테스트셋 정보 누수 차단
Bayesian 가중치 shrinkage	샘플 <500개일 때 prior(동일 가중치)로 끌어당기기. 현재는 gradient만 보고 공격적으로 가중치 이동
Regime stability 테스트	risk_on/neutral/risk_off 외에 하위 regime도 고려. 현재 3-regime은 너무 coarse
Drift detection	Kolmogorov-Smirnov로 팩터 분포 변화 감지. 분포 이동 시 가중치 재학습 트리거
구현: src/decision/tune_weights.py 확장 + src/decision/drift_monitor.py 신설. ~1일.

3. 표현력 (비선형/상호작용)
현재는 선형 가중합 + regime multiplier. 팩터 간 상호작용이 표현 안 됨.

기능	설명
Meta-labeling	Stage 1: 방향 예측(현재 시스템). Stage 2: "이 신호를 받아야 하나?" 확률 모델. 낮은 확신도 시그널은 abstain → hit rate↑
Triple-barrier labeling	현재: 5D 후 리턴만 봄. 개선: 상단 +3%/하단 -2%/타임아웃 중 먼저 터치하는 것을 라벨로 → 실제 트레이딩 결과에 가까움
트리 기반 컨빅션	팩터 선형합 대신 gradient boosting(scikit-learn)으로 8팩터 → 컨빅션 매핑. "momentum 높을 때만 news_tone 의미있음" 같은 상호작용 포착
Ensemble disagreement = uncertainty	이미 ensemble 시스템 있음 → economy/standard 모델 간 불일치를 confidence band로 변환. 불일치 크면 컨빅션 할인
Conformal prediction	컨빅션에 예측 구간 부여 — "80% 확률로 5D 리턴 -3%~+5%". 불확실성 명시적으로 전달
구현: src/decision/meta_filter.py + XGBoost 실험. 현재 linear 시스템과 A/B 가능. ~2일.

4. 신규 정보원 (정보 우위 확보)
현재: 가격 + 뉴스 + SEC + 옵션 + macro. 많지만 정제 안 된 원료.

기능	설명
뉴스 감성 추세 미분	현재 news_tone은 당일 sentiment. 개선: 7일 롤링 감성 추세(slope) → 리스크 전환점 early warning
구조적 변화 감지	Change-point detection(CUSUM)으로 "이 종목의 펀더멘털 체제가 바뀌었는지" 감지 → 과거 팩터 무효화
Cross-asset leading indicator	반도체 ETF(SMH) 움직임이 개별 반도체 주식 3-5일 선행. lagged correlation 시그널 추가
거래량 프로파일 이상치	평소 대비 거래량 z-score. 옵션 거래량 vs 주가 상관도 — informed trading proxy
Options skew	put/call IV skew 변화 → tail risk pricing. 현재 put_call_ratio만 있는데 skew가 더 풍부
Peer relative momentum	이미 peer_candidates 있음 → 동종업계 대비 잔차 수익률(sector-neutral alpha) 팩터화
Analyst revision breadth	EPS/매출 상향조정 애널리스트 비율. Finnhub/FMP에서 무료
구현: 각 1-2개 팩터씩 src/decision/factors/ 아래 추가. 팩터당 반나절.

5. 실행 통합 (신호를 실제 수익으로)
현재는 시그널 = buy/watch/avoid 추천으로 끝. 포지션 사이징 연동 없음.

기능	설명
Conviction → 포지션 크기	Kelly fraction × (1/vol) × regime_multiplier → "이 종목에 portfolio 몇 %" 수치 출력
상관관계 기반 익스포저 캡	방금 구현한 correlation heatmap 활용 — 상관 0.7+ 쌍이 둘 다 buy면 둘 중 하나만 추천
거래비용 현실화	bid-ask spread + 슬리피지 모델 → conviction 임계값을 유동성(ADV)별로 차등
시그널 lifecycle 관리	entry signal vs exit signal 분리. "언제 buy" + "언제 익절/손절" 둘 다 기록 → 완전한 trade round-trip 성과
Stop-loss / target 자동화	triple-barrier 라벨과 동일한 로직 → 시그널 시점의 vol × 1.5 ATR 기반
Portfolio-level optimization	개별 conviction을 제약조건 하에 결합 (max weight, sector cap, beta target) → cvxpy 간단 LP
구현: src/decision/sizing.py + src/decision/lifecycle.py. ~2일.

우선순위 로드맵
Phase A — 즉시 실행 (측정 먼저) (1주)

팩터별 IC 추적 + 대시보드 IC 패널
Triple-barrier labeling 전환 (hit/stop/timeout)
Walk-forward + Purged K-fold validation

Phase B — 견고성 (1-2주)
4. Conformal prediction → conviction 구간
5. Drift detection → 가중치 재학습 트리거
6. Ensemble disagreement를 uncertainty로 활용

Phase C — 표현력 / 신호 확장 (2-4주)
7. Meta-labeling (2단계 필터)
8. Peer-relative momentum, analyst revision breadth 팩터
9. Options skew, 뉴스 추세 slope

Phase D — 실행 통합 (1-2주)
10. 포지션 사이징 + 상관관계 캡
11. 시그널 lifecycle (entry/exit 분리)
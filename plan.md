# pkrich v2 — 투자 의사결정 엔진 설계

> **핵심 전환**: 리서치 자동화 → 의사결정 엔진
>
> `데이터 → 분석 → 판단(decision) → 실행(timing/sizing) → 전략(portfolio/macro)`

---

## 우선순위 맵

| 등급 | 기능 | 핵심 가치 |
|------|------|-----------|
| **P0** | Decision Layer, Timing Engine, Market Regime | 이것만 있어도 실행 가능한 시스템 |
| **P1** | Position Sizing, Signal Quality, News Impact | 실행 품질 향상 |
| **P2** | Mega Trend Tracker, Factor Analysis, Theme Expansion, Risk Score, Strategy Comment, Auto Rebalance | 포트폴리오 레벨 고도화 |

---

## P0 — 핵심 의사결정 레이어

### 1. Decision Layer (결론 자동 생성)

**문제**: 데이터와 분석은 있으나 "지금 사야 하는가?"에 대한 판단이 없음

**기능**: 종목별 최종 결론을 구조화된 형태로 생성

```yaml
decision:
  ticker: "NVDA"
  action: buy | watch | avoid
  conviction: 0-100          # 확신도
  reason: "AI capex 사이클 수혜 + 실적 가속 구간"
  valid_until: "2025-04-20"  # 판단 유효 기간
```

**효과**: 리서치 결과물이 실행 가능한 정보로 전환됨

---

### 2. Timing Engine (진입/이탈 판단)

**문제**: 분석은 좋은데 "언제?"가 없음

**기능**: 기술적 데이터 기반 진입·이탈 레벨 자동 산출

```yaml
timing:
  ticker: "NVDA"
  entry_zone: [850, 880]     # 매수 구간
  breakout_level: 920        # 돌파 시 추격 매수 기준
  stop_loss: 810             # 손절 라인
  risk_reward_ratio: 2.8
  basis:                     # 산출 근거
    - ATR(14): 32.5
    - SMA50: 865
    - SMA200: 780
    - 52W_position: 0.82     # 0~1 (52주 내 위치)
    - RVOL: 1.4              # 상대 거래량
```

**효과**: "좋은 종목"에서 "좋은 타이밍"까지 커버

---

### 3. Market Regime (시장 상태 판단)

**문제**: 종목 판단은 있으나 매크로 환경 반영이 없음

**기능**: 현재 시장의 리스크 성향을 종합 판단

```yaml
market_regime:
  state: risk_on | neutral | risk_off
  confidence: 0-100
  drivers:
    rates: "10Y 하락 추세 → 위험자산 우호적"
    trend: "SPX > SMA50 > SMA200 → 상승 구조"
    volatility: "VIX 14.2 → 안정 구간"
    breadth: "A/D ratio 양호"
  implication: "성장주 비중 확대 유효"
```

**활용**: 전체 전략 방향의 앵커 역할. Decision/Timing 결과에 가중치 부여

---

## P1 — 실행 품질 향상

### 4. Position Sizing (포지션 사이징)

**문제**: 무엇을, 언제 살지는 알지만 "얼마나?"가 없음

**기능**: 변동성·확신도·상관관계 기반 비중 추천

```yaml
position_sizing:
  ticker: "NVDA"
  suggested_weight: 8%        # 포트폴리오 내 추천 비중
  max_risk_pct: 2%            # 최대 손실 허용 비율
  volatility_adjusted: true
  inputs:
    atr_pct: 3.8%
    conviction: 85
    correlation_to_portfolio: 0.72
```

---

### 5. Signal Quality (시그널 품질 평가)

**문제**: signal_tracker가 있지만 시그널의 신뢰도 평가가 없음

**기능**: 과거 시그널 성과 기반 품질 점수 산출

```yaml
signal_quality:
  strategy: "breakout_above_SMA50"
  win_rate: 62%
  avg_return: 4.2%
  avg_loss: -2.1%
  sharpe_like: 1.35
  sample_size: 48
  grade: A | B | C | D        # 종합 등급
```

**효과**: 좋은 시그널과 노이즈를 구분

---

### 6. News Impact (뉴스 영향력 분석)

**문제**: 뉴스는 수집하지만 중요도 판단이 없음

**기능**: 개별 뉴스의 투자 영향력을 구조화

```yaml
news_impact:
  headline: "NVDA, 차세대 Blackwell Ultra 발표"
  impact_score: 0-100
  type: earnings | macro | policy | product | rumor | insider
  direction: positive | negative | mixed
  expected_duration: short | mid | long
  affected_tickers: ["NVDA", "TSM", "AVGO"]
```

---

## P2 — 포트폴리오 레벨 고도화

### 7. Mega Trend Tracker (메가 트렌드 추적)

**기능**: 테마 단위로 모멘텀·자금흐름·뉴스톤을 종합

```yaml
trend_tracker:
  AI:       { momentum: bullish,  flow: inflow,  news_tone: positive }
  Energy:   { momentum: neutral,  flow: flat,    news_tone: mixed    }
  Quantum:  { momentum: bearish,  flow: outflow, news_tone: negative }
  Defense:  { momentum: bullish,  flow: inflow,  news_tone: positive }
```

**데이터**: 관련 종목 평균 수익률, 뉴스 감성, ETF 자금 흐름

---

### 8. Factor Analysis (퀀트 레이어)

**기능**: 종목별 멀티팩터 점수로 AI 분석과 퀀트 결합

```yaml
factors:
  ticker: "NVDA"
  momentum_score: 88     # 가격 모멘텀
  value_score: 35        # 밸류에이션
  quality_score: 91      # 수익성·재무건전성
  volatility_score: 52   # 변동성 (낮을수록 안정)
  composite: 72
```

---

### 9. Theme → Ticker Expansion (테마 → 종목 추천)

**기능**: 테마 키워드로부터 관련 종목을 자동 확장

```yaml
theme_expansion:
  AI_Infra:   [NVDA, AMD, AVGO, MRVL, TSM]
  AI_Software: [MSFT, CRM, PLTR, NOW]
  Defense:    [LMT, RTX, NOC, GD]
  Space:      [RKLB, LUNR, ASTS]
```

**효과**: watchlist 자동 확장, 테마 내 비교 분석 기반

---

### 10. Integrated Risk Score (리스크 통합 점수)

**기능**: 종목별 리스크를 단일 점수로 통합

```yaml
risk_score:
  ticker: "PLTR"
  total: 62
  breakdown:
    financial: 25       # 재무 리스크
    volatility: 78      # 변동성 리스크
    dilution: 45        # 희석 리스크
    macro: 30           # 매크로 민감도
    liquidity: 15       # 유동성 리스크
```

---

### 11. AI Strategy Comment (전략 코멘트)

**기능**: 하루 1회, 시장 상태 + 포트폴리오 상황을 종합한 전략 코멘트 생성

```yaml
strategy_comment:
  date: "2025-04-13"
  comment: >
    시장은 risk-on 전환 초입. AI/반도체 집중 전략 유효하나
    VIX 저점 구간이라 급등 시 부분 익절 고려.
    방산 섹터는 지정학 이벤트 대기 중 — watch 유지.
  key_changes:
    - "AMD: watch → buy (SMA50 돌파 확인)"
    - "KO: hold → trim (성장 대비 방어 비중 과다)"
```

---

### 12. Auto Rebalance Suggestion (리밸런싱 제안)

**기능**: 포트폴리오 상태 변화에 따른 비중 조정 제안

```yaml
rebalance:
  trigger: "AI 섹터 비중 45% → 목표 35% 초과"
  actions:
    increase: [{ ticker: "LMT", reason: "방산 저평가 + 지정학 모멘텀" }]
    decrease: [{ ticker: "NVDA", reason: "목표가 근접 + 비중 과다" }]
    hold:     [{ ticker: "MSFT", reason: "적정 비중 유지 중" }]
```

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────┐
│                    DATA LAYER                        │
│  yfinance · news API · macro indicators · SEC filings│
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                  ANALYSIS LAYER                      │
│  factor scores · signal detection · news sentiment   │
│  trend tracking · risk calculation                   │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                 DECISION LAYER (P0)                   │
│  market_regime → decision → timing                   │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                 EXECUTION LAYER (P1)                  │
│  position_sizing · signal_quality · news_impact      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│                 STRATEGY LAYER (P2)                   │
│  trend_tracker · rebalance · strategy_comment        │
│  theme_expansion · risk_score · factor_analysis      │
└─────────────────────────────────────────────────────┘
```

---

## 구현 로드맵

| 단계 | 기능 | 의존성 | 예상 작업량 |
|------|------|--------|-------------|
| **Phase 1** | Market Regime + Decision | 기존 데이터 파이프라인 | 1~2주 |
| **Phase 2** | Timing Engine | Phase 1 + 기술적 지표 계산 | 1주 |
| **Phase 3** | Position Sizing + Signal Quality | Phase 1~2 + 백테스트 데이터 | 1~2주 |
| **Phase 4** | News Impact | 뉴스 API + 감성 분석 | 1주 |
| **Phase 5** | P2 전체 | Phase 1~4 완료 | 2~3주 |
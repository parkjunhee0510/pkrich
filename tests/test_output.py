from __future__ import annotations

import csv
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from src.output.json_export import _serialize_analysis, write_json_outputs
from src.output.markdown import append_price_history, render_daily_markdown, render_ticker_markdown
from src.types import NewsItem, PortfolioPosition, PortfolioSummary, TickerAnalysis, TickerDecision


def _sample_analysis() -> TickerAnalysis:
    return TickerAnalysis(
        ticker='AAPL',
        name='Apple Inc.',
        date='2026-04-08',
        summary='샘플 요약입니다.',
        key_news=[
            '애플 실적이 예상치를 웃돌았습니다.',
            '애플의 신제품 기대감이 이어지고 있습니다.',
            '애플이 SEC에 분기 실적 관련 보고서를 제출했습니다.',
            '애플의 오래된 기사입니다.',
        ],
        news_references=[
            NewsItem(
                title='Apple earnings beat expectations',
                source='Reuters',
                published_at='2026-04-08',
                link='https://example.com/apple-earnings',
            ),
            NewsItem(
                title='Apple product preview gains attention',
                source='Yahoo Finance',
                published_at='2026-04-07',
                link='https://example.com/apple-preview',
            ),
            NewsItem(
                title='[실적] Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출',
                source='SEC EDGAR',
                published_at='2026-04-06',
                link='https://example.com/apple-sec-10q',
            ),
            NewsItem(
                title='Apple legacy milestone feature',
                source='Reuters',
                published_at='2025-01-30',
                link='https://example.com/apple-old',
            ),
        ],
        financial_highlights=['시가총액: 1.00T', '최근 12개월 PER: 25.00'],
        risks_or_watchpoints=['경쟁 심화 여부 점검'],
        signal_or_takeaway='관찰 지속',
        data_snapshot={
            'Price': '100.00 USD',
            'Daily Change': '+1.23%',
            'Market Cap': '1.00T',
            'Trailing P/E': '25.00',
            'EPS': '6.10',
            '52W High': '110.00',
            '52W Low': '80.00',
            '50D SMA': '98.50',
            '200D SMA': '95.10',
            'Volume': '12.30M',
            '3M Avg Volume': '18.50M',
            'Price/Book': '8.50',
            'Dividend Yield': '0.45%',
            'Sector': 'Technology',
        },
        fundamentals={
            'market_cap': '1.00T',
            'trailing_pe': '25.00',
            'eps': '6.10',
            'forward_eps': '6.80',
            'earnings_growth': '+12.40% YoY',
            'price_to_book': '8.50',
            'dividend_yield': '0.45%',
            'volume': '12.30M',
            'avg_volume_3m': '18.50M',
            '52w_high': '110.00',
            '52w_low': '80.00',
            'short_float_pct': '3.20%',
            'short_ratio': '2.10일',
            'analyst_target_price': '130.00 USD',
            'analyst_recommendation': 'Buy',
            'analyst_count': '18명',
            'held_by_insiders': '0.07%',
            'held_by_institutions': '61.30%',
            'implied_volatility': '28.40%',
        },
        price_action={
            'atr_14d': '5.23',
            'atr_percent': '2.02%',
            'relative_volume': '1.42x',
            'gap_percent': '+0.80%',
            'price_vs_sma50': '+3.20%',
            'price_vs_sma200': '+8.10%',
            'week52_position': '73%',
            'rs_vs_spy': '+4.10%',
        },
        quarterly_financials=[
            {'quarter': '2025-Q4', 'revenue': '120.00B', 'operating_income': '35.00B', 'eps': '2.10', 'estimated_eps': '2.00', 'surprise_pct': '+5.00%', 'beat_miss': 'beat'},
            {'quarter': '2025-Q3', 'revenue': '118.00B', 'operating_income': '33.00B', 'eps': '1.98', 'estimated_eps': '2.05', 'surprise_pct': '-3.41%', 'beat_miss': 'in-line'},
            {'quarter': '2025-Q2', 'revenue': '115.00B', 'operating_income': '31.00B', 'eps': '1.90', 'estimated_eps': '2.05', 'surprise_pct': '-7.32%', 'beat_miss': 'miss'},
            {'quarter': '2025-Q1', 'revenue': '110.00B', 'operating_income': '30.00B', 'eps': '1.80', 'estimated_eps': '1.82', 'surprise_pct': '-1.10%', 'beat_miss': 'in-line'},
            {'quarter': '2024-Q4', 'revenue': '100.00B', 'operating_income': '30.00B', 'eps': '1.80', 'estimated_eps': '1.75', 'surprise_pct': '+2.86%', 'beat_miss': 'in-line'},
            {'quarter': '2024-Q3', 'revenue': '98.00B', 'operating_income': '28.00B', 'eps': '1.70', 'estimated_eps': '1.66', 'surprise_pct': '+2.41%', 'beat_miss': 'in-line'},
        ],
        upcoming_events=[
            {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-14', 'days_until': '6', 'timing': 'AMC'},
        ],
        news_tone={'label': 'bullish', 'score': 1.0},
        trade_frame={
            'entry_price': '현재가 $100.50 또는 SMA50 $98.50 눌림 시',
            'stop_loss': 'SMA50 $98.50',
            'target_1': '$105.00 (1.5×ATR)',
            'target_2': '애널리스트 목표 $120.00',
            'risk_reward_ratio': '2.3R',
            'position_size_note': '$10,000 계좌 1% 리스크 기준 약 30주',
            'bull_scenario': '실적 beat와 거래량 확대가 이어지면 상단 돌파를 시도할 수 있습니다.',
            'base_scenario': '실적 전까지 현재 구간에서 방향성 탐색이 이어질 가능성이 큽니다.',
            'bear_scenario': '50일선 이탈 시 단기 조정 압력이 커질 수 있습니다.',
            'invalidation_price': '50일 이동평균선인 98.50 USD 하향 이탈 시',
            'watch_period': '2026-04-14 실적 발표 전까지',
        },
        options_summary={
            'expiry': '2026-05-15',
            'atm_call_iv': '28.5%',
            'atm_put_iv': '30.1%',
            'put_call_ratio': '0.72',
            'iv_percentile_30d': '68%',
            'tone': 'bullish',
            'unusual_activity': 'CALL $270, vol 8200, OI ?? 42%',
            'oi_change': '? OI +25.0% / ? OI +16.7%',
        },
    )


def _sample_committee_analysis() -> dict[str, object]:
    return {
        'status': 'deep_reviewed',
        'agreement_status': 'mixed',
        'deep_review_triggered': True,
        'deep_review_reasons': ['pm_low_confidence', 'risk_strong_objection'],
        'roles': {
            'growth_analyst': {
                'role': 'growth_analyst',
                'round': 'economy',
                'profile': 'economy',
                'stance': 'buy',
                'action': 'buy',
                'confidence': 0.62,
                'strong_objection': False,
                'summary': 'Growth remains healthy.',
                'valid': True,
                'invalid_reason': '',
            },
            'value_skeptic': {
                'role': 'value_skeptic',
                'round': 'economy',
                'profile': 'economy',
                'stance': 'watch',
                'action': 'watch',
                'confidence': 0.58,
                'strong_objection': False,
                'summary': 'Valuation still looks stretched.',
                'valid': True,
                'invalid_reason': '',
            },
            'risk_manager': {
                'role': 'risk_manager',
                'round': 'deep',
                'profile': 'deep',
                'stance': 'reduce',
                'action': 'avoid',
                'confidence': 0.74,
                'strong_objection': True,
                'summary': 'Risk remains elevated around the event window.',
                'valid': True,
                'invalid_reason': '',
            },
            'macro_strategist': {
                'role': 'macro_strategist',
                'round': 'deep',
                'profile': 'deep',
                'stance': 'avoid',
                'action': 'avoid',
                'confidence': 0.77,
                'strong_objection': False,
                'summary': 'Macro backdrop is still fragile.',
                'valid': True,
                'invalid_reason': '',
            },
            'pm': {
                'role': 'pm',
                'round': 'deep',
                'profile': 'deep',
                'stance': 'buy',
                'action': 'buy',
                'confidence': 0.68,
                'strong_objection': False,
                'summary': 'Net view remains constructive with risk controls.',
                'valid': True,
                'invalid_reason': '',
            },
        },
    }


class OutputTests(unittest.TestCase):
    def test_render_daily_markdown_includes_key_sections_and_schedule(self) -> None:
        content = render_daily_markdown(
            [_sample_analysis()],
            date(2026, 4, 8),
            market_overview=[{'label': 'S&P 500', 'symbol': '^GSPC', 'price': '5,234.18', 'change': '+0.45%'}],
            decisions=[
                TickerDecision(
                    ticker='AAPL',
                    action='buy',
                    conviction=74,
                    reason='실적 전 추세와 모멘텀이 유지됩니다.',
                    valid_until='2026-04-14',
                    factors={'momentum': 12, 'earnings_pattern': 8, 'regime_adjustment': -2},
                )
            ],
            portfolio_summary=PortfolioSummary(
                positions=[
                    PortfolioPosition(
                        ticker='AAPL',
                        shares=10,
                        avg_cost=90.0,
                        currency='USD',
                        market_price=100.0,
                        market_value=1000.0,
                        cost_basis=900.0,
                        unrealized_pnl=100.0,
                        unrealized_return_pct=11.11,
                    )
                ],
                total_market_value=1000.0,
                total_cost_basis=900.0,
                total_unrealized_pnl=100.0,
                total_unrealized_return_pct=11.11,
            ),
        )

        self.assertIn('# 일일 리서치 - 2026-04-08', content)
        self.assertIn('## TL;DR', content)
        self.assertIn('- AAPL: 우선 실행 · 확신도 74 · 실적 전 추세와 모멘텀이 유지됩니다.', content)
        self.assertIn('- 일정 체크: AAPL 실적 발표 2026-04-14 (D-6 · AMC)', content)
        self.assertIn('## 시장 개요', content)
        self.assertIn('## 포트폴리오 현황', content)
        self.assertIn('## 주요 뉴스 링크', content)
        self.assertIn('## SEC 공시', content)
        self.assertIn('## 다가오는 일정', content)
        self.assertNotIn('## 주요 움직임', content)
        self.assertIn('**AAPL** 실적 발표: 2026-04-14 (D-6 · AMC)', content)
        self.assertIn('**AAPL** [실적] [Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출](https://example.com/apple-sec-10q) (2026-04-06)', content)

    def test_serialize_analysis_includes_earnings_pattern(self) -> None:
        serialized = _serialize_analysis(_sample_analysis(), {})
        self.assertIn('earnings_pattern', serialized)
        self.assertIn('peer_rank', serialized)
        self.assertIn('analysis_consensus', serialized)
        self.assertIn('committee_analysis', serialized)
        self.assertEqual(serialized['earnings_pattern']['beat_streak'], 1)
        self.assertEqual(serialized['earnings_pattern']['surprise_trend'], 'improving')
        self.assertEqual(serialized['earnings_pattern']['avg_surprise_pct'], '-1.7%')
        self.assertEqual(serialized['options_summary']['tone'], 'bullish')
        self.assertIn('CALL $270', serialized['options_summary']['unusual_activity'])

    def test_serialize_analysis_includes_committee_analysis_payload(self) -> None:
        analysis = TickerAnalysis(**{**_sample_analysis().__dict__, 'committee_analysis': _sample_committee_analysis()})

        serialized = _serialize_analysis(analysis, {})

        self.assertEqual(serialized['committee_analysis']['status'], 'deep_reviewed')
        self.assertEqual(serialized['committee_analysis']['agreement_status'], 'mixed')
        self.assertEqual(serialized['committee_analysis']['deep_review_reasons'], ['pm_low_confidence', 'risk_strong_objection'])
        self.assertEqual(serialized['committee_analysis']['roles']['pm']['summary'], 'Net view remains constructive with risk controls.')

    def test_serialize_analysis_maps_decision_ensemble_agreement(self) -> None:
        analysis = _sample_analysis()
        analysis = TickerAnalysis(**{**analysis.__dict__, 'analysis_consensus': {'status': 'conflicted'}})
        serialized = _serialize_analysis(
            analysis,
            {},
            decision=TickerDecision(
                ticker='AAPL',
                action='watch',
                conviction=55,
                reason='테스트',
                valid_until='2026-04-15',
                factors={},
            ),
        )
        self.assertEqual(serialized['decision']['ensemble_agreement'], 'conflict')

    def test_serialize_analysis_includes_decision_confidence_shadow_fields(self) -> None:
        analysis = _sample_analysis()
        serialized = _serialize_analysis(
            analysis,
            {},
            decision=TickerDecision(
                ticker='AAPL',
                action='buy',
                conviction=74,
                raw_conviction=81,
                reason='테스트',
                valid_until='2026-04-15',
                factors={},
                confidence_meta={'confidence_gate': 0.75, 'data_quality': 0.9},
            ),
        )

        self.assertEqual(serialized['decision']['raw_conviction'], 81)
        self.assertEqual(
            serialized['decision']['confidence_meta'],
            {'confidence_gate': 0.75, 'data_quality': 0.9},
        )

    def test_serialize_analysis_omits_confidence_shadow_fields_when_empty(self) -> None:
        analysis = _sample_analysis()
        serialized = _serialize_analysis(
            analysis,
            {},
            decision=TickerDecision(
                ticker='AAPL',
                action='buy',
                conviction=74,
                raw_conviction=81,
                reason='테스트',
                valid_until='2026-04-15',
                factors={},
            ),
        )

        self.assertNotIn('raw_conviction', serialized['decision'])
        self.assertNotIn('confidence_meta', serialized['decision'])

    def test_write_json_outputs_preserves_decision_confidence_shadow_fields_in_dashboard_history(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_path = Path(temp_dir)
            output_root = temp_path / 'output'
            (output_root / 'data').mkdir(parents=True, exist_ok=True)

            write_json_outputs(
                [_sample_analysis()],
                date(2026, 4, 8),
                output_root=output_root,
                decisions=[
                    TickerDecision(
                        ticker='AAPL',
                        action='buy',
                        conviction=74,
                        raw_conviction=81,
                        reason='confidence shadow',
                        valid_until='2026-04-15',
                        factors={'momentum': 12.0},
                        confidence_meta={
                            'confidence_gate': 0.75,
                            'data_quality': 0.9,
                            'evidence_coverage': 0.8,
                            'evidence_consistency': 0.7,
                            'model_agreement': 0.85,
                        },
                    )
                ],
            )

            payload = json.loads((output_root / 'data' / 'dashboard_history.json').read_text(encoding='utf-8'))
            decision = payload['days'][0]['tickers'][0]['decision']

            self.assertEqual(decision['conviction'], 74)
            self.assertEqual(decision['raw_conviction'], 81)
            self.assertEqual(
                decision['confidence_meta'],
                {
                    'confidence_gate': 0.75,
                    'data_quality': 0.9,
                    'evidence_coverage': 0.8,
                    'evidence_consistency': 0.7,
                    'model_agreement': 0.85,
                },
            )

    def test_render_ticker_markdown_includes_period_quarterly_events_and_timeline(self) -> None:
        content = render_ticker_markdown(
            TickerAnalysis(**{**_sample_analysis().__dict__, 'committee_analysis': _sample_committee_analysis()}),
            period_changes={'7d': '+3.25%', '30d': '+8.10%'},
            recent_timeline=[
                {
                    'date': '2026-04-08',
                    'signal_or_takeaway': '관찰 지속',
                    'top_news_summary': '애플 관련 핵심 뉴스 요약',
                }
            ],
        )

        self.assertIn('## 최근 변화 비교', content)
        self.assertIn('- 7일 변화: +3.25%', content)
        self.assertIn('- 뉴스 톤: bullish (6.0 / 10)', content)
        self.assertIn('| ATR(14) | 5.23 (2.02%) |', content)
        self.assertIn('| Relative Volume | 1.42x |', content)
        self.assertIn('| 공매도 | 3.20% float (커버 2.10일) |', content)
        self.assertIn('| 애널리스트 | Buy (18명, 목표 130.00 USD) |', content)
        self.assertIn('| 기관 보유 | 61.30% |', content)
        self.assertIn('| 옵션 IV | 28.40% |', content)
        self.assertIn('## 포지셔닝 데이터', content)
        self.assertIn('- 공매도: 3.20% float (커버 2.10일)', content)
        self.assertIn('- 애널리스트: Buy (18명, 목표 130.00 USD)', content)
        self.assertIn('## 실적 셋업 요약', content)
        self.assertIn('| Forward vs TTM | 최근 분기 결과 | 다음 실적 D-day | EPS 성장률 |', content)
        self.assertIn('| +11.48% (위) | +5.00% / ✅ beat | D-6 · AMC | +12.40% YoY |', content)
        self.assertIn('| 6.80 USD/share vs 6.10 USD/share | 컨센서스 EPS 2.00 USD/share | 2026-04-14 실적 발표 (D-6 · AMC) | YoY 기준 이익 성장 체력 |', content)
        self.assertIn('## 실적 컨센서스 디테일', content)
        self.assertIn('- Forward EPS: 6.80 USD/share', content)
        self.assertIn('- TTM EPS: 6.10 USD/share', content)
        self.assertIn('- Forward vs TTM: +11.48% (위)', content)
        self.assertIn('- EPS 성장률: +12.40% YoY', content)
        self.assertIn('- 최근 분기 추정 EPS: 2.00 USD/share', content)
        self.assertIn('- 최근 분기 서프라이즈: +5.00% / ✅ beat', content)
        self.assertIn('- 다음 실적 체크포인트: 2026-04-14 실적 발표 (D-6 · AMC)', content)
        self.assertIn('## 최근 4분기 재무', content)
        self.assertIn('| 2025-Q4 | 120.00B USD (+20.0% YoY) | 35.00B USD (+16.7% YoY) | 2.10 USD/share (+16.7% YoY) | 2.00 USD/share | +5.00% | ✅ beat |', content)
        self.assertIn('## 위원회 분석', content)
        self.assertIn('- 합의 상태: mixed', content)
        self.assertIn('- 딥 리뷰: triggered · pm_low_confidence, risk_strong_objection', content)
        self.assertIn('- Growth Analyst: Growth remains healthy. [buy]', content)
        self.assertIn('- Risk Manager: Risk remains elevated around the event window. [reduce]', content)
        self.assertIn('- PM: Net view remains constructive with risk controls. [buy]', content)
        self.assertIn('## 다가오는 일정', content)
        self.assertIn('실적 발표: 2026-04-14 (D-6 · AMC)', content)
        self.assertIn('## 최근 타임라인', content)
        self.assertIn('2026-04-08: 관찰 지속 | 애플 관련 핵심 뉴스 요약', content)
        self.assertIn('## 트레이드 프레임', content)
        self.assertIn('- **Bull**: 실적 beat와 거래량 확대가 이어지면 상단 돌파를 시도할 수 있습니다.', content)
        self.assertIn('- **무효화**: 50일 이동평균선인 98.50 USD 하향 이탈 시', content)
        self.assertIn('| 거래량 | 12.30M 주 |', content)
        self.assertIn('| 3개월 평균 거래량 | 18.50M 주 |', content)
        self.assertIn('| EPS (TTM) | 6.10 USD/share |', content)
        self.assertIn('| 52주 최고 | 110.00 USD |', content)
        self.assertNotIn('Apple legacy milestone feature', content)
        self.assertLess(content.find('Apple earnings beat expectations'), content.find('Apple product preview gains attention'))

    def test_render_ticker_markdown_drops_empty_original_news_details_block(self) -> None:
        analysis = _sample_analysis()
        analysis = TickerAnalysis(
            **{
                **analysis.__dict__,
                'key_news': ['요약만 남는 뉴스입니다.'],
                'news_references': [NewsItem(title='   ', source='', published_at='', link='')],
            }
        )

        content = render_ticker_markdown(analysis)

        self.assertIn('- 요약만 남는 뉴스입니다.', content)
        self.assertNotIn('<summary>원문 보기</summary>', content)

    def test_render_ticker_markdown_shows_committee_section_when_missing_payload(self) -> None:
        content = render_ticker_markdown(_sample_analysis())

        self.assertIn('## 위원회 분석', content)
        self.assertIn('- 합의 상태: N/A', content)
        self.assertIn('- 딥 리뷰: 없음', content)
        self.assertIn('- 역할 요약: 데이터 없음', content)

    def test_append_price_history_replaces_same_day_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'price_history.csv'
            append_price_history(csv_path, [_sample_analysis()])
            append_price_history(csv_path, [_sample_analysis()])
            with csv_path.open('r', encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['ticker'], 'AAPL')

    def test_write_json_outputs_writes_dashboard_price_history_and_timeline(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_path = Path(temp_dir)
            output_root = temp_path / 'output'
            data_dir = output_root / 'data'
            web_data_dir = temp_path / 'web' / 'public' / 'output' / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            (temp_path / 'web').mkdir(parents=True, exist_ok=True)
            (data_dir / 'price_history.csv').write_text(
                '\n'.join(
                    [
                        'date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low',
                        '2026-03-31,AAPL,95.00 USD,+0.50%,1.00T,25.00,6.10,110.00,80.00',
                        '2026-04-08,AAPL,100.00 USD,+1.23%,1.00T,25.00,6.10,110.00,80.00',
                    ]
                ),
                encoding='utf-8',
            )

            original_emit_legacy = os.environ.get('EMIT_LEGACY_DASHBOARD')
            os.environ['EMIT_LEGACY_DASHBOARD'] = '1'
            try:
                timelines = write_json_outputs(
                    [_sample_analysis()],
                    date(2026, 4, 8),
                    market_overview=[{'label': 'S&P 500', 'symbol': '^GSPC', 'price': '5,234.18', 'change': '+0.45%'}],
                    output_root=output_root,
                    period_changes_by_ticker={'AAPL': {'7d': '+3.25%', '30d': 'N/A'}},
                    portfolio_risk={
                        'hhi': 2550.0,
                        'portfolio_beta': 1.18,
                        'correlation_matrix': {'AAPL': {'AAPL': 1.0}},
                        'mdd_20d': 6.2,
                        'var_95': 2.4,
                        'risk_grade': 'C',
                        'recommendations': ['기술 섹터 비중을 점검하세요.'],
                        'positions_by_weight': [],
                    },
                    portfolio_summary=PortfolioSummary(
                        positions=[
                            PortfolioPosition(
                                ticker='AAPL',
                                shares=10,
                                avg_cost=90.0,
                                currency='USD',
                                market_price=100.0,
                                market_value=1000.0,
                                cost_basis=900.0,
                                unrealized_pnl=100.0,
                                unrealized_return_pct=11.11,
                            )
                        ],
                        total_market_value=1000.0,
                        total_cost_basis=900.0,
                        total_unrealized_pnl=100.0,
                        total_unrealized_return_pct=11.11,
                    ),
                    weekly_summary=SimpleNamespace(
                        iso_year=2026,
                        iso_week=15,
                        start_date='2026-04-06',
                        end_date='2026-04-08',
                        trading_days=3,
                        weekly_insight='주간 요약',
                        weekly_report={
                            'headline': '2026-W15 주간 리포트',
                            'summary': '구조화된 주간 리포트입니다.',
                            'market_environment': {'summary': '중립', 'details': ['VIX 안정']},
                            'top_movers': {'summary': '핵심 이동 종목', 'items': []},
                            'signal_review': {'summary': '시그널 리뷰', 'details': []},
                            'risk_points': {'summary': '리스크', 'items': []},
                            'next_week_action_plan': {'summary': '액션 플랜', 'items': []},
                            'portfolio_suggestions': {'summary': '포트폴리오 제안', 'items': []},
                        },
                    ),
                )
            finally:
                if original_emit_legacy is None:
                    os.environ.pop('EMIT_LEGACY_DASHBOARD', None)
                else:
                    os.environ['EMIT_LEGACY_DASHBOARD'] = original_emit_legacy

            dashboard = json.loads((web_data_dir / 'dashboard.json').read_text(encoding='utf-8'))
            dashboard_history = json.loads((web_data_dir / 'dashboard_history.json').read_text(encoding='utf-8'))
            price_history = json.loads((web_data_dir / 'price_history.json').read_text(encoding='utf-8'))
            timeline = json.loads((web_data_dir / 'ticker_timelines.json').read_text(encoding='utf-8'))

            self.assertIn('AAPL', timelines)
            self.assertEqual(len(dashboard['days']), 1)
            self.assertEqual(len(dashboard_history['days']), 1)
            self.assertEqual(dashboard['days'][0]['portfolio_summary']['positions'][0]['ticker'], 'AAPL')
            self.assertEqual(dashboard['days'][0]['portfolio_risk']['risk_grade'], 'C')
            self.assertEqual(dashboard['days'][0]['portfolio_risk']['hhi'], 2550.0)
            self.assertEqual(dashboard['days'][0]['pm_view']['as_of'], '2026-04-08')
            self.assertEqual(dashboard['days'][0]['pm_view']['swap_candidates'], [])
            self.assertEqual(dashboard['days'][0]['pm_view']['event_exposure_items'][0]['ticker'], 'AAPL')
            self.assertGreaterEqual(
                dashboard['days'][0]['pm_view']['today_priority_queue'][0]['today_priority_score'],
                dashboard['days'][0]['pm_view']['today_priority_queue'][-1]['today_priority_score'],
            )
            self.assertEqual(dashboard_history['days'][0]['portfolio_summary']['positions'][0]['ticker'], 'AAPL')
            self.assertEqual(dashboard_history['days'][0]['pm_view']['as_of'], '2026-04-08')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['period_changes']['7d'], '+3.25%')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['news_tone']['label'], 'bullish')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['earnings_setup']['forward_eps'], '6.80 USD/share')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['earnings_setup']['forward_vs_ttm'], '+11.48%')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['price_action']['relative_volume'], '1.42x')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['fundamentals']['short_float_pct'], '3.20%')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['fundamentals']['analyst_target_price'], '130.00 USD')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['trade_frame']['watch_period'], '2026-04-14 실적 발표 전까지')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['upcoming_events'][0]['label'], '실적 발표')
            self.assertEqual(dashboard['weekly_summary']['weekly_report']['headline'], '2026-W15 주간 리포트')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['sec_filing_tags'], ['실적'])
            self.assertEqual(dashboard['days'][0]['tickers'][0]['sec_filings'][0]['tag'], '실적')
            self.assertEqual(dashboard['days'][0]['tickers'][0]['sec_filings'][0]['form_type'], '10-Q')
            self.assertEqual(
                dashboard['days'][0]['tickers'][0]['sec_filings'][0]['title'],
                'Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출',
            )
            self.assertEqual(price_history[-1]['ticker'], 'AAPL')
            self.assertEqual(timeline['AAPL'][0]['top_news_summary'], '애플 실적이 예상치를 웃돌았습니다.')
            with (data_dir / 'price_history.csv').open('r', encoding='utf-8', newline='') as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 2)

    def test_write_json_outputs_reconciles_history_snapshot_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_path = Path(temp_dir)
            output_root = temp_path / 'output'
            data_dir = output_root / 'data'
            web_data_dir = temp_path / 'web' / 'public' / 'output' / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            (temp_path / 'web').mkdir(parents=True, exist_ok=True)

            history_payload = {
                'days': [
                    {
                        'date': '2026-04-10',
                        'market_overview': [],
                        'tickers': [
                            {
                                'ticker': 'AAPL',
                                'name': 'Apple Inc.',
                                'date': '2026-04-10',
                                'summary': 'Apple은 999.99 USD (+9.99%)로 거래 중입니다.',
                                'key_news': [],
                                'news_references': [],
                                'financial_highlights': [],
                                'risks_or_watchpoints': [],
                                'signal_or_takeaway': '관찰',
                                'data_snapshot': {
                                    'Price': '999.99 USD',
                                    'Daily Change': '+9.99%',
                                    'Open': '999.99',
                                    'High': '999.99',
                                    'Low': '999.99',
                                    'Close': '999.99',
                                    'Volume': '9.99M',
                                },
                                'fundamentals': {},
                                'earnings_setup': {},
                                'earnings_surprise_history': [],
                                'price_action': {},
                                'quarterly_financials': [],
                                'upcoming_events': [],
                                'news_tone': {'label': 'neutral', 'score': 0.0},
                                'trade_frame': {},
                                'options_summary': {},
                                'signal_history': [],
                                'sector_comparison': {},
                                'valuation_score': {},
                                'period_changes': {'7d': 'N/A', '30d': 'N/A'},
                                'sec_filing_tags': [],
                                'sec_filings': [],
                            }
                        ],
                    }
                ],
                'signal_stats': {},
                'weekly_summary': {},
            }
            (data_dir / 'dashboard_history.json').write_text(
                json.dumps(history_payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            (data_dir / 'price_history.csv').write_text(
                '\n'.join(
                    [
                        'date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low',
                        '2026-04-10,AAPL,250.75 USD,+1.25%,1.00T,25.00,6.10,110.00,80.00',
                        '2026-04-13,AAPL,100.00 USD,+1.23%,1.00T,25.00,6.10,110.00,80.00',
                    ]
                ),
                encoding='utf-8',
            )

            sqlite_path = data_dir / 'price_history.sqlite'
            connection = sqlite3.connect(sqlite_path)
            try:
                connection.execute(
                    'create table prices (date text, ticker text, open text, high text, low text, close text, volume text, price text, daily_change text)'
                )
                connection.execute(
                    'insert into prices values (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    ('2026-04-10', 'AAPL', '250.10', '251.00', '249.50', '250.75', '11.20M', '250.75 USD', '+1.25%'),
                )
                connection.execute(
                    'insert into prices values (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    ('2026-04-13', 'AAPL', '99.50', '100.50', '98.90', '100.00', '12.30M', '100.00 USD', '+1.23%'),
                )
                connection.commit()
            finally:
                connection.close()

            write_json_outputs(
                [_sample_analysis()],
                date(2026, 4, 13),
                market_overview=[],
                output_root=output_root,
            )

            repaired = json.loads((data_dir / 'dashboard_history.json').read_text(encoding='utf-8'))
            repaired_day = next(day for day in repaired['days'] if day['date'] == '2026-04-10')
            repaired_ticker = next(t for t in repaired_day['tickers'] if t['ticker'] == 'AAPL')
            self.assertEqual(repaired_ticker['summary'], 'Apple은 250.75 USD (+1.25%)로 거래 중입니다.')
            self.assertEqual(repaired_ticker['data_snapshot']['Price'], '250.75 USD')
            self.assertEqual(repaired_ticker['data_snapshot']['Daily Change'], '+1.25%')
            self.assertEqual(repaired_ticker['data_snapshot']['Open'], '250.10')
            self.assertEqual(repaired_ticker['data_snapshot']['Close'], '250.75')
            self.assertTrue((web_data_dir / 'dashboard_history.json').exists())

    def test_write_json_outputs_rebuilds_price_history_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_path = Path(temp_dir)
            output_root = temp_path / 'output'
            data_dir = output_root / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            (temp_path / 'web').mkdir(parents=True, exist_ok=True)

            (data_dir / 'price_history.csv').write_text(
                '\n'.join(
                    [
                        'date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low,open,high,low,close,volume',
                        '2026-04-10,AAPL,999.99 USD,+9.99%,1.00T,25.00,6.10,110.00,80.00,999.99,999.99,999.99,999.99,9.99M',
                        '2026-04-11,AAPL,998.99 USD,+8.99%,1.00T,25.00,6.10,110.00,80.00,998.99,998.99,998.99,998.99,8.99M',
                    ]
                ),
                encoding='utf-8',
            )
            sqlite_path = data_dir / 'price_history.sqlite'
            connection = sqlite3.connect(sqlite_path)
            try:
                connection.execute(
                    'create table prices (date text, ticker text, open text, high text, low text, close text, volume text, price text, daily_change text, market_cap text, trailing_pe text, eps text, high_52w text, low_52w text)'
                )
                connection.execute(
                    'insert into prices values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    ('2026-04-10', 'AAPL', '250.10', '251.00', '249.50', '250.75', '11.20M', '250.75 USD', '+1.25%', '1.00T', '25.00', '6.10', '110.00', '80.00'),
                )
                connection.execute(
                    'insert into prices values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    ('2026-04-13', 'AAPL', '99.50', '100.50', '98.90', '100.00', '12.30M', '100.00 USD', '+1.23%', '1.00T', '25.00', '6.10', '110.00', '80.00'),
                )
                connection.commit()
            finally:
                connection.close()

            write_json_outputs(
                [_sample_analysis()],
                date(2026, 4, 13),
                market_overview=[],
                output_root=output_root,
            )

            json_rows = json.loads((data_dir / 'price_history.json').read_text(encoding='utf-8'))
            with (data_dir / 'price_history.csv').open('r', encoding='utf-8', newline='') as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(json_rows), 2)
            self.assertEqual(len(csv_rows), 2)
            self.assertEqual(json_rows[0]['date'], '2026-04-10')
            self.assertEqual(json_rows[0]['price'], '250.75 USD')
            self.assertEqual(json_rows[1]['date'], '2026-04-13')
            self.assertEqual(csv_rows[0]['price'], '250.75 USD')
            self.assertEqual(csv_rows[1]['date'], '2026-04-13')


if __name__ == '__main__':
    unittest.main()

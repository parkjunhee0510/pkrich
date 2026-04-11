from __future__ import annotations

import json
import unittest

from src.analyzer.research_note import _parse_and_validate_response, _response_schema
from src.types import WatchlistItem


def _watchlist() -> list[WatchlistItem]:
    return [WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology')]


def _valid_entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        'ticker': 'AAPL',
        'summary': '애플은 195.20 USD 부근에서 50일선 위를 유지하고 있으며 RVOL 1.40x로 단기 수급이 살아 있습니다. 2026-04-30 실적 발표 전까지 가이던스와 195.00 USD 지지 확인이 핵심입니다.',
        'key_news': ['10-Q 공시 제출, 실적 수치 재확인 필요'],
        'financial_highlights': ['영업이익률 30.2%로 전년 대비 +1.8%p 개선됐습니다.'],
        'risks_or_watchpoints': ['SMA50 190.50 USD 하향 이탈 시 단기 추세 약화로 해석합니다.'],
        'signal_or_takeaway': '매수 관찰 — 실적 기대 유지 | 진입존 192.00-197.00 / 무효화 190.50 USD',
        'news_tone': {
            'label': 'bullish',
            'confidence': 4,
            'reasoning': '실적 기대와 기술적 지지가 함께 확인됩니다.',
        },
        'trade_frame': {
            'entry_price': '현재가 $195.20 또는 SMA50 $190.50 눌림 시',
            'stop_loss': 'SMA50 $190.50 USD',
            'target_1': '$200.00 (1.5×ATR)',
            'target_2': '애널리스트 목표 $215.00',
            'risk_reward_ratio': '1.5R (target_1 기준)',
            'position_size_note': '$10,000 계좌 1% 리스크 기준 약 30주 (ATR $3.20 기반)',
            'bull_scenario': '실적 beat와 거래량 확대가 겹치면 205.00 USD 저항 재시험 가능성이 있습니다.',
            'base_scenario': '실적 전까지 192.00-200.00 USD 범위에서 박스권 소화 가능성이 큽니다.',
            'bear_scenario': '실적 기대 약화와 함께 190.50 USD를 잃으면 단기 조정 압력이 커질 수 있습니다.',
            'invalidation_price': 'SMA50 190.50 USD 아래로 내려가면 약세 시나리오 확인입니다.',
            'watch_period': '2026-04-30 실적 발표 전까지 유효합니다.',
        },
        'valuation_score': {
            'score': '6/10',
            'factors': ['PER 25.0x', '목표가 상단 여력 존재'],
            'assessment': '현재 밸류에이션은 대체로 적정 범위로 보입니다.',
        },
    }
    entry.update(overrides)
    return entry


class AnalyzerSchemaTests(unittest.TestCase):
    def test_response_schema_sets_min_lengths_for_guardrails(self) -> None:
        schema = _response_schema()
        ticker_schema = schema['properties']['tickers']['items']
        self.assertEqual(ticker_schema['properties']['summary']['minLength'], 40)
        self.assertEqual(ticker_schema['properties']['signal_or_takeaway']['minLength'], 30)
        self.assertEqual(ticker_schema['properties']['financial_highlights']['items']['minLength'], 15)
        self.assertEqual(ticker_schema['properties']['risks_or_watchpoints']['items']['minLength'], 15)
        self.assertEqual(ticker_schema['properties']['trade_frame']['properties']['bull_scenario']['minLength'], 10)

    def test_parse_and_validate_response_accepts_valid_payload(self) -> None:
        content = json.dumps({'tickers': [_valid_entry()]})

        result = _parse_and_validate_response(content, _watchlist())

        self.assertEqual(result[0]['ticker'], 'AAPL')
        self.assertEqual(result[0]['key_news'], ['10-Q 공시 제출, 실적 수치 재확인 필요'])
        self.assertEqual(result[0]['news_tone']['label'], 'bullish')

    def test_parse_and_validate_response_rejects_unexpected_ticker(self) -> None:
        content = json.dumps({'tickers': [_valid_entry(ticker='MSFT')]})

        with self.assertRaises(ValueError):
            _parse_and_validate_response(content, _watchlist())

    def test_parse_and_validate_response_rejects_too_short_summary(self) -> None:
        content = json.dumps({'tickers': [_valid_entry(summary='짧은 요약입니다.')]})

        with self.assertRaisesRegex(ValueError, 'summary'):
            _parse_and_validate_response(content, _watchlist())

    def test_parse_and_validate_response_rejects_too_short_signal(self) -> None:
        content = json.dumps({'tickers': [_valid_entry(signal_or_takeaway='중립 관찰')]})

        with self.assertRaisesRegex(ValueError, 'signal_or_takeaway'):
            _parse_and_validate_response(content, _watchlist())

    def test_parse_and_validate_response_rejects_non_quantitative_financial_highlight(self) -> None:
        content = json.dumps(
            {
                'tickers': [
                    _valid_entry(
                        financial_highlights=['수익성이 개선되는 흐름을 보이고 있습니다.']
                    )
                ]
            }
        )

        with self.assertRaisesRegex(ValueError, 'financial_highlights'):
            _parse_and_validate_response(content, _watchlist())

    def test_parse_and_validate_response_accepts_missing_data_financial_highlight(self) -> None:
        content = json.dumps(
            {
                'tickers': [
                    _valid_entry(
                        financial_highlights=[
                            'PE 데이터가 없어 동종 대비 밸류에이션 판단이 제한됩니다.',
                            'Forward EPS와 TTM EPS가 모두 N/A라 성장률 비교가 어렵습니다.',
                        ]
                    )
                ]
            }
        )

        result = _parse_and_validate_response(content, _watchlist())

        self.assertEqual(len(result[0]['financial_highlights']), 2)

    def test_parse_and_validate_response_accepts_compact_trade_frame_values(self) -> None:
        content = json.dumps(
            {
                'tickers': [
                    _valid_entry(
                        trade_frame={
                            'entry_price': '195',
                            'stop_loss': '190',
                            'target_1': '200',
                            'target_2': '210',
                            'risk_reward_ratio': '1.4R',
                            'position_size_note': '약 20주 기준',
                            'bull_scenario': '상승 추세 지속 가능성',
                            'base_scenario': '박스권 유지 가능성 높음',
                            'bear_scenario': '지지 이탈 주의가 필요함',
                            'invalidation_price': '190 이탈 확인',
                            'watch_period': '향후 5거래일',
                        }
                    )
                ]
            }
        )

        result = _parse_and_validate_response(content, _watchlist())

        self.assertEqual(result[0]['trade_frame']['risk_reward_ratio'], '1.4R')


if __name__ == '__main__':
    unittest.main()

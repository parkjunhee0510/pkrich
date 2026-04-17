from __future__ import annotations

import unittest
from unittest.mock import patch
import sys
from datetime import date

from src.collector.price import (
    _collect_single_ticker,
    _extract_alpha_forward_eps_from_estimates,
    _extract_alpha_growth_from_estimates,
    _derive_growth_from_quarterly_financials,
    _extract_forward_eps_from_analyst_targets,
    _extract_forward_eps_from_earnings_estimate,
    _extract_alpha_calendar_events,
    _extract_yfinance_quarterly_financials,
    _extract_yfinance_events,
    _fetch_stooq_price_snapshot,
    _format_percent_ratio,
    _merge_alpha_earnings_calendar,
    _normalize_upcoming_events,
    _select_price_snapshot,
)
from src.types import WatchlistItem


class _FakeHistory:
    def __init__(self, closes: list[float | None]) -> None:
        self._closes = closes
        self.empty = not closes

    def __contains__(self, key: object) -> bool:
        return key == 'Close'

    def __getitem__(self, key: str) -> list[float | None]:
        if key != 'Close':
            raise KeyError(key)
        return self._closes


class _FakeCalendar:
    def to_dict(self) -> dict[str, object]:
        return {
            'Event': {
                'Earnings Date': ['2026-04-12', '2026-04-13'],
                'Ex-Dividend Date': '2026-04-18',
            }
        }


class _FakeTicker:
    def __init__(
        self,
        calendar: object,
        quarterly_income_stmt: object | None = None,
        earnings_history: object | None = None,
        earnings_estimate: object | None = None,
    ) -> None:
        self.calendar = calendar
        self.quarterly_income_stmt = quarterly_income_stmt
        self.earnings_history = earnings_history
        self.earnings_estimate = earnings_estimate


class _FakeStatement:
    def __init__(self) -> None:
        self.columns = ["2025-12-31", "2025-09-30", "2024-12-31"]
        self.index = {
            "Total Revenue",
            "Operating Income",
            "Diluted EPS",
        }
        self._values = {
            ("Total Revenue", "2025-12-31"): 120_000_000_000,
            ("Operating Income", "2025-12-31"): 35_000_000_000,
            ("Diluted EPS", "2025-12-31"): 2.10,
            ("Total Revenue", "2025-09-30"): 118_000_000_000,
            ("Operating Income", "2025-09-30"): 33_000_000_000,
            ("Diluted EPS", "2025-09-30"): 1.98,
            ("Total Revenue", "2024-12-31"): 100_000_000_000,
            ("Operating Income", "2024-12-31"): 30_000_000_000,
            ("Diluted EPS", "2024-12-31"): 1.80,
        }
        self.empty = False
        self.at = self
        self.loc = self

    def __getitem__(self, key: tuple[str, str]) -> object:
        return self._values[key]


class _FakeStatementWithoutEps(_FakeStatement):
    def __init__(self) -> None:
        super().__init__()
        self.index = {
            "Total Revenue",
            "Operating Income",
        }
        self._values = {
            ("Total Revenue", "2025-12-31"): 120_000_000_000,
            ("Operating Income", "2025-12-31"): 35_000_000_000,
            ("Total Revenue", "2025-09-30"): 118_000_000_000,
            ("Operating Income", "2025-09-30"): 33_000_000_000,
            ("Total Revenue", "2024-12-31"): 100_000_000_000,
            ("Operating Income", "2024-12-31"): 30_000_000_000,
        }


class _FakeEarningsHistory:
    def __init__(self) -> None:
        self.empty = False
        self.index = ["2026-01-29", "2025-10-29", "2025-01-29"]

    def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError(orient)
        return [
            {"quarter": "2025-12-31", "epsEstimate": 2.00, "epsActual": 2.10, "surprisePercent": 5.0},
            {"quarter": "2025-09-30", "epsEstimate": 2.05, "epsActual": 1.98, "surprisePercent": -3.41},
            {"quarter": "2024-12-31", "epsEstimate": 1.75, "epsActual": 1.80, "surprisePercent": 2.86},
        ]


class _FakeEarningsEstimate:
    def __init__(self) -> None:
        self.index = ["0q", "+1q", "0y", "+1y"]

    def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError(orient)
        return [
            {"avg": 2.35},
            {"avg": 2.52},
            {"avg": 9.85},
            {"avg": 10.42},
        ]


class _FakeYFinanceTicker:
    def __init__(self) -> None:
        self.info = {
            'regularMarketPrice': 250.0,
            'previousClose': 245.0,
            'currency': 'USD',
            'marketCap': 3_000_000_000_000,
            'trailingPE': 30.1,
            'trailingEps': 7.9,
            'fiftyTwoWeekHigh': 260.0,
            'fiftyTwoWeekLow': 180.0,
            'fiftyDayAverage': 240.0,
            'twoHundredDayAverage': 220.0,
            'volume': 40_000_000,
            'averageVolume': 30_000_000,
            'priceToBook': 40.0,
            'dividendYield': 0.0041,
            'forwardEps': 9.33,
            'earningsGrowth': 0.183,
            'earningsDate': '2026-04-30',
            'shortPercentOfFloat': 0.032,
            'shortRatio': 2.1,
            'targetMeanPrice': 310.5,
            'recommendationMean': 2.0,
            'numberOfAnalystOpinions': 18,
            'heldPercentInsiders': 0.0007,
            'heldPercentInstitutions': 0.613,
            'impliedVolatility': 0.284,
        }
        self.calendar = None
        self.earnings_estimate = None
        self.quarterly_income_stmt = _FakeStatement()
        self.earnings_history = _FakeEarningsHistory()

    def history(self, period: str = "", interval: str = "", auto_adjust: bool = True) -> _FakeHistory:
        return _FakeHistory([240.0, 242.0, 245.0, 250.0])


class _FakeYFinanceModule:
    def set_tz_cache_location(self, _: str) -> None:
        return None

    def Ticker(self, _: str) -> _FakeYFinanceTicker:
        return _FakeYFinanceTicker()


class PriceCollectionTests(unittest.TestCase):
    def test_select_price_snapshot_uses_regular_market_price_when_latest_close_is_missing(self) -> None:
        history = _FakeHistory([253.79, 255.63, 255.92, 258.86, None])
        info = {'regularMarketPrice': 253.50, 'previousClose': 258.86}

        price, change_percent = _select_price_snapshot(history, info)

        self.assertEqual(price, 253.50)
        self.assertAlmostEqual(change_percent or 0.0, (253.50 - 258.86) / 258.86 * 100, places=6)

    def test_select_price_snapshot_uses_last_valid_close_when_live_price_is_missing(self) -> None:
        history = _FakeHistory([370.17, 369.37, 373.46, 372.88, None])
        info = {'regularMarketPrice': None, 'previousClose': 372.88}

        price, change_percent = _select_price_snapshot(history, info)

        self.assertEqual(price, 372.88)
        self.assertAlmostEqual(change_percent or 0.0, (372.88 - 373.46) / 373.46 * 100, places=6)

    def test_normalize_upcoming_events_filters_to_next_14_days(self) -> None:
        events = _normalize_upcoming_events(
            [
                {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-10'},
                {'type': 'dividend', 'label': '배당 지급일', 'date': '2026-05-10'},
            ],
            date(2026, 4, 8),
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['label'], '실적 발표')
        self.assertEqual(events[0]['days_until'], '2')

    def test_normalize_upcoming_events_keeps_earnings_up_to_ninety_days(self) -> None:
        events = _normalize_upcoming_events(
            [
                {'type': 'earnings', 'label': '실적 발표', 'date': '2026-06-15'},
                {'type': 'dividend', 'label': '배당 지급일', 'date': '2026-06-15'},
            ],
            date(2026, 4, 8),
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'earnings')
        self.assertEqual(events[0]['days_until'], '68')

    def test_normalize_upcoming_events_keeps_only_earliest_earnings_candidate(self) -> None:
        events = _normalize_upcoming_events(
            [
                {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-29'},
                {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-30'},
                {'type': 'earnings', 'label': '실적 발표', 'date': '2026-05-01'},
                {'type': 'dividend', 'label': '배당 지급일', 'date': '2026-04-18'},
            ],
            date(2026, 4, 8),
        )

        self.assertEqual(
            events,
            [
                {'type': 'dividend', 'label': '배당 지급일', 'date': '2026-04-18', 'days_until': '10', 'timing': ''},
                {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-29', 'days_until': '21', 'timing': ''},
            ],
        )

    def test_extract_yfinance_events_reads_calendar_like_objects(self) -> None:
        events = _extract_yfinance_events(
            'AAPL',
            {'earningsDate': None, 'dividendDate': None, 'exDividendDate': None},
            _FakeTicker(_FakeCalendar()),
            date(2026, 4, 8),
        )

        self.assertEqual([event['label'] for event in events], ['실적 발표', '배당락일'])
        self.assertEqual(events[0]['date'], '2026-04-12')
        self.assertEqual(events[1]['date'], '2026-04-18')

    def test_extract_alpha_calendar_events_normalizes_timing(self) -> None:
        events = _extract_alpha_calendar_events(
            {
                'earnings_calendar': [
                    {'reportDate': '2026-04-30', 'timeOfTheDay': 'bmo'},
                ]
            },
            date(2026, 4, 9),
            ticker='AAPL',
        )

        self.assertEqual(
            events,
            [
                {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-30', 'days_until': '21', 'timing': 'BMO'},
            ],
        )

    def test_merge_alpha_earnings_calendar_keeps_existing_date_and_backfills_timing(self) -> None:
        events = _merge_alpha_earnings_calendar(
            'AAPL',
            [{'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-30', 'days_until': '21', 'timing': ''}],
            {'earnings_calendar': [{'reportDate': '2026-04-30', 'timeOfTheDay': 'amc'}]},
            date(2026, 4, 9),
        )

        self.assertEqual(
            events,
            [{'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-30', 'days_until': '21', 'timing': 'AMC'}],
        )

    def test_extract_yfinance_quarterly_financials_uses_earnings_history_for_estimates(self) -> None:
        rows = _extract_yfinance_quarterly_financials(
            _FakeTicker(
                calendar=None,
                quarterly_income_stmt=_FakeStatement(),
                earnings_history=_FakeEarningsHistory(),
            )
        )

        self.assertEqual(rows[0]['quarter'], '2025-Q4')
        self.assertEqual(rows[0]['estimated_eps'], '2.00')
        self.assertEqual(rows[0]['surprise_pct'], '+5.00%')
        self.assertEqual(rows[0]['beat_miss'], 'beat')

    def test_extract_yfinance_quarterly_financials_falls_back_to_earnings_history_actual_eps(self) -> None:
        rows = _extract_yfinance_quarterly_financials(
            _FakeTicker(
                calendar=None,
                quarterly_income_stmt=_FakeStatementWithoutEps(),
                earnings_history=_FakeEarningsHistory(),
            )
        )

        self.assertEqual(rows[0]['eps'], '2.10')

    def test_extract_forward_eps_from_analyst_targets_uses_consensus_mean_eps(self) -> None:
        value = {'consensusMeanEps': 7.15}

        result = _extract_forward_eps_from_analyst_targets(value)

        self.assertEqual(result, '7.15')

    def test_extract_forward_eps_from_earnings_estimate_prefers_next_year_consensus(self) -> None:
        result = _extract_forward_eps_from_earnings_estimate(_FakeEarningsEstimate())

        self.assertEqual(result, '10.42')

    def test_extract_alpha_forward_eps_from_estimates_prefers_annual_consensus(self) -> None:
        result = _extract_alpha_forward_eps_from_estimates(
            {
                'earnings_estimates': {
                    'annualEstimates': [
                        {'fiscalYear': '2026', 'estimatedEPS': '9.85'},
                        {'fiscalYear': '2027', 'estimatedEPS': '10.42'},
                    ]
                }
            }
        )

        self.assertEqual(result, '9.85')

    def test_extract_alpha_growth_from_estimates_uses_first_two_annual_rows(self) -> None:
        result = _extract_alpha_growth_from_estimates(
            {
                'earnings_estimates': {
                    'annualEstimates': [
                        {'fiscalYear': '2026', 'estimatedEPS': '9.85'},
                        {'fiscalYear': '2027', 'estimatedEPS': '10.42'},
                    ]
                }
            }
        )

        self.assertEqual(result, '+5.79% YoY est')

    def test_collect_single_ticker_persists_forward_eps_and_earnings_growth(self) -> None:
        item = WatchlistItem(ticker='AAPL', name='Apple', sector='Technology', keywords=[])

        def _fake_tcp(host: str, _: int) -> bool:
            return host == 'query1.finance.yahoo.com'

        with patch('src.collector.price.can_open_tcp_connection', side_effect=_fake_tcp):
            with patch.dict(sys.modules, {'yfinance': _FakeYFinanceModule()}):
                data = _collect_single_ticker(item, date(2026, 4, 9))

        self.assertEqual(data.forward_eps, '9.33')
        self.assertEqual(data.earnings_growth, '+18.30% YoY')
        self.assertEqual(data.short_float_pct, '3.20%')
        self.assertEqual(data.short_ratio, '2.10일')
        self.assertEqual(data.analyst_target_price, '310.50 USD')
        self.assertEqual(data.analyst_recommendation, 'Buy')
        self.assertEqual(data.analyst_count, '18명')
        self.assertEqual(data.held_by_insiders, '0.07%')
        self.assertEqual(data.held_by_institutions, '61.30%')
        self.assertEqual(data.implied_volatility, '28.40%')

    def test_derive_growth_from_quarterly_financials_uses_year_ago_eps(self) -> None:
        growth = _derive_growth_from_quarterly_financials(
            [
                {'quarter': '2025-Q4', 'eps': '2.10'},
                {'quarter': '2025-Q3', 'eps': '1.98'},
                {'quarter': '2025-Q2', 'eps': '1.90'},
                {'quarter': '2025-Q1', 'eps': '1.80'},
                {'quarter': '2024-Q4', 'eps': '1.80'},
            ]
        )

        self.assertEqual(growth, '+16.67% YoY')

    def test_fetch_stooq_price_snapshot_uses_last_two_rows(self) -> None:
        with patch('src.collector.price._fetch_stooq_history', return_value=[(date(2026, 4, 7), 98.0), (date(2026, 4, 8), 100.0)]):
            price, change = _fetch_stooq_price_snapshot('AAPL')

        self.assertEqual(price, 100.0)
        self.assertAlmostEqual(change or 0.0, (100.0 - 98.0) / 98.0 * 100, places=6)

    def test_format_percent_ratio_handles_decimal_and_percentage_point_inputs(self) -> None:
        self.assertEqual(_format_percent_ratio(0.0041), '0.41%')
        self.assertEqual(_format_percent_ratio(0.41), '0.41%')
        self.assertEqual(_format_percent_ratio(5.25), '5.25%')


if __name__ == '__main__':
    unittest.main()

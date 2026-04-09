from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.price import (
    _extract_yfinance_events,
    _fetch_stooq_price_snapshot,
    _format_percent_ratio,
    _normalize_upcoming_events,
    _select_price_snapshot,
)


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
    def __init__(self, calendar: object) -> None:
        self.calendar = calendar


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

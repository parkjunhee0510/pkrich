from __future__ import annotations

import unittest
from datetime import date

from src.collector.macro_events import _classify_macro_shock_event, _merge_macro_shock_events
from src.collector.finnhub import _normalize_macro_event
from src.collector.macro import _find_upcoming_events
from src.types import CollectedTickerData, NewsItem, PortfolioPosition, PortfolioSummary, WatchlistItem
from src.utils.macro_sensitivity import attach_portfolio_macro_sensitivity


class MacroCollectionTests(unittest.TestCase):
    def test_normalize_macro_event_supports_extended_event_types(self) -> None:
        run_date = date(2026, 4, 14)
        cases = [
            ({'event': 'Consumer Price Index'}, 'CPI'),
            ({'event': 'Producer Price Index'}, 'PPI'),
            ({'event': 'FOMC Interest Rate Decision'}, 'FOMC'),
            ({'event': 'Non-Farm Payrolls'}, 'NFP'),
            ({'event': 'Unemployment Rate'}, 'UNRATE'),
            ({'event': 'Advance Retail Sales'}, 'RETAIL_SALES'),
        ]
        for entry, expected in cases:
            normalized = _normalize_macro_event({**entry, 'date': '2026-04-15'}, run_date)
            self.assertIsNotNone(normalized)
            self.assertEqual(normalized['event_code'], expected)
            self.assertEqual(normalized['source'], 'finnhub')
            self.assertIn('market_bias', normalized)
            self.assertIn('description', normalized)

    def test_fallback_calendar_contains_extended_macro_events(self) -> None:
        events = _find_upcoming_events(date(2026, 4, 14), 2)
        codes = {event['event_code'] for event in events}
        self.assertIn('CPI', codes)
        self.assertIn('PPI', codes)
        self.assertIn('RETAIL_SALES', codes)

    def test_attach_portfolio_macro_sensitivity_scores_holdings(self) -> None:
        macro_context = {
            'upcoming_macro_events': [
                {'event_code': 'CPI', 'type': 'CPI', 'label': 'CPI ???? ??', 'date': '2026-04-14', 'days_until': '0', 'impact': 'high'},
                {'event_code': 'RETAIL_SALES', 'type': 'RETAIL_SALES', 'label': '???? ??', 'date': '2026-04-15', 'days_until': '1', 'impact': 'high'},
            ]
        }
        portfolio_summary = PortfolioSummary(
            positions=[
                PortfolioPosition('AMD', 10, 100.0, 'USD', 120.0, 1200.0, 1000.0, 200.0, 20.0),
                PortfolioPosition('KO', 5, 60.0, 'USD', 70.0, 350.0, 300.0, 50.0, 16.7),
            ]
        )
        collected = {
            'AMD': CollectedTickerData(
                ticker='AMD', name='Advanced Micro Devices, Inc.', sector='Technology', price=120.0, change_percent=1.0,
                currency='USD', market_cap='1.00T', pe_ratio='42.0', summary_note='memo', dividend_yield='N/A',
            ),
            'KO': CollectedTickerData(
                ticker='KO', name='The Coca-Cola Company', sector='Consumer Staples', price=70.0, change_percent=0.5,
                currency='USD', market_cap='1.00T', pe_ratio='24.0', summary_note='memo', dividend_yield='3.10%',
            ),
        }
        watchlist = [
            WatchlistItem(ticker='AMD', name='Advanced Micro Devices, Inc.', sector='Technology', keywords=['AI chips', 'data center']),
            WatchlistItem(ticker='KO', name='The Coca-Cola Company', sector='Consumer Staples', keywords=['beverages', 'pricing']),
        ]

        enriched = attach_portfolio_macro_sensitivity(macro_context, portfolio_summary, collected, watchlist)

        self.assertIn('portfolio_event_sensitivity', enriched)
        cpi_row = next(row for row in enriched['portfolio_event_sensitivity'] if row['event_code'] == 'CPI')
        retail_row = next(row for row in enriched['portfolio_event_sensitivity'] if row['event_code'] == 'RETAIL_SALES')
        self.assertEqual(cpi_row['sensitive_holdings'][0]['ticker'], 'AMD')
        self.assertEqual(cpi_row['sensitive_holdings'][0]['sensitivity'], 'high')
        self.assertEqual(retail_row['sensitive_holdings'][0]['ticker'], 'KO')
        self.assertIn('portfolio_sensitivity_summary', enriched)
        self.assertIn('CPI', enriched['portfolio_sensitivity_summary'])

    def test_classify_macro_shock_event_normalizes_hormuz_story(self) -> None:
        event = _classify_macro_shock_event(
            NewsItem(
                title="Strait of Hormuz closure risk lifts oil and shipping costs",
                source="Reuters",
                published_at="2026-04-14",
                link="https://example.com/hormuz",
            ),
            date(2026, 4, 14),
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["event_type"], "hormuz_disruption")
        self.assertEqual(event["severity"], "high")
        self.assertIn("oil", event["transmission_channels"])
        self.assertIn("Energy", event["affected_sectors"])
        self.assertIn("Airlines", event["affected_industries"])

    def test_merge_macro_shock_events_deduplicates_same_event_type(self) -> None:
        merged = _merge_macro_shock_events(
            [
                {
                    "event_type": "shipping_disruption",
                    "severity": "medium",
                    "region": "global",
                    "transmission_channels": ["shipping", "supply_chain"],
                    "affected_sectors": ["Industrials"],
                    "direction": "risk_off",
                    "summary_ko": "글로벌 해운 차질이 공급망 부담을 높입니다.",
                    "expires_at": "2026-04-20",
                    "headline": "Red Sea shipping disruption raises freight rates",
                    "published_at": "2026-04-14",
                },
                {
                    "event_type": "shipping_disruption",
                    "severity": "medium",
                    "region": "global",
                    "transmission_channels": ["shipping", "supply_chain"],
                    "affected_sectors": ["Industrials"],
                    "direction": "risk_off",
                    "summary_ko": "글로벌 해운 차질이 공급망 부담을 높입니다.",
                    "expires_at": "2026-04-20",
                    "headline": "Container routes reroute after Red Sea attacks",
                    "published_at": "2026-04-14",
                },
            ]
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["event_type"], "shipping_disruption")


if __name__ == '__main__':
    unittest.main()

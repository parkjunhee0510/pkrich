from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.research_note import (
    _build_fallback_analyses,
    _build_fallback_signal,
    _build_fallback_risks,
)
from src.types import CollectedTickerData, NewsItem, WatchlistItem


def _item() -> WatchlistItem:
    return WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology", keywords=["iPhone"])


def _market(price: float | None = 150.0, change: float | None = 0.5, pe: str = "25.00") -> CollectedTickerData:
    return CollectedTickerData(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        price=price,
        change_percent=change,
        currency="USD",
        market_cap="2.50T",
        pe_ratio=pe,
        summary_note="테스트 노트",
        eps="6.50",
        week52_high="180.00",
        week52_low="120.00",
        sma_50="155.00",
        sma_200="145.00",
    )


def _news() -> list[NewsItem]:
    return [
        NewsItem(title="Apple launches new product", source="Reuters", published_at="2026-04-08", link="https://example.com"),
    ]


class FallbackSignalTests(unittest.TestCase):
    def test_strong_rally_signal(self) -> None:
        signal = _build_fallback_signal(4.5, _news())
        self.assertIn("강한 상승", signal)
        self.assertIn("+4.5%", signal)

    def test_mild_rise_signal(self) -> None:
        signal = _build_fallback_signal(1.5, _news())
        self.assertIn("상승 추세", signal)

    def test_flat_signal(self) -> None:
        signal = _build_fallback_signal(0.2, _news())
        self.assertIn("보합권", signal)

    def test_decline_signal(self) -> None:
        signal = _build_fallback_signal(-1.5, _news())
        self.assertIn("하락 중", signal)

    def test_sharp_drop_signal(self) -> None:
        signal = _build_fallback_signal(-4.0, _news())
        self.assertIn("큰 폭 하락", signal)

    def test_no_price_signal(self) -> None:
        signal = _build_fallback_signal(None, _news())
        self.assertIn("가격 데이터 미수집", signal)


class FallbackRisksTests(unittest.TestCase):
    def test_sharp_drop_adds_risk(self) -> None:
        market = _market(change=-5.0)
        risks = _build_fallback_risks(market, _news())
        self.assertTrue(any("하락 폭" in r for r in risks))

    def test_high_pe_adds_risk(self) -> None:
        market = _market(pe="45.00")
        risks = _build_fallback_risks(market, _news())
        self.assertTrue(any("PER" in r for r in risks))

    def test_no_news_adds_risk(self) -> None:
        risks = _build_fallback_risks(_market(), [])
        self.assertTrue(any("뉴스가 없어" in r for r in risks))

    def test_always_includes_check_reminder(self) -> None:
        risks = _build_fallback_risks(_market(), _news())
        self.assertTrue(any("실적 일정" in r for r in risks))


class FallbackAnalysisIntegrationTests(unittest.TestCase):
    def test_different_tickers_get_different_signals(self) -> None:
        items = [
            WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology"),
            WatchlistItem(ticker="NVDA", name="NVIDIA Corp.", sector="Semiconductors"),
        ]
        collected = {
            "AAPL": _market(change=-3.5),
            "NVDA": CollectedTickerData(
                ticker="NVDA", name="NVIDIA Corp.", sector="Semiconductors",
                price=200.0, change_percent=2.0, currency="USD",
                market_cap="3.00T", pe_ratio="35.00", summary_note="테스트",
            ),
        }
        news_map = {"AAPL": _news(), "NVDA": []}
        analyses = _build_fallback_analyses(items, collected, news_map, date(2026, 4, 8))

        self.assertEqual(len(analyses), 2)
        self.assertNotEqual(analyses[0].signal_or_takeaway, analyses[1].signal_or_takeaway)
        self.assertIn("하락", analyses[0].signal_or_takeaway)
        self.assertIn("상승", analyses[1].signal_or_takeaway)

    def test_fallback_includes_extended_financial_highlights(self) -> None:
        analyses = _build_fallback_analyses(
            [_item()], {"AAPL": _market()}, {"AAPL": _news()}, date(2026, 4, 8),
        )
        highlights = analyses[0].financial_highlights
        self.assertTrue(any("EPS" in h for h in highlights))
        self.assertTrue(any("52주" in h for h in highlights))
        self.assertTrue(any("50일" in h for h in highlights))

    def test_fallback_snapshot_has_extended_fields(self) -> None:
        analyses = _build_fallback_analyses(
            [_item()], {"AAPL": _market()}, {"AAPL": _news()}, date(2026, 4, 8),
        )
        snapshot = analyses[0].data_snapshot
        self.assertIn("EPS", snapshot)
        self.assertIn("52W High", snapshot)
        self.assertIn("52W Low", snapshot)
        self.assertIn("50D SMA", snapshot)
        self.assertIn("200D SMA", snapshot)

    def test_fallback_summary_includes_news_headline(self) -> None:
        analyses = _build_fallback_analyses(
            [_item()], {"AAPL": _market()}, {"AAPL": _news()}, date(2026, 4, 8),
        )
        self.assertIn("Apple launches new product", analyses[0].summary)


if __name__ == "__main__":
    unittest.main()

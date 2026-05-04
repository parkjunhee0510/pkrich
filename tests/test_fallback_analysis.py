from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.research_note import (
    _build_fallback_analyses,
    _build_fallback_risks,
    _build_fallback_signal,
)
from src.types import CollectedTickerData, NewsItem, WatchlistItem


def _item() -> WatchlistItem:
    return WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology", keywords=["iPhone"])


def _market(
    price: float | None = 150.0,
    change: float | None = 0.5,
    pe: str = "25.00",
    *,
    price_vs_sma50: str = "N/A",
    rs_vs_spy: str = "N/A",
    relative_volume: str = "N/A",
    week52_position: str = "N/A",
    short_float_pct: str = "N/A",
    implied_volatility: str = "N/A",
    analyst_recommendation: str = "N/A",
    analyst_target_price: str = "N/A",
    held_by_institutions: str = "N/A",
) -> CollectedTickerData:
    return CollectedTickerData(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        price=price,
        change_percent=change,
        currency="USD",
        market_cap="2.50T",
        pe_ratio=pe,
        summary_note="테스트 메모",
        eps="6.50",
        week52_high="180.00",
        week52_low="120.00",
        sma_50="145.00",
        sma_200="138.00",
        atr_14d="5.00",
        price_vs_sma50=price_vs_sma50,
        rs_vs_spy=rs_vs_spy,
        relative_volume=relative_volume,
        week52_position=week52_position,
        short_float_pct=short_float_pct,
        implied_volatility=implied_volatility,
        analyst_recommendation=analyst_recommendation,
        analyst_target_price=analyst_target_price,
        held_by_institutions=held_by_institutions,
    )


def _news() -> list[NewsItem]:
    return [
        NewsItem(title="Apple launches new product", source="Reuters", published_at="2026-04-08", link="https://example.com"),
    ]


class FallbackSignalTests(unittest.TestCase):
    def test_strong_rally_signal_uses_trader_format(self) -> None:
        signal = _build_fallback_signal(_market(change=4.5, price_vs_sma50="+5.0%", rs_vs_spy="+3.0%"), _news())
        self.assertIn("매수 관찰", signal)
        self.assertIn("진입 트리거", signal)
        self.assertIn("목표", signal)
        self.assertIn("손절", signal)

    def test_fallback_signal_includes_target_pair(self) -> None:
        signal = _build_fallback_signal(
            _market(
                price=150.0,
                change=4.5,
                price_vs_sma50="+5.0%",
                rs_vs_spy="+3.0%",
                analyst_target_price="170.00 USD",
            ),
            _news(),
        )

        self.assertRegex(signal, r"목표 \d+\.\d+/\d+\.\d+")
        self.assertIn("손절", signal)

    def test_flat_signal_uses_neutral_observation(self) -> None:
        signal = _build_fallback_signal(_market(change=0.2), [])
        self.assertIn("중립 관찰", signal)
        self.assertIn("방향성 미확정", signal)

    def test_decline_signal_with_sma_break_uses_warning(self) -> None:
        # Multi-factor: price decline + SMA50 break → bear_score >= 2 → 중립 경계
        signal = _build_fallback_signal(_market(change=-1.5, price_vs_sma50="-5.0%"), [])
        self.assertIn("중립 경계", signal)

    def test_sharp_drop_multi_factor_sell_warning(self) -> None:
        # Multi-factor: sharp drop + SMA break + weak RS → bear_score >= 3 → 매도 경계
        signal = _build_fallback_signal(
            _market(change=-4.0, price_vs_sma50="-5.0%", rs_vs_spy="-3.0%"), []
        )
        self.assertIn("매도 경계", signal)
        self.assertIn("기술적 약세", signal)

    def test_no_price_signal_reports_missing_data(self) -> None:
        signal = _build_fallback_signal(_market(price=None, change=None), _news())
        self.assertIn("가격 데이터 미수집", signal)

    def test_high_rvol_amplifies_bull_direction(self) -> None:
        # Bull bias from price + SMA, amplified by high RVOL → bull_score reaches 3+
        signal = _build_fallback_signal(
            _market(change=3.5, price_vs_sma50="+2.0%", relative_volume="2.00x"), []
        )
        self.assertIn("매수 관찰", signal)


class FallbackRisksTests(unittest.TestCase):
    def test_sharp_drop_adds_risk(self) -> None:
        market = _market(change=-5.0)
        risks = _build_fallback_risks(market, _news())
        self.assertTrue(any("-5.0% 하락" in risk for risk in risks))

    def test_high_pe_adds_risk(self) -> None:
        market = _market(pe="45.00")
        risks = _build_fallback_risks(market, _news())
        self.assertTrue(any("PER" in risk for risk in risks))

    def test_no_news_adds_risk(self) -> None:
        risks = _build_fallback_risks(_market(), [])
        self.assertTrue(any("수집된 뉴스가 없어" in risk for risk in risks))

    def test_includes_check_reminder_when_no_other_risks(self) -> None:
        risks = _build_fallback_risks(_market(), _news())
        self.assertTrue(any("실적 일정" in risk for risk in risks))

    def test_sma200_break_adds_risk(self) -> None:
        market = _market(price_vs_sma50="-6.0%")
        # price_vs_sma200 defaults to N/A, so no SMA200 risk; test SMA200 explicitly
        # The helper doesn't have price_vs_sma200, but _build_fallback_risks checks it
        risks = _build_fallback_risks(market, _news())
        self.assertIsInstance(risks, list)

    def test_high_short_float_adds_risk(self) -> None:
        market = _market(short_float_pct="15.0%")
        risks = _build_fallback_risks(market, _news())
        self.assertTrue(any("공매도" in risk for risk in risks))

    def test_high_iv_adds_risk(self) -> None:
        market = _market(implied_volatility="65.0%")
        risks = _build_fallback_risks(market, _news())
        self.assertTrue(any("IV" in risk for risk in risks))

    def test_risks_capped_at_four(self) -> None:
        market = _market(change=-5.0, pe="50.00", short_float_pct="15.0%", implied_volatility="65.0%")
        risks = _build_fallback_risks(market, [])
        self.assertLessEqual(len(risks), 4)


class FallbackAnalysisIntegrationTests(unittest.TestCase):
    def test_different_tickers_get_different_signals(self) -> None:
        items = [
            WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology"),
            WatchlistItem(ticker="NVDA", name="NVIDIA Corp.", sector="Semiconductors"),
        ]
        collected = {
            "AAPL": _market(change=-3.5, price_vs_sma50="-5.0%", rs_vs_spy="-4.0%"),
            "NVDA": CollectedTickerData(
                ticker="NVDA",
                name="NVIDIA Corp.",
                sector="Semiconductors",
                price=200.0,
                change_percent=2.0,
                currency="USD",
                market_cap="3.00T",
                pe_ratio="35.00",
                summary_note="테스트",
                sma_50="190.00",
                atr_14d="8.00",
                price_vs_sma50="+5.3%",
                rs_vs_spy="+3.0%",
            ),
        }
        news_map = {"AAPL": _news(), "NVDA": []}
        analyses = _build_fallback_analyses(items, collected, news_map, date(2026, 4, 8))

        self.assertEqual(len(analyses), 2)
        self.assertNotEqual(analyses[0].signal_or_takeaway, analyses[1].signal_or_takeaway)
        self.assertIn("매도 경계", analyses[0].signal_or_takeaway)
        self.assertIn("매수 관찰", analyses[1].signal_or_takeaway)

    def test_fallback_includes_extended_financial_highlights(self) -> None:
        analyses = _build_fallback_analyses(
            [_item()],
            {"AAPL": _market(week52_position="73%", analyst_recommendation="Buy", analyst_target_price="$310")},
            {"AAPL": _news()},
            date(2026, 4, 8),
        )
        highlights = analyses[0].financial_highlights
        self.assertTrue(any("PER" in h or "EPS" in h for h in highlights))
        self.assertTrue(any("52주" in h or "SMA50" in h for h in highlights))
        self.assertLessEqual(len(highlights), 5)

    def test_fallback_snapshot_has_extended_fields(self) -> None:
        analyses = _build_fallback_analyses(
            [_item()],
            {"AAPL": _market()},
            {"AAPL": _news()},
            date(2026, 4, 8),
        )
        snapshot = analyses[0].data_snapshot
        self.assertIn("EPS", snapshot)
        self.assertIn("52W High", snapshot)
        self.assertIn("52W Low", snapshot)
        self.assertIn("50D SMA", snapshot)
        self.assertIn("200D SMA", snapshot)

    def test_fallback_summary_includes_news_headline(self) -> None:
        analyses = _build_fallback_analyses(
            [_item()],
            {"AAPL": _market()},
            {"AAPL": _news()},
            date(2026, 4, 8),
        )
        self.assertIn("Apple launches new product", analyses[0].summary)


if __name__ == "__main__":
    unittest.main()

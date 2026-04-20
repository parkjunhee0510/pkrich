"""Unit tests for src/collector/shadow_compare.py diff semantics."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector import shadow_compare
from src.collector.shadow_compare import (
    _diff_ticker,
    _normalize_missing,
    _values_match,
    run_shadow_comparison,
)
from src.types import CollectedTickerData, WatchlistItem


def _make_ctd(**overrides) -> CollectedTickerData:
    base = dict(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        price=100.0,
        change_percent=1.5,
        currency="USD",
        market_cap="3T",
        pe_ratio="28.5",
        summary_note="",
    )
    base.update(overrides)
    return CollectedTickerData(**base)


class NormalizeMissingTests(unittest.TestCase):
    def test_collapses_na_and_empty_and_none(self) -> None:
        for v in (None, "N/A", "n/a", "", "   "):
            self.assertIsNone(_normalize_missing(v))

    def test_preserves_real_values(self) -> None:
        self.assertEqual(_normalize_missing("3T"), "3T")
        self.assertEqual(_normalize_missing(100.0), 100.0)


class ValuesMatchTests(unittest.TestCase):
    def test_both_missing_match(self) -> None:
        self.assertTrue(_values_match(None, "N/A"))
        self.assertTrue(_values_match("", None))

    def test_one_missing_does_not_match(self) -> None:
        self.assertFalse(_values_match(None, "3T"))
        self.assertFalse(_values_match("N/A", 100.0))

    def test_string_equality(self) -> None:
        self.assertTrue(_values_match("3T", "3T"))
        self.assertFalse(_values_match("3T", "2T"))

    def test_float_tolerance_within_bounds(self) -> None:
        # 0.1% relative tolerance or 0.01 absolute, whichever is larger.
        self.assertTrue(_values_match(100.0, 100.005))
        self.assertFalse(_values_match(100.0, 101.0))


class DiffTickerTests(unittest.TestCase):
    def test_no_diff_when_identical(self) -> None:
        a = _make_ctd(price=100.0, market_cap="3T")
        b = _make_ctd(price=100.0, market_cap="3T")
        self.assertEqual(_diff_ticker(a, b), [])

    def test_diff_detected_on_yfinance_field(self) -> None:
        a = _make_ctd(market_cap="3T")
        b = _make_ctd(market_cap="2T")
        diffs = _diff_ticker(a, b)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0][0], "market_cap")

    def test_na_and_empty_do_not_trigger_diff(self) -> None:
        a = _make_ctd(pe_ratio="N/A")
        b = _make_ctd(pe_ratio="")
        self.assertEqual(_diff_ticker(a, b), [])

    def test_non_yfinance_fields_ignored(self) -> None:
        # `sector` is watchlist-sourced, not in _YFINANCE_OWNED_FIELDS.
        a = _make_ctd(sector="Technology")
        b = _make_ctd(sector="Finance")
        self.assertEqual(_diff_ticker(a, b), [])


class RunShadowComparisonTests(unittest.TestCase):
    def test_orchestrator_failure_does_not_raise(self) -> None:
        """If orchestrator construction/run throws, shadow must swallow it."""
        wl = [WatchlistItem(ticker="AAPL", name="Apple", sector="Tech")]
        legacy = {"AAPL": _make_ctd()}

        with patch.object(
            shadow_compare, "build_full_orchestrator", side_effect=RuntimeError("boom")
        ):
            # Must not propagate.
            run_shadow_comparison(wl, date(2026, 4, 15), legacy)

    def test_happy_path_emits_summary_event(self) -> None:
        wl = [WatchlistItem(ticker="AAPL", name="Apple", sector="Tech")]
        legacy = {"AAPL": _make_ctd(market_cap="3T")}
        new = {"AAPL": _make_ctd(market_cap="2T")}

        class _FakeOrch:
            def collect_all(self, *_a, **_kw):
                class _Report:
                    def failure_count(self) -> int:
                        return 0

                return new, _Report()

        with patch.object(shadow_compare, "build_full_orchestrator", return_value=_FakeOrch()):
            with patch.object(shadow_compare, "record_pipeline_event") as rec:
                run_shadow_comparison(wl, date(2026, 4, 15), legacy)

        events = [call.args[2] for call in rec.call_args_list]
        self.assertIn("shadow_comparison_summary", events)
        self.assertIn("shadow_field_diff", events)


if __name__ == "__main__":
    unittest.main()

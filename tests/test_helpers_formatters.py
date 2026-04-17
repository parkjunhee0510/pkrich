"""Unit tests for src/collector/helpers/formatters.py.

These formatters are the pure string/number transforms that many
providers and legacy `price.py` share. The tests here pin down:

  * N/A sentinel semantics — every formatter returns "N/A" for
    missing/non-numeric input, never raises.
  * Suffix formatting — T/B/M boundaries, Korean suffixes (일, 명).
  * Percent ambiguity resolution — format_percent_ratio auto-detects
    decimal vs. percentage-point input; format_fractional_percent
    always treats input as a fraction.
  * Currency code handling in format_price (graceful when empty).
"""
from __future__ import annotations

import math
import unittest

from src.collector.helpers.formatters import (
    calculate_change_percent,
    coerce_finite_float,
    derive_forward_eps,
    format_analyst_count,
    format_fractional_percent,
    format_growth_percentage,
    format_large_number,
    format_percent_ratio,
    format_price,
    format_ratio,
    format_short_ratio,
    map_recommendation,
)


class CoerceFiniteFloatTests(unittest.TestCase):
    def test_int_returns_float(self) -> None:
        self.assertEqual(coerce_finite_float(3), 3.0)

    def test_float_returns_self(self) -> None:
        self.assertEqual(coerce_finite_float(2.5), 2.5)

    def test_numeric_string_coerces(self) -> None:
        self.assertEqual(coerce_finite_float("1.25"), 1.25)

    def test_none_returns_none(self) -> None:
        self.assertIsNone(coerce_finite_float(None))

    def test_non_numeric_string_returns_none(self) -> None:
        self.assertIsNone(coerce_finite_float("N/A"))
        self.assertIsNone(coerce_finite_float(""))

    def test_nan_returns_none(self) -> None:
        self.assertIsNone(coerce_finite_float(float("nan")))

    def test_inf_returns_none(self) -> None:
        self.assertIsNone(coerce_finite_float(math.inf))
        self.assertIsNone(coerce_finite_float(-math.inf))


class CalculateChangePercentTests(unittest.TestCase):
    def test_positive_change(self) -> None:
        self.assertAlmostEqual(calculate_change_percent(110.0, 100.0), 10.0)

    def test_negative_change(self) -> None:
        self.assertAlmostEqual(calculate_change_percent(90.0, 100.0), -10.0)

    def test_baseline_none_returns_none(self) -> None:
        self.assertIsNone(calculate_change_percent(100.0, None))

    def test_baseline_zero_returns_none(self) -> None:
        self.assertIsNone(calculate_change_percent(100.0, 0))


class FormatLargeNumberTests(unittest.TestCase):
    def test_trillion_boundary(self) -> None:
        self.assertEqual(format_large_number(3_500_000_000_000), "3.50T")

    def test_billion_boundary(self) -> None:
        self.assertEqual(format_large_number(2_300_000_000), "2.30B")

    def test_million_boundary(self) -> None:
        self.assertEqual(format_large_number(1_500_000), "1.50M")

    def test_below_million_uses_separator(self) -> None:
        self.assertEqual(format_large_number(42_300), "42,300")

    def test_none_returns_na(self) -> None:
        self.assertEqual(format_large_number(None), "N/A")


class FormatRatioTests(unittest.TestCase):
    def test_two_decimal_format(self) -> None:
        self.assertEqual(format_ratio(28.4567), "28.46")

    def test_zero(self) -> None:
        self.assertEqual(format_ratio(0), "0.00")

    def test_invalid_returns_na(self) -> None:
        self.assertEqual(format_ratio("N/A"), "N/A")


class FormatShortRatioTests(unittest.TestCase):
    def test_korean_suffix(self) -> None:
        self.assertEqual(format_short_ratio(2.1), "2.10일")

    def test_na_stays_na(self) -> None:
        self.assertEqual(format_short_ratio(None), "N/A")


class FormatPriceTests(unittest.TestCase):
    def test_price_with_currency(self) -> None:
        self.assertEqual(format_price(247.96, "USD"), "247.96 USD")

    def test_empty_currency_stripped(self) -> None:
        # Stripping prevents a trailing space when currency is blank.
        self.assertEqual(format_price(100.0, ""), "100.00")

    def test_na_stays_na(self) -> None:
        self.assertEqual(format_price(None, "USD"), "N/A")


class FormatAnalystCountTests(unittest.TestCase):
    def test_integer_with_korean_suffix(self) -> None:
        self.assertEqual(format_analyst_count(18), "18명")

    def test_float_truncates_to_int(self) -> None:
        self.assertEqual(format_analyst_count(18.9), "18명")

    def test_na_stays_na(self) -> None:
        self.assertEqual(format_analyst_count(None), "N/A")


class FormatPercentRatioTests(unittest.TestCase):
    def test_decimal_fraction_multiplied(self) -> None:
        # 0.0041 is clearly a decimal fraction → multiply.
        self.assertEqual(format_percent_ratio(0.0041), "0.41%")

    def test_percentage_point_preserved(self) -> None:
        # 3.5 is clearly already percentage points → preserve.
        self.assertEqual(format_percent_ratio(3.5), "3.50%")

    def test_ambiguity_boundary_at_0_2(self) -> None:
        # At the 0.2 threshold, treat as percentage point (no multiply).
        self.assertEqual(format_percent_ratio(0.2), "0.20%")

    def test_na_stays_na(self) -> None:
        self.assertEqual(format_percent_ratio(None), "N/A")


class FormatFractionalPercentTests(unittest.TestCase):
    def test_always_multiplies(self) -> None:
        # Unlike format_percent_ratio, this never second-guesses —
        # input is always treated as a fraction.
        self.assertEqual(format_fractional_percent(0.25), "25.00%")

    def test_tiny_values(self) -> None:
        self.assertEqual(format_fractional_percent(0.0007), "0.07%")

    def test_na_stays_na(self) -> None:
        self.assertEqual(format_fractional_percent(None), "N/A")


class FormatGrowthPercentageTests(unittest.TestCase):
    def test_decimal_fraction(self) -> None:
        # |value| < 1 → treat as fraction, multiply.
        self.assertEqual(format_growth_percentage(0.15), "+15.00% YoY")

    def test_negative_fraction(self) -> None:
        self.assertEqual(format_growth_percentage(-0.085), "-8.50% YoY")

    def test_already_percentage_preserved(self) -> None:
        self.assertEqual(format_growth_percentage(15), "+15.00% YoY")

    def test_na_stays_na(self) -> None:
        self.assertEqual(format_growth_percentage(None), "N/A")


class MapRecommendationTests(unittest.TestCase):
    def test_strong_buy_boundary(self) -> None:
        self.assertEqual(map_recommendation(1.0), "Strong Buy")
        self.assertEqual(map_recommendation(1.5), "Strong Buy")

    def test_buy(self) -> None:
        self.assertEqual(map_recommendation(1.6), "Buy")
        self.assertEqual(map_recommendation(2.5), "Buy")

    def test_hold(self) -> None:
        self.assertEqual(map_recommendation(3.0), "Hold")
        self.assertEqual(map_recommendation(3.5), "Hold")

    def test_sell(self) -> None:
        self.assertEqual(map_recommendation(4.0), "Sell")
        self.assertEqual(map_recommendation(4.5), "Sell")

    def test_strong_sell_above_4_5(self) -> None:
        self.assertEqual(map_recommendation(4.6), "Strong Sell")
        self.assertEqual(map_recommendation(5.0), "Strong Sell")

    def test_none_returns_na(self) -> None:
        self.assertEqual(map_recommendation(None), "N/A")


class DeriveForwardEpsTests(unittest.TestCase):
    def test_price_divided_by_forward_pe(self) -> None:
        # price=100, forwardPE=20 → forward EPS = 5.00
        self.assertEqual(derive_forward_eps(100.0, 20.0), "5.00")

    def test_forward_pe_zero_returns_na(self) -> None:
        self.assertEqual(derive_forward_eps(100.0, 0), "N/A")

    def test_price_none_returns_na(self) -> None:
        self.assertEqual(derive_forward_eps(None, 20.0), "N/A")

    def test_forward_pe_non_numeric_returns_na(self) -> None:
        self.assertEqual(derive_forward_eps(100.0, "N/A"), "N/A")


if __name__ == "__main__":
    unittest.main()

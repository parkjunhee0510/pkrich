from __future__ import annotations

import unittest

from src.utils.quarterly_financials import build_quarterly_financial_display_rows


class QuarterlyFinancialTests(unittest.TestCase):
    def test_build_quarterly_financial_display_rows_adds_yoy_when_prior_year_exists(self) -> None:
        rows = build_quarterly_financial_display_rows(
            [
                {"quarter": "2025-Q4", "revenue": "120.00B", "operating_income": "35.00B", "eps": "2.10"},
                {"quarter": "2025-Q3", "revenue": "118.00B", "operating_income": "33.00B", "eps": "1.98"},
                {"quarter": "2025-Q2", "revenue": "115.00B", "operating_income": "31.00B", "eps": "1.90"},
                {"quarter": "2025-Q1", "revenue": "110.00B", "operating_income": "30.00B", "eps": "1.80"},
                {"quarter": "2024-Q4", "revenue": "100.00B", "operating_income": "30.00B", "eps": "1.80"},
                {"quarter": "2024-Q3", "revenue": "98.00B", "operating_income": "28.00B", "eps": "1.70"},
            ]
        )

        self.assertEqual(rows[0]["revenue_yoy"], "+20.0% YoY")
        self.assertEqual(rows[0]["operating_income_yoy"], "+16.7% YoY")
        self.assertEqual(rows[0]["eps_yoy"], "+16.7% YoY")
        self.assertEqual(rows[2]["revenue_yoy"], "")

    def test_build_quarterly_financial_display_rows_omits_yoy_without_matching_prior_year(self) -> None:
        rows = build_quarterly_financial_display_rows(
            [
                {"quarter": "2025-Q4", "revenue": "120.00B", "operating_income": "35.00B", "eps": "2.10"},
            ]
        )

        self.assertEqual(rows[0]["revenue_yoy"], "")
        self.assertEqual(rows[0]["operating_income_yoy"], "")
        self.assertEqual(rows[0]["eps_yoy"], "")


if __name__ == "__main__":
    unittest.main()

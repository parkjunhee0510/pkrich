from __future__ import annotations

import unittest

from src.collector.sec_edgar import _parse_8k_item_number


class SecItemParsingTests(unittest.TestCase):
    def test_parse_8k_item_number_from_description(self) -> None:
        self.assertEqual(_parse_8k_item_number("Item 2.02 Results of Operations and Financial Condition"), "2.02")

    def test_parse_8k_item_number_is_case_insensitive(self) -> None:
        self.assertEqual(_parse_8k_item_number("item 5.02 Departure of Directors or Certain Officers"), "5.02")

    def test_parse_8k_item_number_returns_empty_string_for_non_matches(self) -> None:
        self.assertEqual(_parse_8k_item_number("Quarterly dividend announcement"), "")


if __name__ == "__main__":
    unittest.main()

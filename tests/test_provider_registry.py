"""Unit tests for src/collector/registry.py."""
from __future__ import annotations

import unittest

from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.collector.registry import ProviderRegistry


class _StubProvider(DataProvider):
    def __init__(
        self,
        name: str,
        provides: set[str],
        priority: int = 99,
        available: bool = True,
    ) -> None:
        self.name = name
        self.provides = provides
        self.priority = priority
        self.rate_limit = RateLimit(calls_per_minute=60)
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        return ProviderResult.success(
            self.name, PartialTickerData(ticker=ticker, fields={})
        )


class ProviderRegistryTests(unittest.TestCase):
    def test_register_and_lookup_by_name(self) -> None:
        reg = ProviderRegistry()
        p = _StubProvider("yfinance", {"price"})
        reg.register(p)
        self.assertIs(reg.get("yfinance"), p)

    def test_duplicate_registration_raises(self) -> None:
        reg = ProviderRegistry()
        reg.register(_StubProvider("yf", {"price"}))
        with self.assertRaises(ValueError):
            reg.register(_StubProvider("yf", {"fundamentals"}))

    def test_missing_name_raises(self) -> None:
        reg = ProviderRegistry()
        p = _StubProvider("", {"price"})
        with self.assertRaises(ValueError):
            reg.register(p)

    def test_providers_for_sorts_by_priority(self) -> None:
        reg = ProviderRegistry()
        low = _StubProvider("low", {"price"}, priority=3)
        high = _StubProvider("high", {"price"}, priority=1)
        mid = _StubProvider("mid", {"price"}, priority=2)
        reg.register(low)
        reg.register(high)
        reg.register(mid)
        ordered = reg.providers_for("price")
        self.assertEqual([p.name for p in ordered], ["high", "mid", "low"])

    def test_providers_for_ties_break_by_registration_order(self) -> None:
        reg = ProviderRegistry()
        a = _StubProvider("a", {"price"}, priority=2)
        b = _StubProvider("b", {"price"}, priority=2)
        reg.register(a)
        reg.register(b)
        self.assertEqual([p.name for p in reg.providers_for("price")], ["a", "b"])

    def test_providers_for_filters_unavailable(self) -> None:
        reg = ProviderRegistry()
        reg.register(_StubProvider("on", {"price"}, priority=1, available=True))
        reg.register(_StubProvider("off", {"price"}, priority=2, available=False))
        self.assertEqual(
            [p.name for p in reg.providers_for("price")], ["on"]
        )
        # only_available=False returns both.
        self.assertEqual(
            {p.name for p in reg.providers_for("price", only_available=False)},
            {"on", "off"},
        )

    def test_unknown_data_type_returns_empty(self) -> None:
        reg = ProviderRegistry()
        reg.register(_StubProvider("yf", {"price"}))
        self.assertEqual(reg.providers_for("social_sentiment"), [])

    def test_is_available_exception_treated_as_unavailable(self) -> None:
        class Boom(_StubProvider):
            def is_available(self) -> bool:
                raise RuntimeError("boom")

        reg = ProviderRegistry()
        reg.register(Boom("boom", {"price"}))
        self.assertEqual(reg.providers_for("price"), [])

    def test_data_types_union(self) -> None:
        reg = ProviderRegistry()
        reg.register(_StubProvider("a", {"price", "news"}))
        reg.register(_StubProvider("b", {"fundamentals"}))
        self.assertEqual(reg.data_types(), {"price", "news", "fundamentals"})


if __name__ == "__main__":
    unittest.main()

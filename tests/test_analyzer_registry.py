from __future__ import annotations

import unittest

from src.analyzer.base import AnalysisModule, AnalysisContext, ModuleResult
from src.analyzer.registry import ModuleRegistry


class _RegistryModule(AnalysisModule):
    def __init__(self, name: str, priority: int, requires: set[str], produces: set[str]) -> None:
        self.name = name
        self.priority = priority
        self.requires = requires
        self.produces = produces

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        return ModuleResult()


class AnalyzerRegistryTests(unittest.TestCase):
    def test_resolve_order_uses_dag_dependencies(self) -> None:
        registry = ModuleRegistry()
        registry.register(_RegistryModule("valuation", 20, {"price"}, {"valuation_score"}))
        registry.register(_RegistryModule("signal", 40, {"valuation_score"}, {"signal_or_takeaway"}))
        registry.register(_RegistryModule("trade", 10, {"price"}, {"trade_frame"}))
        ordered = registry.resolve_order({"price"})
        self.assertEqual([module.name for module in ordered], ["trade", "valuation", "signal"])

    def test_resolve_order_fails_for_cycle(self) -> None:
        registry = ModuleRegistry()
        registry.register(_RegistryModule("a", 10, {"b_out"}, {"a_out"}))
        registry.register(_RegistryModule("b", 20, {"a_out"}, {"b_out"}))
        with self.assertRaises(ValueError):
            registry.resolve_order(set())

    def test_resolve_order_fails_for_unresolved_requirement(self) -> None:
        registry = ModuleRegistry()
        registry.register(_RegistryModule("a", 10, {"missing"}, {"a_out"}))
        with self.assertRaises(ValueError):
            registry.resolve_order({"price"})

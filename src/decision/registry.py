from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Iterable

from src.decision.base import DecisionFactor


class FactorRegistry:
    def __init__(self) -> None:
        self._factors: dict[str, DecisionFactor] = {}

    def register(self, factor: DecisionFactor) -> None:
        if factor.name in self._factors:
            raise ValueError(f"Duplicate factor name: {factor.name}")
        self._factors[factor.name] = factor

    def discover(self, factor_config: dict[str, dict[str, int]]) -> None:
        package = importlib.import_module("src.decision.factors")
        for module_info in pkgutil.iter_modules(package.__path__):
            if module_info.name.startswith("_"):
                continue
            module = importlib.import_module(f"src.decision.factors.{module_info.name}")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj is DecisionFactor or not issubclass(obj, DecisionFactor):
                    continue
                factor = obj()
                self.register(factor)

        discovered_names = set(self._factors)
        configured_names = set(factor_config)
        missing_config = discovered_names - configured_names
        if missing_config:
            raise ValueError(f"Missing decision weight config for factors: {', '.join(sorted(missing_config))}")
        missing_impl = configured_names - discovered_names
        if missing_impl:
            raise ValueError(f"Missing factor implementations for: {', '.join(sorted(missing_impl))}")

        for name, factor in self._factors.items():
            config = factor_config[name]
            minimum = int(config.get("min", 0))
            maximum = int(config["max"])
            factor.weight_range = (minimum, maximum)

    def all(self) -> list[DecisionFactor]:
        return list(self._factors.values())

    def names(self) -> set[str]:
        return set(self._factors)


def build_factor_registry(factor_config: dict[str, dict[str, int]]) -> FactorRegistry:
    registry = FactorRegistry()
    registry.discover(factor_config)
    return registry

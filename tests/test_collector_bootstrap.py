"""Unit tests for src/collector/bootstrap.py."""
from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.collector.bootstrap import (
    ProviderConfig,
    apply_config_to_provider,
    build_orchestrator,
    load_cache_ttl,
    load_provider_config,
)
from src.utils.config import load_sector_etf_map


class _Stub(DataProvider):
    name = "yfinance"
    provides = {"price"}
    priority = 99
    rate_limit = RateLimit(calls_per_minute=10)

    def is_available(self) -> bool:
        return True

    def collect(self, ticker, ctx):
        return ProviderResult.success(self.name, PartialTickerData(ticker=ticker, fields={}))


class LoadProviderConfigTests(unittest.TestCase):
    def test_missing_file_returns_empty_dict(self) -> None:
        self.assertEqual(load_provider_config(Path("does-not-exist.yaml")), {})

    def test_parses_typical_yaml(self) -> None:
        yaml_text = textwrap.dedent(
            """
            providers:
              yfinance:
                priority: 1
                rate: 60
                burst: 20
              fmp:
                priority: 2
                rate: 300
            """
        ).strip()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(yaml_text)
            path = Path(fh.name)

        try:
            result = load_provider_config(path)
            self.assertEqual(result["yfinance"].priority, 1)
            self.assertEqual(result["yfinance"].rate_limit.calls_per_minute, 60)
            self.assertEqual(result["yfinance"].rate_limit.burst, 20)
            self.assertEqual(result["fmp"].priority, 2)
            # burst omitted → None, effective_burst falls back to cpm.
            self.assertIsNone(result["fmp"].rate_limit.burst)
        finally:
            path.unlink(missing_ok=True)

    def test_bad_entry_skipped_not_fatal(self) -> None:
        yaml_text = textwrap.dedent(
            """
            providers:
              good:
                priority: 1
                rate: 60
              bad:
                priority: not-a-number
                rate: 30
            """
        ).strip()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(yaml_text)
            path = Path(fh.name)
        try:
            result = load_provider_config(path)
            self.assertIn("good", result)
            self.assertNotIn("bad", result)
        finally:
            path.unlink(missing_ok=True)


class LoadCacheTtlTests(unittest.TestCase):
    def test_override_merged_into_defaults(self) -> None:
        yaml_text = textwrap.dedent(
            """
            providers: {}
            cache_ttl:
              fundamentals: 48
              new_type: 3
            """
        ).strip()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(yaml_text)
            path = Path(fh.name)
        try:
            ttl = load_cache_ttl(path)
            self.assertEqual(ttl["fundamentals"], 48.0)
            self.assertEqual(ttl["new_type"], 3.0)
            # Other defaults preserved.
            self.assertIn("sec_filings", ttl)
        finally:
            path.unlink(missing_ok=True)


class ApplyConfigTests(unittest.TestCase):
    def test_applies_priority_and_rate(self) -> None:
        stub = _Stub()
        config = {
            "yfinance": ProviderConfig(
                priority=1, rate_limit=RateLimit(calls_per_minute=120, burst=30),
            )
        }
        apply_config_to_provider(stub, config)
        self.assertEqual(stub.priority, 1)
        self.assertEqual(stub.rate_limit.calls_per_minute, 120)
        self.assertEqual(stub.rate_limit.burst, 30)

    def test_no_entry_leaves_defaults(self) -> None:
        stub = _Stub()
        apply_config_to_provider(stub, {})
        self.assertEqual(stub.priority, 99)
        self.assertEqual(stub.rate_limit.calls_per_minute, 10)


class BuildOrchestratorTests(unittest.TestCase):
    def test_build_without_providers_returns_empty_orchestrator(self) -> None:
        orch = build_orchestrator(
            providers=None,
            config_path=Path("does-not-exist.yaml"),
            cache_path=None,
        )
        self.assertIsNotNone(orch)

    def test_build_wires_providers(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        try:
            orch = build_orchestrator(
                providers=[_Stub()],
                config_path=Path("does-not-exist.yaml"),
                cache_path=Path(tmp.name) / "cache.sqlite",
            )
            # Registry should have our stub.
            self.assertIsNotNone(orch._registry.get("yfinance"))  # type: ignore[attr-defined]
            # Close the SQLite handle before Windows tries to remove the dir.
            if orch._cache is not None:  # type: ignore[attr-defined]
                orch._cache.close()  # type: ignore[attr-defined]
        finally:
            try:
                tmp.cleanup()
            except (OSError, PermissionError):
                # Windows sometimes holds handles open briefly; tolerate.
                pass


class LoadSectorEtfMapTests(unittest.TestCase):
    def test_loads_mapping_from_watchlist_yaml(self) -> None:
        yaml_text = textwrap.dedent(
            """
            sector_etf_map:
              Technology: XLK
              Utilities: XLU
            watchlist: []
            """
        ).strip()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(yaml_text)
            path = Path(fh.name)
        try:
            mapping = load_sector_etf_map(str(path))
            self.assertEqual(mapping["Technology"], "XLK")
            self.assertEqual(mapping["Utilities"], "XLU")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

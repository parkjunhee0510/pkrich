from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.api_status import build_api_status_payload, write_api_status_outputs
from src.types import WatchlistItem


def _watchlist() -> list[WatchlistItem]:
    return [
        WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology"),
        WatchlistItem(ticker="PLUG", name="Plug Power", sector="Industrials"),
    ]


class ApiStatusTests(unittest.TestCase):
    def test_build_api_status_payload_summarizes_latest_run_and_ticker_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_root = Path(temp_dir) / "logs" / "pipeline"
            logs_root.mkdir(parents=True, exist_ok=True)
            log_path = logs_root / "2026-04-13.jsonl"
            rows = [
                {"event": "pipeline_started", "component": "pipeline", "level": "info"},
                {"event": "data_provider_used", "component": "collector", "level": "info", "ticker": "AAPL", "source": "yfinance"},
                {"event": "data_provider_used", "component": "collector", "level": "info", "ticker": "AAPL", "source": "alpha_vantage"},
                {"event": "polygon_options_flow", "component": "collector", "level": "info", "ticker": "AAPL"},
                {"event": "fmp_company_profile", "component": "collector", "level": "info", "ticker": "AAPL"},
                {"event": "finnhub_recommendations", "component": "collector", "level": "info", "ticker": "AAPL"},
                {"event": "news_provider_completed", "component": "collector", "level": "info", "ticker": "AAPL", "source": "SEC EDGAR"},
                {"event": "news_provider_completed", "component": "collector", "level": "info", "ticker": "AAPL", "source": "Apple Newsroom"},
                {"event": "data_provider_used", "component": "collector", "level": "info", "ticker": "PLUG", "source": "yfinance"},
                {"event": "fmp_financial_ratios_unavailable", "component": "collector", "level": "info", "ticker": "PLUG"},
                {"event": "finnhub_recommendations_failed", "component": "collector", "level": "warning", "ticker": "PLUG"},
                {"event": "pipeline_completed", "component": "pipeline", "level": "info"},
            ]
            log_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            payload = build_api_status_payload(date(2026, 4, 13), _watchlist(), logs_root=logs_root)

        summary = payload["summary"]
        matrix = {row["ticker"]: row for row in payload["ticker_matrix"]}

        self.assertTrue(summary["pipeline_completed"])
        self.assertEqual(summary["providers"]["yfinance"]["used_tickers"], 2)
        self.assertEqual(summary["providers"]["alpha_vantage"]["used_tickers"], 1)
        self.assertEqual(summary["providers"]["fmp"]["unavailable_tickers"], 1)
        self.assertEqual(summary["providers"]["fmp"]["throttled_tickers"], 0)
        self.assertEqual(summary["providers"]["finnhub"]["failed_tickers"], 1)

        self.assertEqual(matrix["AAPL"]["yfinance"], "used")
        self.assertEqual(matrix["AAPL"]["alpha_vantage"], "used")
        self.assertEqual(matrix["AAPL"]["polygon"], "used")
        self.assertEqual(matrix["AAPL"]["fmp"], "used")
        self.assertEqual(matrix["AAPL"]["finnhub"], "used")
        self.assertEqual(matrix["AAPL"]["sec_edgar"], "used")
        self.assertEqual(matrix["AAPL"]["ir_rss"], "used")
        self.assertEqual(matrix["PLUG"]["fmp"], "unavailable")
        self.assertEqual(matrix["PLUG"]["finnhub"], "failed")

    def test_build_api_status_payload_marks_throttled_provider_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_root = Path(temp_dir) / "logs" / "pipeline"
            logs_root.mkdir(parents=True, exist_ok=True)
            log_path = logs_root / "2026-04-13.jsonl"
            rows = [
                {"event": "pipeline_started", "component": "pipeline", "level": "info"},
                {"event": "data_provider_used", "component": "collector", "level": "info", "ticker": "AAPL", "source": "yfinance"},
                {"event": "fmp_company_profile_throttled", "component": "collector", "level": "info", "ticker": "AAPL"},
                {"event": "pipeline_completed", "component": "pipeline", "level": "info"},
            ]
            log_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            payload = build_api_status_payload(date(2026, 4, 13), [WatchlistItem(ticker="AAPL", name="Apple Inc.")], logs_root=logs_root)

        summary = payload["summary"]
        matrix = payload["ticker_matrix"][0]
        self.assertEqual(summary["providers"]["fmp"]["overall_status"], "limited")
        self.assertEqual(summary["providers"]["fmp"]["throttled_tickers"], 1)
        self.assertEqual(matrix["fmp"], "throttled")

    def test_write_api_status_outputs_writes_json_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logs_root = root / "logs" / "pipeline"
            output_root = root / "output"
            logs_root.mkdir(parents=True, exist_ok=True)
            (logs_root / "2026-04-13.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "pipeline_started", "component": "pipeline", "level": "info"}),
                        json.dumps({"event": "data_provider_used", "component": "collector", "level": "info", "ticker": "AAPL", "source": "yfinance"}),
                        json.dumps({"event": "pipeline_completed", "component": "pipeline", "level": "info"}),
                    ]
                ),
                encoding="utf-8",
            )

            paths = write_api_status_outputs(date(2026, 4, 13), [WatchlistItem(ticker="AAPL", name="Apple Inc.")], output_root=output_root, logs_root=logs_root)

            self.assertTrue(paths["api_status"].exists())
            self.assertTrue(paths["api_ticker_matrix_json"].exists())
            self.assertTrue(paths["api_ticker_matrix_csv"].exists())


if __name__ == "__main__":
    unittest.main()

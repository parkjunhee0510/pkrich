from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.output.intraday_refresh import write_intraday_refresh_outputs
from src.output.json_export import write_json_outputs
from src.types import CollectedTickerData

from tests.test_output import _sample_analysis


class IntradayRefreshOutputTests(unittest.TestCase):
    def test_intraday_refresh_updates_index_and_latest_shard_price_fields(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_path = Path(temp_dir)
            output_root = temp_path / "output"
            (temp_path / "web").mkdir(parents=True, exist_ok=True)

            write_json_outputs(
                [_sample_analysis()],
                date(2026, 4, 8),
                output_root=output_root,
                market_overview=[],
            )

            collected = {
                "AAPL": CollectedTickerData(
                    ticker="AAPL",
                    name="Apple Inc.",
                    sector="Technology",
                    price=111.25,
                    change_percent=2.5,
                    currency="USD",
                    market_cap="1.10T",
                    pe_ratio="26.00",
                    summary_note="intraday",
                    eps="6.20",
                    week52_high="120.00",
                    week52_low="80.00",
                    sma_50="101.00",
                    sma_200="97.00",
                    volume="15.00M",
                    avg_volume_3m="14.00M",
                    price_to_book="8.90",
                    dividend_yield="0.50%",
                    forward_eps="7.10",
                    earnings_growth="+13.00% YoY",
                    short_float_pct="3.10%",
                    short_ratio="2.00일",
                    analyst_target_price="135.00 USD",
                    analyst_recommendation="Buy",
                    analyst_count="19명",
                    held_by_insiders="0.08%",
                    held_by_institutions="62.00%",
                    implied_volatility="29.00%",
                    price_change_7d="+4.50%",
                    price_change_30d="+9.25%",
                    atr_14d="5.50",
                    atr_percent="2.10%",
                    relative_volume="1.55x",
                    gap_percent="+1.20%",
                    price_vs_sma50="+4.20%",
                    price_vs_sma200="+9.60%",
                    week52_position="79%",
                    rs_vs_spy="+5.00%",
                    rs_vs_sector_etf="+3.00%",
                    open_price="109.50",
                    high_price="112.00",
                    low_price="108.75",
                    close_price="111.25",
                    day_volume="15.00M",
                    options_summary={"put_call_ratio": "0.68", "tone": "bullish"},
                )
            }

            fake_datastore = type(
                "FakeDatastore",
                (),
                {
                    "load_period_changes": lambda self, run_date: {"AAPL": {"7d": "+4.50%", "30d": "+9.25%"}},
                    "query_prices": lambda self: [
                        {
                            "date": "2026-04-08",
                            "ticker": "AAPL",
                            "price": "111.25 USD",
                            "daily_change": "+2.50%",
                            "market_cap": "1.10T",
                            "trailing_pe": "26.00",
                            "eps": "6.20",
                            "52w_high": "120.00",
                            "52w_low": "80.00",
                            "open": "109.50",
                            "high": "112.00",
                            "low": "108.75",
                            "close": "111.25",
                            "volume": "15.00M",
                        }
                    ],
                },
            )()

            with patch("src.output.intraday_refresh.get_datastore", return_value=fake_datastore):
                write_intraday_refresh_outputs(
                    collected,
                    date(2026, 4, 8),
                    market_overview=[{"label": "S&P 500", "symbol": "^GSPC", "price": "5300", "change": "+0.4%"}],
                    macro_context={"vix": {"level": "18.0"}},
                    output_root=output_root,
                )

            index_payload = json.loads((output_root / "data" / "index.json").read_text(encoding="utf-8"))
            latest_payload = json.loads((output_root / "data" / "tickers" / "AAPL" / "latest.json").read_text(encoding="utf-8"))
            price_history_payload = json.loads((output_root / "data" / "price_history.json").read_text(encoding="utf-8"))

            self.assertEqual(index_payload["tickers"][0]["data_snapshot"]["Price"], "111.25 USD")
            self.assertEqual(index_payload["tickers"][0]["data_snapshot"]["Daily Change"], "+2.50%")
            self.assertEqual(index_payload["tickers"][0]["period_changes"]["7d"], "+4.50%")
            self.assertEqual(index_payload["tickers"][0]["price_action"]["relative_volume"], "1.55x")
            self.assertEqual(latest_payload["payload"]["fundamentals"]["analyst_target_price"], "135.00 USD")
            self.assertEqual(price_history_payload[0]["price"], "111.25 USD")
            self.assertIn("intraday_refreshed_at", index_payload)

    def test_intraday_refresh_syncs_dashboard_json_to_web_mirror(self) -> None:
        """Regression: intraday refresh must also sync dashboard.json so the
        frontend never loses its primary payload after an intraday run.
        Previously only index.json and price_history.json were synced, which
        left web/public/output/data/dashboard.json stale or missing.
        """
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_path = Path(temp_dir)
            output_root = temp_path / "output"
            (temp_path / "web").mkdir(parents=True, exist_ok=True)

            with patch.dict(os.environ, {"EMIT_LEGACY_DASHBOARD": "true"}):
                write_json_outputs(
                    [_sample_analysis()],
                    date(2026, 4, 8),
                    output_root=output_root,
                    market_overview=[],
                )

            source_dashboard = output_root / "data" / "dashboard.json"
            mirror_dashboard = temp_path / "web" / "public" / "output" / "data" / "dashboard.json"
            self.assertTrue(source_dashboard.exists(), "precondition: write_json_outputs produces dashboard.json")
            # Remove the mirror to prove the intraday refresh repopulates it.
            if mirror_dashboard.exists():
                mirror_dashboard.unlink()

            fake_datastore = type(
                "FakeDatastore",
                (),
                {
                    "load_period_changes": lambda self, run_date: {},
                    "query_prices": lambda self: [],
                },
            )()

            with patch("src.output.intraday_refresh.get_datastore", return_value=fake_datastore):
                write_intraday_refresh_outputs(
                    {},
                    date(2026, 4, 8),
                    output_root=output_root,
                )

            self.assertTrue(
                mirror_dashboard.exists(),
                "intraday_refresh must sync dashboard.json into web/public/output/data/",
            )
            self.assertEqual(
                source_dashboard.read_bytes(),
                mirror_dashboard.read_bytes(),
                "mirrored dashboard.json must match source byte-for-byte",
            )


if __name__ == "__main__":
    unittest.main()

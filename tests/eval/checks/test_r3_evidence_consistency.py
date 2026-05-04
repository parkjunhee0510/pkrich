from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.r3_evidence_consistency import R3EvidenceConsistency
from tests.eval.fixtures.builders import make_dataset


def _ticker_record(
    ticker: str,
    *,
    execution_mode: str,
    raw: str = "sha256:raw",
    macro: str = "sha256:macro",
    regime: str = "sha256:regime",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_date": "2026-04-28",
        "stage": "analyzer",
        "scope": "ticker",
        "module": "signal_takeaway_module",
        "ticker": ticker,
        "execution_mode": execution_mode,
        "raw_payload_hash": raw,
        "macro_context_hash": macro,
        "market_regime_hash": regime,
        "upstream_payload_hash": "sha256:upstream",
        "macro_context_present": True,
        "market_regime_present": True,
    }


def _committee_record(role: str, *, analysis_hash: str = "sha256:analysis") -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_date": "2026-04-28",
        "stage": "committee",
        "scope": "committee_role",
        "module": f"committee_{role}",
        "ticker": "AAPL",
        "role": role,
        "round": "economy",
        "analysis_payload_hash": analysis_hash,
        "macro_context_present": False,
        "market_regime_present": False,
    }


class TestR3EvidenceConsistency(unittest.TestCase):
    def test_info_when_no_manifests_exist(self) -> None:
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28), llm_evidence_overrides={})

        result = R3EvidenceConsistency().run(ds)

        self.assertEqual(result.severity, "info")
        self.assertEqual(result.metrics["total_records"], 0.0)

    def test_pass_when_ticker_records_share_hashes(self) -> None:
        ds = make_dataset(
            tickers=("AAPL",),
            end=date(2026, 4, 28),
            llm_evidence_overrides={
                date(2026, 4, 28): [
                    _ticker_record("AAPL", execution_mode="full"),
                    _ticker_record("AAPL", execution_mode="llm_only"),
                    {
                        "scope": "run",
                        "module": "macro_narrative",
                        "run_date": "2026-04-28",
                        "macro_context_hash": "sha256:macro",
                        "market_regime_hash": "sha256:regime",
                    },
                ]
            },
        )

        result = R3EvidenceConsistency().run(ds)

        self.assertEqual(result.severity, "pass")
        self.assertEqual(result.metrics["mismatch_count"], 0.0)

    def test_fail_when_deep_uses_different_macro_hash(self) -> None:
        ds = make_dataset(
            tickers=("AAPL",),
            end=date(2026, 4, 28),
            llm_evidence_overrides={
                date(2026, 4, 28): [
                    _ticker_record("AAPL", execution_mode="full", macro="sha256:macro-a"),
                    _ticker_record("AAPL", execution_mode="llm_only", macro="sha256:macro-b"),
                ]
            },
        )

        result = R3EvidenceConsistency().run(ds)

        self.assertEqual(result.severity, "fail")
        self.assertEqual(result.metrics["mismatch_count"], 1.0)
        self.assertEqual(result.findings[0].ticker, "AAPL")

    def test_warn_when_committee_macro_linkage_is_missing(self) -> None:
        ds = make_dataset(
            tickers=("AAPL",),
            end=date(2026, 4, 28),
            llm_evidence_overrides={
                date(2026, 4, 28): [
                    _ticker_record("AAPL", execution_mode="full"),
                    _committee_record("growth_analyst"),
                    _committee_record("pm"),
                ]
            },
        )

        result = R3EvidenceConsistency().run(ds)

        self.assertEqual(result.severity, "warn")
        self.assertEqual(result.metrics["warning_count"], 2.0)

    def test_fail_when_committee_roles_use_different_analysis_hashes(self) -> None:
        ds = make_dataset(
            tickers=("AAPL",),
            end=date(2026, 4, 28),
            llm_evidence_overrides={
                date(2026, 4, 28): [
                    _committee_record("growth_analyst", analysis_hash="sha256:a"),
                    _committee_record("pm", analysis_hash="sha256:b"),
                ]
            },
        )

        result = R3EvidenceConsistency().run(ds)

        self.assertEqual(result.severity, "fail")
        self.assertEqual(result.metrics["mismatch_count"], 1.0)


if __name__ == "__main__":
    unittest.main()

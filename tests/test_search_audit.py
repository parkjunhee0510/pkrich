import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.analyzer.search_audit import build_search_audit_payload
from src.types import TickerAnalysis


def _analysis(
    *,
    ticker: str = "MOD",
    summary: str = "Data center revenue grew 78%.",
    financial_highlights: list[str] | None = None,
    risks_or_watchpoints: list[str] | None = None,
    key_news: list[str] | None = None,
    signal_or_takeaway: str = "",
) -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        name=f"{ticker} Inc.",
        date="2026-05-07",
        summary=summary,
        key_news=key_news or [],
        news_references=[],
        financial_highlights=financial_highlights or [],
        risks_or_watchpoints=risks_or_watchpoints or [],
        signal_or_takeaway=signal_or_takeaway,
        data_snapshot={},
    )


def _search_evidence(items: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "date": "2026-05-07",
        "provider": "cache",
        "items": items,
        "by_ticker": {},
        "run_summary": {},
    }


def _evidence(
    *,
    ticker: str = "MOD",
    title: str = "Modine data center revenue",
    snippet: str = "Data center revenue grew 78%.",
    url: str = "https://example.com/mod-results",
    source_domain: str = "example.com",
) -> dict:
    return {
        "ticker": ticker,
        "query": f"{ticker} latest results",
        "source_domain": source_domain,
        "title": title,
        "url": url,
        "published_at": "2026-05-06",
        "snippet": snippet,
        "evidence_type": "earnings",
        "relevance_score": 0.9,
        "freshness_hours": 24,
        "query_hash": "sha256:test",
    }


class SearchAuditTests(unittest.TestCase):
    def test_build_search_audit_marks_supported_claims(self) -> None:
        payload = build_search_audit_payload(
            run_date=date(2026, 5, 7),
            analyses=[_analysis()],
            search_evidence=_search_evidence([_evidence()]),
        )

        ticker_payload = payload["tickers"][0]
        issue = ticker_payload["issues"][0]

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["date"], "2026-05-07")
        self.assertEqual(ticker_payload["ticker"], "MOD")
        self.assertEqual(ticker_payload["verdict"], "pass")
        self.assertEqual(ticker_payload["checked_claims"], 1)
        self.assertEqual(ticker_payload["supported_claims"], 1)
        self.assertEqual(ticker_payload["conflicting_claims"], 0)
        self.assertEqual(ticker_payload["missing_evidence_claims"], 0)
        self.assertEqual(ticker_payload["insufficient_evidence_claims"], 0)
        self.assertEqual(issue["status"], "supported")
        self.assertEqual(issue["source_url"], "https://example.com/mod-results")

    def test_build_search_audit_marks_conflicting_numeric_claims(self) -> None:
        payload = build_search_audit_payload(
            run_date=date(2026, 5, 7),
            analyses=[_analysis()],
            search_evidence=_search_evidence([
                _evidence(snippet="Data center revenue grew 30%.")
            ]),
        )

        ticker_payload = payload["tickers"][0]
        issue = ticker_payload["issues"][0]

        self.assertEqual(ticker_payload["verdict"], "warn")
        self.assertEqual(ticker_payload["checked_claims"], 1)
        self.assertEqual(ticker_payload["supported_claims"], 0)
        self.assertEqual(ticker_payload["conflicting_claims"], 1)
        self.assertEqual(issue["status"], "conflicting")
        self.assertEqual(issue["source_url"], "https://example.com/mod-results")

    def test_build_search_audit_marks_missing_evidence_when_same_ticker_sources_are_unrelated(self) -> None:
        payload = build_search_audit_payload(
            run_date=date(2026, 5, 7),
            analyses=[_analysis(summary="Backlog reached 5.2 billion dollars.")],
            search_evidence=_search_evidence([
                _evidence(snippet="Gross margin improved during the quarter.")
            ]),
        )

        ticker_payload = payload["tickers"][0]
        issue = ticker_payload["issues"][0]

        self.assertEqual(ticker_payload["verdict"], "warn")
        self.assertEqual(ticker_payload["missing_evidence_claims"], 1)
        self.assertEqual(issue["status"], "missing_evidence")
        self.assertEqual(issue["source_url"], "")

    def test_build_search_audit_marks_insufficient_evidence_when_ticker_has_no_sources(self) -> None:
        payload = build_search_audit_payload(
            run_date=date(2026, 5, 7),
            analyses=[_analysis()],
            search_evidence=_search_evidence([]),
        )

        ticker_payload = payload["tickers"][0]
        issue = ticker_payload["issues"][0]

        self.assertEqual(ticker_payload["verdict"], "warn")
        self.assertEqual(ticker_payload["insufficient_evidence_claims"], 1)
        self.assertEqual(issue["status"], "insufficient_evidence")
        self.assertEqual(issue["source_url"], "")

    def test_build_search_audit_reports_info_when_analysis_has_no_claims(self) -> None:
        payload = build_search_audit_payload(
            run_date=date(2026, 5, 7),
            analyses=[
                _analysis(
                    summary="N/A",
                    financial_highlights=["-"],
                    risks_or_watchpoints=["N/A"],
                    key_news=[],
                    signal_or_takeaway="",
                )
            ],
            search_evidence=_search_evidence([_evidence()]),
        )

        ticker_payload = payload["tickers"][0]

        self.assertEqual(ticker_payload["verdict"], "info")
        self.assertEqual(ticker_payload["checked_claims"], 0)
        self.assertEqual(ticker_payload["issues"], [])

    def test_write_search_audit_output_writes_and_syncs_web_public_copy(self) -> None:
        from src.output.search_audit_json import write_search_audit_output

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)
            payload = build_search_audit_payload(
                run_date=date(2026, 5, 7),
                analyses=[_analysis()],
                search_evidence=_search_evidence([_evidence()]),
            )

            path = write_search_audit_output(payload, output_root=root / "output")

            source = json.loads(path.read_text(encoding="utf-8"))
            mirror = json.loads(
                (root / "web" / "public" / "output" / "data" / "search_audit.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(path, root / "output" / "data" / "search_audit.json")
        self.assertEqual(source["schema_version"], 1)
        self.assertEqual(source, mirror)


if __name__ == "__main__":
    unittest.main()

"""SEC Form 4 insider transaction parser.

Extends the existing SEC EDGAR integration to parse Form 4 filings
for insider buy/sell activity. This is a free fallback/complement
to the FMP insider trading data.
"""

from __future__ import annotations

import gzip
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any
from urllib import request
from urllib.error import URLError

from src.collector.sec_edgar import sec_user_agent
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
_REQUEST_DELAY = 0.15  # SEC allows 10 req/s; stay well under
_LAST_REQUEST_AT: float = 0.0


def collect_insider_transactions(
    cik: str,
    run_date: date,
    *,
    max_filings: int = 5,
    lookback_days: int = 90,
) -> list[dict[str, str]]:
    """Parse recent Form 4 filings for insider transactions."""
    if not cik:
        return []
    if not can_open_tcp_connection("data.sec.gov", 443):
        return []

    try:
        payload = _download_submissions(cik)
        form4_filings = _extract_form4_filings(payload, run_date, max_filings, lookback_days)
        if not form4_filings:
            return []

        transactions: list[dict[str, str]] = []
        for filing in form4_filings:
            parsed = _parse_form4_filing(cik, filing)
            transactions.extend(parsed)

        if transactions:
            record_pipeline_event(
                "collector", "info", "sec_form4_parsed",
                cik=cik, transactions=len(transactions),
            )
        return transactions[:10]
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "sec_form4_failed",
            cik=cik, error=str(exc),
        )
        return []


def _throttle() -> None:
    global _LAST_REQUEST_AT  # noqa: PLW0603
    now = time.monotonic()
    elapsed = now - _LAST_REQUEST_AT
    if elapsed < _REQUEST_DELAY:
        time.sleep(_REQUEST_DELAY - elapsed)
    _LAST_REQUEST_AT = time.monotonic()


def _download_submissions(cik: str) -> dict[str, Any]:
    url = _SEC_SUBMISSIONS_URL.format(cik=cik)
    _throttle()
    req = request.Request(url, headers={
        "User-Agent": sec_user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    })
    with request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
        encoding = str(resp.headers.get("Content-Encoding", "")).lower()
        if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


def _extract_form4_filings(
    payload: dict[str, Any],
    run_date: date,
    max_filings: int,
    lookback_days: int,
) -> list[dict[str, str]]:
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = run_date - timedelta(days=lookback_days)
    results: list[dict[str, str]] = []

    for i, form_type in enumerate(forms):
        if form_type not in ("4", "4/A"):
            continue
        if i >= len(dates) or i >= len(accessions) or i >= len(primary_docs):
            break
        try:
            filing_date = date.fromisoformat(dates[i])
        except (ValueError, TypeError):
            continue
        if filing_date < cutoff:
            continue

        results.append({
            "date": dates[i],
            "accession": accessions[i].replace("-", ""),
            "document": primary_docs[i],
        })
        if len(results) >= max_filings:
            break

    return results


def _parse_form4_filing(cik: str, filing: dict[str, str]) -> list[dict[str, str]]:
    """Download and parse a single Form 4 XML filing."""
    doc = filing.get("document", "")
    if not doc.endswith(".xml"):
        # Try to find the XML document
        doc = doc.replace(".htm", ".xml").replace(".html", ".xml")
        if not doc.endswith(".xml"):
            return []

    url = _SEC_ARCHIVES_URL.format(
        cik=cik.lstrip("0"),
        accession=filing["accession"],
        document=doc,
    )

    try:
        _throttle()
        req = request.Request(url, headers={
            "User-Agent": sec_user_agent(),
            "Accept": "application/xml",
        })
        with request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
    except (URLError, TimeoutError):
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    # Extract reporter name
    reporter_name = _xml_text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName", "Unknown")
    reporter_title = _xml_text(root, ".//reportingOwner/reportingOwnerRelationship/officerTitle", "")
    is_director = _xml_text(root, ".//reportingOwner/reportingOwnerRelationship/isDirector", "0")
    is_officer = _xml_text(root, ".//reportingOwner/reportingOwnerRelationship/isOfficer", "0")

    if not reporter_title:
        if is_officer == "1":
            reporter_title = "Officer"
        elif is_director == "1":
            reporter_title = "Director"

    transactions: list[dict[str, str]] = []
    for tx_elem in root.findall(".//nonDerivativeTransaction"):
        tx_date = _xml_text(tx_elem, ".//transactionDate/value", filing.get("date", ""))
        shares_str = _xml_text(tx_elem, ".//transactionAmounts/transactionShares/value", "0")
        price_str = _xml_text(tx_elem, ".//transactionAmounts/transactionPricePerShare/value", "0")
        acq_disp = _xml_text(tx_elem, ".//transactionAmounts/transactionAcquiredDisposedCode/value", "")

        try:
            shares = float(shares_str)
            price = float(price_str)
        except (ValueError, TypeError):
            continue

        value = shares * price
        tx_type = "buy" if acq_disp.upper() == "A" else "sale" if acq_disp.upper() == "D" else "other"

        transactions.append({
            "name": reporter_name,
            "title": reporter_title,
            "type": tx_type,
            "shares": f"{int(shares):,}",
            "value": f"${value:,.0f}" if value > 0 else "N/A",
            "date": tx_date,
            "source": "SEC Form 4",
        })

    return transactions


def _xml_text(elem: ET.Element, path: str, default: str = "") -> str:
    found = elem.find(path)
    if found is not None and found.text:
        return found.text.strip()
    return default

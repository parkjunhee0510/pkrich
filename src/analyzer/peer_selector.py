from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.analyzer import research_note
from src.types import PeerInfo


class PeerSelector:
    def __init__(self, *, min_peers: int = 3, max_peers: int = 5) -> None:
        self.min_peers = min_peers
        self.max_peers = max_peers

    def select_peers(
        self,
        ticker: str,
        sector: str,
        market_cap: str,
        candidates: list[dict[str, Any]],
    ) -> list[PeerInfo]:
        normalized = [self._normalize_candidate(ticker, sector, candidate) for candidate in candidates]
        usable = [candidate for candidate in normalized if candidate is not None]
        target_market_cap = self._parse_numeric(market_cap)

        size_filtered = usable
        if target_market_cap and target_market_cap > 0:
            same_size = []
            for candidate in usable:
                peer_market_cap = self._parse_numeric(candidate.market_cap)
                if peer_market_cap is None:
                    continue
                if target_market_cap * 0.5 <= peer_market_cap <= target_market_cap * 1.5:
                    same_size.append(candidate)
            if same_size:
                size_filtered = same_size

        ranked = sorted(size_filtered, key=self._sort_key)
        if len(ranked) < self.min_peers:
            seen = {peer.ticker for peer in ranked}
            for candidate in sorted(usable, key=self._sort_key):
                if candidate.ticker in seen:
                    continue
                ranked.append(candidate)
                seen.add(candidate.ticker)
                if len(ranked) >= self.min_peers:
                    break

        return ranked[: self.max_peers]

    @staticmethod
    def serialize(peers: list[PeerInfo]) -> list[dict[str, Any]]:
        return [asdict(peer) for peer in peers]

    def _normalize_candidate(
        self,
        owner_ticker: str,
        sector: str,
        candidate: dict[str, Any],
    ) -> PeerInfo | None:
        peer_ticker = str(candidate.get("ticker", "")).strip().upper()
        if not peer_ticker or peer_ticker == owner_ticker.upper():
            return None

        normalized_sector = str(candidate.get("sector") or sector or "N/A").strip() or "N/A"
        coverage = float(candidate.get("data_coverage_score", 0.0) or 0.0)
        if coverage <= 0:
            coverage = self._coverage_score(candidate)

        return PeerInfo(
            ticker=peer_ticker,
            sector=normalized_sector,
            market_cap=str(candidate.get("market_cap", "N/A")),
            avg_volume=str(candidate.get("avg_volume", "N/A")),
            data_coverage_score=coverage,
            pe_ratio=str(candidate.get("pe_ratio", "N/A")),
            roe=str(candidate.get("roe", "N/A")),
            gross_margin=str(candidate.get("gross_margin", "N/A")),
            price_change_30d=str(candidate.get("price_change_30d", "N/A")),
            rs_vs_spy=str(candidate.get("rs_vs_spy", "N/A")),
            revenue_growth=str(candidate.get("revenue_growth", candidate.get("earnings_growth", "N/A"))),
            dividend_yield=str(candidate.get("dividend_yield", "N/A")),
        )

    def _coverage_score(self, candidate: dict[str, Any]) -> float:
        fields = (
            "market_cap",
            "avg_volume",
            "pe_ratio",
            "roe",
            "gross_margin",
            "price_change_30d",
            "rs_vs_spy",
            "revenue_growth",
            "earnings_growth",
            "dividend_yield",
        )
        return float(sum(1 for field in fields if self._is_present(candidate.get(field))))

    def _sort_key(self, peer: PeerInfo) -> tuple[float, float, str]:
        liquidity_proxy = self._parse_numeric(peer.avg_volume)
        if liquidity_proxy is None:
            liquidity_proxy = self._parse_numeric(peer.market_cap) or 0.0
        return (-peer.data_coverage_score, -liquidity_proxy, peer.ticker)

    @staticmethod
    def _is_present(value: Any) -> bool:
        text = str(value or "").strip()
        return bool(text and text != "N/A")

    @staticmethod
    def _parse_numeric(value: Any) -> float | None:
        return research_note._parse_float_from_text(value)

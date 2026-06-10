"""Concrete DataProvider implementations.

Each file in this package implements the DataProvider contract for a single
external source (yfinance, FMP, Finnhub, Polygon, SEC EDGAR, Stooq,
AlphaVantage). Bootstrap (src/collector/bootstrap.py) wires selected
providers into the CollectionOrchestrator.

Phase 1-0e Step 2 landed yfinance_provider.py first because yfinance is the
most stable and widest-coverage source. Other providers are extracted in
later migration steps.
"""
from __future__ import annotations

from src.collector.providers.alphavantage_provider import AlphaVantageProvider
from src.collector.providers.finnhub_provider import FinnhubProvider
from src.collector.providers.fmp_provider import FMPProvider
from src.collector.providers.polygon_provider import PolygonProvider
from src.collector.providers.sector_etf_provider import SectorEtfProvider
from src.collector.providers.stooq_provider import StooqProvider
from src.collector.providers.toss_invest_provider import TossInvestProvider
from src.collector.providers.yfinance_provider import YFinanceProvider

__all__ = [
    "AlphaVantageProvider",
    "FMPProvider",
    "FinnhubProvider",
    "PolygonProvider",
    "SectorEtfProvider",
    "StooqProvider",
    "TossInvestProvider",
    "YFinanceProvider",
]

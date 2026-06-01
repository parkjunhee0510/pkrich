from datetime import date

from src.types import PortfolioPosition, PortfolioSummary, WatchlistItem


def policy_payload() -> dict:
    return {
        "schema_version": 1,
        "date": date(2026, 5, 19).isoformat(),
        "events": [
            {
                "id": "event-export",
                "category": "export-control",
                "headline": "USTR semiconductor export control review",
                "summary": "반도체 수출통제 강화 가능성이 관찰됐습니다.",
                "source_url": "https://ustr.gov/example",
                "source_domain": "ustr.gov",
                "published_at": "2026-05-19T00:00:00Z",
                "confidence": 0.95,
                "first_seen": "2026-05-19",
                "last_seen": "2026-05-19",
            }
        ],
        "impacts_by_event": {
            "event-export": [
                {
                    "ticker": "NVDA",
                    "direction": "negative",
                    "strength": "direct",
                    "score": -0.78,
                    "confidence": 0.87,
                    "rationale": "수출통제 강화는 AI 칩 공급망에 부담으로 작용할 수 있습니다.",
                }
            ]
        },
    }


def held_nvda_portfolio() -> PortfolioSummary:
    return PortfolioSummary(
        positions=[
            PortfolioPosition(
                ticker="NVDA",
                shares=1.0,
                avg_cost=100.0,
                currency="USD",
                market_price=120.0,
                market_value=120.0,
                cost_basis=100.0,
                unrealized_pnl=20.0,
                unrealized_return_pct=20.0,
            )
        ],
        total_market_value=120.0,
        total_cost_basis=100.0,
        total_unrealized_pnl=20.0,
        total_unrealized_return_pct=20.0,
    )


def nvda_watchlist() -> list[WatchlistItem]:
    return [WatchlistItem(ticker="NVDA", name="NVIDIA", sector="Technology")]


def ai_sector_payload() -> dict:
    return {
        "sectors": [
            {"id": "ai_infra", "name": "AI 인프라", "tickers": [{"ticker": "NVDA", "name": "NVIDIA"}]}
        ]
    }

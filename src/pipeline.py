from __future__ import annotations

from datetime import date
from pathlib import Path

from src.analyzer.research_note import analyze_tickers
from src.collector.news_rss import collect_news_for_watchlist
from src.collector.price import collect_market_data, collect_market_overview
from src.output.markdown import write_outputs
from src.output.slack import send_daily_summary
from src.utils.config import load_portfolio, load_watchlist
from src.utils.datastore import get_datastore
from src.utils.env import load_dotenv
from src.utils.portfolio import calculate_portfolio_summary
from src.utils.pipeline_logging import finalize_pipeline_logging, record_pipeline_event, start_pipeline_logging
from src.utils.signal_tracker import load_signal_stats, record_signals, update_signal_returns


def run_pipeline(run_date: date | None = None) -> None:
    load_dotenv()
    effective_date = run_date or date.today()
    start_pipeline_logging(effective_date)
    record_pipeline_event("pipeline", "info", "pipeline_started", run_date=effective_date.isoformat())

    success = False
    try:
        watchlist = load_watchlist()
        portfolio_holdings = load_portfolio()
        collected = collect_market_data(watchlist, effective_date)
        market_overview = collect_market_overview()
        news_map = collect_news_for_watchlist(watchlist, effective_date)
        analyses = analyze_tickers(watchlist, collected, news_map, effective_date)
        portfolio_summary = calculate_portfolio_summary(portfolio_holdings, collected)
        signal_csv_path = Path("output") / "data" / "signal_tracker.csv"
        price_lookup = {ticker: data.price for ticker, data in collected.items() if data.price is not None}
        datastore = get_datastore(output_root=Path("output"))
        historical_price_rows = datastore.query_prices(tickers=[item.ticker for item in watchlist])
        updated_signals = update_signal_returns(
            signal_csv_path,
            effective_date,
            price_lookup,
            price_history_rows=historical_price_rows,
        )
        record_signals(analyses, effective_date, price_lookup, signal_csv_path)
        signal_stats = load_signal_stats(signal_csv_path)
        direct_period_changes = {
            ticker: {"7d": data.price_change_7d, "30d": data.price_change_30d}
            for ticker, data in collected.items()
        }
        output_paths = write_outputs(
            analyses,
            effective_date,
            market_overview=market_overview,
            direct_period_changes=direct_period_changes,
            portfolio_summary=portfolio_summary,
            signal_stats=signal_stats,
        )
        send_daily_summary(
            analyses,
            effective_date,
            market_overview=market_overview,
            daily_note_path=output_paths.get("daily_path"),
            weekly_note_path=output_paths.get("weekly_path"),
            portfolio_summary=portfolio_summary,
        )
        success = True
        record_pipeline_event("pipeline", "info", "pipeline_completed", ticker_count=len(analyses), updated_signal_rows=updated_signals)
    except Exception as exc:
        record_pipeline_event(
            "pipeline",
            "error",
            "pipeline_failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise
    finally:
        finalize_pipeline_logging(success)

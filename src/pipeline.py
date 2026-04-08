from __future__ import annotations

from datetime import date

from src.analyzer.research_note import analyze_tickers
from src.collector.news_rss import collect_news_for_watchlist
from src.collector.price import collect_market_data
from src.output.markdown import write_outputs
from src.utils.config import load_watchlist
from src.utils.env import load_dotenv


def run_pipeline(run_date: date | None = None) -> None:
    load_dotenv()
    effective_date = run_date or date.today()
    watchlist = load_watchlist()
    collected = collect_market_data(watchlist, effective_date)
    news_map = collect_news_for_watchlist(watchlist, effective_date)
    analyses = analyze_tickers(watchlist, collected, news_map, effective_date)
    write_outputs(analyses, effective_date)

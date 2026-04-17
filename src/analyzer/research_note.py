from __future__ import annotations

import re
from datetime import date
from typing import Any

from src.types import CollectedTickerData, NewsItem, TickerAnalysis, WatchlistItem


def _dedupe_news_items(items: list[NewsItem]) -> list[NewsItem]:
    ranked = sorted(
        items,
        key=lambda article: (
            _source_rank(article.source),
            article.published_at,
            article.importance_score,
        ),
        reverse=True,
    )

    deduped: list[NewsItem] = []
    normalized_seen: list[str] = []
    for article in ranked:
        normalized_title = _normalize_news_title(article.title)
        if not normalized_title:
            deduped.append(article)
            continue
        if any(_titles_similar(normalized_title, seen_title) for seen_title in normalized_seen):
            continue
        normalized_seen.append(normalized_title)
        deduped.append(article)
    return deduped[:5]


def _normalize_news_title(title: str) -> str:
    normalized = re.sub(r'[^a-z0-9가-힣\s]+', ' ', title.lower())
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _titles_similar(left: str, right: str) -> bool:
    if left == right:
        return True
    left_words = left.split()
    right_words = right.split()
    if not left_words or not right_words:
        return False
    prefix_matches = sum(1 for a, b in zip(left_words[:8], right_words[:8], strict=False) if a == b)
    prefix_threshold = min(4, len(left_words), len(right_words))
    if prefix_matches >= prefix_threshold:
        return True
    left_set = set(left_words)
    right_set = set(right_words)
    overlap = len(left_set & right_set)
    denominator = max(1, min(len(left_set), len(right_set)))
    return overlap / denominator >= 0.8


def _source_rank(source: str) -> int:
    normalized = source.strip().lower()
    if 'reuters' in normalized:
        return 6
    if normalized in {'associated press', 'the associated press', 'ap', 'ap news'}:
        return 5
    if 'sec edgar' in normalized:
        return 5
    if 'ir rss' in normalized or 'newsroom' in normalized or 'investor relations' in normalized:
        return 4
    if 'cnbc' in normalized:
        return 3
    if 'yahoo finance' in normalized:
        return 2
    if normalized == 'fallback':
        return -1
    return 1


def _build_ticker_context(analysis_input: dict[str, Any]) -> str:
    price_action = analysis_input.get('price_action', {})
    positioning = analysis_input.get('positioning', {})
    upcoming_events = analysis_input.get('upcoming_events', [])
    next_earnings_event = 'N/A'
    for event in upcoming_events:
        if str(event.get('type', '')).strip() == 'earnings':
            next_earnings_event = (
                f"{event.get('date', 'N/A')} {event.get('label', '실적 발표')} "
                f"(D-{event.get('days_until', 'N/A')})"
            )
            break

    price = analysis_input.get('price', 'N/A')
    sma50 = analysis_input.get('sma_50', 'N/A')
    sma200 = analysis_input.get('sma_200', 'N/A')
    week52_high = analysis_input.get('week52_high', 'N/A')
    week52_low = analysis_input.get('week52_low', 'N/A')
    currency = analysis_input.get('currency', 'USD')
    change_7d = analysis_input.get('price_change_7d', 'N/A')
    earnings_history = _render_earnings_history(analysis_input.get('quarterly_financials', []))
    signal_history = _render_signal_history(analysis_input.get('signal_history', []))
    sector_peer_context = _render_sector_peer_context(analysis_input.get('sector_peer_context', {}))
    options_summary = _render_options_summary(analysis_input.get('options_summary', {}))
    analyst_revisions = _render_analyst_revisions(analysis_input.get('analyst_estimate_revisions', {}))
    insider_activity = _render_insider_transactions(analysis_input.get('insider_transactions', []))
    options_flow = _render_options_flow(analysis_input.get('options_flow', {}))
    recommendation = _render_recommendation_trends(analysis_input.get('recommendation_trends', []))
    fundamentals = _render_fundamental_metrics(analysis_input.get('fundamental_metrics', {}))
    technicals = _render_technical_indicators(analysis_input.get('technical_indicators', {}))

    return (
        f"[Ticker] {analysis_input.get('ticker', 'N/A')} | {analysis_input.get('name', 'N/A')} | {analysis_input.get('sector', 'N/A')}\n"
        f"[Price] {price} {currency} (일간 {analysis_input.get('change_percent', 'N/A')}%) | 7D: {change_7d} | 30D: {price_action.get('price_change_30d', 'N/A')}\n"
        f"[Key Levels] SMA50: {sma50} {currency}, SMA200: {sma200} {currency}, "
        f"52W High: {week52_high}, 52W Low: {week52_low}\n"
        f"[Price Action] ATR(14): {price_action.get('atr_14d', 'N/A')} ({price_action.get('atr_percent', 'N/A')}), "
        f"RVOL: {price_action.get('relative_volume', 'N/A')}, Gap: {price_action.get('gap_percent', 'N/A')}, "
        f"vs SMA50: {price_action.get('price_vs_sma50', 'N/A')}, vs SMA200: {price_action.get('price_vs_sma200', 'N/A')}, "
        f"52W Position: {price_action.get('week52_position', 'N/A')}, RS vs SPY(30D): {price_action.get('rs_vs_spy', 'N/A')}, "
        f"RS vs Sector ETF: {price_action.get('rs_vs_sector_etf', 'N/A')}\n"
        f"[Positioning] Short Float: {positioning.get('short_float_pct', 'N/A')} / {positioning.get('short_ratio', 'N/A')}, "
        f"Analyst: {positioning.get('analyst_recommendation', 'N/A')} "
        f"({positioning.get('analyst_count', 'N/A')}, target {positioning.get('analyst_target_price', 'N/A')}), "
        f"Insiders: {positioning.get('held_by_insiders', 'N/A')}, Institutions: {positioning.get('held_by_institutions', 'N/A')}, "
        f"IV: {positioning.get('implied_volatility', 'N/A')}\n"
        f"[Earnings] Forward EPS: {analysis_input.get('forward_eps', 'N/A')}, TTM EPS: {analysis_input.get('eps', 'N/A')}, "
        f"EPS Growth: {analysis_input.get('earnings_growth', 'N/A')}, Next Earnings: {next_earnings_event}\n"
        f"[Options] {options_summary}\n"
        f"[Earnings History] {earnings_history}\n"
        f"[Analyst Revisions] {analyst_revisions}\n"
        f"[Insider Activity] {insider_activity}\n"
        f"[Options Flow] {options_flow}\n"
        f"[Recommendation] {recommendation}\n"
        f"[Signal History] {signal_history}\n"
        f"[Sector Comparison] {sector_peer_context}\n"
        f"[Fundamentals] {fundamentals}\n"
        f"[Technical Indicators] {technicals}"
    )


def _render_earnings_history(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return 'N/A'
    chunks: list[str] = []
    for row in rows[:4]:
        if not isinstance(row, dict):
            continue
        quarter = str(row.get('quarter', 'N/A'))
        eps = str(row.get('eps', 'N/A'))
        est = str(row.get('estimated_eps', 'N/A'))
        beat_miss = str(row.get('beat_miss', 'N/A'))
        surprise = str(row.get('surprise_pct', 'N/A'))
        chunks.append(f"{quarter}: EPS {eps} vs est {est} ({beat_miss} {surprise})")
    return ', '.join(chunks) if chunks else 'N/A'


def _render_signal_history(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return 'N/A'
    chunks: list[str] = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        signal_date = str(row.get('signal_date', 'N/A'))
        direction = str(row.get('signal_direction', 'neutral'))
        return_5d = str(row.get('return_5d', 'N/A'))
        catalyst = str(row.get('catalyst_tag', '일반 이슈'))
        chunks.append(f"{signal_date} {direction} {return_5d} (5d, {catalyst})")
    return ', '.join(chunks) if chunks else 'N/A'


def _render_sector_peer_context(context: Any) -> str:
    if not isinstance(context, dict) or not context:
        return 'N/A'
    sector = str(context.get('sector', 'N/A'))
    peer_count = str(context.get('peer_count', '0'))

    # Enhanced path: Finnhub peers with FMP metrics
    if context.get('enhanced') == 'true':
        peer_names = context.get('peer_names', 'N/A')
        return (
            f"vs {peer_names} ({sector}, {peer_count}개): "
            f"ROE 현재 {context.get('ticker_roe', 'N/A')} vs peer avg {context.get('peer_avg_roe', 'N/A')}, "
            f"Gross Margin 현재 {context.get('ticker_gross_margin', 'N/A')} vs peer avg {context.get('peer_avg_gross_margin', 'N/A')}, "
            f"PE {context.get('ticker_pe', 'N/A')}, 30D {context.get('ticker_price_change_30d', 'N/A')}, "
            f"RS {context.get('ticker_rs_vs_spy', 'N/A')}"
        )

    # Fallback: watchlist-internal
    return (
        f"{sector} peers {peer_count}개 평균: PE {context.get('average_pe', 'N/A')}, "
        f"30D {context.get('average_price_change_30d', 'N/A')}, "
        f"RS {context.get('average_rs_vs_spy', 'N/A')} "
        f"(vs 현재 종목: PE {context.get('ticker_pe', 'N/A')}, "
        f"30D {context.get('ticker_price_change_30d', 'N/A')}, "
        f"RS {context.get('ticker_rs_vs_spy', 'N/A')})"
    )


def _render_options_summary(summary: Any) -> str:
    if not isinstance(summary, dict) or not summary:
        return 'N/A'
    parts: list[str] = []
    for label, key in (
        ('Tone', 'tone'),
        ('Unusual', 'unusual_activity'),
        ('PCR', 'put_call_ratio'),
        ('OI Change', 'oi_change'),
        ('Expiry', 'expiry'),
        ('Call IV', 'atm_call_iv'),
        ('Put IV', 'atm_put_iv'),
        ('IV Pctl', 'iv_percentile_30d'),
    ):
        value = str(summary.get(key, '')).strip()
        if value and value != 'N/A':
            parts.append(f'{label} {value}')
    return ', '.join(parts) if parts else 'N/A'


def _render_analyst_revisions(revisions: Any) -> str:
    if not isinstance(revisions, dict) or not revisions:
        return 'N/A'
    return (
        f"EPS revision {revisions.get('revision_pct', 'N/A')} "
        f"({revisions.get('direction', 'N/A')}) | current ${revisions.get('current_eps', 'N/A')}"
    )


def _render_insider_transactions(transactions: Any) -> str:
    if not isinstance(transactions, list) or not transactions:
        return 'N/A'
    parts = [
        f"{transaction.get('title', '?')} {transaction.get('type', '?')} {transaction.get('value', '?')} ({transaction.get('date', '')})"
        for transaction in transactions[:3]
        if isinstance(transaction, dict)
    ]
    return '; '.join(parts) if parts else 'N/A'


def _render_options_flow(flow: Any) -> str:
    if not isinstance(flow, dict) or not flow:
        return 'N/A'
    parts: list[str] = []
    # Basic flow metrics
    pcr = flow.get('put_call_volume_ratio')
    if pcr:
        parts.append(f"PCR {pcr} ({flow.get('flow_sentiment', '')})")
    avg_iv = flow.get('avg_iv')
    if avg_iv:
        parts.append(f"avg IV {avg_iv}")
    # Tier A: Max Pain
    max_pain = flow.get('max_pain')
    if max_pain:
        parts.append(f"MaxPain {max_pain}")
    # Tier A: Implied Move
    implied_move = flow.get('implied_move')
    if implied_move:
        parts.append(f"IM {implied_move}")
    # Tier A: GEX
    gex = flow.get('gex_regime')
    if gex:
        parts.append(f"GEX {gex}")
    # Tier A: IV Skew
    skew = flow.get('iv_skew')
    if skew:
        parts.append(f"Skew {skew}")
    # Tier A: Net Delta
    net_delta = flow.get('net_delta')
    if net_delta:
        parts.append(f"NetΔ {net_delta}")
    # Tier A: OI-based P/C ratio
    oi_pcr = flow.get('put_call_oi_ratio')
    if oi_pcr:
        parts.append(f"OI P/C {oi_pcr}")
    # Tier A: OI concentration
    top_calls = flow.get('top_call_oi')
    if top_calls:
        parts.append(f"TopCalls {top_calls}")
    top_puts = flow.get('top_put_oi')
    if top_puts:
        parts.append(f"TopPuts {top_puts}")
    # Tier A: Unusual activity (premium-ranked)
    unusual = flow.get('unusual_activity')
    if unusual:
        parts.append(f"unusual: {unusual}")
    return ' | '.join(parts) if parts else 'N/A'


def _render_recommendation_trends(trends: Any) -> str:
    if not isinstance(trends, list) or not trends:
        return 'N/A'
    trend = trends[0]
    if not isinstance(trend, dict):
        return 'N/A'
    buys = int(str(trend.get('strong_buy', 0))) + int(str(trend.get('buy', 0)))
    sells = int(str(trend.get('sell', 0))) + int(str(trend.get('strong_sell', 0)))
    return (
        f"{trend.get('period', '')} {trend.get('consensus', 'N/A')} "
        f"({trend.get('trend', '')}): {buys}B/{trend.get('hold', '0')}H/{sells}S"
    )


def _render_technical_indicators(indicators: Any) -> str:
    if not isinstance(indicators, dict) or not indicators:
        return 'N/A'
    parts: list[str] = []
    rsi = indicators.get('rsi_14')
    if rsi:
        parts.append(f"RSI(14): {rsi} ({indicators.get('rsi_signal', '')})")
    macd = indicators.get('macd')
    if macd:
        parts.append(
            f"MACD: {macd}/{indicators.get('macd_signal', '')} "
            f"({indicators.get('macd_crossover', '')})"
        )
    bb_upper = indicators.get('bb_upper')
    if bb_upper:
        parts.append(
            f"BB: {indicators.get('bb_lower', '')}-{bb_upper} "
            f"({indicators.get('bb_position', '')}, BW {indicators.get('bb_bandwidth', '')})"
        )
    return ' | '.join(parts) if parts else 'N/A'


def _render_fundamental_metrics(metrics: Any) -> str:
    if not isinstance(metrics, dict) or not metrics:
        return 'N/A'
    parts: list[str] = []
    for key, label in (
        ('roe', 'ROE'), ('roic', 'ROIC'), ('current_ratio', 'CR'),
        ('debt_to_equity', 'D/E'), ('fcf_yield', 'FCF Yield'),
        ('net_debt_to_ebitda', 'ND/EBITDA'),
        ('gross_margin', 'Gross Margin'), ('operating_margin', 'Op Margin'),
        ('annual_dividend', 'Annual Div'), ('dividend_5y_cagr', 'Div CAGR 5Y'),
        ('consecutive_increase_years', 'Div Increase Yrs'), ('industry', 'Industry'),
    ):
        val = metrics.get(key)
        if val and val != 'N/A':
            trend = metrics.get(f'{key}_trend', '')
            parts.append(f"{label}: {val}" + (f" ({trend})" if trend else ""))
    return ', '.join(parts) if parts else 'N/A'


def _build_fallback_analyses(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    account_size_hint: float | None = None,
) -> list[TickerAnalysis]:
    return [
        _build_fallback_analysis(
            item,
            collected,
            news_map,
            run_date,
            account_size_hint=account_size_hint,
        )
        for item in watchlist
    ]


def _analysis_to_payload(analysis: TickerAnalysis) -> dict[str, Any]:
    return {
        field_name: getattr(analysis, field_name)
        for field_name in TickerAnalysis.__dataclass_fields__
    }


def _analysis_from_payload(payload: dict[str, Any]) -> TickerAnalysis:
    kwargs = {
        field_name: payload.get(field_name)
        for field_name in TickerAnalysis.__dataclass_fields__
    }
    return TickerAnalysis(**kwargs)


def _build_fallback_analysis(
    item: WatchlistItem,
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    signal_history: list[dict[str, str]] | None = None,
    sector_comparison: dict[str, Any] | None = None,
    peer_rank: dict[str, Any] | None = None,
    account_size_hint: float | None = None,
) -> TickerAnalysis:
    market = collected[item.ticker]
    ticker_news = news_map.get(item.ticker, [])
    price_text = f'{market.price:.2f} {market.currency}' if market.price is not None else '가격 정보 없음'
    change_text = f'{market.change_percent:+.2f}%' if market.change_percent is not None else '일간 등락률 정보 없음'
    news_context = _summarize_top_headline(ticker_news)
    sma50_text_summary = _with_currency(market.sma_50, market.currency)
    w52_pos = market.week52_position
    position_hint = ''
    if w52_pos != 'N/A':
        position_hint = f', 52주 범위 {w52_pos} 위치'

    # Sentence 1: price situation with technical context
    sentence1 = (
        f'{item.name}({item.ticker})는 {price_text} ({change_text})에 거래 중이며'
        f'{position_hint}'
        f'{f", SMA50 {sma50_text_summary}" if sma50_text_summary != "N/A" else ""}'
        f' 수준입니다.'
    )
    # Sentence 2: catalyst or top headline
    sentence2 = ''
    if news_context:
        sentence2 = f'주요 헤드라인: {news_context}'
    else:
        # Use upcoming events if available
        next_event = _build_watch_period(market.upcoming_events)
        if next_event and next_event != 'N/A':
            sentence2 = f'다음 일정: {next_event}'
        else:
            sentence2 = '주요 촉매 부재로 기술적 흐름 중심 모니터링 필요.'
    summary_parts = [sentence1, sentence2]
    return TickerAnalysis(
        ticker=item.ticker,
        name=item.name,
        date=run_date.isoformat(),
        summary=' '.join(summary_parts),
        key_news=[article.title for article in ticker_news[:5]],
        news_references=ticker_news[:5],
        financial_highlights=_build_fallback_financial_highlights(market),
        risks_or_watchpoints=_build_fallback_risks(market, ticker_news),
        signal_or_takeaway=_build_fallback_signal(market, ticker_news),
        data_snapshot=_build_snapshot(market),
        fundamentals=_build_fundamentals(market),
        price_action=_build_price_action(market),
        quarterly_financials=market.quarterly_financials,
        upcoming_events=market.upcoming_events[:5],
        trade_frame=_build_fallback_trade_frame(market, account_size_hint=account_size_hint),
        options_summary=market.options_summary,
        signal_history=signal_history or [],
        sector_comparison=sector_comparison or {},
        peer_rank=peer_rank or {},
        historical_prices=market.historical_prices,
    )


def _format_sector_comparison(raw_context: Any) -> dict[str, Any]:
    if not isinstance(raw_context, dict) or not raw_context:
        return {}

    average_pe = str(raw_context.get('average_pe', 'N/A'))
    ticker_pe = str(raw_context.get('ticker_pe', 'N/A'))
    average_rs = str(raw_context.get('average_rs_vs_spy', 'N/A'))
    ticker_rs = str(raw_context.get('ticker_rs_vs_spy', 'N/A'))
    average_return = str(raw_context.get('average_price_change_30d', 'N/A'))
    ticker_return = str(raw_context.get('ticker_price_change_30d', 'N/A'))
    sector = str(raw_context.get('sector', 'N/A'))
    peer_count = str(raw_context.get('peer_count', '0'))

    return {
        'summary': f'{sector} 피어 {peer_count}개 평균 대비 밸류에이션/모멘텀 비교',
        'pe_ratio': {
            'company': ticker_pe,
            'peer_average': average_pe,
            'difference': _difference_text(ticker_pe, average_pe),
        },
        'rs_vs_spy': {
            'company': ticker_rs,
            'peer_average': average_rs,
            'difference': _difference_text(ticker_rs, average_rs),
        },
        'price_change_30d': {
            'company': ticker_return,
            'peer_average': average_return,
            'difference': _difference_text(ticker_return, average_return),
        },
    }


def _difference_text(company_value: str, peer_value: str) -> str | None:
    company_numeric = _parse_float_from_text(company_value)
    peer_numeric = _parse_float_from_text(peer_value)
    if company_numeric is None or peer_numeric is None:
        return None
    delta = company_numeric - peer_numeric
    return f'{delta:+.2f}'


def _build_fallback_signal(market: CollectedTickerData, ticker_news: list[NewsItem]) -> str:
    if market.price is None:
        return '중립 관찰 — 가격 데이터 미수집 | 진입존 확인 불가 / 무효화 데이터 수집 필요'

    direction = '중립 관찰'
    catalyst = '특이 재료 부재'
    entry_zone = _build_entry_zone(market.price, market.atr_14d)
    invalidation = _build_invalidation_level(market)
    change_percent = market.change_percent

    headline = _summarize_top_headline(ticker_news)
    if headline:
        catalyst = headline

    # Multi-factor direction scoring: price momentum + SMA positioning + RS
    bull_score = 0
    bear_score = 0

    if change_percent is not None:
        if change_percent >= 3.0:
            bull_score += 2
        elif change_percent >= 1.0:
            bull_score += 1
        elif change_percent <= -3.0:
            bear_score += 2
        elif change_percent < -1.0:
            bear_score += 1

    # SMA50 positioning: above = bullish, below = bearish
    sma50_pct = _parse_float_from_text(market.price_vs_sma50)
    if sma50_pct is not None:
        if sma50_pct > 0:
            bull_score += 1
        elif sma50_pct < -3:
            bear_score += 1

    # Relative strength vs SPY
    rs_value = _parse_float_from_text(market.rs_vs_spy)
    if rs_value is not None:
        if rs_value > 2:
            bull_score += 1
        elif rs_value < -2:
            bear_score += 1

    # RVOL signal: high volume amplifies direction
    rvol_value = _parse_float_from_text(market.relative_volume)
    if rvol_value is not None and rvol_value > 1.5:
        if bull_score > bear_score:
            bull_score += 1
        elif bear_score > bull_score:
            bear_score += 1

    # Determine direction from composite score
    if bull_score >= 3:
        direction = '매수 관찰'
        if not headline:
            catalyst = f'기술적 강세 (SMA 위, RS 양호, {change_percent:+.1f}%)'
    elif bull_score >= 2 and bear_score == 0:
        direction = '매수 관찰'
        if not headline:
            catalyst = f'상승 추세 유지 {change_percent:+.1f}%' if change_percent else '기술적 양호'
    elif bear_score >= 3:
        direction = '매도 경계'
        if not headline:
            catalyst = f'기술적 약세 (SMA 하회, RS 부진, {change_percent:+.1f}%)'
    elif bear_score >= 2 and bull_score == 0:
        direction = '중립 경계'
        if not headline:
            catalyst = f'하락 압력 {change_percent:+.1f}%' if change_percent else '기술적 약화'
    else:
        if not headline:
            catalyst = '방향성 미확정, 추가 재료 대기'

    # Compute R:R for signal line
    rr_text = ""
    atr_value = _parse_float_from_text(market.atr_14d)
    sma50_value = _parse_float_from_text(market.sma_50)
    if market.price is not None and atr_value is not None and atr_value > 0:
        stop_val = sma50_value if sma50_value is not None else (market.price - 2 * atr_value)
        target_val = market.price + 1.5 * atr_value
        risk = market.price - stop_val
        reward = target_val - market.price
        if risk > 0 and reward > 0:
            rr_text = f" (R:R {reward / risk:.1f}R)"

    return f'{direction} — {catalyst} | 진입 트리거 {entry_zone} | 손절 {invalidation}{rr_text}'


def _build_fallback_trade_frame(
    market: CollectedTickerData,
    *,
    account_size_hint: float | None = None,
) -> dict[str, str]:
    price = market.price
    price_text = f"{price:.2f} {market.currency}" if price is not None else "현재 가격 기준"
    sma50_text = _with_currency(market.sma_50, market.currency)
    sma50_val = _parse_float_from_text(market.sma_50)
    atr_val = _parse_float_from_text(market.atr_14d)
    target_val = _parse_float_from_text(market.analyst_target_price)
    w52_high_val = _parse_float_from_text(market.week52_high)
    watch_period = _build_watch_period(market.upcoming_events)

    # Entry price
    entry_price = price_text
    if price is not None and atr_val is not None and atr_val > 0:
        pullback = price - atr_val
        entry_price = f"현재가 {price:.2f} 또는 눌림 시 {pullback:.2f} {market.currency}"

    # Stop loss
    if sma50_val is not None and sma50_val > 0:
        stop_loss = f"SMA50 {sma50_val:.2f} {market.currency}"
    elif price is not None and atr_val is not None and atr_val > 0:
        stop_loss = f"{(price - 2 * atr_val):.2f} {market.currency} (2×ATR)"
    else:
        stop_loss = "데이터 부족"

    stop_val = sma50_val if sma50_val is not None else (price - 2 * atr_val if price is not None and atr_val is not None else None)

    # Targets
    if price is not None and atr_val is not None and atr_val > 0:
        t1_val = price + 1.5 * atr_val
        target_1 = f"{t1_val:.2f} {market.currency} (1.5×ATR)"
    else:
        t1_val = None
        target_1 = "데이터 부족"

    if target_val is not None and target_val > 0:
        target_2 = f"애널리스트 목표 {target_val:.2f} {market.currency}"
        t2_val = target_val
    elif w52_high_val is not None:
        target_2 = f"52주 고점 {w52_high_val:.2f} {market.currency}"
        t2_val = w52_high_val
    else:
        target_2 = "데이터 부족"
        t2_val = None

    # R:R ratio
    rr_text = "N/A"
    if price is not None and stop_val is not None and t1_val is not None:
        risk = price - stop_val
        reward = t1_val - price
        if risk > 0 and reward > 0:
            rr_text = f"{reward / risk:.1f}R"

    # Position sizing (1% risk on account value when available)
    normalized_account_size = account_size_hint if account_size_hint and account_size_hint > 0 else 10000.0
    risk_budget = normalized_account_size * 0.01
    if atr_val is not None and atr_val > 0:
        shares = int(risk_budget // atr_val)
        position_size_note = (
            f"{_format_account_size_hint(normalized_account_size)} 계좌 1% 리스크 기준 약 {shares}주 "
            f"(ATR ${atr_val:.2f} 기반)"
        )
    else:
        position_size_note = "ATR 데이터 부족으로 포지션 사이징 계산 불가"

    invalidation_anchor = sma50_text if sma50_text != "N/A" else price_text
    invalidation_price = (
        f"50일 이동평균선인 {invalidation_anchor} 아래로 밀리면 약세 시나리오 확인"
        if sma50_text != "N/A"
        else f"{invalidation_anchor} 아래로 이탈하면 약세 시나리오 확인"
    )

    bull_scenario = "실적 또는 공시 모멘텀이 이어지고 거래량이 붙으면 상단 저항 재시험 가능성이 있습니다."
    base_scenario = f"{price_text} 부근에서 방향성 확인 전까지 박스권 등락 가능성이 큽니다."
    bear_scenario = "실적 기대가 약해지거나 주요 이동평균선을 이탈하면 단기 조정 압력이 커질 수 있습니다."

    if market.change_percent is not None and market.change_percent <= -3:
        bull_scenario = "과매도 반등이 나오려면 거래량 동반 반등과 함께 50일선 회복이 필요합니다."
        base_scenario = f"{price_text} 인근에서 반등 시도와 재차 흔들림이 반복될 가능성이 큽니다."
    elif market.change_percent is not None and market.change_percent >= 3:
        bull_scenario = "강한 모멘텀이 유지되면 최근 고점 영역 재돌파 시도가 나올 수 있습니다."
        base_scenario = f"{price_text} 부근 상승분을 소화하며 실적 전까지 추세 지속 여부를 점검하는 구간입니다."

    return {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "risk_reward_ratio": rr_text,
        "position_size_note": position_size_note,
        "bull_scenario": bull_scenario,
        "base_scenario": base_scenario,
        "bear_scenario": bear_scenario,
        "invalidation_price": invalidation_price,
        "watch_period": watch_period,
    }


def _build_entry_zone(price: float, atr_text: str) -> str:
    atr_value = _parse_float_from_text(atr_text)
    if atr_value is None or atr_value <= 0:
        return f"{price:.2f} 부근"
    lower = max(price - atr_value, 0)
    upper = price + atr_value
    return f"{lower:.2f}–{upper:.2f}"


def _build_invalidation_level(market: CollectedTickerData) -> str:
    sma50_value = _parse_float_from_text(market.sma_50)
    if sma50_value is not None and sma50_value > 0:
        return f"SMA50({sma50_value:.2f} {market.currency})"

    if market.price is None:
        return "가격 데이터 확인 필요"

    atr_value = _parse_float_from_text(market.atr_14d)
    if atr_value is not None and atr_value > 0:
        return f"{(market.price - (2 * atr_value)):.2f} {market.currency}"
    return f"{market.price:.2f} {market.currency}"


def _build_fallback_risks(market: CollectedTickerData, ticker_news: list[NewsItem]) -> list[str]:
    risks: list[str] = []
    if market.change_percent is not None and market.change_percent <= -3.0:
        risks.append(f'일간 {market.change_percent:+.1f}% 하락 — 추가 하락 또는 데드캣 바운스 주의.')
    if market.pe_ratio != 'N/A':
        try:
            pe_value = float(market.pe_ratio)
            if pe_value > 40:
                risks.append(f'PER {pe_value:.1f}배로 밸류에이션 부담. 실적 miss 시 급락 리스크.')
        except ValueError:
            pass

    # SMA200 이탈 경고
    sma200_pct = _parse_float_from_text(market.price_vs_sma200)
    if sma200_pct is not None and sma200_pct < -5:
        sma200_val = market.sma_200
        risks.append(f'200일 이평선({sma200_val}) 대비 {sma200_pct:+.1f}% 하회 — 중기 추세 약화.')

    # 공매도 비율 경고
    short_pct = _parse_float_from_text(market.short_float_pct)
    if short_pct is not None and short_pct > 10:
        risks.append(f'공매도 비율 {short_pct:.1f}%로 높음 — 숏 스퀴즈 또는 추가 하락 양면 리스크.')

    # 옵션 IV 경고 (실적 전 변동성 확대)
    iv_value = _parse_float_from_text(market.implied_volatility)
    if iv_value is not None and iv_value > 50:
        risks.append(f'옵션 IV {iv_value:.0f}%로 높음 — 시장이 큰 등락을 기대하는 상황.')

    if not ticker_news:
        risks.append('수집된 뉴스가 없어 시장 심리 파악이 어렵습니다.')
    if len(risks) == 0:
        risks.append('의사결정 전 최근 실적 일정과 주요 헤드라인을 다시 확인하세요.')
    return risks[:4]


def _build_fallback_financial_highlights(market: CollectedTickerData) -> list[str]:
    highlights: list[str] = []
    # 핵심 밸류에이션 (수치 포함 필수)
    if market.pe_ratio != 'N/A' and market.eps != 'N/A':
        highlights.append(f'PER {market.pe_ratio}배 (EPS {market.eps})')
    elif market.pe_ratio != 'N/A':
        highlights.append(f'PER {market.pe_ratio}배')
    if market.forward_eps != 'N/A' and market.earnings_growth != 'N/A':
        highlights.append(f'Forward EPS {market.forward_eps}, 성장률 {market.earnings_growth}')
    elif market.forward_eps != 'N/A':
        highlights.append(f'Forward EPS {market.forward_eps}')
    # 시가총액 + 배당
    cap_parts = [f'시가총액 {market.market_cap}']
    if market.dividend_yield != 'N/A':
        cap_parts.append(f'배당 {market.dividend_yield}')
    highlights.append(' / '.join(cap_parts))
    # 기술적 위치
    if market.week52_position != 'N/A' and market.sma_50 != 'N/A':
        highlights.append(f'52주 범위 {market.week52_position} 위치, SMA50 {market.sma_50} {market.currency}')
    elif market.week52_high != 'N/A' and market.week52_low != 'N/A':
        highlights.append(f'52주 범위: {market.week52_low} ~ {market.week52_high}')
    # 포지셔닝 요약
    positioning_parts: list[str] = []
    if market.analyst_recommendation != 'N/A' and market.analyst_target_price != 'N/A':
        positioning_parts.append(f'애널리스트 {market.analyst_recommendation} (목표 {market.analyst_target_price})')
    if market.held_by_institutions != 'N/A':
        positioning_parts.append(f'기관 {market.held_by_institutions}')
    if positioning_parts:
        highlights.append(' / '.join(positioning_parts))
    return highlights[:5]


def _summarize_top_headline(ticker_news: list[NewsItem]) -> str:
    for article in ticker_news:
        if article.title and article.source and article.source.strip().lower() != 'fallback':
            return article.title
    return ''


def _build_snapshot(market: CollectedTickerData) -> dict[str, str]:
    return {
        'Price': f'{market.price:.2f} {market.currency}' if market.price is not None else 'N/A',
        'Daily Change': f'{market.change_percent:+.2f}%' if market.change_percent is not None else 'N/A',
        'Market Cap': market.market_cap,
        'Trailing P/E': market.pe_ratio,
        'EPS': market.eps,
        '52W High': market.week52_high,
        '52W Low': market.week52_low,
        '50D SMA': market.sma_50,
        '200D SMA': market.sma_200,
        'Volume': market.volume,
        '3M Avg Volume': market.avg_volume_3m,
        'Price/Book': market.price_to_book,
        'Dividend Yield': market.dividend_yield,
        'Sector': market.sector or 'N/A',
        'Open': market.open_price,
        'High': market.high_price,
        'Low': market.low_price,
        'Close': market.close_price,
        'RS vs Sector ETF': market.rs_vs_sector_etf,
    }


def _build_fundamentals(market: CollectedTickerData) -> dict[str, str]:
    return {
        'market_cap': market.market_cap,
        'trailing_pe': market.pe_ratio,
        'eps': market.eps,
        'forward_eps': market.forward_eps,
        'earnings_growth': market.earnings_growth,
        'price_to_book': market.price_to_book,
        'dividend_yield': market.dividend_yield,
        'volume': market.volume,
        'avg_volume_3m': market.avg_volume_3m,
        '52w_high': market.week52_high,
        '52w_low': market.week52_low,
        'short_float_pct': market.short_float_pct,
        'short_ratio': market.short_ratio,
        'analyst_target_price': market.analyst_target_price,
        'analyst_recommendation': market.analyst_recommendation,
        'analyst_count': market.analyst_count,
        'held_by_insiders': market.held_by_insiders,
        'held_by_institutions': market.held_by_institutions,
        'implied_volatility': market.implied_volatility,
    }


def _build_price_action(market: CollectedTickerData) -> dict[str, str]:
    return {
        'atr_14d': market.atr_14d,
        'atr_percent': market.atr_percent,
        'relative_volume': market.relative_volume,
        'gap_percent': market.gap_percent,
        'price_vs_sma50': market.price_vs_sma50,
        'price_vs_sma200': market.price_vs_sma200,
        'week52_position': market.week52_position,
        'rs_vs_spy': market.rs_vs_spy,
        'rs_vs_sector_etf': market.rs_vs_sector_etf,
    }


def _build_watch_period(events: list[dict[str, str]]) -> str:
    if events:
        first_event = events[0]
        label = first_event.get('label', '주요 일정')
        event_date = first_event.get('date', '')
        if event_date:
            return f"{event_date} {label} 전까지"
    return "향후 5거래일"


def _with_currency(value: str, currency: str) -> str:
    normalized_value = (value or '').strip()
    if not normalized_value or normalized_value == 'N/A':
        return 'N/A'
    if normalized_value.endswith(currency):
        return normalized_value
    return f"{normalized_value} {currency}".strip()


def _format_account_size_hint(account_size_hint: float | None) -> str:
    normalized = account_size_hint if account_size_hint and account_size_hint > 0 else 10000.0
    return f"${normalized:,.0f}"


def _parse_float_from_text(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == 'N/A':
        return None
    try:
        cleaned = text.replace(',', '').replace('%', '').split()[0]
        return float(cleaned)
    except (IndexError, ValueError):
        return None

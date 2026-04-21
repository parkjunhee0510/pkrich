from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.types import CollectedTickerData, NewsItem, PortfolioSummary, TickerAnalysis, WatchlistItem
from src.utils.cost_tracker import calculate_response_cost
from src.utils.env import load_dotenv
from src.utils.model_config import (
    ModelProfile,
    build_model_profile,
    load_model_profile,
    response_temperature_kwargs,
    safe_input_token_budget,
)
from src.utils.pipeline_logging import record_pipeline_event
from src.utils.token_estimator import estimate_batch_tokens

logger = logging.getLogger(__name__)
_SECTOR_TRANSLATIONS = {
    'Technology': '기술',
    'Semiconductors': '반도체',
    'Healthcare': '헬스케어',
    'Financials': '금융',
    'Energy': '에너지',
    'Consumer Discretionary': '경기소비재',
    'Consumer Staples': '필수소비재',
    'Industrials': '산업재',
    'Communication Services': '커뮤니케이션 서비스',
    'Utilities': '유틸리티',
    'Real Estate': '부동산',
    'Materials': '소재',
}
_MAX_BATCH_SPLIT_DEPTH = 6
_NUMERIC_HIGHLIGHT_PATTERN = re.compile(
    r"(?:[$€₩]\s*[-+]?\d[\d,.]*(?:\.\d+)?)|(?:[-+]?\d[\d,.]*(?:\.\d+)?\s*(?:%p|%|배|x|USD|KRW|원|달러|M|B|T|억|만|조))|(?:\d[\d,.]*)"
)
_MISSING_DATA_HIGHLIGHT_PATTERN = re.compile(
    r'(?:\bN/?A\b|데이터\s*(?:없|부족)|제공되지\s*않|확인\s*불가|판단\s*불가|비교\s*불가|제한됩니다?)',
    re.IGNORECASE,
)
_FEW_SHOT_EXAMPLE = (
    '{"tickers":[{"ticker":"AAPL","summary":"애플은 260.49 USD 부근에서 SMA50 260.57 USD를 두고 방향성을 탐색 중이며 '
    'RS vs SPY +4.10%와 RVOL 1.42x가 단기 수급 버팀목입니다. 2026-04-30 실적 발표 전까지 최근 4개 분기 중 3개 beat 패턴이 유지되는지와 '
    '254.39 USD 지지 여부가 핵심 점검 포인트입니다.","key_news":["10-Q 제출로 분기 실적 재확인 필요"],'
    '"financial_highlights":["최근 4개 분기 중 3개 beat, 최신 서프라이즈 +5.00%입니다.","Forward EPS 6.80 USD/share로 TTM EPS 6.10 대비 +11.48% 높습니다.",'
    '"섹터 평균 PER 22.40x 대비 애플 PER 25.00x로 프리미엄이 존재합니다."],"risks_or_watchpoints":["254.39 USD 이탈 시 2×ATR 기준 단기 추세 훼손 가능성이 있습니다."],'
    '"signal_or_takeaway":"매수 관찰 — 2026-04-30 실적과 연속 beat 유지 여부 | 진입 트리거 254.39-266.59 USD 지지 확인 | 목표 269.58 USD/295.32 USD | 손절 248.37 USD (R:R 1.4R)",'
    '"news_tone":{"label":"neutral","confidence":3,"reasoning":"실적 기대와 밸류에이션 부담이 혼재합니다."},"trade_frame":{"entry_price":"현재가 260.49 USD 또는 254.39-256.00 USD 눌림 시",'
    '"stop_loss":"248.37 USD (2×ATR 기준)","target_1":"269.58 USD (1.5×ATR)","target_2":"애널리스트 목표 295.32 USD","risk_reward_ratio":"1.4R",'
    '"position_size_note":"$10,000 계좌 1% 리스크 기준 약 16주 (ATR $6.06 기반)","bull_scenario":"연속 beat와 가이던스 상향이 확인되면 295.32 USD 재시험 가능성이 있습니다.",'
    '"base_scenario":"실적 전까지 254.39-269.58 USD 범위에서 박스권 소화 가능성이 큽니다.","bear_scenario":"가이던스 실망과 함께 248.37 USD를 이탈하면 단기 조정 압력이 커질 수 있습니다.",'
    '"invalidation_price":"248.37 USD 종가 하회 시 단기 강세 시나리오 무효화","watch_period":"2026-04-30 실적 발표 전까지"}}]}'
)


@dataclass(frozen=True)
class _PreparedPayloadItem:
    item: WatchlistItem
    payload: dict[str, Any]
    estimated_tokens: int


def analyze_tickers(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    macro_context: dict[str, Any] | None = None,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
    model_profile_name: str | None = None,
    portfolio_account_size: float | None = None,
    portfolio_summary: PortfolioSummary | None = None,
) -> list[TickerAnalysis]:
    load_dotenv()
    model_profile = load_model_profile(profile_name=model_profile_name)
    from src.analyzer.modules import (
        NewsAnalysisModule,
        PeerComparisonModule,
        PortfolioRiskModule,
        ResearchNarrativeModule,
        RiskAssessmentModule,
        SignalTakeawayModule,
        TradeFrameModule,
        ValuationModule,
    )
    from src.analyzer.orchestrator import AnalysisOrchestrator
    from src.analyzer.registry import ModuleRegistry

    registry = ModuleRegistry()
    registry.register_many(
        [
            PeerComparisonModule(),
            ValuationModule(),
            TradeFrameModule(),
            PortfolioRiskModule(),
            NewsAnalysisModule(),
            ResearchNarrativeModule(),
            RiskAssessmentModule(),
            SignalTakeawayModule(),
        ]
    )
    orchestrator = AnalysisOrchestrator(registry, model_profile=model_profile, logger=logger)
    return orchestrator.analyze_all(
        watchlist,
        collected,
        news_map,
        run_date,
        macro_context=macro_context,
        signal_history_map=signal_history_map,
        portfolio_account_size=portfolio_account_size,
        portfolio_summary=portfolio_summary,
    )


def _run_legacy_analysis_pipeline(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    macro_context: dict[str, Any] | None = None,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
    model_profile_name: str | None = None,
    portfolio_account_size: float | None = None,
    model_profile: ModelProfile | None = None,
) -> list[TickerAnalysis]:
    active_model_profile = model_profile or load_model_profile(profile_name=model_profile_name)
    if os.getenv('OPENAI_API_KEY'):
        llm_results = _analyze_with_openai(
            watchlist,
            collected,
            news_map,
            run_date,
            model_profile=active_model_profile,
            macro_context=macro_context,
            signal_history_map=signal_history_map,
            portfolio_account_size=portfolio_account_size,
        )
        if llm_results:
            return llm_results
    return _build_fallback_analyses(
        watchlist,
        collected,
        news_map,
        run_date,
        account_size_hint=portfolio_account_size,
    )


def _analyze_with_openai(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    model_profile: ModelProfile,
    macro_context: dict[str, Any] | None = None,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
    portfolio_account_size: float | None = None,
) -> list[TickerAnalysis]:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    except Exception as exc:
        _log_analyzer_event(
            'openai_analyzer_failed',
            model=model_profile.model,
            model_profile=model_profile.name,
            run_date=run_date.isoformat(),
            ticker_count=len(watchlist),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []

    try:
        return _analyze_batches_with_client(
            client,
            model_profile,
            watchlist,
            collected,
            news_map,
            run_date,
            macro_context=macro_context,
            signal_history_map=signal_history_map,
            account_size_hint=portfolio_account_size,
        )
    except Exception as exc:
        _log_analyzer_event(
            'openai_analyzer_failed',
            model=model_profile.model,
            model_profile=model_profile.name,
            run_date=run_date.isoformat(),
            ticker_count=len(watchlist),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []


def _analyze_batches_with_client(
    client: Any,
    model_profile_or_name: ModelProfile | str,
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    macro_context: dict[str, Any] | None = None,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
    account_size_hint: float | None = None,
) -> list[TickerAnalysis]:
    model_profile = _coerce_model_profile(model_profile_or_name)
    prepared = _prepare_payload_items(watchlist, collected, news_map, signal_history_map=signal_history_map)
    batches = _build_batches_for_analysis(prepared, model_profile)
    analyses_by_ticker: dict[str, TickerAnalysis] = {}

    for batch_number, batch in enumerate(batches, start=1):
        _process_batch(
            client,
            model_profile,
            batch,
            collected,
            news_map,
            run_date,
            analyses_by_ticker,
            batch_number=batch_number,
            total_batches=len(batches),
            retry_depth=0,
            macro_context=macro_context,
            account_size_hint=account_size_hint,
        )

    return [analyses_by_ticker[item.ticker] for item in watchlist if item.ticker in analyses_by_ticker]


def _prepare_payload_items(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    *,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
) -> list[_PreparedPayloadItem]:
    payload = _build_payload(watchlist, collected, news_map, signal_history_map=signal_history_map)
    prepared: list[_PreparedPayloadItem] = []
    for item, payload_entry in zip(watchlist, payload, strict=False):
        prepared.append(
            _PreparedPayloadItem(
                item=item,
                payload=payload_entry,
                estimated_tokens=estimate_batch_tokens([payload_entry]),
            )
        )
    return prepared


def _build_batches_for_analysis(
    prepared_items: list[_PreparedPayloadItem],
    model_profile: ModelProfile,
) -> list[list[_PreparedPayloadItem]]:
    if not prepared_items:
        return []

    override_batch_size = _read_batch_size_override()
    if override_batch_size is not None:
        return [prepared_items[index:index + override_batch_size] for index in range(0, len(prepared_items), override_batch_size)]

    soft_batch_size = _calculate_batch_size([item.payload for item in prepared_items], model_profile)
    token_budget = safe_input_token_budget(model_profile)
    batches: list[list[_PreparedPayloadItem]] = []
    current_batch: list[_PreparedPayloadItem] = []

    for prepared_item in prepared_items:
        candidate_batch = current_batch + [prepared_item]
        candidate_tokens = estimate_batch_tokens([item.payload for item in candidate_batch])
        should_split = (
            current_batch
            and (
                len(candidate_batch) > soft_batch_size
                or candidate_tokens > token_budget
            )
        )
        if should_split:
            batches.append(current_batch)
            current_batch = [prepared_item]
        else:
            current_batch = candidate_batch

    if current_batch:
        batches.append(current_batch)

    return batches


def _calculate_batch_size(payload_items: list[dict[str, Any]], model_profile: ModelProfile) -> int:
    override_batch_size = _read_batch_size_override()
    if override_batch_size is not None:
        return override_batch_size
    if not payload_items:
        return 1

    token_budget = safe_input_token_budget(model_profile)
    estimated_total_tokens = estimate_batch_tokens(payload_items)
    average_item_tokens = max(1, estimated_total_tokens // max(len(payload_items), 1))
    dynamic_batch_size = max(1, token_budget // average_item_tokens)
    return max(1, min(len(payload_items), dynamic_batch_size))


def _process_batch(
    client: Any,
    model_profile: ModelProfile,
    batch: list[_PreparedPayloadItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    analyses_by_ticker: dict[str, TickerAnalysis],
    *,
    batch_number: int,
    total_batches: int,
    retry_depth: int,
    macro_context: dict[str, Any] | None = None,
    account_size_hint: float | None = None,
) -> None:
    payload = [entry.payload for entry in batch]
    batch_items = [entry.item for entry in batch]
    token_budget = safe_input_token_budget(model_profile)
    estimated_tokens = estimate_batch_tokens(payload)

    record_pipeline_event(
        'analyzer',
        'info',
        'analysis_batch_planned',
        model=model_profile.model,
        model_profile=model_profile.name,
        batch_number=batch_number,
        total_batches=total_batches,
        batch_size=len(batch_items),
        estimated_tokens=estimated_tokens,
        token_budget=token_budget,
        retry_depth=retry_depth,
    )

    if estimated_tokens > token_budget and len(batch) > 1:
        _split_and_retry_batch(
            client,
            model_profile,
            batch,
            collected,
            news_map,
            run_date,
            analyses_by_ticker,
            batch_number=batch_number,
            total_batches=total_batches,
            retry_depth=retry_depth + 1,
            reason='estimated_token_budget_exceeded',
            macro_context=macro_context,
        )
        return

    parsed = _call_openai_batch(
        client,
        model_profile,
        payload,
        batch_items,
        run_date,
        batch_number=batch_number,
        total_batches=total_batches,
        estimated_tokens=estimated_tokens,
        token_budget=token_budget,
        retry_depth=retry_depth,
        macro_context=macro_context,
        account_size_hint=account_size_hint,
    )
    if parsed is None:
        if len(batch) > 1 and retry_depth < _MAX_BATCH_SPLIT_DEPTH:
            _split_and_retry_batch(
                client,
                model_profile,
                batch,
                collected,
                news_map,
                run_date,
                analyses_by_ticker,
                batch_number=batch_number,
                total_batches=total_batches,
                retry_depth=retry_depth + 1,
                reason='batch_request_failed',
                macro_context=macro_context,
                account_size_hint=account_size_hint,
            )
            return

        for prepared_item in batch:
            fallback_analysis = _build_fallback_analysis(
                prepared_item.item,
                collected,
                news_map,
                run_date,
                signal_history=prepared_item.payload.get('signal_history', []),
                sector_comparison=_format_sector_comparison(prepared_item.payload.get('sector_peer_context', {})),
                peer_rank=prepared_item.payload.get('peer_rank', {}),
                account_size_hint=account_size_hint,
            )
            record_pipeline_event(
                'analyzer',
                'warning',
                'analysis_fallback_applied',
                ticker=fallback_analysis.ticker,
                batch_number=batch_number,
                batch_size=len(batch_items),
                total_batches=total_batches,
                retry_depth=retry_depth,
                error_type='BatchRequestFailed',
                error_message='OpenAI batch failed; deterministic fallback used.',
            )
            analyses_by_ticker[fallback_analysis.ticker] = fallback_analysis
        return

    parsed_by_ticker = {entry['ticker']: entry for entry in parsed}
    for item in batch_items:
        match = parsed_by_ticker.get(item.ticker)
        if match is None:
            _log_analyzer_event(
                'openai_response_missing_ticker',
                model=model_profile.model,
                model_profile=model_profile.name,
                run_date=run_date.isoformat(),
                ticker=item.ticker,
                ticker_count=len(batch_items),
                batch_number=batch_number,
                batch_size=len(batch_items),
                total_batches=total_batches,
                retry_depth=retry_depth,
            )
            record_pipeline_event(
                'analyzer',
                'warning',
                'analysis_fallback_applied',
                ticker=item.ticker,
                batch_number=batch_number,
                batch_size=len(batch_items),
                total_batches=total_batches,
                retry_depth=retry_depth,
                error_type='MissingTicker',
                error_message='OpenAI batch response did not include the requested ticker.',
            )
            payload_entry = next((entry.payload for entry in batch if entry.item.ticker == item.ticker), {})
            analyses_by_ticker[item.ticker] = _build_fallback_analysis(
                item,
                collected,
                news_map,
                run_date,
                signal_history=payload_entry.get('signal_history', []),
                sector_comparison=_format_sector_comparison(payload_entry.get('sector_peer_context', {})),
                peer_rank=payload_entry.get('peer_rank', {}),
                account_size_hint=account_size_hint,
            )
            continue

        payload_entry = next((entry.payload for entry in batch if entry.item.ticker == item.ticker), {})
        analyses_by_ticker[item.ticker] = _build_openai_analysis(
            item,
            match,
            collected,
            news_map,
            run_date,
            signal_history=payload_entry.get('signal_history', []),
            sector_comparison=_format_sector_comparison(payload_entry.get('sector_peer_context', {})),
            peer_rank=payload_entry.get('peer_rank', {}),
        )


def _split_and_retry_batch(
    client: Any,
    model_profile: ModelProfile,
    batch: list[_PreparedPayloadItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    analyses_by_ticker: dict[str, TickerAnalysis],
    *,
    batch_number: int,
    total_batches: int,
    retry_depth: int,
    reason: str,
    macro_context: dict[str, Any] | None = None,
    account_size_hint: float | None = None,
) -> None:
    midpoint = max(1, len(batch) // 2)
    left = batch[:midpoint]
    right = batch[midpoint:]
    record_pipeline_event(
        'analyzer',
        'warning',
        'analysis_batch_split_retry',
        model=model_profile.model,
        model_profile=model_profile.name,
        batch_number=batch_number,
        total_batches=total_batches,
        batch_size=len(batch),
        retry_depth=retry_depth,
        reason=reason,
    )
    for split_batch in (left, right):
        if not split_batch:
            continue
        _process_batch(
            client,
            model_profile,
            split_batch,
            collected,
            news_map,
            run_date,
            analyses_by_ticker,
            batch_number=batch_number,
            total_batches=total_batches,
            retry_depth=retry_depth,
            macro_context=macro_context,
            account_size_hint=account_size_hint,
        )


def _build_payload(
    batch: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    *,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    deduped_news_map = {item.ticker: _dedupe_news_items(news_map.get(item.ticker, [])) for item in batch}
    peer_context_map = _build_sector_peer_context(batch, collected)
    payload: list[dict[str, Any]] = []
    for item in batch:
        market = collected[item.ticker]
        payload.append(
            {
                'ticker': item.ticker,
                'name': item.name,
                'sector': item.sector,
                'price': market.price,
                'change_percent': market.change_percent,
                'currency': market.currency,
                'market_cap': market.market_cap,
                'pe_ratio': market.pe_ratio,
                'eps': market.eps,
                'forward_eps': market.forward_eps,
                'earnings_growth': market.earnings_growth,
                'price_to_book': market.price_to_book,
                'dividend_yield': market.dividend_yield,
                'volume': market.volume,
                'sma_50': market.sma_50,
                'sma_200': market.sma_200,
                'week52_high': market.week52_high,
                'week52_low': market.week52_low,
                'price_change_7d': market.price_change_7d,
                'price_action': {
                    'price_change_30d': market.price_change_30d,
                    'atr_14d': market.atr_14d,
                    'atr_percent': market.atr_percent,
                    'relative_volume': market.relative_volume,
                    'gap_percent': market.gap_percent,
                    'price_vs_sma50': market.price_vs_sma50,
                    'price_vs_sma200': market.price_vs_sma200,
                    'week52_position': market.week52_position,
                    'rs_vs_spy': market.rs_vs_spy,
                    'rs_vs_sector_etf': market.rs_vs_sector_etf,
                },
                'positioning': {
                    'short_float_pct': market.short_float_pct,
                    'short_ratio': market.short_ratio,
                    'analyst_target_price': market.analyst_target_price,
                    'analyst_recommendation': market.analyst_recommendation,
                    'analyst_count': market.analyst_count,
                    'held_by_insiders': market.held_by_insiders,
                    'held_by_institutions': market.held_by_institutions,
                    'implied_volatility': market.implied_volatility,
                },
                'options_summary': market.options_summary,
                'analyst_estimate_revisions': market.analyst_estimate_revisions,
                'insider_transactions': market.insider_transactions[:6],
                'institutional_changes': market.institutional_changes,
                'fmp_earnings_surprises': market.fmp_earnings_surprises[:4],
                'options_flow': market.options_flow,
                'recommendation_trends': market.recommendation_trends[:3],
                'fundamental_metrics': market.fundamental_metrics,
                'technical_indicators': market.technical_indicators,
                'quarterly_financials': market.quarterly_financials[:4],
                'signal_history': (signal_history_map or {}).get(item.ticker, [])[:5],
                'sector_peer_context': peer_context_map.get(item.ticker, {}),
                'upcoming_events': market.upcoming_events[:3],
                'news': [
                    {
                        'title': article.title,
                        'source': article.source,
                        'published_at': article.published_at,
                    }
                    for article in deduped_news_map.get(item.ticker, [])
                ],
            }
        )
    return payload


def _build_sector_peer_context(
    batch: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
) -> dict[str, dict[str, str]]:
    from src.collector.finnhub import collect_finnhub_peers, is_finnhub_ready
    from src.collector.fmp import collect_fmp_peer_metrics, is_fmp_ready

    # Try Finnhub peers + FMP metrics for enhanced comparison
    use_enhanced = is_finnhub_ready() and is_fmp_ready()
    peer_cache: dict[str, list[str]] = {}
    peer_metrics_cache: dict[str, dict[str, str]] = {}

    if use_enhanced:
        for item in batch:
            try:
                peers = collect_finnhub_peers(item.ticker)
                if peers:
                    peer_cache[item.ticker] = peers
                    # Collect FMP metrics for peers not yet cached
                    new_peers = [p for p in peers if p not in peer_metrics_cache]
                    if new_peers:
                        metrics = collect_fmp_peer_metrics(new_peers)
                        peer_metrics_cache.update(metrics)
            except Exception:
                continue

    # Fallback: watchlist-internal grouping
    grouped: dict[str, list[CollectedTickerData]] = {}
    for item in batch:
        sector_key = (item.sector or collected[item.ticker].sector or 'N/A').strip()
        grouped.setdefault(sector_key, []).append(collected[item.ticker])

    context_by_ticker: dict[str, dict[str, str]] = {}
    for item in batch:
        market = collected[item.ticker]
        sector_key = (item.sector or market.sector or 'N/A').strip()

        # Enhanced path: Finnhub peers with FMP metrics
        finnhub_peers = peer_cache.get(item.ticker, [])
        if finnhub_peers and peer_metrics_cache:
            peer_names: list[str] = []
            roe_values: list[str] = []
            margin_values: list[str] = []
            for p in finnhub_peers:
                pm = peer_metrics_cache.get(p, {})
                if pm:
                    peer_names.append(p)
                    if pm.get('roe'):
                        roe_values.append(pm['roe'])
                    if pm.get('gross_margin'):
                        margin_values.append(pm['gross_margin'])
            if peer_names:
                avg_roe = _average_numeric(roe_values, suffix='%') if roe_values else 'N/A'
                avg_margin = _average_numeric(margin_values, suffix='%') if margin_values else 'N/A'
                context_by_ticker[item.ticker] = {
                    'sector': sector_key or 'N/A',
                    'peer_names': '/'.join(peer_names[:5]),
                    'peer_count': str(len(peer_names)),
                    'peer_avg_roe': avg_roe,
                    'peer_avg_gross_margin': avg_margin,
                    'ticker_roe': market.fundamental_metrics.get('roe', 'N/A'),
                    'ticker_gross_margin': market.fundamental_metrics.get('gross_margin', 'N/A'),
                    'ticker_pe': market.pe_ratio,
                    'ticker_price_change_30d': market.price_change_30d,
                    'ticker_rs_vs_spy': market.rs_vs_spy,
                    'enhanced': 'true',
                }
                continue

        # Fallback: watchlist-internal comparison
        peers = [entry for entry in grouped.get(sector_key, []) if entry.ticker != item.ticker]
        if not peers:
            context_by_ticker[item.ticker] = {}
            continue

        avg_pe = _average_numeric([peer.pe_ratio for peer in peers], suffix='x')
        avg_30d = _average_numeric([peer.price_change_30d for peer in peers], suffix='%')
        avg_rs = _average_numeric([peer.rs_vs_spy for peer in peers], suffix='%')
        context_by_ticker[item.ticker] = {
            'sector': sector_key or 'N/A',
            'peer_count': str(len(peers)),
            'average_pe': avg_pe,
            'average_price_change_30d': avg_30d,
            'average_rs_vs_spy': avg_rs,
            'ticker_pe': market.pe_ratio,
            'ticker_price_change_30d': market.price_change_30d,
            'ticker_rs_vs_spy': market.rs_vs_spy,
        }
    return context_by_ticker


def _average_numeric(values: list[str], *, suffix: str) -> str:
    parsed = [_parse_float_from_text(value) for value in values]
    usable = [value for value in parsed if value is not None]
    if not usable:
        return 'N/A'
    return f'{sum(usable) / len(usable):.2f}{suffix}'


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


def _call_openai_batch(
    client: Any,
    model_profile: ModelProfile,
    payload: list[dict[str, Any]],
    batch: list[WatchlistItem],
    run_date: date,
    *,
    batch_number: int,
    total_batches: int,
    estimated_tokens: int,
    token_budget: int,
    retry_depth: int,
    macro_context: dict[str, Any] | None = None,
    account_size_hint: float | None = None,
) -> list[dict[str, Any]] | None:
    try:
        user_prompt = _build_user_prompt(
            payload,
            run_date,
            macro_context=macro_context,
            account_size_hint=account_size_hint,
        )
        response = client.responses.create(
            model=model_profile.model,
            max_output_tokens=model_profile.max_output_tokens,
            input=[
                {
                    'role': 'system',
                    'content': [
                        {
                            'type': 'input_text',
                            'text': _build_system_prompt(),
                        }
                    ],
                },
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'input_text',
                            'text': user_prompt,
                        }
                    ],
                },
            ],
            text={
                'format': {
                    'type': 'json_schema',
                    'name': 'ticker_research_batch',
                    'schema': _response_schema(),
                    'strict': True,
                }
            },
            **response_temperature_kwargs(model_profile),
        )
    except Exception as exc:
        _log_analyzer_event(
            'openai_request_failed',
            model=model_profile.model,
            model_profile=model_profile.name,
            run_date=run_date.isoformat(),
            ticker_count=len(batch),
            batch_number=batch_number,
            batch_size=len(batch),
            total_batches=total_batches,
            estimated_tokens=estimated_tokens,
            token_budget=token_budget,
            retry_depth=retry_depth,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return None

    usage_cost = calculate_response_cost(response, model_profile)
    record_pipeline_event(
        'analyzer',
        'info',
        'openai_usage_recorded',
        model=model_profile.model,
        model_profile=model_profile.name,
        batch_number=batch_number,
        input_tokens=usage_cost.input_tokens,
        output_tokens=usage_cost.output_tokens,
        cached_input_tokens=usage_cost.cached_input_tokens,
        total_tokens=usage_cost.total_tokens,
        estimated_cost_usd=usage_cost.estimated_cost_usd,
    )

    content = getattr(response, 'output_text', '').strip()
    try:
        return _parse_and_validate_response(content, batch)
    except Exception as exc:
        _log_analyzer_event(
            'openai_response_validation_failed',
            model=model_profile.model,
            model_profile=model_profile.name,
            run_date=run_date.isoformat(),
            ticker_count=len(batch),
            batch_number=batch_number,
            batch_size=len(batch),
            total_batches=total_batches,
            estimated_tokens=estimated_tokens,
            token_budget=token_budget,
            retry_depth=retry_depth,
            response_length=len(content),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return None


def _build_system_prompt() -> str:
    return (
        'You are a professional equity research analyst writing actionable trading notes. '
        'Your audience is an active swing trader who needs: (1) concrete price levels for entries and stops, '
        '(2) catalyst timelines, (3) quantitative evidence over qualitative narratives. '
        'Use only the provided data. Return strict JSON with key \'tickers\'. '
        'All human-readable field values must be written in Korean. '
        'Keep ticker symbols and company names unchanged. '
        'Rules: '
        '- Every price-related statement MUST include a specific dollar amount or percentage. '
        '- summary must be exactly 2 sentences: first sentence = current situation with price context, '
        'second sentence = upcoming catalyst or key risk with timeline. '
        '- financial_highlights: max 5 items. Prefer numeric evidence, and ensure at least one item contains a number when data exists. '
        'If quantitative data is unavailable, explicitly say that the metric is unavailable instead of inventing a number. '
        '- risks_or_watchpoints: max 4 items, each must specify a measurable trigger (price level, date, or threshold). '
        '- signal_or_takeaway: one structured sentence: "[방향] — [핵심 catalyst] | 진입 트리거 [조건] | 목표 [가격1]/[가격2] | 손절 [가격] (R:R [비율])" '
        'Direction options: 매수 관찰, 매수 유지, 중립 관찰, 중립 경계, 매도 경계. '
        '- trade_frame: use provided ATR and SMA values for stop loss and target calculations. '
        'Include entry_price (current price or pullback zone), stop_loss (SMA50 or price - 2×ATR), '
        'target_1 (near resistance, 1-2 ATR above entry), target_2 (analyst target or 52W high), '
        'risk_reward_ratio (reward/risk as "X.XR" format), position_size_note (ATR-based 1% risk sizing hint). '
        '- Reflect earnings surprise patterns (consecutive beat/miss, YoY acceleration/deceleration) in financial_highlights and signal_or_takeaway. '
        '- Mention sector-relative valuation or momentum only when the provided peer comparison contains a clear numeric gap. '
        '- Adjust risk posture by volatility regime: VIX < 15 = standard/aggressive targets allowed, '
        'VIX 15-25 = standard posture, VIX 25-35 = tighter stop and smaller size bias, VIX > 35 = defensive and avoid aggressive long entries. '
        '- valuation_score: Return an object with score (1-10 scale as "N/10"), factors (list of key valuation drivers), '
        'and assessment (Korean summary). Scoring guide: 8+/10=저평가, 5-7/10=적정, <5/10=고평가. '
        'Base on ROE/ROIC, PE vs peers, FCF yield, margin trend, debt level. '
        'If fundamental_metrics are unavailable, use PE, PBR, analyst target vs current price. '
        '- Treat duplicated headlines about the same event as one catalyst. Do not overcount repeated coverage. '
        '- news_tone must summarize the overall tone of the provided headlines, paying attention to negations like "no miss" or "denies". '
        '- If any input field is "N/A" or missing, do not repeat it. Instead, infer from neighboring metrics when reasonable, '
        'or omit only that specific data point. '
        'Reference example JSON structure for style and specificity: '
        f'{_FEW_SHOT_EXAMPLE}'
    )


def _build_user_prompt(
    payload: list[dict[str, Any]],
    run_date: date,
    *,
    macro_context: dict[str, Any] | None = None,
    account_size_hint: float | None = None,
) -> str:
    compact_context = "\n\n".join(_build_ticker_context(entry) for entry in payload)
    account_size_text = _format_account_size_hint(account_size_hint)
    one_percent_risk = account_size_hint * 0.01 if account_size_hint and account_size_hint > 0 else 100.0
    instructions = (
        'Create structured research notes for each ticker in Korean.\n'
        'Required fields: ticker, summary, key_news, financial_highlights, '
        'risks_or_watchpoints, signal_or_takeaway, trade_frame.\n\n'
        '## Field Requirements\n'
        'summary: EXACTLY 2 sentences in Korean. '
        'Sentence 1 = current price situation with key technical context (SMA position, 52W range, RVOL). '
        'Sentence 2 = upcoming catalyst or key risk with specific date/timeline.\n\n'
        'key_news: Follow the same order as the provided news array. Each item is a SHORT Korean summary (max 15 words) '
        'of the headline. Example: "Apple, SEC에 분기 실적 보고서(10-Q) 제출" → "10-Q 분기 실적 보고 제출, 실적 확인 필요".\n\n'
        'financial_highlights: Max 5 items. Prefer numeric evidence and make sure at least one item contains a number when the data exists. '
        'If the metric is genuinely unavailable, say so explicitly instead of fabricating a number. '
        'Good: "영업이익률 30.2% (전년 대비 +1.8%p)". Also acceptable when data is missing: "PE 데이터가 없어 동종 대비 밸류에이션 판단이 제한됩니다." '
        'Bad: "수익성이 양호합니다". '
        'Include: margin %, growth rates, PE/PB vs sector average, FCF yield, debt ratio when available.\n\n'
        'risks_or_watchpoints: Max 4 items. Each must specify a MEASURABLE trigger. '
        'Good: "SMA200($230.50) 하향 이탈 시 중기 추세 전환 확인". Bad: "시장 변동성에 유의".\n\n'
        'signal_or_takeaway: One structured sentence in Korean: '
        '"[방향] — [핵심 catalyst] | 진입 트리거 [조건] | 목표 [가격1]/[가격2] | 손절 [가격] (R:R [비율])". '
        'Direction options: 매수 관찰, 매수 유지, 중립 관찰, 중립 경계, 매도 경계. '
        'R:R = (target_1 - entry) / (entry - stop_loss), format as "X.XR".\n\n'
        'news_tone: Return an object with label (bullish|neutral|bearish), confidence (1-5), and reasoning. '
        'Use the combined context from headlines, SEC filings, and catalyst wording; avoid keyword-only mistakes on negations.\n\n'
        'trade_frame:\n'
        '- entry_price: Current price or optimal pullback zone (e.g. "현재가 $150.00 또는 SMA50 $145.20 눌림 시"). Use ATR for pullback range.\n'
        '- stop_loss: SMA50 price from [Key Levels], or price minus 2×ATR. Must be a specific dollar amount.\n'
        '- target_1: Near-term resistance. Use price + 1-2 ATR, or recent swing high.\n'
        '- target_2: Extended target. Use analyst target price or 52W high.\n'
        '- risk_reward_ratio: Calculate (target_1 - entry) / (entry - stop_loss). Format as "X.XR".\n'
        f'- position_size_note: "{account_size_text} 계좌 1% 리스크 기준 약 N주 (ATR $X.XX 기반)" — calculate shares = ${one_percent_risk:.0f} / ATR.\n'
        '- invalidation_price: Same as stop_loss but with context (e.g. "SMA50 $145.20 종가 하회 시 추세 전환 확인").\n'
        '- bull_scenario: Reference target_2 or analyst target. Max 2 sentences.\n'
        '- base_scenario: Most likely range-bound action. Reference current price ± 1 ATR. Max 2 sentences.\n'
        '- bear_scenario: Specify downside trigger (SMA break, earnings miss). Max 2 sentences.\n'
        '- watch_period: Use next earnings date from [Earnings] if within 60 days; otherwise "다음 주요 catalyst".\n\n'
        '## New Signal Integration (신규 시그널 활용 지침)\n'
        '- analyst_estimate_revisions direction="up"이면 financial_highlights에 EPS 컨센서스 상향 조정 문구를 포함합니다.\n'
        '- analyst_estimate_revisions direction="down"이면 risks_or_watchpoints에 하향 조정 리스크를 반영합니다.\n'
        '- insider_transactions에서 최근 30일 C-suite buy는 bullish 구조 신호로 해석하고, 대규모 매도는 리스크로 반영합니다.\n'
        '- insider_transactions의 option exercise는 bearish 신호로 과해석하지 않습니다.\n'
        '- options_flow PCR < 0.5는 bullish, > 1.5는 bearish 포지셔닝으로 해석하되 반드시 가격 확인 조건을 명시합니다.\n'
        '- options_flow MaxPain과 현재가의 괴리가 크면 만기 주간 자석(pin) 효과를 risks_or_watchpoints에 반영하고 괴리 방향을 함께 기술합니다.\n'
        '- options_flow IM(Implied Move)은 시장이 반영한 예상 변동폭이므로 target_1/target_2/stop_loss가 IM 범위와 일관되는지 확인하고, 초과 target은 근거를 명시합니다.\n'
        '- options_flow GEX가 negative이면 변동성 증폭 국면으로 해석해 stop 폭을 넓히고, positive이면 MaxPain 근처 자석 효과를 감안해 목표가를 보수적으로 설정합니다.\n'
        '- options_flow Skew가 fear-biased(+)이면 하방 테일 리스크 프리미엄이 높다는 의미이므로 risks_or_watchpoints에 헤지 수요를 반영합니다. greed-biased(-)이면 과열 신호로 해석합니다.\n'
        '- options_flow NetΔ가 큰 양수이면 콜 중심 포지셔닝, 큰 음수이면 풋 중심 방어 포지셔닝으로 해석합니다.\n'
        '- options_flow TopCalls/TopPuts의 최고 OI 행사가는 단기 지지/저항선 후보로 취급하고 trade_frame 설정 시 보조 근거로 사용합니다.\n'
        '- options_flow avg IV가 높으면 stop 범위를 ATR 기준보다 다소 넓게 허용하고 VIX regime과 결합해 포지션 사이즈를 조정합니다.\n'
        '- options_flow unusual_activity는 premium 금액이 큰 순서로 제공되므로 OI 대비 volume 비율과 가격 확인 조건을 함께 기술합니다.\n'
        '- recommendation_trends trend="upgrading"은 컨센서스 이동을 financial_highlights에, trend="downgrading"은 risks_or_watchpoints에 반영합니다.\n'
        '- fmp_earnings_surprises가 있으면 기존 quarterly_financials보다 우선해서 earnings surprise pattern을 해석합니다.\n'
        '- fundamental_metrics의 ROE/ROIC/FCF yield를 financial_highlights에서 동종 평균과 비교하여 밸류에이션 판단 근거로 사용합니다.\n'
        '- gross_margin_trend/operating_margin_trend가 "improving"이면 수익성 개선 강조, "declining"이면 risks에 마진 축소 리스크를 반영합니다.\n'
        '- debt_to_equity > 1.5이면 재무 레버리지 리스크를, current_ratio < 1.0이면 유동성 리스크를 risks에 반영합니다.\n'
        '- RSI > 70이면 과매수 상태를 risks_or_watchpoints에 반영하고, RSI < 30이면 과매도 반등 가능성을 signal에 반영합니다.\n'
        '- MACD crossover가 bullish이면 진입 트리거 보조 근거로, bearish이면 청산/경계 근거로 사용합니다.\n'
        '- BB lower_band 터치는 가치투자자에게 매수 기회 시그널로, upper_band 터치는 이익실현 고려 시점으로 해석합니다.\n\n'
        '## Valuation Score (밸류에이션 점수)\n'
        '- valuation_score의 score는 1-10점 척도("N/10" 형식). 8+/10=저평가, 5-7/10=적정, <5/10=고평가.\n'
        '- factors에는 점수에 영향을 준 핵심 지표를 나열합니다 (예: "ROE 147% (상위)", "PE 28.5x (프리미엄)").\n'
        '- assessment는 1-2문장의 한국어 종합 평가입니다.\n'
        '- fundamental_metrics가 있으면 ROE/ROIC, FCF yield, margin trend, debt level을 종합합니다.\n'
        '- fundamental_metrics가 없으면 PE, PBR, 애널리스트 목표가 대비 현재가, 52주 범위 위치로 판단합니다.\n\n'
        '## Dividend Analysis (배당 분석)\n'
        '- annual_dividend, dividend_5y_cagr, consecutive_increase_years가 있으면 financial_highlights에 배당 관련 항목을 포함합니다.\n'
        '- 배당 성장률(CAGR)이 5% 이상이고 연속 증가 3년 이상이면 배당 안정성을 강조합니다.\n'
        '- 배당수익률(dividend_yield)이 섹터 평균 대비 높으면 소득 투자 매력을 언급합니다.'
    )
    macro_section = ""
    if macro_context:
        vix = macro_context.get("vix", {})
        events = macro_context.get("upcoming_macro_events", [])
        portfolio_sensitivity = str(macro_context.get("portfolio_sensitivity_summary", "N/A"))
        macro_lines = []
        if vix.get("level") not in (None, "N/A"):
            macro_lines.append(f"VIX: {vix['level']} ({vix.get('change', 'N/A')}) — {vix.get('regime', 'N/A')}")
            regime = str(vix.get('regime', 'N/A'))
            macro_lines.append(f"Volatility guidance: {_volatility_guidance(regime, vix.get('level', 'N/A'))}")
        for evt in events[:5]:
            macro_lines.append(
                f"{evt.get('event_code', evt.get('type', ''))}: "
                f"{evt.get('date', '')} (D-{evt.get('days_until', '?')}, "
                f"{evt.get('impact', 'N/A')}) — {evt.get('market_bias', evt.get('label', ''))}"
            )
        if portfolio_sensitivity not in {"", "N/A"}:
            macro_lines.append(f"Portfolio sensitivity: {portfolio_sensitivity}")
        if macro_lines:
            macro_section = "\n\n[Macro Context]\n" + "\n".join(macro_lines)

    return (
        f'{instructions}\n'
        f'Data date: {run_date.isoformat()}{macro_section}\n\n'
        'Compact context:\n'
        f'{compact_context}\n\n'
        'Structured input JSON:\n'
        f'{json.dumps(payload, ensure_ascii=True)}'
    )


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


def _volatility_guidance(regime: str, vix_level: str) -> str:
    normalized_regime = regime.strip()
    level = _parse_float_from_text(str(vix_level))
    if level is not None:
        if level < 15:
            return '저변동 구간으로 공격적 목표 허용'
        if level < 25:
            return '표준 리스크 관리 유지'
        if level < 35:
            return '손절 타이트, 포지션 축소 권장'
        return '방어적 접근과 신규 매수 보수화'
    if '공포' in normalized_regime:
        return '방어적 접근과 신규 매수 보수화'
    if '경계' in normalized_regime:
        return '손절 타이트, 포지션 축소 권장'
    return '표준 리스크 관리 유지'


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


def _estimate_watchlist_tokens(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    model_profile: ModelProfile,
    macro_context: dict[str, Any] | None = None,
    signal_history_map: dict[str, list[dict[str, str]]] | None = None,
    account_size_hint: float | None = None,
) -> int:
    del run_date, macro_context, account_size_hint
    prepared = _prepare_payload_items(watchlist, collected, news_map, signal_history_map=signal_history_map)
    if not prepared:
        return 0
    token_counts = [item.estimated_tokens for item in prepared]
    batch_size = _calculate_batch_size([item.payload for item in prepared], model_profile)
    return sum(token_counts[:batch_size])


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


def _build_openai_analysis(
    item: WatchlistItem,
    match: dict[str, Any],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    signal_history: list[dict[str, str]] | None = None,
    sector_comparison: dict[str, Any] | None = None,
    peer_rank: dict[str, Any] | None = None,
) -> TickerAnalysis:
    market = collected[item.ticker]
    return TickerAnalysis(
        ticker=item.ticker,
        name=item.name,
        date=run_date.isoformat(),
        summary=match['summary'],
        key_news=match['key_news'][:5],
        news_references=news_map.get(item.ticker, [])[:5],
        financial_highlights=match['financial_highlights'][:5],
        risks_or_watchpoints=match['risks_or_watchpoints'][:5],
        signal_or_takeaway=match['signal_or_takeaway'],
        data_snapshot=_build_snapshot(market),
        fundamentals=_build_fundamentals(market),
        price_action=_build_price_action(market),
        quarterly_financials=market.quarterly_financials,
        upcoming_events=market.upcoming_events[:5],
        news_tone=match.get('news_tone', {}),
        trade_frame=match['trade_frame'],
        options_summary=market.options_summary,
        signal_history=signal_history or [],
        sector_comparison=sector_comparison or {},
        peer_rank=peer_rank or {},
        valuation_score=match.get('valuation_score', {}),
        historical_prices=market.historical_prices,
    )


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


def _translate_sector(sector: str) -> str:
    if not sector:
        return '미지정'
    return _SECTOR_TRANSLATIONS.get(sector, sector)


def _parse_and_validate_response(content: str, watchlist: list[WatchlistItem]) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError('Model response must be a JSON object.')

    tickers = parsed.get('tickers')
    if not isinstance(tickers, list):
        raise ValueError("Model response must contain a 'tickers' list.")

    allowed_tickers = {item.ticker for item in watchlist}
    validated: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()

    for entry in tickers:
        if not isinstance(entry, dict):
            raise ValueError('Each ticker response must be an object.')

        ticker = _require_non_empty_string(entry, 'ticker').upper()
        if ticker not in allowed_tickers:
            raise ValueError(f'Unexpected ticker in model response: {ticker}')
        if ticker in seen_tickers:
            raise ValueError(f'Duplicate ticker in model response: {ticker}')
        seen_tickers.add(ticker)

        validated.append(
            {
                'ticker': ticker,
                'summary': _require_non_empty_string(entry, 'summary', min_length=40),
                'key_news': _require_string_list(entry, 'key_news'),
                'financial_highlights': _require_quantitative_highlights(
                    _require_string_list(entry, 'financial_highlights', item_min_length=15)
                ),
                'risks_or_watchpoints': _require_string_list(entry, 'risks_or_watchpoints', item_min_length=15),
                'signal_or_takeaway': _require_non_empty_string(entry, 'signal_or_takeaway', min_length=30),
                'news_tone': _require_news_tone(entry),
                'trade_frame': _require_trade_frame(entry),
                'valuation_score': _require_valuation_score(entry),
            }
        )

    return validated


def _require_non_empty_string(entry: dict[str, Any], key: str, *, min_length: int = 1) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field '{key}' must be a non-empty string.")
    normalized = value.strip()
    if len(normalized) < min_length:
        raise ValueError(f"Field '{key}' must be at least {min_length} characters long.")
    return normalized


def _require_string_list(entry: dict[str, Any], key: str, *, item_min_length: int = 1) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Field '{key}' must be a list.")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Field '{key}' must contain non-empty strings.")
        stripped = item.strip()
        if len(stripped) < item_min_length:
            raise ValueError(f"Field '{key}' items must be at least {item_min_length} characters long.")
        normalized.append(stripped)
    return normalized


def _require_quantitative_highlights(items: list[str]) -> list[str]:
    has_numeric_evidence = False
    for item in items:
        if _NUMERIC_HIGHLIGHT_PATTERN.search(item):
            has_numeric_evidence = True
            continue
        if _MISSING_DATA_HIGHLIGHT_PATTERN.search(item):
            continue
        if len(item) < 15:
            raise ValueError(f"financial_highlights item missing quantitative data: {item!r}")
    if not has_numeric_evidence and not any(_MISSING_DATA_HIGHLIGHT_PATTERN.search(item) for item in items):
        raise ValueError("financial_highlights must contain at least one numeric datapoint or an explicit missing-data explanation.")
    return items


def _response_schema() -> dict[str, Any]:
    return {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'tickers': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'ticker': {'type': 'string'},
                        'summary': {'type': 'string', 'minLength': 40},
                        'key_news': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 5},
                        'financial_highlights': {
                            'type': 'array',
                            'items': {'type': 'string', 'minLength': 15},
                            'maxItems': 5,
                        },
                        'risks_or_watchpoints': {
                            'type': 'array',
                            'items': {'type': 'string', 'minLength': 15},
                            'maxItems': 4,
                        },
                        'signal_or_takeaway': {'type': 'string', 'minLength': 30},
                        'news_tone': {
                            'type': 'object',
                            'additionalProperties': False,
                            'properties': {
                                'label': {'type': 'string', 'enum': ['bullish', 'neutral', 'bearish']},
                                'confidence': {'type': 'integer', 'minimum': 1, 'maximum': 5},
                                'reasoning': {'type': 'string', 'minLength': 10},
                            },
                            'required': ['label', 'confidence', 'reasoning'],
                        },
                        'trade_frame': {
                            'type': 'object',
                            'additionalProperties': False,
                            'properties': {
                                'entry_price': {'type': 'string', 'minLength': 3},
                                'stop_loss': {'type': 'string', 'minLength': 3},
                                'target_1': {'type': 'string', 'minLength': 3},
                                'target_2': {'type': 'string', 'minLength': 3},
                                'risk_reward_ratio': {'type': 'string', 'minLength': 2},
                                'position_size_note': {'type': 'string', 'minLength': 8},
                                'bull_scenario': {'type': 'string', 'minLength': 10},
                                'base_scenario': {'type': 'string', 'minLength': 10},
                                'bear_scenario': {'type': 'string', 'minLength': 10},
                                'invalidation_price': {'type': 'string', 'minLength': 8},
                                'watch_period': {'type': 'string', 'minLength': 5},
                            },
                            'required': [
                                'entry_price',
                                'stop_loss',
                                'target_1',
                                'target_2',
                                'risk_reward_ratio',
                                'position_size_note',
                                'bull_scenario',
                                'base_scenario',
                                'bear_scenario',
                                'invalidation_price',
                                'watch_period',
                            ],
                        },
                        'valuation_score': {
                            'type': 'object',
                            'additionalProperties': False,
                            'properties': {
                                'score': {'type': 'string'},
                                'factors': {
                                    'type': 'array',
                                    'items': {'type': 'string'},
                                    'maxItems': 5,
                                },
                                'assessment': {'type': 'string', 'minLength': 10},
                            },
                            'required': ['score', 'factors', 'assessment'],
                        },
                    },
                    'required': [
                        'ticker',
                        'summary',
                        'key_news',
                        'financial_highlights',
                        'risks_or_watchpoints',
                        'signal_or_takeaway',
                        'news_tone',
                        'trade_frame',
                        'valuation_score',
                    ],
                },
            }
        },
        'required': ['tickers'],
    }


def _coerce_model_profile(model_profile_or_name: ModelProfile | str) -> ModelProfile:
    if isinstance(model_profile_or_name, ModelProfile):
        return model_profile_or_name
    return build_model_profile(model_profile_or_name)


def _read_batch_size_override() -> int | None:
    raw_value = os.getenv('BATCH_SIZE', '').strip()
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        return None
    return value if value > 0 else None


def _log_analyzer_event(event: str, **fields: Any) -> None:
    logger.warning(_build_log_message(event, **fields))
    record_pipeline_event('analyzer', 'warning', event, **fields)


def _build_log_message(event: str, **fields: Any) -> str:
    payload = {'event': event, **fields}
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _require_trade_frame(entry: dict[str, Any], *, min_length: int = 1) -> dict[str, str]:
    value = entry.get('trade_frame')
    if not isinstance(value, dict):
        raise ValueError("Field 'trade_frame' must be an object.")
    return {
        'entry_price': _require_non_empty_string(value, 'entry_price', min_length=max(min_length, 3)),
        'stop_loss': _require_non_empty_string(value, 'stop_loss', min_length=max(min_length, 3)),
        'target_1': _require_non_empty_string(value, 'target_1', min_length=max(min_length, 3)),
        'target_2': _require_non_empty_string(value, 'target_2', min_length=max(min_length, 3)),
        'risk_reward_ratio': _require_non_empty_string(value, 'risk_reward_ratio', min_length=max(min_length, 2)),
        'position_size_note': _require_non_empty_string(value, 'position_size_note', min_length=max(min_length, 8)),
        'bull_scenario': _require_non_empty_string(value, 'bull_scenario', min_length=max(min_length, 10)),
        'base_scenario': _require_non_empty_string(value, 'base_scenario', min_length=max(min_length, 10)),
        'bear_scenario': _require_non_empty_string(value, 'bear_scenario', min_length=max(min_length, 10)),
        'invalidation_price': _require_non_empty_string(value, 'invalidation_price', min_length=max(min_length, 8)),
        'watch_period': _require_non_empty_string(value, 'watch_period', min_length=max(min_length, 5)),
    }


def _require_valuation_score(entry: dict[str, Any]) -> dict[str, object]:
    value = entry.get('valuation_score')
    if not isinstance(value, dict):
        raise ValueError("Field 'valuation_score' must be an object.")
    score = _require_non_empty_string(value, 'score')
    factors = value.get('factors', [])
    if not isinstance(factors, list):
        raise ValueError("Field 'valuation_score.factors' must be a list.")
    factors = [str(f).strip() for f in factors if isinstance(f, str) and f.strip()]
    assessment = _require_non_empty_string(value, 'assessment', min_length=10)
    return {
        'score': score,
        'factors': factors,
        'assessment': assessment,
    }


def _require_news_tone(entry: dict[str, Any]) -> dict[str, str | float | int]:
    value = entry.get('news_tone')
    if not isinstance(value, dict):
        raise ValueError("Field 'news_tone' must be an object.")

    label = _require_non_empty_string(value, 'label')
    if label not in {'bullish', 'neutral', 'bearish'}:
        raise ValueError("Field 'news_tone.label' must be bullish, neutral, or bearish.")

    confidence = value.get('confidence')
    if not isinstance(confidence, int) or confidence < 1 or confidence > 5:
        raise ValueError("Field 'news_tone.confidence' must be an integer between 1 and 5.")

    reasoning = _require_non_empty_string(value, 'reasoning', min_length=10)
    score = {'bearish': -1.0, 'neutral': 0.0, 'bullish': 1.0}[label] * float(confidence)
    return {
        'label': label,
        'confidence': confidence,
        'reasoning': reasoning,
        'score': score,
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

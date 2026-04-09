from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.types import CollectedTickerData, NewsItem, TickerAnalysis, WatchlistItem
from src.utils.cost_tracker import calculate_response_cost
from src.utils.env import load_dotenv
from src.utils.model_config import ModelProfile, build_model_profile, load_model_profile, safe_input_token_budget
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
) -> list[TickerAnalysis]:
    load_dotenv()
    model_profile = load_model_profile()
    if os.getenv('OPENAI_API_KEY'):
        llm_results = _analyze_with_openai(watchlist, collected, news_map, run_date, model_profile=model_profile)
        if llm_results:
            return llm_results
    return _build_fallback_analyses(watchlist, collected, news_map, run_date)


def _analyze_with_openai(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
    *,
    model_profile: ModelProfile,
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
        return _analyze_batches_with_client(client, model_profile, watchlist, collected, news_map, run_date)
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
) -> list[TickerAnalysis]:
    model_profile = _coerce_model_profile(model_profile_or_name)
    prepared = _prepare_payload_items(watchlist, collected, news_map)
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
        )

    return [analyses_by_ticker[item.ticker] for item in watchlist if item.ticker in analyses_by_ticker]


def _prepare_payload_items(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
) -> list[_PreparedPayloadItem]:
    payload = _build_payload(watchlist, collected, news_map)
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
            )
            return

        for fallback_analysis in _build_fallback_analyses(batch_items, collected, news_map, run_date):
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
            analyses_by_ticker[item.ticker] = _build_fallback_analysis(item, collected, news_map, run_date)
            continue

        analyses_by_ticker[item.ticker] = _build_openai_analysis(item, match, collected, news_map, run_date)


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
        )


def _build_payload(
    batch: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
) -> list[dict[str, Any]]:
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
                'price_to_book': market.price_to_book,
                'dividend_yield': market.dividend_yield,
                'volume': market.volume,
                'news': [
                    {
                        'title': article.title,
                        'source': article.source,
                        'published_at': article.published_at,
                    }
                    for article in news_map.get(item.ticker, [])
                ],
            }
        )
    return payload


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
) -> list[dict[str, Any]] | None:
    try:
        response = client.responses.create(
            model=model_profile.model,
            max_output_tokens=model_profile.max_output_tokens,
            input=[
                {
                    'role': 'system',
                    'content': [
                        {
                            'type': 'input_text',
                            'text': (
                                'You are a cost-aware equity research assistant. '
                                'Use only the provided data. Return strict JSON with key \'tickers\'. '
                                'All human-readable field values must be written in Korean. '
                                'Keep ticker symbols and company names unchanged.'
                            ),
                        }
                    ],
                },
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'input_text',
                            'text': (
                                'Create concise structured research notes for each ticker in Korean. '
                                'Required fields: ticker, summary, key_news, financial_highlights, '
                                'risks_or_watchpoints, signal_or_takeaway. '
                                'Use concise Korean sentences or phrases for every field value. '
                                'The key_news list must follow the same order as the provided news array '
                                'and each item must be a short Korean summary of the corresponding headline. '
                                f'Data date: {run_date.isoformat()}\n'
                                + json.dumps(payload, ensure_ascii=True)
                            ),
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


def _build_fallback_analyses(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
) -> list[TickerAnalysis]:
    return [_build_fallback_analysis(item, collected, news_map, run_date) for item in watchlist]


def _build_openai_analysis(
    item: WatchlistItem,
    match: dict[str, Any],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
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
        quarterly_financials=market.quarterly_financials,
        upcoming_events=market.upcoming_events[:5],
    )


def _build_fallback_analysis(
    item: WatchlistItem,
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
) -> TickerAnalysis:
    market = collected[item.ticker]
    ticker_news = news_map.get(item.ticker, [])
    price_text = f'{market.price:.2f} {market.currency}' if market.price is not None else '가격 정보 없음'
    change_text = f'{market.change_percent:+.2f}%' if market.change_percent is not None else '일간 등락률 정보 없음'
    news_context = _summarize_top_headline(ticker_news)
    summary_parts = [
        f'{item.name}({item.ticker})는 {_translate_sector(item.sector)} 섹터에서 추적 중입니다. 최근 확인 가격은 {price_text}이고, 일간 등락률은 {change_text}입니다.',
    ]
    if news_context:
        summary_parts.append(f'주요 헤드라인: {news_context}')
    return TickerAnalysis(
        ticker=item.ticker,
        name=item.name,
        date=run_date.isoformat(),
        summary=' '.join(summary_parts),
        key_news=[article.title for article in ticker_news[:5]],
        news_references=ticker_news[:5],
        financial_highlights=_build_fallback_financial_highlights(market),
        risks_or_watchpoints=_build_fallback_risks(market, ticker_news),
        signal_or_takeaway=_build_fallback_signal(market.change_percent, ticker_news),
        data_snapshot=_build_snapshot(market),
        fundamentals=_build_fundamentals(market),
        quarterly_financials=market.quarterly_financials,
        upcoming_events=market.upcoming_events[:5],
    )


def _build_fallback_signal(change_percent: float | None, ticker_news: list[NewsItem]) -> str:
    if change_percent is None:
        return '가격 데이터 미수집 — 수집 상태 점검 필요.'
    if change_percent >= 3.0:
        return f'강한 상승({change_percent:+.1f}%) — 모멘텀 지속 여부 확인 필요.'
    if change_percent >= 1.0:
        return f'상승 추세({change_percent:+.1f}%) — 관련 뉴스 및 추가 재료 점검.'
    if change_percent > -1.0:
        return f'보합권({change_percent:+.1f}%) — 특이사항 없음, 추적 유지.'
    if change_percent > -3.0:
        return f'하락 중({change_percent:+.1f}%) — 하락 원인 및 지지선 확인 필요.'
    return f'큰 폭 하락({change_percent:+.1f}%) — 뉴스 및 실적 일정 긴급 확인.'


def _build_fallback_risks(market: CollectedTickerData, ticker_news: list[NewsItem]) -> list[str]:
    risks: list[str] = []
    if market.change_percent is not None and market.change_percent <= -3.0:
        risks.append('일간 하락 폭이 크므로 추가 하락 가능성에 유의하세요.')
    if market.pe_ratio != 'N/A':
        try:
            pe_value = float(market.pe_ratio)
            if pe_value > 40:
                risks.append(f'PER({pe_value:.1f})이 높아 밸류에이션 부담이 있을 수 있습니다.')
        except ValueError:
            pass
    if not ticker_news:
        risks.append('수집된 뉴스가 없어 시장 심리 파악이 어렵습니다.')
    risks.append('의사결정 전 최근 실적 일정과 주요 헤드라인을 다시 확인하세요.')
    return risks


def _build_fallback_financial_highlights(market: CollectedTickerData) -> list[str]:
    highlights = [
        f'시가총액: {market.market_cap}',
        f'최근 12개월 PER: {market.pe_ratio}',
    ]
    if market.eps != 'N/A':
        highlights.append(f'EPS (TTM): {market.eps}')
    if market.price_to_book != 'N/A':
        highlights.append(f'PBR: {market.price_to_book}')
    if market.dividend_yield != 'N/A':
        highlights.append(f'배당수익률: {market.dividend_yield}')
    if market.week52_high != 'N/A' and market.week52_low != 'N/A':
        highlights.append(f'52주 범위: {market.week52_low} ~ {market.week52_high}')
    if market.sma_50 != 'N/A':
        highlights.append(f'50일 이동평균: {market.sma_50}')
    highlights.append(market.summary_note)
    return highlights


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
    }


def _build_fundamentals(market: CollectedTickerData) -> dict[str, str]:
    return {
        'market_cap': market.market_cap,
        'trailing_pe': market.pe_ratio,
        'eps': market.eps,
        'price_to_book': market.price_to_book,
        'dividend_yield': market.dividend_yield,
        'volume': market.volume,
        'avg_volume_3m': market.avg_volume_3m,
        '52w_high': market.week52_high,
        '52w_low': market.week52_low,
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
                'summary': _require_non_empty_string(entry, 'summary'),
                'key_news': _require_string_list(entry, 'key_news'),
                'financial_highlights': _require_string_list(entry, 'financial_highlights'),
                'risks_or_watchpoints': _require_string_list(entry, 'risks_or_watchpoints'),
                'signal_or_takeaway': _require_non_empty_string(entry, 'signal_or_takeaway'),
            }
        )

    return validated


def _require_non_empty_string(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field '{key}' must be a non-empty string.")
    return value.strip()


def _require_string_list(entry: dict[str, Any], key: str) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Field '{key}' must be a list.")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Field '{key}' must contain non-empty strings.")
        normalized.append(item.strip())
    return normalized


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
                        'summary': {'type': 'string'},
                        'key_news': {'type': 'array', 'items': {'type': 'string'}},
                        'financial_highlights': {'type': 'array', 'items': {'type': 'string'}},
                        'risks_or_watchpoints': {'type': 'array', 'items': {'type': 'string'}},
                        'signal_or_takeaway': {'type': 'string'},
                    },
                    'required': [
                        'ticker',
                        'summary',
                        'key_news',
                        'financial_highlights',
                        'risks_or_watchpoints',
                        'signal_or_takeaway',
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

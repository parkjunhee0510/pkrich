from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from src.collector.news_rss import load_source_priorities
from src.output.json_export import write_json_outputs
from src.output.obsidian import mirror_markdown_outputs
from src.types import MarketRegime, PortfolioSummary, TickerAnalysis, TickerDecision
from src.utils.config import load_simple_mapping
from src.utils.datastore import get_datastore
from src.utils.datastore_csv import append_price_history_csv
from src.utils.earnings_history import build_earnings_surprise_summary
from src.utils.earnings_pattern import build_earnings_pattern
from src.utils.earnings_setup import build_earnings_setup, extract_earnings_countdown
from src.utils.monthly_summary import load_monthly_summary
from src.utils.news_tone import build_news_tone
from src.utils.pipeline_logging import record_pipeline_event
from src.utils.quarterly_financials import build_quarterly_financial_display_rows
from src.utils.sec_filings import collect_sec_filings, sort_sec_filings
from src.utils.ticker_timelines import summarize_recent_timeline
from src.utils.weekly_summary import WeeklySummaryData, load_weekly_summary

_SECTOR_DISPLAY_NAMES = {
    "Technology": "기술",
    "Semiconductors": "반도체",
    "Healthcare": "헬스케어",
    "Financials": "금융",
    "Energy": "에너지",
    "Consumer Discretionary": "경기소비재",
    "Consumer Staples": "필수소비재",
    "Industrials": "산업재",
    "Communication Services": "커뮤니케이션 서비스",
    "Utilities": "유틸리티",
    "Real Estate": "부동산",
    "Materials": "소재",
}
_DEFAULT_SECTOR_DISPLAY_ORDER = [
    "Technology",
    "Semiconductors",
    "Healthcare",
    "Financials",
    "Energy",
    "Consumer Discretionary",
    "Consumer Staples",
    "Industrials",
    "Communication Services",
    "Utilities",
    "Real Estate",
    "Materials",
]
_MAX_DISPLAY_NEWS_AGE_DAYS = 180
_COMMITTEE_ROLE_ORDER = (
    "growth_analyst",
    "value_skeptic",
    "risk_manager",
    "macro_strategist",
    "pm",
)
_COMMITTEE_ROLE_LABELS = {
    "growth_analyst": "Growth Analyst",
    "value_skeptic": "Value Skeptic",
    "risk_manager": "Risk Manager",
    "macro_strategist": "Macro Strategist",
    "pm": "PM",
}


def write_outputs(
    analyses: list[TickerAnalysis],
    run_date: date,
    *,
    market_overview: list[dict[str, str]] | None = None,
    direct_period_changes: dict[str, dict[str, str]] | None = None,
    portfolio_summary: PortfolioSummary | None = None,
    signal_stats: dict[str, Any] | None = None,
    macro_context: dict[str, Any] | None = None,
    portfolio_risk: dict[str, Any] | None = None,
    market_regime: MarketRegime | None = None,
    decisions: list[TickerDecision] | None = None,
    state_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_root = Path("output")
    daily_dir = output_root / "daily"
    weekly_dir = daily_dir / "weekly"
    tickers_dir = output_root / "tickers"
    data_dir = output_root / "data"

    daily_dir.mkdir(parents=True, exist_ok=True)
    weekly_dir.mkdir(parents=True, exist_ok=True)
    tickers_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    enriched_analyses = [_enrich_analysis(analysis) for analysis in analyses]
    datastore = get_datastore(output_root)
    datastore.append_prices(enriched_analyses)
    datastore.append_analysis_snapshots(enriched_analyses)
    csv_period_changes = datastore.load_period_changes(run_date)
    period_changes_by_ticker = _merge_period_changes(csv_period_changes, direct_period_changes or {})
    weekly_summary = load_weekly_summary(
        run_date,
        output_root=output_root,
        macro_context=macro_context,
        market_regime=market_regime,
        portfolio_risk=portfolio_risk,
        decisions=decisions,
    )
    timeline_map = write_json_outputs(
        enriched_analyses,
        run_date,
        market_overview=market_overview,
        output_root=output_root,
        period_changes_by_ticker=period_changes_by_ticker,
        portfolio_summary=portfolio_summary,
        signal_stats=signal_stats,
        macro_context=macro_context,
        portfolio_risk=portfolio_risk,
        weekly_summary=weekly_summary,
        market_regime=market_regime,
        decisions=decisions,
        state_metadata=state_metadata,
    )

    daily_path = daily_dir / f"{run_date.isoformat()}.md"
    _write_text_artifact(
        daily_path,
        render_daily_markdown(
            enriched_analyses,
            run_date,
            market_overview=market_overview or [],
            portfolio_summary=portfolio_summary,
            macro_context=macro_context,
            portfolio_risk=portfolio_risk,
            market_regime=market_regime,
            decisions=decisions,
        ),
        artifact="daily_note",
    )

    ticker_paths: dict[str, Path] = {}
    for analysis in enriched_analyses:
        ticker_dir = tickers_dir / analysis.ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        ticker_path = ticker_dir / f"{run_date.isoformat()}.md"
        _write_text_artifact(
            ticker_path,
            render_ticker_markdown(
                analysis,
                period_changes=period_changes_by_ticker.get(analysis.ticker),
                recent_timeline=timeline_map.get(analysis.ticker, [])[:3],
            ),
            artifact="ticker_note",
            ticker=analysis.ticker,
        )
        ticker_paths[analysis.ticker] = ticker_path

    weekly_path = weekly_dir / f"{weekly_summary.iso_year}-W{weekly_summary.iso_week:02d}.md"
    _write_text_artifact(
        weekly_path,
        render_weekly_markdown(weekly_summary, macro_context=macro_context),
        artifact="weekly_note",
    )
    monthly_summary = load_monthly_summary(run_date, output_root=output_root)
    monthly_path = weekly_dir / f"{run_date.strftime('%Y-%m')}.md"
    _write_text_artifact(monthly_path, render_monthly_markdown(monthly_summary), artifact="monthly_note")

    mirror_markdown_outputs(daily_path, ticker_paths)
    return {
        "daily_path": daily_path,
        "weekly_path": weekly_path,
        "monthly_path": monthly_path,
        "ticker_paths": ticker_paths,
    }


def render_daily_markdown(
    analyses: list[TickerAnalysis],
    run_date: date,
    market_overview: list[dict[str, str]] | None = None,
    portfolio_summary: PortfolioSummary | None = None,
    macro_context: dict[str, Any] | None = None,
    portfolio_risk: dict[str, Any] | None = None,
    market_regime: MarketRegime | None = None,
    decisions: list[TickerDecision] | None = None,
) -> str:
    watchlist_rows = "\n".join(
        f"| {analysis.ticker} | {analysis.data_snapshot['Price']} | {analysis.data_snapshot['Daily Change']} | {_escape_table_cell(analysis.signal_or_takeaway)} |"
        for analysis in analyses
    )
    top_news_links = _render_daily_news_links(analyses)
    upcoming_schedule = _render_daily_upcoming_schedule(analyses)
    action_items = "\n".join(f"- [ ] {analysis.ticker}: {analysis.signal_or_takeaway}" for analysis in analyses) or "- [ ] 점검할 항목이 없습니다."
    tldr_lines = _render_daily_tldr(analyses, decisions=decisions, market_regime=market_regime)

    lines = [
        f"# 일일 리서치 - {run_date.isoformat()}",
        "",
        "## TL;DR",
        tldr_lines,
        "",
        "## 시장 개요",
        _render_market_overview(market_overview or []),
        "",
    ]

    if macro_context:
        lines.extend(
            [
                "## 매크로 환경",
                _render_macro_context(macro_context),
                "",
                "## 이번 주 시장 주요 일정",
                _render_weekly_macro_schedule(macro_context),
                "",
                "## 보유 종목 민감도",
                _render_portfolio_macro_sensitivity(macro_context),
                "",
            ]
        )

    if market_regime and market_regime.regime != "neutral":
        regime_labels = {"risk_on": "🟢 위험선호", "neutral": "🟡 중립", "risk_off": "🔴 위험회피"}
        lines.extend([
            "## 시장 리짐",
            f"**{regime_labels.get(market_regime.regime, market_regime.regime)}** (확신도 {market_regime.confidence}%)",
            "",
            market_regime.implication,
            "",
        ])
    elif market_regime:
        lines.extend([
            "## 시장 리짐",
            f"**🟡 중립** (확신도 {market_regime.confidence}%)",
            "",
            market_regime.implication,
            "",
        ])

    if decisions:
        decision_map = {d.ticker: d for d in decisions}
        decision_rows = "\n".join(
            f"| {d.ticker} | {d.action} | {d.conviction} | {_escape_table_cell(d.reason)} | {d.valid_until} |"
            for d in decisions
        )
        lines.extend([
            "## 의사결정 요약",
            "| 티커 | 액션 | 확신도 | 근거 | 유효기간 |",
            "|------|------|--------|------|----------|",
            decision_rows,
            "",
        ])

    lines.extend([
        "## 관심 종목 요약",
        "| 티커 | 가격 | 등락률 | 한줄 판단 |",
        "|------|------|--------|-----------|",
        watchlist_rows or "| N/A | N/A | N/A | N/A |",
        "",
    ])

    if not (_hide_empty_top_news_links_section() and top_news_links == "- 확인 가능한 뉴스 링크가 없습니다."):
        lines.extend(["## 주요 뉴스 링크", top_news_links, ""])

    lines.extend(["## SEC 공시", _render_daily_sec_filings(analyses), ""])

    if portfolio_summary and portfolio_summary.positions:
        lines.extend(["## 포트폴리오 현황", _render_portfolio_summary(portfolio_summary), ""])
        if portfolio_risk and portfolio_risk.get("positions_by_weight"):
            lines.extend(["## 포트폴리오 리스크", _render_portfolio_risk(portfolio_risk), ""])

    lines.extend(["## 다가오는 일정", upcoming_schedule, "", "## 점검 항목", action_items, ""])
    return "\n".join(lines)


def _render_daily_tldr(
    analyses: list[TickerAnalysis],
    *,
    decisions: list[TickerDecision] | None = None,
    market_regime: MarketRegime | None = None,
) -> str:
    bullets: list[str] = []
    added_tickers: set[str] = set()

    if market_regime:
        regime_labels = {
            "risk_on": "위험선호",
            "neutral": "중립",
            "risk_off": "위험회피",
        }
        bullets.append(
            f"- 시장 리짐: {regime_labels.get(market_regime.regime, market_regime.regime)} ({market_regime.confidence}%) · {market_regime.implication or '포지션 크기는 보수적으로 점검'}"
        )

    ordered_decisions = sorted(
        decisions or [],
        key=lambda item: (
            0 if item.action == "buy" else 1 if item.action == "avoid" else 2,
            -item.conviction,
            item.ticker,
        ),
    )
    for decision in ordered_decisions:
        if len(bullets) >= 4:
            break
        if decision.ticker in added_tickers:
            continue
        action_label = {
            "buy": "우선 실행",
            "watch": "관찰 유지",
            "avoid": "회피 유지",
        }.get(decision.action, decision.action)
        bullets.append(
            f"- {decision.ticker}: {action_label} · 확신도 {decision.conviction} · {decision.reason or '세부 근거 점검'}"
        )
        added_tickers.add(decision.ticker)

    next_event = _next_upcoming_event(analyses)
    if next_event and len(bullets) < 5:
        bullets.append(
            "- 일정 체크: {ticker} {label} {date} ({days_until}{timing})".format(
                ticker=next_event["ticker"],
                label=next_event["label"],
                date=next_event["date"],
                days_until=next_event["days_until"],
                timing=f" · {next_event['timing']}" if next_event.get("timing") else "",
            )
        )

    if not bullets:
        fallback = analyses[:4]
        bullets = [f"- {analysis.ticker}: {analysis.signal_or_takeaway}" for analysis in fallback]

    return "\n".join(bullets[:5])


def render_ticker_markdown(
    analysis: TickerAnalysis,
    *,
    period_changes: dict[str, str] | None = None,
    recent_timeline: list[dict[str, Any]] | None = None,
) -> str:
    snapshot_rows = _render_snapshot_rows(analysis.data_snapshot, analysis)
    committee_section = _render_committee_section(getattr(analysis, "committee_analysis", None))
    return "\n".join(
        [
            f"# {analysis.ticker} - {analysis.date}",
            "",
            "## 요약",
            analysis.summary or "요약이 없습니다.",
            "",
            committee_section,
            "",
            "## 실적 셋업 요약",
            _render_earnings_setup_summary(analysis),
            "",
            "## 주요 뉴스",
            _render_news_items(analysis),
            "",
            "## 재무 하이라이트",
            _render_bullets(analysis.financial_highlights),
            "",
            "## 리스크 / 체크포인트",
            _render_bullets(analysis.risks_or_watchpoints),
            "",
            "## 데이터 스냅샷",
            "| 항목 | 값 |",
            "|------|----|",
            *snapshot_rows,
            "",
            "## 포지셔닝 데이터",
            _render_positioning_data(analysis.fundamentals),
            "",
            "## 옵션 요약",
            _render_options_summary(analysis.options_summary),
            "",
            "## 실적 컨센서스 디테일",
            _render_earnings_setup(analysis),
            "",
            "## 최근 변화 비교",
            _render_period_changes(analysis, period_changes),
            "",
            "## 실적 서프라이즈 패턴",
            _render_earnings_surprise_pattern(analysis.quarterly_financials),
            "",
            "## 최근 4분기 재무",
            _render_quarterly_financials(analysis.quarterly_financials),
            "",
            "## 다가오는 일정",
            _render_upcoming_events(analysis.upcoming_events),
            "",
            "## 최근 타임라인",
            _render_recent_timeline(recent_timeline or []),
            "",
            "## 밸류에이션 점수",
            _render_valuation_score(getattr(analysis, 'valuation_score', {})),
            "",
            "## Peer Rank",
            _render_peer_rank(getattr(analysis, 'peer_rank', {})),
            "",
            "## 트레이드 프레임",
            _render_trade_frame(analysis.trade_frame),
            "",
            "## 시그널 / 한줄 결론",
            analysis.signal_or_takeaway or "요약 결론이 없습니다.",
            "",
        ]
    )


def _render_committee_section(committee_analysis: Any) -> str:
    payload = committee_analysis if isinstance(committee_analysis, dict) else {}
    agreement_status = str(payload.get("agreement_status", "N/A") or "N/A")
    deep_review_triggered = bool(payload.get("deep_review_triggered", False))
    deep_review_reasons = payload.get("deep_review_reasons", [])
    if isinstance(deep_review_reasons, list):
        reason_text = ", ".join(str(reason).strip() for reason in deep_review_reasons if str(reason).strip())
    else:
        reason_text = ""
    roles = payload.get("roles", {})
    role_lines = []
    if isinstance(roles, dict):
        for role in _COMMITTEE_ROLE_ORDER:
            role_payload = roles.get(role)
            if not isinstance(role_payload, dict):
                continue
            summary = str(role_payload.get("summary", "")).strip() or "요약이 없습니다."
            stance = str(role_payload.get("stance", "")).strip() or "N/A"
            label = _COMMITTEE_ROLE_LABELS.get(role, role)
            role_lines.append(f"- {label}: {summary} [{stance}]")

    lines = [
        "## 위원회 분석",
        f"- 합의 상태: {agreement_status}",
        f"- 딥 리뷰: {'triggered' if deep_review_triggered else '없음'}"
        + (f" · {reason_text}" if deep_review_triggered and reason_text else ""),
    ]
    if role_lines:
        lines.extend(role_lines)
    else:
        lines.append("- 역할 요약: 데이터 없음")
    return "\n".join(lines)


def render_weekly_markdown(summary: WeeklySummaryData, macro_context: dict[str, Any] | None = None) -> str:
    lines = [
        f"# 주간 리서치 - {summary.iso_year}-W{summary.iso_week:02d}",
        "",
        f"기간: {summary.start_date} ~ {summary.end_date}",
        f"집계 영업일 수: {summary.trading_days}일",
        "",
    ]
    if summary.is_partial:
        lines.extend(["> 데이터 축적 중: 이번 주 영업일 데이터가 3일 미만입니다.", ""])
    if macro_context:
        lines.extend(
            [
                "## 이번 주 시장 주요 일정",
                _render_weekly_macro_schedule(macro_context),
                "",
                "## 보유 종목 민감도",
                _render_portfolio_macro_sensitivity(macro_context),
                "",
            ]
        )
    if summary.weekly_insight:
        lines.extend(["## 주간 인사이트", summary.weekly_insight, ""])
    if summary.weekly_report:
        lines.extend(["## 구조화 주간 보고서", _render_weekly_report(summary.weekly_report), ""])
    lines.extend(
        [
            "## 주간 시장 개요",
            _render_weekly_market_moves(summary),
            "",
            "## 종목별 주간 등락 요약",
            _render_weekly_ticker_table(summary),
            "",
            "## 섹터 퍼포먼스",
            _render_weekly_sector_performance(summary),
            "",
            "## 주간 상위 상승/하락 종목",
            "### 상승",
            _render_weekly_mover_list(summary.top_gainers, empty_message="- 이번 주 상승 종목이 없습니다."),
            "",
            "### 하락",
            _render_weekly_mover_list(summary.top_losers, empty_message="- 이번 주 하락 종목이 없습니다."),
            "",
            "## 이번 주 반복 노출 뉴스 요약",
            _render_weekly_news(summary),
            "",
            "## 시그널 검증 결과 (지난 20거래일)",
            _render_weekly_signal_validation(summary),
            "",
            "## 다음 주 점검 항목",
            _render_weekly_actions(summary),
            "",
        ]
    )
    return "\n".join(lines)


def render_monthly_markdown(summary: dict[str, Any]) -> str:
    if summary.get("status") != "ok":
        return "\n".join(
            [
                f"# 월간 리서치 - {summary.get('month', 'N/A')}",
                "",
                "월간 집계를 생성할 데이터가 아직 충분하지 않습니다.",
                "",
            ]
        )

    lines = [
        f"# 월간 리서치 - {summary.get('month', 'N/A')}",
        "",
        f"기간: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}",
        f"집계 영업일 수: {summary.get('trading_days', 0)}일",
        "",
        "## 상위 종목",
    ]
    top_tickers = summary.get("top_tickers", [])
    if top_tickers:
        lines.extend(
            f"- {row.get('ticker', 'N/A')}: {row.get('avg_daily_change', 'N/A')}"
            for row in top_tickers
        )
    else:
        lines.append("- 데이터가 없습니다.")
    lines.extend(["", "## 상위 섹터"])
    top_sectors = summary.get("top_sectors", [])
    if top_sectors:
        lines.extend(
            f"- {row.get('sector', 'N/A')}: {row.get('avg_daily_change', 'N/A')}"
            for row in top_sectors
        )
    else:
        lines.append("- 데이터가 없습니다.")
    lines.append("")
    return "\n".join(lines)


def append_price_history(path: Path, analyses: list[TickerAnalysis]) -> None:
    append_price_history_csv(path, analyses)


def _merge_period_changes(
    csv: dict[str, dict[str, str]],
    direct: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for ticker in set(csv) | set(direct):
        csv_entry = csv.get(ticker, {})
        direct_entry = direct.get(ticker, {})
        result[ticker] = {
            "7d": csv_entry.get("7d") if csv_entry.get("7d") not in (None, "N/A") else direct_entry.get("7d", "N/A"),
            "30d": csv_entry.get("30d") if csv_entry.get("30d") not in (None, "N/A") else direct_entry.get("30d", "N/A"),
        }
    return result


def _enrich_analysis(analysis: TickerAnalysis) -> TickerAnalysis:
    news_tone = analysis.news_tone or build_news_tone(analysis)
    return replace(analysis, news_tone=news_tone)


def _escape_table_cell(value: Any) -> str:
    text = str(value) if value is not None else ""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _render_weekly_market_moves(summary: WeeklySummaryData) -> str:
    if not summary.market_moves:
        return "- 이번 주 시장 개요 데이터가 없습니다."
    return "\n".join(f"- {move.label}: {move.start_price} -> {move.end_price} ({move.weekly_change})" for move in summary.market_moves)


def _render_weekly_ticker_table(summary: WeeklySummaryData) -> str:
    if not summary.ticker_moves:
        return "| 티커 | 시작가 | 종료가 | 주간 등락률 |\n|------|--------|--------|-------------|\n| N/A | N/A | N/A | N/A |"
    rows = "\n".join(f"| {move.ticker} | {move.start_price} | {move.end_price} | {move.weekly_change} |" for move in summary.ticker_moves)
    return "\n".join(["| 티커 | 시작가 | 종료가 | 주간 등락률 |", "|------|--------|--------|-------------|", rows])


def _render_weekly_sector_performance(summary: WeeklySummaryData) -> str:
    if not summary.sector_performance:
        return "- 이번 주 섹터 성과 데이터가 없습니다."
    rows = "\n".join(
        f"| {item.sector} | {item.ticker_count} | {item.average_weekly_change} |"
        for item in summary.sector_performance
    )
    return "\n".join(
        [
            "| 섹터 | 종목수 | 평균 주간 등락 |",
            "|------|--------|---------------|",
            rows,
        ]
    )


def _render_weekly_mover_list(movers: list[Any], *, empty_message: str) -> str:
    if not movers:
        return empty_message
    return "\n".join(f"- **{move.ticker}**: {move.weekly_change} ({move.start_price} -> {move.end_price})" for move in movers)


def _render_weekly_news(summary: WeeklySummaryData) -> str:
    if not summary.repeated_news:
        return "- 이번 주 반복 노출된 뉴스가 없습니다."
    return "\n".join(f"- {item.count}회 노출: {item.summary} ({', '.join(item.tickers)}) - {item.source}" for item in summary.repeated_news)


def _render_weekly_actions(summary: WeeklySummaryData) -> str:
    if not summary.action_items:
        return "- [ ] 다음 주 점검 항목이 없습니다."
    return "\n".join(f"- [ ] {item}" for item in summary.action_items)


def _render_weekly_signal_validation(summary: WeeklySummaryData) -> str:
    if not summary.signal_validation_rows:
        return "- 아직 평가 가능한 시그널 이력이 없습니다."

    rows = [
        "| 날짜 | 종목 | 방향 | 촉매 | 1D | 5D | 20D |",
        "|------|------|------|------|----|----|-----|",
    ]
    for row in summary.signal_validation_rows:
        rows.append(
            "| {date} | {ticker} | {direction} | {catalyst} | {r1} | {r5} | {r20} |".format(
                date=row.get("signal_date", ""),
                ticker=row.get("ticker", ""),
                direction=row.get("signal_direction", ""),
                catalyst=row.get("catalyst_tag", "N/A"),
                r1=row.get("return_1d", "N/A"),
                r5=row.get("return_5d", "N/A"),
                r20=row.get("return_20d", "N/A"),
            )
        )

    if summary.signal_summary:
        rows.append("")
        rows.extend(f"**{line}**" for line in summary.signal_summary)

    return "\n".join(rows)


def _render_bullets(items: list[str]) -> str:
    if not items:
        return "- 없음."
    return "\n".join(f"- {item}" for item in items)


def _render_news_items(analysis: TickerAnalysis) -> str:
    if analysis.news_references:
        visible_news = _displayable_news_items(
            analysis.news_references,
            anchor_date=_analysis_anchor_date(analysis),
            hide_fallback_without_links=_hide_fallback_news_without_links_in_ticker_notes(),
        )
        if visible_news:
            rendered_lines = [
                line
                for line in (
                    _render_news_line(item, _news_summary_for_reference(analysis, item))
                    for item in visible_news
                )
                if line.strip()
            ]
            if rendered_lines:
                return "\n".join(rendered_lines)
        if _hide_fallback_news_without_links_in_ticker_notes():
            return "- 없음."
    return _render_bullets(analysis.key_news)


def _render_daily_news_links(analyses: list[TickerAnalysis]) -> str:
    grouped: dict[str, list[tuple[tuple[datetime, int], str, str]]] = {}
    for analysis in analyses:
        sector = analysis.data_snapshot.get("Sector", "N/A")
        if analysis.news_references:
            visible_news = _displayable_news_items(
                analysis.news_references,
                anchor_date=_analysis_anchor_date(analysis),
                hide_fallback_without_links=_hide_fallback_news_without_links(),
            )
            if not visible_news:
                continue
            first_news = visible_news[0]
            translated_summary = _news_summary_for_reference(analysis, first_news)
            line = _render_daily_news_entry(analysis.ticker, first_news, translated_summary)
            sort_key = (_news_sort_key(first_news.published_at), _source_priority(first_news.source))
        elif analysis.key_news:
            line = f"- **{analysis.ticker}**: {analysis.key_news[0]}"
            sort_key = (_news_sort_key(""), _source_priority(""))
        else:
            continue
        grouped.setdefault(sector, []).append((sort_key, analysis.ticker, line))

    if not grouped:
        return "- 확인 가능한 뉴스 링크가 없습니다."

    sections: list[str] = []
    for sector in _ordered_sectors(grouped):
        sections.append(f"### {_display_sector(sector)}")
        ordered_lines = sorted(grouped[sector], key=lambda entry: (entry[0][0], entry[0][1], entry[1]), reverse=True)
        sections.extend(entry[2] for entry in ordered_lines)
        sections.append("")
    return "\n".join(sections).rstrip()


def _render_daily_upcoming_schedule(analyses: list[TickerAnalysis]) -> str:
    events: list[tuple[str, str, str, str, str]] = []
    for analysis in analyses:
        for event in analysis.upcoming_events:
            events.append(
                (
                    event.get("date", "9999-12-31"),
                    analysis.ticker,
                    event.get("label", "일정"),
                    event.get("days_until", "N/A"),
                    event.get("timing", ""),
                )
            )
    if not events:
        return "- 확인 가능한 예정 일정이 없습니다."
    ordered = sorted(events, key=lambda item: (item[0], item[1], item[2]))[:8]
    return "\n".join(
        _render_daily_upcoming_schedule_line(event_date, ticker, label, days_until, timing)
        for event_date, ticker, label, days_until, timing in ordered
    )


def _render_daily_sec_filings(analyses: list[TickerAnalysis]) -> str:
    filings: list[tuple[str, dict[str, str]]] = []
    for analysis in analyses:
        for filing in sort_sec_filings(collect_sec_filings(analysis.news_references)):
            filings.append((analysis.ticker, filing))

    if not filings:
        return "- 오늘 반영된 SEC 공시가 없습니다."

    ordered = sorted(
        filings,
        key=lambda entry: (str(entry[1].get("published_at", "")), entry[0], str(entry[1].get("tag", ""))),
        reverse=True,
    )
    lines: list[str] = []
    for ticker, filing in ordered:
        tag = filing.get("tag", "").strip()
        title = filing.get("title", "").strip() or "SEC 공시"
        published_at = filing.get("published_at", "").strip()
        link = filing.get("link", "").strip()
        title_text = f"[{title}]({link})" if link else title
        suffix = f" ({published_at})" if published_at else ""
        tag_prefix = f"[{tag}] " if tag else ""
        lines.append(f"- **{ticker}** {tag_prefix}{title_text}{suffix}")
    return "\n".join(lines)


def _next_upcoming_event(analyses: list[TickerAnalysis]) -> dict[str, str] | None:
    ranked_events: list[tuple[int, str, dict[str, str]]] = []
    for analysis in analyses:
        for event in analysis.upcoming_events or []:
            days_until = str(event.get("days_until", "")).strip()
            try:
                sort_days = int(days_until)
            except ValueError:
                sort_days = 9999
            ranked_events.append(
                (
                    sort_days,
                    analysis.ticker,
                    {
                        "ticker": analysis.ticker,
                        "label": str(event.get("label", "")).strip() or str(event.get("type", "이벤트")).strip() or "이벤트",
                        "date": str(event.get("date", "")).strip() or "N/A",
                        "days_until": f"D-{days_until}" if days_until and not days_until.startswith("D-") else (days_until or "D-?"),
                        "timing": str(event.get("timing", "")).strip(),
                    },
                )
            )
    if not ranked_events:
        return None
    ranked_events.sort(key=lambda item: (item[0], item[1], item[2]["label"]))
    return ranked_events[0][2]


def _render_portfolio_summary(portfolio_summary: PortfolioSummary) -> str:
    rows = [
        "| 티커 | 수량 | 평균단가 | 현재가 | 평가금액 | 손익 | 수익률 |",
        "|------|------|----------|--------|----------|------|--------|",
    ]
    for position in portfolio_summary.positions:
        rows.append(
            "| {ticker} | {shares} | {avg_cost} | {market_price} | {market_value} | {pnl} | {return_pct} |".format(
                ticker=position.ticker,
                shares=_format_decimal(position.shares),
                avg_cost=_format_money(position.avg_cost, position.currency),
                market_price=_format_optional_money(position.market_price, position.currency),
                market_value=_format_optional_money(position.market_value, position.currency),
                pnl=_format_optional_signed_money(position.unrealized_pnl, position.currency),
                return_pct=_format_optional_percent(position.unrealized_return_pct),
            )
        )

    rows.extend(
        [
            "",
            f"- 총 매수금액: {_format_money(portfolio_summary.total_cost_basis, 'USD')}",
            f"- 총 평가금액: {_format_optional_money(portfolio_summary.total_market_value, 'USD')}",
            f"- 총 평가손익: {_format_optional_signed_money(portfolio_summary.total_unrealized_pnl, 'USD')}",
            f"- 총 수익률: {_format_optional_percent(portfolio_summary.total_unrealized_return_pct)}",
        ]
    )
    return "\n".join(rows)


def _render_period_changes(analysis: TickerAnalysis, period_changes: dict[str, str] | None) -> str:
    period_changes = period_changes or {"7d": "N/A", "30d": "N/A"}
    return "\n".join(
        [
            f"- 현재가: {analysis.data_snapshot.get('Price', 'N/A')}",
            f"- 7일 변화: {period_changes.get('7d', 'N/A')}",
            f"- 30일 변화: {period_changes.get('30d', 'N/A')}",
            f"- 뉴스 톤: {_display_news_tone(analysis.news_tone)}",
        ]
    )


def _render_earnings_setup(analysis: TickerAnalysis) -> str:
    currency = _snapshot_currency(analysis.data_snapshot)
    setup = build_earnings_setup(
        analysis.fundamentals,
        analysis.quarterly_financials,
        analysis.upcoming_events,
        currency=currency,
    )
    return "\n".join(
        [
            f"- Forward EPS: {setup.get('forward_eps', 'N/A')}",
            f"- TTM EPS: {setup.get('ttm_eps', 'N/A')}",
            f"- Forward vs TTM: {_render_directional_value(setup.get('forward_vs_ttm', 'N/A'))}",
            f"- EPS 성장률: {setup.get('earnings_growth', 'N/A')}",
            f"- 최근 분기 추정 EPS: {setup.get('latest_estimated_eps', 'N/A')}",
            (
                f"- 최근 분기 서프라이즈: {setup.get('latest_surprise_pct', 'N/A')} / "
                f"{_display_beat_miss(setup.get('latest_beat_miss', 'N/A'))}"
            ),
            f"- 다음 실적 체크포인트: {setup.get('next_earnings_event', 'N/A')}",
        ]
    )


def _render_earnings_setup_summary(analysis: TickerAnalysis) -> str:
    currency = _snapshot_currency(analysis.data_snapshot)
    setup = build_earnings_setup(
        analysis.fundamentals,
        analysis.quarterly_financials,
        analysis.upcoming_events,
        currency=currency,
    )
    return "\n".join(
        [
            "| Forward vs TTM | 최근 분기 결과 | 다음 실적 D-day | EPS 성장률 |",
            "|---|---|---|---|",
            (
                f"| {_render_directional_value(setup.get('forward_vs_ttm', 'N/A'))} "
                f"| {_render_earnings_result_summary(setup)} "
                f"| {extract_earnings_countdown(setup.get('next_earnings_event', 'N/A'))} "
                f"| {setup.get('earnings_growth', 'N/A')} |"
            ),
            (
                f"| {setup.get('forward_eps', 'N/A')} vs {setup.get('ttm_eps', 'N/A')} "
                f"| 컨센서스 EPS {setup.get('latest_estimated_eps', 'N/A')} "
                f"| {setup.get('next_earnings_event', 'N/A')} "
                f"| YoY 기준 이익 성장 체력 |"
            ),
        ]
    )


def _render_price_action(price_action: dict[str, str]) -> str:
    if not price_action:
        return "- 가격 행동 데이터가 없습니다."
    return "\n".join(
        [
            f"- ATR(14): {_render_price_action_pair(price_action.get('atr_14d', 'N/A'), price_action.get('atr_percent', 'N/A'))}",
            f"- Relative Volume: {price_action.get('relative_volume', 'N/A')}",
            f"- Gap: {price_action.get('gap_percent', 'N/A')}",
            f"- vs SMA50: {_render_directional_value(price_action.get('price_vs_sma50', 'N/A'))}",
            f"- vs SMA200: {_render_directional_value(price_action.get('price_vs_sma200', 'N/A'))}",
            f"- 52주 위치: {price_action.get('week52_position', 'N/A')}",
            f"- RS vs SPY(30D): {price_action.get('rs_vs_spy', 'N/A')}",
            f"- RS vs Sector ETF: {price_action.get('rs_vs_sector_etf', 'N/A')}",
        ]
    )


def _render_earnings_surprise_pattern(quarterly_financials: list[dict[str, str]]) -> str:
    summary = build_earnings_surprise_summary(quarterly_financials)
    pattern = build_earnings_pattern(quarterly_financials)
    if summary["pattern"] == "insufficient_data":
        return "- 실적 서프라이즈 데이터가 2분기 미만으로 패턴 분석 불가"
    lines = [
        f"- **패턴**: {summary['pattern']} (최근 {summary['quarters_analyzed']}분기 분석)",
        f"- **Beat 비율**: {summary['beat_rate']} | 평균 서프라이즈: {summary['avg_surprise_pct']}",
        f"- **연속 상회**: {pattern['beat_streak']}분기 | 추세: {_display_surprise_trend(pattern['surprise_trend'])} | 평균 서프라이즈: {pattern['avg_surprise_pct']}",
    ]
    if summary["consecutive_beats"] > 0:
        lines.append(f"- **연속 Beat**: {summary['consecutive_beats']}분기")
    if summary["consecutive_misses"] > 0:
        lines.append(f"- **연속 Miss**: {summary['consecutive_misses']}분기")
    lines.append(f"- **힌트**: {summary['post_earnings_hint']}")
    return "\n".join(lines)


def _display_surprise_trend(value: object) -> str:
    labels = {
        "improving": "개선",
        "deteriorating": "악화",
        "stable": "안정",
        "insufficient_data": "데이터 부족",
    }
    return labels.get(str(value), str(value))


def _render_quarterly_financials(rows: list[dict[str, str]]) -> str:
    display_rows = build_quarterly_financial_display_rows(rows)
    if not display_rows:
        return (
            "| 분기 | 매출 | 영업이익 | EPS | EPS 추정 | 서프라이즈 | 결과 |\n"
            "|------|------|----------|-----|----------|------------|------|\n"
            "| N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
        )
    body = "\n".join(
        (
            f"| {row.get('quarter', 'N/A')} | "
            f"{_format_quarterly_value(row.get('revenue', 'N/A'), unit='USD', yoy=row.get('revenue_yoy', ''))} | "
            f"{_format_quarterly_value(row.get('operating_income', 'N/A'), unit='USD', yoy=row.get('operating_income_yoy', ''))} | "
            f"{_format_quarterly_value(row.get('eps', 'N/A'), unit='USD/share', yoy=row.get('eps_yoy', ''))} | "
            f"{_append_unit_if_missing(row.get('estimated_eps', 'N/A'), 'USD/share')} | "
            f"{row.get('surprise_pct', 'N/A')} | "
            f"{_display_beat_miss(row.get('beat_miss', 'N/A'))} |"
        )
        for row in display_rows
    )
    return "\n".join(
        [
            "| 분기 | 매출 | 영업이익 | EPS | EPS 추정 | 서프라이즈 | 결과 |",
            "|------|------|----------|-----|----------|------------|------|",
            body,
        ]
    )


def _render_upcoming_events(events: list[dict[str, str]]) -> str:
    if not events:
        return "- 예정된 일정이 없습니다."
    return "\n".join(
        _render_upcoming_event_line(event)
        for event in events[:5]
    )


def _render_recent_timeline(entries: list[dict[str, Any]]) -> str:
    lines = summarize_recent_timeline(entries, limit=3)
    if not lines:
        return "- 타임라인 데이터가 없습니다."
    return "\n".join(f"- {line}" for line in lines)


def _render_trade_frame(trade_frame: dict[str, str]) -> str:
    if not trade_frame:
        return "- 트레이드 프레임 정보가 없습니다."
    lines = []
    # Trade plan table
    entry = trade_frame.get('entry_price', '')
    stop = trade_frame.get('stop_loss', '')
    t1 = trade_frame.get('target_1', '')
    t2 = trade_frame.get('target_2', '')
    rr = trade_frame.get('risk_reward_ratio', '')
    if entry or stop or t1:
        lines.extend([
            "| 항목 | 값 |",
            "|------|----|",
            f"| 진입가 | {entry or 'N/A'} |",
            f"| 손절가 | {stop or 'N/A'} |",
            f"| 목표 1 | {t1 or 'N/A'} |",
            f"| 목표 2 | {t2 or 'N/A'} |",
            f"| R:R | {rr or 'N/A'} |",
            "",
        ])
    position_note = trade_frame.get('position_size_note', '')
    if position_note:
        lines.append(f"- **포지션 사이징**: {position_note}")
    lines.extend([
        f"- **Bull**: {trade_frame.get('bull_scenario', 'N/A')}",
        f"- **Base**: {trade_frame.get('base_scenario', 'N/A')}",
        f"- **Bear**: {trade_frame.get('bear_scenario', 'N/A')}",
        f"- **무효화**: {trade_frame.get('invalidation_price', 'N/A')}",
        f"- **관찰 기간**: {trade_frame.get('watch_period', 'N/A')}",
    ])
    return "\n".join(lines)


def _render_valuation_score(valuation_score: dict[str, object]) -> str:
    if not valuation_score:
        return "- 밸류에이션 점수 정보가 없습니다."
    score = valuation_score.get('score', 'N/A')
    factors = valuation_score.get('factors', [])
    assessment = valuation_score.get('assessment', '')
    lines = [f"**점수: {score}**", ""]
    if factors and isinstance(factors, list):
        for factor in factors:
            lines.append(f"- {factor}")
        lines.append("")
    if assessment:
        lines.append(f"> {assessment}")
    return "\n".join(lines)


def _render_news_line(item, translated_summary: str | None = None) -> str:
    if translated_summary:
        return _render_collapsed_news_block(f"- {translated_summary}", item)
    return _render_original_news_line(item)


def _render_daily_news_entry(ticker: str, item, translated_summary: str | None) -> str:
    if translated_summary:
        return _render_collapsed_news_block(f"- **{ticker}**: {translated_summary}", item)
    original_line = _render_original_news_line(item)
    if original_line:
        return f"- **{ticker}**: {original_line[2:]}"
    return f"- **{ticker}**: 뉴스 원문 링크 없음"


def _render_collapsed_news_block(summary_line: str, item) -> str:
    original_line = _render_original_news_line(item)
    if not original_line:
        return summary_line
    original_line = original_line[2:]
    return "\n".join([summary_line, "  <details>", "  <summary>원문 보기</summary>", "", f"  {original_line}", "  </details>"])


def _render_original_news_line(item) -> str:
    title = str(getattr(item, "title", "") or "").strip()
    link = str(getattr(item, "link", "") or "").strip()
    source = str(getattr(item, "source", "") or "").strip()
    published_at = str(getattr(item, "published_at", "") or "").strip()
    if not title and not link:
        return ""
    source = source or "Source"
    published_suffix = f" ({published_at})" if published_at else ""
    title_text = f"[{title}]({link})" if link else title
    return f"- {title_text} - {source}{published_suffix}"


def _news_summary_for_reference(analysis: TickerAnalysis, item) -> str | None:
    try:
        index = analysis.news_references.index(item)
    except ValueError:
        return None
    if index >= len(analysis.key_news):
        return None
    summary = analysis.key_news[index].strip()
    if not summary:
        return None
    if _normalize_text(summary) == _normalize_text(item.title):
        return None
    return summary


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _news_sort_key(raw_value: str) -> datetime:
    if not raw_value:
        return datetime.min
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(raw_value).replace(tzinfo=None)
    except (TypeError, ValueError):
        return datetime.min


def _source_priority(source: str) -> int:
    priorities = _load_source_priorities()
    return priorities.get((source or "").strip().lower(), 0)


def _load_source_priorities() -> dict[str, int]:
    return load_source_priorities()


def _hide_fallback_news_without_links() -> bool:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("hide_fallback_news_without_links")
        return configured if isinstance(configured, bool) else True
    except Exception:
        return True


def _hide_fallback_news_without_links_in_ticker_notes() -> bool:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("hide_fallback_news_without_links_in_ticker_notes")
        return configured if isinstance(configured, bool) else False
    except Exception:
        return False


def _hide_empty_top_news_links_section() -> bool:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("hide_empty_top_news_links_section")
        return configured if isinstance(configured, bool) else False
    except Exception:
        return False


def _ordered_sectors(grouped: dict[str, list[tuple[tuple[datetime, int], str, str]]]) -> list[str]:
    configured_order = _load_sector_display_order()
    order_map = {sector: index for index, sector in enumerate(configured_order)}
    return sorted(grouped, key=lambda sector: (order_map.get(sector, len(order_map)), sector))


def _load_sector_display_order() -> list[str]:
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        configured = raw_config.get("sector_display_order")
        if not isinstance(configured, list):
            return _DEFAULT_SECTOR_DISPLAY_ORDER
        return [str(item) for item in configured if str(item).strip()]
    except Exception:
        return _DEFAULT_SECTOR_DISPLAY_ORDER


def _display_sector(sector: str) -> str:
    if not sector:
        return "기타"
    return _SECTOR_DISPLAY_NAMES.get(sector, sector)


def _display_snapshot_label(label: str) -> str:
    labels = {
        "Price": "가격",
        "Daily Change": "일간 등락률",
        "Market Cap": "시가총액",
        "Trailing P/E": "최근 12개월 PER",
        "EPS": "EPS (TTM)",
        "52W High": "52주 최고",
        "52W Low": "52주 최저",
        "50D SMA": "50일 이동평균",
        "200D SMA": "200일 이동평균",
        "Volume": "거래량",
        "3M Avg Volume": "3개월 평균 거래량",
        "Price/Book": "PBR",
        "Dividend Yield": "배당수익률",
        "Sector": "섹터",
        "RS vs Sector ETF": "섹터 ETF 대비 상대강도",
    }
    return labels.get(label, label)


def _render_snapshot_rows(snapshot: dict[str, str], analysis: TickerAnalysis | None = None) -> list[str]:
    rows = [
        f"| {_display_snapshot_label(key)} | {_display_snapshot_value(snapshot, key, value)} |"
        for key, value in snapshot.items()
    ]
    if analysis is None:
        return rows

    price_action = analysis.price_action or {}
    fundamentals = analysis.fundamentals or {}
    rows.extend(
        [
            f"| ATR(14) | {_render_price_action_pair(price_action.get('atr_14d', 'N/A'), price_action.get('atr_percent', 'N/A'))} |",
            f"| Relative Volume | {price_action.get('relative_volume', 'N/A')} |",
            f"| Gap | {price_action.get('gap_percent', 'N/A')} |",
            f"| vs SMA50 | {_render_directional_value(price_action.get('price_vs_sma50', 'N/A'))} |",
            f"| vs SMA200 | {_render_directional_value(price_action.get('price_vs_sma200', 'N/A'))} |",
            f"| 52주 위치 | {price_action.get('week52_position', 'N/A')} |",
            f"| RS vs SPY(30D) | {price_action.get('rs_vs_spy', 'N/A')} |",
            f"| RS vs Sector ETF | {price_action.get('rs_vs_sector_etf', 'N/A')} |",
            f"| 공매도 | {_render_short_interest(fundamentals)} |",
            f"| 애널리스트 | {_render_analyst_view(fundamentals)} |",
            f"| 내부자 보유 | {fundamentals.get('held_by_insiders', 'N/A')} |",
            f"| 기관 보유 | {fundamentals.get('held_by_institutions', 'N/A')} |",
            f"| 옵션 IV | {fundamentals.get('implied_volatility', 'N/A')} |",
        ]
    )
    return rows


def _render_positioning_data(fundamentals: dict[str, str]) -> str:
    return "\n".join(
        [
            f"- 공매도: {_render_short_interest(fundamentals)}",
            f"- 애널리스트: {_render_analyst_view(fundamentals)}",
            f"- 내부자 보유: {fundamentals.get('held_by_insiders', 'N/A')} / 기관 보유: {fundamentals.get('held_by_institutions', 'N/A')}",
            f"- 옵션 IV: {fundamentals.get('implied_volatility', 'N/A')}",
        ]
    )


def _render_options_summary(options_summary: dict[str, str]) -> str:
    if not options_summary:
        return "- ?? ???? ????."

    ordered_labels = {
        "tone": "?? ?",
        "unusual_activity": "?? ??",
        "put_call_ratio": "Put/Call Ratio",
        "oi_change": "OI ??",
        "expiry": "?? ??? ??",
        "atm_call_iv": "ATM Call IV",
        "atm_put_iv": "ATM Put IV",
        "iv_percentile_30d": "30D IV Percentile",
    }
    lines: list[str] = []
    seen: set[str] = set()

    for key in ordered_labels:
        value = str(options_summary.get(key, "")).strip()
        if not value or value == "N/A":
            continue
        lines.append(f"- {ordered_labels[key]}: {value}")
        seen.add(key)

    for key, value in options_summary.items():
        if key in seen:
            continue
        normalized = str(value).strip()
        if not normalized or normalized == "N/A":
            continue
        lines.append(f"- {key}: {normalized}")

    return "\n".join(lines) if lines else "- ?? ???? ????."



def _render_position_sizing_hint(
    analysis: TickerAnalysis,
    *,
    account_size_hint: float = 10000.0,
    risk_fraction: float = 0.01,
) -> str:
    price = _parse_number_from_text(analysis.data_snapshot.get("Price", ""))
    atr = _parse_number_from_text(analysis.price_action.get("atr_14d", ""))
    currency = _snapshot_currency(analysis.data_snapshot)
    if price is None or atr is None or atr <= 0:
        return "- ATR 기반 포지션 사이징 계산에 필요한 가격 데이터가 부족합니다."

    one_r_risk = account_size_hint * risk_fraction
    shares = int(one_r_risk // atr)
    stop_price = price - (2 * atr)
    target_price = _parse_number_from_text(analysis.fundamentals.get("analyst_target_price", ""))
    risk_reward_text = "N/A"
    if target_price is not None and target_price > price:
        risk_per_share = price - stop_price
        if risk_per_share > 0:
            reward_per_share = target_price - price
            risk_reward_text = f"{reward_per_share / risk_per_share:.2f}R"

    return "\n".join(
        [
            f"- ATR(14): {analysis.price_action.get('atr_14d', 'N/A')} -> 1% 리스크 기준 포지션: {account_size_hint:,.0f} 계좌에서 약 {shares}주",
            f"- 2ATR 스탑 기준: {price:.2f} {currency} - {2 * atr:.2f} = **{stop_price:.2f} {currency}**",
            f"- 애널리스트 목표가 기준 리스크/리워드: {risk_reward_text}",
        ]
    )


def _render_short_interest(fundamentals: dict[str, str]) -> str:
    short_float = fundamentals.get("short_float_pct", "N/A")
    short_ratio = fundamentals.get("short_ratio", "N/A")
    if short_float == "N/A" and short_ratio == "N/A":
        return "N/A"
    if short_ratio == "N/A":
        return f"{short_float} float"
    if short_float == "N/A":
        return f"커버 {short_ratio}"
    return f"{short_float} float (커버 {short_ratio})"


def _render_analyst_view(fundamentals: dict[str, str]) -> str:
    recommendation = fundamentals.get("analyst_recommendation", "N/A")
    count = fundamentals.get("analyst_count", "N/A")
    target_price = fundamentals.get("analyst_target_price", "N/A")
    if recommendation == "N/A" and count == "N/A" and target_price == "N/A":
        return "N/A"

    head = recommendation if recommendation != "N/A" else "Analyst"
    tail: list[str] = []
    if count != "N/A":
        tail.append(count)
    if target_price != "N/A":
        tail.append(f"목표 {target_price}")
    if not tail:
        return head
    return f"{head} ({', '.join(tail)})"


def _parse_number_from_text(value: str) -> float | None:
    text = str(value).strip()
    if not text or text == "N/A":
        return None
    try:
        return float(text.replace(",", "").split()[0])
    except (IndexError, ValueError):
        return None


def _display_snapshot_value(snapshot: dict[str, str], label: str, value: str) -> str:
    currency = _snapshot_currency(snapshot)
    if label == "Sector":
        return _display_sector(value)
    if label == "Market Cap":
        return _append_unit_if_missing(value, "USD")
    if label == "EPS":
        return _append_unit_if_missing(value, "USD/share")
    if label in {"52W High", "52W Low", "50D SMA", "200D SMA"}:
        return _append_unit_if_missing(value, currency)
    if label in {"Volume", "3M Avg Volume"}:
        return _append_unit_if_missing(value, "주")
    return value


def _display_news_tone(news_tone: dict[str, Any]) -> str:
    label = str(news_tone.get("label", "neutral"))
    raw_score = _coerce_float(news_tone.get("score", 0.0))
    display_score = max(0.0, min(10.0, 5.0 + raw_score))
    return f"{label} ({display_score:.1f} / 10)"


def _displayable_news_items(
    items: list[Any],
    *,
    anchor_date: date,
    hide_fallback_without_links: bool,
) -> list[Any]:
    visible_news = [
        item
        for item in items
        if not (
            hide_fallback_without_links
            and not item.link
            and (item.source or "").strip().lower() == "fallback"
        )
    ]
    if not visible_news:
        return []

    recent_news = [item for item in visible_news if _is_recent_news_item(item, anchor_date)]
    if recent_news:
        candidate_news = recent_news
    else:
        candidate_news = visible_news

    return sorted(
        candidate_news,
        key=lambda item: (_news_sort_key(item.published_at), _source_priority(item.source), item.title),
        reverse=True,
    )


def _analysis_anchor_date(analysis: TickerAnalysis) -> date:
    try:
        return date.fromisoformat(analysis.date)
    except ValueError:
        return date.today()


def _is_recent_news_item(item: Any, anchor_date: date) -> bool:
    published_at = _news_sort_key(getattr(item, "published_at", ""))
    if published_at == datetime.min:
        return True
    days_old = (anchor_date - published_at.date()).days
    if days_old < 0:
        return True
    return days_old <= _MAX_DISPLAY_NEWS_AGE_DAYS


def _format_quarterly_value(value: str, *, unit: str, yoy: str) -> str:
    base_value = _append_unit_if_missing(value, unit)
    if base_value == "N/A" or not yoy:
        return base_value
    return f"{base_value} ({yoy})"


def _snapshot_currency(snapshot: dict[str, str]) -> str:
    price_value = str(snapshot.get("Price", "")).strip()
    if not price_value:
        return "USD"
    parts = price_value.split()
    if len(parts) >= 2 and parts[-1].isalpha():
        return parts[-1]
    return "USD"


def _append_unit_if_missing(value: str, unit: str) -> str:
    normalized_value = str(value).strip()
    if not normalized_value or normalized_value == "N/A":
        return "N/A"
    if unit and normalized_value.endswith(unit):
        return normalized_value
    return f"{normalized_value} {unit}".strip()


def _render_price_action_pair(primary: str, secondary: str) -> str:
    primary_value = primary or "N/A"
    secondary_value = secondary or "N/A"
    if primary_value == "N/A" and secondary_value == "N/A":
        return "N/A"
    if secondary_value == "N/A":
        return primary_value
    return f"{primary_value} ({secondary_value})"


def _render_directional_value(value: str) -> str:
    normalized_value = (value or "").strip() or "N/A"
    if normalized_value == "N/A":
        return normalized_value
    try:
        numeric_value = float(normalized_value.replace("%", ""))
    except ValueError:
        return normalized_value
    direction = "위" if numeric_value >= 0 else "아래"
    return f"{normalized_value} ({direction})"


def _render_earnings_result_summary(setup: dict[str, str]) -> str:
    surprise = setup.get("latest_surprise_pct", "N/A")
    beat_miss = _display_beat_miss(setup.get("latest_beat_miss", "N/A"))
    if surprise == "N/A" and beat_miss == "N/A":
        return "N/A"
    if beat_miss == "N/A":
        return surprise
    if surprise == "N/A":
        return beat_miss
    return f"{surprise} / {beat_miss}"


def _render_upcoming_event_line(event: dict[str, str]) -> str:
    timing = str(event.get("timing", "")).strip()
    suffix = f"D-{event.get('days_until', 'N/A')}"
    if timing:
        suffix = f"{suffix} · {timing}"
    return f"- {event.get('label', '일정')}: {event.get('date', 'N/A')} ({suffix})"


def _render_daily_upcoming_schedule_line(
    event_date: str,
    ticker: str,
    label: str,
    days_until: str,
    timing: str,
) -> str:
    suffix = f"D-{days_until}"
    if timing:
        suffix = f"{suffix} · {timing}"
    return f"- **{ticker}** {label}: {event_date} ({suffix})"


def _display_beat_miss(value: str) -> str:
    normalized_value = (value or "").strip().lower()
    if normalized_value == "beat":
        return "✅ beat"
    if normalized_value == "miss":
        return "❌ miss"
    if normalized_value == "in-line":
        return "➖ in-line"
    return "N/A"


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _render_market_overview(overview: list[dict[str, str]]) -> str:
    if not overview:
        return "이번 실행에서 수집한 관심 종목 데이터를 기준으로 정리했습니다."
    return " | ".join(f"{entry['label']}: {entry['price']} ({entry['change']})" for entry in overview)


def _render_portfolio_risk(risk: dict[str, Any]) -> str:
    lines: list[str] = []
    risk_grade = str(risk.get("risk_grade", "")).strip()
    if risk_grade:
        lines.append(f"- **리스크 등급**: {risk_grade}")
    hhi = risk.get("hhi")
    if hhi not in (None, "", "N/A", 0):
        lines.append(f"- **HHI 집중도**: {hhi}")
    portfolio_beta = risk.get("portfolio_beta")
    if portfolio_beta not in (None, "", "N/A"):
        lines.append(f"- **포트폴리오 베타**: {portfolio_beta}")
    var_95 = risk.get("var_95")
    if var_95 not in (None, "", "N/A"):
        lines.append(f"- **1일 VaR (95%)**: {var_95}%")
    mdd_20d = risk.get("mdd_20d")
    if mdd_20d not in (None, "", "N/A"):
        lines.append(f"- **20일 최대 낙폭**: {mdd_20d}%")
    if lines:
        lines.append("")

    # Sector exposure
    sector_exp = risk.get("sector_exposure", {})
    if sector_exp:
        lines.append("**섹터 비중**:")
        for sector, weight in sector_exp.items():
            lines.append(f"- {sector}: {weight:.1f}%")
        lines.append("")

    # Top positions by weight
    positions = risk.get("positions_by_weight", [])
    if positions:
        lines.append("| 종목 | 비중 | 섹터 | ATR 리스크($) |")
        lines.append("|------|------|------|--------------|")
        for pos in positions[:10]:
            lines.append(
                f"| {pos['ticker']} | {pos['weight_pct']:.1f}% | {pos.get('sector', 'N/A')} | ${pos.get('atr_risk_usd', 0):,.0f} |"
            )
        lines.append("")

    # Concentration warning
    warning = risk.get("concentration_warning", "")
    if warning:
        lines.append(f"> **집중도 경고**: {warning}")
        lines.append("")

    # Risk metrics
    lines.append(f"- **일간 ATR 리스크 합계**: ${risk.get('total_atr_risk_usd', 0):,.0f}")
    lines.append(f"- **2×ATR 최대 손실 추정**: ${risk.get('max_drawdown_2atr_usd', 0):,.0f} ({risk.get('max_drawdown_2atr_pct', 'N/A')})")

    recommendations = risk.get("recommendations", [])
    if recommendations:
        lines.append("")
        lines.append("**리스크 완화 제안**:")
        for recommendation in recommendations:
            lines.append(f"- {recommendation}")

    return "\n".join(lines)


def _render_weekly_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    headline = str(report.get("headline", "")).strip()
    summary = str(report.get("summary", "")).strip()
    if headline:
        lines.append(f"**{headline}**")
    if summary:
        lines.extend([summary, ""])

    section_labels = [
        ("market_environment", "1. 시장 환경 요약"),
        ("top_movers", "2. 핵심 이동 종목 Top 3"),
        ("signal_review", "3. 시그널 성과 리뷰"),
        ("risk_points", "4. 리스크 포인트"),
        ("next_week_action_plan", "5. 다음 주 액션 플랜"),
        ("portfolio_suggestions", "6. 포트폴리오 제안"),
    ]
    for key, label in section_labels:
        section = report.get(key, {})
        if not isinstance(section, dict):
            continue
        lines.append(f"### {label}")
        section_summary = str(section.get("summary", "")).strip()
        if section_summary:
            lines.append(section_summary)
        details = section.get("details", [])
        if isinstance(details, list):
            for item in details:
                normalized = str(item).strip()
                if normalized:
                    lines.append(f"- {normalized}")
        items = section.get("items", [])
        if key == "top_movers" and isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "- {ticker} ({name}): {weekly_change} | 촉매 {catalyst} | decision {decision_change}".format(
                        ticker=item.get("ticker", "N/A"),
                        name=item.get("name", item.get("ticker", "N/A")),
                        weekly_change=item.get("weekly_change", "N/A"),
                        catalyst=item.get("catalyst", "N/A"),
                        decision_change=item.get("decision_change", "N/A"),
                    )
                )
        elif isinstance(items, list):
            for item in items:
                normalized = str(item).strip()
                if normalized:
                    lines.append(f"- {normalized}")
        lines.append("")

    return "\n".join(lines).strip() or "- 구조화된 주간 보고서 데이터가 없습니다."


def _render_peer_rank(peer_rank: dict[str, object]) -> str:
    if not peer_rank:
        return "- peer rank 데이터가 없습니다."

    summary = str(peer_rank.get('summary', '')).strip()
    lines: list[str] = []
    if summary:
        lines.append(f"- {summary}")

    labels = {
        'per_pctl': 'PER 퍼센타일',
        'rs_pctl': 'RS 30D 퍼센타일',
        'roe_pctl': 'ROE 퍼센타일',
        'revenue_growth_pctl': '매출 성장률 퍼센타일',
        'dividend_yield_pctl': '배당수익률 퍼센타일',
    }
    for key, label in labels.items():
        value = peer_rank.get(key, 'N/A')
        if value in ('', None, 'N/A'):
            continue
        lines.append(f"- {label}: {value}")
    return "\n".join(lines) if lines else "- peer rank 데이터가 없습니다."


def _render_macro_context(macro: dict[str, Any]) -> str:
    lines: list[str] = []
    vix = macro.get("vix", {})
    if vix.get("level") not in (None, "N/A"):
        lines.append(f"- **VIX**: {vix['level']} ({vix.get('change', 'N/A')}) — {vix.get('regime', 'N/A')}")

    events = macro.get("upcoming_macro_events", [])
    if events:
        lines.append("- **향후 매크로 일정**:")
        for event in events[:5]:
            lines.append(f"  - {event.get('date', '')} {event.get('label', '')} (D-{event.get('days_until', '?')}, 영향: {event.get('impact', 'N/A')})")
    else:
        lines.append("- 향후 14일 내 주요 매크로 이벤트 없음")

    return "\n".join(lines) if lines else "매크로 데이터가 없습니다."


def _render_weekly_macro_schedule(macro: dict[str, Any]) -> str:
    events = [
        event for event in macro.get("upcoming_macro_events", [])
        if isinstance(event, dict) and str(event.get("days_until", "999")).isdigit() and int(str(event.get("days_until"))) <= 7
    ]
    if not events:
        return "- 이번 주 예정된 핵심 매크로 이벤트가 없습니다."

    rows = [
        "| 코드 | 일정 | D-Day | 영향도 | 해석 포인트 |",
        "|------|------|-------|--------|-------------|",
    ]
    for event in events[:6]:
        rows.append(
            "| {code} | {date} | D-{days} | {impact} | {bias} |".format(
                code=event.get("event_code", event.get("type", "N/A")),
                date=event.get("date", "N/A"),
                days=event.get("days_until", "?"),
                impact=event.get("impact", "N/A"),
                bias=event.get("market_bias", event.get("label", "N/A")),
            )
        )
    return "\n".join(rows)


def _render_portfolio_macro_sensitivity(macro: dict[str, Any]) -> str:
    event_rows = [
        event for event in macro.get("portfolio_event_sensitivity", [])
        if isinstance(event, dict)
    ]
    if not event_rows:
        return "- 현재 보유 종목과 연결된 매크로 민감도 데이터가 없습니다."

    lines: list[str] = []
    for event in event_rows[:6]:
        holdings = event.get("sensitive_holdings", [])
        if not holdings:
            continue
        lines.append(f"- **{event.get('event_code', event.get('type', 'N/A'))} / {event.get('date', 'N/A')}**")
        for holding in holdings[:5]:
            lines.append(
                "  - {ticker} ({sensitivity}): {reason}".format(
                    ticker=holding.get("ticker", "N/A"),
                    sensitivity=holding.get("sensitivity", "N/A"),
                    reason=holding.get("reason", "N/A"),
                )
            )
    return "\n".join(lines) if lines else "- 현재 보유 종목과 연결된 매크로 민감도 데이터가 없습니다."


def _write_text_artifact(path: Path, content: str, *, artifact: str, ticker: str | None = None) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        _record_output_failure(f"{artifact}_write_failed", exc, artifact=artifact, ticker=ticker)
        raise
    record_pipeline_event("output", "info", "artifact_written", artifact=artifact, path=str(path), ticker=ticker or "")


def _record_output_failure(event: str, exc: Exception, *, artifact: str, ticker: str | None = None) -> None:
    payload = {
        "artifact": artifact,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    if ticker:
        payload["ticker"] = ticker
    record_pipeline_event("output", "warning", event, **payload)


def _format_decimal(value: float) -> str:
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.2f}"


def _format_money(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def _format_optional_money(value: float | None, currency: str) -> str:
    if value is None:
        return "N/A"
    return _format_money(value, currency)


def _format_optional_signed_money(value: float | None, currency: str) -> str:
    if value is None:
        return "N/A"
    return f"{value:+,.2f} {currency}"


def _format_optional_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"

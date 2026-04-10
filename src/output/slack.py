from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from urllib import error, parse, request

from src.types import PortfolioSummary, TickerAnalysis
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)


def send_daily_summary(
    analyses: list[TickerAnalysis],
    run_date: date,
    *,
    market_overview: list[dict[str, str]] | None = None,
    daily_note_path: Path | None = None,
    weekly_note_path: Path | None = None,
    portfolio_summary: PortfolioSummary | None = None,
    macro_context: dict | None = None,
) -> None:
    _send_slack_text(
        _build_summary_text(
            analyses,
            run_date,
            market_overview=market_overview or [],
            daily_note_path=daily_note_path,
            weekly_note_path=weekly_note_path,
            portfolio_summary=portfolio_summary,
        ),
        ticker_count=len(analyses),
        artifact="slack_summary",
        skipped_event="slack_skipped",
        success_event="slack_summary_sent",
        failure_event="slack_send_failed",
    )


def send_pipeline_failure_alert(run_date: date, error_message: str) -> None:
    _send_slack_text(
        f"[Stock Research] {run_date.isoformat()}\n파이프라인 실행 실패\n{error_message}",
        ticker_count=0,
        artifact="slack_failure",
        skipped_event="slack_skipped",
        success_event="slack_failure_sent",
        failure_event="slack_send_failed",
    )


def send_signal_alerts(messages: list[str]) -> None:
    if not messages:
        return
    _send_slack_text(
        "[Stock Research] 가격/조건 알림\n" + "\n".join(f"- {message}" for message in messages),
        ticker_count=0,
        artifact="slack_alerts",
        skipped_event="slack_skipped",
        success_event="slack_alerts_sent",
        failure_event="slack_send_failed",
    )


def _send_slack_text(
    text: str,
    *,
    ticker_count: int,
    artifact: str,
    skipped_event: str,
    success_event: str,
    failure_event: str,
) -> None:
    webhook_url = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()
    if not webhook_url:
        record_pipeline_event("output", "info", skipped_event, reason="webhook_not_configured", artifact=artifact)
        return
    if not _is_valid_webhook_url(webhook_url):
        logger.warning("Slack webhook URL is not a valid http(s) URL.")
        record_pipeline_event(
            "output",
            "warning",
            "slack_invalid_webhook",
            error_type="InvalidWebhookURL",
            error_message="Slack webhook URL must start with http:// or https://",
            artifact=artifact,
        )
        return

    payload = json.dumps({"text": text}).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise error.HTTPError(webhook_url, status, "Slack webhook rejected the request.", hdrs=None, fp=None)
    except error.HTTPError as exc:
        logger.warning("Slack webhook request failed with HTTP %s", exc.code)
        record_pipeline_event(
            "output",
            "warning",
            failure_event,
            error_type=type(exc).__name__,
            error_message=f"HTTP {exc.code}",
            artifact=artifact,
        )
        return
    except Exception as exc:
        logger.warning("Slack webhook request failed: %s", exc)
        record_pipeline_event(
            "output",
            "warning",
            failure_event,
            error_type=type(exc).__name__,
            error_message=str(exc),
            artifact=artifact,
        )
        return

    record_pipeline_event(
        "output",
        "info",
        success_event,
        artifact=artifact,
        ticker_count=ticker_count,
    )


def _build_summary_text(
    analyses: list[TickerAnalysis],
    run_date: date,
    *,
    market_overview: list[dict[str, str]],
    daily_note_path: Path | None,
    weekly_note_path: Path | None,
    portfolio_summary: PortfolioSummary | None,
) -> str:
    lines = [f"[Stock Research] {run_date.isoformat()}"]

    overview_line = _render_market_overview(market_overview)
    if overview_line:
        lines.append(f"시장 개요: {overview_line}")

    top_movers = sorted(
        analyses,
        key=lambda analysis: _numeric_change(analysis.data_snapshot.get("Daily Change", "N/A")),
        reverse=True,
    )[:3]
    if top_movers:
        lines.append("상위 움직임:")
        lines.extend(
            f"- {analysis.ticker}: {analysis.data_snapshot.get('Daily Change', 'N/A')} | {analysis.signal_or_takeaway}"
            for analysis in top_movers
        )

    action_items = [analysis for analysis in analyses[:3] if analysis.signal_or_takeaway]
    if action_items:
        lines.append("점검 항목:")
        lines.extend(f"- {analysis.ticker}: {analysis.signal_or_takeaway}" for analysis in action_items)

    if portfolio_summary is not None and portfolio_summary.positions:
        market_value = _format_optional_money(portfolio_summary.total_market_value)
        pnl = _format_optional_signed_money(portfolio_summary.total_unrealized_pnl)
        return_pct = _format_optional_percent(portfolio_summary.total_unrealized_return_pct)
        lines.append(f"포트폴리오: 평가금액 {market_value} | 손익 {pnl} | 수익률 {return_pct}")

    upcoming_events = []
    for analysis in analyses:
        for event in analysis.upcoming_events:
            upcoming_events.append(
                (
                    event.get("date", "9999-12-31"),
                    analysis.ticker,
                    event.get("label", "일정"),
                    event.get("days_until", "N/A"),
                )
            )
    if upcoming_events:
        lines.append("다가오는 일정:")
        for event_date, ticker, label, days_until in sorted(upcoming_events)[:3]:
            lines.append(f"- {ticker}: {label} {event_date} (D-{days_until})")

    if daily_note_path is not None:
        lines.append(f"일일 노트: {_relative_path_text(daily_note_path)}")
    if weekly_note_path is not None:
        lines.append(f"주간 노트: {_relative_path_text(weekly_note_path)}")

    return "\n".join(lines)


def _render_market_overview(market_overview: list[dict[str, str]]) -> str:
    if not market_overview:
        return ""
    return " | ".join(
        f"{entry.get('label', 'Index')}: {entry.get('price', 'N/A')} ({entry.get('change', 'N/A')})"
        for entry in market_overview
    )


def _numeric_change(raw_value: str) -> float:
    try:
        return float(str(raw_value).replace("%", "").replace("+", ""))
    except ValueError:
        return float("-inf")


def _relative_path_text(path: Path) -> str:
    try:
        return path.as_posix()
    except Exception:
        return str(path)


def _is_valid_webhook_url(value: str) -> bool:
    parsed = parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _format_optional_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.2f} USD"


def _format_optional_signed_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+,.2f} USD"


def _format_optional_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"

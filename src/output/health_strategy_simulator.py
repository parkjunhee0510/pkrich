"""Health checks for strategy simulator output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_number_or_none,
    _is_probability_or_none,
    _is_string_list,
    _load_json_object,
)


_STATUSES = {"ok", "insufficient_data"}
_MODE = "observational_long_only"
_BASIS = "final_action"
_PRESETS = ("conservative", "balanced", "aggressive")
_EXIT_REASONS = {"stop_loss", "take_profit", "avoid"}
_LLM_ALIGNMENTS = ("aligned", "conflict", "missing")
_ENTRY_CANDIDATE_STATUSES = {
    "entry_ready",
    "pending_next_open",
    "already_held",
    "insufficient_cash",
    "max_positions_reached",
    "missing_entry_price",
    "simulated_entry_closed",
}
_NEWS_STRENGTHS = {"strong", "moderate", "weak", "insufficient"}
_NEWS_TONES = {"bullish", "bearish", "neutral"}
_NEWS_DIRECTIONS = {"bull", "bear", "neutral", "unknown"}
_NEWS_LLM_ALIGNMENTS = {"aligned", "conflict", "missing", "neutral"}
_NEWS_EVIDENCE_REQUIRED = {
    "score",
    "strength",
    "tone",
    "llm_direction",
    "llm_alignment",
    "catalyst_tag",
    "catalyst_recency_score",
    "source_count",
    "has_recent_catalyst",
    "has_hard_catalyst",
    "reason_chips",
    "summary",
}
_NEWS_SHADOW_REQUIRED = {"status", "strategies"}
_NEWS_SHADOW_STRATEGY_ID = "strong_news_llm_bull"
_NEWS_SHADOW_STRATEGY_REQUIRED = {"id", "label", "criteria", "summary", "events"}
_NEWS_SHADOW_SUMMARY_REQUIRED = {
    "sample_count",
    "completed_1d_count",
    "avg_return_1d",
    "win_rate_1d",
    "completed_5d_count",
    "avg_return_5d",
    "win_rate_5d",
    "completed_20d_count",
    "avg_return_20d",
    "win_rate_20d",
}
_NEWS_SHADOW_EVENT_REQUIRED = {
    "signal_date",
    "ticker",
    "entry_date",
    "entry_price",
    "news_score",
    "news_strength",
    "news_tone",
    "llm_direction",
    "return_1d",
    "return_5d",
    "return_20d",
}
_NEWS_SHADOW_HORIZONS = ("1d", "5d", "20d")
_TODAY_QUEUE_VALUES = {"enter", "watch", "skip", "hold"}
_TODAY_TOP_ACTIONS = {"enter", "watch", "skip", "hold", "none"}
_TODAY_ACTION_QUEUE_REQUIRED = {
    "status",
    "as_of",
    "basis",
    "preset_key",
    "preset_label",
    "summary",
    "items",
    "position_alerts",
    "notes",
}
_TODAY_ACTION_QUEUE_SUMMARY_REQUIRED = {
    "enter_count",
    "watch_count",
    "skip_count",
    "hold_count",
    "top_action",
}
_TODAY_ACTION_QUEUE_ITEM_REQUIRED = {
    "queue",
    "decision_label",
    "rank",
    "ticker",
    "action_score",
    "status",
    "status_label",
    "primary_reason",
    "reason_chips",
    "blocking_reasons",
    "positive_reasons",
    "candidate_ref",
    "candidate",
}
_TODAY_ACTION_POSITION_ALERT_REQUIRED = {
    "queue",
    "decision_label",
    "ticker",
    "priority",
    "alert_score",
    "primary_reason",
    "reason_chips",
    "position_ref",
    "position",
}

_ROOT_REQUIRED = {
    "schema_version",
    "status",
    "as_of",
    "mode",
    "basis",
    "inputs",
    "assumptions",
    "presets",
    "notes",
    "news_shadow",
    "today_action_queue",
}
_PRESET_REQUIRED = {
    "label",
    "description",
    "params",
    "summary",
    "equity_curve",
    "trades",
    "open_positions",
    "entry_candidates",
    "skipped_entries",
    "llm_direction_diagnostics",
}
_PARAM_REQUIRED = {
    "initial_capital",
    "position_size_pct",
    "max_positions",
    "stop_loss_pct",
    "take_profit_pct",
    "fee_rate",
    "slippage_rate",
}
_SUMMARY_REQUIRED = {
    "initial_capital",
    "ending_equity",
    "total_return_pct",
    "realized_pnl",
    "unrealized_pnl",
    "cash",
    "cash_pct",
    "invested_value",
    "invested_pct",
    "max_drawdown_pct",
    "trade_count",
    "closed_trade_count",
    "open_position_count",
    "winning_trade_count",
    "losing_trade_count",
    "win_rate",
    "avg_closed_trade_return_pct",
    "skipped_buy_count",
}
_SUMMARY_COUNT_FIELDS = (
    "trade_count",
    "closed_trade_count",
    "open_position_count",
    "winning_trade_count",
    "losing_trade_count",
    "skipped_buy_count",
)
_SUMMARY_NUMBER_FIELDS = (
    "initial_capital",
    "ending_equity",
    "total_return_pct",
    "realized_pnl",
    "unrealized_pnl",
    "cash",
    "cash_pct",
    "invested_value",
    "invested_pct",
    "max_drawdown_pct",
    "avg_closed_trade_return_pct",
)
_EQUITY_POINT_REQUIRED = {
    "date",
    "equity",
    "cash",
    "invested_value",
    "realized_pnl",
    "unrealized_pnl",
    "drawdown_pct",
    "open_position_count",
}
_TRADE_REQUIRED = {
    "ticker",
    "entry_signal_date",
    "entry_date",
    "entry_price",
    "exit_signal_date",
    "exit_date",
    "exit_price",
    "exit_reason",
    "shares",
    "notional",
    "entry_cost",
    "exit_cost",
    "realized_pnl",
    "return_pct",
    "holding_days",
    "conviction",
    "signal_direction",
    "llm_direction",
    "llm_alignment",
}
_OPEN_POSITION_REQUIRED = {
    "ticker",
    "entry_signal_date",
    "entry_date",
    "entry_price",
    "latest_date",
    "latest_close",
    "shares",
    "notional",
    "market_value",
    "unrealized_pnl",
    "return_pct",
    "holding_days",
    "conviction",
    "signal_direction",
    "llm_direction",
    "llm_alignment",
}
_ENTRY_CANDIDATE_REQUIRED = {
    "rank",
    "ticker",
    "status",
    "status_label",
    "signal_date",
    "conviction",
    "entry_date",
    "entry_price",
    "stop_price",
    "take_profit_price",
    "position_size_pct",
    "target_notional",
    "required_cash",
    "available_cash",
    "llm_alignment",
    "signal_direction",
    "llm_direction",
    "reason",
    "news_evidence",
}
_DIAGNOSTIC_REQUIRED = {
    "trade_count",
    "closed_trade_count",
    "open_position_count",
    "realized_pnl",
    "unrealized_pnl",
    "avg_trade_return_pct",
    "win_rate",
}


def _validate_strategy_simulator_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "strategy_simulator.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    issue = _validate_root(path, payload)
    if issue is not None:
        return (issue,)
    if payload.get("status") == "insufficient_data":
        return ()

    for preset_key in _PRESETS:
        issue = _validate_preset(path, preset_key, payload["presets"].get(preset_key))
        if issue is not None:
            return (issue,)
    return ()


def _validate_root(path: Path, payload: dict) -> OutputHealthIssue | None:
    missing = _ROOT_REQUIRED.difference(payload.keys())
    if missing:
        return _issue(path, f"missing required root fields {sorted(missing)}")
    if not _is_non_negative_int(payload.get("schema_version")):
        return _issue(path, "schema_version must be a non-negative integer")
    if payload.get("status") not in _STATUSES:
        return _issue(path, "status must be ok or insufficient_data")
    if not isinstance(payload.get("as_of"), str):
        return _issue(path, "as_of must be a string")
    if payload.get("mode") != _MODE:
        return _issue(path, f"mode must be {_MODE}")
    if payload.get("basis") != _BASIS:
        return _issue(path, f"basis must be {_BASIS}")
    if not isinstance(payload.get("inputs"), dict):
        return _issue(path, "inputs must be an object")
    for field in ("signal_count", "usable_signal_count", "price_row_count"):
        if field in payload["inputs"] and not _is_non_negative_int(payload["inputs"].get(field)):
            return _issue(path, f"{field} must be a non-negative integer for inputs")
    if not isinstance(payload.get("assumptions"), dict):
        return _issue(path, "assumptions must be an object")
    if not isinstance(payload.get("presets"), dict):
        return _issue(path, "presets must be an object")
    if not _is_string_list(payload.get("notes")):
        return _issue(path, "notes must be a list of strings")

    issue = _validate_news_shadow(path, payload.get("news_shadow"))
    if issue is not None:
        return issue

    presets = payload["presets"]
    if payload.get("status") == "insufficient_data":
        if presets != {}:
            return _issue(path, "presets must be empty for insufficient_data strategy_simulator")
        return _validate_today_action_queue(path, payload.get("today_action_queue"), payload.get("status"))
    if set(presets.keys()) != set(_PRESETS):
        return _issue(path, "presets must contain conservative/balanced/aggressive for ok strategy_simulator")
    return _validate_today_action_queue(path, payload.get("today_action_queue"), payload.get("status"))


def _validate_today_action_queue(
    path: Path,
    queue: object,
    root_status: object,
) -> OutputHealthIssue | None:
    if not isinstance(queue, dict):
        return _issue(path, "today_action_queue must be an object")
    missing = _TODAY_ACTION_QUEUE_REQUIRED.difference(queue.keys())
    if missing:
        return _issue(path, f"today_action_queue missing required fields {sorted(missing)}")
    if queue.get("status") not in _STATUSES:
        return _issue(path, "today_action_queue status must be ok or insufficient_data")
    if root_status == "insufficient_data" and queue.get("status") != "insufficient_data":
        return _issue(path, "today_action_queue status must match insufficient_data root status")
    for field in ("as_of", "basis", "preset_key", "preset_label"):
        if not isinstance(queue.get(field), str):
            return _issue(path, f"{field} must be a string for today_action_queue")
    if queue.get("basis") != _BASIS:
        return _issue(path, f"basis must be {_BASIS} for today_action_queue")
    if not _is_string_list(queue.get("notes")):
        return _issue(path, "notes must be a list of strings for today_action_queue")

    issue = _validate_today_action_queue_summary(path, queue.get("summary"))
    if issue is not None:
        return issue

    items = queue.get("items")
    if not isinstance(items, list):
        return _issue(path, "items must be a list for today_action_queue")
    for index, item in enumerate(items):
        issue = _validate_today_action_queue_item(path, index, item)
        if issue is not None:
            return issue

    alerts = queue.get("position_alerts")
    if not isinstance(alerts, list):
        return _issue(path, "position_alerts must be a list for today_action_queue")
    for index, alert in enumerate(alerts):
        issue = _validate_today_action_position_alert(path, index, alert)
        if issue is not None:
            return issue

    if root_status == "insufficient_data" and (items or alerts):
        return _issue(path, "today_action_queue must be empty for insufficient_data strategy_simulator")
    return None


def _validate_today_action_queue_summary(path: Path, summary: object) -> OutputHealthIssue | None:
    if not isinstance(summary, dict):
        return _issue(path, "summary must be an object for today_action_queue")
    missing = _TODAY_ACTION_QUEUE_SUMMARY_REQUIRED.difference(summary.keys())
    if missing:
        return _issue(path, f"summary missing required fields {sorted(missing)} for today_action_queue")
    for field in ("enter_count", "watch_count", "skip_count", "hold_count"):
        if not _is_non_negative_int(summary.get(field)):
            return _issue(path, f"{field} must be a non-negative integer for today_action_queue summary")
    if summary.get("top_action") not in _TODAY_TOP_ACTIONS:
        return _issue(path, "top_action must be enter/watch/skip/hold/none for today_action_queue summary")
    return None


def _validate_today_action_queue_item(path: Path, index: int, item: object) -> OutputHealthIssue | None:
    prefix = f"today_action_queue item {index}"
    if not isinstance(item, dict):
        return _issue(path, f"{prefix} must be an object")
    missing = _TODAY_ACTION_QUEUE_ITEM_REQUIRED.difference(item.keys())
    if missing:
        return _issue(path, f"{prefix} missing required fields {sorted(missing)}")
    if item.get("queue") not in _TODAY_QUEUE_VALUES:
        return _issue(path, f"queue must be enter/watch/skip/hold for {prefix}")
    for field in ("decision_label", "ticker", "status", "status_label", "primary_reason"):
        if not _is_non_empty_string(item.get(field)):
            return _issue(path, f"{field} must be a non-empty string for {prefix}")
    if not _is_non_negative_int(item.get("rank")):
        return _issue(path, f"rank must be a non-negative integer for {prefix}")
    if not _is_score(item.get("action_score")):
        return _issue(path, f"action_score must be a number from 0 to 100 for {prefix}")
    for field in ("reason_chips", "blocking_reasons", "positive_reasons"):
        if not _is_string_list(item.get(field)):
            return _issue(path, f"{field} must be a list of strings for {prefix}")

    ref = item.get("candidate_ref")
    if (
        not isinstance(ref, dict)
        or not _is_non_empty_string(ref.get("preset"))
        or not _is_non_negative_int(ref.get("candidate_rank"))
    ):
        return _issue(path, f"candidate_ref missing minimum fields for {prefix}")
    candidate = item.get("candidate")
    if (
        not isinstance(candidate, dict)
        or not _is_non_empty_string(candidate.get("ticker"))
        or not _is_non_negative_int(candidate.get("rank"))
    ):
        return _issue(path, f"candidate missing minimum fields for {prefix}")
    return None


def _validate_today_action_position_alert(path: Path, index: int, alert: object) -> OutputHealthIssue | None:
    prefix = f"today_action_queue position_alerts item {index}"
    if not isinstance(alert, dict):
        return _issue(path, f"{prefix} must be an object")
    missing = _TODAY_ACTION_POSITION_ALERT_REQUIRED.difference(alert.keys())
    if missing:
        return _issue(path, f"{prefix} missing required fields {sorted(missing)}")
    if alert.get("queue") != "hold":
        return _issue(path, f"queue must be hold for {prefix}")
    for field in ("decision_label", "ticker", "primary_reason"):
        if not _is_non_empty_string(alert.get(field)):
            return _issue(path, f"{field} must be a non-empty string for {prefix}")
    if not _is_non_negative_int(alert.get("priority")):
        return _issue(path, f"priority must be a non-negative integer for {prefix}")
    if not _is_score(alert.get("alert_score")):
        return _issue(path, f"alert_score must be a number from 0 to 100 for {prefix}")
    if not _is_string_list(alert.get("reason_chips")):
        return _issue(path, f"reason_chips must be a list of strings for {prefix}")

    ref = alert.get("position_ref")
    if (
        not isinstance(ref, dict)
        or not _is_non_empty_string(ref.get("preset"))
        or not _is_non_empty_string(ref.get("ticker"))
    ):
        return _issue(path, f"position_ref missing minimum fields for {prefix}")
    position = alert.get("position")
    if not isinstance(position, dict) or not _is_non_empty_string(position.get("ticker")):
        return _issue(path, f"position missing minimum fields for {prefix}")
    return None


def _is_score(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return 0 <= float(value) <= 100


def _validate_news_shadow(path: Path, news_shadow: object) -> OutputHealthIssue | None:
    if not isinstance(news_shadow, dict):
        return _issue(path, "news_shadow must be an object")
    missing = _NEWS_SHADOW_REQUIRED.difference(news_shadow.keys())
    if missing:
        return _issue(path, f"news_shadow missing required fields {sorted(missing)}")
    if news_shadow.get("status") not in _STATUSES:
        return _issue(path, "status must be ok or insufficient_data for news_shadow")
    strategies = news_shadow.get("strategies")
    if not isinstance(strategies, list):
        return _issue(path, "strategies must be a list for news_shadow")
    has_canonical_strategy = False
    for index, strategy in enumerate(strategies):
        issue = _validate_news_shadow_strategy(path, index, strategy)
        if issue is not None:
            return issue
        if isinstance(strategy, dict) and strategy.get("id") == _NEWS_SHADOW_STRATEGY_ID:
            has_canonical_strategy = True
    if not has_canonical_strategy:
        return _issue(path, f"news_shadow strategies must include canonical strategy {_NEWS_SHADOW_STRATEGY_ID}")
    return None


def _validate_news_shadow_strategy(path: Path, index: int, strategy: object) -> OutputHealthIssue | None:
    prefix = f"news_shadow strategies item {index}"
    if not isinstance(strategy, dict):
        return _issue(path, f"{prefix} must be an object")
    missing = _NEWS_SHADOW_STRATEGY_REQUIRED.difference(strategy.keys())
    if missing:
        return _issue(path, f"{prefix} missing required fields {sorted(missing)}")
    for field in ("id", "label"):
        if not _is_non_empty_string(strategy.get(field)):
            return _issue(path, f"{field} must be a non-empty string for {prefix}")
    if not _is_string_list(strategy.get("criteria")):
        return _issue(path, f"criteria must be a list of strings for {prefix}")

    summary = strategy.get("summary")
    if not isinstance(summary, dict):
        return _issue(path, f"summary must be an object for {prefix}")
    missing_summary = _NEWS_SHADOW_SUMMARY_REQUIRED.difference(summary.keys())
    if missing_summary:
        return _issue(path, f"summary missing required fields {sorted(missing_summary)} for {prefix}")
    if not _is_non_negative_int(summary.get("sample_count")):
        return _issue(path, f"sample_count must be a non-negative integer for {prefix} summary")
    for horizon in _NEWS_SHADOW_HORIZONS:
        completed_field = f"completed_{horizon}_count"
        avg_return_field = f"avg_return_{horizon}"
        win_rate_field = f"win_rate_{horizon}"
        if not _is_non_negative_int(summary.get(completed_field)):
            return _issue(path, f"{completed_field} must be a non-negative integer for {prefix} summary")
        if not _is_number_or_none(summary.get(avg_return_field)):
            return _issue(path, f"{avg_return_field} must be a number or null for {prefix} summary")
        if not _is_probability_or_none(summary.get(win_rate_field)):
            return _issue(path, f"{win_rate_field} must be a number from 0 to 1 or null for {prefix} summary")

    events = strategy.get("events")
    if not isinstance(events, list):
        return _issue(path, f"events must be a list for {prefix}")
    for event_index, event in enumerate(events):
        issue = _validate_news_shadow_event(path, index, event_index, event)
        if issue is not None:
            return issue
    if strategy.get("id") == _NEWS_SHADOW_STRATEGY_ID:
        for event_index, event in enumerate(events):
            if event.get("news_strength") != "strong":
                return _issue(
                    path,
                    f"news_strength must be strong for {_NEWS_SHADOW_STRATEGY_ID} events item {event_index}",
                )
    return None


def _validate_news_shadow_event(
    path: Path,
    strategy_index: int,
    event_index: int,
    event: object,
) -> OutputHealthIssue | None:
    prefix = f"news_shadow strategies item {strategy_index} events item {event_index}"
    if not isinstance(event, dict):
        return _issue(path, f"{prefix} must be an object")
    missing = _NEWS_SHADOW_EVENT_REQUIRED.difference(event.keys())
    if missing:
        return _issue(path, f"{prefix} missing required fields {sorted(missing)}")
    for field in ("signal_date", "ticker", "entry_date", "news_strength", "news_tone", "llm_direction"):
        if not _is_non_empty_string(event.get(field)):
            return _issue(path, f"{field} must be a non-empty string for {prefix}")
    if event.get("news_strength") not in _NEWS_STRENGTHS:
        return _issue(path, f"news_strength must be strong/moderate/weak/insufficient for {prefix}")
    if event.get("news_tone") not in _NEWS_TONES:
        return _issue(path, f"news_tone must be bullish/bearish/neutral for {prefix}")
    if event.get("llm_direction") not in _NEWS_DIRECTIONS:
        return _issue(path, f"llm_direction must be bull/bear/neutral/unknown for {prefix}")
    news_score = event.get("news_score")
    if not _is_number_or_none(news_score) or news_score is None or not 0 <= news_score <= 100:
        return _issue(path, f"news_score must be a number from 0 to 100 for {prefix}")
    for field in ("entry_price", "return_1d", "return_5d", "return_20d"):
        if not _is_number_or_none(event.get(field)):
            return _issue(path, f"{field} must be a number or null for {prefix}")
    return None


def _validate_preset(path: Path, preset_key: str, preset: object) -> OutputHealthIssue | None:
    if not isinstance(preset, dict) or not _PRESET_REQUIRED.issubset(preset.keys()):
        return _issue(
            path,
            f"{preset_key} missing label/description/params/summary/equity_curve/trades/open_positions/"
            "entry_candidates/skipped_entries/llm_direction_diagnostics",
        )
    for field in ("label", "description"):
        if not isinstance(preset.get(field), str):
            return _issue(path, f"{field} must be a string for {preset_key}")

    validators = (
        _validate_params,
        _validate_summary,
        _validate_equity_curve,
        _validate_trades,
        _validate_open_positions,
        _validate_entry_candidates,
        _validate_skipped_entries,
        _validate_llm_direction_diagnostics,
    )
    for validator in validators:
        issue = validator(path, preset_key, preset)
        if issue is not None:
            return issue
    return None


def _validate_params(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    params = preset.get("params")
    if not isinstance(params, dict) or not _PARAM_REQUIRED.issubset(params.keys()):
        return _issue(path, f"params missing required fields for {preset_key}")
    for field in ("initial_capital", "stop_loss_pct", "take_profit_pct"):
        if not _is_required_number(params.get(field)):
            return _issue(path, f"{field} must be a number for {preset_key} params")
    for field in ("position_size_pct", "fee_rate", "slippage_rate"):
        if not _is_required_probability(params.get(field)):
            return _issue(path, f"{field} must be a number from 0 to 1 for {preset_key} params")
    if not _is_non_negative_int(params.get("max_positions")):
        return _issue(path, f"max_positions must be a non-negative integer for {preset_key} params")
    return None


def _validate_summary(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    summary = preset.get("summary")
    if not isinstance(summary, dict) or not _SUMMARY_REQUIRED.issubset(summary.keys()):
        return _issue(path, f"summary missing required fields for {preset_key}")
    for field in _SUMMARY_COUNT_FIELDS:
        if not _is_non_negative_int(summary.get(field)):
            return _issue(path, f"{field} must be a non-negative integer for {preset_key} summary")
    for field in _SUMMARY_NUMBER_FIELDS:
        if not _is_number_or_none(summary.get(field)):
            return _issue(path, f"{field} must be a number or null for {preset_key} summary")
    if not _is_probability_or_none(summary.get("win_rate")):
        return _issue(path, f"win_rate must be a number from 0 to 1 or null for {preset_key} summary")
    return None


def _validate_equity_curve(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    curve = preset.get("equity_curve")
    if not isinstance(curve, list):
        return _issue(path, f"equity_curve must be a list for {preset_key}")
    for index, point in enumerate(curve):
        if not isinstance(point, dict) or not _EQUITY_POINT_REQUIRED.issubset(point.keys()):
            return _issue(path, f"equity_curve item {index} missing required fields for {preset_key}")
        if not isinstance(point.get("date"), str):
            return _issue(path, f"date must be a string for {preset_key} equity_curve item {index}")
        if not _is_non_negative_int(point.get("open_position_count")):
            return _issue(
                path,
                f"open_position_count must be a non-negative integer for {preset_key} equity_curve item {index}",
            )
        for field in ("equity", "cash", "invested_value", "realized_pnl", "unrealized_pnl", "drawdown_pct"):
            if not _is_number_or_none(point.get(field)):
                return _issue(path, f"{field} must be a number or null for {preset_key} equity_curve item {index}")
    return None


def _validate_trades(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    trades = preset.get("trades")
    if not isinstance(trades, list):
        return _issue(path, f"trades must be a list for {preset_key}")
    for index, trade in enumerate(trades):
        issue = _validate_trade(path, preset_key, index, trade)
        if issue is not None:
            return issue
    return None


def _validate_trade(path: Path, preset_key: str, index: int, trade: object) -> OutputHealthIssue | None:
    if not isinstance(trade, dict) or not _TRADE_REQUIRED.issubset(trade.keys()):
        return _issue(path, f"trades item {index} missing required fields for {preset_key}")
    for field in ("ticker", "entry_signal_date", "entry_date", "exit_date"):
        if not _is_non_empty_string(trade.get(field)):
            return _issue(path, f"{field} must be a non-empty string for {preset_key} trades item {index}")
    for field in ("exit_signal_date", "signal_direction", "llm_direction"):
        if not _is_string_or_none(trade.get(field)):
            return _issue(path, f"{field} must be a string or null for {preset_key} trades item {index}")
    if trade.get("exit_reason") not in _EXIT_REASONS:
        return _issue(path, f"exit_reason must be stop_loss/take_profit/avoid for {preset_key} trades item {index}")
    if trade.get("llm_alignment") not in _LLM_ALIGNMENTS:
        return _issue(path, f"llm_alignment must be aligned/conflict/missing for {preset_key} trades item {index}")
    if not _is_non_negative_int(trade.get("holding_days")):
        return _issue(path, f"holding_days must be a non-negative integer for {preset_key} trades item {index}")
    for field in (
        "entry_price",
        "exit_price",
        "shares",
        "notional",
        "entry_cost",
        "exit_cost",
        "realized_pnl",
        "return_pct",
        "conviction",
    ):
        if not _is_number_or_none(trade.get(field)):
            return _issue(path, f"{field} must be a number or null for {preset_key} trades item {index}")
    return None


def _validate_open_positions(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    positions = preset.get("open_positions")
    if not isinstance(positions, list):
        return _issue(path, f"open_positions must be a list for {preset_key}")
    for index, position in enumerate(positions):
        issue = _validate_open_position(path, preset_key, index, position)
        if issue is not None:
            return issue
    return None


def _validate_open_position(path: Path, preset_key: str, index: int, position: object) -> OutputHealthIssue | None:
    if not isinstance(position, dict) or not _OPEN_POSITION_REQUIRED.issubset(position.keys()):
        return _issue(path, f"open_positions item {index} missing required fields for {preset_key}")
    for field in ("ticker", "entry_signal_date", "entry_date", "latest_date"):
        if not _is_non_empty_string(position.get(field)):
            return _issue(path, f"{field} must be a non-empty string for {preset_key} open_positions item {index}")
    for field in ("signal_direction", "llm_direction"):
        if not _is_string_or_none(position.get(field)):
            return _issue(path, f"{field} must be a string or null for {preset_key} open_positions item {index}")
    if position.get("llm_alignment") not in _LLM_ALIGNMENTS:
        return _issue(
            path,
            f"llm_alignment must be aligned/conflict/missing for {preset_key} open_positions item {index}",
        )
    if not _is_non_negative_int(position.get("holding_days")):
        return _issue(
            path,
            f"holding_days must be a non-negative integer for {preset_key} open_positions item {index}",
        )
    for field in (
        "entry_price",
        "latest_close",
        "shares",
        "notional",
        "market_value",
        "unrealized_pnl",
        "return_pct",
        "conviction",
    ):
        if not _is_number_or_none(position.get(field)):
            return _issue(path, f"{field} must be a number or null for {preset_key} open_positions item {index}")
    return None


def _validate_entry_candidates(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    candidates = preset.get("entry_candidates")
    if not isinstance(candidates, list):
        return _issue(path, f"entry_candidates must be a list for {preset_key}")
    for index, candidate in enumerate(candidates):
        issue = _validate_entry_candidate(path, preset_key, index, candidate)
        if issue is not None:
            return issue
    return None


def _validate_entry_candidate(path: Path, preset_key: str, index: int, candidate: object) -> OutputHealthIssue | None:
    if not isinstance(candidate, dict):
        return _issue(path, f"entry_candidates item {index} must be an object for {preset_key}")
    missing = _ENTRY_CANDIDATE_REQUIRED.difference(candidate.keys())
    if missing:
        return _issue(
            path,
            f"entry_candidates item {index} missing required fields {sorted(missing)} for {preset_key}",
        )
    if not _is_non_negative_int(candidate.get("rank")):
        return _issue(path, f"rank must be a non-negative integer for {preset_key} entry_candidates item {index}")
    for field in ("ticker", "status_label", "signal_date", "reason"):
        if not _is_non_empty_string(candidate.get(field)):
            return _issue(path, f"{field} must be a non-empty string for {preset_key} entry_candidates item {index}")
    if candidate.get("status") not in _ENTRY_CANDIDATE_STATUSES:
        return _issue(path, f"status must be a known candidate status for {preset_key} entry_candidates item {index}")
    for field in ("entry_date", "signal_direction", "llm_direction"):
        if not _is_string_or_none(candidate.get(field)):
            return _issue(path, f"{field} must be a string or null for {preset_key} entry_candidates item {index}")
    if candidate.get("llm_alignment") not in _LLM_ALIGNMENTS:
        return _issue(path, f"llm_alignment must be aligned/conflict/missing for {preset_key} entry_candidates item {index}")
    for field in (
        "conviction",
        "entry_price",
        "stop_price",
        "take_profit_price",
        "position_size_pct",
        "target_notional",
        "required_cash",
        "available_cash",
    ):
        if not _is_number_or_none(candidate.get(field)):
            return _issue(path, f"{field} must be a number or null for {preset_key} entry_candidates item {index}")
    issue = _validate_news_evidence(path, preset_key, index, candidate.get("news_evidence"))
    if issue is not None:
        return issue
    return None


def _validate_news_evidence(
    path: Path,
    preset_key: str,
    index: int,
    evidence: object,
) -> OutputHealthIssue | None:
    prefix = f"{preset_key} entry_candidates item {index} news_evidence"
    if not isinstance(evidence, dict) or not _NEWS_EVIDENCE_REQUIRED.issubset(evidence.keys()):
        return _issue(path, f"news_evidence missing required fields for {preset_key} entry_candidates item {index}")
    score = evidence.get("score")
    if not _is_number_or_none(score) or score is None or not 0 <= score <= 100:
        return _issue(path, f"score must be a number from 0 to 100 for {prefix}")
    if evidence.get("strength") not in _NEWS_STRENGTHS:
        return _issue(path, f"strength must be strong/moderate/weak/insufficient for {prefix}")
    if evidence.get("tone") not in _NEWS_TONES:
        return _issue(path, f"tone must be bullish/bearish/neutral for {prefix}")
    if evidence.get("llm_direction") not in _NEWS_DIRECTIONS:
        return _issue(path, f"llm_direction must be bull/bear/neutral/unknown for {prefix}")
    if evidence.get("llm_alignment") not in _NEWS_LLM_ALIGNMENTS:
        return _issue(path, f"llm_alignment must be aligned/conflict/missing/neutral for {prefix}")
    if not _is_string_or_none(evidence.get("catalyst_tag")):
        return _issue(path, f"catalyst_tag must be a string or null for {prefix}")
    if not _is_number_or_none(evidence.get("catalyst_recency_score")):
        return _issue(path, f"catalyst_recency_score must be a number or null for {prefix}")
    if not _is_non_negative_int(evidence.get("source_count")):
        return _issue(path, f"source_count must be a non-negative integer for {prefix}")
    for field in ("has_recent_catalyst", "has_hard_catalyst"):
        if not isinstance(evidence.get(field), bool):
            return _issue(path, f"{field} must be boolean for {prefix}")
    if not _is_string_list(evidence.get("reason_chips")):
        return _issue(path, f"reason_chips must be a list of strings for {prefix}")
    if not _is_non_empty_string(evidence.get("summary")):
        return _issue(path, f"summary must be a non-empty string for {prefix}")
    return None


def _validate_skipped_entries(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    skipped = preset.get("skipped_entries")
    required = {"total_count", "by_reason", "examples"}
    if not isinstance(skipped, dict) or not required.issubset(skipped.keys()):
        return _issue(path, f"skipped_entries missing total_count/by_reason/examples for {preset_key}")
    if not _is_non_negative_int(skipped.get("total_count")):
        return _issue(path, f"total_count must be a non-negative integer for {preset_key} skipped_entries")
    if not _is_non_negative_int_mapping(skipped.get("by_reason")):
        return _issue(path, f"by_reason must be an object with non-negative integer counts for {preset_key}")
    examples = skipped.get("examples")
    if not isinstance(examples, list):
        return _issue(path, f"examples must be a list for {preset_key} skipped_entries")
    for index, example in enumerate(examples):
        if not isinstance(example, dict):
            return _issue(path, f"skipped_entries example {index} must be an object for {preset_key}")
        for field in ("ticker", "signal_date", "reason"):
            if not _is_non_empty_string(example.get(field)):
                return _issue(path, f"{field} must be a non-empty string for {preset_key} skipped_entries example {index}")
        if not _is_string_or_none(example.get("entry_date")):
            return _issue(path, f"entry_date must be a string or null for {preset_key} skipped_entries example {index}")
    return None


def _validate_llm_direction_diagnostics(path: Path, preset_key: str, preset: dict) -> OutputHealthIssue | None:
    diagnostics = preset.get("llm_direction_diagnostics")
    if not isinstance(diagnostics, dict):
        return _issue(path, f"llm_direction_diagnostics must be an object for {preset_key}")
    if set(diagnostics.keys()) != set(_LLM_ALIGNMENTS):
        return _issue(path, f"llm_direction_diagnostics must contain aligned/conflict/missing for {preset_key}")
    for bucket in _LLM_ALIGNMENTS:
        stats = diagnostics.get(bucket)
        if not isinstance(stats, dict) or not _DIAGNOSTIC_REQUIRED.issubset(stats.keys()):
            return _issue(path, f"llm_direction_diagnostics {bucket} missing required fields for {preset_key}")
        for field in ("trade_count", "closed_trade_count", "open_position_count"):
            if not _is_non_negative_int(stats.get(field)):
                return _issue(
                    path,
                    f"{field} must be a non-negative integer for {preset_key} llm_direction_diagnostics {bucket}",
                )
        for field in ("realized_pnl", "unrealized_pnl", "avg_trade_return_pct"):
            if not _is_number_or_none(stats.get(field)):
                return _issue(
                    path,
                    f"{field} must be a number or null for {preset_key} llm_direction_diagnostics {bucket}",
                )
        if not _is_probability_or_none(stats.get("win_rate")):
            return _issue(
                path,
                f"win_rate must be a number from 0 to 1 or null for {preset_key} llm_direction_diagnostics {bucket}",
            )
    return None


def _is_required_number(value: object) -> bool:
    return value is not None and _is_number_or_none(value)


def _is_required_probability(value: object) -> bool:
    return value is not None and _is_probability_or_none(value)


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_or_none(value: object) -> bool:
    return value is None or isinstance(value, str)


def _issue(path: Path, detail: str) -> OutputHealthIssue:
    return OutputHealthIssue("invalid_strategy_simulator", str(path), detail)

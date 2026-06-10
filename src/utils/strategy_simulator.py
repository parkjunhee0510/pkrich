from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from src.output.schema import SCHEMA_VERSION
from src.utils.news_evidence import build_news_evidence


INITIAL_CAPITAL = 100000.0
FEE_PCT = 0.001
SLIPPAGE_PCT = 0.0005
TRADE_COST_PCT = FEE_PCT + SLIPPAGE_PCT
MODE = "observational_long_only"
BASIS = "final_action"
NEWS_SHADOW_ID = "strong_news_llm_bull"
NEWS_SHADOW_LABEL = "강한 뉴스 + LLM 강세"
NEWS_SHADOW_HORIZONS = (1, 5, 20)

PRESET_CONFIGS = {
    "conservative": {
        "label": "보수형",
        "description": "작게 사고 빠르게 방어",
        "params": {
            "initial_capital": INITIAL_CAPITAL,
            "position_size_pct": 0.05,
            "max_positions": 6,
            "stop_loss_pct": -0.06,
            "take_profit_pct": 0.12,
            "fee_rate": FEE_PCT,
            "slippage_rate": SLIPPAGE_PCT,
        },
    },
    "balanced": {
        "label": "균형형",
        "description": "기본 비교 기준",
        "params": {
            "initial_capital": INITIAL_CAPITAL,
            "position_size_pct": 0.10,
            "max_positions": 8,
            "stop_loss_pct": -0.08,
            "take_profit_pct": 0.18,
            "fee_rate": FEE_PCT,
            "slippage_rate": SLIPPAGE_PCT,
        },
    },
    "aggressive": {
        "label": "공격형",
        "description": "크게 사고 길게 노림",
        "params": {
            "initial_capital": INITIAL_CAPITAL,
            "position_size_pct": 0.15,
            "max_positions": 10,
            "stop_loss_pct": -0.10,
            "take_profit_pct": 0.25,
            "fee_rate": FEE_PCT,
            "slippage_rate": SLIPPAGE_PCT,
        },
    },
}

VALID_ACTIONS = {"buy", "watch", "avoid"}
VALID_DIRECTIONS = {"bull", "bear", "neutral"}
CANDIDATE_STATUS_LABELS = {
    "entry_ready": "진입 가능",
    "pending_next_open": "다음 open 대기",
    "already_held": "이미 보유",
    "insufficient_cash": "현금 부족",
    "max_positions_reached": "최대 포지션 도달",
    "missing_entry_price": "진입가 없음",
    "simulated_entry_closed": "이미 반영",
}
CANDIDATE_STATUS_REASONS = {
    "entry_ready": "진입 조건 충족",
    "pending_next_open": "다음 거래일 open 가격 필요",
    "already_held": "현재 보유 중",
    "insufficient_cash": "현금 부족",
    "max_positions_reached": "최대 포지션 도달",
    "missing_entry_price": "다음 open 가격 없음",
    "simulated_entry_closed": "이미 시뮬레이션 반영",
}
CANDIDATE_STATUS_PRIORITY = {
    "entry_ready": 0,
    "pending_next_open": 1,
    "already_held": 2,
    "insufficient_cash": 3,
    "max_positions_reached": 4,
    "missing_entry_price": 5,
    "simulated_entry_closed": 6,
}
QUEUE_PRESET_KEY = "balanced"
QUEUE_LABELS = {
    "enter": "진입 검토",
    "watch": "보류",
    "skip": "제외",
    "hold": "보유 관리",
}
QUEUE_STATUS_MAP = {
    "entry_ready": "enter",
    "pending_next_open": "watch",
    "missing_entry_price": "watch",
    "already_held": "watch",
    "insufficient_cash": "skip",
    "max_positions_reached": "skip",
    "simulated_entry_closed": "skip",
}
QUEUE_PRIORITY = {
    "enter": 0,
    "watch": 1,
    "hold": 2,
    "skip": 3,
}
QUEUE_STATUS_POINTS = {
    "entry_ready": 25.0,
    "pending_next_open": 16.0,
    "missing_entry_price": 10.0,
    "already_held": 8.0,
    "insufficient_cash": 4.0,
    "max_positions_reached": 3.0,
    "simulated_entry_closed": 0.0,
}
QUEUE_NEWS_STRENGTH_POINTS = {
    "strong": 12.0,
    "moderate": 8.0,
    "weak": 3.0,
    "insufficient": 0.0,
}
QUEUE_LLM_POINTS = {
    "aligned": 10.0,
    "neutral": 5.0,
    "missing": 3.0,
    "conflict": 0.0,
}
QUEUE_REASON_LABELS = {
    "pending_next_open": "다음 open 대기",
    "missing_entry_price": "진입가 확인 필요",
    "already_held": "이미 보유",
    "insufficient_cash": "현금 부족",
    "max_positions_reached": "포지션 한도",
    "simulated_entry_closed": "과거 반영 완료",
    "weak_news_evidence": "뉴스 근거 약함",
    "llm_conflict": "LLM 충돌",
    "risk_reward_missing": "손익 기준 대기",
    "entry_ready": "진입 조건 충족",
    "strong_news": "뉴스 강함",
    "moderate_news": "뉴스 보통",
    "bullish_news": "긍정 뉴스",
    "llm_aligned": "LLM 일치",
    "cash_available": "현금 가능",
    "risk_reward_defined": "손익 기준 확인",
}
PLACEHOLDER_CATALYST_TAGS = {
    "일반 이슈",
    "general issue",
    "no catalyst",
    "no hard catalyst",
    "no sec filing or hard catalyst detected",
}


@dataclass(frozen=True)
class Signal:
    ticker: str
    signal_date: date
    action: str
    conviction: float | None
    signal_direction: str | None
    llm_direction: str | None
    news_evidence: dict[str, Any]
    ordinal: int


@dataclass(frozen=True)
class Price:
    ticker: str
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None


def build_strategy_simulator(signal_rows: Iterable[Any], price_rows: Iterable[Any]) -> dict:
    """Build a pure, observational long-only strategy simulation payload."""
    signal_list = list(signal_rows or [])
    price_list = list(price_rows or [])
    signals = _normalize_signals(signal_list)
    prices_by_ticker = _normalize_prices(price_list)
    inputs = {
        "signal_count": len(signal_list),
        "usable_signal_count": len(signals),
        "price_row_count": len(price_list),
    }

    if not signals or not prices_by_ticker:
        return _payload("insufficient_data", "", inputs, {})

    all_dates = sorted({price.date for prices in prices_by_ticker.values() for price in prices})
    if not all_dates:
        return _payload("insufficient_data", "", inputs, {})

    presets = {
        key: _simulate_preset(config, signals, prices_by_ticker, all_dates)
        for key, config in PRESET_CONFIGS.items()
    }
    news_shadow = _build_news_shadow(signals, prices_by_ticker)
    return _payload("ok", _iso(all_dates[-1]), inputs, presets, news_shadow)


def _payload(status: str, as_of: str, inputs: dict, presets: dict, news_shadow: dict | None = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "as_of": as_of,
        "mode": MODE,
        "basis": BASIS,
        "inputs": inputs,
        "assumptions": {
            "initial_capital": INITIAL_CAPITAL,
            "entry_timing": "next_trading_day_open",
            "avoid_exit_timing": "next_trading_day_open",
            "short_selling": False,
            "leverage": False,
            "fee_rate": FEE_PCT,
            "slippage_rate": SLIPPAGE_PCT,
        },
        "presets": presets,
        "news_shadow": news_shadow or _empty_news_shadow(),
        "today_action_queue": _build_today_action_queue(status, as_of, presets),
        "notes": _notes_for_status(status),
    }


def _notes_for_status(status: str) -> list[str]:
    if status == "insufficient_data":
        return ["No usable signal or price rows are available for strategy simulation."]
    return [
        "Strategy simulator is observational and does not change official decisions.",
        "AVOID exits or avoids long exposure; it does not open short positions.",
    ]


def _simulate_preset(
    config: dict,
    signals: list[Signal],
    prices_by_ticker: dict[str, list[Price]],
    all_dates: list[date],
) -> dict:
    params = config["params"]
    entry_events, pre_skipped = _entry_events(signals, prices_by_ticker)
    avoid_events = _avoid_events(signals, prices_by_ticker)
    price_by_ticker_date = {
        ticker: {price.date: price for price in prices}
        for ticker, prices in prices_by_ticker.items()
    }

    cash = INITIAL_CAPITAL
    realized_pnl = 0.0
    positions: dict[str, dict] = {}
    trades: list[dict] = []
    skipped = list(pre_skipped)
    equity_curve: list[dict] = []
    peak_equity = INITIAL_CAPITAL
    max_drawdown_pct = 0.0

    for current_date in all_dates:
        for event in sorted(avoid_events.get(current_date, []), key=lambda item: (item.signal.signal_date, item.signal.ticker)):
            position = positions.get(event.signal.ticker)
            if position is None:
                continue
            price = price_by_ticker_date.get(event.signal.ticker, {}).get(current_date)
            if price is None or price.open is None:
                continue
            trade = _close_position(position, event.signal, current_date, price.open, "avoid")
            cash += trade["_cash_delta"]
            realized_pnl += trade["realized_pnl"]
            trades.append(_public_trade(trade))
            del positions[event.signal.ticker]

        for event in sorted(entry_events.get(current_date, []), key=_entry_priority):
            signal = event.signal
            if signal.ticker in positions:
                skipped.append(_skip(signal, "already_held", current_date))
                continue
            if len(positions) >= params["max_positions"]:
                skipped.append(_skip(signal, "max_positions_reached", current_date))
                continue

            entry_base_equity = _portfolio_equity(
                cash,
                positions,
                prices_by_ticker,
                current_date,
                include_current_close=False,
            )
            target_notional = entry_base_equity * params["position_size_pct"]
            entry_cost = target_notional * TRADE_COST_PCT
            required_cash = target_notional + entry_cost
            if cash + 1e-9 < required_cash:
                skipped.append(_skip(signal, "insufficient_cash", current_date))
                continue

            shares = target_notional / event.entry_price
            cash -= required_cash
            positions[signal.ticker] = {
                "ticker": signal.ticker,
                "entry_signal_date": _iso(signal.signal_date),
                "entry_date": _iso(current_date),
                "entry_price": event.entry_price,
                "shares": shares,
                "notional": target_notional,
                "entry_cost": entry_cost,
                "conviction": signal.conviction,
                "signal_direction": signal.signal_direction,
                "llm_direction": signal.llm_direction,
                "llm_alignment": _llm_alignment(signal.signal_direction, signal.llm_direction),
            }

        for ticker in list(positions.keys()):
            price = price_by_ticker_date.get(ticker, {}).get(current_date)
            if price is None:
                continue
            position = positions[ticker]
            stop_price = position["entry_price"] * (1.0 + params["stop_loss_pct"])
            take_price = position["entry_price"] * (1.0 + params["take_profit_pct"])
            exit_reason = None
            exit_price = None
            if price.low is not None and price.low <= stop_price:
                exit_reason = "stop_loss"
                exit_price = stop_price
            elif price.high is not None and price.high >= take_price:
                exit_reason = "take_profit"
                exit_price = take_price
            if exit_reason is None or exit_price is None:
                continue
            trade = _close_position(position, None, current_date, exit_price, exit_reason)
            cash += trade["_cash_delta"]
            realized_pnl += trade["realized_pnl"]
            trades.append(_public_trade(trade))
            del positions[ticker]

        equity, invested_value, unrealized_pnl = _equity_components(cash, positions, prices_by_ticker, current_date)
        peak_equity = max(peak_equity, equity)
        drawdown_pct = (equity / peak_equity - 1.0) if peak_equity else 0.0
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
        equity_curve.append(
            {
                "date": _iso(current_date),
                "equity": equity,
                "cash": cash,
                "invested_value": invested_value,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "drawdown_pct": _to_percentage_points(drawdown_pct),
                "open_position_count": len(positions),
            }
        )

    latest_date = all_dates[-1]
    open_positions = _open_positions(positions, prices_by_ticker, latest_date)
    ending_equity = equity_curve[-1]["equity"] if equity_curve else INITIAL_CAPITAL
    invested_value = equity_curve[-1]["invested_value"] if equity_curve else 0.0
    unrealized_pnl = equity_curve[-1]["unrealized_pnl"] if equity_curve else 0.0
    entry_candidates = _entry_candidates(
        config,
        signals,
        prices_by_ticker,
        latest_date,
        cash,
        positions,
        ending_equity,
    )

    return {
        **config,
        "summary": _summary(
            trades,
            open_positions,
            cash,
            ending_equity,
            realized_pnl,
            len(skipped),
            max_drawdown_pct,
            invested_value,
            unrealized_pnl,
        ),
        "equity_curve": [_round_row(row) for row in equity_curve],
        "trades": [_round_row(trade) for trade in trades],
        "open_positions": [_round_row(position) for position in open_positions],
        "entry_candidates": [_round_row(candidate) for candidate in entry_candidates],
        "skipped_entries": _skipped_payload(skipped),
        "llm_direction_diagnostics": _diagnostics(trades, open_positions),
    }


@dataclass(frozen=True)
class EntryEvent:
    signal: Signal
    entry_date: date
    entry_price: float


@dataclass(frozen=True)
class AvoidEvent:
    signal: Signal
    exit_date: date


def _entry_events(signals: list[Signal], prices_by_ticker: dict[str, list[Price]]) -> tuple[dict[date, list[EntryEvent]], list[dict]]:
    events: dict[date, list[EntryEvent]] = defaultdict(list)
    skipped = []
    for signal in signals:
        if signal.action != "buy":
            continue
        next_price = _next_price_after(prices_by_ticker.get(signal.ticker, []), signal.signal_date)
        if next_price is None or next_price.open is None:
            skipped.append(_skip(signal, "missing_entry_price", None))
            continue
        events[next_price.date].append(EntryEvent(signal, next_price.date, next_price.open))
    return events, skipped


def _avoid_events(signals: list[Signal], prices_by_ticker: dict[str, list[Price]]) -> dict[date, list[AvoidEvent]]:
    events: dict[date, list[AvoidEvent]] = defaultdict(list)
    for signal in signals:
        if signal.action != "avoid":
            continue
        next_price = _next_price_after(prices_by_ticker.get(signal.ticker, []), signal.signal_date)
        if next_price is None:
            continue
        events[next_price.date].append(AvoidEvent(signal, next_price.date))
    return events


def _entry_priority(event: EntryEvent) -> tuple:
    signal = event.signal
    missing_conviction = signal.conviction is None
    conviction_sort = -signal.conviction if signal.conviction is not None else 0.0
    return (missing_conviction, conviction_sort, signal.signal_date, signal.ticker)


def _close_position(
    position: dict,
    exit_signal: Signal | None,
    exit_date: date,
    exit_price: float,
    exit_reason: str,
) -> dict:
    gross_exit_value = position["shares"] * exit_price
    exit_cost = gross_exit_value * TRADE_COST_PCT
    realized_pnl = gross_exit_value - position["notional"] - position["entry_cost"] - exit_cost
    return_pct = _to_percentage_points((realized_pnl / position["notional"]) if position["notional"] else 0.0)
    trade = {
        **position,
        "exit_signal_date": _iso(exit_signal.signal_date) if exit_signal is not None else None,
        "exit_date": _iso(exit_date),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "exit_cost": exit_cost,
        "realized_pnl": realized_pnl,
        "return_pct": return_pct,
        "holding_days": (_parse_date(_iso(exit_date)) - _parse_date(position["entry_date"])).days,
        "_cash_delta": gross_exit_value - exit_cost,
    }
    return trade


def _public_trade(trade: dict) -> dict:
    return {key: value for key, value in trade.items() if not key.startswith("_")}


def _open_positions(positions: dict[str, dict], prices_by_ticker: dict[str, list[Price]], latest_date: date) -> list[dict]:
    rows = []
    for position in positions.values():
        latest_price = _latest_price_on_or_before(prices_by_ticker.get(position["ticker"], []), latest_date)
        latest_close = latest_price.close if latest_price is not None and latest_price.close is not None else position["entry_price"]
        latest_price_date = latest_price.date if latest_price is not None else _parse_date(position["entry_date"])
        market_value = position["shares"] * latest_close
        unrealized_pnl = market_value - position["notional"] - position["entry_cost"]
        rows.append(
            {
                "ticker": position["ticker"],
                "entry_signal_date": position["entry_signal_date"],
                "entry_date": position["entry_date"],
                "entry_price": position["entry_price"],
                "latest_date": _iso(latest_price_date),
                "latest_close": latest_close,
                "shares": position["shares"],
                "notional": position["notional"],
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "return_pct": _to_percentage_points((unrealized_pnl / position["notional"]) if position["notional"] else 0.0),
                "holding_days": (latest_price_date - _parse_date(position["entry_date"])).days,
                "conviction": position["conviction"],
                "signal_direction": position["signal_direction"],
                "llm_direction": position["llm_direction"],
                "llm_alignment": position["llm_alignment"],
            }
        )
    return rows


def _entry_candidates(
    config: dict,
    signals: list[Signal],
    prices_by_ticker: dict[str, list[Price]],
    latest_date: date,
    cash: float,
    positions: dict[str, dict],
    ending_equity: float,
) -> list[dict]:
    params = config["params"]
    latest_by_ticker: dict[str, Signal] = {}
    for signal in signals:
        current = latest_by_ticker.get(signal.ticker)
        if current is None or (signal.signal_date, signal.ordinal) >= (current.signal_date, current.ordinal):
            latest_by_ticker[signal.ticker] = signal

    rows = []
    for signal in latest_by_ticker.values():
        if signal.action != "buy":
            continue
        rows.append(
            _entry_candidate_row(
                signal,
                params,
                prices_by_ticker.get(signal.ticker, []),
                latest_date,
                cash,
                positions,
                ending_equity,
            )
        )

    rows.sort(key=_entry_candidate_priority)
    for index, row in enumerate(rows[:20], start=1):
        row["rank"] = index
    return rows[:20]


def _entry_candidate_row(
    signal: Signal,
    params: dict,
    prices: list[Price],
    latest_date: date,
    cash: float,
    positions: dict[str, dict],
    ending_equity: float,
) -> dict:
    position = positions.get(signal.ticker)
    if position is not None:
        entry_price = position["entry_price"]
        return _candidate_payload(
            signal,
            "already_held",
            position["entry_date"],
            entry_price,
            params,
            position["notional"],
            None,
            cash,
        )

    next_price = _next_price_after(prices, signal.signal_date)
    target_notional = ending_equity * params["position_size_pct"]

    if next_price is None:
        return _candidate_payload(signal, "pending_next_open", None, None, params, target_notional, None, cash)
    if next_price.open is None:
        return _candidate_payload(
            signal,
            "missing_entry_price",
            _iso(next_price.date),
            None,
            params,
            target_notional,
            None,
            cash,
        )
    if next_price.date <= latest_date:
        required_cash = target_notional * (1.0 + TRADE_COST_PCT)
        return _candidate_payload(
            signal,
            "simulated_entry_closed",
            _iso(next_price.date),
            next_price.open,
            params,
            target_notional,
            required_cash,
            cash,
        )
    if len(positions) >= params["max_positions"]:
        return _candidate_payload(
            signal,
            "max_positions_reached",
            _iso(next_price.date),
            next_price.open,
            params,
            target_notional,
            None,
            cash,
        )

    required_cash = target_notional * (1.0 + TRADE_COST_PCT)
    status = "entry_ready" if cash + 1e-9 >= required_cash else "insufficient_cash"
    return _candidate_payload(
        signal,
        status,
        _iso(next_price.date),
        next_price.open,
        params,
        target_notional,
        required_cash,
        cash,
    )


def _candidate_payload(
    signal: Signal,
    status: str,
    entry_date: str | None,
    entry_price: float | None,
    params: dict,
    target_notional: float | None,
    required_cash: float | None,
    available_cash: float,
) -> dict:
    stop_price = entry_price * (1.0 + params["stop_loss_pct"]) if entry_price is not None else None
    take_profit_price = entry_price * (1.0 + params["take_profit_pct"]) if entry_price is not None else None
    return {
        "rank": 0,
        "ticker": signal.ticker,
        "status": status,
        "status_label": CANDIDATE_STATUS_LABELS[status],
        "signal_date": _iso(signal.signal_date),
        "conviction": signal.conviction,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "take_profit_price": take_profit_price,
        "position_size_pct": params["position_size_pct"],
        "target_notional": target_notional,
        "required_cash": required_cash,
        "available_cash": available_cash,
        "llm_alignment": _llm_alignment(signal.signal_direction, signal.llm_direction),
        "signal_direction": signal.signal_direction,
        "llm_direction": signal.llm_direction,
        "news_evidence": signal.news_evidence,
        "reason": CANDIDATE_STATUS_REASONS[status],
    }


def _entry_candidate_priority(row: dict) -> tuple:
    conviction = row.get("conviction")
    missing_conviction = conviction is None
    conviction_sort = -conviction if conviction is not None else 0.0
    signal_date = _date_value(row.get("signal_date")) or date.min
    return (
        CANDIDATE_STATUS_PRIORITY.get(row.get("status"), 99),
        missing_conviction,
        conviction_sort,
        -signal_date.toordinal(),
        row.get("ticker") or "",
    )


def _empty_news_shadow() -> dict:
    return {
        "status": "insufficient_data",
        "strategies": [
            {
                "id": NEWS_SHADOW_ID,
                "label": NEWS_SHADOW_LABEL,
                "criteria": [
                    "news_evidence.strength == strong",
                    "llm_direction == bull",
                    "positive news tone or recent hard catalyst",
                ],
                "summary": _news_shadow_summary([]),
                "events": [],
            }
        ],
    }


def _build_news_shadow(signals: list[Signal], prices_by_ticker: dict[str, list[Price]]) -> dict:
    events = []
    for signal in signals:
        if not _is_news_shadow_candidate(signal):
            continue
        prices = prices_by_ticker.get(signal.ticker, [])
        entry_price = _next_price_after(prices, signal.signal_date)
        if entry_price is None or entry_price.open is None:
            continue
        events.append(_news_shadow_event(signal, prices, entry_price))
    return {
        "status": "ok",
        "strategies": [
            {
                "id": NEWS_SHADOW_ID,
                "label": NEWS_SHADOW_LABEL,
                "criteria": [
                    "news_evidence.strength == strong",
                    "llm_direction == bull",
                    "positive news tone or recent hard catalyst",
                ],
                "summary": _news_shadow_summary(events),
                "events": events[:20],
            }
        ],
    }


def _is_news_shadow_candidate(signal: Signal) -> bool:
    evidence = signal.news_evidence
    score = _float_value(evidence.get("score"))
    if score is None or not math.isfinite(score):
        return False
    if evidence.get("strength") != "strong":
        return False
    if evidence.get("llm_direction") != "bull":
        return False
    return evidence.get("tone") == "bullish" or (
        bool(evidence.get("has_recent_catalyst")) and bool(evidence.get("has_hard_catalyst"))
    )


def _news_shadow_event(signal: Signal, prices: list[Price], entry_price: Price) -> dict:
    returns = {}
    entry_index = None
    for index, price in enumerate(prices):
        if price is entry_price:
            entry_index = index
            break
    if entry_index is None:
        entry_index = 0

    for horizon in NEWS_SHADOW_HORIZONS:
        target_index = entry_index + horizon
        key = f"return_{horizon}d"
        if target_index < len(prices) and prices[target_index].close is not None and entry_price.open:
            returns[key] = _to_percentage_points(prices[target_index].close / entry_price.open - 1.0)
        else:
            returns[key] = None
    return {
        "signal_date": _iso(signal.signal_date),
        "ticker": signal.ticker,
        "entry_date": _iso(entry_price.date),
        "entry_price": entry_price.open,
        "news_score": signal.news_evidence.get("score"),
        "news_strength": signal.news_evidence.get("strength"),
        "news_tone": signal.news_evidence.get("tone"),
        "llm_direction": signal.news_evidence.get("llm_direction"),
        **returns,
    }


def _news_shadow_summary(events: list[dict]) -> dict:
    summary: dict[str, float | int | None] = {"sample_count": len(events)}
    for horizon in NEWS_SHADOW_HORIZONS:
        values = [
            event.get(f"return_{horizon}d")
            for event in events
            if event.get(f"return_{horizon}d") is not None
        ]
        completed_key = f"completed_{horizon}d_count"
        average_key = f"avg_return_{horizon}d"
        win_rate_key = f"win_rate_{horizon}d"
        summary[completed_key] = len(values)
        summary[average_key] = _round_number(sum(values) / len(values)) if values else None
        summary[win_rate_key] = _round_number(sum(1 for value in values if value > 0) / len(values)) if values else None
    return summary


def _empty_today_action_queue(status: str, as_of: str) -> dict:
    return {
        "status": status,
        "as_of": as_of,
        "basis": BASIS,
        "preset_key": QUEUE_PRESET_KEY,
        "preset_label": PRESET_CONFIGS[QUEUE_PRESET_KEY]["label"],
        "summary": {
            "enter_count": 0,
            "watch_count": 0,
            "skip_count": 0,
            "hold_count": 0,
            "top_action": "none",
        },
        "items": [],
        "position_alerts": [],
        "notes": _today_action_queue_notes(status),
    }


def _build_today_action_queue(status: str, as_of: str, presets: dict) -> dict:
    if status != "ok":
        return _empty_today_action_queue(status, as_of)

    preset = presets.get(QUEUE_PRESET_KEY)
    if not isinstance(preset, dict):
        return _empty_today_action_queue("insufficient_data", as_of)

    candidates = preset.get("entry_candidates") or []
    positions = preset.get("open_positions") or []
    items = [
        _today_action_queue_item(candidate)
        for candidate in candidates
        if isinstance(candidate, dict)
    ]
    items.sort(key=_today_action_queue_sort_key)

    sorted_positions = sorted(
        [position for position in positions if isinstance(position, dict)],
        key=_position_alert_sort_key,
    )
    position_alerts = [
        _today_action_position_alert(position, index + 1)
        for index, position in enumerate(sorted_positions)
    ]

    enter_count = sum(1 for item in items if item["queue"] == "enter")
    watch_count = sum(1 for item in items if item["queue"] == "watch")
    skip_count = sum(1 for item in items if item["queue"] == "skip")
    hold_count = len(position_alerts)
    summary = {
        "enter_count": enter_count,
        "watch_count": watch_count,
        "skip_count": skip_count,
        "hold_count": hold_count,
        "top_action": _top_today_action(enter_count, watch_count, hold_count, skip_count),
    }
    return {
        "status": "ok",
        "as_of": as_of,
        "basis": BASIS,
        "preset_key": QUEUE_PRESET_KEY,
        "preset_label": preset.get("label") or PRESET_CONFIGS[QUEUE_PRESET_KEY]["label"],
        "summary": summary,
        "items": items,
        "position_alerts": position_alerts,
        "notes": _today_action_queue_notes("ok"),
    }


def _today_action_queue_notes(status: str) -> list[str]:
    if status == "insufficient_data":
        return ["전략 시뮬레이터 입력이 부족해 오늘 행동 큐를 만들 수 없습니다."]
    return [
        "오늘 행동 큐는 balanced 프리셋 후보를 보기 쉽게 재정렬한 관찰용 화면입니다.",
        "공식 추천, 후보 순서, 포트폴리오 상태, 매매 실행 로직은 변경하지 않습니다.",
    ]


def _today_action_queue_item(candidate: dict) -> dict:
    queue = _queue_for_candidate_status(str(candidate.get("status") or ""))
    blocking_reasons, positive_reasons = _candidate_reason_codes(candidate, queue)
    rank = candidate.get("rank") if isinstance(candidate.get("rank"), int) else 0
    return {
        "queue": queue,
        "decision_label": QUEUE_LABELS[queue],
        "rank": rank,
        "ticker": str(candidate.get("ticker") or ""),
        "action_score": _action_score(candidate),
        "status": str(candidate.get("status") or ""),
        "status_label": str(candidate.get("status_label") or ""),
        "primary_reason": _candidate_primary_reason(candidate, queue),
        "reason_chips": _candidate_reason_chips(candidate, blocking_reasons, positive_reasons),
        "blocking_reasons": blocking_reasons,
        "positive_reasons": positive_reasons,
        "candidate_ref": {
            "preset": QUEUE_PRESET_KEY,
            "candidate_rank": rank,
        },
        "candidate": candidate,
    }


def _queue_for_candidate_status(status: str) -> str:
    return QUEUE_STATUS_MAP.get(status, "watch")


def _action_score(candidate: Mapping[str, Any]) -> float:
    evidence = candidate.get("news_evidence")
    if not isinstance(evidence, Mapping):
        evidence = {}

    conviction = _clamped_numeric(candidate.get("conviction"), 0.0, 100.0)
    news_score = _clamped_numeric(evidence.get("score"), 0.0, 100.0)
    status = str(candidate.get("status") or "")
    strength = str(evidence.get("strength") or "insufficient")
    tone = str(evidence.get("tone") or "neutral")
    llm_alignment = str(candidate.get("llm_alignment") or "missing")

    score = (
        conviction * 0.40
        + QUEUE_STATUS_POINTS.get(status, 0.0)
        + QUEUE_NEWS_STRENGTH_POINTS.get(strength, 0.0)
        + news_score * 0.05
        + (3.0 if tone == "bullish" else 0.0)
        + QUEUE_LLM_POINTS.get(llm_alignment, 0.0)
        + _risk_reward_points(candidate)
    )
    return _round_number(max(0.0, min(100.0, score)))


def _risk_reward_points(candidate: Mapping[str, Any]) -> float:
    return (
        5.0
        if all(
            _number_or_none(candidate.get(field)) is not None
            for field in ("entry_price", "stop_price", "take_profit_price")
        )
        else 0.0
    )


def _candidate_reason_codes(candidate: Mapping[str, Any], queue: str) -> tuple[list[str], list[str]]:
    evidence = candidate.get("news_evidence")
    if not isinstance(evidence, Mapping):
        evidence = {}

    status = str(candidate.get("status") or "")
    strength = str(evidence.get("strength") or "insufficient")
    tone = str(evidence.get("tone") or "neutral")
    llm_alignment = str(candidate.get("llm_alignment") or "missing")

    blocking: list[str] = []
    positive: list[str] = []
    if status in {
        "pending_next_open",
        "missing_entry_price",
        "already_held",
        "insufficient_cash",
        "max_positions_reached",
        "simulated_entry_closed",
    }:
        blocking.append(status)
    if strength in {"weak", "insufficient"}:
        blocking.append("weak_news_evidence")
    if llm_alignment == "conflict":
        blocking.append("llm_conflict")
    if _risk_reward_points(candidate) == 0.0:
        blocking.append("risk_reward_missing")

    if queue == "enter":
        positive.append("entry_ready")
    if strength == "strong":
        positive.append("strong_news")
    elif strength == "moderate":
        positive.append("moderate_news")
    if tone == "bullish":
        positive.append("bullish_news")
    if llm_alignment == "aligned":
        positive.append("llm_aligned")
    if status != "insufficient_cash":
        positive.append("cash_available")
    if _risk_reward_points(candidate) > 0.0:
        positive.append("risk_reward_defined")
    return blocking, positive


def _candidate_reason_chips(candidate: Mapping[str, Any], blocking: list[str], positive: list[str]) -> list[str]:
    chips: list[str] = []
    status_label = candidate.get("status_label")
    if isinstance(status_label, str) and status_label:
        chips.append(status_label)
    for code in positive:
        label = QUEUE_REASON_LABELS.get(code)
        if label:
            chips.append(label)
    conviction = _number_or_none(candidate.get("conviction"))
    if conviction is not None:
        chips.append(f"확신도 {_round_number(conviction)}")
    for code in blocking:
        label = QUEUE_REASON_LABELS.get(code)
        if label:
            chips.append(label)

    unique: list[str] = []
    for chip in chips:
        if chip not in unique:
            unique.append(chip)
    return unique[:5]


def _candidate_primary_reason(candidate: Mapping[str, Any], queue: str) -> str:
    status = str(candidate.get("status") or "")
    if queue == "enter":
        return "다음 거래일 open 기준 진입 조건을 확인할 수 있는 후보입니다."
    if status == "pending_next_open":
        return "다음 거래일 open 가격이 생성되면 진입 조건을 다시 확인합니다."
    if status == "missing_entry_price":
        return "진입 기준 가격이 없어 실제 진입 여부를 보류합니다."
    if status == "already_held":
        return "이미 보유 중인 티커라 신규 진입 대신 보유 상태를 확인합니다."
    if status == "insufficient_cash":
        return "목표 비중 진입에 필요한 현금이 부족해 제외합니다."
    if status == "max_positions_reached":
        return "프리셋의 최대 보유 종목 수에 도달해 제외합니다."
    if status == "simulated_entry_closed":
        return "해당 신호의 다음 open 진입은 과거 시뮬레이션에 이미 반영됐습니다."
    return "현재 후보 상태를 확인해야 합니다."


def _today_action_queue_sort_key(item: Mapping[str, Any]) -> tuple[float, float, int, str]:
    rank = item.get("rank")
    if not isinstance(rank, int):
        rank = 10_000
    return (
        float(QUEUE_PRIORITY.get(str(item.get("queue") or "watch"), 99)),
        -float(item.get("action_score") or 0.0),
        rank,
        str(item.get("ticker") or ""),
    )


def _today_action_position_alert(position: dict, priority: int) -> dict:
    ticker = str(position.get("ticker") or "")
    return {
        "queue": "hold",
        "decision_label": QUEUE_LABELS["hold"],
        "ticker": ticker,
        "priority": priority,
        "alert_score": _position_alert_score(position),
        "primary_reason": "보유 중인 포지션의 미실현 손익과 보유 기간을 확인합니다.",
        "reason_chips": _position_reason_chips(position),
        "position_ref": {
            "preset": QUEUE_PRESET_KEY,
            "ticker": ticker,
        },
        "position": position,
    }


def _position_alert_score(position: Mapping[str, Any]) -> float:
    return_pct = abs(_number_or_none(position.get("return_pct")) or 0.0)
    holding_days = _number_or_none(position.get("holding_days")) or 0.0
    llm_bonus = 5.0 if position.get("llm_alignment") == "conflict" else 0.0
    score = 50.0 + min(return_pct * 2.0, 35.0) + min(holding_days * 0.5, 10.0) + llm_bonus
    return _round_number(max(0.0, min(100.0, score)))


def _position_reason_chips(position: Mapping[str, Any]) -> list[str]:
    chips = ["보유 중"]
    return_pct = _number_or_none(position.get("return_pct"))
    if return_pct is not None:
        chips.append(f"수익률 {return_pct:+.2f}%")
    holding_days = _number_or_none(position.get("holding_days"))
    if holding_days is not None:
        chips.append(f"보유 {int(holding_days)}일")
    llm_alignment = position.get("llm_alignment")
    if isinstance(llm_alignment, str) and llm_alignment:
        chips.append(f"LLM {llm_alignment}")
    return chips[:5]


def _position_alert_sort_key(position: Mapping[str, Any]) -> tuple[float, float, str]:
    return_pct = abs(_number_or_none(position.get("return_pct")) or 0.0)
    holding_days = _number_or_none(position.get("holding_days")) or 0.0
    return (-return_pct, -holding_days, str(position.get("ticker") or ""))


def _top_today_action(enter_count: int, watch_count: int, hold_count: int, skip_count: int) -> str:
    if enter_count:
        return "enter"
    if watch_count:
        return "watch"
    if hold_count:
        return "hold"
    if skip_count:
        return "skip"
    return "none"


def _clamped_numeric(value: object, minimum: float, maximum: float) -> float:
    numeric = _number_or_none(value)
    if numeric is None:
        return 0.0
    return max(minimum, min(maximum, numeric))


def _number_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _summary(
    trades: list[dict],
    open_positions: list[dict],
    cash: float,
    ending_equity: float,
    realized_pnl: float,
    skipped_buy_count: int,
    max_drawdown_pct: float,
    invested_value: float = 0.0,
    unrealized_pnl: float = 0.0,
) -> dict:
    closed_trade_count = len(trades)
    open_position_count = len(open_positions)
    winning_trade_count = sum(1 for trade in trades if trade["realized_pnl"] > 0)
    losing_trade_count = sum(1 for trade in trades if trade["realized_pnl"] < 0)
    return_values = [trade["return_pct"] for trade in trades]
    total_trades = closed_trade_count + open_position_count
    return {
        "initial_capital": INITIAL_CAPITAL,
        "ending_equity": _round_number(ending_equity),
        "total_return_pct": _round_number(_to_percentage_points((ending_equity / INITIAL_CAPITAL - 1.0) if INITIAL_CAPITAL else 0.0)),
        "realized_pnl": _round_number(realized_pnl),
        "unrealized_pnl": _round_number(unrealized_pnl),
        "cash": _round_number(cash),
        "cash_pct": _round_number((cash / ending_equity) if ending_equity else 0.0),
        "invested_value": _round_number(invested_value),
        "invested_pct": _round_number((invested_value / ending_equity) if ending_equity else 0.0),
        "max_drawdown_pct": _round_number(_to_percentage_points(max_drawdown_pct)),
        "trade_count": total_trades,
        "closed_trade_count": closed_trade_count,
        "open_position_count": open_position_count,
        "winning_trade_count": winning_trade_count,
        "losing_trade_count": losing_trade_count,
        "win_rate": _round_number(winning_trade_count / closed_trade_count) if closed_trade_count else None,
        "avg_closed_trade_return_pct": _round_number(sum(return_values) / len(return_values)) if return_values else None,
        "skipped_buy_count": skipped_buy_count,
    }


def _diagnostics(trades: list[dict], open_positions: list[dict]) -> dict:
    payload = {}
    for bucket in ("aligned", "conflict", "missing"):
        bucket_trades = [trade for trade in trades if trade.get("llm_alignment") == bucket]
        bucket_open = [position for position in open_positions if position.get("llm_alignment") == bucket]
        returns = [trade["return_pct"] for trade in bucket_trades] + [position["return_pct"] for position in bucket_open]
        wins = sum(1 for trade in bucket_trades if trade["realized_pnl"] > 0)
        payload[bucket] = {
            "trade_count": len(bucket_trades) + len(bucket_open),
            "closed_trade_count": len(bucket_trades),
            "open_position_count": len(bucket_open),
            "realized_pnl": _round_number(sum(trade["realized_pnl"] for trade in bucket_trades)),
            "unrealized_pnl": _round_number(sum(position["unrealized_pnl"] for position in bucket_open)),
            "avg_trade_return_pct": _round_number(sum(returns) / len(returns)) if returns else None,
            "win_rate": _round_number(wins / len(bucket_trades)) if bucket_trades else None,
        }
    return payload


def _equity_components(
    cash: float,
    positions: dict[str, dict],
    prices_by_ticker: dict[str, list[Price]],
    current_date: date,
) -> tuple[float, float, float]:
    invested_value = 0.0
    unrealized_pnl = 0.0
    for position in positions.values():
        mark = _mark_price(position, prices_by_ticker.get(position["ticker"], []), current_date, include_current_close=True)
        market_value = position["shares"] * mark
        invested_value += market_value
        unrealized_pnl += market_value - position["notional"] - position["entry_cost"]
    return cash + invested_value, invested_value, unrealized_pnl


def _portfolio_equity(
    cash: float,
    positions: dict[str, dict],
    prices_by_ticker: dict[str, list[Price]],
    current_date: date,
    include_current_close: bool,
) -> float:
    equity = cash
    for position in positions.values():
        mark = _mark_price(position, prices_by_ticker.get(position["ticker"], []), current_date, include_current_close)
        equity += position["shares"] * mark
    return equity


def _mark_price(position: dict, prices: list[Price], current_date: date, include_current_close: bool) -> float:
    latest = _latest_price_on_or_before(prices, current_date, include_current_close=include_current_close)
    if latest is not None and latest.close is not None:
        return latest.close
    return position["entry_price"]


def _latest_price_on_or_before(
    prices: list[Price],
    current_date: date,
    include_current_close: bool = True,
) -> Price | None:
    latest = None
    for price in prices:
        if price.date < current_date or (include_current_close and price.date == current_date):
            if price.close is not None:
                latest = price
        elif price.date > current_date:
            break
    return latest


def _next_price_after(prices: list[Price], signal_date: date) -> Price | None:
    for price in prices:
        if price.date > signal_date:
            return price
    return None


def _skipped_payload(skipped: list[dict]) -> dict:
    by_reason: dict[str, int] = {}
    for row in skipped:
        by_reason[row["reason"]] = by_reason.get(row["reason"], 0) + 1
    examples = sorted(skipped, key=lambda row: (row["signal_date"], row["ticker"], row["reason"]))[:20]
    return {
        "total_count": len(skipped),
        "by_reason": by_reason,
        "examples": examples,
    }


def _skip(signal: Signal, reason: str, entry_date: date | None) -> dict:
    return {
        "ticker": signal.ticker,
        "signal_date": _iso(signal.signal_date),
        "entry_date": _iso(entry_date) if entry_date is not None else None,
        "reason": reason,
    }


def _llm_alignment(signal_direction: str | None, llm_direction: str | None) -> str:
    if signal_direction not in VALID_DIRECTIONS or llm_direction not in VALID_DIRECTIONS:
        return "missing"
    return "aligned" if signal_direction == llm_direction else "conflict"


def _normalize_signals(rows: Iterable[Any]) -> list[Signal]:
    signals = []
    for ordinal, row in enumerate(rows or []):
        ticker = _string_value(_get(row, "ticker") or _get(row, "symbol"))
        signal_date = _date_value(_get(row, "signal_date") or _get(row, "date"))
        action = _string_value(_get(row, BASIS) or _get(row, "action")).lower()
        if not ticker or signal_date is None or action not in VALID_ACTIONS:
            continue
        signal_direction = _direction_value(_get(row, "signal_direction"))
        llm_direction = _direction_value(_get(row, "llm_direction"))
        signals.append(
            Signal(
                ticker=ticker.upper(),
                signal_date=signal_date,
                action=action,
                conviction=_float_value(_get(row, "conviction")),
                signal_direction=signal_direction,
                llm_direction=llm_direction,
                news_evidence=_signal_news_evidence(row, signal_direction, llm_direction),
                ordinal=ordinal,
            )
        )
    return sorted(signals, key=lambda signal: (signal.signal_date, signal.ordinal, signal.ticker))


def _signal_news_evidence(
    row: Any,
    signal_direction: str | None,
    llm_direction: str | None,
) -> dict[str, Any]:
    evidence_row = _news_evidence_row(row)
    evidence = build_news_evidence(
        evidence_row,
        signal_direction=signal_direction,
        llm_direction=llm_direction,
    )
    if not _has_actual_news_support(evidence):
        return build_news_evidence({})
    return evidence


def _news_evidence_row(row: Any) -> Mapping[str, Any]:
    if isinstance(row, Mapping):
        return row
    keys = (
        "news_tone",
        "catalyst_tag",
        "catalyst_recency_score",
        "catalyst_recency",
        "factors_json",
        "news_references",
        "key_news_source_titles",
        "confidence_meta_json",
        "search_evidence_score",
        "signal_direction",
        "llm_direction",
    )
    return {key: _get(row, key) for key in keys}


def _has_actual_news_support(evidence: Mapping[str, Any]) -> bool:
    reason_chips = set(evidence.get("reason_chips") or [])
    catalyst_tag = _string_value(evidence.get("catalyst_tag"))
    is_placeholder_catalyst = _is_placeholder_catalyst_tag(catalyst_tag)
    has_non_placeholder_hard_catalyst = not is_placeholder_catalyst and (
        bool(evidence.get("has_hard_catalyst")) or "hard_catalyst" in reason_chips
    )
    return any(
        [
            evidence.get("tone") != "neutral",
            (_float_value(evidence.get("catalyst_recency_score")) or 0.0) > 0,
            (_float_value(evidence.get("source_count")) or 0.0) > 0,
            bool(evidence.get("has_recent_catalyst")),
            has_non_placeholder_hard_catalyst,
            "search_evidence" in reason_chips,
            "positive_news" in reason_chips,
            "negative_news" in reason_chips,
        ]
    )


def _is_placeholder_catalyst_tag(value: Any) -> bool:
    normalized = " ".join(_string_value(value).casefold().split())
    return normalized in PLACEHOLDER_CATALYST_TAGS


def _normalize_prices(rows: Iterable[Any]) -> dict[str, list[Price]]:
    grouped: dict[str, list[Price]] = defaultdict(list)
    seen = set()
    for row in rows or []:
        ticker = _string_value(_get(row, "ticker") or _get(row, "symbol"))
        price_date = _date_value(_get(row, "date") or _get(row, "price_date"))
        if not ticker or price_date is None:
            continue
        price = Price(
            ticker=ticker.upper(),
            date=price_date,
            open=_float_value(_get(row, "open")),
            high=_float_value(_get(row, "high")),
            low=_float_value(_get(row, "low")),
            close=_float_value(_get(row, "close")),
        )
        if price.open is None and price.high is None and price.low is None and price.close is None:
            continue
        identity = (price.ticker, price.date)
        if identity in seen:
            continue
        seen.add(identity)
        grouped[price.ticker].append(price)
    return {ticker: sorted(prices, key=lambda price: price.date) for ticker, prices in grouped.items()}


def _get(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _direction_value(value: Any) -> str | None:
    direction = _string_value(value).lower()
    return direction if direction in VALID_DIRECTIONS else None


def _float_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_value(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _parse_date(value: str) -> date:
    parsed = _date_value(value)
    if parsed is None:
        raise ValueError(f"Invalid date: {value}")
    return parsed


def _iso(value: date) -> str:
    return value.isoformat()


def _round_row(row: dict) -> dict:
    return {key: _round_number(value) if isinstance(value, float) else value for key, value in row.items()}


def _round_number(value: float) -> float:
    return round(float(value), 10)


def _to_percentage_points(value: float) -> float:
    return value * 100.0

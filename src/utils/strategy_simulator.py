from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from src.output.schema import SCHEMA_VERSION


INITIAL_CAPITAL = 100000.0
FEE_PCT = 0.001
SLIPPAGE_PCT = 0.0005
TRADE_COST_PCT = FEE_PCT + SLIPPAGE_PCT
MODE = "observational_long_only"
BASIS = "final_action"

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


@dataclass(frozen=True)
class Signal:
    ticker: str
    signal_date: date
    action: str
    conviction: float | None
    signal_direction: str | None
    llm_direction: str | None
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
    return _payload("ok", _iso(all_dates[-1]), inputs, presets)


def _payload(status: str, as_of: str, inputs: dict, presets: dict) -> dict:
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
        signals.append(
            Signal(
                ticker=ticker.upper(),
                signal_date=signal_date,
                action=action,
                conviction=_float_value(_get(row, "conviction")),
                signal_direction=_direction_value(_get(row, "signal_direction")),
                llm_direction=_direction_value(_get(row, "llm_direction")),
                ordinal=ordinal,
            )
        )
    return sorted(signals, key=lambda signal: (signal.signal_date, signal.ordinal, signal.ticker))


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

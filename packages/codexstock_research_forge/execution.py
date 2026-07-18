from __future__ import annotations

import math
from typing import Any


EXECUTION_PRESETS: dict[str, dict[str, Any]] = {
    "OPTIMISTIC": {"commission_bps": 0.0, "slippage_bps": 0.0, "sell_tax_bps": 0.0, "max_volume_participation": 1.0, "market_impact_bps_at_full_participation": 0.0, "order_delay_bars": 1, "queue_model": "NONE", "missing_queue_fill_haircut": 1.0, "queue_ahead_multiplier": 0.0},
    "REALISTIC": {"commission_bps": 1.5, "slippage_bps": 2.0, "sell_tax_bps": 18.0, "max_volume_participation": 0.1, "market_impact_bps_at_full_participation": 10.0, "order_delay_bars": 1, "queue_model": "QUEUE_AWARE_IF_AVAILABLE", "missing_queue_fill_haircut": 1.0, "queue_ahead_multiplier": 1.0},
    "CONSERVATIVE": {"commission_bps": 3.0, "slippage_bps": 8.0, "sell_tax_bps": 23.0, "max_volume_participation": 0.02, "market_impact_bps_at_full_participation": 30.0, "order_delay_bars": 2, "queue_model": "QUEUE_AWARE_IF_AVAILABLE", "missing_queue_fill_haircut": 0.25, "queue_ahead_multiplier": 1.5},
}


def execution_manifest() -> dict[str, Any]:
    return {"default_mode": "REALISTIC", "presets": {key: dict(value) for key, value in EXECUTION_PRESETS.items()}, "vi_policy": "REJECT_WHILE_ACTIVE", "queue_policy": "executed_at_price_minus_queue_ahead_then_volume_cap"}


def resolve_execution_model(model: dict[str, Any]) -> dict[str, Any]:
    mode = str(model.get("execution_mode") or "CUSTOM").upper()
    if mode != "CUSTOM" and mode not in EXECUTION_PRESETS:
        raise ValueError("execution_mode must be OPTIMISTIC, REALISTIC, CONSERVATIVE, or omitted for CUSTOM")
    defaults = EXECUTION_PRESETS.get(mode, {"commission_bps": 0.0, "slippage_bps": 0.0, "sell_tax_bps": 0.0, "max_volume_participation": 0.1, "market_impact_bps_at_full_participation": 0.0, "order_delay_bars": 1, "queue_model": "QUEUE_AWARE_IF_AVAILABLE", "missing_queue_fill_haircut": 1.0, "queue_ahead_multiplier": 1.0})
    resolved = {**defaults, **dict(model), "execution_mode": mode}
    if str(resolved.get("queue_model")) not in {"NONE", "QUEUE_AWARE_IF_AVAILABLE"}:
        raise ValueError("unsupported queue_model")
    haircut, multiplier = float(resolved["missing_queue_fill_haircut"]), float(resolved["queue_ahead_multiplier"])
    if not 0 <= haircut <= 1 or multiplier < 0:
        raise ValueError("invalid queue assumptions")
    return resolved


def compare_execution_modes(rows: list[dict[str, Any]], entry_signals: list[bool], exit_signals: list[bool], base_model: dict[str, Any] | None = None) -> dict[str, Any]:
    results = {}
    for mode in EXECUTION_PRESETS:
        model = {**dict(base_model or {}), "execution_mode": mode}
        result = simulate_long_only(rows, entry_signals, exit_signals, model)
        results[mode] = {"final_equity": result["final_equity"], "total_return_pct": result["total_return_pct"], "max_drawdown_pct": result["max_drawdown_pct"], "trade_count": result["trade_count"], "filled_quantity": sum(int(trade["quantity"]) for trade in result["trades"]), "partial_fill_count": result["partial_fill_count"], "rejected_order_count": result["rejected_order_count"], "open_position_quantity": result["open_position_quantity"], "execution_assumptions": result["execution_assumptions"]}
    return {"modes": results, "observed_return_order": sorted(results, key=lambda key: results[key]["total_return_pct"], reverse=True), "same_signals": True, "research_only": True}


def execution_capacity(row: dict[str, Any], side: str, model: dict[str, Any], volume: int | None = None) -> tuple[int, dict[str, Any]]:
    volume = max(0, int(float(row.get("volume") or 0))) if volume is None else max(0, int(volume))
    cap = int(volume * float(model["max_volume_participation"]))
    metadata = {"volume_cap": cap, "queue_model": model["queue_model"], "queue_data_available": False, "queue_ahead": None, "executed_at_price": None, "missing_queue_haircut_applied": False}
    if model["queue_model"] == "NONE":
        return cap, metadata
    prefix = "ask" if side == "BUY" else "bid"
    executed_raw = row.get(f"{prefix}_executed_quantity")
    ahead_raw = row.get(f"{prefix}_queue_ahead")
    if executed_raw is None or ahead_raw is None:
        metadata["missing_queue_haircut_applied"] = True
        return int(cap * float(model["missing_queue_fill_haircut"])), metadata
    executed, ahead = max(0, int(float(executed_raw))), max(0, int(float(ahead_raw)))
    metadata.update({"queue_data_available": True, "queue_ahead": ahead, "executed_at_price": executed})
    queue_capacity = max(0, int(executed - ahead * float(model["queue_ahead_multiplier"])))
    return min(cap, queue_capacity), metadata


def capacity_rejection_reason(volume: int, queue: dict[str, Any]) -> str:
    if volume <= 0 or int(queue.get("volume_cap") or 0) <= 0:
        return "NO_LIQUIDITY"
    if queue.get("queue_data_available"):
        return "QUEUE_NOT_REACHED"
    if queue.get("missing_queue_haircut_applied"):
        return "QUEUE_PROXY_ZERO_CAPACITY"
    return "NO_LIQUIDITY"


def simulate_long_only(
    rows: list[dict[str, Any]],
    entry_signals: list[bool],
    exit_signals: list[bool],
    model: dict[str, Any],
) -> dict[str, Any]:
    if not (len(rows) == len(entry_signals) == len(exit_signals)):
        raise ValueError("execution rows and signal lengths differ")
    if not rows:
        raise ValueError("execution requires at least one market bar")
    for index, row in enumerate(rows):
        prices = [float(row.get(key) or 0) for key in ("open", "high", "low", "close")]
        volume = float(row.get("volume") or 0)
        if not all(math.isfinite(value) and value > 0 for value in prices):
            raise ValueError(f"execution bar {index} contains an invalid price")
        if prices[1] < max(prices) or prices[2] > min(prices) or not math.isfinite(volume) or volume < 0:
            raise ValueError(f"execution bar {index} contains invalid OHLCV")
    model = resolve_execution_model(model)
    commission = _bps(model, "commission_bps")
    slippage = _bps(model, "slippage_bps")
    sell_tax = _bps(model, "sell_tax_bps")
    impact_bps = float(model.get("market_impact_bps_at_full_participation") or 0)
    participation = float(model.get("max_volume_participation") or 0.1)
    delay = int(model.get("order_delay_bars") or 1)
    if not 0 < participation <= 1:
        raise ValueError("max_volume_participation must be in (0, 1]")
    if not 1 <= delay <= 20:
        raise ValueError("order_delay_bars must be between 1 and 20")
    if impact_bps < 0:
        raise ValueError("market impact cannot be negative")
    cash = initial_cash = float(model.get("initial_cash") or 100_000_000)
    if cash <= 0:
        raise ValueError("initial_cash must be positive")
    shares = 0
    trades: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    equity_curve: list[float] = []
    for index, row in enumerate(rows):
        signal_index = index - delay
        entry = signal_index >= 0 and entry_signals[signal_index]
        exit_ = signal_index >= 0 and exit_signals[signal_index]
        # Conservative deterministic conflict policy: reduce risk, never reverse/re-enter on the same bar.
        action = "SELL" if exit_ and shares > 0 else "BUY" if entry and shares == 0 and not exit_ else "NONE"
        if action != "NONE":
            signal_date = rows[signal_index].get("date") or rows[signal_index].get("timestamp")
            event_date = row.get("date") or row.get("timestamp")
            reason = execution_block_reason(row, action)
            volume = max(0, int(float(row.get("volume") or 0)))
            max_fill, queue = execution_capacity(row, action, model, volume)
            if reason or max_fill <= 0:
                rejected.append({"date": event_date, "signal_date": signal_date, "side": action, "reason": reason or capacity_rejection_reason(volume, queue), "volume": volume, "queue": queue})
            else:
                open_price = float(row["open"])
                participation_used = min(1.0, max_fill / max(volume, 1))
                impact = impact_bps / 10_000 * participation_used
                if action == "BUY":
                    fill = open_price * (1 + slippage + impact)
                    requested = int(cash / (fill * (1 + commission)))
                    quantity = min(requested, max_fill)
                    if quantity > 0:
                        gross, fee = quantity * fill, quantity * fill * commission
                        cash -= gross + fee
                        shares += quantity
                        trades.append(_fill(row, signal_date, action, requested, quantity, fill, fee, 0, volume, participation, queue))
                else:
                    fill = open_price * (1 - slippage - impact)
                    requested = shares
                    quantity = min(requested, max_fill)
                    if quantity > 0:
                        gross, fee, tax = quantity * fill, quantity * fill * commission, quantity * fill * sell_tax
                        cash += gross - fee - tax
                        shares -= quantity
                        trades.append(_fill(row, signal_date, action, requested, quantity, fill, fee, tax, volume, participation, queue))
        equity_curve.append(cash + shares * float(row["close"]))
    peak, max_drawdown = equity_curve[0], 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1 if peak else 0)
    return {
        "initial_cash": initial_cash,
        "final_equity": round(equity_curve[-1], 2),
        "total_return_pct": round((equity_curve[-1] / initial_cash - 1) * 100, 4),
        "max_drawdown_pct": round(max_drawdown * 100, 4),
        "trade_count": len(trades),
        "trades": trades,
        "rejected_order_count": len(rejected),
        "rejected_orders": rejected,
        "partial_fill_count": sum(bool(row["partial_fill"]) for row in trades),
        "open_position_quantity": shares,
        "equity_curve": [round(value, 2) for value in equity_curve],
        "execution_assumptions": {
            "fill_policy": "IOC_PARTIAL_CANCEL_REMAINDER",
            "signal_conflict_policy": "EXIT_FIRST_NO_SAME_BAR_REENTRY",
            "order_delay_bars": delay,
            "max_volume_participation": participation,
            "market_impact_bps_at_full_participation": impact_bps,
            "execution_mode": model["execution_mode"],
            "queue_model": model["queue_model"],
            "missing_queue_fill_haircut": model["missing_queue_fill_haircut"],
            "queue_ahead_multiplier": model["queue_ahead_multiplier"],
        },
    }


def execution_block_reason(row: dict[str, Any], side: str) -> str | None:
    if row.get("suspended") or row.get("tradable") is False:
        return "TRADING_SUSPENDED"
    if row.get("vi_active") or row.get("volatility_interruption") or row.get("vi_auction"):
        return "VI_ACTIVE"
    open_price = float(row.get("open") or 0)
    if side == "BUY" and (row.get("upper_limit_locked") or (row.get("upper_limit") and open_price >= float(row["upper_limit"]))):
        return "UPPER_LIMIT_BUY_BLOCKED"
    if side == "SELL" and (row.get("lower_limit_locked") or (row.get("lower_limit") and open_price <= float(row["lower_limit"]))):
        return "LOWER_LIMIT_SELL_BLOCKED"
    return None


def _fill(row: dict[str, Any], signal_date: Any, side: str, requested: int, quantity: int, price: float, fee: float, tax: float, volume: int, limit: float, queue: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": row.get("date") or row.get("timestamp"),
        "signal_date": signal_date,
        "side": side,
        "requested_quantity": requested,
        "quantity": quantity,
        "unfilled_quantity": requested - quantity,
        "partial_fill": quantity < requested,
        "fill_ratio": round(quantity / requested, 6) if requested else 0,
        "price": price,
        "fee": fee,
        "tax": tax,
        "bar_volume": volume,
        "participation_limit": limit,
        "queue": queue,
    }


def _bps(model: dict[str, Any], key: str) -> float:
    value = float(model.get(key) or 0)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be non-negative and finite")
    return value / 10_000

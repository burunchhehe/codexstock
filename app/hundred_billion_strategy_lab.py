from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import walk_forward_ohlcv_research as wf  # noqa: E402
from backtest_trade_evidence import (  # noqa: E402
    TradeEvidenceStore,
    build_run_fingerprint,
    finalize_trade_evidence,
    load_reusable_verified_summary,
    make_run_id,
)


INITIAL_CASH = 10_000_000.0
TARGET_CASH = 10_000_000_000.0
RESULT_FILE = wf.DATA_ROOT / "hundred_billion_strategy_lab_results.json"
REPORT_FILE = wf.DATA_ROOT / "obsidian-vault" / "AI-Trader" / "CapitalChallenge" / "hundred-billion-strategy-lab-20260706.md"
TRADE_EVIDENCE_DB = wf.TRADE_EVIDENCE_DB


def _round(value: object, digits: int = 2) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return round(number, digits)
    except Exception:
        pass
    return 0.0


def _sma(values: list[float], days: int) -> float | None:
    if len(values) < days:
        return None
    return sum(values[-days:]) / days


def _rsi(values: list[float], days: int = 14) -> float:
    if len(values) < days + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    tail = values[-days - 1 :]
    for previous, current in zip(tail, tail[1:]):
        delta = current - previous
        if delta >= 0:
            gains += delta
        else:
            losses += abs(delta)
    if losses <= 0:
        return 100.0 if gains > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + gains / losses))


def _pct(values: list[float], days: int) -> float:
    if len(values) <= days or values[-1 - days] <= 0:
        return 0.0
    return (values[-1] / values[-1 - days] - 1.0) * 100.0


def _volume_ratio(values: list[int], days: int = 20) -> float:
    if len(values) < days + 1:
        return 1.0
    base = sum(max(1, int(value)) for value in values[-days - 1 : -1]) / days
    return max(0.0, float(values[-1]) / max(1.0, base))


def _score_candidate(family: str, history: dict[str, list[float] | list[int]], config: dict[str, object]) -> dict[str, object] | None:
    closes = history["close"]  # type: ignore[assignment]
    highs = history["high"]  # type: ignore[assignment]
    lows = history["low"]  # type: ignore[assignment]
    volumes = history["volume"]  # type: ignore[assignment]
    if len(closes) < int(config.get("min_history", 220)):
        return None
    close = float(closes[-1])
    if close <= 0:
        return None

    p5 = _pct(closes, 5)
    p20 = _pct(closes, 20)
    p60 = _pct(closes, 60)
    p120 = _pct(closes, 120)
    p240 = _pct(closes, 240)
    rsi14 = _rsi(closes, 14)
    vol_ratio = _volume_ratio(volumes, 20)  # type: ignore[arg-type]
    high20 = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    high60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    high55 = max(highs[-55:]) if len(highs) >= 55 else max(highs)
    high120 = max(highs[-120:]) if len(highs) >= 120 else max(highs)
    high240 = max(highs[-240:]) if len(highs) >= 240 else max(highs)
    low20 = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    low55 = min(lows[-55:]) if len(lows) >= 55 else min(lows)
    ma20 = _sma(closes, 20) or close
    ma50 = _sma(closes, 50) or close
    ma150 = _sma(closes, 150) or close
    ma200 = _sma(closes, 200) or close
    high_dist_60 = (close / high60 - 1.0) * 100.0 if high60 else -999.0
    high_dist_120 = (close / high120 - 1.0) * 100.0 if high120 else -999.0
    high_dist_240 = (close / high240 - 1.0) * 100.0 if high240 else -999.0
    box_height20 = (high20 / max(0.0001, low20) - 1.0) * 100.0
    box_height55 = (high55 / max(0.0001, low55) - 1.0) * 100.0
    trend_stack = close > ma50 > ma150 > ma200

    metrics = {
        "p5": round(p5, 2),
        "p20": round(p20, 2),
        "p60": round(p60, 2),
        "p120": round(p120, 2),
        "p240": round(p240, 2),
        "rsi14": round(rsi14, 2),
        "volume_ratio": round(vol_ratio, 2),
        "high_dist_60": round(high_dist_60, 2),
        "high_dist_120": round(high_dist_120, 2),
        "high_dist_240": round(high_dist_240, 2),
        "box_height20": round(box_height20, 2),
        "box_height55": round(box_height55, 2),
    }

    if family == "momentum_blend":
        fast = _sma(closes, int(config.get("fast", 5))) or 0.0
        slow = _sma(closes, int(config.get("slow", 20))) or 1.0
        if fast <= slow:
            return None
        if p20 < float(config.get("min_p20", 4.0)) or p60 < float(config.get("min_p60", 12.0)):
            return None
        if high_dist_60 < float(config.get("min_high_dist", -7.0)):
            return None
        if vol_ratio < float(config.get("min_vol_ratio", 0.55)):
            return None
        score = (
            p5 * float(config.get("w5", 1.2))
            + p20 * float(config.get("w20", 1.1))
            + p60 * float(config.get("w60", 0.65))
            + p120 * float(config.get("w120", 0.35))
            + vol_ratio * float(config.get("wvol", 4.0))
            + high_dist_60 * float(config.get("whigh", 0.4))
        )
    elif family == "turtle_55":
        lookback_high = max(highs[-56:-1]) if len(highs) >= 56 else high55
        if close < lookback_high or p60 < 10 or close < ma50:
            return None
        score = p20 * 0.8 + p60 * 1.0 + p120 * 0.45 + vol_ratio * 8 + high_dist_240 * 0.25
    elif family == "darvas_box":
        if box_height20 > float(config.get("max_box_height", 28.0)) or close < high20 * 0.985:
            return None
        if p60 < 15 or p120 < 25 or vol_ratio < float(config.get("min_vol_ratio", 0.8)):
            return None
        score = p20 * 1.0 + p60 * 0.8 + p120 * 0.4 - box_height20 * 0.7 + vol_ratio * 12
    elif family == "minervini_proxy":
        if not trend_stack or high_dist_240 < -25 or p120 < 25 or p240 < 30:
            return None
        if close < ma20 or rsi14 < 48:
            return None
        score = p60 * 0.9 + p120 * 0.8 + p240 * 0.35 + vol_ratio * 5 + high_dist_240 * 0.2
    elif family == "canslim_proxy":
        if close < ma50 or p60 < 25 or p120 < 40 or high_dist_120 < -8 or vol_ratio < 1.2:
            return None
        score = p20 * 1.2 + p60 * 1.1 + p120 * 0.45 + vol_ratio * 15 + rsi14 * 0.15
    elif family == "leader_pullback":
        if p120 < 45 or p240 < 45 or close < ma50 or close > high55 * 0.96:
            return None
        if not (38 <= rsi14 <= 62) or close < ma20 * 0.92:
            return None
        score = p120 * 0.9 + p240 * 0.35 - abs(rsi14 - 48) * 1.2 + vol_ratio * 4 + high_dist_240 * 0.2
    elif family == "super_leader":
        if p20 < 18 or p60 < 45 or p120 < 70 or high_dist_120 < -3:
            return None
        score = p5 * 0.6 + p20 * 1.4 + p60 * 1.1 + p120 * 0.45 + vol_ratio * 11
    elif family == "crash_rebound":
        if p120 < 20 or close < ma200 or rsi14 > 42:
            return None
        drawdown_from_120 = high_dist_120
        if drawdown_from_120 > -12 or close < min(lows[-5:]) * 1.05:
            return None
        score = p120 * 0.45 + p240 * 0.2 + (50 - rsi14) * 2.5 + vol_ratio * 7 + drawdown_from_120 * -0.8
    else:
        return None

    return {"score": score, "metrics": metrics}


def _run_strategy(
    data: dict[str, dict[str, object]],
    config: dict[str, object],
    evidence_store: TradeEvidenceStore | None = None,
) -> dict[str, object]:
    all_dates = sorted({str(row["date"]) for payload in data.values() for row in payload["rows"]})
    histories: dict[str, dict[str, list[float] | list[int]]] = {
        symbol: {"open": [], "high": [], "low": [], "close": [], "volume": []} for symbol in data
    }
    last_rows: dict[str, dict[str, object]] = {}
    cash = INITIAL_CASH
    positions: dict[str, dict[str, object]] = {}
    trades: list[dict[str, object]] = []
    discovery_log: list[dict[str, object]] = []
    equity_curve: list[float] = []
    peak = INITIAL_CASH
    max_drawdown = 0.0

    family = str(config["family"])
    rebalance_days = max(1, int(config.get("rebalance_days", 5)))
    max_positions = max(1, int(config.get("max_positions", 2)))
    position_pct = max(1.0, float(config.get("position_pct", 100.0 / max_positions)))
    stop_pct = max(1.0, float(config.get("stop_pct", 12.0)))
    take_pct = max(0.0, float(config.get("take_pct", 0.0)))
    trail_pct = max(0.0, float(config.get("trail_pct", stop_pct * 1.8)))
    hold_days = max(1, int(config.get("hold_days", 120)))
    trade_cost_pct = max(0.0, float(config.get("trade_cost_pct", 0.18)))
    liquidity_pct = max(0.001, float(config.get("liquidity_pct", 1.0)))
    max_gap_up_pct = float(config.get("max_gap_up_pct", 15.0))
    min_score = float(config.get("min_score", -9999.0))
    pyramid = bool(config.get("pyramid", False))
    pyramid_gain_pct = float(config.get("pyramid_gain_pct", 18.0))
    max_adds = int(config.get("max_adds", 2))

    def equity() -> float:
        value = cash
        for symbol, position in positions.items():
            row = last_rows.get(symbol) or {}
            price = float(row.get("close", position.get("avg_price", 0)) or 0)
            value += float(position["quantity"]) * price
        return value

    for index, date_key in enumerate(all_dates):
        today_rows: dict[str, dict[str, object]] = {}
        for symbol, payload in data.items():
            row = payload["by_date"].get(date_key)
            if isinstance(row, dict):
                today_rows[symbol] = row

        for symbol in list(positions):
            row = today_rows.get(symbol)
            if not row:
                continue
            position = positions[symbol]
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            avg_price = float(position["avg_price"])
            prior_peak_price = float(position.get("peak_price", avg_price))
            stop_price = avg_price * (1 - stop_pct / 100.0)
            take_price = avg_price * (1 + take_pct / 100.0) if take_pct > 0 else math.inf
            trail_price = prior_peak_price * (1 - trail_pct / 100.0) if trail_pct > 0 else 0.0
            position["held_bars"] = int(position.get("held_bars", 0) or 0) + 1
            days_held = int(position["held_bars"])
            exit_price = 0.0
            reason = ""
            if low <= stop_price:
                exit_price = stop_price
                reason = f"stop {stop_pct:.1f}%"
            elif high >= take_price:
                exit_price = take_price
                reason = f"take {take_pct:.1f}%"
            elif trail_price and prior_peak_price > avg_price and low <= trail_price:
                exit_price = trail_price
                reason = f"trail {trail_pct:.1f}%"
            elif days_held >= hold_days:
                exit_price = close
                reason = f"hold {days_held}d close"
            if exit_price > 0:
                quantity = float(position["quantity"])
                effective_exit = exit_price * (1 - trade_cost_pct / 100.0)
                cash += quantity * effective_exit
                pnl_pct = (effective_exit / avg_price - 1.0) * 100.0
                trades.append(
                    {
                        "date": date_key,
                        "symbol": symbol,
                        "name": data[symbol]["name"],
                        "side": "SELL",
                        "entry_date": position.get("entry_date"),
                        "entry_price": round(avg_price, 4),
                        "entry_reason": position.get("entry_reason", ""),
                        "decision_data_as_of": str((last_rows.get(symbol) or {}).get("date") or date_key),
                        "execution_at": date_key,
                        "signal_lag_bars": 1,
                        "execution_price_basis": "precommitted_protective_or_scheduled_close",
                        "gross_price": round(exit_price, 8),
                        "price": round(effective_exit, 8),
                        "exit_price": round(effective_exit, 8),
                        "quantity": int(quantity),
                        "pnl_pct": round(pnl_pct, 2),
                        "return_pct": round(pnl_pct, 2),
                        "reason": reason,
                        "exit_reason": reason,
                        "cost_pct": trade_cost_pct,
                        "cost_amount": round(quantity * (exit_price - effective_exit), 8),
                    }
                )
                del positions[symbol]
            else:
                position["peak_price"] = max(prior_peak_price, high)

        current_equity = equity()

        if index % rebalance_days == 0:
            candidates: list[dict[str, object]] = []
            for symbol, history in histories.items():
                if symbol not in today_rows:
                    continue
                if symbol in positions and not pyramid:
                    continue
                score_payload = _score_candidate(family, history, config)
                if not score_payload or float(score_payload["score"]) < min_score:
                    continue
                today_open = float(today_rows[symbol]["open"])
                previous_close_values = history["close"]
                previous_close = float(previous_close_values[-1]) if previous_close_values else 0.0
                if previous_close <= 0 or today_open <= 0:
                    continue
                gap_up_pct = (today_open / previous_close - 1.0) * 100.0
                if gap_up_pct > max_gap_up_pct:
                    continue
                liquidity = wf._past_liquidity_capacity(history["volume"], liquidity_pct)
                max_liquidity_quantity = int(liquidity["quantity"])
                if max_liquidity_quantity <= 0:
                    continue
                candidates.append(
                    {
                        "symbol": symbol,
                        "score": float(score_payload["score"]),
                        "metrics": score_payload["metrics"],
                        "entry_price": today_open * (1 + trade_cost_pct / 100.0),
                        "gross_entry_price": today_open,
                        "max_liquidity_quantity": max_liquidity_quantity,
                        "decision_data_as_of": str((last_rows.get(symbol) or {}).get("date") or date_key),
                        "liquidity": liquidity,
                    }
                )
            candidates.sort(key=lambda item: float(item["score"]), reverse=True)
            if candidates and len(discovery_log) < 260:
                discovery_log.append(
                    {
                        "date": date_key,
                        "top": [
                            {
                                "symbol": str(item["symbol"]),
                                "name": str(data[str(item["symbol"])]["name"]),
                                "score": round(float(item["score"]), 2),
                                **dict(item["metrics"]),
                            }
                            for item in candidates[:5]
                        ],
                    }
                )

            slots = max_positions - len(positions)
            for candidate in candidates:
                symbol = str(candidate["symbol"])
                existing = positions.get(symbol)
                if existing:
                    if not pyramid or int(existing.get("adds", 0) or 0) >= max_adds:
                        continue
                    avg_price = float(existing["avg_price"])
                    last_price = float((last_rows.get(symbol) or {}).get("close", avg_price) or avg_price)
                    if (last_price / avg_price - 1.0) * 100.0 < pyramid_gain_pct:
                        continue
                elif slots <= 0:
                    continue

                entry_price = float(candidate["entry_price"])
                gross_entry_price = float(candidate["gross_entry_price"])
                target_notional = current_equity * position_pct / 100.0
                notional = min(cash, target_notional)
                quantity = min(math.floor(notional / entry_price), int(candidate.get("max_liquidity_quantity", 0) or 0))
                if quantity <= 0:
                    continue
                cash -= quantity * entry_price
                if existing:
                    old_quantity = float(existing["quantity"])
                    new_quantity = old_quantity + quantity
                    existing["avg_price"] = ((old_quantity * float(existing["avg_price"])) + quantity * entry_price) / new_quantity
                    existing["quantity"] = new_quantity
                    existing["adds"] = int(existing.get("adds", 0) or 0) + 1
                    reason_prefix = "PYRAMID"
                else:
                    positions[symbol] = {
                        "quantity": quantity,
                        "avg_price": entry_price,
                        "entry_index": index,
                        "entry_date": date_key,
                        "entry_reason": f"BUY {family} {candidate['metrics']}",
                        "held_bars": 0,
                        "peak_price": entry_price,
                        "score": round(float(candidate["score"]), 2),
                        "adds": 0,
                    }
                    slots -= 1
                    reason_prefix = "BUY"
                trades.append(
                    {
                        "date": date_key,
                        "symbol": symbol,
                        "name": data[symbol]["name"],
                        "side": "BUY",
                        "decision_data_as_of": candidate["decision_data_as_of"],
                        "execution_at": date_key,
                        "signal_lag_bars": 1,
                        "execution_price_basis": "next_available_open",
                        "gross_price": round(gross_entry_price, 8),
                        "price": round(entry_price, 8),
                        "entry_price": round(entry_price, 8),
                        "quantity": int(quantity),
                        "score": round(float(candidate["score"]), 2),
                        "reason": f"{reason_prefix} {family} {candidate['metrics']}",
                        "liquidity_reference_volume": candidate["liquidity"]["reference_volume"],
                        "liquidity_volume_basis": candidate["liquidity"]["basis"],
                        "cost_pct": trade_cost_pct,
                        "cost_amount": round(quantity * (entry_price - gross_entry_price), 8),
                    }
                )
                current_equity = equity()
                if slots <= 0 and not pyramid:
                    break

        for symbol, row in today_rows.items():
            last_rows[symbol] = row
            histories[symbol]["open"].append(float(row["open"]))
            histories[symbol]["high"].append(float(row["high"]))
            histories[symbol]["low"].append(float(row["low"]))
            histories[symbol]["close"].append(float(row["close"]))
            histories[symbol]["volume"].append(int(row.get("volume", 0) or 0))

        current_equity = equity()
        peak = max(peak, current_equity)
        drawdown = (current_equity / peak - 1.0) * 100.0 if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)
        equity_curve.append(current_equity)

    final_equity = equity_curve[-1] if equity_curve else cash
    closed = [trade for trade in trades if trade["side"] == "SELL"]
    wins = [trade for trade in closed if float(trade.get("pnl_pct", 0) or 0) > 0]
    top_closed = sorted(closed, key=lambda item: float(item.get("pnl_pct", 0) or 0), reverse=True)[:12]
    open_position_evidence = [
        {
            "symbol": symbol,
            "name": data[symbol]["name"],
            "quantity": int(position["quantity"]),
            "avg_price": round(float(position["avg_price"]), 8),
            "last_price": round(float((last_rows.get(symbol) or {}).get("close", position["avg_price"])), 8),
            "unrealized_pct": round((float((last_rows.get(symbol) or {}).get("close", position["avg_price"])) / float(position["avg_price"]) - 1.0) * 100.0, 2),
        }
        for symbol, position in positions.items()
    ]
    timing_model = {
        "version": "past-only-ohlcv-execution.v2",
        "decision_basis": "prior_completed_symbol_bars",
        "execution_basis": "next_available_open",
        "liquidity_volume_basis": "prior_completed_20d_average_volume",
        "current_day_volume_allowed": False,
        "missing_symbol_bar_policy": "skip_execution_until_next_available_symbol_bar",
        "trailing_stop_activation_basis": "prior_completed_peak_only",
        "same_day_ohlc_ambiguity_policy": "stop_first_conservative",
        "lookahead_safe_required": True,
    }
    evidence_audit, ledger_reference = finalize_trade_evidence(
        engine="hundred_billion_strategy_lab",
        strategy_name=str(config["name"]),
        config=config,
        actions=trades,
        initial_cash=INITIAL_CASH,
        final_equity=final_equity,
        open_positions=open_position_evidence,
        timing_model=timing_model,
        store=evidence_store,
    )
    return {
        "name": str(config["name"]),
        "family": family,
        "final_equity": round(final_equity, 2),
        "multiple": round(final_equity / INITIAL_CASH, 4),
        "target_progress_pct": round(final_equity / TARGET_CASH * 100.0, 4),
        "return_pct": round((final_equity / INITIAL_CASH - 1.0) * 100.0, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "trade_count": len(trades),
        "closed_trade_count": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100.0, 2) if closed else 0.0,
        "config": config,
        "open_positions": open_position_evidence,
        "top_closed_trades": top_closed,
        "execution_timing_model": timing_model,
        "trade_evidence_audit": evidence_audit,
        "trade_ledger": ledger_reference,
        "performance_evidence_status": "verified" if evidence_audit.get("official_return_claim_allowed") else "blocked",
        "discovery_log": discovery_log[-25:],
    }


def _configs(mode: str = "quick") -> list[dict[str, object]]:
    configs: list[dict[str, object]] = []
    if mode == "ultra":
        profiles = [
            {"tag": "rb1loose", "rebalance_days": 1, "min_p20": 2.0, "min_p60": 8.0, "min_high_dist": -10.0, "min_vol_ratio": 0.45, "trail_mult": 1.8, "max_gap_up_pct": 14.0},
            {"tag": "rb2fast", "rebalance_days": 2, "min_p20": 3.0, "min_p60": 10.0, "min_high_dist": -8.0, "min_vol_ratio": 0.50, "trail_mult": 1.8, "max_gap_up_pct": 12.0},
            {"tag": "rb3tight", "rebalance_days": 3, "min_p20": 4.0, "min_p60": 12.0, "min_high_dist": -7.0, "min_vol_ratio": 0.55, "trail_mult": 1.6, "max_gap_up_pct": 10.0},
        ]
        for stop in [18.0, 20.0, 22.0, 24.0, 26.0, 28.0]:
            for hold in [50, 60, 70, 80, 90, 100, 120, 160]:
                for profile in profiles:
                    configs.append(
                        {
                            "name": f"ultra_momentum_{profile['tag']}_p1_s{stop:g}_h{hold}",
                            "family": "momentum_blend",
                            "min_history": 120,
                            "fast": 5,
                            "slow": 20,
                            "rebalance_days": profile["rebalance_days"],
                            "max_positions": 1,
                            "position_pct": 100.0,
                            "stop_pct": stop,
                            "take_pct": 0.0,
                            "trail_pct": max(14.0, stop * float(profile["trail_mult"])),
                            "hold_days": hold,
                            "trade_cost_pct": 0.18,
                            "liquidity_pct": 2.0,
                            "max_gap_up_pct": profile["max_gap_up_pct"],
                            "min_p20": profile["min_p20"],
                            "min_p60": profile["min_p60"],
                            "min_high_dist": profile["min_high_dist"],
                            "min_vol_ratio": profile["min_vol_ratio"],
                        }
                    )
        return configs
    if mode == "focus":
        profiles = [
            {"tag": "base", "rebalance_days": 5, "min_p20": 4.0, "min_p60": 12.0, "min_high_dist": -7.0, "min_vol_ratio": 0.55, "trail_mult": 1.8},
            {"tag": "fast", "rebalance_days": 2, "min_p20": 3.0, "min_p60": 10.0, "min_high_dist": -8.0, "min_vol_ratio": 0.50, "trail_mult": 1.8},
            {"tag": "loose", "rebalance_days": 5, "min_p20": 2.0, "min_p60": 8.0, "min_high_dist": -10.0, "min_vol_ratio": 0.45, "trail_mult": 2.2},
        ]
        for slots in [1, 2, 3]:
            for stop in [22.0, 25.0, 28.0, 32.0]:
                for hold in [60, 80, 100, 120]:
                    for profile in profiles:
                        configs.append(
                            {
                                "name": f"focus_momentum_{profile['tag']}_p{slots}_s{stop:g}_h{hold}",
                                "family": "momentum_blend",
                                "min_history": 120,
                                "fast": 5,
                                "slow": 20,
                                "rebalance_days": profile["rebalance_days"],
                                "max_positions": slots,
                                "position_pct": 100.0 / slots,
                                "stop_pct": stop,
                                "take_pct": 0.0,
                                "trail_pct": max(14.0, stop * float(profile["trail_mult"])),
                                "hold_days": hold,
                                "trade_cost_pct": 0.18,
                                "liquidity_pct": 2.0 if slots <= 2 else 1.0,
                                "max_gap_up_pct": 12.0,
                                "min_p20": profile["min_p20"],
                                "min_p60": profile["min_p60"],
                                "min_high_dist": profile["min_high_dist"],
                                "min_vol_ratio": profile["min_vol_ratio"],
                            }
                        )
        return configs
    families = ["turtle_55", "darvas_box", "minervini_proxy", "canslim_proxy", "leader_pullback", "super_leader", "crash_rebound"]
    momentum_stops = [14.0, 16.0, 18.0, 20.0, 22.0, 25.0] if mode == "quick" else [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 25.0, 30.0]
    momentum_holds = [80, 120, 180, 240, 300, 360, 480] if mode == "quick" else [40, 60, 80, 120, 180, 240, 300, 360, 480, 720]
    for slots in ([2, 4] if mode == "quick" else [1, 2, 3, 4, 6]):
        for stop in momentum_stops:
            for hold in momentum_holds:
                configs.append(
                    {
                        "name": f"momentum_blend_p{slots}_s{stop:g}_h{hold}",
                        "family": "momentum_blend",
                        "min_history": 120,
                        "fast": 5,
                        "slow": 20,
                        "rebalance_days": 5,
                        "max_positions": slots,
                        "position_pct": 100.0 / slots,
                        "stop_pct": stop,
                        "take_pct": 0.0,
                        "trail_pct": max(14.0, stop * 1.8),
                        "hold_days": hold,
                        "trade_cost_pct": 0.18,
                        "liquidity_pct": 2.0 if slots <= 2 else 1.0,
                        "max_gap_up_pct": 12.0,
                        "min_p20": 4.0,
                        "min_p60": 12.0,
                        "min_high_dist": -7.0,
                        "min_vol_ratio": 0.55,
                    }
                )
    slots_list = [1, 4] if mode == "quick" else [1, 2, 4]
    stop_list = [12.0, 25.0] if mode == "quick" else [8.0, 12.0, 18.0, 25.0, 35.0]
    hold_list = [60, 240, 480] if mode == "quick" else [20, 60, 120, 240, 480]
    for family in families:
        for slots in slots_list:
            for stop in stop_list:
                for hold in hold_list:
                    if family in {"leader_pullback", "crash_rebound"} and hold < 20:
                        continue
                    configs.append(
                        {
                            "name": f"{family}_p{slots}_s{stop:g}_h{hold}",
                            "family": family,
                            "min_history": 240,
                            "rebalance_days": 5 if family not in {"super_leader", "canslim_proxy"} else 2,
                            "max_positions": slots,
                            "position_pct": 100.0 / slots,
                            "stop_pct": stop,
                            "take_pct": 0.0,
                            "trail_pct": max(12.0, stop * 1.8),
                            "hold_days": hold,
                            "trade_cost_pct": 0.18,
                            "liquidity_pct": 2.0 if slots <= 2 else 1.0,
                            "max_gap_up_pct": 16.0,
                        }
                    )
    pyramid_families = ["super_leader", "canslim_proxy"] if mode == "quick" else ["super_leader", "canslim_proxy", "minervini_proxy", "darvas_box"]
    pyramid_stops = [18.0, 25.0] if mode == "quick" else [12.0, 18.0, 25.0]
    pyramid_holds = [120, 480] if mode == "quick" else [60, 120, 240, 480]
    for family in pyramid_families:
        for stop in pyramid_stops:
            for hold in pyramid_holds:
                configs.append(
                    {
                        "name": f"pyramid_{family}_s{stop:g}_h{hold}",
                        "family": family,
                        "min_history": 240,
                        "rebalance_days": 5,
                        "max_positions": 1,
                        "position_pct": 55.0,
                        "stop_pct": stop,
                        "take_pct": 0.0,
                        "trail_pct": max(18.0, stop * 1.8),
                        "hold_days": hold,
                        "trade_cost_pct": 0.18,
                        "liquidity_pct": 2.0,
                        "max_gap_up_pct": 18.0,
                        "pyramid": True,
                        "pyramid_gain_pct": 18.0,
                        "max_adds": 2,
                    }
                )
    return configs


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_report(summary: dict[str, object]) -> None:
    results = summary.get("results", [])
    best = results[0] if isinstance(results, list) and results and isinstance(results[0], dict) else {}
    lines = [
        "# 100억 전략 실험실",
        "",
        f"- 생성: {summary.get('generated_at')}",
        f"- 구간: {summary.get('start')} ~ {summary.get('end')}",
        f"- 시작 자본: {INITIAL_CASH:,.0f}원",
        f"- 목표 자본: {TARGET_CASH:,.0f}원",
        f"- 데이터 종목: {summary.get('data_symbols')}개",
        f"- 전략 조합: {summary.get('tested')}개",
        f"- 최고 전략: {best.get('name', '-')}",
        f"- 최고 배수: {_round(best.get('multiple'), 4):,.4f}배",
        f"- 최고 최종자산: {_round(best.get('final_equity'), 0):,.0f}원",
        f"- 최고 MDD: {_round(best.get('max_drawdown_pct'), 2):.2f}%",
        "",
        "## 실험 원칙",
        "",
        "- 미래 데이터는 보지 않고, 전일까지의 OHLCV로만 후보를 고릅니다.",
        "- 진입은 다음 거래일 시가 기준으로 근사합니다.",
        "- 기본 거래비용/슬리피지 0.18%를 반영합니다.",
        "- 이 기록은 연구용이며 수익 보장이나 실전 매수 지시가 아닙니다.",
        "",
        "## 상위 20개 전략",
        "",
        "| 순위 | 전략 | 계열 | 최종자산 | 배수 | 목표진행 | MDD | 거래 | 승률 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    if isinstance(results, list):
        for index, row in enumerate([item for item in results if isinstance(item, dict)][:20], 1):
            lines.append(
                f"| {index} | {row.get('name')} | {row.get('family')} | {_round(row.get('final_equity'), 0):,.0f}원 | "
                f"{_round(row.get('multiple'), 4):.4f}배 | {_round(row.get('target_progress_pct'), 4):.4f}% | "
                f"{_round(row.get('max_drawdown_pct'), 2):.2f}% | {row.get('trade_count')} | {_round(row.get('win_rate_pct'), 2):.2f}% |"
            )
    if best:
        lines.extend(["", "## 최고 전략의 주요 수익 거래", ""])
        for trade in best.get("top_closed_trades", [])[:10] if isinstance(best.get("top_closed_trades"), list) else []:
            if isinstance(trade, dict):
                lines.append(f"- {trade.get('date')} {trade.get('name')}({trade.get('symbol')}) {trade.get('pnl_pct')}%: {trade.get('reason')}")
        lines.extend(["", "## 최고 전략 최근 발견 로그", ""])
        for log in best.get("discovery_log", [])[-8:] if isinstance(best.get("discovery_log"), list) else []:
            if not isinstance(log, dict):
                continue
            tops = ", ".join(
                f"{item.get('name')}({item.get('symbol')}) score {item.get('score')}"
                for item in log.get("top", [])[:3]
                if isinstance(item, dict)
            )
            lines.append(f"- {log.get('date')}: {tops}")
    lines.extend(
        [
            "",
            "## 다음 연구 방향",
            "",
            "- 1000배 목표에는 아직 부족하면, 분봉/호가/실시간 거래대금 기반 단타 엔진을 별도 실험해야 합니다.",
            "- 현재 상장 종목 유니버스 기반이라 상장폐지 종목 누락과 생존자 편향이 남아 있습니다.",
            "- KRX 상장/상폐 이력, 섹터별 상대강도, 뉴스/공시 촉매, 시장 국면 필터를 더 붙여야 합니다.",
        ]
    )
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    started = time.time()
    mode = "deep" if "--deep" in sys.argv else "ultra" if "--ultra" in sys.argv else "focus" if "--focus" in sys.argv else "quick"
    configs = _configs(mode=mode)
    fingerprint_options = {
        "start": wf.START,
        "end": wf.END,
        "data_version": wf.DATA_VERSION,
        "mode": mode,
    }
    source_paths = [Path(__file__), Path(wf.__file__), APP_ROOT / "backtest_trade_evidence.py"]
    run_fingerprint = build_run_fingerprint(
        engine="hundred_billion_strategy_lab",
        source_paths=source_paths,
        data_paths=[wf.OHLCV_CACHE],
        configs=configs,
        options=fingerprint_options,
    )
    if "--force" not in sys.argv:
        cached = load_reusable_verified_summary(
            RESULT_FILE,
            expected_fingerprint=run_fingerprint,
            ledger_path=TRADE_EVIDENCE_DB,
            engine="hundred_billion_strategy_lab",
        )
        if cached is not None:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "cache_hit": True,
                        "message": "Identical verified code, data, and strategy evidence was reused.",
                        "run_id": (cached.get("trade_evidence") or {}).get("run_id"),
                        "tested": cached.get("tested"),
                        "result_file": str(RESULT_FILE),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
    data, meta = wf._load_ohlcv_data()
    run_fingerprint = build_run_fingerprint(
        engine="hundred_billion_strategy_lab",
        source_paths=source_paths,
        data_paths=[wf.OHLCV_CACHE],
        configs=configs,
        options=fingerprint_options,
    )
    results: list[dict[str, object]] = []
    run_id = make_run_id("hundred_billion_strategy_lab")
    evidence_store = TradeEvidenceStore(
        TRADE_EVIDENCE_DB,
        engine="hundred_billion_strategy_lab",
        run_id=run_id,
    )
    pruned_ledger_rows = 0
    try:
        for index, config in enumerate(configs, 1):
            results.append(_run_strategy(data, config, evidence_store))
            if index % 20 == 0:
                partial = sorted(results, key=lambda row: float(row.get("final_equity", 0) or 0), reverse=True)
                _write_json(
                    RESULT_FILE,
                    {
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "mode": mode,
                        "status": "PARTIAL",
                        "run_fingerprint": run_fingerprint,
                        "tested": len(results),
                        "planned": len(configs),
                        "elapsed_seconds": round(time.time() - started, 1),
                        **meta,
                        "trade_evidence": {
                            "schema_version": "backtest-trade-evidence.v1",
                            "database_path": str(TRADE_EVIDENCE_DB),
                            "run_id": run_id,
                            "verified_result_count": sum(
                                1
                                for row in partial
                                if isinstance(row.get("trade_evidence_audit"), dict)
                                and row["trade_evidence_audit"].get("official_return_claim_allowed") is True
                            ),
                        },
                        "results": partial,
                    },
                )
        pruned_ledger_rows = evidence_store.prune_old_runs(keep_runs=5)
    finally:
        evidence_store.close()
    results.sort(key=lambda row: float(row.get("final_equity", 0) or 0), reverse=True)
    verified_result_count = sum(
        1
        for row in results
        if isinstance(row.get("trade_evidence_audit"), dict)
        and row["trade_evidence_audit"].get("official_return_claim_allowed") is True
    )
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "status": "DONE",
        "run_fingerprint": run_fingerprint,
        "start": wf.START,
        "end": wf.END,
        "initial_cash": INITIAL_CASH,
        "target_cash": TARGET_CASH,
        "tested": len(results),
        "planned": len(configs),
        "elapsed_seconds": round(time.time() - started, 1),
        **meta,
        "trade_evidence": {
            "schema_version": "backtest-trade-evidence.v1",
            "storage": "sqlite_zlib",
            "database_path": str(TRADE_EVIDENCE_DB),
            "run_id": run_id,
            "verified_result_count": verified_result_count,
            "result_count": len(results),
            "all_results_verified": verified_result_count == len(results),
            "pruned_old_ledger_rows": pruned_ledger_rows,
        },
        "methodology_evidence": {
            "schema_version": "ohlcv-methodology-v2",
            "temporal_integrity": {
                "passed": True,
                "rule": "signals and liquidity use prior completed symbol bars; execution uses the next available open",
            },
            "liquidity_capacity": {
                "passed": True,
                "rule": "execution-day volume is forbidden; prior completed 20-day average volume is used",
            },
            "survivorship_bias": {
                "passed": False,
                "reason": "point-in-time delisted and historical-index constituents are not yet included",
            },
        },
        "results": results,
    }
    _write_json(RESULT_FILE, summary)
    _write_report(summary)
    compact = [
        {
            "name": row.get("name"),
            "family": row.get("family"),
            "final_equity": row.get("final_equity"),
            "multiple": row.get("multiple"),
            "target_progress_pct": row.get("target_progress_pct"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "trade_count": row.get("trade_count"),
            "win_rate_pct": row.get("win_rate_pct"),
        }
        for row in results[:12]
    ]
    print(
        json.dumps(
            {
                "summary": {k: summary[k] for k in ["generated_at", "data_symbols", "tested", "elapsed_seconds"]},
                "top12": compact,
                "report": str(REPORT_FILE),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

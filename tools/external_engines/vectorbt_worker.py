from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from typing import Any

import pandas as pd
import vectorbt as vbt


FORBIDDEN_KEY_PARTS = (
    "account",
    "approval",
    "broker",
    "kis_",
    "order_token",
    "password",
    "secret",
)


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _assert_research_only(value: Any, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(f"forbidden_input_field:{path}.{key}")
            _assert_research_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_research_only(child, f"{path}[{index}]")


def _stage2_trade_evidence(
    portfolio: Any,
    close: pd.Series,
    *,
    symbol: str,
    currency: str,
    price_unit: str,
    fee_rate: float,
    slippage_rate: float,
    snapshot_id: str,
    dataset_hash: str,
    fast_window: int,
    slow_window: int,
) -> dict[str, Any]:
    readable = portfolio.trades.records_readable
    rows = readable.to_dict("records") if readable is not None and not readable.empty else []
    last_timestamp = str(close.index[-1]) if len(close.index) else ""
    ledger: list[dict[str, Any]] = []
    blockers: list[str] = []
    return_mismatch_count = 0
    for row in rows:
        quantity = _finite(row.get("Size"))
        entry_price = _finite(row.get("Avg Entry Price"))
        exit_price = _finite(row.get("Avg Exit Price"))
        entry_fees = _finite(row.get("Entry Fees"))
        exit_fees = _finite(row.get("Exit Fees"))
        pnl = _finite(row.get("PnL"))
        engine_return_pct = _finite(row.get("Return")) * 100.0
        # vectorbt defines per-trade Return against gross entry value; fees are already included in PnL.
        invested_amount = entry_price * quantity
        reconciled_return_pct = (pnl / invested_amount) * 100.0 if invested_amount > 0 else 0.0
        if abs(engine_return_pct - reconciled_return_pct) > 0.000001:
            return_mismatch_count += 1
        exit_timestamp = str(row.get("Exit Timestamp") or "")
        status = str(row.get("Status") or "").strip().lower()
        exit_reason = "final_bar_flatten" if exit_timestamp == last_timestamp else "ma_fast_below_slow"
        ledger.append(
            {
                "symbol": symbol,
                "entry_at": str(row.get("Entry Timestamp") or ""),
                "entry_price": round(entry_price, 8),
                "entry_reason": "ma_fast_above_slow",
                "exit_at": exit_timestamp,
                "exit_price": round(exit_price, 8),
                "exit_reason": exit_reason,
                "quantity": round(quantity, 8),
                "entry_fees": round(entry_fees, 8),
                "exit_fees": round(exit_fees, 8),
                "slippage_rate": round(slippage_rate, 8),
                "gross_return_pct": round(((exit_price / entry_price) - 1.0) * 100.0, 8)
                if entry_price > 0 and exit_price > 0
                else 0.0,
                "net_pnl": round(pnl, 8),
                "net_return_pct": round(engine_return_pct, 8),
                "reconciled_net_return_pct": round(reconciled_return_pct, 8),
                "currency": currency,
                "price_unit": price_unit,
                "status": status,
                "fast_window": fast_window,
                "slow_window": slow_window,
            }
        )
        if status != "closed":
            blockers.append("open_trade_remains")
        if quantity <= 0 or entry_price <= 0 or exit_price <= 0:
            blockers.append("non_positive_trade_value")

    canonical_ledger = json.dumps(
        ledger,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fill_ledger_hash = hashlib.sha256(canonical_ledger.encode("utf-8")).hexdigest()
    entry_exit_passed = bool(ledger) and not blockers
    return_reconciliation_passed = entry_exit_passed and return_mismatch_count == 0
    exit_reason_passed = entry_exit_passed and all(
        trade["exit_reason"] in {"ma_fast_below_slow", "final_bar_flatten"}
        for trade in ledger
    )
    cost_profile_passed = entry_exit_passed and fee_rate >= 0 and slippage_rate >= 0 and all(
        trade["entry_fees"] >= 0 and trade["exit_fees"] >= 0 for trade in ledger
    )
    unit_currency_passed = (
        entry_exit_passed
        and currency in {"KRW", "USD"}
        and price_unit in {"won_integer", "decimal_usd", "usd_decimal"}
        and all(
            trade["currency"] == currency and trade["price_unit"] == price_unit
            for trade in ledger
        )
    )
    evidence = {
        "fill_ledger_hash": fill_ledger_hash,
        "trade_count": len(ledger),
        "trade_ledger": ledger,
        "blockers": sorted(set(blockers)),
        "snapshot_id": snapshot_id,
        "dataset_hash": dataset_hash,
        "entry_exit_return_reason_evidence": {
            "passed": entry_exit_passed,
            "trade_count": len(ledger),
            "fill_ledger_hash": fill_ledger_hash,
        },
        "return_reconciliation_evidence": {
            "passed": return_reconciliation_passed,
            "checked_count": len(ledger),
            "mismatch_count": return_mismatch_count,
            "tolerance_pct": 0.000001,
            "fill_ledger_hash": fill_ledger_hash,
        },
        "exit_reason_alignment_evidence": {
            "passed": exit_reason_passed,
            "checked_count": len(ledger),
            "allowed_reasons": ["ma_fast_below_slow", "final_bar_flatten"],
            "fill_ledger_hash": fill_ledger_hash,
        },
        "fee_tax_slippage_evidence": {
            "passed": cost_profile_passed,
            "composite_fee_rate": fee_rate,
            "slippage_rate": slippage_rate,
            "tax_treatment": "included_in_disclosed_composite_fee_rate",
            "applied_trade_count": len(ledger),
            "fill_ledger_hash": fill_ledger_hash,
        },
        "unit_currency_audit_evidence": {
            "passed": unit_currency_passed,
            "currency": currency,
            "price_unit": price_unit,
            "split_adjustment_source": "codexstock_adjusted_ohlcv_snapshot",
            "fill_ledger_hash": fill_ledger_hash,
        },
        "no_live_order_evidence": {
            "passed": True,
            "order_api_call_count": 0,
            "account_mutation_count": 0,
            "runtime_mode": "historical_backtest_read_only",
            "live_order_allowed": False,
        },
    }
    evidence["validation_grade"] = (
        "A"
        if all(
            evidence[key]["passed"]
            for key in (
                "entry_exit_return_reason_evidence",
                "return_reconciliation_evidence",
                "exit_reason_alignment_evidence",
                "fee_tax_slippage_evidence",
                "unit_currency_audit_evidence",
                "no_live_order_evidence",
            )
        )
        else "BLOCKED"
    )
    return evidence


def _strategy_result(
    close: pd.Series,
    fast_window: int,
    slow_window: int,
    *,
    symbol: str,
    currency: str,
    price_unit: str,
    snapshot_id: str,
    dataset_hash: str,
    initial_cash: float,
    fee_rate: float,
    slippage_rate: float,
) -> dict[str, Any]:
    fast = vbt.MA.run(close, window=fast_window).ma
    slow = vbt.MA.run(close, window=slow_window).ma
    entries = (fast > slow).copy()
    exits = (fast < slow).copy()
    if len(exits):
        entries.iloc[-1] = False
        exits.iloc[-1] = True
    portfolio = vbt.Portfolio.from_signals(
        close,
        entries,
        exits,
        init_cash=initial_cash,
        fees=fee_rate,
        slippage=slippage_rate,
        freq="1D",
    )
    trade_count = int(portfolio.trades.count())
    return_pct = _finite(portfolio.total_return()) * 100.0
    max_drawdown_pct = _finite(portfolio.max_drawdown()) * 100.0
    sharpe = _finite(portfolio.sharpe_ratio())
    final_value = _finite(portfolio.final_value(), initial_cash)
    return {
        "fast_window": fast_window,
        "slow_window": slow_window,
        "trade_count": trade_count,
        "return_pct": round(return_pct, 6),
        "mdd_pct": round(max_drawdown_pct, 6),
        "sharpe": round(sharpe, 6),
        "initial_cash": round(initial_cash, 2),
        "final_value": round(final_value, 2),
        "stage2_evidence": _stage2_trade_evidence(
            portfolio,
            close,
            symbol=symbol,
            currency=currency,
            price_unit=price_unit,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
            snapshot_id=snapshot_id,
            dataset_hash=dataset_hash,
            fast_window=fast_window,
            slow_window=slow_window,
        ),
    }


def _portfolio_scenario(
    close: pd.DataFrame,
    *,
    name: str,
    fast_window: int,
    slow_window: int,
    initial_cash: float,
    fee_rate: float,
    slippage_rate: float,
    signal_delay_bars: int,
) -> dict[str, Any]:
    fast = vbt.MA.run(close, window=fast_window).ma
    slow = vbt.MA.run(close, window=slow_window).ma
    # vectorbt includes the window parameter in DataFrame column labels. Strip it so
    # each fast series is compared with the same symbol's slow series.
    fast.columns = close.columns
    slow.columns = close.columns
    regime = (fast > slow).astype(bool)
    previous_regime = regime.shift(1, fill_value=False).astype(bool)
    entries = (regime & ~previous_regime).astype(bool)
    exits = (~regime & previous_regime).astype(bool)
    if signal_delay_bars:
        entries = entries.shift(signal_delay_bars, fill_value=False).astype(bool)
        exits = exits.shift(signal_delay_bars, fill_value=False).astype(bool)
    if len(exits):
        entries.iloc[-1] = False
        exits.iloc[-1] = True
    portfolio = vbt.Portfolio.from_signals(
        close,
        entries,
        exits,
        init_cash=initial_cash,
        fees=fee_rate,
        slippage=slippage_rate,
        freq="1D",
        cash_sharing=False,
    )
    values = portfolio.value()
    if isinstance(values, pd.Series):
        values = values.to_frame(name=str(close.columns[0]))
    aggregate = values.sum(axis=1)
    initial_total = initial_cash * len(close.columns)
    final_total = _finite(aggregate.iloc[-1], initial_total) if len(aggregate) else initial_total
    aggregate_return_pct = (final_total / initial_total - 1.0) * 100.0 if initial_total > 0 else 0.0
    peaks = aggregate.cummax()
    drawdowns = aggregate / peaks.replace(0.0, math.nan) - 1.0
    aggregate_mdd_pct = _finite(drawdowns.min()) * 100.0 if len(drawdowns) else 0.0
    total_returns = portfolio.total_return()
    if isinstance(total_returns, pd.Series):
        symbol_returns = {
            str(symbol): round(_finite(value) * 100.0, 8)
            for symbol, value in total_returns.items()
        }
    else:
        symbol_returns = {str(close.columns[0]): round(_finite(total_returns) * 100.0, 8)}
    trade_counts = portfolio.trades.count()
    trade_count = int(trade_counts.sum()) if hasattr(trade_counts, "sum") else int(trade_counts)
    equity_hash = hashlib.sha256(
        json.dumps(
            [round(_finite(value), 8) for value in aggregate.tolist()],
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "name": name,
        "ok": bool(len(aggregate)),
        "fast_window": fast_window,
        "slow_window": slow_window,
        "fee_rate": round(fee_rate, 8),
        "slippage_rate": round(slippage_rate, 8),
        "signal_delay_bars": signal_delay_bars,
        "symbol_count": len(close.columns),
        "trade_count": trade_count,
        "initial_value": round(initial_total, 2),
        "final_value": round(final_total, 2),
        "return_pct": round(aggregate_return_pct, 8),
        "mdd_pct": round(aggregate_mdd_pct, 8),
        "symbol_returns_pct": symbol_returns,
        "equity_hash": equity_hash,
    }


def _run_portfolio_scenarios(request: dict[str, Any], started: float) -> dict[str, Any]:
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    rows = snapshot.get("dataset_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset_rows_required")
    frame = pd.DataFrame(rows)
    required = {"symbol", "date", "close", "currency", "price_unit"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("missing_snapshot_fields:" + ",".join(missing))
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["symbol", "date", "close"])
    frame = frame[frame["close"] > 0]
    close = (
        frame.sort_values(["date", "symbol"])
        .drop_duplicates(["date", "symbol"], keep="last")
        .pivot(index="date", columns="symbol", values="close")
        .sort_index()
    )
    minimum_rows = max(40, int(request.get("slow_window", 40)) + 2)
    valid_columns = [column for column in close.columns if int(close[column].notna().sum()) >= minimum_rows]
    close = close[valid_columns].ffill(limit=3).dropna(axis=0, how="any").astype(float)
    if close.empty or len(close.columns) < 2:
        raise ValueError("at_least_two_aligned_symbols_required")

    fast_window = max(2, min(int(request.get("fast_window", 10)), 60))
    slow_window = max(fast_window + 1, min(int(request.get("slow_window", 40)), 200))
    if len(close) < slow_window + 2:
        raise ValueError("insufficient_aligned_rows")
    initial_cash = max(10_000.0, _finite(request.get("initial_cash"), 10_000_000.0))
    fee_rate = min(0.02, max(0.0, _finite(request.get("fee_rate"), 0.0015)))
    slippage_rate = min(0.02, max(0.0, _finite(request.get("slippage_rate"), 0.001)))
    configs = (
        ("base", fee_rate, slippage_rate, 0),
        ("cost_stress", min(0.02, fee_rate * 2.0), min(0.02, slippage_rate * 3.0), 0),
        ("one_bar_latency", fee_rate, slippage_rate, 1),
        ("combined_stress", min(0.02, fee_rate * 2.0), min(0.02, slippage_rate * 3.0), 1),
    )
    scenarios = [
        _portfolio_scenario(
            close,
            name=name,
            fast_window=fast_window,
            slow_window=slow_window,
            initial_cash=initial_cash,
            fee_rate=scenario_fee,
            slippage_rate=scenario_slippage,
            signal_delay_bars=delay,
        )
        for name, scenario_fee, scenario_slippage, delay in configs
    ]
    returns = [float(row["return_pct"]) for row in scenarios]
    drawdowns = [float(row["mdd_pct"]) for row in scenarios]
    profitable_count = sum(value > 0 for value in returns)
    robustness_passed = bool(
        all(row.get("ok") for row in scenarios)
        and profitable_count >= 3
        and min(returns) > -5.0
        and min(drawdowns) > -30.0
    )
    capability_evidence = [
        {"capability": "native_multi_asset_portfolio", "passed": True, "symbol_count": len(close.columns)},
        {"capability": "multi_scenario_replay", "passed": len(scenarios) == 4, "scenario_count": len(scenarios)},
        {"capability": "cost_and_latency_stress", "passed": True, "cost_stress": True, "latency_bars": 1},
        {"capability": "live_order_boundary", "passed": True, "live_order_allowed": False},
    ]
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "engine_commit": request.get("engine_commit"),
        "scenarios": scenarios,
        "robustness_passed": robustness_passed,
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "ok": all(row.get("ok") for row in scenarios),
        "schema": "codexstock_vectorbt_portfolio_scenarios_v1",
        "action": "evaluate_portfolio_scenarios",
        "engine_name": "vectorbt",
        "engine_version": str(vbt.__version__),
        "engine_commit": str(request.get("engine_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "symbol_count": len(close.columns),
        "row_count": len(close),
        "scenario_count": len(scenarios),
        "profitable_scenario_count": profitable_count,
        "scenarios": scenarios,
        "quality_gate": {
            "passed": robustness_passed,
            "minimum_profitable_scenarios": 3,
            "minimum_worst_return_pct": -5.0,
            "minimum_worst_mdd_pct": -30.0,
        },
        "research_verdict": "REVIEW_CANDIDATE" if robustness_passed else "RETRAIN_OR_REJECT",
        "capability_evidence": capability_evidence,
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "promotion_allowed": False,
        "live_order_allowed": False,
        "decision": "RESEARCH_ONLY",
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_research_only(request)
    action = str(request.get("action") or "")
    if action == "evaluate_portfolio_scenarios":
        return _run_portfolio_scenarios(request, started)
    if action != "run_external_backtest":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")

    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    rows = snapshot.get("dataset_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset_rows_required")

    frame = pd.DataFrame(rows)
    required = {"symbol", "date", "close", "currency", "price_unit"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("missing_snapshot_fields:" + ",".join(missing))
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["symbol", "date", "close"])
    frame = frame[frame["close"] > 0]
    if frame.empty:
        raise ValueError("no_valid_close_rows")

    fast_windows = sorted({int(value) for value in request.get("fast_windows", [5, 10, 20]) if int(value) >= 2})[:8]
    slow_windows = sorted({int(value) for value in request.get("slow_windows", [20, 40, 60]) if int(value) >= 3})[:8]
    initial_cash = max(10_000.0, _finite(request.get("initial_cash"), 10_000_000.0))
    fee_rate = min(0.02, max(0.0, _finite(request.get("fee_rate"), 0.0015)))
    slippage_rate = min(0.02, max(0.0, _finite(request.get("slippage_rate"), 0.001)))

    candidates: list[dict[str, Any]] = []
    symbol_summaries: list[dict[str, Any]] = []
    stage2_evidence_by_symbol: dict[str, dict[str, Any]] = {}
    for symbol, symbol_frame in frame.groupby("symbol", sort=True):
        symbol_frame = symbol_frame.sort_values("date").drop_duplicates("date", keep="last")
        close = pd.Series(symbol_frame["close"].to_numpy(dtype=float), index=pd.Index(symbol_frame["date"].astype(str)))
        currency = str(symbol_frame.iloc[-1]["currency"]).upper()
        price_unit = str(symbol_frame.iloc[-1]["price_unit"])
        symbol_candidates: list[dict[str, Any]] = []
        for fast_window in fast_windows:
            for slow_window in slow_windows:
                if fast_window >= slow_window or len(close) < slow_window + 2:
                    continue
                result = _strategy_result(
                    close,
                    fast_window,
                    slow_window,
                    symbol=str(symbol),
                    currency=currency,
                    price_unit=price_unit,
                    snapshot_id=str(request.get("snapshot_id") or ""),
                    dataset_hash=str(request.get("dataset_hash") or ""),
                    initial_cash=initial_cash,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                )
                result.update(
                    {
                        "symbol": str(symbol),
                        "currency": currency,
                        "price_unit": price_unit,
                        "row_count": len(close),
                    }
                )
                symbol_candidates.append(result)
        symbol_candidates.sort(key=lambda item: (item["return_pct"], item["sharpe"]), reverse=True)
        best_internal = symbol_candidates[0] if symbol_candidates else None
        if best_internal and isinstance(best_internal.get("stage2_evidence"), dict):
            stage2_evidence_by_symbol[str(symbol)] = best_internal["stage2_evidence"]
        public_candidates = [
            {key: value for key, value in candidate.items() if key != "stage2_evidence"}
            for candidate in symbol_candidates
        ]
        candidates.extend(public_candidates)
        symbol_summaries.append(
            {
                "symbol": str(symbol),
                "row_count": len(close),
                "candidate_count": len(public_candidates),
                "best_candidate": public_candidates[0] if public_candidates else None,
                "stage2_validation_grade": (
                    stage2_evidence_by_symbol.get(str(symbol), {}).get("validation_grade", "BLOCKED")
                ),
            }
        )

    candidates.sort(key=lambda item: (item["return_pct"], item["sharpe"]), reverse=True)
    compact_candidates = candidates[:30]
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "engine_commit": request.get("engine_commit"),
        "candidates": compact_candidates,
        "stage2_evidence_by_symbol": stage2_evidence_by_symbol,
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "ok": True,
        "schema": "codexstock_vectorbt_result_v1",
        "action": "run_external_backtest",
        "engine_name": "vectorbt",
        "engine_version": str(vbt.__version__),
        "engine_commit": str(request.get("engine_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "cost_model": {
            "fee_rate": fee_rate,
            "slippage_rate": slippage_rate,
            "initial_cash": initial_cash,
        },
        "symbol_count": len(symbol_summaries),
        "candidate_count": len(candidates),
        "symbol_summaries": symbol_summaries,
        "top_candidates": compact_candidates,
        "stage2_evidence_by_symbol": stage2_evidence_by_symbol,
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "live_order_allowed": False,
        "decision": "VERIFY_ONLY",
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("request_must_be_object")
        result = run(payload)
    except Exception as exc:
        result = {
            "ok": False,
            "schema": "codexstock_vectorbt_result_v1",
            "engine_name": "vectorbt",
            "error": str(exc)[:400],
            "live_order_allowed": False,
            "decision": "BLOCKED",
        }
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

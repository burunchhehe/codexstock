from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import datetime
from typing import Any

import backtrader as bt


FORBIDDEN_KEY_PARTS = (
    "account_number",
    "approval",
    "broker_token",
    "kis_",
    "order_token",
    "password",
    "secret",
)


def _assert_verify_only(value: Any, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(f"forbidden_input_field:{path}.{key}")
            _assert_verify_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_verify_only(child, f"{path}[{index}]")


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


class SnapshotFeed(bt.feed.DataBase):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__()
        self._rows = rows
        self._cursor = 0

    def _load(self) -> bool:
        if self._cursor >= len(self._rows):
            return False
        row = self._rows[self._cursor]
        self._cursor += 1
        self.lines.datetime[0] = bt.date2num(datetime.fromisoformat(str(row["date"])))
        self.lines.open[0] = _finite(row.get("open"), _finite(row.get("close")))
        self.lines.high[0] = _finite(row.get("high"), _finite(row.get("close")))
        self.lines.low[0] = _finite(row.get("low"), _finite(row.get("close")))
        self.lines.close[0] = _finite(row.get("close"))
        self.lines.volume[0] = _finite(row.get("volume"))
        self.lines.openinterest[0] = 0.0
        return True


class MovingAverageEventStrategy(bt.Strategy):
    params = (("fast_window", 5), ("slow_window", 20), ("liquidation_date", ""))

    def __init__(self) -> None:
        self.fast = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.fast_window)
        self.slow = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.slow_window)
        self.pending_order = None
        self.pending_reason = ""
        self.fills: list[dict[str, Any]] = []
        self.closed_trades: list[dict[str, Any]] = []

    def notify_order(self, order: Any) -> None:
        if order.status in {order.Submitted, order.Accepted}:
            return
        if order.status == order.Completed:
            self.fills.append(
                {
                    "side": "BUY" if order.isbuy() else "SELL",
                    "date": str(bt.num2date(order.executed.dt).date()),
                    "price": round(float(order.executed.price), 8),
                    "size": abs(int(order.executed.size)),
                    "value": round(float(order.executed.value), 8),
                    "commission": round(float(order.executed.comm), 8),
                    "reason": self.pending_reason,
                }
            )
        self.pending_order = None
        self.pending_reason = ""

    def notify_trade(self, trade: Any) -> None:
        if trade.isclosed:
            self.closed_trades.append(
                {
                    "entry_date": str(bt.num2date(trade.dtopen).date()),
                    "exit_date": str(bt.num2date(trade.dtclose).date()),
                    "gross_pnl": round(float(trade.pnl), 8),
                    "net_pnl": round(float(trade.pnlcomm), 8),
                    "bar_count": int(trade.barlen),
                }
            )

    def next(self) -> None:
        if self.pending_order:
            return
        current_date = str(self.data.datetime.date(0))
        if self.position and current_date >= self.p.liquidation_date:
            self.pending_reason = "terminal_liquidation"
            self.pending_order = self.close()
            return
        if len(self) < self.p.slow_window or current_date >= self.p.liquidation_date:
            return
        if not self.position and self.fast[0] > self.slow[0] and self.fast[-1] <= self.slow[-1]:
            self.pending_reason = "ma_cross_up"
            self.pending_order = self.order_target_percent(target=0.95)
        elif self.position and self.fast[0] < self.slow[0] and self.fast[-1] >= self.slow[-1]:
            self.pending_reason = "ma_cross_down"
            self.pending_order = self.close()


def _run_symbol(
    symbol: str,
    rows: list[dict[str, Any]],
    *,
    fast_window: int,
    slow_window: int,
    commission_rate: float,
    slippage_rate: float,
) -> dict[str, Any]:
    valid_rows = [
        row
        for row in sorted(rows, key=lambda item: str(item.get("date") or ""))
        if _finite(row.get("close")) > 0 and str(row.get("date") or "")
    ]
    if len(valid_rows) < slow_window + 5:
        return {"ok": False, "symbol": symbol, "error": "insufficient_rows", "row_count": len(valid_rows)}
    currencies = {str(row.get("currency") or "") for row in valid_rows}
    price_units = {str(row.get("price_unit") or "") for row in valid_rows}
    if len(currencies) != 1 or len(price_units) != 1:
        return {"ok": False, "symbol": symbol, "error": "currency_or_unit_mismatch"}

    initial_cash = 100_000_000.0
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.adddata(SnapshotFeed(valid_rows), name=symbol)
    cerebro.addstrategy(
        MovingAverageEventStrategy,
        fast_window=fast_window,
        slow_window=slow_window,
        liquidation_date=str(valid_rows[-2]["date"]),
    )
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission_rate)
    cerebro.broker.set_slippage_perc(perc=slippage_rate, slip_open=True, slip_match=True, slip_out=False)
    strategy = cerebro.run(runonce=False, preload=False, exactbars=1)[0]
    final_value = float(cerebro.broker.getvalue())
    fills = list(strategy.fills)
    buy_fills = [row for row in fills if row["side"] == "BUY"]
    sell_fills = [row for row in fills if row["side"] == "SELL"]
    fill_pairs = []
    for entry, exit_fill in zip(buy_fills, sell_fills):
        gross_return = exit_fill["price"] / entry["price"] - 1.0 if entry["price"] > 0 else 0.0
        fill_pairs.append(
            {
                "entry_date": entry["date"],
                "entry_price": entry["price"],
                "exit_date": exit_fill["date"],
                "exit_price": exit_fill["price"],
                "exit_reason": exit_fill["reason"],
                "gross_return_pct": round(gross_return * 100.0, 8),
            }
        )
    return {
        "ok": True,
        "symbol": symbol,
        "row_count": len(valid_rows),
        "currency": next(iter(currencies)),
        "price_unit": next(iter(price_units)),
        "initial_cash": initial_cash,
        "final_value": round(final_value, 4),
        "net_return_pct": round((final_value / initial_cash - 1.0) * 100.0, 8),
        "fill_count": len(fills),
        "closed_trade_count": len(strategy.closed_trades),
        "open_position": bool(strategy.position),
        "fills": fills,
        "fill_reconciliation": fill_pairs,
        "closed_trades": strategy.closed_trades,
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_verify_only(request)
    if str(request.get("action") or "") != "event_backtest_bias_check":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    rows = snapshot.get("dataset_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset_rows_required")
    fast_window = max(2, min(int(request.get("fast_window", 5) or 5), 60))
    slow_window = max(fast_window + 1, min(int(request.get("slow_window", 20) or 20), 180))
    commission_rate = max(0.0, min(_finite(request.get("commission_rate"), 0.00015), 0.02))
    slippage_rate = max(0.0, min(_finite(request.get("slippage_rate"), 0.0005), 0.02))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if isinstance(row, dict):
            symbol = str(row.get("symbol") or "").strip()
            if symbol:
                grouped.setdefault(symbol, []).append(row)
    symbol_results = [
        _run_symbol(
            symbol,
            symbol_rows,
            fast_window=fast_window,
            slow_window=slow_window,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )
        for symbol, symbol_rows in sorted(grouped.items())
    ]
    successful = sum(1 for row in symbol_results if row.get("ok"))
    unreconciled_positions = sum(1 for row in symbol_results if row.get("open_position"))
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "source_commit": request.get("source_commit"),
        "fast_window": fast_window,
        "slow_window": slow_window,
        "symbol_results": symbol_results,
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "ok": bool(symbol_results) and successful == len(symbol_results) and unreconciled_positions == 0,
        "schema": "codexstock_backtrader_event_check_v1",
        "action": "event_backtest_bias_check",
        "engine_name": "Backtrader",
        "engine_version": str(bt.__version__),
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "fast_window": fast_window,
        "slow_window": slow_window,
        "commission_rate": commission_rate,
        "slippage_rate": slippage_rate,
        "fill_contract": "signal_close_then_next_bar_open_v1",
        "symbol_count": len(symbol_results),
        "successful_symbol_count": successful,
        "unreconciled_position_count": unreconciled_positions,
        "symbol_results": symbol_results,
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "network_access_allowed": False,
        "decision": "VERIFY_ONLY",
        "live_order_allowed": False,
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
            "schema": "codexstock_backtrader_event_check_v1",
            "engine_name": "Backtrader",
            "error": str(exc)[:600],
            "decision": "BLOCKED",
            "live_order_allowed": False,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

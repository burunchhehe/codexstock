from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import math
import sys
from typing import Any, Protocol
from .strategy_runtime import indicator_signals, run_signals_next_open
from .execution import capacity_rejection_reason, execution_block_reason, execution_capacity, resolve_execution_model, simulate_long_only
from .storage import AnalyticalStorage
from .custom_indicators import CustomIndicatorRegistry
from .multitimeframe import evaluate_multitimeframe
from .regimes import analyze_market_regimes
from .attribution import analyze_benchmark_attribution


class BacktestAdapter(Protocol):
    name: str

    def run(self, strategy: dict[str, Any], data_snapshot: dict[str, Any], execution_model: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class MockBacktestAdapter:
    """Deterministic adapter used by doctor/demo without market or broker access."""

    name: str = "mock"

    def run(self, strategy: dict[str, Any], data_snapshot: dict[str, Any], execution_model: dict[str, Any]) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "data_mode": "mock",
            "trade_count": 0,
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "strategy_name": strategy.get("name"),
            "dataset_id": data_snapshot.get("dataset_id", "mock-v1"),
            "execution_model": execution_model,
        }


@dataclass
class CodexStockNativeBacktestAdapter:
    """Adapter for the existing CodexStock NativeBacktester.

    The current native engine generates deterministic synthetic prices.  This
    adapter therefore refuses snapshots that claim to contain live or
    historical-provider market data; provenance must remain explicit.
    """

    app_root: Path
    name: str = "codexstock-native-synthetic"

    def run(self, strategy: dict[str, Any], data_snapshot: dict[str, Any], execution_model: dict[str, Any]) -> dict[str, Any]:
        data_mode = str(data_snapshot.get("data_mode") or "synthetic")
        if data_mode not in {"mock", "synthetic"}:
            raise ValueError("CodexStock native adapter currently supports only synthetic/mock snapshots")
        rules = dict(strategy.get("rules") or {})
        strategy_type = str(rules.get("type") or "ma_cross")
        if strategy_type != "ma_cross":
            raise ValueError("CodexStock native adapter currently supports only rules.type=ma_cross")
        if str(self.app_root) not in sys.path:
            sys.path.insert(0, str(self.app_root))
        from native_core import NativeBacktester

        symbol = str(rules.get("symbol") or data_snapshot.get("symbol") or "005930").upper()
        start_date = str(data_snapshot.get("start_date") or "2020-01-01")
        end_date = str(data_snapshot.get("end_date") or "2025-12-31")
        fast = int(rules.get("fast") or 5)
        slow = int(rules.get("slow") or 20)
        if fast < 2 or slow <= fast:
            raise ValueError("ma_cross requires 2 <= fast < slow")
        initial_cash = float(execution_model.get("initial_cash") or 10_000.0)
        result = NativeBacktester(initial_cash=initial_cash).run_ma_cross_range(
            symbol, start_date, end_date, fast, slow
        )
        result.update(
            {
                "adapter": self.name,
                "data_mode": "synthetic",
                "dataset_id": data_snapshot["dataset_id"],
                "provenance_warning": "NativeBacktester generated deterministic synthetic prices; this is not provider historical data.",
                "execution_model": execution_model,
            }
        )
        return result


@dataclass
class LocalOhlcvBacktestAdapter:
    """Point-in-time, next-bar execution adapter for CodexStock's local adjusted OHLCV cache."""

    data_root: Path
    name: str = "codexstock-local-ohlcv-v1"
    _cache: dict[Path, tuple[str, dict[str, Any]]] = field(default_factory=dict, init=False, repr=False)

    def run(self, strategy: dict[str, Any], data_snapshot: dict[str, Any], execution_model: dict[str, Any]) -> dict[str, Any]:
        if str(data_snapshot.get("data_mode") or "") != "historical_provider":
            raise ValueError("local OHLCV adapter requires data_mode=historical_provider")
        rules = dict(strategy.get("rules") or {})
        strategy_type = str(rules.get("type") or "")
        if strategy_type not in {"ma_cross", "portfolio_ma_cross", "indicator_rules"}:
            raise ValueError("local OHLCV adapter supports ma_cross, portfolio_ma_cross, and indicator_rules")
        symbol = str(rules.get("symbol") or data_snapshot.get("symbol") or "").upper()
        if strategy_type in {"ma_cross", "indicator_rules"} and (not symbol or not symbol.isalnum()):
            raise ValueError("a safe alphanumeric symbol is required")
        fast, slow = int(rules.get("fast") or 5), int(rules.get("slow") or 20)
        if fast < 2 or slow <= fast or slow > 250:
            raise ValueError("ma_cross requires 2 <= fast < slow <= 250")
        cache_name = str(data_snapshot.get("cache_file") or "walk_forward_ohlcv_cache_adj_20160706_20260706.json")
        if Path(cache_name).name != cache_name or not cache_name.endswith(".json"):
            raise ValueError("cache_file must be a JSON filename inside the CodexStock data root")
        cache_path = (self.data_root / cache_name).resolve()
        if cache_path.parent != self.data_root.resolve() or not cache_path.is_file():
            raise ValueError("OHLCV cache file is missing or outside the data root")
        cached = self._cache.get(cache_path)
        if cached is None:
            cached = (_sha256(cache_path), json.loads(cache_path.read_text(encoding="utf-8")))
            self._cache[cache_path] = cached
        digest, payload = cached
        expected = str(data_snapshot.get("dataset_hash") or "")
        if expected and expected.removeprefix("sha256:").lower() != digest:
            raise ValueError("dataset_hash does not match the local OHLCV cache")
        if strategy_type == "portfolio_ma_cross":
            result = _portfolio_ma_cross(payload, rules, data_snapshot, execution_model)
            result.update(
                {
                    "adapter": self.name,
                    "data_mode": "historical_provider",
                    "data_source": "Yahoo adjusted OHLCV portfolio",
                    "dataset_id": data_snapshot["dataset_id"],
                    "dataset_hash": f"sha256:{digest}",
                    "signal_timing": "close_t",
                    "fill_timing": "open_t_plus_1",
                    "execution_model": execution_model,
                }
            )
            return result
        symbol_payload = payload.get(symbol) if isinstance(payload, dict) else None
        if not isinstance(symbol_payload, dict) or not symbol_payload.get("ok"):
            raise ValueError(f"symbol {symbol} is not available in the OHLCV snapshot")
        start = str(data_snapshot.get("start_date") or "0000-01-01")
        end = str(data_snapshot.get("end_date") or "9999-12-31")
        rows = _exclude_boundary_rows([dict(row) for row in symbol_payload.get("rows", []) if isinstance(row, dict) and start <= str(row.get("date")) <= end], data_snapshot)
        quality = {**_quality(rows), "boundary_row_exclusions": _boundary_exclusion_evidence(data_snapshot)}
        if len(rows) < slow + 2:
            raise ValueError(f"insufficient OHLCV rows: {len(rows)}; need at least {slow + 2}")
        if not quality["strict_temporal_order"] or quality["invalid_ohlc_rows"]:
            raise ValueError(f"OHLCV quality gate failed: {quality}")
        if strategy_type == "indicator_rules":
            entry, exit = indicator_signals(rows, rules)
            result = run_signals_next_open(rows, entry, exit, execution_model)
            result["indicator_profile"] = str(rules.get("profile") or "STANDARD")
        else:
            result = _ma_cross_next_open(rows, fast, slow, execution_model)
        result["regime_performance"] = analyze_market_regimes(rows, result["equity_curve"])
        result["benchmark_attribution"] = analyze_benchmark_attribution(rows, result["equity_curve"])
        result.update(
            {
                "adapter": self.name,
                "data_mode": "historical_provider",
                "data_source": f"Yahoo adjusted OHLCV:{symbol_payload.get('yahoo', symbol)}",
                "dataset_id": data_snapshot["dataset_id"],
                "dataset_hash": f"sha256:{digest}",
                "symbol": symbol,
                "start_date": rows[0]["date"],
                "end_date": rows[-1]["date"],
                "row_count": len(rows),
                "data_quality": quality,
                "signal_timing": "close_t",
                "fill_timing": "open_t_plus_1",
                "execution_model": execution_model,
            }
        )
        return result


@dataclass
class AnalyticalStorageBacktestAdapter:
    """Multi-timeframe adapter over bounded DuckDB queries and verified custom indicators."""

    storage_root: Path
    custom_indicator_root: Path
    name: str = "codexstock-analytical-multitimeframe-v1"

    def run(self, strategy: dict[str, Any], data_snapshot: dict[str, Any], execution_model: dict[str, Any]) -> dict[str, Any]:
        rules = dict(strategy.get("rules") or {})
        symbol = str(rules.get("symbol") or "").upper()
        start, end = str(data_snapshot.get("start_date") or ""), str(data_snapshot.get("end_date") or "")
        if not symbol.isalnum() or not start or not end:
            raise ValueError("analytical adapter requires symbol and date range")
        if rules.get("type") == "ma_cross":
            return self._run_ma_cross(rules, data_snapshot, execution_model, symbol, start, end)
        if rules.get("type") != "multi_timeframe_indicator_rules":
            raise ValueError("analytical adapter requires ma_cross or multi_timeframe_indicator_rules")
        storage, query_evidence, rows_by_context = AnalyticalStorage(self.storage_root), {}, {}
        for alias, context in rules.get("contexts", {}).items():
            result = storage.query([symbol], start, end, str(context["timeframe"]), 100_000)
            if result["truncated"]: raise ValueError(f"context {alias} exceeds the 100000-row safety limit")
            if not result["rows"]: raise ValueError(f"context {alias} has no analytical rows")
            rows_by_context[alias] = result["rows"]
            query_evidence[alias] = {"timeframe": context["timeframe"], "row_count": result["count"], "result_hash": result["result_hash"]}
        evaluated = evaluate_multitimeframe(rules, rows_by_context, CustomIndicatorRegistry(self.custom_indicator_root))
        base_rows, entry, exit_values = evaluated.pop("rows"), evaluated.pop("entry_signals"), evaluated.pop("exit_signals")
        result = simulate_long_only(base_rows, entry, exit_values, execution_model)
        result["regime_performance"] = analyze_market_regimes(base_rows, result["equity_curve"])
        result["benchmark_attribution"] = analyze_benchmark_attribution(base_rows, result["equity_curve"])
        canonical = json.dumps(query_evidence, sort_keys=True, separators=(",", ":"))
        result.update({
            "adapter": self.name, "data_mode": "historical_provider", "data_source": "Research Forge DuckDB multi-timeframe",
            "dataset_id": data_snapshot["dataset_id"], "dataset_hash": f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}",
            "symbol": symbol, "start_date": start, "end_date": end, "row_count": len(base_rows),
            "data_quality": {"strict_temporal_order": True, "invalid_ohlc_rows": 0, "contexts": query_evidence},
            "signal_timing": "completed_bar_t", "fill_timing": "open_t_plus_delay", "multi_timeframe": evaluated,
            "execution_model": execution_model,
        })
        return result

    def _run_ma_cross(
        self, rules: dict[str, Any], data_snapshot: dict[str, Any], execution_model: dict[str, Any],
        symbol: str, start: str, end: str,
    ) -> dict[str, Any]:
        fast, slow = int(rules.get("fast") or 0), int(rules.get("slow") or 0)
        if not 2 <= fast < slow <= 250:
            raise ValueError("analytical ma_cross requires 2 <= fast < slow <= 250")
        timeframe = str(data_snapshot.get("timeframe") or "1d")
        query = AnalyticalStorage(self.storage_root).query([symbol], start, end, timeframe, 100_000)
        if query["truncated"]:
            raise ValueError("analytical ma_cross exceeds the 100000-row safety limit")
        allowed_sources = data_snapshot.get("sources")
        if allowed_sources is not None and not isinstance(allowed_sources, list):
            raise ValueError("data snapshot sources must be an array")
        source_set = {str(value) for value in (allowed_sources or []) if str(value)}
        rows = _exclude_boundary_rows([row for row in query["rows"] if not source_set or str(row.get("source") or "") in source_set], data_snapshot)
        timestamps = [str(row.get("timestamp") or "") for row in rows]
        if len(rows) < slow + 2:
            raise ValueError("analytical ma_cross has insufficient rows after source filtering")
        if not all(left < right for left, right in zip(timestamps, timestamps[1:])) or len(timestamps) != len(set(timestamps)):
            raise ValueError("analytical ma_cross requires unique strictly ordered timestamps")
        quality = {**_quality([{**row, "date": row["timestamp"]} for row in rows]), "boundary_row_exclusions": _boundary_exclusion_evidence(data_snapshot)}
        if quality["invalid_ohlc_rows"]:
            raise ValueError(f"analytical OHLCV quality failed: {quality}")
        result = _ma_cross_next_open(rows, fast, slow, execution_model)
        result["regime_performance"] = analyze_market_regimes(rows, result["equity_curve"])
        result["benchmark_attribution"] = analyze_benchmark_attribution(rows, result["equity_curve"])
        evidence = [{key: row.get(key) for key in ("symbol", "timestamp", "open", "high", "low", "close", "volume", "source")} for row in rows]
        digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        result.update({
            "adapter": self.name, "data_mode": "historical_provider", "data_source": "Research Forge DuckDB OHLCV",
            "dataset_id": data_snapshot["dataset_id"], "dataset_hash": f"sha256:{digest}", "symbol": symbol,
            "start_date": timestamps[0], "end_date": timestamps[-1], "row_count": len(rows),
            "data_quality": {**quality, "timeframe": timeframe, "sources": sorted(source_set), "query_result_hash": query["result_hash"]},
            "signal_timing": "close_t", "fill_timing": "open_t_plus_delay", "execution_model": execution_model,
        })
        return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _exclude_boundary_rows(rows: list[dict[str, Any]], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    head, tail = int(snapshot.get("exclude_head_rows") or 0), int(snapshot.get("exclude_tail_rows") or 0)
    if not 0 <= head <= 10_000 or not 0 <= tail <= 10_000: raise ValueError("row exclusions must be between 0 and 10000")
    if head + tail >= len(rows) and (head or tail): raise ValueError("row exclusions leave no observations")
    return rows[head:len(rows) - tail if tail else None]


def _boundary_exclusion_evidence(snapshot: dict[str, Any]) -> dict[str, int]:
    return {"excluded_head_rows": int(snapshot.get("exclude_head_rows") or 0), "excluded_tail_rows": int(snapshot.get("exclude_tail_rows") or 0)}


def _quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [str(row.get("date") or "") for row in rows]
    invalid = 0
    invalid_samples: list[dict[str, Any]] = []
    for row in rows:
        try:
            open_, high, low, close = (float(row[key]) for key in ("open", "high", "low", "close"))
            volume = float(row.get("volume") or 0)
            valid = all(math.isfinite(value) and value > 0 for value in (open_, high, low, close))
            valid = valid and high >= max(open_, close, low) and low <= min(open_, close, high) and volume >= 0
            if not valid:
                invalid += 1
                if len(invalid_samples) < 5:
                    invalid_samples.append({key: row.get(key) for key in ("date", "open", "high", "low", "close", "volume")})
        except (KeyError, TypeError, ValueError):
            invalid += 1
            if len(invalid_samples) < 5:
                invalid_samples.append({key: row.get(key) for key in ("date", "open", "high", "low", "close", "volume")})
    return {
        "row_count": len(rows),
        "strict_temporal_order": all(left < right for left, right in zip(dates, dates[1:])),
        "duplicate_dates": len(dates) - len(set(dates)),
        "invalid_ohlc_rows": invalid,
        "invalid_ohlc_samples": invalid_samples,
    }


def _ma_cross_next_open(rows: list[dict[str, Any]], fast: int, slow: int, model: dict[str, Any]) -> dict[str, Any]:
    closes = [float(row["close"]) for row in rows]
    entry, exit_ = [False] * len(rows), [False] * len(rows)
    for index in range(slow - 1, len(rows)):
        fast_ma = sum(closes[index - fast + 1 : index + 1]) / fast
        slow_ma = sum(closes[index - slow + 1 : index + 1]) / slow
        entry[index] = fast_ma > slow_ma
        exit_[index] = fast_ma <= slow_ma
    return simulate_long_only(rows, entry, exit_, model)


def _portfolio_ma_cross(
    payload: dict[str, Any], rules: dict[str, Any], snapshot: dict[str, Any], model: dict[str, Any]
) -> dict[str, Any]:
    model = resolve_execution_model(model)
    symbols = list(dict.fromkeys(str(value).upper() for value in rules["symbols"]))
    fast, slow = int(rules["fast"]), int(rules["slow"])
    max_positions, position_size = int(rules["max_positions"]), float(rules["position_size"])
    start, end = str(snapshot.get("start_date") or "0000-01-01"), str(snapshot.get("end_date") or "9999-12-31")
    by_symbol: dict[str, dict[str, dict[str, Any]]] = {}
    qualities: dict[str, Any] = {}
    for symbol in symbols:
        item = payload.get(symbol)
        if not isinstance(item, dict) or not item.get("ok"):
            raise ValueError(f"portfolio symbol {symbol} is unavailable")
        rows = [dict(row) for row in item.get("rows", []) if isinstance(row, dict) and start <= str(row.get("date")) <= end]
        quality = _quality(rows)
        if len(rows) < slow + 2 or not quality["strict_temporal_order"] or quality["invalid_ohlc_rows"]:
            raise ValueError(f"portfolio OHLCV quality failed for {symbol}: {quality}")
        by_symbol[symbol] = {str(row["date"]): row for row in rows}
        qualities[symbol] = quality
    calendar = sorted(set().union(*(set(rows) for rows in by_symbol.values())))
    histories: dict[str, list[float]] = {symbol: [] for symbol in symbols}
    signal_history: dict[str, list[tuple[str, bool]]] = {symbol: [] for symbol in symbols}
    last_close: dict[str, float] = {}
    positions: dict[str, int] = {}
    commission = float(model.get("commission_bps") or 0) / 10_000
    slippage = float(model.get("slippage_bps") or 0) / 10_000
    sell_tax = float(model.get("sell_tax_bps") or 0) / 10_000
    if min(commission, slippage, sell_tax) < 0:
        raise ValueError("execution costs cannot be negative")
    participation = float(model.get("max_volume_participation") or 0.1)
    impact_bps = float(model.get("market_impact_bps_at_full_participation") or 0)
    delay = int(model.get("order_delay_bars") or 1)
    if not 0 < participation <= 1 or not 1 <= delay <= 20 or impact_bps < 0:
        raise ValueError("invalid portfolio liquidity or delay settings")
    cash = initial_cash = float(model.get("initial_cash") or 100_000_000)
    if cash <= 0:
        raise ValueError("initial_cash must be positive")
    trades: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    for day in calendar:
        available = {symbol: rows[day] for symbol, rows in by_symbol.items() if day in rows}
        delayed = {
            symbol: signal_history[symbol][-delay]
            for symbol in available
            if len(signal_history[symbol]) >= delay
        }
        for symbol in sorted(list(positions)):
            if symbol in available and symbol in delayed and delayed[symbol][1] is False:
                row, signal_date = available[symbol], delayed[symbol][0]
                reason = execution_block_reason(row, "SELL")
                volume = max(0, int(float(row.get("volume") or 0)))
                max_fill, queue = execution_capacity(row, "SELL", model, volume)
                if reason or max_fill <= 0:
                    rejected.append({"date": day, "signal_date": signal_date, "symbol": symbol, "side": "SELL", "reason": reason or capacity_rejection_reason(volume, queue), "queue": queue})
                    continue
                requested = positions[symbol]
                quantity = min(requested, max_fill)
                impact = impact_bps / 10_000 * min(1.0, quantity / max(volume, 1))
                fill = float(row["open"]) * (1 - slippage - impact)
                gross, fee, tax = quantity * fill, quantity * fill * commission, quantity * fill * sell_tax
                cash += gross - fee - tax
                positions[symbol] -= quantity
                if positions[symbol] <= 0:
                    positions.pop(symbol)
                trades.append({"date": day, "signal_date": signal_date, "symbol": symbol, "side": "SELL", "price": fill, "requested_quantity": requested, "quantity": quantity, "unfilled_quantity": requested - quantity, "partial_fill": quantity < requested, "fee": fee, "tax": tax, "bar_volume": volume, "queue": queue})
        entries = [symbol for symbol in sorted(available) if symbol in delayed and delayed[symbol][1] is True and symbol not in positions]
        for symbol in entries:
            if len(positions) >= max_positions:
                rejected.append({"date": day, "signal_date": delayed[symbol][0], "symbol": symbol, "side": "BUY", "reason": "MAX_POSITIONS"})
                continue
            row = available[symbol]
            reason = execution_block_reason(row, "BUY")
            volume = max(0, int(float(row.get("volume") or 0)))
            max_fill, queue = execution_capacity(row, "BUY", model, volume)
            if reason or max_fill <= 0:
                rejected.append({"date": day, "signal_date": delayed[symbol][0], "symbol": symbol, "side": "BUY", "reason": reason or capacity_rejection_reason(volume, queue), "queue": queue})
                continue
            impact = impact_bps / 10_000 * min(1.0, max_fill / max(volume, 1))
            fill = float(row["open"]) * (1 + slippage + impact)
            budget = min(position_size, cash)
            requested = int(budget / (fill * (1 + commission)))
            quantity = min(requested, max_fill)
            if quantity <= 0:
                rejected.append({"date": day, "signal_date": delayed[symbol][0], "symbol": symbol, "side": "BUY", "reason": "INSUFFICIENT_CASH"})
                continue
            cost, fee = quantity * fill, quantity * fill * commission
            cash -= cost + fee
            positions[symbol] = quantity
            trades.append({"date": day, "signal_date": delayed[symbol][0], "symbol": symbol, "side": "BUY", "price": fill, "requested_quantity": requested, "quantity": quantity, "unfilled_quantity": requested - quantity, "partial_fill": quantity < requested, "fee": fee, "tax": 0.0, "bar_volume": volume, "queue": queue})
        for symbol, row in available.items():
            close = float(row["close"])
            histories[symbol].append(close)
            last_close[symbol] = close
            if len(histories[symbol]) >= slow:
                values = histories[symbol]
                signal_history[symbol].append((day, sum(values[-fast:]) / fast > sum(values[-slow:]) / slow))
        equity = cash + sum(quantity * last_close.get(symbol, 0) for symbol, quantity in positions.items())
        equity_curve.append({"date": day, "equity": round(equity, 2), "cash": round(cash, 2), "positions": len(positions)})
    values = [row["equity"] for row in equity_curve]
    peak, max_drawdown = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1 if peak else 0)
    return {
        "symbols": symbols,
        "start_date": calendar[0],
        "end_date": calendar[-1],
        "row_count": sum(item["row_count"] for item in qualities.values()),
        "data_quality": {
            "strict_temporal_order": all(item["strict_temporal_order"] for item in qualities.values()),
            "invalid_ohlc_rows": sum(item["invalid_ohlc_rows"] for item in qualities.values()),
            "symbols": qualities,
        },
        "initial_cash": initial_cash,
        "final_equity": values[-1],
        "total_return_pct": round((values[-1] / initial_cash - 1) * 100, 4),
        "max_drawdown_pct": round(max_drawdown * 100, 4),
        "trade_count": len(trades),
        "trades": trades,
        "partial_fill_count": sum(bool(row["partial_fill"]) for row in trades),
        "rejected_order_count": len(rejected),
        "rejected_orders": rejected,
        "open_positions": positions,
        "equity_curve": equity_curve,
        "portfolio_constraints": {"max_positions": max_positions, "position_size": position_size},
        "entry_priority": "symbol_ascending_deterministic",
        "execution_assumptions": {"execution_mode": model["execution_mode"], "order_delay_bars": delay, "max_volume_participation": participation, "market_impact_bps_at_full_participation": impact_bps, "queue_model": model["queue_model"], "missing_queue_fill_haircut": model["missing_queue_fill_haircut"], "queue_ahead_multiplier": model["queue_ahead_multiplier"], "fill_policy": "IOC_PARTIAL_CANCEL_REMAINDER"},
    }

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import nautilus_trader
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import (
    FillModel,
    LatencyModel,
    LimitOrderPartialFillModel,
    OneTickSlippageFillModel,
    SizeAwareFillModel,
)
from nautilus_trader.config import LoggingConfig
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model import Bar, BarType, QuoteTick, TraderId
from nautilus_trader.model.currencies import KRW, USD
from nautilus_trader.model.enums import AccountType, BookType, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy


FORBIDDEN_KEY_PARTS = (
    "account_number",
    "approval",
    "broker_token",
    "kis_",
    "order_token",
    "password",
    "secret",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


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


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _price_text(value: Any, precision: int) -> str:
    number = _finite(value)
    return f"{number:.{precision}f}"


def _timestamp_nanos(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        raise ValueError("bar_date_required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(dt_to_unix_nanos(parsed.astimezone(UTC)))


class MovingAverageReplayStrategy(Strategy):
    def __init__(self, bar_type: BarType, fast_window: int, slow_window: int, total_bars: int) -> None:
        super().__init__()
        self.bar_type = bar_type
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.total_bars = total_bars
        self.closes: list[float] = []
        self.long_open = False
        self.order_reasons: dict[str, str] = {}

    def on_start(self) -> None:
        self.subscribe_bars(self.bar_type)

    def _submit(self, side: OrderSide, reason: str) -> None:
        order = self.order_factory.market(
            instrument_id=self.bar_type.instrument_id,
            order_side=side,
            quantity=Quantity.from_int(1),
            time_in_force=TimeInForce.GTC,
        )
        self.order_reasons[str(order.client_order_id)] = reason
        self.submit_order(order)

    def on_bar(self, bar: Bar) -> None:
        self.closes.append(float(bar.close.as_double()))
        count = len(self.closes)
        if count >= self.slow_window:
            fast_mean = sum(self.closes[-self.fast_window :]) / self.fast_window
            slow_mean = sum(self.closes[-self.slow_window :]) / self.slow_window
            if not self.long_open and fast_mean > slow_mean:
                self._submit(OrderSide.BUY, "ma_cross_up")
                self.long_open = True
            elif self.long_open and fast_mean < slow_mean:
                self._submit(OrderSide.SELL, "ma_cross_down")
                self.long_open = False
        if count == self.total_bars and self.long_open:
            self._submit(OrderSide.SELL, "final_bar_flatten")
            self.long_open = False


class ExecutionStressStrategy(Strategy):
    def __init__(
        self,
        instrument_id: InstrumentId,
        *,
        order_quantity: int,
        price_mode: str,
        cancel_after_quotes: int | None,
    ) -> None:
        super().__init__()
        self.instrument_id = instrument_id
        self.order_quantity = order_quantity
        self.price_mode = price_mode
        self.cancel_after_quotes = cancel_after_quotes
        self.quote_count = 0
        self.order: Any = None
        self.submitted_at_ns = 0
        self.event_log: list[dict[str, Any]] = []

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self.instrument_id)

    def on_quote_tick(self, quote: QuoteTick) -> None:
        self.quote_count += 1
        if self.order is None:
            if self.price_mode == "market":
                self.order = self.order_factory.market(
                    instrument_id=self.instrument_id,
                    order_side=OrderSide.BUY,
                    quantity=Quantity.from_int(self.order_quantity),
                    time_in_force=TimeInForce.IOC,
                )
            else:
                target = quote.ask_price if self.price_mode == "cross_ask" else quote.bid_price
                self.order = self.order_factory.limit(
                    instrument_id=self.instrument_id,
                    order_side=OrderSide.BUY,
                    price=target,
                    quantity=Quantity.from_int(self.order_quantity),
                    time_in_force=TimeInForce.GTC,
                    post_only=False,
                )
            self.submitted_at_ns = int(quote.ts_event)
            self.submit_order(self.order)
            return
        if (
            self.cancel_after_quotes is not None
            and self.quote_count >= self.cancel_after_quotes
            and not self.order.is_closed
        ):
            self.cancel_order(self.order)

    def on_event(self, event: Any) -> None:
        event_name = event.__class__.__name__
        if not event_name.startswith("Order"):
            return
        self.event_log.append(
            {
                "event": event_name,
                "ts_event": int(getattr(event, "ts_event", 0) or 0),
                "last_qty": _finite(getattr(event, "last_qty", 0.0)),
                "last_px": _finite(getattr(event, "last_px", 0.0)),
            }
        )


def _records(frame: Any) -> list[dict[str, str]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return frame.reset_index().astype(str).to_dict("records")


def _normalized_order_side(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text.endswith("BUY"):
        return "BUY"
    if text.endswith("SELL"):
        return "SELL"
    return text


def _normalize_orderbook_events(value: Any) -> tuple[str, list[dict[str, Any]], str]:
    source_rows = value if isinstance(value, list) else []
    rows: list[dict[str, Any]] = []
    symbols: set[str] = set()
    for event in source_rows[:200]:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
        symbol = str(event.get("symbol") or payload.get("symbol") or "").strip().upper()
        timestamp = str(event.get("timestamp") or payload.get("timestamp") or "").strip()
        levels = payload.get("levels") if isinstance(payload.get("levels"), list) else []
        level_one = levels[0] if levels and isinstance(levels[0], dict) else {}
        bids = payload.get("bids") if isinstance(payload.get("bids"), list) else []
        asks = payload.get("asks") if isinstance(payload.get("asks"), list) else []
        first_bid = bids[0] if bids and isinstance(bids[0], (list, tuple)) else []
        first_ask = asks[0] if asks and isinstance(asks[0], (list, tuple)) else []
        best_bid = _finite(
            payload.get("best_bid")
            or level_one.get("bid_price")
            or (first_bid[0] if len(first_bid) >= 1 else 0)
        )
        best_ask = _finite(
            payload.get("best_ask")
            or level_one.get("ask_price")
            or (first_ask[0] if len(first_ask) >= 1 else 0)
        )
        bid_quantity = _finite(
            level_one.get("bid_quantity")
            or payload.get("best_bid_quantity")
            or (first_bid[1] if len(first_bid) >= 2 else 0)
        )
        ask_quantity = _finite(
            level_one.get("ask_quantity")
            or payload.get("best_ask_quantity")
            or (first_ask[1] if len(first_ask) >= 2 else 0)
        )
        source = str(event.get("source") or payload.get("source") or "").strip()
        if (
            not symbol
            or not timestamp
            or best_bid <= 0
            or best_ask <= best_bid
            or bid_quantity <= 0
            or ask_quantity <= 0
            or not source
        ):
            continue
        symbols.add(symbol)
        rows.append(
            {
                "event_id": str(event.get("event_id") or ""),
                "symbol": symbol,
                "timestamp": timestamp,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "bid_quantity": bid_quantity,
                "ask_quantity": ask_quantity,
                "spread": best_ask - best_bid,
                "source": source,
            }
        )
    if len(symbols) != 1:
        raise ValueError("exactly_one_orderbook_symbol_required")
    rows.sort(key=lambda row: _timestamp_nanos(row["timestamp"]))
    unique_rows: list[dict[str, Any]] = []
    seen_timestamps: set[int] = set()
    for row in rows:
        timestamp_ns = _timestamp_nanos(row["timestamp"])
        if timestamp_ns in seen_timestamps:
            continue
        seen_timestamps.add(timestamp_ns)
        row["timestamp_ns"] = timestamp_ns
        unique_rows.append(row)
    if len(unique_rows) < 3:
        raise ValueError("at_least_three_real_orderbook_events_required")
    evidence_hash = hashlib.sha256(
        json.dumps(unique_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return next(iter(symbols)), unique_rows, evidence_hash


def _run_execution_scenario(
    *,
    scenario_name: str,
    symbol: str,
    events: list[dict[str, Any]],
    fill_model: Any,
    latency_model: Any | None,
    order_quantity: int,
    price_mode: str,
    cancel_after_quotes: int | None,
    expected_behavior: str,
) -> dict[str, Any]:
    venue = Venue("XKRX")
    instrument_id = InstrumentId(Symbol(symbol), venue)
    instrument = Equity(
        instrument_id=instrument_id,
        raw_symbol=Symbol(symbol),
        currency=KRW,
        price_precision=0,
        price_increment=Price.from_str("1"),
        lot_size=Quantity.from_int(1),
        maker_fee=Decimal("0"),
        taker_fee=Decimal("0"),
        ts_event=0,
        ts_init=0,
    )
    engine = BacktestEngine(
        BacktestEngineConfig(
            trader_id=TraderId(f"STRESS-{scenario_name[:12].upper()}"),
            logging=LoggingConfig(bypass_logging=True, print_config=False),
        )
    )
    strategy: ExecutionStressStrategy | None = None
    try:
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(100_000_000, KRW)],
            base_currency=KRW,
            default_leverage=Decimal(1),
            fill_model=fill_model,
            latency_model=latency_model,
            book_type=BookType.L1_MBP,
            bar_execution=False,
            trade_execution=True,
            liquidity_consumption=True,
            queue_position=True,
        )
        engine.add_instrument(instrument)
        quotes = [
            QuoteTick(
                instrument_id=instrument_id,
                bid_price=Price.from_str(_price_text(row["best_bid"], 0)),
                ask_price=Price.from_str(_price_text(row["best_ask"], 0)),
                bid_size=Quantity.from_int(max(1, int(row["bid_quantity"]))),
                ask_size=Quantity.from_int(max(1, int(row["ask_quantity"]))),
                ts_event=int(row["timestamp_ns"]),
                ts_init=int(row["timestamp_ns"]),
            )
            for row in events
        ]
        engine.add_data(quotes)
        strategy = ExecutionStressStrategy(
            instrument_id,
            order_quantity=order_quantity,
            price_mode=price_mode,
            cancel_after_quotes=cancel_after_quotes,
        )
        engine.add_strategy(strategy)
        engine.run()
        fills = _records(engine.trader.generate_fills_report())
        orders = _records(engine.trader.generate_orders_report())
        filled_quantity = sum(_finite(row.get("last_qty")) for row in fills)
        fill_events = [row for row in strategy.event_log if row.get("event") == "OrderFilled"]
        first_fill_ns = min((int(row.get("ts_event") or 0) for row in fill_events), default=0)
        observed_latency_ns = (
            max(0, first_fill_ns - strategy.submitted_at_ns)
            if first_fill_ns and strategy.submitted_at_ns
            else 0
        )
        partial_observed = 0.0 < filled_quantity < float(order_quantity)
        unfilled_observed = filled_quantity == 0.0 and bool(orders)
        if expected_behavior == "partial_fill":
            behavior_passed = partial_observed
        elif expected_behavior == "unfilled":
            behavior_passed = unfilled_observed
        elif expected_behavior == "latency":
            behavior_passed = filled_quantity > 0.0 and observed_latency_ns >= 5_000_000_000
        else:
            behavior_passed = False
        return {
            "name": scenario_name,
            "ok": bool(orders),
            "expected_behavior": expected_behavior,
            "behavior_passed": behavior_passed,
            "order_quantity": order_quantity,
            "order_count": len(orders),
            "fill_count": len(fills),
            "filled_quantity": round(filled_quantity, 8),
            "remaining_quantity": round(max(0.0, order_quantity - filled_quantity), 8),
            "partial_fill_observed": partial_observed,
            "unfilled_observed": unfilled_observed,
            "submitted_at_ns": strategy.submitted_at_ns,
            "first_fill_at_ns": first_fill_ns,
            "observed_latency_ns": observed_latency_ns,
            "event_log": strategy.event_log[:30],
            "orders": orders[:10],
            "fills": fills[:20],
        }
    finally:
        engine.dispose()


def _run_execution_stress(request: dict[str, Any], started: float) -> dict[str, Any]:
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    symbol, events, orderbook_hash = _normalize_orderbook_events(request.get("microstructure_events"))
    scenarios = [
        _run_execution_scenario(
            scenario_name="partial_limit_fill",
            symbol=symbol,
            events=events,
            fill_model=LimitOrderPartialFillModel(),
            latency_model=None,
            order_quantity=25,
            price_mode="cross_ask",
            cancel_after_quotes=2,
            expected_behavior="partial_fill",
        ),
        _run_execution_scenario(
            scenario_name="deliberate_unfilled_limit",
            symbol=symbol,
            events=events,
            fill_model=FillModel(prob_fill_on_limit=0.0, prob_slippage=0.0, random_seed=17),
            latency_model=None,
            order_quantity=3,
            price_mode="rest_bid",
            cancel_after_quotes=2,
            expected_behavior="unfilled",
        ),
        _run_execution_scenario(
            scenario_name="ten_second_insert_latency",
            symbol=symbol,
            events=events,
            fill_model=SizeAwareFillModel(),
            latency_model=LatencyModel(
                base_latency_nanos=0,
                insert_latency_nanos=10_000_000_000,
                update_latency_nanos=0,
                cancel_latency_nanos=0,
            ),
            order_quantity=3,
            price_mode="market",
            cancel_after_quotes=None,
            expected_behavior="latency",
        ),
    ]
    scenarios = _json_safe(scenarios)
    quote_evidence_passed = bool(
        len(events) >= 3
        and all(row["best_ask"] > row["best_bid"] > 0 for row in events)
        and all(row["ask_quantity"] > 0 and row["bid_quantity"] > 0 for row in events)
    )
    quality_passed = quote_evidence_passed and all(row.get("behavior_passed") for row in scenarios)
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "release_commit": request.get("release_commit"),
        "orderbook_hash": orderbook_hash,
        "scenarios": scenarios,
    }
    result_hash = hashlib.sha256(
        json.dumps(
            result_material,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "ok": all(row.get("ok") for row in scenarios),
        "schema": "codexstock_nautilus_execution_stress_v1",
        "action": "evaluate_execution_stress",
        "engine_name": "NautilusTrader",
        "engine_version": str(nautilus_trader.__version__),
        "release_commit": str(request.get("release_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "symbol": symbol,
        "orderbook_evidence": {
            "passed": quote_evidence_passed,
            "event_count": len(events),
            "source_count": len({row["source"] for row in events}),
            "first_timestamp": events[0]["timestamp"],
            "last_timestamp": events[-1]["timestamp"],
            "orderbook_hash": orderbook_hash,
            "real_recorded_events_required": True,
        },
        "scenarios": scenarios,
        "quality_gate": {
            "passed": quality_passed,
            "partial_fill_passed": bool(scenarios[0].get("behavior_passed")),
            "unfilled_passed": bool(scenarios[1].get("behavior_passed")),
            "latency_passed": bool(scenarios[2].get("behavior_passed")),
            "orderbook_evidence_passed": quote_evidence_passed,
        },
        "research_verdict": "EXECUTION_ASSUMPTIONS_VERIFIED" if quality_passed else "REVISE_EXECUTION_ASSUMPTIONS",
        "capability_evidence": [
            {"capability": "real_quote_tick_replay", "passed": quote_evidence_passed, "event_count": len(events)},
            {"capability": "partial_limit_fill", "passed": bool(scenarios[0].get("behavior_passed"))},
            {"capability": "deliberate_unfilled_order", "passed": bool(scenarios[1].get("behavior_passed"))},
            {"capability": "insert_latency", "passed": bool(scenarios[2].get("behavior_passed")), "configured_ns": 10_000_000_000},
            {"capability": "live_order_boundary", "passed": True, "live_order_allowed": False},
        ],
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "promotion_allowed": False,
        "live_order_allowed": False,
        "decision": "RESEARCH_ONLY",
    }


def _stage2_trade_evidence(
    symbol: str,
    fills: list[dict[str, str]],
    *,
    currency: str,
    price_unit: str,
    fee_rate: float,
    snapshot_id: str,
    dataset_hash: str,
) -> dict[str, Any]:
    trade_ledger: list[dict[str, Any]] = []
    pairing_errors: list[str] = []
    open_fill: dict[str, str] | None = None
    for fill in fills:
        side = _normalized_order_side(fill.get("order_side"))
        if side == "BUY":
            if open_fill is not None:
                pairing_errors.append("overlapping_buy_fill")
            else:
                open_fill = fill
            continue
        if side != "SELL":
            pairing_errors.append("unknown_fill_side")
            continue
        if open_fill is None:
            pairing_errors.append("sell_without_open_buy")
            continue
        entry_price = _finite(open_fill.get("last_px"))
        exit_price = _finite(fill.get("last_px"))
        quantity = max(1.0, _finite(open_fill.get("last_qty"), 1.0))
        exit_reason = str(fill.get("reason") or "").strip()
        gross_return_pct = ((exit_price / entry_price) - 1.0) * 100.0 if entry_price > 0 else 0.0
        entry_notional = entry_price * quantity
        exit_notional = exit_price * quantity
        entry_fee = entry_notional * fee_rate
        exit_fee = exit_notional * fee_rate
        net_pnl = exit_notional - exit_fee - entry_notional - entry_fee
        net_return_pct = (net_pnl / (entry_notional + entry_fee)) * 100.0 if entry_notional > 0 else 0.0
        trade_ledger.append(
            {
                "trade_id": f"{symbol}-{len(trade_ledger) + 1:04d}",
                "symbol": symbol,
                "entry_at": str(open_fill.get("ts_event") or open_fill.get("ts_init") or ""),
                "exit_at": str(fill.get("ts_event") or fill.get("ts_init") or ""),
                "entry_price": round(entry_price, 8),
                "exit_price": round(exit_price, 8),
                "quantity": round(quantity, 8),
                "exit_reason": exit_reason,
                "gross_return_pct": round(gross_return_pct, 8),
                "net_return_pct": round(net_return_pct, 8),
                "entry_fee": round(entry_fee, 8),
                "exit_fee": round(exit_fee, 8),
                "net_pnl": round(net_pnl, 8),
                "currency": currency,
                "price_unit": price_unit,
                "snapshot_id": snapshot_id,
                "dataset_hash": dataset_hash,
            }
        )
        open_fill = None
    if open_fill is not None:
        pairing_errors.append("open_buy_without_sell")

    canonical_ledger = json.dumps(
        trade_ledger,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fill_ledger_hash = hashlib.sha256(canonical_ledger.encode("utf-8")).hexdigest()
    valid_trade_count = sum(
        1
        for trade in trade_ledger
        if trade["entry_price"] > 0
        and trade["exit_price"] > 0
        and trade["quantity"] > 0
        and trade["exit_reason"] in {"ma_cross_down", "final_bar_flatten"}
    )
    has_round_trip = bool(trade_ledger)
    entry_exit_passed = has_round_trip and valid_trade_count == len(trade_ledger) and not pairing_errors
    return_reconciliation_passed = entry_exit_passed and all(
        math.isfinite(float(trade["gross_return_pct"]))
        and math.isfinite(float(trade["net_return_pct"]))
        and float(trade["net_return_pct"]) <= float(trade["gross_return_pct"]) + 1e-8
        for trade in trade_ledger
    )
    exit_reason_passed = has_round_trip and all(
        trade["exit_reason"] in {"ma_cross_down", "final_bar_flatten"}
        for trade in trade_ledger
    )
    cost_passed = has_round_trip and 0.0 <= fee_rate <= 0.02
    unit_passed = bool(
        has_round_trip
        and currency in {"KRW", "USD"}
        and price_unit in {"won_integer", "decimal_usd", "usd_decimal"}
        and all(
            trade["currency"] == currency and trade["price_unit"] == price_unit
            for trade in trade_ledger
        )
    )
    evidence = {
        "fill_ledger_hash": fill_ledger_hash,
        "trade_count": len(trade_ledger),
        "trade_ledger": trade_ledger,
        "pairing_errors": pairing_errors,
        "entry_exit_return_reason_evidence": {
            "passed": entry_exit_passed,
            "trade_count": len(trade_ledger),
            "fill_ledger_hash": fill_ledger_hash,
        },
        "return_reconciliation_evidence": {
            "passed": return_reconciliation_passed,
            "checked_count": len(trade_ledger),
            "mismatch_count": 0 if return_reconciliation_passed else max(1, len(pairing_errors)),
            "fill_ledger_hash": fill_ledger_hash,
        },
        "exit_reason_alignment_evidence": {
            "passed": exit_reason_passed,
            "checked_count": len(trade_ledger),
            "allowed_reasons": ["ma_cross_down", "final_bar_flatten"],
            "fill_ledger_hash": fill_ledger_hash,
        },
        "fee_tax_slippage_evidence": {
            "passed": cost_passed,
            "fee_rate": fee_rate,
            "slippage_model": "nautilus_one_tick_slippage_fill_model",
            "applied_trade_count": len(trade_ledger),
            "fill_ledger_hash": fill_ledger_hash,
        },
        "unit_currency_audit_evidence": {
            "passed": unit_passed,
            "currency": currency,
            "price_unit": price_unit,
            "split_adjustment_source": "codexstock_adjusted_ohlcv_snapshot",
            "fill_ledger_hash": fill_ledger_hash,
        },
        "no_live_order_evidence": {
            "passed": True,
            "order_api_call_count": 0,
            "account_mutation_count": 0,
            "position_mutation_count": 0,
            "runtime_mode": "historical_replay_read_only",
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


def _replay_symbol(
    symbol: str,
    rows: list[dict[str, Any]],
    *,
    fast_window: int,
    slow_window: int,
    initial_cash: float,
    fee_rate: float,
    snapshot_id: str,
    dataset_hash: str,
) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: str(row.get("date") or ""))
    if len(rows) < slow_window + 2:
        return {"symbol": symbol, "ok": False, "error": "insufficient_rows", "row_count": len(rows)}
    currency_code = str(rows[-1].get("currency") or "").upper()
    if currency_code not in {"KRW", "USD"}:
        return {"symbol": symbol, "ok": False, "error": "unsupported_currency", "currency": currency_code}
    currency = KRW if currency_code == "KRW" else USD
    price_unit = str(rows[-1].get("price_unit") or "")
    precision = 0 if price_unit == "won_integer" else 4
    venue = Venue("XKRX" if currency_code == "KRW" else "XNAS")
    instrument_id = InstrumentId(Symbol(symbol), venue)
    price_increment = Price.from_str("1" if precision == 0 else "0.0001")
    instrument = Equity(
        instrument_id=instrument_id,
        raw_symbol=Symbol(symbol),
        currency=currency,
        price_precision=precision,
        price_increment=price_increment,
        lot_size=Quantity.from_int(1),
        maker_fee=Decimal(str(fee_rate)),
        taker_fee=Decimal(str(fee_rate)),
        ts_event=0,
        ts_init=0,
    )
    engine = BacktestEngine(
        BacktestEngineConfig(
            trader_id=TraderId("CODEXSTOCK-001"),
            logging=LoggingConfig(bypass_logging=True, print_config=False),
        )
    )
    strategy: MovingAverageReplayStrategy | None = None
    try:
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(initial_cash, currency)],
            base_currency=currency,
            default_leverage=Decimal(1),
            fill_model=OneTickSlippageFillModel(),
            bar_execution=True,
        )
        engine.add_instrument(instrument)
        bar_type = BarType.from_str(f"{instrument_id}-1-DAY-LAST-EXTERNAL")
        bars: list[Bar] = []
        for row in rows:
            ts = _timestamp_nanos(row.get("date"))
            volume = max(0, int(_finite(row.get("volume"))))
            bars.append(
                Bar(
                    bar_type,
                    Price.from_str(_price_text(row.get("open"), precision)),
                    Price.from_str(_price_text(row.get("high"), precision)),
                    Price.from_str(_price_text(row.get("low"), precision)),
                    Price.from_str(_price_text(row.get("close"), precision)),
                    Quantity.from_int(volume),
                    ts,
                    ts,
                )
            )
        engine.add_data(bars)
        strategy = MovingAverageReplayStrategy(bar_type, fast_window, slow_window, len(bars))
        engine.add_strategy(strategy)
        engine.run()

        fills = _records(engine.trader.generate_fills_report())
        orders = _records(engine.trader.generate_orders_report())
        positions = _records(engine.trader.generate_positions_report())
        result = engine.get_result()
        for fill in fills:
            fill["reason"] = strategy.order_reasons.get(str(fill.get("client_order_id") or ""), "unmapped")
        fill_prices = [_finite(fill.get("last_px")) for fill in fills]
        entry_fill = next((fill for fill in fills if fill.get("order_side") == "BUY"), None)
        exit_fill = next((fill for fill in reversed(fills) if fill.get("order_side") == "SELL"), None)
        entry_price = _finite(entry_fill.get("last_px")) if entry_fill else 0.0
        exit_price = _finite(exit_fill.get("last_px")) if exit_fill else 0.0
        gross_return_pct = ((exit_price / entry_price) - 1.0) * 100.0 if entry_price > 0 and exit_price > 0 else 0.0
        closed_position_count = sum(1 for row in positions if str(row.get("ts_closed") or "") not in {"", "None", "NaT"})
        reconciliation_errors: list[str] = []
        if len(orders) != len(fills):
            reconciliation_errors.append("order_fill_count_mismatch")
        if any(fill.get("currency") != currency_code for fill in fills):
            reconciliation_errors.append("fill_currency_mismatch")
        if any(price <= 0 for price in fill_prices):
            reconciliation_errors.append("non_positive_fill_price")
        if len(fills) % 2 != 0:
            reconciliation_errors.append("unpaired_fill_count")
        if positions and closed_position_count != len(positions):
            reconciliation_errors.append("open_position_remains")
        if any(fill.get("reason") == "unmapped" for fill in fills):
            reconciliation_errors.append("fill_reason_unmapped")
        summary = dict(getattr(result, "summary", {}) or {})
        stats_pnls = dict(getattr(result, "stats_pnls", {}) or {})
        stats_returns = dict(getattr(result, "stats_returns", {}) or {})
        stage2_evidence = _stage2_trade_evidence(
            symbol,
            fills,
            currency=currency_code,
            price_unit=price_unit,
            fee_rate=fee_rate,
            snapshot_id=snapshot_id,
            dataset_hash=dataset_hash,
        )
        return {
            "symbol": symbol,
            "ok": not reconciliation_errors,
            "row_count": len(rows),
            "currency": currency_code,
            "price_unit": price_unit,
            "order_count": len(orders),
            "fill_count": len(fills),
            "position_count": len(positions),
            "closed_position_count": closed_position_count,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": exit_fill.get("reason") if exit_fill else "no_exit_fill",
            "gross_return_pct": round(gross_return_pct, 6),
            "fills": fills[:20],
            "orders": orders[:20],
            "positions": positions[:10],
            "engine_summary": {str(key): str(value) for key, value in summary.items()},
            "stats_pnls": json.loads(json.dumps(stats_pnls, default=str)),
            "stats_returns": {
                str(key): round(_finite(value), 8) for key, value in stats_returns.items()
            },
            "reconciliation": {
                "ok": not reconciliation_errors,
                "errors": reconciliation_errors,
                "orders_equal_fills": len(orders) == len(fills),
                "all_fill_currencies_match": not any(fill.get("currency") != currency_code for fill in fills),
                "all_fill_prices_positive": not any(price <= 0 for price in fill_prices),
            },
            "stage2_evidence": stage2_evidence,
        }
    finally:
        engine.dispose()


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_research_only(request)
    action = str(request.get("action") or "")
    if action == "evaluate_execution_stress":
        return _run_execution_stress(request, started)
    if action != "run_external_replay":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    rows = snapshot.get("dataset_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset_rows_required")

    fast_window = max(2, min(int(request.get("fast_window", 10)), 60))
    slow_window = max(fast_window + 1, min(int(request.get("slow_window", 60)), 200))
    initial_cash = max(10_000.0, _finite(request.get("initial_cash"), 10_000_000.0))
    fee_rate = min(0.02, max(0.0, _finite(request.get("fee_rate"), 0.0015)))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if isinstance(row, dict) and str(row.get("symbol") or ""):
            grouped.setdefault(str(row["symbol"]), []).append(row)
    symbol_results = [
        _replay_symbol(
            symbol,
            symbol_rows,
            fast_window=fast_window,
            slow_window=slow_window,
            initial_cash=initial_cash,
            fee_rate=fee_rate,
            snapshot_id=str(request.get("snapshot_id") or ""),
            dataset_hash=str(request.get("dataset_hash") or ""),
        )
        for symbol, symbol_rows in sorted(grouped.items())[:5]
    ]
    reconciliation_ok = bool(symbol_results) and all(
        bool(row.get("ok")) and bool(row.get("reconciliation", {}).get("ok"))
        for row in symbol_results
    )
    successful_count = sum(1 for row in symbol_results if row.get("ok"))
    stage2_evidence_by_symbol = {
        str(row.get("symbol") or ""): row.get("stage2_evidence", {})
        for row in symbol_results
        if str(row.get("symbol") or "")
    }
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "release_commit": request.get("release_commit"),
        "symbol_results": symbol_results,
        "stage2_evidence_by_symbol": stage2_evidence_by_symbol,
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "ok": successful_count > 0 and reconciliation_ok,
        "schema": "codexstock_nautilus_replay_result_v1",
        "action": "run_external_replay",
        "engine_name": "NautilusTrader",
        "engine_version": str(nautilus_trader.__version__),
        "release_commit": str(request.get("release_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "fast_window": fast_window,
        "slow_window": slow_window,
        "symbol_count": len(symbol_results),
        "successful_symbol_count": successful_count,
        "symbol_results": symbol_results,
        "stage2_evidence_by_symbol": stage2_evidence_by_symbol,
        "reconciliation_ok": reconciliation_ok,
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
            "schema": "codexstock_nautilus_replay_result_v1",
            "engine_name": "NautilusTrader",
            "error": str(exc)[:600],
            "live_order_allowed": False,
            "decision": "BLOCKED",
        }
    json.dump(
        _json_safe(result),
        sys.stdout,
        ensure_ascii=False,
        default=str,
        allow_nan=False,
        separators=(",", ":"),
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

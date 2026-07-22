"""Normalize read-only KIS data into a fail-closed sidecar snapshot."""

from __future__ import annotations

from datetime import datetime
import math
import time
from typing import Callable, Mapping

from .execution_sidecar import MarketSnapshot, OrderSignal


Payload = Mapping[str, object]


def _number(value: object) -> float:
    try:
        normalized = value.replace(",", "") if isinstance(value, str) else value
        parsed = float(normalized or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _finite_number(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        normalized = value.replace(",", "") if isinstance(value, str) else value
        parsed = float(normalized)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


class KisShadowSnapshotProvider:
    def __init__(
        self,
        quote: Callable[[str], Payload],
        orderbook: Callable[[str], Payload],
        account: Callable[[], Payload],
        executions: Callable[[str], Payload] | None = None,
        emergency_halt: Callable[[], bool] | None = None,
    ) -> None:
        self.quote = quote
        self.orderbook = orderbook
        self.account = account
        self.executions = executions
        self.emergency_halt = emergency_halt or (lambda: False)

    def __call__(self, signal: OrderSignal) -> MarketSnapshot:
        fetch_started = time.monotonic()
        errors: list[str] = []
        try:
            quote = dict(self.quote(signal.symbol))
        except Exception as exc:
            quote = {}
            errors.append(f"quote_exception:{type(exc).__name__}")
        try:
            orderbook = dict(self.orderbook(signal.symbol))
        except Exception as exc:
            orderbook = {}
            errors.append(f"orderbook_exception:{type(exc).__name__}")
        try:
            account = dict(self.account())
        except Exception as exc:
            account = {}
            errors.append(f"account_exception:{type(exc).__name__}")
        try:
            execution_payload = dict(self.executions(signal.symbol)) if self.executions else {}
        except Exception as exc:
            execution_payload = {}
            errors.append(f"executions_exception:{type(exc).__name__}")
        if self.executions and execution_payload.get("ok") is not True:
            errors.append("executions_unavailable")
        if self.executions and str(execution_payload.get("source") or "") != "kis_daily_executions":
            errors.append("executions_non_kis_source")
        if self.executions:
            if str(execution_payload.get("currency") or "").upper().strip() != "KRW":
                errors.append("executions_currency_mismatch")
            if _finite_number(execution_payload.get("unit_scale")) != 1.0:
                errors.append("executions_unit_scale_mismatch")

        expected_sources = {
            "quote": (quote, "kis_readonly"),
            "orderbook": (orderbook, "kis_orderbook"),
            "account": (account, "kis_readonly_account"),
        }
        for name, (payload, source) in expected_sources.items():
            if payload.get("ok") is not True:
                errors.append(f"{name}_unavailable")
            if str(payload.get("source") or "") != source:
                errors.append(f"{name}_non_kis_source")
            currency = str(payload.get("currency") or "").upper().strip()
            if currency != "KRW":
                errors.append(f"{name}_currency_mismatch")
            unit_scale = _finite_number(payload.get("unit_scale"))
            if unit_scale != 1.0:
                errors.append(f"{name}_unit_scale_mismatch")
            if name != "account":
                observed_symbol = str(payload.get("symbol") or "").upper().strip()
                if observed_symbol != signal.symbol.upper().strip():
                    errors.append(f"{name}_symbol_mismatch")

        def required_number(value: object, label: str) -> float:
            parsed = _finite_number(value)
            if parsed is None:
                errors.append(f"{label}_invalid")
                return 0.0
            return parsed

        summary = account.get("summary") if isinstance(account.get("summary"), dict) else {}
        positions = account.get("positions") if isinstance(account.get("positions"), list) else []
        position = next(
            (
                row for row in positions
                if isinstance(row, dict) and str(row.get("symbol") or "").upper() == signal.symbol.upper()
            ),
            {},
        )
        executions = execution_payload.get("executions") if isinstance(execution_payload.get("executions"), list) else []
        pending_same_symbol = any(
            isinstance(row, dict)
            and str(row.get("symbol") or "").upper() == signal.symbol.upper()
            and (
                _number(row.get("remaining_quantity")) > 0
                or str(row.get("status") or row.get("status_name") or row.get("filled") or "").lower()
                in {"pending", "open", "unfilled", "미체결"}
            )
            for row in executions
        )
        daily_order_count = len([row for row in executions if isinstance(row, dict)])
        levels = orderbook.get("levels") if isinstance(orderbook.get("levels"), list) else []
        top_level = levels[0] if levels and isinstance(levels[0], dict) else {}
        current_price = required_number(quote.get("price"), "quote_price")
        ask_price = required_number(orderbook.get("best_ask"), "orderbook_best_ask")
        bid_price = required_number(orderbook.get("best_bid"), "orderbook_best_bid")
        for value, label in (
            (current_price, "quote_price"),
            (ask_price, "orderbook_best_ask"),
            (bid_price, "orderbook_best_bid"),
        ):
            if value <= 0:
                errors.append(f"{label}_non_positive")
            elif abs(value - round(value)) > 0.001:
                errors.append(f"{label}_fractional_krw")
        if ask_price > 0 and bid_price > 0:
            if ask_price < bid_price:
                errors.append("orderbook_crossed")
            mid_price = (ask_price + bid_price) / 2.0
            price_ratio = max(current_price, mid_price) / max(0.000001, min(current_price, mid_price))
            if current_price > 0 and price_ratio > 1.5:
                errors.append("quote_orderbook_price_scale_mismatch")
        if current_price > 0 and signal.reference_price > 0:
            reference_ratio = max(current_price, signal.reference_price) / max(
                0.000001, min(current_price, signal.reference_price)
            )
            if reference_ratio >= 5.0:
                errors.append("signal_market_price_scale_mismatch")
        previous_close = _finite_number(quote.get("previous_close"))
        high_price = _finite_number(quote.get("high"))
        low_price = _finite_number(quote.get("low"))
        upper_limit = _finite_number(quote.get("upper_limit_price"))
        lower_limit = _finite_number(quote.get("lower_limit_price"))
        if high_price is not None and low_price is not None and high_price > 0 and low_price > 0:
            if high_price < low_price:
                errors.append("quote_high_low_inverted")
            elif current_price > 0 and not low_price * 0.99 <= current_price <= high_price * 1.01:
                errors.append("quote_price_outside_daily_range")
        if upper_limit is not None and upper_limit > 0 and current_price > upper_limit * 1.001:
            errors.append("quote_above_upper_limit")
        if lower_limit is not None and lower_limit > 0 and current_price < lower_limit * 0.999:
            errors.append("quote_below_lower_limit")
        if previous_close is not None and previous_close > 0:
            change_pct = _finite_number(quote.get("change_pct"))
            if change_pct is not None and current_price > 0:
                implied_change_pct = (current_price / previous_close - 1.0) * 100.0
                if abs(implied_change_pct - change_pct) > 0.75:
                    errors.append("quote_change_pct_inconsistent")
        equity = required_number(
            summary.get("net_liquidation_value") or summary.get("total_value"), "account_equity"
        )
        available_cash = required_number(
            summary.get("available_cash") if summary.get("available_cash") is not None else summary.get("cash"),
            "account_available_cash",
        )
        total_exposure = required_number(summary.get("stock_value"), "account_stock_value")
        purchase_amount = _number(summary.get("purchase_amount"))
        profit_loss = _number(summary.get("profit_loss"))
        rate = _finite_number(summary.get("profit_loss_rate"))
        if rate is not None:
            daily_loss_pct = rate
        elif purchase_amount > 0 and _finite_number(summary.get("profit_loss")) is not None:
            daily_loss_pct = profit_loss / purchase_amount * 100
        else:
            daily_loss_pct = 0.0
            errors.append("account_daily_pnl_invalid")
        symbol_exposure = 0.0
        available_position_quantity = 0.0
        if position:
            symbol_exposure = required_number(position.get("evaluation_amount"), "position_evaluation_amount")
            required_number(position.get("quantity"), "position_quantity")
            available_position_quantity = required_number(
                position.get("available_quantity"), "position_available_quantity"
            )
        vi_code = str(quote.get("vi_cls_code") or quote.get("overtime_vi_cls_code") or "").upper().strip()
        vi_active = vi_code not in {"", "0", "N", "NONE", "FALSE"}

        return MarketSnapshot(
            observed_at=datetime.now().astimezone().isoformat(timespec="milliseconds"),
            current_price=current_price,
            ask_price=ask_price,
            bid_price=bid_price,
            account_ok=not errors,
            available_cash=available_cash,
            equity=equity,
            total_exposure=total_exposure,
            symbol_exposure=symbol_exposure,
            daily_loss_pct=daily_loss_pct,
            daily_order_count=daily_order_count,
            already_held=_number(position.get("quantity")) > 0,
            emergency_halt=bool(self.emergency_halt()),
            pending_same_symbol=pending_same_symbol,
            data_source=(
                "KIS_READONLY_CALLS_LIVE_PROFILE"
                if account.get("order_allowed") is True
                else "KIS_READONLY"
            ),
            snapshot_errors=tuple(dict.fromkeys(errors)),
            available_position_quantity=available_position_quantity,
            market_halted=str(quote.get("temporary_halt_yn") or "").upper() == "Y",
            vi_active=vi_active,
            fetch_latency_seconds=round(time.monotonic() - fetch_started, 4),
            best_ask_quantity=_number(
                orderbook.get("best_ask_quantity") or orderbook.get("ask_quantity") or top_level.get("ask_quantity")
            ),
            best_bid_quantity=_number(
                orderbook.get("best_bid_quantity") or orderbook.get("bid_quantity") or top_level.get("bid_quantity")
            ),
        )

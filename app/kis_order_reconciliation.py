from __future__ import annotations

from typing import Any


def _number(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def normalize_order(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_no": _text(row, "order_no", "ODNO", "odno"),
        "symbol": _text(row, "symbol", "pdno", "PDNO").upper(),
        "side": _text(row, "side", "sll_buy_dvsn_cd", "SLL_BUY_DVSN_CD").upper(),
        "ordered_qty": _number(row.get("ordered_qty", row.get("submitted_quantity", row.get("quantity", 0)))),
        "filled_qty": _number(row.get("filled_qty", row.get("broker_quantity", row.get("tot_ccld_qty", 0)))),
        "avg_price": _number(row.get("avg_price", row.get("price", row.get("avg_prvs", 0)))),
    }


def _order_key(row: dict[str, Any]) -> tuple[str, ...]:
    order_no = str(row.get("order_no") or "")
    if order_no:
        return ("order_no", order_no)
    return (
        "fallback",
        str(row.get("symbol") or ""),
        str(row.get("side") or ""),
        f"{_number(row.get('ordered_qty')):.6f}",
    )


def allocate_primary_executions(
    local_orders: list[dict[str, Any]],
    broker_executions: list[dict[str, Any]],
    *,
    quantity_tolerance: float = 0.000001,
) -> dict[str, Any]:
    """Allocate fills by order number first and never cross-match numbered orders."""
    execution_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(broker_executions):
        if not isinstance(raw, dict):
            continue
        execution_rows.append(
            {
                "index": index,
                "date": _text(raw, "date", "executed_date"),
                "symbol": _text(raw, "symbol", "pdno", "PDNO").upper(),
                "side": _text(raw, "side").upper(),
                "order_no": _text(raw, "order_no", "ODNO", "odno"),
                "quantity": _number(raw.get("quantity", raw.get("filled_quantity", 0))),
                "price": _number(raw.get("price", raw.get("avg_price", 0))),
                "raw": raw,
            }
        )
    remaining = {row["index"]: max(0.0, _number(row["quantity"])) for row in execution_rows}
    allocations: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    seen_local_order_numbers: set[str] = set()

    for local_index, raw in enumerate(local_orders):
        if not isinstance(raw, dict):
            continue
        date_text = _text(raw, "date", "created_date")
        symbol = _text(raw, "symbol").upper()
        side = _text(raw, "side").upper()
        order_no = _text(raw, "order_no", "ODNO")
        requested = _number(raw.get("quantity", raw.get("submitted_quantity", raw.get("ordered_qty", 0))))
        group = [
            row
            for row in execution_rows
            if row["date"] == date_text and row["symbol"] == symbol and row["side"] == side
        ]
        exact = [row for row in group if order_no and row["order_no"] == order_no]
        unnumbered = [row for row in group if not row["order_no"]]
        numbered = [row for row in group if row["order_no"]]
        matching_basis = "order_no"
        candidates = exact
        reason = ""
        if order_no:
            if order_no in seen_local_order_numbers:
                reason = "duplicate_local_order_no"
                candidates = []
            elif not exact and unnumbered and not numbered:
                matching_basis = "legacy_unnumbered_fallback"
                candidates = unnumbered
            elif not exact:
                reason = "local_order_no_not_found_at_broker"
        else:
            matching_basis = "legacy_unnumbered_fallback"
            candidates = unnumbered
            if not candidates and numbered:
                reason = "local_order_no_missing_for_numbered_broker_execution"
        if order_no:
            seen_local_order_numbers.add(order_no)

        allocated = 0.0
        allocated_value = 0.0
        used_execution_indexes: list[int] = []
        for execution in candidates:
            available = remaining.get(execution["index"], 0.0)
            take = min(max(0.0, requested - allocated), available)
            if take <= quantity_tolerance:
                continue
            allocated += take
            allocated_value += take * _number(execution["price"])
            remaining[execution["index"]] = max(0.0, available - take)
            used_execution_indexes.append(int(execution["index"]))
            if allocated >= requested - quantity_tolerance:
                break
        if reason:
            mismatches.append(
                {
                    "local_index": local_index,
                    "date": date_text,
                    "symbol": symbol,
                    "side": side,
                    "order_no": order_no,
                    "reason": reason,
                    "broker_order_numbers": sorted({str(row["order_no"]) for row in numbered}),
                }
            )
        allocations.append(
            {
                "local_index": local_index,
                "order_no": order_no,
                "matching_basis": matching_basis,
                "requested_quantity": requested,
                "allocated_quantity": round(allocated, 6),
                "unfilled_quantity": round(max(0.0, requested - allocated), 6),
                "avg_price": round(allocated_value / allocated, 6) if allocated > 0 else 0.0,
                "broker_group_quantity": round(sum(_number(row["quantity"]) for row in group), 6),
                "used_execution_indexes": used_execution_indexes,
                "mismatch_reason": reason,
            }
        )
    remaining_executions = [
        {**row["raw"], "remaining_quantity": round(remaining.get(row["index"], 0.0), 6)}
        for row in execution_rows
        if remaining.get(row["index"], 0.0) > quantity_tolerance
    ]
    return {
        "allocations": allocations,
        "order_number_mismatches": mismatches,
        "order_number_mismatch_count": len(mismatches),
        "remaining_executions": remaining_executions,
        "matching_policy": "order_no_first; fallback_only_when_both_sides_are_unnumbered",
    }


def reconcile_order_snapshots(
    primary_orders: list[dict[str, Any]],
    secondary_orders: list[dict[str, Any]] | None,
    *,
    secondary_connected: bool,
    quantity_tolerance: float = 0.000001,
    price_tolerance: float = 0.01,
) -> dict[str, Any]:
    """Compare deterministic KIS records with an independent read-only KIS MCP snapshot."""
    primary = [normalize_order(row) for row in primary_orders if isinstance(row, dict)]
    if not secondary_connected:
        return {
            "ok": True,
            "status": "primary_only_fallback",
            "hard_block": False,
            "primary_count": len(primary),
            "secondary_count": 0,
            "mismatch_count": 0,
            "mismatches": [],
            "next_order_allowed": True,
            "verification_mode": "deterministic_kis_only",
        }
    if secondary_orders is None:
        return {
            "ok": False,
            "status": "secondary_snapshot_pending",
            "hard_block": bool(primary),
            "primary_count": len(primary),
            "secondary_count": 0,
            "mismatch_count": 1 if primary else 0,
            "mismatches": ([{"field": "secondary_snapshot", "reason": "missing_after_primary_order"}] if primary else []),
            "next_order_allowed": not bool(primary),
            "verification_mode": "dual_path_pending",
        }

    secondary = [normalize_order(row) for row in secondary_orders if isinstance(row, dict)]
    primary_map = {_order_key(row): row for row in primary}
    secondary_map = {_order_key(row): row for row in secondary}
    mismatches: list[dict[str, Any]] = []
    for key in sorted(set(primary_map) | set(secondary_map)):
        left = primary_map.get(key)
        right = secondary_map.get(key)
        if left is None or right is None:
            mismatches.append(
                {
                    "order_key": list(key),
                    "field": "order_presence",
                    "primary_present": left is not None,
                    "secondary_present": right is not None,
                }
            )
            continue
        for field in ("order_no", "symbol", "side"):
            if str(left.get(field) or "") != str(right.get(field) or ""):
                mismatches.append(
                    {"order_key": list(key), "field": field, "primary": left.get(field), "secondary": right.get(field)}
                )
        for field in ("ordered_qty", "filled_qty"):
            if abs(_number(left.get(field)) - _number(right.get(field))) > quantity_tolerance:
                mismatches.append(
                    {"order_key": list(key), "field": field, "primary": left.get(field), "secondary": right.get(field)}
                )
        left_price = _number(left.get("avg_price"))
        right_price = _number(right.get("avg_price"))
        if left_price > 0 and right_price > 0 and abs(left_price - right_price) > price_tolerance:
            mismatches.append(
                {"order_key": list(key), "field": "avg_price", "primary": left_price, "secondary": right_price}
            )
    hard_block = bool(mismatches)
    return {
        "ok": not hard_block,
        "status": "matched" if not hard_block else "mismatch_blocked",
        "hard_block": hard_block,
        "primary_count": len(primary),
        "secondary_count": len(secondary),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:30],
        "next_order_allowed": not hard_block,
        "verification_mode": "deterministic_kis_plus_official_mcp",
        "comparison_fields": ["order_no", "symbol", "side", "ordered_qty", "filled_qty", "avg_price"],
    }


def _account_snapshot(value: dict[str, Any] | None) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    current = row.get("current")
    if isinstance(current, dict):
        row = current
    return row


def _position_map(value: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    snapshot = _account_snapshot(value)
    positions = snapshot.get("positions") if isinstance(snapshot.get("positions"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for raw in positions:
        if not isinstance(raw, dict):
            continue
        symbol = _text(raw, "symbol", "pdno", "code").upper()
        if symbol:
            result[symbol] = raw
    return result


def _cash_value(value: dict[str, Any] | None) -> tuple[bool, float]:
    snapshot = _account_snapshot(value)
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    for row in (snapshot, summary):
        for key in ("available_cash", "cash", "ord_psbl_cash"):
            if key in row and row.get(key) not in (None, ""):
                return True, _number(row.get(key))
    return False, 0.0


def _side(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"BUY", "B", "02", "매수"}:
        return "BUY"
    if text in {"SELL", "S", "01", "매도"}:
        return "SELL"
    return text


def reconcile_account_ledger(
    order: dict[str, Any],
    fill: dict[str, Any],
    pre_snapshot: dict[str, Any] | None,
    post_snapshot: dict[str, Any] | None,
    *,
    quantity_tolerance: float = 0.000001,
    average_price_tolerance_pct: float = 0.002,
    max_transaction_cost_pct: float = 0.03,
) -> dict[str, Any]:
    """Reconcile a filled order against before/after broker account evidence.

    Cash movement is used to derive net realized P/L for sells, so fees and tax
    are reflected instead of being silently ignored. Missing evidence is kept
    out of official performance and learning; contradictory evidence hard-blocks.
    """
    symbol = _text(order, "symbol", "pdno", "PDNO").upper()
    side = _side(order.get("side"))
    order_no = _text(order, "order_no", "ODNO", "odno")
    filled_qty = _number(fill.get("filled_qty", fill.get("allocated_quantity", fill.get("quantity", 0))))
    fill_price = _number(fill.get("avg_price", fill.get("price", 0)))
    base = {
        "order_no": order_no,
        "symbol": symbol,
        "side": side,
        "filled_quantity": round(filled_qty, 6),
        "fill_avg_price": round(fill_price, 6),
        "verification_fields": ["position_quantity", "average_price", "cash_delta", "realized_pnl"],
    }
    missing: list[str] = []
    if not symbol:
        missing.append("symbol")
    if side not in {"BUY", "SELL"}:
        missing.append("side")
    if filled_qty <= quantity_tolerance:
        missing.append("filled_quantity")
    if fill_price <= 0:
        missing.append("fill_avg_price")
    if not isinstance(pre_snapshot, dict) or not pre_snapshot:
        missing.append("pre_account_snapshot")
    if not isinstance(post_snapshot, dict) or not post_snapshot:
        missing.append("post_account_snapshot")
    if missing:
        return {
            **base,
            "ok": False,
            "status": "incomplete_evidence",
            "hard_block": False,
            "missing_evidence": missing,
            "next_order_allowed": False,
            "official_trade_eligible": False,
            "official_performance_eligible": False,
            "learning_eligible": False,
        }

    before_positions = _position_map(pre_snapshot)
    after_positions = _position_map(post_snapshot)
    before = before_positions.get(symbol, {})
    after = after_positions.get(symbol, {})
    before_qty = _number(before.get("quantity", before.get("holding_quantity", before.get("hldg_qty", 0))))
    after_qty = _number(after.get("quantity", after.get("holding_quantity", after.get("hldg_qty", 0))))
    before_avg = _number(before.get("avg_price", before.get("average_price", before.get("pchs_avg_pric", 0))))
    after_avg = _number(after.get("avg_price", after.get("average_price", after.get("pchs_avg_pric", 0))))
    expected_delta = filled_qty if side == "BUY" else -filled_qty
    actual_delta = after_qty - before_qty
    quantity_ok = abs(actual_delta - expected_delta) <= quantity_tolerance

    expected_after_avg = 0.0
    average_price_ok = True
    average_price_evidence = "not_applicable"
    if side == "BUY" and after_qty > quantity_tolerance:
        expected_after_avg = (
            ((before_qty * before_avg) + (filled_qty * fill_price)) / (before_qty + filled_qty)
            if before_qty > quantity_tolerance and before_avg > 0
            else fill_price
        )
        tolerance = max(1.0, expected_after_avg * max(0.0, average_price_tolerance_pct))
        average_price_ok = after_avg > 0 and abs(after_avg - expected_after_avg) <= tolerance
        average_price_evidence = "weighted_position_average"
    elif side == "SELL" and after_qty > quantity_tolerance:
        expected_after_avg = before_avg
        tolerance = max(1.0, expected_after_avg * max(0.0, average_price_tolerance_pct))
        average_price_ok = before_avg > 0 and after_avg > 0 and abs(after_avg - expected_after_avg) <= tolerance
        average_price_evidence = "remaining_lot_average_unchanged"
    elif side == "SELL":
        average_price_evidence = "full_position_closed"

    before_cash_ok, before_cash = _cash_value(pre_snapshot)
    after_cash_ok, after_cash = _cash_value(post_snapshot)
    cash_evidence_available = before_cash_ok and after_cash_ok
    cash_delta = after_cash - before_cash if cash_evidence_available else 0.0
    gross_notional = filled_qty * fill_price
    expected_cash_delta = -gross_notional if side == "BUY" else gross_notional
    transaction_cost = (
        (-cash_delta - gross_notional) if side == "BUY" else (gross_notional - cash_delta)
    ) if cash_evidence_available else 0.0
    cost_lower_bound = -max(10.0, gross_notional * 0.005)
    cost_upper_bound = max(1000.0, gross_notional * max(0.0, max_transaction_cost_pct))
    cash_direction_ok = cash_evidence_available and (cash_delta < 0 if side == "BUY" else cash_delta > 0)
    cash_cost_ok = cash_evidence_available and cost_lower_bound <= transaction_cost <= cost_upper_bound
    cash_ok = cash_direction_ok and cash_cost_ok

    realized: dict[str, Any] = {"status": "not_applicable", "eligible": False}
    pnl_evidence_ok = True
    if side == "SELL":
        pnl_evidence_ok = before_avg > 0 and cash_ok
        if pnl_evidence_ok:
            cost_basis = before_avg * filled_qty
            realized = {
                "status": "account_cash_reconciled",
                "eligible": True,
                "cost_basis": round(cost_basis, 2),
                "gross_pnl_before_costs": round((fill_price - before_avg) * filled_qty, 2),
                "net_realized_pnl": round(cash_delta - cost_basis, 2),
                "net_realized_pnl_pct": round(((cash_delta - cost_basis) / cost_basis * 100) if cost_basis else 0.0, 4),
                "transaction_cost_and_tax": round(transaction_cost, 2),
                "source": "broker_fill_plus_account_cash_delta",
            }
        else:
            realized = {
                "status": "missing_or_invalid_account_pnl_evidence",
                "eligible": False,
                "source": "unverified",
            }

    mismatches: list[dict[str, Any]] = []
    if not quantity_ok:
        mismatches.append({"field": "position_quantity", "expected_delta": round(expected_delta, 6), "actual_delta": round(actual_delta, 6)})
    if not average_price_ok:
        mismatches.append({"field": "average_price", "expected": round(expected_after_avg, 6), "actual": round(after_avg, 6)})
    if not cash_evidence_available:
        missing.append("cash_delta")
    elif not cash_ok:
        mismatches.append({"field": "cash_delta", "expected_direction": "negative" if side == "BUY" else "positive", "actual": round(cash_delta, 2), "implied_cost": round(transaction_cost, 2)})
    if side == "SELL" and not pnl_evidence_ok:
        missing.append("realized_pnl")

    hard_block = bool(mismatches)
    complete = not hard_block and not missing
    status = "matched" if complete else "mismatch_blocked" if hard_block else "incomplete_evidence"
    return {
        **base,
        "ok": complete,
        "status": status,
        "hard_block": hard_block,
        "missing_evidence": sorted(set(missing)),
        "mismatches": mismatches,
        "position": {
            "before_quantity": round(before_qty, 6),
            "after_quantity": round(after_qty, 6),
            "expected_delta": round(expected_delta, 6),
            "actual_delta": round(actual_delta, 6),
            "quantity_matched": quantity_ok,
        },
        "average_price": {
            "before": round(before_avg, 6),
            "after": round(after_avg, 6),
            "expected_after": round(expected_after_avg, 6),
            "matched": average_price_ok,
            "evidence": average_price_evidence,
        },
        "cash": {
            "evidence_available": cash_evidence_available,
            "actual_delta": round(cash_delta, 2),
            "expected_gross_delta": round(expected_cash_delta, 2),
            "implied_transaction_cost_and_tax": round(transaction_cost, 2),
            "direction_matched": cash_direction_ok,
            "cost_range_matched": cash_cost_ok,
        },
        "realized_pnl": realized,
        "next_order_allowed": complete,
        "official_trade_eligible": complete,
        "official_performance_eligible": complete and side == "SELL",
        "learning_eligible": complete and side == "SELL",
    }

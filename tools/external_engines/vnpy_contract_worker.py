from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import time
from typing import Any

import vnpy
from vnpy.trader.constant import Direction, Exchange, OrderType
from vnpy.trader.object import OrderRequest


FORBIDDEN_KEY_PARTS = (
    "account_number",
    "api_key",
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


def _normalize_order(row: dict[str, Any], index: int) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").strip()
    if not re.fullmatch(r"[0-9A-Za-z._-]{1,24}", symbol):
        raise ValueError(f"invalid_symbol:{index}")
    side = str(row.get("side") or "BUY").strip().upper()
    order_type = str(row.get("order_type") or "LIMIT").strip().upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError(f"invalid_side:{index}")
    if order_type not in {"LIMIT", "MARKET"}:
        raise ValueError(f"invalid_order_type:{index}")
    quantity = int(_finite(row.get("quantity"), 0.0))
    price = _finite(row.get("price"), 0.0)
    if quantity <= 0:
        raise ValueError(f"invalid_quantity:{index}")
    if order_type == "LIMIT" and price <= 0:
        raise ValueError(f"limit_price_required:{index}")
    if str(row.get("currency") or "KRW") != "KRW":
        raise ValueError(f"currency_must_be_krw:{index}")
    if str(row.get("price_unit") or "won_integer") != "won_integer":
        raise ValueError(f"price_unit_must_be_won_integer:{index}")
    return {
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "price": price if order_type == "LIMIT" else 0.0,
        "currency": "KRW",
        "price_unit": "won_integer",
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_verify_only(request)
    if str(request.get("action") or "") != "validate_order_contract":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    orders = request.get("orders")
    if not isinstance(orders, list) or not orders:
        raise ValueError("orders_required")
    if len(orders) > 20:
        raise ValueError("too_many_orders")
    normalized = [_normalize_order(row, index) for index, row in enumerate(orders) if isinstance(row, dict)]
    if len(normalized) != len(orders):
        raise ValueError("order_must_be_object")

    results = []
    for index, row in enumerate(normalized, start=1):
        request_object = OrderRequest(
            symbol=row["symbol"],
            exchange=Exchange.KRX,
            direction=Direction.LONG if row["side"] == "BUY" else Direction.SHORT,
            type=OrderType.LIMIT if row["order_type"] == "LIMIT" else OrderType.MARKET,
            volume=row["quantity"],
            price=row["price"],
            reference="codexstock-verify-only",
        )
        order_data = request_object.create_order_data(f"VERIFY-{index:04d}", "CODEXSTOCK_VERIFY_ONLY")
        cancel_request = order_data.create_cancel_request()
        reconciled = bool(
            request_object.vt_symbol == f"{row['symbol']}.KRX"
            and order_data.symbol == row["symbol"]
            and order_data.exchange == Exchange.KRX
            and order_data.direction == request_object.direction
            and order_data.type == request_object.type
            and int(order_data.volume) == row["quantity"]
            and abs(float(order_data.price) - row["price"]) < 1e-9
            and cancel_request.vt_symbol == request_object.vt_symbol
        )
        results.append(
            {
                "input": row,
                "vnpy": {
                    "vt_symbol": request_object.vt_symbol,
                    "vt_orderid": order_data.vt_orderid,
                    "direction": row["side"],
                    "order_type": row["order_type"],
                    "price": float(order_data.price),
                    "quantity": int(order_data.volume),
                    "cancel_vt_symbol": cancel_request.vt_symbol,
                    "gateway_name": order_data.gateway_name,
                },
                "reconciled": reconciled,
            }
        )
    all_reconciled = all(row["reconciled"] for row in results)
    material = {
        "source_commit": request.get("source_commit"),
        "orders": results,
    }
    result_hash = hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "ok": all_reconciled,
        "schema": "codexstock_vnpy_order_contract_v1",
        "action": "validate_order_contract",
        "engine_name": "vn.py",
        "engine_version": str(vnpy.__version__),
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "gateway_mode": "CODEXSTOCK_VERIFY_ONLY",
        "order_count": len(results),
        "reconciled_count": sum(1 for row in results if row["reconciled"]),
        "all_reconciled": all_reconciled,
        "order_results": results,
        "result_hash": result_hash,
        "network_access_allowed": False,
        "gateway_access_allowed": False,
        "credentials_allowed": False,
        "decision": "VERIFY_ONLY",
        "live_order_allowed": False,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
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
            "schema": "codexstock_vnpy_order_contract_v1",
            "engine_name": "vn.py",
            "error": str(exc)[:600],
            "decision": "BLOCKED",
            "live_order_allowed": False,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

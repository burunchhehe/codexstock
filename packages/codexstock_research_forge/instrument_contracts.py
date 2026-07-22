from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


CONTRACTS: dict[str, dict[str, Any]] = {
    "KR_EQUITY": {
        "market": "KR", "asset_class": "EQUITY", "currency": "KRW",
        "quote_unit": "KRW_PER_SHARE", "timezone": "Asia/Seoul", "lot_size": 1,
        "fractional_quantity_allowed": False, "tick_rule": "KRX_DYNAMIC",
        "supported_read_providers": ["kis-readonly", "krx"],
    },
    "KR_ETF": {
        "market": "KR", "asset_class": "ETF", "currency": "KRW",
        "quote_unit": "KRW_PER_SHARE", "timezone": "Asia/Seoul", "lot_size": 1,
        "fractional_quantity_allowed": False, "tick_rule": "KRX_DYNAMIC",
        "supported_read_providers": ["kis-readonly", "krx"],
    },
    "US_EQUITY": {
        "market": "US", "asset_class": "EQUITY", "currency": "USD",
        "quote_unit": "USD_PER_SHARE", "timezone": "America/New_York", "lot_size": 1,
        "fractional_quantity_allowed": False, "tick_rule": "USD_CENT_OR_VENUE",
        "supported_read_providers": ["kis-overseas-readonly", "openbb", "qlib"],
    },
    "US_ETF": {
        "market": "US", "asset_class": "ETF", "currency": "USD",
        "quote_unit": "USD_PER_SHARE", "timezone": "America/New_York", "lot_size": 1,
        "fractional_quantity_allowed": False, "tick_rule": "USD_CENT_OR_VENUE",
        "supported_read_providers": ["kis-overseas-readonly", "openbb", "qlib"],
    },
}


def contract_manifest() -> dict[str, Any]:
    contracts = [{"contract_id": identifier, **value} for identifier, value in sorted(CONTRACTS.items())]
    payload = {
        "schema_version": 1, "contracts": contracts, "contract_count": len(contracts),
        "scope": "research_data_contract_only", "live_order_allowed": False,
        "provider_runtime_verified": False,
    }
    payload["contract_hash"] = _hash(contracts)
    return payload


def normalize_instrument_dataset_contract(
    snapshot: dict[str, Any],
    symbols: list[str],
) -> dict[str, Any]:
    """Bind a research dataset to one unambiguous market/currency/unit contract."""
    if not isinstance(snapshot, dict):
        raise ValueError("instrument dataset snapshot must be an object")
    snapshot_symbols = snapshot.get("symbols")
    if not isinstance(snapshot_symbols, list):
        snapshot_symbols = [snapshot.get("symbol")] if snapshot.get("symbol") else []
    normalized_symbols = sorted({
        str(value or "").upper().strip()
        for value in [*symbols, *snapshot_symbols]
        if str(value or "").strip()
    })
    errors: list[str] = []
    if not normalized_symbols:
        errors.append("instrument_symbols_missing")
    elif any(len(value) > 32 or not all(char.isalnum() or char in {".", "-"} for char in value) for value in normalized_symbols):
        errors.append("invalid_symbol")

    declared_contract_id = str(
        snapshot.get("instrument_contract_id")
        or snapshot.get("contract_id")
        or ""
    ).upper().strip()
    declared_market = str(snapshot.get("market") or "").upper().strip()
    market_aliases = {
        "KOSPI": "KR", "KOSDAQ": "KR", "KONEX": "KR", "KRX": "KR",
        "NASDAQ": "US", "NYSE": "US", "AMEX": "US",
    }
    declared_market = market_aliases.get(declared_market, declared_market)
    inferred_markets = {
        "KR" if value.isdigit() and len(value) == 6 else "US"
        for value in normalized_symbols
    }
    if len(inferred_markets) > 1:
        errors.append("mixed_market_dataset_not_supported")
    inferred_market = next(iter(inferred_markets), "")
    asset_class = str(snapshot.get("asset_class") or "EQUITY").upper().strip()
    if asset_class not in {"EQUITY", "ETF"}:
        errors.append("unsupported_asset_class")
    resolved_market = declared_market or inferred_market
    inferred_contract_id = f"{resolved_market}_{asset_class}" if resolved_market and asset_class else ""
    contract_id = declared_contract_id or inferred_contract_id
    contract = CONTRACTS.get(contract_id)
    if contract is None:
        errors.append("unsupported_instrument_contract")
        contract = {}
    if declared_contract_id and inferred_contract_id and declared_contract_id != inferred_contract_id:
        errors.append("contract_id_symbol_mismatch")

    for key in ("market", "asset_class", "currency", "quote_unit"):
        declared_value = str(snapshot.get(key) or "").upper().strip()
        if key == "market":
            declared_value = market_aliases.get(declared_value, declared_value)
        expected_value = str(contract.get(key) or "").upper().strip()
        if declared_value and expected_value and declared_value != expected_value:
            errors.append(f"{key}_contract_mismatch")
    provider = str(snapshot.get("provider") or snapshot.get("data_provider") or "").strip()
    supported_providers = list(contract.get("supported_read_providers") or [])
    if provider and supported_providers and provider not in supported_providers:
        errors.append("provider_contract_mismatch")

    normalized_snapshot = dict(snapshot)
    normalized_snapshot.pop("contract_id", None)
    if normalized_symbols:
        normalized_snapshot["symbols"] = normalized_symbols
        if len(normalized_symbols) == 1:
            normalized_snapshot["symbol"] = normalized_symbols[0]
    if contract:
        normalized_snapshot.update({
            "instrument_contract_id": contract_id,
            "market": contract["market"],
            "asset_class": contract["asset_class"],
            "currency": contract["currency"],
            "quote_unit": contract["quote_unit"],
            "market_timezone": contract["timezone"],
            "lot_size": contract["lot_size"],
        })
    canonical = {
        "contract_id": contract_id,
        "symbols": normalized_symbols,
        "market": contract.get("market"),
        "asset_class": contract.get("asset_class"),
        "currency": contract.get("currency"),
        "quote_unit": contract.get("quote_unit"),
        "timezone": contract.get("timezone"),
        "lot_size": contract.get("lot_size"),
        "provider": provider,
    }
    evidence = {
        "schema_version": 1,
        "passed": not errors,
        "errors": list(dict.fromkeys(errors)),
        "contract_id": contract_id,
        "symbols": normalized_symbols,
        "contract": {"contract_id": contract_id, **contract} if contract else {},
        "provider": provider,
        "contract_hash": _hash(canonical),
        "research_only": True,
        "live_order_allowed": False,
    }
    normalized_snapshot["instrument_contract"] = evidence
    return {**evidence, "normalized_snapshot": normalized_snapshot}


def validate_instrument_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError("instrument snapshot must be an object")
    contract_id = str(snapshot.get("contract_id") or "").upper()
    contract = CONTRACTS.get(contract_id)
    if contract is None:
        raise ValueError("unsupported instrument contract")
    errors: list[str] = []
    symbol = str(snapshot.get("symbol") or "").upper()
    if not symbol or len(symbol) > 32 or not all(char.isalnum() or char in {".", "-"} for char in symbol):
        errors.append("invalid_symbol")
    for key in ("market", "asset_class", "currency", "quote_unit"):
        if str(snapshot.get(key) or "").upper() != str(contract[key]).upper():
            errors.append(f"{key}_contract_mismatch")
    try:
        price = Decimal(str(snapshot.get("price")))
        if not price.is_finite() or price <= 0: errors.append("invalid_price")
    except (InvalidOperation, TypeError):
        errors.append("invalid_price"); price = Decimal(0)
    quantity_value = snapshot.get("quantity")
    if quantity_value is not None:
        try:
            quantity = Decimal(str(quantity_value))
            if not quantity.is_finite() or quantity < 0: errors.append("invalid_quantity")
            if not contract["fractional_quantity_allowed"] and quantity != quantity.to_integral_value(): errors.append("fractional_quantity_not_allowed")
            if quantity and quantity % Decimal(str(contract["lot_size"])) != 0: errors.append("lot_size_mismatch")
        except (InvalidOperation, TypeError): errors.append("invalid_quantity")
    timestamp = str(snapshot.get("timestamp") or "")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None: errors.append("timestamp_timezone_missing")
    except ValueError: errors.append("invalid_timestamp")
    source = str(snapshot.get("source") or "")
    if not source: errors.append("source_missing")
    provider_declared = str(snapshot.get("provider") or "")
    provider_supported = not provider_declared or provider_declared in contract["supported_read_providers"]
    if not provider_supported: errors.append("provider_contract_mismatch")
    canonical = {
        "contract_id": contract_id, "symbol": symbol, "market": contract["market"],
        "asset_class": contract["asset_class"], "currency": contract["currency"],
        "quote_unit": contract["quote_unit"], "price": str(price), "quantity": quantity_value,
        "timestamp": timestamp, "source": source, "provider": provider_declared,
    }
    return {
        "passed": not errors, "errors": errors, "contract": {"contract_id": contract_id, **contract},
        "normalized": canonical, "snapshot_hash": _hash(canonical),
        "research_only": True, "live_order_allowed": False,
    }


def _hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

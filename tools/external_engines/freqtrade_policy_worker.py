from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from typing import Any

import freqtrade
from freqtrade.configuration.config_validation import validate_config_consistency
from freqtrade.enums import RunMode


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


def _assert_policy_only(value: Any, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(f"forbidden_input_field:{path}.{key}")
            _assert_policy_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_policy_only(child, f"{path}[{index}]")


def _number(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _risk_tier(allocation_pct: float) -> dict[str, str]:
    if allocation_pct >= 80.0:
        return {"level": "DANGER", "color": "red", "label": "위험"}
    if allocation_pct > 30.0:
        return {"level": "CAUTION", "color": "yellow", "label": "주의"}
    return {"level": "GOOD", "color": "green", "label": "양호"}


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_policy_only(request)
    if str(request.get("action") or "") != "validate_paper_operation_policy":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    allocation_pct = max(0.0, min(_number(request.get("allocation_pct"), 30.0), 100.0))
    paper_wallet = max(1_000.0, min(_number(request.get("paper_wallet"), 100_000_000.0), 10**15))
    max_open_trades = max(1, min(int(request.get("max_open_trades", 3) or 3), 50))
    stoploss_pct = max(0.1, min(_number(request.get("stoploss_pct"), 5.0), 30.0))
    allocated_capital = paper_wallet * allocation_pct / 100.0
    stake_amount = allocated_capital / max_open_trades
    config = {
        "runmode": RunMode.OTHER,
        "exchange": {"name": "binance", "key": "", "secret": "", "pair_whitelist": []},
        "dry_run": True,
        "dataformat_ohlcv": "feather",
        "dataformat_trades": "feather",
        "max_open_trades": max_open_trades,
        "stake_amount": stake_amount,
        "stoploss": -stoploss_pct / 100.0,
    }
    validate_config_consistency(config, preliminary=True)
    tier = _risk_tier(allocation_pct)
    sanitized_contract = {
        "dry_run": True,
        "exchange_credentials_present": False,
        "allocation_pct": round(allocation_pct, 4),
        "paper_wallet": round(paper_wallet, 4),
        "allocated_capital": round(allocated_capital, 4),
        "max_open_trades": max_open_trades,
        "stake_amount_per_position": round(stake_amount, 4),
        "stoploss_pct": round(stoploss_pct, 4),
        "risk_tier": tier,
    }
    contract_hash = hashlib.sha256(
        json.dumps(sanitized_contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "ok": True,
        "schema": "codexstock_freqtrade_paper_policy_v1",
        "action": "validate_paper_operation_policy",
        "engine_name": "Freqtrade",
        "engine_version": str(freqtrade.__version__),
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "official_config_validation_passed": True,
        "paper_contract": sanitized_contract,
        "contract_hash": contract_hash,
        "network_access_allowed": False,
        "credentials_allowed": False,
        "decision": "PAPER_POLICY_ONLY",
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
            "schema": "codexstock_freqtrade_paper_policy_v1",
            "engine_name": "Freqtrade",
            "error": str(exc)[:600],
            "decision": "BLOCKED",
            "live_order_allowed": False,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

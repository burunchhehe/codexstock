from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import math
import sys
import time
from typing import Any

import numpy as np


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


def _assert_paper_only(value: Any, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(f"forbidden_input_field:{path}.{key}")
            _assert_paper_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_paper_only(child, f"{path}[{index}]")


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _load_finrl_environment() -> tuple[type, str, str]:
    distribution = importlib.metadata.distribution("finrl")
    module_path = distribution.locate_file("finrl/meta/env_stock_trading/env_stocktrading_np.py")
    spec = importlib.util.spec_from_file_location("_codexstock_finrl_environment", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("finrl_environment_module_not_found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.StockTradingEnv, importlib.metadata.version("finrl"), str(module_path)


def _build_arrays(rows: list[dict[str, Any]], max_symbols: int = 5) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip()
        date = str(row.get("date") or "").strip()
        close = _finite(row.get("close"))
        if symbol and date and close > 0:
            grouped.setdefault(symbol, {})[date] = close
    symbols = sorted(grouped)[:max_symbols]
    if len(symbols) < 2:
        raise ValueError("at_least_two_symbols_required")
    common_dates = sorted(set.intersection(*(set(grouped[symbol]) for symbol in symbols)))
    if len(common_dates) < 40:
        raise ValueError("at_least_40_common_dates_required")
    price_array = np.asarray([[grouped[symbol][date] for symbol in symbols] for date in common_dates], dtype=np.float32)
    return_1 = np.zeros_like(price_array)
    return_1[1:] = price_array[1:] / price_array[:-1] - 1.0
    momentum_5 = np.zeros_like(price_array)
    momentum_5[5:] = price_array[5:] / price_array[:-5] - 1.0
    tech_array = np.concatenate([return_1, momentum_5], axis=1).astype(np.float32)
    return symbols, common_dates, price_array, tech_array


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_paper_only(request)
    if str(request.get("action") or "") != "validate_finrl_paper_environment":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    rows = snapshot.get("dataset_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset_rows_required")
    allocation_cap_pct = max(1.0, min(_finite(request.get("allocation_cap_pct"), 30.0), 80.0))
    initial_capital = max(1_000_000.0, min(_finite(request.get("paper_capital"), 100_000_000.0), 10**15))
    symbols, dates, price_array, tech_array = _build_arrays(rows)
    stock_dim = len(symbols)
    turbulence_array = (np.std(tech_array[:, :stock_dim], axis=1) * 100.0).astype(np.float32)
    environment_class, finrl_version, module_path = _load_finrl_environment()
    environment = environment_class(
        config={
            "price_array": price_array,
            "tech_array": tech_array,
            "turbulence_array": turbulence_array,
            "if_train": False,
        },
        initial_capital=initial_capital,
        max_stock=5,
        buy_cost_pct=0.001,
        sell_cost_pct=0.001,
        reward_scaling=2**-11,
    )
    state, _ = environment.reset(seed=7)
    action_bound_ok = True
    max_exposure_pct = 0.0
    step_count = 0
    buy_action_count = 0
    sell_action_count = 0
    total_reward = 0.0
    while environment.day < environment.max_step:
        current_day = int(environment.day)
        if current_day >= environment.max_step - 1:
            actions = np.full(stock_dim, -1.0, dtype=np.float32)
        else:
            lookback_day = max(0, current_day - 5)
            momentum = price_array[current_day] / price_array[lookback_day] - 1.0
            actions = np.clip(momentum * 8.0, -0.25, 0.25).astype(np.float32)
            actions[np.asarray(environment.stocks) > 0] = np.minimum(actions[np.asarray(environment.stocks) > 0], 0.0)
            current_price = price_array[current_day]
            current_total = float(environment.amount + (environment.stocks * current_price).sum())
            current_exposure = float((environment.stocks * current_price).sum() / current_total * 100.0) if current_total > 0 else 0.0
            if current_exposure >= allocation_cap_pct:
                actions[actions > 0] = 0.0
        action_bound_ok = action_bound_ok and bool(np.all(actions >= -1.0) and np.all(actions <= 1.0))
        buy_action_count += int(np.count_nonzero(actions > 0))
        sell_action_count += int(np.count_nonzero(actions < 0))
        state, reward, done, truncated, _ = environment.step(actions)
        total_reward += float(reward)
        step_count += 1
        current_price = price_array[environment.day]
        total_asset = float(environment.amount + (environment.stocks * current_price).sum())
        exposure_pct = float((environment.stocks * current_price).sum() / total_asset * 100.0) if total_asset > 0 else 0.0
        max_exposure_pct = max(max_exposure_pct, exposure_pct)
        if done or truncated:
            break
    final_holdings = [int(value) for value in np.asarray(environment.stocks).tolist()]
    final_total_asset = float(environment.total_asset)
    final_exposure_pct = (
        float((environment.stocks * price_array[environment.day]).sum() / final_total_asset * 100.0)
        if final_total_asset > 0
        else 0.0
    )
    allocation_gate_passed = max_exposure_pct <= allocation_cap_pct + 0.5
    terminal_reconciled = all(value == 0 for value in final_holdings)
    environment_validated = bool(action_bound_ok and allocation_gate_passed and terminal_reconciled)
    material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "source_commit": request.get("source_commit"),
        "symbols": symbols,
        "dates": [dates[0], dates[-1]],
        "final_holdings": final_holdings,
        "final_total_asset": round(final_total_asset, 6),
    }
    result_hash = hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "ok": environment_validated,
        "schema": "codexstock_finrl_environment_result_v1",
        "action": "validate_finrl_paper_environment",
        "engine_name": "FinRL",
        "engine_version": finrl_version,
        "environment_module": module_path,
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "policy_contract": "deterministic_past_momentum_smoke_v1",
        "symbol_count": stock_dim,
        "symbols": symbols,
        "date_count": len(dates),
        "start_date": dates[0],
        "end_date": dates[-1],
        "step_count": step_count,
        "state_dimension": int(environment.state_dim),
        "observed_state_dimension": int(np.asarray(state).size),
        "action_dimension": int(environment.action_dim),
        "action_low": float(environment.action_space.low.min()),
        "action_high": float(environment.action_space.high.max()),
        "action_bound_ok": action_bound_ok,
        "buy_action_count": buy_action_count,
        "sell_action_count": sell_action_count,
        "allocation_cap_pct": round(allocation_cap_pct, 4),
        "max_exposure_pct": round(max_exposure_pct, 8),
        "allocation_gate_passed": allocation_gate_passed,
        "initial_capital": round(initial_capital, 4),
        "final_total_asset": round(final_total_asset, 4),
        "paper_return_pct": round((final_total_asset / initial_capital - 1.0) * 100.0, 8),
        "total_scaled_reward": round(total_reward, 10),
        "final_holdings": final_holdings,
        "final_exposure_pct": round(final_exposure_pct, 8),
        "terminal_reconciled": terminal_reconciled,
        "environment_validated": environment_validated,
        "promotion_allowed": False,
        "result_hash": result_hash,
        "network_access_allowed": False,
        "credentials_allowed": False,
        "decision": "PAPER_RESEARCH_ONLY",
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
            "schema": "codexstock_finrl_environment_result_v1",
            "engine_name": "FinRL",
            "error": str(exc)[:600],
            "decision": "BLOCKED",
            "live_order_allowed": False,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

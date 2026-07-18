from __future__ import annotations

import hashlib
import json
import math
import statistics
from typing import Any


def analyze_benchmark_attribution(rows: list[dict[str, Any]], equity_curve: list[Any], annualization: int = 252) -> dict[str, Any]:
    if len(rows) != len(equity_curve) or len(rows) < 3:
        raise ValueError("benchmark attribution requires aligned market rows and equity")
    closes = [float(row.get("close") or 0) for row in rows]
    equity = [float(value.get("equity") if isinstance(value, dict) else value) for value in equity_curve]
    if min(closes) <= 0 or min(equity) <= 0 or not all(math.isfinite(value) for value in closes + equity):
        raise ValueError("benchmark attribution received invalid values")
    benchmark_returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    strategy_returns = [equity[index] / equity[index - 1] - 1 for index in range(1, len(equity))]
    benchmark_mean, strategy_mean = statistics.fmean(benchmark_returns), statistics.fmean(strategy_returns)
    variance = statistics.variance(benchmark_returns) if len(benchmark_returns) > 1 else 0.0
    covariance = sum((left - strategy_mean) * (right - benchmark_mean) for left, right in zip(strategy_returns, benchmark_returns)) / (len(strategy_returns) - 1)
    beta = covariance / variance if variance > 0 else None
    strategy_std = statistics.stdev(strategy_returns); benchmark_std = statistics.stdev(benchmark_returns)
    correlation = covariance / (strategy_std * benchmark_std) if strategy_std > 0 and benchmark_std > 0 else None
    excess_returns = [left - right for left, right in zip(strategy_returns, benchmark_returns)]
    tracking_daily = statistics.stdev(excess_returns)
    tracking_error = tracking_daily * math.sqrt(annualization)
    information_ratio = statistics.fmean(excess_returns) / tracking_daily * math.sqrt(annualization) if tracking_daily > 0 else None
    strategy_total = equity[-1] / equity[0] - 1; benchmark_total = closes[-1] / closes[0] - 1
    payload = {
        "method": "aligned_close_to_close_no_future_data", "benchmark": "underlying_buy_and_hold", "period_count": len(strategy_returns), "annualization": annualization,
        "strategy_return_pct": round(strategy_total * 100, 6), "benchmark_return_pct": round(benchmark_total * 100, 6),
        "geometric_excess_return_pct": round(((1 + strategy_total) / (1 + benchmark_total) - 1) * 100, 6),
        "strategy_max_drawdown_pct": round(_drawdown(equity) * 100, 6), "benchmark_max_drawdown_pct": round(_drawdown(closes) * 100, 6),
        "beta": round(beta, 8) if beta is not None else None, "correlation": round(correlation, 8) if correlation is not None else None,
        "annualized_tracking_error_pct": round(tracking_error * 100, 6), "information_ratio": round(information_ratio, 8) if information_ratio is not None else None,
        "strategy_annualized_volatility_pct": round(strategy_std * math.sqrt(annualization) * 100, 6), "benchmark_annualized_volatility_pct": round(benchmark_std * math.sqrt(annualization) * 100, 6),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")); payload["evidence_hash"] = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
    return payload


def _drawdown(values: list[float]) -> float:
    peak, worst = values[0], 0.0
    for value in values:
        peak = max(peak, value); worst = min(worst, value / peak - 1)
    return worst

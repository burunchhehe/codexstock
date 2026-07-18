from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def analyze_market_regimes(rows: list[dict[str, Any]], equity_curve: list[Any], lookback: int = 20, threshold_pct: float = 5.0) -> dict[str, Any]:
    if len(rows) != len(equity_curve) or len(rows) < lookback + 2:
        raise ValueError("regime analysis requires aligned market rows and equity with sufficient history")
    if not 2 <= lookback <= 252 or not 0 < threshold_pct <= 50:
        raise ValueError("invalid regime lookback or threshold")
    closes = [float(row.get("close") or 0) for row in rows]
    equity = [float(value.get("equity") if isinstance(value, dict) else value) for value in equity_curve]
    if min(closes) <= 0 or min(equity) <= 0 or not all(math.isfinite(value) for value in closes + equity):
        raise ValueError("regime analysis received invalid prices or equity")
    buckets: dict[str, list[float]] = {"BULL": [], "BEAR": [], "SIDEWAYS": []}
    sequence = []
    threshold = threshold_pct / 100
    for index in range(lookback, len(rows)):
        market_return = closes[index] / closes[index - lookback] - 1
        regime = "BULL" if market_return >= threshold else "BEAR" if market_return <= -threshold else "SIDEWAYS"
        strategy_return = equity[index] / equity[index - 1] - 1
        buckets[regime].append(strategy_return)
        sequence.append({"timestamp": str(rows[index].get("timestamp") or rows[index].get("date") or ""), "regime": regime, "market_lookback_return_pct": round(market_return * 100, 6), "strategy_bar_return_pct": round(strategy_return * 100, 6)})
    summary = {}
    for regime, returns in buckets.items():
        compounded = math.prod(1 + value for value in returns) - 1 if returns else 0.0
        summary[regime] = {"bar_count": len(returns), "strategy_compounded_return_pct": round(compounded * 100, 6), "strategy_average_bar_return_pct": round(sum(returns) / len(returns) * 100, 6) if returns else 0.0, "best_bar_return_pct": round(max(returns) * 100, 6) if returns else 0.0, "worst_bar_return_pct": round(min(returns) * 100, 6) if returns else 0.0}
    canonical = json.dumps({"lookback": lookback, "threshold_pct": threshold_pct, "sequence": sequence}, sort_keys=True, separators=(",", ":"))
    return {"method": "trailing_close_return_no_future_data", "lookback_bars": lookback, "threshold_pct": threshold_pct, "classified_bar_count": len(sequence), "unclassified_prefix_bars": lookback, "summary": summary, "sequence_hash": f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"}

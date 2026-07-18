from __future__ import annotations

from typing import Any
from .strategy_runtime import validate_indicator_rules
from .multitimeframe import validate_multitimeframe_rules


SUPPORTED_STRATEGIES: dict[str, set[str]] = {
    "ma_cross": {"type", "symbol", "fast", "slow", "label_horizon_rows"},
    "portfolio_ma_cross": {"type", "symbols", "fast", "slow", "max_positions", "position_size"},
    "indicator_rules": {"type", "symbol", "profile", "entry", "exit"},
    "multi_timeframe_indicator_rules": {"type", "symbol", "execution_context", "contexts", "entry", "exit"},
}


def validate_typed_rules(rules: dict[str, Any]) -> list[str]:
    """Validate the non-evaluating Phase-1 strategy DSL.

    Rules without a ``type`` remain draft-compatible. Typed rules are strict:
    no Python, function calls, or undeclared keys are executed.
    """
    strategy_type = str(rules.get("type") or "")
    if not strategy_type:
        return []
    allowed = SUPPORTED_STRATEGIES.get(strategy_type)
    if allowed is None:
        return [f"unsupported strategy type: {strategy_type}"]
    unknown = sorted(set(rules) - allowed)
    errors = [f"unknown {strategy_type} rule key: {key}" for key in unknown]
    if strategy_type == "ma_cross":
        symbol = str(rules.get("symbol") or "")
        if not symbol or not symbol.isalnum():
            errors.append("ma_cross.symbol must be alphanumeric")
        try:
            fast, slow = int(rules.get("fast")), int(rules.get("slow"))
            if not 2 <= fast < slow <= 250:
                errors.append("ma_cross requires 2 <= fast < slow <= 250")
        except (TypeError, ValueError):
            errors.append("ma_cross.fast and slow must be integers")
        try:
            if not 0 <= int(rules.get("label_horizon_rows") or 0) <= 10_000:
                errors.append("ma_cross.label_horizon_rows must be between 0 and 10000")
        except (TypeError, ValueError):
            errors.append("ma_cross.label_horizon_rows must be an integer")
    if strategy_type == "portfolio_ma_cross":
        symbols = rules.get("symbols")
        if not isinstance(symbols, list) or not 2 <= len(symbols) <= 50:
            errors.append("portfolio_ma_cross.symbols must contain 2..50 symbols")
        elif any(not str(symbol).isalnum() for symbol in symbols):
            errors.append("portfolio_ma_cross symbols must be alphanumeric")
        try:
            fast, slow = int(rules.get("fast")), int(rules.get("slow"))
            max_positions = int(rules.get("max_positions"))
            position_size = float(rules.get("position_size"))
            if not 2 <= fast < slow <= 250:
                errors.append("portfolio_ma_cross requires 2 <= fast < slow <= 250")
            if not 1 <= max_positions <= 50 or position_size <= 0:
                errors.append("portfolio limits must be positive and max_positions <= 50")
        except (TypeError, ValueError):
            errors.append("portfolio numeric fields are invalid")
    if strategy_type == "indicator_rules":
        symbol = str(rules.get("symbol") or "")
        if not symbol or not symbol.isalnum():
            errors.append("indicator_rules.symbol must be alphanumeric")
        errors.extend(validate_indicator_rules(rules))
    if strategy_type == "multi_timeframe_indicator_rules":
        symbol = str(rules.get("symbol") or "")
        if not symbol or not symbol.isalnum(): errors.append("multi_timeframe_indicator_rules.symbol must be alphanumeric")
        errors.extend(validate_multitimeframe_rules(rules))
    return errors

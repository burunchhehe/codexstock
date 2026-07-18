from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import pstdev, stdev
from typing import Any, Callable


@dataclass(frozen=True)
class IndicatorProfile:
    name: str
    ema_seed: str = "sma"
    rsi_method: str = "wilder"
    bollinger_ddof: int = 0
    price_field: str = "close"
    compatibility_verified: bool = False
    note: str = ""


PROFILES = {
    "STANDARD": IndicatorProfile("STANDARD", compatibility_verified=True, note="Research Forge canonical profile"),
    "CUTLER": IndicatorProfile("CUTLER", rsi_method="sma", compatibility_verified=True, note="Cutler RSI profile"),
    "LS_HTS": IndicatorProfile("LS_HTS", compatibility_verified=False, note="Candidate profile; verify against exported LS HTS values per indicator"),
    "KIWOOM_HTS": IndicatorProfile("KIWOOM_HTS", compatibility_verified=False, note="Candidate profile; verify against exported Kiwoom HTS values per indicator"),
    "KIS": IndicatorProfile("KIS", compatibility_verified=False, note="Candidate profile; verify against KIS reference values per indicator"),
}


INDICATORS: dict[str, dict[str, Any]] = {
    "SMA": {"outputs": ["value"], "required": ["period"]},
    "EMA": {"outputs": ["value"], "required": ["period"]},
    "RSI": {"outputs": ["value"], "required": ["period"]},
    "BOLLINGER": {"outputs": ["lower", "middle", "upper"], "required": ["period", "deviations"]},
    "ENVELOPE": {"outputs": ["lower", "middle", "upper"], "required": ["period", "percent"]},
    "ATR": {"outputs": ["value"], "required": ["period"]},
    "WMA": {"outputs": ["value"], "required": ["period"]},
    "MACD": {"outputs": ["macd", "signal", "histogram"], "required": ["fast", "slow", "signal"]},
    "ROC": {"outputs": ["value"], "required": ["period"]},
    "OBV": {"outputs": ["value"], "required": []},
    "VWAP": {"outputs": ["value"], "required": []},
    "STOCHASTIC": {"outputs": ["k", "d"], "required": ["period", "smooth"]},
    "WILLIAMS_R": {"outputs": ["value"], "required": ["period"]},
    "MFI": {"outputs": ["value"], "required": ["period"]},
    "CCI": {"outputs": ["value"], "required": ["period"]},
    "ADX": {"outputs": ["adx", "plus_di", "minus_di"], "required": ["period"]},
}


def manifest() -> dict[str, Any]:
    return {
        "indicators": [{"name": name, **definition} for name, definition in INDICATORS.items()],
        "profiles": [asdict(profile) for profile in PROFILES.values()],
    }


def calculate(name: str, rows: list[dict[str, Any]], parameters: dict[str, Any], profile_name: str = "STANDARD") -> dict[str, Any]:
    name = name.upper()
    if name not in INDICATORS:
        raise ValueError(f"unsupported indicator: {name}")
    profile = PROFILES.get(profile_name.upper())
    if profile is None:
        raise ValueError(f"unsupported indicator profile: {profile_name}")
    if not rows:
        raise ValueError("indicator rows are required")
    period = int(parameters.get("period") or 14)
    if not 2 <= period <= 500:
        raise ValueError("indicator period must be between 2 and 500")
    closes = _field(rows, profile.price_field)
    if name == "SMA":
        outputs = {"value": _rolling(closes, period, lambda values: sum(values) / len(values))}
    elif name == "EMA":
        outputs = {"value": _ema(closes, period, profile.ema_seed)}
    elif name == "RSI":
        outputs = {"value": _rsi(closes, period, profile.rsi_method)}
    elif name == "WMA":
        divisor = period * (period + 1) / 2
        outputs = {"value": _rolling(closes, period, lambda values: sum((index + 1) * value for index, value in enumerate(values)) / divisor)}
    elif name == "MACD":
        fast, slow, signal_period = int(parameters.get("fast") or 12), int(parameters.get("slow") or 26), int(parameters.get("signal") or 9)
        if not 2 <= fast < slow <= 500 or not 2 <= signal_period <= 200:
            raise ValueError("MACD requires 2 <= fast < slow <= 500 and signal 2..200")
        fast_line, slow_line = _ema(closes, fast, profile.ema_seed), _ema(closes, slow, profile.ema_seed)
        macd = [None if left is None or right is None else left - right for left, right in zip(fast_line, slow_line)]
        signal_line = _ema_optional(macd, signal_period)
        outputs = {"macd": macd, "signal": signal_line, "histogram": [None if left is None or right is None else left - right for left, right in zip(macd, signal_line)]}
    elif name == "ROC":
        values: list[float | None] = [None] * len(closes)
        for index in range(period, len(closes)):
            values[index] = (closes[index] / closes[index - period] - 1) * 100 if closes[index - period] else None
        outputs = {"value": values}
    elif name == "OBV":
        volumes = _field(rows, "volume")
        values = [0.0]
        for index in range(1, len(closes)):
            direction = 1 if closes[index] > closes[index - 1] else -1 if closes[index] < closes[index - 1] else 0
            values.append(values[-1] + volumes[index] * direction)
        outputs = {"value": values}
    elif name == "VWAP":
        highs, lows, volumes = _field(rows, "high"), _field(rows, "low"), _field(rows, "volume")
        cumulative_value = cumulative_volume = 0.0
        values = []
        for high, low, close, volume in zip(highs, lows, closes, volumes):
            cumulative_value += ((high + low + close) / 3) * volume
            cumulative_volume += volume
            values.append(cumulative_value / cumulative_volume if cumulative_volume else None)
        outputs = {"value": values}
    elif name == "STOCHASTIC":
        smooth = int(parameters.get("smooth") or 3)
        k = _stochastic(rows, period)
        d = _rolling_optional(k, smooth)
        outputs = {"k": k, "d": d}
    elif name == "WILLIAMS_R":
        outputs = {"value": _williams_r(rows, period)}
    elif name == "MFI":
        outputs = {"value": _mfi(rows, period)}
    elif name == "CCI":
        outputs = {"value": _cci(rows, period)}
    elif name == "ADX":
        adx, plus_di, minus_di = _adx(rows, period)
        outputs = {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}
    elif name == "BOLLINGER":
        deviations = float(parameters.get("deviations") or 2)
        middle = _rolling(closes, period, lambda values: sum(values) / len(values))
        deviation = _rolling(closes, period, pstdev if profile.bollinger_ddof == 0 else stdev)
        outputs = {
            "lower": [_combine(m, d, -deviations) for m, d in zip(middle, deviation)],
            "middle": middle,
            "upper": [_combine(m, d, deviations) for m, d in zip(middle, deviation)],
        }
    elif name == "ENVELOPE":
        percent = float(parameters.get("percent") or 0.06)
        if not 0 < percent < 1:
            raise ValueError("envelope percent must be between 0 and 1")
        middle = _rolling(closes, period, lambda values: sum(values) / len(values))
        outputs = {
            "lower": [None if value is None else value * (1 - percent) for value in middle],
            "middle": middle,
            "upper": [None if value is None else value * (1 + percent) for value in middle],
        }
    else:
        outputs = {"value": _atr(rows, period)}
    warmup = period
    if name == "MACD":
        warmup = int(parameters.get("slow") or 26) + int(parameters.get("signal") or 9) - 1
    elif name == "STOCHASTIC":
        warmup = period + int(parameters.get("smooth") or 3) - 1
    elif name == "ADX":
        warmup = period * 2 - 1
    return {
        "indicator": name,
        "parameters": dict(parameters),
        "profile": asdict(profile),
        "row_count": len(rows),
        "warmup_bars": warmup,
        "outputs": outputs,
    }


def verify(
    name: str,
    rows: list[dict[str, Any]],
    parameters: dict[str, Any],
    expected: dict[str, float],
    profile_name: str,
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    result = calculate(name, rows, parameters, profile_name)
    tolerance = float(tolerance)
    if tolerance < 0:
        raise ValueError("tolerance cannot be negative")
    comparisons = []
    for output_name, expected_value in expected.items():
        series = result["outputs"].get(output_name)
        if not isinstance(series, list):
            raise ValueError(f"unknown indicator output: {output_name}")
        actual = next((value for value in reversed(series) if value is not None), None)
        difference = None if actual is None else abs(float(actual) - float(expected_value))
        comparisons.append(
            {"output": output_name, "expected": float(expected_value), "actual": actual, "absolute_difference": difference, "passed": difference is not None and difference <= tolerance}
        )
    passed = bool(comparisons) and all(item["passed"] for item in comparisons)
    return {
        "passed": passed,
        "profile": profile_name.upper(),
        "profile_compatibility_verified": passed,
        "tolerance": tolerance,
        "comparisons": comparisons,
        "calculation": result,
    }


def _field(rows: list[dict[str, Any]], name: str) -> list[float]:
    values = []
    for row in rows:
        try:
            value = float(row[name])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"indicator row is missing numeric {name}")
        if not math.isfinite(value):
            raise ValueError(f"indicator {name} must be finite")
        values.append(value)
    return values


def _rolling(values: list[float], period: int, function: Callable[[list[float]], float]) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        output[index] = function(values[index - period + 1 : index + 1])
    return output


def _ema(values: list[float], period: int, seed: str) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    current = sum(values[:period]) / period if seed == "sma" else values[0]
    output[period - 1] = current
    alpha = 2 / (period + 1)
    for index in range(period, len(values)):
        current = values[index] * alpha + current * (1 - alpha)
        output[index] = current
    return output


def _rsi(values: list[float], period: int, method: str) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return output
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(value, 0) for value in changes]
    losses = [max(-value, 0) for value in changes]
    average_gain, average_loss = sum(gains[:period]) / period, sum(losses[:period]) / period
    output[period] = _rsi_value(average_gain, average_loss)
    for index in range(period + 1, len(values)):
        change_index = index - 1
        if method == "sma":
            average_gain = sum(gains[change_index - period + 1 : change_index + 1]) / period
            average_loss = sum(losses[change_index - period + 1 : change_index + 1]) / period
        else:
            average_gain = (average_gain * (period - 1) + gains[change_index]) / period
            average_loss = (average_loss * (period - 1) + losses[change_index]) / period
        output[index] = _rsi_value(average_gain, average_loss)
    return output


def _rsi_value(gain: float, loss: float) -> float:
    if loss == 0:
        return 100.0 if gain > 0 else 50.0
    return 100 - 100 / (1 + gain / loss)


def _atr(rows: list[dict[str, Any]], period: int) -> list[float | None]:
    highs, lows, closes = _field(rows, "high"), _field(rows, "low"), _field(rows, "close")
    ranges = []
    for index in range(len(rows)):
        prior = closes[index - 1] if index else closes[index]
        ranges.append(max(highs[index] - lows[index], abs(highs[index] - prior), abs(lows[index] - prior)))
    return _wilder(ranges, period)


def _ema_optional(values: list[float | None], period: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    valid = [(index, value) for index, value in enumerate(values) if value is not None]
    if len(valid) < period:
        return output
    start_pos = valid[period - 1][0]
    current = sum(float(value) for _, value in valid[:period]) / period
    output[start_pos] = current
    alpha = 2 / (period + 1)
    for index, value in valid[period:]:
        current = float(value) * alpha + current * (1 - alpha)
        output[index] = current
    return output


def _rolling_optional(values: list[float | None], period: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1 : index + 1]
        if all(value is not None for value in window):
            output[index] = sum(float(value) for value in window) / period
    return output


def _stochastic(rows: list[dict[str, Any]], period: int) -> list[float | None]:
    highs, lows, closes = _field(rows, "high"), _field(rows, "low"), _field(rows, "close")
    output: list[float | None] = [None] * len(rows)
    for index in range(period - 1, len(rows)):
        high, low = max(highs[index - period + 1 : index + 1]), min(lows[index - period + 1 : index + 1])
        output[index] = 50.0 if high == low else (closes[index] - low) / (high - low) * 100
    return output


def _williams_r(rows: list[dict[str, Any]], period: int) -> list[float | None]:
    stochastic = _stochastic(rows, period)
    return [None if value is None else value - 100 for value in stochastic]


def _mfi(rows: list[dict[str, Any]], period: int) -> list[float | None]:
    highs, lows, closes, volumes = _field(rows, "high"), _field(rows, "low"), _field(rows, "close"), _field(rows, "volume")
    typical = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes)]
    positive, negative = [0.0] * len(rows), [0.0] * len(rows)
    for index in range(1, len(rows)):
        flow = typical[index] * volumes[index]
        if typical[index] > typical[index - 1]: positive[index] = flow
        elif typical[index] < typical[index - 1]: negative[index] = flow
    output: list[float | None] = [None] * len(rows)
    for index in range(period, len(rows)):
        pos, neg = sum(positive[index - period + 1 : index + 1]), sum(negative[index - period + 1 : index + 1])
        output[index] = 100.0 if neg == 0 and pos > 0 else 50.0 if neg == 0 else 100 - 100 / (1 + pos / neg)
    return output


def _cci(rows: list[dict[str, Any]], period: int) -> list[float | None]:
    highs, lows, closes = _field(rows, "high"), _field(rows, "low"), _field(rows, "close")
    typical = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes)]
    output: list[float | None] = [None] * len(rows)
    for index in range(period - 1, len(rows)):
        window = typical[index - period + 1 : index + 1]
        mean = sum(window) / period
        deviation = sum(abs(value - mean) for value in window) / period
        output[index] = 0.0 if deviation == 0 else (typical[index] - mean) / (0.015 * deviation)
    return output


def _wilder(values: list[float], period: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    current = sum(values[:period]) / period
    output[period - 1] = current
    for index in range(period, len(values)):
        current = (current * (period - 1) + values[index]) / period
        output[index] = current
    return output


def _adx(rows: list[dict[str, Any]], period: int) -> tuple[list[float | None], list[float | None], list[float | None]]:
    highs, lows, closes = _field(rows, "high"), _field(rows, "low"), _field(rows, "close")
    tr, plus_dm, minus_dm = [0.0], [0.0], [0.0]
    for index in range(1, len(rows)):
        up, down = highs[index] - highs[index - 1], lows[index - 1] - lows[index]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(highs[index] - lows[index], abs(highs[index] - closes[index - 1]), abs(lows[index] - closes[index - 1])))
    atr, plus_smoothed, minus_smoothed = _wilder(tr, period), _wilder(plus_dm, period), _wilder(minus_dm, period)
    plus_di: list[float | None] = [None] * len(rows)
    minus_di: list[float | None] = [None] * len(rows)
    dx: list[float | None] = [None] * len(rows)
    for index in range(period - 1, len(rows)):
        if atr[index] and atr[index] > 0:
            plus_di[index] = float(plus_smoothed[index]) / float(atr[index]) * 100
            minus_di[index] = float(minus_smoothed[index]) / float(atr[index]) * 100
            total = plus_di[index] + minus_di[index]
            dx[index] = abs(plus_di[index] - minus_di[index]) / total * 100 if total else 0.0
    adx = _wilder_optional(dx, period)
    return adx, plus_di, minus_di


def _wilder_optional(values: list[float | None], period: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    valid = [(index, float(value)) for index, value in enumerate(values) if value is not None]
    if len(valid) < period:
        return output
    current = sum(value for _, value in valid[:period]) / period
    output[valid[period - 1][0]] = current
    for index, value in valid[period:]:
        current = (current * (period - 1) + value) / period
        output[index] = current
    return output


def _combine(middle: float | None, deviation: float | None, multiplier: float) -> float | None:
    return None if middle is None or deviation is None else middle + deviation * multiplier

from __future__ import annotations

import math
import random
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal


Side = Literal["BUY", "SELL"]
SYMBOLS = ("AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "AMD", "NFLX", "SPY", "QQQ", "PLTR")

MSG_QTY = "\uc218\ub7c9\uc740 0\ubcf4\ub2e4 \ucee4\uc57c \ud569\ub2c8\ub2e4"
MSG_SIDE = "\uc8fc\ubb38 \uad6c\ubd84\uc740 BUY \ub610\ub294 SELL\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4"
MSG_CASH = "\ud604\uae08\uc774 \ubd80\uc871\ud569\ub2c8\ub2e4"
MSG_SHARES = "\ubcf4\uc720 \uc218\ub7c9\uc774 \ubd80\uc871\ud569\ub2c8\ub2e4"
MSG_WAIT = "\uc9c0\ud45c \uacc4\uc0b0\uc744 \uc704\ud55c \ub370\uc774\ud130\uac00 \ubd80\uc871\ud569\ub2c8\ub2e4"
MSG_BUY_REASON = "\ub2e8\uae30\uc120\uc774 \uc7a5\uae30\uc120 \uc704\uc5d0 \uc788\uc2b5\ub2c8\ub2e4"
MSG_SELL_REASON = "\ub2e8\uae30\uc120\uc774 \uc7a5\uae30\uc120 \uc544\ub798\uc5d0 \uc788\uc2b5\ub2c8\ub2e4"
MSG_HOLD_REASON = "\uc0c8 \uc8fc\ubb38 \uc870\uac74\uc774 \uc544\ub2d9\ub2c8\ub2e4"
MSG_RISK_ORDERS = "\uc624\ub298 \uc8fc\ubb38 \ud55c\ub3c4\uc5d0 \ub3c4\ub2ec\ud588\uc2b5\ub2c8\ub2e4"
MSG_RISK_POSITION = "\ud55c \uc885\ubaa9 \ube44\uc911 \ud55c\ub3c4\ub97c \ub118\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4"


def moving_average(values: list[float], window: int) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            output.append(None)
            continue
        chunk = values[index + 1 - window : index + 1]
        output.append(sum(chunk) / window)
    return output


def rsi(values: list[float], window: int = 14) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    for index in range(window, len(values)):
        gains = 0.0
        losses = 0.0
        for prev, current in zip(values[index - window : index], values[index - window + 1 : index + 1]):
            delta = current - prev
            if delta >= 0:
                gains += delta
            else:
                losses -= delta
        output[index] = 100.0 if losses == 0 else 100.0 - (100.0 / (1.0 + gains / losses))
    return output


def generate_prices(symbol: str, bars: int, seed_offset: int = 0) -> list[float]:
    symbol = symbol.upper()
    random.seed(f"{symbol}:{seed_offset}")
    price = 60.0 + (sum(ord(char) for char in symbol) % 170)
    volatility = 0.8 + (sum(ord(char) for char in symbol) % 9) / 10
    drift = ((sum(ord(char) for char in symbol) % 11) - 4) / 10000
    prices: list[float] = []
    for index in range(bars):
        cycle = math.sin(index / 18.0 + len(symbol)) * 0.004
        shock = random.gauss(drift + cycle, volatility / 100)
        price = max(2.0, price * (1.0 + shock))
        prices.append(round(price, 2))
    return prices


def performance_stats(equity_curve: list[float], initial_cash: float) -> dict[str, float]:
    final_equity = equity_curve[-1]
    returns = [(equity_curve[i] / equity_curve[i - 1]) - 1.0 for i in range(1, len(equity_curve))]
    avg_return = sum(returns) / len(returns) if returns else 0.0
    variance = sum((value - avg_return) ** 2 for value in returns) / len(returns) if returns else 0.0
    sharpe = (avg_return / math.sqrt(variance) * math.sqrt(252)) if variance else 0.0
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value / peak) - 1.0)
    return {
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(((final_equity / initial_cash) - 1.0) * 100.0, 2),
        "max_drawdown_pct": round(max_drawdown * 100.0, 2),
        "sharpe": round(sharpe, 2),
    }


def trade_quality_stats(trades: list[dict[str, object]], final_price: float | None = None) -> dict[str, object]:
    round_trips: list[dict[str, float | int]] = []
    entry: dict[str, object] | None = None
    for trade in trades:
        side = str(trade.get("side", "")).upper()
        if side == "BUY":
            entry = trade
        elif side == "SELL" and entry:
            buy_price = float(entry.get("price", 0) or 0)
            sell_price = float(trade.get("price", 0) or 0)
            if buy_price > 0 and sell_price > 0:
                pnl_pct = ((sell_price / buy_price) - 1.0) * 100.0
                round_trips.append(
                    {
                        "entry_day": int(entry.get("day", 0) or 0),
                        "exit_day": int(trade.get("day", 0) or 0),
                        "holding_days": max(0, int(trade.get("day", 0) or 0) - int(entry.get("day", 0) or 0)),
                        "pnl_pct": round(pnl_pct, 2),
                    }
                )
            entry = None
    if entry and final_price:
        buy_price = float(entry.get("price", 0) or 0)
        if buy_price > 0:
            round_trips.append(
                {
                    "entry_day": int(entry.get("day", 0) or 0),
                    "exit_day": int(entry.get("day", 0) or 0),
                    "holding_days": 0,
                    "pnl_pct": round(((final_price / buy_price) - 1.0) * 100.0, 2),
                }
            )
    wins = [float(item["pnl_pct"]) for item in round_trips if float(item["pnl_pct"]) > 0]
    losses = [float(item["pnl_pct"]) for item in round_trips if float(item["pnl_pct"]) <= 0]
    total = len(round_trips)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    expectancy = ((len(wins) / total) * avg_win - (len(losses) / total) * avg_loss) if total else 0.0
    if total > 1:
        avg = sum(float(item["pnl_pct"]) for item in round_trips) / total
        variance = sum((float(item["pnl_pct"]) - avg) ** 2 for item in round_trips) / total
        sqn = (avg / math.sqrt(variance)) * math.sqrt(total) if variance else 0.0
    else:
        sqn = 0.0
    longest_loss_streak = 0
    current_loss_streak = 0
    for item in round_trips:
        if float(item["pnl_pct"]) <= 0:
            current_loss_streak += 1
            longest_loss_streak = max(longest_loss_streak, current_loss_streak)
        else:
            current_loss_streak = 0
    return {
        "round_trips": round_trips[-30:],
        "closed_trades": total,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate_pct": round((len(wins) / total) * 100.0, 2) if total else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else round(gross_profit, 2) if gross_profit else 0.0,
        "average_win_pct": round(avg_win, 2),
        "average_loss_pct": round(avg_loss, 2),
        "expectancy_pct": round(expectancy, 2),
        "sqn": round(sqn, 2),
        "longest_loss_streak": longest_loss_streak,
    }


def evaluate_ma_cross_prices(prices: list[float], fast: int, slow: int, initial_cash: float) -> dict[str, object]:
    fast_ma = moving_average(prices, fast)
    slow_ma = moving_average(prices, slow)
    rsi_values = rsi(prices)
    cash = initial_cash
    shares = 0.0
    trades: list[dict[str, object]] = []
    equity_curve: list[float] = []
    signals: list[str] = []

    for index, current in enumerate(prices):
        signal = "HOLD"
        f_value = fast_ma[index]
        s_value = slow_ma[index]
        r_value = rsi_values[index]
        if f_value is not None and s_value is not None:
            buy_signal = f_value > s_value and shares == 0 and (r_value is None or r_value < 72)
            sell_signal = f_value < s_value and shares > 0
            if buy_signal:
                shares = cash / current
                cash = 0.0
                signal = "BUY"
                trades.append({"day": index + 1, "side": "BUY", "price": current, "reason": "fast_ma_above_slow_ma"})
            elif sell_signal:
                cash = shares * current
                shares = 0.0
                signal = "SELL"
                trades.append({"day": index + 1, "side": "SELL", "price": current, "reason": "fast_ma_below_slow_ma"})
        signals.append(signal)
        equity_curve.append(round(cash + shares * current, 2))

    stats = performance_stats(equity_curve, initial_cash)
    quality = trade_quality_stats(trades, prices[-1] if prices else None)
    stats.update(
        {
            "trade_count": len(trades),
            "trades": trades,
            "trade_quality": quality,
            "prices": prices,
            "equity_curve": equity_curve,
            "signals": signals,
            "fast_ma": fast_ma,
            "slow_ma": slow_ma,
            "rsi": rsi_values,
        }
    )
    return stats


def evaluate_protected_ma_cross_prices(
    prices: list[float],
    fast: int,
    slow: int,
    initial_cash: float,
    config: dict[str, object] | None = None,
) -> dict[str, object]:
    cfg = {
        "cooldown_bars": 5,
        "stop_loss_pct": -7.0,
        "take_profit_pct": 18.0,
        "stoploss_guard_lookback": 80,
        "stoploss_guard_limit": 3,
        "stoploss_guard_lock_bars": 20,
        "max_drawdown_limit_pct": -22.0,
        "max_drawdown_lock_bars": 30,
        "low_profit_lookback_trades": 3,
        "low_profit_required_pct": 1.0,
        "low_profit_lock_bars": 15,
    }
    if config:
        cfg.update(config)
    fast_ma = moving_average(prices, fast)
    slow_ma = moving_average(prices, slow)
    rsi_values = rsi(prices)
    cash = initial_cash
    shares = 0.0
    entry_price = 0.0
    peak_equity = initial_cash
    locked_until = 0
    lock_reason = ""
    trades: list[dict[str, object]] = []
    closed_rounds: list[dict[str, object]] = []
    protection_events: list[dict[str, object]] = []
    equity_curve: list[float] = []
    signals: list[str] = []

    def lock(index: int, bars: int, reason: str) -> None:
        nonlocal locked_until, lock_reason
        until = index + max(1, bars)
        if until > locked_until:
            locked_until = until
            lock_reason = reason
            protection_events.append({"day": index + 1, "until_day": until + 1, "reason": reason})

    def close_trade(index: int, current: float, reason: str) -> None:
        nonlocal cash, shares, entry_price
        if shares <= 0:
            return
        cash = shares * current
        pnl_pct = ((current / entry_price) - 1.0) * 100.0 if entry_price else 0.0
        trades.append({"day": index + 1, "side": "SELL", "price": current, "reason": reason, "pnl_pct": round(pnl_pct, 2)})
        closed_rounds.append({"day": index + 1, "pnl_pct": pnl_pct, "reason": reason})
        shares = 0.0
        entry_price = 0.0
        lock(index, int(cfg["cooldown_bars"]), "CooldownPeriod")
        recent_losses = [
            item
            for item in closed_rounds
            if index + 1 - int(item["day"]) <= int(cfg["stoploss_guard_lookback"])
            and float(item["pnl_pct"]) <= float(cfg["stop_loss_pct"])
        ]
        if len(recent_losses) >= int(cfg["stoploss_guard_limit"]):
            lock(index, int(cfg["stoploss_guard_lock_bars"]), "StoplossGuard")
        recent_rounds = closed_rounds[-int(cfg["low_profit_lookback_trades"]) :]
        if len(recent_rounds) >= int(cfg["low_profit_lookback_trades"]):
            avg_profit = sum(float(item["pnl_pct"]) for item in recent_rounds) / len(recent_rounds)
            if avg_profit < float(cfg["low_profit_required_pct"]):
                lock(index, int(cfg["low_profit_lock_bars"]), "LowProfitPairs")

    for index, current in enumerate(prices):
        signal = "HOLD"
        equity = cash + shares * current
        peak_equity = max(peak_equity, equity)
        drawdown_pct = ((equity / peak_equity) - 1.0) * 100.0 if peak_equity else 0.0
        if drawdown_pct <= float(cfg["max_drawdown_limit_pct"]):
            lock(index, int(cfg["max_drawdown_lock_bars"]), "MaxDrawdown")
        f_value = fast_ma[index]
        s_value = slow_ma[index]
        r_value = rsi_values[index]
        pnl_pct = ((current / entry_price) - 1.0) * 100.0 if entry_price and shares > 0 else 0.0
        stop_sell = shares > 0 and pnl_pct <= float(cfg["stop_loss_pct"])
        take_sell = shares > 0 and pnl_pct >= float(cfg["take_profit_pct"])
        if shares > 0 and (stop_sell or take_sell):
            signal = "SELL"
            close_trade(index, current, "stop_loss" if stop_sell else "take_profit")
        elif f_value is not None and s_value is not None:
            buy_signal = f_value > s_value and shares == 0 and index >= locked_until and (r_value is None or r_value < 72)
            sell_signal = f_value < s_value and shares > 0
            if buy_signal:
                shares = cash / current
                cash = 0.0
                entry_price = current
                signal = "BUY"
                trades.append({"day": index + 1, "side": "BUY", "price": current, "reason": "protected_fast_ma_above_slow_ma"})
            elif sell_signal:
                signal = "SELL"
                close_trade(index, current, "trend_down")
        if index < locked_until and shares == 0 and signal == "HOLD":
            signal = f"LOCKED:{lock_reason}"
        signals.append(signal)
        equity_curve.append(round(cash + shares * current, 2))

    stats = performance_stats(equity_curve, initial_cash)
    quality = trade_quality_stats(trades, prices[-1] if prices else None)
    stats.update(
        {
            "trade_count": len(trades),
            "trades": trades,
            "trade_quality": quality,
            "prices": prices,
            "equity_curve": equity_curve,
            "signals": signals,
            "fast_ma": fast_ma,
            "slow_ma": slow_ma,
            "rsi": rsi_values,
            "protection_events": protection_events[-80:],
            "protection_config": cfg,
        }
    )
    return stats


def extract_strategy_from_text(text: str) -> dict[str, object]:
    source = " ".join((text or "").replace("\n", " ").split())
    lower = source.lower()
    numbers = [int(item) for item in re.findall(r"(?<!\d)(\d{1,3})(?!\d)", source)]
    ma_numbers = [value for value in numbers if 2 <= value <= 240]
    fast = 20
    slow = 60
    if len(ma_numbers) >= 2:
        fast, slow = sorted(ma_numbers[:2])
        if fast == slow:
            slow = fast * 3
    elif ma_numbers:
        fast = min(ma_numbers[0], 20)
        slow = max(ma_numbers[0], 60)

    percents = [float(item) for item in re.findall(r"(-?\d+(?:\.\d+)?)\s*%", source)]
    stop_loss = -7.0
    take_profit = 15.0
    for value in percents:
        context_index = source.find(f"{value:g}%")
        context = source[max(0, context_index - 20) : context_index + 24] if context_index >= 0 else source
        if "익절" in context or "목표" in context or "take" in context.lower():
            take_profit = abs(value)
        elif "손절" in context or "stop" in context.lower() or value < 0:
            stop_loss = -abs(value)

    uses_rsi = "rsi" in lower or "과매도" in source or "과매수" in source
    uses_breakout = "돌파" in source or "신고가" in source or "breakout" in lower
    breakout_window = next((value for value in ma_numbers if 10 <= value <= 120), 20)
    oversold = 30
    overbought = 70
    if uses_rsi:
        rsi_context_numbers = []
        for match in re.finditer(r"rsi|과매도|과매수", source, re.IGNORECASE):
            context = source[max(0, match.start() - 24) : match.end() + 36]
            rsi_context_numbers.extend(int(item) for item in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", context))
        low_values = [value for value in rsi_context_numbers if 10 <= value <= 40]
        high_values = [value for value in rsi_context_numbers if 50 <= value <= 90]
        if low_values and "과매도" in source:
            oversold = min(low_values)
        if high_values:
            overbought = max(high_values)

    rule_parts = []
    if "이평" in source or "이동평균" in source or "ma" in lower or "평균" in source:
        rule_parts.append(f"이동평균 {fast}/{slow} 추세")
    if uses_breakout:
        rule_parts.append(f"{breakout_window}일 고가 돌파")
    if uses_rsi:
        rule_parts.append(f"RSI {oversold}/{overbought}")
    if not rule_parts:
        rule_parts.append(f"기본 이동평균 {fast}/{slow}")

    return {
        "name": "자막추출 전략",
        "summary": " + ".join(rule_parts),
        "fast": fast,
        "slow": slow,
        "uses_rsi": uses_rsi,
        "uses_breakout": uses_breakout,
        "breakout_window": breakout_window,
        "rsi_oversold": oversold,
        "rsi_overbought": overbought,
        "stop_loss_pct": stop_loss,
        "take_profit_pct": take_profit,
        "confidence": round(min(0.95, 0.45 + 0.12 * len(rule_parts) + min(len(source), 2000) / 10000), 2),
        "extracted_from_chars": len(source),
        "notes": [
            "자막에서 숫자, 이동평균, RSI, 돌파, 손절/익절 키워드를 추출했습니다.",
            "첫 버전은 규칙 기반 추출이며, 결과는 반드시 백테스트와 복기로 검증해야 합니다.",
        ],
    }


def evaluate_text_strategy_prices(prices: list[float], strategy: dict[str, object], initial_cash: float) -> dict[str, object]:
    fast = int(strategy.get("fast", 20))
    slow = int(strategy.get("slow", 60))
    stop_loss_pct = float(strategy.get("stop_loss_pct", -7.0))
    take_profit_pct = float(strategy.get("take_profit_pct", 15.0))
    uses_rsi = bool(strategy.get("uses_rsi", False))
    uses_breakout = bool(strategy.get("uses_breakout", False))
    breakout_window = int(strategy.get("breakout_window", 20))
    oversold = float(strategy.get("rsi_oversold", 30))
    overbought = float(strategy.get("rsi_overbought", 70))
    fast_ma = moving_average(prices, fast)
    slow_ma = moving_average(prices, slow)
    rsi_values = rsi(prices)
    cash = initial_cash
    shares = 0.0
    entry_price = 0.0
    trades: list[dict[str, object]] = []
    equity_curve: list[float] = []
    signals: list[str] = []

    for index, current in enumerate(prices):
        signal = "HOLD"
        f_value = fast_ma[index]
        s_value = slow_ma[index]
        r_value = rsi_values[index]
        previous_high = max(prices[max(0, index - breakout_window) : index], default=current)
        trend_buy = f_value is not None and s_value is not None and f_value > s_value
        trend_sell = f_value is not None and s_value is not None and f_value < s_value
        rsi_buy = uses_rsi and r_value is not None and r_value <= oversold
        rsi_sell = uses_rsi and r_value is not None and r_value >= overbought
        breakout_buy = uses_breakout and index > breakout_window and current > previous_high
        pnl_pct = ((current / entry_price) - 1.0) * 100 if entry_price and shares > 0 else 0.0
        stop_sell = shares > 0 and pnl_pct <= stop_loss_pct
        take_sell = shares > 0 and pnl_pct >= take_profit_pct

        if shares == 0 and (trend_buy or rsi_buy or breakout_buy):
            shares = cash / current
            cash = 0.0
            entry_price = current
            signal = "BUY"
            reason = "breakout" if breakout_buy else "rsi_oversold" if rsi_buy else "trend"
            trades.append({"day": index + 1, "side": "BUY", "price": current, "reason": reason})
        elif shares > 0 and (trend_sell or rsi_sell or stop_sell or take_sell):
            cash = shares * current
            shares = 0.0
            signal = "SELL"
            reason = "stop_loss" if stop_sell else "take_profit" if take_sell else "rsi_overbought" if rsi_sell else "trend_down"
            trades.append({"day": index + 1, "side": "SELL", "price": current, "reason": reason})
            entry_price = 0.0
        signals.append(signal)
        equity_curve.append(round(cash + shares * current, 2))

    stats = performance_stats(equity_curve, initial_cash)
    quality = trade_quality_stats(trades, prices[-1] if prices else None)
    stats.update(
        {
            "trade_count": len(trades),
            "trades": trades,
            "trade_quality": quality,
            "prices": prices,
            "equity_curve": equity_curve,
            "signals": signals,
            "fast_ma": fast_ma,
            "slow_ma": slow_ma,
            "rsi": rsi_values,
        }
    )
    return stats


@dataclass
class NativeJournal:
    events: list[dict[str, object]] = field(default_factory=list)

    def add(self, event_type: str, message: str, payload: dict[str, object] | None = None) -> None:
        self.events.append({"time": time.time(), "type": event_type, "message": message, "payload": payload or {}})
        if len(self.events) > 200:
            self.events = self.events[-200:]

    def recent(self, limit: int = 40) -> list[dict[str, object]]:
        return list(reversed(self.events[-limit:]))


@dataclass
class StrategySlot:
    name: str
    fast: int
    slow: int
    memo: str = ""
    locked: bool = False


@dataclass
class NativeLogicBook:
    slots: dict[str, StrategySlot] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.slots:
            self.slots["기준전략"] = StrategySlot("기준전략", fast=12, slow=32, memo="기본 이동평균 교차 전략", locked=True)

    def save(self, name: str, fast: int, slow: int, memo: str = "", locked: bool = False) -> dict[str, object]:
        if name in self.slots and self.slots[name].locked:
            raise ValueError("잠긴 로직은 수정할 수 없습니다")
        self.slots[name] = StrategySlot(name=name, fast=fast, slow=slow, memo=memo, locked=locked)
        return self.as_dict(name)

    def lock(self, name: str, locked: bool) -> dict[str, object]:
        if name not in self.slots:
            raise ValueError("로직을 찾을 수 없습니다")
        self.slots[name].locked = locked
        return self.as_dict(name)

    def as_dict(self, name: str) -> dict[str, object]:
        slot = self.slots[name]
        return {"name": slot.name, "fast": slot.fast, "slow": slot.slow, "memo": slot.memo, "locked": slot.locked}

    def list(self) -> list[dict[str, object]]:
        return [self.as_dict(name) for name in sorted(self.slots)]


@dataclass
class NativeMarket:
    bars: int = 220
    prices: dict[str, list[float]] = field(default_factory=dict)
    opens: dict[str, float] = field(default_factory=dict)
    volumes: dict[str, int] = field(default_factory=dict)
    tick_index: int = 0

    def __post_init__(self) -> None:
        for symbol in SYMBOLS:
            series = generate_prices(symbol, self.bars)
            self.prices[symbol] = series
            self.opens[symbol] = series[0]
            self.volumes[symbol] = 500_000 + (sum(ord(char) for char in symbol) * 3711)

    def tick(self) -> dict[str, object]:
        self.tick_index += 1
        snapshot = []
        for symbol in SYMBOLS:
            series = self.prices[symbol]
            last = series[-1]
            random.seed(f"tick:{symbol}:{self.tick_index}")
            next_price = max(1.0, round(last * (1.0 + random.gauss(0.00015, 0.0025)), 2))
            series.append(next_price)
            if len(series) > self.bars:
                series.pop(0)
            self.volumes[symbol] += random.randint(1_000, 45_000)
            change_pct = ((next_price / self.opens[symbol]) - 1.0) * 100
            snapshot.append(
                {
                    "symbol": symbol,
                    "price": next_price,
                    "open": round(self.opens[symbol], 2),
                    "change_pct": round(change_pct, 2),
                    "volume": self.volumes[symbol],
                }
            )
        return {"time": time.time(), "quotes": snapshot}

    def history(self, symbol: str, bars: int = 180) -> list[float]:
        series = self.prices.get(symbol.upper())
        if not series:
            series = generate_prices(symbol, max(bars, 220), seed_offset=1)
        return series[-bars:]

    def quote(self, symbol: str) -> dict[str, object]:
        symbol = symbol.upper()
        series = self.history(symbol)
        price = series[-1]
        open_price = self.opens.get(symbol, series[0])
        return {
            "symbol": symbol,
            "price": price,
            "open": round(open_price, 2),
            "change_pct": round(((price / open_price) - 1.0) * 100, 2),
            "volume": self.volumes.get(symbol, 0),
        }

    def orderbook(self, symbol: str, levels: int = 5) -> dict[str, object]:
        quote = self.quote(symbol)
        mid = float(quote["price"])
        spread = max(0.01, mid * 0.00035)
        asks = []
        bids = []
        for level in range(levels, 0, -1):
            random.seed(f"ask:{symbol}:{self.tick_index}:{level}")
            asks.append({"price": round(mid + spread * level, 2), "size": random.randint(20, 600)})
        for level in range(1, levels + 1):
            random.seed(f"bid:{symbol}:{self.tick_index}:{level}")
            bids.append({"price": round(mid - spread * level, 2), "size": random.randint(20, 600)})
        return {"symbol": symbol.upper(), "mid": mid, "spread": round(spread, 4), "asks": asks, "bids": bids}


@dataclass
class NativeBroker:
    market: NativeMarket
    journal: NativeJournal
    cash: float = 100_000.0
    positions: dict[str, float] = field(default_factory=dict)
    orders: list[dict[str, object]] = field(default_factory=list)
    max_orders: int = 20
    max_position_pct: float = 0.25

    def submit_market_order(self, symbol: str, side: Side, quantity: float) -> dict[str, object]:
        if quantity <= 0:
            raise ValueError(MSG_QTY)
        symbol = symbol.upper()
        side = side.upper()  # type: ignore[assignment]
        if side not in ("BUY", "SELL"):
            raise ValueError(MSG_SIDE)
        price = float(self.market.quote(symbol)["price"])
        notional = price * quantity
        fee = max(1.0, notional * 0.0005)
        if side == "BUY":
            if len(self.orders) >= self.max_orders:
                raise ValueError(MSG_RISK_ORDERS)
            portfolio = self.portfolio()
            current_value = next((item["value"] for item in portfolio["positions"] if item["symbol"] == symbol), 0.0)
            next_weight = (float(current_value) + notional) / max(1.0, float(portfolio["equity"]))
            if next_weight > self.max_position_pct:
                raise ValueError(MSG_RISK_POSITION)
            if self.cash < notional + fee:
                raise ValueError(MSG_CASH)
            self.cash -= notional + fee
            self.positions[symbol] = self.positions.get(symbol, 0.0) + quantity
        else:
            current = self.positions.get(symbol, 0.0)
            if current < quantity:
                raise ValueError(MSG_SHARES)
            self.positions[symbol] = current - quantity
            self.cash += notional - fee
        order = {
            "id": len(self.orders) + 1,
            "time": time.time(),
            "symbol": symbol,
            "side": side,
            "quantity": round(quantity, 4),
            "price": round(price, 2),
            "fee": round(fee, 2),
            "status": "FILLED",
        }
        self.orders.append(order)
        self.journal.add(
            "ORDER",
            f"{symbol} {side} {round(quantity, 4)} @ {round(price, 2)}",
            {"order": order, "portfolio": self.portfolio()},
        )
        return order

    def portfolio(self) -> dict[str, object]:
        items = []
        market_value = 0.0
        for symbol, quantity in sorted(self.positions.items()):
            if quantity <= 0:
                continue
            price = float(self.market.quote(symbol)["price"])
            value = price * quantity
            market_value += value
            items.append({"symbol": symbol, "quantity": round(quantity, 4), "price": round(price, 2), "value": round(value, 2)})
        return {
            "cash": round(self.cash, 2),
            "market_value": round(market_value, 2),
            "equity": round(self.cash + market_value, 2),
            "positions": items,
            "orders": self.orders[-20:],
            "risk": {
                "max_orders": self.max_orders,
                "used_orders": len(self.orders),
                "max_position_pct": round(self.max_position_pct * 100, 2),
            },
        }


@dataclass
class NativeStrategyRunner:
    market: NativeMarket
    broker: NativeBroker

    def run_once(self, symbol: str, fast: int = 12, slow: int = 32, quantity: float = 10) -> dict[str, object]:
        symbol = symbol.upper()
        prices = self.market.history(symbol, max(120, slow + 5))
        fast_now = moving_average(prices, fast)[-1]
        slow_now = moving_average(prices, slow)[-1]
        position = self.broker.positions.get(symbol, 0.0)
        if fast_now is None or slow_now is None:
            return {"action": "WAIT", "reason": MSG_WAIT, "portfolio": self.broker.portfolio()}
        if fast_now > slow_now and position <= 0:
            order = self.broker.submit_market_order(symbol, "BUY", quantity)
            return {"action": "BUY", "reason": MSG_BUY_REASON, "order": order, "portfolio": self.broker.portfolio()}
        if fast_now < slow_now and position > 0:
            order = self.broker.submit_market_order(symbol, "SELL", min(quantity, position))
            return {"action": "SELL", "reason": MSG_SELL_REASON, "order": order, "portfolio": self.broker.portfolio()}
        return {"action": "HOLD", "reason": MSG_HOLD_REASON, "portfolio": self.broker.portfolio()}


@dataclass
class NativeBacktester:
    initial_cash: float = 10_000.0

    def _bars_from_dates(self, start_date: str, end_date: str) -> tuple[int, list[str]]:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        if end <= start:
            raise ValueError("종료일은 시작일보다 뒤여야 합니다")
        calendar_days = (end - start).days + 1
        bars = max(60, min(3650, int(calendar_days * 5 / 7)))
        if bars <= 1:
            bars = 60
        span = max(1, (end - start).days)
        dates = [
            (start + timedelta(days=round((span * index) / max(1, bars - 1)))).isoformat()
            for index in range(bars)
        ]
        dates[-1] = end.isoformat()
        return bars, dates

    def run_ma_cross(self, symbol: str, days: int, fast: int, slow: int) -> dict[str, object]:
        prices = generate_prices(symbol, days, seed_offset=7)
        result = evaluate_ma_cross_prices(prices, fast, slow, self.initial_cash)
        return {
            "symbol": symbol.upper(),
            "days": days,
            "fast_window": fast,
            "slow_window": slow,
            "final_equity": result["final_equity"],
            "total_return_pct": result["total_return_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe": result["sharpe"],
            "trade_count": result["trade_count"],
            "trades": result["trades"][-20:],
            "trade_actions_sample": result["trades"][-120:],
            "trade_action_count": len(result["trades"]),
            "trade_quality": result["trade_quality"],
            "prices": result["prices"],
            "equity_curve": result["equity_curve"],
            "signals": result["signals"][-120:],
            "fast_ma": result["fast_ma"],
            "slow_ma": result["slow_ma"],
            "rsi": result["rsi"],
        }

    def run_ma_cross_range(self, symbol: str, start_date: str, end_date: str, fast: int, slow: int) -> dict[str, object]:
        bars, dates = self._bars_from_dates(start_date, end_date)
        prices = generate_prices(symbol, bars, seed_offset=sum(ord(ch) for ch in start_date + end_date))
        result = evaluate_ma_cross_prices(prices, fast, slow, self.initial_cash)
        buy_hold_return = round(((prices[-1] / prices[0]) - 1.0) * 100.0, 2)
        payload = {
            "symbol": symbol.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "bars": bars,
            "fast_window": fast,
            "slow_window": slow,
            "buy_hold_return_pct": buy_hold_return,
            "final_equity": result["final_equity"],
            "total_return_pct": result["total_return_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe": result["sharpe"],
            "trade_count": result["trade_count"],
            "trades": result["trades"][-40:],
            "trade_actions_sample": result["trades"][-120:],
            "trade_action_count": len(result["trades"]),
            "trade_quality": result["trade_quality"],
            "dates": dates,
            "prices": prices,
            "equity_curve": result["equity_curve"],
            "signals": result["signals"],
            "fast_ma": result["fast_ma"],
            "slow_ma": result["slow_ma"],
            "rsi": result["rsi"],
        }
        return payload

    def run_protected_range(self, symbol: str, start_date: str, end_date: str, fast: int, slow: int) -> dict[str, object]:
        bars, dates = self._bars_from_dates(start_date, end_date)
        seed = sum(ord(ch) for ch in f"{symbol}:{start_date}:{end_date}:protected")
        prices = generate_prices(symbol, bars, seed_offset=seed)
        base = evaluate_ma_cross_prices(prices, fast, slow, self.initial_cash)
        protected = evaluate_protected_ma_cross_prices(prices, fast, slow, self.initial_cash)
        buy_hold_return = round(((prices[-1] / prices[0]) - 1.0) * 100.0, 2)
        return {
            "symbol": symbol.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "bars": bars,
            "fast_window": fast,
            "slow_window": slow,
            "buy_hold_return_pct": buy_hold_return,
            "base": {
                "symbol": symbol.upper(),
                "start_date": start_date,
                "end_date": end_date,
                "final_equity": base["final_equity"],
                "total_return_pct": base["total_return_pct"],
                "max_drawdown_pct": base["max_drawdown_pct"],
                "sharpe": base["sharpe"],
                "trade_count": base["trade_count"],
                "trades": base["trades"][-40:],
                "trade_actions_sample": base["trades"][-120:],
                "trade_action_count": len(base["trades"]),
                "trade_quality": base["trade_quality"],
                "dates": dates,
                "equity_curve": base["equity_curve"],
            },
            "protected": {
                "symbol": symbol.upper(),
                "start_date": start_date,
                "end_date": end_date,
                "final_equity": protected["final_equity"],
                "total_return_pct": protected["total_return_pct"],
                "max_drawdown_pct": protected["max_drawdown_pct"],
                "sharpe": protected["sharpe"],
                "trade_count": protected["trade_count"],
                "trades": protected["trades"][-40:],
                "trade_actions_sample": protected["trades"][-120:],
                "trade_action_count": len(protected["trades"]),
                "trade_quality": protected["trade_quality"],
                "dates": dates,
                "equity_curve": protected["equity_curve"],
                "protection_events": protected["protection_events"],
                "protection_config": protected["protection_config"],
            },
            "dates": dates,
            "prices": prices,
            "impact": {
                "return_delta_pct": round(float(protected["total_return_pct"]) - float(base["total_return_pct"]), 2),
                "drawdown_delta_pct": round(float(protected["max_drawdown_pct"]) - float(base["max_drawdown_pct"]), 2),
                "lock_count": len(protected["protection_events"]),
                "verdict": "보호장치 유리" if float(protected["max_drawdown_pct"]) > float(base["max_drawdown_pct"]) else "수익 우선",
            },
            "inspired_by": ["Freqtrade Protections", "StoplossGuard", "MaxDrawdown", "LowProfitPairs", "CooldownPeriod"],
        }

    def compare_symbols_range(self, symbols: list[str], start_date: str, end_date: str, fast: int, slow: int) -> dict[str, object]:
        unique_symbols = []
        for symbol in symbols:
            symbol = symbol.strip().upper()
            if symbol and symbol not in unique_symbols:
                unique_symbols.append(symbol)
        if not unique_symbols:
            unique_symbols = ["AAPL"]
        results = [self.run_ma_cross_range(symbol, start_date, end_date, fast, slow) for symbol in unique_symbols[:8]]
        ranked = sorted(
            [
                {
                    "symbol": item["symbol"],
                    "final_equity": item["final_equity"],
                    "total_return_pct": item["total_return_pct"],
                    "buy_hold_return_pct": item["buy_hold_return_pct"],
                    "max_drawdown_pct": item["max_drawdown_pct"],
                    "sharpe": item["sharpe"],
                    "trade_count": item["trade_count"],
                    "trade_quality": item.get("trade_quality", {}),
                }
                for item in results
            ],
            key=lambda row: float(row["total_return_pct"]),
            reverse=True,
        )
        return {
            "start_date": start_date,
            "end_date": end_date,
            "fast_window": fast,
            "slow_window": slow,
            "results": results,
            "ranked": ranked,
            "best": ranked[0] if ranked else None,
        }

    def optimize_ma_range(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fast_values: list[int] | None = None,
        slow_values: list[int] | None = None,
    ) -> dict[str, object]:
        fast_values = fast_values or [5, 8, 12, 20, 30]
        slow_values = slow_values or [24, 32, 50, 80, 120]
        fast_values = sorted({value for value in fast_values if value >= 2})[:12]
        slow_values = sorted({value for value in slow_values if value >= 3})[:12]
        bars, dates = self._bars_from_dates(start_date, end_date)
        prices = generate_prices(symbol, bars, seed_offset=sum(ord(ch) for ch in f"{symbol}:{start_date}:{end_date}:optimize"))
        split = max(120, int(len(prices) * 0.65))
        warmup = min(80, max(slow_values or [32]))
        train_prices = prices[:split]
        test_prices = prices[max(0, split - warmup):]
        candidates: list[dict[str, object]] = []
        matrix: list[dict[str, object]] = []
        for fast in fast_values:
            cells = []
            for slow in slow_values:
                if fast >= slow:
                    cells.append({"fast": fast, "slow": slow, "valid": False})
                    continue
                full = evaluate_ma_cross_prices(prices, fast, slow, self.initial_cash)
                train = evaluate_ma_cross_prices(train_prices, fast, slow, self.initial_cash)
                test = evaluate_ma_cross_prices(test_prices, fast, slow, self.initial_cash)
                quality = test.get("trade_quality", {})
                if not isinstance(quality, dict):
                    quality = {}
                test_return = float(test.get("total_return_pct", 0) or 0)
                train_return = float(train.get("total_return_pct", 0) or 0)
                full_return = float(full.get("total_return_pct", 0) or 0)
                mdd = float(test.get("max_drawdown_pct", 0) or 0)
                sharpe = float(test.get("sharpe", 0) or 0)
                win_rate = float(quality.get("win_rate_pct", 0) or 0)
                profit_factor = float(quality.get("profit_factor", 0) or 0)
                trade_count = int(test.get("trade_count", 0) or 0)
                overfit_gap = abs(train_return - test_return)
                score = (
                    test_return
                    + sharpe * 4.0
                    + win_rate * 0.12
                    + min(profit_factor, 4.0) * 5.0
                    + max(mdd, -80.0) * 0.35
                    - overfit_gap * 0.28
                    - max(0, 5 - trade_count) * 2.0
                )
                score = round(score, 2)
                verdict = "집중 검토"
                if overfit_gap > 45 or mdd < -40:
                    verdict = "과최적화 주의"
                elif score >= 55 and test_return > 0 and mdd > -30 and trade_count >= 3:
                    verdict = "우선 후보"
                row = {
                    "fast": fast,
                    "slow": slow,
                    "score": score,
                    "verdict": verdict,
                    "total_return_pct": round(test_return, 2),
                    "full_return_pct": round(full_return, 2),
                    "train_return_pct": round(train_return, 2),
                    "test_return_pct": round(test_return, 2),
                    "overfit_gap_pct": round(overfit_gap, 2),
                    "max_drawdown_pct": round(mdd, 2),
                    "test_drawdown_pct": round(mdd, 2),
                    "sharpe": round(sharpe, 3),
                    "test_sharpe": round(sharpe, 3),
                    "win_rate_pct": round(win_rate, 2),
                    "profit_factor": round(profit_factor, 3),
                    "trade_count": trade_count,
                    "trade_quality": quality,
                    "final_equity": test.get("final_equity"),
                }
                candidates.append(row)
                cells.append({"fast": fast, "slow": slow, "valid": True, "score": score, "return_pct": round(test_return, 2), "mdd_pct": round(mdd, 2), "verdict": verdict})
            matrix.append({"fast": fast, "cells": cells})
        candidates.sort(key=lambda item: float(item["score"]), reverse=True)
        top_results = []
        for row in candidates[:3]:
            result = self.run_ma_cross_range(symbol, start_date, end_date, int(row["fast"]), int(row["slow"]))
            result["optimization_score"] = row["score"]
            result["optimization_verdict"] = row["verdict"]
            top_results.append(result)
        warnings = []
        if candidates:
            best = candidates[0]
            if float(best.get("overfit_gap_pct", 0) or 0) > 35:
                warnings.append("최고 후보의 학습/검증 수익률 차이가 큽니다. 같은 전략을 다른 구간에서도 확인해야 합니다.")
            if float(best.get("test_drawdown_pct", 0) or 0) < -35:
                warnings.append("최고 후보의 검증구간 MDD가 큽니다. 보호장치 또는 포지션 축소가 필요합니다.")
            if int(best.get("trade_count", 0) or 0) < 3:
                warnings.append("검증구간 거래 횟수가 적어 통계 신뢰도가 낮습니다.")
        best_candidate = candidates[0] if candidates else None
        walk_forward = (
            self._walk_forward_summary(prices, dates, int(best_candidate["fast"]), int(best_candidate["slow"]))
            if best_candidate
            else None
        )
        if walk_forward:
            wf_summary = walk_forward.get("summary", {})
            if isinstance(wf_summary, dict) and float(wf_summary.get("stability_score", 0) or 0) < 45:
                warnings.append("워크포워드 구간 안정성이 낮습니다. 특정 기간에만 맞춘 전략일 수 있습니다.")
        stress_test = (
            self._monte_carlo_stress_summary(prices, int(best_candidate["fast"]), int(best_candidate["slow"]))
            if best_candidate
            else None
        )
        if stress_test:
            stress_summary = stress_test.get("summary", {})
            if isinstance(stress_summary, dict) and float(stress_summary.get("loss_probability_pct", 0) or 0) > 40:
                warnings.append("몬테카를로 스트레스에서 손실 확률이 높습니다. 전략 적용 전 기간과 보호장치를 다시 확인해야 합니다.")
            if isinstance(stress_summary, dict) and float(stress_summary.get("p05_return_pct", 0) or 0) < -25:
                warnings.append("몬테카를로 하위 5% 수익률이 크게 나쁩니다. 최악 상황 대비 포지션 축소가 필요합니다.")
        parameter_robustness = self._parameter_robustness_summary(candidates, best_candidate) if best_candidate else None
        if parameter_robustness:
            param_summary = parameter_robustness.get("summary", {})
            if isinstance(param_summary, dict) and float(param_summary.get("plateau_score", 0) or 0) < 45:
                warnings.append("최고 파라미터 주변 성과가 약합니다. 특정 조합 하나에만 맞춘 결과일 수 있습니다.")
        relative_performance = (
            self._relative_performance_summary(symbol, start_date, end_date, prices, int(best_candidate["fast"]), int(best_candidate["slow"]))
            if best_candidate
            else None
        )
        if relative_performance:
            relative_summary = relative_performance.get("summary", {})
            if isinstance(relative_summary, dict) and float(relative_summary.get("excess_vs_hold_pct", 0) or 0) < 0:
                warnings.append("전략이 같은 종목 단순 보유보다 낮습니다. 매매 전략을 쓸 이유가 있는지 다시 확인해야 합니다.")
            if isinstance(relative_summary, dict) and float(relative_summary.get("excess_vs_benchmark_pct", 0) or 0) < 0:
                warnings.append("전략이 시장 벤치마크보다 낮습니다. 종목 선택 또는 전략 조건을 재검토해야 합니다.")
        decision = self._optimization_decision(best_candidate, walk_forward, stress_test, parameter_robustness, relative_performance)
        promotion_review = self._promotion_review_summary(best_candidate, decision, walk_forward, stress_test, parameter_robustness, relative_performance)
        if promotion_review:
            blockers = promotion_review.get("blockers", [])
            if isinstance(blockers, list) and blockers:
                warnings.append("운용 승급 심사에서 차단 항목이 있습니다. 모의투자 승급 전 차단 사유를 먼저 해소해야 합니다.")
        return {
            "symbol": symbol.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "bars": bars,
            "fast_values": fast_values,
            "slow_values": slow_values,
            "matrix": matrix,
            "ranked": candidates[:20],
            "best": candidates[0] if candidates else None,
            "top_results": top_results,
            "warnings": warnings,
            "decision": decision,
            "walk_forward": walk_forward,
            "stress_test": stress_test,
            "parameter_robustness": parameter_robustness,
            "relative_performance": relative_performance,
            "promotion_review": promotion_review,
            "method": "동일 가격경로 기준 MA 파라미터 스윕 + 학습/검증 분리 + MDD/승률/PF/과최적화 패널티",
            "inspired_by": ["vectorbt parameter grid", "Backtrader analyzers", "QuantConnect LEAN walk-forward", "Freqtrade hyperopt/protections", "퀀트킹 조건 검증 UX"],
        }

    def _promotion_review_summary(
        self,
        best: dict[str, object] | None,
        decision: dict[str, object] | None,
        walk_forward: dict[str, object] | None,
        stress_test: dict[str, object] | None,
        parameter_robustness: dict[str, object] | None,
        relative_performance: dict[str, object] | None,
    ) -> dict[str, object]:
        if not best:
            return {
                "stage": "WAIT",
                "label": "검증 대기",
                "readiness_score": 0.0,
                "recommended_mode": "research_only",
                "checks": [],
                "blockers": ["유효한 최고 후보가 없습니다."],
                "next_actions": ["전략 최적화 후보를 먼저 생성하세요."],
            }

        wf_summary = walk_forward.get("summary", {}) if isinstance(walk_forward, dict) else {}
        stress_summary = stress_test.get("summary", {}) if isinstance(stress_test, dict) else {}
        param_summary = parameter_robustness.get("summary", {}) if isinstance(parameter_robustness, dict) else {}
        relative_summary = relative_performance.get("summary", {}) if isinstance(relative_performance, dict) else {}

        test_return = float(best.get("test_return_pct", 0) or 0)
        drawdown = float(best.get("test_drawdown_pct", 0) or 0)
        trade_count = int(best.get("trade_count", 0) or 0)
        profit_factor = float(best.get("profit_factor", 0) or 0)
        overfit_gap = float(best.get("overfit_gap_pct", 0) or 0)
        wf_score = float(wf_summary.get("stability_score", 0) or 0) if isinstance(wf_summary, dict) else 0.0
        stress_score = float(stress_summary.get("resilience_score", 0) or 0) if isinstance(stress_summary, dict) else 0.0
        loss_probability = float(stress_summary.get("loss_probability_pct", 0) or 0) if isinstance(stress_summary, dict) else 0.0
        plateau_score = float(param_summary.get("plateau_score", 0) or 0) if isinstance(param_summary, dict) else 0.0
        relative_score = float(relative_summary.get("relative_score", 0) or 0) if isinstance(relative_summary, dict) else 0.0
        excess_vs_hold = float(relative_summary.get("excess_vs_hold_pct", 0) or 0) if isinstance(relative_summary, dict) else 0.0
        decision_status = str((decision or {}).get("status", "WAIT"))

        checks = [
            {"key": "profitability", "label": "검증 수익률", "ok": test_return > 0, "value": round(test_return, 2), "required": "> 0%", "severity": "blocker"},
            {"key": "drawdown", "label": "검증 MDD", "ok": drawdown > -35, "value": round(drawdown, 2), "required": "> -35%", "severity": "blocker"},
            {"key": "trade_count", "label": "거래 횟수", "ok": trade_count >= 8, "value": trade_count, "required": ">= 8", "severity": "review"},
            {"key": "profit_factor", "label": "손익비", "ok": profit_factor >= 1.05, "value": round(profit_factor, 2), "required": ">= 1.05", "severity": "review"},
            {"key": "overfit_gap", "label": "과최적화 차이", "ok": overfit_gap <= 35, "value": round(overfit_gap, 2), "required": "<= 35%p", "severity": "blocker"},
            {"key": "walk_forward", "label": "워크포워드 안정성", "ok": wf_score >= 55, "value": round(wf_score, 1), "required": ">= 55", "severity": "blocker"},
            {"key": "stress", "label": "스트레스 회복력", "ok": stress_score >= 50 and loss_probability <= 35, "value": round(stress_score, 1), "required": ">= 50", "severity": "blocker"},
            {"key": "parameter", "label": "파라미터 견고성", "ok": plateau_score >= 50, "value": round(plateau_score, 1), "required": ">= 50", "severity": "review"},
            {"key": "relative", "label": "상대성과", "ok": relative_score >= 45 and excess_vs_hold >= 0, "value": round(relative_score, 1), "required": ">= 45", "severity": "blocker"},
        ]
        blockers = [item["label"] for item in checks if not item["ok"] and item["severity"] == "blocker"]
        review_items = [item["label"] for item in checks if not item["ok"] and item["severity"] == "review"]
        safety_score = max(0.0, min(100.0, 100.0 - abs(drawdown) * 1.5 - overfit_gap * 0.35))
        quality_score = max(0.0, min(100.0, 50.0 + test_return * 0.15 + min(profit_factor, 4.0) * 8.0 + min(trade_count, 20) * 1.2))
        readiness_score = round(
            quality_score * 0.18
            + safety_score * 0.16
            + wf_score * 0.18
            + stress_score * 0.16
            + plateau_score * 0.14
            + relative_score * 0.18,
            1,
        )

        if blockers:
            stage = "BLOCKED"
            label = "운용 보류"
            recommended_mode = "research_only"
            next_actions = [
                "차단 항목을 먼저 해소한 뒤 다시 검증하세요.",
                "기간을 바꾸거나 보호장치/전략 파라미터를 조정하세요.",
                "실거래가 아니라 연구 목록에만 남기세요.",
            ]
        elif readiness_score >= 75 and decision_status == "PASS":
            stage = "PAPER_READY"
            label = "모의투자 승급 후보"
            recommended_mode = "paper_candidate"
            next_actions = [
                "소액 모의투자 후보로 올리고 실시간 추적을 시작하세요.",
                "텔레그램 보고와 매매일지를 연결해 결과를 매일 복기하세요.",
                "실거래 전 최소 여러 사이클의 모의 기록을 확보하세요.",
            ]
        elif readiness_score >= 55:
            stage = "REVIEW"
            label = "추가 검토"
            recommended_mode = "watchlist_research"
            next_actions = [
                "관심 후보로 보관하고 다른 기간/종목에서도 반복 검증하세요.",
                "차단은 없지만 검토 항목을 줄인 뒤 모의투자 후보로 올리세요.",
            ]
        else:
            stage = "RESEARCH"
            label = "연구 유지"
            recommended_mode = "research_only"
            next_actions = [
                "현재 조건에서는 모의투자 승급보다 전략 연구를 계속하세요.",
                "다른 전략 프리셋 또는 종목으로 비교 검증하세요.",
            ]

        return {
            "stage": stage,
            "label": label,
            "readiness_score": readiness_score,
            "recommended_mode": recommended_mode,
            "checks": checks,
            "blockers": blockers,
            "review_items": review_items,
            "next_actions": next_actions,
            "guardrail": "실거래 주문은 여전히 OFF이며, 이 판정은 모의투자 승급 여부만 판단합니다.",
        }

    def _buy_hold_stats(self, prices: list[float]) -> dict[str, float]:
        if len(prices) < 2 or prices[0] <= 0:
            return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "final_equity": self.initial_cash}
        shares = self.initial_cash / prices[0]
        equity_curve = [round(shares * price, 2) for price in prices]
        stats = performance_stats(equity_curve, self.initial_cash)
        return {
            "return_pct": float(stats.get("total_return_pct", 0) or 0),
            "max_drawdown_pct": float(stats.get("max_drawdown_pct", 0) or 0),
            "final_equity": float(stats.get("final_equity", self.initial_cash) or self.initial_cash),
        }

    def _relative_performance_summary(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        prices: list[float],
        fast: int,
        slow: int,
    ) -> dict[str, object]:
        benchmark = "069500" if re.match(r"^\d{6}$", symbol) else "SPY"
        strategy = evaluate_ma_cross_prices(prices, fast, slow, self.initial_cash)
        hold = self._buy_hold_stats(prices)
        benchmark_prices = generate_prices(
            benchmark,
            len(prices),
            seed_offset=sum(ord(ch) for ch in f"{benchmark}:{start_date}:{end_date}:benchmark"),
        )
        benchmark_hold = self._buy_hold_stats(benchmark_prices)
        strategy_return = float(strategy.get("total_return_pct", 0) or 0)
        strategy_drawdown = float(strategy.get("max_drawdown_pct", 0) or 0)
        hold_return = float(hold.get("return_pct", 0) or 0)
        hold_drawdown = float(hold.get("max_drawdown_pct", 0) or 0)
        benchmark_return = float(benchmark_hold.get("return_pct", 0) or 0)
        benchmark_drawdown = float(benchmark_hold.get("max_drawdown_pct", 0) or 0)
        excess_vs_hold = strategy_return - hold_return
        excess_vs_benchmark = strategy_return - benchmark_return
        drawdown_edge_vs_hold = abs(hold_drawdown) - abs(strategy_drawdown)
        drawdown_edge_vs_benchmark = abs(benchmark_drawdown) - abs(strategy_drawdown)
        return_score = max(0.0, min(100.0, 50.0 + excess_vs_hold * 0.3 + excess_vs_benchmark * 0.25))
        drawdown_score = max(0.0, min(100.0, 50.0 + drawdown_edge_vs_hold * 0.7 + drawdown_edge_vs_benchmark * 0.35))
        absolute_score = max(0.0, min(100.0, 50.0 + strategy_return * 0.12))
        relative_score = round(return_score * 0.5 + drawdown_score * 0.25 + absolute_score * 0.25, 1)
        if relative_score >= 70 and excess_vs_hold > 0 and excess_vs_benchmark > 0:
            verdict = "상대성과 우수"
        elif relative_score >= 45:
            verdict = "상대성과 검토"
        else:
            verdict = "상대성과 취약"

        return {
            "symbol": symbol.upper(),
            "benchmark": benchmark.upper(),
            "fast": fast,
            "slow": slow,
            "strategy": {
                "return_pct": round(strategy_return, 2),
                "max_drawdown_pct": round(strategy_drawdown, 2),
                "final_equity": strategy.get("final_equity"),
            },
            "buy_hold": {
                "return_pct": round(hold_return, 2),
                "max_drawdown_pct": round(hold_drawdown, 2),
                "final_equity": round(float(hold.get("final_equity", self.initial_cash) or self.initial_cash), 2),
            },
            "benchmark_hold": {
                "return_pct": round(benchmark_return, 2),
                "max_drawdown_pct": round(benchmark_drawdown, 2),
                "final_equity": round(float(benchmark_hold.get("final_equity", self.initial_cash) or self.initial_cash), 2),
            },
            "summary": {
                "verdict": verdict,
                "relative_score": relative_score,
                "excess_vs_hold_pct": round(excess_vs_hold, 2),
                "excess_vs_benchmark_pct": round(excess_vs_benchmark, 2),
                "drawdown_edge_vs_hold_pct": round(drawdown_edge_vs_hold, 2),
                "drawdown_edge_vs_benchmark_pct": round(drawdown_edge_vs_benchmark, 2),
            },
        }

    def _parameter_robustness_summary(
        self,
        candidates: list[dict[str, object]],
        best: dict[str, object] | None,
    ) -> dict[str, object]:
        if not candidates or not best:
            return {"neighbors": [], "summary": {"verdict": "후보 없음", "plateau_score": 0.0}}

        fast_grid = sorted({int(row["fast"]) for row in candidates})
        slow_grid = sorted({int(row["slow"]) for row in candidates})
        best_fast = int(best["fast"])
        best_slow = int(best["slow"])
        best_score = float(best.get("score", 0) or 0)
        best_return = float(best.get("test_return_pct", 0) or 0)
        best_fast_index = fast_grid.index(best_fast) if best_fast in fast_grid else 0
        best_slow_index = slow_grid.index(best_slow) if best_slow in slow_grid else 0

        neighbors: list[dict[str, object]] = []
        for row in candidates:
            fast = int(row["fast"])
            slow = int(row["slow"])
            fast_index = fast_grid.index(fast)
            slow_index = slow_grid.index(slow)
            if abs(fast_index - best_fast_index) <= 1 and abs(slow_index - best_slow_index) <= 1:
                score = float(row.get("score", 0) or 0)
                return_pct = float(row.get("test_return_pct", 0) or 0)
                mdd_pct = float(row.get("test_drawdown_pct", 0) or 0)
                near_score = score >= best_score - max(8.0, abs(best_score) * 0.15)
                near_return = return_pct >= best_return * 0.55 if best_return > 0 else return_pct > 0
                neighbors.append(
                    {
                        "fast": fast,
                        "slow": slow,
                        "score": round(score, 2),
                        "return_pct": round(return_pct, 2),
                        "max_drawdown_pct": round(mdd_pct, 2),
                        "near_score": near_score,
                        "near_return": near_return,
                        "is_best": fast == best_fast and slow == best_slow,
                    }
                )

        if not neighbors:
            return {"neighbors": [], "summary": {"verdict": "주변 후보 없음", "plateau_score": 0.0}}

        returns = [float(row["return_pct"]) for row in neighbors]
        scores = [float(row["score"]) for row in neighbors]
        drawdowns = [float(row["max_drawdown_pct"]) for row in neighbors]
        near_score_count = len([row for row in neighbors if row["near_score"]])
        near_return_count = len([row for row in neighbors if row["near_return"]])
        positive_count = len([value for value in returns if value > 0])
        near_score_rate = near_score_count / len(neighbors) * 100.0
        near_return_rate = near_return_count / len(neighbors) * 100.0
        positive_rate = positive_count / len(neighbors) * 100.0
        average_return = sum(returns) / len(returns)
        average_score = sum(scores) / len(scores)
        worst_drawdown = min(drawdowns)
        return_score = max(0.0, min(100.0, 50.0 + average_return))
        drawdown_score = max(0.0, min(100.0, 100.0 - abs(worst_drawdown) * 1.7))
        plateau_score = round(near_score_rate * 0.35 + near_return_rate * 0.2 + positive_rate * 0.2 + return_score * 0.15 + drawdown_score * 0.1, 1)
        if plateau_score >= 70 and near_score_rate >= 45:
            verdict = "파라미터 지대 양호"
        elif plateau_score >= 45:
            verdict = "파라미터 추가 검토"
        else:
            verdict = "외딴 최고점 주의"

        neighbors.sort(key=lambda item: (not bool(item["is_best"]), -float(item["score"])))
        return {
            "fast": best_fast,
            "slow": best_slow,
            "neighbors": neighbors,
            "summary": {
                "verdict": verdict,
                "plateau_score": plateau_score,
                "neighbor_count": len(neighbors),
                "near_score_rate_pct": round(near_score_rate, 1),
                "near_return_rate_pct": round(near_return_rate, 1),
                "positive_rate_pct": round(positive_rate, 1),
                "average_neighbor_score": round(average_score, 2),
                "average_neighbor_return_pct": round(average_return, 2),
                "worst_neighbor_return_pct": round(min(returns), 2),
                "worst_neighbor_drawdown_pct": round(worst_drawdown, 2),
            },
        }

    def _walk_forward_summary(
        self,
        prices: list[float],
        dates: list[str],
        fast: int,
        slow: int,
        segments: int = 6,
    ) -> dict[str, object]:
        if not prices:
            return {"segments": [], "summary": {"verdict": "데이터 없음", "stability_score": 0.0}}

        min_segment = max(slow + 20, 90)
        segment_count = max(1, min(segments, len(prices) // min_segment))
        if segment_count < 2:
            segment_count = 1
        step = max(1, len(prices) // segment_count)
        rows: list[dict[str, object]] = []
        for index in range(segment_count):
            start_index = index * step
            end_index = len(prices) if index == segment_count - 1 else min(len(prices), (index + 1) * step)
            segment_prices = prices[start_index:end_index]
            if len(segment_prices) < slow + 5:
                continue
            result = evaluate_ma_cross_prices(segment_prices, fast, slow, self.initial_cash)
            total_return = float(result.get("total_return_pct", 0) or 0)
            drawdown = float(result.get("max_drawdown_pct", 0) or 0)
            trade_count = int(result.get("trade_count", 0) or 0)
            passed = total_return > 0 and drawdown > -35 and trade_count >= 2
            rows.append(
                {
                    "index": index + 1,
                    "start_date": dates[start_index] if start_index < len(dates) else "",
                    "end_date": dates[end_index - 1] if end_index - 1 < len(dates) else "",
                    "return_pct": round(total_return, 2),
                    "max_drawdown_pct": round(drawdown, 2),
                    "sharpe": result.get("sharpe", 0),
                    "trade_count": trade_count,
                    "passed": passed,
                }
            )

        if not rows:
            return {"segments": [], "summary": {"verdict": "구간 부족", "stability_score": 0.0}}

        returns = [float(row["return_pct"]) for row in rows]
        drawdowns = [float(row["max_drawdown_pct"]) for row in rows]
        trade_counts = [int(row["trade_count"]) for row in rows]
        passed_count = len([row for row in rows if row["passed"]])
        positive_count = len([value for value in returns if value > 0])
        avg_return = sum(returns) / len(returns)
        avg_drawdown = sum(drawdowns) / len(drawdowns)
        avg_trade_count = sum(trade_counts) / len(trade_counts)
        sorted_returns = sorted(returns)
        median_return = sorted_returns[len(sorted_returns) // 2]
        pass_rate = passed_count / len(rows) * 100.0
        positive_rate = positive_count / len(rows) * 100.0
        mdd_score = max(0.0, min(100.0, 100.0 - abs(min(drawdowns)) * 2.0))
        return_score = max(0.0, min(100.0, 50.0 + avg_return))
        trade_score = max(0.0, min(100.0, avg_trade_count * 12.0))
        stability_score = round(pass_rate * 0.4 + positive_rate * 0.25 + mdd_score * 0.25 + trade_score * 0.1, 1)
        if stability_score >= 70 and pass_rate >= 60:
            verdict = "구간 안정"
        elif stability_score >= 45:
            verdict = "구간 추가 검토"
        else:
            verdict = "구간 취약"

        return {
            "fast": fast,
            "slow": slow,
            "segments": rows,
            "summary": {
                "verdict": verdict,
                "stability_score": stability_score,
                "pass_rate_pct": round(pass_rate, 1),
                "positive_rate_pct": round(positive_rate, 1),
                "average_return_pct": round(avg_return, 2),
                "median_return_pct": round(median_return, 2),
                "worst_return_pct": round(min(returns), 2),
                "average_drawdown_pct": round(avg_drawdown, 2),
                "worst_drawdown_pct": round(min(drawdowns), 2),
                "average_trade_count": round(avg_trade_count, 1),
            },
        }

    def _monte_carlo_stress_summary(
        self,
        prices: list[float],
        fast: int,
        slow: int,
        simulations: int = 250,
    ) -> dict[str, object]:
        result = evaluate_ma_cross_prices(prices, fast, slow, self.initial_cash)
        equity_curve = [float(value) for value in result.get("equity_curve", []) if float(value) > 0]
        if len(equity_curve) < 40:
            return {"paths": [], "summary": {"verdict": "표본 부족", "resilience_score": 0.0}}

        returns = [
            (equity_curve[index] / equity_curve[index - 1]) - 1.0
            for index in range(1, len(equity_curve))
            if equity_curve[index - 1] > 0
        ]
        if len(returns) < 30:
            return {"paths": [], "summary": {"verdict": "수익률 표본 부족", "resilience_score": 0.0}}

        rng = random.Random(f"stress:{fast}:{slow}:{len(prices)}:{round(sum(prices[:30]), 4)}")
        path_returns: list[float] = []
        path_drawdowns: list[float] = []
        for _ in range(max(50, min(1000, simulations))):
            equity = self.initial_cash
            peak = equity
            max_drawdown = 0.0
            for _step in range(len(returns)):
                equity = max(0.01, equity * (1.0 + rng.choice(returns)))
                peak = max(peak, equity)
                max_drawdown = min(max_drawdown, (equity / peak) - 1.0)
            path_returns.append(((equity / self.initial_cash) - 1.0) * 100.0)
            path_drawdowns.append(max_drawdown * 100.0)

        def percentile(values: list[float], pct: float) -> float:
            ordered = sorted(values)
            if not ordered:
                return 0.0
            position = (len(ordered) - 1) * pct / 100.0
            lower = math.floor(position)
            upper = math.ceil(position)
            if lower == upper:
                return ordered[int(position)]
            weight = position - lower
            return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

        loss_probability = len([value for value in path_returns if value < 0]) / len(path_returns) * 100.0
        p05_return = percentile(path_returns, 5)
        median_return = percentile(path_returns, 50)
        p95_return = percentile(path_returns, 95)
        p05_drawdown = percentile(path_drawdowns, 5)
        median_drawdown = percentile(path_drawdowns, 50)
        loss_score = max(0.0, min(100.0, 100.0 - loss_probability * 1.5))
        tail_score = max(0.0, min(100.0, 50.0 + p05_return))
        drawdown_score = max(0.0, min(100.0, 100.0 - abs(p05_drawdown) * 1.7))
        median_score = max(0.0, min(100.0, 50.0 + median_return * 0.5))
        resilience_score = round(loss_score * 0.35 + tail_score * 0.25 + drawdown_score * 0.25 + median_score * 0.15, 1)
        if resilience_score >= 70 and loss_probability <= 25 and p05_return > -12:
            verdict = "스트레스 양호"
        elif resilience_score >= 45:
            verdict = "스트레스 주의"
        else:
            verdict = "스트레스 취약"

        sample_paths = sorted(path_returns)
        return {
            "fast": fast,
            "slow": slow,
            "simulation_count": len(path_returns),
            "sample_returns_pct": [round(value, 2) for value in sample_paths[:: max(1, len(sample_paths) // 24)][:24]],
            "summary": {
                "verdict": verdict,
                "resilience_score": resilience_score,
                "loss_probability_pct": round(loss_probability, 1),
                "p05_return_pct": round(p05_return, 2),
                "median_return_pct": round(median_return, 2),
                "p95_return_pct": round(p95_return, 2),
                "p05_drawdown_pct": round(p05_drawdown, 2),
                "median_drawdown_pct": round(median_drawdown, 2),
            },
        }

    def _optimization_decision(
        self,
        best: dict[str, object] | None,
        walk_forward: dict[str, object] | None = None,
        stress_test: dict[str, object] | None = None,
        parameter_robustness: dict[str, object] | None = None,
        relative_performance: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if not best:
            return {
                "status": "WAIT",
                "label": "검증 대기",
                "summary": "아직 유효한 전략 후보가 없습니다.",
                "reasons": ["단기선/장기선 후보 범위를 다시 지정해야 합니다."],
                "next_actions": ["검증 성향을 바꾸거나 후보 이동평균 값을 더 넓게 입력해 보세요."],
            }

        score = float(best.get("score", 0) or 0)
        test_return = float(best.get("test_return_pct", 0) or 0)
        drawdown = float(best.get("test_drawdown_pct", 0) or 0)
        overfit_gap = float(best.get("overfit_gap_pct", 0) or 0)
        profit_factor = float(best.get("profit_factor", 0) or 0)
        win_rate = float(best.get("win_rate_pct", 0) or 0)
        trade_count = int(best.get("trade_count", 0) or 0)
        wf_summary = walk_forward.get("summary", {}) if isinstance(walk_forward, dict) else {}
        wf_score = float(wf_summary.get("stability_score", 0) or 0) if isinstance(wf_summary, dict) else 0.0
        wf_pass_rate = float(wf_summary.get("pass_rate_pct", 0) or 0) if isinstance(wf_summary, dict) else 0.0
        stress_summary = stress_test.get("summary", {}) if isinstance(stress_test, dict) else {}
        stress_score = float(stress_summary.get("resilience_score", 0) or 0) if isinstance(stress_summary, dict) else 0.0
        loss_probability = float(stress_summary.get("loss_probability_pct", 0) or 0) if isinstance(stress_summary, dict) else 0.0
        param_summary = parameter_robustness.get("summary", {}) if isinstance(parameter_robustness, dict) else {}
        plateau_score = float(param_summary.get("plateau_score", 0) or 0) if isinstance(param_summary, dict) else 0.0
        relative_summary = relative_performance.get("summary", {}) if isinstance(relative_performance, dict) else {}
        relative_score = float(relative_summary.get("relative_score", 0) or 0) if isinstance(relative_summary, dict) else 0.0
        excess_vs_hold = float(relative_summary.get("excess_vs_hold_pct", 0) or 0) if isinstance(relative_summary, dict) else 0.0
        excess_vs_benchmark = float(relative_summary.get("excess_vs_benchmark_pct", 0) or 0) if isinstance(relative_summary, dict) else 0.0
        reasons: list[str] = []

        if test_return <= 0:
            reasons.append("검증구간 수익률이 0% 이하입니다.")
        if drawdown < -35:
            reasons.append("검증구간 최대낙폭이 큽니다.")
        if overfit_gap > 35:
            reasons.append("학습구간과 검증구간 성과 차이가 큽니다.")
        if trade_count < 8:
            reasons.append("거래 횟수가 적어 통계 신뢰도가 낮습니다.")
        if profit_factor < 1.05:
            reasons.append("손익비가 아직 충분히 우수하지 않습니다.")
        if win_rate < 42:
            reasons.append("승률이 보호장치 기준보다 낮습니다.")
        if wf_score and wf_score < 45:
            reasons.append("워크포워드 안정성 점수가 낮아 특정 구간에 치우쳤을 가능성이 있습니다.")
        elif wf_score and wf_pass_rate < 50:
            reasons.append("워크포워드 통과 구간 비율이 낮습니다.")
        if stress_score and stress_score < 45:
            reasons.append("몬테카를로 스트레스 점수가 낮아 수익률 순서가 바뀌면 취약할 수 있습니다.")
        elif loss_probability > 35:
            reasons.append("몬테카를로 손실 확률이 높습니다.")
        if plateau_score and plateau_score < 45:
            reasons.append("최고 파라미터 주변 조합의 성과가 약해 과최적화 위험이 있습니다.")
        if relative_score and relative_score < 45:
            reasons.append("단순 보유 또는 시장 벤치마크 대비 상대성과가 약합니다.")
        elif excess_vs_hold < 0:
            reasons.append("같은 종목을 단순 보유한 결과보다 전략 성과가 낮습니다.")
        elif excess_vs_benchmark < 0:
            reasons.append("시장 벤치마크 보유 성과보다 전략 성과가 낮습니다.")

        if score >= 55 and test_return > 0 and drawdown > -30 and overfit_gap <= 25 and trade_count >= 8 and profit_factor >= 1.15 and wf_score >= 55 and stress_score >= 50 and plateau_score >= 50 and relative_score >= 45:
            status = "PASS"
            label = "우선 모의투자 후보"
            summary = "수익, 낙폭, 과최적화 차이, 거래 횟수가 모두 비교적 균형적입니다."
            next_actions = [
                "보호장치 백테스트와 강건성 검증을 같이 통과하는지 확인하세요.",
                "같은 업종의 다른 종목과 비교해 전략이 종목 하나에만 맞춘 결과인지 점검하세요.",
                "실거래가 아니라 모의투자 기록으로 먼저 추적하세요.",
            ]
        elif score >= 25 and test_return > 0:
            status = "REVIEW"
            label = "추가 검토 후보"
            summary = "성과는 보이지만 낙폭, 거래 횟수, 과최적화 중 확인할 지점이 남아 있습니다."
            next_actions = [
                "기간을 바꿔 3개 이상 구간에서 반복 검증하세요.",
                "쿨다운, 손절, 익절 보호장치를 켠 결과와 비교하세요.",
                "후보 파라미터 주변값도 비슷하게 버티는지 히트맵을 확인하세요.",
            ]
        else:
            status = "HOLD"
            label = "보류"
            summary = "현재 조건에서는 자동 운용 후보로 보기 어렵습니다."
            next_actions = [
                "다른 전략 프리셋 또는 더 긴 기간으로 다시 검증하세요.",
                "거래 횟수가 너무 적다면 단기선/장기선 후보 범위를 조정하세요.",
                "종목을 바꿔 전략 자체가 시장에 맞는지 먼저 확인하세요.",
            ]

        if not reasons:
            reasons.append("핵심 위험 경고는 크지 않지만, 실전 전에는 보호장치 검증이 필요합니다.")

        return {
            "status": status,
            "label": label,
            "summary": summary,
            "reasons": reasons[:5],
            "next_actions": next_actions,
        }

    def robustness_range(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fast: int,
        slow: int,
        benchmark: str = "SPY",
        segments: int = 6,
    ) -> dict[str, object]:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        if end <= start:
            raise ValueError("종료일은 시작일보다 뒤여야 합니다")
        segments = max(3, min(12, segments))
        total_days = (end - start).days + 1
        window_days = max(90, total_days // segments)
        rows: list[dict[str, object]] = []
        current = start
        while current < end and len(rows) < segments:
            segment_end = min(end, current + timedelta(days=window_days - 1))
            seg_start = current.isoformat()
            seg_end = segment_end.isoformat()
            strategy = self.run_ma_cross_range(symbol, seg_start, seg_end, fast, slow)
            bench = self.run_ma_cross_range(benchmark, seg_start, seg_end, fast, slow)
            excess = round(float(strategy["total_return_pct"]) - float(bench["buy_hold_return_pct"]), 2)
            rows.append(
                {
                    "index": len(rows) + 1,
                    "start_date": seg_start,
                    "end_date": seg_end,
                    "symbol": strategy["symbol"],
                    "strategy_return_pct": strategy["total_return_pct"],
                    "buy_hold_return_pct": strategy["buy_hold_return_pct"],
                    "benchmark_symbol": benchmark.upper(),
                    "benchmark_return_pct": bench["buy_hold_return_pct"],
                    "excess_return_pct": excess,
                    "max_drawdown_pct": strategy["max_drawdown_pct"],
                    "sharpe": strategy["sharpe"],
                    "trade_count": strategy["trade_count"],
                    "passed": excess > 0 and float(strategy["max_drawdown_pct"]) > -35,
                }
            )
            current = segment_end + timedelta(days=1)
        if not rows:
            raise ValueError("검증 구간을 만들 수 없습니다")
        returns = [float(row["strategy_return_pct"]) for row in rows]
        excess_values = [float(row["excess_return_pct"]) for row in rows]
        pass_count = sum(1 for row in rows if row["passed"])
        avg_return = sum(returns) / len(returns)
        avg_excess = sum(excess_values) / len(excess_values)
        variance = sum((value - avg_return) ** 2 for value in returns) / len(returns)
        stability = max(0.0, min(100.0, 60.0 + avg_excess - (variance ** 0.5) * 0.45 + pass_count * 5.0))
        verdict = "실전 후보"
        if stability < 55 or pass_count < len(rows) / 2:
            verdict = "재검증 필요"
        if stability >= 75 and pass_count >= max(2, int(len(rows) * 0.67)):
            verdict = "우선 연구 후보"
        return {
            "symbol": symbol.upper(),
            "benchmark": benchmark.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "fast_window": fast,
            "slow_window": slow,
            "segments": rows,
            "summary": {
                "segment_count": len(rows),
                "pass_count": pass_count,
                "pass_rate_pct": round(pass_count / len(rows) * 100, 2),
                "average_return_pct": round(avg_return, 2),
                "average_excess_pct": round(avg_excess, 2),
                "worst_return_pct": round(min(returns), 2),
                "best_return_pct": round(max(returns), 2),
                "stability_score": round(stability, 1),
                "verdict": verdict,
            },
            "inspired_by": ["QuantConnect LEAN", "vectorbt", "Backtrader", "Freqtrade", "FinRL-X"],
        }

    def run_text_strategy_range(self, symbol: str, start_date: str, end_date: str, transcript: str) -> dict[str, object]:
        strategy = extract_strategy_from_text(transcript)
        bars, dates = self._bars_from_dates(start_date, end_date)
        seed = sum(ord(ch) for ch in f"{symbol}:{start_date}:{end_date}:text-strategy")
        prices = generate_prices(symbol, bars, seed_offset=seed)
        result = evaluate_text_strategy_prices(prices, strategy, self.initial_cash)
        base = evaluate_ma_cross_prices(prices, 12, 32, self.initial_cash)
        buy_hold_return = round(((prices[-1] / prices[0]) - 1.0) * 100.0, 2)
        return {
            "symbol": symbol.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "bars": bars,
            "strategy": strategy,
            "buy_hold_return_pct": buy_hold_return,
            "base_strategy_return_pct": base["total_return_pct"],
            "final_equity": result["final_equity"],
            "total_return_pct": result["total_return_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe": result["sharpe"],
            "trade_count": result["trade_count"],
            "trades": result["trades"][-40:],
            "trade_actions_sample": result["trades"][-120:],
            "trade_action_count": len(result["trades"]),
            "trade_quality": result["trade_quality"],
            "dates": dates,
            "prices": prices,
            "equity_curve": result["equity_curve"],
            "signals": result["signals"],
            "fast_ma": result["fast_ma"],
            "slow_ma": result["slow_ma"],
            "rsi": result["rsi"],
        }

    def compare(self, symbol: str, days: int, fast: int, slow: int) -> dict[str, object]:
        prices = generate_prices(symbol, days, seed_offset=13)
        base = evaluate_ma_cross_prices(prices, 12, 32, self.initial_cash)
        candidate = evaluate_ma_cross_prices(prices, fast, slow, self.initial_cash)
        base_curve = base["equity_curve"]
        candidate_curve = candidate["equity_curve"]
        correlation = self._correlation(base_curve, candidate_curve)
        return {
            "symbol": symbol.upper(),
            "base": self._summary("기준전략 MA 12/32", base),
            "candidate": self._summary(f"비교전략 MA {fast}/{slow}", candidate),
            "correlation": round(correlation, 4),
            "base_curve": base_curve,
            "candidate_curve": candidate_curve,
        }

    def _summary(self, name: str, result: dict[str, object]) -> dict[str, object]:
        return {
            "name": name,
            "final_equity": result["final_equity"],
            "total_return_pct": result["total_return_pct"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "sharpe": result["sharpe"],
            "trade_count": result["trade_count"],
        }

    def _correlation(self, left: list[float], right: list[float]) -> float:
        size = min(len(left), len(right))
        if size < 2:
            return 0.0
        left = left[-size:]
        right = right[-size:]
        left_avg = sum(left) / size
        right_avg = sum(right) / size
        numerator = sum((a - left_avg) * (b - right_avg) for a, b in zip(left, right))
        left_var = sum((a - left_avg) ** 2 for a in left)
        right_var = sum((b - right_avg) ** 2 for b in right)
        denominator = math.sqrt(left_var * right_var)
        return numerator / denominator if denominator else 0.0


@dataclass
class NativeResearchLab:
    journal: NativeJournal
    initial_cash: float = 10_000.0

    def scan(self, symbol: str, days: int = 260) -> dict[str, object]:
        prices = generate_prices(symbol, days, seed_offset=11)
        split = max(120, int(days * 0.65))
        train = prices[:split]
        test = prices[split - 80 :]
        candidates = []
        for fast in (5, 8, 12, 20):
            for slow in (24, 32, 50, 80):
                if fast >= slow:
                    continue
                train_result = evaluate_ma_cross_prices(train, fast, slow, self.initial_cash)
                test_result = evaluate_ma_cross_prices(test, fast, slow, self.initial_cash)
                score = (
                    float(test_result["total_return_pct"])
                    + float(test_result["sharpe"]) * 2.0
                    + float(test_result["max_drawdown_pct"]) * 0.7
                    - abs(float(train_result["total_return_pct"]) - float(test_result["total_return_pct"])) * 0.15
                )
                candidates.append(
                    {
                        "name": f"MA {fast}/{slow}",
                        "fast": fast,
                        "slow": slow,
                        "score": round(score, 2),
                        "train_return_pct": train_result["total_return_pct"],
                        "test_return_pct": test_result["total_return_pct"],
                        "test_drawdown_pct": test_result["max_drawdown_pct"],
                        "test_sharpe": test_result["sharpe"],
                        "test_trades": test_result["trade_count"],
                    }
                )
        candidates.sort(key=lambda item: item["score"], reverse=True)
        result = {"symbol": symbol.upper(), "best": candidates[0], "candidates": candidates[:8]}
        self.journal.add("RESEARCH", f"{symbol.upper()} 전략 후보 {len(candidates)}개 평가", result)
        return result


MARKET = NativeMarket()
JOURNAL = NativeJournal()
LOGIC_BOOK = NativeLogicBook()
BROKER = NativeBroker(MARKET, JOURNAL)
BACKTESTER = NativeBacktester()
STRATEGY = NativeStrategyRunner(MARKET, BROKER)
RESEARCH = NativeResearchLab(JOURNAL)

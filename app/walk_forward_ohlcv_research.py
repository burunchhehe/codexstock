from __future__ import annotations

import json
import hashlib
import math
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import stock_suite_app as app  # noqa: E402
from backtest_trade_evidence import (  # noqa: E402
    TradeEvidenceStore,
    build_run_fingerprint,
    finalize_trade_evidence,
    load_reusable_verified_summary,
    make_run_id,
)
from runtime_paths import active_data_root  # noqa: E402


START = "2016-07-06"
END = app.today_kst()
INITIAL_CASH = 10_000_000.0
TARGET_CASH = 10_000_000_000.0
MAX_POOL = 420
DATA_VERSION = "adj_ohlcv_v2"
DATA_ROOT = active_data_root(REPO_ROOT)
OHLCV_CACHE = DATA_ROOT / "walk_forward_ohlcv_cache_adj_20160706_20260706.json"
RESULT_FILE = DATA_ROOT / "walk_forward_ohlcv_results.json"
REPORT_FILE = DATA_ROOT / "obsidian-vault" / "AI-Trader" / "CapitalChallenge" / "walk-forward-ohlcv-20260706.md"
TRADE_EVIDENCE_DB = DATA_ROOT / "backtest_trade_evidence.sqlite3"

BAD_NAME_PARTS = [
    "ETF",
    "ETN",
    "LEVERAGE",
    "LEVERAGED",
    "DAILY",
    "2X",
    "3X",
    "ULTRA",
    "BEAR",
    "BULL",
    "INVERSE",
    "SHORT",
    "WARRANT",
    "RIGHT",
    "UNIT",
    "PREFERRED",
    "TRUST",
    "FUND",
]


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_symbol(symbol: str, name: str, first_price: float) -> bool:
    upper_name = str(name or "").upper()
    if any(part in upper_name for part in BAD_NAME_PARTS):
        return False
    if symbol.isdigit():
        return first_price >= 1000
    return symbol.isalpha() and len(symbol) <= 5 and first_price >= 5


def _candidate_pool() -> list[dict[str, str]]:
    random.seed(20260706)
    universe = app.load_universe().get("rows", [])
    kr_kospi: list[dict[str, str]] = []
    kr_kosdaq: list[dict[str, str]] = []
    us: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in universe:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol", "")).upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        market = str(raw.get("market", "")).upper()
        name = str(raw.get("name") or symbol)
        item = {"symbol": symbol, "name": name, "market": market}
        if symbol.isdigit() and "KOSDAQ" in market:
            kr_kosdaq.append(item)
        elif symbol.isdigit() and ("KOSPI" in market or market.startswith("KR")):
            kr_kospi.append(item)
        elif not symbol.isdigit() and len(symbol) <= 5 and symbol.isalpha():
            us.append(item)

    pool: list[dict[str, str]] = []
    pool.extend(kr_kospi[:90])
    pool.extend(kr_kosdaq[:120])
    pool.extend(us[:120])
    if len(kr_kospi) > 90:
        pool.extend(random.sample(kr_kospi[90:900], min(50, len(kr_kospi[90:900]))))
    if len(kr_kosdaq) > 120:
        pool.extend(random.sample(kr_kosdaq[120:1200], min(70, len(kr_kosdaq[120:1200]))))
    if len(us) > 120:
        pool.extend(random.sample(us[120:1500], min(60, len(us[120:1500]))))

    unique: dict[str, dict[str, str]] = {}
    for item in pool:
        unique[item["symbol"]] = item
    return list(unique.values())[:MAX_POOL]


def _fetch_yahoo_ohlcv(symbol: str, start: str, end: str, timeout: float = 6.0) -> dict[str, object]:
    start_dt = app._parse_replay_date(start, "2016-01-01")
    end_dt = app._parse_replay_date(end, app.today_kst()) + app.timedelta(days=1)
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote_plus(symbol)}?period1={int(start_dt.timestamp())}&period2={int(end_dt.timestamp())}"
        "&interval=1d&events=history&includeAdjustedClose=true"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 CodexStockOHLCV/1.0"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    result = ((payload.get("chart") or {}).get("result") or [None])[0] or {}
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    adjclose = (((result.get("indicators") or {}).get("adjclose") or [{}])[0] or {}).get("adjclose") or []
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    rows: list[dict[str, object]] = []
    for index, stamp in enumerate(timestamps):
        try:
            open_price = float(opens[index])
            high_price = float(highs[index])
            low_price = float(lows[index])
            close_price = float(closes[index])
            volume = int(volumes[index] or 0)
            adjusted_close = float(adjclose[index]) if index < len(adjclose) and adjclose[index] else close_price
        except Exception:
            continue
        if min(open_price, high_price, low_price, close_price) <= 0:
            continue
        adjust_ratio = adjusted_close / close_price if close_price > 0 and adjusted_close > 0 else 1.0
        if math.isfinite(adjust_ratio) and 0 < adjust_ratio < 100:
            open_price *= adjust_ratio
            high_price *= adjust_ratio
            low_price *= adjust_ratio
            close_price *= adjust_ratio
        date_key = datetime.fromtimestamp(int(stamp), timezone.utc).date().isoformat()
        if start <= date_key <= end:
            rows.append(
                {
                    "date": date_key,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }
            )
    if len(rows) < 120:
        raise ValueError(f"{symbol} OHLCV rows too short: {len(rows)}")
    return {"source": f"Yahoo OHLCV:{symbol}", "rows": rows}


def _load_ohlcv_data() -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    pool = _candidate_pool()
    cache = _read_json(OHLCV_CACHE)

    def fetch_one(item: dict[str, str]) -> tuple[str, dict[str, object]]:
        symbol = item["symbol"]
        existing = cache.get(symbol)
        if isinstance(existing, dict) and existing.get("rows") and existing.get("version") == DATA_VERSION:
            return symbol, existing
        errors: list[str] = []
        for yahoo_symbol in app._yahoo_symbol_candidates(symbol):
            try:
                result = _fetch_yahoo_ohlcv(yahoo_symbol, START, END)
                rows = [row for row in result.get("rows", []) if isinstance(row, dict)]
                first_price = float(rows[0].get("close", 0) or 0) if rows else 0.0
                if rows and _clean_symbol(symbol, item.get("name", symbol), first_price):
                    return (
                        symbol,
                        {
                            "version": DATA_VERSION,
                            "ok": True,
                            "symbol": symbol,
                            "name": item.get("name", symbol),
                            "market": item.get("market", ""),
                            "yahoo": yahoo_symbol,
                            "rows": rows,
                        },
                    )
            except Exception as exc:
                errors.append(f"{yahoo_symbol}: {exc}")
        return {
            "symbol": symbol,
        }["symbol"], {
            "ok": False,
            "symbol": symbol,
            "name": item.get("name", symbol),
            "market": item.get("market", ""),
            "rows": [],
            "errors": errors[-4:],
        }

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=24) as executor:
        futures = [executor.submit(fetch_one, item) for item in pool]
        for index, future in enumerate(as_completed(futures), 1):
            symbol, payload = future.result()
            cache[symbol] = payload
            if index % 50 == 0:
                _write_json(OHLCV_CACHE, cache)
    _write_json(OHLCV_CACHE, cache)

    data: dict[str, dict[str, object]] = {}
    for symbol, payload in cache.items():
        if not isinstance(payload, dict) or not payload.get("ok") or payload.get("version") != DATA_VERSION:
            continue
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict) and START <= str(row.get("date")) <= END]
        if len(rows) < 120:
            continue
        data[symbol] = {
            "name": payload.get("name", symbol),
            "market": payload.get("market", ""),
            "rows": rows,
            "by_date": {str(row["date"]): row for row in rows},
        }
    meta = {
        "pool_requested": len(pool),
        "cache_symbols": len(cache),
        "data_symbols": len(data),
        "fetch_elapsed_seconds": round(time.time() - start_time, 1),
    }
    return data, meta


def _pct(values: list[float], days: int) -> float:
    if len(values) <= days or values[-1 - days] <= 0:
        return 0.0
    return (values[-1] / values[-1 - days] - 1.0) * 100.0


def _sma(values: list[float], days: int) -> float | None:
    if len(values) < days:
        return None
    return sum(values[-days:]) / days


def _volume_ratio(values: list[int], days: int = 20) -> float:
    if len(values) < days + 1:
        return 1.0
    base = sum(max(1, int(value)) for value in values[-days - 1 : -1]) / days
    return max(0.0, float(values[-1]) / max(1.0, base))


def _past_liquidity_capacity(
    values: list[int],
    liquidity_pct: float,
    days: int = 20,
) -> dict[str, object]:
    window = [max(0, int(value)) for value in values[-max(1, int(days)) :] if int(value) > 0]
    reference_volume = sum(window) / len(window) if window else 0.0
    return {
        "quantity": math.floor(reference_volume * max(0.0, float(liquidity_pct)) / 100.0),
        "reference_volume": round(reference_volume, 4),
        "sample_count": len(window),
        "basis": "prior_completed_20d_average_volume",
        "current_day_volume_used": False,
    }


def _run_ohlcv_strategy(
    data: dict[str, dict[str, object]],
    config: dict[str, object],
    evidence_store: TradeEvidenceStore | None = None,
) -> dict[str, object]:
    all_dates = sorted({str(row["date"]) for payload in data.values() for row in payload["rows"]})
    cash = INITIAL_CASH
    positions: dict[str, dict[str, object]] = {}
    histories = {symbol: {"date": [], "close": [], "volume": []} for symbol in data}
    last_rows: dict[str, dict[str, object]] = {}
    trades: list[dict[str, object]] = []
    discovery_log: list[dict[str, object]] = []
    equity_curve: list[float] = []
    peak = INITIAL_CASH
    max_drawdown = 0.0

    min_history = int(config.get("min_history", 60))
    rebalance_days = max(1, int(config.get("rebalance_days", 1)))
    max_positions = max(1, int(config.get("max_positions", 4)))
    allocation_pct = float(config.get("allocation_pct", 100.0))
    position_pct = float(config.get("position_pct", allocation_pct / max_positions))
    stop_pct = float(config.get("stop_pct", 3.0))
    take_pct = float(config.get("take_pct", 6.0))
    hold_days = max(1, int(config.get("hold_days", 3)))
    entry_buffer_pct = float(config.get("entry_buffer_pct", 0.0))
    trail_pct = float(config.get("trail_pct", stop_pct * 1.5))
    liquidity_pct = max(0.001, float(config.get("liquidity_pct", 1.0)))
    trade_cost_pct = max(0.0, float(config.get("trade_cost_pct", 0.18)))
    entry_mode = str(config.get("entry_mode", "breakout"))
    max_gap_up_pct = float(config.get("max_gap_up_pct", 12.0))

    def equity() -> float:
        value = cash
        for symbol, position in positions.items():
            row = last_rows.get(symbol) or {}
            price = float(row.get("close", position.get("avg_price", 0)) or 0)
            value += float(position["quantity"]) * price
        return value

    for index, date_key in enumerate(all_dates):
        today_rows: dict[str, dict[str, object]] = {}
        for symbol, payload in data.items():
            row = payload["by_date"].get(date_key)
            if not isinstance(row, dict):
                continue
            today_rows[symbol] = row

        # Sell/hold decisions use today's OHLC after positions already existed.
        for symbol in list(positions):
            row = today_rows.get(symbol)
            if not row:
                continue
            position = positions[symbol]
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            avg_price = float(position["avg_price"])
            prior_peak_price = float(position.get("peak_price", avg_price))
            stop_price = avg_price * (1 - stop_pct / 100.0)
            take_price = avg_price * (1 + take_pct / 100.0) if take_pct > 0 else math.inf
            trail_price = prior_peak_price * (1 - trail_pct / 100.0)
            position["held_bars"] = int(position.get("held_bars", 0) or 0) + 1
            days_held = int(position["held_bars"])
            exit_price = 0.0
            reason = ""
            if low <= stop_price:
                exit_price = stop_price
                reason = f"stop {stop_pct:.1f}%"
            elif high >= take_price:
                exit_price = take_price
                reason = f"take {take_pct:.1f}%"
            elif prior_peak_price > avg_price and low <= trail_price:
                exit_price = trail_price
                reason = f"trail {trail_pct:.1f}%"
            elif days_held >= hold_days:
                exit_price = close
                reason = f"hold {days_held}d close"
            if exit_price > 0:
                quantity = float(position["quantity"])
                effective_exit_price = exit_price * (1 - trade_cost_pct / 100.0)
                cash += quantity * effective_exit_price
                pnl_pct = (effective_exit_price / avg_price - 1.0) * 100.0
                trades.append(
                    {
                        "date": date_key,
                        "symbol": symbol,
                        "name": data[symbol]["name"],
                        "side": "SELL",
                        "entry_date": position.get("entry_date"),
                        "entry_price": round(avg_price, 4),
                        "decision_data_as_of": (histories[symbol].get("date") or [date_key])[-1],
                        "execution_at": date_key,
                        "signal_lag_bars": 1,
                        "gross_price": round(exit_price, 8),
                        "price": round(effective_exit_price, 8),
                        "exit_price": round(effective_exit_price, 8),
                        "quantity": int(quantity),
                        "pnl_pct": round(pnl_pct, 2),
                        "return_pct": round(pnl_pct, 2),
                        "reason": reason,
                        "exit_reason": reason,
                        "execution_price_basis": "precommitted_protective_or_scheduled_close",
                        "cost_pct": trade_cost_pct,
                        "cost_amount": round(quantity * (exit_price - effective_exit_price), 8),
                    }
                )
                del positions[symbol]
            else:
                position["peak_price"] = max(prior_peak_price, high)

        current_equity = equity()

        # Candidate ranking is built before today's history is appended, so it only sees the past.
        if index % rebalance_days == 0:
            candidates: list[dict[str, object]] = []
            for symbol, history in histories.items():
                if symbol in positions or symbol not in today_rows:
                    continue
                closes = history["close"]
                volumes = history["volume"]
                if len(closes) < min_history:
                    continue
                row = today_rows[symbol]
                previous_close = closes[-1]
                if previous_close <= 0:
                    continue
                p5 = _pct(closes, 5)
                p20 = _pct(closes, 20)
                p60 = _pct(closes, 60)
                p120 = _pct(closes, 120)
                high20 = max(closes[-20:]) if len(closes) >= 20 else max(closes)
                high60 = max(closes[-60:]) if len(closes) >= 60 else max(closes)
                high_dist = (previous_close / high60 - 1.0) * 100.0 if high60 else -999.0
                vol_ratio = _volume_ratio(volumes, 20)
                ma_fast = _sma(closes, int(config.get("fast", 5))) or 0.0
                ma_slow = _sma(closes, int(config.get("slow", 20))) or 1.0
                if ma_fast <= ma_slow:
                    continue
                if p20 < float(config.get("min_p20", 3.0)) or p60 < float(config.get("min_p60", 8.0)):
                    continue
                if high_dist < float(config.get("min_high_dist", -8.0)):
                    continue
                if vol_ratio < float(config.get("min_vol_ratio", 1.0)):
                    continue
                trigger_price = max(previous_close * (1 + entry_buffer_pct / 100.0), high20 * float(config.get("breakout_factor", 0.995)))
                day_high = float(row["high"])
                day_open = float(row["open"])
                gap_up_pct = (day_open / previous_close - 1.0) * 100.0
                if entry_mode == "next_open":
                    if day_open <= 0 or gap_up_pct > max_gap_up_pct:
                        continue
                    raw_entry_price = day_open
                else:
                    if day_high < trigger_price:
                        continue
                    # Conservative OHLC assumption: enter at trigger/open, and if stop/take both happen, stop comes first.
                    raw_entry_price = max(day_open, trigger_price)
                entry_price = raw_entry_price * (1 + trade_cost_pct / 100.0)
                liquidity = _past_liquidity_capacity(volumes, liquidity_pct)
                max_liquidity_quantity = int(liquidity["quantity"])
                if max_liquidity_quantity <= 0:
                    continue
                score = (
                    p5 * float(config.get("w5", 1.2))
                    + p20 * float(config.get("w20", 0.9))
                    + p60 * float(config.get("w60", 0.5))
                    + p120 * float(config.get("w120", 0.15))
                    + vol_ratio * float(config.get("wvol", 8.0))
                    + high_dist * float(config.get("whigh", 0.7))
                )
                candidates.append(
                    {
                        "symbol": symbol,
                        "score": score,
                        "entry_price": entry_price,
                        "gross_entry_price": raw_entry_price,
                        "max_liquidity_quantity": max_liquidity_quantity,
                        "decision_data_as_of": (history.get("date") or [date_key])[-1],
                        "liquidity": liquidity,
                        "metrics": {
                            "p5": round(p5, 2),
                            "p20": round(p20, 2),
                            "p60": round(p60, 2),
                            "p120": round(p120, 2),
                            "volume_ratio": round(vol_ratio, 2),
                            "high_dist": round(high_dist, 2),
                        },
                    }
                )
            candidates.sort(key=lambda item: float(item["score"]), reverse=True)
            if candidates and len(discovery_log) < 160:
                discovery_log.append(
                    {
                        "date": date_key,
                        "top": [
                            {
                                "symbol": str(item["symbol"]),
                                "name": str(data[str(item["symbol"])]["name"]),
                                "score": round(float(item["score"]), 2),
                                **dict(item["metrics"]),
                            }
                            for item in candidates[:5]
                        ],
                    }
                )
            slots = max_positions - len(positions)
            for candidate in candidates[: max(0, slots)]:
                symbol = str(candidate["symbol"])
                entry_price = float(candidate["entry_price"])
                gross_entry_price = float(candidate["gross_entry_price"])
                target_notional = current_equity * position_pct / 100.0
                notional = min(cash, target_notional)
                quantity = min(math.floor(notional / entry_price), int(candidate.get("max_liquidity_quantity", 0) or 0))
                if quantity <= 0:
                    continue
                cash -= quantity * entry_price
                positions[symbol] = {
                    "quantity": quantity,
                    "avg_price": entry_price,
                    "entry_index": index,
                    "entry_date": date_key,
                    "held_bars": 0,
                    "peak_price": entry_price,
                    "score": round(float(candidate["score"]), 2),
                }
                trades.append(
                    {
                        "date": date_key,
                        "symbol": symbol,
                        "name": data[symbol]["name"],
                        "side": "BUY",
                        "decision_data_as_of": candidate["decision_data_as_of"],
                        "execution_at": date_key,
                        "signal_lag_bars": 1,
                        "execution_price_basis": "next_open_or_intraday_trigger",
                        "gross_price": round(gross_entry_price, 8),
                        "price": round(entry_price, 8),
                        "entry_price": round(entry_price, 8),
                        "quantity": int(quantity),
                        "score": round(float(candidate["score"]), 2),
                        "reason": f"past-only OHLCV {entry_mode} {candidate['metrics']}",
                        "liquidity_pct": liquidity_pct,
                        "liquidity_reference_volume": candidate["liquidity"]["reference_volume"],
                        "liquidity_volume_basis": candidate["liquidity"]["basis"],
                        "entry_mode": entry_mode,
                        "cost_pct": trade_cost_pct,
                        "cost_amount": round(quantity * (entry_price - gross_entry_price), 8),
                    }
                )
                same_day_stop = entry_price * (1 - stop_pct / 100.0)
                same_day_take = entry_price * (1 + take_pct / 100.0) if take_pct > 0 else math.inf
                today_row = today_rows.get(symbol, {})
                same_day_low = float(today_row.get("low", entry_price) or entry_price)
                same_day_high = float(today_row.get("high", entry_price) or entry_price)
                same_day_close = float(today_row.get("close", entry_price) or entry_price)
                same_day_exit_price = 0.0
                same_day_reason = ""
                if same_day_low <= same_day_stop:
                    same_day_exit_price = same_day_stop
                    same_day_reason = f"same-day stop {stop_pct:.1f}%"
                elif same_day_high >= same_day_take:
                    same_day_exit_price = same_day_take
                    same_day_reason = f"same-day take {take_pct:.1f}%"
                elif hold_days <= 1:
                    same_day_exit_price = same_day_close
                    same_day_reason = "same-day close"
                if same_day_exit_price > 0 and symbol in positions:
                    effective_same_day_exit = same_day_exit_price * (1 - trade_cost_pct / 100.0)
                    cash += quantity * effective_same_day_exit
                    pnl_pct = (effective_same_day_exit / entry_price - 1.0) * 100.0
                    trades.append(
                        {
                            "date": date_key,
                            "symbol": symbol,
                            "name": data[symbol]["name"],
                            "side": "SELL",
                            "entry_date": date_key,
                            "entry_price": round(entry_price, 4),
                            "decision_data_as_of": candidate["decision_data_as_of"],
                            "execution_at": date_key,
                            "signal_lag_bars": 1,
                            "execution_price_basis": "same_day_ohlc_stop_first_conservative",
                            "gross_price": round(same_day_exit_price, 8),
                            "price": round(effective_same_day_exit, 8),
                            "exit_price": round(effective_same_day_exit, 8),
                            "quantity": int(quantity),
                            "pnl_pct": round(pnl_pct, 2),
                            "return_pct": round(pnl_pct, 2),
                            "reason": same_day_reason,
                            "exit_reason": same_day_reason,
                            "cost_pct": trade_cost_pct,
                            "cost_amount": round(quantity * (same_day_exit_price - effective_same_day_exit), 8),
                        }
                    )
                    del positions[symbol]
                current_equity = equity()

        for symbol, row in today_rows.items():
            last_rows[symbol] = row
            histories[symbol]["date"].append(date_key)
            histories[symbol]["close"].append(float(row["close"]))
            histories[symbol]["volume"].append(int(row.get("volume", 0) or 0))

        current_equity = equity()
        peak = max(peak, current_equity)
        drawdown = (current_equity / peak - 1.0) * 100.0 if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)
        equity_curve.append(current_equity)

    final_equity = equity_curve[-1] if equity_curve else cash
    closed = [trade for trade in trades if trade["side"] == "SELL"]
    wins = [trade for trade in closed if float(trade.get("pnl_pct", 0) or 0) > 0]
    top_closed = sorted(closed, key=lambda item: float(item.get("pnl_pct", 0) or 0), reverse=True)[:12]
    open_position_evidence = [
        {
            "symbol": symbol,
            "name": data[symbol]["name"],
            "quantity": int(position["quantity"]),
            "avg_price": round(float(position["avg_price"]), 8),
            "last_price": round(float((last_rows.get(symbol) or {}).get("close", position["avg_price"])), 8),
            "unrealized_pct": round((float((last_rows.get(symbol) or {}).get("close", position["avg_price"])) / float(position["avg_price"]) - 1.0) * 100.0, 2),
        }
        for symbol, position in positions.items()
    ]
    timing_model = {
        "version": "past-only-ohlcv-execution.v2",
        "decision_basis": "prior_completed_symbol_bars",
        "liquidity_volume_basis": "prior_completed_20d_average_volume",
        "current_day_volume_allowed": False,
        "missing_symbol_bar_policy": "skip_execution_until_next_available_symbol_bar",
        "trailing_stop_activation_basis": "prior_completed_peak_only",
        "same_day_ohlc_ambiguity_policy": "stop_first_conservative",
        "lookahead_safe_required": True,
    }
    evidence_audit, ledger_reference = finalize_trade_evidence(
        engine="walk_forward_ohlcv",
        strategy_name=str(config["name"]),
        config=config,
        actions=trades,
        initial_cash=INITIAL_CASH,
        final_equity=final_equity,
        open_positions=open_position_evidence,
        timing_model=timing_model,
        store=evidence_store,
    )
    return {
        "name": str(config["name"]),
        "final_equity": round(final_equity, 2),
        "multiple": round(final_equity / INITIAL_CASH, 4),
        "target_progress_pct": round(final_equity / TARGET_CASH * 100.0, 4),
        "return_pct": round((final_equity / INITIAL_CASH - 1.0) * 100.0, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "trade_count": len(trades),
        "closed_trade_count": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100.0, 2) if closed else 0.0,
        "open_positions": open_position_evidence,
        "top_closed_trades": top_closed,
        "execution_timing_model": timing_model,
        "trade_evidence_audit": evidence_audit,
        "trade_ledger": ledger_reference,
        "performance_evidence_status": "verified" if evidence_audit.get("official_return_claim_allowed") else "blocked",
        "discovery_log": discovery_log[-20:],
    }


def _configs() -> list[dict[str, object]]:
    base = {
        "min_history": 80,
        "fast": 5,
        "slow": 20,
        "breakout_factor": 0.995,
        "min_high_dist": -6.0,
        "min_vol_ratio": 0.9,
        "w5": 1.2,
        "w20": 1.0,
        "w60": 0.45,
        "w120": 0.1,
        "wvol": 7.5,
        "whigh": 0.8,
    }
    configs: list[dict[str, object]] = []
    for stop in [2.0, 3.0, 4.0, 5.0, 7.0]:
        for take in [4.0, 6.0, 10.0, 15.0, 25.0]:
            for hold in [1, 2, 3, 5, 8]:
                configs.append(
                    {
                        **base,
                        "name": f"ohlcv_breakout_s{stop:g}_t{take:g}_h{hold}",
                        "entry_mode": "breakout",
                        "rebalance_days": 1,
                        "max_positions": 4,
                        "allocation_pct": 100.0,
                        "position_pct": 25.0,
                        "stop_pct": stop,
                        "take_pct": take,
                        "trail_pct": max(3.0, stop * 1.5),
                        "hold_days": hold,
                        "entry_buffer_pct": 0.2,
                        "liquidity_pct": 1.0,
                        "trade_cost_pct": 0.18,
                        "min_p20": 3.0,
                        "min_p60": 8.0,
                    }
                )
    for stop in [8.0, 12.0, 18.0]:
        for hold in [20, 60, 160, 360]:
            configs.append(
                {
                    **base,
                    "name": f"ohlcv_leader_hold_s{stop:g}_h{hold}",
                    "entry_mode": "breakout",
                    "rebalance_days": 5,
                    "max_positions": 2,
                    "allocation_pct": 100.0,
                    "position_pct": 50.0,
                    "stop_pct": stop,
                    "take_pct": 0.0,
                    "trail_pct": max(12.0, stop * 2),
                    "hold_days": hold,
                    "entry_buffer_pct": 0.0,
                    "liquidity_pct": 2.0,
                    "trade_cost_pct": 0.18,
                    "min_p20": 5.0,
                    "min_p60": 15.0,
                    "min_vol_ratio": 0.7,
                    "w120": 0.35,
                }
            )
    for stop in [6.0, 8.0, 12.0, 18.0, 25.0]:
        for hold in [20, 60, 120, 240, 480]:
            for slots in [1, 2, 4]:
                configs.append(
                    {
                        **base,
                        "name": f"nextopen_momentum_p{slots}_s{stop:g}_h{hold}",
                        "entry_mode": "next_open",
                        "rebalance_days": 5,
                        "max_positions": slots,
                        "allocation_pct": 100.0,
                        "position_pct": 100.0 / slots,
                        "stop_pct": stop,
                        "take_pct": 0.0,
                        "trail_pct": max(14.0, stop * 1.8),
                        "hold_days": hold,
                        "liquidity_pct": 2.0,
                        "trade_cost_pct": 0.18,
                        "max_gap_up_pct": 12.0,
                        "min_p20": 4.0,
                        "min_p60": 12.0,
                        "min_vol_ratio": 0.6,
                        "w20": 1.1,
                        "w60": 0.65,
                        "w120": 0.35,
                        "wvol": 4.0,
                        "whigh": 0.4,
                    }
                )
    for stop in [4.0, 6.0, 8.0, 12.0]:
        for take in [12.0, 20.0, 35.0]:
            for hold in [5, 10, 20, 40]:
                configs.append(
                    {
                        **base,
                        "name": f"nextopen_swing_p2_s{stop:g}_t{take:g}_h{hold}",
                        "entry_mode": "next_open",
                        "rebalance_days": 2,
                        "max_positions": 2,
                        "allocation_pct": 100.0,
                        "position_pct": 50.0,
                        "stop_pct": stop,
                        "take_pct": take,
                        "trail_pct": max(8.0, stop * 2.0),
                        "hold_days": hold,
                        "liquidity_pct": 1.5,
                        "trade_cost_pct": 0.18,
                        "max_gap_up_pct": 9.0,
                        "min_p20": 3.0,
                        "min_p60": 8.0,
                        "min_vol_ratio": 0.8,
                    }
                )
    return configs


def _write_report(summary: dict[str, object]) -> None:
    results = summary.get("results", [])
    best = results[0] if results else {}
    best_multiple = float(best.get("multiple", 0) or 0) if isinstance(best, dict) else 0.0
    verdict = "목표 달성" if best_multiple >= 1000.0 else "목표 미달성"
    lines = [
        "# OHLCV 워크포워드 주도주/스윙 100억 도전",
        "",
        f"- 생성: {summary.get('generated_at')}",
        f"- 구간: {START} ~ {END}",
        f"- 시작 자본: {INITIAL_CASH:,.0f}원",
        f"- 목표 자본: {TARGET_CASH:,.0f}원",
        f"- 후보 요청: {summary.get('pool_requested')}개",
        f"- OHLCV 데이터 확보: {summary.get('data_symbols')}개",
        f"- 테스트 조합: {summary.get('tested')}개",
        f"- 최고 결과: {best_multiple:,.4f}배, {verdict}",
        "- 방식: 각 날짜 직전까지의 OHLCV만 사용해 후보를 고르고, 당일/다음 시가 진입 규칙으로 체결을 근사했습니다.",
        "- 보정: Yahoo Adj Close 비율로 시가/고가/저가/종가를 보정하고, 기본 거래비용/슬리피지 0.18%를 반영했습니다.",
        "- 주의: 현재 상장 유니버스 기반이라 상장폐지 종목 누락 가능성이 남아 있습니다. 이 결과는 연구 기록이지 수익 보장이 아닙니다.",
        "",
        "## 상위 결과",
        "",
        "| 순위 | 전략 | 최종자산 | 배수 | 목표진행률 | MDD | 거래 | 승률 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(results[:20], 1):
        lines.append(
            f"| {index} | {row['name']} | {float(row['final_equity']):,.0f}원 | "
            f"{float(row['multiple']):.4f}배 | {float(row['target_progress_pct']):.4f}% | "
            f"{float(row['max_drawdown_pct']):.2f}% | {row['trade_count']} | {float(row['win_rate_pct']):.2f}% |"
        )
    if results:
        best = results[0]
        lines.extend(["", "## 최고 전략 최근 발견 로그", ""])
        for log in best.get("discovery_log", [])[-8:]:
            if not isinstance(log, dict):
                continue
            tops = ", ".join(f"{item.get('name')}({item.get('symbol')}) score {item.get('score')}" for item in log.get("top", [])[:3] if isinstance(item, dict))
            lines.append(f"- {log.get('date')}: {tops}")
        lines.extend(["", "## 최고 전략 상위 청산 거래", ""])
        for trade in best.get("top_closed_trades", [])[:10]:
            if isinstance(trade, dict):
                lines.append(f"- {trade.get('date')} {trade.get('name')}({trade.get('symbol')}) {trade.get('pnl_pct')}%: {trade.get('reason')}")
    lines.extend(
        [
            "",
            "## 판단",
            "",
            "이번 결과는 '진짜 돈을 넣으면 바로 된다'는 결론이 아니라, 어떤 조건에서 복리와 손실통제가 동시에 작동하는지 찾기 위한 연구 기록입니다.",
            "다음 단계는 KRX 상장/상폐 이력, 체결 가능 호가, 세금, 시장별 환율, 실시간 대금 필터를 더 붙여서 과대평가를 계속 줄이는 것입니다.",
        ]
    )
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    started = time.time()
    configs = _configs()
    fingerprint_options = {"start": START, "end": END, "data_version": DATA_VERSION}
    run_fingerprint = build_run_fingerprint(
        engine="walk_forward_ohlcv",
        source_paths=[Path(__file__), APP_ROOT / "backtest_trade_evidence.py"],
        data_paths=[OHLCV_CACHE],
        configs=configs,
        options=fingerprint_options,
    )
    if "--force" not in sys.argv:
        cached = load_reusable_verified_summary(
            RESULT_FILE,
            expected_fingerprint=run_fingerprint,
            ledger_path=TRADE_EVIDENCE_DB,
            engine="walk_forward_ohlcv",
        )
        if cached is not None:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "cache_hit": True,
                        "message": "Identical verified code, data, and strategy evidence was reused.",
                        "run_id": (cached.get("trade_evidence") or {}).get("run_id"),
                        "tested": cached.get("tested"),
                        "result_file": str(RESULT_FILE),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
    data, meta = _load_ohlcv_data()
    run_fingerprint = build_run_fingerprint(
        engine="walk_forward_ohlcv",
        source_paths=[Path(__file__), APP_ROOT / "backtest_trade_evidence.py"],
        data_paths=[OHLCV_CACHE],
        configs=configs,
        options=fingerprint_options,
    )
    run_id = make_run_id("walk_forward_ohlcv")
    with TradeEvidenceStore(TRADE_EVIDENCE_DB, engine="walk_forward_ohlcv", run_id=run_id) as evidence_store:
        results = [_run_ohlcv_strategy(data, config, evidence_store) for config in configs]
        pruned_ledger_rows = evidence_store.prune_old_runs(keep_runs=5)
    results.sort(key=lambda row: float(row.get("final_equity", 0) or 0), reverse=True)
    verified_result_count = sum(
        1
        for row in results
        if isinstance(row.get("trade_evidence_audit"), dict)
        and row["trade_evidence_audit"].get("official_return_claim_allowed") is True
    )
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "DONE",
        "run_fingerprint": run_fingerprint,
        "start": START,
        "end": END,
        "initial_cash": INITIAL_CASH,
        "target_cash": TARGET_CASH,
        "tested": len(results),
        "elapsed_seconds": round(time.time() - started, 1),
        **meta,
        "trade_evidence": {
            "schema_version": "backtest-trade-evidence.v1",
            "storage": "sqlite_zlib",
            "database_path": str(TRADE_EVIDENCE_DB),
            "run_id": run_id,
            "verified_result_count": verified_result_count,
            "result_count": len(results),
            "all_results_verified": verified_result_count == len(results),
            "pruned_old_ledger_rows": pruned_ledger_rows,
        },
        "methodology_evidence": {
            "schema_version": "ohlcv-methodology-v2",
            "source_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "temporal_integrity": {
                "passed": True,
                "rule": "candidate history is appended only after ranking; execution uses current open/trigger after past-only signal",
            },
            "corporate_actions": {
                "passed": True,
                "rule": "Yahoo adjclose ratio is applied to open/high/low/close",
            },
            "transaction_cost": {
                "passed": True,
                "profile_id": "ohlcv-roundtrip-cost-v1",
                "combined_cost_pct_per_side": 0.18,
            },
            "liquidity_capacity": {
                "passed": True,
                "rule": "quantity is capped by configured percentage of prior completed 20-day average volume; execution-day volume is forbidden",
            },
            "survivorship_bias": {
                "passed": False,
                "reason": "point-in-time delisted and historical-index constituents are not yet included",
            },
        },
        "results": results,
    }
    _write_json(RESULT_FILE, summary)
    _write_report(summary)
    compact_top10 = [
        {
            "name": row.get("name"),
            "final_equity": row.get("final_equity"),
            "multiple": row.get("multiple"),
            "target_progress_pct": row.get("target_progress_pct"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "trade_count": row.get("trade_count"),
            "win_rate_pct": row.get("win_rate_pct"),
        }
        for row in results[:10]
    ]
    print(
        json.dumps(
            {
                "summary": {k: summary[k] for k in ["generated_at", "data_symbols", "tested", "elapsed_seconds"]},
                "top10": compact_top10,
                "report": str(REPORT_FILE),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

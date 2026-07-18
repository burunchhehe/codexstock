from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path

import stock_suite_app as app
import walk_forward_ohlcv_research as wf


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_cache() -> dict[str, dict[str, object]]:
    cache_path = wf.OHLCV_CACHE
    if not cache_path.is_file():
        fallback = app.USER_DATA_ROOT / cache_path.name
        cache_path = fallback if fallback.is_file() else cache_path
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    data: dict[str, dict[str, object]] = {}
    for symbol, payload in raw.items() if isinstance(raw, dict) else []:
        if not isinstance(payload, dict):
            continue
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict) and row.get("date")]
        if len(rows) < 80:
            continue
        data[str(symbol)] = {
            "name": payload.get("name") or symbol,
            "market": payload.get("market") or "",
            "rows": rows,
            "by_date": {str(row["date"]): row for row in rows},
        }
    return data


def _year_proxy_returns(data: dict[str, dict[str, object]]) -> dict[int, float]:
    by_year: dict[int, list[float]] = {}
    for payload in data.values():
        if "KOSPI" not in str(payload.get("market") or "").upper():
            continue
        yearly: dict[int, list[float]] = {}
        for row in payload.get("rows", []):
            try:
                year = int(str(row.get("date"))[:4])
                close = float(row.get("close") or 0)
            except (TypeError, ValueError):
                continue
            if close > 0:
                yearly.setdefault(year, []).append(close)
        for year, closes in yearly.items():
            if len(closes) >= 120 and closes[0] > 0:
                by_year.setdefault(year, []).append((closes[-1] / closes[0] - 1.0) * 100.0)
    return {
        year: round(statistics.median(returns), 2)
        for year, returns in by_year.items()
        if len(returns) >= 20
    }


def _representative_years(year_returns: dict[int, float]) -> dict[str, int]:
    bull = [(year, value) for year, value in year_returns.items() if value >= 10.0]
    bear = [(year, value) for year, value in year_returns.items() if value <= -10.0]
    sideways = [(year, value) for year, value in year_returns.items() if -10.0 < value < 10.0]
    selected: dict[str, int] = {}
    if bull:
        selected["bull"] = max(bull, key=lambda item: item[1])[0]
    if bear:
        selected["bear"] = min(bear, key=lambda item: item[1])[0]
    if sideways:
        selected["sideways"] = min(sideways, key=lambda item: abs(item[1]))[0]
    return selected


def _slice_year(data: dict[str, dict[str, object]], year: int) -> dict[str, dict[str, object]]:
    sliced: dict[str, dict[str, object]] = {}
    prefix = f"{year:04d}-"
    for symbol, payload in data.items():
        rows = [row for row in payload.get("rows", []) if str(row.get("date") or "").startswith(prefix)]
        if len(rows) < 80:
            continue
        sliced[symbol] = {
            "name": payload.get("name") or symbol,
            "market": payload.get("market") or "",
            "rows": rows,
            "by_date": {str(row["date"]): row for row in rows},
        }
    return sliced


def main() -> int:
    data = _load_cache()
    year_returns = _year_proxy_returns(data)
    selected = _representative_years(year_returns)
    prior_result = json.loads(app.OHLCV_WALK_FORWARD_RESULT_FILE.read_text(encoding="utf-8"))
    prior_rows = prior_result.get("results", []) if isinstance(prior_result, dict) else []
    best_name = str((prior_rows[0] if prior_rows else {}).get("name") or "")
    configs = wf._configs()
    config = next((row for row in configs if str(row.get("name")) == best_name), configs[0])
    segments = []
    for regime in ("bull", "bear", "sideways"):
        year = selected.get(regime)
        if not year:
            continue
        result = wf._run_ohlcv_strategy(_slice_year(data, year), config)
        strategy_return = float(result.get("return_pct", 0) or 0)
        drawdown = float(result.get("max_drawdown_pct", 0) or 0)
        proxy_return = float(year_returns.get(year, 0) or 0)
        performance_pass = (
            strategy_return > 0
            if regime in {"bull", "sideways"}
            else strategy_return > proxy_return
        ) and drawdown > -35.0
        segments.append(
            {
                "regime": regime,
                "year": year,
                "market_proxy_return_pct": year_returns.get(year),
                "strategy_return_pct": result.get("return_pct"),
                "max_drawdown_pct": result.get("max_drawdown_pct"),
                "trade_count": result.get("trade_count"),
                "win_rate_pct": result.get("win_rate_pct"),
                "sample_passed": int(result.get("trade_count", 0) or 0) >= 5,
                "performance_passed": performance_pass,
                "passed": int(result.get("trade_count", 0) or 0) >= 5 and performance_pass,
            }
        )
    passed = len(segments) == 3 and all(bool(row.get("passed")) for row in segments)
    cache_path = wf.OHLCV_CACHE if wf.OHLCV_CACHE.is_file() else app.USER_DATA_ROOT / wf.OHLCV_CACHE.name
    payload = {
        "ok": True,
        "passed": passed,
        "status": "verified" if passed else "blocked",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "schema_version": "market-regime-validation-v1",
        "strategy_name": best_name,
        "strategy_config": config,
        "strategy_config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest(),
        "market_proxy": "KOSPI common-stock median annual return",
        "classification": {"bull": ">= +10%", "bear": "<= -10%", "sideways": "between -10% and +10%"},
        "regime_count": len({str(row.get("regime")) for row in segments if row.get("passed")}),
        "segments": segments,
        "year_proxy_returns": year_returns,
        "data_file": cache_path.name,
        "data_hash": _hash_file(cache_path),
        "source_hash": _hash_file(Path(__file__)),
        "guardrail": "Historical adjusted OHLCV research only. No live order is submitted.",
    }
    app.MARKET_REGIME_VALIDATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    app.MARKET_REGIME_VALIDATION_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

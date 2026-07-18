from __future__ import annotations

import asyncio
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import openbb_core
import openbb_yfinance
import yfinance
from openbb_yfinance.models.equity_historical import YFinanceEquityHistoricalFetcher
from openbb_yfinance.models.equity_profile import YFinanceEquityProfileFetcher
from openbb_yfinance.models.income_statement import YFinanceIncomeStatementFetcher
from openbb_yfinance.models.index_historical import YFinanceIndexHistoricalFetcher
from openbb_yfinance.models.key_metrics import YFinanceKeyMetricsFetcher
from openbb_yfinance.models.currency_historical import YFinanceCurrencyHistoricalFetcher


FORBIDDEN_KEY_PARTS = (
    "account_number",
    "approval",
    "broker_token",
    "kis_",
    "order_token",
    "password",
    "secret",
)


def _assert_information_only(value: Any, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(f"forbidden_input_field:{path}.{key}")
            _assert_information_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_information_only(child, f"{path}[{index}]")


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _external_candidates(symbol: str, market: str) -> list[str]:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        return []
    if "." in normalized or market.upper() not in {"KR", "KOSPI", "KOSDAQ"}:
        return [normalized]
    if normalized.isdigit() and len(normalized) == 6:
        return [f"{normalized}.KS", f"{normalized}.KQ"]
    return [normalized]


def _fetch_symbol(
    symbol: str,
    market: str,
    start_date: str,
    end_date: str,
    *,
    adjustment: str = "splits_only",
) -> dict[str, Any]:
    errors: list[str] = []
    for external_symbol in _external_candidates(symbol, market):
        try:
            query = YFinanceEquityHistoricalFetcher.transform_query(
                {
                    "symbol": external_symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "interval": "1d",
                    "include_actions": True,
                    "adjustment": adjustment,
                }
            )
            raw = YFinanceEquityHistoricalFetcher.extract_data(query, None)
            models = YFinanceEquityHistoricalFetcher.transform_data(query, raw)
            if not models:
                errors.append(f"{external_symbol}:empty")
                continue
            currency = "KRW" if external_symbol.endswith((".KS", ".KQ")) else "USD"
            price_unit = "won_integer" if currency == "KRW" else "decimal_usd"
            rows = []
            for model in models:
                payload = model.model_dump(mode="json")
                close = _finite(payload.get("close"))
                if close <= 0:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "external_symbol": external_symbol,
                        "date": str(payload.get("date") or ""),
                        "open": _finite(payload.get("open")),
                        "high": _finite(payload.get("high")),
                        "low": _finite(payload.get("low")),
                        "close": close,
                        "volume": _finite(payload.get("volume")),
                        "dividend": _finite(payload.get("dividend")),
                        "split_ratio": _finite(payload.get("split_ratio")),
                        "market": market,
                        "currency": currency,
                        "price_unit": price_unit,
                        "provider": "openbb_yfinance",
                    }
                )
            if rows:
                return {
                    "ok": True,
                    "symbol": symbol,
                    "external_symbol": external_symbol,
                    "row_count": len(rows),
                    "rows": rows,
                    "adjustment": adjustment,
                    "errors": errors,
                }
        except Exception as exc:
            errors.append(f"{external_symbol}:{str(exc)[:180]}")
    return {"ok": False, "symbol": symbol, "row_count": 0, "rows": [], "errors": errors}


async def _fetch_async_models(fetcher: Any, params: dict[str, Any]) -> list[dict[str, Any]]:
    query = fetcher.transform_query(dict(params))
    raw = await fetcher.aextract_data(query, None)
    return [model.model_dump(mode="json") for model in fetcher.transform_data(query, raw)]


def _select_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: payload.get(field) for field in fields if payload.get(field) is not None}


def _fetch_fundamental_symbol(symbol: str, market: str, as_of_date: str) -> dict[str, Any]:
    errors: list[str] = []
    for external_symbol in _external_candidates(symbol, market):
        profile_rows: list[dict[str, Any]] = []
        metric_rows: list[dict[str, Any]] = []
        statement_rows: list[dict[str, Any]] = []
        try:
            profile_rows = asyncio.run(
                _fetch_async_models(YFinanceEquityProfileFetcher, {"symbol": external_symbol})
            )
        except Exception as exc:
            errors.append(f"{external_symbol}:profile:{str(exc)[:160]}")
        try:
            metric_rows = asyncio.run(
                _fetch_async_models(YFinanceKeyMetricsFetcher, {"symbol": external_symbol})
            )
        except Exception as exc:
            errors.append(f"{external_symbol}:metrics:{str(exc)[:160]}")
        try:
            query = YFinanceIncomeStatementFetcher.transform_query(
                {"symbol": external_symbol, "period": "annual", "limit": 3}
            )
            raw = YFinanceIncomeStatementFetcher.extract_data(query, None)
            statement_rows = [
                model.model_dump(mode="json")
                for model in YFinanceIncomeStatementFetcher.transform_data(query, raw)
            ]
        except Exception as exc:
            errors.append(f"{external_symbol}:income:{str(exc)[:160]}")

        profile = _select_fields(
            profile_rows[0] if profile_rows else {},
            (
                "symbol",
                "name",
                "stock_exchange",
                "exchange_timezone",
                "issue_type",
                "currency",
                "sector",
                "industry_category",
                "market_cap",
                "shares_outstanding",
                "shares_float",
                "dividend_yield",
                "beta",
            ),
        )
        metrics = _select_fields(
            metric_rows[0] if metric_rows else {},
            (
                "market_cap",
                "pe_ratio",
                "forward_pe",
                "price_to_book",
                "enterprise_to_ebitda",
                "earnings_growth",
                "revenue_growth",
                "debt_to_equity",
                "current_ratio",
                "gross_margin",
                "operating_margin",
                "profit_margin",
                "return_on_assets",
                "return_on_equity",
                "price_return_1y",
                "currency",
            ),
        )
        all_statements = [
            _select_fields(
                row,
                (
                    "period_ending",
                    "fiscal_period",
                    "fiscal_year",
                    "revenue",
                    "gross_profit",
                    "operating_income",
                    "pretax_income",
                    "net_income",
                    "basic_eps",
                    "diluted_eps",
                ),
            )
            for row in statement_rows[:3]
        ]
        statements = [
            row
            for row in all_statements
            if str(row.get("period_ending") or "")[:10] <= as_of_date
        ]
        future_statement_count = len(all_statements) - len(statements)
        try:
            historical_request = datetime.strptime(as_of_date, "%Y-%m-%d").date() < (
                datetime.now().date() - timedelta(days=7)
            )
        except ValueError:
            historical_request = True
        coverage_count = len(profile) + len(metrics) + sum(len(row) for row in statements)
        if profile or metrics or statements:
            point_in_time_safe = not historical_request and future_statement_count == 0
            return {
                "ok": bool(profile and metrics),
                "symbol": symbol,
                "external_symbol": external_symbol,
                "provider": "openbb_yfinance",
                "profile": profile,
                "key_metrics": metrics,
                "income_statements": statements,
                "field_coverage_count": coverage_count,
                "point_in_time_audit": {
                    "passed": point_in_time_safe,
                    "requested_as_of_date": as_of_date,
                    "current_profile_and_metrics": True,
                    "historical_request": historical_request,
                    "future_statement_rows_removed": future_statement_count,
                    "reason": (
                        "current_snapshot_context_only"
                        if point_in_time_safe
                        else "current_yfinance_fundamentals_not_valid_for_historical_oos"
                    ),
                },
                "strategy_feature_eligible": point_in_time_safe,
                "errors": errors,
            }
    return {
        "ok": False,
        "symbol": symbol,
        "external_symbol": "",
        "provider": "openbb_yfinance",
        "profile": {},
        "key_metrics": {},
        "income_statements": [],
        "field_coverage_count": 0,
        "point_in_time_audit": {
            "passed": False,
            "requested_as_of_date": as_of_date,
            "reason": "fundamental_fetch_failed",
        },
        "strategy_feature_eligible": False,
        "errors": errors,
    }


def _fetch_macro_series(
    fetcher: Any,
    *,
    name: str,
    symbol: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    try:
        query = fetcher.transform_query(
            {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "interval": "1d",
            }
        )
        raw = fetcher.extract_data(query, None)
        models = fetcher.transform_data(query, raw)
        rows = [model.model_dump(mode="json") for model in models]
        closes = [_finite(row.get("close"), math.nan) for row in rows]
        closes = [value for value in closes if math.isfinite(value) and value > 0]
        returns = [closes[index] / closes[index - 1] - 1.0 for index in range(1, len(closes))]
        period_return = closes[-1] / closes[0] - 1.0 if len(closes) >= 2 else math.nan
        realized_volatility = (
            (sum((value - sum(returns) / len(returns)) ** 2 for value in returns) / (len(returns) - 1)) ** 0.5
            * (252.0**0.5)
            if len(returns) >= 2
            else math.nan
        )
        return {
            "ok": len(closes) >= 2,
            "name": name,
            "symbol": symbol,
            "provider": "openbb_yfinance",
            "row_count": len(rows),
            "start_close": round(closes[0], 8) if closes else None,
            "end_close": round(closes[-1], 8) if closes else None,
            "period_return_pct": round(period_return * 100.0, 8) if math.isfinite(period_return) else None,
            "annualized_realized_volatility_pct": (
                round(realized_volatility * 100.0, 8) if math.isfinite(realized_volatility) else None
            ),
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "name": name,
            "symbol": symbol,
            "provider": "openbb_yfinance",
            "row_count": 0,
            "error": str(exc)[:240],
        }


def _normalize_calendar_events(value: Any) -> dict[str, Any]:
    rows = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    invalid_count = 0
    for row in rows[:200]:
        if not isinstance(row, dict):
            invalid_count += 1
            continue
        title = str(row.get("title") or row.get("name") or row.get("event") or "").strip()
        event_at = str(row.get("event_at") or row.get("datetime") or row.get("date") or "").strip()
        source = str(row.get("source") or row.get("provider") or "").strip()
        try:
            datetime.fromisoformat(event_at.replace("Z", "+00:00"))
            time_valid = True
        except (TypeError, ValueError):
            time_valid = False
        if not title or not event_at or not source or not time_valid:
            invalid_count += 1
            continue
        normalized.append(
            {
                "title": title[:180],
                "event_at": event_at,
                "source": source[:120],
                "importance": str(row.get("importance") or row.get("impact") or "unknown")[:40],
                "country": str(row.get("country") or "")[:40],
            }
        )
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in normalized:
        groups[(row["title"].casefold(), row["event_at"][:10])].add(row["source"])
    corroborated_count = sum(1 for sources in groups.values() if len(sources) >= 2)
    return {
        "passed": bool(normalized) and invalid_count == 0,
        "provider_contract": "external_scout_calendar_input_validated_by_openbb_context",
        "native_openbb_calendar_model_available": False,
        "event_count": len(normalized),
        "invalid_event_count": invalid_count,
        "source_count": len({row["source"] for row in normalized}),
        "corroborated_event_count": corroborated_count,
        "events": normalized[:50],
    }


def _run_fundamental_macro_calendar_crosscheck(
    request: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    reference_rows = snapshot.get("dataset_rows")
    if not isinstance(reference_rows, list) or not reference_rows:
        raise ValueError("dataset_rows_required")
    descriptor = request.get("descriptor") if isinstance(request.get("descriptor"), dict) else {}
    start_date = str(descriptor.get("start") or "")
    end_date = str(descriptor.get("end") or "")
    market = str(descriptor.get("market") or "KR")
    if not start_date or not end_date:
        raise ValueError("snapshot_date_range_required")
    macro_start_date = str(request.get("macro_start_date") or "")
    if not macro_start_date:
        macro_start_date = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=120)).strftime("%Y-%m-%d")

    symbols = list(
        dict.fromkeys(
            str(row.get("symbol") or "").strip().upper()
            for row in reference_rows
            if isinstance(row, dict) and str(row.get("symbol") or "").strip()
        )
    )[:3]
    fundamentals = [_fetch_fundamental_symbol(symbol, market, end_date) for symbol in symbols]
    macro_results = [
        _fetch_macro_series(
            YFinanceIndexHistoricalFetcher,
            name="KOSPI",
            symbol="^KS11",
            start_date=macro_start_date,
            end_date=end_date,
        ),
        _fetch_macro_series(
            YFinanceIndexHistoricalFetcher,
            name="S&P500",
            symbol="^GSPC",
            start_date=macro_start_date,
            end_date=end_date,
        ),
        _fetch_macro_series(
            YFinanceIndexHistoricalFetcher,
            name="VIX",
            symbol="^VIX",
            start_date=macro_start_date,
            end_date=end_date,
        ),
        _fetch_macro_series(
            YFinanceCurrencyHistoricalFetcher,
            name="USD_KRW",
            symbol="KRW",
            start_date=macro_start_date,
            end_date=end_date,
        ),
    ]
    action_results = [_fetch_symbol(symbol, market, start_date, end_date) for symbol in symbols]
    corporate_actions = []
    for result in action_results:
        events = [
            {
                "symbol": row.get("symbol"),
                "external_symbol": row.get("external_symbol"),
                "date": row.get("date"),
                "dividend": row.get("dividend"),
                "split_ratio": row.get("split_ratio"),
                "provider": row.get("provider"),
            }
            for row in result.get("rows", [])
            if _finite(row.get("dividend")) != 0.0 or _finite(row.get("split_ratio")) != 0.0
        ]
        corporate_actions.extend(events)
    calendar = _normalize_calendar_events(request.get("economic_calendar_events"))
    fundamental_retrieval_passed = sum(1 for row in fundamentals if row.get("ok")) == len(symbols) and bool(symbols)
    fundamental_passed = (
        fundamental_retrieval_passed
        and all(row.get("strategy_feature_eligible") for row in fundamentals)
    )
    macro_passed = sum(1 for row in macro_results if row.get("ok")) >= 3
    action_check_passed = all(result.get("ok") for result in action_results) and bool(action_results)
    blockers: list[str] = []
    if not fundamental_retrieval_passed:
        blockers.append("fundamental_coverage_incomplete")
    if fundamental_retrieval_passed and not fundamental_passed:
        blockers.append("fundamental_point_in_time_leakage_risk")
    if not macro_passed:
        blockers.append("macro_proxy_coverage_incomplete")
    if not action_check_passed:
        blockers.append("corporate_action_history_check_incomplete")
    if not calendar.get("passed"):
        blockers.append("economic_calendar_evidence_missing_or_invalid")
    quality_passed = not blockers
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "fundamentals": fundamentals,
        "macro_results": macro_results,
        "corporate_actions": corporate_actions,
        "economic_calendar": calendar,
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "ok": bool(fundamentals) and bool(macro_results),
        "schema": "codexstock_openbb_fundamental_macro_calendar_v1",
        "action": "crosscheck_fundamental_macro_calendar",
        "engine_name": "OpenBB",
        "engine_components": {
            "openbb_core": getattr(openbb_core, "__version__", "1.6.13"),
            "openbb_yfinance": getattr(openbb_yfinance, "__version__", "1.6.3"),
            "yfinance": yfinance.__version__,
        },
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "start_date": start_date,
        "end_date": end_date,
        "fundamental_results": fundamentals,
        "macro_results": macro_results,
        "corporate_action_history": {
            "passed": action_check_passed,
            "checked_symbol_count": len(action_results),
            "event_count": len(corporate_actions),
            "events": corporate_actions[:100],
        },
        "economic_calendar_evidence": calendar,
        "quality_gate": {
            "passed": quality_passed,
            "fundamental_coverage_passed": fundamental_passed,
            "fundamental_retrieval_passed": fundamental_retrieval_passed,
            "macro_proxy_coverage_passed": macro_passed,
            "corporate_action_history_passed": action_check_passed,
            "economic_calendar_passed": bool(calendar.get("passed")),
            "blockers": blockers,
        },
        "research_verdict": "CONTEXT_VERIFIED" if quality_passed else "PARTIAL_EVIDENCE_REVIEW",
        "capability_evidence": [
            {"capability": "openbb_fundamental_models", "passed": fundamental_retrieval_passed, "symbol_count": len(symbols)},
            {"capability": "fundamental_point_in_time_safety", "passed": fundamental_passed, "symbol_count": len(symbols)},
            {"capability": "openbb_macro_market_proxies", "passed": macro_passed, "series_count": len(macro_results)},
            {"capability": "openbb_corporate_actions", "passed": action_check_passed, "event_count": len(corporate_actions)},
            {"capability": "economic_calendar_contract", "passed": bool(calendar.get("passed")), "native_model": False},
            {"capability": "live_order_boundary", "passed": True, "live_order_allowed": False},
        ],
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "score_allowed": False,
        "promotion_allowed": False,
        "network_scope": "public_market_data_only",
        "decision": "VERIFY_ONLY",
        "live_order_allowed": False,
    }


def _run_historical_backfill(request: dict[str, Any], started: float) -> dict[str, Any]:
    contract = request.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("contract_required")
    symbols = [str(symbol).strip().upper() for symbol in contract.get("symbols", []) if str(symbol).strip()]
    symbols = list(dict.fromkeys(symbols))
    if not symbols or len(symbols) > 25:
        raise ValueError("symbols_required_or_over_limit")
    start_date = str(contract.get("start_date") or "")
    end_date = str(contract.get("end_date") or "")
    if not start_date or not end_date or start_date > end_date:
        raise ValueError("valid_date_range_required")
    if str(contract.get("timeframe") or "1d") != "1d":
        raise ValueError("only_daily_timeframe_supported")

    adjustment = "splits_and_dividends"
    fetched = [
        _fetch_symbol(
            symbol,
            "KR" if symbol.isdigit() and len(symbol) == 6 else "US",
            start_date,
            end_date,
            adjustment=adjustment,
        )
        for symbol in symbols
    ]
    rows = [row for result in fetched for row in result.get("rows", []) if isinstance(row, dict)]
    rows.sort(key=lambda row: (str(row.get("symbol") or ""), str(row.get("date") or "")))
    dataset_hash = hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    successful_symbols = [str(result.get("symbol") or "") for result in fetched if result.get("ok")]
    failed_symbols = [str(result.get("symbol") or "") for result in fetched if not result.get("ok")]
    currencies = sorted({str(row.get("currency") or "") for row in rows if row.get("currency")})
    price_units = sorted({str(row.get("price_unit") or "") for row in rows if row.get("price_unit")})
    all_required_fields = all(
        all(field in row for field in ("date", "open", "high", "low", "close", "volume"))
        for row in rows
    )
    return {
        "ok": len(successful_symbols) == len(symbols) and bool(rows) and all_required_fields,
        "schema": "codexstock_openbb_historical_backfill_result_v1",
        "action": "fetch_historical_ohlcv",
        "engine_name": "OpenBB",
        "source_commit": str(request.get("source_commit") or ""),
        "request_id": str(request.get("request_id") or ""),
        "request_hash": str(request.get("request_hash") or ""),
        "contract": contract,
        "adjustment_applied": adjustment,
        "symbol_count": len(symbols),
        "successful_symbol_count": len(successful_symbols),
        "failed_symbol_count": len(failed_symbols),
        "successful_symbols": successful_symbols,
        "failed_symbols": failed_symbols,
        "row_count": len(rows),
        "currencies": currencies,
        "price_units": price_units,
        "required_fields_complete": all_required_fields,
        "dataset_hash": dataset_hash,
        "dataset_rows": rows,
        "symbol_results": [
            {
                "symbol": result.get("symbol"),
                "external_symbol": result.get("external_symbol", ""),
                "ok": bool(result.get("ok")),
                "row_count": result.get("row_count", 0),
                "errors": result.get("errors", []),
            }
            for result in fetched
        ],
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "network_scope": "public_market_data_only",
        "decision": "VERIFY_ONLY",
        "score_allowed": False,
        "promotion_allowed": False,
        "live_order_allowed": False,
    }


def _compare_rows(reference_rows: list[dict[str, Any]], external_rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference = {
        (str(row.get("symbol") or ""), str(row.get("date") or "")): row
        for row in reference_rows
        if isinstance(row, dict)
    }
    comparisons: list[dict[str, Any]] = []
    currency_mismatches = 0
    unit_mismatches = 0
    for row in external_rows:
        local = reference.get((str(row.get("symbol") or ""), str(row.get("date") or "")))
        if not local:
            continue
        local_close = _finite(local.get("close"))
        external_close = _finite(row.get("close"))
        difference_pct = abs(external_close / local_close - 1.0) * 100.0 if local_close > 0 else 0.0
        currency_match = str(local.get("currency") or "") == str(row.get("currency") or "")
        unit_match = str(local.get("price_unit") or "") == str(row.get("price_unit") or "")
        currency_mismatches += 0 if currency_match else 1
        unit_mismatches += 0 if unit_match else 1
        comparisons.append(
            {
                "symbol": row["symbol"],
                "date": row["date"],
                "local_close": local_close,
                "external_close": external_close,
                "absolute_difference_pct": round(difference_pct, 8),
                "within_0_5pct": difference_pct <= 0.5,
                "currency_match": currency_match,
                "price_unit_match": unit_match,
            }
        )
    within_tolerance = sum(1 for row in comparisons if row["within_0_5pct"])
    max_difference = max((row["absolute_difference_pct"] for row in comparisons), default=0.0)
    mean_difference = (
        sum(row["absolute_difference_pct"] for row in comparisons) / len(comparisons)
        if comparisons
        else 0.0
    )
    return {
        "ok": bool(comparisons) and currency_mismatches == 0 and unit_mismatches == 0,
        "overlap_count": len(comparisons),
        "within_0_5pct_count": within_tolerance,
        "within_0_5pct_ratio": round(within_tolerance / len(comparisons), 6) if comparisons else 0.0,
        "max_absolute_difference_pct": round(max_difference, 8),
        "mean_absolute_difference_pct": round(mean_difference, 8),
        "currency_mismatch_count": currency_mismatches,
        "price_unit_mismatch_count": unit_mismatches,
        "latest_comparisons": comparisons[-15:],
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_information_only(request)
    action = str(request.get("action") or "")
    if action == "fetch_historical_ohlcv":
        return _run_historical_backfill(request, started)
    if action == "crosscheck_fundamental_macro_calendar":
        return _run_fundamental_macro_calendar_crosscheck(request, started)
    if action != "crosscheck_external_market_data":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    reference_rows = snapshot.get("dataset_rows")
    if not isinstance(reference_rows, list) or not reference_rows:
        raise ValueError("dataset_rows_required")
    descriptor = request.get("descriptor") if isinstance(request.get("descriptor"), dict) else {}
    start_date = str(descriptor.get("start") or "")
    end_date = str(descriptor.get("end") or "")
    market = str(descriptor.get("market") or "")
    if not start_date or not end_date:
        raise ValueError("snapshot_date_range_required")

    symbols: list[str] = []
    for row in reference_rows:
        symbol = str(row.get("symbol") or "") if isinstance(row, dict) else ""
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    fetched = [_fetch_symbol(symbol, market, start_date, end_date) for symbol in symbols[:5]]
    external_rows = [row for result in fetched for row in result.get("rows", [])]
    comparisons_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in external_rows:
        comparisons_by_symbol[str(row.get("symbol") or "")].append(row)
    symbol_results = []
    for result in fetched:
        symbol = str(result.get("symbol") or "")
        local_rows = [row for row in reference_rows if isinstance(row, dict) and str(row.get("symbol") or "") == symbol]
        comparison = _compare_rows(local_rows, comparisons_by_symbol.get(symbol, []))
        symbol_results.append(
            {
                "symbol": symbol,
                "external_symbol": result.get("external_symbol", ""),
                "fetched": bool(result.get("ok")),
                "external_row_count": result.get("row_count", 0),
                "errors": result.get("errors", []),
                "comparison": comparison,
            }
        )
    successful = sum(1 for row in symbol_results if row["fetched"] and row["comparison"]["ok"])
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "source_commit": request.get("source_commit"),
        "symbol_results": symbol_results,
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "ok": bool(symbol_results) and successful == len(symbol_results),
        "schema": "codexstock_openbb_crosscheck_result_v1",
        "action": "crosscheck_external_market_data",
        "engine_name": "OpenBB",
        "engine_components": {
            "openbb_core": getattr(openbb_core, "__version__", "1.6.13"),
            "openbb_yfinance": getattr(openbb_yfinance, "__version__", "1.6.3"),
            "yfinance": yfinance.__version__,
        },
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "start_date": start_date,
        "end_date": end_date,
        "symbol_count": len(symbol_results),
        "successful_symbol_count": successful,
        "external_row_count": len(external_rows),
        "symbol_results": symbol_results,
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "network_scope": "public_market_data_only",
        "decision": "VERIFY_ONLY",
        "live_order_allowed": False,
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
            "schema": "codexstock_openbb_crosscheck_result_v1",
            "engine_name": "OpenBB",
            "error": str(exc)[:600],
            "decision": "BLOCKED",
            "live_order_allowed": False,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

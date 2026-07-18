from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
import qlib
from qlib.contrib.eva.alpha import calc_ic, calc_long_short_return


FORBIDDEN_KEY_PARTS = (
    "account_number",
    "approval",
    "broker_token",
    "kis_",
    "order_token",
    "password",
    "secret",
)
FEATURE_COLUMNS = ["momentum_5", "momentum_20", "volume_ratio_20", "volatility_20"]


def _assert_research_only(value: Any, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(f"forbidden_input_field:{path}.{key}")
            _assert_research_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_research_only(child, f"{path}[{index}]")


def _finite(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _build_feature_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        close = _finite(row.get("close"))
        volume = _finite(row.get("volume"))
        symbol = str(row.get("symbol") or "").strip()
        date = str(row.get("date") or "").strip()
        if symbol and date and close > 0:
            records.append({"datetime": date, "instrument": symbol, "close": close, "volume": max(0.0, volume)})
    if not records:
        raise ValueError("valid_snapshot_rows_required")
    frame = pd.DataFrame.from_records(records)
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame = frame.dropna(subset=["datetime"]).sort_values(["instrument", "datetime"])
    grouped = frame.groupby("instrument", group_keys=False)
    frame["return_1"] = grouped["close"].pct_change(fill_method=None)
    frame["momentum_5"] = grouped["close"].pct_change(5, fill_method=None)
    frame["momentum_20"] = grouped["close"].pct_change(20, fill_method=None)
    volume_mean = grouped["volume"].rolling(20, min_periods=10).mean().reset_index(level=0, drop=True)
    frame["volume_ratio_20"] = frame["volume"] / volume_mean.replace(0.0, np.nan) - 1.0
    frame["volatility_20"] = (
        frame.groupby("instrument")["return_1"].rolling(20, min_periods=10).std().reset_index(level=0, drop=True)
    )
    frame["label"] = grouped["close"].shift(-1) / frame["close"] - 1.0
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS + ["label"])


def _fit_train_only_ridge(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    alpha: float = 1e-3,
) -> tuple[np.ndarray, dict[str, float]]:
    train_x = train[FEATURE_COLUMNS].to_numpy(dtype=float)
    test_x = test[FEATURE_COLUMNS].to_numpy(dtype=float)
    train_y = train["label"].to_numpy(dtype=float)
    means = train_x.mean(axis=0)
    scales = train_x.std(axis=0)
    scales[scales < 1e-12] = 1.0
    train_z = (train_x - means) / scales
    test_z = (test_x - means) / scales
    design = np.column_stack([np.ones(len(train_z)), train_z])
    ridge = np.eye(design.shape[1]) * max(0.0, float(alpha))
    ridge[0, 0] = 0.0
    matrix = design.T @ design + ridge
    target = design.T @ train_y
    coefficients = (
        np.linalg.lstsq(matrix, target, rcond=None)[0]
        if alpha <= 0.0
        else np.linalg.solve(matrix, target)
    )
    predictions = np.column_stack([np.ones(len(test_z)), test_z]) @ coefficients
    weights = {"intercept": float(coefficients[0])}
    weights.update({name: float(value) for name, value in zip(FEATURE_COLUMNS, coefficients[1:])})
    return predictions, weights


def _safe_metric(value: Any) -> float | None:
    number = _finite(value)
    return round(number, 10) if math.isfinite(number) else None


def _evaluate_predictions(test: pd.DataFrame, predictions: np.ndarray) -> dict[str, Any]:
    evaluated = test.copy()
    evaluated["prediction"] = predictions
    indexed = evaluated.set_index(["datetime", "instrument"]).sort_index()
    pred = indexed["prediction"]
    label = indexed["label"]
    ic, rank_ic = calc_ic(pred, label, dropna=True)
    instrument_count = int(indexed.index.get_level_values("instrument").nunique())
    quantile = max(0.2, 1.0 / max(2, instrument_count))
    long_short, market_average = calc_long_short_return(pred, label, quantile=quantile, dropna=True)
    mean_rank_ic = float(rank_ic.mean()) if len(rank_ic) else math.nan
    rank_ic_std = float(rank_ic.std(ddof=1)) if len(rank_ic) > 1 else math.nan
    positive_rank_ic_ratio = float((rank_ic > 0).mean()) if len(rank_ic) else math.nan
    cumulative_long_short_return = float((1.0 + long_short).prod() - 1.0) if len(long_short) else math.nan
    return {
        "ok": bool(len(rank_ic) and len(long_short)),
        "instrument_count": instrument_count,
        "oos_row_count": int(len(evaluated)),
        "oos_date_count": int(evaluated["datetime"].nunique()),
        "mean_ic": _safe_metric(ic.mean()),
        "mean_rank_ic": _safe_metric(mean_rank_ic),
        "rank_icir": _safe_metric(mean_rank_ic / rank_ic_std) if rank_ic_std > 0 else None,
        "positive_rank_ic_ratio": _safe_metric(positive_rank_ic_ratio),
        "mean_long_short_return": _safe_metric(long_short.mean()),
        "cumulative_long_short_return": _safe_metric(cumulative_long_short_return),
        "mean_market_return": _safe_metric(market_average.mean()),
    }


def _rolling_fold_boundaries(dates: list[Any], requested_fold_count: int) -> list[tuple[int, int]]:
    if len(dates) < 60:
        raise ValueError("at_least_60_feature_dates_required_for_rolling_oos")
    minimum_train_dates = max(30, int(len(dates) * 0.4))
    available_oos_dates = len(dates) - minimum_train_dates
    fold_count = max(3, min(int(requested_fold_count or 4), 8, available_oos_dates // 8))
    if fold_count < 3:
        raise ValueError("at_least_three_rolling_folds_required")
    test_size = max(8, available_oos_dates // fold_count)
    boundaries: list[tuple[int, int]] = []
    for fold_index in range(fold_count):
        start = minimum_train_dates + fold_index * test_size
        end = len(dates) if fold_index == fold_count - 1 else min(len(dates), start + test_size)
        if end - start >= 5:
            boundaries.append((start, end))
    if len(boundaries) < 3:
        raise ValueError("rolling_fold_construction_failed")
    return boundaries


def _run_rolling_model_comparison(request: dict[str, Any], started: float) -> dict[str, Any]:
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    rows = snapshot.get("dataset_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset_rows_required")

    frame = _build_feature_frame(rows)
    dates = sorted(frame["datetime"].unique())
    boundaries = _rolling_fold_boundaries(dates, int(request.get("fold_count") or 4))
    model_specs = (
        ("linear_lstsq", 0.0),
        ("ridge_1e-4", 1e-4),
        ("ridge_1e-3", 1e-3),
        ("ridge_1e-2", 1e-2),
    )
    models: list[dict[str, Any]] = []
    for model_name, alpha in model_specs:
        folds: list[dict[str, Any]] = []
        for fold_number, (start, end) in enumerate(boundaries, start=1):
            test_start = dates[start]
            test_end = dates[end - 1]
            train = frame[frame["datetime"] < test_start].copy()
            test = frame[(frame["datetime"] >= test_start) & (frame["datetime"] <= test_end)].copy()
            if len(train) < 80 or len(test) < 20 or test["instrument"].nunique() < 2:
                raise ValueError(f"insufficient_rolling_fold_rows:{fold_number}")
            predictions, weights = _fit_train_only_ridge(train, test, alpha=alpha)
            metrics = _evaluate_predictions(test, predictions)
            folds.append(
                {
                    "fold": fold_number,
                    "train_end": str(pd.Timestamp(test_start).date() - pd.Timedelta(days=1)),
                    "oos_start": str(pd.Timestamp(test_start).date()),
                    "oos_end": str(pd.Timestamp(test_end).date()),
                    "train_row_count": int(len(train)),
                    "feature_weights": {key: round(value, 10) for key, value in weights.items()},
                    **metrics,
                }
            )
        rank_ics = [float(row["mean_rank_ic"]) for row in folds if row.get("mean_rank_ic") is not None]
        long_shorts = [
            float(row["cumulative_long_short_return"])
            for row in folds
            if row.get("cumulative_long_short_return") is not None
        ]
        positive_fold_ratio = (
            sum(value > 0.0 for value in rank_ics) / len(rank_ics)
            if rank_ics
            else 0.0
        )
        compounded_long_short = (
            float(np.prod([1.0 + value for value in long_shorts]) - 1.0)
            if long_shorts
            else math.nan
        )
        median_rank_ic = float(np.median(rank_ics)) if rank_ics else math.nan
        minimum_rank_ic = min(rank_ics) if rank_ics else math.nan
        robust = bool(
            len(folds) >= 3
            and all(row.get("ok") for row in folds)
            and median_rank_ic >= 0.02
            and positive_fold_ratio >= 2.0 / 3.0
            and compounded_long_short > 0.0
        )
        models.append(
            {
                "model_name": model_name,
                "alpha": alpha,
                "fold_count": len(folds),
                "folds": folds,
                "median_rank_ic": _safe_metric(median_rank_ic),
                "minimum_rank_ic": _safe_metric(minimum_rank_ic),
                "positive_fold_ratio": _safe_metric(positive_fold_ratio),
                "compounded_long_short_return": _safe_metric(compounded_long_short),
                "quality_gate_passed": robust,
            }
        )
    models.sort(
        key=lambda row: (
            bool(row.get("quality_gate_passed")),
            float(row.get("median_rank_ic") or -999.0),
            float(row.get("compounded_long_short_return") or -999.0),
        ),
        reverse=True,
    )
    selected = models[0]
    quality_gate_passed = bool(selected.get("quality_gate_passed"))
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "source_commit": request.get("source_commit"),
        "models": models,
        "selected_model": selected.get("model_name"),
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "ok": all(all(fold.get("ok") for fold in model["folds"]) for model in models),
        "schema": "codexstock_qlib_rolling_model_comparison_v1",
        "action": "evaluate_rolling_model_comparison",
        "engine_name": "Qlib",
        "engine_version": str(getattr(qlib, "__version__", "0.9.7")),
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "feature_contract": "past_only_momentum_volume_volatility_v1",
        "label_contract": "next_session_close_return_v1",
        "validation_contract": "expanding_train_rolling_oos_no_future_rows_v1",
        "model_count": len(models),
        "fold_count": len(boundaries),
        "models": models,
        "selected_research_model": selected.get("model_name"),
        "quality_gate": {
            "passed": quality_gate_passed,
            "minimum_median_rank_ic": 0.02,
            "minimum_positive_fold_ratio": round(2.0 / 3.0, 6),
            "requires_positive_compounded_long_short_return": True,
            "blind_holdout_still_required": True,
        },
        "research_verdict": "QUEUE_BLIND_HOLDOUT" if quality_gate_passed else "RETRAIN_OR_REJECT",
        "capability_evidence": [
            {"capability": "expanding_rolling_oos", "passed": len(boundaries) >= 3, "fold_count": len(boundaries)},
            {"capability": "native_qlib_ic_evaluation", "passed": True, "model_count": len(models)},
            {"capability": "multi_model_comparison", "passed": len(models) >= 3, "model_count": len(models)},
            {"capability": "future_row_isolation", "passed": True, "training_rule": "datetime < oos_start"},
            {"capability": "live_order_boundary", "passed": True, "live_order_allowed": False},
        ],
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "promotion_allowed": False,
        "network_access_allowed": False,
        "decision": "RESEARCH_ONLY",
        "live_order_allowed": False,
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    _assert_research_only(request)
    action = str(request.get("action") or "")
    if action == "evaluate_rolling_model_comparison":
        return _run_rolling_model_comparison(request, started)
    if action != "evaluate_oos_rank_model":
        raise ValueError("unsupported_action")
    if request.get("live_order_allowed") is not False:
        raise ValueError("live_order_allowed_must_be_false")
    snapshot = request.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_required")
    rows = snapshot.get("dataset_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dataset_rows_required")

    frame = _build_feature_frame(rows)
    dates = sorted(frame["datetime"].unique())
    if len(dates) < 30:
        raise ValueError("at_least_30_feature_dates_required")
    split_index = max(20, min(len(dates) - 10, int(len(dates) * 0.7)))
    split_date = dates[split_index]
    train = frame[frame["datetime"] < split_date].copy()
    test = frame[frame["datetime"] >= split_date].copy()
    if len(train) < 40 or len(test) < 20 or test["instrument"].nunique() < 2:
        raise ValueError("insufficient_train_or_oos_rows")

    predictions, weights = _fit_train_only_ridge(train, test, alpha=1e-3)
    test["prediction"] = predictions
    indexed = test.set_index(["datetime", "instrument"]).sort_index()
    pred = indexed["prediction"]
    label = indexed["label"]
    ic, rank_ic = calc_ic(pred, label, dropna=True)
    instrument_count = int(indexed.index.get_level_values("instrument").nunique())
    quantile = max(0.2, 1.0 / max(2, instrument_count))
    long_short, market_average = calc_long_short_return(pred, label, quantile=quantile, dropna=True)
    rank_ic_std = float(rank_ic.std(ddof=1)) if len(rank_ic) > 1 else math.nan
    mean_rank_ic = float(rank_ic.mean())
    positive_rank_ic_ratio = float((rank_ic > 0).mean())
    cumulative_long_short_return = float((1.0 + long_short).prod() - 1.0)
    quality_gate_passed = bool(
        mean_rank_ic >= 0.02
        and positive_rank_ic_ratio >= 0.55
        and cumulative_long_short_return > 0.0
    )
    result_material = {
        "snapshot_id": request.get("snapshot_id"),
        "dataset_hash": request.get("dataset_hash"),
        "source_commit": request.get("source_commit"),
        "split_date": str(pd.Timestamp(split_date).date()),
        "weights": weights,
        "rank_ic": [_safe_metric(value) for value in rank_ic.tolist()],
        "long_short": [_safe_metric(value) for value in long_short.tolist()],
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "ok": bool(len(rank_ic) and len(long_short)),
        "schema": "codexstock_qlib_oos_result_v1",
        "action": "evaluate_oos_rank_model",
        "engine_name": "Qlib",
        "engine_version": str(getattr(qlib, "__version__", "0.9.7")),
        "source_commit": str(request.get("source_commit") or ""),
        "runtime_mode": "spawn_on_demand_only",
        "snapshot_id": str(request.get("snapshot_id") or ""),
        "dataset_hash": str(request.get("dataset_hash") or ""),
        "model_contract": "train_only_ridge_v1",
        "feature_contract": "past_only_momentum_volume_volatility_v1",
        "label_contract": "next_session_close_return_v1",
        "split_date": str(pd.Timestamp(split_date).date()),
        "train_row_count": int(len(train)),
        "oos_row_count": int(len(test)),
        "oos_date_count": int(test["datetime"].nunique()),
        "instrument_count": instrument_count,
        "feature_weights": {key: round(value, 10) for key, value in weights.items()},
        "mean_ic": _safe_metric(ic.mean()),
        "mean_rank_ic": _safe_metric(mean_rank_ic),
        "rank_icir": _safe_metric(mean_rank_ic / rank_ic_std) if rank_ic_std > 0 else None,
        "positive_rank_ic_ratio": _safe_metric(positive_rank_ic_ratio),
        "mean_long_short_return": _safe_metric(long_short.mean()),
        "cumulative_long_short_return": _safe_metric(cumulative_long_short_return),
        "mean_market_return": _safe_metric(market_average.mean()),
        "quality_gate": {
            "passed": quality_gate_passed,
            "minimum_mean_rank_ic": 0.02,
            "minimum_positive_rank_ic_ratio": 0.55,
            "requires_positive_cumulative_long_short_return": True,
        },
        "research_verdict": "REVIEW_CANDIDATE" if quality_gate_passed else "REJECT_CANDIDATE",
        "promotion_allowed": False,
        "result_hash": result_hash,
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "network_access_allowed": False,
        "decision": "RESEARCH_ONLY",
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
            "schema": "codexstock_qlib_oos_result_v1",
            "engine_name": "Qlib",
            "error": str(exc)[:600],
            "decision": "BLOCKED",
            "live_order_allowed": False,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

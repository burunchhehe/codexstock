from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Any, Callable

from .models import ExperimentRecord


Runner = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]


def walk_forward(record: ExperimentRecord, runner: Runner, folds: int = 4) -> dict[str, Any]:
    folds = max(2, min(10, int(folds)))
    start = date.fromisoformat(str(record.data_snapshot.get("start_date")))
    end = date.fromisoformat(str(record.data_snapshot.get("end_date")))
    days = (end - start).days + 1
    if days < folds * 60:
        raise ValueError("walk-forward requires at least 60 calendar days per fold")
    strategy = _strategy_payload(record)
    rows: list[dict[str, Any]] = []
    for index in range(folds):
        fold_start = start + timedelta(days=(days * index) // folds)
        fold_end = start + timedelta(days=(days * (index + 1)) // folds - 1)
        snapshot = dict(record.data_snapshot)
        snapshot.update({"start_date": fold_start.isoformat(), "end_date": min(fold_end, end).isoformat()})
        result = runner(strategy, snapshot, record.execution_model)
        rows.append(
            {
                "fold": index + 1,
                "start_date": result.get("start_date"),
                "end_date": result.get("end_date"),
                "row_count": result.get("row_count"),
                "total_return_pct": float(result.get("total_return_pct") or 0),
                "max_drawdown_pct": float(result.get("max_drawdown_pct") or 0),
                "trade_count": int(result.get("trade_count") or 0),
            }
        )
    returns = [row["total_return_pct"] for row in rows]
    positive = sum(value > 0 for value in returns)
    pass_rate = positive / len(rows) * 100
    return {
        "folds": rows,
        "summary": {
            "fold_count": len(rows),
            "positive_fold_count": positive,
            "pass_rate_pct": round(pass_rate, 2),
            "median_return_pct": round(median(returns), 4),
            "worst_return_pct": round(min(returns), 4),
            "stable": pass_rate >= 60 and median(returns) > 0,
        },
    }


def optimized_walk_forward(
    record: ExperimentRecord,
    runner: Runner,
    folds: int = 3,
    fast_values: list[int] | None = None,
    slow_values: list[int] | None = None,
    purge_days: int = 0,
    embargo_days: int = 0,
    purge_rows: int = 0,
    embargo_rows: int = 0,
) -> dict[str, Any]:
    """Anchored train/next-window-test walk-forward with no parameter lookahead."""
    if str(record.strategy.rules.get("type")) != "ma_cross":
        raise ValueError("strict walk-forward currently supports type=ma_cross")
    folds = max(2, min(8, int(folds)))
    start = date.fromisoformat(str(record.data_snapshot.get("start_date")))
    end = date.fromisoformat(str(record.data_snapshot.get("end_date")))
    total_days = (end - start).days + 1
    if total_days < (folds + 1) * 90:
        raise ValueError("strict walk-forward requires at least 90 calendar days per segment")
    purge_days, embargo_days = int(purge_days), int(embargo_days)
    if not 0 <= purge_days <= 365 or not 0 <= embargo_days <= 365:
        raise ValueError("purge_days and embargo_days must be between 0 and 365")
    requested_purge_rows = int(purge_rows); declared_label_horizon_rows = int(record.strategy.rules.get("label_horizon_rows") or 0)
    if not 0 <= requested_purge_rows <= 10_000 or not 0 <= declared_label_horizon_rows <= 10_000:
        raise ValueError("purge_rows and label_horizon_rows must be between 0 and 10000")
    purge_rows, embargo_rows = max(requested_purge_rows, declared_label_horizon_rows), int(embargo_rows)
    if not 0 <= purge_rows <= 10_000 or not 0 <= embargo_rows <= 10_000:
        raise ValueError("purge_rows and embargo_rows must be between 0 and 10000")
    fast_values = sorted({int(value) for value in (fast_values or [3, 5, 8, 12, 20]) if int(value) >= 2})[:12]
    slow_values = sorted({int(value) for value in (slow_values or [15, 20, 32, 50, 80]) if int(value) >= 3})[:12]
    candidates = [(fast, slow) for fast in fast_values for slow in slow_values if fast < slow]
    if not candidates:
        raise ValueError("strict walk-forward parameter grid is empty")
    segment_count = folds + 1
    boundaries = [start + timedelta(days=(total_days * index) // segment_count) for index in range(segment_count)] + [end + timedelta(days=1)]
    base_strategy = _strategy_payload(record)
    windows = []
    compounded = 1.0
    for fold in range(folds):
        boundary = boundaries[fold + 1]
        train_start, train_end = start, boundary - timedelta(days=purge_days + 1)
        test_start, test_end = boundary + timedelta(days=embargo_days), boundaries[fold + 2] - timedelta(days=1)
        if train_end < train_start or test_end < test_start:
            raise ValueError("purge/embargo leaves an empty train or test window")
        ranked = []
        for fast, slow in candidates:
            strategy = dict(base_strategy)
            strategy["rules"] = {**record.strategy.rules, "fast": fast, "slow": slow}
            snapshot = {**record.data_snapshot, "start_date": train_start.isoformat(), "end_date": train_end.isoformat(), "exclude_tail_rows": purge_rows}
            result = runner(strategy, snapshot, record.execution_model)
            total_return = float(result.get("total_return_pct") or 0)
            drawdown = abs(float(result.get("max_drawdown_pct") or 0))
            trades = int(result.get("trade_count") or 0)
            score = total_return - drawdown * 0.5 - (5 if trades < 2 else 0)
            ranked.append({"fast": fast, "slow": slow, "score": round(score, 6), "train_return_pct": total_return, "train_mdd_pct": -drawdown, "train_trades": trades, "train_row_count": result.get("row_count")})
        ranked.sort(key=lambda row: (row["score"], row["train_return_pct"], -row["fast"], -row["slow"]), reverse=True)
        selected = ranked[0]
        strategy = dict(base_strategy)
        strategy["rules"] = {**record.strategy.rules, "fast": selected["fast"], "slow": selected["slow"]}
        test_snapshot = {**record.data_snapshot, "start_date": test_start.isoformat(), "end_date": min(test_end, end).isoformat(), "exclude_head_rows": embargo_rows}
        test_result = runner(strategy, test_snapshot, record.execution_model)
        oos_return = float(test_result.get("total_return_pct") or 0)
        compounded *= 1 + oos_return / 100
        windows.append(
            {
                "fold": fold + 1,
                "train_start": train_start.isoformat(),
                "train_end": train_end.isoformat(),
                "test_start": test_start.isoformat(),
                "test_end": min(test_end, end).isoformat(),
                "purge_days": purge_days,
                "embargo_days": embargo_days,
                "purge_rows": purge_rows,
                "embargo_rows": embargo_rows,
                "excluded_boundary_days": (test_start - train_end).days - 1,
                "selected": selected,
                "candidate_count": len(ranked),
                "oos_return_pct": oos_return,
                "oos_mdd_pct": float(test_result.get("max_drawdown_pct") or 0),
                "oos_trade_count": int(test_result.get("trade_count") or 0),
                "oos_row_count": test_result.get("row_count"),
                "temporal_leakage": not (train_end < test_start),
            }
        )
    oos_returns = [row["oos_return_pct"] for row in windows]
    positive = sum(value > 0 for value in oos_returns)
    return {
        "method": "anchored_train_next_window_test",
        "parameter_selection_uses_oos": False,
        "purge_days": purge_days,
        "embargo_days": embargo_days,
        "purge_rows": purge_rows,
        "embargo_rows": embargo_rows,
        "requested_purge_rows": requested_purge_rows,
        "declared_label_horizon_rows": declared_label_horizon_rows,
        "windows": windows,
        "summary": {
            "fold_count": folds,
            "candidate_count_per_fold": len(candidates),
            "positive_oos_folds": positive,
            "oos_positive_rate_pct": round(positive / folds * 100, 2),
            "median_oos_return_pct": round(median(oos_returns), 4),
            "worst_oos_return_pct": round(min(oos_returns), 4),
            "compounded_oos_return_pct": round((compounded - 1) * 100, 4),
            "temporal_leakage_detected": any(row["temporal_leakage"] for row in windows),
            "passed": positive / folds >= 0.6 and median(oos_returns) > 0,
        },
    }


def parameter_robustness(record: ExperimentRecord, runner: Runner, radius: int = 2) -> dict[str, Any]:
    rules = dict(record.strategy.rules)
    if str(rules.get("type")) != "ma_cross":
        raise ValueError("parameter robustness currently supports type=ma_cross")
    radius = max(1, min(5, int(radius)))
    fast, slow = int(rules["fast"]), int(rules["slow"])
    candidates: list[dict[str, Any]] = []
    for fast_delta in range(-radius, radius + 1):
        for slow_delta in range(-radius * 2, radius * 2 + 1, 2):
            candidate_fast, candidate_slow = fast + fast_delta, slow + slow_delta
            if not 2 <= candidate_fast < candidate_slow <= 250:
                continue
            candidate_rules = dict(rules)
            candidate_rules.update({"fast": candidate_fast, "slow": candidate_slow})
            strategy = _strategy_payload(record)
            strategy["rules"] = candidate_rules
            result = runner(strategy, record.data_snapshot, record.execution_model)
            candidates.append(
                {
                    "fast": candidate_fast,
                    "slow": candidate_slow,
                    "total_return_pct": float(result.get("total_return_pct") or 0),
                    "max_drawdown_pct": float(result.get("max_drawdown_pct") or 0),
                    "trade_count": int(result.get("trade_count") or 0),
                }
            )
    returns = [row["total_return_pct"] for row in candidates]
    positive = sum(value > 0 for value in returns)
    positive_rate = positive / len(returns) * 100 if returns else 0
    return {
        "candidates": candidates,
        "summary": {
            "candidate_count": len(candidates),
            "positive_candidate_count": positive,
            "positive_rate_pct": round(positive_rate, 2),
            "median_return_pct": round(median(returns), 4) if returns else 0.0,
            "worst_return_pct": round(min(returns), 4) if returns else 0.0,
            "robust": positive_rate >= 60 and bool(returns) and median(returns) > 0,
        },
    }


def compare_records(records: list[ExperimentRecord]) -> dict[str, Any]:
    rows = []
    for record in records:
        rows.append(
            {
                "experiment_id": record.id,
                "strategy_name": record.strategy.name,
                "status": record.status.value,
                "adapter": record.backtest_adapter,
                "dataset_id": record.data_snapshot.get("dataset_id"),
                "total_return_pct": float(record.result.get("total_return_pct") or 0),
                "max_drawdown_pct": float(record.result.get("max_drawdown_pct") or 0),
                "trade_count": int(record.result.get("trade_count") or 0),
                "validation_passed": bool(record.validation.get("passed")),
            }
        )
    ranked = sorted(rows, key=lambda row: (row["validation_passed"], row["total_return_pct"], row["max_drawdown_pct"]), reverse=True)
    return {"count": len(rows), "ranked": ranked, "comparable": _comparable(rows)}


def _strategy_payload(record: ExperimentRecord) -> dict[str, Any]:
    return {
        "name": record.strategy.name,
        "version": record.strategy.version,
        "description": record.strategy.description,
        "rules": dict(record.strategy.rules),
    }


def _comparable(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and len({(row["adapter"], row["dataset_id"]) for row in rows}) == 1

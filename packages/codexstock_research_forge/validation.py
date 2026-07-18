from __future__ import annotations

from typing import Any
from .execution import resolve_execution_model


def validate_experiment_evidence(
    data_snapshot: dict[str, Any],
    execution_model: dict[str, Any],
    result: dict[str, Any],
    universe_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_execution = resolve_execution_model(execution_model)
    preset_declared = resolved_execution["execution_mode"] != "CUSTOM"
    data_mode = str(result.get("data_mode") or data_snapshot.get("data_mode") or "")
    quality = result.get("data_quality") if isinstance(result.get("data_quality"), dict) else {}
    checks = [
        {
            "id": "historical_provider_data",
            "ok": data_mode == "historical_provider",
            "required": True,
            "detail": data_mode or "missing",
        },
        {
            "id": "dataset_hash_recorded",
            "ok": bool(result.get("dataset_hash")),
            "required": True,
            "detail": str(result.get("dataset_hash") or "missing"),
        },
        {
            "id": "strict_temporal_order",
            "ok": bool(quality.get("strict_temporal_order")),
            "required": True,
            "detail": str(quality.get("strict_temporal_order")),
        },
        {
            "id": "no_invalid_ohlc",
            "ok": int(quality.get("invalid_ohlc_rows") or 0) == 0,
            "required": True,
            "detail": str(quality.get("invalid_ohlc_rows") or 0),
        },
        {
            "id": "next_bar_execution",
            "ok": (result.get("signal_timing"), result.get("fill_timing")) in {
                ("close_t", "open_t_plus_1"), ("close_t", "open_t_plus_delay"),
                ("completed_bar_t", "open_t_plus_delay"),
            },
            "required": True,
            "detail": f"{result.get('signal_timing')} -> {result.get('fill_timing')}",
        },
        {
            "id": "costs_declared",
            "ok": preset_declared or all(key in execution_model for key in ("commission_bps", "slippage_bps", "sell_tax_bps")),
            "required": True,
            "detail": "commission_bps, slippage_bps, sell_tax_bps required",
        },
        {
            "id": "liquidity_model_declared",
            "ok": preset_declared or all(key in execution_model for key in ("max_volume_participation", "market_impact_bps_at_full_participation")),
            "required": True,
            "detail": "volume participation and market impact must be explicit",
        },
        {
            "id": "order_delay_declared",
            "ok": (preset_declared or "order_delay_bars" in execution_model) and int(resolved_execution.get("order_delay_bars") or 0) >= 1,
            "required": True,
            "detail": str(resolved_execution.get("order_delay_bars") or "missing"),
        },
        {"id": "non_optimistic_execution", "ok": resolved_execution["execution_mode"] != "OPTIMISTIC", "required": True, "detail": resolved_execution["execution_mode"]},
        {
            "id": "point_in_time_universe",
            "ok": bool(universe_evidence and universe_evidence.get("passed")),
            "required": True,
            "detail": universe_evidence or "registered universe evidence is required to block survivorship bias",
        },
        {
            "id": "corporate_actions_adjusted",
            "ok": bool(data_snapshot.get("adjusted_prices")),
            "required": True,
            "detail": str(bool(data_snapshot.get("adjusted_prices"))),
        },
    ]
    blockers = [item["id"] for item in checks if item["required"] and not item["ok"]]
    return {
        "passed": not blockers,
        "checks": checks,
        "blockers": blockers,
        "recommendation": "PAPER_CANDIDATE" if not blockers else "RESEARCH_ONLY",
        "automatic_promotion": False,
        "universe_evidence": universe_evidence or {},
    }

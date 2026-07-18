from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

try:
    from .replay_evidence_milestones import (
        EVIDENCE_BUNDLE_HASH_CONTRACT,
        evidence_scope_hash,
        replay_evidence_bundle_hash,
    )
except ImportError:  # Direct app execution adds this directory to sys.path.
    from replay_evidence_milestones import (  # type: ignore[no-redef]
        EVIDENCE_BUNDLE_HASH_CONTRACT,
        evidence_scope_hash,
        replay_evidence_bundle_hash,
    )

try:
    from .replay_calendar_evidence import (
        CALENDAR_ADJACENCY_PROOF_CONTRACT,
        verify_calendar_adjacency_proof,
    )
except ImportError:  # Direct app execution adds this directory to sys.path.
    from replay_calendar_evidence import (  # type: ignore[no-redef]
        CALENDAR_ADJACENCY_PROOF_CONTRACT,
        verify_calendar_adjacency_proof,
    )


RESOLVED_STATUSES = {"verified_replacement_candidate", "quarantined_new_result"}


def rounded_financial_mean_pct(values: Iterable[float]) -> float:
    """Return a JSON-stable two-decimal mean using financial half-up rounding."""
    decimals = [Decimal(str(value)) for value in values]
    if not decimals:
        return 0.0
    mean = sum(decimals, Decimal("0")) / Decimal(len(decimals))
    return float(mean.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
ACTION_TIMING_EVIDENCE_FIELDS = (
    "decision_data_as_of",
    "execution_at",
    "signal_lag_bars",
    "decision_market_price",
    "execution_price_basis",
)
TRADE_EVIDENCE_FIELDS = (
    "symbol",
    "quantity",
    "entry_date",
    "entry_price",
    "entry_reason",
    "date",
    "holding_days",
    "price",
    "reason",
    "pnl_pct",
    "market_price",
    "execution_price",
    "notional",
    "net_proceeds",
    "commission",
    "sell_tax",
    "peak_market_price",
    "exit_trigger_market_price",
    "peak_drawdown_pct",
    "decision_return_pct",
    *ACTION_TIMING_EVIDENCE_FIELDS,
)

TRADE_NUMERIC_EVIDENCE_FIELDS = tuple(
    field
    for field in TRADE_EVIDENCE_FIELDS
    if field not in {
        "symbol",
        "reason",
        "entry_date",
        "entry_reason",
        "date",
        "decision_data_as_of",
        "execution_at",
        "execution_price_basis",
    }
)
BUY_EVIDENCE_FIELDS = (
    "symbol",
    "quantity",
    "date",
    "price",
    "reason",
    "market_price",
    "execution_price",
    "notional",
    "commission",
    "cash_cost",
    *ACTION_TIMING_EVIDENCE_FIELDS,
)
BUY_NUMERIC_EVIDENCE_FIELDS = (
    "quantity",
    "price",
    "market_price",
    "execution_price",
    "notional",
    "commission",
    "cash_cost",
    "signal_lag_bars",
    "decision_market_price",
)
NUMERIC_RECONCILIATION_TOLERANCE = 0.021
REPLAY_ARTIFACT_HASH_CONTRACT = "sha256-canonical-replay-v1+exact-journal-bytes-v1"


def canonical_replay_artifact_sha256(replay: dict[str, Any]) -> str:
    """Hash the exact logical replay row independently of JSONL formatting."""
    payload = json.dumps(
        replay,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def journal_artifact_sha256(journal_bytes: bytes) -> str:
    """Hash the exact persisted journal bytes so harmless-looking edits are visible."""
    return hashlib.sha256(journal_bytes).hexdigest()


def classify_replay_source_comparison(row: dict[str, Any]) -> dict[str, Any]:
    """Separate a valid new journal from an unsupported source-equivalence claim."""
    source_trade_count = _integer(row.get("source_trade_count"))
    new_trade_count = _integer(row.get("new_trade_count"))
    source_return = _number(row.get("source_total_return_pct"))
    new_return = _number(row.get("new_total_return_pct"))
    trade_count_difference = new_trade_count - source_trade_count
    return_difference = round(new_return - source_return, 4)
    cost_policy = row.get("cost_policy") if isinstance(row.get("cost_policy"), dict) else {}
    cost_policy_changed = bool(cost_policy.get("changed_from_archive"))
    review_reasons: list[str] = []
    if source_trade_count <= 0:
        review_reasons.append("source_trade_count_missing")
    elif trade_count_difference:
        review_reasons.append("trade_count_changed")
    if row.get("source_total_return_pct") is None:
        review_reasons.append("source_return_missing")
    elif abs(return_difference) > 0.1:
        review_reasons.append("return_changed_over_0_1pct_point")
    if cost_policy_changed:
        review_reasons.append("cost_policy_changed_from_source")
    equivalence_allowed = not review_reasons
    return {
        "schema": "codexstock_replay_source_comparison_v1",
        "status": "equivalent" if equivalence_allowed else "new_result_valid_source_equivalence_unproven",
        "source_trade_count": source_trade_count,
        "new_trade_count": new_trade_count,
        "trade_count_difference": trade_count_difference,
        "source_total_return_pct": row.get("source_total_return_pct"),
        "new_total_return_pct": row.get("new_total_return_pct"),
        "return_difference_pct_point": return_difference,
        "cost_policy_changed": cost_policy_changed,
        "review_reasons": review_reasons,
        "source_equivalence_claim_allowed": equivalence_allowed,
        "new_result_return_claim_is_separate": True,
    }


def audit_regeneration_evidence(
    *,
    ledger_rows: Iterable[dict[str, Any]],
    campaign_ids: Iterable[str],
    journal_root: Path,
    replay_rows: Iterable[dict[str, Any]] | None = None,
    deep: bool = True,
    issue_sample_limit: int = 20,
    required_evidence_schema_version: str | None = None,
    required_execution_timing_model_version: str | None = None,
    required_replay_data_bundle_evidence_schema: str | None = None,
) -> dict[str, Any]:
    """Independently verify every resolved Paper replay's durable evidence."""
    scope = {str(value or "").strip().upper() for value in campaign_ids if str(value or "").strip()}
    latest: dict[str, dict[str, Any]] = {}
    for row in ledger_rows:
        source_id = str(row.get("source_replay_id") or "").strip().upper()
        if source_id in scope:
            latest[source_id] = row
    replay_by_id = {
        str(row.get("id") or "").strip().upper(): row
        for row in (replay_rows or [])
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    replay_summary_required = replay_rows is not None
    evidence_version_match = re.fullmatch(
        r"historical-replay-evidence\.v(\d+)",
        str(required_evidence_schema_version or ""),
    )
    artifact_hash_required = bool(
        evidence_version_match and int(evidence_version_match.group(1)) >= 5
    )
    immutable_data_bundle_required = bool(
        evidence_version_match and int(evidence_version_match.group(1)) >= 4
    )

    issue_records: list[dict[str, Any]] = []
    issue_code_counts: dict[str, int] = {}
    missing_trade_field_counts = {field: 0 for field in TRADE_EVIDENCE_FIELDS}
    missing_buy_field_counts = {field: 0 for field in BUY_EVIDENCE_FIELDS}
    verified_count = 0
    quarantined_count = 0
    failed_count = 0
    legacy_evidence_count = 0
    audited_journal_count = 0
    audited_closed_trade_count = 0
    audited_buy_fill_count = 0
    audited_open_position_count = 0
    audited_replay_summary_count = 0
    comparison_status_counts: dict[str, int] = {}
    comparison_review_required_count = 0
    source_equivalence_claim_allowed_count = 0
    comparison_review_samples: list[dict[str, Any]] = []
    artifact_contract_valid_ids: set[str] = set()
    journal_artifact_match_ids: set[str] = set()
    replay_artifact_match_ids: set[str] = set()
    ledger_digest = hashlib.sha256()
    journal_digest = hashlib.sha256()
    replay_digest = hashlib.sha256()

    def add_issue(source_id: str, new_id: str, code: str, detail: str = "") -> None:
        issue_code_counts[code] = issue_code_counts.get(code, 0) + 1
        if len(issue_records) < max(1, int(issue_sample_limit)):
            issue_records.append(
                {
                    "source_replay_id": source_id,
                    "new_replay_id": new_id,
                    "code": code,
                    "detail": detail[:240],
                }
            )

    for source_id in sorted(latest):
        row = latest[source_id]
        ledger_digest.update(source_id.encode("utf-8"))
        ledger_digest.update(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        status = str(row.get("status") or "")
        if status == "regeneration_failed":
            failed_count += 1
            add_issue(source_id, "", "regeneration_failed", str(row.get("error") or ""))
            continue
        if status not in RESOLVED_STATUSES:
            continue
        new_id = str(row.get("new_replay_id") or "").strip().upper()
        if (
            required_evidence_schema_version
            and str(row.get("evidence_schema_version") or "")
            != required_evidence_schema_version
        ):
            legacy_evidence_count += 1
            add_issue(
                source_id,
                new_id,
                "evidence_schema_outdated",
                (
                    f"actual={row.get('evidence_schema_version') or 'missing'},"
                    f"required={required_evidence_schema_version}"
                ),
            )
            continue
        if (
            required_execution_timing_model_version
            and str(row.get("execution_timing_model_version") or "")
            != required_execution_timing_model_version
        ):
            legacy_evidence_count += 1
            add_issue(
                source_id,
                new_id,
                "execution_timing_model_ledger_outdated",
                (
                    f"actual={row.get('execution_timing_model_version') or 'missing'},"
                    f"required={required_execution_timing_model_version}"
                ),
            )
            continue
        if status == "quarantined_new_result":
            quarantined_count += 1
            add_issue(source_id, new_id, "quarantined_verdict")
            continue
        verified_count += 1
        expected_replay_artifact_sha256 = str(
            row.get("replay_artifact_sha256") or ""
        ).strip().lower()
        expected_journal_artifact_sha256 = str(
            row.get("journal_artifact_sha256") or ""
        ).strip().lower()
        if artifact_hash_required:
            artifact_contract_valid = (
                str(row.get("artifact_hash_contract") or "")
                == REPLAY_ARTIFACT_HASH_CONTRACT
                and re.fullmatch(r"[0-9a-f]{64}", expected_replay_artifact_sha256)
                is not None
                and re.fullmatch(r"[0-9a-f]{64}", expected_journal_artifact_sha256)
                is not None
            )
            if artifact_contract_valid:
                artifact_contract_valid_ids.add(source_id)
            if str(row.get("artifact_hash_contract") or "") != REPLAY_ARTIFACT_HASH_CONTRACT:
                add_issue(
                    source_id,
                    new_id,
                    "artifact_hash_contract_missing_or_invalid",
                    str(row.get("artifact_hash_contract") or "missing"),
                )
            if not re.fullmatch(r"[0-9a-f]{64}", expected_replay_artifact_sha256):
                add_issue(
                    source_id,
                    new_id,
                    "replay_artifact_hash_missing_or_invalid",
                )
            if not re.fullmatch(r"[0-9a-f]{64}", expected_journal_artifact_sha256):
                add_issue(
                    source_id,
                    new_id,
                    "journal_artifact_hash_missing_or_invalid",
                )
        comparison = classify_replay_source_comparison(row)
        comparison_status = str(comparison.get("status") or "unknown")
        comparison_status_counts[comparison_status] = comparison_status_counts.get(comparison_status, 0) + 1
        if comparison.get("source_equivalence_claim_allowed") is True:
            source_equivalence_claim_allowed_count += 1
        else:
            comparison_review_required_count += 1
            if len(comparison_review_samples) < max(1, int(issue_sample_limit)):
                comparison_review_samples.append(
                    {
                        "source_replay_id": source_id,
                        "new_replay_id": new_id,
                        **comparison,
                    }
                )
        if row.get("paper_only") is not True or row.get("live_order_allowed") is not False:
            add_issue(source_id, new_id, "unsafe_execution_boundary")
        if row.get("automatic_promotion") is not False:
            add_issue(source_id, new_id, "automatic_promotion_not_blocked")
        if not re.fullmatch(r"HREPLAY-[0-9]+", new_id):
            add_issue(source_id, new_id, "invalid_new_replay_id")
            continue

        expected_trades = _integer(row.get("new_trade_count"))
        reconciliation = row.get("reconciliation") if isinstance(row.get("reconciliation"), dict) else {}
        if (
            row.get("official_return_claim_allowed") is not True
            or reconciliation.get("official_return_claim_allowed") is not True
            or _integer(reconciliation.get("checked_count")) != expected_trades
            or _integer(reconciliation.get("warning_count")) != 0
            or _integer(reconciliation.get("blocker_count")) != 0
            or _integer(reconciliation.get("official_return_blocker_count")) != 0
            or _integer(reconciliation.get("needs_review")) != 0
        ):
            add_issue(source_id, new_id, "reconciliation_contract_invalid")

        current_costs = (
            row.get("cost_policy", {}).get("current", {})
            if isinstance(row.get("cost_policy"), dict)
            else {}
        )
        required_costs = {"commission_bps", "slippage_bps", "kr_sell_tax_bps"}
        market_specific_policy = str(current_costs.get("policy_version") or "").endswith(
            "paper-costs.v2"
        )
        if market_specific_policy:
            required_costs.add("fx_conversion_spread_bps")
        cost_policy_valid = required_costs.issubset(current_costs) and not any(
            _number(current_costs.get(key)) < 0 for key in required_costs
        )
        if market_specific_policy:
            cost_policy_valid = bool(
                cost_policy_valid
                and current_costs.get("us_regulatory_fee_policy_version")
                == "us-sec-finra-date-aware.v1"
                and isinstance(current_costs.get("us_sec_fee_schedule"), list)
                and isinstance(current_costs.get("us_finra_taf_schedule"), list)
            )
        if not cost_policy_valid:
            add_issue(source_id, new_id, "cost_policy_missing")

        journal_path = journal_root / f"{new_id}.json"
        if not journal_path.is_file():
            add_issue(source_id, new_id, "journal_missing", str(journal_path))
            continue
        if not deep:
            continue
        try:
            journal_bytes = journal_path.read_bytes()
            journal = json.loads(journal_bytes.decode("utf-8"))
            journal_digest.update(new_id.encode("utf-8"))
            actual_journal_artifact_sha256 = journal_artifact_sha256(journal_bytes)
            journal_digest.update(bytes.fromhex(actual_journal_artifact_sha256))
            if (
                artifact_hash_required
                and re.fullmatch(r"[0-9a-f]{64}", expected_journal_artifact_sha256)
                and actual_journal_artifact_sha256
                != expected_journal_artifact_sha256
            ):
                add_issue(
                    source_id,
                    new_id,
                    "journal_artifact_hash_mismatch",
                    (
                        f"expected={expected_journal_artifact_sha256},"
                        f"actual={actual_journal_artifact_sha256}"
                    ),
                )
            elif (
                artifact_hash_required
                and actual_journal_artifact_sha256
                == expected_journal_artifact_sha256
            ):
                journal_artifact_match_ids.add(source_id)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            add_issue(source_id, new_id, "journal_invalid", f"{type(exc).__name__}: {exc}")
            continue
        actions = journal.get("actions") if isinstance(journal, dict) else None
        if not isinstance(actions, list):
            add_issue(source_id, new_id, "journal_actions_missing")
            continue
        audited_journal_count += 1
        open_buys: dict[str, dict[str, Any]] = {}
        paired_entry_market_prices: dict[int, float] = {}
        buy_numeric_issues: dict[str, set[str]] = {}
        previous_action_day: date | None = None

        def note_buy_issue(code: str, detail: str) -> None:
            buy_numeric_issues.setdefault(code, set()).add(detail)

        for action_index, action in enumerate(actions):
            if not isinstance(action, dict):
                note_buy_issue(
                    "journal_action_shape_invalid",
                    f"index={action_index},type={type(action).__name__}",
                )
                continue
            side = str(action.get("side") or "").upper()
            symbol = str(action.get("symbol") or "").strip().upper()
            if side in {"BUY", "SELL"}:
                action_day = _iso_date(action.get("date"))
                if action_day is not None:
                    if previous_action_day is not None and action_day < previous_action_day:
                        note_buy_issue(
                            "journal_action_date_order_invalid",
                            f"previous={previous_action_day.isoformat()},current={action_day.isoformat()}",
                        )
                    previous_action_day = action_day
                for timing_code, timing_detail in _audit_action_timing(
                    action,
                    require_calendar_proof=str(
                        required_execution_timing_model_version or ""
                    ).endswith(".v3"),
                ):
                    note_buy_issue(timing_code, f"index={action_index},{timing_detail}")
            if side == "BUY":
                audited_buy_fill_count += 1
                for field in BUY_EVIDENCE_FIELDS:
                    value = action.get(field)
                    missing = value is None or (
                        field in {
                            "symbol",
                            "date",
                            "reason",
                            "decision_data_as_of",
                            "execution_at",
                            "execution_price_basis",
                        }
                        and not str(value).strip()
                    )
                    if missing:
                        missing_buy_field_counts[field] += 1
                numbers = {
                    field: _finite_number(action.get(field))
                    for field in BUY_NUMERIC_EVIDENCE_FIELDS
                }
                invalid_fields = sorted(
                    field for field, value in numbers.items() if value is None
                )
                if invalid_fields:
                    note_buy_issue("buy_numeric_invalid", ",".join(invalid_fields))
                else:
                    quantity = numbers["quantity"]
                    effective_price = numbers["price"]
                    market_price = numbers["market_price"]
                    execution_price = numbers["execution_price"]
                    notional = numbers["notional"]
                    commission = numbers["commission"]
                    cash_cost = numbers["cash_cost"]
                    positive = {
                        "quantity": quantity,
                        "price": effective_price,
                        "market_price": market_price,
                        "execution_price": execution_price,
                        "notional": notional,
                        "cash_cost": cash_cost,
                    }
                    nonpositive = sorted(
                        field for field, value in positive.items() if value <= 0
                    )
                    if nonpositive:
                        note_buy_issue("buy_price_or_quantity_nonpositive", ",".join(nonpositive))
                    else:
                        if not _is_whole_share_quantity(quantity):
                            note_buy_issue("buy_quantity_unit_invalid", str(quantity))
                        if commission < 0:
                            note_buy_issue("buy_commission_negative", "commission")
                        if market_price > execution_price + NUMERIC_RECONCILIATION_TOLERANCE or (
                            execution_price > effective_price + NUMERIC_RECONCILIATION_TOLERANCE
                        ):
                            note_buy_issue(
                                "buy_execution_order_invalid",
                                "market<=execution<=effective_entry",
                            )
                        if cost_policy_valid:
                            commission_rate = _number(current_costs.get("commission_bps")) / 10_000.0
                            slippage_rate = _number(current_costs.get("slippage_bps")) / 10_000.0
                            market = str(
                                action.get("market")
                                or ("KR" if re.fullmatch(r"[0-9]{6}", symbol) else "US")
                            ).upper()
                            fx_spread_rate = (
                                _number(current_costs.get("fx_conversion_spread_bps"))
                                / 10_000.0
                                if market_specific_policy and market == "US"
                                else 0.0
                            )
                            gross_cost = quantity * execution_price
                            amount_rounding_tolerance = max(
                                NUMERIC_RECONCILIATION_TOLERANCE,
                                quantity * 0.000051 + NUMERIC_RECONCILIATION_TOLERANCE,
                            )
                            expected_commission = round(gross_cost * commission_rate, 2)
                            expected_fx_conversion = round(gross_cost * fx_spread_rate, 2)
                            expected_execution = round(
                                market_price * (1.0 + slippage_rate),
                                4,
                            )
                            expected_effective = round(cash_cost / quantity, 4)
                            if abs(commission - expected_commission) > NUMERIC_RECONCILIATION_TOLERANCE:
                                note_buy_issue("buy_commission_mismatch", "commission")
                            if abs(execution_price - expected_execution) > NUMERIC_RECONCILIATION_TOLERANCE:
                                note_buy_issue("buy_slippage_mismatch", "execution_price")
                            if abs(effective_price - expected_effective) > NUMERIC_RECONCILIATION_TOLERANCE:
                                note_buy_issue("buy_effective_price_mismatch", "price")
                            if abs(notional - gross_cost) > amount_rounding_tolerance:
                                note_buy_issue("buy_notional_mismatch", "notional")
                            cash_rounding_tolerance = max(
                                NUMERIC_RECONCILIATION_TOLERANCE,
                                quantity * 0.00011,
                            )
                            if (
                                abs(
                                    _number(action.get("fx_conversion_cost"))
                                    - expected_fx_conversion
                                )
                                > NUMERIC_RECONCILIATION_TOLERANCE
                            ):
                                note_buy_issue(
                                    "buy_fx_conversion_cost_mismatch",
                                    "fx_conversion_cost",
                                )
                            if (
                                abs(
                                    cash_cost
                                    - (notional + commission + expected_fx_conversion)
                                )
                                > cash_rounding_tolerance
                            ):
                                note_buy_issue("buy_cash_cost_mismatch", "cash_cost")
                if _iso_date(action.get("date")) is None:
                    note_buy_issue("buy_date_invalid", str(action.get("date") or "missing"))
                if symbol in open_buys:
                    note_buy_issue("buy_duplicate_open_position", symbol)
                if symbol:
                    open_buys[symbol] = action
            elif side == "SELL":
                entry = open_buys.pop(symbol, None)
                if entry is None:
                    note_buy_issue("sell_without_buy_evidence", symbol or "missing_symbol")
                    continue
                pair_numbers = {
                    "buy_quantity": _finite_number(entry.get("quantity")),
                    "sell_quantity": _finite_number(action.get("quantity")),
                    "buy_price": _finite_number(entry.get("price")),
                    "sell_entry_price": _finite_number(action.get("entry_price")),
                }
                if any(value is None for value in pair_numbers.values()):
                    note_buy_issue("entry_fill_pair_numeric_invalid", symbol)
                else:
                    if abs(pair_numbers["buy_quantity"] - pair_numbers["sell_quantity"]) > 1e-9:
                        note_buy_issue("entry_fill_quantity_mismatch", symbol)
                    if (
                        abs(pair_numbers["buy_price"] - pair_numbers["sell_entry_price"])
                        > NUMERIC_RECONCILIATION_TOLERANCE
                    ):
                        note_buy_issue("entry_fill_price_mismatch", symbol)
                if str(action.get("entry_date") or "") != str(entry.get("date") or ""):
                    note_buy_issue("entry_fill_date_mismatch", symbol)
                if str(action.get("entry_reason") or "") != str(entry.get("reason") or ""):
                    note_buy_issue("entry_fill_reason_mismatch", symbol)
                entry_market_price = _finite_number(entry.get("market_price"))
                if entry_market_price is not None:
                    paired_entry_market_prices[id(action)] = entry_market_price
            else:
                note_buy_issue(
                    "journal_action_side_invalid",
                    f"index={action_index},side={side or 'missing'}",
                )
        audited_open_position_count += len(open_buys)
        if any(missing_buy_field_counts.values()):
            # Per-journal issue details remain bounded while aggregate field counts
            # preserve the exact number of incomplete BUY fills.
            missing_here = sorted(
                field
                for field in BUY_EVIDENCE_FIELDS
                if any(
                    isinstance(action, dict)
                    and str(action.get("side") or "").upper() == "BUY"
                    and (
                        action.get(field) is None
                        or (
                            field in {
                                "symbol",
                                "date",
                                "reason",
                                "decision_data_as_of",
                                "execution_at",
                                "execution_price_basis",
                            }
                            and not str(action.get(field) or "").strip()
                        )
                    )
                    for action in actions
                )
            )
            if missing_here:
                add_issue(source_id, new_id, "buy_evidence_missing", ",".join(missing_here))
        for code, details in sorted(buy_numeric_issues.items()):
            add_issue(source_id, new_id, code, ",".join(sorted(details)))

        if replay_summary_required:
            replay = replay_by_id.get(new_id)
            if replay is None:
                add_issue(source_id, new_id, "replay_summary_missing")
            else:
                audited_replay_summary_count += 1
                actual_replay_artifact_sha256 = canonical_replay_artifact_sha256(replay)
                if (
                    artifact_hash_required
                    and re.fullmatch(r"[0-9a-f]{64}", expected_replay_artifact_sha256)
                    and actual_replay_artifact_sha256
                    != expected_replay_artifact_sha256
                ):
                    add_issue(
                        source_id,
                        new_id,
                        "replay_artifact_hash_mismatch",
                        (
                            f"expected={expected_replay_artifact_sha256},"
                            f"actual={actual_replay_artifact_sha256}"
                        ),
                    )
                elif (
                    artifact_hash_required
                    and actual_replay_artifact_sha256
                    == expected_replay_artifact_sha256
                ):
                    replay_artifact_match_ids.add(source_id)
                replay_digest.update(new_id.encode("utf-8"))
                replay_digest.update(
                    json.dumps(
                        replay,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                for code, detail in _audit_replay_data_contract(
                    replay,
                    ledger=row,
                    actions=actions,
                    require_immutable_data_bundle=immutable_data_bundle_required,
                    required_execution_timing_model_version=required_execution_timing_model_version,
                ):
                    add_issue(source_id, new_id, code, detail)
                for code, detail in _audit_replay_summary(
                    ledger=row,
                    replay=replay,
                    actions=actions,
                    cost_policy=current_costs,
                    action_count=len(actions),
                    closed_count=len(
                        [
                            action
                            for action in actions
                            if isinstance(action, dict)
                            and str(action.get("side") or "").upper() == "SELL"
                        ]
                    ),
                    open_position_count=len(open_buys),
                    action_cost_evidence=_journal_action_cost_evidence(actions),
                    action_date_bounds=_journal_action_date_bounds(actions),
                    action_symbols={
                        str(action.get("symbol") or "").strip().upper()
                        for action in actions
                        if isinstance(action, dict)
                        and str(action.get("side") or "").upper() in {"BUY", "SELL"}
                        and str(action.get("symbol") or "").strip()
                    },
                    closed_returns=[
                        value
                        for action in actions
                        if isinstance(action, dict)
                        and str(action.get("side") or "").upper() == "SELL"
                        and (value := _finite_number(action.get("pnl_pct"))) is not None
                    ],
                    open_position_evidence=open_buys,
                ):
                    add_issue(source_id, new_id, code, detail)
        closed = [
            action
            for action in actions
            if isinstance(action, dict) and str(action.get("side") or "").upper() == "SELL"
        ]
        audited_closed_trade_count += len(closed)
        if len(closed) != expected_trades:
            add_issue(
                source_id,
                new_id,
                "journal_trade_count_mismatch",
                f"journal={len(closed)}, ledger={expected_trades}",
            )
        record_missing: set[str] = set()
        record_numeric_issues: dict[str, set[str]] = {}

        def note_numeric_issue(code: str, detail: str) -> None:
            record_numeric_issues.setdefault(code, set()).add(detail)

        for trade in closed:
            for field in TRADE_EVIDENCE_FIELDS:
                value = trade.get(field)
                missing = value is None or (
                    field in {
                        "reason",
                        "symbol",
                        "entry_date",
                        "entry_reason",
                        "date",
                        "decision_data_as_of",
                        "execution_at",
                        "execution_price_basis",
                    }
                    and not str(value).strip()
                )
                if missing:
                    missing_trade_field_counts[field] += 1
                    record_missing.add(field)
            numbers = {
                field: _finite_number(trade.get(field))
                for field in TRADE_NUMERIC_EVIDENCE_FIELDS
            }
            invalid_numeric_fields = sorted(
                field for field, value in numbers.items() if value is None
            )
            if invalid_numeric_fields:
                note_numeric_issue("trade_numeric_invalid", ",".join(invalid_numeric_fields))
                continue
            entry_day = _iso_date(trade.get("entry_date"))
            exit_day = _iso_date(trade.get("date"))
            if entry_day is None or exit_day is None:
                note_numeric_issue("trade_date_invalid", "entry_date_or_exit_date")
            elif exit_day < entry_day:
                note_numeric_issue("trade_date_order_invalid", "exit_before_entry")
            else:
                holding_days = numbers["holding_days"]
                calendar_days = (exit_day - entry_day).days
                if holding_days < 0 or holding_days > calendar_days:
                    note_numeric_issue(
                        "trade_holding_days_invalid",
                        f"recorded={holding_days},calendar_days={calendar_days}",
                    )

            quantity = numbers["quantity"]
            entry_price = numbers["entry_price"]
            exit_price = numbers["price"]
            market_price = numbers["market_price"]
            execution_price = numbers["execution_price"]
            notional = numbers["notional"]
            net_proceeds = numbers["net_proceeds"]
            commission = numbers["commission"]
            sell_tax = numbers["sell_tax"]
            peak_price = numbers["peak_market_price"]
            trigger_price = numbers["exit_trigger_market_price"]
            recorded_return = numbers["pnl_pct"]
            recorded_drawdown = numbers["peak_drawdown_pct"]
            decision_return = numbers["decision_return_pct"]
            decision_market_price = numbers["decision_market_price"]
            positive_fields = {
                "quantity": quantity,
                "entry_price": entry_price,
                "price": exit_price,
                "market_price": market_price,
                "execution_price": execution_price,
                "notional": notional,
                "net_proceeds": net_proceeds,
                "peak_market_price": peak_price,
                "exit_trigger_market_price": trigger_price,
                "decision_market_price": decision_market_price,
            }
            nonpositive = sorted(field for field, value in positive_fields.items() if value <= 0)
            if nonpositive:
                note_numeric_issue("trade_price_or_quantity_nonpositive", ",".join(nonpositive))
                continue
            if not _is_whole_share_quantity(quantity):
                note_numeric_issue("trade_quantity_unit_invalid", str(quantity))
            if commission < 0 or sell_tax < 0:
                note_numeric_issue("trade_cost_negative", "commission_or_sell_tax")
            if exit_price > execution_price + NUMERIC_RECONCILIATION_TOLERANCE or (
                execution_price > market_price + NUMERIC_RECONCILIATION_TOLERANCE
            ):
                note_numeric_issue("trade_execution_order_invalid", "net_exit<=execution<=market")
            if trigger_price > peak_price + NUMERIC_RECONCILIATION_TOLERANCE:
                note_numeric_issue("trade_peak_order_invalid", "trigger<=peak")
            entry_market_price = paired_entry_market_prices.get(id(trade))
            if (
                entry_market_price is not None
                and peak_price + NUMERIC_RECONCILIATION_TOLERANCE < entry_market_price
            ):
                note_numeric_issue(
                    "trade_peak_below_entry_market",
                    f"peak={peak_price},entry_market={entry_market_price}",
                )
            if abs(trigger_price - decision_market_price) > NUMERIC_RECONCILIATION_TOLERANCE:
                note_numeric_issue(
                    "trade_exit_trigger_price_mismatch",
                    f"trigger={trigger_price},decision_market={decision_market_price}",
                )

            computed_return = ((exit_price / entry_price) - 1.0) * 100.0
            if abs(computed_return - recorded_return) > NUMERIC_RECONCILIATION_TOLERANCE:
                note_numeric_issue("trade_return_mismatch", "pnl_pct")
            computed_drawdown = ((trigger_price / peak_price) - 1.0) * 100.0
            if abs(computed_drawdown - recorded_drawdown) > NUMERIC_RECONCILIATION_TOLERANCE:
                note_numeric_issue("trade_peak_drawdown_mismatch", "peak_drawdown_pct")
            reason_issue = _audit_exit_reason_threshold(
                trade,
                computed_return=decision_return,
                computed_drawdown=computed_drawdown,
            )
            if reason_issue:
                note_numeric_issue("exit_reason_threshold_mismatch", reason_issue)

            if cost_policy_valid:
                commission_rate = _number(current_costs.get("commission_bps")) / 10_000.0
                sell_tax_rate = _number(current_costs.get("kr_sell_tax_bps")) / 10_000.0
                slippage_rate = _number(current_costs.get("slippage_bps")) / 10_000.0
                gross_proceeds = quantity * execution_price
                amount_rounding_tolerance = (
                    quantity * 0.000051 + NUMERIC_RECONCILIATION_TOLERANCE
                )
                expected_commission = round(gross_proceeds * commission_rate, 2)
                symbol = str(trade.get("symbol") or "").strip().upper()
                market = str(
                    trade.get("market")
                    or ("KR" if re.fullmatch(r"[0-9]{6}", symbol) else "US")
                ).upper()
                expected_sell_tax = (
                    round(gross_proceeds * sell_tax_rate, 2)
                    if market == "KR"
                    else 0.0
                )
                fx_spread_rate = (
                    _number(current_costs.get("fx_conversion_spread_bps")) / 10_000.0
                    if market_specific_policy and market == "US"
                    else 0.0
                )
                expected_fx_conversion = round(gross_proceeds * fx_spread_rate, 2)
                expected_us_sec_fee, expected_us_finra_taf = (
                    _us_regulatory_cost_from_policy(
                        current_costs,
                        trade_date=str(trade.get("date") or ""),
                        quantity=quantity,
                        gross_krw=gross_proceeds,
                        usdkrw_rate=_number(trade.get("usdkrw_rate")),
                    )
                    if market_specific_policy and market == "US"
                    else (0.0, 0.0)
                )
                expected_us_sec_fee = round(expected_us_sec_fee, 2)
                expected_us_finra_taf = round(expected_us_finra_taf, 2)
                expected_execution = round(market_price * (1.0 - slippage_rate), 4)
                expected_exit = round(
                    (
                        gross_proceeds
                        - expected_commission
                        - expected_sell_tax
                        - expected_fx_conversion
                        - expected_us_sec_fee
                        - expected_us_finra_taf
                    )
                    / quantity,
                    4,
                )
                if abs(commission - expected_commission) > NUMERIC_RECONCILIATION_TOLERANCE:
                    note_numeric_issue("trade_commission_mismatch", "commission")
                if abs(sell_tax - expected_sell_tax) > NUMERIC_RECONCILIATION_TOLERANCE:
                    note_numeric_issue("trade_sell_tax_mismatch", "sell_tax")
                if (
                    abs(_number(trade.get("fx_conversion_cost")) - expected_fx_conversion)
                    > NUMERIC_RECONCILIATION_TOLERANCE
                ):
                    note_numeric_issue(
                        "trade_fx_conversion_cost_mismatch",
                        "fx_conversion_cost",
                    )
                if (
                    abs(_number(trade.get("us_sec_fee")) - expected_us_sec_fee)
                    > NUMERIC_RECONCILIATION_TOLERANCE
                ):
                    note_numeric_issue("trade_us_sec_fee_mismatch", "us_sec_fee")
                if (
                    abs(_number(trade.get("us_finra_taf")) - expected_us_finra_taf)
                    > NUMERIC_RECONCILIATION_TOLERANCE
                ):
                    note_numeric_issue("trade_us_finra_taf_mismatch", "us_finra_taf")
                if abs(execution_price - expected_execution) > NUMERIC_RECONCILIATION_TOLERANCE:
                    note_numeric_issue("trade_slippage_mismatch", "execution_price")
                if abs(exit_price - expected_exit) > NUMERIC_RECONCILIATION_TOLERANCE:
                    note_numeric_issue("trade_net_exit_price_mismatch", "price")
                if abs(notional - gross_proceeds) > amount_rounding_tolerance:
                    note_numeric_issue("trade_notional_mismatch", "notional")
                if (
                    abs(
                        net_proceeds
                        - (
                            notional
                            - commission
                            - sell_tax
                            - expected_fx_conversion
                            - expected_us_sec_fee
                            - expected_us_finra_taf
                        )
                    )
                    > amount_rounding_tolerance
                ):
                    note_numeric_issue("trade_net_proceeds_mismatch", "net_proceeds")
        if record_missing:
            add_issue(source_id, new_id, "trade_evidence_missing", ",".join(sorted(record_missing)))
        for code, details in sorted(record_numeric_issues.items()):
            add_issue(source_id, new_id, code, ",".join(sorted(details)))

    resolved_count = verified_count + quarantined_count
    unresolved_count = max(0, len(scope) - resolved_count - failed_count)
    missing_trade_field_counts = {
        key: value for key, value in missing_trade_field_counts.items() if value
    }
    missing_buy_field_counts = {
        key: value for key, value in missing_buy_field_counts.items() if value
    }
    issue_count = sum(issue_code_counts.values())
    artifact_anchor_verified_ids = (
        artifact_contract_valid_ids
        & journal_artifact_match_ids
        & replay_artifact_match_ids
    )
    artifact_anchor_verified_count = len(artifact_anchor_verified_ids)
    artifact_anchor_required_count = verified_count if artifact_hash_required else 0
    artifact_anchor_verified_pct = round(
        (artifact_anchor_verified_count / artifact_anchor_required_count) * 100.0,
        2,
    ) if artifact_anchor_required_count else 0.0
    artifact_anchor_campaign_coverage_pct = round(
        (artifact_anchor_verified_count / len(scope)) * 100.0,
        2,
    ) if scope else 100.0
    ledger_evidence_hash = ledger_digest.hexdigest()
    journal_evidence_hash = journal_digest.hexdigest() if deep else None
    replay_evidence_hash = (
        replay_digest.hexdigest() if deep and replay_summary_required else None
    )
    audited_source_ids = sorted(scope)
    audited_scope_hash = evidence_scope_hash(audited_source_ids)
    effective_artifact_hash_contract = (
        REPLAY_ARTIFACT_HASH_CONTRACT if artifact_hash_required else "not_required"
    )
    evidence_bundle_hash = replay_evidence_bundle_hash(
        audited_scope_hash=audited_scope_hash,
        evidence_schema_version=required_evidence_schema_version,
        execution_timing_model_version=required_execution_timing_model_version,
        artifact_hash_contract=effective_artifact_hash_contract,
        ledger_evidence_hash=ledger_evidence_hash,
        journal_evidence_hash=journal_evidence_hash,
        replay_evidence_hash=replay_evidence_hash,
        replay_data_bundle_evidence_schema=required_replay_data_bundle_evidence_schema,
    )
    audit_ok = issue_count == 0 and unresolved_count == 0
    return {
        "schema": "codexstock_replay_evidence_audit_v8",
        "ok": audit_ok,
        "status": "passed" if audit_ok else "review_required",
        "deep": bool(deep),
        "required_evidence_schema_version": required_evidence_schema_version,
        "required_execution_timing_model_version": required_execution_timing_model_version,
        "required_replay_data_bundle_evidence_schema": required_replay_data_bundle_evidence_schema,
        "campaign_target_count": len(scope),
        "resolved_count": resolved_count,
        "verified_count": verified_count,
        "quarantined_count": quarantined_count,
        "failed_count": failed_count,
        "legacy_evidence_count": legacy_evidence_count,
        "unresolved_count": unresolved_count,
        "audited_journal_count": audited_journal_count,
        "audited_closed_trade_count": audited_closed_trade_count,
        "audited_buy_fill_count": audited_buy_fill_count,
        "audited_open_position_count": audited_open_position_count,
        "audited_replay_summary_count": audited_replay_summary_count,
        "artifact_hash_contract": effective_artifact_hash_contract,
        "artifact_anchor_required_count": artifact_anchor_required_count,
        "artifact_anchor_verified_count": artifact_anchor_verified_count,
        "artifact_anchor_mismatch_count": max(
            0,
            artifact_anchor_required_count - artifact_anchor_verified_count,
        ),
        "artifact_anchor_verified_pct": artifact_anchor_verified_pct,
        "artifact_anchor_campaign_coverage_pct": artifact_anchor_campaign_coverage_pct,
        "artifact_anchor_deep_verified": bool(
            artifact_hash_required
            and deep
            and replay_summary_required
            and artifact_anchor_verified_count == artifact_anchor_required_count
        ),
        "comparison_status_counts": comparison_status_counts,
        "comparison_review_required_count": comparison_review_required_count,
        "source_equivalence_claim_allowed_count": source_equivalence_claim_allowed_count,
        "comparison_review_samples": comparison_review_samples,
        "issue_count": issue_count,
        "issue_code_counts": issue_code_counts,
        "missing_trade_field_counts": missing_trade_field_counts,
        "missing_buy_field_counts": missing_buy_field_counts,
        "issue_records": issue_records,
        "ledger_evidence_hash": ledger_evidence_hash,
        "journal_evidence_hash": journal_evidence_hash,
        "replay_evidence_hash": replay_evidence_hash,
        "audited_source_ids": audited_source_ids,
        "audited_scope_hash": audited_scope_hash,
        "evidence_bundle_hash_contract": EVIDENCE_BUNDLE_HASH_CONTRACT,
        "evidence_bundle_hash": evidence_bundle_hash,
        "paper_only": True,
        "live_order_allowed": False,
    }


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _us_regulatory_cost_from_policy(
    cost_policy: dict[str, Any],
    *,
    trade_date: str,
    quantity: float,
    gross_krw: float,
    usdkrw_rate: float,
) -> tuple[float, float]:
    """Recalculate SEC/FINRA costs from the immutable policy snapshot."""
    sec_rows = cost_policy.get("us_sec_fee_schedule")
    taf_rows = cost_policy.get("us_finra_taf_schedule")
    if not isinstance(sec_rows, list) or not sec_rows:
        return 0.0, 0.0
    if not isinstance(taf_rows, list) or not taf_rows:
        return 0.0, 0.0
    normalized_date = str(trade_date or "")[:10]
    sec_row = sec_rows[0] if isinstance(sec_rows[0], dict) else {}
    for row in sec_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("effective_from") or "") <= normalized_date:
            sec_row = row
        else:
            break
    taf_row = taf_rows[0] if isinstance(taf_rows[0], dict) else {}
    for row in taf_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("effective_from") or "") <= normalized_date:
            taf_row = row
        else:
            break
    sec_fee = max(0.0, gross_krw) * _number(sec_row.get("fee_bps")) / 10_000.0
    taf_usd = min(
        max(0.0, quantity) * _number(taf_row.get("per_share_usd")),
        _number(taf_row.get("max_per_trade_usd")),
    )
    return sec_fee, taf_usd * max(0.0, usdkrw_rate)


def _replay_data_bundle_slice_manifest_hash(evidence: dict[str, Any]) -> str:
    fields = (
        "schema",
        "bundle_content_hash",
        "slice_content_hash",
        "bundle_period",
        "requested_period",
        "symbols",
        "symbol_count",
        "symbol_row_counts",
        "symbol_row_bounds",
        "symbol_calendar_adjacency_roots",
        "symbol_calendar_pair_counts",
        "fx_row_count",
        "excluded_before_row_count",
        "excluded_future_row_count",
        "future_rows_excluded_before_strategy",
        "no_rows_outside_requested_period",
        "source_fetch_reused",
        "live_order_allowed",
    )
    payload = {field: evidence.get(field) for field in fields}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _audit_replay_data_contract(
    replay: dict[str, Any],
    *,
    ledger: dict[str, Any] | None = None,
    actions: list[Any] | None = None,
    require_immutable_data_bundle: bool = False,
    required_execution_timing_model_version: str | None = None,
) -> list[tuple[str, str]]:
    """Independently reject simulated, incomplete, or unit-inconsistent replay inputs."""
    issues: list[tuple[str, str]] = []
    if str(replay.get("data_mode") or "") != "real":
        issues.append(("replay_data_mode_not_real", str(replay.get("data_mode") or "missing")))
    data_errors = replay.get("data_errors")
    if not isinstance(data_errors, list) or data_errors:
        issues.append(("replay_data_errors_present", str(data_errors or "invalid")))
    timing_model = replay.get("execution_timing_model")
    if not isinstance(timing_model, dict):
        issues.append(("execution_timing_model_missing", "execution_timing_model"))
    elif (
        timing_model.get("lookahead_safe_required") is not True
        or timing_model.get("same_bar_signal_execution_allowed") is not False
        or _integer(timing_model.get("minimum_signal_lag_bars")) < 1
        or str(timing_model.get("decision_basis") or "") != "completed_prior_daily_bar"
        or str(timing_model.get("execution_basis") or "") not in {"next_available_open", "next_available_close"}
    ):
        issues.append(("execution_timing_model_invalid", json.dumps(timing_model, sort_keys=True)))
    elif required_execution_timing_model_version:
        if str(timing_model.get("version") or "") != required_execution_timing_model_version:
            issues.append(
                (
                    "execution_timing_model_version_mismatch",
                    (
                        f"actual={timing_model.get('version') or 'missing'},"
                        f"required={required_execution_timing_model_version}"
                    ),
                )
            )
        if (
            timing_model.get("execution_bar_excluded_from_decision") is not True
            or timing_model.get("symbol_calendar_alignment_required") is not True
            or str(timing_model.get("missing_execution_bar_policy") or "")
            != "skip_until_next_available_symbol_bar"
        ):
            issues.append(
                (
                    "execution_timing_symbol_calendar_contract_invalid",
                    json.dumps(timing_model, sort_keys=True),
                )
            )
        if (
            str(required_execution_timing_model_version).endswith(".v3")
            and str(timing_model.get("calendar_adjacency_proof_contract") or "")
            != CALENDAR_ADJACENCY_PROOF_CONTRACT
        ):
            issues.append(
                (
                    "execution_timing_calendar_proof_contract_invalid",
                    str(timing_model.get("calendar_adjacency_proof_contract") or "missing"),
                )
            )
    if require_immutable_data_bundle:
        require_calendar_proof = str(
            required_execution_timing_model_version or ""
        ).endswith(".v3")
        evidence = replay.get("replay_data_bundle_evidence")
        if not isinstance(evidence, dict):
            issues.append(
                ("replay_data_bundle_evidence_missing", "replay_data_bundle_evidence")
            )
            evidence = {}
        bundle_hash = str(evidence.get("bundle_content_hash") or "")
        slice_hash = str(evidence.get("slice_content_hash") or "")
        if (
            evidence.get("schema")
            != (
                "codexstock_replay_data_bundle_slice_evidence_v3"
                if require_calendar_proof
                else "codexstock_replay_data_bundle_slice_evidence_v2"
            )
            or evidence.get("used") is not True
            or evidence.get("passed") is not True
            or evidence.get("source_fetch_reused") is not True
            or evidence.get("live_order_allowed") is not False
        ):
            issues.append(
                (
                    "replay_data_bundle_evidence_invalid",
                    str(evidence.get("schema") or "missing"),
                )
            )
        hash_pattern = r"sha256:[0-9a-f]{64}"
        if not re.fullmatch(hash_pattern, bundle_hash) or not re.fullmatch(
            hash_pattern, slice_hash
        ):
            issues.append(
                (
                    "replay_data_bundle_hash_invalid",
                    f"bundle={bundle_hash or 'missing'},slice={slice_hash or 'missing'}",
                )
            )
        requested_period = (
            evidence.get("requested_period")
            if isinstance(evidence.get("requested_period"), dict)
            else {}
        )
        expected_period = {
            "start_date": str(replay.get("start_date") or ""),
            "end_date": str(replay.get("end_date") or ""),
        }
        if requested_period != expected_period:
            issues.append(
                (
                    "replay_data_bundle_period_mismatch",
                    f"expected={expected_period},actual={requested_period}",
                )
            )
        bundle_period = (
            evidence.get("bundle_period")
            if isinstance(evidence.get("bundle_period"), dict)
            else {}
        )
        if (
            not str(bundle_period.get("start_date") or "")
            or not str(bundle_period.get("end_date") or "")
            or str(bundle_period.get("start_date")) > expected_period["start_date"]
            or str(bundle_period.get("end_date")) < expected_period["end_date"]
        ):
            issues.append(
                ("replay_data_bundle_coverage_invalid", str(bundle_period or "missing"))
            )
        replay_symbols = {
            str(value or "").strip().upper()
            for value in (
                replay.get("symbols") if isinstance(replay.get("symbols"), list) else []
            )
            if str(value or "").strip()
        }
        evidence_symbols = {
            str(value or "").strip().upper()
            for value in (
                evidence.get("symbols")
                if isinstance(evidence.get("symbols"), list)
                else []
            )
            if str(value or "").strip()
        }
        row_counts = (
            evidence.get("symbol_row_counts")
            if isinstance(evidence.get("symbol_row_counts"), dict)
            else {}
        )
        row_bounds = (
            evidence.get("symbol_row_bounds")
            if isinstance(evidence.get("symbol_row_bounds"), dict)
            else {}
        )
        calendar_roots = (
            evidence.get("symbol_calendar_adjacency_roots")
            if isinstance(evidence.get("symbol_calendar_adjacency_roots"), dict)
            else {}
        )
        calendar_pair_counts = (
            evidence.get("symbol_calendar_pair_counts")
            if isinstance(evidence.get("symbol_calendar_pair_counts"), dict)
            else {}
        )
        normalized_count_symbols = {
            str(value or "").strip().upper() for value in row_counts
        }
        normalized_bound_symbols = {
            str(value or "").strip().upper() for value in row_bounds
        }
        normalized_calendar_root_symbols = {
            str(value or "").strip().upper() for value in calendar_roots
        }
        normalized_calendar_count_symbols = {
            str(value or "").strip().upper() for value in calendar_pair_counts
        }
        if (
            evidence_symbols != replay_symbols
            or normalized_count_symbols != replay_symbols
            or normalized_bound_symbols != replay_symbols
            or _integer(evidence.get("symbol_count")) != len(replay_symbols)
            or (
                require_calendar_proof
                and (
                    normalized_calendar_root_symbols != replay_symbols
                    or normalized_calendar_count_symbols != replay_symbols
                )
            )
        ):
            issues.append(
                (
                    "replay_data_bundle_symbol_coverage_invalid",
                    (
                        f"replay={sorted(replay_symbols)},"
                        f"evidence={sorted(evidence_symbols)},"
                        f"counts={sorted(normalized_count_symbols)},"
                        f"bounds={sorted(normalized_bound_symbols)}"
                    ),
                )
            )
        for symbol in sorted(replay_symbols):
            count = _integer(row_counts.get(symbol))
            bounds = row_bounds.get(symbol)
            if not isinstance(bounds, dict):
                issues.append(("replay_data_bundle_row_bounds_invalid", f"{symbol}:missing"))
                continue
            first_day = _iso_date(bounds.get("first_date"))
            last_day = _iso_date(bounds.get("last_date"))
            declared_bound_count = _integer(bounds.get("row_count"))
            start_day = _iso_date(expected_period["start_date"])
            end_day = _iso_date(expected_period["end_date"])
            if (
                count <= 0
                or count != declared_bound_count
                or first_day is None
                or last_day is None
                or start_day is None
                or end_day is None
                or first_day > last_day
                or first_day < start_day
                or last_day > end_day
            ):
                issues.append(
                    (
                        "replay_data_bundle_row_bounds_invalid",
                        f"{symbol}:count={count},bounds={bounds}",
                    )
                )
            if require_calendar_proof:
                root = str(calendar_roots.get(symbol) or "")
                pair_count = _integer(calendar_pair_counts.get(symbol))
                if (
                    re.fullmatch(r"[0-9a-f]{64}", root) is None
                    or pair_count != max(0, count - 1)
                ):
                    issues.append(
                        (
                            "replay_symbol_calendar_root_invalid",
                            f"{symbol}:pairs={pair_count},rows={count}",
                        )
                    )
        if (
            evidence.get("future_rows_excluded_before_strategy") is not True
            or evidence.get("no_rows_outside_requested_period") is not True
            or _integer(evidence.get("excluded_future_row_count")) < 0
            or _integer(evidence.get("excluded_before_row_count")) < 0
        ):
            issues.append(
                (
                    "replay_data_bundle_future_exclusion_invalid",
                    "future_or_outside_period_guard_not_proven",
                )
            )
        expected_manifest_hash = _replay_data_bundle_slice_manifest_hash(evidence)
        if str(evidence.get("slice_manifest_hash") or "") != expected_manifest_hash:
            issues.append(
                (
                    "replay_data_bundle_manifest_hash_mismatch",
                    str(evidence.get("slice_manifest_hash") or "missing"),
                )
            )
        ledger = ledger if isinstance(ledger, dict) else {}
        if (
            str(ledger.get("replay_data_bundle_evidence_schema") or "")
            != str(evidence.get("schema") or "")
            or str(ledger.get("replay_data_bundle_hash") or "") != bundle_hash
            or str(ledger.get("replay_data_slice_hash") or "") != slice_hash
        ):
            issues.append(
                (
                    "replay_data_bundle_ledger_binding_mismatch",
                    f"ledger={ledger.get('replay_data_bundle_hash') or 'missing'}",
                )
            )
        for index, action in enumerate(actions or []):
            if not isinstance(action, dict) or str(action.get("side") or "").upper() not in {
                "BUY",
                "SELL",
            }:
                continue
            action_hash = str(action.get("market_data_snapshot_hash") or "")
            if not action_hash:
                issues.append(
                    ("journal_market_data_snapshot_hash_missing", f"index={index}")
                )
            elif action_hash != slice_hash:
                issues.append(
                    (
                        "journal_market_data_snapshot_hash_mismatch",
                        f"index={index},actual={action_hash}",
                    )
                )
            if require_calendar_proof:
                symbol = str(action.get("symbol") or "").strip().upper()
                expected_root = str(calendar_roots.get(symbol) or "")
                if not verify_calendar_adjacency_proof(
                    action,
                    expected_symbol=symbol,
                    expected_root=expected_root,
                ):
                    issues.append(
                        (
                            "journal_symbol_calendar_binding_invalid",
                            f"index={index},symbol={symbol or 'missing'}",
                        )
                    )
    audit = replay.get("price_currency_unit_audit")
    if not isinstance(audit, dict):
        return issues + [("price_currency_unit_audit_missing", "price_currency_unit_audit")]
    if audit.get("passed") is not True or audit.get("blockers"):
        issues.append(("price_currency_unit_audit_not_passed", str(audit.get("blockers") or "passed=false")))
    if audit.get("base_currency") != "KRW":
        issues.append(("price_audit_base_currency_invalid", str(audit.get("base_currency") or "missing")))
    contracts = audit.get("contracts") if isinstance(audit.get("contracts"), dict) else {}
    symbols = {
        str(value or "").strip().upper()
        for value in (replay.get("symbols") if isinstance(replay.get("symbols"), list) else [])
        if str(value or "").strip()
    }
    contract_symbols = {str(value or "").strip().upper() for value in contracts}
    if not contracts or contract_symbols != symbols:
        issues.append(("price_contract_coverage_incomplete", f"symbols={len(symbols)},contracts={len(contracts)}"))
    declared_count = _integer(audit.get("symbol_count"))
    passed_count = _integer(audit.get("passed_symbol_count"))
    actual_passed = sum(
        1
        for contract in contracts.values()
        if isinstance(contract, dict) and contract.get("passed") is True and not contract.get("blockers")
    )
    if declared_count != len(contracts) or passed_count != actual_passed:
        issues.append(("price_contract_count_mismatch", f"declared={declared_count}/{passed_count},actual={len(contracts)}/{actual_passed}"))
    for symbol, contract in contracts.items():
        if not isinstance(contract, dict):
            issues.append(("price_contract_invalid", str(symbol)))
            continue
        contract_symbol = str(contract.get("symbol") or "").strip().upper()
        if contract_symbol != str(symbol).strip().upper():
            issues.append(
                ("price_contract_symbol_identity_mismatch", f"key={symbol},value={contract_symbol or 'missing'}")
            )
        blockers = contract.get("blockers")
        if contract.get("passed") is not True or blockers:
            issues.append(("price_contract_not_passed", f"{symbol}:{blockers or 'passed=false'}"))
        if contract.get("base_currency") != "KRW" or contract.get("quote_unit") != "KRW_per_share":
            issues.append(("price_contract_unit_invalid", str(symbol)))
        if contract.get("corporate_action_adjusted") is not True or contract.get("price_basis") != "adjusted_close":
            issues.append(("price_contract_adjustment_invalid", str(symbol)))
        if contract.get("currency_normalized") is not True:
            issues.append(("price_contract_currency_not_normalized", str(symbol)))
        if not str(contract.get("provider") or "").strip():
            issues.append(("price_contract_provider_missing", str(symbol)))
        if contract.get("partial_fx_conversion_blocked") is not False:
            issues.append(("price_contract_partial_fx_state_invalid", str(symbol)))
        adjusted_coverage = _finite_number(contract.get("adjusted_close_coverage_pct"))
        fx_coverage = _finite_number(contract.get("fx_coverage_pct"))
        if adjusted_coverage is None or not 95.0 <= adjusted_coverage <= 100.0:
            issues.append(("price_contract_adjusted_coverage_low", f"{symbol}:{adjusted_coverage}"))
        if fx_coverage is None or not 95.0 <= fx_coverage <= 100.0:
            issues.append(("price_contract_fx_coverage_low", f"{symbol}:{fx_coverage}"))
        market = str(contract.get("market") or "")
        if market == "KR":
            if contract.get("source_currency") != "KRW" or contract.get("fx_conversion_applied") is not False:
                issues.append(("price_contract_kr_currency_invalid", str(symbol)))
        elif market == "US":
            if (
                contract.get("source_currency") != "USD"
                or contract.get("fx_conversion_applied") is not True
                or contract.get("fx_pair") != "USD/KRW"
                or not str(contract.get("fx_source") or "").strip()
            ):
                issues.append(("price_contract_us_fx_invalid", str(symbol)))
        else:
            issues.append(("price_contract_market_invalid", f"{symbol}:{market or 'missing'}"))
    return issues


def _audit_replay_summary(
    *,
    ledger: dict[str, Any],
    replay: dict[str, Any],
    actions: list[Any],
    cost_policy: dict[str, Any],
    action_count: int,
    closed_count: int,
    open_position_count: int,
    action_cost_evidence: dict[str, float],
    action_date_bounds: tuple[date | None, date | None],
    action_symbols: set[str],
    closed_returns: list[float],
    open_position_evidence: dict[str, dict[str, Any]],
) -> list[tuple[str, str]]:
    """Independently reconcile portfolio-level return, costs, and bounded MDD evidence."""
    issues: list[tuple[str, str]] = []
    numeric_fields = (
        "initial_cash",
        "final_equity",
        "total_return_pct",
        "max_drawdown_pct",
        "total_commission",
        "total_slippage_cost",
        "total_sell_tax",
        "total_turnover",
        "total_transaction_cost",
        "transaction_cost_pct_of_initial_cash",
        "win_rate_pct",
        "average_win_pct",
        "average_loss_pct",
    )
    numbers = {field: _finite_number(replay.get(field)) for field in numeric_fields}
    invalid = sorted(field for field, value in numbers.items() if value is None)
    if invalid:
        return [("replay_summary_numeric_invalid", ",".join(invalid))]
    optional_costs = {
        field: _finite_number(replay.get(field)) or 0.0
        for field in (
            "total_us_sec_fee",
            "total_us_finra_taf",
            "total_fx_conversion_cost",
        )
    }
    initial_cash = numbers["initial_cash"]
    final_equity = numbers["final_equity"]
    if initial_cash <= 0 or final_equity < 0:
        issues.append(("replay_equity_nonpositive", "initial_cash_or_final_equity"))
        return issues
    if not -100.0 <= numbers["max_drawdown_pct"] <= 0.0:
        issues.append(("replay_mdd_range_invalid", "expected_-100_to_0"))
    replay_symbols = {
        str(value or "").strip().upper()
        for value in (replay.get("symbols") if isinstance(replay.get("symbols"), list) else [])
        if str(value or "").strip()
    }
    outside_symbols = sorted(action_symbols - replay_symbols)
    if outside_symbols:
        issues.append(
            ("journal_symbol_outside_replay_universe", ",".join(outside_symbols))
        )

    wins = [value for value in closed_returns if value > 0]
    losses = [value for value in closed_returns if value <= 0]
    expected_trade_stats = {
        "replay_win_rate_mismatch": (
            numbers["win_rate_pct"],
            round((len(wins) / len(closed_returns)) * 100.0, 2) if closed_returns else 0.0,
        ),
        "replay_average_win_mismatch": (
            numbers["average_win_pct"],
            rounded_financial_mean_pct(wins),
        ),
        "replay_average_loss_mismatch": (
            numbers["average_loss_pct"],
            rounded_financial_mean_pct(losses),
        ),
    }
    for code, (recorded, expected) in expected_trade_stats.items():
        if abs(recorded - expected) > 0.001:
            issues.append((code, f"recorded={recorded},trades={expected}"))

    computed_return = ((final_equity / initial_cash) - 1.0) * 100.0
    if abs(computed_return - numbers["total_return_pct"]) > NUMERIC_RECONCILIATION_TOLERANCE:
        issues.append(("replay_total_return_mismatch", "initial_to_final_equity"))
    ledger_return = _finite_number(ledger.get("new_total_return_pct"))
    if ledger_return is None or (
        abs(ledger_return - numbers["total_return_pct"]) > NUMERIC_RECONCILIATION_TOLERANCE
    ):
        issues.append(("ledger_total_return_mismatch", "new_total_return_pct"))

    component_cost = (
        numbers["total_commission"]
        + numbers["total_slippage_cost"]
        + numbers["total_sell_tax"]
        + optional_costs["total_us_sec_fee"]
        + optional_costs["total_us_finra_taf"]
        + optional_costs["total_fx_conversion_cost"]
    )
    if abs(component_cost - numbers["total_transaction_cost"]) > NUMERIC_RECONCILIATION_TOLERANCE:
        issues.append(("replay_total_cost_mismatch", "cost_components"))
    computed_cost_pct = (numbers["total_transaction_cost"] / initial_cash) * 100.0
    if abs(computed_cost_pct - numbers["transaction_cost_pct_of_initial_cash"]) > 0.00011:
        issues.append(("replay_cost_pct_mismatch", "transaction_cost_pct_of_initial_cash"))

    action_cost_checks = {
        "replay_commission_action_sum_mismatch": (
            numbers["total_commission"],
            action_cost_evidence["commission"],
            action_cost_evidence["commission_tolerance"],
        ),
        "replay_sell_tax_action_sum_mismatch": (
            numbers["total_sell_tax"],
            action_cost_evidence["sell_tax"],
            action_cost_evidence["sell_tax_tolerance"],
        ),
        "replay_slippage_action_sum_mismatch": (
            numbers["total_slippage_cost"],
            action_cost_evidence["slippage"],
            action_cost_evidence["slippage_tolerance"],
        ),
        "replay_us_sec_fee_action_sum_mismatch": (
            optional_costs["total_us_sec_fee"],
            action_cost_evidence["us_sec_fee"],
            action_cost_evidence["us_regulatory_tolerance"],
        ),
        "replay_us_finra_taf_action_sum_mismatch": (
            optional_costs["total_us_finra_taf"],
            action_cost_evidence["us_finra_taf"],
            action_cost_evidence["us_regulatory_tolerance"],
        ),
        "replay_fx_conversion_action_sum_mismatch": (
            optional_costs["total_fx_conversion_cost"],
            action_cost_evidence["fx_conversion_cost"],
            action_cost_evidence["fx_conversion_tolerance"],
        ),
        "replay_turnover_action_sum_mismatch": (
            numbers["total_turnover"],
            action_cost_evidence["turnover"],
            action_cost_evidence["turnover_tolerance"],
        ),
    }
    for code, (recorded, calculated, tolerance) in action_cost_checks.items():
        if abs(recorded - calculated) > tolerance:
            issues.append(
                (code, f"recorded={recorded},actions={calculated},tolerance={tolerance}")
            )

    equity_curve = replay.get("equity_curve")
    dates = replay.get("dates")
    if not isinstance(equity_curve, list) or not equity_curve:
        issues.append(("replay_equity_curve_missing", "equity_curve"))
    else:
        curve = [_finite_number(value) for value in equity_curve]
        if any(value is None or value < 0 for value in curve):
            issues.append(("replay_equity_curve_invalid", "nonfinite_or_negative"))
        else:
            if abs(curve[0] - initial_cash) > NUMERIC_RECONCILIATION_TOLERANCE:
                issues.append(("replay_initial_equity_mismatch", "equity_curve_first"))
            if abs(curve[-1] - final_equity) > NUMERIC_RECONCILIATION_TOLERANCE:
                issues.append(("replay_final_equity_mismatch", "equity_curve_last"))
            peak = curve[0]
            sampled_mdd = 0.0
            for value in curve:
                peak = max(peak, value)
                if peak > 0:
                    sampled_mdd = min(sampled_mdd, ((value / peak) - 1.0) * 100.0)
            # The persisted curve is sampled. The full-run MDD may be more severe,
            # but it must never hide a drawdown already visible in the sample.
            if numbers["max_drawdown_pct"] > sampled_mdd + NUMERIC_RECONCILIATION_TOLERANCE:
                issues.append(("replay_mdd_understates_sample", "max_drawdown_pct"))
    if not isinstance(dates, list) or not isinstance(equity_curve, list) or len(dates) != len(equity_curve):
        issues.append(("replay_curve_date_length_mismatch", "dates_vs_equity_curve"))
        parsed_dates: list[date | None] = []
    elif dates:
        parsed_dates = [_iso_date(value) for value in dates]
        if any(value is None for value in parsed_dates):
            issues.append(("replay_curve_date_invalid", "non_iso_date"))
        elif any(
            current <= previous
            for previous, current in zip(parsed_dates, parsed_dates[1:])
        ):
            issues.append(("replay_curve_date_order_invalid", "dates_not_strictly_increasing"))
    else:
        parsed_dates = []

    start_day = _iso_date(replay.get("start_date"))
    end_day = _iso_date(replay.get("end_date"))
    if start_day is None or end_day is None or end_day < start_day:
        issues.append(("replay_period_invalid", "start_date_or_end_date"))
    else:
        valid_curve_dates = [value for value in parsed_dates if value is not None]
        if valid_curve_dates and (
            valid_curve_dates[0] < start_day or valid_curve_dates[-1] > end_day
        ):
            issues.append(("replay_curve_outside_period", "dates_vs_start_end"))
        first_action_day, last_action_day = action_date_bounds
        if (
            first_action_day is not None
            and last_action_day is not None
            and (first_action_day < start_day or last_action_day > end_day)
        ):
            issues.append(
                ("journal_action_outside_replay_period", "action_dates_vs_start_end")
            )

    monthly_equity = replay.get("monthly_equity")
    if not isinstance(monthly_equity, list) or not monthly_equity:
        issues.append(("replay_monthly_equity_missing", "monthly_equity"))
    else:
        month_values: list[str] = []
        monthly_shape_invalid = False
        monthly_month_invalid = False
        monthly_equity_invalid = False
        for row in monthly_equity:
            if not isinstance(row, dict):
                monthly_shape_invalid = True
                continue
            month = str(row.get("month") or "")
            if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month):
                monthly_month_invalid = True
            else:
                month_values.append(month)
            equity = _finite_number(row.get("equity"))
            if equity is None or equity < 0:
                monthly_equity_invalid = True
        if monthly_shape_invalid:
            issues.append(("replay_monthly_row_invalid", "non_object_row"))
        if monthly_month_invalid:
            issues.append(("replay_monthly_month_invalid", "expected_yyyy_mm"))
        if monthly_equity_invalid:
            issues.append(("replay_monthly_equity_invalid", "nonfinite_or_negative"))
        if len(month_values) >= 2 and any(
            current <= previous
            for previous, current in zip(month_values, month_values[1:])
        ):
            issues.append(("replay_monthly_order_invalid", "months_not_strictly_increasing"))
        monthly_last = _finite_number(
            monthly_equity[-1].get("equity")
            if isinstance(monthly_equity[-1], dict)
            else None
        )
        if monthly_last is None or abs(monthly_last - final_equity) > NUMERIC_RECONCILIATION_TOLERANCE:
            issues.append(("replay_monthly_final_mismatch", "monthly_equity_last"))

    count_checks = {
        "replay_closed_count_mismatch": (_integer(replay.get("closed_trade_count")), closed_count),
        "replay_trade_count_mismatch": (_integer(replay.get("trade_count")), action_count),
        "replay_action_count_mismatch": (_integer(replay.get("trade_action_count")), action_count),
    }
    for code, (recorded, actual) in count_checks.items():
        if recorded != actual:
            issues.append((code, f"recorded={recorded},actual={actual}"))
    reconciliation_summary = replay.get("trade_journal_reconciliation_summary")
    if not isinstance(reconciliation_summary, dict):
        issues.append(("replay_reconciliation_summary_missing", "trade_journal_reconciliation_summary"))
    else:
        expected_reconciliation_counts = {
            "checked_count": closed_count,
            "ok_count": closed_count,
            "warning_count": 0,
            "blocker_count": 0,
            "official_return_blocker_count": 0,
            "needs_review": 0,
        }
        mismatched_reconciliation = {
            field: {
                "recorded": _integer(reconciliation_summary.get(field)),
                "expected": expected,
            }
            for field, expected in expected_reconciliation_counts.items()
            if _integer(reconciliation_summary.get(field)) != expected
        }
        if mismatched_reconciliation:
            issues.append(
                (
                    "replay_reconciliation_summary_mismatch",
                    json.dumps(mismatched_reconciliation, sort_keys=True),
                )
            )
        if not str(reconciliation_summary.get("reconciliation_engine_version") or "").strip():
            issues.append(("replay_reconciliation_engine_missing", "reconciliation_engine_version"))
    open_positions = replay.get("open_positions")
    if not isinstance(open_positions, list) or len(open_positions) != open_position_count:
        issues.append(("replay_open_position_count_mismatch", "open_positions"))
    elif isinstance(open_positions, list):
        replay_open_by_symbol: dict[str, dict[str, Any]] = {}
        invalid_rows = False
        duplicate_symbols = False
        for position in open_positions:
            if not isinstance(position, dict):
                invalid_rows = True
                continue
            symbol = str(position.get("symbol") or "").strip().upper()
            if not symbol:
                invalid_rows = True
                continue
            if symbol in replay_open_by_symbol:
                duplicate_symbols = True
            replay_open_by_symbol[symbol] = position
        if invalid_rows:
            issues.append(("replay_open_position_row_invalid", "missing_or_non_object"))
        if duplicate_symbols:
            issues.append(("replay_open_position_duplicate_symbol", "duplicate_symbol"))
        if set(replay_open_by_symbol) != set(open_position_evidence):
            issues.append(("replay_open_position_symbol_mismatch", "journal_vs_replay"))
        for symbol in sorted(set(replay_open_by_symbol) & set(open_position_evidence)):
            position = replay_open_by_symbol[symbol]
            buy = open_position_evidence[symbol]
            quantity = _finite_number(position.get("quantity"))
            avg_cost = _finite_number(position.get("avg_cost"))
            last_price = _finite_number(position.get("last_price"))
            unrealized = _finite_number(position.get("unrealized_pct"))
            buy_quantity = _finite_number(buy.get("quantity"))
            buy_price = _finite_number(buy.get("price"))
            if any(
                value is None or value <= 0
                for value in (quantity, avg_cost, last_price, buy_quantity, buy_price)
            ) or unrealized is None:
                issues.append(("replay_open_position_numeric_invalid", symbol))
                continue
            if abs(quantity - buy_quantity) > 1e-9:
                issues.append(("replay_open_position_quantity_mismatch", symbol))
            if abs(avg_cost - buy_price) > NUMERIC_RECONCILIATION_TOLERANCE:
                issues.append(("replay_open_position_avg_cost_mismatch", symbol))
            expected_unrealized = round(((last_price / avg_cost) - 1.0) * 100.0, 2)
            if abs(unrealized - expected_unrealized) > 0.011:
                issues.append(("replay_open_position_return_mismatch", symbol))

    cash = initial_cash
    minimum_cash = initial_cash
    cash_ledger_valid = True
    for action in actions:
        if not isinstance(action, dict):
            cash_ledger_valid = False
            continue
        side = str(action.get("side") or "").upper()
        field = "cash_cost" if side == "BUY" else "net_proceeds" if side == "SELL" else ""
        amount = _finite_number(action.get(field)) if field else None
        if amount is None or amount < 0:
            cash_ledger_valid = False
            continue
        cash += -amount if side == "BUY" else amount
        minimum_cash = min(minimum_cash, cash)
    cash_rounding_tolerance = action_count * 0.005 + NUMERIC_RECONCILIATION_TOLERANCE
    if cash_ledger_valid and minimum_cash < -cash_rounding_tolerance:
        issues.append(("replay_cash_balance_negative", f"minimum_cash={minimum_cash}"))

    experience_log = replay.get("experience_log")
    if not isinstance(experience_log, list) or not experience_log:
        issues.append(("replay_experience_log_missing", "experience_log"))
    else:
        actions_by_date: dict[str, list[dict[str, Any]]] = {}
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_date = str(action.get("date") or "")
            actions_by_date.setdefault(action_date, []).append(action)
        replay_cash_by_date: dict[str, tuple[float, int, int]] = {}
        replay_cash = initial_cash
        applied_action_count = 0
        replay_position_symbols: set[str] = set()
        experience_date_strings = {
            str(row.get("date") or "")
            for row in experience_log
            if isinstance(row, dict)
        }
        for day in sorted(set(actions_by_date) | experience_date_strings):
            for action in actions_by_date.get(day, []):
                side = str(action.get("side") or "").upper()
                symbol = str(action.get("symbol") or "").strip().upper()
                field = "cash_cost" if side == "BUY" else "net_proceeds" if side == "SELL" else ""
                amount = _finite_number(action.get(field)) if field else None
                if amount is not None and amount >= 0:
                    replay_cash += -amount if side == "BUY" else amount
                    applied_action_count += 1
                if side == "BUY" and symbol:
                    replay_position_symbols.add(symbol)
                elif side == "SELL" and symbol:
                    replay_position_symbols.discard(symbol)
            replay_cash_by_date[day] = (
                replay_cash,
                applied_action_count,
                len(replay_position_symbols),
            )

        previous_experience_day: date | None = None
        for index, experience in enumerate(experience_log):
            if not isinstance(experience, dict):
                issues.append(("replay_experience_row_invalid", f"index={index}"))
                continue
            experience_day = _iso_date(experience.get("date"))
            if experience_day is None:
                issues.append(("replay_experience_date_invalid", f"index={index}"))
            elif previous_experience_day is not None and experience_day <= previous_experience_day:
                issues.append(("replay_experience_date_order_invalid", f"index={index}"))
            if experience_day is not None:
                previous_experience_day = experience_day
            day_key = str(experience.get("date") or "")
            expected_cash, applied_count, expected_position_count = replay_cash_by_date.get(
                day_key,
                (float("nan"), 0, 0),
            )
            recorded_day_cash = _finite_number(experience.get("cash"))
            recorded_day_equity = _finite_number(experience.get("equity"))
            recorded_position_count = _finite_number(experience.get("positions"))
            if (
                recorded_day_cash is None
                or recorded_day_cash < 0
                or recorded_day_equity is None
                or recorded_day_equity < 0
                or recorded_position_count is None
                or recorded_position_count < 0
                or not float(recorded_position_count).is_integer()
            ):
                issues.append(("replay_experience_numeric_invalid", f"index={index}"))
            elif math.isfinite(expected_cash):
                day_tolerance = applied_count * 0.005 + NUMERIC_RECONCILIATION_TOLERANCE
                if abs(recorded_day_cash - expected_cash) > day_tolerance:
                    issues.append(
                        (
                            "replay_experience_cash_mismatch",
                            f"date={day_key},recorded={recorded_day_cash},actions={expected_cash}",
                        )
                    )
                if int(recorded_position_count) != expected_position_count:
                    issues.append(
                        (
                            "replay_experience_position_count_mismatch",
                            f"date={day_key},recorded={int(recorded_position_count)},actions={expected_position_count}",
                        )
                    )
            recorded_day_actions = experience.get("actions")
            if not isinstance(recorded_day_actions, list) or recorded_day_actions != actions_by_date.get(day_key, []):
                issues.append(("replay_experience_actions_mismatch", f"date={day_key}"))

        last_experience = experience_log[-1]
        if not isinstance(last_experience, dict):
            issues.append(("replay_experience_final_row_invalid", "non_object"))
        else:
            recorded_cash = _finite_number(last_experience.get("cash"))
            recorded_equity = _finite_number(last_experience.get("equity"))
            if recorded_cash is None or recorded_cash < 0 or recorded_equity is None or recorded_equity < 0:
                issues.append(("replay_experience_final_row_invalid", "cash_or_equity"))
            else:
                if cash_ledger_valid and abs(recorded_cash - cash) > cash_rounding_tolerance:
                    issues.append(
                        (
                            "replay_final_cash_mismatch",
                            f"recorded={recorded_cash},actions={cash},tolerance={cash_rounding_tolerance}",
                        )
                    )
                if abs(recorded_equity - final_equity) > NUMERIC_RECONCILIATION_TOLERANCE:
                    issues.append(
                        (
                            "replay_experience_final_equity_mismatch",
                            f"recorded={recorded_equity},summary={final_equity}",
                        )
                    )
            final_curve_date = str(dates[-1] if isinstance(dates, list) and dates else "")
            if str(last_experience.get("date") or "") != final_curve_date:
                issues.append(("replay_experience_final_date_mismatch", "experience_log_vs_curve"))

    if cash_ledger_valid and isinstance(open_positions, list):
        open_value = 0.0
        valuation_rounding_tolerance = 0.0
        valuation_valid = True
        for position in open_positions:
            if not isinstance(position, dict):
                valuation_valid = False
                continue
            quantity = _finite_number(position.get("quantity"))
            last_price = _finite_number(position.get("last_price"))
            if quantity is None or quantity <= 0 or last_price is None or last_price <= 0:
                valuation_valid = False
                continue
            commission_rate = _number(cost_policy.get("commission_bps")) / 10_000.0
            slippage_rate = _number(cost_policy.get("slippage_bps")) / 10_000.0
            sell_tax_rate = _number(cost_policy.get("kr_sell_tax_bps")) / 10_000.0
            execution_price = last_price * (1.0 - slippage_rate)
            gross_proceeds = quantity * execution_price
            commission = gross_proceeds * commission_rate
            symbol = str(position.get("symbol") or "").strip().upper()
            market = str(
                position.get("market")
                or ("KR" if re.fullmatch(r"[0-9]{6}", symbol) else "US")
            ).upper()
            sell_tax = gross_proceeds * sell_tax_rate if market == "KR" else 0.0
            market_specific_policy = str(cost_policy.get("policy_version") or "").endswith(
                "paper-costs.v2"
            )
            fx_conversion_cost = (
                gross_proceeds
                * _number(cost_policy.get("fx_conversion_spread_bps"))
                / 10_000.0
                if market_specific_policy and market == "US"
                else 0.0
            )
            us_sec_fee, us_finra_taf = (
                _us_regulatory_cost_from_policy(
                    cost_policy,
                    trade_date=str(position.get("valuation_date") or ""),
                    quantity=quantity,
                    gross_krw=gross_proceeds,
                    usdkrw_rate=_number(position.get("last_usdkrw_rate")),
                )
                if market_specific_policy and market == "US"
                else (0.0, 0.0)
            )
            open_value += (
                gross_proceeds
                - commission
                - sell_tax
                - fx_conversion_cost
                - us_sec_fee
                - us_finra_taf
            )
            valuation_rounding_tolerance += quantity * 0.000051
        if valuation_valid:
            expected_equity = cash + open_value
            tolerance = cash_rounding_tolerance + valuation_rounding_tolerance
            if abs(expected_equity - final_equity) > tolerance:
                issues.append(
                    (
                        "replay_cash_positions_equity_mismatch",
                        f"cash_plus_positions={expected_equity},summary={final_equity},tolerance={tolerance}",
                    )
                )
    return issues


def _journal_action_cost_evidence(actions: list[Any]) -> dict[str, float]:
    commission = 0.0
    sell_tax = 0.0
    us_sec_fee = 0.0
    us_finra_taf = 0.0
    fx_conversion_cost = 0.0
    slippage = 0.0
    turnover = 0.0
    quantity_sum = 0.0
    valid_action_count = 0
    sell_count = 0
    for action in actions:
        if not isinstance(action, dict):
            continue
        side = str(action.get("side") or "").upper()
        if side not in {"BUY", "SELL"}:
            continue
        valid_action_count += 1
        quantity = _finite_number(action.get("quantity"))
        market_price = _finite_number(action.get("market_price"))
        execution_price = _finite_number(action.get("execution_price"))
        action_commission = _finite_number(action.get("commission"))
        action_notional = _finite_number(action.get("notional"))
        if action_commission is not None:
            commission += action_commission
        action_fx_conversion = _finite_number(action.get("fx_conversion_cost"))
        if action_fx_conversion is not None:
            fx_conversion_cost += action_fx_conversion
        if action_notional is not None:
            turnover += action_notional
        if side == "SELL":
            sell_count += 1
            action_sell_tax = _finite_number(action.get("sell_tax"))
            if action_sell_tax is not None:
                sell_tax += action_sell_tax
            action_sec_fee = _finite_number(action.get("us_sec_fee"))
            action_taf = _finite_number(action.get("us_finra_taf"))
            if action_sec_fee is not None:
                us_sec_fee += action_sec_fee
            if action_taf is not None:
                us_finra_taf += action_taf
        if quantity is not None and market_price is not None and execution_price is not None:
            quantity_sum += quantity
            slippage += quantity * (
                execution_price - market_price
                if side == "BUY"
                else market_price - execution_price
            )
    return {
        "commission": commission,
        "sell_tax": sell_tax,
        "us_sec_fee": us_sec_fee,
        "us_finra_taf": us_finra_taf,
        "fx_conversion_cost": fx_conversion_cost,
        "slippage": slippage,
        "turnover": turnover,
        # Persisted action prices/costs are rounded; tolerances are bounded by
        # the maximum accumulated rounding error, not a percentage of cost.
        "commission_tolerance": valid_action_count * 0.005 + NUMERIC_RECONCILIATION_TOLERANCE,
        "sell_tax_tolerance": sell_count * 0.005 + NUMERIC_RECONCILIATION_TOLERANCE,
        "us_regulatory_tolerance": sell_count * 0.005 + NUMERIC_RECONCILIATION_TOLERANCE,
        "fx_conversion_tolerance": valid_action_count * 0.005 + NUMERIC_RECONCILIATION_TOLERANCE,
        "slippage_tolerance": quantity_sum * 0.000051 + NUMERIC_RECONCILIATION_TOLERANCE,
        "turnover_tolerance": valid_action_count * 0.005 + NUMERIC_RECONCILIATION_TOLERANCE,
    }


def _journal_action_date_bounds(actions: list[Any]) -> tuple[date | None, date | None]:
    days = [
        parsed
        for action in actions
        if isinstance(action, dict)
        and str(action.get("side") or "").upper() in {"BUY", "SELL"}
        and (parsed := _iso_date(action.get("date"))) is not None
    ]
    return (min(days), max(days)) if days else (None, None)


def _integer(value: object) -> int:
    return int(_number(value))


def _iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _audit_action_timing(
    action: dict[str, Any],
    *,
    require_calendar_proof: bool = False,
) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    decision_day = _iso_date(action.get("decision_data_as_of"))
    execution_day = _iso_date(action.get("execution_at"))
    action_day = _iso_date(action.get("date"))
    if decision_day is None or execution_day is None:
        issues.append(("lookahead_timing_date_invalid", "decision_or_execution_date"))
    elif decision_day >= execution_day:
        issues.append(
            (
                "lookahead_detected",
                f"decision_data_as_of={decision_day.isoformat()},execution_at={execution_day.isoformat()}",
            )
        )
    if action_day is None or execution_day is None or action_day != execution_day:
        issues.append(("execution_date_mismatch", f"action={action.get('date')},execution={action.get('execution_at')}"))

    lag = _finite_number(action.get("signal_lag_bars"))
    if lag is None or lag < 1 or abs(lag - round(lag)) > 1e-9:
        issues.append(("signal_lag_bars_invalid", str(action.get("signal_lag_bars"))))
    decision_price = _finite_number(action.get("decision_market_price"))
    if decision_price is None or decision_price <= 0:
        issues.append(("decision_market_price_invalid", str(action.get("decision_market_price"))))
    basis = str(action.get("execution_price_basis") or "").strip().lower()
    if basis not in {"next_available_open", "next_available_close", "next_available_bar"}:
        issues.append(("execution_price_basis_invalid", basis or "missing"))
    if require_calendar_proof:
        if not verify_calendar_adjacency_proof(
            action,
            expected_symbol=action.get("symbol"),
        ):
            issues.append(("symbol_calendar_adjacency_proof_invalid", "merkle_proof"))
        if str(action.get("decision_symbol_bar_date") or "") != str(
            action.get("decision_data_as_of") or ""
        ):
            issues.append(("decision_symbol_bar_date_mismatch", "decision_data_as_of"))
        if str(action.get("execution_symbol_bar_date") or "") != str(
            action.get("execution_at") or ""
        ):
            issues.append(("execution_symbol_bar_date_mismatch", "execution_at"))
    return issues


def _audit_exit_reason_threshold(
    trade: dict[str, Any],
    *,
    computed_return: float,
    computed_drawdown: float,
) -> str:
    reason = str(trade.get("reason") or "").strip()
    matches = re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%", reason)
    if not matches:
        return ""
    threshold = _number(matches[-1])
    lowered = reason.lower()
    trailing = bool(re.search(r"trailing|trail|peak\s*drawdown", lowered))
    actual = computed_drawdown if trailing else computed_return
    if trailing:
        configured = _finite_number(trade.get("trailing_trigger_pct"))
        if configured is not None:
            threshold = configured
    tolerance = max(0.25, abs(threshold) * 0.05)
    comparison_actual = round(actual, 2)
    comparison_threshold = round(threshold, 2)
    if threshold > 0 and comparison_actual < comparison_threshold - tolerance:
        return f"actual={actual:.4f},required_at_least={threshold:.4f}"
    if threshold < 0 and comparison_actual > comparison_threshold + tolerance:
        return f"actual={actual:.4f},required_at_most={threshold:.4f}"
    if threshold == 0 and abs(comparison_actual) > tolerance:
        return f"actual={actual:.4f},required_near_zero"
    return ""


def _is_whole_share_quantity(value: float, *, tolerance: float = 1e-9) -> bool:
    """Historical replay sizing uses whole shares for every supported market."""
    return abs(value - round(value)) <= tolerance

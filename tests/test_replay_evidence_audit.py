import json
import tempfile
import unittest
from pathlib import Path

from app.replay_evidence_audit import (
    REPLAY_ARTIFACT_HASH_CONTRACT,
    _replay_data_bundle_slice_manifest_hash,
    audit_regeneration_evidence,
    canonical_replay_artifact_sha256,
    classify_replay_source_comparison,
    journal_artifact_sha256,
    rounded_financial_mean_pct,
)
from app.replay_calendar_evidence import (
    CALENDAR_ADJACENCY_PROOF_CONTRACT,
    build_calendar_adjacency_proof,
    calendar_adjacency_root,
)


class ReplayEvidenceAuditTests(unittest.TestCase):
    def test_financial_mean_rounding_is_stable_at_half_cent_boundaries(self):
        self.assertEqual(-2.35, rounded_financial_mean_pct([-2.57, -0.17, -3.85, -2.79]))
        self.assertEqual(7.32, rounded_financial_mean_pct([4.14, 10.49]))

    def _ledger(self):
        return {
            "source_replay_id": "HREPLAY-1",
            "new_replay_id": "HREPLAY-2",
            "status": "verified_replacement_candidate",
            "new_trade_count": 1,
            "official_return_claim_allowed": True,
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
            "replay_data_bundle_evidence_schema": "codexstock_replay_data_bundle_slice_evidence_v2",
            "replay_data_bundle_hash": "sha256:" + "b" * 64,
            "replay_data_slice_hash": "sha256:" + "a" * 64,
            "cost_policy": {
                "current": {
                    "commission_bps": 1.5,
                    "slippage_bps": 5.0,
                    "kr_sell_tax_bps": 18.0,
                }
            },
            "reconciliation": {
                "official_return_claim_allowed": True,
                "checked_count": 1,
                "warning_count": 0,
                "blocker_count": 0,
                "official_return_blocker_count": 0,
                "needs_review": 0,
            },
        }

    def _sell(self):
        return {
            "side": "SELL",
            "symbol": "005930",
            "quantity": 1.0,
            "entry_date": "2026-01-02",
            "entry_price": 100.0,
            "entry_reason": "entry signal",
            "date": "2026-01-03",
            "decision_data_as_of": "2026-01-02",
            "execution_at": "2026-01-03",
            "signal_lag_bars": 1,
            "decision_market_price": 110.275,
            "decision_return_pct": 10.275,
            "execution_price_basis": "next_available_close",
            "market_data_snapshot_hash": "sha256:" + "a" * 64,
            "holding_days": 1,
            "price": 109.9999,
            "reason": "time exit",
            "pnl_pct": 10.0,
            "market_price": 110.275,
            "execution_price": 110.2199,
            "notional": 110.2199,
            "net_proceeds": 109.9999,
            "commission": 0.02,
            "sell_tax": 0.20,
            "peak_market_price": 111.0,
            "exit_trigger_market_price": 110.275,
            "peak_drawdown_pct": -0.6532,
        }

    def _buy(self):
        return {
            "side": "BUY",
            "symbol": "005930",
            "quantity": 1.0,
            "date": "2026-01-02",
            "decision_data_as_of": "2026-01-01",
            "execution_at": "2026-01-02",
            "signal_lag_bars": 1,
            "decision_market_price": 99.94,
            "execution_price_basis": "next_available_close",
            "market_data_snapshot_hash": "sha256:" + "a" * 64,
            "price": 100.0,
            "reason": "entry signal",
            "market_price": 99.94,
            "execution_price": 99.99,
            "notional": 99.99,
            "commission": 0.01,
            "cash_cost": 100.0,
        }

    def _replay(self):
        replay = {
            "id": "HREPLAY-2",
            "start_date": "2026-01-02",
            "end_date": "2026-01-03",
            "data_mode": "real",
            "data_errors": [],
            "replay_data_bundle_evidence": {
                "schema": "codexstock_replay_data_bundle_slice_evidence_v2",
                "used": True,
                "passed": True,
                "content_hash": "sha256:" + "b" * 64,
                "bundle_content_hash": "sha256:" + "b" * 64,
                "slice_content_hash": "sha256:" + "a" * 64,
                "bundle_period": {
                    "start_date": "2026-01-02",
                    "end_date": "2026-01-03",
                },
                "requested_period": {
                    "start_date": "2026-01-02",
                    "end_date": "2026-01-03",
                },
                "symbols": ["005930"],
                "symbol_count": 1,
                "symbol_row_counts": {"005930": 2},
                "symbol_row_bounds": {
                    "005930": {
                        "first_date": "2026-01-02",
                        "last_date": "2026-01-03",
                        "row_count": 2,
                    }
                },
                "fx_row_count": 0,
                "excluded_before_row_count": 0,
                "excluded_future_row_count": 0,
                "future_rows_excluded_before_strategy": True,
                "no_rows_outside_requested_period": True,
                "source_fetch_reused": True,
                "live_order_allowed": False,
            },
            "symbols": ["005930"],
            "price_currency_unit_audit": {
                "passed": True,
                "base_currency": "KRW",
                "symbol_count": 1,
                "passed_symbol_count": 1,
                "blockers": [],
                "contracts": {
                    "005930": {
                        "symbol": "005930",
                        "market": "KR",
                        "source_currency": "KRW",
                        "base_currency": "KRW",
                        "quote_unit": "KRW_per_share",
                        "price_basis": "adjusted_close",
                        "provider": "KIS_adjusted_verified",
                        "adjusted_close_coverage_pct": 100.0,
                        "corporate_action_adjusted": True,
                        "fx_coverage_pct": 100.0,
                        "fx_conversion_applied": False,
                        "partial_fx_conversion_blocked": False,
                        "currency_normalized": True,
                        "passed": True,
                        "blockers": [],
                    }
                },
            },
            "execution_timing_model": {
                "version": "prior-bar-signal-next-close.v1",
                "decision_basis": "completed_prior_daily_bar",
                "execution_basis": "next_available_close",
                "minimum_signal_lag_bars": 1,
                "same_bar_signal_execution_allowed": False,
                "lookahead_safe_required": True,
            },
            "initial_cash": 100.0,
            "final_equity": 110.0,
            "total_return_pct": 10.0,
            "max_drawdown_pct": 0.0,
            "total_commission": 0.03,
            "total_slippage_cost": 0.11,
            "total_sell_tax": 0.20,
            "total_turnover": 210.2099,
            "total_transaction_cost": 0.34,
            "transaction_cost_pct_of_initial_cash": 0.34,
            "win_rate_pct": 100.0,
            "average_win_pct": 10.0,
            "average_loss_pct": 0.0,
            "equity_curve": [100.0, 110.0],
            "dates": ["2026-01-02", "2026-01-03"],
            "monthly_equity": [{"month": "2026-01", "equity": 110.0}],
            "closed_trade_count": 1,
            "trade_count": 2,
            "trade_action_count": 2,
            "trade_journal_reconciliation_summary": {
                "reconciliation_engine_version": "trade-price-return-audit.v6",
                "checked_count": 1,
                "ok_count": 1,
                "warning_count": 0,
                "blocker_count": 0,
                "official_return_blocker_count": 0,
                "needs_review": 0,
                "samples": [],
            },
            "open_positions": [],
            "experience_log": [
                {
                    "date": "2026-01-03",
                    "cash": 110.0,
                    "equity": 110.0,
                    "positions": 0,
                    "actions": [self._sell()],
                },
            ],
        }
        evidence = replay["replay_data_bundle_evidence"]
        evidence["slice_manifest_hash"] = _replay_data_bundle_slice_manifest_hash(
            evidence
        )
        return replay

    def test_deep_audit_accepts_complete_verified_journal(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[self._replay()],
                deep=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(1, result["audited_journal_count"])
        self.assertEqual(1, result["audited_closed_trade_count"])
        self.assertEqual(1, result["audited_replay_summary_count"])
        self.assertEqual({}, result["missing_trade_field_counts"])
        self.assertEqual(64, len(result["ledger_evidence_hash"]))
        self.assertEqual(64, len(result["journal_evidence_hash"]))
        self.assertEqual(64, len(result["replay_evidence_hash"]))
        self.assertEqual(64, len(result["evidence_bundle_hash"]))

    def test_v3_audit_requires_symbol_calendar_safe_execution_contract(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        ledger["evidence_schema_version"] = "historical-replay-evidence.v3"
        ledger["execution_timing_model_version"] = "prior-bar-signal-next-close.v2"
        replay = self._replay()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            rejected = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
                required_evidence_schema_version="historical-replay-evidence.v3",
                required_execution_timing_model_version="prior-bar-signal-next-close.v2",
            )

            replay["execution_timing_model"].update(
                {
                    "version": "prior-bar-signal-next-close.v2",
                    "execution_bar_excluded_from_decision": True,
                    "symbol_calendar_alignment_required": True,
                    "missing_execution_bar_policy": "skip_until_next_available_symbol_bar",
                }
            )
            accepted = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
                required_evidence_schema_version="historical-replay-evidence.v3",
                required_execution_timing_model_version="prior-bar-signal-next-close.v2",
            )

        self.assertFalse(rejected["ok"])
        self.assertIn("execution_timing_model_version_mismatch", rejected["issue_code_counts"])
        self.assertIn(
            "execution_timing_symbol_calendar_contract_invalid",
            rejected["issue_code_counts"],
        )
        self.assertTrue(accepted["ok"])
        self.assertEqual(
            "prior-bar-signal-next-close.v2",
            accepted["required_execution_timing_model_version"],
        )

    def _v4_audit(self, ledger, replay, actions):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": actions}),
                encoding="utf-8",
            )
            return audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
                required_evidence_schema_version="historical-replay-evidence.v4",
                required_execution_timing_model_version="prior-bar-signal-next-close.v2",
            )

    def _v4_inputs(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        ledger["evidence_schema_version"] = "historical-replay-evidence.v4"
        ledger["execution_timing_model_version"] = "prior-bar-signal-next-close.v2"
        replay = self._replay()
        replay["execution_timing_model"].update(
            {
                "version": "prior-bar-signal-next-close.v2",
                "execution_bar_excluded_from_decision": True,
                "symbol_calendar_alignment_required": True,
                "missing_execution_bar_policy": "skip_until_next_available_symbol_bar",
            }
        )
        return ledger, replay, [self._buy(), self._sell()]

    def _v5_inputs(self):
        ledger, replay, actions = self._v4_inputs()
        journal_bytes = json.dumps({"actions": actions}).encode("utf-8")
        ledger.update(
            {
                "evidence_schema_version": "historical-replay-evidence.v5",
                "artifact_hash_contract": REPLAY_ARTIFACT_HASH_CONTRACT,
                "replay_artifact_sha256": canonical_replay_artifact_sha256(replay),
                "journal_artifact_sha256": journal_artifact_sha256(journal_bytes),
            }
        )
        return ledger, replay, actions

    def _v5_audit(self, ledger, replay, actions, *, journal_payload=None):
        payload = journal_payload or {"actions": actions}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_bytes(
                json.dumps(payload).encode("utf-8")
            )
            return audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
                required_evidence_schema_version="historical-replay-evidence.v5",
                required_execution_timing_model_version="prior-bar-signal-next-close.v2",
            )

    def test_v4_audit_accepts_immutable_bundle_and_action_lineage(self):
        ledger, replay, actions = self._v4_inputs()

        result = self._v4_audit(ledger, replay, actions)

        self.assertTrue(result["ok"], result["issue_records"])
        self.assertEqual({}, result["issue_code_counts"])

    def test_v4_audit_blocks_bundle_tampering_and_lineage_mismatch(self):
        cases = []

        ledger, replay, actions = self._v4_inputs()
        replay.pop("replay_data_bundle_evidence")
        cases.append(("missing", ledger, replay, actions, "replay_data_bundle_evidence_missing"))

        ledger, replay, actions = self._v4_inputs()
        replay["replay_data_bundle_evidence"]["requested_period"]["end_date"] = "2026-01-04"
        cases.append(("period", ledger, replay, actions, "replay_data_bundle_period_mismatch"))

        ledger, replay, actions = self._v4_inputs()
        evidence = replay["replay_data_bundle_evidence"]
        evidence["symbol_row_bounds"]["005930"]["last_date"] = "2026-01-04"
        evidence["slice_manifest_hash"] = _replay_data_bundle_slice_manifest_hash(evidence)
        cases.append(("bounds", ledger, replay, actions, "replay_data_bundle_row_bounds_invalid"))

        ledger, replay, actions = self._v4_inputs()
        replay["replay_data_bundle_evidence"]["future_rows_excluded_before_strategy"] = False
        replay["replay_data_bundle_evidence"]["slice_manifest_hash"] = (
            _replay_data_bundle_slice_manifest_hash(
                replay["replay_data_bundle_evidence"]
            )
        )
        cases.append(
            (
                "future_guard",
                ledger,
                replay,
                actions,
                "replay_data_bundle_future_exclusion_invalid",
            )
        )

        ledger, replay, actions = self._v4_inputs()
        ledger["replay_data_slice_hash"] = "sha256:" + "c" * 64
        cases.append(
            (
                "ledger_binding",
                ledger,
                replay,
                actions,
                "replay_data_bundle_ledger_binding_mismatch",
            )
        )

        ledger, replay, actions = self._v4_inputs()
        actions[0]["market_data_snapshot_hash"] = "sha256:" + "c" * 64
        cases.append(
            (
                "action_lineage",
                ledger,
                replay,
                actions,
                "journal_market_data_snapshot_hash_mismatch",
            )
        )

        for label, ledger, replay, actions, expected_issue in cases:
            with self.subTest(label=label):
                result = self._v4_audit(ledger, replay, actions)
                self.assertFalse(result["ok"])
                self.assertIn(expected_issue, result["issue_code_counts"])

    def test_v5_audit_accepts_creation_time_artifact_anchors(self):
        ledger, replay, actions = self._v5_inputs()

        result = self._v5_audit(ledger, replay, actions)

        self.assertTrue(result["ok"], result["issue_records"])
        self.assertEqual("codexstock_replay_evidence_audit_v8", result["schema"])
        self.assertEqual(
            "sha256-canonical-json-replay-evidence-bundle-v2",
            result["evidence_bundle_hash_contract"],
        )
        self.assertRegex(str(result["audited_scope_hash"]), r"^[0-9a-f]{64}$")
        self.assertEqual(1, result["artifact_anchor_required_count"])
        self.assertEqual(1, result["artifact_anchor_verified_count"])
        self.assertEqual(0, result["artifact_anchor_mismatch_count"])
        self.assertEqual(100.0, result["artifact_anchor_verified_pct"])
        self.assertEqual(100.0, result["artifact_anchor_campaign_coverage_pct"])
        self.assertTrue(result["artifact_anchor_deep_verified"])

    def test_v5_audit_blocks_replay_or_journal_tampering(self):
        ledger, replay, actions = self._v5_inputs()
        replay["tampered_note"] = "changed after creation"
        replay_result = self._v5_audit(ledger, replay, actions)

        ledger, replay, actions = self._v5_inputs()
        journal_result = self._v5_audit(
            ledger,
            replay,
            actions,
            journal_payload={
                "actions": actions,
                "tampered_note": "changed after creation",
            },
        )

        self.assertFalse(replay_result["ok"])
        self.assertEqual(0, replay_result["artifact_anchor_verified_count"])
        self.assertEqual(1, replay_result["artifact_anchor_mismatch_count"])
        self.assertIn(
            "replay_artifact_hash_mismatch",
            replay_result["issue_code_counts"],
        )
        self.assertFalse(journal_result["ok"])
        self.assertEqual(0, journal_result["artifact_anchor_verified_count"])
        self.assertEqual(1, journal_result["artifact_anchor_mismatch_count"])
        self.assertIn(
            "journal_artifact_hash_mismatch",
            journal_result["issue_code_counts"],
        )

    def test_v5_audit_rejects_missing_creation_time_artifact_hashes(self):
        ledger, replay, actions = self._v5_inputs()
        ledger.pop("journal_artifact_sha256")

        result = self._v5_audit(ledger, replay, actions)

        self.assertFalse(result["ok"])
        self.assertIn(
            "journal_artifact_hash_missing_or_invalid",
            result["issue_code_counts"],
        )

    def test_required_evidence_schema_rejects_legacy_resolved_ledger(self):
        result = audit_regeneration_evidence(
            ledger_rows=[self._ledger()],
            campaign_ids=["HREPLAY-1"],
            journal_root=Path("unused"),
            replay_rows=[self._replay()],
            deep=False,
            required_evidence_schema_version="historical-replay-evidence.v2",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(0, result["verified_count"])
        self.assertEqual(1, result["legacy_evidence_count"])
        self.assertEqual(1, result["unresolved_count"])
        self.assertEqual(1, result["issue_code_counts"]["evidence_schema_outdated"])

    def test_deep_audit_blocks_same_bar_decision_and_execution(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        buy = self._buy()
        buy["decision_data_as_of"] = buy["execution_at"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [buy, self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[self._replay()],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("lookahead_detected", result["issue_code_counts"])

    def test_deep_audit_blocks_missing_execution_timing_model(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay.pop("execution_timing_model")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("execution_timing_model_missing", result["issue_code_counts"])

    def test_deep_audit_blocks_tampered_portfolio_return_and_cost_summary(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["total_return_pct"] = 99.0
        replay["total_transaction_cost"] = 9.0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_total_return_mismatch", result["issue_code_counts"])
        self.assertIn("ledger_total_return_mismatch", result["issue_code_counts"])
        self.assertIn("replay_total_cost_mismatch", result["issue_code_counts"])

    def test_deep_audit_reconciles_summary_costs_to_action_sums(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["total_commission"] += 1.0
        replay["total_slippage_cost"] += 1.0
        replay["total_sell_tax"] += 1.0
        replay["total_transaction_cost"] += 3.0
        replay["transaction_cost_pct_of_initial_cash"] += 3.0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_commission_action_sum_mismatch", result["issue_code_counts"])
        self.assertIn("replay_sell_tax_action_sum_mismatch", result["issue_code_counts"])
        self.assertIn("replay_slippage_action_sum_mismatch", result["issue_code_counts"])

    def test_deep_audit_reconstructs_cash_and_final_equity_from_actions(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["experience_log"][-1]["cash"] = 90.0
        buy = self._buy()
        buy["cash_cost"] = 200.0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [buy, self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_cash_balance_negative", result["issue_code_counts"])
        self.assertIn("replay_final_cash_mismatch", result["issue_code_counts"])
        self.assertIn("replay_cash_positions_equity_mismatch", result["issue_code_counts"])

    def test_deep_audit_values_open_positions_at_net_liquidation_value(self):
        ledger = self._ledger()
        ledger["new_trade_count"] = 0
        ledger["new_total_return_pct"] = 0.85
        ledger["reconciliation"]["checked_count"] = 0
        replay = self._replay()
        last_price = 101.1
        gross = last_price * (1.0 - 5.0 / 10_000.0)
        final_equity = round(
            gross - gross * (1.5 / 10_000.0) - gross * (18.0 / 10_000.0),
            2,
        )
        replay.update(
            {
                "final_equity": final_equity,
                "total_return_pct": 0.85,
                "total_commission": 0.01,
                "total_slippage_cost": 0.05,
                "total_sell_tax": 0.0,
                "total_turnover": 99.99,
                "total_transaction_cost": 0.06,
                "transaction_cost_pct_of_initial_cash": 0.06,
                "win_rate_pct": 0.0,
                "average_win_pct": 0.0,
                "closed_trade_count": 0,
                "trade_count": 1,
                "trade_action_count": 1,
                "trade_journal_reconciliation_summary": {
                    "reconciliation_engine_version": "trade-price-return-audit.v6",
                    "checked_count": 0,
                    "ok_count": 0,
                    "warning_count": 0,
                    "blocker_count": 0,
                    "official_return_blocker_count": 0,
                    "needs_review": 0,
                    "samples": [],
                },
                "equity_curve": [100.0, final_equity],
                "monthly_equity": [{"month": "2026-01", "equity": final_equity}],
                "open_positions": [
                    {
                        "symbol": "005930",
                        "quantity": 1.0,
                        "avg_cost": 100.0,
                        "last_price": last_price,
                        "unrealized_pct": 1.1,
                    }
                ],
                "experience_log": [
                    {
                        "date": "2026-01-03",
                        "cash": 0.0,
                        "equity": final_equity,
                        "positions": 1,
                        "actions": [],
                    },
                ],
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertTrue(result["ok"], result["issue_records"])

    def test_deep_audit_blocks_tampered_reconciliation_summary(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["trade_journal_reconciliation_summary"]["ok_count"] = 0
        replay["trade_journal_reconciliation_summary"]["needs_review"] = 1
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_reconciliation_summary_mismatch", result["issue_code_counts"])

    def test_deep_audit_reconciles_experience_log_rows_to_full_journal(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["experience_log"][-1]["cash"] = 90.0
        replay["experience_log"][-1]["positions"] = 4
        replay["experience_log"][-1]["actions"] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_experience_cash_mismatch", result["issue_code_counts"])
        self.assertIn("replay_experience_actions_mismatch", result["issue_code_counts"])
        self.assertIn(
            "replay_experience_position_count_mismatch",
            result["issue_code_counts"],
        )

    def test_deep_audit_blocks_invalid_equity_curve_origin_and_date_order(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["equity_curve"][0] = 99.0
        replay["dates"] = ["2026-01-03", "2026-01-02"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_initial_equity_mismatch", result["issue_code_counts"])
        self.assertIn("replay_curve_date_order_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_invalid_mdd_and_monthly_equity_timeline(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["max_drawdown_pct"] = 1.0
        replay["monthly_equity"] = [
            {"month": "2026-02", "equity": 110.0},
            {"month": "2026-01", "equity": -1.0},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_mdd_range_invalid", result["issue_code_counts"])
        self.assertIn("replay_monthly_order_invalid", result["issue_code_counts"])
        self.assertIn("replay_monthly_equity_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_curve_and_actions_outside_replay_period(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["start_date"] = "2026-01-03"
        replay["end_date"] = "2026-01-04"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_curve_outside_period", result["issue_code_counts"])
        self.assertIn("journal_action_outside_replay_period", result["issue_code_counts"])

    def test_deep_audit_blocks_action_and_contract_symbol_identity_mismatch(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["price_currency_unit_audit"]["contracts"]["005930"]["symbol"] = "000660"
        buy = self._buy()
        sell = self._sell()
        buy["symbol"] = "000660"
        sell["symbol"] = "000660"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [buy, sell]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("price_contract_symbol_identity_mismatch", result["issue_code_counts"])
        self.assertIn("journal_symbol_outside_replay_universe", result["issue_code_counts"])

    def test_deep_audit_blocks_missing_price_provider_and_partial_fx_state(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        contract = replay["price_currency_unit_audit"]["contracts"]["005930"]
        contract["provider"] = ""
        contract["partial_fx_conversion_blocked"] = True
        contract["market"] = "US"
        contract["source_currency"] = "USD"
        contract["fx_conversion_applied"] = True
        contract["fx_pair"] = "USD/KRW"
        contract["fx_source"] = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("price_contract_provider_missing", result["issue_code_counts"])
        self.assertIn("price_contract_partial_fx_state_invalid", result["issue_code_counts"])
        self.assertIn("price_contract_us_fx_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_coverage_above_one_hundred_percent(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        contract = replay["price_currency_unit_audit"]["contracts"]["005930"]
        contract["adjusted_close_coverage_pct"] = 101.0
        contract["fx_coverage_pct"] = 150.0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("price_contract_adjusted_coverage_low", result["issue_code_counts"])
        self.assertIn("price_contract_fx_coverage_low", result["issue_code_counts"])

    def test_deep_audit_recomputes_win_and_average_return_statistics(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["win_rate_pct"] = 50.0
        replay["average_win_pct"] = 9.0
        replay["average_loss_pct"] = -9.0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_win_rate_mismatch", result["issue_code_counts"])
        self.assertIn("replay_average_win_mismatch", result["issue_code_counts"])
        self.assertIn("replay_average_loss_mismatch", result["issue_code_counts"])

    def test_deep_audit_reconciles_open_position_details_to_last_buy(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["open_positions"] = [
            {
                "symbol": "005930",
                "quantity": 2.0,
                "avg_cost": 110.0,
                "last_price": 99.0,
                "unrealized_pct": 99.0,
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_open_position_quantity_mismatch", result["issue_code_counts"])
        self.assertIn("replay_open_position_avg_cost_mismatch", result["issue_code_counts"])
        self.assertIn("replay_open_position_return_mismatch", result["issue_code_counts"])

    def test_deep_audit_reconciles_notional_and_net_proceeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buy = self._buy()
            sell = self._sell()
            buy["notional"] = 999.0
            sell["notional"] = 999.0
            sell["net_proceeds"] = 999.0
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [buy, sell]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("buy_notional_mismatch", result["issue_code_counts"])
        self.assertIn("trade_notional_mismatch", result["issue_code_counts"])
        self.assertIn("trade_net_proceeds_mismatch", result["issue_code_counts"])

    def test_deep_audit_reconciles_total_turnover_to_action_notionals(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        replay["total_turnover"] = 999.0
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("replay_turnover_action_sum_mismatch", result["issue_code_counts"])

    def test_deep_audit_blocks_failed_price_currency_contract(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        replay = self._replay()
        contract = replay["price_currency_unit_audit"]["contracts"]["005930"]
        replay["price_currency_unit_audit"]["passed"] = False
        replay["price_currency_unit_audit"]["blockers"] = [{"symbol": "005930"}]
        contract["passed"] = False
        contract["corporate_action_adjusted"] = False
        contract["price_basis"] = "raw_close_unverified"
        contract["adjusted_close_coverage_pct"] = 0.38
        contract["blockers"] = ["split_dividend_adjustment_not_verified"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("price_currency_unit_audit_not_passed", result["issue_code_counts"])
        self.assertIn("price_contract_not_passed", result["issue_code_counts"])

    def test_deep_audit_blocks_missing_fill_and_peak_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trade = self._sell()
            trade["execution_price"] = None
            trade["peak_market_price"] = None
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), trade]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(1, result["missing_trade_field_counts"]["execution_price"])
        self.assertEqual(1, result["missing_trade_field_counts"]["peak_market_price"])
        self.assertEqual("trade_evidence_missing", result["issue_records"][0]["code"])

    def test_deep_audit_blocks_missing_exit_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trade = self._sell()
            trade.pop("date")
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), trade]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(1, result["missing_trade_field_counts"]["date"])
        self.assertIn("trade_evidence_missing", result["issue_code_counts"])
        self.assertIn("execution_date_mismatch", result["issue_code_counts"])

    def test_deep_audit_blocks_exit_before_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trade = self._sell()
            trade["date"] = "2025-12-31"
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), trade]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("trade_date_order_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_holding_days_beyond_calendar_interval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trade = self._sell()
            trade["holding_days"] = 99
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), trade]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("trade_holding_days_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_fractional_share_quantity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buy = self._buy()
            sell = self._sell()
            buy["quantity"] = 0.5
            sell["quantity"] = 0.5
            buy["commission"] = 0.0
            buy["cash_cost"] = 50.025
            sell["commission"] = 0.0
            sell["sell_tax"] = 0.09
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [buy, sell]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("buy_quantity_unit_invalid", result["issue_code_counts"])
        self.assertIn("trade_quantity_unit_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_disconnected_peak_and_exit_trigger_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trade = self._sell()
            trade["peak_market_price"] = 99.0
            trade["exit_trigger_market_price"] = 98.0
            trade["peak_drawdown_pct"] = round(((98.0 / 99.0) - 1.0) * 100.0, 4)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), trade]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("trade_peak_below_entry_market", result["issue_code_counts"])
        self.assertIn("trade_exit_trigger_price_mismatch", result["issue_code_counts"])

    def test_deep_audit_blocks_reverse_chronological_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            late_buy = self._buy()
            late_buy["symbol"] = "MSFT"
            late_buy["date"] = "2025-12-31"
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell(), late_buy]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("journal_action_date_order_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_unknown_and_malformed_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps(
                    {
                        "actions": [
                            self._buy(),
                            self._sell(),
                            {"side": "HOLD", "date": "2026-01-03"},
                            "damaged-row",
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("journal_action_side_invalid", result["issue_code_counts"])
        self.assertIn("journal_action_shape_invalid", result["issue_code_counts"])

    def test_deep_audit_blocks_exit_reason_threshold_not_met(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trade = self._sell()
            trade["reason"] = "take profit +20.0%"
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), trade]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("exit_reason_threshold_mismatch", result["issue_code_counts"])

    def test_bundle_hash_changes_when_journal_evidence_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "HREPLAY-2.json"
            trade = self._sell()
            path.write_text(json.dumps({"actions": [self._buy(), trade]}), encoding="utf-8")
            first = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )
            trade["commission"] = 9.0
            path.write_text(json.dumps({"actions": [self._buy(), trade]}), encoding="utf-8")
            second = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertNotEqual(first["journal_evidence_hash"], second["journal_evidence_hash"])
        self.assertNotEqual(first["evidence_bundle_hash"], second["evidence_bundle_hash"])

    def test_bundle_hash_changes_when_replay_summary_changes(self):
        ledger = self._ledger()
        ledger["new_total_return_pct"] = 10.0
        first_replay = self._replay()
        second_replay = self._replay()
        second_replay["tampered_note"] = "changed"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            first = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[first_replay],
                deep=True,
            )
            second = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[second_replay],
                deep=True,
            )

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertNotEqual(first["replay_evidence_hash"], second["replay_evidence_hash"])
        self.assertNotEqual(first["evidence_bundle_hash"], second["evidence_bundle_hash"])

    def test_deep_audit_blocks_tampered_return_cost_and_fill_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trade = self._sell()
            trade["pnl_pct"] = 99.0
            trade["commission"] = 9.0
            trade["execution_price"] = 102.0
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), trade]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("trade_return_mismatch", result["issue_code_counts"])
        self.assertIn("trade_commission_mismatch", result["issue_code_counts"])
        self.assertIn("trade_slippage_mismatch", result["issue_code_counts"])

    def test_deep_audit_blocks_tampered_buy_fill_and_entry_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buy = self._buy()
            buy["execution_price"] = 98.0
            sell = self._sell()
            sell["entry_price"] = 150.0
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [buy, sell]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[self._ledger()],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertFalse(result["ok"])
        self.assertIn("buy_slippage_mismatch", result["issue_code_counts"])
        self.assertIn("entry_fill_price_mismatch", result["issue_code_counts"])

    def test_source_comparison_does_not_claim_equivalence_after_cost_and_trade_change(self):
        row = self._ledger()
        row.update(
            {
                "source_trade_count": 175,
                "new_trade_count": 179,
                "source_total_return_pct": 54.0,
                "new_total_return_pct": 33.41,
                "cost_policy": {
                    **row["cost_policy"],
                    "changed_from_archive": True,
                },
            }
        )

        result = classify_replay_source_comparison(row)

        self.assertEqual("new_result_valid_source_equivalence_unproven", result["status"])
        self.assertFalse(result["source_equivalence_claim_allowed"])
        self.assertEqual(4, result["trade_count_difference"])
        self.assertEqual(-20.59, result["return_difference_pct_point"])
        self.assertIn("trade_count_changed", result["review_reasons"])
        self.assertIn("cost_policy_changed_from_source", result["review_reasons"])

    def test_evidence_audit_reports_comparison_review_without_failing_new_journal(self):
        ledger = self._ledger()
        ledger.update(
            {
                "source_trade_count": 1,
                "source_total_return_pct": 8.0,
                "new_total_return_pct": 1.0,
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "HREPLAY-2.json").write_text(
                json.dumps({"actions": [self._buy(), self._sell()]}),
                encoding="utf-8",
            )
            result = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                deep=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(1, result["comparison_review_required_count"])
        self.assertEqual(0, result["source_equivalence_claim_allowed_count"])
        self.assertEqual(0, result["issue_count"])

    def test_v3_deep_audit_binds_actions_to_adjacent_symbol_calendar_bars(self):
        dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
        actions = [self._buy(), self._sell()]
        actions[0].update(build_calendar_adjacency_proof("005930", dates, 1))
        actions[1].update(build_calendar_adjacency_proof("005930", dates, 2))
        replay = self._replay()
        replay["start_date"] = dates[0]
        replay["experience_log"][0]["actions"] = [actions[1]]
        replay["execution_timing_model"].update(
            {
                "version": "prior-bar-signal-next-close.v3",
                "execution_bar_excluded_from_decision": True,
                "symbol_calendar_alignment_required": True,
                "missing_execution_bar_policy": "skip_until_next_available_symbol_bar",
                "calendar_adjacency_proof_contract": CALENDAR_ADJACENCY_PROOF_CONTRACT,
            }
        )
        bundle = replay["replay_data_bundle_evidence"]
        bundle.update(
            {
                "schema": "codexstock_replay_data_bundle_slice_evidence_v3",
                "bundle_period": {"start_date": dates[0], "end_date": dates[-1]},
                "requested_period": {"start_date": dates[0], "end_date": dates[-1]},
                "symbol_row_counts": {"005930": 3},
                "symbol_row_bounds": {
                    "005930": {
                        "first_date": dates[0],
                        "last_date": dates[-1],
                        "row_count": 3,
                    }
                },
                "symbol_calendar_adjacency_roots": {
                    "005930": calendar_adjacency_root("005930", dates)
                },
                "symbol_calendar_pair_counts": {"005930": 2},
            }
        )
        bundle["slice_manifest_hash"] = _replay_data_bundle_slice_manifest_hash(bundle)
        ledger = self._ledger()
        ledger.update(
            {
                "evidence_schema_version": "historical-replay-evidence.v6",
                "execution_timing_model_version": "prior-bar-signal-next-close.v3",
                "replay_data_bundle_evidence_schema": bundle["schema"],
                "artifact_hash_contract": REPLAY_ARTIFACT_HASH_CONTRACT,
                "replay_artifact_sha256": canonical_replay_artifact_sha256(replay),
                "new_total_return_pct": 10.0,
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            journal_path = root / "HREPLAY-2.json"
            journal_bytes = json.dumps({"actions": actions}, sort_keys=True).encode("utf-8")
            journal_path.write_bytes(journal_bytes)
            ledger["journal_artifact_sha256"] = journal_artifact_sha256(journal_bytes)
            accepted = audit_regeneration_evidence(
                ledger_rows=[ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
                required_evidence_schema_version="historical-replay-evidence.v6",
                required_execution_timing_model_version="prior-bar-signal-next-close.v3",
            )
            tampered_actions = [dict(action) for action in actions]
            tampered_actions[1]["execution_symbol_bar_date"] = "2026-01-04"
            tampered_bytes = json.dumps({"actions": tampered_actions}, sort_keys=True).encode("utf-8")
            journal_path.write_bytes(tampered_bytes)
            tampered_ledger = {
                **ledger,
                "journal_artifact_sha256": journal_artifact_sha256(tampered_bytes),
            }
            rejected = audit_regeneration_evidence(
                ledger_rows=[tampered_ledger],
                campaign_ids=["HREPLAY-1"],
                journal_root=root,
                replay_rows=[replay],
                deep=True,
                required_evidence_schema_version="historical-replay-evidence.v6",
                required_execution_timing_model_version="prior-bar-signal-next-close.v3",
            )

        self.assertTrue(accepted["ok"], accepted["issue_code_counts"])
        self.assertFalse(rejected["ok"])
        self.assertIn("symbol_calendar_adjacency_proof_invalid", rejected["issue_code_counts"])
        self.assertIn("journal_symbol_calendar_binding_invalid", rejected["issue_code_counts"])


if __name__ == "__main__":
    unittest.main()

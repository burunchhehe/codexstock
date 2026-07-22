import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_suite.pipeline_audit import audit_candidate_pipeline


class CandidatePipelineAuditTests(unittest.TestCase):
    def test_published_candidate_proves_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ticket_file = root / "tickets.jsonl"
            row = {
                "id": "T1", "mode": "live_candidate", "risk_status": "PASSED",
                "created_at": datetime.now().astimezone().isoformat(),
                "shadow_signal": {"published": True, "reason": "signed_shadow_signal_published"},
            }
            ticket_file.write_text(json.dumps(row) + "\n", encoding="utf-8")
            audit = audit_candidate_pipeline(ticket_file, root / "inbox")
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["state"], "executor_processing")
        self.assertEqual(audit["signed_signal_published_count"], 1)
        self.assertEqual(audit["no_trade_classification"], "NORMAL_IN_PROGRESS")
        self.assertTrue(audit["trading_pipeline_healthy"])

    def test_publish_failure_is_exposed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {
                "id": "T2", "mode": "live_candidate", "risk_status": "PASSED",
                "created_at": datetime.now().astimezone().isoformat(),
                "shadow_signal": {"published": False, "reason": "write_failed"},
            }
            (root / "tickets.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            audit = audit_candidate_pipeline(root / "tickets.jsonl", root / "inbox")
        self.assertFalse(audit["ok"])
        self.assertEqual(audit["publish_failure_count"], 1)
        self.assertEqual(audit["incidents"][0]["code"], "SIGNED_SIGNAL_MISSING")

    def test_no_candidate_is_normal_watch_not_a_system_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = audit_candidate_pipeline(root / "tickets.jsonl", root / "inbox")
        self.assertTrue(audit["trading_pipeline_healthy"])
        self.assertEqual(audit["state"], "normal_watch")
        self.assertEqual(audit["no_trade_classification"], "NORMAL_WATCH")
        self.assertEqual(audit["evidence_levels"]["market_scan"], "not_observed_today")

    def test_delegated_ticket_with_approval_token_is_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {
                "id": "T3", "mode": "live_candidate", "risk_status": "PASSED",
                "status": "DELEGATED_SIGNAL_READY", "approval_token": "legacy",
                "created_at": datetime.now().astimezone().isoformat(),
                "shadow_signal": {"published": True},
            }
            (root / "tickets.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            audit = audit_candidate_pipeline(root / "tickets.jsonl", root / "inbox")
        self.assertFalse(audit["trading_pipeline_healthy"])
        self.assertEqual(audit["incidents"][0]["code"], "LEGACY_APPROVAL_GATE_ACTIVE")

    def test_full_auto_completed_handoff_ignores_inert_legacy_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime.now().astimezone()
            tickets = []
            processed = root / "processed"
            results = root / "results"
            processed.mkdir()
            results.mkdir()
            for index in range(4):
                signal_id = f"AUTO-{index}"
                tickets.append({
                    "id": signal_id,
                    "mode": "live_candidate",
                    "status": "DELEGATED_SIGNAL_READY",
                    "risk_status": "PASSED",
                    "approval_token": "historical-inert-token",
                    "created_at": now.isoformat(),
                    "metadata": {"execution_mode": "delegated_auto", "require_approval": False},
                    "shadow_signal": {"published": True, "signal_id": signal_id},
                })
                (processed / f"{signal_id}.json").write_text(
                    json.dumps({"signal_id": signal_id, "execution_mode": "delegated_auto"}),
                    encoding="utf-8",
                )
                (results / f"{signal_id}.json").write_text(
                    json.dumps({"signal_id": signal_id, "state": "REJECTED", "reason": "risk", "result": {"mode": "live"}}),
                    encoding="utf-8",
                )
            (root / "tickets.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in tickets), encoding="utf-8"
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl", root / "inbox", processed, results,
                service_mode="live", control_mode="delegated_auto", now=now,
            )
        self.assertTrue(audit["trading_pipeline_healthy"])
        self.assertEqual(4, audit["matched_executor_result_count"])
        self.assertEqual(0, audit["legacy_approval_token_count"])
        self.assertEqual(4, audit["legacy_approval_token_observed_count"])

    def test_semi_auto_signal_without_approval_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {
                "id": "SEMI-1", "mode": "live_candidate", "risk_status": "PASSED",
                "status": "APPROVAL_REQUIRED", "created_at": datetime.now().astimezone().isoformat(),
                "metadata": {"execution_mode": "manual_approval", "require_approval": True},
                "shadow_signal": {"published": True, "signal_id": "SEMI-1"},
            }
            (root / "tickets.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl", root / "inbox", control_mode="manual_approval"
            )
        self.assertFalse(audit["trading_pipeline_healthy"])
        self.assertIn("APPROVAL_GATE_BYPASSED", [row["code"] for row in audit["incidents"]])

    def test_execution_mode_mismatch_is_high_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {
                "id": "MODE-1", "mode": "live_candidate", "risk_status": "PASSED",
                "status": "DELEGATED_SIGNAL_READY", "created_at": datetime.now().astimezone().isoformat(),
                "metadata": {"execution_mode": "delegated_auto"},
                "shadow_signal": {"published": True, "signal_id": "MODE-1"},
            }
            (root / "tickets.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            results = root / "results"
            results.mkdir()
            (results / "MODE-1.json").write_text(
                json.dumps({"state": "SHADOW_ACCEPTED", "result": {"mode": "shadow"}}), encoding="utf-8"
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl", root / "inbox", results_dir=results,
                service_mode="live", control_mode="delegated_auto"
            )
        incident = next(row for row in audit["incidents"] if row["code"] == "EXECUTION_MODE_MISMATCH")
        self.assertEqual("high", incident["severity"])

    def test_stale_market_scan_during_session_is_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            pulse = {"generated_at": (now - timedelta(minutes=11)).isoformat(), "count": 30}
            (root / "pulse.jsonl").write_text(json.dumps(pulse) + "\n", encoding="utf-8")
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl", root / "inbox", market_pulse_file=root / "pulse.jsonl", now=now
            )
        self.assertFalse(audit["trading_pipeline_healthy"])
        self.assertEqual(audit["incidents"][0]["code"], "MARKET_SCAN_STALLED")

    def test_ready_decision_without_ticket_is_promotion_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            decision = {
                "recorded_at": (now - timedelta(minutes=3)).isoformat(),
                "candidate_ready": True,
                "broker_submit_ready": True,
            }
            (root / "decisions.jsonl").write_text(json.dumps(decision) + "\n", encoding="utf-8")
            (root / "pulse.jsonl").write_text(
                json.dumps({"generated_at": now.isoformat(), "count": 0}) + "\n",
                encoding="utf-8",
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl", root / "inbox",
                market_pulse_file=root / "pulse.jsonl",
                candidate_decision_file=root / "decisions.jsonl", now=now,
            )
        self.assertFalse(audit["trading_pipeline_healthy"])
        self.assertEqual(audit["incidents"][0]["code"], "CANDIDATE_PROMOTION_STALLED")

    def test_risk_blocked_decision_remains_normal_watch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            decision = {
                "recorded_at": (now - timedelta(minutes=30)).isoformat(),
                "candidate_ready": False,
                "broker_submit_ready": False,
                "checks_summary": {"blocked_labels": ["risk_gate"]},
            }
            (root / "decisions.jsonl").write_text(json.dumps(decision) + "\n", encoding="utf-8")
            (root / "pulse.jsonl").write_text(
                json.dumps({"generated_at": now.isoformat(), "count": 0}) + "\n",
                encoding="utf-8",
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl", root / "inbox",
                market_pulse_file=root / "pulse.jsonl",
                candidate_decision_file=root / "decisions.jsonl", now=now,
            )
        self.assertTrue(audit["trading_pipeline_healthy"])
        self.assertEqual(audit["state"], "normal_risk_block")
        self.assertEqual(audit["no_trade_classification"], "NORMAL_RISK_BLOCK")
        self.assertEqual(audit["normal_watch_reason"]["blocked_labels"], ["risk_gate"])

    def test_missing_market_scan_during_session_is_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl",
                root / "inbox",
                market_pulse_file=root / "pulse.jsonl",
                now=now,
            )
        self.assertFalse(audit["trading_pipeline_healthy"])
        self.assertEqual("MARKET_SCAN_STALLED", audit["incidents"][0]["code"])
        self.assertIsNone(audit["incidents"][0]["age_seconds"])

    def test_unrelated_result_does_not_satisfy_signed_signal_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            row = {
                "id": "T-HANDOFF",
                "mode": "live_candidate",
                "risk_status": "PASSED",
                "created_at": (now - timedelta(minutes=5)).isoformat(),
                "shadow_signal": {"published": True, "signal_id": "T-HANDOFF"},
            }
            (root / "tickets.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            results = root / "results"
            results.mkdir()
            (results / "OTHER-SIGNAL.json").write_text("{}", encoding="utf-8")
            (root / "pulse.jsonl").write_text(
                json.dumps({"generated_at": now.isoformat(), "count": 0}) + "\n",
                encoding="utf-8",
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl",
                root / "inbox",
                results_dir=results,
                market_pulse_file=root / "pulse.jsonl",
                now=now,
            )
        codes = [item["code"] for item in audit["incidents"]]
        self.assertIn("EXECUTOR_HANDOFF_FAILED", codes)
        self.assertEqual(0, audit["matched_executor_result_count"])
        self.assertEqual(["T-HANDOFF"], audit["pending_handoff_signal_ids"])

    def test_matching_result_proves_end_to_end_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            row = {
                "id": "T-MATCH",
                "mode": "live_candidate",
                "risk_status": "PASSED",
                "created_at": (now - timedelta(seconds=30)).isoformat(),
                "shadow_signal": {"published": True, "signal_id": "T-MATCH"},
            }
            (root / "tickets.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            results = root / "results"
            results.mkdir()
            (results / "T-MATCH.json").write_text("{}", encoding="utf-8")
            (root / "pulse.jsonl").write_text(
                json.dumps({"generated_at": now.isoformat(), "count": 0}) + "\n",
                encoding="utf-8",
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl",
                root / "inbox",
                results_dir=results,
                market_pulse_file=root / "pulse.jsonl",
                now=now,
            )
        self.assertTrue(audit["trading_pipeline_healthy"])
        self.assertEqual("connected", audit["state"])
        self.assertEqual(1, audit["matched_executor_result_count"])
        self.assertEqual("end_to_end_success", audit["evidence_levels"]["executor_handoff"])

    def test_continuously_pending_high_score_candidate_triggers_sla(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            pulse = {"generated_at": now.isoformat(), "count": 1}
            radar_rows = [
                {
                    "generated_at": (now - timedelta(minutes=6)).isoformat(),
                    "items": [{"symbol": "005930", "score": 91, "detail_validation_passed": False}],
                },
                {
                    "generated_at": (now - timedelta(seconds=5)).isoformat(),
                    "items": [{"symbol": "005930", "score": 92, "detail_validation_passed": False}],
                },
            ]
            (root / "pulse.jsonl").write_text(json.dumps(pulse) + "\n", encoding="utf-8")
            (root / "radar.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in radar_rows),
                encoding="utf-8",
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl",
                root / "inbox",
                market_pulse_file=root / "pulse.jsonl",
                minute_radar_file=root / "radar.jsonl",
                now=now,
            )
        codes = [item["code"] for item in audit["incidents"]]
        self.assertIn("CANDIDATE_VALIDATION_STALLED", codes)

    def test_data_unavailable_is_not_mislabeled_as_normal_risk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            decision = {
                "recorded_at": (now - timedelta(minutes=1)).isoformat(),
                "candidate_ready": False,
                "broker_submit_ready": False,
                "checks_summary": {
                    "blocked_labels": ["quote"],
                    "blocker_classification": {
                        "primary": "DATA_UNAVAILABLE",
                        "counts": {"DATA_UNAVAILABLE": 1},
                    },
                },
            }
            (root / "decisions.jsonl").write_text(json.dumps(decision) + "\n", encoding="utf-8")
            (root / "pulse.jsonl").write_text(
                json.dumps({"generated_at": now.isoformat(), "count": 0}) + "\n",
                encoding="utf-8",
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl",
                root / "inbox",
                market_pulse_file=root / "pulse.jsonl",
                candidate_decision_file=root / "decisions.jsonl",
                now=now,
            )
        self.assertTrue(audit["trading_pipeline_healthy"])
        self.assertEqual("data_wait", audit["state"])
        self.assertEqual("DATA_UNAVAILABLE", audit["no_trade_classification"])

    def test_old_data_unavailable_block_becomes_pipeline_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=9)))
            decision = {
                "recorded_at": (now - timedelta(minutes=6)).isoformat(),
                "candidate_ready": False,
                "broker_submit_ready": False,
                "checks_summary": {
                    "blocked_labels": ["quote"],
                    "blocker_classification": {"primary": "DATA_UNAVAILABLE"},
                },
            }
            (root / "decisions.jsonl").write_text(json.dumps(decision) + "\n", encoding="utf-8")
            (root / "pulse.jsonl").write_text(
                json.dumps({"generated_at": now.isoformat(), "count": 0}) + "\n",
                encoding="utf-8",
            )
            audit = audit_candidate_pipeline(
                root / "tickets.jsonl",
                root / "inbox",
                market_pulse_file=root / "pulse.jsonl",
                candidate_decision_file=root / "decisions.jsonl",
                now=now,
            )
        codes = [item["code"] for item in audit["incidents"]]
        self.assertIn("CANDIDATE_VALIDATION_STALLED", codes)
        self.assertEqual("SYSTEM_BOTTLENECK", audit["no_trade_classification"])


if __name__ == "__main__":
    unittest.main()

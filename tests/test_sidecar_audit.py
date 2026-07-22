import json
import hashlib
import sqlite3
import tempfile
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_suite.sidecar_audit import audit_shadow_runtime
from stock_suite.runtime_evidence import RuntimeEvidenceLedger
from stock_suite.execution_sidecar import OrderSignal


def _write_evidence(
    root: Path, signal_id: str, result: dict[str, object], strategy_id: str = "candidate-ledger",
    *, candidate_origin: bool = False, ticket_risk_status: str = "PASSED",
    ticket_created_at: datetime | None = None,
) -> None:
    source: dict[str, object] = {"signal_id": signal_id, "strategy_id": strategy_id}
    if candidate_origin:
        now = datetime.now(timezone.utc)
        ticket = {
            "id": signal_id,
            "mode": "live_candidate",
            "risk_status": ticket_risk_status,
            "symbol": "005930",
            "created_at": (ticket_created_at or now).isoformat(),
        }
        ticket_encoded = json.dumps(
            ticket, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        secret = b"audit-test-secret"
        (root / "signal_secret").write_bytes(secret)
        signed = OrderSignal(
            signal_id=signal_id,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=1)).isoformat(),
            symbol="005930",
            side="BUY",
            quantity=1,
            order_type="IOC_LIMIT",
            reference_price=70000.0,
            max_price=70280.0,
            stop_loss_pct=-2.0,
            take_profit_pct=3.0,
            strategy_id=strategy_id,
            evidence_hash="1" * 64,
            origin="candidate_ledger",
            candidate_ticket_hash=hashlib.sha256(ticket_encoded).hexdigest(),
        ).sign(secret)
        source = asdict(signed)
        with (root.parent / "order_tickets.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(ticket, ensure_ascii=False) + "\n")
    encoded = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_hash = hashlib.sha256(encoded).hexdigest()
    (root / "results" / f"{signal_id}.json").write_text(json.dumps(result), encoding="utf-8")
    (root / "processed" / f"{signal_id}.json").write_text(json.dumps(source), encoding="utf-8")
    db = sqlite3.connect(root / "ledger.sqlite3")
    try:
        db.execute(
            "CREATE TABLE IF NOT EXISTS signals ("
            "signal_id TEXT PRIMARY KEY, payload_hash TEXT, state TEXT, reason TEXT, result_json TEXT)"
        )
        db.execute(
            "INSERT INTO signals(signal_id,payload_hash,state,reason,result_json) VALUES(?,?,?,?,?)",
            (
                signal_id, payload_hash, result.get("state"), result.get("reason"),
                json.dumps(result.get("result") or {}, ensure_ascii=False),
            ),
        )
        db.commit()
    finally:
        db.close()


def _write_runtime_heartbeat(root: Path, observed_at: datetime) -> None:
    RuntimeEvidenceLedger(root / "runtime_evidence.sqlite3", session_id="TEST").heartbeat(
        mode="shadow", cycle=1, ok=True, observed_at=observed_at
    )
    (root / "shadow_candidate_scheduler.json").write_text(json.dumps({
        "last_checked_at": observed_at.isoformat(),
        "last_status": "MARKET_CLOSED",
        "market_open": False,
    }), encoding="utf-8")


class ShadowRuntimeAuditTests(unittest.TestCase):
    def test_operational_health_is_separate_from_time_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            status = {
                "ok": True, "started_at": (now - timedelta(hours=1)).isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }
            (root / "status.json").write_text(json.dumps(status), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "A", "state": "SHADOW_ACCEPTED",
                "result": {"real_order_submitted": False, "snapshot": {"account_ok": True, "snapshot_errors": []}},
            }
            _write_evidence(root, "A", result)
            audit = audit_shadow_runtime(root, min_observation_hours=24)
        self.assertTrue(audit["operational_ok"])
        self.assertFalse(audit["proof_complete"])

    def test_real_order_flag_or_invalid_snapshot_fails_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": (now - timedelta(hours=25)).isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            bad = {
                "signal_id": "BAD", "state": "SHADOW_ACCEPTED",
                "result": {"real_order_submitted": True, "snapshot": {"account_ok": False, "snapshot_errors": ["bad"]}},
            }
            _write_evidence(root, "BAD", bad)
            audit = audit_shadow_runtime(root, min_observation_hours=24)
        self.assertFalse(audit["operational_ok"])
        self.assertFalse(audit["proof_complete"])

    def test_idle_uptime_does_not_complete_proof_without_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": (now - timedelta(hours=25)).isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            audit = audit_shadow_runtime(root, min_observation_hours=24, min_result_count=10, min_symbol_count=2)
        self.assertTrue(audit["operational_ok"])
        self.assertFalse(audit["coverage_complete"])
        self.assertFalse(audit["proof_complete"])

    def test_diagnostic_results_do_not_count_as_candidate_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": now.isoformat(), "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "DIAG", "state": "SHADOW_ACCEPTED",
                "result": {"symbol": "005930", "real_order_submitted": False,
                           "snapshot": {"account_ok": True, "snapshot_errors": []}},
            }
            _write_evidence(root, "DIAG", result, strategy_id="shadow-e2e-diagnostic")
            audit = audit_shadow_runtime(root, min_result_count=1, min_symbol_count=1)
        self.assertEqual(audit["evidence"]["result_count"], 1)
        self.assertEqual(audit["evidence"]["qualifying_result_count"], 0)
        self.assertFalse(audit["coverage_complete"])

    def test_only_candidate_ledger_signal_with_kis_snapshot_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "execution_sidecar"
            (root / "results").mkdir(parents=True)
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": now.isoformat(), "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "LIVE-CANDIDATE", "state": "SHADOW_ACCEPTED",
                "result": {"symbol": "005930", "real_order_submitted": False,
                           "snapshot": {"account_ok": True, "snapshot_errors": [],
                                        "data_source": "KIS_READONLY_CALLS_LIVE_PROFILE"}},
            }
            _write_evidence(root, "LIVE-CANDIDATE", result, candidate_origin=True)
            audit = audit_shadow_runtime(
                root, min_observation_hours=0, min_result_count=1, min_symbol_count=1
            )
        self.assertEqual(audit["evidence"]["qualifying_result_count"], 1)
        self.assertEqual(audit["evidence"]["observed_symbols"], ["005930"])
        self.assertTrue(audit["coverage_complete"])
        self.assertTrue(audit["proof_complete"])

    def test_candidate_ticket_hash_mismatch_fails_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "execution_sidecar"
            (root / "results").mkdir(parents=True)
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": now.isoformat(), "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "ALTERED", "state": "SHADOW_ACCEPTED",
                "result": {"symbol": "005930", "real_order_submitted": False,
                           "snapshot": {"account_ok": True, "snapshot_errors": [],
                                        "data_source": "KIS_READONLY_CALLS_LIVE_PROFILE"}},
            }
            _write_evidence(root, "ALTERED", result, candidate_origin=True)
            (root.parent / "order_tickets.jsonl").write_text(
                json.dumps({"id": "ALTERED", "mode": "live_candidate", "risk_status": "BLOCKED"}) + "\n",
                encoding="utf-8",
            )
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=1, min_symbol_count=1)
        self.assertFalse(audit["checks"]["candidate_ticket_hash_parity"])
        self.assertFalse(audit["operational_ok"])
        self.assertIn("ALTERED", audit["evidence"]["candidate_ticket_hash_mismatches"])

    def test_signed_blocked_upstream_ticket_never_counts_as_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "execution_sidecar"
            (root / "results").mkdir(parents=True)
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": now.isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "BLOCKED-UPSTREAM", "state": "SHADOW_ACCEPTED",
                "result": {"symbol": "005930", "real_order_submitted": False,
                           "snapshot": {"account_ok": True, "snapshot_errors": [],
                                        "data_source": "KIS_READONLY_CALLS_LIVE_PROFILE"}},
            }
            _write_evidence(
                root, "BLOCKED-UPSTREAM", result,
                candidate_origin=True, ticket_risk_status="BLOCKED",
            )
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=1, min_symbol_count=1)
        self.assertEqual(audit["evidence"]["qualifying_result_count"], 0)
        self.assertIn(
            "upstream_gate_not_passed",
            audit["evidence"]["qualification_failures"]["BLOCKED-UPSTREAM"],
        )

    def test_candidate_from_prior_runtime_session_never_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "execution_sidecar"
            (root / "results").mkdir(parents=True)
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": now.isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "OLD-CANDIDATE", "state": "SHADOW_ACCEPTED",
                "result": {"symbol": "005930", "real_order_submitted": False,
                           "snapshot": {"account_ok": True, "snapshot_errors": [],
                                        "data_source": "KIS_READONLY_CALLS_LIVE_PROFILE"}},
            }
            old = now - timedelta(minutes=1)
            _write_evidence(
                root, "OLD-CANDIDATE", result,
                candidate_origin=True, ticket_created_at=old,
            )
            source_path = root / "processed" / "OLD-CANDIDATE.json"
            source = json.loads(source_path.read_text(encoding="utf-8"))
            source["created_at"] = old.isoformat()
            source_path.write_text(json.dumps(source), encoding="utf-8")
            encoded = json.dumps(
                source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            db = sqlite3.connect(root / "ledger.sqlite3")
            db.execute(
                "UPDATE signals SET payload_hash=? WHERE signal_id=?",
                (hashlib.sha256(encoded).hexdigest(), "OLD-CANDIDATE"),
            )
            db.commit()
            db.close()
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=1, min_symbol_count=1)
        self.assertEqual(audit["evidence"]["qualifying_result_count"], 0)
        self.assertIn(
            "signal_predates_runtime_segment",
            audit["evidence"]["qualification_failures"]["OLD-CANDIDATE"],
        )

    def test_candidate_signature_mismatch_fails_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "execution_sidecar"
            (root / "results").mkdir(parents=True)
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": now.isoformat(), "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "BAD-SIGNATURE", "state": "SHADOW_ACCEPTED",
                "result": {"symbol": "005930", "real_order_submitted": False,
                           "snapshot": {"account_ok": True, "snapshot_errors": [],
                                        "data_source": "KIS_READONLY_CALLS_LIVE_PROFILE"}},
            }
            _write_evidence(root, "BAD-SIGNATURE", result, candidate_origin=True)
            source_path = root / "processed" / "BAD-SIGNATURE.json"
            source = json.loads(source_path.read_text(encoding="utf-8"))
            source["signature"] = "0" * 64
            source_path.write_text(json.dumps(source), encoding="utf-8")
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=1, min_symbol_count=1)
        self.assertFalse(audit["checks"]["candidate_signature_parity"])
        self.assertFalse(audit["operational_ok"])
        self.assertIn("BAD-SIGNATURE", audit["evidence"]["candidate_signature_mismatches"])

    def test_tampered_result_payload_fails_full_ledger_parity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "mode": "shadow", "started_at": now.isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            result = {
                "signal_id": "RESULT-TAMPER", "state": "SHADOW_ACCEPTED", "reason": "all_guards_passed",
                "result": {"symbol": "005930", "real_order_submitted": False,
                           "snapshot": {"account_ok": True, "snapshot_errors": []}},
            }
            _write_evidence(root, "RESULT-TAMPER", result)
            result["result"]["symbol"] = "000660"
            (root / "results" / "RESULT-TAMPER.json").write_text(
                json.dumps(result), encoding="utf-8"
            )
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=0, min_symbol_count=0)
        self.assertFalse(audit["checks"]["ledger_result_parity"])
        self.assertFalse(audit["operational_ok"])
        self.assertIn("RESULT-TAMPER", audit["evidence"]["result_payload_mismatches"])

    def test_market_open_candidate_scheduler_failure_fails_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "started_at": now.isoformat(), "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            (root / "shadow_candidate_scheduler.json").write_text(json.dumps({
                "last_checked_at": now.isoformat(),
                "last_status": "PUBLISH_BLOCKED",
                "market_open": True,
            }), encoding="utf-8")
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=0, min_symbol_count=0)
        self.assertFalse(audit["checks"]["shadow_candidate_scheduler_healthy"])
        self.assertFalse(audit["operational_ok"])

    def test_runtime_mode_mismatch_fails_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "mode": "shadow", "started_at": now.isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            RuntimeEvidenceLedger(root / "runtime_evidence.sqlite3", session_id="PAPER").heartbeat(
                mode="paper", cycle=1, ok=True, observed_at=now
            )
            (root / "shadow_candidate_scheduler.json").write_text(json.dumps({
                "last_checked_at": now.isoformat(), "last_status": "MARKET_CLOSED", "market_open": False,
            }), encoding="utf-8")
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=0, min_symbol_count=0)
        self.assertFalse(audit["checks"]["runtime_mode_matches_service"])
        self.assertFalse(audit["operational_ok"])

    def test_future_status_timestamp_cannot_pass_freshness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True,
                "mode": "shadow",
                "started_at": now.isoformat(),
                "updated_at": (now + timedelta(minutes=5)).isoformat(),
                "inbox_pending": 0,
            }), encoding="utf-8")
            _write_runtime_heartbeat(root, now)
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=0, min_symbol_count=0)
        self.assertFalse(audit["checks"]["heartbeat_fresh"])
        self.assertFalse(audit["operational_ok"])

    def test_future_scheduler_timestamp_cannot_pass_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "processed").mkdir()
            now = datetime.now(timezone.utc)
            (root / "status.json").write_text(json.dumps({
                "ok": True, "mode": "shadow", "started_at": now.isoformat(),
                "updated_at": now.isoformat(), "inbox_pending": 0,
            }), encoding="utf-8")
            RuntimeEvidenceLedger(root / "runtime_evidence.sqlite3", session_id="FUTURE-SCHED").heartbeat(
                mode="shadow", cycle=1, ok=True, observed_at=now
            )
            (root / "shadow_candidate_scheduler.json").write_text(json.dumps({
                "last_checked_at": (now + timedelta(minutes=5)).isoformat(),
                "last_status": "MARKET_CLOSED", "market_open": False,
            }), encoding="utf-8")
            audit = audit_shadow_runtime(root, min_observation_hours=0, min_result_count=0, min_symbol_count=0)
        self.assertFalse(audit["checks"]["shadow_candidate_scheduler_healthy"])
        self.assertFalse(audit["operational_ok"])


if __name__ == "__main__":
    unittest.main()

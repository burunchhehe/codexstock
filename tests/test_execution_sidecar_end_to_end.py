import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_suite.execution_sidecar import (
    ExecutionSidecar,
    MarketSnapshot,
    SignalLedger,
    process_signal_directory_once,
)
from stock_suite.runtime_evidence import RuntimeEvidenceLedger
from stock_suite.sidecar_audit import audit_shadow_runtime
from stock_suite.signal_bridge import ShadowSignalPublisher, load_or_create_signing_secret


class ExecutionSidecarEndToEndTests(unittest.TestCase):
    def test_candidate_to_signed_shadow_result_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            data_root = Path(directory)
            sidecar_root = data_root / "execution_sidecar"
            now = datetime.now(timezone.utc)
            candidate_at = now + timedelta(seconds=1)
            ticket = {
                "id": "TIC-E2E-LIVE-1",
                "created_at": candidate_at.isoformat(),
                "symbol": "005930",
                "side": "BUY",
                "quantity": 1,
                "price": 100_000,
                "mode": "live_candidate",
                "risk_status": "PASSED",
                "source": "candidate-radar",
                "memo": "validated live candidate",
                "risk_checks": [{"name": "candidate_gate", "ok": True}],
                "metadata": {"strategy_id": "momentum-production-v1"},
            }
            publisher = ShadowSignalPublisher(
                sidecar_root / "inbox", sidecar_root / "signal_secret", ttl_seconds=30
            )
            publication = publisher.publish(ticket)
            self.assertTrue(publication["published"])
            ticket["shadow_signal"] = publication
            (data_root / "order_tickets.jsonl").write_text(
                json.dumps(ticket, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            secret = load_or_create_signing_secret(sidecar_root / "signal_secret")
            executor = ExecutionSidecar(
                SignalLedger(sidecar_root / "ledger.sqlite3"),
                secret,
                mode="shadow",
                clock=lambda: now + timedelta(seconds=2),
            )
            snapshot = MarketSnapshot(
                observed_at=(now + timedelta(seconds=2)).isoformat(),
                current_price=100_000,
                ask_price=100_000,
                bid_price=99_900,
                account_ok=True,
                available_cash=1_000_000,
                equity=10_000_000,
                total_exposure=0,
                symbol_exposure=0,
                daily_loss_pct=0,
                daily_order_count=0,
                data_source="KIS_READONLY_CALLS_LIVE_PROFILE",
            )
            completed = process_signal_directory_once(
                sidecar_root / "inbox",
                sidecar_root / "processed",
                sidecar_root / "results",
                executor,
                lambda _signal: snapshot,
            )
            self.assertEqual(completed[0]["state"], "SHADOW_ACCEPTED")
            self.assertFalse(completed[0]["result"]["real_order_submitted"])

            status = {
                "ok": True,
                "mode": "shadow",
                "started_at": now.isoformat(),
                "updated_at": (now + timedelta(seconds=2)).isoformat(),
                "inbox_pending": 0,
                "candidate_pipeline": {"ok": True},
                "real_order_supported": False,
            }
            (sidecar_root / "status.json").write_text(json.dumps(status), encoding="utf-8")
            (sidecar_root / "shadow_candidate_scheduler.json").write_text(json.dumps({
                "last_checked_at": (now + timedelta(seconds=2)).isoformat(),
                "last_status": "PUBLISHED",
                "market_open": True,
            }), encoding="utf-8")
            RuntimeEvidenceLedger(
                sidecar_root / "runtime_evidence.sqlite3", session_id="E2E"
            ).heartbeat(mode="shadow", cycle=1, ok=True, observed_at=now)

            audit = audit_shadow_runtime(
                sidecar_root,
                min_observation_hours=0,
                min_result_count=1,
                min_symbol_count=1,
            )

        self.assertTrue(audit["operational_ok"])
        self.assertTrue(audit["proof_complete"])
        self.assertEqual(audit["evidence"]["qualifying_result_count"], 1)
        self.assertEqual(audit["evidence"]["observed_symbols"], ["005930"])
        self.assertEqual(audit["evidence"]["real_order_violations"], [])
        self.assertEqual(audit["evidence"]["candidate_ticket_hash_mismatches"], [])


if __name__ == "__main__":
    unittest.main()

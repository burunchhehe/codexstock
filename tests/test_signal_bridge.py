import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ops_core import HepiOpsCore
from stock_suite.execution_sidecar import OrderSignal
from stock_suite.signal_bridge import ShadowSignalPublisher, load_or_create_signing_secret


def candidate(**changes):
    row = {
        "id": "TIC-100",
        "symbol": "005930",
        "side": "BUY",
        "quantity": 1,
        "price": 100_000,
        "mode": "live_candidate",
        "risk_status": "PASSED",
        "source": "candidate-radar",
        "memo": "validated candidate",
        "risk_checks": [{"name": "price", "ok": True}],
        "metadata": {"strategy_id": "momentum-v1", "stop_loss_pct": 2, "take_profit_pct": 3},
    }
    row.update(changes)
    return row


class ShadowSignalPublisherTests(unittest.TestCase):
    def test_publishes_signed_signal_for_passed_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = ShadowSignalPublisher(root / "inbox", root / "secret")
            result = publisher.publish(candidate())
            payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
            signal = OrderSignal(**payload)
            secret = (root / "secret").read_bytes().strip()
            self.assertTrue(signal.verify(secret))
            self.assertEqual(signal.symbol, "005930")
            self.assertEqual(result["mode"], "shadow_only")
            self.assertEqual(publisher.publish(candidate())["reason"], "idempotent_replay")

    def test_non_live_or_blocked_candidate_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = ShadowSignalPublisher(root / "inbox", root / "secret")
            self.assertEqual(publisher.publish(candidate(mode="paper"))["reason"], "not_live_candidate")
            self.assertEqual(
                publisher.publish(candidate(risk_status="BLOCKED"))["reason"], "candidate_risk_blocked"
            )
            self.assertFalse((root / "inbox").exists())

    def test_same_ticket_cannot_be_reissued_with_changed_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = ShadowSignalPublisher(root / "inbox", root / "secret")
            self.assertTrue(publisher.publish(candidate())["published"])
            rejected = publisher.publish(candidate(quantity=2))
            self.assertFalse(rejected["published"])
            self.assertEqual(rejected["reason"], "signal_id_already_published")

    def test_same_ticket_id_with_changed_risk_metadata_is_not_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publisher = ShadowSignalPublisher(root / "inbox", root / "secret")
            self.assertTrue(publisher.publish(candidate())["published"])
            changed = candidate(metadata={
                "strategy_id": "momentum-v1",
                "stop_loss_pct": 4,
                "take_profit_pct": 3,
                "min_price": 95_000,
            })
            rejected = publisher.publish(changed)
            self.assertFalse(rejected["published"])
            self.assertEqual(rejected["reason"], "signal_id_already_published")

    def test_ops_live_candidate_automatically_publishes_shadow_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict("os.environ", {"CODEXSTOCK_USER_DATA_DIR": str(root / "user-data")}):
                ops = HepiOpsCore(root / "repo")
                ticket = ops.create_order(
                    symbol="005930",
                    side="BUY",
                    quantity=1,
                    price=100_000,
                    mode="live_candidate",
                    source="integration-test",
                    metadata={"strategy_id": "shadow-bridge-test"},
                )
            self.assertEqual(ticket["risk_status"], "PASSED")
            self.assertTrue(ticket["shadow_signal"]["published"])
            signal_path = Path(ticket["shadow_signal"]["path"])
            self.assertTrue(signal_path.exists())
            signal = OrderSignal(**json.loads(signal_path.read_text(encoding="utf-8")))
            self.assertEqual(signal.signal_id, ticket["id"])

    def test_shadow_validation_candidate_never_creates_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict("os.environ", {"CODEXSTOCK_USER_DATA_DIR": str(root / "user-data")}):
                ops = HepiOpsCore(root / "repo")
                ticket = ops.create_order(
                    symbol="005930", side="BUY", quantity=1, price=100_000,
                    mode="live_candidate", source="shadow-forward-validation",
                    metadata={
                        "shadow_validation_only": True,
                        "strategy_id": "shadow-forward-validation-v1",
                        "real_order_allowed": False,
                    },
                )
            self.assertEqual(ticket["status"], "SHADOW_VALIDATION_READY")
            self.assertNotIn("approval_token", ticket)
            self.assertTrue(ticket["shadow_signal"]["published"])
            self.assertEqual(ticket["real_execution"], "BLOCKED")
            self.assertEqual(ops.approvals(), [])

    def test_corrupt_secret_fails_closed_without_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            path.write_text("not-a-valid-256-bit-secret", encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "corrupt|256 bits"):
                load_or_create_signing_secret(path)
            self.assertEqual(path.read_text(encoding="ascii"), "not-a-valid-256-bit-secret")


if __name__ == "__main__":
    unittest.main()

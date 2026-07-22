import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

from app.ops_core import HepiOpsCore
from app.stock_suite_app import _approval_gate_contract


class ExecutionControlModeTests(unittest.TestCase):
    def setUp(self):
        self.runtime_path_patch = patch("app.ops_core.configured_user_data_root", return_value=None)
        self.runtime_path_patch.start()

    def tearDown(self):
        self.runtime_path_patch.stop()

    def test_default_is_manual_approval_and_live_execution_stays_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = HepiOpsCore(Path(directory)).autotrade_policy()
        self.assertEqual(policy["live_execution_control_mode"], "manual_approval")
        self.assertTrue(policy["require_approval"])
        self.assertFalse(policy["delegated_live_autonomy_enabled"])
        self.assertFalse(policy["live_execution_enabled"])

    def test_delegated_mode_atomically_switches_approval_contract_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ops = HepiOpsCore(Path(directory))
            policy = ops.save_autotrade_policy({"live_execution_control_mode": "delegated_auto"})
            restored = HepiOpsCore(Path(directory)).autotrade_policy()
        for current in (policy, restored):
            self.assertEqual(current["live_execution_control_mode"], "delegated_auto")
            self.assertFalse(current["require_approval"])
            self.assertTrue(current["delegated_live_autonomy_enabled"])
            self.assertFalse(current["live_execution_enabled"])

    def test_manual_mode_clears_stale_delegation_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            ops = HepiOpsCore(Path(directory))
            ops.save_autotrade_policy({
                "live_execution_control_mode": "delegated_auto",
                "delegated_live_authorization_confirmed": True,
                "delegated_live_authorized_date": "2026-07-20",
            })
            policy = ops.save_autotrade_policy({"live_execution_control_mode": "manual_approval"})
        self.assertTrue(policy["require_approval"])
        self.assertFalse(policy["delegated_live_autonomy_enabled"])
        self.assertFalse(policy["delegated_live_authorization_confirmed"])
        self.assertEqual(policy["delegated_live_authorized_date"], "")

    def test_invalid_mode_is_rejected_without_persisting(self):
        with tempfile.TemporaryDirectory() as directory:
            ops = HepiOpsCore(Path(directory))
            with self.assertRaisesRegex(ValueError, "invalid_live_execution_control_mode"):
                ops.save_autotrade_policy({"live_execution_control_mode": "unrestricted"})
            restored = ops.autotrade_policy()
        self.assertEqual(restored["live_execution_control_mode"], "manual_approval")

    def test_legacy_delegated_flags_migrate_to_canonical_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            ops = HepiOpsCore(Path(directory))
            ops.autotrade_policy_file.parent.mkdir(parents=True, exist_ok=True)
            ops.autotrade_policy_file.write_text(json.dumps({
                "delegated_live_autonomy_enabled": True,
                "require_approval": False,
                "live_execution_enabled": False,
            }), encoding="utf-8")
            policy = ops.autotrade_policy()
        self.assertEqual(policy["live_execution_control_mode"], "delegated_auto")
        self.assertFalse(policy["require_approval"])
        self.assertTrue(policy["delegated_live_autonomy_enabled"])

    def test_delegated_mode_publishes_signed_executor_signal_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            ops = HepiOpsCore(Path(directory))
            policy = ops.save_autotrade_policy({"live_execution_control_mode": "delegated_auto"})
            ticket = ops.create_order(
                symbol="005930",
                side="BUY",
                quantity=1,
                price=1000,
                mode="live_candidate",
                source="test",
                request_approval=False,
                metadata={"strategy_id": "test-strategy"},
            )
        self.assertEqual("standing", policy["delegated_live_authorization_mode"])
        self.assertEqual("DELEGATED_SIGNAL_READY", ticket["status"])
        self.assertNotIn("approval_token", ticket)
        self.assertTrue(ticket["shadow_signal"]["published"])

    def test_approval_gate_contract_accepts_both_supported_modes(self):
        delegated_ok, delegated_detail = _approval_gate_contract({
            "live_execution_control_mode": "delegated_auto",
            "delegated_live_autonomy_enabled": True,
            "require_approval": False,
        })
        manual_ok, manual_detail = _approval_gate_contract({
            "live_execution_control_mode": "manual_approval",
            "require_approval": True,
        })
        self.assertTrue(delegated_ok)
        self.assertIn("서명 신호", delegated_detail)
        self.assertTrue(manual_ok)
        self.assertIn("승인 토큰", manual_detail)


if __name__ == "__main__":
    unittest.main()

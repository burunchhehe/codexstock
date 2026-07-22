import unittest

from app import stock_suite_app as suite


def delegated_policy():
    return {
        "live_execution_control_mode": "delegated_auto",
        "delegated_live_autonomy_enabled": True,
        "delegated_live_authorization_mode": "standing",
        "require_approval": False,
        "live_pilot_enabled": True,
        "live_execution_enabled": True,
        "emergency_halt": False,
        "day_halted": False,
    }


class ExecutionModeContractTests(unittest.TestCase):
    def test_delegated_runtime_is_ready_only_when_every_surface_matches(self):
        contract = suite.build_execution_mode_contract(
            delegated_policy(),
            sidecar_mode="live",
            supervisor_mode="live",
            sidecar_real_order_supported=True,
            sidecar_ok=True,
            supervisor_state="MONITORING",
            live_executor_enabled=True,
            require_runtime_evidence=True,
        )
        self.assertTrue(contract["policy_consistent"])
        self.assertTrue(contract["mode_consistent"])
        self.assertTrue(contract["live_path_ready"])
        self.assertFalse(contract["requires_user_approval"])
        self.assertEqual("DELEGATED_AUTO_READY", contract["state"])

    def test_supervisor_mode_mismatch_fails_closed(self):
        contract = suite.build_execution_mode_contract(
            delegated_policy(),
            sidecar_mode="live",
            supervisor_mode="shadow",
            sidecar_real_order_supported=True,
            sidecar_ok=True,
            supervisor_state="MODE_MISMATCH",
            live_executor_enabled=True,
            require_runtime_evidence=True,
        )
        self.assertFalse(contract["mode_consistent"])
        self.assertFalse(contract["live_path_ready"])
        self.assertIn("supervisor_mode_mismatch", contract["runtime_conflicts"])
        self.assertIn("sidecar_supervisor_mode_mismatch", contract["runtime_conflicts"])
        self.assertIn("supervisor_not_monitoring", contract["runtime_conflicts"])

    def test_missing_runtime_evidence_cannot_enable_live_path(self):
        contract = suite.build_execution_mode_contract(
            delegated_policy(),
            live_executor_enabled=True,
            require_runtime_evidence=True,
        )
        self.assertFalse(contract["live_path_ready"])
        self.assertIn("sidecar_mode_unverified", contract["runtime_conflicts"])
        self.assertIn("supervisor_mode_unverified", contract["runtime_conflicts"])
        self.assertIn("sidecar_not_healthy", contract["runtime_conflicts"])

    def test_conflicting_policy_fails_closed(self):
        policy = delegated_policy()
        policy["require_approval"] = True
        contract = suite.build_execution_mode_contract(policy)
        self.assertFalse(contract["policy_consistent"])
        self.assertFalse(contract["live_path_ready"])
        self.assertIn(
            "delegated_mode_cannot_require_per_order_approval",
            contract["policy_conflicts"],
        )

    def test_manual_mode_keeps_approval_contract(self):
        policy = {
            "live_execution_control_mode": "manual_approval",
            "delegated_live_autonomy_enabled": False,
            "require_approval": True,
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
        }
        contract = suite.build_execution_mode_contract(policy)
        self.assertTrue(contract["policy_consistent"])
        self.assertTrue(contract["requires_user_approval"])
        self.assertTrue(contract["live_path_ready"])
        self.assertEqual("shadow", contract["desired_sidecar_mode"])

    def test_startup_supervisor_uses_live_only_for_valid_delegated_policy(self):
        contract = suite.build_startup_execution_mode_contract(delegated_policy())

        self.assertEqual("live", contract["desired_sidecar_mode"])
        self.assertEqual("live", contract["supervisor_launch_mode"])
        self.assertTrue(contract["live_executor_capability_enabled"])
        self.assertEqual(
            "bundled_execution_sidecar_supervisor",
            contract["startup_capability_source"],
        )

    def test_startup_supervisor_falls_back_to_shadow_when_halted(self):
        policy = delegated_policy()
        policy["emergency_halt"] = True

        contract = suite.build_startup_execution_mode_contract(policy)

        self.assertEqual("shadow", contract["desired_sidecar_mode"])
        self.assertEqual("shadow", contract["supervisor_launch_mode"])

    def test_startup_supervisor_falls_back_to_shadow_for_manual_mode(self):
        policy = {
            "live_execution_control_mode": "manual_approval",
            "delegated_live_autonomy_enabled": False,
            "require_approval": True,
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
        }

        contract = suite.build_startup_execution_mode_contract(policy)

        self.assertEqual("shadow", contract["desired_sidecar_mode"])
        self.assertEqual("shadow", contract["supervisor_launch_mode"])


if __name__ == "__main__":
    unittest.main()

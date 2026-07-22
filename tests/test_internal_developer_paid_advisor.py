import tempfile
import unittest
from pathlib import Path

from app.internal_developer_paid_advisor import PaidAdvisorGate


class PaidAdvisorGateTests(unittest.TestCase):
    def test_request_requires_failed_recovery_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = PaidAdvisorGate(Path(directory))
            with self.assertRaisesRegex(ValueError, "attempts_insufficient"):
                gate.request(
                    incident_id="INC-1",
                    incident_state="NEEDS_EXTERNAL_ADVICE",
                    self_recovery_attempts=1,
                    diagnostic_bundle={},
                )
            record = gate.request(
                incident_id="INC-1",
                incident_state="NEEDS_EXTERNAL_ADVICE",
                self_recovery_attempts=2,
                diagnostic_bundle={"error": "timeout", "api_key": "secret", "nested": {"token": "secret"}},
            )
        self.assertEqual("[REDACTED]", record["diagnostic_bundle"]["api_key"])
        self.assertEqual("[REDACTED]", record["diagnostic_bundle"]["nested"]["token"])
        self.assertFalse(record["execution_authorized"])

    def test_invoke_requires_explicit_approval_and_enforces_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = PaidAdvisorGate(Path(directory), max_incident_budget_krw=5000)
            request = gate.request(
                incident_id="INC-2",
                incident_state="RECOVERY_FAILED",
                self_recovery_attempts=3,
                diagnostic_bundle={"error": "db locked"},
            )
            with self.assertRaisesRegex(ValueError, "not_approved"):
                gate.invoke(request["request_id"], estimated_cost_krw=100, advisor=lambda _: {})
            gate.approve(request["request_id"], approved_by="owner", budget_krw=1000)
            with self.assertRaisesRegex(ValueError, "budget_exceeded"):
                gate.invoke(request["request_id"], estimated_cost_krw=1001, advisor=lambda _: {})
            result = gate.invoke(
                request["request_id"],
                estimated_cost_krw=500,
                advisor=lambda payload: {
                    "summary": "restart the bounded worker",
                    "received_incident": payload["incident_id"],
                    "app_secret": "must-not-store",
                },
            )
        self.assertEqual("ADVICE_QUARANTINED", result["status"])
        self.assertEqual(500, result["used_budget_krw"])
        self.assertEqual("[REDACTED]", result["advisor_result"]["app_secret"])
        self.assertFalse(result["code_edit_authorized"])
        self.assertFalse(result["live_order_allowed"])

    def test_request_is_idempotent_for_same_incident_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = PaidAdvisorGate(Path(directory))
            first = gate.request(
                incident_id="INC-3",
                incident_state="NEEDS_CODE_FIX",
                self_recovery_attempts=2,
                diagnostic_bundle={"failure": "same"},
            )
            second = gate.request(
                incident_id="INC-3",
                incident_state="NEEDS_CODE_FIX",
                self_recovery_attempts=2,
                diagnostic_bundle={"failure": "same"},
            )
        self.assertEqual(first["request_id"], second["request_id"])

    def test_launcher_status_exposes_paid_advisor_without_execution_authority(self):
        from app import stock_suite_app as stock_app

        with tempfile.TemporaryDirectory() as directory:
            result = stock_app.build_internal_developer_launcher_status(Path(directory))
        paid = result["paid_advisor"]
        self.assertEqual(0, paid["request_count"])
        self.assertEqual(5000, paid["max_incident_budget_krw"])
        self.assertFalse(paid["execution_authorized"])
        self.assertFalse(paid["live_order_allowed"])


if __name__ == "__main__":
    unittest.main()

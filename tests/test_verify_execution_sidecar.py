import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "verify_execution_sidecar.py"
SPEC = importlib.util.spec_from_file_location("verify_execution_sidecar", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def status_payload(*, complete: bool = False) -> dict[str, object]:
    return {
        "ok": True,
        "mode": "shadow",
        "runtime_session_id": "session-1",
        "runtime_process": {"process_id": 42, "process_alive": True, "status_fresh": True},
        "supervisor": {"state": "MONITORING"},
        "validation_proof": {
            "operational_ok": True,
            "proof_complete": complete,
            "observation_hours": 24.0 if complete else 1.0,
            "required_observation_hours": 24.0,
            "qualifying_result_count": 10 if complete else 0,
            "required_result_count": 10,
            "observed_symbol_count": 2 if complete else 0,
            "required_symbol_count": 2,
            "checks": {"heartbeat_fresh": True, "no_real_order_submission": True},
        },
        "real_order_supported": False,
    }


class VerifyExecutionSidecarTests(unittest.TestCase):
    def test_operational_mode_passes_before_time_proof(self):
        report = MODULE.evaluate(status_payload(), require_complete=False)
        self.assertTrue(report["ok"])

    def test_completion_mode_requires_time_and_coverage(self):
        report = MODULE.evaluate(status_payload(), require_complete=True)
        self.assertFalse(report["ok"])
        self.assertIn("long_run_and_coverage_complete", report["failures"])

    def test_real_order_capability_always_fails_verification(self):
        payload = status_payload(complete=True)
        payload["real_order_supported"] = True
        report = MODULE.evaluate(payload, require_complete=True)
        self.assertFalse(report["ok"])
        self.assertIn("real_order_disabled", report["failures"])

    def test_failed_embedded_check_is_exposed(self):
        payload = status_payload()
        payload["validation_proof"]["checks"]["source_hash_parity"] = False
        report = MODULE.evaluate(payload)
        self.assertFalse(report["ok"])
        self.assertEqual(report["failed_embedded_checks"], ["source_hash_parity"])


if __name__ == "__main__":
    unittest.main()

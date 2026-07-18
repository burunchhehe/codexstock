import unittest
from unittest.mock import patch

from app.stock_suite_app import _marketwide_intraday_candidate_pool, _verified_external_signal_candidates


class ExternalSignalRadarCandidateTests(unittest.TestCase):
    def test_verified_external_signals_enter_watch_candidate_pool_only(self):
        inbox = {
        "current_source_usable": True,
        "report_signature": "sig-1",
        "report": {
            "signals": [
                {
                    "symbol": "042660",
                    "name": "Hanwha Ocean",
                    "theme": "shipbuilding",
                    "confidence": 0.84,
                    "urgency": "urgent",
                    "source_count": 52,
                },
                {"symbol": "000660", "confidence": 0.7},
            ]
        },
        "verification_queue": {
            "recent_requests": [
                {
                    "symbol": "042660",
                    "report_signature": "sig-1",
                    "status": "SNAPSHOT_VERIFIED_PENDING_STAGE2_RESULT",
                    "snapshot_validation": {"passed": True},
                },
                {
                    "symbol": "000660",
                    "report_signature": "sig-1",
                    "status": "SNAPSHOT_BLOCKED",
                    "snapshot_validation": {"passed": False},
                },
            ]
        },
        }
        stage2_queue = {
            "jobs": [
                {
                    "symbol": "042660",
                    "stage2_job_id": "external-signal-stage2:042660:contract-1",
                    "contract_hash_prefix": "0123456789ab",
                    "candidate_pool_allowed": True,
                    "accepted_result": {
                        "external_engine_name": "nautilustrader",
                        "validation_grade": "A",
                    },
                }
            ]
        }
        with (
            patch("app.stock_suite_app.external_signal_inbox_status", return_value=inbox),
            patch("app.stock_suite_app.build_external_signal_stage2_queue", return_value=stage2_queue),
        ):
            candidates = _verified_external_signal_candidates()

        self.assertEqual(["042660"], [row["symbol"] for row in candidates])
        self.assertIs(candidates[0]["candidate_pool_only"], True)
        self.assertIs(candidates[0]["score_allowed"], False)
        self.assertIs(candidates[0]["live_order_allowed"], False)
        self.assertEqual("nautilustrader", candidates[0]["stage2_engine"])
        self.assertEqual("A", candidates[0]["stage2_validation_grade"])

    def test_unusable_external_source_cannot_enter_radar_pool(self):
        with patch(
            "app.stock_suite_app.external_signal_inbox_status",
            return_value={"current_source_usable": False, "report": {"signals": [{"symbol": "042660"}]}},
        ):
            self.assertEqual([], _verified_external_signal_candidates())

    def test_marketwide_pool_prefers_actionable_non_limit_up_names(self):
        pulse = {
            "ok": True,
            "items": [
                {"symbol": "035610", "price": 4320, "change_pct": 6.9, "pulse_score": 87, "rapid_score": 0},
                {"symbol": "006340", "price": 12750, "change_pct": 17.8, "pulse_score": 64, "rapid_score": 0},
                {"symbol": "089230", "price": 1950, "change_pct": 30, "pulse_score": 78, "rapid_score": 0},
                {"symbol": "477850", "price": 27650, "change_pct": 12.4, "pulse_score": 58, "rapid_score": 0},
            ],
        }

        candidates = _marketwide_intraday_candidate_pool(pulse=pulse)

        self.assertEqual("035610", candidates[0]["symbol"])
        self.assertIn("006340", [row["symbol"] for row in candidates])
        self.assertIn("477850", [row["symbol"] for row in candidates])
        self.assertNotIn("089230", [row["symbol"] for row in candidates])
        self.assertIs(candidates[0]["live_order_allowed"], False)


if __name__ == "__main__":
    unittest.main()

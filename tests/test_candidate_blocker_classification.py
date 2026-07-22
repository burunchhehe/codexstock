import unittest

from app import stock_suite_app as suite


class CandidateBlockerClassificationTests(unittest.TestCase):
    def test_blockers_are_split_into_risk_data_and_system_classes(self):
        self.assertEqual(
            "NORMAL_RISK_BLOCK",
            suite._candidate_blocker_classification(
                {"label": "spread", "detail": "spread exceeded 0.5 percent"}
            ),
        )
        self.assertEqual(
            "DATA_UNAVAILABLE",
            suite._candidate_blocker_classification(
                {"label": "quote", "detail": "data unavailable"}
            ),
        )
        self.assertEqual(
            "SYSTEM_BOTTLENECK",
            suite._candidate_blocker_classification(
                {"label": "mode contract", "detail": "pipeline handoff mismatch"}
            ),
        )

    def test_decision_report_persists_blocker_evidence(self):
        report = suite.build_live_candidate_decision_report(
            {
                "generated_at": "2026-07-21T10:00:00+09:00",
                "symbol": "005930",
                "name": "Samsung Electronics",
                "side": "BUY",
                "candidate_ready": False,
                "broker_submit_ready": False,
                "checks": [
                    {
                        "label": "quote",
                        "status": "blocked",
                        "detail": "data unavailable",
                    }
                ],
                "selection": {
                    "symbol": "005930",
                    "name": "Samsung Electronics",
                    "score": 80,
                },
                "learning_evidence_gate": {"ok": True},
            }
        )
        checks = report["checks_summary"]
        self.assertEqual("DATA_UNAVAILABLE", checks["blocker_classification"]["primary"])
        self.assertEqual("data unavailable", checks["blocker_details"][0]["detail"])


if __name__ == "__main__":
    unittest.main()

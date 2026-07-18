import unittest

from app.stock_suite_app import (
    _build_maturity_implementation_health,
    _select_maturity_tournament_evidence,
)


class MaturityImplementationHealthTests(unittest.TestCase):
    def test_full_implementation_health_is_100(self) -> None:
        result = _build_maturity_implementation_health(
            {
                "score": 100,
                "normal_count": 35,
                "total": 35,
                "surface_coverage": {
                    "coverage_pct": 100,
                    "covered_count": 392,
                    "total_count": 392,
                },
                "external_engine_health": {
                    "monitored_count": 9,
                    "operational_counts": {"normal": 9},
                },
            }
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(len(result["components"]), 3)

    def test_health_uses_live_coverage_instead_of_activity_counts(self) -> None:
        result = _build_maturity_implementation_health(
            {
                "score": 80,
                "normal_count": 28,
                "total": 35,
                "surface_coverage": {
                    "coverage_pct": 90,
                    "covered_count": 353,
                    "total_count": 392,
                },
                "external_engine_health": {
                    "monitored_count": 5,
                    "operational_counts": {"normal": 3},
                },
            }
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["score"], 79.0)
        self.assertIn("시간 경과", result["message"])

    def test_validation_evidence_survives_empty_official_champion(self) -> None:
        selected = _select_maturity_tournament_evidence(
            {
                "champion": {},
                "shadow_validation": {"ok": True, "passed": True, "status": "블라인드 통과"},
                "rankings": [
                    {
                        "competition_gate": {"shadow_passed": True},
                        "monte_carlo_stress": {
                            "ok": True,
                            "passed": False,
                            "status": "스트레스 취약",
                        },
                    }
                ],
            }
        )

        self.assertTrue(selected["shadow_validation"]["passed"])
        self.assertTrue(selected["gate"]["shadow_passed"])
        self.assertTrue(selected["stress"]["ok"])
        self.assertFalse(selected["stress"]["passed"])


if __name__ == "__main__":
    unittest.main()

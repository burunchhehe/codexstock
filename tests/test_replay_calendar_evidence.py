import unittest

from app.replay_calendar_evidence import (
    build_calendar_adjacency_proof,
    calendar_adjacency_root,
    verify_calendar_adjacency_proof,
)


class ReplayCalendarEvidenceTests(unittest.TestCase):
    def test_proof_binds_adjacent_symbol_bars_across_calendar_gap(self):
        dates = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-09"]
        proof = build_calendar_adjacency_proof("005930", dates, 3)

        self.assertEqual(calendar_adjacency_root("005930", dates), proof["symbol_calendar_root"])
        self.assertEqual("2026-01-06", proof["decision_symbol_bar_date"])
        self.assertEqual("2026-01-09", proof["execution_symbol_bar_date"])
        self.assertTrue(
            verify_calendar_adjacency_proof(
                proof,
                expected_symbol="005930",
                expected_root=calendar_adjacency_root("005930", dates),
            )
        )

    def test_date_index_root_and_merkle_tampering_are_rejected(self):
        dates = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-09"]
        proof = build_calendar_adjacency_proof("005930", dates, 2)
        mutations = (
            {"execution_symbol_bar_date": "2026-01-07"},
            {"execution_symbol_bar_index": 3},
            {"symbol_calendar_root": "0" * 64},
            {"symbol_calendar_adjacency_proof": []},
        )
        for mutation in mutations:
            self.assertFalse(
                verify_calendar_adjacency_proof({**proof, **mutation}, expected_symbol="005930"),
                mutation,
            )


if __name__ == "__main__":
    unittest.main()

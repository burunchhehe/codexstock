import tempfile
import unittest
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from stock_suite.shadow_candidate_scheduler import eligible_shadow_candidates, run_shadow_candidate_tick


class ShadowCandidateSchedulerTests(unittest.TestCase):
    def test_only_upstream_passed_korean_candidates_are_eligible(self):
        rows = eligible_shadow_candidates([
            {"symbol": "005930", "gate": "PASSED"},
            {"symbol": "000660", "gate": "BLOCKED"},
            {"symbol": "AAPL", "gate": "PASSED"},
            {"symbol": "083450", "risk_gate_status": "PASSED"},
            {"symbol": "042700", "gate": "REVIEW"},
        ])
        self.assertEqual([row["symbol"] for row in rows], ["005930", "083450"])

    def test_state_write_retries_transient_windows_reader_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            real_replace = os.replace
            attempts = []

            def flaky_replace(source, destination):
                attempts.append(1)
                if len(attempts) == 1:
                    raise PermissionError("transient reader lock")
                return real_replace(source, destination)

            with patch("stock_suite.shadow_candidate_scheduler.os.replace", side_effect=flaky_replace):
                result = run_shadow_candidate_tick(
                    state_file=state_file, market_open=False, candidates=[],
                    create_candidate=lambda row: {},
                    now=datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc),
                )
            stored = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "MARKET_CLOSED")
        self.assertEqual(stored["last_status"], "MARKET_CLOSED")
        self.assertEqual(len(attempts), 2)

    def test_market_closed_never_creates_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            result = run_shadow_candidate_tick(
                state_file=Path(directory) / "state.json",
                market_open=False,
                candidates=[{"symbol": "005930"}],
                create_candidate=lambda row: calls.append(row),
                now=datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc),
            )
            state_exists = (Path(directory) / "state.json").exists()
        self.assertEqual(result["status"], "MARKET_CLOSED")
        self.assertEqual(calls, [])
        self.assertFalse(result["real_order_allowed"])
        self.assertTrue(state_exists)

    def test_persists_cadence_rotates_symbols_and_enforces_daily_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            now = datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc)
            calls = []

            def create(row):
                calls.append(row["symbol"])
                return {
                    "id": f"TIC-{len(calls)}",
                    "risk_status": "PASSED",
                    "shadow_signal": {"published": True, "signal_id": f"TIC-{len(calls)}"},
                }

            first = run_shadow_candidate_tick(
                state_file=state_file, market_open=True,
                candidates=[{"symbol": "005930"}, {"symbol": "000660"}],
                create_candidate=create, now=now, cadence_seconds=1800, max_per_day=2,
            )
            waiting = run_shadow_candidate_tick(
                state_file=state_file, market_open=True,
                candidates=[{"symbol": "005930"}, {"symbol": "000660"}],
                create_candidate=create, now=now + timedelta(minutes=5), cadence_seconds=1800, max_per_day=2,
            )
            second = run_shadow_candidate_tick(
                state_file=state_file, market_open=True,
                candidates=[{"symbol": "005930"}, {"symbol": "000660"}],
                create_candidate=create, now=now + timedelta(minutes=31), cadence_seconds=1800, max_per_day=2,
            )
            limited = run_shadow_candidate_tick(
                state_file=state_file, market_open=True,
                candidates=[{"symbol": "005930"}, {"symbol": "000660"}],
                create_candidate=create, now=now + timedelta(minutes=62), cadence_seconds=1800, max_per_day=2,
            )

        self.assertTrue(first["published"])
        self.assertEqual(waiting["status"], "CADENCE_WAIT")
        self.assertTrue(second["published"])
        self.assertEqual(calls, ["005930", "000660"])
        self.assertEqual(second["observed_symbols"], ["005930", "000660"])
        self.assertEqual(limited["status"], "DAILY_EVIDENCE_LIMIT_REACHED")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

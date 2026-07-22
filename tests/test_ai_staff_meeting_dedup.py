import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app import stock_suite_app as suite


class AiStaffMeetingDedupTests(unittest.TestCase):
    def test_automatic_quick_source_is_classified_as_automatic(self):
        self.assertEqual(
            "auto",
            suite._staff_meeting_latest_group("autopilot-scheduler-autopilot-quick"),
        )
        self.assertEqual("manual", suite._staff_meeting_latest_group("manual-quick"))

    def test_recent_matching_automatic_meeting_is_duplicate(self):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        previous = {
            "id": "MEET-1",
            "created_at": (now - timedelta(minutes=5)).isoformat(timespec="seconds"),
            "source": "autopilot-scheduler-autopilot-quick",
            "signature": "same-signature",
            "note": {"source_group": "auto"},
        }
        current = {
            "id": "MEET-2",
            "source": "autopilot-scheduler-autopilot-quick",
            "signature": "same-signature",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ai_staff_meetings.jsonl"
            path.write_text(json.dumps(previous) + "\n", encoding="utf-8")
            with patch.object(suite, "AI_STAFF_MEETING_FILE", path):
                duplicate = suite._recent_duplicate_auto_staff_meeting(current)

        self.assertEqual("MEET-1", duplicate["id"])

    def test_manual_or_stale_meeting_is_not_duplicate(self):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        previous = {
            "id": "MEET-1",
            "created_at": (now - timedelta(minutes=31)).isoformat(timespec="seconds"),
            "source": "autopilot-daemon",
            "signature": "same-signature",
            "note": {"source_group": "auto"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ai_staff_meetings.jsonl"
            path.write_text(json.dumps(previous) + "\n", encoding="utf-8")
            with patch.object(suite, "AI_STAFF_MEETING_FILE", path):
                stale = suite._recent_duplicate_auto_staff_meeting(
                    {"source": "autopilot-daemon", "signature": "same-signature"}
                )
                manual = suite._recent_duplicate_auto_staff_meeting(
                    {"source": "manual-quick", "signature": "same-signature"}
                )

        self.assertEqual({}, stale)
        self.assertEqual({}, manual)


if __name__ == "__main__":
    unittest.main()

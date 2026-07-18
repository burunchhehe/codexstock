import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.integrations import FredBridge


class FredReleaseDatesTests(unittest.TestCase):
    @patch("app.integrations._fetch_json")
    def test_release_dates_keep_date_precision_and_official_source(self, fetch_json):
        fetch_json.return_value = (
            {
                "release_dates": [
                    {"release_id": 10, "release_name": "Consumer Price Index", "date": "2026-07-14"}
                ]
            },
            False,
        )
        settings = SimpleNamespace(fred_configured=True, fred_api_key="secret", fred_cache_ttl_sec=300)
        result = FredBridge(settings).release_dates(start="2026-07-14", end="2026-07-20")
        self.assertTrue(result["ok"])
        row = result["rows"][0]
        self.assertEqual("2026-07-14", row["observed_at"])
        self.assertEqual("date_only", row["time_precision"])
        self.assertEqual("FRED release dates", row["source"])
        self.assertTrue(row["verified"])
        called_url = fetch_json.call_args.args[0]
        self.assertIn("/releases/dates?", called_url)
        self.assertIn("realtime_start=2026-07-14", called_url)

    def test_unconfigured_bridge_does_not_invent_calendar(self):
        settings = SimpleNamespace(fred_configured=False, fred_api_key="", fred_cache_ttl_sec=300)
        result = FredBridge(settings).release_dates()
        self.assertFalse(result["ok"])
        self.assertFalse(result.get("query_ok", False))
        self.assertEqual([], result["rows"])

    @patch("app.integrations._fetch_json")
    def test_empty_official_response_marks_query_ok(self, fetch_json):
        fetch_json.return_value = ({"release_dates": []}, False)
        settings = SimpleNamespace(fred_configured=True, fred_api_key="secret", fred_cache_ttl_sec=300)

        result = FredBridge(settings).release_dates(start="2026-07-14", end="2026-07-20")

        self.assertFalse(result["ok"])
        self.assertTrue(result["query_ok"])
        self.assertTrue(result["configured"])
        self.assertEqual([], result["rows"])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from app import stock_suite_app as suite


class FullChartHistoryTests(unittest.TestCase):
    def setUp(self):
        suite.FULL_CHART_HISTORY_CACHE.clear()

    def test_full_chart_history_uses_real_adjusted_daily_rows(self):
        rows = [
            {
                "date": f"2024-{month:02d}-{day:02d}",
                "close": float(month * 100 + day),
                "adjusted_close": float(month * 100 + day + 1),
            }
            for month in range(1, 4)
            for day in range(1, 11)
        ]
        with patch.object(
            suite,
            "_fetch_yahoo_chart_range",
            return_value={"source": "Yahoo chart:AAPL", "rows": rows},
        ):
            payload = suite.full_chart_history("AAPL", start_date="1970-01-01", end_date="2026-07-19")

        self.assertTrue(payload["ok"])
        self.assertEqual(30, payload["bars"])
        self.assertEqual("2024-01-01", payload["actual_start_date"])
        self.assertEqual(102.0, payload["history"][0])
        self.assertEqual("real", payload["data_mode"])
        self.assertEqual("adjusted_close_when_available", payload["price_basis"])


if __name__ == "__main__":
    unittest.main()

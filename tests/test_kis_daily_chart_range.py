from datetime import date, timedelta
from types import SimpleNamespace
import unittest

from app.integrations import KisReadonlyBridge


def _bridge_with_pages(pages):
    bridge = object.__new__(KisReadonlyBridge)
    bridge.settings = SimpleNamespace(kis_quote_throttle_ms=0, kis_mode="real")
    calls = []

    def daily_chart(**kwargs):
        calls.append(kwargs)
        return pages[len(calls) - 1]

    bridge.daily_chart = daily_chart
    return bridge, calls


def _descending_rows(end_day: date, count: int):
    return [
        {
            "date": (end_day - timedelta(days=index)).isoformat(),
            "close": float(1000 - index),
            "adjusted_close": float(1000 - index),
        }
        for index in range(count)
    ]


class KisDailyChartRangeTests(unittest.TestCase):
    def test_walks_back_and_deduplicates_rows(self):
        first = _descending_rows(date(2020, 4, 10), 100)
        second = _descending_rows(date(2020, 1, 1), 32)
        second.append(dict(second[0]))
        bridge, calls = _bridge_with_pages(
            [
                {"ok": True, "rows": first},
                {"ok": True, "rows": second},
            ]
        )

        result = bridge.daily_chart_range("005930", "2019-12-01", "2020-04-10", max_pages=5)

        self.assertTrue(result["ok"])
        self.assertTrue(result["range_complete"])
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["provider"], "KIS_adjusted_verified")
        self.assertEqual(len({row["date"] for row in result["rows"]}), len(result["rows"]))
        self.assertLess(calls[1]["end_date"], calls[0]["end_date"])

    def test_blocks_partial_pages_after_request_failure(self):
        bridge, _ = _bridge_with_pages(
            [
                {"ok": True, "rows": _descending_rows(date(2020, 4, 10), 100)},
                {"ok": False, "rows": [], "message": "rate limited"},
            ]
        )

        result = bridge.daily_chart_range("005930", "2019-12-01", "2020-04-10", max_pages=5)

        self.assertFalse(result["ok"])
        self.assertFalse(result["range_complete"])
        self.assertEqual(result["stop_reason"], "page_request_failed")
        self.assertTrue(result["rows"])

    def test_blocks_cursor_that_does_not_advance(self):
        page = _descending_rows(date(2020, 4, 10), 100)
        bridge, _ = _bridge_with_pages(
            [
                {"ok": True, "rows": page},
                {"ok": True, "rows": page},
            ]
        )

        result = bridge.daily_chart_range("005930", "2019-12-01", "2020-04-10", max_pages=5)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "page_cursor_did_not_advance")


if __name__ == "__main__":
    unittest.main()

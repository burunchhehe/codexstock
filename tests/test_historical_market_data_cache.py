import sqlite3
import tempfile
import unittest
import os
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.historical_market_data_cache import HistoricalMarketDataCache
from app import stock_suite_app as suite


class HistoricalMarketDataCacheTests(unittest.TestCase):
    def test_exact_contract_round_trip_preserves_payload_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = HistoricalMarketDataCache(Path(temp_dir) / "cache.sqlite3")
            contract = {"symbol": "AAPL", "start_date": "2024-01-01", "end_date": "2024-02-01"}
            payload = {"source": "yahoo_chart", "rows": [{"date": "2024-01-02", "close": 100.0}]}

            stored = cache.store(contract, payload, ttl_seconds=3600, now_epoch=1000)
            loaded = cache.load(contract, now_epoch=1001)

        self.assertTrue(stored["stored"])
        self.assertTrue(loaded["hit"])
        self.assertEqual(payload, loaded["payload"])
        self.assertEqual(stored["payload_sha256"], loaded["payload_sha256"])

    def test_status_proves_persistent_cache_reuse(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = HistoricalMarketDataCache(Path(temp_dir) / "cache.sqlite3")
            first_contract = {"symbol": "AAPL", "start_date": "2024-01-01"}
            second_contract = {"symbol": "MSFT", "start_date": "2024-01-01"}
            cache.store(first_contract, {"rows": [{"close": 100.0}]}, ttl_seconds=3600, now_epoch=1000)
            cache.store(second_contract, {"rows": [{"close": 200.0}]}, ttl_seconds=3600, now_epoch=1000)

            cache.load(first_contract, now_epoch=1001)
            cache.load(first_contract, now_epoch=1002)
            status = cache.status()

        self.assertTrue(status["reuse_verified"])
        self.assertEqual(2, status["total_hit_count"])
        self.assertEqual(1, status["reused_entry_count"])
        self.assertEqual("1970-01-01T00:16:42+00:00", status["last_hit_at"])
        self.assertEqual("1970-01-01T00:16:40+00:00", status["last_write_at"])

    def test_v1_database_is_migrated_without_losing_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cache.sqlite3"
            legacy = HistoricalMarketDataCache(path)
            contract = {"symbol": "AAPL"}
            payload = {"rows": [{"close": 100.0}]}
            cache_key, contract_json = legacy._key(contract)
            payload_bytes = legacy._canonical(payload)
            import hashlib
            import zlib

            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE historical_market_data_cache (
                        cache_key TEXT PRIMARY KEY,
                        schema_version TEXT NOT NULL,
                        contract_json TEXT NOT NULL,
                        payload_zlib BLOB NOT NULL,
                        payload_sha256 TEXT NOT NULL,
                        stored_at_epoch REAL NOT NULL,
                        expires_at_epoch REAL NOT NULL,
                        last_access_epoch REAL NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO historical_market_data_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        cache_key,
                        "codexstock_historical_market_data_cache_v1",
                        contract_json,
                        sqlite3.Binary(zlib.compress(payload_bytes)),
                        hashlib.sha256(payload_bytes).hexdigest(),
                        1000,
                        4600,
                        1000,
                    ),
                )
                connection.commit()

            loaded = HistoricalMarketDataCache(path).load(contract, now_epoch=1001)
            status = HistoricalMarketDataCache(path).status()

        self.assertTrue(loaded["hit"])
        self.assertEqual(payload, loaded["payload"])
        self.assertEqual("codexstock_historical_market_data_cache_v2", status["schema"])
        self.assertEqual(1, status["total_hit_count"])

    def test_contract_mismatch_and_expiry_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = HistoricalMarketDataCache(Path(temp_dir) / "cache.sqlite3")
            contract = {"symbol": "AAPL", "start_date": "2024-01-01", "end_date": "2024-02-01"}
            cache.store(contract, {"rows": [{"date": "2024-01-02", "close": 100.0}]}, ttl_seconds=60, now_epoch=1000)

            mismatch = cache.load({**contract, "symbol": "MSFT"}, now_epoch=1001)
            expired = cache.load(contract, now_epoch=1061)

        self.assertFalse(mismatch["hit"])
        self.assertEqual("cache_miss", mismatch["status"])
        self.assertFalse(expired["hit"])
        self.assertEqual("cache_invalidated", expired["status"])

    def test_payload_hash_tampering_is_invalidated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cache.sqlite3"
            cache = HistoricalMarketDataCache(path)
            contract = {"symbol": "AAPL"}
            cache.store(contract, {"rows": [{"date": "2024-01-02", "close": 100.0}]}, ttl_seconds=3600, now_epoch=1000)
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "UPDATE historical_market_data_cache SET payload_sha256 = ?",
                    ("0" * 64,),
                )
                connection.commit()

            loaded = cache.load(contract, now_epoch=1001)
            second = cache.load(contract, now_epoch=1002)

        self.assertFalse(loaded["hit"])
        self.assertEqual("cache_hash_invalidated", loaded["status"])
        self.assertEqual("cache_miss", second["status"])

    def test_historical_close_rows_reuses_sqlite_after_memory_cache_is_cleared(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = HistoricalMarketDataCache(Path(temp_dir) / "cache.sqlite3")
            dates = suite._business_dates("2024-01-01", "2024-03-31", min_days=40)
            rows = [
                {"date": date_key, "close": 100.0 + index, "volume": 1000 + index}
                for index, date_key in enumerate(dates)
            ]
            upstream = {
                "ok": True,
                "source": "yahoo_chart",
                "provider": "Yahoo",
                "rows": rows,
            }
            suite.HISTORICAL_CLOSE_ROWS_CACHE.clear()
            with (
                patch.dict(os.environ, {"CODEXSTOCK_HISTORICAL_CACHE_ENABLE": "1"}),
                patch.object(suite, "HISTORICAL_MARKET_DATA_CACHE", cache),
                patch.object(suite, "_yahoo_symbol_candidates", return_value=["AAPL"]),
                patch.object(suite, "_fetch_yahoo_chart_range", return_value=upstream) as fetch,
            ):
                first = suite._historical_close_rows("AAPL", "2024-01-01", "2024-03-31")
                suite.HISTORICAL_CLOSE_ROWS_CACHE.clear()
                second = suite._historical_close_rows("AAPL", "2024-01-01", "2024-03-31")
            suite.HISTORICAL_CLOSE_ROWS_CACHE.clear()

        self.assertEqual(1, fetch.call_count)
        self.assertTrue(first["persistent_cache_stored"])
        self.assertTrue(second["persistent_cache_hit"])
        self.assertEqual(first["rows"], second["rows"])
        self.assertNotEqual("simulated_fallback", second["source"])


if __name__ == "__main__":
    unittest.main()

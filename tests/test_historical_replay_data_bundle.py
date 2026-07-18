import copy
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import app.stock_suite_app as suite
from app.stock_suite_app import (
    HISTORICAL_CLOSE_ROWS_CACHE,
    HISTORICAL_CLOSE_ROWS_CACHE_MAX_ENTRIES,
    _build_historical_replay_data_bundle,
    _historical_close_rows,
    _normalize_replay_price_rows,
    _replay_usdkrw_rows,
    _slice_historical_replay_data_bundle,
    run_historical_paper_replay,
)


def _source(symbol: str, start: date, days: int = 90) -> dict[str, object]:
    rows = []
    for index in range(days):
        price = 100.0 + index * (0.6 if symbol.endswith("1") else 0.35)
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "close": price,
                "adjclose": price,
                "volume": 1_000_000 + index,
            }
        )
    return {
        "source": "test_adjusted",
        "provider": "test",
        "rows": rows,
        "listing_evidence": {
            "status": "verified",
            "listed_at": "1990-01-01",
            "delisted_at": "",
        },
    }


class HistoricalReplayDataBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        HISTORICAL_CLOSE_ROWS_CACHE.clear()
        self.start = date(2026, 1, 1)
        self.start_text = self.start.isoformat()
        self.end_text = (self.start + timedelta(days=89)).isoformat()

    def tearDown(self) -> None:
        HISTORICAL_CLOSE_ROWS_CACHE.clear()

    def test_builder_fetches_fx_and_each_symbol_exactly_once(self) -> None:
        def source_for(symbol, *_args, **_kwargs):
            return _source(symbol, self.start)

        fx_payload = {
            "rows": [
                {
                    "date": (self.start + timedelta(days=index)).isoformat(),
                    "close": 1300.0 + index * 0.1,
                    "adjclose": 1300.0 + index * 0.1,
                }
                for index in range(90)
            ]
        }
        with (
            patch("app.stock_suite_app._historical_close_rows", side_effect=source_for) as price_fetch,
            patch("app.stock_suite_app._fetch_yahoo_chart_range", return_value=fx_payload) as fx_fetch,
        ):
            bundle = _build_historical_replay_data_bundle(
                ["900001", "BUNDLEUS"],
                self.start_text,
                self.end_text,
                min_bars=5,
            )

        self.assertTrue(bundle["complete"])
        self.assertEqual(2, price_fetch.call_count)
        fx_fetch.assert_called_once()
        self.assertTrue(str(bundle["content_hash"]).startswith("sha256:"))
        self.assertEqual("execution_scoped_memory_only", bundle["persistence_policy"])

    def test_replays_reuse_bundle_and_slice_future_rows_before_strategy(self) -> None:
        symbols = ["900001", "900002"]
        with patch(
            "app.stock_suite_app._historical_close_rows",
            side_effect=lambda symbol, *_args, **_kwargs: _source(symbol, self.start),
        ) as price_fetch:
            bundle = _build_historical_replay_data_bundle(
                symbols,
                self.start_text,
                self.end_text,
                min_bars=5,
            )
        self.assertEqual(2, price_fetch.call_count)
        replay_end = (self.start + timedelta(days=45)).isoformat()
        with (
            patch(
                "app.stock_suite_app._historical_close_rows",
                side_effect=AssertionError("provider must not be called when a bundle is supplied"),
            ),
            patch(
                "app.stock_suite_app._fetch_yahoo_chart_range",
                side_effect=AssertionError("FX provider must not be called when a bundle is supplied"),
            ),
        ):
            result = run_historical_paper_replay(
                symbols,
                self.start_text,
                replay_end,
                fast=2,
                slow=3,
                min_bars=5,
                persist_detail=False,
                replay_data_bundle=bundle,
            )

        evidence = result["replay_data_bundle_evidence"]
        self.assertEqual(
            "codexstock_replay_data_bundle_slice_evidence_v3",
            evidence["schema"],
        )
        self.assertTrue(evidence["used"])
        self.assertTrue(evidence["source_fetch_reused"])
        self.assertTrue(evidence["future_rows_excluded_before_strategy"])
        self.assertTrue(evidence["no_rows_outside_requested_period"])
        self.assertGreater(evidence["excluded_future_row_count"], 0)
        self.assertRegex(evidence["bundle_content_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(evidence["slice_content_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(evidence["slice_manifest_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(set(symbols), set(evidence["symbol_row_bounds"]))
        self.assertEqual(set(symbols), set(evidence["symbol_calendar_adjacency_roots"]))
        self.assertEqual(set(symbols), set(evidence["symbol_calendar_pair_counts"]))
        self.assertTrue(
            all(
                row["market_data_snapshot_hash"] == evidence["slice_content_hash"]
                for row in result["trades"]
            )
        )
        self.assertLessEqual(result["actual_end_date"], replay_end)
        self.assertTrue(all(row["date"] <= replay_end for row in result["trades"]))

    def test_bundle_contract_rejects_hash_period_and_symbol_mismatch(self) -> None:
        with patch(
            "app.stock_suite_app._historical_close_rows",
            return_value=_source("900001", self.start),
        ):
            bundle = _build_historical_replay_data_bundle(
                ["900001"],
                self.start_text,
                self.end_text,
                min_bars=5,
            )
        bad_hash = copy.deepcopy(bundle)
        bad_hash["content_hash"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "content hash mismatch"):
            _slice_historical_replay_data_bundle(
                bad_hash,
                ["900001"],
                self.start_text,
                self.end_text,
                allow_simulated_fallback=False,
            )
        with self.assertRaisesRegex(ValueError, "does not cover requested period"):
            _slice_historical_replay_data_bundle(
                bundle,
                ["900001"],
                (self.start - timedelta(days=1)).isoformat(),
                self.end_text,
                allow_simulated_fallback=False,
            )
        with self.assertRaisesRegex(ValueError, "symbols missing"):
            _slice_historical_replay_data_bundle(
                bundle,
                ["900002"],
                self.start_text,
                self.end_text,
                allow_simulated_fallback=False,
            )

    def test_distinct_intraday_strategies_execute_on_the_same_snapshot_bundle(self) -> None:
        symbols = ["900001", "900002"]
        with patch(
            "app.stock_suite_app._historical_close_rows",
            side_effect=lambda symbol, *_args, **_kwargs: _source(symbol, self.start),
        ):
            bundle = _build_historical_replay_data_bundle(
                symbols,
                self.start_text,
                self.end_text,
                min_bars=5,
            )
        modes = {
            "intraday_theme_leader",
            "intraday_momentum_breakout",
            "intraday_pullback_reclaim",
            "intraday_mean_reversion",
        }
        for mode in modes:
            with self.subTest(mode=mode):
                result = run_historical_paper_replay(
                    symbols,
                    self.start_text,
                    self.end_text,
                    fast=3,
                    slow=15,
                    min_bars=5,
                    strategy_mode=mode,
                    holding_limit_days=4,
                    persist_detail=False,
                    replay_data_bundle=bundle,
                )
                self.assertEqual(result["strategy_mode"], mode)
                self.assertTrue(result["replay_data_bundle_evidence"]["used"])
                self.assertTrue(result["replay_data_bundle_evidence"]["future_rows_excluded_before_strategy"])

    def test_early_yahoo_fx_gap_is_filled_only_with_official_ecos_history(self) -> None:
        yahoo_rows = [
            {
                "date": (self.start + timedelta(days=index)).isoformat(),
                "close": 1320.0 + index * 0.1,
                "adjusted_close": 1320.0 + index * 0.1,
            }
            for index in range(30, 90)
        ]

        def ecos_series(*, start, end, **_kwargs):
            chunk_start = date.fromisoformat(f"{start[:4]}-{start[4:6]}-{start[6:8]}")
            chunk_end = date.fromisoformat(f"{end[:4]}-{end[4:6]}-{end[6:8]}")
            rows = []
            current = chunk_start
            while current <= chunk_end:
                rows.append({
                    "time": current.strftime("%Y%m%d"),
                    "value": 1300.0,
                    "unit": "KRW per USD",
                })
                current += timedelta(days=1)
            return {"ok": True, "configured": True, "rows": rows}

        with (
            patch("app.stock_suite_app._fetch_yahoo_chart_range", return_value={"rows": yahoo_rows}),
            patch("app.stock_suite_app.INTEGRATIONS.ecos_series", side_effect=ecos_series) as ecos_fetch,
        ):
            fx = _replay_usdkrw_rows(self.start_text, self.end_text, min_rows=5)

        self.assertGreaterEqual(ecos_fetch.call_count, 1)
        self.assertGreater(fx["evidence"]["official_row_count"], 0)
        self.assertFalse(fx["evidence"]["future_value_used"])
        self.assertIn("BOK ECOS 731Y001/0000001", fx["evidence"]["sources"])
        stock_rows = [
            {
                "date": (self.start + timedelta(days=index)).isoformat(),
                "close": 100.0 + index,
                "adjusted_close": 100.0 + index,
            }
            for index in range(90)
        ]
        _, contract = _normalize_replay_price_rows(
            "SPY",
            stock_rows,
            provider="Yahoo",
            fx_rows=fx["rows"],
        )
        self.assertTrue(contract["passed"])
        self.assertEqual(100.0, contract["fx_coverage_pct"])
        self.assertIn("BOK ECOS", contract["fx_source"])
        self.assertFalse(contract["fx_future_value_used"])

    def test_historical_provider_cache_is_bounded(self) -> None:
        payload = _source("CACHE", self.start, days=70)
        with (
            patch("app.stock_suite_app._official_listing_evidence", return_value={}),
            patch("app.stock_suite_app._load_verified_replay_data_backfill", return_value=None),
            patch("app.stock_suite_app._yahoo_symbol_candidates", side_effect=lambda symbol: [symbol]),
            patch("app.stock_suite_app._fetch_yahoo_chart_range", return_value=payload),
        ):
            for index in range(HISTORICAL_CLOSE_ROWS_CACHE_MAX_ENTRIES + 12):
                _historical_close_rows(
                    f"CACHE{index}",
                    self.start_text,
                    (self.start + timedelta(days=69)).isoformat(),
                    min_rows=5,
                )

        self.assertLessEqual(
            len(HISTORICAL_CLOSE_ROWS_CACHE),
            HISTORICAL_CLOSE_ROWS_CACHE_MAX_ENTRIES,
        )

    def test_official_market_transfer_uses_earliest_verified_listing_date(self) -> None:
        record: dict[str, object] = {
            "symbol": "199800",
            "name": "ToolGen",
            "earliest_listing_date": "2014-06-25",
            "transition_date": "2021-12-10",
            "from_market": "KONEX",
            "to_market": "KOSDAQ",
            "event": "market_transfer",
            "source_kind": "KRX_KIND_OFFICIAL_DISCLOSURE",
            "source_document_id": "20211208001351/32007",
            "source_url": (
                "https://kind.krx.co.kr/external/2021/12/08/000508/"
                "20211208001351/32007.htm"
            ),
        }
        record["evidence_hash"] = suite._official_market_transition_evidence_hash(record)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            universe_root = root / "universe"
            universe_root.mkdir()
            (universe_root / "kosdaq.json").write_text(
                json.dumps(
                    {
                        "dataset_id": "krx-kosdaq-test",
                        "content_hash": "sha256:test",
                        "evidence": {"official": True, "grade": "official_snapshot"},
                        "records": [
                            {
                                "symbol": "199800",
                                "listing_date": "2021-12-10",
                                "delisting_date": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            transition_file = root / "market_transitions.json"
            transition_file.write_text(
                json.dumps(
                    {
                        "schema": "codexstock_krx_market_transition_evidence_v1",
                        "records": [record],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(suite, "POINT_IN_TIME_UNIVERSE_ROOT", universe_root),
                patch.object(
                    suite,
                    "OFFICIAL_MARKET_TRANSITION_EVIDENCE_FILE",
                    transition_file,
                ),
            ):
                suite.OFFICIAL_LISTING_EVIDENCE_CACHE.clear()
                evidence = suite._official_listing_evidence("199800")

        suite.OFFICIAL_LISTING_EVIDENCE_CACHE.clear()
        self.assertEqual("2014-06-25", evidence["listing_date"])
        self.assertEqual(["2021-12-10"], evidence["current_market_listing_dates"])
        self.assertTrue(evidence["market_transition_verified"])
        self.assertEqual("KONEX", evidence["market_transitions"][0]["from_market"])

    def test_new_listing_accepts_short_verified_range_without_prelisting_rows(self) -> None:
        request_start = "2026-01-01"
        listing_date = "2026-03-20"
        request_end = "2026-03-31"
        post_listing_dates = suite._business_dates(listing_date, request_end, min_days=1)
        backfill_rows = [
            {"date": "2026-01-05", "close": 10.0},
            *[
                {"date": date_key, "close": 100.0 + index}
                for index, date_key in enumerate(post_listing_dates)
            ],
        ]
        with (
            patch(
                "app.stock_suite_app._official_listing_evidence",
                return_value={
                    "listing_date": listing_date,
                    "source": "registered_official_point_in_time_universe",
                },
            ),
            patch(
                "app.stock_suite_app._load_verified_replay_data_backfill",
                return_value={
                    "source": "verified_stage2_backfill",
                    "provider": "test",
                    "rows": backfill_rows,
                    "errors": [],
                },
            ),
        ):
            result = _historical_close_rows(
                "999991",
                request_start,
                request_end,
                min_rows=40,
            )

        self.assertLess(len(result["rows"]), 40)
        self.assertTrue(all(row["date"] >= listing_date for row in result["rows"]))
        self.assertTrue(result["listing_evidence"]["prelisting_gap_exempted"])
        self.assertEqual(listing_date, result["listing_evidence"]["effective_start_date"])


if __name__ == "__main__":
    unittest.main()

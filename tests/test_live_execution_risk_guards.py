import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import stock_suite_app as suite
from app.integrations import KisReadonlyBridge


class LiveExecutionRiskGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        with suite.LIVE_PORTFOLIO_RISK_CACHE_LOCK:
            suite.LIVE_PORTFOLIO_RISK_CACHE.clear()

    def test_vi_and_upper_limit_block_new_buy(self) -> None:
        result = suite._live_market_microstructure_guard(
            "BUY",
            {
                "price": 29_900,
                "upper_limit_price": 30_000,
                "vi_cls_code": "1",
                "risk_fields_observed": True,
                "source": "kis_readonly",
            },
            {"risk_fields_observed": True},
            require_official_fields=True,
        )

        self.assertFalse(result["ok"])
        self.assertIn("vi_active", result["blockers"])
        self.assertIn("upper_limit_entry", result["blockers"])

    def test_missing_official_risk_fields_block_automated_buy(self) -> None:
        result = suite._live_market_microstructure_guard(
            "BUY",
            {"price": 10_000, "source": "fallback"},
            {},
            require_official_fields=True,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            ["official_market_risk_fields_unavailable"],
            result["blockers"],
        )

    def test_sell_remains_available_during_vi_or_daily_loss_stop(self) -> None:
        market = suite._live_market_microstructure_guard(
            "SELL",
            {
                "price": 30_000,
                "upper_limit_price": 30_000,
                "vi_cls_code": "1",
                "temporary_halt_yn": "Y",
            },
            {},
            require_official_fields=True,
        )
        loss = suite._intraday_loss_guard_from_events(
            [
                {"date": "2026-07-18", "symbol": "005930", "side": "BUY", "quantity": 100, "price": 10_000, "executed_at": "2026-07-18T09:00:00+09:00"},
                {"date": "2026-07-18", "symbol": "005930", "side": "SELL", "quantity": 100, "price": 9_700, "executed_at": "2026-07-18T10:00:00+09:00"},
            ],
            side="SELL",
            account_equity=1_000_000,
            policy={"daily_loss_stop_krw": 20_000},
            target_date="2026-07-18",
        )

        self.assertTrue(market["ok"])
        self.assertTrue(loss["ok"])
        self.assertFalse(loss["hard_block"])
        self.assertEqual(0.0, loss["size_multiplier"])

    def test_daily_loss_budget_shrinks_then_blocks_new_buy(self) -> None:
        base = {
            "date": "2026-07-18",
            "symbol": "005930",
            "quantity": 100,
        }
        buy = {**base, "side": "BUY", "price": 10_000, "executed_at": "2026-07-18T09:00:00+09:00"}
        shrink = suite._intraday_loss_guard_from_events(
            [buy, {**base, "side": "SELL", "price": 9_900, "executed_at": "2026-07-18T10:00:00+09:00"}],
            side="BUY",
            account_equity=1_000_000,
            policy={"daily_loss_stop_krw": 20_000},
            target_date="2026-07-18",
        )
        stopped = suite._intraday_loss_guard_from_events(
            [buy, {**base, "side": "SELL", "price": 9_700, "executed_at": "2026-07-18T10:00:00+09:00"}],
            side="BUY",
            account_equity=1_000_000,
            policy={"daily_loss_stop_krw": 20_000},
            target_date="2026-07-18",
        )

        self.assertEqual("RISK_BUDGET_50_PCT", shrink["state"])
        self.assertEqual(0.5, shrink["size_multiplier"])
        self.assertTrue(stopped["hard_block"])
        self.assertEqual("DAILY_LOSS_STOP", stopped["state"])

    def test_order_transport_error_is_unknown_and_not_retry_safe(self) -> None:
        bridge = object.__new__(KisReadonlyBridge)
        bridge.settings = SimpleNamespace(
            live_trading=True,
            kis_readonly=False,
            kis_configured=True,
            kis_use_mock=False,
            kis_account_no="12345678",
            kis_product_code="01",
            kis_app_key="key",
            kis_app_secret="secret",
            kis_mode="real",
        )
        bridge.base_url = "https://example.invalid"
        bridge._cached_token = lambda: "token"
        bridge._hashkey = lambda body: "hash"

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            result = bridge.cash_order("005930", "BUY", 1, 70_000)

        self.assertFalse(result["ok"])
        self.assertFalse(result["outcome_known"])
        self.assertFalse(result["retry_safe"])
        self.assertEqual("UNKNOWN_AFTER_SEND", result["status"])

    def test_accepted_response_without_order_number_remains_unknown(self) -> None:
        bridge = object.__new__(KisReadonlyBridge)
        bridge.settings = SimpleNamespace(
            live_trading=True,
            kis_readonly=False,
            kis_configured=True,
            kis_use_mock=False,
            kis_account_no="12345678",
            kis_product_code="01",
            kis_app_key="key",
            kis_app_secret="secret",
            kis_mode="real",
        )
        bridge.base_url = "https://example.invalid"
        bridge._cached_token = lambda: "token"
        bridge._hashkey = lambda body: "hash"

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"rt_cd": "0", "msg1": "accepted", "output": {}}).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=Response()):
            result = bridge.cash_order("005930", "BUY", 1, 70_000)

        self.assertFalse(result["ok"])
        self.assertFalse(result["outcome_known"])
        self.assertFalse(result["retry_safe"])

    def test_aligned_beta_and_correlation_are_deterministic(self) -> None:
        benchmark = {f"2026-05-{day:02d}": value for day, value in enumerate([0.01, -0.005] * 12, start=1)}
        asset = {day: value * 2.0 for day, value in benchmark.items()}

        result = suite._aligned_beta_correlation(asset, benchmark)

        self.assertTrue(result["ok"])
        self.assertAlmostEqual(2.0, result["beta"], places=6)
        self.assertAlmostEqual(1.0, result["correlation"], places=6)

    def test_portfolio_beta_guard_blocks_excessive_automated_buy(self) -> None:
        def payload(symbol, start_date, end_date, min_rows=40):
            price = 100.0
            rows = [{"date": "2026-04-01", "close": price}]
            for index in range(1, 51):
                benchmark_return = 0.01 if index % 2 else -0.005
                daily_return = benchmark_return if symbol == "069500" else benchmark_return * 2.0
                price *= 1.0 + daily_return
                rows.append({"date": f"2026-05-{index:02d}", "close": price})
            return {
                "rows": rows,
                "data_mode": "real",
                "data_source": "test",
                "data_provider": "test",
            }

        with patch.object(suite, "_historical_price_payload", side_effect=payload):
            result = suite._live_portfolio_market_risk_guard(
                "123456",
                {"positions": []},
                candidate_notional=100_000,
                require_evidence=True,
            )

        self.assertTrue(result["evidence_ready"])
        self.assertTrue(result["hard_block"])
        self.assertIn("portfolio_gross_beta_above_1_8", result["blockers"])

    def test_portfolio_beta_guard_fails_closed_when_evidence_is_missing(self) -> None:
        with patch.object(
            suite,
            "_historical_price_payload",
            side_effect=ValueError("missing adjusted prices"),
        ):
            result = suite._live_portfolio_market_risk_guard(
                "654321",
                {"positions": []},
                candidate_notional=100_000,
                require_evidence=True,
            )

        self.assertTrue(result["hard_block"])
        self.assertIn(
            "portfolio_beta_correlation_evidence_incomplete",
            result["blockers"],
        )


if __name__ == "__main__":
    unittest.main()

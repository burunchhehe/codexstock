import unittest
import math
from datetime import datetime, timedelta, timezone

from stock_suite.execution_sidecar import ExecutionSidecar, OrderSignal, SignalLedger
from stock_suite.snapshot_provider import KisShadowSnapshotProvider


def signal():
    now = datetime.now(timezone.utc)
    return OrderSignal(
        signal_id="SNAP-1", created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=1)).isoformat(), symbol="005930", side="BUY",
        quantity=1, order_type="IOC_LIMIT", reference_price=100_000, max_price=100_300,
        stop_loss_pct=-2, take_profit_pct=3, strategy_id="test", evidence_hash="a" * 64,
    )


def account():
    return {
        "ok": True, "source": "kis_readonly_account", "readonly": True, "order_allowed": False,
        "currency": "KRW", "unit_scale": 1,
        "summary": {
            "available_cash": 1_000_000, "total_value": 10_000_000,
            "stock_value": 1_000_000, "purchase_amount": 900_000, "profit_loss": -9_000,
        },
        "positions": [{
            "symbol": "005930", "quantity": 2, "available_quantity": 1,
            "evaluation_amount": 200_000,
        }],
    }


def contract(payload):
    return {"symbol": "005930", **payload, "currency": "KRW", "unit_scale": 1}


class KisShadowSnapshotProviderTests(unittest.TestCase):
    def test_normalizes_three_readonly_kis_sources(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({"ok": True, "source": "kis_readonly", "price": 100_100}),
            orderbook=lambda symbol: contract({
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100, "best_bid": 100_000,
                "levels": [{"ask_quantity": 17, "bid_quantity": 23}],
            }),
            account=account,
            executions=lambda symbol: {
                "ok": True, "source": "kis_daily_executions",
                "currency": "KRW", "unit_scale": 1,
                "executions": [{"symbol": "000660", "status": "filled"}],
            },
        )
        snapshot = provider(signal())
        self.assertTrue(snapshot.account_ok)
        self.assertEqual(snapshot.data_source, "KIS_READONLY")
        self.assertEqual(snapshot.symbol_exposure, 200_000)
        self.assertTrue(snapshot.already_held)
        self.assertEqual(snapshot.available_position_quantity, 1)
        self.assertEqual(snapshot.best_ask_quantity, 17)
        self.assertEqual(snapshot.best_bid_quantity, 23)
        self.assertAlmostEqual(snapshot.daily_loss_pct, -1.0)

    def test_fallback_or_missing_source_fails_closed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: {"ok": True, "source": "yahoo", "price": 100_100},
            orderbook=lambda symbol: {"ok": False, "source": "kis_orderbook"},
            account=account,
        )
        snapshot = provider(signal())
        self.assertFalse(snapshot.account_ok)
        self.assertIn("quote_non_kis_source", snapshot.snapshot_errors)
        self.assertIn("orderbook_unavailable", snapshot.snapshot_errors)

    def test_pending_same_symbol_is_exposed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({"ok": True, "source": "kis_readonly", "price": 100_100}),
            orderbook=lambda symbol: contract({
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100, "best_bid": 100_000,
            }),
            account=account,
            executions=lambda symbol: {
                "ok": True, "source": "kis_daily_executions",
                "currency": "KRW", "unit_scale": 1,
                "executions": [{"symbol": symbol, "remaining_quantity": 1}],
            },
        )
        self.assertTrue(provider(signal()).pending_same_symbol)

    def test_live_account_profile_is_allowed_through_readonly_call_boundary(self):
        live_profile = account()
        live_profile.update({"readonly": False, "order_allowed": True})
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({"ok": True, "source": "kis_readonly", "price": 100_100}),
            orderbook=lambda symbol: contract({
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100, "best_bid": 100_000,
            }),
            account=lambda: live_profile,
        )
        snapshot = provider(signal())
        self.assertTrue(snapshot.account_ok)
        self.assertEqual(snapshot.data_source, "KIS_READONLY_CALLS_LIVE_PROFILE")

    def test_non_finite_critical_number_fails_closed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({"ok": True, "source": "kis_readonly", "price": math.nan}),
            orderbook=lambda symbol: contract({
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100, "best_bid": 100_000,
            }),
            account=account,
        )
        snapshot = provider(signal())
        self.assertFalse(snapshot.account_ok)
        self.assertEqual(snapshot.current_price, 0.0)
        self.assertIn("quote_price_invalid", snapshot.snapshot_errors)

    def test_zero_vi_code_is_not_treated_as_active(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({
                "ok": True, "source": "kis_readonly", "price": "100,100", "vi_cls_code": "0",
            }),
            orderbook=lambda symbol: contract({
                "ok": True, "source": "kis_orderbook", "best_ask": "100,100", "best_bid": "100,000",
            }),
            account=account,
        )
        snapshot = provider(signal())
        self.assertTrue(snapshot.account_ok)
        self.assertFalse(snapshot.vi_active)
        self.assertEqual(snapshot.current_price, 100_100)

    def test_currency_or_unit_mismatch_fails_closed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: {
                "ok": True, "source": "kis_readonly", "price": 100_100, "currency": "USD",
            },
            orderbook=lambda symbol: {
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100,
                "best_bid": 100_000, "unit_scale": 1000,
            },
            account=account,
        )
        snapshot = provider(signal())
        self.assertFalse(snapshot.account_ok)
        self.assertIn("quote_currency_mismatch", snapshot.snapshot_errors)
        self.assertIn("orderbook_unit_scale_mismatch", snapshot.snapshot_errors)

    def test_missing_currency_or_unit_contract_fails_closed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: {"ok": True, "source": "kis_readonly", "price": 100_100},
            orderbook=lambda symbol: {
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100, "best_bid": 100_000,
            },
            account=lambda: {
                key: value for key, value in account().items() if key not in {"currency", "unit_scale"}
            },
        )
        snapshot = provider(signal())
        self.assertFalse(snapshot.account_ok)
        for source in ("quote", "orderbook", "account"):
            self.assertIn(f"{source}_currency_mismatch", snapshot.snapshot_errors)
            self.assertIn(f"{source}_unit_scale_mismatch", snapshot.snapshot_errors)

    def test_missing_execution_currency_or_unit_contract_fails_closed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({"ok": True, "source": "kis_readonly", "price": 100_100}),
            orderbook=lambda symbol: contract({
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100, "best_bid": 100_000,
            }),
            account=account,
            executions=lambda symbol: {"ok": True, "source": "kis_daily_executions", "executions": []},
        )
        snapshot = provider(signal())
        self.assertFalse(snapshot.account_ok)
        self.assertIn("executions_currency_mismatch", snapshot.snapshot_errors)
        self.assertIn("executions_unit_scale_mismatch", snapshot.snapshot_errors)

    def test_quote_and_orderbook_scale_mismatch_fails_closed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({
                "ok": True,
                "source": "kis_readonly",
                "price": 1_001_000,
                "previous_close": 1_000_000,
                "high": 1_010_000,
                "low": 990_000,
            }),
            orderbook=lambda symbol: contract({
                "ok": True,
                "source": "kis_orderbook",
                "best_ask": 100_100,
                "best_bid": 100_000,
            }),
            account=account,
        )

        snapshot = provider(signal())

        self.assertFalse(snapshot.account_ok)
        self.assertIn("quote_orderbook_price_scale_mismatch", snapshot.snapshot_errors)

    def test_wrong_symbol_from_quote_source_fails_closed(self):
        provider = KisShadowSnapshotProvider(
            quote=lambda symbol: contract({
                "ok": True, "source": "kis_readonly", "price": 100_100, "symbol": "000660",
            }),
            orderbook=lambda symbol: contract({
                "ok": True, "source": "kis_orderbook", "best_ask": 100_100, "best_bid": 100_000,
            }),
            account=account,
        )

        snapshot = provider(signal())

        self.assertFalse(snapshot.account_ok)
        self.assertIn("quote_symbol_mismatch", snapshot.snapshot_errors)


if __name__ == "__main__":
    unittest.main()

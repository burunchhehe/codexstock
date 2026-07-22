import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import app.stock_suite_app as stock_app


def approval(token: str, status: str = "pending") -> dict[str, object]:
    return {
        "token": token,
        "status": status,
        "expires_at": (datetime.now(ZoneInfo("Asia/Seoul")) + timedelta(minutes=30)).isoformat(),
        "ticket": {
            "symbol": "005930",
            "side": "BUY",
            "quantity": 1.0,
            "price": 100_000.0,
        },
    }


class ShortLiveConfirmationTests(unittest.TestCase):
    def test_one_word_confirmation_submits_exactly_one_ticket(self):
        pending = approval("APP-1111111111111111")
        resolved = {**pending, "status": "approved"}
        ops = Mock()
        ops.approvals.return_value = [pending]
        ops.resolve_approval.return_value = resolved
        ops.live_dry_submits.return_value = []
        ops.live_dry_submit.return_value = {
            "status": "LIVE_READY_NOT_SUBMITTED",
            "approval": resolved,
        }
        submit_result = {
            "ok": True,
            "status": "LIVE_SUBMITTED",
            "symbol": "005930",
            "side": "BUY",
            "quantity": 1.0,
            "message": "submitted",
        }

        with patch.object(stock_app, "OPS", ops), patch.object(
            stock_app, "submit_live_pilot_order", return_value=submit_result
        ) as submit:
            result = stock_app._confirm_single_live_order(source="test")

        self.assertTrue(result["ok"])
        submit.assert_called_once_with(
            token="APP-1111111111111111",
            confirm_phrase="1주 파일럿 승인",
            order_type="limit",
            execution_actor="operator",
        )

    def test_one_word_confirmation_fails_closed_when_multiple_tickets_exist(self):
        ops = Mock()
        ops.approvals.return_value = [
            approval("APP-1111111111111111"),
            approval("APP-2222222222222222"),
        ]

        with patch.object(stock_app, "OPS", ops), patch.object(
            stock_app, "submit_live_pilot_order"
        ) as submit:
            result = stock_app._confirm_single_live_order(source="test")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "AMBIGUOUS_ORDER_CONFIRMATION")
        submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()

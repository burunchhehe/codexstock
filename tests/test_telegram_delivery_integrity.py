import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.integrations import TelegramBridge, telegram_text_integrity
from app.ops_core import HepiOpsCore
from app import stock_suite_app


class _TelegramResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps({"ok": True, "result": {"message_id": 101}}).encode("utf-8")


def _settings():
    return SimpleNamespace(
        telegram_enabled=True,
        telegram_configured=True,
        telegram_dry_run=False,
        telegram_stub=False,
        telegram_bot_token="secret-token",
        telegram_chat_id="12345",
    )


class TelegramDeliveryIntegrityTests(unittest.TestCase):
    def test_bridge_sends_exact_hangul_as_utf8_json(self):
        message = "코덱스스톡 기능 정상입니다. 외부 자문 1건 반영 완료."
        with patch("app.integrations.urllib.request.urlopen", return_value=_TelegramResponse()) as urlopen:
            result = TelegramBridge(_settings()).send_message(message)

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertTrue(result["sent"])
        self.assertEqual(message, body["text"])
        self.assertEqual("application/json; charset=utf-8", request.get_header("Content-type"))
        self.assertTrue(result["text_integrity"]["ok"])

    def test_bridge_replaces_question_mark_loss_with_safe_korean_notice(self):
        corrupted = "[긴급] ??? ??? 95,000?"
        integrity = telegram_text_integrity(corrupted)
        self.assertFalse(integrity["ok"])

        with patch("app.integrations.urllib.request.urlopen", return_value=_TelegramResponse()) as urlopen:
            result = TelegramBridge(_settings()).send_message(corrupted)

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertTrue(result["sent"])
        self.assertTrue(result["used_integrity_fallback"])
        self.assertNotIn("???", body["text"])
        self.assertIn("문자 손상", body["text"])

    def test_dispatcher_coalesces_concurrent_calls_and_sends_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.ops_core.configured_user_data_root", return_value=None):
                ops = HepiOpsCore(Path(temp_dir))
            ops.queue_telegram(
                "내부 개발자 단일 장애 보고",
                message_type="internal_developer_urgent",
                source="internal-developer-service",
                metadata={
                    "incident_id": "INC-DISPATCH-1",
                    "single_delivery": True,
                    "single_delivery_id": "INC-DISPATCH-1",
                },
            )
            send_count = 0
            send_count_lock = threading.Lock()
            barrier = threading.Barrier(2)

            def slow_send(_text):
                nonlocal send_count
                with send_count_lock:
                    send_count += 1
                time.sleep(0.12)
                return {"ok": True, "sent": True, "message": "sent", "delivery_status": "sent"}

            def dispatch():
                barrier.wait()
                return stock_suite_app.dispatch_telegram_outbox(limit=1, source="test")

            with (
                patch.object(stock_suite_app, "OPS", ops),
                patch.object(stock_suite_app.INTEGRATIONS, "telegram_send", side_effect=slow_send),
                patch.object(stock_suite_app, "build_telegram_dispatch_center", return_value={}),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                results = list(executor.map(lambda _index: dispatch(), range(2)))

            self.assertEqual(1, send_count)
            self.assertEqual(1, sum(int(row.get("processed", 0)) for row in results))
            self.assertEqual(1, sum(bool(row.get("coalesced")) for row in results))
            self.assertEqual([], ops.pending_telegram_outbox())


if __name__ == "__main__":
    unittest.main()

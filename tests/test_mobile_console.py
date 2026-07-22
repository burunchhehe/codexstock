from __future__ import annotations

import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import app.stock_suite_app as stock_app

from app.mobile_console import (
    MobileAccessStore,
    bearer_token_from_headers,
    mobile_command_is_read_only,
    mobile_cors_origin_allowed,
)


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 22, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value


class MobileConsoleTests(unittest.TestCase):
    def test_pairing_issues_revocable_hashed_device_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            store = MobileAccessStore(Path(directory), now=clock.now)
            pairing = store.create_pairing_code(ttl_seconds=600)
            claim = store.claim_pairing_code(pairing["code"], device_name="Jinwoo Phone")

            self.assertTrue(claim["ok"])
            self.assertTrue(str(claim["token"]).startswith("csm_"))
            self.assertTrue(store.authenticate(claim["token"], touch=False)["ok"])
            self.assertNotIn(str(claim["token"]), store.path.read_text(encoding="utf-8"))
            self.assertEqual(
                store.claim_pairing_code(pairing["code"], device_name="again")["error"],
                "pairing_not_active",
            )

            revoked = store.revoke(claim["device_id"])
            self.assertTrue(revoked["ok"])
            self.assertEqual(
                store.authenticate(claim["token"], touch=False)["error"],
                "mobile_token_revoked",
            )

    def test_pairing_expires_and_invalid_attempts_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            store = MobileAccessStore(Path(directory), now=clock.now)
            pairing = store.create_pairing_code(ttl_seconds=60)
            for _ in range(7):
                self.assertFalse(store.claim_pairing_code("00000000", device_name="bad")["ok"])
            locked = store.claim_pairing_code("00000000", device_name="bad")
            self.assertEqual(locked["attempts_remaining"], 0)
            self.assertEqual(
                store.claim_pairing_code(pairing["code"], device_name="late")["error"],
                "pairing_not_active",
            )

            pairing = store.create_pairing_code(ttl_seconds=60)
            clock.value += timedelta(seconds=61)
            self.assertEqual(
                store.claim_pairing_code(pairing["code"], device_name="expired")["error"],
                "pairing_expired",
            )

    def test_mobile_assistant_blocks_mutation_but_allows_status_questions(self) -> None:
        self.assertEqual(mobile_command_is_read_only("지금 직원들 뭐해?"), (True, "read_only"))
        self.assertEqual(mobile_command_is_read_only("오늘 왜 삼성전자를 샀어?"), (True, "read_only"))
        self.assertFalse(mobile_command_is_read_only("삼성전자 3주 매수해")[0])
        self.assertFalse(mobile_command_is_read_only("자동매매 시작해")[0])
        self.assertFalse(mobile_command_is_read_only("오늘 장 50번 복기해")[0])

    def test_mobile_header_and_cors_contract(self) -> None:
        self.assertEqual(
            bearer_token_from_headers({"Authorization": "Bearer csm_abc"}),
            "csm_abc",
        )
        self.assertEqual(
            bearer_token_from_headers({"X-CodexStock-Mobile-Token": "csm_xyz"}),
            "csm_xyz",
        )
        self.assertTrue(mobile_cors_origin_allowed("capacitor://localhost"))
        self.assertFalse(mobile_cors_origin_allowed("https://attacker.example"))

    def test_mobile_payload_cache_serves_stale_while_refreshing(self) -> None:
        cache_key = f"unit-mobile-cache-{id(self)}"
        refreshed = threading.Event()
        calls = 0

        def builder() -> dict[str, object]:
            nonlocal calls
            calls += 1
            if calls > 1:
                refreshed.set()
            return {"ok": True, "value": calls}

        try:
            first = stock_app._mobile_console_cached_payload(
                cache_key,
                builder,
                ttl_seconds=1,
            )
            self.assertEqual(1, first["value"])
            self.assertFalse(first["mobile_cache"]["hit"])

            with stock_app.MOBILE_CONSOLE_CACHE_LOCK:
                _, payload = stock_app.MOBILE_CONSOLE_CACHE[cache_key]
                stock_app.MOBILE_CONSOLE_CACHE[cache_key] = (time.monotonic() - 2, payload)

            stale = stock_app._mobile_console_cached_payload(
                cache_key,
                builder,
                ttl_seconds=1,
            )
            self.assertEqual(1, stale["value"])
            self.assertTrue(stale["mobile_cache"]["stale"])
            self.assertTrue(stale["mobile_cache"]["refreshing"])
            self.assertTrue(refreshed.wait(timeout=2))

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                with stock_app.MOBILE_CONSOLE_CACHE_LOCK:
                    current = stock_app.MOBILE_CONSOLE_CACHE.get(cache_key)
                if current and current[1].get("value") == 2:
                    break
                time.sleep(0.01)
            current_payload = stock_app._mobile_console_cached_payload(
                cache_key,
                builder,
                ttl_seconds=1,
            )
            self.assertEqual(2, current_payload["value"])
            self.assertFalse(current_payload["mobile_cache"]["stale"])
        finally:
            with stock_app.MOBILE_CONSOLE_CACHE_LOCK:
                stock_app.MOBILE_CONSOLE_CACHE.pop(cache_key, None)
                stock_app.MOBILE_CONSOLE_BUILD_LOCKS.pop(cache_key, None)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping


MOBILE_SCHEMA = "codexstock_mobile_access_v1"
TOKEN_PREFIX = "csm_"
DEFAULT_TOKEN_DAYS = 180
MAX_DEVICES = 5
MAX_PAIRING_ATTEMPTS = 8


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_device_name(value: object) -> str:
    text = re.sub(r"[^0-9A-Za-z가-힣 _.-]", "", str(value or "").strip())
    return text[:48] or "Android phone"


class MobileAccessStore:
    """Persist only hashes for revocable mobile device access."""

    def __init__(
        self,
        root: Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root)
        self.path = self.root / "mobile_access.json"
        self._now = now or _utc_now
        self._lock = threading.RLock()

    def _default(self) -> dict[str, object]:
        return {
            "schema": MOBILE_SCHEMA,
            "updated_at": _iso(self._now()),
            "pairing": {},
            "devices": [],
        }

    def _load_unlocked(self) -> dict[str, object]:
        if not self.path.is_file():
            return self._default()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default()
        if not isinstance(payload, dict) or payload.get("schema") != MOBILE_SCHEMA:
            return self._default()
        if not isinstance(payload.get("devices"), list):
            payload["devices"] = []
        if not isinstance(payload.get("pairing"), dict):
            payload["pairing"] = {}
        return payload

    def _write_unlocked(self, payload: dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload["schema"] = MOBILE_SCHEMA
        payload["updated_at"] = _iso(self._now())
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def create_pairing_code(self, *, ttl_seconds: int = 600) -> dict[str, object]:
        ttl = max(60, min(int(ttl_seconds), 1800))
        now = self._now().astimezone(timezone.utc)
        code = f"{secrets.randbelow(100_000_000):08d}"
        with self._lock:
            payload = self._load_unlocked()
            payload["pairing"] = {
                "code_hash": _digest(code),
                "created_at": _iso(now),
                "expires_at": _iso(now + timedelta(seconds=ttl)),
                "attempts": 0,
                "consumed": False,
            }
            self._write_unlocked(payload)
        return {
            "ok": True,
            "code": code,
            "expires_at": _iso(now + timedelta(seconds=ttl)),
            "ttl_seconds": ttl,
            "message": "휴대폰 연결 화면에 이 일회용 코드를 입력하세요.",
        }

    def claim_pairing_code(
        self,
        code: object,
        *,
        device_name: object,
        token_days: int = DEFAULT_TOKEN_DAYS,
    ) -> dict[str, object]:
        supplied = re.sub(r"\D", "", str(code or ""))
        now = self._now().astimezone(timezone.utc)
        with self._lock:
            payload = self._load_unlocked()
            pairing = payload.get("pairing") if isinstance(payload.get("pairing"), dict) else {}
            expires_at = _parse_datetime(pairing.get("expires_at"))
            attempts = int(pairing.get("attempts", 0) or 0)
            if not pairing or pairing.get("consumed"):
                return {"ok": False, "error": "pairing_not_active"}
            if expires_at is None or expires_at <= now:
                pairing["consumed"] = True
                payload["pairing"] = pairing
                self._write_unlocked(payload)
                return {"ok": False, "error": "pairing_expired"}
            if attempts >= MAX_PAIRING_ATTEMPTS:
                return {"ok": False, "error": "pairing_locked"}
            pairing["attempts"] = attempts + 1
            expected_hash = str(pairing.get("code_hash") or "")
            if len(supplied) != 8 or not hmac.compare_digest(_digest(supplied), expected_hash):
                if int(pairing["attempts"]) >= MAX_PAIRING_ATTEMPTS:
                    pairing["consumed"] = True
                payload["pairing"] = pairing
                self._write_unlocked(payload)
                return {
                    "ok": False,
                    "error": "pairing_code_invalid",
                    "attempts_remaining": max(0, MAX_PAIRING_ATTEMPTS - int(pairing["attempts"])),
                }

            token = TOKEN_PREFIX + secrets.token_urlsafe(32)
            device_id = "mob-" + secrets.token_hex(6)
            days = max(1, min(int(token_days), DEFAULT_TOKEN_DAYS))
            devices = [
                row
                for row in payload.get("devices", [])
                if isinstance(row, dict) and not bool(row.get("revoked"))
            ]
            if len(devices) >= MAX_DEVICES:
                oldest = min(devices, key=lambda row: str(row.get("created_at") or ""))
                oldest["revoked"] = True
                oldest["revoked_at"] = _iso(now)
            device = {
                "device_id": device_id,
                "device_name": _safe_device_name(device_name),
                "token_hash": _digest(token),
                "created_at": _iso(now),
                "expires_at": _iso(now + timedelta(days=days)),
                "last_seen_at": "",
                "revoked": False,
            }
            all_devices = [row for row in payload.get("devices", []) if isinstance(row, dict)]
            all_devices.append(device)
            payload["devices"] = all_devices[-20:]
            pairing["consumed"] = True
            pairing["consumed_at"] = _iso(now)
            pairing.pop("code_hash", None)
            payload["pairing"] = pairing
            self._write_unlocked(payload)

        return {
            "ok": True,
            "device_id": device_id,
            "device_name": device["device_name"],
            "token": token,
            "expires_at": device["expires_at"],
            "permissions": ["read_status", "read_reports", "assistant_read_only", "emergency_stop"],
            "message": "휴대폰 연결이 완료됐습니다. 증권사 키는 휴대폰으로 전달되지 않았습니다.",
        }

    def authenticate(self, token: object, *, touch: bool = True) -> dict[str, object]:
        raw = str(token or "").strip()
        if not raw.startswith(TOKEN_PREFIX) or len(raw) < 32:
            return {"ok": False, "error": "mobile_token_missing"}
        now = self._now().astimezone(timezone.utc)
        token_hash = _digest(raw)
        with self._lock:
            payload = self._load_unlocked()
            devices = [row for row in payload.get("devices", []) if isinstance(row, dict)]
            for device in devices:
                expected = str(device.get("token_hash") or "")
                if not expected or not hmac.compare_digest(token_hash, expected):
                    continue
                if bool(device.get("revoked")):
                    return {"ok": False, "error": "mobile_token_revoked"}
                expires_at = _parse_datetime(device.get("expires_at"))
                if expires_at is None or expires_at <= now:
                    return {"ok": False, "error": "mobile_token_expired"}
                last_seen = _parse_datetime(device.get("last_seen_at"))
                if touch and (last_seen is None or (now - last_seen).total_seconds() >= 300):
                    device["last_seen_at"] = _iso(now)
                    payload["devices"] = devices
                    self._write_unlocked(payload)
                return {
                    "ok": True,
                    "device_id": str(device.get("device_id") or ""),
                    "device_name": str(device.get("device_name") or "Android phone"),
                    "expires_at": str(device.get("expires_at") or ""),
                }
        return {"ok": False, "error": "mobile_token_invalid"}

    def revoke(self, device_id: object) -> dict[str, object]:
        target = str(device_id or "").strip()
        now = self._now().astimezone(timezone.utc)
        with self._lock:
            payload = self._load_unlocked()
            devices = [row for row in payload.get("devices", []) if isinstance(row, dict)]
            found = False
            for device in devices:
                if str(device.get("device_id") or "") == target:
                    device["revoked"] = True
                    device["revoked_at"] = _iso(now)
                    found = True
                    break
            payload["devices"] = devices
            self._write_unlocked(payload)
        return {"ok": found, "device_id": target, "error": "" if found else "device_not_found"}

    def status(self) -> dict[str, object]:
        now = self._now().astimezone(timezone.utc)
        with self._lock:
            payload = self._load_unlocked()
        pairing = payload.get("pairing") if isinstance(payload.get("pairing"), dict) else {}
        pairing_expires = _parse_datetime(pairing.get("expires_at"))
        devices = []
        for row in payload.get("devices", []):
            if not isinstance(row, dict):
                continue
            expires_at = _parse_datetime(row.get("expires_at"))
            devices.append(
                {
                    "device_id": str(row.get("device_id") or ""),
                    "device_name": str(row.get("device_name") or ""),
                    "created_at": str(row.get("created_at") or ""),
                    "last_seen_at": str(row.get("last_seen_at") or ""),
                    "expires_at": str(row.get("expires_at") or ""),
                    "active": bool(
                        not row.get("revoked")
                        and expires_at is not None
                        and expires_at > now
                    ),
                    "revoked": bool(row.get("revoked")),
                }
            )
        return {
            "ok": True,
            "schema": MOBILE_SCHEMA,
            "pairing_active": bool(
                pairing
                and not pairing.get("consumed")
                and pairing_expires is not None
                and pairing_expires > now
            ),
            "pairing_expires_at": str(pairing.get("expires_at") or ""),
            "active_device_count": sum(1 for row in devices if row["active"]),
            "devices": devices,
            "token_values_exposed": False,
        }


def bearer_token_from_headers(headers: Mapping[str, str]) -> str:
    authorization = str(headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return str(headers.get("X-CodexStock-Mobile-Token") or "").strip()


_MUTATING_COMMAND_PATTERNS = (
    r"(?:매수|매도|주문|체결시켜|사줘|팔아줘|사라|팔아라)",
    r"(?:자동매매|오토파일럿|데몬).*(?:시작|켜|정지|중지|꺼|재개)",
    r"(?:승인|허용|위임|한도|비중).*(?:변경|설정|적용|올려|낮춰)",
    r"(?:긴급정지|비상정지).*(?:해제|풀어|재개)",
    r"(?:실행|돌려|훈련해|복기해|생성해|등록해|삭제해|수정해|동기화해|전송해|보내줘)",
    r"\b(?:buy|sell|order|approve|submit|start|stop|resume|enable|disable|restart|delete|update|sync)\b",
)


def mobile_command_is_read_only(command: object) -> tuple[bool, str]:
    text = re.sub(r"\s+", " ", str(command or "").strip())
    if not text:
        return False, "empty_command"
    if len(text) > 500:
        return False, "command_too_long"
    lowered = text.lower()
    for pattern in _MUTATING_COMMAND_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            return False, "mutating_command_blocked"
    return True, "read_only"


def mobile_cors_origin_allowed(origin: object) -> bool:
    value = str(origin or "").strip().lower()
    if not value:
        return False
    if value in {"capacitor://localhost", "https://localhost", "http://localhost"}:
        return True
    return value.startswith("http://127.0.0.1:") or value.startswith("http://localhost:")

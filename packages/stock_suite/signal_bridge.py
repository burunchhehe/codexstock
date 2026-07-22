"""Bridge validated CodexStock candidate tickets to signed Shadow signals."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping

from .execution_sidecar import OrderSignal


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _harden_secret_permissions(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        raise RuntimeError("cannot restrict signing secret permissions") from exc
    if os.name != "nt":
        return
    try:
        username = str(os.environ.get("USERNAME") or "").strip()
        domain = str(os.environ.get("USERDOMAIN") or os.environ.get("COMPUTERNAME") or "").strip()
        if not username:
            raise RuntimeError("Windows user identity is unavailable")
        identity = f"{domain}\\{username}" if domain else username
        subprocess.run(
            [
                "icacls", str(path), "/inheritance:r",
                "/grant:r", f"{identity}:(F)",
                "/grant:r", "*S-1-5-18:(F)",
            ],
            check=True, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("cannot apply Windows ACL to signing secret") from exc


def load_or_create_signing_secret(secret_file: Path) -> bytes:
    secret_file = Path(secret_file)
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if not secret_file.exists():
        try:
            descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(secrets.token_hex(32).encode("ascii"))
    secret = secret_file.read_bytes().strip()
    try:
        decoded = bytes.fromhex(secret.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("shadow signal signing secret is corrupt") from exc
    if len(decoded) != 32 or len(secret) != 64:
        raise RuntimeError("shadow signal signing secret must contain exactly 256 bits")
    _harden_secret_permissions(secret_file)
    return secret


class ShadowSignalPublisher:
    """Publish only risk-passed live candidates; this class cannot place orders."""

    def __init__(self, outbox: Path, secret_file: Path, ttl_seconds: int = 15) -> None:
        self.outbox = Path(outbox)
        self.secret_file = Path(secret_file)
        self.ttl_seconds = max(3, min(int(ttl_seconds), 120))

    def _secret(self) -> bytes:
        return load_or_create_signing_secret(self.secret_file)

    def publish(self, ticket: Mapping[str, object]) -> dict[str, object]:
        if str(ticket.get("mode") or "") != "live_candidate":
            return {"published": False, "reason": "not_live_candidate"}
        if str(ticket.get("risk_status") or "") != "PASSED":
            return {"published": False, "reason": "candidate_risk_blocked"}

        metadata = ticket.get("metadata") if isinstance(ticket.get("metadata"), dict) else {}
        output_mode = (
            "external_executor"
            if str(ticket.get("status") or "") == "DELEGATED_SIGNAL_READY"
            else "shadow_only"
        )
        price = float(ticket.get("price") or 0)
        quantity = int(float(ticket.get("quantity") or 0))
        signal_id = str(ticket.get("id") or "").strip()
        candidate_ticket_hash = hashlib.sha256(
            json.dumps(ticket, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        target = self.outbox / f"{signal_id}.json"
        if target.exists():
            existing = OrderSignal(**json.loads(target.read_text(encoding="utf-8")))
            same_order = (
                existing.signal_id == signal_id
                and existing.symbol == str(ticket.get("symbol") or "").upper().strip()
                and existing.side == str(ticket.get("side") or "").upper().strip()
                and existing.quantity == quantity
                and existing.reference_price == price
                and existing.candidate_ticket_hash == candidate_ticket_hash
            )
            if same_order:
                return {
                    "published": True,
                    "reason": "idempotent_replay",
                    "signal_id": signal_id,
                    "path": str(target),
                    "mode": output_mode,
                }
            return {"published": False, "reason": "signal_id_already_published", "signal_id": signal_id}
        now = datetime.now().astimezone()
        max_price = float(metadata.get("max_price") or price * 1.004)
        min_price = float(metadata.get("min_price") or price * 0.996)
        stop_loss = -abs(float(metadata.get("stop_loss_pct") or 2.0))
        take_profit = abs(float(metadata.get("take_profit_pct") or 3.0))
        evidence_seed = {
            "ticket_id": ticket.get("id"),
            "memo": ticket.get("memo"),
            "metadata": metadata,
            "risk_checks": ticket.get("risk_checks"),
        }
        evidence_hash = str(metadata.get("evidence_hash") or "").strip() or hashlib.sha256(
            json.dumps(evidence_seed, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        signal = OrderSignal(
            signal_id=signal_id,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.ttl_seconds)).isoformat(),
            symbol=str(ticket.get("symbol") or "").upper().strip(),
            side=str(ticket.get("side") or "").upper().strip(),
            quantity=quantity,
            order_type=str(metadata.get("order_type") or "IOC_LIMIT").upper(),
            reference_price=price,
            max_price=max_price,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
            strategy_id=str(metadata.get("strategy_id") or ticket.get("source") or "candidate-ledger")[:120],
            evidence_hash=evidence_hash,
            origin="candidate_ledger",
            candidate_ticket_hash=candidate_ticket_hash,
            min_price=min_price,
            execution_mode=str(metadata.get("execution_mode") or "unspecified"),
        )
        signal.validate()
        signed = signal.sign(self._secret())
        payload = json.dumps(signed.__dict__, ensure_ascii=False, indent=2, sort_keys=True)
        _atomic_write(target, payload)
        return {
            "published": True,
            "reason": "signed_external_executor_signal_published" if output_mode == "external_executor" else "signed_shadow_signal_published",
            "signal_id": signed.signal_id,
            "expires_at": signed.expires_at,
            "path": str(target),
            "mode": output_mode,
        }

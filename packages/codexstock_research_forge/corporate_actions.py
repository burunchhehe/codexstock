from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def adjust_split_history(rows: list[dict[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Backward-adjust OHLCV for official splits, dividends, and rights issues."""
    if not rows or not actions:
        raise ValueError("corporate-action adjustment requires rows and actions")
    if any(row.get("corporate_action_adjustment_hash") for row in rows):
        raise ValueError("rows already contain corporate-action adjustment provenance")
    values = [dict(row) for row in rows]
    timestamps = [str(row.get("timestamp") or row.get("date") or "") for row in values]
    dates = [date.fromisoformat(value[:10]) for value in timestamps]
    if any(not value for value in timestamps) or not all(left < right for left, right in zip(timestamps, timestamps[1:])):
        raise ValueError("corporate-action rows require unique chronological timestamps")
    for row in values:
        prices = [float(row.get(key) or 0) for key in ("open", "high", "low", "close")]
        if min(prices) <= 0 or float(row.get("volume") or 0) < 0:
            raise ValueError("corporate-action rows contain invalid OHLCV")

    normalized = [_action(value, dates[0], dates[-1]) for value in actions]
    normalized.sort(key=lambda value: (value["effective_date"], value["source_hash"]))
    if len({(row["effective_date"], row["source_hash"]) for row in normalized}) != len(normalized):
        raise ValueError("duplicate corporate actions are not allowed")
    price_factors = [1.0] * len(values)
    volume_factors = [1.0] * len(values)
    ledger = []
    for action in normalized:
        effective = date.fromisoformat(action["effective_date"])
        previous_index = max(index for index, row_date in enumerate(dates) if row_date < effective)
        previous_close = float(values[previous_index]["close"])
        if action["type"] in {"SPLIT", "REVERSE_SPLIT"}:
            price_factor = action["old_shares"] / action["new_shares"]
            volume_factor = action["new_shares"] / action["old_shares"]
        elif action["type"] == "CASH_DIVIDEND":
            cash = action["cash_per_share"]
            if not 0 < cash < previous_close:
                raise ValueError("cash dividend must be positive and below the previous close")
            price_factor, volume_factor = (previous_close - cash) / previous_close, 1.0
        else:
            new_shares, old_shares, subscription = action["new_shares"], action["old_shares"], action["subscription_price"]
            theoretical_ex_rights = (old_shares * previous_close + new_shares * subscription) / (old_shares + new_shares)
            if not 0 < theoretical_ex_rights <= previous_close:
                raise ValueError("rights issue produces an invalid theoretical ex-rights price")
            price_factor, volume_factor = theoretical_ex_rights / previous_close, (old_shares + new_shares) / old_shares
        for index, row_date in enumerate(dates):
            if row_date < effective:
                price_factors[index] *= price_factor
                volume_factors[index] *= volume_factor
        ledger.append({**action, "reference_previous_close": previous_close, "price_factor_for_prior_rows": round(price_factor, 12), "volume_factor_for_prior_rows": round(volume_factor, 12)})

    input_hash = _hash(values)
    for index, row in enumerate(values):
        price_factor = price_factors[index]
        for key in ("open", "high", "low", "close"):
            row[key] = round(float(row[key]) * price_factor, 10)
        row["volume"] = round(float(row.get("volume") or 0) * volume_factors[index], 10)
        row["corporate_action_price_factor"] = round(price_factor, 12)
        row["corporate_action_volume_factor"] = round(volume_factors[index], 12)
    canonical_actions = json.dumps(ledger, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    adjustment_hash = f"sha256:{hashlib.sha256((input_hash + canonical_actions).encode()).hexdigest()}"
    for row in values:
        row["corporate_action_adjustment_hash"] = adjustment_hash
    return {"ok": True, "rows": values, "row_count": len(values), "action_count": len(normalized), "ledger": ledger, "input_hash": input_hash, "adjusted_hash": _hash(values), "adjustment_hash": adjustment_hash, "method": "official_corporate_action_backward_adjustment", "live_order_allowed": False}


def _action(value: dict[str, Any], first: date, last: date) -> dict[str, Any]:
    supported = {"SPLIT", "REVERSE_SPLIT", "CASH_DIVIDEND", "RIGHTS_ISSUE"}
    if not isinstance(value, dict) or str(value.get("type") or "") not in supported:
        raise ValueError("unsupported corporate action type")
    effective = date.fromisoformat(str(value.get("effective_date") or ""))
    if not first < effective <= last:
        raise ValueError("corporate action must fall inside the OHLCV history after its first row")
    source_url, source_hash = str(value.get("source_url") or ""), str(value.get("source_hash") or "")
    if not source_url.startswith(("https://kind.krx.co.kr/", "https://data.krx.co.kr/")):
        raise ValueError("corporate action requires an official KRX source URL")
    if not source_hash.startswith("sha256:") or len(source_hash) != 71:
        raise ValueError("corporate action requires a SHA-256 source hash")
    output = {"type": str(value["type"]), "effective_date": effective.isoformat(), "source_url": source_url, "source_hash": source_hash}
    if output["type"] == "CASH_DIVIDEND":
        cash = float(value.get("cash_per_share") or 0)
        if cash <= 0: raise ValueError("cash dividend requires positive cash_per_share")
        output["cash_per_share"] = cash
        return output
    new_shares, old_shares = float(value.get("new_shares") or 0), float(value.get("old_shares") or 0)
    if new_shares <= 0 or old_shares <= 0:
        raise ValueError("share action requires positive new_shares and old_shares")
    if output["type"] in {"SPLIT", "REVERSE_SPLIT"}:
        if new_shares == old_shares: raise ValueError("split ratio must change share count")
        expected = "SPLIT" if new_shares > old_shares else "REVERSE_SPLIT"
        if output["type"] != expected: raise ValueError("corporate action type conflicts with its share ratio")
    else:
        subscription = float(value.get("subscription_price") if value.get("subscription_price") is not None else -1)
        if subscription < 0: raise ValueError("rights issue requires a non-negative subscription_price")
        output["subscription_price"] = subscription
    output.update({"new_shares": new_shares, "old_shares": old_shares})
    return output


def _hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


class CorporateActionRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root; root.mkdir(parents=True, exist_ok=True)

    def register(self, dataset_id: str, symbol: str, actions: list[dict[str, Any]], complete_history: bool = False, source_documents_verified: bool = False) -> dict[str, Any]:
        if not dataset_id or Path(dataset_id).name != dataset_id or not dataset_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("invalid corporate-action dataset id")
        symbol = symbol.upper()
        if not symbol.isalnum() or not actions:
            raise ValueError("corporate-action registry requires an alphanumeric symbol and actions")
        normalized = [_action(value, date.min, date.max) for value in actions]
        normalized.sort(key=lambda value: (value["effective_date"], value["source_hash"]))
        if len({(row["effective_date"], row["source_hash"]) for row in normalized}) != len(normalized):
            raise ValueError("duplicate corporate actions are not allowed")
        payload = {"schema_version": 1, "dataset_id": dataset_id, "symbol": symbol, "actions": normalized, "action_count": len(normalized), "coverage_start": normalized[0]["effective_date"], "coverage_end": normalized[-1]["effective_date"], "complete_history": bool(complete_history), "source_documents_verified": bool(source_documents_verified), "registered_at": datetime.now(timezone.utc).isoformat()}
        payload["content_hash"] = _hash(payload)
        path = self._path(dataset_id); temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)
        return {key: payload[key] for key in ("dataset_id", "symbol", "action_count", "coverage_start", "coverage_end", "complete_history", "source_documents_verified", "content_hash", "registered_at")}

    def get(self, dataset_id: str) -> dict[str, Any]:
        path = self._path(dataset_id)
        if not path.is_file(): raise ValueError("corporate-action dataset not found")
        payload = json.loads(path.read_text(encoding="utf-8")); stored = payload.pop("content_hash", ""); expected = _hash(payload); payload["content_hash"] = stored
        if payload.get("schema_version") != 1 or stored != expected:
            raise ValueError("corporate-action dataset integrity verification failed")
        return payload

    def query(self, dataset_id: str, start: str = "", end: str = "") -> dict[str, Any]:
        payload = self.get(dataset_id); first = date.fromisoformat(start) if start else date.min; last = date.fromisoformat(end) if end else date.max
        if last < first: raise ValueError("corporate-action query end precedes start")
        actions = [row for row in payload["actions"] if first <= date.fromisoformat(row["effective_date"]) <= last]
        return {"ok": True, "dataset_id": dataset_id, "symbol": payload["symbol"], "actions": actions, "count": len(actions), "complete_history": payload["complete_history"], "source_documents_verified": payload.get("source_documents_verified", False), "content_hash": payload["content_hash"], "result_hash": _hash(actions)}

    def adjust(self, dataset_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        payload = self.get(dataset_id); timestamps = [str(row.get("timestamp") or row.get("date") or "") for row in rows]
        if not timestamps: raise ValueError("registered corporate-action adjustment requires rows")
        relevant = self.query(dataset_id, timestamps[0][:10], timestamps[-1][:10])
        if not relevant["actions"]: raise ValueError("registered dataset has no actions inside the OHLCV range")
        result = adjust_split_history(rows, relevant["actions"]); result.update({"dataset_id": dataset_id, "symbol": payload["symbol"], "registry_content_hash": payload["content_hash"], "registry_complete_history": payload["complete_history"], "source_documents_verified": payload.get("source_documents_verified", False)})
        return result

    def status(self) -> dict[str, Any]:
        datasets, invalid = [], []
        for path in sorted(self.root.glob("*.json")):
            try:
                payload = self.get(path.stem); datasets.append({key: payload.get(key) for key in ("dataset_id", "symbol", "action_count", "coverage_start", "coverage_end", "complete_history", "source_documents_verified", "content_hash")})
            except Exception as exc: invalid.append({"path": str(path), "error": str(exc)})
        return {"ok": not invalid, "dataset_count": len(datasets), "datasets": datasets, "invalid": invalid, "complete_dataset_count": sum(bool(row["complete_history"]) for row in datasets)}

    def _path(self, dataset_id: str) -> Path:
        if not dataset_id or Path(dataset_id).name != dataset_id: raise ValueError("invalid corporate-action dataset id")
        return self.root / f"{dataset_id}.json"


class OfficialCorporateActionEvidenceProvider:
    """Read-only verifier for exact KRX/KIND source documents; it does not infer economics from prose."""
    def __init__(self, opener: Any = None) -> None: self.opener = opener or urllib.request.urlopen

    def verify(self, actions: list[dict[str, Any]], timeout: float = 15.0, max_bytes: int = 10_000_000, attempts: int = 3) -> dict[str, Any]:
        if not actions or not 1 <= attempts <= 5 or not 1024 <= max_bytes <= 50_000_000:
            raise ValueError("official document verification received invalid bounds")
        output, documents = [], []
        for value in actions:
            action = dict(value); url = str(action.get("source_url") or "")
            if not url.startswith(("https://kind.krx.co.kr/", "https://data.krx.co.kr/")):
                raise ValueError("official document URL must use KRX or KIND HTTPS")
            body, content_type, error = b"", "", None
            for attempt in range(1, attempts + 1):
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "CodexStock-Research-Forge/0.3"})
                    with self.opener(request, timeout=timeout) as response:
                        body = response.read(max_bytes + 1); content_type = str(response.headers.get("Content-Type") or "")
                    if len(body) > max_bytes: raise ValueError("official document exceeds max_bytes")
                    if not body: raise ValueError("official document is empty")
                    error = None; break
                except Exception as exc:
                    error = exc
                    if isinstance(exc, ValueError) or attempt == attempts: break
                    time.sleep(min(1.0, 0.1 * (2 ** (attempt - 1))))
            if error is not None: raise ValueError(f"official document verification failed: {error}")
            digest = f"sha256:{hashlib.sha256(body).hexdigest()}"; declared = str(action.get("source_hash") or "")
            if declared and declared != digest: raise ValueError("official document SHA-256 does not match the declared source_hash")
            action["source_hash"] = digest; output.append(action)
            documents.append({"source_url": url, "source_hash": digest, "bytes": len(body), "content_type": content_type})
        return {"ok": True, "actions": output, "documents": documents, "document_count": len(documents), "verified_at": datetime.now(timezone.utc).isoformat(), "network_checked": True, "read_only": True, "order_allowed": False}

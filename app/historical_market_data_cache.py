from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import zlib
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class HistoricalMarketDataCache:
    """Bounded, integrity-checked cache for exact historical market-data requests."""

    SCHEMA_VERSION = "codexstock_historical_market_data_cache_v2"
    LEGACY_SCHEMA_VERSIONS = {"codexstock_historical_market_data_cache_v1"}
    MAX_COMPRESSED_BYTES = 16 * 1024 * 1024
    MAX_DECOMPRESSED_BYTES = 64 * 1024 * 1024

    def __init__(self, path: Path, *, max_entries: int = 512) -> None:
        self.path = Path(path)
        self.max_entries = max(16, min(int(max_entries), 5_000))

    @staticmethod
    def _canonical(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS historical_market_data_cache (
                cache_key TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                contract_json TEXT NOT NULL,
                payload_zlib BLOB NOT NULL,
                payload_sha256 TEXT NOT NULL,
                stored_at_epoch REAL NOT NULL,
                expires_at_epoch REAL NOT NULL,
                last_access_epoch REAL NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                last_hit_epoch REAL
            )
            """
        )
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(historical_market_data_cache)")
        }
        if "hit_count" not in columns:
            connection.execute(
                "ALTER TABLE historical_market_data_cache "
                "ADD COLUMN hit_count INTEGER NOT NULL DEFAULT 0"
            )
        if "last_hit_epoch" not in columns:
            connection.execute(
                "ALTER TABLE historical_market_data_cache ADD COLUMN last_hit_epoch REAL"
            )
        connection.execute(
            "UPDATE historical_market_data_cache SET schema_version = ? "
            "WHERE schema_version = ?",
            (self.SCHEMA_VERSION, "codexstock_historical_market_data_cache_v1"),
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_historical_market_data_cache_expiry "
            "ON historical_market_data_cache(expires_at_epoch)"
        )
        return connection

    def _key(self, contract: dict[str, object]) -> tuple[str, str]:
        contract_bytes = self._canonical(contract)
        return hashlib.sha256(contract_bytes).hexdigest(), contract_bytes.decode("utf-8")

    def invalidate(self, contract: dict[str, object]) -> None:
        cache_key, _ = self._key(contract)
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    "DELETE FROM historical_market_data_cache WHERE cache_key = ?",
                    (cache_key,),
                )
                connection.commit()
        except sqlite3.Error:
            return

    def load(
        self,
        contract: dict[str, object],
        *,
        now_epoch: float | None = None,
    ) -> dict[str, object]:
        now = float(time.time() if now_epoch is None else now_epoch)
        cache_key, contract_json = self._key(contract)
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT schema_version, contract_json, payload_zlib, payload_sha256,
                           stored_at_epoch, expires_at_epoch
                    FROM historical_market_data_cache
                    WHERE cache_key = ?
                    """,
                    (cache_key,),
                ).fetchone()
                if row is None:
                    return {"ok": True, "hit": False, "status": "cache_miss"}
                schema_version, stored_contract, compressed, expected_hash, stored_at, expires_at = row
                if (
                    schema_version != self.SCHEMA_VERSION
                    or stored_contract != contract_json
                    or float(expires_at) <= now
                    or not isinstance(compressed, bytes)
                    or len(compressed) > self.MAX_COMPRESSED_BYTES
                ):
                    connection.execute(
                        "DELETE FROM historical_market_data_cache WHERE cache_key = ?",
                        (cache_key,),
                    )
                    connection.commit()
                    return {"ok": True, "hit": False, "status": "cache_invalidated"}
                decompressor = zlib.decompressobj()
                payload_bytes = decompressor.decompress(
                    compressed,
                    self.MAX_DECOMPRESSED_BYTES + 1,
                )
                if (
                    len(payload_bytes) > self.MAX_DECOMPRESSED_BYTES
                    or not decompressor.eof
                    or decompressor.unconsumed_tail
                    or hashlib.sha256(payload_bytes).hexdigest() != str(expected_hash)
                ):
                    connection.execute(
                        "DELETE FROM historical_market_data_cache WHERE cache_key = ?",
                        (cache_key,),
                    )
                    connection.commit()
                    return {"ok": True, "hit": False, "status": "cache_hash_invalidated"}
                payload = json.loads(payload_bytes.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("cached payload must be an object")
                connection.execute(
                    "UPDATE historical_market_data_cache "
                    "SET last_access_epoch = ?, last_hit_epoch = ?, hit_count = hit_count + 1 "
                    "WHERE cache_key = ?",
                    (now, now, cache_key),
                )
                connection.commit()
                return {
                    "ok": True,
                    "hit": True,
                    "status": "cache_hit",
                    "payload": payload,
                    "payload_sha256": str(expected_hash),
                    "stored_at": datetime.fromtimestamp(float(stored_at), timezone.utc).isoformat(),
                    "expires_at": datetime.fromtimestamp(float(expires_at), timezone.utc).isoformat(),
                }
        except (sqlite3.Error, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, zlib.error) as exc:
            self.invalidate(contract)
            return {
                "ok": False,
                "hit": False,
                "status": "cache_read_failed",
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }

    def store(
        self,
        contract: dict[str, object],
        payload: dict[str, object],
        *,
        ttl_seconds: int,
        now_epoch: float | None = None,
    ) -> dict[str, object]:
        now = float(time.time() if now_epoch is None else now_epoch)
        ttl = max(60, min(int(ttl_seconds), 90 * 24 * 60 * 60))
        cache_key, contract_json = self._key(contract)
        payload_bytes = self._canonical(payload)
        if len(payload_bytes) > self.MAX_DECOMPRESSED_BYTES:
            return {"ok": False, "stored": False, "status": "payload_too_large"}
        compressed = zlib.compress(payload_bytes, level=6)
        if len(compressed) > self.MAX_COMPRESSED_BYTES:
            return {"ok": False, "stored": False, "status": "compressed_payload_too_large"}
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO historical_market_data_cache (
                        cache_key, schema_version, contract_json, payload_zlib, payload_sha256,
                        stored_at_epoch, expires_at_epoch, last_access_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        schema_version = excluded.schema_version,
                        contract_json = excluded.contract_json,
                        payload_zlib = excluded.payload_zlib,
                        payload_sha256 = excluded.payload_sha256,
                        stored_at_epoch = excluded.stored_at_epoch,
                        expires_at_epoch = excluded.expires_at_epoch,
                        last_access_epoch = excluded.last_access_epoch
                    """,
                    (
                        cache_key,
                        self.SCHEMA_VERSION,
                        contract_json,
                        sqlite3.Binary(compressed),
                        payload_hash,
                        now,
                        now + ttl,
                        now,
                    ),
                )
                connection.execute(
                    "DELETE FROM historical_market_data_cache WHERE expires_at_epoch <= ?",
                    (now,),
                )
                connection.execute(
                    """
                    DELETE FROM historical_market_data_cache
                    WHERE cache_key NOT IN (
                        SELECT cache_key FROM historical_market_data_cache
                        ORDER BY last_access_epoch DESC
                        LIMIT ?
                    )
                    """,
                    (self.max_entries,),
                )
                connection.commit()
            return {
                "ok": True,
                "stored": True,
                "status": "cache_stored",
                "payload_sha256": payload_hash,
                "expires_at": datetime.fromtimestamp(now + ttl, timezone.utc).isoformat(),
            }
        except (sqlite3.Error, OSError) as exc:
            return {
                "ok": False,
                "stored": False,
                "status": "cache_write_failed",
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }

    def status(self) -> dict[str, object]:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT COUNT(*), MIN(expires_at_epoch), MAX(last_access_epoch), "
                    "MAX(stored_at_epoch), COALESCE(SUM(hit_count), 0), "
                    "SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END), MAX(last_hit_epoch) "
                    "FROM historical_market_data_cache"
                ).fetchone() or (0, None, None, None, 0, 0, None)
            total_hit_count = int(row[4] or 0)
            return {
                "ok": True,
                "status": "ready",
                "schema": self.SCHEMA_VERSION,
                "entry_count": int(row[0] or 0),
                "max_entries": self.max_entries,
                "total_hit_count": total_hit_count,
                "reused_entry_count": int(row[5] or 0),
                "reuse_verified": total_hit_count > 0,
                "last_write_at": (
                    datetime.fromtimestamp(float(row[3]), timezone.utc).isoformat()
                    if row[3] is not None
                    else ""
                ),
                "last_hit_at": (
                    datetime.fromtimestamp(float(row[6]), timezone.utc).isoformat()
                    if row[6] is not None
                    else ""
                ),
                "source_last_success_at": (
                    datetime.fromtimestamp(float(row[2]), timezone.utc).isoformat()
                    if row[2] is not None
                    else ""
                ),
                "path": str(self.path),
            }
        except (sqlite3.Error, OSError) as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "entry_count": 0,
                "max_entries": self.max_entries,
                "path": str(self.path),
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }

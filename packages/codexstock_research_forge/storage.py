from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


_CONNECT_LOCK = threading.RLock()


class AnalyticalStorage:
    """DuckDB catalog plus partitioned Parquet analytical storage."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.db_path = root / "research_forge.duckdb"
        self.parquet_root = root / "parquet"
        self.migrations_root = root / "migrations"
        self.spool_root = root / "spool"
        root.mkdir(parents=True, exist_ok=True)
        self.parquet_root.mkdir(parents=True, exist_ok=True)
        self.migrations_root.mkdir(parents=True, exist_ok=True)
        self.spool_root.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def doctor() -> dict[str, Any]:
        try:
            duckdb = _duckdb()
            return {"ok": True, "backend": "duckdb", "version": duckdb.__version__, "parquet": True}
        except Exception as exc:
            return {"ok": False, "backend": "unavailable", "message": str(exc), "install": "pip install .[storage]"}

    def ingest(self, rows: Iterable[dict[str, Any]], timeframe: str, collection_job_id: str = "") -> dict[str, Any]:
        values = []
        for row in rows:
            prices = [float(row[key]) for key in ("open", "high", "low", "close")]
            volume = float(row.get("volume") or 0)
            if not all(math.isfinite(value) and value > 0 for value in prices) or prices[1] < max(prices) or prices[2] > min(prices) or not math.isfinite(volume) or volume < 0:
                raise ValueError("storage ingest contains invalid OHLCV")
            values.append(
                (
                    str(row["symbol"]).upper(), str(row["timestamp"]), timeframe,
                    prices[0], prices[1], prices[2], prices[3], volume, str(row.get("source") or "unknown"),
                    str(row.get("collected_at") or datetime.now(timezone.utc).isoformat()), collection_job_id,
                )
            )
        if not values:
            raise ValueError("storage ingest requires rows")
        connection = self._connect()
        try:
            before = connection.execute("SELECT count(*) FROM bars").fetchone()[0]
            connection.begin()
            if len(values) >= 500:
                self._bulk_insert(connection, values)
            else:
                connection.executemany("INSERT OR REPLACE INTO bars VALUES (?, ?::TIMESTAMPTZ, ?, ?, ?, ?, ?, ?, ?, ?::TIMESTAMPTZ, ?)", values)
            connection.commit()
            after = connection.execute("SELECT count(*) FROM bars").fetchone()[0]
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"ok": True, "received": len(values), "inserted_net": after - before, "row_count": after}

    def import_collection(self, collection_root: Path) -> dict[str, Any]:
        files, received, net = 0, 0, 0
        for path in sorted((collection_root / "bars").rglob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            result = self.ingest(payload.get("rows") or [], str(payload.get("timeframe") or path.parent.name), str(payload.get("collection_job_id") or ""))
            files += 1
            received += int(result["received"])
            net += int(result["inserted_net"])
        return {"ok": True, "files": files, "received": received, "inserted_net": net, **self.summary()}

    def import_legacy_ohlcv(
        self, cache_path: Path, symbols: list[str] | None = None, max_symbols: int = 0,
        batch_rows: int = 50_000, resume: bool = True,
    ) -> dict[str, Any]:
        """Stream the legacy top-level symbol cache without loading the full JSON file."""
        try:
            import ijson
        except ImportError as exc:
            raise RuntimeError("Streaming legacy import requires ijson: pip install .[storage]") from exc
        if not cache_path.is_file():
            raise FileNotFoundError(cache_path)
        selected = {str(value).upper() for value in (symbols or [])}
        batch_rows = max(1_000, min(250_000, int(batch_rows)))
        fingerprint = _file_hash(cache_path)
        checkpoint_path = self.migrations_root / f"legacy_{fingerprint}.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if resume and checkpoint_path.is_file() else {
            "schema_version": 1, "cache": cache_path.name, "cache_hash": f"sha256:{fingerprint}",
            "completed_symbols": [], "received": 0, "inserted_net": 0, "invalid_rows": 0,
            "invalid_samples": [], "status": "PENDING",
        }
        completed = set(checkpoint.get("completed_symbols") or [])
        initial_completed_count = len(completed)
        initial_invalid_rows = int(checkpoint.get("invalid_rows") or 0)
        initial_invalid_samples = list(checkpoint.get("invalid_samples") or [])
        imported_symbols = received = net = skipped = invalid_rows = 0
        invalid_samples: list[dict[str, Any]] = []
        buffer: list[dict[str, Any]] = []
        pending_symbols: list[str] = []

        def flush() -> None:
            nonlocal received, net, buffer, pending_symbols
            if not buffer: return
            result = self.ingest(buffer, "1d", f"legacy:{cache_path.name}")
            received += int(result["received"]); net += int(result["inserted_net"])
            completed.update(pending_symbols)
            checkpoint.update({"completed_symbols": sorted(completed), "received": int(checkpoint.get("received") or 0) + int(result["received"]), "inserted_net": int(checkpoint.get("inserted_net") or 0) + int(result["inserted_net"]), "invalid_rows": initial_invalid_rows + invalid_rows, "invalid_samples": initial_invalid_samples + invalid_samples, "status": "RUNNING", "updated_at": datetime.now(timezone.utc).isoformat()})
            checkpoint["invalid_samples"] = checkpoint["invalid_samples"][:20]
            self._write_json(checkpoint_path, checkpoint)
            buffer, pending_symbols = [], []
        with cache_path.open("rb") as stream:
            for key, payload in ijson.kvitems(stream, ""):
                symbol = str(key).upper()
                if symbol in completed:
                    skipped += 1
                    continue
                if selected and symbol not in selected:
                    skipped += 1
                    continue
                if max_symbols > 0 and imported_symbols >= max_symbols:
                    break
                symbol_valid_count = 0
                for source_row in payload.get("rows") or []:
                    candidate = {
                        "symbol": symbol,
                        "timestamp": source_row.get("timestamp") or f"{source_row.get('date')}T00:00:00+09:00",
                        "open": source_row["open"], "high": source_row["high"],
                        "low": source_row["low"], "close": source_row["close"],
                        "volume": source_row.get("volume") or 0,
                        "source": f"legacy:{payload.get('version') or 'ohlcv'}",
                    }
                    try:
                        prices = [float(candidate[field]) for field in ("open", "high", "low", "close")]
                        volume = float(candidate["volume"])
                        valid = all(math.isfinite(value) and value > 0 for value in prices) and prices[1] >= max(prices) and prices[2] <= min(prices) and math.isfinite(volume) and volume >= 0
                    except (TypeError, ValueError): valid = False
                    if valid: buffer.append(candidate); symbol_valid_count += 1
                    else:
                        invalid_rows += 1
                        if len(invalid_samples) < 20: invalid_samples.append({"symbol": symbol, "date": source_row.get("date"), "open": source_row.get("open"), "high": source_row.get("high"), "low": source_row.get("low"), "close": source_row.get("close"), "volume": source_row.get("volume")})
                if not symbol_valid_count:
                    skipped += 1
                    continue
                imported_symbols += 1
                pending_symbols.append(symbol)
                if len(buffer) >= batch_rows: flush()
        flush()
        checkpoint.update({"status": "COMPLETED", "finished_at": datetime.now(timezone.utc).isoformat()})
        self._write_json(checkpoint_path, checkpoint)
        return {
            "ok": True, "streaming": True, "cache": cache_path.name,
            "imported_symbols": imported_symbols, "skipped_symbols": skipped,
            "received": received, "inserted_net": net, "invalid_rows": invalid_rows,
            "cache_hash": checkpoint["cache_hash"], "checkpoint": str(checkpoint_path),
            "resumed_completed_symbols": initial_completed_count, **self.summary(),
        }

    def _bulk_insert(self, connection: Any, values: list[tuple[Any, ...]]) -> None:
        spool = self.spool_root / f"batch_{uuid4().hex}.jsonl"
        columns = ("symbol", "timestamp", "timeframe", "open", "high", "low", "close", "volume", "source", "collected_at", "collection_job_id")
        try:
            with spool.open("w", encoding="utf-8", newline="\n") as handle:
                for values_row in values:
                    handle.write(json.dumps(dict(zip(columns, values_row)), ensure_ascii=False, separators=(",", ":")) + "\n")
            path = spool.as_posix().replace("'", "''")
            schema = "{'symbol':'VARCHAR','timestamp':'VARCHAR','timeframe':'VARCHAR','open':'DOUBLE','high':'DOUBLE','low':'DOUBLE','close':'DOUBLE','volume':'DOUBLE','source':'VARCHAR','collected_at':'VARCHAR','collection_job_id':'VARCHAR'}"
            connection.execute(f"INSERT OR REPLACE INTO bars SELECT symbol, timestamp::TIMESTAMPTZ, timeframe, open, high, low, close, volume, source, collected_at::TIMESTAMPTZ, collection_job_id FROM read_json('{path}', format='newline_delimited', columns={schema})")
        finally:
            spool.unlink(missing_ok=True)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
        temporary.replace(path)

    def query(self, symbols: list[str], start: str, end: str, timeframe: str, limit: int = 10000) -> dict[str, Any]:
        limit = max(1, min(100_000, int(limit)))
        params: list[Any] = [timeframe, start, end]
        clause = "timeframe = ? AND timestamp >= ?::TIMESTAMPTZ AND timestamp <= ?::TIMESTAMPTZ"
        if symbols:
            normalized = [str(value).upper() for value in symbols]
            clause += f" AND symbol IN ({','.join('?' for _ in normalized)})"
            params.extend(normalized)
        params.append(limit)
        connection = self._connect(read_only=True)
        try:
            cursor = connection.execute(
                f"SELECT symbol, timestamp, open, high, low, close, volume, source, collection_job_id FROM bars WHERE {clause} ORDER BY timestamp, symbol LIMIT ?",
                params,
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
        finally:
            connection.close()
        for row in rows:
            row["timestamp"] = row["timestamp"].isoformat()
        digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"ok": True, "count": len(rows), "rows": rows, "result_hash": f"sha256:{digest}", "truncated": len(rows) == limit}

    def export_parquet(self) -> dict[str, Any]:
        connection = self._connect()
        destination = self.parquet_root.as_posix().replace("'", "''")
        try:
            connection.execute("SET threads = 1")
            connection.execute(
                f"COPY (SELECT *, year(timestamp) AS year, month(timestamp) AS month, lpad(cast(hash(symbol) % 8 AS VARCHAR), 2, '0') AS symbol_bucket FROM bars) TO '{destination}' (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (timeframe, year, month, symbol_bucket), OVERWRITE_OR_IGNORE true)"
            )
        finally:
            connection.close()
        files = list(self.parquet_root.rglob("*.parquet"))
        return {"ok": True, "parquet_files": len(files), "bytes": sum(path.stat().st_size for path in files), "partitioning": ["timeframe", "year", "month", "symbol_bucket"], "symbol_bucket_count": 8, "symbol_bucket_method": "duckdb_hash_modulo"}

    def summary(self) -> dict[str, Any]:
        connection = self._connect(read_only=True)
        try:
            row_count, symbols, minimum, maximum = connection.execute("SELECT count(*), count(DISTINCT symbol), min(timestamp), max(timestamp) FROM bars").fetchone()
        finally:
            connection.close()
        files = list(self.parquet_root.rglob("*.parquet"))
        return {"row_count": row_count, "symbol_count": symbols, "min_timestamp": minimum.isoformat() if minimum else None, "max_timestamp": maximum.isoformat() if maximum else None, "parquet_files": len(files), "database_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0}

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS bars (symbol VARCHAR, timestamp TIMESTAMPTZ, timeframe VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, source VARCHAR, collected_at TIMESTAMPTZ, collection_job_id VARCHAR, PRIMARY KEY(symbol, timestamp, timeframe, source))"
            )
        finally:
            connection.close()

    def _connect(self, read_only: bool = False):
        # DuckDB rejects mixed read_only/read_write configurations for the same
        # database inside one process. Query methods remain SQL read-only, while
        # sharing the writer-compatible connection configuration enables MVCC.
        last_error: Exception | None = None
        for attempt in range(50):
            try:
                with _CONNECT_LOCK:
                    return _duckdb().connect(str(self.db_path))
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if "file is already open" not in message and "another process" not in message and "다른 프로세스" not in message:
                    raise
                time.sleep(min(0.01 * (attempt + 1), 0.1))
        raise RuntimeError(f"DuckDB connection remained locked after bounded retry: {last_error}")


def _duckdb():
    try:
        import duckdb
        return duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB storage extra is required: pip install .[storage]") from exc


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

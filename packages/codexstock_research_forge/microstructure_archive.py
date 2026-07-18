from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class MicrostructureArchive:
    """Incremental JSONL-to-Parquet archive that never blocks or rewrites the live append log."""

    def __init__(self, microstructure_root: Path) -> None:
        self.store_root = microstructure_root
        self.events_root = microstructure_root / "events"
        self.root = microstructure_root / "archive"
        self.parquet_root = self.root / "parquet"
        self.spool_root = self.root / "spool"
        self.manifest_path = self.root / "manifest.json"
        self.parquet_root.mkdir(parents=True, exist_ok=True); self.spool_root.mkdir(parents=True, exist_ok=True)

    def export_incremental(self, max_source_files: int = 0) -> dict[str, Any]:
        manifest = self._load(); exported = []; skipped = []
        sources = sorted(self.events_root.glob("*/*/*.jsonl"))
        if max_source_files > 0: sources = sources[:max_source_files]
        for source in sources:
            key = source.relative_to(self.events_root).as_posix(); entry = manifest["sources"].setdefault(key, {"exported_bytes": 0, "chunks": []})
            offset = int(entry.get("exported_bytes") or 0); size = source.stat().st_size
            if size < offset: raise RuntimeError(f"live microstructure source was truncated: {key}")
            with source.open("rb") as handle: handle.seek(offset); raw = handle.read()
            complete_end = raw.rfind(b"\n") + 1
            if complete_end <= 0: skipped.append(key); continue
            chunk = raw[:complete_end]
            if not chunk.strip(): skipped.append(key); continue
            for line in chunk.splitlines(): json.loads(line)
            chunk_hash = hashlib.sha256(chunk).hexdigest(); event_type, day, filename = key.split("/"); symbol = Path(filename).stem
            target_dir = self.parquet_root / f"event_type={event_type}" / f"day={day}" / f"symbol={symbol}"; target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"part-{offset:020d}-{chunk_hash[:16]}.parquet"
            if target.exists(): raise RuntimeError("archive target collision")
            spool = self.spool_root / f"{uuid4().hex}.jsonl"; spool.write_bytes(chunk); temporary = target.with_suffix(".parquet.tmp")
            try:
                connection = _duckdb().connect()
                src, dst = _sql(spool), _sql(temporary)
                try:
                    rows = int(connection.execute(f"SELECT count(*) FROM read_json_auto('{src}', format='newline_delimited', union_by_name=true)").fetchone()[0])
                    connection.execute(f"COPY (SELECT * FROM read_json_auto('{src}', format='newline_delimited', union_by_name=true)) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)")
                finally: connection.close()
                temporary.replace(target)
            finally:
                if spool.exists(): spool.unlink()
                if temporary.exists(): temporary.unlink()
            evidence = {"source_offset": offset, "source_bytes": complete_end, "source_chunk_hash": f"sha256:{chunk_hash}", "rows": rows, "parquet_path": target.relative_to(self.root).as_posix(), "parquet_bytes": target.stat().st_size, "parquet_hash": f"sha256:{_hash(target)}", "exported_at": datetime.now(timezone.utc).isoformat()}
            entry["chunks"].append(evidence); entry["exported_bytes"] = offset + complete_end; entry["source_size_at_export"] = size; exported.append({"source": key, **evidence})
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat(); self._save(manifest)
        return {"ok": True, "exported_chunk_count": len(exported), "exported_rows": sum(row["rows"] for row in exported), "exported": exported, "skipped": skipped, "status": self.status()}

    def status(self) -> dict[str, Any]:
        manifest = self._load(); chunks = [chunk for entry in manifest["sources"].values() for chunk in entry.get("chunks") or []]
        return {"ok": True, "source_count": len(manifest["sources"]), "chunk_count": len(chunks), "row_count": sum(int(row.get("rows") or 0) for row in chunks), "parquet_bytes": sum(int(row.get("parquet_bytes") or 0) for row in chunks), "manifest_hash": manifest.get("manifest_hash"), "updated_at": manifest.get("updated_at")}

    def inventory(self) -> dict[str, Any]:
        keys = sorted(self._load()["sources"])
        parsed = [key.split("/") for key in keys if len(key.split("/")) == 3]
        return {"symbols": sorted({Path(parts[2]).stem for parts in parsed}), "days": sorted({parts[1] for parts in parsed}), "event_types": sorted({parts[0] for parts in parsed})}

    def verify(self) -> dict[str, Any]:
        manifest = self._load(); errors = []
        stored = manifest.pop("manifest_hash", None); expected = _payload_hash(manifest)
        if stored != expected: errors.append("manifest_hash_mismatch")
        checked = 0
        for entry in manifest["sources"].values():
            for chunk in entry.get("chunks") or []:
                path = self.root / str(chunk["parquet_path"]); checked += 1
                if not path.is_file(): errors.append(f"missing:{chunk['parquet_path']}")
                elif f"sha256:{_hash(path)}" != chunk.get("parquet_hash"): errors.append(f"hash:{chunk['parquet_path']}")
        return {"ok": not errors, "verified": not errors, "checked_chunks": checked, "errors": errors, "manifest_hash": stored}

    def query(self, symbols: list[str], start: str, end: str, event_types: list[str] | None = None, limit: int = 10_000) -> dict[str, Any]:
        normalized = sorted({str(value).upper() for value in symbols})
        types = sorted(set(event_types or ["tick", "orderbook", "program_flow"]))
        if not normalized or any(not value.isalnum() for value in normalized): raise ValueError("archive query requires alphanumeric symbols")
        if not set(types).issubset({"tick", "orderbook", "program_flow"}): raise ValueError("unsupported archive event type")
        first, last = _utc_naive(start), _utc_naive(end)
        if last < first: raise ValueError("archive query end precedes start")
        cap = max(1, min(100_000, int(limit)))
        files = []
        for event_type in types:
            for symbol in normalized: files.extend(str(path) for path in (self.parquet_root / f"event_type={event_type}").glob(f"day=*/symbol={symbol}/*.parquet"))
        if not files: return {"ok": True, "count": 0, "matched": 0, "truncated": False, "events": [], "backend": "parquet_duckdb"}
        symbol_marks = ",".join("?" for _ in normalized); type_marks = ",".join("?" for _ in types)
        sql = f"SELECT event_id,event_type,symbol,timestamp,source,to_json(payload),count(*) OVER() AS matched FROM read_parquet(?, union_by_name=true, hive_partitioning=false) WHERE symbol IN ({symbol_marks}) AND event_type IN ({type_marks}) AND timestamp BETWEEN ? AND ? ORDER BY timestamp,event_type,event_id LIMIT ?"
        connection = _duckdb().connect()
        try: rows = connection.execute(sql, [files, *normalized, *types, first, last, cap]).fetchall()
        finally: connection.close()
        events = [{"event_id": row[0], "event_type": row[1], "symbol": row[2], "timestamp": row[3].replace(tzinfo=timezone.utc).isoformat(), "source": row[4], "payload": json.loads(row[5]) if row[5] else {}} for row in rows]
        matched = int(rows[0][6]) if rows else 0
        return {"ok": True, "count": len(events), "matched": matched, "truncated": matched > cap, "events": events, "backend": "parquet_duckdb", "scanned_files": len(files)}

    def _load(self) -> dict[str, Any]:
        if not self.manifest_path.is_file(): return {"schema_version": 1, "sources": {}, "manifest_hash": None}
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("sources"), dict): raise ValueError("unsupported microstructure archive manifest")
        return payload

    def _save(self, manifest: dict[str, Any]) -> None:
        manifest.pop("manifest_hash", None); manifest["manifest_hash"] = _payload_hash(manifest)
        temporary = self.manifest_path.with_suffix(".json.tmp"); temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(self.manifest_path)


def _duckdb():
    try: import duckdb; return duckdb
    except ImportError as exc: raise RuntimeError("DuckDB storage extra is required") from exc


def _sql(path: Path) -> str: return path.as_posix().replace("'", "''")
def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()
def _payload_hash(payload: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"


def _utc_naive(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None: raise ValueError("archive query timestamps require timezone")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)

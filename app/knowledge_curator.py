from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable


KST = timezone(timedelta(hours=9))

SQLITE_KNOWLEDGE_TABLE_TOKENS = (
    "research", "meeting", "review", "replay", "learning", "strategy",
    "journal", "memory", "evidence", "insight", "backfill", "event", "source_meta",
)
SQLITE_PRIVATE_TABLE_TOKENS = (
    "account", "balance", "credential", "execution", "fill", "order",
    "position", "secret", "token",
)
SQLITE_PRIVATE_COLUMN_TOKENS = (
    "account", "acnt", "api_key", "app_key", "app_secret", "cano",
    "credential", "password", "secret", "token",
)


@dataclass(frozen=True)
class EnginePolicy:
    engine_id: str
    source_dir: str
    module_name: str
    role: str
    weight: str
    minimum_interval_hours: int
    minimum_changed_documents: int


ENGINE_POLICIES = (
    EnginePolicy("llamaindex", "llama_index", "llama_index", "document_ingestion", "medium", 6, 20),
    EnginePolicy("qdrant", "qdrant", "qdrant_client", "semantic_retrieval", "light", 1, 1),
    EnginePolicy("graphiti", "graphiti", "graphiti_core", "temporal_relationships", "heavy", 24, 30),
    EnginePolicy("graphrag", "graphrag", "graphrag", "global_synthesis", "very_heavy", 24 * 14, 300),
)


class KnowledgeCurator:
    """Read-only source index with optional specialist-engine scheduling.

    Source ledgers remain authoritative. This database only stores searchable
    projections and provenance needed to locate the original evidence.
    """

    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = Path(runtime_root)
        self.root = self.runtime_root / "knowledge_curator"
        self.engine_root = self.runtime_root.parent / "engines"
        self.runtime_python = self.engine_root / "_knowledge_runtime" / "Scripts" / "python.exe"
        self.worker_path = Path(__file__).with_name("knowledge_engine_worker.py")
        self._runtime_probe_cache: dict[str, tuple[datetime, bool, str]] = {}
        self._ollama_probe_cache: tuple[datetime, set[str], str] | None = None
        self._index_lock = threading.Lock()
        self._specialist_lock = threading.Lock()
        self._workspace_secret_hardening_error = ""
        self.root.mkdir(parents=True, exist_ok=True)
        self._harden_workspace_secrets()
        self.db_path = self.root / "knowledge_index.sqlite3"
        self._initialize()

    def _harden_workspace_secrets(self) -> None:
        """Keep specialist-engine environment files private to this user and SYSTEM."""
        secret_paths = (self.root / "graphrag_workspace" / ".env",)
        for path in secret_paths:
            if not path.is_file():
                continue
            try:
                os.chmod(path, 0o600)
            except OSError as exc:
                self._workspace_secret_hardening_error = str(exc)[:240]
                continue
            if os.name != "nt":
                continue
            username = str(os.environ.get("USERNAME") or "").strip()
            domain = str(
                os.environ.get("USERDOMAIN") or os.environ.get("COMPUTERNAME") or ""
            ).strip()
            if not username:
                self._workspace_secret_hardening_error = (
                    "Windows user identity is unavailable for knowledge secret ACL"
                )
                continue
            identity = f"{domain}\\{username}" if domain else username
            try:
                subprocess.run(
                    [
                        "icacls",
                        str(path),
                        "/inheritance:r",
                        "/grant:r",
                        f"{identity}:(F)",
                        "/grant:r",
                        "*S-1-5-18:(F)",
                    ],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self._workspace_secret_hardening_error = str(exc)[:240]

    def _connect(self, *, timeout_seconds: float = 30.0) -> sqlite3.Connection:
        timeout = max(0.1, float(timeout_seconds))
        connection = sqlite3.connect(self.db_path, timeout=timeout)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={max(100, int(timeout * 1000))}")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            # Journal mode is a database setting. Reissuing it on every read can
            # contend with the background index writer and stall status requests.
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_locator TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_content_hash TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    event_time TEXT,
                    indexed_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_documents_source
                    ON documents(source_path, source_locator);
                CREATE INDEX IF NOT EXISTS idx_documents_event_time
                    ON documents(event_time DESC);
                CREATE TABLE IF NOT EXISTS source_state (
                    source_path TEXT PRIMARY KEY,
                    source_size INTEGER NOT NULL,
                    source_mtime_ns INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    document_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS engine_runs (
                    engine_id TEXT PRIMARY KEY,
                    last_started_at TEXT,
                    last_completed_at TEXT,
                    last_status TEXT NOT NULL,
                    input_digest TEXT,
                    changed_document_count INTEGER NOT NULL DEFAULT 0,
                    detail TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS engine_run_history (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    engine_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_digest TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_engine_run_history_engine
                    ON engine_run_history(engine_id, run_id DESC);
                """
            )
            source_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(source_state)")
            }
            for column_name, definition in (
                ("source_offset", "INTEGER NOT NULL DEFAULT 0"),
                ("source_line_count", "INTEGER NOT NULL DEFAULT 0"),
                ("source_head_hash", "TEXT NOT NULL DEFAULT ''"),
                ("source_tail_hash", "TEXT NOT NULL DEFAULT ''"),
                ("source_digest", "TEXT NOT NULL DEFAULT ''"),
            ):
                if column_name not in source_columns:
                    connection.execute(
                        f"ALTER TABLE source_state ADD COLUMN {column_name} {definition}"
                    )
            document_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(documents)")
            }
            if "source_content_hash" not in document_columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN source_content_hash TEXT NOT NULL DEFAULT ''"
                )
            try:
                connection.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(document_id UNINDEXED, title, content)"
                )
            except sqlite3.OperationalError:
                pass

    @staticmethod
    def _canonical_text(value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _binary_safe_value(cls, value: object) -> object:
        if isinstance(value, bytes):
            return {
                "blob_size": len(value),
                "blob_sha256": hashlib.sha256(value).hexdigest(),
            }
        if isinstance(value, dict):
            return {
                str(key): cls._binary_safe_value(child)
                for key, child in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls._binary_safe_value(child) for child in value]
        return value

    @classmethod
    def _source_content_hash(cls, value: object) -> str:
        canonical = cls._canonical_text(cls._binary_safe_value(value))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _event_time(row: object) -> str:
        if not isinstance(row, dict):
            return ""
        for key in ("created_at", "generated_at", "updated_at", "work_date", "date", "timestamp"):
            value = str(row.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _title(row: object, fallback: str) -> str:
        if isinstance(row, dict):
            for key in ("title", "summary", "agenda", "name", "id", "event_type"):
                value = str(row.get(key) or "").strip()
                if value:
                    return value[:240]
        return fallback[:240]

    @staticmethod
    def _source_signature(path: Path) -> tuple[int, int]:
        stat = path.stat()
        total_size = int(stat.st_size)
        latest_mtime = int(stat.st_mtime_ns)
        if path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
            # WAL contains committed data; SHM is a volatile coordination file
            # whose timestamp can change on read-only connections.
            for suffix in ("-wal",):
                sidecar = Path(f"{path}{suffix}")
                if sidecar.is_file():
                    sidecar_stat = sidecar.stat()
                    total_size += int(sidecar_stat.st_size)
                    latest_mtime = max(latest_mtime, int(sidecar_stat.st_mtime_ns))
        return total_size, latest_mtime

    @staticmethod
    def _file_edge_hash(path: Path, *, end_offset: int, tail: bool) -> str:
        bounded_end = max(0, min(int(end_offset), int(path.stat().st_size)))
        if bounded_end <= 0:
            return ""
        size = min(4096, bounded_end)
        start = bounded_end - size if tail else 0
        with path.open("rb") as stream:
            stream.seek(start)
            return hashlib.sha256(stream.read(size)).hexdigest()

    @staticmethod
    def _file_sha256(path: Path, *, end_offset: int | None = None) -> str:
        remaining = None if end_offset is None else max(0, int(end_offset))
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while remaining is None or remaining > 0:
                chunk_size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                if remaining is not None:
                    remaining -= len(chunk)
        return digest.hexdigest()

    def _source_state_row(self, path: Path) -> dict[str, object]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM source_state WHERE source_path = ?",
                (str(path.resolve()),),
            ).fetchone()
        return dict(row) if row else {}

    def _source_unchanged(self, path: Path) -> bool:
        source_size, source_mtime_ns = self._source_signature(path)
        row = self._source_state_row(path)
        signature_matches = bool(
            row
            and row["source_size"] == source_size
            and row["source_mtime_ns"] == source_mtime_ns
        )
        if not signature_matches:
            suffix = path.suffix.lower()
            previous_digest = str(row.get("source_digest") or "") if row else ""
            if suffix not in {".sqlite", ".sqlite3", ".db"} and previous_digest:
                current_digest = self._file_sha256(path)
                if current_digest == previous_digest:
                    with closing(self._connect()) as connection, connection:
                        connection.execute(
                            "UPDATE source_state SET source_size = ?, source_mtime_ns = ? "
                            "WHERE source_path = ?",
                            (source_size, source_mtime_ns, str(path.resolve())),
                        )
                    signature_matches = True
            if not signature_matches:
                return False
        suffix = path.suffix.lower()
        if (
            suffix not in {".sqlite", ".sqlite3", ".db"}
            and row
            and not str(row.get("source_digest") or "")
        ):
            digest_end = int(row.get("source_offset") or 0) if suffix == ".jsonl" else 0
            source_digest = self._file_sha256(
                path,
                end_offset=digest_end if digest_end > 0 else None,
            )
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "UPDATE source_state SET source_digest = ? WHERE source_path = ?",
                    (source_digest, str(path.resolve())),
                )
        # Documents created before source/projection hashes were separated need
        # one safe rebuild even when their source file itself did not change.
        with closing(self._connect()) as connection:
            legacy_projection = connection.execute(
                "SELECT 1 FROM documents WHERE source_path = ? "
                "AND source_content_hash = '' LIMIT 1",
                (str(path.resolve()),),
            ).fetchone()
        return legacy_projection is None

    @staticmethod
    def _read_jsonl(
        path: Path,
        *,
        start_offset: int = 0,
        start_line: int = 0,
    ) -> tuple[list[tuple[str, object]], int, int]:
        rows: list[tuple[str, object]] = []
        line_number = max(0, int(start_line))
        final_offset = max(0, int(start_offset))
        file_size = int(path.stat().st_size)
        with path.open("rb") as stream:
            stream.seek(final_offset)
            while True:
                line_start = stream.tell()
                raw_line = stream.readline()
                if not raw_line:
                    break
                # Do not index a line while another process may still be writing it.
                if not raw_line.endswith(b"\n") and stream.tell() >= file_size:
                    final_offset = line_start
                    break
                line_number += 1
                final_offset = stream.tell()
                encoding = "utf-8-sig" if line_start == 0 else "utf-8"
                line = raw_line.decode(encoding, errors="replace").strip()
                if not line:
                    continue
                try:
                    value: object = json.loads(line)
                except json.JSONDecodeError:
                    value = line
                rows.append((f"line:{line_number}", value))
        return rows, line_number, final_offset

    @staticmethod
    def _sqlite_identifier(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    @staticmethod
    def _sqlite_table_allowed(table_name: str) -> bool:
        normalized = table_name.lower()
        identifier_tokens = {
            token.rstrip("s")
            for token in re.findall(r"[a-z0-9]+", normalized)
            if token
        }
        if any(token in identifier_tokens for token in SQLITE_PRIVATE_TABLE_TOKENS):
            return False
        return any(token in normalized for token in SQLITE_KNOWLEDGE_TABLE_TOKENS)

    @classmethod
    def _sanitize_sqlite_value(cls, key: str, value: object) -> object:
        normalized_key = re.sub(r"[^a-z0-9]+", "_", key.lower())
        if any(token in normalized_key for token in SQLITE_PRIVATE_COLUMN_TOKENS):
            return "[REDACTED]"
        if isinstance(value, bytes):
            return {
                "blob_size": len(value),
                "blob_sha256": hashlib.sha256(value).hexdigest(),
            }
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                try:
                    return cls._sanitize_sqlite_value(key, json.loads(stripped))
                except json.JSONDecodeError:
                    pass
            return value
        if isinstance(value, dict):
            return {
                str(child_key): cls._sanitize_sqlite_value(str(child_key), child_value)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list):
            return [cls._sanitize_sqlite_value(key, item) for item in value]
        return value

    def _iter_sqlite_source(self, path: Path) -> Iterable[tuple[str, object]]:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            tables = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
                if self._sqlite_table_allowed(str(row[0]))
            ]
            remaining = 50_000
            for table_name in tables:
                if remaining <= 0:
                    break
                quoted_table = self._sqlite_identifier(table_name)
                columns = list(connection.execute(f"PRAGMA table_info({quoted_table})"))
                column_names = [str(row[1]) for row in columns]
                primary_keys = [str(row[1]) for row in columns if int(row[5] or 0) > 0]
                safe_limit = min(remaining, 20_000)
                rows = connection.execute(f"SELECT * FROM {quoted_table} LIMIT ?", (safe_limit,))
                for ordinal, row in enumerate(rows, start=1):
                    payload = {column_name: row[column_name] for column_name in column_names}
                    if primary_keys:
                        key_text = "|".join(str(row[column]) for column in primary_keys)
                        locator = f"table:{table_name}/pk:{key_text}"
                    else:
                        locator = f"table:{table_name}/row:{ordinal}"
                    yield locator, payload
                    remaining -= 1
                    if remaining <= 0:
                        break

    def _iter_source(self, path: Path) -> Iterable[tuple[str, object]]:
        suffix = path.suffix.lower()
        if suffix in {".sqlite", ".sqlite3", ".db"}:
            yield from self._iter_sqlite_source(path)
            return
        if suffix == ".jsonl":
            rows, _, _ = self._read_jsonl(path)
            yield from rows
            return
        if suffix == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                payload = path.read_text(encoding="utf-8-sig", errors="replace")
            if isinstance(payload, list):
                for index, item in enumerate(payload):
                    yield f"item:{index}", item
            else:
                yield "document", payload
            return
        yield "document", path.read_text(encoding="utf-8-sig", errors="replace")

    def index_paths(self, paths: Iterable[Path], *, force: bool = False) -> dict[str, object]:
        # The scheduler and manual API share one curator instance. Serialize their
        # projection writes so a long first import cannot make the other path skip
        # sources with transient `database is locked` errors.
        with self._index_lock:
            return self._index_paths_locked(paths, force=force)

    def _index_paths_locked(self, paths: Iterable[Path], *, force: bool = False) -> dict[str, object]:
        indexed = 0
        changed_documents = 0
        unchanged = 0
        skipped = 0
        scanned_sources = 0
        incremental_sources = 0
        full_reindexed_sources = 0
        errors: list[dict[str, str]] = []
        now = datetime.now(KST).isoformat(timespec="seconds")
        for raw_path in paths:
            path = Path(raw_path)
            if not path.is_file() or path.suffix.lower() not in {
                ".jsonl", ".json", ".md", ".txt", ".sqlite", ".sqlite3", ".db",
            }:
                skipped += 1
                continue
            scanned_sources += 1
            try:
                if not force and self._source_unchanged(path):
                    unchanged += 1
                    continue
                suffix = path.suffix.lower()
                source_state = self._source_state_row(path)
                append_mode = False
                source_offset = int(path.stat().st_size)
                source_line_count = 0
                source_head_hash = ""
                source_tail_hash = ""
                source_digest = ""
                if suffix == ".jsonl":
                    previous_offset = int(source_state.get("source_offset") or 0)
                    previous_line_count = int(source_state.get("source_line_count") or 0)
                    current_size = int(path.stat().st_size)
                    previous_head_hash = str(source_state.get("source_head_hash") or "")
                    previous_tail_hash = str(source_state.get("source_tail_hash") or "")
                    append_mode = bool(
                        not force
                        and source_state
                        and previous_offset > 0
                        and current_size > previous_offset
                        and previous_head_hash
                        and previous_tail_hash
                        and previous_head_hash == self._file_edge_hash(
                            path, end_offset=previous_offset, tail=False
                        )
                        and previous_tail_hash == self._file_edge_hash(
                            path, end_offset=previous_offset, tail=True
                        )
                    )
                    if append_mode:
                        rows, source_line_count, source_offset = self._read_jsonl(
                            path,
                            start_offset=previous_offset,
                            start_line=previous_line_count,
                        )
                    else:
                        rows, source_line_count, source_offset = self._read_jsonl(path)
                    source_head_hash = self._file_edge_hash(
                        path, end_offset=source_offset, tail=False
                    )
                    source_tail_hash = self._file_edge_hash(
                        path, end_offset=source_offset, tail=True
                    )
                    source_digest = self._file_sha256(path, end_offset=source_offset)
                else:
                    rows = list(self._iter_source(path))
                    if suffix not in {".sqlite", ".sqlite3", ".db"}:
                        source_digest = self._file_sha256(path)
                total_document_count = (
                    int(source_state.get("document_count") or 0) + len(rows)
                    if append_mode
                    else len(rows)
                )
                resolved = str(path.resolve())
                with closing(self._connect()) as connection, connection:
                    fts_available = connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE name='documents_fts'"
                    ).fetchone() is not None
                    previous_hashes: dict[str, str] = {}
                    if not append_mode:
                        previous_hashes = {
                            str(row["document_id"]): str(row["content_hash"])
                            for row in connection.execute(
                                "SELECT document_id, content_hash FROM documents WHERE source_path = ?",
                                (resolved,),
                            ).fetchall()
                        }
                        previous_ids = list(previous_hashes)
                        if fts_available and previous_ids:
                            # FTS virtual tables can turn one DELETE per document
                            # into repeated scans. Delete bounded groups instead.
                            for offset in range(0, len(previous_ids), 400):
                                batch = previous_ids[offset:offset + 400]
                                placeholders = ",".join("?" for _ in batch)
                                connection.execute(
                                    f"DELETE FROM documents_fts WHERE document_id IN ({placeholders})",
                                    batch,
                                )
                        connection.execute("DELETE FROM documents WHERE source_path = ?", (resolved,))
                    current_ids: set[str] = set()
                    for locator, row in rows:
                        source_content_hash = self._source_content_hash(row)
                        safe_row = self._sanitize_sqlite_value("", row)
                        content = self._canonical_text(safe_row)
                        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                        document_id = hashlib.sha256(f"{resolved}|{locator}".encode("utf-8")).hexdigest()
                        current_ids.add(document_id)
                        if append_mode or previous_hashes.get(document_id) != content_hash:
                            changed_documents += 1
                        title = self._title(safe_row, path.stem)
                        metadata = {
                            "source_name": path.name,
                            "source_suffix": path.suffix.lower(),
                            "content_hash": content_hash,
                            "source_content_hash": source_content_hash,
                            "redacted_projection": source_content_hash != content_hash,
                        }
                        connection.execute(
                            """INSERT INTO documents
                            (document_id, source_path, source_kind, source_locator, content_hash,
                             source_content_hash, title, content, event_time, indexed_at, metadata_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(document_id) DO UPDATE SET
                              content_hash=excluded.content_hash,
                              source_content_hash=excluded.source_content_hash,
                              title=excluded.title, content=excluded.content,
                              event_time=excluded.event_time, indexed_at=excluded.indexed_at,
                              metadata_json=excluded.metadata_json""",
                            (document_id, resolved, path.suffix.lower().lstrip("."), locator, content_hash,
                             source_content_hash, title, content, self._event_time(safe_row), now,
                             json.dumps(metadata, ensure_ascii=False, sort_keys=True)),
                        )
                        if fts_available:
                            connection.execute(
                                "INSERT INTO documents_fts(document_id, title, content) VALUES (?, ?, ?)",
                                (document_id, title, content),
                            )
                    if not append_mode:
                        changed_documents += len(set(previous_hashes) - current_ids)
                    source_size, source_mtime_ns = self._source_signature(path)
                    connection.execute(
                        """INSERT INTO source_state
                        (source_path, source_size, source_mtime_ns, indexed_at, document_count,
                         source_offset, source_line_count, source_head_hash, source_tail_hash,
                         source_digest)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_path) DO UPDATE SET source_size=excluded.source_size,
                          source_mtime_ns=excluded.source_mtime_ns, indexed_at=excluded.indexed_at,
                           document_count=excluded.document_count, source_offset=excluded.source_offset,
                           source_line_count=excluded.source_line_count,
                           source_head_hash=excluded.source_head_hash,
                           source_tail_hash=excluded.source_tail_hash,
                           source_digest=excluded.source_digest""",
                        (
                            resolved, source_size, source_mtime_ns, now, total_document_count,
                            source_offset, source_line_count, source_head_hash, source_tail_hash,
                            source_digest,
                        ),
                    )
                indexed += len(rows)
                if append_mode:
                    incremental_sources += 1
                else:
                    full_reindexed_sources += 1
            except (OSError, sqlite3.Error, UnicodeError) as exc:
                errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"[:300]})
        return {
            "ok": not errors,
            "indexed_documents": indexed,
            "changed_documents": changed_documents,
            "scanned_sources": scanned_sources,
            "changed_sources": incremental_sources + full_reindexed_sources,
            "unchanged_sources": unchanged,
            "skipped_sources": skipped,
            "incremental_sources": incremental_sources,
            "full_reindexed_sources": full_reindexed_sources,
            "errors": errors,
            "source_immutable": True,
            "live_order_allowed": False,
        }

    def search(self, query: str, *, limit: int = 10) -> dict[str, object]:
        normalized = " ".join(str(query or "").split())
        if not normalized:
            return {"ok": False, "error": "query_required", "results": []}
        safe_limit = max(1, min(int(limit), 50))
        with closing(self._connect()) as connection:
            fts_available = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='documents_fts'"
            ).fetchone() is not None
            if fts_available:
                terms = [term.replace('"', "") for term in normalized.split() if term]
                match = " OR ".join(f'"{term}"' for term in terms)
                try:
                    rows = connection.execute(
                        """SELECT d.*, bm25(documents_fts) AS relevance
                        FROM documents_fts JOIN documents d USING(document_id)
                        WHERE documents_fts MATCH ? ORDER BY relevance, d.event_time DESC LIMIT ?""",
                        (match, safe_limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            else:
                rows = []
            if not rows:
                pattern = f"%{normalized}%"
                rows = connection.execute(
                    """SELECT *, 0.0 AS relevance FROM documents
                    WHERE title LIKE ? OR content LIKE ? ORDER BY event_time DESC LIMIT ?""",
                    (pattern, pattern, safe_limit),
                ).fetchall()
        results = []
        for row in rows:
            content = str(row["content"])
            results.append(
                {
                    "document_id": row["document_id"],
                    "title": row["title"],
                    "excerpt": content[:600],
                    "event_time": row["event_time"],
                    "source": {
                        "path": row["source_path"],
                        "locator": row["source_locator"],
                        "content_hash": row["source_content_hash"] or row["content_hash"],
                        "projection_hash": row["content_hash"],
                        "redacted_projection": bool(
                            row["source_content_hash"]
                            and row["source_content_hash"] != row["content_hash"]
                        ),
                    },
                    "relevance": float(row["relevance"] or 0),
                }
            )
        return {"ok": True, "query": normalized, "result_count": len(results), "results": results}

    def index_fingerprint(self) -> dict[str, object]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT source_path, source_size, source_mtime_ns, document_count, source_digest "
                "FROM source_state ORDER BY source_path"
            ).fetchall()
            document_count = int(
                connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            )
        canonical = [
            (
                str(row["source_path"]),
                int(row["document_count"]),
                str(row["source_digest"] or "")
                or f'{int(row["source_size"])}:{int(row["source_mtime_ns"])}',
            )
            for row in rows
        ]
        digest = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "digest": digest,
            "document_count": document_count,
            "source_count": len(rows),
        }

    def engine_status(self, *, refresh_runtime_probes: bool = True) -> dict[str, object]:
        engines = []
        fingerprint = self.index_fingerprint()
        with closing(self._connect()) as connection:
            run_rows = {row["engine_id"]: dict(row) for row in connection.execute("SELECT * FROM engine_runs")}
            counts = connection.execute(
                "SELECT COUNT(*) AS documents, COUNT(DISTINCT source_path) AS sources FROM documents"
            ).fetchone()
            history_rows = connection.execute(
                "SELECT * FROM engine_run_history ORDER BY run_id DESC LIMIT 20"
            ).fetchall()
        runtime_probe_results: dict[str, tuple[bool, str, bool]] = {}

        def runtime_probe(module_name: str) -> tuple[bool, str, bool]:
            cached_result = runtime_probe_results.get(module_name)
            if cached_result is not None:
                return cached_result
            if refresh_runtime_probes:
                installed, probe_status = self._probe_runtime(module_name)
                result = (installed, probe_status, False)
            else:
                result = self._runtime_probe_snapshot(module_name)
            runtime_probe_results[module_name] = result
            return result

        if refresh_runtime_probes:
            ollama_models, ollama_probe = self._probe_ollama()
            ollama_probe_stale = False
        else:
            ollama_models, ollama_probe, ollama_probe_stale = self._ollama_probe_snapshot()

        for policy in ENGINE_POLICIES:
            run = run_rows.get(policy.engine_id, {})
            detail_text = str(run.get("detail") or "")
            try:
                last_evidence = json.loads(detail_text) if detail_text else {}
                if not isinstance(last_evidence, dict):
                    last_evidence = {}
            except json.JSONDecodeError:
                last_evidence = {"error": detail_text} if detail_text else {}
            source_path = self.engine_root / policy.source_dir
            source_downloaded = source_path.is_dir() and any(source_path.iterdir())
            runtime_installed, runtime_probe_status, runtime_probe_stale = runtime_probe(
                policy.module_name
            )
            prerequisite_blockers: list[str] = []
            kuzu_installed = False
            if policy.engine_id == "graphiti":
                kuzu_installed, _, _ = runtime_probe("kuzu")
                neo4j_configured = bool(
                    os.getenv("CODEXSTOCK_GRAPHITI_NEO4J_URI", "").strip()
                    and os.getenv("CODEXSTOCK_GRAPHITI_NEO4J_PASSWORD", "").strip()
                )
                if not (kuzu_installed or neo4j_configured):
                    prerequisite_blockers.append("graph_database_not_configured")
                if not (os.getenv("OPENAI_API_KEY", "").strip() or ollama_models):
                    prerequisite_blockers.append("llm_provider_not_configured")
            if policy.engine_id == "graphrag":
                workspace = self.root / "graphrag_workspace"
                settings_path = workspace / "settings.yaml"
                settings_text = settings_path.read_text(encoding="utf-8", errors="replace") if settings_path.is_file() else ""
                if not settings_text:
                    prerequisite_blockers.append("graphrag_workspace_not_initialized")
                local_configured = (
                    "model_provider: ollama" in settings_text
                    and "model: bge-m3" in settings_text
                    and "model: qwen2.5:3b" in settings_text
                )
                if local_configured and "bge-m3:latest" not in ollama_models and "bge-m3" not in ollama_models:
                    prerequisite_blockers.append("ollama_embedding_model_not_available")
                if not local_configured and not os.getenv("OPENAI_API_KEY", "").strip():
                    prerequisite_blockers.append("llm_provider_not_configured")
                if self._workspace_secret_hardening_error:
                    prerequisite_blockers.append("workspace_secret_acl_not_private")
            operational_ready = runtime_installed and not prerequisite_blockers
            automatic_enabled = (
                True
                if policy.engine_id in {"qdrant", "llamaindex"}
                else str(
                    os.getenv(
                        f"CODEXSTOCK_{policy.engine_id.upper()}_AUTO_ENABLED",
                        "0",
                    )
                ).strip().lower() in {"1", "true", "yes", "on"}
            )
            index_stale = str(run.get("input_digest") or "") != str(fingerprint["digest"])
            last_status = str(run.get("last_status") or "never_run")
            engines.append(
                {
                    "engine_id": policy.engine_id,
                    "role": policy.role,
                    "weight": policy.weight,
                    "source_downloaded": source_downloaded,
                    "source_path": str(source_path),
                    "runtime_installed": runtime_installed,
                    "runtime_probe": runtime_probe_status,
                    "runtime_probe_stale": runtime_probe_stale,
                    "runtime_python": str(self.runtime_python),
                    "ollama_probe": ollama_probe if policy.engine_id in {"graphiti", "graphrag"} else None,
                    "ollama_probe_stale": (
                        ollama_probe_stale if policy.engine_id in {"graphiti", "graphrag"} else None
                    ),
                    "backend": (
                        "kuzu_local_compatibility"
                        if policy.engine_id == "graphiti" and kuzu_installed
                        else "neo4j"
                        if policy.engine_id == "graphiti"
                        else None
                    ),
                    "warnings": (
                        ["kuzu_backend_is_transitional_and_deprecated_upstream"]
                        if policy.engine_id == "graphiti" and kuzu_installed
                        else []
                    ),
                    "operational_ready": operational_ready,
                    "automatic_enabled": automatic_enabled,
                    "prerequisite_blockers": prerequisite_blockers,
                    "installed": runtime_installed,
                    "readiness": (
                        "operational_ready"
                        if operational_ready
                        else "prerequisites_blocked"
                        if runtime_installed and prerequisite_blockers
                        else "source_only"
                        if source_downloaded
                        else "not_downloaded"
                    ),
                    "mode": "always_available" if policy.engine_id == "qdrant" else "on_demand",
                    "minimum_interval_hours": policy.minimum_interval_hours,
                    "minimum_changed_documents": policy.minimum_changed_documents,
                    "last_status": last_status,
                    "last_completed_at": run.get("last_completed_at"),
                    "input_digest": run.get("input_digest"),
                    "index_stale": index_stale,
                    "coverage_state": (
                        "stale"
                        if last_status == "completed" and index_stale
                        else
                        "complete"
                        if last_status == "completed"
                        else "partial"
                        if last_status == "partial"
                        else "validated"
                        if last_status == "validated"
                        else "failed"
                        if last_status == "failed"
                        else "unverified"
                    ),
                    "last_evidence": last_evidence,
                }
            )
        return {
            "ok": True,
            "schema": "codexstock_knowledge_curator_status_v1",
            "employee": "knowledge_curator",
            "mode": "lightweight_always_on",
            "indexed_documents": int(counts["documents"] if counts else 0),
            "indexed_sources": int(counts["sources"] if counts else 0),
            "index_fingerprint": fingerprint,
            "engines": engines,
            "recent_engine_runs": [dict(row) for row in history_rows],
            "heavy_engine_concurrency": 1,
            "dependency_probe_mode": (
                "active_refresh" if refresh_runtime_probes else "cached_snapshot"
            ),
            "execution_policy": {
                "always_on": "sqlite_fts_projection_and_change_detection",
                "market_hours": ["qdrant_incremental_when_stale"],
                "off_hours": ["qdrant_incremental", "llamaindex_incremental"],
                "heavy_opt_in": ["graphiti_temporal_projection", "graphrag_global_synthesis"],
                "heavy_engines_default_enabled": False,
                "one_specialist_at_a_time": True,
            },
            "source_immutable": True,
            "live_order_allowed": False,
        }

    def _probe_ollama(self) -> tuple[set[str], str]:
        now = datetime.now(KST)
        if self._ollama_probe_cache and now - self._ollama_probe_cache[0] < timedelta(minutes=2):
            return self._ollama_probe_cache[1], self._ollama_probe_cache[2]
        models: set[str] = set()
        status = "unavailable"
        base = str(os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
        try:
            with urllib.request.urlopen(f"{base}/api/tags", timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            for row in payload.get("models", []) if isinstance(payload, dict) else []:
                if isinstance(row, dict):
                    for key in ("name", "model"):
                        value = str(row.get(key) or "").strip()
                        if value:
                            models.add(value)
            status = "available" if models else "available_no_models"
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            status = "unavailable"
        self._ollama_probe_cache = (now, models, status)
        return models, status

    def _ollama_probe_snapshot(self) -> tuple[set[str], str, bool]:
        cached = self._ollama_probe_cache
        if cached is None:
            return set(), "not_probed", True
        observed_at, models, status = cached
        stale = datetime.now(KST) - observed_at >= timedelta(minutes=2)
        return set(models), status, stale

    def _runtime_probe_snapshot(self, module_name: str) -> tuple[bool, str, bool]:
        cached = self._runtime_probe_cache.get(module_name)
        if cached is None:
            return False, "not_probed", True
        observed_at, installed, probe_status = cached
        stale = datetime.now(KST) - observed_at >= timedelta(minutes=5)
        return installed, probe_status, stale

    def _probe_runtime(self, module_name: str) -> tuple[bool, str]:
        if importlib.util.find_spec(module_name) is not None:
            return True, "host_import"
        now = datetime.now(KST)
        cached = self._runtime_probe_cache.get(module_name)
        if cached and now - cached[0] < timedelta(minutes=5):
            return cached[1], cached[2]
        installed = False
        probe_status = "isolated_runtime_missing"
        if self.runtime_python.is_file():
            try:
                probe = subprocess.run(
                    [str(self.runtime_python), "-c", f"import {module_name}; print('ok')"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                    check=False,
                )
                installed = probe.returncode == 0 and "ok" in probe.stdout
                probe_status = "isolated_import_ok" if installed else "isolated_import_failed"
            except (OSError, subprocess.SubprocessError):
                probe_status = "isolated_import_error"
        self._runtime_probe_cache[module_name] = (now, installed, probe_status)
        return installed, probe_status

    def plan_engine_work(
        self,
        *,
        changed_documents: int,
        market_open: bool,
        heavy_work_allowed: bool | None = None,
        now: datetime | None = None,
    ) -> dict[str, object]:
        current = now or datetime.now(KST)
        status_payload = self.engine_status()
        status = {row["engine_id"]: row for row in status_payload["engines"]}
        fingerprint = status_payload.get("index_fingerprint") or self.index_fingerprint()
        jobs = []
        for policy in ENGINE_POLICIES:
            engine = status[policy.engine_id]
            reasons: list[str] = []
            allowed = True
            if market_open and policy.weight in {"medium", "heavy", "very_heavy"}:
                allowed = False
                reasons.append("deferred_during_market_hours")
            if (
                heavy_work_allowed is False
                and policy.weight in {"heavy", "very_heavy"}
            ):
                allowed = False
                reasons.append("heavy_window_not_open")
            if not engine["installed"]:
                allowed = False
                reasons.append("engine_not_installed")
            elif not engine.get("operational_ready"):
                allowed = False
                reasons.extend(str(item) for item in engine.get("prerequisite_blockers", []))
            if not engine.get("automatic_enabled"):
                allowed = False
                reasons.append("automatic_execution_not_enabled")
            engine_stale = str(engine.get("input_digest") or "") != str(fingerprint["digest"])
            available_evidence = int(changed_documents) if changed_documents else (
                int(fingerprint["document_count"]) if engine_stale else 0
            )
            if available_evidence < policy.minimum_changed_documents:
                allowed = False
                reasons.append("insufficient_new_evidence")
            completed = (
                str(engine.get("last_completed_at") or "")
                if str(engine.get("last_status") or "") == "completed"
                else ""
            )
            if completed:
                try:
                    elapsed = current - datetime.fromisoformat(completed)
                    if elapsed < timedelta(hours=policy.minimum_interval_hours):
                        allowed = False
                        reasons.append("minimum_interval_not_elapsed")
                except ValueError:
                    reasons.append("invalid_last_completed_at")
            jobs.append(
                {
                    "engine_id": policy.engine_id,
                    "decision": "queue" if allowed else "skip",
                    "reasons": reasons or ["new_evidence_requires_refresh"],
                    "weight": policy.weight,
                    "index_stale": engine_stale,
                    "available_evidence": available_evidence,
                }
            )
        queued = [job for job in jobs if job["decision"] == "queue"]
        weight_order = {"light": 0, "medium": 1, "heavy": 2, "very_heavy": 3}
        queued.sort(key=lambda row: (weight_order.get(str(row["weight"]), 99), row["engine_id"]))
        return {
            "ok": True,
            "market_open": market_open,
            "heavy_work_allowed": not market_open if heavy_work_allowed is None else heavy_work_allowed,
            "changed_documents": max(0, int(changed_documents)),
            "index_fingerprint": fingerprint,
            "jobs": jobs,
            "next_job": queued[0] if queued else None,
            "queued_count": len(queued),
            "heavy_engine_concurrency": 1,
            "duplicate_work_blocked": True,
            "live_order_allowed": False,
        }

    def run_specialist(self, operation: str, **options: object) -> dict[str, object]:
        allowed = {
            "qdrant_sync": "qdrant",
            "qdrant_search": "qdrant",
            "llamaindex_sync": "llamaindex",
            "graphrag_init": "graphrag",
            "graphrag_validate": "graphrag",
            "graphrag_index": "graphrag",
            "graphiti_probe": "graphiti",
            "graphiti_sync": "graphiti",
        }
        engine_id = allowed.get(str(operation))
        if not engine_id:
            return {"ok": False, "error": "unsupported_operation", "live_order_allowed": False}
        if not self.runtime_python.is_file() or not self.worker_path.is_file():
            return {"ok": False, "error": "isolated_runtime_not_ready", "engine_id": engine_id, "live_order_allowed": False}
        if not self._specialist_lock.acquire(blocking=False):
            return {
                "ok": False,
                "error": "specialist_engine_busy",
                "engine_id": engine_id,
                "retryable": True,
                "live_order_allowed": False,
            }
        projection_lock_acquired = False
        try:
            if operation != "qdrant_search":
                self._index_lock.acquire()
                projection_lock_acquired = True
            return self._run_specialist_locked(operation, engine_id, **options)
        finally:
            if projection_lock_acquired:
                self._index_lock.release()
            self._specialist_lock.release()

    def _run_specialist_locked(
        self,
        operation: str,
        engine_id: str,
        **options: object,
    ) -> dict[str, object]:
        payload = {
            "operation": operation,
            "index_db": str(self.db_path),
            "qdrant_path": str(self.root / "qdrant"),
            "qdrant_state_db": str(self.root / "qdrant_sync.sqlite3"),
            "chunk_db": str(self.root / "llamaindex_chunks.sqlite3"),
            "workspace": str(self.root / "graphrag_workspace"),
            "graphiti_path": str(
                Path(
                    os.getenv(
                        "CODEXSTOCK_GRAPHITI_LOCAL_PATH",
                        r"C:\CodexStockRuntime\knowledge_curator\graphiti.kuzu",
                    )
                )
            ),
            "graphiti_state_db": str(self.root / "graphiti_sync.sqlite3"),
            **options,
        }
        started = datetime.now(KST)
        digest = str(self.index_fingerprint()["digest"])
        try:
            process = subprocess.run(
                [str(self.runtime_python), str(self.worker_path)],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=max(15, min(int(options.get("timeout_seconds") or 300), 1_800)),
                check=False,
            )
            result = json.loads(process.stdout.strip().splitlines()[-1]) if process.stdout.strip() else {
                "ok": False,
                "error": process.stderr.strip()[:500] or "worker_empty_response",
            }
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]}
        completed = datetime.now(KST)
        coverage_complete = bool(result.get("coverage_complete", True))
        recorded_status = (
            "validated"
            if operation in {"graphrag_validate", "graphiti_probe"} and result.get("ok")
            else "partial"
            if result.get("ok") and not coverage_complete
            else "completed"
            if result.get("ok")
            else "failed"
        )
        evidence_keys = (
            "ok", "error", "coverage_complete", "coverage_scope", "cached",
            "indexed_points", "input_rows", "processed_documents", "written_chunks",
            "chunk_count", "matching_documents", "remaining_documents",
            "total_synced_documents", "input_documents", "total_documents",
            "artifact_count", "backend",
        )
        evidence = {key: result.get(key) for key in evidence_keys if key in result}
        detail = json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:4000]
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO engine_run_history(engine_id, operation, started_at, completed_at, status, input_digest, detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    engine_id,
                    operation,
                    started.isoformat(timespec="seconds"),
                    completed.isoformat(timespec="seconds"),
                    recorded_status,
                    digest,
                    detail,
                ),
            )
        if operation not in {"qdrant_search", "graphrag_init"}:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                """INSERT INTO engine_runs(engine_id, last_started_at, last_completed_at, last_status,
                input_digest, changed_document_count, detail) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(engine_id) DO UPDATE SET last_started_at=excluded.last_started_at,
                  last_completed_at=excluded.last_completed_at, last_status=excluded.last_status,
                  input_digest=excluded.input_digest, changed_document_count=excluded.changed_document_count,
                  detail=excluded.detail""",
                    (engine_id, started.isoformat(timespec="seconds"), completed.isoformat(timespec="seconds"),
                     recorded_status, digest if recorded_status == "completed" else "",
                     int(options.get("changed_documents") or 0), detail),
                )
        return {
            **result,
            "engine_id": engine_id,
            "operation": operation,
            "elapsed_seconds": round((completed - started).total_seconds(), 3),
            "source_immutable": True,
            "live_order_allowed": False,
        }


class KnowledgeCuratorScheduler:
    """Low-cost source watcher that invokes at most one specialist per cycle."""

    def __init__(
        self,
        curator: KnowledgeCurator,
        source_provider: Callable[[], Iterable[Path]],
        market_open_provider: Callable[[], bool],
        heavy_work_provider: Callable[[], bool] | None = None,
    ) -> None:
        self.curator = curator
        self.source_provider = source_provider
        self.market_open_provider = market_open_provider
        self.heavy_work_provider = heavy_work_provider or (lambda: not self.market_open_provider())
        self.interval_seconds = 60
        self.running = False
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.last_cycle_at = ""
        self.last_success_at = ""
        self.last_error = ""
        self.last_result: dict[str, object] = {}
        self.current_phase = "idle"
        self.current_engine = ""
        self.last_elapsed_seconds = 0.0

    def start(self, interval_seconds: int | None = None) -> dict[str, object]:
        with self.lock:
            if interval_seconds is not None:
                self.interval_seconds = max(30, min(int(interval_seconds), 3600))
            self.running = True
            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(
                    target=self._loop,
                    name="knowledge-curator",
                    daemon=True,
                )
                self.thread.start()
        return self.status()

    def stop(self) -> dict[str, object]:
        with self.lock:
            self.running = False
        return self.status()

    def run_cycle(self) -> dict[str, object]:
        started = datetime.now(KST)
        started_monotonic = time.monotonic()
        self.last_cycle_at = started.isoformat(timespec="seconds")
        market_open = bool(self.market_open_provider())
        heavy_work_allowed = bool(self.heavy_work_provider())
        self.current_phase = "indexing_core_sources"
        self.current_engine = ""
        indexed = self.curator.index_paths(self.source_provider())
        changed = int(indexed.get("changed_documents", indexed.get("indexed_documents")) or 0)
        self.current_phase = "planning_specialist_work"
        plan = self.curator.plan_engine_work(
            changed_documents=changed,
            market_open=market_open,
            heavy_work_allowed=heavy_work_allowed,
            now=started,
        )
        selected = plan.get("next_job") if isinstance(plan.get("next_job"), dict) else None
        specialist: dict[str, object] | None = None
        if selected:
            operation = {
                "qdrant": "qdrant_sync",
                "llamaindex": "llamaindex_sync",
                "graphiti": "graphiti_sync",
                "graphrag": "graphrag_index",
            }.get(str(selected.get("engine_id") or ""))
            if operation:
                selected_engine_id = str(selected.get("engine_id") or "")
                self.current_phase = "running_specialist_engine"
                self.current_engine = selected_engine_id
                specialist_limit = (
                    300
                    if selected_engine_id == "graphrag"
                    else 5
                    if selected_engine_id == "graphiti"
                    else 2000
                    if market_open
                    else 10000
                )
                specialist = self.curator.run_specialist(
                    operation,
                    changed_documents=changed,
                    limit=specialist_limit,
                    timeout_seconds=120 if market_open else 900,
                )
        result = {
            "ok": bool(indexed.get("ok")) and (specialist is None or bool(specialist.get("ok"))),
            "cycle_at": self.last_cycle_at,
            "market_open": market_open,
            "heavy_work_allowed": heavy_work_allowed,
            "index": indexed,
            "plan": plan,
            "selected_engine": selected,
            "specialist": specialist,
            "source_immutable": True,
            "live_order_allowed": False,
        }
        self.last_result = result
        self.last_elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
        self.current_phase = "idle"
        self.current_engine = ""
        if result["ok"]:
            self.last_success_at = datetime.now(KST).isoformat(timespec="seconds")
            self.last_error = ""
        else:
            self.last_error = str((specialist or {}).get("error") or indexed.get("errors") or "cycle_failed")[:500]
        return result

    def _loop(self) -> None:
        while True:
            if not self.running:
                time.sleep(1)
                continue
            try:
                self.run_cycle()
            except Exception as exc:  # The employee stays alive and reports the cycle error.
                self.last_error = f"{type(exc).__name__}: {exc}"[:500]
                self.current_phase = "error_waiting_retry"
                self.current_engine = ""
                self.last_result = {
                    "ok": False,
                    "cycle_at": datetime.now(KST).isoformat(timespec="seconds"),
                    "error": self.last_error,
                    "live_order_allowed": False,
                }
            slept = 0.0
            while self.running and slept < self.interval_seconds:
                time.sleep(0.5)
                slept += 0.5

    def status(self) -> dict[str, object]:
        return {
            "running": self.running,
            "thread_alive": bool(self.thread and self.thread.is_alive()),
            "interval_seconds": self.interval_seconds,
            "last_cycle_at": self.last_cycle_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "last_result": self.last_result,
            "current_phase": self.current_phase,
            "current_engine": self.current_engine,
            "last_elapsed_seconds": self.last_elapsed_seconds,
            "source_immutable": True,
            "live_order_allowed": False,
        }

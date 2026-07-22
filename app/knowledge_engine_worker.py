from __future__ import annotations

import hashlib
import asyncio
import json
import math
import re
import shutil
import sqlite3
import sys
import subprocess
import uuid
import traceback
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


VECTOR_SIZE = 96


def _vector(text: str) -> list[float]:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    tokens = re.findall(r"[0-9a-zA-Z가-힣]+", normalized)
    features = tokens + [normalized[index:index + 3] for index in range(max(0, len(normalized) - 2))]
    vector = [0.0] * VECTOR_SIZE
    for feature in features[:20_000]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        vector[value % VECTOR_SIZE] += -1.0 if value & 1 else 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _documents(index_db: Path, limit: int) -> list[sqlite3.Row]:
    with closing(sqlite3.connect(index_db)) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT document_id, title, content, source_path, source_locator, content_hash, "
            "source_content_hash, event_time "
            "FROM documents ORDER BY indexed_at DESC LIMIT ?",
            (max(1, min(limit, 100_000)),),
        ).fetchall()


def _document_count(index_db: Path) -> int:
    with closing(sqlite3.connect(index_db)) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])


def _current_documents(index_db: Path) -> tuple[list[sqlite3.Row], dict[str, str]]:
    rows = _documents(index_db, 100_000)
    hashes = {
        str(row["document_id"]): str(row["content_hash"])
        for row in rows
    }
    return rows, hashes


def _point_id(document_id: str) -> str:
    return str(uuid.UUID(hex=document_id[:32]))


def qdrant_sync(payload: dict[str, object]) -> dict[str, object]:
    from qdrant_client import QdrantClient, models

    index_db = Path(str(payload["index_db"]))
    qdrant_path = Path(str(payload["qdrant_path"]))
    qdrant_path.mkdir(parents=True, exist_ok=True)
    collection = str(payload.get("collection") or "codexstock_knowledge")
    state_db = Path(str(payload.get("qdrant_state_db") or qdrant_path.parent / "qdrant_sync.sqlite3"))
    state_db.parent.mkdir(parents=True, exist_ok=True)
    all_rows, current_hashes = _current_documents(index_db)
    total_documents = len(all_rows)
    requested_limit = max(1, min(int(payload.get("limit") or 20_000), 100_000))
    client = QdrantClient(path=str(qdrant_path))

    with closing(sqlite3.connect(state_db)) as state, state:
        state.execute(
            "CREATE TABLE IF NOT EXISTS synced_documents (document_id TEXT PRIMARY KEY, "
            "content_hash TEXT NOT NULL, synced_at TEXT NOT NULL)"
        )
        synced = {
            str(row[0]): str(row[1])
            for row in state.execute("SELECT document_id, content_hash FROM synced_documents")
        }

    collection_exists = client.collection_exists(collection)
    collection_count = client.count(collection_name=collection, exact=True).count if collection_exists else 0
    # Rebuild when the local collection and its idempotency ledger disagree.
    if collection_exists and int(collection_count) != len(synced):
        client.delete_collection(collection_name=collection)
        collection_exists = False
        synced = {}
        with closing(sqlite3.connect(state_db)) as state, state:
            state.execute("DELETE FROM synced_documents")
    elif not collection_exists and synced:
        synced = {}
        with closing(sqlite3.connect(state_db)) as state, state:
            state.execute("DELETE FROM synced_documents")

    stale_ids = sorted(set(synced) - set(current_hashes))
    if stale_ids and collection_exists:
        client.delete(
            collection_name=collection,
            points_selector=models.PointIdsList(points=[_point_id(value) for value in stale_ids]),
            wait=True,
        )
    if stale_ids:
        with closing(sqlite3.connect(state_db)) as state, state:
            state.executemany("DELETE FROM synced_documents WHERE document_id = ?", [(value,) for value in stale_ids])
        for value in stale_ids:
            synced.pop(value, None)

    full_refresh = bool(payload.get("force"))
    if full_refresh and collection_exists:
        client.delete_collection(collection_name=collection)
        collection_exists = False
        synced = {}
        with closing(sqlite3.connect(state_db)) as state, state:
            state.execute("DELETE FROM synced_documents")
    if not collection_exists:
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
        )
    pending_rows = [
        row for row in all_rows
        if synced.get(str(row["document_id"])) != str(row["content_hash"])
    ]
    rows = pending_rows[:requested_limit]
    batch = []
    for row in rows:
        point_id = _point_id(str(row["document_id"]))
        batch.append(
            models.PointStruct(
                id=point_id,
                vector=_vector(f"{row['title']}\n{row['content']}"),
                payload={
                    "document_id": row["document_id"],
                    "title": row["title"],
                    "source_path": row["source_path"],
                    "source_locator": row["source_locator"],
                    "content_hash": row["content_hash"],
                    "source_content_hash": row["source_content_hash"] or row["content_hash"],
                    "event_time": row["event_time"],
                    "excerpt": str(row["content"])[:800],
                },
            )
        )
        if len(batch) >= 128:
            client.upsert(collection_name=collection, points=batch, wait=True)
            batch = []
    if batch:
        client.upsert(collection_name=collection, points=batch, wait=True)
    if rows:
        synced_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(state_db)) as state, state:
            state.executemany(
                "INSERT OR REPLACE INTO synced_documents(document_id, content_hash, synced_at) VALUES (?, ?, ?)",
                [
                    (str(row["document_id"]), str(row["content_hash"]), synced_at)
                    for row in rows
                ],
            )
    with closing(sqlite3.connect(state_db)) as state:
        final_synced = {
            str(row[0]): str(row[1])
            for row in state.execute("SELECT document_id, content_hash FROM synced_documents")
        }
    matching_documents = sum(
        1 for document_id, content_hash in current_hashes.items()
        if final_synced.get(document_id) == content_hash
    )
    count = client.count(collection_name=collection, exact=True).count
    client.close()
    coverage_complete = matching_documents == total_documents and int(count) == total_documents
    return {
        "ok": True,
        "engine_id": "qdrant",
        "indexed_points": int(count),
        "input_rows": len(rows),
        "total_documents": total_documents,
        "matching_documents": matching_documents,
        "remaining_documents": max(0, total_documents - matching_documents),
        "coverage_complete": coverage_complete,
        "coverage_scope": "full_projection",
    }


def qdrant_search(payload: dict[str, object]) -> dict[str, object]:
    from qdrant_client import QdrantClient

    client = QdrantClient(path=str(Path(str(payload["qdrant_path"]))))
    collection = str(payload.get("collection") or "codexstock_knowledge")
    result = client.query_points(
        collection_name=collection,
        query=_vector(str(payload.get("query") or "")),
        limit=max(1, min(int(payload.get("limit") or 10), 50)),
        with_payload=True,
    ).points
    client.close()
    return {
        "ok": True,
        "engine_id": "qdrant",
        "results": [
            {"score": float(point.score), **dict(point.payload or {})}
            for point in result
        ],
    }


def llamaindex_sync(payload: dict[str, object]) -> dict[str, object]:
    from llama_index.core import Document
    from llama_index.core.node_parser import SentenceSplitter

    index_db = Path(str(payload["index_db"]))
    chunk_db = Path(str(payload["chunk_db"]))
    chunk_db.parent.mkdir(parents=True, exist_ok=True)
    all_rows, current_hashes = _current_documents(index_db)
    total_documents = len(all_rows)
    requested_limit = max(1, min(int(payload.get("limit") or 20_000), 100_000))
    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
    written = 0
    with closing(sqlite3.connect(chunk_db)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS chunks (chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, "
            "content_hash TEXT NOT NULL, text TEXT NOT NULL, metadata_json TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS sync_state (document_id TEXT PRIMARY KEY, "
            "content_hash TEXT NOT NULL, synced_at TEXT NOT NULL)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)")
        synced = {
            str(row[0]): str(row[1])
            for row in connection.execute("SELECT document_id, content_hash FROM sync_state")
        }
        stale_ids = sorted(set(synced) - set(current_hashes))
        if stale_ids:
            connection.executemany("DELETE FROM chunks WHERE document_id = ?", [(value,) for value in stale_ids])
            connection.executemany("DELETE FROM sync_state WHERE document_id = ?", [(value,) for value in stale_ids])
            for value in stale_ids:
                synced.pop(value, None)
        full_refresh = bool(payload.get("force"))
        if full_refresh:
            connection.execute("DELETE FROM chunks")
            connection.execute("DELETE FROM sync_state")
            synced = {}
        pending_rows = [
            row for row in all_rows
            if synced.get(str(row["document_id"])) != str(row["content_hash"])
        ]
        rows = pending_rows[:requested_limit]
        for row in rows:
            connection.execute("DELETE FROM chunks WHERE document_id = ?", (row["document_id"],))
            document = Document(
                text=str(row["content"]),
                metadata={
                    "document_id": row["document_id"],
                    "source_path": row["source_path"],
                    "source_locator": row["source_locator"],
                    "content_hash": row["content_hash"],
                    "source_content_hash": row["source_content_hash"] or row["content_hash"],
                },
            )
            for index, node in enumerate(splitter.get_nodes_from_documents([document])):
                chunk_id = hashlib.sha256(f"{row['document_id']}|{index}|{node.text}".encode("utf-8")).hexdigest()
                connection.execute(
                    "INSERT OR REPLACE INTO chunks(chunk_id, document_id, content_hash, text, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (chunk_id, row["document_id"], row["content_hash"], node.text,
                     json.dumps(node.metadata, ensure_ascii=False, sort_keys=True)),
                )
                written += 1
            connection.execute(
                "INSERT OR REPLACE INTO sync_state(document_id, content_hash, synced_at) VALUES (?, ?, ?)",
                (
                    str(row["document_id"]),
                    str(row["content_hash"]),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
        count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        final_synced = {
            str(row[0]): str(row[1])
            for row in connection.execute("SELECT document_id, content_hash FROM sync_state")
        }
    matching_documents = sum(
        1 for document_id, content_hash in current_hashes.items()
        if final_synced.get(document_id) == content_hash
    )
    return {
        "ok": True,
        "engine_id": "llamaindex",
        "chunk_count": int(count),
        "processed_documents": len(rows),
        "written_chunks": written,
        "total_documents": total_documents,
        "matching_documents": matching_documents,
        "remaining_documents": max(0, total_documents - matching_documents),
        "coverage_complete": matching_documents == total_documents,
        "coverage_scope": "full_projection",
    }


def graphrag_init(payload: dict[str, object]) -> dict[str, object]:
    workspace = Path(str(payload["workspace"]))
    workspace.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "graphrag",
            "init",
            "--root",
            str(workspace),
            "--model",
            str(payload.get("model") or "gpt-4.1"),
            "--embedding",
            str(payload.get("embedding") or "text-embedding-3-large"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    settings = workspace / "settings.yaml"
    return {
        "ok": process.returncode == 0 and settings.is_file(),
        "engine_id": "graphrag",
        "workspace": str(workspace),
        "settings_created": settings.is_file(),
        "stdout": str(process.stdout or "")[-1000:],
        "stderr": str(process.stderr or "")[-1000:],
    }


def _prepare_graphrag_input(payload: dict[str, object]) -> tuple[Path, int, int]:
    workspace = Path(str(payload["workspace"]))
    input_dir = workspace / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    index_db = Path(str(payload["index_db"]))
    rows = _documents(
        index_db,
        int(payload.get("limit") or 300),
    )
    output = input_dir / "codexstock_knowledge.txt"
    blocks = []
    for row in rows:
        blocks.append(
            "\n".join(
                (
                    f"DOCUMENT_ID: {row['document_id']}",
                    f"TITLE: {row['title']}",
                    f"EVENT_TIME: {row['event_time'] or ''}",
                    f"CONTENT_HASH: {row['content_hash']}",
                    f"SOURCE_CONTENT_HASH: {row['source_content_hash'] or row['content_hash']}",
                    str(row["content"])[:12_000],
                )
            )
        )
    output.write_text("\n\n---\n\n".join(blocks), encoding="utf-8")
    return output, len(rows), _document_count(index_db)


def graphrag_validate(payload: dict[str, object]) -> dict[str, object]:
    workspace = Path(str(payload["workspace"]))
    input_file, document_count, total_documents = _prepare_graphrag_input(payload)
    process = subprocess.run(
        [sys.executable, "-m", "graphrag", "index", "--root", str(workspace), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return {
        "ok": process.returncode == 0,
        "engine_id": "graphrag",
        "validation": "dry_run",
        "input_file": str(input_file),
        "input_documents": document_count,
        "total_documents": total_documents,
        "stdout": str(process.stdout or "")[-2000:],
        "stderr": str(process.stderr or "")[-2000:],
    }


def graphrag_index(payload: dict[str, object]) -> dict[str, object]:
    workspace = Path(str(payload["workspace"]))
    input_file, document_count, total_documents = _prepare_graphrag_input(payload)
    input_digest = hashlib.sha256(input_file.read_bytes()).hexdigest()
    run_workspace = workspace / "runs" / input_digest
    run_input = run_workspace / "input"
    run_input.mkdir(parents=True, exist_ok=True)
    settings_source = workspace / "settings.yaml"
    if not settings_source.is_file():
        raise FileNotFoundError("graphrag_settings_missing")
    shutil.copy2(settings_source, run_workspace / "settings.yaml")
    prompts_source = workspace / "prompts"
    if prompts_source.is_dir() and not (run_workspace / "prompts").exists():
        shutil.copytree(prompts_source, run_workspace / "prompts")
    shutil.copy2(input_file, run_input / input_file.name)
    marker = run_workspace / "codexstock_success.json"
    if marker.is_file():
        previous = json.loads(marker.read_text(encoding="utf-8"))
        return {
            **previous,
            "ok": True,
            "cached": True,
            "coverage_complete": document_count >= int(payload.get("minimum_batch_documents") or 300),
            "coverage_scope": "minimum_evidence_batch",
            "total_documents": total_documents,
            "input_digest": input_digest,
            "run_workspace": str(run_workspace),
        }
    method = str(payload.get("method") or "fast")
    if method not in {"fast", "standard"}:
        raise ValueError("unsupported_graphrag_method")
    process = subprocess.run(
        [sys.executable, "-m", "graphrag", "index", "--root", str(run_workspace), "--method", method],
        capture_output=True,
        text=True,
        timeout=max(300, min(int(payload.get("timeout_seconds") or 1800), 7200)),
        check=False,
    )
    output_dir = run_workspace / "output"
    artifacts = [str(path) for path in output_dir.glob("*") if path.is_file()]
    result = {
        "ok": process.returncode == 0 and bool(artifacts),
        "engine_id": "graphrag",
        "method": method,
        "input_file": str(input_file),
        "input_documents": document_count,
        "total_documents": total_documents,
        "input_digest": input_digest,
        "run_workspace": str(run_workspace),
        "artifact_count": len(artifacts),
        "coverage_complete": document_count >= int(payload.get("minimum_batch_documents") or 300),
        "coverage_scope": "minimum_evidence_batch",
        "stdout": str(process.stdout or "")[-3000:],
        "stderr": str(process.stderr or "")[-3000:],
    }
    if result["ok"]:
        marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _graphiti_client(payload: dict[str, object]):
    from graphiti_core import Graphiti
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    from graphiti_core.driver.kuzu_driver import KuzuDriver
    from graphiti_core.driver.driver import GraphProvider
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
    from graphiti_core.graph_queries import get_fulltext_indices
    import kuzu

    base_url = str(payload.get("ollama_openai_base") or "http://127.0.0.1:11434/v1")
    graph_path = Path(str(payload.get("graphiti_path") or "graphiti.kuzu"))
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    driver = KuzuDriver(db=str(graph_path), max_concurrent_queries=1)
    # Graphiti 0.29.2's deprecated Kuzu adapter omits the base driver's
    # database marker, although add_episode reads it before cloning a driver.
    driver._database = "codexstock"
    # Kuzu 0.11.3 accepts the async FTS DDL without persisting an index.
    # Build and verify those four static indexes through its sync connection.
    sync_connection = kuzu.Connection(driver.db)
    for query in get_fulltext_indices(GraphProvider.KUZU):
        try:
            sync_connection.execute(query)
        except RuntimeError as exc:
            if "already exists" not in str(exc).lower():
                raise
    llm_config = LLMConfig(
        api_key="local-ollama",
        model=str(payload.get("completion_model") or "qwen2.5:3b"),
        small_model=str(payload.get("completion_model") or "qwen2.5:3b"),
        base_url=base_url,
        temperature=0,
        max_tokens=4096,
    )
    llm = OpenAIGenericClient(
        config=llm_config,
        max_tokens=4096,
        structured_output_mode="json_object",
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            embedding_dim=1024,
            embedding_model=str(payload.get("embedding_model") or "bge-m3"),
            api_key="local-ollama",
            base_url=base_url,
        )
    )
    return Graphiti(
        graph_driver=driver,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=OpenAIRerankerClient(config=llm_config),
        max_coroutines=1,
    )


def graphiti_probe(payload: dict[str, object]) -> dict[str, object]:
    async def run() -> dict[str, object]:
        graphiti = _graphiti_client(payload)
        try:
            await graphiti.build_indices_and_constraints()
            return {
                "ok": True,
                "engine_id": "graphiti",
                "backend": "kuzu_local_compatibility",
                "schema_ready": True,
            }
        finally:
            await graphiti.close()

    return asyncio.run(run())


def graphiti_sync(payload: dict[str, object]) -> dict[str, object]:
    from graphiti_core.nodes import EpisodeType

    index_db = Path(str(payload["index_db"]))
    candidate_rows, current_hashes = _current_documents(index_db)
    state_db = Path(str(payload["graphiti_state_db"]))
    state_db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(state_db)) as state, state:
        state.execute(
            "CREATE TABLE IF NOT EXISTS synced_documents (document_id TEXT PRIMARY KEY, "
            "content_hash TEXT NOT NULL, synced_at TEXT NOT NULL)"
        )
        synced = {
            str(row[0]): str(row[1])
            for row in state.execute("SELECT document_id, content_hash FROM synced_documents")
        }
        stale_ids = sorted(set(synced) - set(current_hashes))
        if stale_ids:
            state.executemany("DELETE FROM synced_documents WHERE document_id = ?", [(value,) for value in stale_ids])
            for value in stale_ids:
                synced.pop(value, None)
    limit = max(1, min(int(payload.get("limit") or 5), 20))
    rows = [
        row for row in candidate_rows
        if synced.get(str(row["document_id"])) != str(row["content_hash"])
    ][:limit]

    async def run() -> dict[str, object]:
        graphiti = _graphiti_client(payload)
        written = 0
        try:
            await graphiti.build_indices_and_constraints()
            for row in rows:
                event_time = str(row["event_time"] or "")
                try:
                    reference_time = datetime.fromisoformat(event_time)
                except ValueError:
                    reference_time = datetime.now(timezone.utc)
                if reference_time.tzinfo is None:
                    reference_time = reference_time.replace(tzinfo=timezone.utc)
                await graphiti.add_episode(
                    name=str(row["title"])[:240],
                    episode_body=str(row["content"])[:2000],
                    source_description="CodexStock immutable knowledge projection",
                    reference_time=reference_time,
                    source=EpisodeType.text,
                    group_id="codexstock",
                    update_communities=False,
                )
                with closing(sqlite3.connect(state_db)) as state, state:
                    state.execute(
                        "INSERT OR REPLACE INTO synced_documents(document_id, content_hash, synced_at) "
                        "VALUES (?, ?, ?)",
                        (
                            str(row["document_id"]),
                            str(row["content_hash"]),
                            datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        ),
                    )
                written += 1
        finally:
            await graphiti.close()
        with closing(sqlite3.connect(state_db)) as state:
            final_synced = {
                str(row[0]): str(row[1])
                for row in state.execute("SELECT document_id, content_hash FROM synced_documents")
            }
        total_synced = len(final_synced)
        total_documents = len(current_hashes)
        matching_documents = sum(
            1 for document_id, content_hash in current_hashes.items()
            if final_synced.get(document_id) == content_hash
        )
        return {
            "ok": True,
            "engine_id": "graphiti",
            "backend": "kuzu_local_compatibility",
            "processed_documents": len(rows),
            "written_episodes": written,
            "total_synced_documents": total_synced,
            "matching_documents": matching_documents,
            "total_documents": total_documents,
            "remaining_documents": max(0, total_documents - matching_documents),
            "coverage_complete": matching_documents == total_documents,
            "coverage_scope": "full_temporal_projection",
        }

    return asyncio.run(run())


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        operation = str(payload.get("operation") or "")
        handlers = {
            "qdrant_sync": qdrant_sync,
            "qdrant_search": qdrant_search,
            "llamaindex_sync": llamaindex_sync,
            "graphrag_init": graphrag_init,
            "graphrag_validate": graphrag_validate,
            "graphrag_index": graphrag_index,
            "graphiti_probe": graphiti_probe,
            "graphiti_sync": graphiti_sync,
        }
        if operation not in handlers:
            raise ValueError("unsupported_operation")
        result = handlers[operation](payload)
        result.update({"source_immutable": True, "live_order_allowed": False})
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-4000:],
            "live_order_allowed": False,
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

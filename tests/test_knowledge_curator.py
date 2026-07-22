import json
import os
import sqlite3
import tempfile
import unittest
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.knowledge_curator import ENGINE_POLICIES, KnowledgeCurator, KnowledgeCuratorScheduler


class KnowledgeCuratorTests(unittest.TestCase):
    def test_existing_graphrag_environment_file_is_hardened(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            env_path = runtime_root / "knowledge_curator" / "graphrag_workspace" / ".env"
            env_path.parent.mkdir(parents=True)
            env_path.write_text("LOCAL_ONLY=true\n", encoding="utf-8")
            with (
                patch("app.knowledge_curator.os.chmod") as chmod,
                patch("app.knowledge_curator.os.name", "nt"),
                patch.dict(
                    "app.knowledge_curator.os.environ",
                    {"USERNAME": "testuser", "USERDOMAIN": "TEST"},
                ),
                patch("app.knowledge_curator.subprocess.run") as run,
            ):
                KnowledgeCurator(runtime_root)

        chmod.assert_called_once_with(env_path, 0o600)
        run.assert_called_once()
        self.assertIn("/inheritance:r", run.call_args.args[0])
        self.assertIn("TEST\\testuser:(F)", run.call_args.args[0])
    def test_indexes_without_modifying_source_and_returns_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "meetings.jsonl"
            source.write_text(
                json.dumps({"id": "M1", "created_at": "2026-07-21T10:00:00+09:00", "summary": "삼성전자 후보 보류"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            before = source.read_bytes()
            curator = KnowledgeCurator(root / "runtime")
            indexed = curator.index_paths([source])
            result = curator.search("삼성전자")

            self.assertTrue(indexed["ok"])
            self.assertEqual(before, source.read_bytes())
            self.assertEqual(1, result["result_count"])
            self.assertEqual(str(source.resolve()), result["results"][0]["source"]["path"])
            self.assertEqual("line:1", result["results"][0]["source"]["locator"])
            self.assertEqual(64, len(result["results"][0]["source"]["content_hash"]))

    def test_unchanged_source_is_not_reindexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "journal.md"
            source.write_text("# 복기\n놓친 종목 원인", encoding="utf-8")
            curator = KnowledgeCurator(root / "runtime")
            self.assertEqual(1, curator.index_paths([source])["indexed_documents"])
            second = curator.index_paths([source])
            self.assertEqual(0, second["indexed_documents"])
            self.assertEqual(1, second["unchanged_sources"])

    def test_timestamp_only_rewrite_is_skipped_by_content_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "meetings.jsonl"
            source.write_text(json.dumps({"summary": "same evidence"}) + "\n", encoding="utf-8")
            curator = KnowledgeCurator(root / "runtime")
            self.assertEqual(1, curator.index_paths([source])["indexed_documents"])

            stat = source.stat()
            os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            second = curator.index_paths([source])

            self.assertEqual(0, second["indexed_documents"])
            self.assertEqual(1, second["unchanged_sources"])

    def test_jsonl_sensitive_fields_are_redacted_but_source_hash_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "meetings.jsonl"
            source.write_text(
                json.dumps({
                    "summary": "safe research summary",
                    "api_token": "never-project-this-token",
                }) + "\n",
                encoding="utf-8",
            )
            curator = KnowledgeCurator(root / "runtime")
            curator.index_paths([source])
            result = curator.search("safe research")

            self.assertEqual(1, result["result_count"])
            provenance = result["results"][0]["source"]
            self.assertTrue(provenance["redacted_projection"])
            self.assertNotEqual(provenance["content_hash"], provenance["projection_hash"])
            self.assertEqual(0, curator.search("never-project-this-token")["result_count"])

    def test_jsonl_append_indexes_only_new_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "meetings.jsonl"
            source.write_text(json.dumps({"summary": "first meeting"}) + "\n", encoding="utf-8")
            curator = KnowledgeCurator(root / "runtime")
            first = curator.index_paths([source])
            with source.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"summary": "second unique meeting"}) + "\n")
            second = curator.index_paths([source])

            self.assertEqual(1, first["indexed_documents"])
            self.assertEqual(1, second["indexed_documents"])
            self.assertEqual(1, second["incremental_sources"])
            self.assertEqual(0, second["full_reindexed_sources"])
            self.assertEqual(1, curator.search("second unique")["result_count"])

    def test_jsonl_incomplete_tail_waits_until_line_is_finished(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "learning.jsonl"
            source.write_bytes(
                (json.dumps({"summary": "complete row"}) + "\n" + '{"summary":"unfinished').encode("utf-8")
            )
            curator = KnowledgeCurator(root / "runtime")
            first = curator.index_paths([source])
            self.assertEqual(1, first["indexed_documents"])
            self.assertEqual(0, curator.search("unique_tail_token")["result_count"])

            with source.open("ab") as stream:
                stream.write(b' unique_tail_token"}\n')
            second = curator.index_paths([source])
            self.assertEqual(1, second["indexed_documents"])
            self.assertEqual(1, second["incremental_sources"])
            self.assertEqual(1, curator.search("unique_tail_token")["result_count"])

    def test_reindex_removes_rows_deleted_from_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "journal.jsonl"
            source.write_text(
                json.dumps({"summary": "keep"}) + "\n" + json.dumps({"summary": "remove me"}) + "\n",
                encoding="utf-8",
            )
            curator = KnowledgeCurator(root / "runtime")
            curator.index_paths([source])
            self.assertEqual(1, curator.search("remove me")["result_count"])

            source.write_text(json.dumps({"summary": "keep"}) + "\n", encoding="utf-8")
            curator.index_paths([source])
            self.assertEqual(0, curator.search("remove me")["result_count"])

    def test_full_rewrite_counts_only_rows_with_changed_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "journal.jsonl"
            source.write_text(
                json.dumps({"summary": "alpha"}) + "\n" + json.dumps({"summary": "beta"}) + "\n",
                encoding="utf-8",
            )
            curator = KnowledgeCurator(root / "runtime")
            self.assertEqual(2, curator.index_paths([source])["changed_documents"])

            source.write_text(
                json.dumps({"summary": "alpha"}) + "\n" + json.dumps({"summary": "zeta"}) + "\n",
                encoding="utf-8",
            )
            refreshed = curator.index_paths([source])

            self.assertEqual(2, refreshed["indexed_documents"])
            self.assertEqual(1, refreshed["changed_documents"])

    def test_sqlite_knowledge_projection_is_read_only_and_redacts_private_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "research_journal.sqlite3"
            with closing(sqlite3.connect(source)) as connection, connection:
                connection.execute(
                    "CREATE TABLE research_notes (id INTEGER PRIMARY KEY, title TEXT, note TEXT, "
                    "created_at TEXT, api_token TEXT)"
                )
                connection.execute(
                    "INSERT INTO research_notes VALUES (1, 'Strategy alpha', 'liquidity lesson', "
                    "'2026-07-21T10:00:00+09:00', 'secret-token-value')"
                )
                connection.execute("CREATE TABLE account_tokens (id INTEGER PRIMARY KEY, token TEXT)")
                connection.execute("INSERT INTO account_tokens VALUES (1, 'never-index-this')")
            before = source.read_bytes()

            curator = KnowledgeCurator(root / "runtime")
            indexed = curator.index_paths([source])
            result = curator.search("liquidity lesson")

            self.assertTrue(indexed["ok"])
            self.assertEqual(before, source.read_bytes())
            self.assertEqual(1, result["result_count"])
            self.assertEqual("table:research_notes/pk:1", result["results"][0]["source"]["locator"])
            self.assertEqual(0, curator.search("secret-token-value")["result_count"])
            self.assertEqual(0, curator.search("never-index-this")["result_count"])

    def test_sqlite_wal_update_invalidates_source_projection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "research_events.sqlite3"
            writer = sqlite3.connect(source)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute(
                    "CREATE TABLE research_events (id INTEGER PRIMARY KEY, summary TEXT, created_at TEXT)"
                )
                writer.execute(
                    "INSERT INTO research_events VALUES (1, 'first observation', '2026-07-21T10:00:00+09:00')"
                )
                writer.commit()
                curator = KnowledgeCurator(root / "runtime")
                self.assertEqual(1, curator.index_paths([source])["indexed_documents"])

                writer.execute(
                    "INSERT INTO research_events VALUES (2, 'second observation with more evidence', "
                    "'2026-07-21T10:01:00+09:00')"
                )
                writer.commit()
                refreshed = curator.index_paths([source])
                self.assertEqual(2, refreshed["indexed_documents"])
                self.assertEqual(1, curator.search("more evidence")["result_count"])
            finally:
                writer.close()

    def test_market_hours_defer_heavy_engines_and_only_one_is_selected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            curator = KnowledgeCurator(Path(temp_dir))
            with patch("app.knowledge_curator.importlib.util.find_spec", return_value=object()):
                plan = curator.plan_engine_work(
                    changed_documents=500,
                    market_open=True,
                    now=datetime(2026, 7, 21, 1, 0, tzinfo=timezone.utc),
                )
            decisions = {row["engine_id"]: row for row in plan["jobs"]}
            self.assertEqual("queue", decisions["qdrant"]["decision"])
            self.assertEqual("skip", decisions["graphiti"]["decision"])
            self.assertEqual("skip", decisions["graphrag"]["decision"])
            self.assertEqual(1, plan["heavy_engine_concurrency"])
            self.assertEqual("qdrant", plan["next_job"]["engine_id"])

    def test_engine_queue_prefers_medium_before_enabled_heavy_engines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            curator = KnowledgeCurator(Path(temp_dir))
            status = {
                "engines": [
                    {
                        "engine_id": engine_id,
                        "installed": True,
                        "operational_ready": True,
                        "automatic_enabled": True,
                        "input_digest": "current" if engine_id == "qdrant" else "",
                        "last_status": "never_run",
                        "last_completed_at": "",
                        "prerequisite_blockers": [],
                    }
                    for engine_id in ("llamaindex", "qdrant", "graphiti", "graphrag")
                ]
            }
            with (
                patch.object(curator, "engine_status", return_value=status),
                patch.object(curator, "index_fingerprint", return_value={
                    "digest": "current", "document_count": 500, "source_count": 3,
                }),
            ):
                plan = curator.plan_engine_work(
                    changed_documents=0,
                    market_open=False,
                    heavy_work_allowed=True,
                )
            self.assertEqual("llamaindex", plan["next_job"]["engine_id"])

    def test_status_distinguishes_downloaded_source_from_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir) / "data"
            source_root = Path(temp_dir) / "engines" / "graphiti"
            source_root.mkdir(parents=True)
            (source_root / "README.md").write_text("graphiti", encoding="utf-8")
            curator = KnowledgeCurator(data_root)
            with (
                patch("app.knowledge_curator.importlib.util.find_spec", return_value=None),
                patch.object(Path, "is_file", return_value=False),
            ):
                status = curator.engine_status()
            graphiti = next(row for row in status["engines"] if row["engine_id"] == "graphiti")
            self.assertTrue(graphiti["source_downloaded"])
            self.assertFalse(graphiti["runtime_installed"])
            self.assertEqual("source_only", graphiti["readiness"])

    def test_dashboard_status_never_runs_active_dependency_probes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            curator = KnowledgeCurator(Path(temp_dir) / "runtime")
            old = datetime.now(timezone.utc) - timedelta(hours=1)
            curator._runtime_probe_cache = {
                policy.module_name: (old, True, "isolated_import_ok")
                for policy in ENGINE_POLICIES
            }
            curator._runtime_probe_cache["kuzu"] = (old, True, "isolated_import_ok")
            curator._ollama_probe_cache = (old, {"bge-m3", "qwen2.5:3b"}, "available")

            with (
                patch(
                    "app.knowledge_curator.importlib.util.find_spec",
                    side_effect=AssertionError("active import probe"),
                ),
                patch.object(curator, "_probe_runtime", side_effect=AssertionError("active runtime probe")),
                patch.object(curator, "_probe_ollama", side_effect=AssertionError("active ollama probe")),
            ):
                status = curator.engine_status(refresh_runtime_probes=False)

            self.assertEqual("cached_snapshot", status["dependency_probe_mode"])
            self.assertTrue(all(row["runtime_probe_stale"] for row in status["engines"]))
            graphiti = next(row for row in status["engines"] if row["engine_id"] == "graphiti")
            self.assertEqual("kuzu_local_compatibility", graphiti["backend"])

    def test_sqlite_read_connections_do_not_reissue_journal_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            curator = KnowledgeCurator(Path(temp_dir) / "runtime")
            with closing(curator._connect(timeout_seconds=0.2)) as connection:
                self.assertEqual(200, int(connection.execute("PRAGMA busy_timeout").fetchone()[0]))
                self.assertEqual(
                    "wal",
                    str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
                )

    def test_scheduler_indexes_changes_and_invokes_only_selected_specialist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "journal.jsonl"
            source.write_text(json.dumps({"summary": "new evidence"}) + "\n", encoding="utf-8")
            curator = KnowledgeCurator(root / "runtime")
            scheduler = KnowledgeCuratorScheduler(curator, lambda: [source], lambda: True)
            with (
                patch.object(curator, "plan_engine_work", return_value={
                    "ok": True,
                    "next_job": {"engine_id": "qdrant", "decision": "queue"},
                    "jobs": [],
                }),
                patch.object(curator, "run_specialist", return_value={"ok": True}) as specialist,
            ):
                result = scheduler.run_cycle()

            self.assertTrue(result["ok"])
            self.assertEqual(1, result["index"]["indexed_documents"])
            specialist.assert_called_once()
            self.assertEqual("qdrant_sync", specialist.call_args.args[0])
            self.assertFalse(result["live_order_allowed"])

    def test_scheduler_invokes_selected_graphiti_only_through_specialist_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            curator = KnowledgeCurator(root / "runtime")
            scheduler = KnowledgeCuratorScheduler(curator, lambda: [], lambda: False)
            with (
                patch.object(curator, "plan_engine_work", return_value={
                    "ok": True,
                    "next_job": {"engine_id": "graphiti", "decision": "queue"},
                    "jobs": [],
                }),
                patch.object(curator, "run_specialist") as specialist,
            ):
                result = scheduler.run_cycle()

            self.assertTrue(result["ok"])
            specialist.assert_called_once()
            self.assertEqual("graphiti_sync", specialist.call_args.args[0])
            self.assertEqual(5, specialist.call_args.kwargs["limit"])

    def test_mcp_exposes_read_only_knowledge_tools(self):
        from app import codexstock_mcp_server as mcp_server

        names = {str(tool.get("name") or "") for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_knowledge_curator_status", names)
        self.assertIn("codexstock_knowledge_search", names)
        self.assertIn("codexstock_knowledge_engine_plan", names)
        self.assertTrue(
            {
                "codexstock_knowledge_curator_status",
                "codexstock_knowledge_search",
                "codexstock_knowledge_engine_plan",
            }.issubset(mcp_server.ASK_AGENT_ROUTABLE_TOOLS)
        )
        detailed_status = {
            "ok": True,
            "employee": "knowledge_curator",
            "mode": "lightweight_always_on",
            "indexed_documents": 12,
            "indexed_sources": 3,
            "discoverable_source_count": 3,
            "archive_source_count": 7,
            "dependency_probe_mode": "cached_snapshot",
            "scheduler": {
                "running": True,
                "thread_alive": True,
                "current_phase": "idle",
                "last_success_at": "2026-07-21T23:00:00+09:00",
                "last_error": "",
            },
            "engines": [
                {
                    "engine_id": "qdrant",
                    "readiness": "operational_ready",
                    "runtime_installed": True,
                    "runtime_probe": "isolated_import_ok",
                    "runtime_probe_stale": False,
                    "operational_ready": True,
                    "automatic_enabled": True,
                    "last_status": "completed",
                    "last_completed_at": "2026-07-21T22:59:00+09:00",
                    "coverage_state": "complete",
                    "index_stale": False,
                    "prerequisite_blockers": [],
                    "source_path": "must-not-leak-into-summary",
                    "last_evidence": {"very_large": "x" * 10000},
                }
            ],
            "status_cache": {"cached": True, "age_seconds": 0.2},
            "source_immutable": True,
        }
        with patch("app.codexstock_mcp_server._http_json", return_value=detailed_status):
            status_result = mcp_server._call_tool(
                "codexstock_knowledge_curator_status",
                {"max_chars": 4000},
            )
        status_payload = json.loads(status_result["content"][0]["text"])
        self.assertTrue(status_payload["summary_only"])
        self.assertEqual(12, status_payload["indexed_documents"])
        self.assertEqual(1, status_payload["engine_summary"]["operational_ready_count"])
        self.assertNotIn("source_path", status_payload["engines"][0])
        self.assertLess(len(status_result["content"][0]["text"]), 4000)
        with patch("app.codexstock_mcp_server._http_json", return_value={"ok": True}) as http_json:
            result = mcp_server._call_tool(
                "codexstock_knowledge_search",
                {"query": "Samsung", "limit": 3},
            )
        http_json.assert_called_once_with(
            "GET",
            "/api/knowledge-curator/search",
            {"q": "Samsung", "limit": 3},
            timeout_seconds=15.0,
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["ok"])

        with patch("app.codexstock_mcp_server._http_json", return_value={"ok": True}) as http_json:
            mcp_server._call_tool(
                "codexstock_knowledge_engine_plan",
                {"changed_documents": 30, "market_open": False, "heavy_work_allowed": True},
            )
        http_json.assert_called_once_with(
            "GET",
            "/api/knowledge-curator/engine-plan",
            {"changed_documents": 30, "market_open": 0, "heavy_work_allowed": 1},
            timeout_seconds=15.0,
        )

    def test_ask_agent_routes_knowledge_status_before_generic_external_sources(self):
        from app import codexstock_mcp_server as mcp_server

        with patch.object(mcp_server, "_call_tool", return_value={"content": []}) as call_tool:
            result = mcp_server._agent_local_fallback(
                "지식관리 직원 상태와 외부 자료 최근 색인 현황만 알려줘",
                max_chars=4000,
            )

        self.assertIsNotNone(result)
        call_tool.assert_called_once_with(
            "codexstock_knowledge_curator_status",
            {"max_chars": 4000},
        )
        self.assertEqual("codexstock_knowledge_curator_status", result["routed_tool"])
        self.assertTrue(result["schema_cache_fallback"])

    def test_ask_agent_structured_route_reaches_knowledge_search_during_schema_lag(self):
        from app import codexstock_mcp_server as mcp_server

        with patch.object(mcp_server, "_call_tool", return_value={"content": []}) as call_tool:
            result = mcp_server._agent_local_fallback(
                json.dumps(
                    {
                        "mcp_tool": "codexstock_knowledge_search",
                        "arguments": {"query": "삼성전자 회의", "limit": 3},
                    },
                    ensure_ascii=False,
                ),
                max_chars=4000,
            )

        self.assertIsNotNone(result)
        call_tool.assert_called_once_with(
            "codexstock_knowledge_search",
            {"query": "삼성전자 회의", "limit": 3, "max_chars": 4000},
        )
        self.assertEqual("codexstock_knowledge_search", result["routed_tool"])

    def test_partial_specialist_result_does_not_mark_index_digest_complete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "journal.jsonl"
            source.write_text(json.dumps({"summary": "one"}) + "\n", encoding="utf-8")
            curator = KnowledgeCurator(root / "runtime")
            curator.index_paths([source])
            curator.runtime_python = Path(sys.executable)
            completed = type("Completed", (), {
                "stdout": json.dumps({"ok": True, "coverage_complete": False}),
                "stderr": "",
                "returncode": 0,
            })()
            with patch("app.knowledge_curator.subprocess.run", return_value=completed):
                result = curator.run_specialist("qdrant_sync", changed_documents=1)

            self.assertTrue(result["ok"])
            qdrant = next(row for row in curator.engine_status()["engines"] if row["engine_id"] == "qdrant")
            self.assertEqual("partial", qdrant["last_status"])
            self.assertEqual("", qdrant["input_digest"])

    def test_specialist_sync_holds_projection_lock_for_a_stable_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            curator = KnowledgeCurator(Path(temp_dir))
            curator.runtime_python = Path(sys.executable)
            curator.worker_path = Path(sys.executable)

            def inspect_lock(operation, engine_id, **options):
                return {
                    "ok": curator._index_lock.locked(),
                    "operation": operation,
                    "engine_id": engine_id,
                }

            with patch.object(curator, "_run_specialist_locked", side_effect=inspect_lock):
                result = curator.run_specialist("qdrant_sync")

            self.assertTrue(result["ok"])
            self.assertFalse(curator._index_lock.locked())
            self.assertFalse(curator._specialist_lock.locked())

    def test_completed_engine_is_reported_stale_after_projection_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "journal.jsonl"
            source.write_text(json.dumps({"summary": "one"}) + "\n", encoding="utf-8")
            curator = KnowledgeCurator(root / "runtime")
            curator.index_paths([source])
            current_digest = str(curator.index_fingerprint()["digest"])
            with closing(curator._connect()) as connection, connection:
                connection.execute(
                    "INSERT INTO engine_runs "
                    "(engine_id, last_status, input_digest, changed_document_count, detail) "
                    "VALUES ('qdrant', 'completed', 'old-digest', 1, '{}')"
                )

            with patch("app.knowledge_curator.importlib.util.find_spec", return_value=object()):
                stale = next(
                    row for row in curator.engine_status()["engines"] if row["engine_id"] == "qdrant"
                )
            self.assertTrue(stale["index_stale"])
            self.assertEqual("stale", stale["coverage_state"])

            with closing(curator._connect()) as connection, connection:
                connection.execute(
                    "UPDATE engine_runs SET input_digest = ? WHERE engine_id = 'qdrant'",
                    (current_digest,),
                )
            with patch("app.knowledge_curator.importlib.util.find_spec", return_value=object()):
                current = next(
                    row for row in curator.engine_status()["engines"] if row["engine_id"] == "qdrant"
                )
            self.assertFalse(current["index_stale"])
            self.assertEqual("complete", current["coverage_state"])


if __name__ == "__main__":
    unittest.main()

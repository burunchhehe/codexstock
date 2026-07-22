import json
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import app.stock_suite_app as stock_app

from app.stock_suite_app import (
    AiResearchDaemon,
    AutopilotScheduler,
    _closed_trade_journal_from_actions,
    _external_signal_freshness_feature_probe,
    _historical_replay_base_audit,
    _live_reconciliation_blocker_summary,
    _historical_replay_regeneration_campaign,
      _historical_replay_regeneration_ledger_progress,
      _historical_replay_completion_estimate,
      _historical_replay_worker_public_status,
    _historical_replay_status_file_signature,
    _historical_close_rows,
    _sqlite_storage_feature_probe,
    _tournament_reconciliation_health_probe,
    build_common_quote_snapshot,
    build_live_execution_authority_contract,
    build_operating_focus,
    build_system_feature_health,
    build_position_unit_audit,
    build_backtest_return_reconciliation,
    historical_replay_regeneration_contract,
    regenerate_historical_paper_replay,
    reassess_historical_replay_regeneration,
    historical_replay_regeneration_status,
    historical_replay_evidence_milestone_status,
    run_due_historical_replay_evidence_milestones,
    cached_historical_replay_regeneration_status,
    run_historical_replay_regeneration_manual_batch,
    historical_replay_data_gap_queue,
    run_historical_replay_data_gap_backfill,
    HISTORICAL_REPLAY_DATA_BACKFILL_LOCK,
    HISTORICAL_CLOSE_ROWS_CACHE,
    build_historical_replay_backup_contract_index,
    jsonl_compaction_backup_retention,
    next_historical_replay_regeneration_candidate,
    classify_historical_replay_regeneration_failure,
    ai_staff_learning_audit,
    _always_on_research_enabled,
    _research_startup_initial_delay_seconds,
    _autopilot_should_restore,
    build_delegated_live_authorization,
    build_simple_trade_telegram_text,
    build_scheduled_report_text,
    build_live_trade_memory_summary,
    _asset_gear,
    _append_jsonl,
    _compact_jsonl,
    _fallback_live_positions_from_order_log,
    _delegated_live_position_reviews,
    submit_live_pilot_order,
    query_runtime_event_index,
    reconcile_runtime_event_index,
)


TEST_REPLAY_ARTIFACT_ANCHORS = {
    "artifact_hash_contract": stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
    "replay_artifact_sha256": "a" * 64,
    "journal_artifact_sha256": "b" * 64,
}


def _verified_replay_bundle_evidence(
    symbol: str,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    evidence = {
        "schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
        "used": True,
        "passed": True,
        "content_hash": "sha256:" + "b" * 64,
        "bundle_content_hash": "sha256:" + "b" * 64,
        "slice_content_hash": "sha256:" + "a" * 64,
        "bundle_period": {"start_date": start_date, "end_date": end_date},
        "requested_period": {"start_date": start_date, "end_date": end_date},
        "symbols": [symbol],
        "symbol_count": 1,
        "symbol_row_counts": {symbol: 2},
        "symbol_row_bounds": {
            symbol: {
                "first_date": start_date,
                "last_date": end_date,
                "row_count": 2,
            }
        },
        "symbol_calendar_adjacency_roots": {
            symbol: stock_app.calendar_adjacency_root(symbol, [start_date, end_date])
        },
        "symbol_calendar_pair_counts": {symbol: 1},
        "fx_row_count": 0,
        "excluded_before_row_count": 0,
        "excluded_future_row_count": 0,
        "future_rows_excluded_before_strategy": True,
        "no_rows_outside_requested_period": True,
        "source_fetch_reused": True,
        "live_order_allowed": False,
    }
    evidence["slice_manifest_hash"] = stock_app._replay_data_bundle_slice_manifest_hash(
        evidence
    )
    return evidence


class TradeReconciliationTests(unittest.TestCase):
    def test_targeted_reverse_jsonl_lookup_stops_after_latest_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large-replays.jsonl"
            rows = [{"id": "TARGET", "version": "old", "padding": "x" * 2000}]
            rows.extend(
                {"id": f"OLD-{index}", "padding": "x" * 2000}
                for index in range(180)
            )
            rows.extend(
                [
                    {"id": "SECOND", "version": "latest", "padding": "x" * 2000},
                    {"id": "TARGET", "version": "latest", "padding": "x" * 2000},
                ]
            )
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            selected, evidence = stock_app._read_jsonl_latest_by_ids(
                path,
                ["TARGET", "SECOND"],
            )

        self.assertEqual(["TARGET", "SECOND"], [row["id"] for row in selected])
        self.assertTrue(all(row["version"] == "latest" for row in selected))
        self.assertEqual(2, evidence["found_id_count"])
        self.assertEqual(0, evidence["missing_id_count"])
        self.assertTrue(evidence["stopped_after_all_ids_found"])
        self.assertLess(evidence["bytes_scanned"], evidence["file_size_bytes"])

    def test_shallow_replay_evidence_audit_skips_large_replay_archive(self):
        campaign = {
            "campaign_id": "campaign-1",
            "source_replay_ids": ["HREPLAY-1"],
        }
        with (
            patch("app.stock_suite_app._historical_replay_base_audit", return_value={}),
            patch("app.stock_suite_app._historical_replay_regeneration_campaign", return_value=campaign),
            patch("app.stock_suite_app._read_jsonl", return_value=[]) as read_jsonl,
        ):
            result = stock_app.historical_replay_evidence_audit(deep=False)

        requested_paths = [Path(call.args[0]) for call in read_jsonl.call_args_list]
        self.assertIn(stock_app.HISTORICAL_REPLAY_REGENERATION_FILE, requested_paths)
        self.assertNotIn(stock_app.HISTORICAL_REPLAY_FILE, requested_paths)
        self.assertFalse(result["deep"])

    def test_completion_certificate_uses_frozen_campaign_evidence_signature(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tournament_path = root / "tournaments.jsonl"
            ledger_path = root / "regenerations.jsonl"
            campaign_path = root / "campaign.json"
            replay_path = root / "replays.jsonl"
            journal_root = root / "journals"
            journal_path = journal_root / "HREPLAY-1.json"
            certificate_path = root / "certificate.json"
            journal_root.mkdir()
            for path in (tournament_path, ledger_path, campaign_path, replay_path, journal_path):
                path.write_text("{}\n", encoding="utf-8")
            audit = {
                "schema": "codexstock_historical_replay_completion_audit_v3",
                "ok": True,
                "completion_verified": True,
                "certificate_allowed": True,
                "expected_total": 757,
                "paper_only": True,
                "automatic_promotion": False,
                "live_order_allowed": False,
                "evidence_audit": {
                    "campaign_id": "campaign-1",
                    "ledger_evidence_hash": "a" * 64,
                    "journal_evidence_hash": "b" * 64,
                    "replay_evidence_hash": "c" * 64,
                    "evidence_bundle_hash": "d" * 64,
                },
            }
            milestone_status = {
                "campaign_id": "campaign-1",
                "target_count": 757,
                "campaign_scope_hash": "e" * 64,
                "required_evidence_schema_version": "historical-replay-evidence.v6",
                "required_execution_timing_model_version": "prior-bar-signal-next-close.v3",
                "required_replay_data_bundle_evidence_schema": "codexstock_replay_data_bundle_slice_evidence_v3",
                "resolved_count": 757,
                "passed_milestones": [10, 25, 100, 300, 500, 757],
                "deep_verification": {
                    "verified_through_count": 757,
                    "last_verified_at": "2026-07-16T23:41:29+09:00",
                    "ledger_evidence_hash": "a" * 64,
                    "journal_evidence_hash": "b" * 64,
                    "replay_evidence_hash": "c" * 64,
                    "evidence_bundle_hash": "d" * 64,
                    "audited_scope_hash": "e" * 64,
                    "evidence_bundle_hash_contract": "sha256-canonical-json-replay-evidence-bundle-v2",
                    "artifact_hash_contract": "sha256-canonical-replay-v1+exact-journal-bytes-v1",
                    "artifact_anchor_required_count": 757,
                    "artifact_anchor_verified_count": 757,
                    "artifact_anchor_mismatch_count": 0,
                    "artifact_anchor_deep_verified": True,
                },
            }
            with (
                patch("app.stock_suite_app.AI_TOURNAMENT_FILE", tournament_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE", ledger_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE", campaign_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_FILE", replay_path),
                patch("app.stock_suite_app.TRADE_JOURNAL_DIR", journal_root),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_COMPLETION_CERTIFICATE_FILE", certificate_path),
                patch(
                    "app.stock_suite_app.historical_replay_evidence_milestone_status",
                    return_value=milestone_status,
                ),
            ):
                persisted = stock_app.persist_historical_replay_completion_certificate(audit)
                loaded = stock_app.load_historical_replay_completion_certificate()
                replay_path.write_text("{}\n{}\n", encoding="utf-8")
                still_current_after_unrelated_replay = stock_app.load_historical_replay_completion_certificate()
                journal_path.write_text('{"changed":true}\n', encoding="utf-8")
                still_current_after_unrelated_journal = stock_app.load_historical_replay_completion_certificate()
                milestone_status["deep_verification"]["replay_evidence_hash"] = "f" * 64
                stale_evidence = stock_app.load_historical_replay_completion_certificate()

        self.assertTrue(persisted["ok"])
        self.assertTrue(loaded["hash_valid"])
        self.assertTrue(loaded["source_signature_current"])
        self.assertEqual("certificate_verified", loaded["status"])
        self.assertEqual("codexstock_historical_replay_completion_certificate_v3", loaded["schema"])
        self.assertEqual(3, loaded["source_signature_version"])
        self.assertEqual("campaign-1", loaded["campaign_id"])
        self.assertEqual("a" * 64, loaded["ledger_evidence_hash"])
        self.assertEqual("c" * 64, loaded["replay_evidence_hash"])
        self.assertRegex(loaded["certificate_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(still_current_after_unrelated_replay["ok"])
        self.assertTrue(still_current_after_unrelated_journal["ok"])
        self.assertFalse(stale_evidence["ok"])
        self.assertEqual("certificate_stale", stale_evidence["status"])
        self.assertFalse(stale_evidence["source_signature_current"])
        self.assertFalse(stale_evidence["live_order_allowed"])

    def test_completion_certificate_rejects_missing_replay_evidence_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            certificate_path = Path(temp_dir) / "certificate.json"
            with patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_COMPLETION_CERTIFICATE_FILE",
                certificate_path,
            ):
                result = stock_app.persist_historical_replay_completion_certificate(
                    {
                        "ok": True,
                        "certificate_allowed": True,
                        "completion_verified": True,
                        "evidence_audit": {
                            "ledger_evidence_hash": "a" * 64,
                            "journal_evidence_hash": "b" * 64,
                            "evidence_bundle_hash": "c" * 64,
                        },
                    }
                )

        self.assertFalse(result["ok"])
        self.assertEqual("certificate_evidence_hashes_invalid", result["status"])
        self.assertEqual(["replay_evidence_hash"], result["invalid_evidence_hashes"])
        self.assertFalse(result["certificate_persisted"])
        self.assertFalse(certificate_path.exists())

    def test_completion_certificate_refresh_reuses_one_in_process_audit_snapshot(self):
        audit = {
            "ok": True,
            "certificate_allowed": True,
            "completion_verified": True,
        }
        persisted = {
            "ok": True,
            "status": "certificate_verified",
            "certificate_id": "HRCERT-1",
        }
        with (
            patch(
                "app.stock_suite_app.historical_replay_completion_audit",
                return_value=audit,
            ) as completion_audit,
            patch(
                "app.stock_suite_app._sync_historical_replay_completion_milestone",
                return_value={"ok": True, "status": "final_milestone_already_verified"},
            ) as milestone_sync,
            patch(
                "app.stock_suite_app.persist_historical_replay_completion_certificate",
                return_value=persisted,
            ) as persist,
        ):
            result = stock_app.refresh_historical_replay_completion_certificate()

        completion_audit.assert_called_once_with()
        milestone_sync.assert_called_once_with(audit)
        persist.assert_called_once_with(audit)
        self.assertTrue(result["ok"])
        self.assertTrue(result["audit_snapshot_reused"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_order_allowed"])

    def test_completion_refresh_can_persist_final_milestone_from_same_full_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            campaign_path = root / "campaign.json"
            milestone_path = root / "milestones.jsonl"
            campaign_ids = ["HREPLAY-A", "HREPLAY-B"]
            campaign_scope_hash = stock_app.evidence_scope_hash(campaign_ids)
            campaign_path.write_text(
                json.dumps(
                    {
                        "campaign_id": "campaign-final",
                        "target_count": 2,
                        "source_replay_ids": campaign_ids,
                    }
                ),
                encoding="utf-8",
            )
            evidence = {
                "ok": True,
                "deep": True,
                "resolved_count": 2,
                "verified_count": 2,
                "quarantined_count": 0,
                "failed_count": 0,
                "issue_count": 0,
                "audited_journal_count": 2,
                "audited_closed_trade_count": 4,
                "audited_source_ids": campaign_ids,
                "audited_scope_hash": campaign_scope_hash,
                "artifact_hash_contract": stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
                "artifact_anchor_required_count": 2,
                "artifact_anchor_verified_count": 2,
                "artifact_anchor_mismatch_count": 0,
                "artifact_anchor_deep_verified": True,
                "ledger_evidence_hash": "a" * 64,
                "journal_evidence_hash": "b" * 64,
                "replay_evidence_hash": "c" * 64,
                "evidence_bundle_hash_contract": stock_app.EVIDENCE_BUNDLE_HASH_CONTRACT,
            }
            evidence["evidence_bundle_hash"] = stock_app.replay_evidence_bundle_hash(
                audited_scope_hash=campaign_scope_hash,
                evidence_schema_version=stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                execution_timing_model_version=stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                replay_data_bundle_evidence_schema=stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                artifact_hash_contract=stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
                ledger_evidence_hash=evidence["ledger_evidence_hash"],
                journal_evidence_hash=evidence["journal_evidence_hash"],
                replay_evidence_hash=evidence["replay_evidence_hash"],
            )
            status = {
                "campaign_id": "campaign-final",
                "target_count": 2,
                "campaign_scope_hash": campaign_scope_hash,
                "resolved_count": 2,
                "passed_milestones": [],
            }
            refreshed = {**status, "passed_milestones": [2]}
            audit = {
                "ok": True,
                "completion_verified": True,
                "certificate_allowed": True,
                "evidence_audit": evidence,
            }
            with (
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE",
                    campaign_path,
                ),
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_FILE",
                    milestone_path,
                ),
                patch(
                    "app.stock_suite_app.historical_replay_evidence_milestone_status",
                    side_effect=[status, refreshed],
                ),
            ):
                result = stock_app._sync_historical_replay_completion_milestone(audit)

            record = json.loads(milestone_path.read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertTrue(result["final_milestone_persisted"])
            self.assertEqual(2, result["milestone"])
            self.assertEqual("passed", record["status"])
            self.assertEqual(campaign_scope_hash, record["audited_scope_hash"])
            self.assertFalse(record["live_order_allowed"])

    def test_incomplete_audit_cannot_create_completion_certificate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            certificate_path = Path(temp_dir) / "certificate.json"
            with patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_COMPLETION_CERTIFICATE_FILE",
                certificate_path,
            ):
                result = stock_app.persist_historical_replay_completion_certificate(
                    {
                        "ok": False,
                        "certificate_allowed": False,
                        "completion_verified": False,
                    }
                )

        self.assertFalse(result["certificate_persisted"])
        self.assertFalse(certificate_path.exists())
        self.assertFalse(result["live_order_allowed"])

    def test_queue_completion_fails_closed_until_certificate_is_verified(self):
        selection = {"ok": True, "status": "queue_complete", "unresolved_count": 0}
        with (
            patch(
                "app.stock_suite_app.load_historical_replay_completion_certificate",
                return_value={"ok": False, "status": "certificate_missing"},
            ),
            patch(
                "app.stock_suite_app.persist_historical_replay_completion_certificate",
                return_value={
                    "ok": False,
                    "status": "in_progress",
                    "certificate_path": "certificate.json",
                },
            ),
        ):
            blocked = stock_app._finalize_historical_replay_queue_selection(
                selection,
                schedule_mode="test",
            )
        with patch(
            "app.stock_suite_app.load_historical_replay_completion_certificate",
            return_value={
                "ok": True,
                "status": "certificate_verified",
                "certificate_id": "HRCERT-1",
                "certificate_sha256": "d" * 64,
                "path": "certificate.json",
            },
        ):
            verified = stock_app._finalize_historical_replay_queue_selection(
                selection,
                schedule_mode="test",
            )

        self.assertFalse(blocked["ok"])
        self.assertEqual("completion_certificate_review_required", blocked["status"])
        self.assertFalse(blocked["score_allowed"])
        self.assertFalse(blocked["promotion_allowed"])
        self.assertFalse(blocked["live_order_allowed"])
        self.assertTrue(verified["ok"])
        self.assertEqual("queue_complete", verified["status"])
        self.assertTrue(verified["completion_verified"])
        self.assertTrue(verified["score_allowed"])
        self.assertFalse(verified["promotion_allowed"])
        self.assertFalse(verified["live_order_allowed"])

    def test_milestone_status_invalidates_legacy_passes_after_evidence_upgrade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            campaign_path = root / "campaign.json"
            milestone_path = root / "milestones.jsonl"
            campaign_path.write_text(
                json.dumps(
                    {
                        "schema": "codexstock_replay_regeneration_campaign_v1",
                        "campaign_id": "campaign-1",
                        "target_count": 2,
                        "source_replay_ids": ["HREPLAY-1", "HREPLAY-2"],
                    }
                ),
                encoding="utf-8",
            )
            ledger = [
                {
                    "source_replay_id": "HREPLAY-1",
                    "status": "verified_replacement_candidate",
                    "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                    "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                }
            ]
            legacy_milestone = {
                "schema": "codexstock_replay_evidence_milestone_v1",
                "campaign_id": "campaign-1",
                "milestone": 2,
                "status": "passed",
                "resolved_count": 2,
                "verified_count": 2,
                "audited_journal_count": 2,
                "quarantined_count": 0,
                "failed_count": 0,
                "issue_count": 0,
                "ledger_evidence_hash": "a" * 64,
                "journal_evidence_hash": "b" * 64,
                "evidence_bundle_hash": "c" * 64,
                "paper_only": True,
                "live_order_allowed": False,
            }

            def fake_read(path, limit=0):
                return [legacy_milestone] if Path(path) == milestone_path else ledger

            with (
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE", campaign_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_FILE", milestone_path),
                patch("app.stock_suite_app._read_jsonl", side_effect=fake_read),
            ):
                result = historical_replay_evidence_milestone_status()

        self.assertEqual([], result["passed_milestones"])
        self.assertEqual([2], result["invalidated_milestones"])
        self.assertEqual(2, result["next_milestone"])
        self.assertEqual([], result["due_milestones"])
        self.assertFalse(result["latest_records"][0]["current_contract_valid"])
        self.assertEqual("invalidated", result["latest_records"][0]["effective_status"])
        self.assertEqual(0, result["deep_verification"]["verified_through_count"])
        self.assertEqual("0/2 (0.00%)", result["deep_verification"]["progress_label"])

    def test_completed_replay_status_keeps_worker_asleep_at_startup(self):
        completed = stock_app.historical_replay_worker_startup_gate(
            {
                "status": "complete",
                "source_signature_current": True,
                "progress": {
                    "remaining_candidate_count": 0,
                    "confirmed": True,
                },
            }
        )
        uncertain = stock_app.historical_replay_worker_startup_gate(
            {
                "status": "complete",
                "source_signature_current": False,
                "progress": {
                    "remaining_candidate_count": 0,
                    "confirmed": False,
                },
            }
        )

        self.assertTrue(completed["completion_confirmed"])
        self.assertFalse(completed["worker_start_required"])
        self.assertEqual("completed_campaign_auto_sleep", completed["reason"])
        self.assertFalse(uncertain["completion_confirmed"])
        self.assertTrue(uncertain["worker_start_required"])
        self.assertFalse(completed["live_order_allowed"])

        gap_completed = stock_app.historical_replay_data_gap_worker_startup_gate(
            completed
        )
        gap_uncertain = stock_app.historical_replay_data_gap_worker_startup_gate(
            uncertain
        )
        self.assertFalse(gap_completed["worker_start_required"])
        self.assertTrue(gap_completed["completion_confirmed"])
        self.assertTrue(gap_uncertain["worker_start_required"])
        self.assertFalse(gap_completed["live_order_allowed"])

    def test_milestone_status_reuses_memory_and_disk_cache_for_unchanged_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            campaign_path = root / "campaign.json"
            ledger_path = root / "regenerations.jsonl"
            milestone_path = root / "milestones.jsonl"
            cache_path = root / "milestone-status-cache.json"
            for path in (campaign_path, ledger_path, milestone_path):
                path.write_text("{}\n", encoding="utf-8")
            payload = {
                "ok": True,
                "schema": "codexstock_replay_evidence_milestone_status_v8",
                "passed_milestones": [2],
                "live_order_allowed": False,
            }
            with (
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE",
                    campaign_path,
                ),
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE",
                    ledger_path,
                ),
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_FILE",
                    milestone_path,
                ),
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_STATUS_CACHE_FILE",
                    cache_path,
                ),
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_STATUS_CACHE",
                    None,
                ),
                patch(
                    "app.stock_suite_app._build_historical_replay_evidence_milestone_status",
                    return_value=payload,
                ) as builder,
            ):
                first = historical_replay_evidence_milestone_status()
                second = historical_replay_evidence_milestone_status()
                stock_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_STATUS_CACHE = None
                third = historical_replay_evidence_milestone_status()
                cache_persisted = cache_path.exists()

        self.assertEqual(1, builder.call_count)
        self.assertFalse(first["cache_hit"])
        self.assertEqual("memory", second["cache_source"])
        self.assertEqual("disk", third["cache_source"])
        self.assertTrue(cache_persisted)

    def test_milestone_status_exposes_deep_lookahead_evidence_coverage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            campaign_path = root / "campaign.json"
            milestone_path = root / "milestones.jsonl"
            source_ids = ["HREPLAY-1", "HREPLAY-2"]
            campaign_path.write_text(
                json.dumps(
                    {
                        "schema": "codexstock_replay_regeneration_campaign_v1",
                        "campaign_id": "campaign-1",
                        "target_count": 2,
                        "source_replay_ids": source_ids,
                    }
                ),
                encoding="utf-8",
            )
            ledger = [
                {
                    "source_replay_id": replay_id,
                    "status": "verified_replacement_candidate",
                    "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                    "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                    "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                }
                for replay_id in source_ids
            ]
            passed_record = {
                "schema": "codexstock_replay_evidence_milestone_v8",
                "campaign_id": "campaign-1",
                "target_count": 2,
                "campaign_scope_hash": stock_app.evidence_scope_hash(source_ids),
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                "milestone": 2,
                "status": "passed",
                "generated_at": "2026-07-15T02:20:00+09:00",
                "resolved_count": 2,
                "verified_count": 2,
                "audited_journal_count": 2,
                "quarantined_count": 0,
                "failed_count": 0,
                "issue_count": 0,
                "ledger_evidence_hash": "a" * 64,
                "journal_evidence_hash": "b" * 64,
                "replay_evidence_hash": "c" * 64,
                "audited_source_ids": source_ids,
                "audited_scope_hash": stock_app.evidence_scope_hash(source_ids),
                "evidence_bundle_hash_contract": stock_app.EVIDENCE_BUNDLE_HASH_CONTRACT,
                "artifact_hash_contract": stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
                "artifact_anchor_required_count": 2,
                "artifact_anchor_verified_count": 2,
                "artifact_anchor_mismatch_count": 0,
                "artifact_anchor_deep_verified": True,
                "paper_only": True,
                "live_order_allowed": False,
            }
            passed_record["evidence_bundle_hash"] = stock_app.replay_evidence_bundle_hash(
                audited_scope_hash=passed_record["audited_scope_hash"],
                evidence_schema_version=passed_record["evidence_schema_version"],
                execution_timing_model_version=passed_record["execution_timing_model_version"],
                artifact_hash_contract=passed_record["artifact_hash_contract"],
                ledger_evidence_hash=passed_record["ledger_evidence_hash"],
                journal_evidence_hash=passed_record["journal_evidence_hash"],
                replay_evidence_hash=passed_record["replay_evidence_hash"],
                replay_data_bundle_evidence_schema=passed_record[
                    "replay_data_bundle_evidence_schema"
                ],
            )

            def fake_read(path, limit=0):
                return [passed_record] if Path(path) == milestone_path else ledger

            with (
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE", campaign_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_FILE", milestone_path),
                patch("app.stock_suite_app._read_jsonl", side_effect=fake_read),
            ):
                result = historical_replay_evidence_milestone_status()

        deep = result["deep_verification"]
        self.assertEqual("passed_to_milestone", deep["status"])
        self.assertEqual(2, deep["verified_through_count"])
        self.assertEqual("2/2 (100.00%)", deep["progress_label"])
        self.assertEqual("2026-07-15T02:20:00+09:00", deep["last_verified_at"])
        self.assertEqual("a" * 64, deep["ledger_evidence_hash"])
        self.assertEqual("c" * 64, deep["replay_evidence_hash"])
        self.assertFalse(deep["live_order_allowed"])

    def test_current_review_required_milestone_activates_fail_closed_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            campaign_path = root / "campaign.json"
            milestone_path = root / "milestones.jsonl"
            source_ids = ["HREPLAY-1", "HREPLAY-2"]
            campaign_path.write_text(
                json.dumps(
                    {
                        "schema": "codexstock_replay_regeneration_campaign_v1",
                        "campaign_id": "campaign-1",
                        "target_count": 2,
                        "source_replay_ids": source_ids,
                    }
                ),
                encoding="utf-8",
            )
            ledger = [
                {
                    "source_replay_id": replay_id,
                    "status": "verified_replacement_candidate",
                    "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                    "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                    "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                }
                for replay_id in source_ids
            ]
            review_record = {
                "schema": "codexstock_replay_evidence_milestone_v8",
                "campaign_id": "campaign-1",
                "target_count": 2,
                "campaign_scope_hash": stock_app.evidence_scope_hash(source_ids),
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                "milestone": 2,
                "status": "review_required",
                "resolved_count": 2,
                "verified_count": 1,
                "audited_journal_count": 2,
                "quarantined_count": 0,
                "failed_count": 0,
                "issue_count": 1,
                "artifact_hash_contract": stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
                "artifact_anchor_required_count": 2,
                "artifact_anchor_verified_count": 1,
                "artifact_anchor_mismatch_count": 1,
                "artifact_anchor_deep_verified": False,
                "paper_only": True,
                "live_order_allowed": False,
            }

            def fake_read(path, limit=0):
                return [review_record] if Path(path) == milestone_path else ledger

            with (
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE", campaign_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_FILE", milestone_path),
                patch("app.stock_suite_app._read_jsonl", side_effect=fake_read),
            ):
                result = historical_replay_evidence_milestone_status()

        self.assertFalse(result["ok"])
        self.assertEqual([2], result["active_review_required_milestones"])
        self.assertEqual("review_required", result["latest_records"][0]["effective_status"])

    def test_due_milestone_audits_only_current_verified_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_path = Path(temp_dir) / "campaign.json"
            campaign_path.write_text(
                json.dumps(
                    {
                        "schema": "codexstock_replay_regeneration_campaign_v1",
                        "campaign_id": "campaign-1",
                        "target_count": 3,
                        "source_replay_ids": ["HREPLAY-1", "HREPLAY-2", "HREPLAY-3"],
                    }
                ),
                encoding="utf-8",
            )
            initial_status = {
                "campaign_id": "campaign-1",
                "target_count": 3,
                "campaign_scope_hash": "d" * 64,
                "due_milestones": [2],
            }
            final_status = {**initial_status, "due_milestones": [], "passed_milestones": [2]}
            ledger = [
                {
                    "source_replay_id": replay_id,
                    "status": "verified_replacement_candidate",
                    "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                    "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                    "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                }
                for replay_id in ("HREPLAY-1", "HREPLAY-2")
            ]
            evidence = {
                "ok": True,
                "resolved_count": 2,
                "verified_count": 2,
                "quarantined_count": 0,
                "failed_count": 0,
                "audited_journal_count": 2,
                "audited_closed_trade_count": 5,
                "issue_count": 0,
                "issue_code_counts": {},
                "missing_trade_field_counts": {},
                "comparison_status_counts": {"review_required": 2},
                "comparison_review_required_count": 2,
                "source_equivalence_claim_allowed_count": 0,
                "ledger_evidence_hash": "a" * 64,
                "journal_evidence_hash": "b" * 64,
                "replay_evidence_hash": "c" * 64,
                "evidence_bundle_hash": "d" * 64,
                "audited_source_ids": ["HREPLAY-1", "HREPLAY-2"],
                "audited_scope_hash": stock_app.evidence_scope_hash(["HREPLAY-1", "HREPLAY-2"]),
                "evidence_bundle_hash_contract": stock_app.EVIDENCE_BUNDLE_HASH_CONTRACT,
                "artifact_hash_contract": stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
                "artifact_anchor_required_count": 2,
                "artifact_anchor_verified_count": 2,
                "artifact_anchor_mismatch_count": 0,
                "artifact_anchor_deep_verified": True,
            }
            with (
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE", campaign_path),
                patch(
                    "app.stock_suite_app.historical_replay_evidence_milestone_status",
                    side_effect=[initial_status, final_status],
                ),
                patch("app.stock_suite_app._read_jsonl", return_value=ledger),
                patch(
                    "app.stock_suite_app.historical_replay_evidence_audit",
                    return_value=evidence,
                ) as audit,
                patch("app.stock_suite_app._append_jsonl") as append,
            ):
                result = run_due_historical_replay_evidence_milestones()

        audit.assert_called_once_with(
            deep=True,
            scope_ids=["HREPLAY-1", "HREPLAY-2"],
        )
        record = append.call_args.args[1]
        self.assertEqual("codexstock_replay_evidence_milestone_v8", record["schema"])
        self.assertEqual("c" * 64, record["replay_evidence_hash"])
        self.assertEqual(stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION, record["evidence_schema_version"])
        self.assertEqual(
            stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
            record["execution_timing_model_version"],
        )
        self.assertEqual(3, record["target_count"])
        self.assertEqual("passed", record["status"])
        self.assertEqual([2], result["passed_milestones"])

    def test_replay_progress_latest_activity_stays_inside_frozen_campaign(self):
        rows = [
            {
                "source_replay_id": "HREPLAY-IN-SCOPE",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                "generated_at": "2026-07-14T21:39:51+09:00",
            },
            {
                "source_replay_id": "HREPLAY-OUTSIDE",
                "status": "regeneration_failed",
                "generated_at": "2026-07-14T21:40:00+09:00",
            },
        ]
        with patch("app.stock_suite_app._read_jsonl", return_value=rows):
            result = _historical_replay_regeneration_ledger_progress(
                1,
                {"HREPLAY-IN-SCOPE"},
            )

        self.assertEqual("1/1 (100.00%)", result["label"])
        self.assertEqual("HREPLAY-IN-SCOPE", result["latest_activity"]["source_replay_id"])
        self.assertEqual(
            "2026-07-14T21:39:51+09:00",
            result["latest_activity"]["generated_at"],
        )

    def test_replay_progress_rejects_matching_schema_with_old_timing_model(self):
        rows = [
            {
                "source_replay_id": "HREPLAY-1",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": "prior-bar-signal-next-close.v1",
                "generated_at": "2026-07-14T22:00:00+09:00",
            }
        ]
        with patch("app.stock_suite_app._read_jsonl", return_value=rows):
            result = _historical_replay_regeneration_ledger_progress(1, {"HREPLAY-1"})

        self.assertEqual("0/1 (0.00%)", result["label"])
        self.assertEqual(1, result["legacy_resolved_count"])
        self.assertEqual(
            stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
            result["required_execution_timing_model_version"],
        )

    def test_replay_progress_rejects_current_top_level_with_old_data_bundle(self):
        rows = [
            {
                "source_replay_id": "HREPLAY-1",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": "codexstock_replay_data_bundle_slice_evidence_v2",
                "generated_at": "2026-07-14T22:00:00+09:00",
            }
        ]
        with patch("app.stock_suite_app._read_jsonl", return_value=rows):
            result = _historical_replay_regeneration_ledger_progress(1, {"HREPLAY-1"})

        self.assertEqual("0/1 (0.00%)", result["label"])
        self.assertEqual(1, result["legacy_resolved_count"])
        self.assertEqual(
            stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
            result["required_replay_data_bundle_evidence_schema"],
        )

    def test_replay_worker_public_status_uses_actual_thread_liveness(self):
        result = _historical_replay_worker_public_status(
            {
                "running": True,
                "thread_alive": False,
                "current_replay_id": "",
                "last_result": {},
            },
            {
                "latest_activity": {
                    "status": "verified_replacement_candidate",
                    "generated_at": "2026-07-14T21:24:32+09:00",
                }
            },
        )

        self.assertFalse(result["running"])
        self.assertTrue(result["configured_running"])
        self.assertFalse(result["thread_alive"])
        self.assertEqual("BROKEN", result["health_state"])
        self.assertEqual("스레드 중단", result["health_label"])
        self.assertEqual("2026-07-14T21:24:32+09:00", result["last_success_at"])
        self.assertFalse(result["live_order_allowed"])

    def test_runtime_index_reconciles_compacted_jsonl_and_reads_only_fresh_full_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "historical_paper_replays.jsonl"
            database = root / "runtime_event_index.sqlite3"
            previous_connection = stock_app.RUNTIME_EVENT_INDEX_CONNECTION
            stock_app.RUNTIME_EVENT_INDEX_CONNECTION = None
            try:
                with patch.object(stock_app, "USER_DATA_ROOT", root), patch.object(
                    stock_app, "RUNTIME_EVENT_INDEX_DB", database
                ):
                    for index in range(10):
                        _append_jsonl(
                            source,
                            {
                                "id": f"HREPLAY-{index}",
                                "generated_at": f"2026-07-{index + 1:02d}T10:00:00+09:00",
                                "total_return_pct": index,
                            },
                        )
                    partial = query_runtime_event_index(source, limit=3)
                    self.assertFalse(partial["ok"])
                    self.assertEqual(partial["status"], "index_partial")

                    with patch.object(
                        stock_app,
                        "_read_jsonl",
                        side_effect=AssertionError("full-file materialization is forbidden"),
                    ):
                        reconciled = reconcile_runtime_event_index(
                            source_names=[source.name],
                            vacuum=False,
                        )
                    self.assertTrue(reconciled["ok"])
                    self.assertEqual(reconciled["total_indexed_after"], 10)
                    self.assertEqual(reconciled["memory_mode"], "bounded_streaming_one_row")
                    self.assertEqual(reconciled["sources"][0]["read_mode"], "streaming_jsonl")
                    ready = query_runtime_event_index(source, limit=3)
                    self.assertTrue(ready["ok"])
                    self.assertEqual([row["id"] for row in ready["rows"]], ["HREPLAY-9", "HREPLAY-8", "HREPLAY-7"])

                    _compact_jsonl(source, max_rows=3)
                    compacted = query_runtime_event_index(source, limit=10)
                    self.assertTrue(compacted["ok"])
                    self.assertEqual(compacted["indexed_row_count"], 3)
                    self.assertEqual([row["id"] for row in compacted["rows"]], ["HREPLAY-9", "HREPLAY-8", "HREPLAY-7"])
            finally:
                if stock_app.RUNTIME_EVENT_INDEX_CONNECTION is not None:
                    stock_app.RUNTIME_EVENT_INDEX_CONNECTION.close()
                stock_app.RUNTIME_EVENT_INDEX_CONNECTION = previous_connection

    def test_runtime_index_streaming_rebuild_rolls_back_partial_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "events.jsonl"
            database = root / "runtime_event_index.sqlite3"
            previous_connection = stock_app.RUNTIME_EVENT_INDEX_CONNECTION
            stock_app.RUNTIME_EVENT_INDEX_CONNECTION = None
            try:
                with patch.object(stock_app, "USER_DATA_ROOT", root), patch.object(
                    stock_app, "RUNTIME_EVENT_INDEX_DB", database
                ):
                    source.write_text(
                        "".join(json.dumps({"id": index}) + "\n" for index in range(2)),
                        encoding="utf-8",
                    )
                    baseline = reconcile_runtime_event_index(source_names=[source.name])
                    self.assertTrue(baseline["ok"])

                    source.write_text(
                        "".join(json.dumps({"id": index}) + "\n" for index in range(3)),
                        encoding="utf-8",
                    )
                    real_insert = stock_app._runtime_event_index_insert_unlocked
                    insert_calls = 0

                    def fail_second_insert(*args, **kwargs):
                        nonlocal insert_calls
                        insert_calls += 1
                        if insert_calls == 2:
                            raise sqlite3.OperationalError("injected rebuild failure")
                        return real_insert(*args, **kwargs)

                    with patch.object(
                        stock_app,
                        "_runtime_event_index_insert_unlocked",
                        side_effect=fail_second_insert,
                    ):
                        failed = reconcile_runtime_event_index(source_names=[source.name])

                    self.assertFalse(failed["ok"])
                    self.assertEqual("partial_failure", failed["status"])
                    connection = stock_app._runtime_event_index_connection()
                    preserved_count = int(
                        connection.execute(
                            "SELECT COUNT(*) FROM jsonl_events WHERE source_name=?",
                            (source.name,),
                        ).fetchone()[0]
                    )
                    self.assertEqual(2, preserved_count)
            finally:
                if stock_app.RUNTIME_EVENT_INDEX_CONNECTION is not None:
                    stock_app.RUNTIME_EVENT_INDEX_CONNECTION.close()
                stock_app.RUNTIME_EVENT_INDEX_CONNECTION = previous_connection

    def test_runtime_index_reconcile_prunes_temporary_and_orphan_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runtime"
            root.mkdir()
            source = root / "events.jsonl"
            source.write_text('{"id":"real"}\n', encoding="utf-8")
            database = root / "runtime_event_index.sqlite3"
            outside = Path(tmp) / "temporary"
            outside.mkdir()
            contaminated = outside / source.name
            orphan = outside / "orphan.jsonl"
            previous_connection = stock_app.RUNTIME_EVENT_INDEX_CONNECTION
            stock_app.RUNTIME_EVENT_INDEX_CONNECTION = None
            try:
                with patch.object(stock_app, "USER_DATA_ROOT", root), patch.object(
                    stock_app, "RUNTIME_EVENT_INDEX_DB", database
                ):
                    connection = stock_app._runtime_event_index_connection()
                    for path in (contaminated, orphan):
                        stock_app._runtime_event_index_insert_unlocked(
                            connection,
                            path,
                            {"id": f"temp-{path.stem}"},
                        )
                        stock_app._runtime_event_index_update_meta_unlocked(
                            connection,
                            path,
                            source_row_count=1,
                            indexed_row_count=1,
                            coverage_mode="full",
                        )
                    connection.commit()

                    contaminated_status = stock_app.build_runtime_storage_status()
                    self.assertFalse(contaminated_status["ok"])
                    self.assertEqual(2, contaminated_status["untrusted_index_source_count"])
                    self.assertTrue(contaminated_status["reconciliation_required"])

                    result = reconcile_runtime_event_index(source_names=[source.name])

                    self.assertTrue(result["ok"])
                    cleanup = result["untrusted_source_cleanup"]
                    self.assertEqual(2, cleanup["removed_source_count"])
                    self.assertEqual(2, cleanup["removed_event_row_count"])
                    self.assertEqual(1, result["automatic_rebuild_source_count"])
                    remaining_names = {
                        row[0]
                        for row in connection.execute(
                            "SELECT DISTINCT source_name FROM jsonl_events"
                        ).fetchall()
                    }
                    self.assertEqual({source.name}, remaining_names)
                    stored_path = connection.execute(
                        "SELECT source_path FROM jsonl_source_meta WHERE source_name=?",
                        (source.name,),
                    ).fetchone()[0]
                    self.assertEqual(str(source), stored_path)
                    ready_status = stock_app.build_runtime_storage_status()
                    self.assertTrue(ready_status["ok"])
                    self.assertEqual(0, ready_status["untrusted_index_source_count"])
                    self.assertEqual(100.0, ready_status["coverage_pct"])
            finally:
                if stock_app.RUNTIME_EVENT_INDEX_CONNECTION is not None:
                    stock_app.RUNTIME_EVENT_INDEX_CONNECTION.close()
                stock_app.RUNTIME_EVENT_INDEX_CONNECTION = previous_connection

    def test_live_memory_requires_account_ledger_for_official_net_pnl(self):
        submitted = [
            {
                "created_at": "2026-07-14T10:00:00+09:00",
                "symbol": "001440",
                "name": "test",
                "side": "BUY",
                "quantity": 3,
                "price": 29550,
                "status": "LIVE_SUBMITTED",
                "reason": "entry evidence",
                "kis_submit": {"order_no": "B-1"},
            },
            {
                "created_at": "2026-07-14T10:20:00+09:00",
                "symbol": "001440",
                "name": "test",
                "side": "SELL",
                "quantity": 3,
                "price": 29050,
                "status": "LIVE_SUBMITTED",
                "reason": "exit evidence",
                "kis_submit": {"order_no": "S-1"},
            },
        ]
        realized = {
            "ok": True,
            "total_pnl": -1500,
            "total_buy_amount": 88650,
            "total_sell_amount": 87150,
            "realized": [
                {
                    "symbol": "001440",
                    "name": "test",
                    "quantity": 3,
                    "buy_price": 29550,
                    "sell_price": 29050,
                    "buy_amount": 88650,
                    "sell_amount": 87150,
                    "pnl": -1500,
                    "pnl_pct": -1.692,
                    "buy_order_no": "B-1",
                    "sell_order_no": "S-1",
                }
            ],
            "open_lots": [],
            "unmatched_sells": [],
        }
        audit = {
            "account_ledger_reconciliation": {
                "matched": [
                    {"order_no": "B-1", "side": "BUY", "official_trade_eligible": True, "account_ledger_reconciliation": {"status": "matched"}},
                    {
                        "order_no": "S-1",
                        "side": "SELL",
                        "official_trade_eligible": True,
                        "account_ledger_reconciliation": {
                            "status": "matched",
                            "realized_pnl": {
                                "eligible": True,
                                "gross_pnl_before_costs": -1500,
                                "net_realized_pnl": -2111,
                                "net_realized_pnl_pct": -2.3813,
                                "transaction_cost_and_tax": 611,
                                "source": "broker_fill_plus_account_cash_delta",
                            },
                        },
                    },
                ]
            }
        }
        with patch("app.stock_suite_app._today_live_submits", return_value=submitted), patch(
            "app.stock_suite_app._read_jsonl", return_value=[]
        ), patch("app.stock_suite_app.build_today_broker_executions_summary", return_value={"executions": [{}]}), patch(
            "app.stock_suite_app.summarize_broker_execution_realized", return_value=realized
        ), patch("app.stock_suite_app.build_live_reconciliation_audit", return_value=audit), patch(
            "app.stock_suite_app.INTEGRATIONS.kis_account", return_value={"ok": True, "positions": [], "summary": {}}
        ):
            memory = build_live_trade_memory_summary(limit=10, include_account=True)
        trade = memory["realized_preview"]["realized"][0]
        self.assertTrue(trade["official_performance_eligible"])
        self.assertTrue(trade["learning_eligible"])
        self.assertEqual(trade["estimated_net_pnl"], -2111)
        self.assertEqual(trade["net_pnl_source"], "account_cash_reconciled")
        self.assertEqual(memory["net_pnl_reconciliation"]["status"], "matched_order_account_ledger")

    def test_live_memory_recovers_reason_from_nearest_submit_when_order_no_missing(self):
        submitted = [
            {
                "created_at": "2026-07-14T10:00:00+09:00",
                "symbol": "001440",
                "name": "test",
                "side": "BUY",
                "quantity": 1,
                "price": 10000,
                "status": "LIVE_SUBMITTED",
                "reason": "fresh entry reason",
                "kis_submit": {"order_no": ""},
            },
            {
                "created_at": "2026-07-14T10:30:00+09:00",
                "symbol": "001440",
                "name": "test",
                "side": "SELL",
                "quantity": 1,
                "price": 10100,
                "status": "LIVE_SUBMITTED",
                "reason": "fresh exit reason",
                "kis_submit": {"order_no": ""},
            },
        ]
        realized = {
            "ok": True,
            "realized": [
                {
                    "symbol": "001440",
                    "name": "test",
                    "quantity": 1,
                    "buy_price": 10000,
                    "sell_price": 10100,
                    "pnl": 100,
                    "pnl_pct": 1.0,
                    "buy_at": "2026-07-14T10:01:00+09:00",
                    "sell_at": "2026-07-14T10:31:00+09:00",
                    "buy_order_no": "BROKER-BUY",
                    "sell_order_no": "BROKER-SELL",
                }
            ],
            "open_lots": [],
            "unmatched_sells": [],
        }
        with patch("app.stock_suite_app._today_live_submits", return_value=submitted), patch(
            "app.stock_suite_app._read_jsonl", return_value=[]
        ), patch("app.stock_suite_app.build_today_broker_executions_summary", return_value={"executions": [{}]}), patch(
            "app.stock_suite_app.summarize_broker_execution_realized", return_value=realized
        ), patch("app.stock_suite_app.build_live_reconciliation_audit", return_value={"account_ledger_reconciliation": {"matched": []}}), patch(
            "app.stock_suite_app.INTEGRATIONS.kis_account", return_value={"ok": True, "positions": [], "summary": {}}
        ):
            memory = build_live_trade_memory_summary(limit=10, include_account=True)
        trade = memory["realized_preview"]["realized"][0]
        self.assertEqual("fresh entry reason", trade["entry_reason"])
        self.assertEqual("fresh exit reason", trade["exit_reason"])
        self.assertEqual("nearest_submit", trade["reason_recovery"]["entry_source"])
        self.assertEqual("nearest_submit", trade["reason_recovery"]["exit_source"])

    def test_live_execution_authority_is_exclusive_to_operator(self):
        contract = build_live_execution_authority_contract()
        self.assertEqual(contract["exclusive_executor"], "operator")
        self.assertNotIn("operator", contract["support_roles"])
        self.assertIn("risk_manager", contract["support_roles"])

    def test_research_ai_cannot_reach_live_order_submission(self):
        with patch("app.stock_suite_app.OPS.audit"):
            result = submit_live_pilot_order(
                token="unused",
                confirm_phrase="unused",
                execution_actor="research_strategy",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "LIVE_SUBMIT_AUTHORITY_BLOCKED")
        self.assertEqual(result["real_execution"], "BLOCKED")

    def test_operating_focus_prioritizes_execution_during_kr_regular_market(self):
        clock = {"sessions": [{"id": "KR", "is_regular_open": True, "market_time": "2026-07-14T10:00:00+09:00"}]}
        focus = build_operating_focus(clock)
        self.assertEqual(focus["mode"], "MARKET_EXECUTION_FOCUS")
        self.assertEqual(focus["trading_focus_pct"], 100)
        self.assertEqual(focus["research_focus_pct"], 0)
        self.assertFalse(focus["heavy_research_allowed"])

    def test_operating_focus_restores_heavy_research_after_market(self):
        clock = {"sessions": [{"id": "KR", "is_regular_open": False, "market_time": "2026-07-14T18:30:00+09:00"}]}
        focus = build_operating_focus(clock)
        self.assertEqual(focus["mode"], "DAILY_REVIEW_FOCUS")
        self.assertEqual(focus["research_focus_pct"], 80)
        self.assertTrue(focus["heavy_research_allowed"])
        self.assertFalse(focus["large_batch_jobs_allowed"])

    def test_market_priority_runtime_contract_detects_stopped_scheduler(self):
        result = stock_app.build_market_priority_runtime_contract(
            focus={
                "market_priority_active": True,
                "market_phase": "regular",
                "autopilot_interval_seconds": 60,
            },
            scheduler={
                "running": False,
                "thread_alive": False,
                "effective_interval_seconds": 60,
            },
            latest_tick_age_seconds=30,
            resource_gate={"active_heavy_job_count": 0},
            runtime_age_seconds=600,
        )

        self.assertFalse(result["ok"])
        self.assertEqual("market_priority_degraded", result["status"])
        self.assertIn("market_scheduler_not_running", result["blockers"])
        self.assertIn("market_scheduler_thread_dead", result["blockers"])
        self.assertFalse(result["live_order_allowed"])

    def test_market_priority_runtime_contract_detects_stale_tick_at_181_seconds(self):
        result = stock_app.build_market_priority_runtime_contract(
            focus={
                "market_priority_active": True,
                "market_phase": "regular",
                "autopilot_interval_seconds": 60,
            },
            scheduler={
                "running": True,
                "thread_alive": True,
                "effective_interval_seconds": 60,
            },
            latest_tick_age_seconds=181,
            resource_gate={"active_heavy_job_count": 0},
            runtime_age_seconds=600,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(180, result["stale_threshold_seconds"])
        self.assertIn("market_scheduler_tick_stale", result["blockers"])

    def test_market_priority_runtime_contract_detects_heavy_job_collision(self):
        result = stock_app.build_market_priority_runtime_contract(
            focus={
                "market_priority_active": True,
                "market_phase": "regular",
                "autopilot_interval_seconds": 60,
            },
            scheduler={
                "running": True,
                "thread_alive": True,
                "effective_interval_seconds": 60,
            },
            latest_tick_age_seconds=30,
            resource_gate={"active_heavy_job_count": 1},
            runtime_age_seconds=600,
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["preemption_required"])
        self.assertIn("market_priority_heavy_work_still_running", result["blockers"])

    def test_market_priority_runtime_contract_releases_after_market(self):
        result = stock_app.build_market_priority_runtime_contract(
            focus={"market_priority_active": False, "market_phase": "closed"},
            scheduler={
                "running": False,
                "thread_alive": False,
                "effective_interval_seconds": 300,
            },
            latest_tick_age_seconds=3600,
            resource_gate={"active_heavy_job_count": 1},
            runtime_age_seconds=7200,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("not_required", result["status"])
        self.assertEqual([], result["blockers"])
        self.assertFalse(result["preemption_required"])

    def test_market_priority_fault_injection_audit_passes_all_scenarios(self):
        result = stock_app.build_market_priority_fault_injection_audit()

        self.assertTrue(result["ok"])
        self.assertEqual(5, result["scenario_count"])
        self.assertEqual(5, result["passed_count"])
        self.assertEqual(0, result["failed_count"])
        self.assertTrue(all(row["passed"] for row in result["scenarios"]))
        self.assertFalse(result["live_order_allowed"])

    def test_weekend_allows_large_batch_research(self):
        clock = {"sessions": [{"id": "KR", "is_regular_open": False, "market_time": "2026-07-18T10:00:00+09:00"}]}
        focus = build_operating_focus(clock)
        self.assertEqual(focus["mode"], "MARKET_CLOSED_LARGE_RESEARCH_FOCUS")
        self.assertTrue(focus["large_batch_jobs_allowed"])
        self.assertEqual(focus["market_closed_reason"], "주말")

    def test_operator_paper_focus_uses_fast_serial_lane_after_market(self):
        focus = {
            "large_batch_jobs_allowed": False,
            "market_priority_active": False,
            "market_open": False,
            "large_batch_schedule": "weekend",
        }
        selected = {
            "ok": True,
            "status": "ready",
            "replay_id": "HREPLAY-FOCUS",
            "paper_only": True,
            "live_order_allowed": False,
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.historical_replay_evidence_milestone_status",
                return_value={"ok": True, "active_review_required_milestones": []},
            ),
            patch(
                "app.stock_suite_app.historical_replay_focus_mode_status",
                return_value={"ok": True, "active": True, "mode": "manual_paper_focus_batch"},
            ),
            patch(
                "app.stock_suite_app.next_historical_replay_regeneration_candidate",
                return_value=selected,
            ) as select_next,
        ):
            result = stock_app.next_scheduled_historical_replay_regeneration_candidate(
                now=datetime(2026, 7, 16, 21, 0, tzinfo=ZoneInfo("Asia/Seoul"))
            )

        self.assertEqual("manual_paper_focus_batch", result["schedule_mode"])
        self.assertTrue(result["focus_mode"]["active"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_order_allowed"])
        select_next.assert_called_once_with()

    def test_incremental_status_separates_skipped_and_legacy_upgrade_work(self):
        audit = {"regeneration_candidate_count": 10, "regeneration_batches": []}
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": False,
                    "interval_seconds": 15,
                    "recent_success_elapsed_seconds": [1.0],
                }
            },
        )()
        ledger_progress = {
            "resolved_count": 3,
            "legacy_resolved_count": 6,
            "unattempted_count": 7,
            "retryable_failure_count": 0,
            "blocked_failure_count": 0,
            "remaining_candidate_count": 7,
            "latest_verdict_counts": {"verified": 3, "quarantined": 0, "failed": 0},
            "unique_source_replay_count": 10,
        }
        with (
            patch("app.stock_suite_app._historical_replay_base_audit", return_value=audit),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": [], "target_count": 10},
            ),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_ledger_progress",
                return_value=ledger_progress,
            ),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
            patch("app.stock_suite_app.historical_replay_focus_mode_status", return_value={"active": False}),
        ):
            result = historical_replay_regeneration_status()

        plan = result["incremental_plan"]
        self.assertEqual(3, plan["current_evidence_skipped_count"])
        self.assertEqual(6, plan["pending_evidence_upgrade_count"])
        self.assertEqual(1, plan["genuinely_unattempted_count"])
        self.assertEqual(7, plan["remaining_count"])
        self.assertTrue(plan["append_only_checkpoint"])
        self.assertFalse(plan["old_record_rewritten"])
        self.assertFalse(plan["live_order_allowed"])

    def test_confirmed_krx_holiday_allows_large_batch_research(self):
        clock = {"sessions": [{"id": "KR", "is_regular_open": False, "market_time": "2026-07-17T10:00:00+09:00"}]}
        focus = build_operating_focus(clock)
        self.assertEqual(focus["mode"], "MARKET_CLOSED_LARGE_RESEARCH_FOCUS")
        self.assertTrue(focus["large_batch_jobs_allowed"])
        self.assertEqual(focus["market_closed_reason"], "제헌절")

    def test_confirmed_krx_holiday_overrides_premarket_phase(self):
        clock = {
            "local_time": "2026-07-17T07:30:00+09:00",
            "sessions": [
                {
                    "id": "KR",
                    "is_regular_open": False,
                    "phase": "premarket",
                    "market_time": "2026-07-17T07:30:00+09:00",
                }
            ],
        }
        focus = build_operating_focus(clock)
        self.assertEqual(focus["mode"], "MARKET_CLOSED_LARGE_RESEARCH_FOCUS")
        self.assertTrue(focus["market_closed_day"])
        self.assertFalse(focus["market_priority_active"])
        self.assertTrue(focus["heavy_research_allowed"])
        self.assertTrue(focus["large_batch_jobs_allowed"])

    def test_screener_health_probe_can_reuse_expired_success_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "agent_screener_cache.json"
            cache_file.write_text(
                json.dumps(
                    {
                        "saved_at": 1,
                        "payload": {
                            "generated_at": "2026-07-16T15:30:00+09:00",
                            "candidates": [{"symbol": "005930", "name": "sample"}],
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(stock_app, "AGENT_SCREENER_CACHE_FILE", cache_file), patch.object(
                stock_app,
                "build_screener_targets",
                side_effect=AssertionError("health probe must not rebuild an expired screener cache"),
            ):
                payload = stock_app.build_ai_screener(allow_stale_health_cache=True)

        self.assertTrue(payload["cached"])
        self.assertTrue(payload["health_probe_cache"])
        self.assertEqual(payload["candidates"][0]["symbol"], "005930")

    def test_sector_news_health_probe_can_reuse_expired_success_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "sector_news_cache.json"
            cache_file.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "generated_at": "2026-07-16T15:30:00+09:00",
                        "sectors": [{"id": "semiconductor"}],
                        "tasks": [],
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(stock_app, "SECTOR_NEWS_CACHE_FILE", cache_file), patch.object(
                stock_app,
                "fetch_news_rss",
                side_effect=AssertionError("health probe must not refetch an expired sector-news cache"),
            ):
                payload = stock_app.build_sector_news_report(allow_stale_health_cache=True)

        self.assertTrue(payload["cached"])
        self.assertTrue(payload["health_probe_cache"])
        self.assertEqual(payload["sectors"][0]["id"], "semiconductor")

    def test_sector_news_fetches_independent_sectors_concurrently(self):
        active = 0
        max_active = 0
        active_lock = threading.Lock()
        barrier = threading.Barrier(3)

        def fake_fetch(query, limit=8, timeout=7.0):
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            try:
                barrier.wait(timeout=2)
                return []
            finally:
                with active_lock:
                    active -= 1

        sectors = [
            {"id": "one", "name": "one", "query": "one"},
            {"id": "two", "name": "two", "query": "two"},
            {"id": "three", "name": "three", "query": "three"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(stock_app, "DEFAULT_SECTOR_NEWS", sectors), patch.object(
                stock_app, "SECTOR_NEWS_CACHE_FILE", root / "sector_news_cache.json"
            ), patch.object(stock_app, "OBSIDIAN_VAULT", root / "obsidian"), patch.object(
                stock_app, "fetch_news_rss", side_effect=fake_fetch
            ), patch.object(stock_app.JOURNAL, "add", return_value=None):
                payload = stock_app.build_sector_news_report(force=True)

        self.assertGreaterEqual(max_active, 2)
        self.assertEqual([row["id"] for row in payload["sectors"]], ["one", "two", "three"])

    def test_weekday_after_hours_replay_load_policy_adapts_without_parallelism(self):
        normal = stock_app._weekday_after_hours_replay_load_policy([10.0] * 8)
        light = stock_app._weekday_after_hours_replay_load_policy([1.0] * 8)
        heavy = stock_app._weekday_after_hours_replay_load_policy([100.0] * 8)
        no_history = stock_app._weekday_after_hours_replay_load_policy([])

        self.assertEqual(40, normal["cadence_seconds"])
        self.assertEqual(30, light["cadence_seconds"])
        self.assertEqual(300, heavy["cadence_seconds"])
        self.assertEqual(60, no_history["cadence_seconds"])
        self.assertTrue(normal["serial_worker"])
        self.assertTrue(normal["paper_only"])
        self.assertFalse(normal["live_order_allowed"])

    def test_replay_selection_stops_when_current_milestone_needs_review(self):
        focus = {
            "large_batch_jobs_allowed": False,
            "market_open": False,
            "large_batch_schedule": "weekend",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.historical_replay_evidence_milestone_status",
                return_value={"ok": False, "active_review_required_milestones": [25]},
            ),
            patch("app.stock_suite_app.next_historical_replay_regeneration_candidate") as select_next,
        ):
            result = stock_app.next_scheduled_historical_replay_regeneration_candidate()

        self.assertFalse(result["ok"])
        self.assertEqual("evidence_milestone_review_required", result["status"])
        self.assertEqual("evidence_fail_closed", result["schedule_mode"])
        self.assertEqual([25], result["active_review_required_milestones"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["promotion_allowed"])
        self.assertFalse(result["live_order_allowed"])
        select_next.assert_not_called()

    def test_premarket_priority_defers_historical_replay_regeneration(self):
        now = datetime(2026, 7, 15, 7, 40, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "large_batch_jobs_allowed": False,
            "large_batch_schedule": "weekend",
            "market_open": False,
            "market_phase": "premarket",
            "market_priority_active": True,
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.historical_replay_evidence_milestone_status",
                return_value={"ok": True, "active_review_required_milestones": []},
            ) as milestone_status,
            patch("app.stock_suite_app.next_historical_replay_regeneration_candidate") as select_next,
        ):
            result = stock_app.next_scheduled_historical_replay_regeneration_candidate(now=now)

        self.assertTrue(result["ok"])
        self.assertEqual("scheduled_for_market_closed_day", result["status"])
        self.assertEqual("market_priority_deferred", result["schedule_mode"])
        self.assertTrue(result["market_priority_active"])
        self.assertEqual("premarket", result["market_phase"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_order_allowed"])
        milestone_status.assert_not_called()
        select_next.assert_not_called()

    def test_weekday_after_hours_replay_lane_enforces_cooldown(self):
        now = datetime(2026, 7, 14, 21, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "large_batch_jobs_allowed": False,
            "market_open": False,
            "large_batch_schedule": "weekend",
        }
        ledger = [
            {
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                "generated_at": "2026-07-14T20:58:00+09:00",
            }
        ]
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.historical_replay_evidence_milestone_status",
                return_value={"ok": True, "active_review_required_milestones": []},
            ),
            patch(
                "app.stock_suite_app._weekday_after_hours_replay_load_policy",
                return_value={"cadence_seconds": 300},
            ),
            patch("app.stock_suite_app._read_jsonl", return_value=ledger),
            patch("app.stock_suite_app._historical_replay_campaign_manifest_scope", return_value=(0, set())),
            patch("app.stock_suite_app.next_historical_replay_regeneration_candidate") as select_next,
        ):
            result = stock_app.next_scheduled_historical_replay_regeneration_candidate(now=now)

        self.assertEqual("weekday_after_hours_cooldown", result["status"])
        self.assertEqual(180, result["retry_after_seconds"])
        self.assertEqual(300, result["cadence_seconds"])
        self.assertEqual("2026-07-14T21:03:00+09:00", result["next_eligible_at"])
        self.assertEqual(25, result["max_source_trade_count"])
        select_next.assert_not_called()

    def test_weekday_after_hours_replay_lane_selects_only_small_contracts(self):
        now = datetime(2026, 7, 14, 21, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "large_batch_jobs_allowed": False,
            "market_open": False,
            "large_batch_schedule": "weekend",
        }
        ledger = [
            {
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "generated_at": "2026-07-14T20:00:00+09:00",
            }
        ]
        selected = {"ok": True, "status": "ready", "replay_id": "HREPLAY-2"}
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.historical_replay_evidence_milestone_status",
                return_value={"ok": True, "active_review_required_milestones": []},
            ),
            patch(
                "app.stock_suite_app._weekday_after_hours_replay_load_policy",
                return_value={"cadence_seconds": 300},
            ),
            patch("app.stock_suite_app._read_jsonl", return_value=ledger),
            patch("app.stock_suite_app._historical_replay_campaign_manifest_scope", return_value=(0, set())),
            patch(
                "app.stock_suite_app.next_historical_replay_regeneration_candidate",
                return_value=selected,
            ) as select_next,
        ):
            result = stock_app.next_scheduled_historical_replay_regeneration_candidate(now=now)

        self.assertEqual("weekday_after_hours_bounded", result["schedule_mode"])
        self.assertEqual(300, result["retry_after_seconds"])
        self.assertEqual(300, result["cadence_seconds"])
        self.assertEqual("2026-07-14T21:05:00+09:00", result["next_eligible_at"])
        select_next.assert_called_once_with(max_source_trade_count=25)

    def test_weekday_after_hours_replay_lane_probes_next_lane_only_after_small_lane_finishes(self):
        now = datetime(2026, 7, 14, 21, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "large_batch_jobs_allowed": False,
            "market_open": False,
            "large_batch_schedule": "weekend",
        }
        first = {
            "ok": False,
            "status": "no_recoverable_contract_in_queue",
            "deferred_large_candidate_count": 10,
        }
        second = {
            "ok": True,
            "status": "ready",
            "replay_id": "HREPLAY-40",
            "source_trade_count": 40,
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.historical_replay_evidence_milestone_status",
                return_value={"ok": True, "active_review_required_milestones": []},
            ),
            patch(
                "app.stock_suite_app._weekday_after_hours_replay_load_policy",
                return_value={"cadence_seconds": 300},
            ),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch("app.stock_suite_app._historical_replay_campaign_manifest_scope", return_value=(0, set())),
            patch(
                "app.stock_suite_app.next_historical_replay_regeneration_candidate",
                side_effect=[first, second],
            ) as select_next,
        ):
            result = stock_app.next_scheduled_historical_replay_regeneration_candidate(now=now)

        self.assertEqual("HREPLAY-40", result["replay_id"])
        self.assertTrue(result["adaptive_lane"])
        self.assertTrue(result["adaptive_probe"])
        self.assertEqual(50, result["max_source_trade_count"])
        self.assertEqual(0, result["weekday_runtime_profiles"][0]["sample_count"])
        self.assertEqual(
            [
                unittest.mock.call(max_source_trade_count=25),
                unittest.mock.call(max_source_trade_count=50),
            ],
            select_next.call_args_list,
        )

    def test_weekday_after_hours_replay_lane_blocks_slow_expansion_until_weekend(self):
        ledger = [
            {
                "source_replay_id": "HREPLAY-SLOW",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                "source_trade_count": 40,
                "started_at": "2026-07-14T20:00:00+09:00",
                "generated_at": "2026-07-14T20:02:00+09:00",
            }
        ]
        first = {
            "ok": False,
            "status": "no_recoverable_contract_in_queue",
            "deferred_large_candidate_count": 10,
        }
        with patch(
            "app.stock_suite_app.next_historical_replay_regeneration_candidate",
            return_value=first,
        ) as select_next:
            result = stock_app._select_weekday_after_hours_replay_candidate(
                ledger_rows=ledger,
                campaign_ids={"HREPLAY-SLOW"},
            )

        self.assertEqual("weekday_after_hours_runtime_guard", result["status"])
        self.assertEqual(25, result["max_source_trade_count"])
        self.assertFalse(result["adaptive_lane"])
        self.assertFalse(result["weekday_runtime_profiles"][0]["observed_safe"])
        self.assertEqual(120.0, result["weekday_runtime_profiles"][0]["max_elapsed_seconds"])
        select_next.assert_called_once_with(max_source_trade_count=25)

    def test_weekday_replay_cooldown_ignores_rows_outside_frozen_campaign(self):
        now = datetime(2026, 7, 14, 21, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "large_batch_jobs_allowed": False,
            "market_open": False,
            "large_batch_schedule": "weekend",
        }
        ledger = [
            {
                "source_replay_id": "HREPLAY-IN-SCOPE",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "generated_at": "2026-07-14T20:00:00+09:00",
            },
            {
                "source_replay_id": "HREPLAY-OUTSIDE",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "generated_at": "2026-07-14T20:59:00+09:00",
            },
        ]
        selected = {"ok": True, "status": "ready", "replay_id": "HREPLAY-IN-SCOPE"}
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.historical_replay_evidence_milestone_status",
                return_value={"ok": True, "active_review_required_milestones": []},
            ),
            patch(
                "app.stock_suite_app._weekday_after_hours_replay_load_policy",
                return_value={"cadence_seconds": 300},
            ),
            patch("app.stock_suite_app._read_jsonl", return_value=ledger),
            patch(
                "app.stock_suite_app._historical_replay_campaign_manifest_scope",
                return_value=(1, {"HREPLAY-IN-SCOPE"}),
            ),
            patch(
                "app.stock_suite_app.next_historical_replay_regeneration_candidate",
                return_value=selected,
            ) as select_next,
        ):
            result = stock_app.next_scheduled_historical_replay_regeneration_candidate(now=now)

        self.assertEqual("HREPLAY-IN-SCOPE", result["replay_id"])
        self.assertEqual("weekday_after_hours_bounded", result["schedule_mode"])
        select_next.assert_called_once_with(max_source_trade_count=25)

    def test_market_open_daemon_cycle_defers_heavy_research(self):
        daemon = AiResearchDaemon()
        focus = build_operating_focus({"sessions": [{"id": "KR", "is_regular_open": True, "market_time": "2026-07-14T10:00:00+09:00"}]})
        with patch("app.stock_suite_app.build_operating_focus", return_value=focus), patch(
            "app.stock_suite_app.MEMORY.append_cycle"
        ), patch("app.stock_suite_app.JOURNAL.add"):
            cycle = daemon.run_cycle(source="daemon")
        self.assertIn(cycle["status"], {"MARKET_PULSE_ACTIVE", "MARKET_PULSE_DEGRADED"})
        self.assertEqual(cycle["heavy_research_status"], "DEFERRED_MARKET_PRIORITY")
        self.assertIn("과거장 리플레이", cycle["deferred_tasks"])

    def test_premarket_focus_blocks_heavy_research_and_prioritizes_scheduler(self):
        focus = build_operating_focus(
            {
                "sessions": [
                    {
                        "id": "KR",
                        "phase": "premarket",
                        "is_regular_open": False,
                        "market_time": "2026-07-15T07:40:00+09:00",
                    }
                ]
            }
        )
        self.assertEqual(focus["mode"], "MARKET_PREPARATION_FOCUS")
        self.assertTrue(focus["market_priority_active"])
        self.assertFalse(focus["market_open"])
        self.assertEqual(focus["trading_focus_pct"], 100)
        self.assertEqual(focus["research_focus_pct"], 0)
        self.assertFalse(focus["heavy_research_allowed"])
        self.assertEqual(focus["autopilot_interval_seconds"], 300)
        self.assertEqual(focus["research_cycle_min_seconds"], 300)

        daemon = AiResearchDaemon()
        with patch("app.stock_suite_app.build_operating_focus", return_value=focus), patch.object(
            daemon, "_run_market_execution_focus_cycle", return_value={"status": "PREMARKET_PRIORITY"}
        ) as market_cycle:
            cycle = daemon.run_cycle(source="daemon")
        market_cycle.assert_called_once_with("daemon", focus)
        self.assertEqual(cycle["status"], "PREMARKET_PRIORITY")

    def test_market_open_manual_cycle_cannot_bypass_resource_priority(self):
        daemon = AiResearchDaemon()
        focus = {"market_priority_active": True, "mode": "MARKET_EXECUTION_FOCUS"}
        with patch("app.stock_suite_app.build_operating_focus", return_value=focus), patch.object(
            daemon,
            "_run_market_execution_focus_cycle",
            return_value={"status": "MARKET_PRIORITY", "source": "manual"},
        ) as market_cycle:
            cycle = daemon.run_cycle(source="manual")
        market_cycle.assert_called_once_with("manual", focus)
        self.assertEqual(cycle["status"], "MARKET_PRIORITY")

    def test_research_startup_delay_defaults_to_market_priority_and_allows_override(self):
        with patch("app.stock_suite_app.build_operating_focus", return_value={"market_priority_active": True}), patch.dict(
            stock_app.os.environ, {}, clear=False
        ):
            stock_app.os.environ.pop("CODEXSTOCK_RESEARCH_INITIAL_DELAY_SECONDS", None)
            self.assertEqual(_research_startup_initial_delay_seconds(), 120)
        with patch.dict(stock_app.os.environ, {"CODEXSTOCK_RESEARCH_INITIAL_DELAY_SECONDS": "17"}):
            self.assertEqual(_research_startup_initial_delay_seconds(), 17)

    def test_market_priority_http_payload_reuses_expensive_dashboard_result(self):
        calls: list[int] = []

        def builder() -> dict[str, object]:
            calls.append(1)
            return {"ok": True, "build_count": len(calls)}

        cache_key = "test-market-priority-http-cache"
        with stock_app.MARKET_PRIORITY_HTTP_CACHE_LOCK:
            stock_app.MARKET_PRIORITY_HTTP_CACHE.pop(cache_key, None)
            stock_app.MARKET_PRIORITY_HTTP_BUILD_LOCKS.pop(cache_key, None)
        focus = {"market_priority_active": True, "market_phase": "premarket"}
        with patch("app.stock_suite_app.build_operating_focus", return_value=focus):
            first = stock_app._market_priority_http_payload(
                cache_key,
                builder,
                premarket_ttl_seconds=30,
                regular_ttl_seconds=5,
            )
            second = stock_app._market_priority_http_payload(
                cache_key,
                builder,
                premarket_ttl_seconds=30,
                regular_ttl_seconds=5,
            )

        self.assertEqual(len(calls), 1)
        self.assertFalse(first["market_priority_cache"]["hit"])
        self.assertTrue(second["market_priority_cache"]["hit"])

    def test_market_priority_defers_heavy_jobs_but_keeps_live_order_routes_open(self):
        focus = {"market_priority_active": True, "market_phase": "regular"}
        with patch("app.stock_suite_app.build_operating_focus", return_value=focus):
            deferred = stock_app._market_priority_deferred_request(
                "POST",
                "/api/external-engines/vectorbt/backtest",
            )
            live_route = stock_app._market_priority_deferred_request(
                "POST",
                "/api/ops/live/submit",
            )

        self.assertEqual(deferred["status"], "DEFERRED_MARKET_PRIORITY")
        self.assertIsNone(live_route)

        with patch(
            "app.stock_suite_app.build_operating_focus",
            return_value={"market_priority_active": False},
        ):
            self.assertIsNone(
                stock_app._market_priority_deferred_request(
                    "GET",
                    "/api/backtest",
                )
            )

    def test_autopilot_scheduler_runs_at_one_minute_during_market(self):
        scheduler = AutopilotScheduler()
        focus = build_operating_focus({"sessions": [{"id": "KR", "is_regular_open": True, "market_time": "2026-07-14T10:00:00+09:00"}]})
        with patch("app.stock_suite_app.build_operating_focus", return_value=focus):
            self.assertEqual(scheduler._next_interval_seconds({"summary": {"cadence_minutes": 5}}), 60)

    def test_fallback_position_drops_lot_already_closed_at_broker(self):
        performance = {
            "open_lots": [{"symbol": "091970", "name": "LSK아이로봇", "quantity": 1, "buy_price": 2905}],
        }
        broker_events = [
            {"symbol": "091970", "side": "BUY", "quantity": 1},
            {"symbol": "091970", "side": "SELL", "quantity": 1},
        ]
        with patch("app.stock_suite_app.build_live_trade_performance", return_value=performance), patch(
            "app.stock_suite_app._live_reconciliation_flatten_broker_checks", return_value=(broker_events, 0)
        ):
            self.assertEqual(_fallback_live_positions_from_order_log(), [])

    def test_position_review_trusts_recent_confirmed_empty_account_snapshot(self):
        snapshot = {
            "ok": True,
            "snapshot_at": "2026-07-14T12:44:02+09:00",
            "positions": [],
            "position_count": 0,
        }
        with patch("app.stock_suite_app.INTEGRATIONS.kis_account", return_value={"ok": False, "positions": []}), patch(
            "app.stock_suite_app._latest_confirmed_live_account_snapshot", return_value=snapshot
        ), patch("app.stock_suite_app._fallback_live_positions_from_order_log") as fallback:
            review = _delegated_live_position_reviews({})
        fallback.assert_not_called()
        self.assertEqual(review["reviews"], [])
        self.assertTrue(review["confirmed_snapshot_used"])

    def test_position_review_uses_restart_safe_partial_profit_plan(self):
        position = {
            "symbol": "005930", "name": "Samsung Electronics", "quantity": 10,
            "available_quantity": 10, "avg_price": 100_000, "current_price": 104_000,
            "profit_loss_rate": 4.0, "buy_at": "2026-07-20T09:10:00+09:00",
        }
        screener = {
            "symbol": "005930", "amount": 50_000_000_000, "change_pct": 4.0,
            "company_quality": {"grade": "A", "score": 80, "blockers": []},
            "risk_flags": [],
            "trade_horizon": {"mode": "스윙", "stop_loss_pct": 2.0, "take_profit_pct": 3.0},
        }
        with tempfile.TemporaryDirectory() as directory, \
            patch.object(stock_app.OPS, "data_dir", Path(directory)), \
            patch("app.stock_suite_app.INTEGRATIONS.kis_account", return_value={"ok": True, "positions": [position]}), \
            patch("app.stock_suite_app.build_market_session_clock", return_value={"sessions": [{"id": "KR"}]}), \
            patch("app.stock_suite_app.build_ai_screener", return_value={"candidates": [screener]}), \
            patch("app.stock_suite_app.fetch_kr_market_rows", return_value=("2026-07-20", [])):
            review = _delegated_live_position_reviews({
                "delegated_live_profit_partial_exit_pct": 50,
                "delegated_live_profit_trailing_drawdown_pct": 1,
            })
        decision = review["reviews"][0]
        self.assertEqual(decision["urgency"], "profit_partial")
        self.assertEqual(decision["recommended_exit_quantity"], 5)
        self.assertEqual(decision["exit_scope"], "partial_available_position")
        self.assertTrue(str(decision["exit_plan_id"]).startswith("EXIT-"))

    def test_asset_gear_includes_one_day_move_for_premarket_report(self):
        rows = [{"date": "2026-07-10", "close": 100.0}, {"date": "2026-07-11", "close": 102.0}]
        with patch("app.stock_suite_app._market_series", return_value={"source": "test", "rows": rows}):
            gear = _asset_gear("SPY", "S&P500", days=2)
        self.assertEqual(gear["return_1d_pct"], 2.0)

    def test_midday_telegram_report_keeps_only_market_trade_and_next_plan(self):
        market_rows = [
            {"symbol": "005930", "name": "삼성전자", "change_pct": 4.2, "amount": 300_000_000_000},
            {"symbol": "000660", "name": "SK하이닉스", "change_pct": 3.1, "amount": 250_000_000_000},
            {"symbol": "035720", "name": "카카오", "change_pct": -5.3, "amount": 80_000_000_000},
        ]
        trade_summary = {
            "live_submitted": [{"line": "삼성전자 매수 1주 @ 80,000원", "side": "BUY", "message": "거래대금 확인"}],
            "paper_filled": [{"line": "SK하이닉스 매수 1주 @ 200,000원", "side": "BUY", "message": "모의훈련"}],
        }
        live_memory = {
            "realized_preview": {"realized": [{"name": "삼성전자", "pnl_pct": 1.5, "exit_reason": "수익보호"}]},
            "latest_review_summary": "추격 진입을 줄여야 합니다.",
        }
        with patch("app.stock_suite_app.fetch_kr_market_rows", return_value=("2026-07-14", market_rows)), patch(
            "app.stock_suite_app.analyze_kr_market", return_value={"headline": "한국장 강세"}
        ), patch("app.stock_suite_app.build_sector_news_report", return_value={"sectors": []}), patch(
            "app.stock_suite_app.build_today_trade_quick_summary", return_value=trade_summary
        ), patch("app.stock_suite_app.build_live_trade_memory_summary", return_value=live_memory):
            text = build_scheduled_report_text("market_midday", {"label": "장중"}, plan={})

        self.assertTrue(text.startswith("[장중 핵심]"))
        self.assertIn("강세:", text)
        self.assertIn("약세:", text)
        self.assertIn("[실제매매]", text)
        self.assertIn("[모의매매]", text)
        self.assertIn("수익/청산:", text)
        self.assertIn("부족한 점:", text)
        self.assertIn("다음 계획:", text)
        self.assertNotIn("오토파일럿:", text)

    def test_simple_trade_telegram_distinguishes_paper_and_live(self):
        trade = {
            "symbol": "005930",
            "name": "삼성전자",
            "side": "BUY",
            "quantity": 2,
            "price": 81000,
            "created_at": "2026-07-14T10:15:00+09:00",
        }
        paper = build_simple_trade_telegram_text(trade, report_mode="paper", reason="거래대금과 주도 테마 확인")
        live = build_simple_trade_telegram_text(trade, report_mode="live_execution", reason="최종 게이트 통과")

        self.assertTrue(paper.startswith("[모의매매]"))
        self.assertIn("실제 계좌 주문이 아닙니다", paper)
        self.assertNotIn("[실제매매 주문]", paper)
        self.assertTrue(live.startswith("[실제매매 주문]"))
        self.assertIn("실제매수 주문 제출", live)
        self.assertNotIn("실제 계좌 주문이 아닙니다", live)

    def test_autopilot_restores_for_standing_delegation_but_honors_halt(self):
        policy = {
            "delegated_live_autonomy_enabled": True,
            "delegated_live_authorization_confirmed": True,
            "delegated_live_authorized_date": stock_app.today_kst(),
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
            "paper_autopilot_enabled": False,
            "live_candidate_enabled": False,
            "emergency_halt": False,
            "day_halted": False,
        }
        self.assertTrue(_autopilot_should_restore({}, policy))
        stale = {**policy, "delegated_live_authorized_date": "2026-07-10"}
        self.assertFalse(_autopilot_should_restore({}, stale))
        self.assertTrue(_autopilot_should_restore({}, {**stale, "live_candidate_enabled": True}))
        self.assertFalse(_autopilot_should_restore({}, {**policy, "day_halted": True}))
        self.assertFalse(_autopilot_should_restore({"enabled": True}, {**policy, "day_halted": True}))

    def test_delegated_live_authorization_expires_each_trading_day(self):
        policy = {
            "delegated_live_autonomy_enabled": True,
            "delegated_live_authorization_confirmed": True,
            "delegated_live_authorized_date": "2026-07-14",
        }
        expired = build_delegated_live_authorization(policy, target_date="2026-07-15")
        valid = build_delegated_live_authorization(
            {**policy, "delegated_live_authorized_date": "2026-07-15"},
            target_date="2026-07-15",
        )
        self.assertFalse(expired["valid_today"])
        self.assertEqual(expired["status"], "DAILY_AUTHORIZATION_EXPIRED")
        self.assertTrue(valid["valid_today"])
        self.assertEqual(valid["status"], "AUTHORIZED_TODAY")

    def test_delegated_live_diversification_splits_total_cash_across_symbols(self):
        diversified = stock_app._delegated_live_diversification_request(
            "30% 자금 알아서 2종목 이상",
            30,
        )
        single = stock_app._delegated_live_diversification_request(
            "주문가능 현금 30%",
            30,
        )

        self.assertEqual(2, diversified["target_symbol_count"])
        self.assertEqual(2, diversified["max_buy_orders_per_day"])
        self.assertEqual(15.0, diversified["per_symbol_cash_pct"])
        self.assertTrue(diversified["distinct_symbols_required"])
        self.assertEqual(1, single["target_symbol_count"])
        self.assertEqual(30.0, single["per_symbol_cash_pct"])

    def test_explicit_live_delegation_wins_over_today_trade_read_query(self):
        command = "오늘 주문가능 현금 총 30% 이내를 서로 다른 2종목에 분산해 실전 자동매매하도록 최종 위임한다"
        expected = {"ok": True, "reply": "delegated", "actions": []}
        with patch("app.stock_suite_app.load_ai_brain", return_value={"provider": "test", "model": "test"}), patch(
            "app.stock_suite_app._execute_ops_command_if_any", return_value=expected
        ) as execute_ops, patch("app.stock_suite_app.is_today_trade_quick_query") as quick_query:
            result = stock_app.execute_agent_command(command, source="test")

        self.assertEqual(expected, result)
        execute_ops.assert_called_once()
        quick_query.assert_not_called()

    def test_ai_model_identity_question_uses_fast_truthful_reply(self):
        with patch(
            "app.stock_suite_app.load_ai_brain",
            return_value={"provider": "ollama-gemma", "model": "gemma4:latest"},
        ), patch("app.stock_suite_app.JOURNAL.add"), patch(
            "app.stock_suite_app.ask_selected_ai_brain"
        ) as ai_brain:
            result = stock_app.execute_agent_command("너 젬마4야?", source="test")

        self.assertTrue(result["ok"])
        self.assertIn("gemma4:latest", result["reply"])
        self.assertTrue(result["brain"]["fast_path"])
        ai_brain.assert_not_called()

    def test_secretary_smalltalk_skips_slow_model_even_when_gemma_is_configured(self):
        with patch(
            "app.stock_suite_app.load_ai_brain",
            return_value={"provider": "ollama-gemma", "model": "gemma4:latest"},
        ), patch("app.stock_suite_app.JOURNAL.add"), patch(
            "app.stock_suite_app.ask_selected_ai_brain"
        ) as ai_brain:
            result = stock_app.execute_agent_command("안녕", source="test")

        self.assertTrue(result["ok"])
        self.assertTrue(result["brain"]["fast_path"])
        self.assertEqual("builtin-fast", result["brain"]["provider"])
        ai_brain.assert_not_called()

    def test_secretary_uses_light_model_unless_deep_reasoning_is_requested(self):
        tags = {
            "ok": True,
            "models": ["qwen2.5:3b", "qwen2.5:1.5b", "gemma4:latest"],
        }
        with patch(
            "app.stock_suite_app.resolve_ollama_model",
            return_value={"model": "gemma4:latest", "configured_model": "gemma4:latest", "tags": tags},
        ):
            fast = stock_app._resolve_secretary_ollama_model(
                "gemma4:latest", "http://127.0.0.1:11434", "자유롭게 이야기해줘"
            )
            deep = stock_app._resolve_secretary_ollama_model(
                "gemma4:latest", "http://127.0.0.1:11434", "심층 분석해줘"
            )

        self.assertEqual("qwen2.5:1.5b", fast["model"])
        self.assertTrue(fast["fast_secretary"])
        self.assertEqual("gemma4:latest", deep["model"])
        self.assertFalse(deep["fast_secretary"])

    def test_ai_mission_report_returns_object_contract(self):
        daemon_status = {
            "running": True,
            "interval_seconds": 300,
            "memory": {
                "cycle_count": 4,
                "historical_replay_memory_count": 2,
                "knowledge_graph": {"node_count": 3, "edge_count": 2},
                "top_candidates": [],
            },
            "last_cycle": {},
        }
        with patch("app.stock_suite_app.AI_DAEMON.status", return_value=daemon_status), patch(
            "app.stock_suite_app.fetch_kr_market_rows", return_value=("20260717", [])
        ), patch("app.stock_suite_app.analyze_kr_market", return_value={}), patch(
            "app.stock_suite_app.analyze_themes_from_rows", return_value=[]
        ), patch("app.stock_suite_app.build_agent_radar", return_value={}), patch(
            "app.stock_suite_app.build_ai_screener", return_value={}
        ), patch("app.stock_suite_app.build_market_session_clock", return_value={}), patch(
            "app.stock_suite_app.build_ai_pipeline", return_value={"summary": {}}
        ):
            report = stock_app.build_ai_mission_report()

        self.assertIsInstance(report, dict)
        self.assertTrue(report["running"])
        self.assertEqual(4, report["cycle_count"])
        self.assertEqual("20260717", report["latest_trading_day"])
        self.assertIn("task_queue", report)

    def test_autotrade_capability_question_reads_policy_instead_of_ai_guess(self):
        status = {
            "flags": {
                "delegated_live_autonomy_enabled": True,
                "delegated_live_authorized_today": True,
            },
            "capital_policy": {
                "auto_submit_max_cash_pct": 30.0,
                "max_position_cash_pct": 15.0,
            },
            "delegated_authorization": {
                "trading_date": "2026-07-15",
                "valid_today": True,
            },
        }
        policy = {
            "delegated_live_max_buy_orders_per_day": 2,
            "delegated_live_max_sell_orders_per_day": 1,
        }
        with patch("app.stock_suite_app.load_ai_brain", return_value={"provider": "test", "model": "test"}), patch(
            "app.stock_suite_app.build_autotrade_status_quick", return_value=status
        ), patch("app.stock_suite_app.OPS.autotrade_policy", return_value=policy), patch(
            "app.stock_suite_app._delegated_live_order_counts", return_value={"total": 1, "buy": 1, "sell": 0}
        ), patch("app.stock_suite_app.ask_selected_ai_brain") as ai_brain:
            result = stock_app.execute_agent_command("코덱스스톡 자동으로 매매하는 기능 있어?", source="test")

        self.assertTrue(result["ok"])
        self.assertIn("실전 위임 자동매매 기능", result["reply"])
        self.assertIn("주문마다 다시 묻지 않습니다", result["reply"])
        self.assertIn("총 30%", result["reply"])
        self.assertIn("종목당 최대 15%", result["reply"])
        ai_brain.assert_not_called()

    def test_autotrade_status_poll_never_scans_detailed_ledgers(self):
        stock_app.AUTOTRADE_STATUS_QUICK_CACHE = None
        policy = {
            "delegated_live_autonomy_enabled": False,
            "paper_autopilot_enabled": True,
            "live_candidate_enabled": True,
            "live_pilot_enabled": False,
            "live_execution_enabled": False,
            "require_approval": True,
            "emergency_halt": False,
            "day_halted": False,
            "buy_blocked": False,
        }
        with patch("app.stock_suite_app.OPS.autotrade_policy", return_value=policy), patch(
            "app.stock_suite_app.AUTOPILOT_SCHEDULER.status",
            side_effect=AssertionError("scheduler.status must not run during polling"),
        ), patch(
            "app.stock_suite_app.AI_DAEMON.status",
            side_effect=AssertionError("daemon.status must not run during polling"),
        ), patch(
            "app.stock_suite_app.OPS.approvals",
            side_effect=AssertionError("approval ledger must not run during polling"),
        ), patch(
            "app.stock_suite_app.build_today_trade_quick_summary",
            side_effect=AssertionError("trade ledgers must not run during polling"),
        ):
            result = stock_app.build_autotrade_status_quick()

        self.assertTrue(result["ok"])
        self.assertTrue(result["quick"])
        self.assertEqual("memory_and_policy_only", result["poll_health"]["profile"])
        self.assertEqual("ops_status_poll_cache_stabilized", result["server_runtime"]["runtime_marker"])

    def test_today_live_buy_symbols_reads_direct_and_nested_symbols(self):
        rows = [
            {"status": "LIVE_SUBMITTED", "side": "BUY", "symbol": "005930"},
            {"status": "LIVE_SUBMITTED", "side": "BUY", "plan": {"ticket": {"symbol": "000660"}}},
            {"status": "LIVE_SUBMITTED", "side": "SELL", "symbol": "035420"},
        ]
        with patch("app.stock_suite_app._today_live_submits", return_value=rows):
            symbols = stock_app._today_live_buy_symbols()

        self.assertEqual({"005930", "000660"}, symbols)

    def test_live_candidate_selection_skips_symbols_already_bought_today(self):
        plan = {
            "generated_at": "2026-07-15T10:00:00+09:00",
            "buy_candidates": [
                {"symbol": "005930", "name": "삼성전자", "growth_score": 95, "reasons": ["거래대금"]},
                {"symbol": "000660", "name": "SK하이닉스", "growth_score": 85, "reasons": ["거래대금"]},
            ],
            "account": {},
            "limits": {},
            "daytrade_scout": {"work_date": "2026-07-15"},
        }
        with patch("app.stock_suite_app._today_live_buy_symbols", return_value={"005930"}), patch(
            "app.stock_suite_app.build_small_account_growth_plan", return_value=plan
        ), patch(
            "app.stock_suite_app.latest_intraday_minute_radar_records", return_value=[]
        ), patch("app.stock_suite_app.missed_buy_feedback_live_rows", return_value=[]), patch(
            "app.stock_suite_app.build_market_session_clock", return_value={"sessions": [{"id": "KR", "is_regular_open": True}]}
        ), patch("app.stock_suite_app.today_kst", return_value="2026-07-15"), patch(
            "app.stock_suite_app._iso_age_seconds", return_value=60
        ):
            selected = stock_app.select_ai_live_pilot_symbol(side="BUY", max_notional=300_000, quantity=1)

        self.assertEqual("000660", selected["symbol"])
        self.assertNotIn("005930", {row["symbol"] for row in selected["candidate_pool"]})
        self.assertTrue(selected["eligible_for_live_buy"])

    def test_stale_candidate_source_is_visible_but_not_live_buy_eligible(self):
        stale_plan = {
            "generated_at": "2026-07-13T10:01:06+09:00",
            "stale_cache_allowed": True,
            "buy_candidates": [
                {"symbol": "001440", "name": "대한전선", "growth_score": 100, "reasons": ["오래된 거래대금"]},
            ],
            "daytrade_scout": {"work_date": "2026-07-13"},
        }
        with patch("app.stock_suite_app._today_live_buy_symbols", return_value=set()), patch(
            "app.stock_suite_app.build_small_account_growth_plan", return_value=stale_plan
        ), patch(
            "app.stock_suite_app.latest_intraday_minute_radar_records", return_value=[]
        ), patch("app.stock_suite_app.missed_buy_feedback_live_rows", return_value=[]), patch(
            "app.stock_suite_app.build_market_session_clock", return_value={"sessions": [{"id": "KR", "is_regular_open": True}]}
        ), patch("app.stock_suite_app.today_kst", return_value="2026-07-15"), patch(
            "app.stock_suite_app._iso_age_seconds", return_value=172800
        ):
            selected = stock_app.select_ai_live_pilot_symbol(side="BUY", max_notional=300_000, quantity=1)

        self.assertEqual("001440", selected["symbol"])
        self.assertFalse(selected["eligible_for_live_buy"])
        self.assertEqual("stale", selected["candidate_source_freshness"]["state"])
        self.assertIn("시장 자료 기준일 2026-07-13", selected["candidate_source_freshness"]["detail"])

    def test_automated_live_buy_requires_average_and_latest_strength_at_least_100(self):
        weak = stock_app._live_buy_strength_gate(
            "BUY",
            "small_account_growth",
            True,
            {"ok": True, "avg_strength": 98.5, "latest_strength": 101.0},
        )
        strong = stock_app._live_buy_strength_gate(
            "BUY",
            "small_account_growth",
            True,
            {"ok": True, "avg_strength": 104.0, "latest_strength": 103.0},
        )
        missing = stock_app._live_buy_strength_gate("BUY", "ai_screener", True, {"ok": False})
        radar_weak = stock_app._live_buy_strength_gate(
            "BUY",
            "intraday_affordable_radar",
            True,
            {"ok": True, "avg_strength": 104.9, "latest_strength": 130.0},
        )
        radar_strong = stock_app._live_buy_strength_gate(
            "BUY",
            "intraday_affordable_radar",
            True,
            {"ok": True, "avg_strength": 120.0, "latest_strength": 110.0},
        )

        self.assertFalse(weak["ok"])
        self.assertTrue(weak["required"])
        self.assertTrue(strong["ok"])
        self.assertFalse(missing["ok"])
        self.assertTrue(radar_weak["required"])
        self.assertFalse(radar_weak["ok"])
        self.assertEqual(105.0, radar_weak["threshold"])
        self.assertTrue(radar_strong["ok"])
        self.assertIn("확인하지 못했습니다", missing["detail"])

    def test_intraday_radar_requires_positive_current_minute_momentum(self):
        fading = stock_app._live_buy_minute_momentum_gate(
            "BUY", "intraday_affordable_radar", True, {"ok": True, "momentum_pct": -0.01}
        )
        continuing = stock_app._live_buy_minute_momentum_gate(
            "BUY", "intraday_affordable_radar", True, {"ok": True, "momentum_pct": 0.01}
        )

        self.assertTrue(fading["required"])
        self.assertFalse(fading["ok"])
        self.assertTrue(continuing["ok"])

    def test_live_trade_incident_writes_jsonl_and_markdown_once(self):
        payload = {
            "date": "2026-07-15",
            "title": "약한 강도 후보 오선정",
            "summary": "오래된 후보 캐시와 약한 실시간 강도를 충분히 차단하지 못했습니다.",
            "symbols": [
                {"symbol": "001440", "name": "대한전선", "buy_price": 28600, "sell_price": 29550, "pnl_pct": 3.32},
                {"symbol": "010140", "name": "삼성중공업", "buy_price": 21750, "sell_price": 21675, "pnl_pct": -0.34},
            ],
            "causes": ["후보 생성일 검증 누락", "체결강도 차단 기준이 너무 낮음"],
            "corrective_actions": ["당일 후보만 실전 매수 허용", "평균·최신 체결강도 100 이상 강제"],
            "outcome": {"estimated_net_pnl_krw": 775, "estimated_net_pnl_pct": 1.54},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incident_file = root / "live_trade_incidents.jsonl"
            vault = root / "vault"
            with patch("app.stock_suite_app.LIVE_TRADE_INCIDENT_FILE", incident_file), patch(
                "app.stock_suite_app.OBSIDIAN_VAULT", vault
            ):
                first = stock_app.record_live_trade_incident(payload)
                second = stock_app.record_live_trade_incident(payload)

            self.assertTrue(first["saved"])
            self.assertFalse(second["saved"])
            self.assertEqual(1, len(incident_file.read_text(encoding="utf-8").splitlines()))
            self.assertTrue(Path(first["note_path"]).exists())
            latest_text = Path(first["latest_note_path"]).read_text(encoding="utf-8")
            self.assertIn("약한 강도 후보 오선정", latest_text)
            self.assertIn("평균·최신 체결강도 100 이상 강제", latest_text)

    def test_candidate_creation_blockers_include_theme_gate_after_inserted_checks(self):
        checks = [
            {"label": f"후보 검사 {index}", "status": "ok"}
            for index in range(20)
        ]
        checks.append({"label": "테마 내 대체후보 비교", "status": "blocked", "detail": "상대강도 부족"})
        checks.append({"label": "계좌 조회", "status": "blocked", "detail": "후속 실행 검사"})

        blockers = stock_app._candidate_creation_blockers(checks)

        self.assertEqual(["테마 내 대체후보 비교"], [row["label"] for row in blockers])

    def test_candidate_decision_blockers_survive_to_final_submit_gate(self):
        report = {
            "checks_summary": {
                "blocked_count": 2,
                "blocked_labels": ["테마 내 대체후보 비교"],
            }
        }

        labels = stock_app._candidate_decision_blocker_labels(report)

        self.assertEqual(2, len(labels))
        self.assertEqual("테마 내 대체후보 비교", labels[0])

    def test_scheduler_status_does_not_label_expired_delegation_active(self):
        scheduler = AutopilotScheduler()
        policy = {
            "delegated_live_autonomy_enabled": True,
            "delegated_live_authorization_confirmed": True,
            "delegated_live_authorized_date": "2026-07-10",
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
            "live_candidate_enabled": True,
        }
        with patch.object(scheduler, "load_state", return_value={"enabled": True}), patch(
            "app.stock_suite_app.build_operating_focus", return_value={}
        ), patch("app.stock_suite_app.OPS.autotrade_policy", return_value=policy), patch(
            "app.stock_suite_app.autopilot_runs", return_value=[]
        ):
            status = scheduler.status()
        self.assertEqual(status["live_execution_state"], "DAILY_AUTHORIZATION_REQUIRED")
        self.assertFalse(status["delegated_live_authorization"]["valid_today"])

    def test_expired_delegation_blocks_before_account_or_candidate_work(self):
        policy = {
            "delegated_live_autonomy_enabled": True,
            "delegated_live_authorization_confirmed": True,
            "delegated_live_authorized_date": "2026-07-10",
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
        }
        with patch("app.stock_suite_app.OPS.autotrade_policy", return_value=policy), patch(
            "app.stock_suite_app._delegated_live_order_counts", return_value={"total": 0, "buy": 0, "sell": 0}
        ), patch("app.stock_suite_app.build_market_session_clock", return_value={"sessions": [{"id": "KR", "is_regular_open": True}]}), patch(
            "app.stock_suite_app._delegated_live_position_reviews"
        ) as position_review, patch("app.stock_suite_app.create_live_pilot_candidate") as create_candidate:
            result = stock_app._run_delegated_live_autonomy_unlocked(source="test")
        self.assertEqual(result["status"], "DAILY_AUTHORIZATION_EXPIRED")
        position_review.assert_not_called()
        create_candidate.assert_not_called()

    def test_delegated_autonomy_stops_after_dry_submit_for_user_confirmation(self):
        policy = {
            "delegated_live_autonomy_enabled": True,
            "delegated_live_authorization_confirmed": True,
            "delegated_live_authorized_date": stock_app.today_kst(),
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
            "delegated_live_max_buy_orders_per_day": 2,
            "delegated_live_max_sell_orders_per_day": 1,
            "delegated_live_auto_submit_max_cash_pct": 30.0,
            "live_pilot_max_cash_pct": 15.0,
            "live_pilot_dynamic_max_cash_pct": 15.0,
        }
        ticket = {"approval_token": "approval-1", "symbol": "005930", "quantity": 2}
        with (
            patch.object(stock_app.OPS, "autotrade_policy", return_value=policy),
            patch("app.stock_suite_app._delegated_live_order_counts", return_value={"total": 0, "buy": 0, "sell": 0}),
            patch("app.stock_suite_app.build_market_session_clock", return_value={"sessions": [{"id": "KR", "is_regular_open": True}]}),
            patch("app.stock_suite_app._delegated_live_position_reviews", return_value={"reviews": [], "message": ""}),
            patch("app.stock_suite_app.build_live_reconciliation_audit", return_value={"ok": True, "status": "ready", "summary": "ready"}),
            patch("app.stock_suite_app.create_live_pilot_candidate", return_value={"ok": True, "ticket": ticket}),
            patch.object(stock_app.OPS, "resolve_approval", return_value={"status": "approved"}),
            patch.object(stock_app.OPS, "live_dry_submit", return_value={"status": "LIVE_READY_NOT_SUBMITTED"}),
            patch.object(stock_app.OPS, "audit"),
            patch("app.stock_suite_app.submit_live_pilot_order") as submit,
        ):
            result = stock_app._run_delegated_live_autonomy_unlocked(source="test")

        self.assertTrue(result["ok"])
        self.assertEqual("FINAL_CONFIRMATION_REQUIRED", result["status"])
        self.assertTrue(result["final_confirmation"]["required"])
        self.assertEqual("005930", result["final_confirmation"]["symbol"])
        self.assertEqual(2, result["final_confirmation"]["quantity"])
        submit.assert_not_called()

    def test_always_on_research_defaults_on_and_allows_explicit_opt_out(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(_always_on_research_enabled())
        with patch.dict("os.environ", {"CODEXSTOCK_ALWAYS_ON_RESEARCH": "off"}, clear=True):
            self.assertFalse(_always_on_research_enabled())

    def test_staff_learning_audit_does_not_call_repetition_growth(self):
        row = {
            "contestant_id": "operator",
            "strategy_mode": "intraday_theme_leader",
            "fast_window": 5,
            "slow_window": 20,
            "selected_symbols": ["005930"],
            "selected_challenge_config": {
                "strategy_mode": "intraday_theme_leader",
                "stop_loss_pct": 2,
                "take_profit_pct": 4,
                "holding_limit_days": 2,
                "allocation_pct": 35,
                "max_positions": 2,
            },
        }
        records = [
            {"id": "AITOUR-1", "rankings": [row]},
            {"id": "AITOUR-2", "rankings": [dict(row)]},
        ]
        with patch("app.stock_suite_app._read_jsonl", return_value=records):
            result = ai_staff_learning_audit(limit=10)
        operator = next(item for item in result["staff"] if item["contestant_id"] == "operator")
        self.assertFalse(operator["growth_proven"])
        self.assertEqual(operator["growth_status"], "검증된 학습 없음")
        self.assertEqual(operator["run_count"], 2)
        self.assertEqual(operator["trusted_run_count"], 0)

    def _actions(self, **sell_overrides):
        sell = {
            "date": "2026-01-10",
            "entry_date": "2026-01-02",
            "symbol": "TEST",
            "name": "Test",
            "side": "SELL",
            "entry_price": 100.0,
            "price": 114.0,
            "quantity": 1,
            "pnl_pct": 14.0,
            "reason": "profit protection trailing -5.0%",
            "peak_market_price": 120.0,
            "exit_trigger_market_price": 114.0,
            "peak_drawdown_pct": -5.0,
            "trailing_trigger_pct": -3.0,
        }
        sell.update(sell_overrides)
        return [
            {
                "date": "2026-01-02",
                "symbol": "TEST",
                "name": "Test",
                "side": "BUY",
                "price": 100.0,
                "quantity": 1,
                "reason": "entry",
            },
            sell,
        ]

    def test_replay_queue_waits_while_stage2_backfill_is_running(self):
        self.assertTrue(HISTORICAL_REPLAY_DATA_BACKFILL_LOCK.acquire(blocking=False))
        try:
            focus = {
                "mode": "AFTER_HOURS_RESEARCH_FOCUS",
                "market_phase": "after_hours",
                "market_priority_active": False,
                "market_open": False,
            }
            with patch("app.stock_suite_app.build_operating_focus", return_value=focus):
                result = next_historical_replay_regeneration_candidate()
                duplicate = run_historical_replay_data_gap_backfill("HREGAP-test")
        finally:
            HISTORICAL_REPLAY_DATA_BACKFILL_LOCK.release()

        self.assertEqual("waiting_for_data_backfill", result["status"])
        self.assertEqual("data_backfill_busy", duplicate["status"])
        self.assertFalse(result["live_order_allowed"])

    def test_data_gap_backfill_defers_during_market_priority_focus(self):
        class _BackfillService:
            def run(self, request_id):
                raise AssertionError("backfill service must not run during market priority focus")

        focus = {
            "mode": "MARKET_PREPARATION_FOCUS",
            "market_phase": "premarket",
            "market_priority_active": True,
            "market_open": False,
        }

        with patch("app.stock_suite_app.build_operating_focus", return_value=focus):
            with patch("app.stock_suite_app.HISTORICAL_REPLAY_DATA_BACKFILL_SERVICE", _BackfillService()):
                result = run_historical_replay_data_gap_backfill("HREGAP-test")

        self.assertTrue(result["ok"])
        self.assertEqual("deferred_to_market_closed_window", result["status"])
        self.assertEqual("HREGAP-test", result["request_id"])
        self.assertEqual("MARKET_PREPARATION_FOCUS", result["current_focus_mode"])
        self.assertEqual("premarket", result["current_market_phase"])
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["unverified_result_affects_score"])
        self.assertIn("백필 보류", result["operator_message"])

    def test_trailing_evidence_is_verified(self):
        row = _closed_trade_journal_from_actions(self._actions())[0]
        audit = row["return_reconciliation"]

        self.assertEqual("OK", audit["status"])
        self.assertTrue(audit["reason_threshold_verifiable"])
        self.assertEqual("verified", audit["trailing_evidence_status"])
        self.assertFalse(audit["official_return_blocker"])

    def test_missing_peak_evidence_keeps_legacy_trade_under_review(self):
        missing = {
            "peak_market_price": None,
            "exit_trigger_market_price": None,
            "peak_drawdown_pct": None,
            "trailing_trigger_pct": None,
        }
        actions = self._actions(**missing)
        row = _closed_trade_journal_from_actions(actions)[0]
        result = build_backtest_return_reconciliation({"trades": actions})

        self.assertEqual("REASON_TRAILING_PEAK_UNVERIFIED", row["reconciliation_status"])
        self.assertEqual("warning", result["status"])
        self.assertFalse(result["official_return_claim_allowed"])

    def test_inconsistent_peak_drawdown_is_blocked(self):
        row = _closed_trade_journal_from_actions(self._actions(peak_drawdown_pct=-1.0))[0]
        audit = row["return_reconciliation"]

        self.assertEqual("TRAILING_EVIDENCE_MISMATCH", audit["status"])
        self.assertEqual("blocker", audit["severity"])
        self.assertTrue(audit["official_return_blocker"])

    def test_entry_return_threshold_uses_published_two_decimal_precision(self):
        actions = self._actions(
            price=103.7499,
            pnl_pct=3.75,
            reason="take profit +4.0%",
            peak_market_price=None,
            exit_trigger_market_price=None,
            peak_drawdown_pct=None,
            trailing_trigger_pct=None,
        )
        row = _closed_trade_journal_from_actions(actions)[0]
        result = build_backtest_return_reconciliation({"trades": actions})

        self.assertEqual(3.75, row["return_reconciliation"]["computed_return_pct"])
        self.assertEqual(-0.25, row["return_reconciliation"]["reason_threshold_diff_pct"])
        self.assertTrue(row["return_reconciliation"]["reason_threshold_met"])
        self.assertEqual("OK", row["reconciliation_status"])
        self.assertTrue(result["official_return_claim_allowed"])

    def test_delayed_exit_reason_uses_decision_return_while_pnl_uses_fill(self):
        actions = self._actions(
            price=102.0,
            pnl_pct=2.0,
            reason="take profit +4.0%",
            decision_return_pct=4.1,
            peak_market_price=None,
            exit_trigger_market_price=None,
            peak_drawdown_pct=None,
            trailing_trigger_pct=None,
        )
        row = _closed_trade_journal_from_actions(actions)[0]

        self.assertEqual(2.0, row["return_reconciliation"]["computed_return_pct"])
        self.assertEqual(4.1, row["return_reconciliation"]["decision_return_pct"])
        self.assertTrue(row["return_reconciliation"]["reason_threshold_met"])
        self.assertEqual("OK", row["reconciliation_status"])

    def test_official_reconciliation_blocks_same_bar_signal_execution(self):
        actions = self._actions()
        for action in actions:
            action.update(
                {
                    "decision_data_as_of": action["date"],
                    "execution_at": action["date"],
                    "signal_lag_bars": 0,
                    "decision_market_price": action.get("exit_trigger_market_price") or action["price"],
                    "execution_price_basis": "next_available_close",
                }
            )
        result = build_backtest_return_reconciliation(
            {
                "trades": actions,
                "execution_timing_model": {"lookahead_safe_required": True},
            }
        )

        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["official_return_claim_allowed"])
        blockers = result["closed_trade_sample"][0]["return_reconciliation"]["blockers"]
        self.assertTrue(any("lookahead_detected" in blocker for blocker in blockers))

    def _calendar_proven_actions(self):
        dates = ["2026-01-01", "2026-01-02", "2026-01-09", "2026-01-10"]
        actions = self._actions()
        actions[0].update(
            {
                "decision_data_as_of": dates[0],
                "execution_at": dates[1],
                "signal_lag_bars": 1,
                "decision_market_price": 99.0,
                "execution_price_basis": "next_available_close",
                **stock_app.build_calendar_adjacency_proof("TEST", dates, 1),
            }
        )
        actions[1].update(
            {
                "decision_data_as_of": dates[2],
                "execution_at": dates[3],
                "signal_lag_bars": 1,
                "decision_market_price": 115.0,
                "execution_price_basis": "next_available_close",
                **stock_app.build_calendar_adjacency_proof("TEST", dates, 3),
            }
        )
        return actions, stock_app.calendar_adjacency_root("TEST", dates)

    def test_official_reconciliation_verifies_each_trade_calendar_merkle_proof(self):
        actions, root = self._calendar_proven_actions()
        result = build_backtest_return_reconciliation(
            {
                "trades": actions,
                "execution_timing_model": {"lookahead_safe_required": True},
                "replay_data_bundle_evidence": {"symbol_calendar_adjacency_roots": {"TEST": root}},
            }
        )

        self.assertEqual("passed", result["status"])
        self.assertTrue(result["official_return_claim_allowed"])
        audit = result["closed_trade_sample"][0]["return_reconciliation"]
        self.assertTrue(audit["entry_timing"]["calendar_proof_ok"])
        self.assertTrue(audit["exit_timing"]["calendar_proof_ok"])

    def test_official_reconciliation_blocks_tampered_calendar_merkle_proof(self):
        actions, root = self._calendar_proven_actions()
        actions[1]["symbol_calendar_root"] = "0" * 64
        result = build_backtest_return_reconciliation(
            {
                "trades": actions,
                "execution_timing_model": {"lookahead_safe_required": True},
                "replay_data_bundle_evidence": {"symbol_calendar_adjacency_roots": {"TEST": root}},
            }
        )

        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["official_return_claim_allowed"])
        blockers = result["closed_trade_sample"][0]["return_reconciliation"]["blockers"]
        self.assertIn("lookahead_calendar_adjacency_proof_invalid", blockers)

    def test_open_positions_can_prove_mark_to_market_return_without_closed_trades(self):
        result = {
            "initial_cash": 1_100_000.0,
            "final_equity": 1_110_369.14,
            "total_return_pct": 0.94,
            "trades": [
                {
                    "side": "BUY",
                    "symbol": "005930",
                    "quantity": 10,
                    "cash_cost": 1_000_150.0,
                    "price": 100_015.0,
                    "date": "2026-01-02",
                }
            ],
            "open_positions": [
                {"symbol": "005930", "quantity": 10, "avg_cost": 100_015.0, "last_price": 101_300.0}
            ],
            "experience_log": [
                {"date": "2026-01-02", "cash": 99_850.0, "equity": 1_110_369.14, "positions": 1}
            ],
            "cost_model": {
                "commission_bps_each_side": 1.5,
                "slippage_bps_each_side": 5.0,
                "kr_sell_tax_bps": 18.0,
            },
            "price_currency_unit_audit": {
                "contracts": {"005930": {"market": "KR", "passed": True}}
            },
        }

        reconciliation = build_backtest_return_reconciliation(result)

        self.assertEqual("open_positions_mark_to_market_passed", reconciliation["status"])
        self.assertTrue(reconciliation["official_return_claim_allowed"])
        self.assertEqual(1, reconciliation["valuation_checked_count"])

    def test_open_position_mark_to_market_mismatch_remains_blocked(self):
        result = {
            "initial_cash": 1_000_000.0,
            "final_equity": 1_100_000.0,
            "total_return_pct": 10.0,
            "trades": [
                {
                    "side": "BUY",
                    "symbol": "005930",
                    "quantity": 5,
                    "cash_cost": 500_075.0,
                    "price": 100_015.0,
                    "date": "2026-01-02",
                }
            ],
            "open_positions": [
                {"symbol": "005930", "quantity": 4, "avg_cost": 100_015.0, "last_price": 101_000.0}
            ],
            "experience_log": [
                {"date": "2026-01-02", "cash": 499_925.0, "equity": 1_100_000.0, "positions": 1}
            ],
            "cost_model": {
                "commission_bps_each_side": 1.5,
                "slippage_bps_each_side": 5.0,
                "kr_sell_tax_bps": 18.0,
            },
            "price_currency_unit_audit": {
                "contracts": {"005930": {"market": "KR", "passed": True}}
            },
        }

        reconciliation = build_backtest_return_reconciliation(result)

        self.assertEqual("open_positions_mark_to_market_blocked", reconciliation["status"])
        self.assertFalse(reconciliation["official_return_claim_allowed"])
        self.assertIn("open_position_quantity_mismatch:005930", [row["reason"] for row in reconciliation["samples"]])

    def test_official_mid_period_listing_allows_post_listing_daily_history(self):
        rows = []
        cursor = date(2014, 11, 27)
        while cursor <= date(2015, 12, 31):
            if cursor.weekday() < 5:
                rows.append({"date": cursor.isoformat(), "close": 10_000.0, "adjusted_close": 10_000.0})
            cursor += timedelta(days=1)
        with (
            patch.dict(HISTORICAL_CLOSE_ROWS_CACHE, {}, clear=True),
            patch(
                "app.stock_suite_app._official_listing_evidence",
                return_value={"listing_date": "2014-11-27", "source": "official-test", "dataset_ids": ["test"]},
            ),
            patch(
                "app.stock_suite_app.INTEGRATIONS.kis_daily_chart",
                return_value={
                    "ok": True,
                    "source": "kis_daily_chart_range",
                    "provider": "KIS_adjusted_verified",
                    "rows": rows,
                    "range_complete": True,
                },
            ),
        ):
            result = _historical_close_rows("112610", "2010-01-01", "2015-12-31")

        self.assertEqual(len(rows), len(result["rows"]))
        self.assertTrue(result["listing_evidence"]["prelisting_gap_exempted"])
        self.assertEqual("2014-11-27", result["listing_evidence"]["effective_start_date"])

    def test_short_long_range_history_without_listing_evidence_is_rejected(self):
        rows = []
        cursor = date(2014, 11, 27)
        while cursor <= date(2015, 12, 31):
            if cursor.weekday() < 5:
                rows.append({"date": cursor.isoformat(), "close": 10_000.0})
            cursor += timedelta(days=1)
        with (
            patch.dict(HISTORICAL_CLOSE_ROWS_CACHE, {}, clear=True),
            patch("app.stock_suite_app._official_listing_evidence", return_value={}),
            patch(
                "app.stock_suite_app.INTEGRATIONS.kis_daily_chart",
                return_value={"ok": True, "message": "short", "rows": rows},
            ),
            patch("app.stock_suite_app._yahoo_symbol_candidates", return_value=[]),
            patch("app.stock_suite_app.TOSS_PUBLIC.chart", return_value={"ok": False, "message": "disabled"}),
        ):
            with self.assertRaises(ValueError):
                _historical_close_rows("999998", "2010-01-01", "2015-12-31")

    def test_unresolved_same_day_order_always_requests_fresh_broker_check(self):
        target_date = stock_app.today_kst()
        pending = [
            {
                "date": target_date,
                "symbol": "005930",
                "name": "Samsung Electronics",
                "side": "BUY",
                "side_label": "BUY",
                "created_at": f"{target_date}T10:05:00+09:00",
            }
        ]
        plan = stock_app._live_reconciliation_broker_refresh_plan(
            pending=pending,
            partial=[],
            broker_check_rows=[
                {
                    "date": target_date,
                    "created_at": f"{target_date}T09:30:00+09:00",
                    "executions": [],
                }
            ],
        )

        self.assertEqual([target_date], plan["refresh_required_dates"])
        self.assertEqual(target_date, plan["next_broker_check_requests"][0]["date"])
        self.assertTrue(plan["next_broker_check_requests"][0]["refresh_until_resolved"])
        self.assertTrue(plan["pending_groups"][0]["needs_broker_check"])

    def test_refresh_summary_counts_account_and_dual_path_blockers(self):
        before = {
            "next_broker_check_requests": [],
            "recent_live_submitted_count": 0,
        }
        after = {
            "ok": False,
            "status": "review_required",
            "summary": {},
            "blocker_summary": {
                "hard_block_count": 1,
                "review_required_count": 2,
            },
            "duplicate_broker_execution_event_count": 0,
            "historical_broker_without_local_submit_count": 0,
        }
        with patch(
            "app.stock_suite_app.build_live_reconciliation_audit",
            side_effect=[before, after],
        ):
            result = stock_app.run_live_reconciliation_refresh(
                refresh=False,
                persist=False,
                limit=120,
            )

        self.assertEqual(3, result["summary"]["blockers"])
        self.assertEqual(1, result["summary"]["hard_blockers"])
        self.assertEqual(2, result["summary"]["review_blockers"])
        self.assertFalse(result["live_order_allowed"])


class CommonQuoteSnapshotTests(unittest.TestCase):
    def test_mixed_age_kr_cache_is_refreshed_as_one_coherent_snapshot(self):
        calls = []

        def quote(symbol, *, prefer_live=True):
            calls.append((symbol, prefer_live))
            age = 0.0 if prefer_live or symbol == "005930" else 600.0
            return {
                "symbol": symbol,
                "name": symbol,
                "market": "KR",
                "currency": "KRW",
                "unit_scale": 1,
                "price": 100_000.0,
                "source": "kis_readonly" if prefer_live else "KIS_VERIFIED_CACHE",
                "verified_quote_age_seconds": age,
                "updated_at": "2026-01-02T10:00:00+09:00",
            }

        with patch("app.stock_suite_app.ops_quote", side_effect=quote):
            snapshot = build_common_quote_snapshot(symbols=["005930", "000660"])

        self.assertTrue(snapshot["ok"])
        self.assertEqual(2, snapshot["summary"]["counts"]["eligible_marks"])
        self.assertEqual(0, snapshot["summary"]["counts"]["temporal_blocked"])
        self.assertTrue(snapshot["temporal_audit"]["coherence_refresh_attempted"])
        self.assertEqual(["KR"], snapshot["temporal_audit"]["coherence_refresh_markets"])
        self.assertEqual(
            [("005930", False), ("000660", False), ("005930", True), ("000660", True)],
            calls,
        )

    def test_bounded_snapshot_keeps_temporal_block_without_live_refresh(self):
        calls = []

        def quote(symbol, *, prefer_live=True):
            calls.append((symbol, prefer_live))
            return {
                "symbol": symbol,
                "name": symbol,
                "market": "KR",
                "currency": "KRW",
                "unit_scale": 1,
                "price": 100_000.0,
                "source": "KIS_VERIFIED_CACHE",
                "verified_quote_age_seconds": 0.0 if symbol == "005930" else 600.0,
                "updated_at": "2026-01-02T10:00:00+09:00",
            }

        with patch("app.stock_suite_app.ops_quote", side_effect=quote):
            snapshot = build_common_quote_snapshot(
                symbols=["005930", "000660"],
                allow_coherence_live_refresh=False,
            )

        self.assertEqual([("005930", False), ("000660", False)], calls)
        self.assertFalse(snapshot["temporal_audit"]["coherence_refresh_attempted"])
        self.assertFalse(snapshot["temporal_audit"]["coherence_refresh_allowed"])
        self.assertGreater(snapshot["summary"]["counts"]["temporal_blocked"], 0)

    def test_native_us_market_cache_is_not_an_official_mark(self):
        with patch(
            "app.stock_suite_app.ops_quote",
            return_value={
                "symbol": "AAPL",
                "name": "Apple",
                "market": "US",
                "currency": "USD",
                "price": 188.43,
                "source": "MARKET_CACHE",
            },
        ):
            snapshot = build_common_quote_snapshot(symbols=["AAPL"])

        self.assertEqual("watch", snapshot["rows"][0]["unit_status"])
        self.assertFalse(snapshot["rows"][0]["official_mark_eligible"])
        self.assertEqual({}, snapshot["marks"])
        self.assertIn("simulated_fallback_quote", snapshot["rows"][0]["warnings"])

    def test_trusted_quote_without_explicit_unit_contract_is_blocked(self):
        with patch(
            "app.stock_suite_app.ops_quote",
            return_value={
                "symbol": "005930",
                "name": "Samsung Electronics",
                "market": "KR",
                "currency": "KRW",
                "price": 100_000,
                "source": "kis_readonly",
                "verified_quote_age_seconds": 0.0,
            },
        ):
            snapshot = build_common_quote_snapshot(symbols=["005930"], prefer_live=True)

        self.assertEqual("codexstock_common_quote_snapshot_v2", snapshot["schema"])
        self.assertFalse(snapshot["rows"][0]["official_mark_eligible"])
        self.assertEqual("blocked", snapshot["rows"][0]["snapshot_status"])
        self.assertIn("quote_unit_scale_missing", snapshot["rows"][0]["issues"])
        self.assertEqual({}, snapshot["marks"])

    def test_live_snapshot_blocks_stale_verified_cache(self):
        with patch(
            "app.stock_suite_app.ops_quote",
            return_value={
                "symbol": "005930",
                "name": "Samsung Electronics",
                "market": "KR",
                "currency": "KRW",
                "unit_scale": 1,
                "price": 100_000,
                "source": "KIS_VERIFIED_CACHE",
                "verified_quote_age_seconds": 120.0,
            },
        ):
            snapshot = build_common_quote_snapshot(symbols=["005930"], prefer_live=True)

        self.assertFalse(snapshot["rows"][0]["official_mark_eligible"])
        self.assertIn("official_quote_stale", snapshot["rows"][0]["issues"])
        self.assertEqual({}, snapshot["marks"])

    def test_plausible_unknown_source_is_watch_only_not_official(self):
        with patch(
            "app.stock_suite_app.ops_quote",
            return_value={
                "symbol": "005930",
                "name": "Samsung Electronics",
                "market": "KR",
                "currency": "KRW",
                "unit_scale": 1,
                "price": 100_000,
                "source": "local_cache",
                "verified_quote_age_seconds": 0.0,
            },
        ):
            snapshot = build_common_quote_snapshot(symbols=["005930"])

        self.assertEqual("watch", snapshot["rows"][0]["snapshot_status"])
        self.assertFalse(snapshot["rows"][0]["official_mark_eligible"])
        self.assertIn("untrusted_quote_source_not_eligible", snapshot["rows"][0]["warnings"])
        self.assertEqual({}, snapshot["marks"])

    def test_official_quote_with_inconsistent_price_fields_is_blocked(self):
        with patch(
            "app.stock_suite_app.ops_quote",
            return_value={
                "symbol": "005930",
                "name": "Samsung Electronics",
                "market": "KR",
                "currency": "KRW",
                "unit_scale": 1,
                "price": 1_000_000,
                "previous_close": 100_000,
                "high": 101_000,
                "low": 99_000,
                "change_pct": 0.0,
                "upper_limit_price": 130_000,
                "lower_limit_price": 70_000,
                "source": "kis_readonly",
                "verified_quote_age_seconds": 0.0,
            },
        ):
            snapshot = build_common_quote_snapshot(symbols=["005930"], prefer_live=True)

        row = snapshot["rows"][0]
        self.assertFalse(row["official_mark_eligible"])
        self.assertIn("quote_price_outside_daily_range", row["issues"])
        self.assertIn("quote_above_upper_limit", row["issues"])
        self.assertIn("quote_change_pct_inconsistent", row["issues"])

    def test_trusted_kis_price_above_static_reference_is_not_rescaled(self):
        guard = stock_app.quote_unit_guard(
            "000660",
            1_842_000,
            "KR",
            "KRW",
            "kis_readonly",
        )

        self.assertEqual("ok", guard["status"])
        self.assertEqual(1_842_000, guard["price"])
        self.assertTrue(
            any(str(item).startswith("trusted_official_static_reference_outdated:") for item in guard["observations"])
        )
        self.assertFalse(any("possible_scaled_price_candidate" in str(item) for item in guard["observations"]))


class PositionUnitAuditTests(unittest.TestCase):
    def test_fractional_krw_average_cost_is_not_treated_as_an_order_price(self):
        result = stock_app._position_unit_audit_row(
            {
                "symbol": "083450",
                "name": "GST",
                "quantity": 87,
                "avg_price": 46_700.5747,
                "value": 4_062_950,
                "currency": "KRW",
            },
            {
                "symbol": "083450",
                "market": "KR",
                "currency": "KRW",
                "unit_status": "ok",
                "official_mark_eligible": False,
                "unit_guard": {"safety_block": False},
            },
            0.0,
            source="paper",
            account_equity=100_000_000,
        )

        self.assertNotEqual(result["status"], "blocked")
        self.assertFalse(any("fractional_krw_price" in issue for issue in result["issues"]))
        self.assertTrue(
            any("fractional_krw_cost_basis_allowed" in item for item in result["valuation_unit_observations"])
        )

    def test_fractional_krw_official_quote_remains_blocked(self):
        guard = stock_app.quote_unit_guard("083450", 46_700.5747, "KR", "KRW", "cache")

        self.assertTrue(guard["safety_block"])
        self.assertTrue(any("fractional_krw_price" in issue for issue in guard["issues"]))

    def test_bounded_health_probe_never_attempts_live_quote_fallback(self):
        paper = {
            "equity": 1_000_000,
            "positions": [
                {
                    "symbol": "005930",
                    "quantity": 1,
                    "avg_price": 70_000,
                    "currency": "KRW",
                }
            ],
        }
        blocked_snapshot = {
            "schema": "codexstock_common_quote_snapshot_v1",
            "snapshot_hash": "cached-blocked",
            "rows": [
                {
                    "symbol": "005930",
                    "market": "KR",
                    "currency": "KRW",
                    "unit_status": "blocked",
                    "temporal_status": "blocked",
                    "official_mark_eligible": False,
                }
            ],
            "marks": {},
            "summary": {
                "status": "blocked",
                "counts": {
                    "ok": 0,
                    "watch": 0,
                    "blocked": 1,
                    "temporal_blocked": 1,
                    "eligible_marks": 0,
                },
                "checked": 1,
            },
        }
        with patch(
            "app.stock_suite_app.build_common_quote_snapshot",
            return_value=blocked_snapshot,
        ) as snapshot_builder:
            result = build_position_unit_audit(
                paper=paper,
                include_live=False,
                prefer_live_quotes=False,
                allow_live_quote_fallback=False,
                source="test-bounded-health-probe",
            )

        snapshot_builder.assert_called_once()
        self.assertFalse(result["quote_snapshot"]["fallback_allowed"])
        self.assertTrue(result["quote_snapshot"]["fallback_skipped"])
        self.assertFalse(result["quote_snapshot"]["fallback_applied"])


class SqliteStorageAuditTests(unittest.TestCase):
    def test_query_benchmark_uses_median_and_preserves_transient_peak(self):
        con = sqlite3.connect(":memory:")
        try:
            con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            with patch(
                "app.stock_suite_app.time.perf_counter",
                side_effect=[0.0, 0.6, 1.0, 1.001, 2.0, 2.001],
            ):
                result = stock_app._benchmark_sqlite_read_query(
                    con,
                    "SELECT id FROM sample",
                )
        finally:
            con.close()

        self.assertEqual(3, result["sample_count"])
        self.assertEqual(1.0, result["median_ms"])
        self.assertEqual(600.0, result["max_ms"])
        self.assertTrue(result["transient_spike"])

    def test_query_benchmark_keeps_persistent_latency_above_slow_threshold(self):
        con = sqlite3.connect(":memory:")
        try:
            con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            with patch(
                "app.stock_suite_app.time.perf_counter",
                side_effect=[0.0, 0.3, 1.0, 1.3, 2.0, 2.3],
            ):
                result = stock_app._benchmark_sqlite_read_query(
                    con,
                    "SELECT id FROM sample",
                )
        finally:
            con.close()

        self.assertGreaterEqual(
            result["median_ms"],
            stock_app.SQLITE_STORAGE_QUERY_SLOW_MS,
        )
        self.assertFalse(result["transient_spike"])

    def test_database_audit_budget_starts_after_discovery_budget(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "events.sqlite3"
            con = sqlite3.connect(db_path)
            try:
                con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
                con.commit()
            finally:
                con.close()
            clock = {"value": 0.0}

            def fake_monotonic():
                current = clock["value"]
                clock["value"] += 0.001
                return current

            def finish_discovery(*_args, **_kwargs):
                clock["value"] = 10.0
                return [db_path], {
                    "complete": True,
                    "truncated_reason": None,
                    "elapsed_ms": 10000.0,
                    "directories_scanned": 1,
                    "excluded_directory_count": 0,
                    "scope": "active_runtime_databases",
                    "files_seen": 1,
                    "discovered_database_count": 1,
                    "database_limit": stock_app.SQLITE_STORAGE_BOUNDED_MAX_DATABASES,
                    "time_budget_seconds": stock_app.SQLITE_STORAGE_BOUNDED_DISCOVERY_SECONDS,
                }

            with (
                patch("app.stock_suite_app.USER_DATA_ROOT", root),
                patch("app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE_FILE", root / "audit-cache.json"),
                patch(
                    "app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE",
                    {"saved_at": 0.0, "scope": "", "payload": {}},
                ),
                patch(
                    "app.stock_suite_app._discover_sqlite_storage_paths",
                    side_effect=finish_discovery,
                ),
                patch(
                    "app.stock_suite_app._fast_sqlite_storage_snapshot",
                    return_value={},
                ),
                patch(
                    "app.stock_suite_app.time.monotonic",
                    side_effect=fake_monotonic,
                ),
            ):
                result = _sqlite_storage_feature_probe(
                    full_integrity=False,
                    force=True,
                )

        self.assertEqual(1, result["opened_database_count"])
        self.assertEqual(0, result["deferred_database_count"])
        self.assertTrue(result["bounded_audit_complete"])

    def test_bounded_probe_defers_full_duplicate_and_row_count_scans(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "events.sqlite3"
            con = sqlite3.connect(db_path)
            try:
                con.execute("PRAGMA journal_mode=WAL")
                con.execute(
                    "CREATE TABLE jsonl_events ("
                    "id INTEGER PRIMARY KEY, source_name TEXT, payload_hash TEXT, "
                    "event_date TEXT, symbol TEXT, status TEXT)"
                )
                con.execute(
                    "CREATE UNIQUE INDEX uq_jsonl_events_source_payload_hash "
                    "ON jsonl_events(source_name, payload_hash) "
                    "WHERE payload_hash IS NOT NULL AND payload_hash <> ''"
                )
                con.executemany(
                    "INSERT INTO jsonl_events(source_name, payload_hash, event_date, symbol, status) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [
                        ("a.jsonl", "hash-1", "2026-01-01", "A", "ok"),
                        ("a.jsonl", "hash-2", "2026-01-02", "B", "ok"),
                    ],
                )
                con.commit()
            finally:
                con.close()
            with (
                patch("app.stock_suite_app.USER_DATA_ROOT", root),
                patch("app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE_FILE", root / "audit-cache.json"),
                patch(
                    "app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE",
                    {"saved_at": 0.0, "scope": "", "payload": {}},
                ),
            ):
                bounded = _sqlite_storage_feature_probe(full_integrity=False, force=True)
                full = _sqlite_storage_feature_probe(full_integrity=True)

        bounded_db = bounded["databases"][0]
        full_db = full["databases"][0]
        self.assertIsNone(bounded_db["duplicate_payload_rows"])
        self.assertEqual("deferred_to_full_audit", bounded_db["duplicate_payload_check_mode"])
        self.assertEqual({}, bounded_db["table_row_counts"])
        self.assertTrue(bounded_db["storage_concurrency_safe"])
        self.assertFalse(bounded_db["busy_timeout_affects_storage_health"])
        self.assertEqual(0, full_db["duplicate_payload_rows"])
        self.assertEqual(2, full_db["table_row_counts"]["jsonl_events"])
        self.assertEqual("ok", full_db["quick_check"])

    def test_cold_probe_returns_metadata_while_background_audit_starts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sqlite3.connect(root / "events.sqlite3").close()
            with (
                patch("app.stock_suite_app.USER_DATA_ROOT", root),
                patch("app.stock_suite_app.load_probe_cache", side_effect=[None, None]),
                patch(
                    "app.stock_suite_app._start_sqlite_storage_audit_refresh",
                    return_value=True,
                ) as refresh,
            ):
                result = _sqlite_storage_feature_probe(full_integrity=False)

        refresh.assert_called_once_with()
        self.assertEqual("background_audit_pending", result["status"])
        self.assertEqual(1, result["sqlite_file_count"])
        self.assertTrue(result["refreshing"])
        self.assertEqual(
            "initial_inventory_then_background_bounded_audit",
            result["health_probe_mode"],
        )

    def test_forced_refresh_response_never_runs_database_probe_inline(self):
        cached = {"ok": True, "status": "ready", "summary": {"status": "ready"}}
        with (
            patch(
                "app.stock_suite_app._start_sqlite_storage_audit_refresh",
                return_value=True,
            ),
            patch(
                "app.stock_suite_app._fast_sqlite_storage_snapshot",
                return_value=cached,
            ),
            patch(
                "app.stock_suite_app._sqlite_storage_feature_probe",
                side_effect=AssertionError("HTTP refresh must not run a database audit inline"),
            ),
        ):
            result = stock_app._sqlite_storage_refresh_response()

        self.assertTrue(result["ok"])
        self.assertTrue(result["refreshing"])
        self.assertEqual("cached_while_bounded_audit_refreshes", result["health_probe_mode"])

    def test_vacuum_recommendation_is_maintenance_not_storage_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "maintenance.sqlite3"
            con = sqlite3.connect(db_path)
            try:
                con.execute("CREATE TABLE payloads (id INTEGER PRIMARY KEY, body BLOB)")
                con.execute("INSERT INTO payloads(body) VALUES (zeroblob(12582912))")
                con.commit()
                con.execute("DELETE FROM payloads")
                con.commit()
            finally:
                con.close()
            with (
                patch("app.stock_suite_app.USER_DATA_ROOT", root),
                patch("app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE_FILE", root / "audit-cache.json"),
                patch(
                    "app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE",
                    {"saved_at": 0.0, "scope": "", "payload": {}},
                ),
            ):
                result = _sqlite_storage_feature_probe(full_integrity=False, force=True)

        self.assertTrue(result["ok"])
        self.assertEqual("ready_large_healthy", result["status"])
        self.assertEqual(0, result["problem_sqlite_count"])
        self.assertEqual(1, result["maintenance_advisory_count"])

    def test_bounded_discovery_skips_cold_archives_but_keeps_active_databases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            active_dir = root / "ops" / "execution_sidecar"
            archive_dir = root / "backups" / "old-runtime"
            active_dir.mkdir(parents=True)
            archive_dir.mkdir(parents=True)
            active_db = active_dir / "ledger.sqlite3"
            archived_db = archive_dir / "ledger.sqlite3"
            active_db.touch()
            archived_db.touch()

            paths, discovery = stock_app._discover_sqlite_storage_paths(
                root,
                full_integrity=False,
            )

        self.assertEqual([active_db], paths)
        self.assertTrue(discovery["complete"])
        self.assertEqual("active_runtime_databases", discovery["scope"])
        self.assertGreaterEqual(discovery["excluded_directory_count"], 1)

    def test_bounded_audit_reuses_unchanged_verified_database_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ("first.sqlite3", "second.sqlite3"):
                con = sqlite3.connect(root / name)
                con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
                con.commit()
                con.close()
            cache_file = root / "audit-cache.json"
            with (
                patch("app.stock_suite_app.USER_DATA_ROOT", root),
                patch("app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE_FILE", cache_file),
                patch(
                    "app.stock_suite_app.SQLITE_STORAGE_AUDIT_CACHE",
                    {"saved_at": 0.0, "scope": "", "payload": {}},
                ),
            ):
                first = _sqlite_storage_feature_probe(full_integrity=False, force=True)
                persisted = stock_app._fast_sqlite_storage_snapshot(
                    max_age_seconds=7 * 24 * 60 * 60
                )
                self.assertEqual(2, len(persisted["database_catalog"]))
                with (
                    patch(
                        "app.stock_suite_app._fast_sqlite_storage_snapshot",
                        return_value=persisted,
                    ),
                    patch(
                        "app.stock_suite_app.sqlite3.connect",
                        side_effect=AssertionError(
                            "unchanged verified databases must be reused"
                        ),
                    ),
                ):
                    second = _sqlite_storage_feature_probe(
                        full_integrity=False,
                        force=True,
                    )

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(2, second["reused_database_count"])
        self.assertEqual(0, second["opened_database_count"])
        self.assertTrue(second["bounded_audit_complete"])
        self.assertTrue(all(row["audit_reused"] for row in second["database_catalog"]))

    def test_bounded_discovery_reports_database_limit_instead_of_hiding_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for index in range(stock_app.SQLITE_STORAGE_BOUNDED_MAX_DATABASES + 2):
                (root / f"db-{index:03d}.sqlite3").touch()

            paths, discovery = stock_app._discover_sqlite_storage_paths(
                root,
                full_integrity=False,
            )

        self.assertEqual(stock_app.SQLITE_STORAGE_BOUNDED_MAX_DATABASES, len(paths))
        self.assertFalse(discovery["complete"])
        self.assertEqual("database_count_budget_exceeded", discovery["truncated_reason"])


class FeatureHealthClassificationTests(unittest.TestCase):
    def test_stage2_health_audit_reuses_durable_cache_after_restart(self):
        payload = {"ok": True, "stage2_handoff": {"ready_count": 0}}
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "stage2-health.json"
            stock_app.TOURNAMENT_RECONCILIATION_HEALTH_CACHES.clear()
            with (
                patch("app.stock_suite_app._runtime_file", return_value=cache_path),
                patch(
                    "app.stock_suite_app.ai_tournament_reconciliation_audit",
                    return_value=payload,
                ) as builder,
            ):
                first = stock_app._cached_tournament_reconciliation_health_audit()
            self.assertEqual(1, builder.call_count)
            self.assertEqual(0, first["stage2_handoff"]["ready_count"])

            stock_app.TOURNAMENT_RECONCILIATION_HEALTH_CACHES.clear()
            with (
                patch("app.stock_suite_app._runtime_file", return_value=cache_path),
                patch(
                    "app.stock_suite_app.ai_tournament_reconciliation_audit",
                    side_effect=AssertionError("durable cache should avoid a cold rebuild"),
                ),
            ):
                second = stock_app._cached_tournament_reconciliation_health_audit()

        stock_app.TOURNAMENT_RECONCILIATION_HEALTH_CACHES.clear()
        self.assertTrue(second["cached"])
        self.assertEqual("stale_while_refresh", second["cache_source"])

    def test_probe_surfaces_nested_watch_status_as_attention(self):
        result = stock_app._feature_health_probe(
            "unit_watch",
            "Unit watch",
            "data",
            "/api/unit-watch",
            lambda: {"ok": True, "summary": {"status": "watch"}},
            degraded_statuses={"watch", "blocked", "review_required"},
        )

        self.assertEqual("degraded", result["status"])

    def test_domain_attention_is_not_misclassified_as_feature_failure(self):
        result = stock_app._feature_health_probe(
            "sector_concentration",
            "Sector concentration",
            "risk",
            "/api/agent/sector-concentration",
            lambda: {
                "ok": False,
                "status": "review_required",
                "summary": {"status": "review_required"},
                "domain_attention": True,
                "domain_attention_label": "업종 편중 검토 필요",
                "domain_attention_reason": "반도체 후보 비중 80%",
            },
            "Cap crowded sectors before promotion.",
            degraded_statuses={"no_cache"},
            domain_attention_statuses={"review_required"},
        )

        self.assertEqual("alive", result["status"])
        self.assertTrue(result["metadata"]["domain_attention"])
        self.assertEqual("review_required", result["metadata"]["domain_status"])
        self.assertEqual("Cap crowded sectors before promotion.", result["action"])
        self.assertEqual("normal", stock_app._feature_health_operational_state(result)[0])

    def test_probe_preserves_mcp_exposure_reconciliation_metadata(self):
        client_exposure = {
            "status": "MISMATCH",
            "core_exposure_status": "CORE_MATCHED",
        }
        reconciliation = {
            "full_surface_status": "MISMATCH",
            "core_surface_status": "CORE_MATCHED",
            "next_action": "REFRESH_CONNECTOR_SCHEMA_AND_RESUBMIT_RECEIPT",
        }
        result = stock_app._feature_health_probe(
            "mcp_manifest",
            "MCP manifest/tools",
            "mcp",
            "mcp://codexstock_mcp_manifest",
            lambda: {
                "ok": True,
                "status": "ready",
                "client_exposure": client_exposure,
                "exposure_reconciliation": reconciliation,
            },
        )

        self.assertEqual(client_exposure, result["metadata"]["client_exposure"])
        self.assertEqual(reconciliation, result["metadata"]["exposure_reconciliation"])

    def test_autopilot_health_excludes_expired_pending_approvals(self):
        expired = {
            "status": "pending",
            "created_at": "2026-07-15T10:00:00+09:00",
            "expires_at": "2026-07-15T13:00:00+09:00",
        }
        with (
            patch.object(
                stock_app.AUTOPILOT_SCHEDULER,
                "status",
                return_value={
                    "running": True,
                    "thread_alive": True,
                    "interval_override_seconds": 300,
                    "last_error": "",
                },
            ),
            patch("app.stock_suite_app.autopilot_runs", return_value=[]),
            patch.object(
                stock_app.OPS,
                "status",
                return_value={"telegram_outbox": {"pending_dispatch": 0}},
            ),
            patch.object(stock_app.OPS, "approvals", return_value=[expired, expired, expired]),
            patch.object(
                stock_app.TELEGRAM_POLLER,
                "status",
                return_value={"running": True, "thread_alive": True, "ready": True},
            ),
            patch.object(
                stock_app.TELEGRAM_DISPATCHER,
                "status",
                return_value={
                    "running": True,
                    "thread_alive": True,
                    "auto_dispatch": True,
                    "telegram_ready": True,
                    "eligible_recent": 0,
                },
            ),
            patch.object(stock_app.MEMORY, "summary", return_value={"cycle_count": 1}),
            patch("app.stock_suite_app.load_user_watchlist", return_value={"symbols": ["005930"]}),
            patch(
                "app.stock_suite_app.live_quote",
                return_value={
                    "ok": True,
                    "symbol": "005930",
                    "source": "kis_readonly",
                    "price": 255000,
                    "message": "정상",
                },
            ),
        ):
            result = stock_app.build_autopilot_health(compact=True)

        approval_check = next(row for row in result["checks"] if row["id"] == "approval_queue")
        self.assertEqual(0, result["summary"]["pending_approvals"])
        self.assertEqual("ok", approval_check["status"])

    def test_fresh_external_report_requires_integrity_and_exposes_snapshot_counts(self):
        inbox = {
            "ready": True,
            "current_source_usable": True,
            "summary": {"pending_validation_count": 8},
            "source_integrity": {
                "usable": True,
                "status": "USABLE",
                "manifest_binding": {
                    "hash_binding_mode": "receiver_computed_legacy_manifest",
                    "blockers": [],
                },
            },
            "verification_queue": {
                "current_report_pending_count": 8,
                "snapshot_verified_count": 8,
                "snapshot_blocked_count": 0,
                "stage2_passed_count": 0,
                "unverified_score_influence_count": 0,
                "unverified_order_influence_count": 0,
            },
            "file_poller": {
                "running": True,
                "status": "WATCHING",
                "source_age_minutes": 10,
                "last_error": "",
            },
            "report_freshness": {
                "fresh": True,
                "age_minutes": 10,
                "max_age_minutes": 180,
                "session": "intraday",
            },
        }
        with patch("app.stock_suite_app.external_signal_inbox_status", return_value=inbox):
            result = _external_signal_freshness_feature_probe()

        self.assertTrue(result["ok"])
        self.assertEqual("ready", result["status"])
        self.assertEqual(8, result["summary"]["snapshot_verified_count"])
        self.assertEqual(0, result["summary"]["unverified_order_influence_count"])
        self.assertEqual("receiver_computed_legacy_manifest", result["external_signal_manifest_binding_mode"])
        self.assertEqual(0, result["external_signal_manifest_binding_blocker_count"])

    def test_stale_external_report_is_visible_and_quarantined(self):
        inbox = {
            "ready": True,
            "summary": {"pending_validation_count": 7},
            "file_poller": {
                "running": True,
                "status": "SOURCE_STALE",
                "source_age_minutes": 1085,
                "last_error": "external_report_stale",
            },
        }
        with patch("app.stock_suite_app.external_signal_inbox_status", return_value=inbox):
            result = _external_signal_freshness_feature_probe()

        self.assertFalse(result["ok"])
        self.assertEqual("source_stale", result["status"])
        self.assertFalse(result["live_order_allowed"])

    def test_quarantined_legacy_warning_is_alive_but_visible(self):
        audit = {
            "ok": True,
            "status": "review_required",
            "regeneration_candidate_count": 756,
            "summary": {
                "status": "review_required",
                "missing_summary_rows": 0,
                "blocker_rows": 0,
                "official_return_blocker_trade_count": 0,
                "warning_rows": 3,
                "official_return_claim_allowed": False,
            },
        }
        with (
            patch(
                "app.stock_suite_app.responsive_historical_replay_regeneration_status",
                return_value={
                    "progress": {
                        "total_candidate_count": 0,
                        "verified_count": 0,
                        "remaining_candidate_count": 0,
                    }
                },
            ),
            patch(
                "app.stock_suite_app._cached_verified_historical_replay_completion_certificate",
                return_value={"ok": False, "completion_verified": False},
            ),
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit) as mocked_audit,
            patch(
                "app.stock_suite_app._historical_replay_campaign_manifest_scope",
                return_value=(757, {"HREPLAY-1"}),
            ),
            patch(
                "app.stock_suite_app._read_jsonl",
                return_value=[
                    {
                        "source_replay_id": "HREPLAY-1",
                        "status": "verified_replacement_candidate",
                        "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                        "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                        "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                    }
                ],
            ),
        ):
            result = _tournament_reconciliation_health_probe()

        mocked_audit.assert_called_once_with(limit=300)
        self.assertEqual("ready_with_historical_quarantine", result["status"])
        self.assertEqual("warning", result["severity"])
        self.assertEqual("review_required", result["summary"]["audit_status"])
        self.assertEqual("1/757 (0.13%)", result["regeneration_progress"]["label"])
        self.assertEqual(756, result["regeneration_audit_candidate_count"])
        self.assertEqual(757, result["regeneration_campaign_target_count"])
        self.assertEqual("frozen_campaign_manifest", result["regeneration_progress_denominator_source"])
        detail = stock_app._feature_probe_detail(result)
        self.assertIn("regeneration_audit_candidate_count=756", detail)
        self.assertIn("regeneration_campaign_target_count=757", detail)
        self.assertIn("regeneration_progress_denominator_source=frozen_campaign_manifest", detail)

    def test_blocker_keeps_tournament_health_degraded(self):
        audit = {
            "ok": True,
            "status": "review_required",
            "regeneration_candidate_count": 756,
            "summary": {
                "status": "review_required",
                "missing_summary_rows": 0,
                "blocker_rows": 1,
                "official_return_blocker_trade_count": 1,
                "warning_rows": 0,
                "official_return_claim_allowed": False,
            },
        }
        with (
            patch(
                "app.stock_suite_app.responsive_historical_replay_regeneration_status",
                return_value={
                    "progress": {
                        "total_candidate_count": 0,
                        "verified_count": 0,
                        "remaining_candidate_count": 0,
                    }
                },
            ),
            patch(
                "app.stock_suite_app._cached_verified_historical_replay_completion_certificate",
                return_value={"ok": False, "completion_verified": False},
            ),
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit) as mocked_audit,
            patch(
                "app.stock_suite_app._historical_replay_campaign_manifest_scope",
                return_value=(0, set()),
            ),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
        ):
            result = _tournament_reconciliation_health_probe()

        mocked_audit.assert_called_once_with(limit=300)
        self.assertEqual("review_required", result["status"])
        self.assertNotIn("severity", result)

    def test_signed_replacement_certificate_makes_reconciliation_health_ready(self):
        progress = {
            "total_candidate_count": 757,
            "verified_count": 757,
            "remaining_candidate_count": 0,
            "label": "757/757 (100.0%)",
        }
        certificate = {
            "ok": True,
            "completion_verified": True,
            "resolved_count": 757,
            "certificate_id": "CERT-757",
            "certificate_sha256": "abc123",
            "issued_at": "2026-07-17T06:00:00+09:00",
        }
        with (
            patch(
                "app.stock_suite_app.responsive_historical_replay_regeneration_status",
                return_value={"progress": progress},
            ),
            patch(
                "app.stock_suite_app._cached_verified_historical_replay_completion_certificate",
                return_value=certificate,
            ),
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit") as deep_audit,
        ):
            result = _tournament_reconciliation_health_probe()

        deep_audit.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertEqual("ready_certified_replacement_scope", result["status"])
        self.assertEqual("certified_757_replacement_replays_only", result["official_performance_scope"])
        self.assertFalse(result["legacy_official_return_claim_allowed"])


class HistoricalReplayRegenerationContractTests(unittest.TestCase):
    def test_sqlite_storage_probe_serves_stale_cache_while_refreshing(self):
        stale = {"ok": True, "status": "ready", "summary": {"status": "ready"}}
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("app.stock_suite_app.USER_DATA_ROOT", Path(temp_dir)),
                patch("app.stock_suite_app.load_probe_cache", side_effect=[None, stale]),
                patch("app.stock_suite_app._start_sqlite_storage_audit_refresh", return_value=True) as refresh,
            ):
                result = stock_app._sqlite_storage_feature_probe()

        refresh.assert_called_once_with()
        self.assertTrue(result["ok"])
        self.assertTrue(result["stale"])
        self.assertTrue(result["refreshing"])
        self.assertEqual("stale_while_revalidate", result["health_probe_mode"])

    def test_runtime_retention_probe_serves_stale_cache_while_refreshing(self):
        stale = {"ok": True, "status": "ready", "summary": {"status": "ready"}}
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("app.stock_suite_app.USER_DATA_ROOT", Path(temp_dir) / "data"),
                patch("app.stock_suite_app.load_probe_cache", side_effect=[None, stale]),
                patch("app.stock_suite_app._start_runtime_storage_retention_refresh", return_value=True) as refresh,
            ):
                result = stock_app._runtime_storage_retention_feature_probe()

        refresh.assert_called_once_with()
        self.assertTrue(result["ok"])
        self.assertTrue(result["stale"])
        self.assertTrue(result["refreshing"])
        self.assertEqual("stale_while_revalidate", result["health_probe_mode"])

    def test_data_gap_queue_uses_current_manifest_without_rescanning_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger_path = root / "regenerations.jsonl"
            queue_path = root / "data-gap-queue.json"
            ledger_path.write_text('{"id":"HREGEN-1"}\n', encoding="utf-8")
            queue_path.write_text(
                json.dumps({"ok": True, "status": "empty", "request_count": 0, "requests": []}),
                encoding="utf-8",
            )
            queue_path.touch()
            with (
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE", ledger_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_DATA_GAP_QUEUE_FILE", queue_path),
                patch("app.stock_suite_app._read_jsonl") as ledger_reader,
            ):
                result = stock_app.historical_replay_data_gap_queue(record=False)

        ledger_reader.assert_not_called()
        self.assertTrue(result["cached"])
        self.assertEqual("manifest_newer_than_regeneration_ledger", result["cache_validation"])

    def test_data_gap_storage_audit_reuses_signature_bound_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result_dir = root / "results"
            result_dir.mkdir()
            index_path = root / "index.sqlite3"
            cache_path = root / "audit-cache.json"
            memory_cache = {"saved_at": 0.0, "scope": "", "payload": {}}
            with (
                patch("app.stock_suite_app.HISTORICAL_REPLAY_DATA_GAP_RESULT_DIR", result_dir),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_DATA_GAP_INDEX_FILE", index_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_DATA_GAP_STORAGE_CACHE_FILE", cache_path),
                patch("app.stock_suite_app.TOURNAMENT_DATA_GAP_STORAGE_CACHE", memory_cache),
                patch(
                    "app.stock_suite_app._audit_replay_data_backfill_storage",
                    return_value={"ok": True, "status": "healthy"},
                ) as audit,
            ):
                first = stock_app._tournament_data_gap_storage_health_probe()
                second = stock_app._tournament_data_gap_storage_health_probe()

        audit.assert_called_once_with(result_dir=result_dir, index_path=index_path)
        self.assertTrue(first["ok"])
        self.assertTrue(second["cached"])

    def test_symbol_lookup_uses_local_universe_cache_without_network_refresh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "universe.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "source": "test",
                        "rows": [{"symbol": "000660", "name": "SK hynix", "market": "KR"}],
                    }
                ),
                encoding="utf-8",
            )
            old_cache = dict(stock_app.SYMBOL_LOOKUP_CACHE)
            old_mtime = stock_app.SYMBOL_LOOKUP_CACHE_MTIME
            try:
                stock_app.SYMBOL_LOOKUP_CACHE.clear()
                stock_app.SYMBOL_LOOKUP_CACHE_MTIME = -1.0
                with (
                    patch.object(stock_app, "UNIVERSE_CACHE", cache_path),
                    patch("app.stock_suite_app.load_universe") as network_refresh,
                ):
                    result = stock_app._lookup_symbols(["000660", "UNKNOWN"])
            finally:
                stock_app.SYMBOL_LOOKUP_CACHE.clear()
                stock_app.SYMBOL_LOOKUP_CACHE.update(old_cache)
                stock_app.SYMBOL_LOOKUP_CACHE_MTIME = old_mtime

        network_refresh.assert_not_called()
        self.assertEqual("SK hynix", result[0]["name"])
        self.assertEqual("UNKNOWN", result[1]["name"])

    def test_position_unit_health_probe_never_waits_for_live_quote_fallback(self):
        expected = {
            "ok": True,
            "summary": {"status": "ok", "active_position_blocker_count": 0},
            "blocked": [],
            "watch": [],
        }
        with (
            patch("app.stock_suite_app._quote_health_probe_bundle") as quote_bundle,
            patch("app.stock_suite_app.build_position_unit_audit", return_value=expected) as audit,
        ):
            result = stock_app._position_unit_health_probe()

        quote_bundle.assert_not_called()
        audit.assert_called_once_with(
            include_live=False,
            prefer_live_quotes=False,
            allow_live_quote_fallback=False,
            source="feature-health-position-unit-audit",
        )
        self.assertTrue(result["ok"])
        self.assertEqual("ready_with_safe_quarantine", result["status"])
        self.assertEqual("ok", result["raw_summary"]["status"])

    def test_agent_radar_explicit_symbols_bypass_default_cache(self):
        cached_default = {
            "payload": {
                "generated_at": "2026-07-15T09:00:00",
                "cached": False,
                "symbols": ["005930"],
                "news": [],
                "financials": [],
                "watch_tasks": [],
            }
        }
        requested_rows = [{"symbol": "000660", "name": "SK하이닉스"}]
        with (
            patch("app.stock_suite_app._agent_cache_load", return_value=cached_default) as cache_load,
            patch("app.stock_suite_app._agent_cache_save") as cache_save,
            patch("app.stock_suite_app.MEMORY.summary", return_value={"top_candidates": []}),
            patch("app.stock_suite_app._lookup_symbols", return_value=requested_rows) as lookup,
            patch("app.stock_suite_app.build_news_radar", return_value=[]),
            patch("app.stock_suite_app.build_financial_radar", return_value=[]),
            patch("app.stock_suite_app.build_toss_public_market_radar", return_value={"items": []}),
        ):
            result = stock_app.build_agent_radar(symbols=["000660"], force=False)

        cache_load.assert_not_called()
        cache_save.assert_not_called()
        lookup.assert_called_once_with(["000660"])
        self.assertFalse(result["cached"])
        self.assertEqual(["000660"], result["requested_symbols"])
        self.assertEqual("explicit_symbols", result["request_scope"])
        self.assertEqual(["000660"], result["symbols"])

    def test_agent_radar_queries_independent_sources_concurrently(self):
        ready = threading.Event()
        lock = threading.Lock()
        started = 0

        def concurrent_result(value):
            nonlocal started
            with lock:
                started += 1
                if started == 3:
                    ready.set()
            if not ready.wait(timeout=2):
                raise AssertionError("radar sources did not overlap")
            return value

        requested_rows = [{"symbol": "000660", "name": "SK hynix"}]
        with (
            patch("app.stock_suite_app.MEMORY.summary", return_value={"top_candidates": []}),
            patch("app.stock_suite_app._lookup_symbols", return_value=requested_rows),
            patch("app.stock_suite_app.build_news_radar", side_effect=lambda rows: concurrent_result([])),
            patch("app.stock_suite_app.build_financial_radar", side_effect=lambda rows: concurrent_result([])),
            patch(
                "app.stock_suite_app.build_toss_public_market_radar",
                side_effect=lambda symbols: concurrent_result({"items": []}),
            ),
        ):
            result = stock_app.build_agent_radar(symbols=["000660"], force=True)

        self.assertEqual(3, started)
        self.assertEqual(["000660"], result["symbols"])

    def test_news_radar_fetches_symbols_concurrently_and_keeps_request_order(self):
        ready = threading.Event()
        lock = threading.Lock()
        started = 0

        def concurrent_news(*, query, limit):
            nonlocal started
            with lock:
                started += 1
                if started == 4:
                    ready.set()
            if not ready.wait(timeout=2):
                raise AssertionError("symbol news requests did not overlap")
            return []

        requested = [
            {"symbol": symbol, "name": symbol, "market": "US"}
            for symbol in ("AAPL", "MSFT", "NVDA", "TSM")
        ]
        with patch("app.stock_suite_app.fetch_news_rss", side_effect=concurrent_news):
            result = stock_app.build_news_radar(requested)

        self.assertEqual(4, started)
        self.assertEqual(["AAPL", "MSFT", "NVDA", "TSM"], [row["symbol"] for row in result])

    def test_news_radar_scores_only_symbol_matched_items(self):
        rss_items = [
            {"title": "SK하이닉스 HBM 투자 확대", "source": "news"},
            {"title": "삼성바이오로직스 신규 수주 기대", "source": "news"},
        ]
        with patch("app.stock_suite_app.fetch_news_rss", return_value=rss_items):
            result = stock_app.build_news_radar([{"symbol": "207940", "name": "삼성바이오로직스"}])

        row = result[0]
        self.assertEqual(1, row["verified_item_count"])
        self.assertEqual(1, row["unverified_item_count"])
        self.assertFalse(row["items"][0]["score_allowed"])
        self.assertTrue(row["items"][1]["score_allowed"])
        self.assertIn("삼성바이오로직스", row["items"][1]["symbol_match_aliases"])

    def test_account_total_value_gap_explains_small_broker_display_difference(self):
        result = stock_app._explain_account_total_value_gap(298_053, 298_828)

        self.assertEqual("within_tolerance", result["status"])
        self.assertTrue(result["within_tolerance"])
        self.assertEqual(775, result["gap"])
        self.assertIn("settlement_pending_cash", result["likely_causes"])
        self.assertIn("broker_display_timing", result["likely_causes"])

    def test_live_account_state_exposes_total_value_reconciliation(self):
        snapshot = {
            "ok": True,
            "snapshot_at": "2026-07-15T23:40:00+09:00",
            "available_cash": 298_053,
            "total_value": 298_053,
            "broker_total_value": 298_828,
            "position_count": 0,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "live_account_latest_snapshot.json"
            changes_path = Path(temp_dir) / "live_account_changes.jsonl"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            changes_path.write_text("", encoding="utf-8")
            with (
                patch("app.stock_suite_app.LIVE_ACCOUNT_SNAPSHOT_FILE", snapshot_path),
                patch("app.stock_suite_app.LIVE_ACCOUNT_CHANGE_FILE", changes_path),
            ):
                state = stock_app._live_reconciliation_account_state("2026-07-15T10:00:00+09:00")

        reconciliation = state["total_value_reconciliation"]
        self.assertEqual(298_828, state["broker_total_value"])
        self.assertEqual("within_tolerance", reconciliation["status"])
        self.assertEqual(775, reconciliation["gap"])

    def test_live_reconciliation_blocks_when_account_totals_exceed_tolerance(self):
        summary = _live_reconciliation_blocker_summary(
            order_number_mismatches=[],
            active_account_ledger_mismatches=[],
            active_account_ledger_incomplete=[],
            active_unmatched_broker_events=[],
            pending=[],
            partial=[],
            account_snapshot_required=False,
            account_snapshot_failed=False,
            account_total_value_mismatch=True,
        )

        self.assertFalse(summary["next_order_allowed"])
        self.assertFalse(summary["official_performance_allowed"])
        self.assertFalse(summary["learning_allowed"])
        self.assertEqual("review_required", summary["status"])
        self.assertIn(
            "account_total_value_mismatch",
            [row["code"] for row in summary["blockers"]],
        )

    def test_live_reconciliation_certificate_separates_fill_from_account_and_pnl_proof(self):
        buy = {
            "date": "2026-07-15",
            "order_no": "B-1",
            "symbol": "005930",
            "side": "BUY",
            "submitted_quantity": 1,
            "broker_quantity": 1,
            "avg_price": 71000,
            "reconciliation": "matched",
            "official_trade_eligible": True,
            "official_performance_eligible": False,
            "learning_eligible": False,
            "account_ledger_reconciliation": {"status": "matched"},
        }
        sell = {
            "date": "2026-07-16",
            "order_no": "S-1",
            "symbol": "005930",
            "side": "SELL",
            "submitted_quantity": 1,
            "broker_quantity": 1,
            "avg_price": 72000,
            "reconciliation": "matched",
            "official_trade_eligible": False,
            "official_performance_eligible": False,
            "learning_eligible": False,
            "account_ledger_reconciliation": {"status": "incomplete_evidence"},
        }
        certificate = stock_app._live_reconciliation_evidence_certificate(
            submitted=[buy, sell],
            matched=[buy, sell],
            partial=[],
            pending=[],
            account_matched=[buy],
            account_mismatched=[],
            account_incomplete=[sell],
            unmatched_broker_events=[],
        )

        self.assertEqual(100.0, certificate["order_fill_coverage_pct"])
        self.assertEqual(50.0, certificate["account_ledger_coverage_pct"])
        self.assertEqual(0.0, certificate["sell_pnl_coverage_pct"])
        self.assertTrue(certificate["global_order_fill_complete"])
        self.assertFalse(certificate["global_account_ledger_complete"])
        self.assertFalse(certificate["global_sell_pnl_complete"])
        self.assertFalse(certificate["global_history_complete"])
        self.assertTrue(certificate["evidence_sha256"].startswith("sha256:"))
        self.assertFalse(certificate["live_order_allowed"])

    def test_live_reconciliation_blocker_summary_blocks_next_order_with_reason_counts(self):
        summary = _live_reconciliation_blocker_summary(
            order_number_mismatches=[],
            active_account_ledger_mismatches=[
                {
                    "order_no": "B-1",
                    "symbol": "005930",
                    "account_ledger_reconciliation": {
                        "status": "mismatch_blocked",
                        "mismatches": [
                            {"field": "average_price", "expected": 72000, "actual": 71000},
                            {"field": "cash_delta", "actual": -71000},
                        ],
                    },
                }
            ],
            active_account_ledger_incomplete=[
                {
                    "order_no": "S-1",
                    "symbol": "005930",
                    "account_ledger_reconciliation": {
                        "status": "incomplete_evidence",
                        "missing_evidence": ["post_account_snapshot", "realized_pnl"],
                    },
                }
            ],
            active_unmatched_broker_events=[],
            pending=[],
            partial=[],
            account_snapshot_required=False,
            account_snapshot_failed=False,
            dual_path_reconciliation={"hard_block": False},
        )

        self.assertEqual("blocked", summary["status"])
        self.assertFalse(summary["next_order_allowed"])
        self.assertIn("하드 차단", summary["next_order_reason"])
        self.assertIn("대사 차단", summary["operator_message"])
        self.assertFalse(summary["official_performance_allowed"])
        self.assertEqual(1, summary["mismatch_field_counts"]["average_price"])
        self.assertEqual(1, summary["mismatch_field_counts"]["cash_delta"])
        self.assertEqual(1, summary["missing_evidence_counts"]["post_account_snapshot"])
        self.assertEqual(1, summary["missing_evidence_counts"]["realized_pnl"])
        self.assertIn("수량·평균단가·현금 이동·실현손익 대사 재실행", summary["required_before_next_order"])

    def test_live_reconciliation_blocker_summary_explains_clear_next_order(self):
        summary = _live_reconciliation_blocker_summary(
            order_number_mismatches=[],
            active_account_ledger_mismatches=[],
            active_account_ledger_incomplete=[],
            active_unmatched_broker_events=[],
            pending=[],
            partial=[],
            account_snapshot_required=False,
            account_snapshot_failed=False,
            dual_path_reconciliation={"hard_block": False},
        )

        self.assertEqual("clear", summary["status"])
        self.assertTrue(summary["next_order_allowed"])
        self.assertIn("미해결 사유가 없습니다", summary["next_order_reason"])
        self.assertEqual("대사 통과: 다음 주문 가능", summary["operator_message"])
        self.assertEqual([], summary["required_before_next_order"])

    def test_feature_probe_detail_surfaces_operator_and_freshness_messages(self):
        detail = stock_app._feature_probe_detail(
            {
                "ok": True,
                "status": "ready",
                "blocker_summary": {
                    "operator_message": "대사 통과: 다음 주문 가능",
                    "next_order_reason": "실전 주문·체결·계좌 대사에서 현재 주문을 막는 미해결 사유가 없습니다.",
                },
                "cache_policy": {
                    "freshness_status": "refresh_due",
                    "next_refresh_in_seconds": 0,
                    "force_refresh_recommended": True,
                },
            }
        )

        self.assertIn("operator=대사 통과: 다음 주문 가능", detail)
        self.assertIn("next_order_reason=실전 주문·체결·계좌 대사", detail)
        self.assertIn("freshness=refresh_due", detail)
        self.assertIn("refresh_in=0s", detail)
        self.assertIn("force_refresh=True", detail)

    def test_mcp_mask_labels_are_ascii_and_not_mojibake(self):
        import app.codexstock_mcp_server as mcp_server

        self.assertEqual("[MCP-REDACTED]", mcp_server.REDACTED)
        self.assertEqual("[MCP-MONEY-REDACTED]", mcp_server.REDACTED_MONEY)
        self.assertNotRegex(mcp_server.REDACTED + mcp_server.REDACTED_MONEY, r"[留湲덉]")

    def test_mcp_money_mask_preserves_evaluation_schedule_metadata(self):
        import app.codexstock_mcp_server as mcp_server

        safe = mcp_server._sanitize_for_mcp(
            {
                "first_eligible_evaluation_date": "2026-11-30",
                "days_until_final_ab_evaluation": 133,
                "evaluation_amount": 255_000,
                "valuation_price": 98_000,
                "profit_loss_rate": 3.2,
            }
        )

        self.assertEqual("2026-11-30", safe["first_eligible_evaluation_date"])
        self.assertEqual(133, safe["days_until_final_ab_evaluation"])
        self.assertTrue(str(safe["evaluation_amount"]).startswith(mcp_server.REDACTED_MONEY))
        self.assertTrue(str(safe["valuation_price"]).startswith(mcp_server.REDACTED_MONEY))
        self.assertEqual(3.2, safe["profit_loss_rate"])

    def test_mcp_preserves_uppercase_diagnostic_status_while_redacting_secrets(self):
        import app.codexstock_mcp_server as mcp_server

        safe = mcp_server._sanitize_for_mcp(
            {
                "status": "NOT_APPLICABLE_CLOSED_SESSION",
                "api_key": "must-never-leak",
            }
        )

        self.assertEqual("NOT_APPLICABLE_CLOSED_SESSION", safe["status"])
        self.assertEqual(mcp_server.REDACTED, safe["api_key"])

    def test_mcp_user_facing_source_has_no_mojibake_cjk_artifacts(self):
        import app.codexstock_mcp_server as mcp_server

        source = Path(mcp_server.__file__).read_text(encoding="utf-8")
        suspicious = [
            char
            for char in source
            if 0x3400 <= ord(char) <= 0x9FFF
            or 0xF900 <= ord(char) <= 0xFAFF
            or 0x2460 <= ord(char) <= 0x24FF
            or 0x3100 <= ord(char) <= 0x312F
        ]

        self.assertEqual([], suspicious)

    def test_mcp_connection_failure_and_order_block_messages_are_readable(self):
        import urllib.error
        import app.codexstock_mcp_server as mcp_server

        with patch.object(
            mcp_server.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            failure = mcp_server._http_json("GET", "/api/status")

        self.assertIn("코덱스스톡 로컬 앱에 연결하지 못했습니다", failure["error"])
        self.assertIn("코덱스스톡을 실행하세요", failure["hint"])

        blocked = mcp_server._call_tool(
            "codexstock_ask_agent",
            {"question": "삼성전자 실주문 매수해"},
        )
        payload = json.loads(blocked["content"][0]["text"])
        self.assertTrue(payload["blocked"])
        self.assertIn("실주문 승인과 최종 전송 명령을 차단", payload["message"])

    def test_ask_agent_routes_external_signal_inbox_before_engine_contract(self):
        import app.codexstock_mcp_server as mcp_server

        inbox = {
            "ok": True,
            "schema": "codexstock_external_signal_inbox_status_v1",
            "generated_at": "2026-07-15T09:10:00+09:00",
            "signal_count": 8,
        }
        with patch("app.codexstock_mcp_server._http_json", return_value=inbox) as http_json:
            result = mcp_server._agent_local_fallback(
                "최신 외부 신호 인박스 생성시각, 수신시각, 신호 수, 오류 알려줘",
                max_chars=12000,
            )

        http_json.assert_called_once_with("GET", "/api/external-signal/latest")
        self.assertIsNotNone(result)
        text = result["content"][0]["text"]
        payload = json.loads(text)
        self.assertEqual("mcp-local-external-signal-inbox", payload["handled_by"])
        self.assertEqual("codexstock_external_signal_inbox_status_v1", payload["data"]["schema"])
        self.assertNotEqual("mcp-local-external-engine-contract", payload["handled_by"])

    def test_status_attach_uses_compact_manifest_summary(self):
        import app.codexstock_mcp_server as mcp_server

        result = mcp_server._attach_mcp_manifest({"ok": True, "status": "alive"})
        manifest = result["mcp_server_manifest"]

        self.assertTrue(manifest["summary_only"])
        self.assertEqual("codexstock_mcp_manifest", manifest["full_manifest_tool"])
        self.assertGreaterEqual(int(manifest["tool_count"]), 1)
        self.assertNotIn("tool_names", manifest)
        self.assertNotIn("tool_categories", manifest)

    def test_mcp_manifest_reports_client_exposure_mismatch_truthfully(self):
        import app.codexstock_mcp_server as mcp_server

        with patch.dict(
            mcp_server.os.environ,
            {"CODEXSTOCK_MCP_EXPOSED_TOOL_NAMES": json.dumps(["codexstock_status"])},
        ):
            manifest = mcp_server._mcp_manifest()

        exposure = manifest["client_exposure"]
        self.assertEqual("MISMATCH", exposure["status"])
        self.assertEqual("ALL_SERVER_TOOLS_PUBLISHED", exposure["server_publish_status"])
        self.assertTrue(exposure["server_publish_complete"])
        self.assertFalse(exposure["server_side_filter_active"])
        self.assertEqual(0, exposure["server_side_hidden_tool_count"])
        self.assertEqual("REFRESH_REQUIRED", exposure["client_cache_status"])
        self.assertTrue(exposure["client_schema_refresh_required"])
        self.assertEqual(
            "server_published_all_client_schema_refresh_required",
            exposure["availability_truth"],
        )
        self.assertFalse(exposure["schema_match"])
        self.assertEqual(1, exposure["client_exposed_tool_count"])
        self.assertEqual(1, exposure["client_cached_tool_count"])
        self.assertGreater(exposure["server_tool_count"], 1)
        self.assertTrue(exposure["missing_on_client"])
        self.assertEqual(len(exposure["missing_on_client"]), exposure["missing_on_client_count"])
        self.assertEqual(exposure["missing_on_client"], exposure["filtered_tool_names"])
        self.assertEqual(exposure["server_schema_sha256"], exposure["server_manifest_hash"])
        self.assertEqual(64, len(manifest["server_schema_sha256"]))
        self.assertEqual("CORE_MISMATCH", exposure["core_exposure_status"])
        self.assertGreater(exposure["core_missing_on_client_count"], 0)
        self.assertEqual(
            "REFRESH_CONNECTOR_SCHEMA_AND_RESUBMIT_RECEIPT",
            exposure["reconciliation"]["next_action"],
        )

    def test_mcp_manifest_distinguishes_core_match_from_full_surface_mismatch(self):
        import app.codexstock_mcp_server as mcp_server

        with patch.dict(
            mcp_server.os.environ,
            {
                "CODEXSTOCK_MCP_EXPOSED_TOOL_NAMES": json.dumps(
                    list(mcp_server.MCP_CORE_TOOL_NAMES)
                )
            },
            clear=True,
        ):
            manifest = mcp_server._mcp_manifest()

        exposure = manifest["client_exposure"]
        self.assertEqual(20, manifest["core_tool_count"])
        self.assertEqual([], manifest["undeclared_core_tools"])
        self.assertEqual("MISMATCH", exposure["status"])
        self.assertEqual("CORE_MATCHED", exposure["core_exposure_status"])
        self.assertEqual(100.0, exposure["core_coverage_pct"])
        self.assertEqual([], exposure["core_missing_on_client"])
        self.assertTrue(exposure["core_tool_name_set_match"])
        self.assertTrue(
            exposure["reconciliation"]["automatically_reconciled_on_manifest_call"]
        )

    def test_mcp_manifest_reports_own_runtime_source_freshness(self):
        import app.codexstock_mcp_server as mcp_server

        current = mcp_server._mcp_manifest()["runtime_source"]
        self.assertEqual("current", current["status"])
        self.assertFalse(current["restart_required"])
        self.assertEqual(
            current["loaded_source_sha256"],
            current["current_source_sha256"],
        )
        self.assertTrue(current["read_only"])
        self.assertFalse(current["live_order_allowed"])

        with patch.object(mcp_server, "MCP_SOURCE_LOADED_STAT", (0, 0)), patch.object(
            mcp_server,
            "MCP_SOURCE_LOADED_SHA256",
            "0" * 64,
        ):
            stale = mcp_server._mcp_manifest()["runtime_source"]

        self.assertEqual("restart_required", stale["status"])
        self.assertTrue(stale["source_changed_since_process_start"])
        self.assertTrue(stale["restart_required"])

    def test_mcp_exposes_tools_only_with_valid_object_input_schemas(self):
        import app.codexstock_mcp_server as mcp_server

        initialized = mcp_server._handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "schema-contract-test", "version": "1"},
                },
            }
        )
        self.assertEqual({"tools": {}}, initialized["result"]["capabilities"])

        for method in ("resources/list", "prompts/list"):
            unsupported = mcp_server._handle(
                {"jsonrpc": "2.0", "id": 2, "method": method, "params": {}}
            )
            self.assertEqual(-32601, unsupported["error"]["code"])

        listed = mcp_server._handle(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        )
        tools = listed["result"]["tools"]
        names = [tool.get("name") for tool in tools]
        self.assertEqual(len(tools), len(set(names)))
        self.assertTrue(all(isinstance(name, str) and name for name in names))
        for tool in tools:
            self.assertTrue(str(tool.get("description") or "").strip())
            schema = tool.get("inputSchema")
            self.assertIsInstance(schema, dict)
            self.assertEqual("object", schema.get("type"))
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            self.assertIsInstance(properties, dict)
            self.assertIsInstance(required, list)
            self.assertTrue(set(required).issubset(properties))

    def test_mcp_manifest_compares_client_schema_hash_and_refresh_time(self):
        import app.codexstock_mcp_server as mcp_server

        server_hash = mcp_server._mcp_manifest()["server_schema_sha256"]
        with patch.dict(
            mcp_server.os.environ,
            {
                "CODEXSTOCK_MCP_EXPOSED_TOOL_NAMES": json.dumps(
                    [tool["name"] for tool in mcp_server.TOOLS]
                ),
                "CODEXSTOCK_MCP_EXPOSED_SCHEMA_SHA256": server_hash,
                "CODEXSTOCK_MCP_LAST_SCHEMA_REFRESH_AT": "2026-07-18T09:00:00+09:00",
            },
        ):
            exposure = mcp_server._mcp_manifest()["client_exposure"]

        self.assertEqual("MATCHED", exposure["status"])
        self.assertEqual("CURRENT", exposure["client_cache_status"])
        self.assertFalse(exposure["client_schema_refresh_required"])
        self.assertEqual(
            "server_published_all_and_client_schema_matched",
            exposure["availability_truth"],
        )
        self.assertTrue(exposure["schema_match"])
        self.assertTrue(exposure["tool_name_set_match"])
        self.assertTrue(exposure["schema_hash_match"])
        self.assertEqual(server_hash, exposure["exposed_schema_hash"])
        self.assertEqual("2026-07-18T09:00:00+09:00", exposure["last_schema_refresh_at"])
        self.assertEqual("CORE_MATCHED", exposure["core_exposure_status"])
        self.assertEqual("NONE", exposure["reconciliation"]["next_action"])

    def test_mcp_manifest_persists_and_reuses_client_exposure_receipt(self):
        import app.codexstock_mcp_server as mcp_server

        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "client_exposure_receipt.json"
            with patch.object(
                mcp_server,
                "_mcp_client_exposure_receipt_path",
                return_value=receipt_path,
            ), patch.dict(mcp_server.os.environ, {}, clear=True):
                server_hash = mcp_server._mcp_manifest()["server_schema_sha256"]
                receipt = mcp_server._record_mcp_client_exposure(
                    {
                        "client_name": "chatgpt-connector",
                        "client_tool_names": [tool["name"] for tool in mcp_server.TOOLS],
                        "client_schema_sha256": server_hash,
                        "client_observed_at": "2026-07-18T09:00:00+09:00",
                    }
                )
                manifest = mcp_server._mcp_manifest()
                receipt_written = receipt_path.exists()

        self.assertIsNotNone(receipt)
        self.assertTrue(receipt_written)
        exposure = manifest["client_exposure"]
        self.assertEqual("MATCHED", exposure["status"])
        self.assertEqual("persistent_client_receipt", exposure["observation_source"])
        self.assertEqual("full_name_and_schema_hash", exposure["evidence_level"])
        self.assertEqual("chatgpt-connector", exposure["client_name"])
        self.assertEqual(len(mcp_server.TOOLS), exposure["client_exposed_tool_count"])

    def test_mcp_manifest_reconciles_connector_truncated_tool_aliases(self):
        import app.codexstock_mcp_server as mcp_server

        canonical_name = "codexstock_internal_developer_readonly_diagnostics"
        connector_name = "codexstock_internal_developer_1cf8eb3c4dc1"
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "client_exposure_receipt.json"
            with patch.object(
                mcp_server,
                "_mcp_client_exposure_receipt_path",
                return_value=receipt_path,
            ), patch.dict(mcp_server.os.environ, {}, clear=True):
                server_hash = mcp_server._mcp_manifest()["server_schema_sha256"]
                client_names = [
                    tool["name"]
                    for tool in mcp_server.TOOLS
                    if tool["name"] != canonical_name
                ]
                client_names.append(f"{connector_name}=>{canonical_name}")
                receipt = mcp_server._record_mcp_client_exposure(
                    {
                        "client_name": "codex-desktop-connector",
                        "client_tool_names": client_names,
                        "client_schema_sha256": server_hash,
                        "client_observed_at": "2026-07-20T00:45:00+09:00",
                    }
                )
                manifest = mcp_server._mcp_manifest()

        self.assertIsNotNone(receipt)
        self.assertIn(connector_name, receipt["client_tool_names"])
        self.assertNotIn(canonical_name, receipt["client_tool_names"])
        self.assertIn(canonical_name, receipt["client_resolved_tool_names"])
        exposure = manifest["client_exposure"]
        self.assertEqual("MATCHED", exposure["status"])
        self.assertTrue(exposure["client_tool_aliases_applied"])
        self.assertEqual(1, exposure["client_tool_alias_count"])
        self.assertEqual([], exposure["missing_on_client"])
        self.assertEqual([], exposure["unknown_on_client"])
        self.assertEqual("CORE_MATCHED", exposure["core_exposure_status"])
        self.assertEqual("NONE", exposure["reconciliation"]["next_action"])
        self.assertEqual(
            "codexstock.mcp-exposure-reconciliation.v3",
            exposure["reconciliation"]["schema"],
        )

    def test_mcp_manifest_quarantines_stale_subset_receipt_instead_of_reusing_it(self):
        import app.codexstock_mcp_server as mcp_server

        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "client_exposure_receipt.json"
            stale_path = Path(tmp) / "client_exposure_receipt.stale.json"
            with patch.object(
                mcp_server,
                "_mcp_client_exposure_receipt_path",
                return_value=receipt_path,
            ), patch.object(
                mcp_server,
                "_mcp_stale_client_exposure_receipt_path",
                return_value=stale_path,
            ), patch.dict(mcp_server.os.environ, {}, clear=True):
                mcp_server._record_mcp_client_exposure(
                    {
                        "client_name": "stale-connector-cache",
                        "client_tool_names": ["codexstock_status"],
                        "client_schema_sha256": "0" * 64,
                        "client_observed_at": "2026-07-18T09:00:00+09:00",
                    }
                )
                exposure = mcp_server._mcp_manifest()["client_exposure"]
                repeated_exposure = mcp_server._mcp_manifest()["client_exposure"]
                active_exists = receipt_path.exists()
                stale_exists = stale_path.exists()

        self.assertFalse(active_exists)
        self.assertTrue(stale_exists)
        self.assertEqual("CLIENT_EXPOSURE_UNOBSERVED", exposure["status"])
        self.assertEqual("OBSERVATION_REQUIRED", exposure["client_cache_status"])
        self.assertIsNone(exposure["client_cached_tool_count"])
        self.assertEqual(1, exposure["last_observed_stale_tool_count"])
        self.assertTrue(exposure["stale_observation_quarantined"])
        self.assertTrue(exposure["client_observation_required"])
        self.assertEqual([], exposure["missing_on_client"])
        self.assertEqual("CLIENT_EXPOSURE_UNOBSERVED", exposure["core_exposure_status"])
        self.assertEqual("REPORT_CLIENT_TOOL_SURFACE", exposure["reconciliation"]["next_action"])
        self.assertEqual("quarantined_stale_client_receipt", exposure["observation_source"])
        self.assertEqual(1, repeated_exposure["last_observed_stale_tool_count"])
        self.assertEqual(
            "quarantined_stale_client_receipt",
            repeated_exposure["observation_source"],
        )

    def test_mcp_manifest_does_not_claim_full_match_from_names_only(self):
        import app.codexstock_mcp_server as mcp_server

        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "client_exposure_receipt.json"
            with patch.object(
                mcp_server,
                "_mcp_client_exposure_receipt_path",
                return_value=receipt_path,
            ), patch.dict(mcp_server.os.environ, {}, clear=True):
                mcp_server._record_mcp_client_exposure(
                    {
                        "client_name": "name-only-client",
                        "client_tool_names": [tool["name"] for tool in mcp_server.TOOLS],
                        "client_observed_at": "2026-07-18T09:00:00+09:00",
                    }
                )
                exposure = mcp_server._mcp_manifest()["client_exposure"]

        self.assertEqual("NAMES_MATCHED_SCHEMA_UNVERIFIED", exposure["status"])
        self.assertEqual("SCHEMA_HASH_VERIFICATION_REQUIRED", exposure["client_cache_status"])
        self.assertIsNone(exposure["client_schema_refresh_required"])
        self.assertIsNone(exposure["schema_match"])
        self.assertEqual("tool_names_only", exposure["evidence_level"])

    def test_mcp_historical_replay_regeneration_manual_batch_is_paper_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_historical_replay_regeneration_manual_batch", tool_names)

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "paper_only": True,
                "live_order_allowed": False,
                "automatic_promotion": False,
                "verified_delta": 1,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_historical_replay_regeneration_manual_batch",
                {"max_cycles": 2},
            )

        http_json.assert_called_once_with(
            "POST",
            "/api/ai-tournament/regeneration-worker/manual-batch",
            payload={"max_cycles": 2},
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["automatic_promotion"])

    def test_mcp_weakness_force_requests_background_refresh(self):
        import app.codexstock_mcp_server as mcp_server

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "refresh_requested": True,
                "refreshing": True,
                "live_order_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_weakness_completion_audit",
                {"force": True},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/codexstock/weakness-completion-audit",
            {"refresh": 1},
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["request_succeeded"])
        self.assertTrue(payload["cache"]["refresh_requested"])
        self.assertTrue(payload["cache"]["refreshing"])
        self.assertTrue(payload["summary_only"])
        self.assertFalse(payload["live_order_allowed"])

    def test_mcp_weakness_read_uses_cached_status_without_forcing_refresh(self):
        import app.codexstock_mcp_server as mcp_server

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={"ok": True, "refresh_requested": False},
        ) as http_json:
            mcp_server._call_tool(
                "codexstock_weakness_completion_audit",
                {"force": False},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/codexstock/weakness-completion-audit",
            {"force": 0},
        )

    def test_mcp_weakness_summary_preserves_progress_and_blockers_without_raw_evidence(self):
        import app.codexstock_mcp_server as mcp_server

        summary = mcp_server._weakness_completion_audit_summary(
            {
                "ok": False,
                "schema": "codexstock_weakness_completion_audit_v1",
                "status": "verification_pending",
                "summary": {
                    "implementation_label": "10/10 (100%)",
                    "evidence_label": "9/10 (90%)",
                },
                "items": [
                    {
                        "id": 5,
                        "title": "learning",
                        "implementation_verified": True,
                        "current_evidence_passed": False,
                        "status": "verification_pending",
                        "blockers": ["forward_evidence_pending"],
                        "evidence": {"raw_rows": [1] * 1000},
                    }
                ],
                "objective_scope": {
                    "track_count": 1,
                    "system_ready_count": 1,
                    "system_progress_pct": 100.0,
                    "current_outcome_passed_count": 0,
                    "current_outcome_progress_pct": 0.0,
                    "tracks": [
                        {
                            "id": "forward",
                            "label": "forward proof",
                            "system_ready": True,
                            "current_outcome_passed": False,
                            "completion_requirement": "time_evidence",
                            "detail": {"blockers": ["90_days_pending"]},
                        }
                    ],
                },
                "pending_evidence_summary": [
                    {
                        "id": 5,
                        "next_eligible_date": "2026-09-21",
                        "operator_message": "wait for evidence",
                        "large_raw_detail": [1] * 1000,
                    }
                ],
                "collector_errors": {},
                "refresh_requested": True,
                "refreshing": True,
                "live_order_allowed": False,
            }
        )

        self.assertEqual("10/10 (100%)", summary["summary"]["implementation_label"])
        self.assertEqual(["forward_evidence_pending"], summary["items"][0]["blockers"])
        self.assertNotIn("evidence", summary["items"][0])
        self.assertEqual("2026-09-21", summary["pending_evidence_summary"][0]["next_eligible_date"])
        self.assertNotIn("large_raw_detail", summary["pending_evidence_summary"][0])
        self.assertTrue(summary["cache"]["refresh_requested"])
        self.assertFalse(summary["live_order_allowed"])

    def test_mcp_staff_learning_counterfactual_triplet_batch_is_paper_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_staff_learning_counterfactual_triplet_batch", tool_names)

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "paper_only": True,
                "live_order_allowed": False,
                "automatic_promotion": False,
                "official_learning_evidence": False,
                "completed_triplet_count": 2,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_staff_learning_counterfactual_triplet_batch",
                {
                    "max_triplets": 2,
                    "symbols": ["005930", "000660"],
                    "start_date": "2024-01-02",
                    "end_date": "2024-03-29",
                },
            )

        http_json.assert_called_once_with(
            "POST",
            "/api/ai-tournament/staff-learning-counterfactual-triplet-batch",
            payload={
                "max_triplets": 2,
                "symbols": ["005930", "000660"],
                "start_date": "2024-01-02",
                "end_date": "2024-03-29",
                "allow_simulated_fallback": False,
            },
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["automatic_promotion"])
        self.assertFalse(payload["official_learning_evidence"])

    def test_mcp_staff_learning_counterfactual_triplet_batch_omits_legacy_default_period(self):
        import app.codexstock_mcp_server as mcp_server

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={"ok": True, "paper_only": True, "live_order_allowed": False},
        ) as http_json:
            mcp_server._call_tool(
                "codexstock_staff_learning_counterfactual_triplet_batch",
                {"max_triplets": 1},
            )

        http_json.assert_called_once_with(
            "POST",
            "/api/ai-tournament/staff-learning-counterfactual-triplet-batch",
            payload={
                "max_triplets": 1,
                "symbols": [],
                "start_date": "",
                "end_date": "",
                "allow_simulated_fallback": False,
            },
        )

    def test_mcp_staff_learning_counterfactual_schedule_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_staff_learning_counterfactual_schedule", tool_names)

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "status": "deferred_to_market_closed_window",
                "ready_to_run": False,
                "paper_only": True,
                "live_order_allowed": False,
                "automatic_promotion": False,
                "official_learning_evidence": False,
                "unverified_result_affects_score": False,
                "unverified_result_affects_live_candidate": False,
                "blockers": ["market_priority_active"],
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_staff_learning_counterfactual_schedule",
                {"max_triplets": 2},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/ai-tournament/staff-learning-counterfactual-schedule",
            {"max_triplets": 2},
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual("deferred_to_market_closed_window", payload["status"])
        self.assertFalse(payload["ready_to_run"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["automatic_promotion"])
        self.assertFalse(payload["official_learning_evidence"])
        self.assertFalse(payload["unverified_result_affects_score"])
        self.assertFalse(payload["unverified_result_affects_live_candidate"])

    def test_mcp_staff_learning_counterfactual_preregistration_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn(
            "codexstock_staff_learning_counterfactual_preregistration",
            tool_names,
        )
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "status": "REGISTERED",
                "valid": True,
                "contract_hash": "a" * 64,
                "full_strategy_payload_exposed": False,
                "paper_only": True,
                "live_order_allowed": False,
                "automatic_promotion": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_staff_learning_counterfactual_preregistration",
                {},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/ai-tournament/staff-learning-counterfactual-preregistration",
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual("REGISTERED", payload["status"])
        self.assertTrue(payload["valid"])
        self.assertFalse(payload["full_strategy_payload_exposed"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["automatic_promotion"])

    def test_mcp_runtime_deployment_freshness_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_runtime_deployment_freshness", tool_names)
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": False,
                "status": "restart_required",
                "source_changed_since_runtime_start": True,
                "restart_required": True,
                "read_only": True,
                "live_order_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_runtime_deployment_freshness",
                {},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/runtime/deployment-freshness",
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual("restart_required", payload["status"])
        self.assertTrue(payload["restart_required"])
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["live_order_allowed"])

    def test_mcp_promotion_candidate_evidence_audit_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_promotion_candidate_evidence_audit", tool_names)
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": False,
                "verified_count": 0,
                "quarantined_count": 1,
                "paper_only": True,
                "live_order_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_promotion_candidate_evidence_audit",
                {},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/strategy/promotion-candidate-evidence-audit",
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(1, payload["quarantined_count"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])

    def test_mcp_promotion_candidate_discovery_audit_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_promotion_candidate_discovery_audit", tool_names)
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "contract_ready": True,
                "scheduler_eligible_candidate_count": 0,
                "requires_next_krx_session_cooling": True,
                "paper_only": True,
                "live_order_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_promotion_candidate_discovery_audit",
                {},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/strategy/promotion-candidate-discovery-audit",
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["contract_ready"])
        self.assertTrue(payload["requires_next_krx_session_cooling"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])

    def test_mcp_promotion_forward_observation_audit_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_promotion_forward_observation_audit", tool_names)
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "ready": False,
                "verified_forward_days": 0,
                "paper_only": True,
                "live_order_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_promotion_forward_observation_audit",
                {},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/strategy/promotion-forward-observation-audit",
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertFalse(payload["ready"])
        self.assertEqual(0, payload["verified_forward_days"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])

    def test_mcp_promotion_rehearsal_evidence_audit_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_promotion_rehearsal_evidence_audit", tool_names)
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "readiness": {
                    "ready": False,
                    "verified_count": 0,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
                "paper_only": True,
                "live_order_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_promotion_rehearsal_evidence_audit",
                {},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/strategy/promotion-rehearsal-evidence-audit",
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertFalse(payload["readiness"]["ready"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])

    def test_mcp_monte_carlo_evidence_audit_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_monte_carlo_evidence_audit", tool_names)
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "status": "paper_retraining_required",
                "actual_trade_sample_count": 139,
                "paper_only": True,
                "live_order_allowed": False,
                "automatic_promotion": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_monte_carlo_evidence_audit",
                {},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/ai-tournament/monte-carlo-evidence-audit",
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(139, payload["actual_trade_sample_count"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["automatic_promotion"])

    def test_mcp_staff_learning_decision_reflection_audit_is_read_only_endpoint(self):
        import app.codexstock_mcp_server as mcp_server

        tool_names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertIn(
            "codexstock_staff_learning_decision_reflection_audit",
            tool_names,
        )
        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "status": "decision_reflection_verified_performance_pending",
                "next_decision_reflection_verified": True,
                "performance_improvement_proven": False,
                "historical_regressed_repeat_opportunity_count": 7,
                "paper_only": True,
                "live_order_allowed": False,
                "automatic_promotion": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_staff_learning_decision_reflection_audit",
                {"as_of_date": "2026-07-17"},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/ai-tournament/staff-learning-decision-reflection-audit",
            {"as_of_date": "2026-07-17"},
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["next_decision_reflection_verified"])
        self.assertFalse(payload["performance_improvement_proven"])
        self.assertEqual(7, payload["historical_regressed_repeat_opportunity_count"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["automatic_promotion"])

    def test_surface_contract_inventory_covers_all_buttons_apis_and_mcp_tools(self):
        result = stock_app._feature_surface_contract_probe()
        coverage = stock_app._feature_surface_coverage_contract(result)

        self.assertTrue(result["ok"])
        self.assertEqual(133, result["ui_button_count"])
        self.assertEqual(result["ui_button_count"], result["ui_button_bound_count"])
        self.assertEqual(0, result["ui_button_unbound_count"])
        self.assertGreaterEqual(result["ui_api_call_count"], 100)
        self.assertEqual(0, result["ui_api_missing_count"])
        self.assertEqual(185, result["mcp_tool_count"])
        self.assertEqual(result["mcp_tool_count"], result["mcp_tool_handled_count"])
        self.assertEqual(0, result["mcp_tool_unhandled_count"])
        self.assertTrue(coverage["ok"])
        self.assertEqual(100.0, coverage["coverage_pct"])
        self.assertEqual(coverage["covered_count"], coverage["total_count"])
        self.assertEqual("structural_wiring", coverage["coverage_kind"])
        self.assertFalse(coverage["runtime_execution_verified"])
        self.assertTrue(coverage["runtime_evidence_required_separately"])
        self.assertTrue(coverage["audit_only"])
        self.assertFalse(coverage["live_order_allowed"])

    def test_runtime_execution_evidence_does_not_overstate_static_coverage(self):
        checks = [
            {
                "id": "recent",
                "endpoint": "/api/recent",
                "mcp_tool": "codexstock_recent",
                "operational_state": "normal",
                "last_success_at": "2026-07-19T09:00:00+09:00",
                "last_success_age_seconds": 10,
            },
            {
                "id": "stale",
                "endpoint": "/api/stale",
                "operational_state": "delayed",
                "last_success_at": "2026-07-17T09:00:00+09:00",
                "last_success_age_seconds": 172_800,
            },
            {
                "id": "never",
                "mcp_tool": "codexstock_never",
                "operational_state": "verification_pending",
                "last_success_at": "",
            },
        ]
        evidence = stock_app._feature_runtime_execution_evidence(
            checks,
            {"total_count": 420},
        )

        self.assertEqual("bounded_health_probes_only", evidence["scope"])
        self.assertEqual(3, evidence["monitored_check_count"])
        self.assertEqual(1, evidence["recent_success_count"])
        self.assertEqual(1, evidence["stale_success_count"])
        self.assertEqual(1, evidence["never_verified_count"])
        self.assertEqual(2, evidence["current_issue_count"])
        self.assertEqual(420, evidence["structural_surface_total_count"])
        self.assertFalse(evidence["all_structural_features_runtime_verified"])
        self.assertFalse(evidence["live_order_allowed"])

    def test_surface_runtime_smoke_executes_only_curated_read_only_contracts(self):
        def payload_for(contract):
            expected = dict(contract.get("expected_values") or {})
            boolean_keys = set(contract.get("boolean_keys") or ())
            payload = {}
            for key in contract.get("required_keys") or ():
                if key in expected:
                    payload[key] = expected[key]
                elif key in boolean_keys:
                    payload[key] = True
                elif key in {
                    "scheduler",
                    "daemon",
                    "operational_counts",
                    "counts",
                    "workflow",
                    "runtime_process",
                    "candidate_pipeline",
                    "summary",
                    "employee",
                    "app",
                    "system",
                }:
                    payload[key] = {}
                elif key == "engines":
                    payload[key] = []
                elif key.endswith("_count") or key in {"total", "indexed_documents"}:
                    payload[key] = 1
                else:
                    payload[key] = f"test-{key}"
            return {"status_code": 200, "payload": payload}

        api_by_path = {
            str(contract["path"]): contract
            for contract in stock_app.SURFACE_RUNTIME_API_SMOKE_CONTRACTS
        }
        mcp_by_tool = {
            str(contract["tool"]): contract
            for contract in stock_app.SURFACE_RUNTIME_MCP_SMOKE_CONTRACTS
        }
        called_paths = []
        called_tools = []

        def api_fetcher(path, timeout):
            called_paths.append((path, timeout))
            return payload_for(api_by_path[path])

        def mcp_caller(tool, arguments):
            called_tools.append((tool, dict(arguments)))
            return payload_for(mcp_by_tool[tool])

        result = stock_app._run_surface_runtime_smoke(
            base_url="http://127.0.0.1:8765",
            api_fetcher=api_fetcher,
            mcp_caller=mcp_caller,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("ready", result["status"])
        self.assertEqual(11, result["api_total_count"])
        self.assertEqual(11, result["api_passed_count"])
        self.assertEqual(6, result["mcp_total_count"])
        self.assertEqual(6, result["mcp_passed_count"])
        self.assertEqual(17, result["passed_count"])
        self.assertEqual(0, result["failed_count"])
        self.assertEqual(11, len(called_paths))
        self.assertEqual(6, len(called_tools))
        self.assertTrue(all(path.startswith("/api/") for path, _ in called_paths))
        self.assertFalse(any("order" in tool or "submit" in tool for tool, _ in called_tools))
        self.assertFalse(result["safety_contract"]["mutation_allowed"])
        self.assertFalse(result["safety_contract"]["live_order_allowed"])
        self.assertFalse(result["all_structural_features_runtime_verified"])

    def test_surface_runtime_smoke_reports_response_schema_break_without_payload_leak(self):
        api_contracts = {
            str(contract["path"]): contract
            for contract in stock_app.SURFACE_RUNTIME_API_SMOKE_CONTRACTS
        }
        mcp_contracts = {
            str(contract["tool"]): contract
            for contract in stock_app.SURFACE_RUNTIME_MCP_SMOKE_CONTRACTS
        }

        def minimal_payload(contract):
            expected = dict(contract.get("expected_values") or {})
            boolean_keys = set(contract.get("boolean_keys") or ())
            payload = {}
            for key in contract.get("required_keys") or ():
                payload[key] = (
                    expected[key]
                    if key in expected
                    else True
                    if key in boolean_keys
                    else 0
                    if key.endswith("_count") or key == "total"
                    else {}
                    if key in {"scheduler", "daemon", "operational_counts", "counts", "workflow", "runtime_process", "candidate_pipeline", "summary", "employee", "app", "system"}
                    else []
                    if key == "engines"
                    else "value"
                )
            return payload

        def api_fetcher(path, timeout):
            payload = minimal_payload(api_contracts[path])
            if path == "/api/runtime/deployment-freshness":
                payload.pop("restart_required", None)
                payload["private_token"] = "must-not-be-persisted"
            return {"status_code": 200, "payload": payload}

        def mcp_caller(tool, arguments):
            return {"status_code": 200, "payload": minimal_payload(mcp_contracts[tool])}

        result = stock_app._run_surface_runtime_smoke(
            base_url="http://127.0.0.1:8765",
            api_fetcher=api_fetcher,
            mcp_caller=mcp_caller,
        )

        self.assertFalse(result["ok"])
        self.assertEqual("contract_failure", result["status"])
        self.assertEqual(1, result["failed_count"])
        self.assertEqual(["deployment_freshness"], result["failed_ids"])
        failed = next(row for row in result["evidence"] if row["id"] == "deployment_freshness")
        self.assertEqual(["restart_required"], failed["missing_keys"])
        self.assertNotIn("private_token", json.dumps(result, ensure_ascii=False))
        self.assertTrue(failed["redacted_evidence_only"])
        self.assertFalse(result["live_order_allowed"])

    def test_feature_health_lifecycle_keeps_last_success_and_classifies_states(self):
        previous_at = "2026-07-13T09:00:00+09:00"
        generated_at = "2026-07-14T09:00:00+09:00"
        previous = {
            "generated_at": previous_at,
            "checks": [
                {"id": "stale", "status": "alive", "category": "data"},
                {"id": "broken", "status": "alive", "category": "api"},
            ],
        }
        checks = [
            {
                "id": "stale",
                "status": "degraded",
                "category": "data",
                "detail": "source stale",
                "metadata": {"status_reason": "external_report_stale"},
            },
            {"id": "broken", "status": "broken", "category": "api", "detail": "boom"},
            {"id": "slow", "status": "alive", "category": "api", "latency_ms": 3_500},
            {"id": "ready", "status": "alive", "category": "api", "latency_ms": 20},
            {"id": "pending", "status": "degraded", "category": "api", "detail": "review pending"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "feature-health.jsonl"
            path.write_text(json.dumps(previous) + "\n", encoding="utf-8")
            with patch("app.stock_suite_app.FEATURE_HEALTH_FILE", path):
                counts = stock_app._apply_feature_health_lifecycle(checks, generated_at=generated_at)

        by_id = {row["id"]: row for row in checks}
        self.assertEqual("delayed", by_id["stale"]["operational_state"])
        self.assertEqual("지연", by_id["stale"]["operational_state_label"])
        self.assertEqual("warning", by_id["stale"]["operational_severity"])
        self.assertIn("응답이 느립니다", by_id["stale"]["operational_state_description"])
        self.assertEqual(previous_at, by_id["stale"]["last_success_at"])
        self.assertEqual("broken", by_id["broken"]["operational_state"])
        self.assertEqual("고장", by_id["broken"]["status_badge"])
        self.assertEqual(generated_at, by_id["broken"]["last_failure_at"])
        self.assertEqual("delayed", by_id["slow"]["operational_state"])
        self.assertEqual(generated_at, by_id["slow"]["last_success_at"])
        self.assertEqual("normal", by_id["ready"]["operational_state"])
        self.assertEqual("정상", by_id["ready"]["operational_state_label"])
        self.assertEqual("verified", by_id["ready"]["success_evidence_status"])
        self.assertEqual("verification_pending", by_id["pending"]["operational_state"])
        self.assertEqual("never_verified", by_id["pending"]["success_evidence_status"])
        self.assertEqual("성공 기록 없음", by_id["pending"]["success_evidence_label"])
        self.assertTrue(all(str(row.get("action") or "").strip() for row in checks))
        self.assertEqual({"normal": 1, "delayed": 2, "verification_pending": 1, "broken": 1}, counts)
        contract = stock_app._feature_health_lifecycle_contract(checks)
        self.assertTrue(contract["ok"])
        self.assertEqual(0, contract["missing_field_count"])
        self.assertIn("verification_pending", contract["required_states"])
        self.assertIn("success_evidence_status", contract["required_fields"])

    def test_feature_health_uses_source_last_success_for_degraded_probe(self):
        source_success_at = "2026-07-14T08:55:00+09:00"
        checks = [
            {
                "id": "source_delayed",
                "status": "degraded",
                "category": "data",
                "detail": "source stale",
                "metadata": {"source_last_success_at": source_success_at},
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.stock_suite_app.FEATURE_HEALTH_FILE", Path(temp_dir) / "health.jsonl"):
                stock_app._apply_feature_health_lifecycle(
                    checks,
                    generated_at="2026-07-14T09:00:00+09:00",
                )

        self.assertEqual(source_success_at, checks[0]["last_success_at"])
        self.assertEqual("verified", checks[0]["success_evidence_status"])

    def test_external_engine_health_surface_exposes_each_engine_lifecycle(self):
        dashboard = {
            "ok": True,
            "generated_at": "2026-07-14T09:00:00+09:00",
            "summary": {"engine_count": 2},
            "engines": [
                {
                    "engine_id": "verified-engine",
                    "display_name": "Verified",
                    "status": "ready",
                    "operational_state": "normal",
                    "last_checked_at": "2026-07-14T09:00:00+09:00",
                    "last_success_at": "2026-07-14T08:59:00+09:00",
                    "connected": True,
                    "adapter_ready": True,
                    "round_trip_verified": True,
                },
                {
                    "engine_id": "pending-engine",
                    "display_name": "Pending",
                    "status": "preparing",
                    "operational_state": "verification_pending",
                    "last_checked_at": "2026-07-14T09:00:00+09:00",
                    "last_success_at": "",
                },
            ],
        }

        result = stock_app._compact_external_engine_health_surface(dashboard)

        self.assertTrue(result["ok"])
        self.assertEqual(2, result["engine_count"])
        self.assertEqual(2, result["monitored_count"])
        self.assertEqual(100.0, result["coverage_pct"])
        self.assertEqual(1, result["success_evidence_count"])
        self.assertEqual(1, result["missing_success_evidence_count"])
        self.assertEqual("never_verified", result["engines"][1]["success_evidence_status"])
        self.assertTrue(all(row["next_action"] for row in result["engines"]))
        self.assertFalse(result["live_order_allowed"])

    def test_feature_health_lifecycle_contract_rejects_missing_display_fields(self):
        checks = [
            {
                "id": "api_without_display",
                "status": "alive",
                "category": "api",
                "operational_state": "normal",
                "last_checked_at": "2026-07-14T09:00:00+09:00",
                "last_success_at": "2026-07-14T09:00:00+09:00",
            }
        ]
        contract = stock_app._feature_health_lifecycle_contract(checks)
        self.assertFalse(contract["ok"])
        self.assertGreater(contract["missing_field_count"], 0)
        self.assertIn("operational_state_label", contract["missing_by_id"]["api_without_display"])

    def test_feature_health_summary_uses_operational_states_not_raw_liveness(self):
        checks = [
            {"id": "ready", "status": "alive", "category": "api", "operational_state": "normal"},
            {"id": "slow", "status": "alive", "category": "api", "operational_state": "delayed"},
            {
                "id": "pending",
                "status": "alive",
                "category": "contract",
                "operational_state": "verification_pending",
            },
        ]
        payload = {
            "status": "alive",
            "alive_count": 3,
            "degraded_count": 0,
            "summary": {"counts": {"alive": 3, "degraded": 0, "broken": 0, "unknown": 0}},
            "checks": checks,
        }

        result = stock_app._synchronize_feature_health_operational_summary(payload, checks)

        self.assertEqual(3, result["alive_count"])
        self.assertEqual(1, result["normal_count"])
        self.assertEqual(1, result["delayed_count"])
        self.assertEqual(1, result["verification_pending_count"])
        self.assertEqual(2, result["degraded_count"])
        self.assertEqual("degraded", result["status"])
        self.assertEqual(
            "전체 3개 · 정상 1 · 지연 1 · 검증대기 1 · 고장 0",
            result["health_line_plain"],
        )
        self.assertEqual(3, sum(result["operational_counts"].values()))

    def test_system_feature_health_marks_alive_but_delayed_row_as_attention(self):
        board = {
            "generated_at": "2026-07-19T18:40:00+09:00",
            "checked_count": 2,
            "alive_count": 2,
            "liveness_degraded_count": 0,
            "liveness_broken_count": 0,
            "operational_counts": {
                "normal": 1,
                "delayed": 1,
                "verification_pending": 0,
                "broken": 0,
            },
            "summary": {"counts": {"alive": 2, "degraded": 0, "broken": 0, "unknown": 0}},
            "checks": [
                {
                    "id": "ready",
                    "status": "alive",
                    "operational_state": "normal",
                    "operational_state_label": "정상",
                },
                {
                    "id": "slow",
                    "status": "alive",
                    "operational_state": "delayed",
                    "operational_state_label": "지연",
                },
            ],
        }
        with patch("app.stock_suite_app.build_feature_health_board", return_value=board):
            result = build_system_feature_health(compact=True)

        self.assertEqual("watch", result["overall"])
        self.assertEqual(1, result["normal_count"])
        self.assertEqual(1, result["delayed_count"])
        self.assertEqual(1, result["attention_count"])
        self.assertEqual("watch", result["checks"][1]["status"])
        self.assertEqual(
            "전체 2개 · 정상 1 · 지연 1 · 검증대기 0 · 고장 0",
            result["health_line_plain"],
        )

    def test_system_feature_health_reports_domain_attention_separately(self):
        board = {
            "generated_at": "2026-07-20T08:00:00+09:00",
            "checked_count": 1,
            "alive_count": 1,
            "summary": {"counts": {"alive": 1, "degraded": 0, "broken": 0, "unknown": 0}},
            "checks": [
                {
                    "id": "sector_concentration",
                    "label": "Sector concentration",
                    "category": "risk",
                    "status": "alive",
                    "operational_state": "normal",
                    "operational_state_label": "정상",
                    "metadata": {
                        "domain_attention": True,
                        "domain_status": "review_required",
                        "domain_attention_label": "업종 편중 검토 필요",
                        "domain_attention_reason": "반도체 후보 비중 80%",
                    },
                    "detail": "status=review_required, top_sector_share_pct=80.0",
                    "action": "Cap crowded sectors before promotion.",
                }
            ],
        }
        with patch("app.stock_suite_app.build_feature_health_board", return_value=board):
            result = build_system_feature_health(compact=True)

        self.assertEqual("ok", result["overall"])
        self.assertEqual(1, result["normal_count"])
        self.assertEqual(0, result["attention_count"])
        self.assertEqual(1, result["domain_attention_count"])
        self.assertEqual("sector_concentration", result["domain_attention_buttons"][0]["id"])
        self.assertTrue(result["checks"][0]["domain_attention"])

    def test_instant_feature_health_uses_cached_snapshot_without_deep_overlays(self):
        board = {
            "generated_at": "2026-07-19T21:00:00+09:00",
            "checks": [
                {
                    "id": "sqlite_storage",
                    "status": "degraded",
                    "operational_state": "verification_pending",
                },
                {
                    "id": "runtime_failure",
                    "status": "broken",
                    "operational_state": "broken",
                },
            ],
        }
        with (
            patch.object(
                stock_app,
                "FEATURE_HEALTH_BOARD_CACHE",
                (stock_app.time.time(), board),
            ),
            patch(
                "app.stock_suite_app._fast_sqlite_storage_snapshot",
                return_value={
                    "ok": True,
                    "stale": False,
                    "problem_sqlite_count": 0,
                    "max_query_ms": 12.5,
                },
            ),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_ledger_progress",
                side_effect=AssertionError("deep overlay must not run"),
            ),
            patch("app.stock_suite_app._start_feature_health_refresh") as refresh,
        ):
            result = stock_app.build_system_feature_health_instant()

        refresh.assert_not_called()
        self.assertEqual("cached_snapshot_no_deep_overlay", result["diagnostic_mode"])
        self.assertEqual(1, result["normal_count"])
        self.assertEqual(1, result["operational_broken_count"])
        self.assertEqual("normal", result["checks"][0]["operational_state"])
        self.assertFalse(result["live_order_allowed"])

    def test_completion_certificate_health_separates_progress_verified_and_broken(self):
        progress = {
            "progress": {
                "total_candidate_count": 757,
                "verified_count": 59,
                "remaining_candidate_count": 698,
                "label": "59/757 (7.79%)",
            }
        }
        complete = {
            "progress": {
                "total_candidate_count": 757,
                "verified_count": 757,
                "remaining_candidate_count": 0,
                "label": "757/757 (100.00%)",
            }
        }
        verified_certificate = {
            "ok": True,
            "status": "certificate_verified",
            "certificate_id": "HRCERT-1",
            "certificate_sha256": "a" * 64,
            "issued_at": "2026-07-14T23:59:00+09:00",
            "path": "certificate.json",
        }
        with (
            patch(
                "app.stock_suite_app.responsive_historical_replay_regeneration_status",
                return_value=progress,
            ),
            patch(
                "app.stock_suite_app._cached_verified_historical_replay_completion_certificate",
                return_value={"ok": False, "status": "certificate_missing", "path": "certificate.json"},
            ),
        ):
            pending = stock_app._tournament_completion_certificate_health_probe()
        with (
            patch(
                "app.stock_suite_app.responsive_historical_replay_regeneration_status",
                return_value=complete,
            ),
            patch(
                "app.stock_suite_app._cached_verified_historical_replay_completion_certificate",
                return_value=verified_certificate,
            ),
        ):
            verified = stock_app._tournament_completion_certificate_health_probe()
        with (
            patch(
                "app.stock_suite_app.responsive_historical_replay_regeneration_status",
                return_value=complete,
            ),
            patch(
                "app.stock_suite_app._cached_verified_historical_replay_completion_certificate",
                return_value={"ok": False, "status": "certificate_stale", "path": "certificate.json"},
            ),
        ):
            broken = stock_app._tournament_completion_certificate_health_probe()

        self.assertTrue(pending["ok"])
        self.assertEqual("verification_pending", pending["status"])
        self.assertFalse(pending["score_allowed"])
        self.assertFalse(pending["live_order_allowed"])
        self.assertTrue(verified["ok"])
        self.assertEqual("certificate_verified", verified["status"])
        self.assertEqual("2026-07-14T23:59:00+09:00", verified["source_last_success_at"])
        self.assertTrue(verified["score_allowed"])
        self.assertFalse(verified["automatic_promotion"])
        self.assertFalse(broken["ok"])
        self.assertEqual("certificate_stale", broken["status"])
        self.assertEqual("error", broken["severity"])
        self.assertFalse(broken["score_allowed"])
        self.assertFalse(broken["live_order_allowed"])

    def test_completion_certificate_feature_health_maps_all_three_states(self):
        generated_at = "2026-07-15T00:01:00+09:00"
        cases = [
            (
                {
                    "ok": True,
                    "status": "verification_pending",
                    "severity": "warning",
                    "status_reason": "historical_replay_regeneration_in_progress",
                },
                "degraded",
                "verification_pending",
                "",
            ),
            (
                {
                    "ok": True,
                    "status": "certificate_verified",
                    "severity": "ok",
                    "status_reason": "historical_replay_completion_certificate_verified",
                    "source_last_success_at": "2026-07-14T23:59:00+09:00",
                },
                "alive",
                "normal",
                "2026-07-14T23:59:00+09:00",
            ),
            (
                {
                    "ok": False,
                    "status": "certificate_missing",
                    "severity": "error",
                    "status_reason": "historical_replay_certificate_missing",
                },
                "broken",
                "broken",
                "",
            ),
        ]
        for payload, expected_status, expected_state, expected_success_at in cases:
            with self.subTest(status=payload["status"]):
                row = stock_app._feature_health_probe(
                    "tournament_completion_certificate",
                    "Tournament completion certificate",
                    "contract",
                    "/api/ai-tournament/regeneration-completion-audit",
                    lambda payload=payload: payload,
                    degraded_statuses={"verification_pending"},
                    failure_status="broken",
                )
                with tempfile.TemporaryDirectory() as temp_dir:
                    path = Path(temp_dir) / "feature-health.jsonl"
                    with patch("app.stock_suite_app.FEATURE_HEALTH_FILE", path):
                        stock_app._apply_feature_health_lifecycle([row], generated_at=generated_at)
                self.assertEqual(expected_status, row["status"])
                self.assertEqual(expected_state, row["operational_state"])
                self.assertEqual(expected_success_at, row["last_success_at"])

    def test_regeneration_campaign_defers_candidates_added_after_scope_freeze(self):
        initial = {
            "regeneration_candidate_count": 2,
            "regeneration_queue": [
                {"replay_id": "HREPLAY-1"},
                {"replay_id": "HREPLAY-2"},
            ],
        }
        expanded = {
            "regeneration_candidate_count": 3,
            "regeneration_queue": [
                {"replay_id": "HREPLAY-1"},
                {"replay_id": "HREPLAY-2"},
                {"replay_id": "HREPLAY-3"},
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_path = Path(temp_dir) / "campaign.json"
            with patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE",
                campaign_path,
            ):
                first = _historical_replay_regeneration_campaign(initial)
                second = _historical_replay_regeneration_campaign(expanded)

        self.assertEqual(2, first["target_count"])
        self.assertEqual(2, second["target_count"])
        self.assertEqual("complete", second["candidate_identity_comparison_status"])
        self.assertTrue(second["candidate_identity_comparison_claim_allowed"])
        self.assertEqual(1, second["deferred_new_candidate_count"])
        self.assertEqual(
            ["HREPLAY-1", "HREPLAY-2"],
            second["source_replay_ids"],
        )

    def test_system_health_overlays_current_replay_progress_on_cached_board(self):
        board = {
            "generated_at": "2026-07-13T18:00:00+09:00",
            "checked_count": 1,
            "attention_count": 1,
            "summary": {"counts": {"degraded": 1}, "visible_warning_count": 1},
            "checks": [
                {
                    "id": "tournament_reconciliation_audit",
                    "label": "Tournament return reconciliation",
                    "category": "data",
                    "status": "degraded",
                    "detail": "summary=review_required, replay_recovery=1/10 (10.00%), issue=legacy",
                    "metadata": {
                        "regeneration_progress": {
                            "total_candidate_count": 10,
                            "label": "1/10 (10.00%)",
                        }
                    },
                }
            ],
        }
        with (
            patch("app.stock_suite_app.build_feature_health_board", return_value=board),
            patch(
                "app.stock_suite_app._historical_replay_campaign_manifest_scope",
                return_value=(10, {"HREPLAY-1", "HREPLAY-2"}),
            ),
            patch(
                "app.stock_suite_app.responsive_historical_replay_regeneration_status",
                return_value={
                    "progress": {
                        "total_candidate_count": 10,
                        "verified_count": 2,
                        "quarantined_count": 0,
                        "retryable_failure_count": 0,
                        "blocked_failure_count": 0,
                        "unattempted_count": 8,
                        "remaining_candidate_count": 8,
                        "label": "2/10 (20.00%)",
                        "accounting": {"invariant_ok": True},
                    },
                    "worker": {
                        "health_state": "HEALTHY",
                        "last_success_at": "2026-07-14T21:24:32+09:00",
                    },
                    "completion_estimate": {
                        "cooldown_seconds": 300,
                        "estimated_worker_duty_cycle_pct": 1.32,
                        "estimated_hours_remaining": 2.0,
                        "estimated_throughput_per_hour": 4.0,
                    },
                },
            ),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_ledger_progress",
                side_effect=AssertionError("cached health rendering must not rescan the ledger"),
            ),
        ):
            result = build_system_feature_health(compact=True)

        row = result["checks"][0]
        self.assertTrue(row["live_progress_overlay"])
        self.assertEqual("2/10 (20.00%)", row["regeneration_progress"]["label"])
        self.assertEqual("HEALTHY", row["regeneration_worker"]["health_state"])
        self.assertEqual("2026-07-14T21:24:32+09:00", row["regeneration_worker"]["last_success_at"])
        self.assertEqual(300, row["regeneration_estimate"]["cooldown_seconds"])
        self.assertEqual(1.32, row["regeneration_estimate"]["estimated_worker_duty_cycle_pct"])
        self.assertIn("replay_recovery=2/10 (20.00%)", row["detail"])
        self.assertIn("accounting_ok:True", row["detail"])
        self.assertIn("replay_worker=HEALTHY", row["detail"])
        self.assertIn("replay_duty_pct=1.32", row["detail"])

    def test_system_health_uses_persisted_sqlite_snapshot_without_database_probe(self):
        board = {
            "generated_at": "2026-07-20T00:00:00+09:00",
            "checked_count": 1,
            "summary": {"counts": {"alive": 1}},
            "checks": [
                {
                    "id": "sqlite_storage",
                    "label": "SQLite storage",
                    "category": "data",
                    "status": "alive",
                    "operational_state": "normal",
                    "detail": "cached sqlite result",
                }
            ],
        }
        with (
            patch("app.stock_suite_app.build_feature_health_board", return_value=board),
            patch(
                "app.stock_suite_app._fast_sqlite_storage_snapshot",
                return_value={
                    "ok": True,
                    "status": "ready",
                    "cached": True,
                    "stale": False,
                    "sqlite_file_count": 3,
                    "total_sqlite_mb": 61.9,
                    "problem_sqlite_count": 0,
                    "max_query_ms": 7.5,
                },
            ),
            patch(
                "app.stock_suite_app._sqlite_storage_feature_probe",
                side_effect=AssertionError("cached health rendering must not reopen SQLite"),
            ),
        ):
            result = build_system_feature_health(compact=True)

        row = result["checks"][0]
        self.assertEqual("normal", row["operational_state"])
        self.assertTrue(row["live_progress_overlay"])
        self.assertIn("cached=True", row["detail"])

    def test_forced_system_feature_health_returns_synchronous_fresh_board(self):
        board = {
            "ok": True,
            "status": "ready",
            "summary": {"counts": {"alive": 1}, "checked": 1},
            "checks": [],
        }
        with patch("app.stock_suite_app.build_feature_health_board", return_value=board) as build:
            result = build_system_feature_health(force=True, compact=True)

        build.assert_called_once_with(
            probe=True,
            record=True,
            source="system-feature-health",
        )
        self.assertEqual([], result["checks"])
        self.assertTrue(result["audit_only"])
        self.assertFalse(result["live_order_allowed"])

    def test_deep_feature_health_probe_group_runs_concurrently_and_preserves_order(self):
        barrier = threading.Barrier(2)

        def build(check_id):
            def run():
                barrier.wait(timeout=1.0)
                return {"id": check_id, "status": "alive"}

            return run

        result = stock_app._run_feature_health_probe_group(
            [build("first"), build("second")],
            max_workers=2,
        )

        self.assertEqual(["first", "second"], [row["id"] for row in result])

    def test_recorded_feature_health_builds_do_not_overlap(self):
        first_entered = threading.Event()
        release_first = threading.Event()
        state_lock = threading.Lock()
        state = {"active": 0, "max_active": 0, "calls": 0}

        def build(**_kwargs):
            with state_lock:
                state["active"] += 1
                state["calls"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
                call_number = state["calls"]
            if call_number == 1:
                first_entered.set()
                release_first.wait(timeout=1.0)
            with state_lock:
                state["active"] -= 1
            return {"ok": True, "status": "alive", "summary": {"counts": {}}, "checks": []}

        with patch("app.stock_suite_app._build_feature_health_board_uncached", side_effect=build):
            first = threading.Thread(
                target=stock_app.build_feature_health_board,
                kwargs={"probe": True, "record": True, "source": "first"},
            )
            second = threading.Thread(
                target=stock_app.build_feature_health_board,
                kwargs={"probe": True, "record": True, "source": "second"},
            )
            first.start()
            self.assertTrue(first_entered.wait(timeout=1.0))
            second.start()
            self.assertEqual(1, state["max_active"])
            release_first.set()
            first.join(timeout=1.0)
            second.join(timeout=1.0)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(2, state["calls"])
        self.assertEqual(1, state["max_active"])

    def test_forced_feature_health_coalesces_matching_background_probe(self):
        original_cache = stock_app.FEATURE_HEALTH_BOARD_CACHE
        original_refreshing = stock_app.FEATURE_HEALTH_REFRESHING
        original_refresh_probe = stock_app.FEATURE_HEALTH_REFRESH_PROBE
        try:
            stock_app.FEATURE_HEALTH_BOARD_CACHE = (
                1.0,
                {
                    "ok": True,
                    "status": "alive",
                    "probe": True,
                    "generated_at": "2026-07-15T03:00:00+09:00",
                    "summary": {"counts": {"alive": 1}},
                    "checks": [{"id": "fresh"}],
                },
            )
            stock_app.FEATURE_HEALTH_REFRESHING = True
            stock_app.FEATURE_HEALTH_REFRESH_PROBE = True
            stock_app.FEATURE_HEALTH_REFRESH_COMPLETE.set()
            with patch("app.stock_suite_app._build_feature_health_board_uncached") as build:
                result = stock_app.build_feature_health_board(
                    probe=True,
                    record=True,
                    source="forced-test",
                )
        finally:
            stock_app.FEATURE_HEALTH_BOARD_CACHE = original_cache
            stock_app.FEATURE_HEALTH_REFRESHING = original_refreshing
            stock_app.FEATURE_HEALTH_REFRESH_PROBE = original_refresh_probe
            stock_app.FEATURE_HEALTH_REFRESH_COMPLETE.set()

        build.assert_not_called()
        self.assertTrue(result["coalesced_refresh"])
        self.assertFalse(result["cached"])
        self.assertEqual("forced-test", result["requested_source"])
        self.assertEqual("fresh", result["checks"][0]["id"])
        self.assertEqual("verification_pending", result["checks"][0]["operational_state"])
        self.assertEqual("검증대기", result["checks"][0]["status_badge"])
        self.assertEqual("2026-07-15T03:00:00+09:00", result["checks"][0]["last_checked_at"])

    def test_failure_classification_is_append_only_and_disables_retry(self):
        failed = {
            "id": "HREGEN-1",
            "status": "regeneration_failed",
            "source_replay_id": "HREPLAY-9",
            "error": "market data unavailable",
        }
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=[failed]),
            patch("app.stock_suite_app._append_jsonl") as append,
        ):
            result = classify_historical_replay_regeneration_failure(
                "HREPLAY-9",
                failure_kind="input_or_market_data_unavailable",
                retryable=False,
            )

        self.assertTrue(result["ok"])
        self.assertFalse(result["ledger"]["retryable"])
        self.assertEqual("HREGEN-1", result["ledger"]["supersedes_ledger_id"])
        self.assertFalse(result["ledger"]["old_record_rewritten"])
        append.assert_called_once()

    def test_selector_skips_nonretryable_failure(self):
        audit = {
            "regeneration_candidate_count": 2,
            "regeneration_queue": [
                {"replay_id": "HREPLAY-1"},
                {"replay_id": "HREPLAY-2"},
            ],
        }
        ledger = [
            {
                "source_replay_id": "HREPLAY-1",
                "status": "regeneration_failed",
                "retryable": False,
            }
        ]
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=ledger),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": ["HREPLAY-1", "HREPLAY-2"], "target_count": 2},
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                return_value={"ok": True, "status": "ready"},
            ) as contract,
        ):
            selected = next_historical_replay_regeneration_candidate()

        self.assertEqual("HREPLAY-2", selected["replay_id"])
        contract.assert_called_once_with("HREPLAY-2")

    def test_full_scope_selector_skips_resolved_and_invalid_contracts(self):
        queue_rows = [
            {"replay_id": "HREPLAY-1"},
            {"replay_id": "HREPLAY-2"},
            {"replay_id": "HREPLAY-3"},
        ]
        audit = {
            "regeneration_candidate_count": 756,
            "regeneration_queue": queue_rows,
        }
        ledger = [
            {
                "source_replay_id": "HREPLAY-1",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
            }
        ]
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit) as audit_mock,
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=ledger),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": ["HREPLAY-1", "HREPLAY-2", "HREPLAY-3"], "target_count": 3},
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                side_effect=[
                    {"ok": False, "status": "detail_archive_missing"},
                    {
                        "ok": True,
                        "status": "ready_with_cost_policy_change",
                        "source_trade_count": 10,
                        "source_total_return_pct": 5.0,
                    },
                ],
            ),
        ):
            selected = next_historical_replay_regeneration_candidate()

        audit_mock.assert_called_once_with(limit=300, queue_limit=1000, batch_limit=200)
        self.assertEqual("HREPLAY-3", selected["replay_id"])
        self.assertEqual(3, selected["queue_position"])
        self.assertEqual(3, selected["total_candidate_count"])
        self.assertFalse(selected["live_order_allowed"])

    def test_selector_restores_frozen_campaign_source_missing_from_live_audit(self):
        audit = {
            "regeneration_candidate_count": 1,
            "regeneration_queue": [
                {"replay_id": "HREPLAY-1", "expected_trade_count": 20},
            ],
        }
        ledger = [
            {
                "source_replay_id": "HREPLAY-1",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
            }
        ]
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=ledger),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={
                    "source_replay_ids": ["HREPLAY-1", "HREPLAY-2"],
                    "target_count": 2,
                },
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                return_value={
                    "ok": True,
                    "status": "ready",
                    "source_trade_count": 7,
                },
            ) as contract,
        ):
            selected = next_historical_replay_regeneration_candidate()

        self.assertTrue(selected["ok"])
        self.assertEqual("HREPLAY-2", selected["replay_id"])
        self.assertEqual(2, selected["queue_position"])
        self.assertEqual(2, selected["queue_count"])
        self.assertEqual(2, selected["total_candidate_count"])
        self.assertTrue(selected["paper_only"])
        self.assertFalse(selected["live_order_allowed"])
        contract.assert_called_once_with("HREPLAY-2")

    def test_selector_opens_only_top_ranked_valid_contract(self):
        audit = {
            "regeneration_candidate_count": 3,
            "regeneration_queue": [
                {"replay_id": "HREPLAY-1", "expected_trade_count": 2},
                {"replay_id": "HREPLAY-2", "expected_trade_count": 30},
                {"replay_id": "HREPLAY-3", "expected_trade_count": 10},
            ],
        }
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": ["HREPLAY-1", "HREPLAY-2", "HREPLAY-3"], "target_count": 3},
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                return_value={
                    "ok": True,
                    "status": "ready",
                    "source_trade_count": 30,
                },
            ) as contract,
        ):
            selected = next_historical_replay_regeneration_candidate()

        self.assertEqual("HREPLAY-2", selected["replay_id"])
        self.assertEqual(3, selected["candidate_pool_count"])
        self.assertEqual(1, selected["contracts_checked_count"])
        contract.assert_called_once_with("HREPLAY-2")

    def test_selector_trade_cap_defers_large_replays(self):
        audit = {
            "regeneration_candidate_count": 2,
            "regeneration_queue": [
                {"replay_id": "HREPLAY-1", "expected_trade_count": 50},
                {"replay_id": "HREPLAY-2", "expected_trade_count": 10},
            ],
        }
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": ["HREPLAY-1", "HREPLAY-2"], "target_count": 2},
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                return_value={
                    "ok": True,
                    "status": "ready",
                    "source_trade_count": 10,
                    "run_arguments": {},
                },
            ) as contract,
        ):
            selected = next_historical_replay_regeneration_candidate(max_source_trade_count=25)

        self.assertEqual("HREPLAY-2", selected["replay_id"])
        self.assertEqual(1, selected["deferred_large_candidate_count"])
        self.assertEqual(25, selected["max_source_trade_count"])
        contract.assert_called_once_with("HREPLAY-2")

    def test_missing_zip_recovers_contract_from_hashed_backup_index(self):
        replay_id = "HREPLAY-777"
        payload = {
            "id": replay_id,
            "symbols": ["005930"],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "strategy_mode": "ma_cross",
            "initial_cash": 10_000_000,
            "closed_trade_count": 3,
            "strategy_config": {
                "fast": 5,
                "slow": 20,
                "allocation_pct": 25,
                "max_positions": 1,
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backup_root = root / "backups"
            detail_root = root / "details"
            index_path = root / "contract-index.json"
            backup_root.mkdir()
            detail_root.mkdir()
            backup = backup_root / "historical_paper_replays.jsonl.20260101-000000.bak"
            backup.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            indexed = build_historical_replay_backup_contract_index(
                [replay_id], backup_root=backup_root, index_path=index_path
            )
            with patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_BACKUP_CONTRACT_INDEX_FILE",
                index_path,
            ):
                recovered = historical_replay_regeneration_contract(replay_id, detail_root=detail_root)

            envelope = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertTrue(indexed["ok"])
        self.assertTrue(recovered["ok"])
        self.assertEqual("backup_contract_index", recovered["detail_source"])
        self.assertEqual(64, len(envelope["entries"][replay_id]["source_line_sha256"]))
        self.assertEqual(64, len(envelope["entries"][replay_id]["payload_sha256"]))
        self.assertFalse(recovered["live_order_allowed"])

    def test_missing_zip_recovers_contract_from_embedded_tournament_inputs(self):
        replay_id = "HREPLAY-778"
        tournament = {
            "id": "AITOUR-1",
            "generated_at": "2026-07-13T20:59:09+09:00",
            "start_date": "2010-01-01",
            "end_date": "2015-12-31",
            "rankings": [
                {
                    "replay_id": replay_id,
                    "strategy_mode": "intraday_theme_leader",
                    "fast_window": 5,
                    "slow_window": 20,
                    "selected_symbols": ["005930", "000660"],
                    "initial_cash": 10_000_000,
                    "closed_trade_count": 12,
                    "total_return_pct": 8.5,
                    "selected_challenge_config": {
                        "allocation_pct": 35,
                        "max_positions": 2,
                        "stop_loss_pct": 2,
                        "take_profit_pct": 4,
                        "holding_limit_days": 2,
                    },
                    "cost_model": {
                        "commission_bps_each_side": 1.5,
                        "slippage_bps_each_side": 5,
                        "kr_sell_tax_bps": 18,
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            detail_root = root / "details"
            detail_root.mkdir()
            tournament_path = root / "tournaments.jsonl"
            tournament_path.write_text(json.dumps(tournament) + "\n", encoding="utf-8")
            index_path = root / "missing-index.json"
            with (
                patch("app.stock_suite_app.AI_TOURNAMENT_FILE", tournament_path),
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_BACKUP_CONTRACT_INDEX_FILE",
                    index_path,
                ),
            ):
                recovered = historical_replay_regeneration_contract(
                    replay_id,
                    detail_root=detail_root,
                )

        self.assertTrue(recovered["ok"])
        self.assertEqual("tournament_embedded_contract", recovered["detail_source"])
        self.assertEqual("2010-01-01", recovered["run_arguments"]["start_date"])
        self.assertEqual(35.0, recovered["run_arguments"]["allocation_pct"])
        self.assertEqual(1.5, recovered["run_arguments"]["commission_bps"])
        self.assertFalse(recovered["live_order_allowed"])

    def test_selector_keeps_frozen_candidate_missing_from_live_audit_queue(self):
        audit = {
            "regeneration_candidate_count": 1,
            "regeneration_queue": [{"replay_id": "HREPLAY-1", "expected_trade_count": 20}],
        }
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={
                    "source_replay_ids": ["HREPLAY-1", "HREPLAY-2"],
                    "target_count": 2,
                },
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                side_effect=[
                    {"ok": False, "status": "detail_archive_missing"},
                    {"ok": True, "status": "ready", "source_trade_count": 12},
                ],
            ) as contract,
        ):
            selected = next_historical_replay_regeneration_candidate()

        self.assertEqual("HREPLAY-2", selected["replay_id"])
        self.assertEqual(2, selected["total_candidate_count"])
        self.assertEqual(
            [unittest.mock.call("HREPLAY-1"), unittest.mock.call("HREPLAY-2")],
            contract.call_args_list,
        )

    def test_tampered_backup_index_payload_is_rejected(self):
        replay_id = "HREPLAY-888"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            detail_root = root / "details"
            detail_root.mkdir()
            payload = {"id": replay_id, "symbols": ["005930"]}
            index_path = root / "contract-index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            replay_id: {
                                "payload": payload,
                                "payload_sha256": "0" * 64,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_BACKUP_CONTRACT_INDEX_FILE",
                index_path,
            ):
                result = historical_replay_regeneration_contract(replay_id, detail_root=detail_root)

        self.assertFalse(result["ok"])
        self.assertEqual("detail_archive_missing", result["status"])

    def test_retention_never_prunes_backup_pinned_by_contract_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            backup_dir = data_dir / "backups" / "jsonl_compaction"
            backup_dir.mkdir(parents=True)
            oldest = backup_dir / "historical_paper_replays.jsonl.20260101-000000.bak"
            pinned = backup_dir / "historical_paper_replays.jsonl.20260102-000000.bak"
            newest = backup_dir / "historical_paper_replays.jsonl.20260103-000000.bak"
            oldest.write_bytes(b"largest-baseline")
            pinned.write_bytes(b"pin")
            newest.write_bytes(b"new")
            os_times = [(1, oldest), (2, pinned), (3, newest)]
            for timestamp, path in os_times:
                path.touch()
                import os
                os.utime(path, (timestamp, timestamp))
            index_path = data_dir / "historical_replay_backup_contract_index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            "HREPLAY-1": {"source_backup_path": str(pinned)}
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_BACKUP_CONTRACT_INDEX_FILE",
                index_path,
            ):
                result = jsonl_compaction_backup_retention(
                    "historical_paper_replays.jsonl", data_dir=data_dir
                )

        preserved = {row["name"]: row for row in result["preserved"]}
        self.assertEqual(1, result["contract_index_pinned_count"])
        self.assertTrue(preserved[pinned.name]["contract_index_pinned"])
        self.assertNotIn(pinned.name, {row["name"] for row in result["removable"]})

    def test_detail_archive_recovers_paper_contract_and_discloses_cost_change(self):
        replay_id = "HREPLAY-123"
        payload = {
            "id": replay_id,
            "symbols": ["005930", "000660"],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "strategy_mode": "intraday_theme_leader",
            "initial_cash": 10_000_000,
            "closed_trade_count": 12,
            "total_return_pct": 8.5,
            "data_mode": "real",
            "strategy_config": {
                "fast": 5,
                "slow": 20,
                "allocation_pct": 35,
                "max_positions": 2,
                "stop_loss_pct": 2,
                "take_profit_pct": 4,
                "holding_limit_days": 2,
                "cycles_per_day": 24,
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / f"{replay_id}.json.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(f"{replay_id}.json", json.dumps(payload))
            result = historical_replay_regeneration_contract(replay_id, detail_root=Path(temp_dir))

        self.assertTrue(result["ok"])
        self.assertEqual("ready_with_cost_policy_change", result["status"])
        self.assertEqual(["005930", "000660"], result["run_arguments"]["symbols"])
        self.assertEqual(5, result["run_arguments"]["fast"])
        self.assertTrue(result["cost_policy"]["changed_from_archive"])
        self.assertFalse(result["live_order_allowed"])

    def test_identity_mismatch_is_blocked(self):
        replay_id = "HREPLAY-123"
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / f"{replay_id}.json.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(f"{replay_id}.json", json.dumps({"id": "HREPLAY-999"}))
            result = historical_replay_regeneration_contract(replay_id, detail_root=Path(temp_dir))

        self.assertFalse(result["ok"])
        self.assertEqual("detail_identity_mismatch", result["status"])

    def test_regeneration_is_append_only_paper_and_never_auto_promotes(self):
        contract = {
            "ok": True,
            "replay_id": "HREPLAY-123",
            "source_trade_count": 12,
            "source_total_return_pct": 8.5,
            "cost_policy": {"changed_from_archive": True},
            "run_arguments": {
                "symbols": ["005930"],
                "start_date": "2020-01-01",
                "end_date": "2020-12-31",
            },
        }
        replay = {
            "id": "HREPLAY-456",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "data_mode": "real",
            "data_errors": [],
            "replay_data_bundle_evidence": _verified_replay_bundle_evidence(
                "005930", "2020-01-01", "2020-12-31"
            ),
            "execution_timing_model": {
                "version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "decision_basis": "completed_prior_daily_bar",
                "execution_basis": "next_available_close",
                "minimum_signal_lag_bars": 1,
                "same_bar_signal_execution_allowed": False,
                "lookahead_safe_required": True,
                "execution_bar_excluded_from_decision": True,
                "symbol_calendar_alignment_required": True,
                "missing_execution_bar_policy": "skip_until_next_available_symbol_bar",
                "calendar_adjacency_proof_contract": stock_app.CALENDAR_ADJACENCY_PROOF_CONTRACT,
            },
            "symbols": ["005930"],
            "price_currency_unit_audit": {
                "passed": True,
                "blockers": [],
                "contracts": {"005930": {"passed": True, "blockers": []}},
            },
            "closed_trade_count": 11,
            "total_return_pct": 7.0,
            "trade_journal_reconciliation_summary": {
                "official_return_claim_allowed": True,
                "status": "passed",
            },
        }
        with (
            patch("app.stock_suite_app.historical_replay_regeneration_contract", return_value=contract),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch("app.stock_suite_app.run_historical_paper_replay", return_value=replay) as runner,
            patch(
                "app.stock_suite_app._historical_replay_artifact_anchors",
                return_value=TEST_REPLAY_ARTIFACT_ANCHORS,
            ),
            patch("app.stock_suite_app._append_jsonl") as append,
        ):
            result = regenerate_historical_paper_replay("HREPLAY-123")

        self.assertTrue(result["ok"])
        self.assertEqual("verified_replacement_candidate", result["status"])
        self.assertFalse(result["ledger"]["old_record_rewritten"])
        self.assertFalse(result["ledger"]["automatic_promotion"])
        self.assertFalse(result["live_order_allowed"])
        self.assertEqual(
            stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
            result["ledger"]["evidence_schema_version"],
        )
        self.assertEqual(
            TEST_REPLAY_ARTIFACT_ANCHORS["replay_artifact_sha256"],
            result["ledger"]["replay_artifact_sha256"],
        )
        self.assertEqual(
            TEST_REPLAY_ARTIFACT_ANCHORS["journal_artifact_sha256"],
            result["ledger"]["journal_artifact_sha256"],
        )
        runner.assert_called_once()
        append.assert_called_once()

    def test_selector_requeues_legacy_resolved_result_for_evidence_upgrade(self):
        audit = {
            "regeneration_candidate_count": 1,
            "regeneration_queue": [{"replay_id": "HREPLAY-1", "expected_trade_count": 12}],
        }
        legacy_ledger = [
            {
                "source_replay_id": "HREPLAY-1",
                "status": "verified_replacement_candidate",
            }
        ]
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=legacy_ledger),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": ["HREPLAY-1"], "target_count": 1},
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                return_value={"ok": True, "status": "ready", "run_arguments": {}},
            ),
        ):
            selected = next_historical_replay_regeneration_candidate()

        self.assertEqual("HREPLAY-1", selected["replay_id"])
        self.assertTrue(selected["evidence_upgrade_required"])
        self.assertEqual(
            stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
            selected["required_evidence_schema_version"],
        )

    def test_selector_does_not_repeat_current_evidence_result(self):
        audit = {
            "regeneration_candidate_count": 1,
            "regeneration_queue": [{"replay_id": "HREPLAY-1", "expected_trade_count": 12}],
        }
        current_ledger = [
            {
                "source_replay_id": "HREPLAY-1",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
            }
        ]
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=current_ledger),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": ["HREPLAY-1"], "target_count": 1},
            ),
            patch("app.stock_suite_app.historical_replay_regeneration_contract") as contract,
        ):
            selected = next_historical_replay_regeneration_candidate()

        self.assertTrue(selected["ok"])
        self.assertEqual("queue_complete", selected["status"])
        contract.assert_not_called()

    def test_status_counts_only_latest_append_only_verdict(self):
        audit = {
            "regeneration_candidate_count": 10,
            "regeneration_batch_sample_limited": True,
            "official_return_claim_allowed": False,
            "summary": {"status": "review_required"},
            "regeneration_batches": [{"replay_id": "HREPLAY-123"}, {"replay_id": "HREPLAY-999"}],
        }
        rows = [
            {"source_replay_id": "HREPLAY-123", "status": "quarantined_new_result"},
            {
                "source_replay_id": "HREPLAY-123",
                "status": "verified_replacement_candidate",
                "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
                "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
                "generated_at": "2026-07-13T18:00:00+09:00",
            },
            {
                "source_replay_id": "HREPLAY-999",
                "status": "regeneration_failed",
                "failure_kind": "input_or_market_data_unavailable",
                "retryable": False,
                "generated_at": "2026-07-13T18:01:00+09:00",
            },
        ]
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=rows),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={
                    "source_replay_ids": ["HREPLAY-123", "HREPLAY-999"],
                    "target_count": 10,
                },
            ),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                side_effect=[{"ok": True}, {"ok": False, "status": "detail_archive_missing"}],
            ),
        ):
            result = historical_replay_regeneration_status()

        self.assertEqual("1/10 (10.00%)", result["progress"]["label"])
        self.assertEqual(1, result["latest_verdict_counts"]["verified"])
        self.assertEqual(0, result["latest_verdict_counts"]["quarantined"])
        self.assertEqual(1, result["progress"]["blocked_failure_count"])
        self.assertEqual(0, result["progress"]["retryable_failure_count"])
        self.assertEqual(8, result["progress"]["unattempted_count"])
        self.assertEqual(
            1,
            result["progress"]["failure_kind_counts"]["input_or_market_data_unavailable"],
        )
        self.assertTrue(result["progress"]["accounting"]["invariant_ok"])
        self.assertEqual("HREPLAY-999", result["progress"]["latest_activity"]["source_replay_id"])
        self.assertEqual(1, result["source_preview"]["detail_archive_missing_count"])

    def test_status_eta_uses_recent_median_instead_of_last_outlier(self):
        audit = {
            "regeneration_candidate_count": 10,
            "regeneration_batches": [],
        }
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": True,
                    "interval_seconds": 15,
                    "cycle_count": 4,
                    "last_result": {"elapsed_seconds": 300},
                    "recent_success_elapsed_seconds": [20, 30, 40, 300],
                }
            },
        )()
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": [], "target_count": 10},
            ),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
        ):
            result = historical_replay_regeneration_status()

        estimate = result["completion_estimate"]
        self.assertEqual(35.0, estimate["median_job_elapsed_seconds"])
        self.assertEqual(300.0, estimate["p90_job_elapsed_seconds"])
        self.assertEqual(4, estimate["duration_sample_count"])
        self.assertEqual(500, estimate["estimated_seconds_remaining"])
        self.assertEqual(
            "remaining * (median_recent_success_elapsed_seconds + cooldown_seconds)",
            estimate["basis"],
        )

    def test_status_eta_discloses_weekday_throttle_and_full_batch_speed(self):
        audit = {"regeneration_candidate_count": 10, "regeneration_batches": []}
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": True,
                    "interval_seconds": 15,
                    "last_wait_seconds": 900,
                    "next_due_at": "2026-07-14T21:30:00+09:00",
                    "last_result": {
                        "selection": {
                            "schedule_mode": "weekday_after_hours_bounded",
                            "cadence_seconds": 300,
                            "next_eligible_at": "2026-07-14T21:35:00+09:00",
                        },
                    },
                    "recent_success_elapsed_seconds": [20, 30, 40, 300],
                }
            },
        )()
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": [], "target_count": 10},
            ),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
        ):
            result = historical_replay_regeneration_status()

        estimate = result["completion_estimate"]
        self.assertEqual(300, estimate["cooldown_seconds"])
        self.assertEqual(300, estimate["cadence_seconds"])
        self.assertEqual(15, estimate["base_interval_seconds"])
        self.assertEqual(3350, estimate["estimated_seconds_remaining"])
        self.assertEqual(10.75, estimate["estimated_throughput_per_hour"])
        self.assertEqual(10.45, estimate["estimated_worker_duty_cycle_pct"])
        self.assertEqual(50.0, estimate["conservative_worker_duty_cycle_pct"])
        self.assertEqual(0.14, estimate["full_batch_hours_remaining"])
        self.assertEqual("weekday_after_hours_bounded", estimate["schedule_mode"])
        self.assertEqual("2026-07-14T21:30:00+09:00", estimate["next_due_at"])
        self.assertEqual("2026-07-14T21:35:00+09:00", estimate["next_eligible_at"])

    def test_status_eta_uses_closed_day_success_cooldown_for_full_batch(self):
        audit = {"regeneration_candidate_count": 10, "regeneration_batches": []}
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": True,
                    "interval_seconds": 15,
                    "closed_day_success_cooldown_seconds": 2,
                    "last_result": {"elapsed_seconds": 1.0},
                    "recent_success_elapsed_seconds": [1.0, 1.2, 1.4],
                }
            },
        )()
        with (
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_campaign",
                return_value={"source_replay_ids": [], "target_count": 10},
            ),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
        ):
            result = historical_replay_regeneration_status()

        estimate = result["completion_estimate"]
        self.assertEqual(2, estimate["closed_day_interval_seconds"])
        self.assertEqual(32, estimate["full_batch_seconds_remaining"])
        self.assertEqual(
            "remaining * (median_recent_success_elapsed_seconds + closed_day_interval_seconds)",
            estimate["full_batch_basis"],
        )

    def test_status_eta_uses_zero_cooldown_in_manual_paper_focus(self):
        estimate = _historical_replay_completion_estimate(
            10,
            {
                "interval_seconds": 15,
                "closed_day_success_cooldown_seconds": 2,
                "last_wait_seconds": 0,
                "last_result": {
                    "selection": {"schedule_mode": "manual_paper_focus_batch"},
                },
                "recent_success_elapsed_seconds": [5.0, 6.0, 7.0],
            },
        )

        self.assertEqual(0, estimate["cooldown_seconds"])
        self.assertEqual(60, estimate["estimated_seconds_remaining"])
        self.assertEqual(600.0, estimate["estimated_throughput_per_hour"])

    def test_completion_audit_defers_replay_during_market_priority_focus(self):
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "interval_seconds": 15,
                    "last_result": {
                        "elapsed_seconds": 1.0,
                        "selection": {
                            "schedule_mode": "weekday_after_hours_bounded",
                            "cadence_seconds": 30,
                        },
                    },
                    "recent_success_elapsed_seconds": [1.0, 1.2, 1.4],
                }
            },
        )()
        completion = {
            "ok": False,
            "status": "in_progress",
            "expected_total": 757,
            "progress_label": "182/757 (24.04%)",
            "resolved_count": 182,
            "remaining_count": 575,
            "completion_verified": False,
            "certificate_allowed": False,
            "paper_only": True,
            "automatic_promotion": False,
            "live_order_allowed": False,
            "blockers": ["all_candidates_resolved"],
        }
        with (
            patch("app.stock_suite_app.cached_historical_replay_regeneration_status", return_value={"progress": {}, "campaign": {"target_count": 757}, "unique_source_replay_count": 757}),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
            patch("app.stock_suite_app.historical_replay_data_gap_queue", return_value={"ok": True}),
            patch("app.stock_suite_app.historical_replay_evidence_audit", return_value={"ok": False}),
            patch("app.stock_suite_app._historical_replay_campaign_manifest_scope", return_value=("campaign", {"A"})),
            patch("app.stock_suite_app.audit_replay_completion", return_value=completion),
            patch("app.stock_suite_app.historical_replay_evidence_milestone_status", return_value={"deep_verification": {}}),
            patch(
                "app.stock_suite_app.build_operating_focus",
                return_value={
                    "mode": "MARKET_PREPARATION_FOCUS",
                    "market_phase": "premarket",
                    "market_priority_active": True,
                    "market_open": False,
                },
            ),
        ):
            result = stock_app.historical_replay_completion_audit()

        self.assertEqual("defer_to_market_closed_window", result["next_action"])
        self.assertFalse(result["current_run_allowed"])
        self.assertTrue(result["current_market_priority_active"])
        self.assertEqual("premarket", result["current_market_phase"])
        self.assertEqual("MARKET_PREPARATION_FOCUS", result["current_focus_mode"])

    def test_completion_audit_reuses_current_verified_certificate(self):
        certificate_cache_dir = tempfile.TemporaryDirectory()
        self.addCleanup(certificate_cache_dir.cleanup)
        certificate_cache_path = Path(certificate_cache_dir.name) / "verified-certificate-cache.json"
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "interval_seconds": 15,
                    "running": True,
                    "thread_alive": True,
                    "recent_success_elapsed_seconds": [1.0],
                }
            },
        )()
        certificate = {
            "ok": True,
            "status": "certificate_verified",
            "completion_verified": True,
            "certificate_allowed": True,
            "resolved_count": 757,
            "expected_total": 757,
            "progress_label": "757/757 (100.00%)",
            "evidence_audit": {"ok": True},
            "deep_evidence_gate": {"status": "passed_to_milestone"},
            "paper_only": True,
            "automatic_promotion": False,
            "live_order_allowed": False,
        }
        with (
            patch(
                "app.stock_suite_app.cached_historical_replay_regeneration_status",
                return_value={
                    "progress": {
                        "resolved_count": 757,
                        "remaining_candidate_count": 0,
                    },
                    "campaign": {"target_count": 757},
                    "incremental_plan": {"remaining_count": 0},
                },
            ),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
            patch(
                "app.stock_suite_app.load_historical_replay_completion_certificate",
                return_value=certificate,
            ) as certificate_loader,
            patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_VERIFIED_CERTIFICATE_CACHE",
                None,
            ),
            patch(
                "app.stock_suite_app.HISTORICAL_REPLAY_VERIFIED_CERTIFICATE_CACHE_FILE",
                certificate_cache_path,
            ),
            patch("app.stock_suite_app.historical_replay_data_gap_queue") as data_gap,
            patch("app.stock_suite_app.historical_replay_evidence_audit") as evidence_audit,
            patch(
                "app.stock_suite_app.build_operating_focus",
                return_value={
                    "mode": "MARKET_CLOSED_RESEARCH",
                    "market_phase": "closed",
                    "market_priority_active": False,
                    "market_open": False,
                },
            ),
            patch(
                "app.stock_suite_app.historical_replay_focus_mode_status",
                return_value={"mode": "paper_focus"},
            ),
        ):
            result = stock_app.historical_replay_completion_audit()
            cached_result = stock_app.historical_replay_completion_audit()

        certificate_loader.assert_called_once_with()
        data_gap.assert_not_called()
        evidence_audit.assert_not_called()
        self.assertTrue(result["completion_audit_cache_hit"])
        self.assertTrue(result["deep_rescan_skipped"])
        self.assertEqual("verified_completion_certificate", result["completion_audit_cache_source"])
        self.assertEqual("codexstock_historical_replay_completion_audit_v3", result["schema"])
        self.assertFalse(result["current_run_allowed"])
        self.assertFalse(result["live_order_allowed"])
        self.assertTrue(cached_result["certificate_fast_cache_hit"])

    def test_verified_completion_certificate_reuses_hash_checked_disk_cache(self):
        certificate = {
            "ok": True,
            "status": "certificate_verified",
            "completion_verified": True,
            "issued_at": "2026-07-17T07:00:00+09:00",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_paths = [root / f"source-{index}.json" for index in range(5)]
            for path in source_paths:
                path.write_text("{}", encoding="utf-8")
            cache_path = root / "verified-cache.json"
            with (
                patch("app.stock_suite_app.AI_TOURNAMENT_FILE", source_paths[0]),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE", source_paths[1]),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE", source_paths[2]),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_EVIDENCE_MILESTONE_FILE", source_paths[3]),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_COMPLETION_CERTIFICATE_FILE", source_paths[4]),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_VERIFIED_CERTIFICATE_CACHE_FILE", cache_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_VERIFIED_CERTIFICATE_CACHE", None),
                patch(
                    "app.stock_suite_app.load_historical_replay_completion_certificate",
                    return_value=certificate,
                ) as loader,
            ):
                first = stock_app._cached_verified_historical_replay_completion_certificate()
                stock_app.HISTORICAL_REPLAY_VERIFIED_CERTIFICATE_CACHE = None
                second = stock_app._cached_verified_historical_replay_completion_certificate()

        loader.assert_called_once_with()
        self.assertFalse(first["certificate_fast_cache_hit"])
        self.assertTrue(second["certificate_fast_cache_hit"])
        self.assertEqual("disk", second["certificate_fast_cache_source"])

    def test_base_audit_cache_ignores_live_ledger_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tournament_path = Path(temp_dir) / "tournaments.jsonl"
            ledger_path = Path(temp_dir) / "regenerations.jsonl"
            tournament_path.write_text("{}\n", encoding="utf-8")
            ledger_path.write_text("{}\n", encoding="utf-8")
            audit = {
                "regeneration_candidate_count": 756,
                "regeneration_batches": [{"replay_id": "HREPLAY-1"}],
            }
            with (
                patch("app.stock_suite_app.AI_TOURNAMENT_FILE", tournament_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE", ledger_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
                patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit) as builder,
                patch(
                    "app.stock_suite_app.historical_replay_regeneration_contract",
                    return_value={"ok": True, "status": "ready"},
                ) as contract_builder,
            ):
                first = _historical_replay_base_audit()
                ledger_path.write_text("{}\n{}\n", encoding="utf-8")
                second = _historical_replay_base_audit()

        self.assertFalse(first["base_audit_cache_hit"])
        self.assertTrue(second["base_audit_cache_hit"])
        self.assertEqual(1, builder.call_count)
        self.assertEqual(1, contract_builder.call_count)
        self.assertEqual(1, second["_source_preview"]["recoverable_count"])

    def test_base_audit_bounds_detail_contract_preview(self):
        audit = {
            "regeneration_candidate_count": 25,
            "regeneration_batches": [
                {"replay_id": f"HREPLAY-{index}"}
                for index in range(1, 26)
            ],
        }
        with (
            patch("app.stock_suite_app.HISTORICAL_REPLAY_BASE_AUDIT_CACHE", None),
            patch("app.stock_suite_app.ai_tournament_reconciliation_audit", return_value=audit),
            patch(
                "app.stock_suite_app.historical_replay_regeneration_contract",
                return_value={"ok": True, "status": "ready"},
            ) as contract_builder,
        ):
            result = _historical_replay_base_audit()

        self.assertEqual(20, result["_source_preview"]["checked_unique_replay_count"])
        self.assertEqual(20, result["_source_preview"]["preview_limit"])
        self.assertTrue(result["_source_preview"]["sample_limited"])
        self.assertEqual(20, contract_builder.call_count)

    def test_cached_status_invalidates_when_source_file_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tournament_path = Path(temp_dir) / "tournaments.jsonl"
            ledger_path = Path(temp_dir) / "regenerations.jsonl"
            cache_path = Path(temp_dir) / "status-cache.json"
            tournament_path.write_text("{}\n", encoding="utf-8")
            ledger_path.write_text("{}\n", encoding="utf-8")
            with (
                patch("app.stock_suite_app.AI_TOURNAMENT_FILE", tournament_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE", ledger_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_STATUS_CACHE_FILE", cache_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_STATUS_CACHE", None),
                patch(
                    "app.stock_suite_app.historical_replay_regeneration_status",
                    side_effect=[{"progress": {"label": "1/10"}}, {"progress": {"label": "2/10"}}],
                ) as builder,
            ):
                first = cached_historical_replay_regeneration_status()
                second = cached_historical_replay_regeneration_status()
                ledger_path.write_text("{}\n{}\n", encoding="utf-8")
                third = cached_historical_replay_regeneration_status()

        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertFalse(third["cache_hit"])
        self.assertEqual("2/10", third["progress"]["label"])
        self.assertEqual(2, builder.call_count)

    def test_cached_status_overlays_live_worker_busy_state(self):
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": True,
                    "busy": True,
                    "current_replay_id": "HREPLAY-LIVE",
                    "interval_seconds": 15,
                    "cycle_count": 9,
                    "next_due_at": "",
                    "last_wait_reason": "success_cooldown",
                }
            },
        )()
        with tempfile.TemporaryDirectory() as temp_dir:
            tournament_path = Path(temp_dir) / "tournaments.jsonl"
            ledger_path = Path(temp_dir) / "regenerations.jsonl"
            campaign_path = Path(temp_dir) / "campaign.json"
            tournament_path.write_text("{}\n", encoding="utf-8")
            ledger_path.write_text("{}\n", encoding="utf-8")
            signature = (
                _historical_replay_status_file_signature(tournament_path),
                _historical_replay_status_file_signature(ledger_path),
                _historical_replay_status_file_signature(campaign_path),
            )
            with (
                patch("app.stock_suite_app.AI_TOURNAMENT_FILE", tournament_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE", ledger_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_CAMPAIGN_FILE", campaign_path),
                patch(
                    "app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_STATUS_CACHE",
                    (signature, {"progress": {"label": "cached"}, "worker": {"busy": False}}),
                ),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
            ):
                result = cached_historical_replay_regeneration_status()

        self.assertTrue(result["cache_hit"])
        self.assertTrue(result["worker"]["busy"])
        self.assertEqual("HREPLAY-LIVE", result["worker"]["current_replay_id"])
        self.assertFalse(result["worker"]["live_order_allowed"])

    def test_responsive_status_overlays_live_worker_on_cached_progress(self):
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": True,
                    "busy": True,
                    "current_replay_id": "HREPLAY-LIVE",
                    "interval_seconds": 15,
                    "cycle_count": 12,
                    "next_due_at": "",
                    "last_wait_reason": "success_cooldown",
                }
            },
        )()
        status_cache = type(
            "StatusCache",
            (),
            {
                "get": lambda self: {
                    "ok": True,
                    "progress": {"verified_count": 250, "total_candidate_count": 757, "label": "250/757"},
                    "worker": {"busy": False},
                    "stale": True,
                    "refreshing": True,
                }
            },
        )()
        with (
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_RESPONSIVE_STATUS_CACHE", status_cache),
        ):
            from app.stock_suite_app import responsive_historical_replay_regeneration_status

            result = responsive_historical_replay_regeneration_status()

        self.assertEqual(250, result["progress"]["verified_count"])
        self.assertTrue(result["worker"]["busy"])
        self.assertEqual("HREPLAY-LIVE", result["worker"]["current_replay_id"])
        self.assertTrue(result["stale"])
        self.assertTrue(result["refreshing"])
        self.assertTrue(result["progress"]["snapshot_stale"])
        self.assertTrue(result["progress"]["refreshing"])
        self.assertFalse(result["progress"]["confirmed"])
        self.assertNotEqual(result["progress"]["label"], result["progress"]["display_label"])
        self.assertFalse(result["worker"]["live_order_allowed"])

    def test_responsive_status_confirms_expired_cache_when_source_signature_matches(self):
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": True,
                    "busy": False,
                    "interval_seconds": 15,
                    "last_wait_seconds": 900,
                    "last_result": {},
                }
            },
        )()
        status_cache = type(
            "StatusCache",
            (),
            {
                "get": lambda self: {
                    "ok": True,
                    "progress": {
                        "verified_count": 2,
                        "remaining_candidate_count": 755,
                        "label": "2/757 (0.26%)",
                    },
                    "responsive_source_signature": [[1, 2], [3, 4], [5, 6]],
                    "stale": True,
                    "refreshing": True,
                }
            },
        )()
        with (
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_RESPONSIVE_STATUS_CACHE", status_cache),
            patch("app.stock_suite_app._historical_replay_responsive_cache_is_current", return_value=True),
        ):
            result = stock_app.responsive_historical_replay_regeneration_status()

        self.assertFalse(result["stale"])
        self.assertTrue(result["cache_expired"])
        self.assertTrue(result["source_signature_current"])
        self.assertEqual("CONFIRMED_CACHED", result["source_state"])
        self.assertFalse(result["progress"]["snapshot_stale"])
        self.assertTrue(result["progress"]["confirmed"])
        self.assertEqual(result["progress"]["label"], result["progress"]["display_label"])

    def test_responsive_status_never_rescans_ledger_while_full_audit_refreshes(self):
        worker = type(
            "Worker",
            (),
            {
                "status": lambda self: {
                    "running": True,
                    "busy": False,
                    "interval_seconds": 15,
                    "last_wait_seconds": 30,
                    "last_result": {},
                }
            },
        )()
        status_cache = type(
            "StatusCache",
            (),
            {
                "get": lambda self: {
                    "ok": True,
                    "progress": {
                        "verified_count": 10,
                        "remaining_candidate_count": 747,
                        "label": "10/757 (1.32%)",
                    },
                    "responsive_source_signature": [[1, 2], [3, 4], [5, 6]],
                    "stale": True,
                    "refreshing": True,
                }
            },
        )()
        with (
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", worker),
            patch("app.stock_suite_app.HISTORICAL_REPLAY_RESPONSIVE_STATUS_CACHE", status_cache),
            patch("app.stock_suite_app._historical_replay_responsive_cache_is_current", return_value=False),
            patch(
                "app.stock_suite_app._historical_replay_regeneration_ledger_progress",
                side_effect=AssertionError("request path must not rescan the replay ledger"),
            ),
        ):
            result = stock_app.responsive_historical_replay_regeneration_status()

        self.assertEqual("10/757 (1.32%)", result["progress"]["label"])
        self.assertFalse(result["progress"]["confirmed"])
        self.assertFalse(result["progress"]["live_ledger_overlay"])
        self.assertTrue(result["progress"]["detail_snapshot_stale"])
        self.assertTrue(result["progress"]["snapshot_stale"])
        self.assertEqual("SOURCE_CHANGED_REFRESHING", result["source_state"])
        self.assertNotEqual(result["progress"]["label"], result["progress"]["display_label"])
        self.assertFalse(result["worker"]["live_order_allowed"])

    def test_manual_replay_regeneration_batch_reports_verified_delta_and_cooldown_stop(self):
        class Worker:
            def __init__(self):
                self.calls = 0

            def run_once(self):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "ok": True,
                        "status": "verified_replacement_candidate",
                        "replay_id": "HREPLAY-1",
                        "elapsed_seconds": 1.25,
                        "selection": {"status": "ready"},
                        "paper_only": True,
                        "live_order_allowed": False,
                    }
                return {
                    "ok": True,
                    "status": "weekday_after_hours_cooldown",
                    "selection": {"status": "weekday_after_hours_cooldown"},
                    "paper_only": True,
                    "live_order_allowed": False,
                }

            def status(self):
                return {"interval_seconds": 15, "paper_only": True, "live_order_allowed": False}

            def _cooldown_for_result(self, result):
                if result["status"] == "verified_replacement_candidate":
                    return 15, "success_cooldown"
                return 300, "schedule_wait"

        before = {
            "progress": {
                "resolved_count": 45,
                "remaining_candidate_count": 712,
                "label": "45/757 (5.94%)",
            },
            "worker": {"interval_seconds": 15},
        }
        after = {
            "progress": {
                "resolved_count": 46,
                "remaining_candidate_count": 711,
                "label": "46/757 (6.08%)",
            },
            "worker": {"interval_seconds": 15},
        }
        with (
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", Worker()),
            patch("app.stock_suite_app.cached_historical_replay_regeneration_status", side_effect=[before, after]),
            patch(
                "app.stock_suite_app.build_operating_focus",
                return_value={
                    "mode": "MARKET_CLOSED_RESEARCH",
                    "market_phase": "closed",
                    "market_priority_active": False,
                    "market_open": False,
                },
            ),
        ):
            result = run_historical_replay_regeneration_manual_batch(max_cycles=3)

        self.assertTrue(result["ok"])
        self.assertEqual(2, result["executed_cycles"])
        self.assertEqual(1, result["verified_delta"])
        self.assertEqual("weekday_after_hours_cooldown", result["stop_reason"])
        self.assertEqual("45/757 (5.94%)", result["before_label"])
        self.assertEqual("46/757 (6.08%)", result["after_label"])
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["automatic_promotion"])
        self.assertFalse(result["unverified_result_affects_score"])

    def test_manual_replay_regeneration_batch_defers_during_market_priority_focus(self):
        class Worker:
            def run_once(self):
                raise AssertionError("manual replay batch must not run during market priority")

        before = {
            "progress": {
                "resolved_count": 45,
                "remaining_candidate_count": 712,
                "label": "45/757 (5.94%)",
            },
            "worker": {"interval_seconds": 15},
        }
        with (
            patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_WORKER", Worker()),
            patch("app.stock_suite_app.cached_historical_replay_regeneration_status", return_value=before),
            patch(
                "app.stock_suite_app.build_operating_focus",
                return_value={
                    "mode": "MARKET_PREPARATION_FOCUS",
                    "market_phase": "premarket",
                    "market_priority_active": True,
                    "market_open": False,
                },
            ),
        ):
            result = run_historical_replay_regeneration_manual_batch(max_cycles=3)

        self.assertTrue(result["ok"])
        self.assertEqual("deferred_to_market_closed_window", result["status"])
        self.assertEqual("market_priority_active", result["stop_reason"])
        self.assertEqual(0, result["executed_cycles"])
        self.assertEqual(0, result["verified_delta"])
        self.assertEqual("45/757 (5.94%)", result["before_label"])
        self.assertEqual("45/757 (5.94%)", result["after_label"])
        self.assertEqual("MARKET_PREPARATION_FOCUS", result["current_focus_mode"])
        self.assertIn("수동 대사 보류", result["operator_message"])
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["unverified_result_affects_score"])

    def test_cached_status_rejects_stale_schema_even_when_files_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tournament_path = Path(temp_dir) / "tournaments.jsonl"
            ledger_path = Path(temp_dir) / "regenerations.jsonl"
            cache_path = Path(temp_dir) / "status-cache.json"
            tournament_path.write_text("{}\n", encoding="utf-8")
            ledger_path.write_text("{}\n", encoding="utf-8")
            signature = [
                list(_historical_replay_status_file_signature(tournament_path)),
                list(_historical_replay_status_file_signature(ledger_path)),
            ]
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": "historical-replay-regeneration-status-cache.v1",
                        "source_signature": signature,
                        "payload": {"progress": {"label": "stale"}},
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch("app.stock_suite_app.AI_TOURNAMENT_FILE", tournament_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_FILE", ledger_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_STATUS_CACHE_FILE", cache_path),
                patch("app.stock_suite_app.HISTORICAL_REPLAY_REGENERATION_STATUS_CACHE", None),
                patch(
                    "app.stock_suite_app.historical_replay_regeneration_status",
                    return_value={"progress": {"label": "fresh"}},
                ) as builder,
            ):
                result = cached_historical_replay_regeneration_status()

        self.assertFalse(result["cache_hit"])
        self.assertEqual("fresh", result["progress"]["label"])
        builder.assert_called_once_with()

    def test_data_gap_queue_repairs_stale_empty_manifest_from_ledger(self):
        rows = [
            {
                "id": "HREGEN-1",
                "source_replay_id": "HREPLAY-123",
                "status": "regeneration_failed",
                "retryable": False,
                "failure_kind": "input_or_market_data_unavailable",
            }
        ]
        contract = {
            "run_arguments": {
                "symbols": ["005930"],
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data-gaps.json"
            path.write_text(json.dumps({"status": "empty", "requests": []}), encoding="utf-8")
            with (
                patch("app.stock_suite_app.HISTORICAL_REPLAY_DATA_GAP_QUEUE_FILE", path),
                patch("app.stock_suite_app._read_jsonl", return_value=rows),
                patch("app.stock_suite_app.historical_replay_regeneration_contract", return_value=contract),
            ):
                result = historical_replay_data_gap_queue(record=False)

        self.assertEqual("backfill_required", result["status"])
        self.assertEqual(1, result["request_count"])
        self.assertEqual("HREPLAY-123", result["requests"][0]["contract"]["replay_id"])
        self.assertFalse(result["requests"][0]["live_order_allowed"])

    def test_reassessment_appends_corrected_verdict_without_rewriting(self):
        previous = {
            "id": "HREGEN-1",
            "source_replay_id": "HREPLAY-123",
            "new_replay_id": "HREPLAY-456",
            "status": "quarantined_new_result",
        }
        journal = {"actions": []}
        replay = {
            "id": "HREPLAY-456",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "data_mode": "real",
            "data_errors": [],
            "replay_data_bundle_evidence": _verified_replay_bundle_evidence(
                "005930", "2026-01-01", "2026-01-31"
            ),
            "execution_timing_model": {
                "version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
                "decision_basis": "completed_prior_daily_bar",
                "execution_basis": "next_available_close",
                "minimum_signal_lag_bars": 1,
                "same_bar_signal_execution_allowed": False,
                "lookahead_safe_required": True,
                "execution_bar_excluded_from_decision": True,
                "symbol_calendar_alignment_required": True,
                "missing_execution_bar_policy": "skip_until_next_available_symbol_bar",
                "calendar_adjacency_proof_contract": stock_app.CALENDAR_ADJACENCY_PROOF_CONTRACT,
            },
            "symbols": ["005930"],
            "price_currency_unit_audit": {
                "passed": True,
                "blockers": [],
                "contracts": {"005930": {"passed": True, "blockers": []}},
            },
        }
        with (
            patch("app.stock_suite_app._read_jsonl", side_effect=[[previous], [replay]]),
            patch("pathlib.Path.is_file", return_value=True),
            patch("app.stock_suite_app.is_inside", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=json.dumps(journal).encode("utf-8")),
            patch(
                "app.stock_suite_app.build_backtest_return_reconciliation",
                return_value={"official_return_claim_allowed": True, "status": "passed"},
            ),
            patch("app.stock_suite_app._append_jsonl") as append,
        ):
            result = reassess_historical_replay_regeneration("HREPLAY-123", "HREPLAY-456")

        self.assertTrue(result["ok"])
        self.assertEqual("HREGEN-1", result["ledger"]["supersedes_ledger_id"])
        self.assertFalse(result["ledger"]["old_record_rewritten"])
        append.assert_called_once()

    def test_artifact_anchor_helper_hashes_persisted_replay_and_exact_journal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            journal_root = root / "journals"
            journal_root.mkdir()
            journal_path = journal_root / "HREPLAY-456.json"
            journal_bytes = b'{"actions":[],"note":"creation bytes"}'
            journal_path.write_bytes(journal_bytes)
            replay = {
                "id": "HREPLAY-456",
                "trade_journal_path": str(journal_path),
                "dates": [],
                "equity_curve": [],
            }
            with (
                patch("app.stock_suite_app.TRADE_JOURNAL_DIR", journal_root),
                patch("app.stock_suite_app.USER_DATA_ROOT", root),
            ):
                anchors = stock_app._historical_replay_artifact_anchors(replay)

        self.assertEqual(
            stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
            anchors["artifact_hash_contract"],
        )
        self.assertEqual(
            stock_app.canonical_replay_artifact_sha256(
                stock_app._compact_historical_replay_storage_record(replay)
            ),
            anchors["replay_artifact_sha256"],
        )
        self.assertEqual(
            stock_app.journal_artifact_sha256(journal_bytes),
            anchors["journal_artifact_sha256"],
        )

    def test_reassessment_blocks_current_artifact_hash_mismatch(self):
        journal = {"actions": []}
        journal_bytes = json.dumps(journal).encode("utf-8")
        replay = {
            "id": "HREPLAY-456",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "data_mode": "real",
            "data_errors": [],
            "symbols": ["005930"],
            "price_currency_unit_audit": {
                "passed": True,
                "blockers": [],
                "contracts": {"005930": {"passed": True, "blockers": []}},
            },
        }
        previous = {
            "id": "HREGEN-1",
            "source_replay_id": "HREPLAY-123",
            "new_replay_id": "HREPLAY-456",
            "status": "quarantined_new_result",
            "evidence_schema_version": stock_app.HISTORICAL_REPLAY_EVIDENCE_SCHEMA_VERSION,
            "execution_timing_model_version": stock_app.HISTORICAL_REPLAY_EXECUTION_TIMING_MODEL_VERSION,
            "replay_data_bundle_evidence_schema": stock_app.HISTORICAL_REPLAY_DATA_BUNDLE_SLICE_EVIDENCE_SCHEMA,
            "artifact_hash_contract": stock_app.REPLAY_ARTIFACT_HASH_CONTRACT,
            "replay_artifact_sha256": "0" * 64,
            "journal_artifact_sha256": stock_app.journal_artifact_sha256(journal_bytes),
        }
        with (
            patch("app.stock_suite_app._read_jsonl", side_effect=[[previous], [replay]]),
            patch("pathlib.Path.is_file", return_value=True),
            patch("app.stock_suite_app.is_inside", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=journal_bytes),
            patch(
                "app.stock_suite_app.build_backtest_return_reconciliation",
                return_value={"official_return_claim_allowed": True, "status": "passed"},
            ),
            patch("app.stock_suite_app._append_jsonl") as append,
        ):
            result = reassess_historical_replay_regeneration(
                "HREPLAY-123", "HREPLAY-456"
            )

        self.assertFalse(result["ok"])
        self.assertEqual("artifact_integrity_mismatch", result["status"])
        append.assert_not_called()

    def test_regeneration_quarantines_failed_price_currency_audit(self):
        contract = {
            "ok": True,
            "replay_id": "HREPLAY-123",
            "source_trade_count": 1,
            "source_total_return_pct": 1.0,
            "cost_policy": {},
            "run_arguments": {"symbols": ["000660"]},
        }
        replay = {
            "id": "HREPLAY-456",
            "data_mode": "real",
            "data_errors": [],
            "symbols": ["000660"],
            "price_currency_unit_audit": {
                "passed": False,
                "blockers": [{"symbol": "000660"}],
                "contracts": {
                    "000660": {
                        "passed": False,
                        "blockers": ["split_dividend_adjustment_not_verified"],
                    }
                },
            },
            "closed_trade_count": 1,
            "total_return_pct": 2.0,
            "trade_journal_reconciliation_summary": {
                "official_return_claim_allowed": True,
                "status": "passed",
            },
        }
        with (
            patch("app.stock_suite_app.historical_replay_regeneration_contract", return_value=contract),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch("app.stock_suite_app.run_historical_paper_replay", return_value=replay),
            patch(
                "app.stock_suite_app._historical_replay_artifact_anchors",
                return_value=TEST_REPLAY_ARTIFACT_ANCHORS,
            ),
            patch("app.stock_suite_app._append_jsonl"),
        ):
            result = regenerate_historical_paper_replay("HREPLAY-123")

        self.assertFalse(result["ok"])
        self.assertEqual("quarantined_new_result", result["status"])
        self.assertIn(
            "price_currency_unit_audit_not_passed",
            result["ledger"]["official_return_block_reasons"],
        )

    def test_regeneration_quarantines_missing_lookahead_timing_evidence(self):
        contract = {
            "ok": True,
            "replay_id": "HREPLAY-123",
            "source_trade_count": 1,
            "source_total_return_pct": 1.0,
            "cost_policy": {},
            "run_arguments": {"symbols": ["000660"]},
        }
        replay = {
            "id": "HREPLAY-456",
            "data_mode": "real",
            "data_errors": [],
            "symbols": ["000660"],
            "price_currency_unit_audit": {
                "passed": True,
                "blockers": [],
                "contracts": {"000660": {"passed": True, "blockers": []}},
            },
            "closed_trade_count": 1,
            "total_return_pct": 2.0,
            "trade_journal_reconciliation_summary": {
                "official_return_claim_allowed": True,
                "status": "passed",
            },
        }
        with (
            patch("app.stock_suite_app.historical_replay_regeneration_contract", return_value=contract),
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch("app.stock_suite_app.run_historical_paper_replay", return_value=replay),
            patch(
                "app.stock_suite_app._historical_replay_artifact_anchors",
                return_value=TEST_REPLAY_ARTIFACT_ANCHORS,
            ),
            patch("app.stock_suite_app._append_jsonl"),
        ):
            result = regenerate_historical_paper_replay("HREPLAY-123")

        self.assertFalse(result["ok"])
        self.assertEqual("quarantined_new_result", result["status"])
        self.assertIn(
            "lookahead_safe_execution_timing_model_missing_or_invalid",
            result["ledger"]["official_return_block_reasons"],
        )


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.codexstock_mcp_server as mcp_server
import app.stock_suite_app as stock_app


def _replacement(source_replay_id: str, return_pct: float) -> dict[str, object]:
    return {
        "source_replay_id": source_replay_id,
        "new_replay_id": f"HREPLAY-{source_replay_id.split('-')[-1]}9",
        "milestone": 25,
        "milestone_generated_at": "2026-07-15T00:00:00+09:00",
        "evidence_bundle_hash": "a" * 64,
        "replay": {
            "total_return_pct": return_pct,
            "max_drawdown_pct": -5.0,
            "win_rate_pct": 55.0,
            "trade_count": 20,
            "closed_trade_count": 10,
            "symbols": ["005930"],
            "cost_model": {
                "enabled": True,
                "commission_bps_each_side": 1.5,
                "slippage_bps_each_side": 5.0,
                "kr_sell_tax_bps": 18.0,
            },
            "price_currency_unit_audit": {
                "passed": True,
                "blockers": [],
            },
        },
        "reconciliation": {
            "status": "passed",
            "checked_count": 10,
            "official_return_claim_allowed": True,
        },
        "official_verdict": {
            "official_return_claim_allowed": True,
            "block_reasons": [],
        },
    }


def _row(replay_id: str, contestant_id: str) -> dict[str, object]:
    return {
        "replay_id": replay_id,
        "contestant_id": contestant_id,
        "name": contestant_id,
        "rank": 1,
        "score": 999.0,
        "total_return_pct": 999.0,
        "risk_limit_pct": 20.0,
        "selected_symbols": ["005930"],
        "bias_audit": {"passed": True},
    }


class TournamentScoreGateTests(unittest.TestCase):
    def test_base_audit_cold_start_uses_matching_durable_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tournament_path = root / "ai_tournaments.jsonl"
            tournament_path.write_text('{"id":"AITOUR-1"}\n', encoding="utf-8")
            signature = list(stock_app._historical_replay_status_file_signature(tournament_path))
            cache_path = root / "base_audit_cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "schema": "codexstock_historical_replay_base_audit_cache_v1",
                        "source_signature": signature,
                        "payload": {
                            "regeneration_candidate_count": 1,
                            "regeneration_queue": [{"replay_id": "HREPLAY-1"}],
                            "summary": {"status": "review_required"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stock_app, "AI_TOURNAMENT_FILE", tournament_path),
                patch.object(stock_app, "HISTORICAL_REPLAY_BASE_AUDIT_CACHE_FILE", cache_path),
                patch.object(
                    stock_app,
                    "HISTORICAL_REPLAY_BASE_AUDIT_CACHE",
                    stock_app._HISTORICAL_REPLAY_BASE_AUDIT_UNINITIALIZED,
                ),
                patch.object(
                    stock_app,
                    "ai_tournament_reconciliation_audit",
                    side_effect=AssertionError("matching durable cache must avoid full audit"),
                ),
            ):
                result = stock_app._historical_replay_base_audit()

        self.assertTrue(result["base_audit_cache_hit"])
        self.assertEqual("disk", result["base_audit_cache_source"])
        self.assertEqual("HREPLAY-1", result["regeneration_queue"][0]["replay_id"])

    def test_certified_index_rehashes_scoped_artifacts_without_full_source_audit(self):
        source_id = "HREPLAY-1"
        replacement_id = "HREPLAY-19"
        replay_hash = "b" * 64
        journal_hash = "c" * 64
        ledger = {
            "source_replay_id": source_id,
            "new_replay_id": replacement_id,
            "status": "verified_replacement_candidate",
            "official_return_claim_allowed": True,
            "artifact_hash_contract": "contract-v1",
            "replay_artifact_sha256": replay_hash,
            "journal_artifact_sha256": journal_hash,
            "reconciliation": {
                "status": "passed",
                "official_return_claim_allowed": True,
            },
        }
        replay = {
            "id": replacement_id,
            "total_return_pct": 4.2,
            "trade_journal_path": "unused-in-mocked-anchor",
        }
        scope_hash = stock_app.evidence_scope_hash([source_id])
        milestone = {
            "milestone": 1,
            "current_contract_valid": True,
            "effective_status": "passed",
            "audited_source_ids": [source_id],
            "audited_scope_hash": scope_hash,
            "evidence_bundle_hash": "d" * 64,
            "ledger_evidence_hash": "e" * 64,
            "replay_evidence_hash": "f" * 64,
            "journal_evidence_hash": "a" * 64,
            "generated_at": "2026-07-15T00:00:00+09:00",
        }
        status = {
            "campaign_id": "HRCAMPAIGN-1",
            "target_count": 757,
            "deep_verification": {"verified_through_count": 1},
            "latest_records": [milestone],
        }
        verdict = {"official_return_claim_allowed": True, "block_reasons": []}

        with (
            patch.object(stock_app, "HISTORICAL_REPLAY_SCORE_GATE_CACHE", None),
            patch.object(stock_app, "_historical_replay_score_gate_source_signature", return_value=("sig",)),
            patch.object(stock_app, "historical_replay_evidence_milestone_status", return_value=status),
            patch.object(stock_app, "_read_jsonl", return_value=[ledger]),
            patch.object(
                stock_app,
                "_read_jsonl_latest_by_ids",
                return_value=([replay], {"found_id_count": 1}),
            ),
            patch.object(stock_app, "_historical_replay_evidence_contract_is_current", return_value=True),
            patch.object(stock_app, "_historical_replay_official_verdict", return_value=verdict),
            patch.object(
                stock_app,
                "_historical_replay_artifact_anchors",
                return_value={
                    "artifact_hash_contract": "contract-v1",
                    "replay_artifact_sha256": replay_hash,
                    "journal_artifact_sha256": journal_hash,
                },
            ),
            patch.object(
                stock_app,
                "historical_replay_evidence_audit",
                side_effect=AssertionError("full source audit must not run on a standings read"),
            ),
        ):
            result = stock_app._historical_replay_certified_score_index()

        self.assertTrue(result["ok"])
        self.assertEqual("codexstock_historical_replay_score_gate_index_v2", result["schema"])
        self.assertEqual(1, result["certified_replacement_count"])
        self.assertIn(source_id, result["replacements"])
        self.assertIn("exact_ledger_replay_journal_rehash", result["verification_method"])

    def test_unverified_replay_cannot_claim_score_or_return(self):
        index = {
            "ok": True,
            "verified_through_count": 25,
            "target_count": 757,
            "replacements": {},
            "blockers": [],
        }
        claim = stock_app._ai_tournament_official_claim_state(
            _row("HREPLAY-26", "operator"),
            certified_index=index,
        )

        self.assertFalse(claim["eligible"])
        self.assertFalse(claim["score_allowed"])
        self.assertIsNone(claim["official_total_return_pct"])
        self.assertIn("source_replay_not_in_deep_verified_milestone", claim["reasons"])
        self.assertFalse(claim["promotion_allowed"])
        self.assertFalse(claim["live_order_allowed"])

    def test_reconciliation_audit_uses_certified_replacement_summary(self):
        index = {
            "ok": True,
            "verified_through_count": 1,
            "target_count": 1,
            "replacements": {
                "HREPLAY-1": _replacement("HREPLAY-1", 5.0),
            },
            "blockers": [],
        }
        source_row = _row("HREPLAY-1", "operator")

        state, score_gate = stock_app._ai_tournament_effective_reconciliation_state(
            source_row,
            certified_index=index,
        )

        self.assertTrue(score_gate["score_allowed"])
        self.assertTrue(state["certified_replacement"])
        self.assertEqual("passed", state["status"])
        self.assertEqual(10, state["checked_count"])
        self.assertEqual("HREPLAY-19", state["certified_replay_id"])

    def test_partial_certification_never_issues_official_champion(self):
        index = {
            "ok": True,
            "verified_through_count": 25,
            "target_count": 757,
            "replacements": {
                "HREPLAY-1": _replacement("HREPLAY-1", 5.0),
            },
            "blockers": [],
        }
        record = {
            "id": "AITOUR-1",
            "rankings": [
                _row("HREPLAY-1", "operator"),
                _row("HREPLAY-2", "researcher"),
            ],
            "champion": _row("HREPLAY-2", "researcher"),
            "errors": [],
        }

        result = stock_app._enrich_ai_tournament_record(
            record,
            certified_index=index,
        )

        self.assertFalse(result["record_score_allowed"])
        self.assertEqual({}, result["official_champion"])
        self.assertEqual({}, result["champion"])
        self.assertEqual(1, result["score_certified_count"])
        self.assertEqual(1, result["score_blocked_count"])
        self.assertTrue(result["rankings"][0]["score_allowed"])
        self.assertIsNone(result["rankings"][0]["official_rank"])
        self.assertFalse(result["rankings"][1]["score_allowed"])

    def test_complete_certification_recomputes_rank_from_verified_returns(self):
        index = {
            "ok": True,
            "verified_through_count": 25,
            "target_count": 757,
            "replacements": {
                "HREPLAY-1": _replacement("HREPLAY-1", 5.0),
                "HREPLAY-2": _replacement("HREPLAY-2", 12.0),
            },
            "blockers": [],
        }
        first = _row("HREPLAY-1", "operator")
        second = _row("HREPLAY-2", "researcher")
        first["rank"] = 1
        second["rank"] = 2
        record = {
            "id": "AITOUR-2",
            "rankings": [first, second],
            "champion": first,
            "errors": [],
        }

        result = stock_app._enrich_ai_tournament_record(
            record,
            certified_index=index,
        )

        self.assertTrue(result["record_score_allowed"])
        self.assertEqual("researcher", result["official_champion"]["contestant_id"])
        ranks = {
            row["contestant_id"]: row["official_rank"]
            for row in result["rankings"]
        }
        self.assertEqual({"operator": 2, "researcher": 1}, ranks)
        self.assertEqual(12.0, result["official_champion"]["official_total_return_pct"])
        self.assertEqual(999.0, result["reference_champion"]["total_return_pct"])

    def test_reference_champion_symbols_do_not_leak_into_next_session_plan(self):
        candidate = {
            "symbol": "005930",
            "name": "삼성전자",
            "score": 80.0,
            "amount": 100_000_000_000,
            "risk_gate_status": "PASSED",
            "reasons": ["공통 스냅샷 확인"],
        }
        reference_only_league = {
            "id": "AITOUR-REFERENCE-ONLY",
            "champion": {},
            "official_champion": {},
            "reference_champion": {
                "contestant_id": "operator",
                "selected_symbols": ["005930"],
            },
            "record_score_allowed": False,
        }
        with (
            patch.object(stock_app, "latest_next_session_live_watch_plans", return_value=[]),
            patch.object(stock_app, "latest_ai_internal_league_record", return_value=reference_only_league),
            patch.object(stock_app, "_next_kr_trading_date", return_value="2026-07-16"),
            patch.object(stock_app, "_append_jsonl"),
            patch.object(stock_app, "_compact_jsonl"),
            patch.object(stock_app.JOURNAL, "add"),
        ):
            plan = stock_app.build_next_session_live_watch_plan(
                candidates=[candidate],
                force=True,
                source="unit-test",
            )

        self.assertNotIn(
            "AI 내부 리그 우승/상위 전략의 관심 종목군",
            plan["candidates"][0]["reasons"],
        )
        self.assertEqual({}, plan["internal_league_reference"].get("winner") or {})

    def test_mcp_exposes_read_only_tournament_standings(self):
        tool_names = {str(tool.get("name")) for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_tournament_standings", tool_names)
        payload = {
            "ok": True,
            "score_gate": {
                "deep_verified_replay_count": 25,
                "target_replay_count": 757,
                "live_order_allowed": False,
            },
        }
        with patch.object(mcp_server, "_http_json", return_value=payload) as http_json:
            result = mcp_server._call_tool(
                "codexstock_tournament_standings",
                {"limit": 30},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/ai-tournament/standings",
            {"limit": 30},
        )
        self.assertFalse(result["isError"])

    def test_standings_cache_collapses_repeated_reads_for_same_evidence(self):
        payload = {"ok": True, "standings": [], "score_gate": {"live_order_allowed": False}}
        with (
            patch.object(stock_app, "AI_TOURNAMENT_STANDINGS_CACHE", {}),
            patch.object(
                stock_app,
                "_ai_tournament_standings_source_signature",
                return_value=("same-evidence",),
            ),
            patch.object(
                stock_app,
                "_build_ai_tournament_standings",
                return_value=payload,
            ) as build,
        ):
            first = stock_app.ai_tournament_standings(30)
            second = stock_app.ai_tournament_standings(30)

        build.assert_called_once_with(30)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual("memory_evidence_signature", second["cache_source"])

    def test_standings_cache_keeps_multiple_query_limits(self):
        with (
            patch.object(stock_app, "AI_TOURNAMENT_STANDINGS_CACHE", {}),
            patch.object(
                stock_app,
                "_ai_tournament_standings_source_signature",
                side_effect=lambda limit: ("same-evidence", limit),
            ),
            patch.object(
                stock_app,
                "_build_ai_tournament_standings",
                side_effect=lambda limit: {"ok": True, "limit": limit},
            ) as build,
        ):
            first_30 = stock_app.ai_tournament_standings(30)
            first_100 = stock_app.ai_tournament_standings(100)
            second_30 = stock_app.ai_tournament_standings(30)

        self.assertEqual(2, build.call_count)
        self.assertFalse(first_30["cache_hit"])
        self.assertFalse(first_100["cache_hit"])
        self.assertTrue(second_30["cache_hit"])

    def test_activity_standings_remain_visible_during_official_refresh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "career.jsonl"
            ledger_path.write_text(
                json.dumps(
                    {
                        "record_id": "AITOUR-1",
                        "generated_at": "2026-07-17T12:00:00+09:00",
                        "rankings": [
                            {
                                "contestant_id": "operator",
                                "display_name": "self · 매매 직원",
                                "rank": 1,
                                "return_pct": 3.5,
                                "max_drawdown_pct": -1.2,
                                "trade_count": 7,
                                "strategy_name": "momentum",
                                "official_claim_eligible": False,
                            },
                            {
                                "contestant_id": "researcher",
                                "display_name": "헤헤 · 연구 직원",
                                "rank": 2,
                                "return_pct": 2.0,
                                "max_drawdown_pct": -0.8,
                                "trade_count": 5,
                                "strategy_name": "swing",
                                "official_claim_eligible": False,
                            },
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            with (
                patch.object(stock_app, "AI_STAFF_CAREER_LEDGER_FILE", ledger_path),
                patch.object(stock_app, "load_ai_staff_long_horizon_benchmark", return_value={"staff": []}),
                patch.object(stock_app, "ai_tournament_contestants", return_value=[]),
            ):
                result = stock_app._build_ai_tournament_activity_standings()

        self.assertTrue(result["ok"])
        self.assertFalse(result["refreshing"])
        self.assertEqual(1, result["run_count"])
        self.assertEqual(2, len(result["standings"]))
        self.assertEqual(1, result["standings"][0]["activity_wins"])
        self.assertEqual("career_activity_snapshot", result["summary_mode"])

    def test_responsive_standings_uses_fast_fallback_without_deep_build(self):
        fallback = {"ok": True, "standings": [{"contestant_id": "operator"}], "refreshing": True}
        with (
            patch.object(stock_app, "AI_TOURNAMENT_STANDINGS_CACHE", {}),
            patch.object(stock_app, "AI_TOURNAMENT_STANDINGS_LAST_GOOD", None),
            patch.object(stock_app, "AI_TOURNAMENT_STANDINGS_REFRESH_STATE", {"running": True}),
            patch.object(stock_app, "_ai_tournament_standings_source_signature", return_value=("new",)),
            patch.object(stock_app, "_start_ai_tournament_standings_refresh", return_value=False) as refresh_start,
            patch.object(stock_app, "_build_ai_tournament_activity_standings", return_value=fallback) as fast_build,
            patch.object(stock_app, "_build_ai_tournament_standings") as deep_build,
        ):
            result = stock_app.ai_tournament_standings_responsive(100)

        fast_build.assert_called_once_with()
        deep_build.assert_not_called()
        refresh_start.assert_not_called()
        self.assertEqual("career_ledger_fast_fallback", result["cache_source"])
        self.assertEqual(1, len(result["standings"]))


if __name__ == "__main__":
    unittest.main()

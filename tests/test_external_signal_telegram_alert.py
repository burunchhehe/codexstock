import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.stock_suite_app import (
    _build_external_signal_news_verification,
    _external_signal_alert_items,
    _external_signal_context_coverage,
    _external_signal_promotion_audit,
    _enqueue_external_context_verification_requests,
    _normalize_external_signal_report,
    _normalize_external_signal_sources,
    _queue_external_signal_telegram_alert,
    build_external_signal_telegram_text,
)


class ExternalSignalTelegramAlertTests(unittest.TestCase):
    def _report(self):
        return {
            "generated_at": "2026-07-14T16:30:00+09:00",
            "market_context": [
                {
                    "context_id": "CTX-FLOW-1",
                    "category": "capital_flows",
                    "headline": "외국인 주식자금 순유출 확대",
                    "summary": "글로벌 위험회피와 환율 영향을 교차확인해야 함",
                    "severity": "high",
                    "confidence": 0.9,
                    "source_count": 3,
                    "risk_flags": [],
                }
            ],
            "signals": [
                {
                    "symbol": "000660",
                    "name": "SK하이닉스",
                    "theme": "AI 반도체",
                    "urgency": "urgent",
                    "confidence": 0.82,
                    "source_count": 12,
                    "evidence_summary": "여러 출처에서 반복 언급됨",
                    "risk_flags": ["원출처 미확인"],
                },
                {
                    "symbol": "042660",
                    "name": "한화오션",
                    "theme": "조선",
                    "urgency": "watch",
                    "confidence": 0.7,
                    "source_count": 8,
                    "evidence_summary": "수주 관련 관심 증가",
                    "risk_flags": [],
                },
            ],
            "urgent_triggers": [
                {
                    "type": "multi_source_spike",
                    "severity": "high",
                    "theme": "AI 반도체",
                    "symbols": ["000660"],
                    "reason": "짧은 시간 안에 여러 출처에서 반복",
                },
                {
                    "type": "datalab_spike",
                    "severity": "watch",
                    "theme": "원전",
                    "symbols": [],
                    "reason": "검색 관심도 급증",
                },
            ],
        }

    def test_selects_only_urgent_and_relevant_trigger_items(self):
        items = _external_signal_alert_items(self._report())
        self.assertEqual(
            ["외국인·글로벌 자금흐름", "AI 반도체", "원전"],
            [item["theme"] for item in items],
        )

    def test_text_is_concise_and_explicitly_verification_only(self):
        text = build_external_signal_telegram_text(self._report())
        self.assertIn("[외부정보·검증중]", text)
        self.assertIn("외국인 주식자금 순유출 확대", text)
        self.assertIn("SK하이닉스(000660)", text)
        self.assertIn("검색 관심도 급증", text)
        self.assertIn("실제 주문하지 않습니다", text)
        self.assertLessEqual(len(text), 1200)

    def test_context_coverage_exposes_missing_market_information(self):
        coverage = _external_signal_context_coverage(self._report()["market_context"])
        self.assertEqual("INCOMPLETE", coverage["status"])
        self.assertEqual(16.7, coverage["coverage_pct"])
        self.assertIn("경제일정", coverage["missing_labels"])
        self.assertIn("환율", coverage["missing_labels"])

    def test_optional_market_context_is_normalized_without_granting_order_authority(self):
        context = {
            **self._report()["market_context"][0],
            "detected_at": "2026-07-14T16:29:00+09:00",
            "markets": ["KR", "US"],
            "symbols": [],
            "impact_channels": ["환율", "외국인 수급"],
            "sources": [{"type": "news", "name": "공식자료", "title": "자금 흐름", "url": "https://example.com/flow"}],
            "external_engine_decision": "VERIFY_ONLY",
            "live_order_allowed": False,
        }
        raw = {
            "schema": "codexstock_external_signal_report_v1",
            "generated_at": "2026-07-14T16:30:00+09:00",
            "report_type": "urgent",
            "report_slot": "market_close",
            "engine": {"name": "test", "version": "1"},
            "collection_window": {},
            "safety": {
                "decision_scope": "information_only",
                "external_engine_decision": "VERIFY_ONLY",
                "live_order_allowed": False,
                "requires_codexstock_validation": True,
            },
            "signals": [],
            "urgent_triggers": [],
            "market_context": [context],
        }
        normalized, errors = _normalize_external_signal_report(raw)
        self.assertEqual([], errors)
        self.assertIsNotNone(normalized)
        self.assertFalse(normalized["market_context"][0]["live_order_allowed"])
        self.assertEqual("INCOMPLETE", normalized["context_coverage"]["status"])

    def test_declared_source_count_cannot_inflate_independent_evidence(self):
        raw = {
            "schema": "codexstock_external_signal_report_v1",
            "generated_at": "2026-07-15T03:19:21+09:00",
            "report_type": "urgent",
            "report_slot": "pre_market",
            "engine": {"name": "test", "version": "1"},
            "collection_window": {},
            "safety": {
                "decision_scope": "information_only",
                "external_engine_decision": "VERIFY_ONLY",
                "live_order_allowed": False,
                "requires_codexstock_validation": True,
            },
            "signals": [
                {
                    "signal_id": "SIG-SOURCE-COUNT-1",
                    "detected_at": "2026-07-15T03:18:00+09:00",
                    "symbol": "005930",
                    "name": "삼성전자",
                    "market": "KR",
                    "theme": "반도체",
                    "sentiment": "positive",
                    "urgency": "high",
                    "keywords": ["반도체"],
                    "source_count": 137,
                    "sources": [
                        {"name": "A", "title": "기사 1", "url": "https://www.media-a.co.kr/article/1"},
                        {"name": "A", "title": "기사 2", "url": "https://m.media-a.co.kr/article/2"},
                        {"name": "A", "title": "기사 1 중복", "url": "https://www.media-a.co.kr/article/1#body"},
                        {"name": "B", "title": "기사 3", "url": "https://news.media-b.com/story/3"},
                        {"name": "위험", "title": "잘못된 URL", "url": "javascript:alert(1)"},
                        {"name": "URL 없음", "title": "출처 주장만 있음"},
                    ],
                    "evidence_summary": "외부 엔진이 반복 언급을 주장함",
                    "confidence": 0.95,
                    "freshness_minutes": 1,
                    "risk_flags": [],
                    "requested_codexstock_checks": ["원문 확인"],
                    "external_engine_decision": "VERIFY_ONLY",
                    "live_order_allowed": False,
                }
            ],
            "urgent_triggers": [],
            "market_context": [],
        }

        normalized, errors = _normalize_external_signal_report(raw)

        self.assertEqual([], errors)
        signal = normalized["signals"][0]
        self.assertEqual(137, signal["reported_source_count"])
        self.assertEqual(5, signal["attached_source_count"])
        self.assertEqual(3, signal["valid_source_url_count"])
        self.assertEqual(2, signal["source_count"])
        self.assertEqual(["media-a.co.kr", "media-b.com"], signal["independent_source_domains"])
        self.assertTrue(signal["multi_source_evidence"])
        self.assertTrue(signal["source_count_capped"])
        self.assertEqual(1, normalized["summary"]["source_count_inflation_blocked_count"])
        alert = _external_signal_alert_items(normalized)[0]
        self.assertEqual(2, alert["source_count"])

    def test_original_body_evidence_requires_hash_id_and_matching_domain(self):
        sources, evidence = _normalize_external_signal_sources(
            [
                {
                    "name": "A",
                    "title": "A headline",
                    "url": "https://news.media-a.co.kr/article/1",
                    "original_evidence": {
                        "canonical_url": "https://www.media-a.co.kr/article/1",
                        "raw_item_id": "a" * 24,
                        "body_char_count": 1200,
                        "body_hash": "b" * 24,
                        "fetch_status": "FULL_TEXT_FETCHED",
                        "body_included": False,
                    },
                },
                {
                    "name": "B",
                    "title": "B headline",
                    "url": "https://media-b.com/article/2",
                    "original_evidence": {
                        "canonical_url": "https://different.test/article/2",
                        "raw_item_id": "c" * 24,
                        "body_char_count": 900,
                        "body_hash": "not-a-hash",
                        "fetch_status": "FULL_TEXT_FETCHED",
                        "body_included": False,
                    },
                },
            ]
        )

        self.assertEqual(2, evidence["independent_source_domain_count"])
        self.assertEqual(1, evidence["original_body_evidence_count"])
        self.assertTrue(evidence["original_body_evidence"])
        self.assertTrue(sources[0]["original_evidence"]["body_evidence_attested"])
        self.assertFalse(sources[1]["original_evidence"]["body_evidence_attested"])

    def test_source_lineage_contract_exposes_all_audit_fields(self):
        sources, evidence = _normalize_external_signal_sources(
            [
                {
                    "type": "news",
                    "name": "Publisher A",
                    "title": "Material event",
                    "url": "https://publisher-a.test/article/1",
                    "published_at": "2026-07-15T05:00:00+09:00",
                    "fetched_at": "2026-07-15T05:01:00+09:00",
                    "primary_or_secondary": "SECONDARY",
                    "relevance_score": 0.93,
                    "original_evidence": {
                        "canonical_url": "https://publisher-a.test/article/1",
                        "raw_item_id": "a" * 24,
                        "body_char_count": 1200,
                        "body_hash": "b" * 24,
                        "fetch_status": "FULL_TEXT_FETCHED",
                        "body_included": False,
                    },
                }
            ],
            freshness_minutes=60,
        )

        source = sources[0]
        for field in evidence["lineage_contract_fields"]:
            self.assertIn(field, source)
        self.assertTrue(source["lineage_complete"])
        self.assertTrue(source["content_hash"].startswith("sha256:"))
        self.assertTrue(source["duplicate_group"].startswith("sha256:"))
        self.assertTrue(source["expiry_at"])
        self.assertTrue(evidence["source_lineage_complete"])

    @patch("app.stock_suite_app._dart_disclosure_matches_news", return_value=(True, ["contract"], 0))
    @patch("app.stock_suite_app._news_material_tags", return_value={"contract"})
    @patch("app.stock_suite_app.INTEGRATIONS.dart_disclosures")
    @patch("app.stock_suite_app.load_dart_corp_code_map")
    def test_external_news_gate_binds_original_multi_source_and_dart(
        self, corp_map, disclosures, _material_tags, _match
    ):
        corp_map.return_value = {
            "005930": {"stock_code": "005930", "corp_code": "00126380", "name": "Samsung"}
        }
        disclosures.return_value = {
            "items": [
                {"report_nm": "Supply contract", "rcept_dt": "20260715", "rcept_no": "20260715000001"}
            ]
        }
        sources, source_evidence = _normalize_external_signal_sources(
            [
                {
                    "name": "A",
                    "title": "Supply contract A",
                    "url": "https://media-a.test/a",
                    "published_at": "2026-07-15T05:00:00+09:00",
                    "fetched_at": "2026-07-15T05:02:00+09:00",
                    "expiry_at": "2026-07-15T06:00:00+09:00",
                    "primary_or_secondary": "SECONDARY",
                    "relevance_score": 0.96,
                    "original_evidence": {
                        "canonical_url": "https://media-a.test/a",
                        "raw_item_id": "a" * 24,
                        "body_char_count": 1000,
                        "body_hash": "b" * 24,
                        "fetch_status": "FULL_TEXT_FETCHED",
                        "body_included": False,
                    },
                },
                {
                    "name": "B",
                    "title": "Supply contract B",
                    "url": "https://media-b.test/b",
                    "published_at": "2026-07-15T05:01:00+09:00",
                    "fetched_at": "2026-07-15T05:03:00+09:00",
                    "expiry_at": "2026-07-15T06:01:00+09:00",
                    "primary_or_secondary": "SECONDARY",
                    "relevance_score": 0.91,
                    "original_evidence": {
                        "canonical_url": "https://media-b.test/b",
                        "raw_item_id": "c" * 24,
                        "body_char_count": 900,
                        "body_hash": "d" * 24,
                        "fetch_status": "FULL_TEXT_FETCHED",
                        "body_included": False,
                    },
                },
            ]
        )
        signal = {
            "signal_id": "SIG-EVIDENCE-1",
            "symbol": "005930",
            "name": "Samsung",
            "theme": "contract",
            "evidence_summary": "supply contract",
            "sources": sources,
            **source_evidence,
        }

        result = _build_external_signal_news_verification({"signals": [signal]})["SIG-EVIDENCE-1"]

        self.assertEqual("EVIDENCE_READY_FOR_STAGE2", result["status"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(1, result["official_disclosure_match_count"])
        self.assertTrue(result["checks"]["source_lineage_bundle_passed"])
        self.assertEqual(2, result["source_lineage_complete_count"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_promotion_audit_blocks_missing_news_evidence_even_after_stage2(self):
        digest = "a" * 64
        request = {
            "status": "STAGE2_PASSED",
            "stage2_result_gate_passed": True,
            "contract_hash": digest,
            "contract_hash_echo": digest,
            "contract_schema_version_echo": "stage2-handoff-contract.v1.40",
            "stage2_snapshot_id": "snapshot-1",
            "required_snapshot_id_echo": "snapshot-1",
            "stage2_dataset_hash": digest,
            "dataset_hash_echo": digest,
            "validation_grade": "A",
            "validation_evidence": {
                "return_reconciliation_passed": True,
                "exit_reason_alignment_passed": True,
                "cost_profile_passed": True,
                "unit_currency_passed": True,
                "no_live_order_passed": True,
            },
            "news_verification": {
                "status": "EVIDENCE_BLOCKED",
                "checks": {
                    "original_body_evidence_passed": False,
                    "multi_source_evidence_passed": True,
                    "official_disclosure_gate_passed": True,
                },
            },
        }

        audit = _external_signal_promotion_audit(request)

        self.assertFalse(audit["eligible"])
        self.assertIn("original_body_evidence_not_passed", audit["blockers"])

    def test_market_context_enters_separate_verify_only_queue(self):
        report = self._report()
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.EXTERNAL_CONTEXT_VERIFICATION_QUEUE_FILE",
            Path(directory) / "context_queue.jsonl",
        ):
            count = _enqueue_external_context_verification_requests(
                report,
                received_at="2026-07-14T16:31:00+09:00",
                source="test",
                report_signature="sig-1",
            )
            duplicate_count = _enqueue_external_context_verification_requests(
                report,
                received_at="2026-07-14T16:32:00+09:00",
                source="test",
                report_signature="sig-1",
            )
            self.assertEqual(1, count)
            self.assertEqual(0, duplicate_count)
            row = __import__("json").loads((Path(directory) / "context_queue.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("PENDING_CONTEXT_CROSS_CHECKS", row["status"])
            self.assertFalse(row["score_allowed"])
            self.assertFalse(row["live_order_allowed"])

    @patch("app.stock_suite_app.OPS.queue_telegram")
    def test_queue_uses_dedicated_type_and_never_allows_live_order(self, queue_telegram):
        queue_telegram.return_value = {"id": "TG-1", "status": "queued"}
        result = _queue_external_signal_telegram_alert(
            self._report(), report_signature="abc123", source="external-info-scout"
        )
        self.assertEqual("queued", result["status"])
        kwargs = queue_telegram.call_args.kwargs
        self.assertEqual("external_signal_alert", kwargs["message_type"])
        self.assertFalse(kwargs["metadata"]["live_order_allowed"])
        self.assertTrue(kwargs["metadata"]["verification_required"])

    @patch("app.stock_suite_app.OPS.queue_telegram")
    def test_non_urgent_report_does_not_enter_outbox(self, queue_telegram):
        report = {"signals": [], "urgent_triggers": []}
        result = _queue_external_signal_telegram_alert(
            report, report_signature="none", source="external-info-scout"
        )
        self.assertEqual("not_urgent", result["status"])
        queue_telegram.assert_not_called()


if __name__ == "__main__":
    unittest.main()

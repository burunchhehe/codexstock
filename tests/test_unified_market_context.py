import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.stock_suite_app import (
    _annotate_market_context_freshness,
    _market_news_context_rows,
    _resolve_original_via_bing_news,
    build_market_news_evidence,
    build_unified_market_context_snapshot,
    score_news_items,
    unified_market_context_telegram_lines,
)


class UnifiedMarketContextTests(unittest.TestCase):
    def test_bing_locator_requires_title_and_publisher_domain_match(self):
        rss = """<?xml version="1.0" encoding="utf-8"?>
        <rss version="2.0"><channel>
          <item>
            <title>반도체 공급계약 확대 발표</title>
            <link>https://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fwrong.test%2Farticle%2F1</link>
          </item>
          <item>
            <title>반도체 공급계약 확대 발표</title>
            <link>https://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fmedia-a.co.kr%2Farticle%2F1</link>
          </item>
        </channel></rss>""".encode("utf-8")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self, limit=-1):
                return rss[:limit] if limit and limit > 0 else rss

        with patch("app.stock_suite_app.urlopen", return_value=FakeResponse()):
            original_url, error = _resolve_original_via_bing_news(
                "https://www.media-a.co.kr",
                "반도체 공급계약 확대 발표 - 매체A",
                timeout=1.0,
            )

        self.assertEqual("https://media-a.co.kr/article/1", original_url)
        self.assertEqual("", error)

    def test_news_cross_source_repetition_is_not_treated_as_verified(self):
        report = {
            "issues": [
                {
                    "name": "미국장",
                    "items": [
                        {"title": "미국 CPI 예상 하회, 나스닥 급등 - 매체A", "source": "매체A", "link": "https://a.test/1"},
                        {"title": "미국 CPI 예상 하회에 나스닥 급등 - 매체B", "source": "매체B", "link": "https://b.test/1"},
                    ],
                }
            ]
        }
        rows = _market_news_context_rows(report)
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]["corroborated"])
        self.assertEqual(2, rows[0]["corroborating_source_count"])
        self.assertEqual(["매체A", "매체B"], rows[0]["corroborating_sources"])
        self.assertFalse(rows[0]["verified"])

    def test_unverified_headline_score_is_diagnostic_only(self):
        pending = score_news_items(
            [{"title": "대규모 수주 계약", "verified": False, "score_allowed": False}]
        )
        verified = score_news_items(
            [{"title": "대규모 수주 계약", "verified": True, "score_allowed": True}]
        )

        self.assertEqual(2, pending["raw_score"])
        self.assertEqual(0, pending["score"])
        self.assertEqual("검증 대기", pending["stance"])
        self.assertEqual(2, verified["score"])
        self.assertEqual("verified_and_score_allowed_only", verified["score_policy"])

    def test_preserves_source_time_currency_and_verification_boundary(self):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        today_compact = now.strftime("%Y%m%d")
        current_month = now.strftime("%Y%m")
        today = now.date().isoformat()
        macro = {
            "ecos": {
                "source": "BOK ECOS",
                "rows": [
                    {"id": "usd_krw", "name": "원/달러 환율", "ok": True, "value": 1504.9, "time": today_compact, "unit": "원"},
                    {"id": "base_rate", "name": "한국은행 기준금리", "ok": True, "value": 2.5, "time": current_month, "unit": "연%"},
                ],
            },
            "fred": {"source": "FRED", "rows": []},
        }
        regime = {
            "assets": [
                {"symbol": "SPY", "label": "S&P500", "return_1d_pct": -0.77, "latest_date": today, "source": "Yahoo chart", "price": 749.17}
            ]
        }
        flow = {
            "ok": True,
            "source": "kis_foreign_institution_rank",
            "items": [
                {"symbol": "000660", "name": "SK하이닉스", "foreign_net_amount": 520_336_000_000, "institution_net_amount": 665_724_000_000, "amount_unit": "KRW"}
            ],
        }
        inbox = {
            "report": {
                "market_context": [
                    {"context_id": "cal-1", "category": "economic_calendar", "headline": "미국 CPI 발표", "verified": False}
                ]
            }
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.UNIFIED_MARKET_CONTEXT_CACHE_FILE", Path(directory) / "context.json"
        ), patch(
            "app.stock_suite_app.EXTERNAL_CONTEXT_COLLECTION_REQUEST_FILE", Path(directory) / "request.json"
        ), patch("app.stock_suite_app.external_signal_inbox_status", return_value=inbox), patch(
            "app.stock_suite_app.INTEGRATIONS.macro_snapshot", return_value=macro
        ), patch("app.stock_suite_app.build_market_regime", return_value=regime), patch(
            "app.stock_suite_app.INTEGRATIONS.kis_foreign_institution_rank", return_value=flow
        ), patch(
            "app.stock_suite_app.INTEGRATIONS.fred_release_dates", return_value={"ok": False, "rows": []}
        ), patch(
            "app.stock_suite_app.build_overnight_issue_report", return_value={"ok": True, "issues": [], "source": "Google News RSS"}
        ):
            result = build_unified_market_context_snapshot(force=True)

        fx = result["categories"]["fx_rates"]["rows"][0]
        self.assertEqual(1504.9, fx["value"])
        self.assertEqual("원", fx["unit"])
        self.assertEqual(today_compact, fx["observed_at"])
        self.assertEqual("BOK ECOS", fx["source"])
        self.assertEqual("FRESH", fx["freshness_state"])
        self.assertTrue(fx["fresh_verified"])
        capital = result["categories"]["capital_flows"]["rows"][0]
        self.assertEqual("KRW", capital["unit"])
        self.assertEqual("KIS 장중 잠정 순매수 상위", capital["basis"])
        self.assertEqual("MISSING", result["categories"]["economic_calendar"]["status"])
        self.assertEqual([], result["categories"]["economic_calendar"]["rows"])
        self.assertEqual(1, len(result["pending_external_context"]))
        self.assertEqual("cal-1", result["pending_external_context"][0]["context_id"])
        self.assertEqual(
            "external_decision_not_verify_only",
            result["pending_external_context"][0]["verification_basis"],
        )
        self.assertIn("시장 속보", result["coverage"]["missing_labels"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])
        self.assertEqual("codexstock_unified_market_context_v2", result["schema"])
        request = result["external_collection_request"]
        self.assertEqual("COLLECT_INFORMATION_ONLY", request["action"])
        self.assertFalse(request["safety"]["score_allowed"])
        self.assertFalse(request["safety"]["live_order_allowed"])
        self.assertEqual(6, request["requested_category_count"])
        economic_request = next(
            row for row in request["requested_categories"] if row["category"] == "economic_calendar"
        )
        self.assertEqual("present_but_failed_codexstock_validation", economic_request["reason"])
        self.assertIn("event_at", economic_request["required_fields"])
        self.assertTrue(economic_request["acceptance_contract"]["must_not_be_general_news_or_sports_article"])

        lines = unified_market_context_telegram_lines(result)
        joined = "\n".join(lines)
        self.assertIn(f"원/달러 환율 +1504.9원({today_compact})", joined)
        self.assertIn("외국인 SK하이닉스 +5,203억원", joined)
        self.assertNotIn(inbox["report"]["market_context"][0]["headline"], joined)

    def test_freshness_annotation_distinguishes_fresh_stale_and_scheduled(self):
        now = datetime(2026, 7, 14, 12, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        rows = [
            {"observed_at": (now - timedelta(hours=2)).isoformat(), "verified": True},
            {"observed_at": (now - timedelta(days=8)).isoformat(), "verified": True},
            {"observed_at": (now + timedelta(days=1)).date().isoformat(), "verified": True},
            {"observed_at": "not-a-date", "verified": True},
        ]

        _annotate_market_context_freshness("global_markets", rows, now=now)

        self.assertEqual("FRESH", rows[0]["freshness_state"])
        self.assertTrue(rows[0]["fresh_verified"])
        self.assertEqual("STALE", rows[1]["freshness_state"])
        self.assertFalse(rows[1]["fresh_verified"])
        self.assertEqual("SCHEDULED", rows[2]["freshness_state"])
        self.assertTrue(rows[2]["fresh_verified"])
        self.assertEqual("UNKNOWN", rows[3]["freshness_state"])
        self.assertFalse(rows[3]["fresh_verified"])

    def test_verified_external_economic_calendar_can_complete_decision_context(self):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        today = now.date().isoformat()
        macro = {
            "ecos": {
                "source": "BOK ECOS",
                "rows": [
                    {"id": "usd_krw", "name": "USD/KRW", "ok": True, "value": 1380.0, "time": today, "unit": "KRW"},
                    {"id": "base_rate", "name": "Base rate", "ok": True, "value": 2.5, "time": today, "unit": "%"},
                ],
            },
            "fred": {"source": "FRED", "rows": []},
        }
        regime = {
            "assets": [
                {"symbol": "SPY", "label": "S&P500", "return_1d_pct": 0.4, "latest_date": today, "source": "Yahoo chart", "price": 700.0}
            ]
        }
        flow = {
            "ok": True,
            "source": "kis_foreign_institution_rank",
            "items": [
                {"symbol": "000660", "name": "SK hynix", "foreign_net_amount": 100_000_000_000, "institution_net_amount": 50_000_000_000, "amount_unit": "KRW"}
            ],
        }
        inbox = {
            "report": {
                "generated_at": now.isoformat(),
                "market_context": [
                    {
                        "context_id": "cal-cpi",
                        "category": "economic_calendar",
                        "headline": "US CPI release",
                        "summary": "Scheduled high impact inflation release.",
                        "event_name": "US CPI",
                        "event_at": (now + timedelta(hours=3)).isoformat(),
                        "timezone": "America/New_York",
                        "severity": "high",
                        "detected_at": now.isoformat(),
                        "markets": ["US", "KR"],
                        "symbols": [],
                        "impact_channels": ["inflation", "rates"],
                        "confidence": 0.92,
                        "source_count": 2,
                        "sources": [
                            {"name": "BLS calendar", "url": "https://www.bls.gov/schedule/news_release/cpi.htm", "title": "CPI", "published_at": today},
                            {"name": "FRED calendar", "url": "https://fred.stlouisfed.org/releases/calendar", "title": "Releases", "published_at": today},
                        ],
                        "risk_flags": [],
                        "external_engine_decision": "VERIFY_ONLY",
                        "live_order_allowed": False,
                    }
                ],
            }
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.UNIFIED_MARKET_CONTEXT_CACHE_FILE", Path(directory) / "context.json"
        ), patch(
            "app.stock_suite_app.EXTERNAL_CONTEXT_COLLECTION_REQUEST_FILE", Path(directory) / "request.json"
        ), patch("app.stock_suite_app.external_signal_inbox_status", return_value=inbox), patch(
            "app.stock_suite_app.INTEGRATIONS.macro_snapshot", return_value=macro
        ), patch("app.stock_suite_app.build_market_regime", return_value=regime), patch(
            "app.stock_suite_app.INTEGRATIONS.kis_foreign_institution_rank", return_value=flow
        ), patch(
            "app.stock_suite_app.INTEGRATIONS.fred_release_dates", return_value={"ok": False, "rows": []}
        ), patch(
            "app.stock_suite_app.build_overnight_issue_report", return_value={"ok": True, "issues": [], "source": "Google News RSS"}
        ):
            result = build_unified_market_context_snapshot(force=True)

        calendar = result["categories"]["economic_calendar"]
        self.assertEqual("VERIFIED_FRESH_INTERNAL", calendar["status"])
        self.assertTrue(calendar["rows"][0]["fresh_verified"])
        self.assertEqual("external_calendar_multi_source_verified", calendar["rows"][0]["verification_basis"])
        self.assertTrue(result["coverage"]["decision_context_ready"])
        self.assertEqual([], result["coverage"]["decision_context_blockers"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_empty_official_economic_calendar_is_neutral_verified_context_only(self):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        today = now.date().isoformat()
        macro = {
            "ecos": {
                "source": "BOK ECOS",
                "rows": [
                    {"id": "usd_krw", "name": "USD/KRW", "ok": True, "value": 1380.0, "time": today, "unit": "KRW"},
                    {"id": "base_rate", "name": "Base rate", "ok": True, "value": 2.5, "time": today, "unit": "%"},
                ],
            },
            "fred": {"source": "FRED", "rows": []},
        }
        regime = {
            "assets": [
                {"symbol": "SPY", "label": "S&P500", "return_1d_pct": 0.4, "latest_date": today, "source": "Yahoo chart", "price": 700.0}
            ]
        }
        flow = {
            "ok": True,
            "source": "kis_foreign_institution_rank",
            "items": [
                {"symbol": "000660", "name": "SK hynix", "foreign_net_amount": 100_000_000_000, "institution_net_amount": 50_000_000_000, "amount_unit": "KRW"}
            ],
        }
        inbox = {
            "report": {
                "market_context": [
                    {"context_id": "bad-cal", "category": "economic_calendar", "headline": "football headline", "verified": False}
                ]
            }
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.UNIFIED_MARKET_CONTEXT_CACHE_FILE", Path(directory) / "context.json"
        ), patch(
            "app.stock_suite_app.EXTERNAL_CONTEXT_COLLECTION_REQUEST_FILE", Path(directory) / "request.json"
        ), patch("app.stock_suite_app.external_signal_inbox_status", return_value=inbox), patch(
            "app.stock_suite_app.INTEGRATIONS.macro_snapshot", return_value=macro
        ), patch("app.stock_suite_app.build_market_regime", return_value=regime), patch(
            "app.stock_suite_app.INTEGRATIONS.kis_foreign_institution_rank", return_value=flow
        ), patch(
            "app.stock_suite_app.INTEGRATIONS.fred_release_dates", return_value={"ok": False, "query_ok": True, "configured": True, "rows": []}
        ), patch(
            "app.stock_suite_app.build_overnight_issue_report", return_value={"ok": True, "issues": [], "source": "Google News RSS"}
        ):
            result = build_unified_market_context_snapshot(force=True)

        calendar = result["categories"]["economic_calendar"]
        self.assertEqual("VERIFIED_FRESH_INTERNAL", calendar["status"])
        self.assertEqual(1, calendar["fresh_verified_count"])
        row = calendar["rows"][0]
        self.assertEqual("VERIFIED_EMPTY_OFFICIAL", row["verification_status"])
        self.assertTrue(row["neutral_context_only"])
        self.assertFalse(row["score_allowed"])
        self.assertFalse(row["live_order_allowed"])
        self.assertEqual(1, len(result["pending_external_context"]))
        self.assertEqual("bad-cal", result["pending_external_context"][0]["context_id"])
        self.assertTrue(result["coverage"]["decision_context_ready"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_legacy_empty_fred_calendar_response_is_neutral_verified_context_only(self):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        today = now.date().isoformat()
        macro = {
            "ecos": {
                "source": "BOK ECOS",
                "rows": [
                    {"id": "usd_krw", "name": "USD/KRW", "ok": True, "value": 1380.0, "time": today, "unit": "KRW"},
                    {"id": "base_rate", "name": "Base rate", "ok": True, "value": 2.5, "time": today, "unit": "%"},
                ],
            },
            "fred": {"source": "FRED", "rows": []},
        }
        regime = {
            "assets": [
                {"symbol": "SPY", "label": "S&P500", "return_1d_pct": 0.4, "latest_date": today, "source": "Yahoo chart", "price": 700.0}
            ]
        }
        flow = {
            "ok": True,
            "source": "kis_foreign_institution_rank",
            "items": [
                {"symbol": "000660", "name": "SK hynix", "foreign_net_amount": 100_000_000_000, "institution_net_amount": 50_000_000_000, "amount_unit": "KRW"}
            ],
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.UNIFIED_MARKET_CONTEXT_CACHE_FILE", Path(directory) / "context.json"
        ), patch(
            "app.stock_suite_app.EXTERNAL_CONTEXT_COLLECTION_REQUEST_FILE", Path(directory) / "request.json"
        ), patch("app.stock_suite_app.external_signal_inbox_status", return_value={"report": {"market_context": []}}), patch(
            "app.stock_suite_app.INTEGRATIONS.macro_snapshot", return_value=macro
        ), patch("app.stock_suite_app.build_market_regime", return_value=regime), patch(
            "app.stock_suite_app.INTEGRATIONS.kis_foreign_institution_rank", return_value=flow
        ), patch(
            "app.stock_suite_app.INTEGRATIONS.fred_release_dates",
            return_value={"ok": False, "configured": True, "rows": [], "cached": False, "start": today, "end": today},
        ), patch(
            "app.stock_suite_app.build_overnight_issue_report", return_value={"ok": True, "issues": [], "source": "Google News RSS"}
        ):
            result = build_unified_market_context_snapshot(force=True)

        calendar = result["categories"]["economic_calendar"]
        self.assertEqual("VERIFIED_FRESH_INTERNAL", calendar["status"])
        self.assertEqual("VERIFIED_EMPTY_OFFICIAL", calendar["rows"][0]["verification_status"])
        self.assertTrue(calendar["rows"][0]["neutral_context_only"])
        self.assertFalse(calendar["rows"][0]["score_allowed"])
        self.assertFalse(calendar["rows"][0]["live_order_allowed"])
        self.assertTrue(result["coverage"]["decision_context_ready"])

    def test_normal_empty_kis_flow_rank_is_neutral_verified_context_only(self):
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        today = now.date().isoformat()
        macro = {
            "ecos": {
                "source": "BOK ECOS",
                "rows": [
                    {"id": "usd_krw", "name": "USD/KRW", "ok": True, "value": 1380.0, "time": today, "unit": "KRW"},
                    {"id": "base_rate", "name": "Base rate", "ok": True, "value": 2.5, "time": today, "unit": "%"},
                ],
            },
            "fred": {"source": "FRED", "rows": []},
        }
        regime = {
            "assets": [
                {"symbol": "SPY", "label": "S&P500", "return_1d_pct": 0.4, "latest_date": today, "source": "Yahoo chart", "price": 700.0}
            ]
        }
        flow = {
            "ok": False,
            "source": "kis_foreign_institution_rank",
            "items": [],
            "message": "정상처리 되었습니다.",
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.UNIFIED_MARKET_CONTEXT_CACHE_FILE", Path(directory) / "context.json"
        ), patch(
            "app.stock_suite_app.EXTERNAL_CONTEXT_COLLECTION_REQUEST_FILE", Path(directory) / "request.json"
        ), patch("app.stock_suite_app.external_signal_inbox_status", return_value={"report": {"market_context": []}}), patch(
            "app.stock_suite_app.INTEGRATIONS.macro_snapshot", return_value=macro
        ), patch("app.stock_suite_app.build_market_regime", return_value=regime), patch(
            "app.stock_suite_app.INTEGRATIONS.kis_foreign_institution_rank", return_value=flow
        ), patch(
            "app.stock_suite_app.INTEGRATIONS.fred_release_dates", return_value={"ok": False, "rows": []}
        ), patch(
            "app.stock_suite_app.build_overnight_issue_report", return_value={"ok": True, "issues": [], "source": "Google News RSS"}
        ):
            result = build_unified_market_context_snapshot(force=True)

        capital = result["categories"]["capital_flows"]
        self.assertEqual("VERIFIED_FRESH_INTERNAL", capital["status"])
        self.assertEqual(1, capital["fresh_verified_count"])
        row = capital["rows"][0]
        self.assertEqual("official_status", row["investor"])
        self.assertTrue(row["neutral_context_only"])
        self.assertFalse(row["score_allowed"])
        self.assertFalse(row["live_order_allowed"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_news_is_verified_only_when_dart_material_and_date_match(self):
        report = {
            "issues": [
                {
                    "name": "반도체",
                    "items": [
                        {
                            "title": "SK하이닉스 공급계약 체결 - 매체A",
                            "source": "매체A",
                            "link": "https://news.google.com/articles/a",
                            "source_home_url": "https://media-a.test",
                            "published": "Tue, 14 Jul 2026 01:00:00 GMT",
                        }
                    ],
                }
            ]
        }
        corp_map = {
            "000660": {"stock_code": "000660", "corp_code": "00164779", "name": "SK하이닉스"}
        }
        dart = {
            "configured": True,
            "items": [
                {
                    "report_nm": "단일판매ㆍ공급계약체결",
                    "rcept_dt": "20260714",
                    "rcept_no": "20260714000123",
                }
            ],
        }
        resolution = {
            "status": "RESOLVED_ORIGINAL_URL",
            "aggregator_url": "https://news.google.com/articles/a",
            "original_url": "https://media-a.test/article/1",
            "publisher_url": "https://media-a.test",
            "original_host": "media-a.test",
            "error": "",
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch(
            "app.stock_suite_app.load_dart_corp_code_map", return_value=corp_map
        ), patch(
            "app.stock_suite_app._resolve_news_original_url", return_value=resolution
        ), patch(
            "app.stock_suite_app.INTEGRATIONS.dart_disclosures", return_value=dart
        ):
            result = build_market_news_evidence(report=report, force=True)

        row = result["rows"][0]
        self.assertEqual("OFFICIAL_DISCLOSURE_CORROBORATED", row["evidence_grade"])
        self.assertTrue(row["verified"])
        self.assertTrue(row["score_allowed"])
        self.assertFalse(row["live_order_allowed"])
        self.assertEqual(1, row["official_disclosure_match_count"])
        self.assertEqual(
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260714000123",
            row["official_disclosure_matches"][0]["source_url"],
        )
        self.assertEqual(1, result["summary"]["verified_article_claim_count"])
        self.assertEqual(1, result["summary"]["official_disclosure_primary_count"])
        self.assertEqual("dart-applicability.v1", result["disclosure_evidence_contract_version"])
        self.assertEqual("satisfied", result["summary"]["official_disclosure_requirement_status"])
        primary = next(item for item in result["rows"] if item.get("official_disclosure_primary"))
        self.assertTrue(primary["verified"])
        self.assertFalse(primary["score_allowed"])
        self.assertEqual("OFFICIAL_DISCLOSURE_PRIMARY", primary["evidence_grade"])

    def test_independent_original_articles_corroborate_but_do_not_verify_claim(self):
        report = {
            "issues": [
                {
                    "name": "미국장",
                    "items": [
                        {
                            "title": "미국 CPI 예상 하회, 나스닥 급등 - 매체A",
                            "source": "매체A",
                            "link": "https://news.google.com/articles/a",
                            "source_home_url": "https://media-a.test",
                            "published": "Tue, 14 Jul 2026 01:00:00 GMT",
                        },
                        {
                            "title": "미국 CPI 예상 하회, 나스닥 급등 - 매체B",
                            "source": "매체B",
                            "link": "https://news.google.com/articles/b",
                            "source_home_url": "https://media-b.test",
                            "published": "Tue, 14 Jul 2026 01:02:00 GMT",
                        },
                    ],
                }
            ]
        }

        publishers_seen = []

        def resolve(link, publisher, headline="", timeout=4.0):
            publishers_seen.append(publisher)
            suffix = "a" if str(link).endswith("/a") else "b"
            return {
                "status": "RESOLVED_ORIGINAL_URL",
                "aggregator_url": link,
                "original_url": f"https://media-{suffix}.test/article/1",
                "publisher_url": publisher,
                "original_host": f"media-{suffix}.test",
                "error": "",
            }

        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch(
            "app.stock_suite_app.load_dart_corp_code_map", return_value={}
        ), patch(
            "app.stock_suite_app._resolve_news_original_url", side_effect=resolve
        ):
            result = build_market_news_evidence(report=report, force=True)

        row = result["rows"][0]
        self.assertEqual("MULTI_SOURCE_ORIGINAL_CORROBORATED", row["evidence_grade"])
        self.assertEqual(2, row["independent_original_domain_count"])
        self.assertTrue(row["multi_source_original_corroborated"])
        self.assertFalse(row["verified"])
        self.assertFalse(row["score_allowed"])
        self.assertFalse(row["live_order_allowed"])
        self.assertEqual({"https://media-a.test", "https://media-b.test"}, set(publishers_seen))
        self.assertEqual(2, len(row["source_records"]))
        self.assertEqual(0, result["summary"]["dart_material_eligible_article_count"])
        self.assertEqual(
            "not_applicable_no_dart_eligible_article",
            result["summary"]["official_disclosure_requirement_status"],
        )

    def test_fresh_integrity_checked_external_context_adds_originals_without_score_or_order(self):
        observed_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        inbox = {
            "current_source_usable": True,
            "report_signature": "external-report-signature",
            "report": {
                "generated_at": observed_at,
                "market_context": [
                    {
                        "context_id": "CTX-MACRO-1",
                        "category": "macro_economy",
                        "detected_at": observed_at,
                        "headline": "미국 물가 둔화와 금리 기대 확대",
                        "sources": [
                            {
                                "type": "naver_news",
                                "name": "매체A",
                                "title": "미국 물가 둔화와 금리 기대 확대",
                                "url": "https://media-a.test/article/1",
                                "published_at": observed_at,
                                "original_evidence": {
                                    "canonical_url": "https://media-a.test/article/1",
                                    "fetch_status": "TITLE_SNIPPET_ONLY",
                                    "body_included": False,
                                    "body_hash": "",
                                    "body_char_count": 0,
                                },
                            },
                            {
                                "type": "naver_news",
                                "name": "매체B",
                                "title": "물가 둔화에 금리 기대 커져",
                                "url": "https://media-b.test/article/2",
                                "published_at": observed_at,
                                "original_evidence": {
                                    "canonical_url": "https://media-b.test/article/2",
                                    "fetch_status": "TITLE_SNIPPET_ONLY",
                                    "body_included": False,
                                    "body_hash": "",
                                    "body_char_count": 0,
                                },
                            },
                        ],
                    }
                ],
            },
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch(
            "app.stock_suite_app.external_signal_inbox_status", return_value=inbox
        ), patch(
            "app.stock_suite_app.load_dart_corp_code_map", return_value={}
        ):
            result = build_market_news_evidence(
                report={"issues": []},
                force=True,
                include_external_context=True,
            )

        self.assertEqual(1, result["summary"]["multi_source_original_count"])
        self.assertTrue(result["external_context_evidence"]["source_usable"])
        self.assertEqual(1, result["external_context_evidence"]["accepted_row_count"])
        self.assertEqual(2, result["external_context_evidence"]["accepted_original_url_count"])
        self.assertEqual(0, result["external_context_evidence"]["body_verified_count"])
        row = result["rows"][0]
        self.assertEqual("external_signal_market_context", row["evidence_origin"])
        self.assertEqual(2, row["independent_original_domain_count"])
        self.assertTrue(row["multi_source_original_corroborated"])
        self.assertFalse(row["verified"])
        self.assertFalse(row["score_allowed"])
        self.assertFalse(row["live_order_allowed"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_unusable_external_context_is_rejected_before_news_evidence(self):
        inbox = {
            "current_source_usable": False,
            "report_signature": "stale-report",
            "report": {
                "market_context": [
                    {
                        "headline": "신뢰하면 안 되는 외부 기사",
                        "sources": [
                            {
                                "type": "naver_news",
                                "url": "https://media-a.test/article/1",
                            }
                        ],
                    }
                ]
            },
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch(
            "app.stock_suite_app.external_signal_inbox_status", return_value=inbox
        ), patch(
            "app.stock_suite_app.load_dart_corp_code_map", return_value={}
        ):
            result = build_market_news_evidence(
                report={"issues": []},
                force=True,
                include_external_context=True,
            )

        self.assertEqual(0, result["summary"]["news_count"])
        self.assertFalse(result["external_context_evidence"]["source_usable"])
        self.assertIn(
            "external_signal_source_not_current_or_integrity_verified",
            result["external_context_evidence"]["blockers"],
        )
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_publisher_subdomains_do_not_count_as_independent_sources(self):
        report = {
            "issues": [
                {
                    "name": "반도체",
                    "items": [
                        {
                            "title": "반도체 공급계약 확대 발표 - 매체A",
                            "source": "매체A",
                            "link": "https://www.media-a.co.kr/article/1",
                            "source_home_url": "https://www.media-a.co.kr",
                            "published": "Tue, 14 Jul 2026 01:00:00 GMT",
                        },
                        {
                            "title": "반도체 공급계약 확대 발표 - 매체A 모바일",
                            "source": "매체A 모바일",
                            "link": "https://m.media-a.co.kr/article/1",
                            "source_home_url": "https://m.media-a.co.kr",
                            "published": "Tue, 14 Jul 2026 01:01:00 GMT",
                        },
                    ],
                }
            ]
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch("app.stock_suite_app.load_dart_corp_code_map", return_value={}):
            result = build_market_news_evidence(report=report, force=True)

        row = result["rows"][0]
        self.assertEqual(["media-a.co.kr"], row["independent_original_domains"])
        self.assertEqual(1, row["independent_original_domain_count"])
        self.assertFalse(row["multi_source_original_corroborated"])
        self.assertFalse(row["verified"])

    def test_same_event_from_independent_originals_is_context_only(self):
        report = {
            "issues": [
                {
                    "name": "반도체",
                    "items": [
                        {
                            "title": "SK하이닉스 급락, 반도체 투자심리 냉각 - 매체A",
                            "source": "매체A",
                            "link": "https://media-a.test/article/1",
                            "source_home_url": "https://media-a.test",
                            "published": "Tue, 14 Jul 2026 01:00:00 GMT",
                        },
                        {
                            "title": "마이크론 하락 여파에 반도체주 약세 - 매체B",
                            "source": "매체B",
                            "link": "https://media-b.test/article/2",
                            "source_home_url": "https://media-b.test",
                            "published": "Tue, 14 Jul 2026 02:00:00 GMT",
                        },
                    ],
                }
            ]
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch("app.stock_suite_app.load_dart_corp_code_map", return_value={}):
            result = build_market_news_evidence(report=report, force=True)

        article_rows = [row for row in result["rows"] if not row.get("official_disclosure_primary")]
        self.assertEqual(2, len(article_rows))
        self.assertTrue(all(row["event_level_multi_source_original_corroborated"] for row in article_rows))
        self.assertTrue(all(row["corroboration_scope"] == "event" for row in article_rows))
        self.assertTrue(all(row["evidence_grade"] == "MULTI_SOURCE_EVENT_CORROBORATED" for row in article_rows))
        self.assertTrue(all(row["verified"] is False for row in article_rows))
        self.assertTrue(all(row["score_allowed"] is False for row in article_rows))
        self.assertEqual(2, result["summary"]["event_multi_source_original_count"])

    def test_future_dart_disclosure_cannot_verify_earlier_article(self):
        report = {
            "issues": [
                {
                    "name": "반도체",
                    "items": [
                        {
                            "title": "SK하이닉스 공급계약 체결 - 매체A",
                            "source": "매체A",
                            "link": "https://media-a.test/article/1",
                            "source_home_url": "https://media-a.test",
                            "published": "Tue, 14 Jul 2026 01:00:00 GMT",
                        }
                    ],
                }
            ]
        }
        corp_map = {
            "000660": {"stock_code": "000660", "corp_code": "00164779", "name": "SK하이닉스"}
        }
        future_dart = {
            "configured": True,
            "items": [
                {
                    "report_nm": "단일판매ㆍ공급계약체결",
                    "rcept_dt": "20260715",
                    "rcept_no": "20260715000123",
                }
            ],
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch(
            "app.stock_suite_app.load_dart_corp_code_map", return_value=corp_map
        ), patch(
            "app.stock_suite_app.INTEGRATIONS.dart_disclosures", return_value=future_dart
        ):
            result = build_market_news_evidence(report=report, force=True)

        row = result["rows"][0]
        self.assertFalse(row["official_disclosure_corroborated"])
        self.assertEqual(0, row["official_disclosure_match_count"])
        self.assertEqual(-1, row["related_disclosures"][0]["date_distance_days"])
        self.assertFalse(row["related_disclosures"][0]["disclosure_available_before_or_same_day"])
        self.assertFalse(row["verified"])
        self.assertFalse(row["score_allowed"])

    def test_original_url_from_wrong_publisher_domain_is_rejected(self):
        report = {
            "issues": [
                {
                    "name": "반도체",
                    "items": [
                        {
                            "title": "반도체 공급계약 확대 - 매체A",
                            "source": "매체A",
                            "link": "https://news.google.com/articles/a",
                            "source_home_url": "https://media-a.test",
                            "published": "Tue, 14 Jul 2026 01:00:00 GMT",
                        }
                    ],
                }
            ]
        }
        mismatch = {
            "status": "RESOLVED_ORIGINAL_URL",
            "aggregator_url": "https://news.google.com/articles/a",
            "original_url": "https://different-publisher.test/article/1",
            "publisher_url": "https://media-a.test",
            "original_host": "different-publisher.test",
            "error": "",
        }
        with TemporaryDirectory() as directory, patch(
            "app.stock_suite_app.MARKET_NEWS_EVIDENCE_CACHE_FILE", Path(directory) / "news.json"
        ), patch(
            "app.stock_suite_app.load_dart_corp_code_map", return_value={}
        ), patch(
            "app.stock_suite_app._resolve_news_original_url", return_value=mismatch
        ):
            result = build_market_news_evidence(report=report, force=True)

        row = result["rows"][0]
        self.assertEqual([], row["original_source_urls"])
        self.assertEqual(1, row["publisher_domain_mismatch_count"])
        self.assertFalse(row["original_source_confirmed"])
        self.assertEqual("PUBLISHER_ATTRIBUTED", row["evidence_grade"])


if __name__ == "__main__":
    unittest.main()

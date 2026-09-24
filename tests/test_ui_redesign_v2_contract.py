import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1] / "app" / "web"


class UiRedesignV2ContractTests(unittest.TestCase):
    def test_v2_is_explicitly_opt_in_and_does_not_replace_default_ui(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        boot = (WEB_ROOT / "ui-v2" / "boot.js").read_text(encoding="utf-8")

        self.assertIn("ui-v2/boot.js", html)
        self.assertIn('get("ui") !== "v2"', boot)
        self.assertIn('document.body.dataset.uiV2 = "true"', boot)
        self.assertNotIn("MutationObserver", boot)

    def test_v2_uses_only_documented_read_only_data_contracts(self):
        source = (WEB_ROOT / "ui-v2" / "dashboard.js").read_text(encoding="utf-8")
        source_map = (Path(__file__).resolve().parents[1] / "docs" / "UI_V2_DATA_SOURCE_MAP.md").read_text(encoding="utf-8")

        for path in (
            "/api/ops/status/poll",
            "/api/kis/account",
            "/api/ops/live-performance",
            "/api/agent/staff/quick?ttl=60",
            "/api/agent/market-clock",
            "/api/agent/alerts",
            "/api/agent/screener",
            "/api/market?bars=1",
        ):
            self.assertIn(path, source)
            self.assertIn(path, source_map)
        self.assertIn("Promise.all", source)
        self.assertIn("REFRESH_MS = 30_000", source)
        self.assertIn("ACCOUNT_REFRESH_MS = 60_000", source)
        self.assertNotIn("MutationObserver", source)
        self.assertNotIn('method: "POST"', source)
        self.assertNotIn("/api/order", source)
        self.assertNotIn("/api/approval", source)
        self.assertNotIn("/api/risk", source)
        self.assertIn('document.body.dataset.uiV2 = "false"', source)

    def test_v2_never_relabels_backtest_data_as_account_history(self):
        source = (WEB_ROOT / "ui-v2" / "dashboard.js").read_text(encoding="utf-8")
        source_map = (Path(__file__).resolve().parents[1] / "docs" / "UI_V2_DATA_SOURCE_MAP.md").read_text(encoding="utf-8")

        self.assertIn("계좌 자산 시계열 데이터가 아직 없습니다.", source)
        self.assertNotIn("state.equity", source)
        self.assertIn('value === null || value === undefined || value === ""', source)
        self.assertIn("not implemented until a true account", source_map)

    def test_dashboard_contains_requested_operational_sections(self):
        source = (WEB_ROOT / "ui-v2" / "dashboard.js").read_text(encoding="utf-8")

        for label in (
            "대시보드", "AI 트레이더", "후보/추천", "매매 승인", "포트폴리오",
            "전략 연구", "백테스트", "AI 직원", "매매일지", "시스템 관제", "설정",
            "총 자산", "오늘 실현 손익", "투자중 금액", "리스크 상태", "자산 추이",
            "실시간 주요 종목", "AI 추천 후보", "승인 필요", "공지 및 시스템 알림",
        ):
            self.assertIn(label, source)

    def test_risk_approval_and_timer_states_are_semantic(self):
        source = (WEB_ROOT / "ui-v2" / "dashboard.js").read_text(encoding="utf-8")

        self.assertIn('riskTone = /BLOCK|HALT|CONFLICT|REQUIRED|차단|정지|오류/i.test(safety)', source)
        self.assertIn('classList.toggle("v2-has-pending", pending.length > 0)', source)
        self.assertIn('if (state.timer || state.clockTimer) return', source)
        self.assertIn('global.clearInterval(state.timer)', source)

    def test_1440_keeps_three_primary_columns_and_four_operational_cards(self):
        styles = (WEB_ROOT / "ui-v2" / "dashboard.css").read_text(encoding="utf-8")

        self.assertNotIn("@media (max-width: 1500px)", styles)
        self.assertIn(".v2-primary-grid { grid-template-columns: minmax(380px, 1.24fr)", styles)
        self.assertIn(".v2-operations-grid { grid-template-columns: repeat(4, minmax(0, 1fr))", styles)

    def test_visual_fixture_is_explicit_and_read_only(self):
        fixture = (WEB_ROOT / "ui-v2" / "visual-fixture.js").read_text(encoding="utf-8")
        source = (WEB_ROOT / "ui-v2" / "dashboard.js").read_text(encoding="utf-8")

        self.assertIn('params.get("ui") === "v2" && params.get("fixture") === "visual"', fixture)
        self.assertNotIn("fetch(", fixture)
        self.assertNotIn("POST", fixture)
        self.assertNotIn("/api/", fixture)
        self.assertIn("테스트 데이터", source)
        self.assertIn("테스트 데이터 · 거래 불가", source)
        self.assertIn("CodexStockUiV2VisualFixture?.get?.()", source)

    def test_v2_has_tokens_and_dashboard_only_scope(self):
        tokens = (WEB_ROOT / "ui-v2" / "tokens.css").read_text(encoding="utf-8")
        styles = (WEB_ROOT / "ui-v2" / "dashboard.css").read_text(encoding="utf-8")
        spec = (Path(__file__).resolve().parents[1] / "docs" / "UI_REDESIGN_V2_SPEC.md").read_text(encoding="utf-8")

        for token in ("--v2-bg", "--v2-surface", "--v2-accent", "--v2-profit", "--v2-loss", "--v2-warning", "--v2-danger"):
            self.assertIn(token, tokens)
        self.assertIn('body[data-ui-v2="true"]', styles)
        self.assertIn("overflow-x: hidden", styles)
        self.assertIn("dashboard-only", spec)
        self.assertIn("?ui=v2", spec)


if __name__ == "__main__":
    unittest.main()

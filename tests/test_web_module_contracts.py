import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1] / "app" / "web"


class WebModuleContractTests(unittest.TestCase):
    def test_external_engine_module_loads_before_main_app(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        module_position = html.index("external-engine-dashboard.js")
        subpage_position = html.index("workspace-subpages.js")
        app_position = html.index("app.js?v=")

        self.assertLess(module_position, subpage_position)
        self.assertLess(subpage_position, app_position)
        self.assertLess(module_position, app_position)

    def test_main_app_uses_isolated_external_engine_dashboard(self):
        app_source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        module_source = (WEB_ROOT / "external-engine-dashboard.js").read_text(encoding="utf-8")

        self.assertIn("window.CodexExternalEngineDashboard", app_source)
        self.assertIn("global.CodexExternalEngineDashboard", module_source)
        self.assertNotIn('class="external-engine-card', app_source)
        self.assertIn('class="external-engine-card', module_source)

    def test_external_engine_counts_separate_runtime_from_fresh_verification(self):
        module_source = (WEB_ROOT / "external-engine-dashboard.js").read_text(encoding="utf-8")

        self.assertIn("runtime_connected_count", module_source)
        self.assertIn("formal_connected_count", module_source)
        self.assertIn("summary.connected_count", module_source)
        self.assertIn("summary.fresh_round_trip_count", module_source)
        self.assertIn("connection_truth", module_source)

    def test_external_executor_status_is_visible_and_polled(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        app_source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        module_source = (WEB_ROOT / "external-engine-dashboard.js").read_text(encoding="utf-8")
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

        for element_id in (
            "executionSidecarCard",
            "executionSidecarBadge",
            "executionSidecarHeartbeat",
            "executionSidecarObservationBar",
            "executionSidecarCandidateBar",
            "executionSidecarOrderBoundary",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('/api/execution-sidecar/status', module_source)
        self.assertIn('renderExecutionSidecar', module_source)
        self.assertIn('loadExecutionSidecar', module_source)
        self.assertIn('setInterval(() => loadExternalEngineDashboard(true), 5000)', app_source)
        self.assertIn('.execution-sidecar-card', styles)
        self.assertIn('실주문 차단 · Shadow/Paper', module_source)

    def test_workspace_subpages_cover_every_visible_main_menu(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        app_source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        subpage_source = (WEB_ROOT / "workspace-subpages.js").read_text(encoding="utf-8")
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("workspace-subpages.js", html)
        self.assertLess(html.index('id="tickerStrip"'), html.index('id="workspaceSubviewHost"'))
        self.assertLess(html.index('id="workspaceSubviewHost"'), html.index('class="workspace-map panel"'))
        for page_id in (
            "dashboard",
            "aiTrader",
            "recommendations",
            "trading",
            "research",
            "settings",
            "capitalChallenge",
        ):
            self.assertIn(f"{page_id}: {{", subpage_source)
        self.assertIn("window.CodexStockSubpages?.init()", app_source)
        self.assertIn("window.CodexStockSubpages?.activate(pageId)", app_source)
        self.assertIn("workspace-subview-hidden", styles)
        self.assertIn("기능 설명", subpage_source)

    def test_workspace_subpages_preserve_page_state_and_accessibility(self):
        source = (WEB_ROOT / "workspace-subpages.js").read_text(encoding="utf-8")

        self.assertIn("localStorage.setItem(STORAGE_KEY", source)
        self.assertIn('aria-haspopup="true"', source)
        self.assertIn('aria-current', source)
        self.assertIn('event.key !== "Escape"', source)
        self.assertIn('document.createElement("div")', source)
        self.assertNotIn('workspace-subview-progress', source)
        self.assertNotIn('workspace-subview-prev', source)
        self.assertNotIn('workspace-subview-next', source)
        self.assertIn('data-instant-navigation="true"', source)
        self.assertIn("메뉴 <span>", source)
        self.assertIn('positionPopover(toolbar)', source)
        self.assertIn('position: fixed', (WEB_ROOT / "styles.css").read_text(encoding="utf-8"))
        self.assertIn('.workspace-subview-nav[hidden]', (WEB_ROOT / "styles.css").read_text(encoding="utf-8"))
        self.assertIn("실전 주문", source)

    def test_navigation_buttons_skip_async_run_feedback(self):
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("function isInstantNavigationButton(button)", source)
        self.assertIn("const INSTANT_NAVIGATION_SELECTOR", source)
        self.assertIn('"[data-main-chart-window]"', source)
        self.assertIn('"#priceChartZoomIn"', source)
        self.assertIn('"#priceChartPanRight"', source)
        self.assertIn("isInstantNavigationButton(button)", source)
        self.assertIn("function clearInstantNavigationRunState(root = document)", source)
        self.assertIn("clearInstantNavigationRunState();", source)
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("button[data-run-state]::before", styles)
        self.assertIn("button[data-run-state]::after", styles)
        self.assertIn("button[data-run-state] {\n  isolation: auto;\n}", styles)
        self.assertNotIn("button[data-run-state] {\n  isolation: isolate;\n  overflow: hidden;", styles)
        self.assertIn("완료 · 로그 확인", source)
        self.assertIn("실패 · 로그 확인", source)
        self.assertIn('class="workspace-last-action-progress"', source)
        self.assertIn("workspace-action-progress-running", styles)
        self.assertIn("workspace-action-progress-pending", styles)

    def test_full_chart_button_fetches_and_preserves_long_history(self):
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("/api/market/history?${params.toString()}", source)
        self.assertIn("async function ensureFullPriceChartHistory", source)
        self.assertIn('{ cache: "no-store" }', source)
        self.assertIn("전체 이력이 확장되지 않았습니다", source)
        self.assertIn("state.fullHistoryLoaded.add(symbol)", source)
        self.assertIn("if (state.fullHistoryLoaded.has(state.active))", source)
        self.assertIn("mergePriceHistory(state.active", source)
        self.assertIn("const loaded = await ensureFullPriceChartHistory(symbol)", source)
        self.assertIn("if (!loaded) return", source)

    def test_trading_judgment_uses_full_width_board_without_ticket_menu(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        source = (WEB_ROOT / "workspace-subpages.js").read_text(encoding="utf-8")
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertEqual(1, html.count('id="refreshRecommendations"'))
        self.assertIn('class="chart-judgment-board"', html)
        self.assertIn('recommendations-panel trading-record-only workspace-subview-hidden', html)
        self.assertIn('paper-panel trading-record-only workspace-subview-hidden', html)
        self.assertIn('orderbook-panel ai-internal-evidence workspace-subview-hidden', html)
        self.assertIn('minute-flow-panel ai-internal-evidence workspace-subview-hidden', html)
        self.assertIn('condition-screener-panel ai-internal-evidence workspace-subview-hidden', html)
        self.assertIn('kis-quote-balance-radar-panel ai-internal-evidence workspace-subview-hidden', html)
        self.assertIn('page.dataset.activeSubview = active.id', source)
        self.assertNotIn('group("ticket", "주문·Paper"', source)
        self.assertNotIn('group("guide", "감독 안내"', source)
        self.assertIn('trading-guide-only workspace-subview-hidden', html)
        self.assertIn('toolbar.classList.toggle("single-view", config.groups.length === 1)', source)
        self.assertIn('.workspace-subview-nav.single-view .workspace-view-menu', styles)
        self.assertIn('.chart-judgment-board', styles)
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr))', styles)
        self.assertIn('#trading .trading-record-only', styles)
        self.assertIn('#trading .ai-internal-evidence', styles)
        self.assertIn('margin-top: 570px', styles)

    def test_internal_developer_overlay_stays_above_workspace_cards(self):
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn(".internal-developer-dock {\n  position: fixed;\n  z-index: 20000;", styles)
        self.assertIn(".watchlist-panel {", styles)

    def test_release_panel_distinguishes_leaks_from_separated_runtime_records(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="friendReleaseRuntimeCount"', html)
        self.assertIn("코드/배포 유출", html)
        self.assertIn("안전 분리 기록", html)
        self.assertIn("summary.repo_private_files", source)
        self.assertIn("summary.dist_private_files", source)
        self.assertIn("summary.runtime_private_files", source)

    def test_settings_page_exposes_long_term_evidence_progress(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

        for element_id in (
            "longTermEvidenceOverall",
            "longTermEvidenceAverage",
            "longTermEvidenceNextDue",
            "longTermEvidenceRows",
            "refreshLongTermEvidence",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("/api/system/long-term-evidence-progress", source)
        self.assertIn("function renderLongTermEvidenceProgress", source)
        self.assertIn("function loadLongTermEvidenceProgress", source)
        self.assertIn(".long-term-evidence-grid", styles)
        self.assertIn("실전 주문은 실행하지 않습니다", html)

    def test_agent_console_reconnects_only_read_only_conversations(self):
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("function agentCommandCanRetry(command)", source)
        self.assertIn("AGENT_COMMAND_ACTION_PATTERN", source)
        self.assertIn("waitForAgentConsoleServer", source)
        self.assertIn("/api/system/feature-health/instant", source)
        self.assertIn("서버 재연결 중", source)
        self.assertIn("!agentCommandCanRetry(text)", source)
        for protected_action in ("매수", "매도", "주문", "자동매매", "실행"):
            self.assertIn(protected_action, source)

    def test_agent_console_behaves_as_contextual_secretary(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("코덱스스톡 비서", html)
        self.assertIn("자유롭게 말해주세요", html)
        self.assertIn("notifyAgentSecretaryButtonResult", source)
        self.assertIn("agentSecretaryConversationContext", source)
        self.assertIn("conversation_context", source)
        self.assertIn("localStorage.setItem(AGENT_SECRETARY_STORAGE_KEY", source)
        self.assertIn('button.closest("#agentConsole")', source)

    def test_background_connection_failures_are_coalesced_and_recovered(self):
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("function isAppConnectionFailure(message)", source)
        self.assertIn("function recordAppConnectionFailure(message)", source)
        self.assertIn("function scheduleAppConnectionRecoveryProbe()", source)
        self.assertIn("동일 사건 1건으로 묶었습니다", source)
        self.assertIn("본체 연결 복구 완료", source)
        self.assertIn("if (isAppConnectionFailure(message))", source)


if __name__ == "__main__":
    unittest.main()

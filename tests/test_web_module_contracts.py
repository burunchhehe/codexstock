import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1] / "app" / "web"


class WebModuleContractTests(unittest.TestCase):
    def test_external_engine_module_loads_before_main_app(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        module_position = html.index("external-engine-dashboard.js")
        subpage_position = html.index("workspace-subpages.js")
        app_position = html.index("app.js?v=20260713-navigation-no-progress")

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
        self.assertIn("isInstantNavigationButton(button)", source)
        self.assertIn("function clearInstantNavigationRunState(root = document)", source)
        self.assertIn("clearInstantNavigationRunState();", source)
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("button.tab[data-run-state]::after", styles)
        self.assertIn("button[data-page-jump][data-run-state]::after", styles)

    def test_release_panel_distinguishes_leaks_from_separated_runtime_records(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="friendReleaseRuntimeCount"', html)
        self.assertIn("코드/배포 유출", html)
        self.assertIn("안전 분리 기록", html)
        self.assertIn("summary.repo_private_files", source)
        self.assertIn("summary.dist_private_files", source)
        self.assertIn("summary.runtime_private_files", source)


if __name__ == "__main__":
    unittest.main()

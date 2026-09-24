import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1] / "app" / "web"


class UiRedesignV2ContractTests(unittest.TestCase):
    def test_v2_is_explicitly_opt_in_and_does_not_replace_default_ui(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        boot = (WEB_ROOT / "ui-v2" / "boot.js").read_text(encoding="utf-8")

        self.assertIn("ui-v2/boot.js", html)
        self.assertIn('params.get("ui") !== "v2"', boot)
        self.assertIn('document.body.dataset.uiV2 = "true"', boot)
        self.assertIn('document.querySelector(".app-shell")', boot)
        self.assertNotIn("observe(document.body", boot)
        self.assertIn("observer?.disconnect()", boot)

    def test_v2_layer_uses_existing_dom_and_never_issues_requests(self):
        source = (WEB_ROOT / "ui-v2" / "dashboard.js").read_text(encoding="utf-8")

        self.assertIn('sourceText("#dashEquity"', source)
        self.assertIn('sourceText("#accountPnlValue"', source)
        self.assertIn('sourceText("#accountStockValue"', source)
        self.assertIn('sourceText("#dashRisk"', source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("/api/order", source)
        self.assertNotIn("POST", source)
        self.assertIn('document.body.dataset.uiV2 = "false"', source)

    def test_v2_has_tokens_and_dashboard_only_scope(self):
        tokens = (WEB_ROOT / "ui-v2" / "tokens.css").read_text(encoding="utf-8")
        styles = (WEB_ROOT / "ui-v2" / "dashboard.css").read_text(encoding="utf-8")
        spec = (Path(__file__).resolve().parents[1] / "docs" / "UI_REDESIGN_V2_SPEC.md").read_text(encoding="utf-8")

        for token in ("--v2-bg", "--v2-surface", "--v2-accent", "--v2-profit", "--v2-loss", "--v2-warning", "--v2-danger"):
            self.assertIn(token, tokens)
        self.assertIn('body[data-ui-v2="true"]', styles)
        self.assertIn("dashboard-only", spec)
        self.assertIn("?ui=v2", spec)


if __name__ == "__main__":
    unittest.main()

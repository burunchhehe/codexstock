import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.stock_suite_app as stock_app


class RuntimeDataSeparationTests(unittest.TestCase):
    def test_recursive_audit_detects_nested_secret_without_returning_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime_root = root / "runtime"
            repo_root = root / "repo"
            nested = runtime_root / "nested"
            nested.mkdir(parents=True)
            repo_root.mkdir()
            secret_value = "abcdefghijklmnop1234567890"
            (nested / "notes.json").write_text(
                '{"api_' + 'key":"' + secret_value + '"}',
                encoding="utf-8",
            )

            with (
                patch.object(stock_app, "USER_DATA_ROOT", runtime_root),
                patch.object(stock_app, "REPO_ROOT", repo_root),
                patch.object(stock_app, "LEGACY_DATA_ROOT", repo_root / "data"),
                patch.object(stock_app, "TRADE_JOURNAL_DIR", root / "journals"),
                patch.object(stock_app, "OBSIDIAN_VAULT", root / "vault"),
            ):
                result = stock_app._runtime_data_separation_feature_probe_uncached()

        self.assertEqual("review_required", result["status"])
        self.assertEqual("recursive_inventory_tiered_content", result["scan_scope"])
        self.assertEqual(1, result["secret_content_hit_count"])
        self.assertTrue(
            any(label.endswith("notes.json:secret-like-value") for label in result["secret_content_hit_labels"])
        )
        self.assertNotIn(secret_value, str(result))

    def test_force_bypasses_runtime_separation_cache(self):
        fresh = {"ok": True, "status": "ready"}
        with (
            patch("app.stock_suite_app.load_probe_cache", return_value={"status": "cached"}) as load_cache,
            patch(
                "app.stock_suite_app._runtime_data_separation_feature_probe_uncached",
                return_value=fresh,
            ) as build,
            patch("app.stock_suite_app.save_probe_cache"),
        ):
            result = stock_app._runtime_data_separation_feature_probe(force=True)

        load_cache.assert_not_called()
        build.assert_called_once_with()
        self.assertEqual("ready", result["status"])


if __name__ == "__main__":
    unittest.main()

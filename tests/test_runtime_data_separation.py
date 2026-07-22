import tempfile
import unittest
import subprocess
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
        self.assertEqual("single_pass_os_walk", result["scan_engine"])
        self.assertGreaterEqual(result["inventory_elapsed_ms"], 0)
        self.assertGreaterEqual(result["content_scan_elapsed_ms"], 0)
        self.assertEqual(1, result["secret_content_hit_count"])
        self.assertTrue(
            any(label.endswith("notes.json:secret-like-value") for label in result["secret_content_hit_labels"])
        )
        self.assertNotIn(secret_value, str(result))

    def test_secret_named_files_are_classified_by_acl_not_name_alone(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime_root = root / "runtime"
            repo_root = root / "repo"
            runtime_root.mkdir()
            repo_root.mkdir()
            protected = runtime_root / "signal_secret"
            permissive = runtime_root / ".env"
            protected.write_text("a" * 64, encoding="ascii")
            permissive.write_text("LOCAL_ONLY=true\n", encoding="utf-8")

            def acl_result(command, **_kwargs):
                target = str(command[1])
                if target.endswith("signal_secret"):
                    output = b"TEST\\testuser:(F)\nNT AUTHORITY\\SYSTEM:(F)"
                else:
                    output = (
                        b"TEST\\testuser:(F)\nNT AUTHORITY\\SYSTEM:(F)\n"
                        b"TEST\\CodexSandboxUsers:(RX)"
                    )
                return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")

            with (
                patch.object(stock_app, "USER_DATA_ROOT", runtime_root),
                patch.object(stock_app, "REPO_ROOT", repo_root),
                patch.object(stock_app, "LEGACY_DATA_ROOT", repo_root / "data"),
                patch.object(stock_app, "TRADE_JOURNAL_DIR", root / "journals"),
                patch.object(stock_app, "OBSIDIAN_VAULT", root / "vault"),
                patch.dict(stock_app.os.environ, {"USERNAME": "testuser"}),
                patch.object(stock_app.subprocess, "run", side_effect=acl_result),
            ):
                result = stock_app._runtime_data_separation_feature_probe_uncached()

        self.assertEqual(1, result["protected_secret_artifact_count"])
        self.assertEqual(1, result["permissive_secret_artifact_count"])
        self.assertEqual(1, result["suspicious_filename_count"])
        self.assertTrue(
            any("signal_secret:private-acl" in label for label in result["protected_secret_artifact_labels"])
        )

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

    def test_force_refresh_response_returns_cached_result_without_deep_scan(self):
        cached = {
            "ok": True,
            "status": "ready",
            "summary": {"status": "ready"},
        }
        with (
            patch(
                "app.stock_suite_app._start_runtime_data_separation_refresh",
                return_value=True,
            ) as refresh,
            patch("app.stock_suite_app.load_probe_cache", return_value=cached),
            patch(
                "app.stock_suite_app._runtime_data_separation_refresh_state",
                return_value={"status": "running", "refreshing": True},
            ),
            patch(
                "app.stock_suite_app._runtime_data_separation_feature_probe_uncached"
            ) as deep_audit,
        ):
            result = stock_app._runtime_data_separation_refresh_response()

        refresh.assert_called_once_with()
        deep_audit.assert_not_called()
        self.assertTrue(result["refresh_requested"])
        self.assertTrue(result["refreshing"])
        self.assertTrue(result["background_refresh_started"])
        self.assertEqual(
            "cached_while_background_deep_audit_refreshes",
            result["health_probe_mode"],
        )

    def test_refresh_progress_is_ignored_when_no_background_audit_is_running(self):
        before = dict(stock_app.RUNTIME_DATA_SEPARATION_REFRESH_STATE)
        with patch.object(stock_app, "RUNTIME_DATA_SEPARATION_REFRESHING", False):
            stock_app._runtime_data_separation_refresh_progress(
                stage="content_scan",
                progress_pct=75,
            )
        self.assertEqual(before, stock_app.RUNTIME_DATA_SEPARATION_REFRESH_STATE)

    def test_expired_runtime_separation_cache_is_served_while_refreshing(self):
        stale = {
            "ok": True,
            "status": "ready",
            "summary": {"status": "ready"},
        }
        with (
            patch(
                "app.stock_suite_app.load_probe_cache",
                side_effect=[None, stale],
            ),
            patch(
                "app.stock_suite_app._start_runtime_data_separation_refresh",
                return_value=True,
            ) as refresh,
            patch(
                "app.stock_suite_app._runtime_data_separation_feature_probe_uncached"
            ) as deep_audit,
            patch(
                "app.stock_suite_app._runtime_data_separation_refresh_state",
                return_value={"status": "running", "refreshing": True},
            ),
        ):
            result = stock_app._runtime_data_separation_feature_probe()

        refresh.assert_called_once_with()
        deep_audit.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertTrue(result["stale"])
        self.assertTrue(result["refreshing"])
        self.assertEqual("stale_while_revalidate", result["health_probe_mode"])
        self.assertEqual("running", result["refresh_state"]["status"])

    def test_first_runtime_separation_check_returns_contract_without_waiting(self):
        contract = {
            "valid": True,
            "user_data_root": str(stock_app.USER_DATA_ROOT),
        }
        resolution = {
            "source": "verified_runtime_root_contract",
            "execution_account_independent": True,
            "contract": contract,
        }
        with (
            patch("app.stock_suite_app.load_probe_cache", side_effect=[None, None]),
            patch(
                "app.stock_suite_app.runtime_root_resolution",
                return_value=resolution,
            ),
            patch("app.stock_suite_app.is_inside", return_value=False),
            patch(
                "app.stock_suite_app._start_runtime_data_separation_refresh",
                return_value=True,
            ) as refresh,
            patch(
                "app.stock_suite_app._runtime_data_separation_feature_probe_uncached"
            ) as deep_audit,
        ):
            result = stock_app._runtime_data_separation_feature_probe()

        refresh.assert_called_once_with()
        deep_audit.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertEqual("background_audit_pending", result["status"])
        self.assertTrue(result["refreshing"])
        self.assertEqual(
            "initial_contract_then_background_deep_audit",
            result["health_probe_mode"],
        )

    def test_expired_jsonl_storage_cache_is_served_while_refreshing(self):
        stale = {
            "ok": True,
            "status": "ready_large_healthy",
            "summary": {"status": "ready_large_healthy"},
        }
        with (
            patch(
                "app.stock_suite_app.load_probe_cache",
                side_effect=[None, stale],
            ),
            patch(
                "app.stock_suite_app._start_jsonl_storage_audit_refresh",
                return_value=True,
            ) as refresh,
            patch(
                "app.stock_suite_app._jsonl_storage_feature_probe_uncached"
            ) as deep_audit,
        ):
            result = stock_app._jsonl_storage_feature_probe()

        refresh.assert_called_once_with()
        deep_audit.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertTrue(result["stale"])
        self.assertTrue(result["refreshing"])
        self.assertEqual("stale_while_revalidate", result["health_probe_mode"])

    def test_first_jsonl_storage_check_returns_metadata_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "events.jsonl").write_text('{"ok":true}\n', encoding="utf-8")
            with (
                patch.object(stock_app, "USER_DATA_ROOT", root),
                patch(
                    "app.stock_suite_app.load_probe_cache",
                    side_effect=[None, None],
                ),
                patch(
                    "app.stock_suite_app._start_jsonl_storage_audit_refresh",
                    return_value=True,
                ) as refresh,
                patch(
                    "app.stock_suite_app._jsonl_storage_feature_probe_uncached"
                ) as deep_audit,
            ):
                result = stock_app._jsonl_storage_feature_probe()

        refresh.assert_called_once_with()
        deep_audit.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertEqual("background_audit_pending", result["status"])
        self.assertEqual(1, result["jsonl_file_count"])
        self.assertEqual(
            "initial_inventory_then_background_deep_audit",
            result["health_probe_mode"],
        )


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from app.safe_update_manager import SafeUpdateManager


class SafeUpdateManagerTests(unittest.TestCase):
    def test_prepare_excludes_runtime_and_secrets_then_validates_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            (source / "app").mkdir(parents=True)
            (source / "data").mkdir()
            (source / "app" / "main.py").write_text("print('new')", encoding="utf-8")
            (source / ".env").write_text("TOKEN=secret", encoding="utf-8")
            (source / "data" / "account.json").write_text("private", encoding="utf-8")
            manager = SafeUpdateManager(root / "updates")
            staged = manager.prepare(source, release_id="R1")
            self.assertEqual(1, staged["file_count"])
            self.assertFalse(staged["secrets_included"])
            result = manager.validate("R1", [lambda path: ((path / "app/main.py").is_file(), "compile ok")])
            self.assertEqual("VALIDATED", result["status"])

    def test_market_priority_blocks_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "main.py").write_text("new", encoding="utf-8")
            manager = SafeUpdateManager(root / "updates")
            manager.prepare(source, release_id="R2")
            manager.validate("R2", [lambda _: (True, "ok")])
            with self.assertRaises(PermissionError):
                manager.activate(
                    "R2",
                    root / "live",
                    market_priority_active=True,
                    confirm="ACTIVATE_VALIDATED_UPDATE",
                )

    def test_activate_and_rollback_restore_previous_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            live = root / "live"
            source = root / "source"
            live.mkdir()
            source.mkdir()
            (live / "version.txt").write_text("old", encoding="utf-8")
            (source / "version.txt").write_text("new", encoding="utf-8")
            manager = SafeUpdateManager(root / "updates")
            manager.prepare(source, release_id="R3")
            manager.validate("R3", [lambda _: (True, "tests passed")])
            activated = manager.activate(
                "R3",
                live,
                market_priority_active=False,
                confirm="ACTIVATE_VALIDATED_UPDATE",
            )
            self.assertEqual("new", (live / "version.txt").read_text(encoding="utf-8"))
            self.assertTrue(activated["restart_required"])
            rolled_back = manager.rollback(
                "R3",
                market_priority_active=False,
                confirm="ROLLBACK_FAILED_UPDATE",
            )
            self.assertEqual("old", (live / "version.txt").read_text(encoding="utf-8"))
            self.assertEqual("ROLLED_BACK_RESTART_REQUIRED", rolled_back["status"])


if __name__ == "__main__":
    unittest.main()
